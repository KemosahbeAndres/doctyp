<script setup>
import { ref, onMounted, onUnmounted, watch } from "vue";
import { Compartment, EditorState } from "@codemirror/state";
import { EditorView, keymap, lineNumbers } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { codeFolding, foldGutter, foldKeymap } from "@codemirror/language";
import {
  jumpToDefinitionKeymap, findReferencesKeymap, renameKeymap, formatDocument,
} from "@codemirror/lsp-client";
import { typstLanguage, typstHighlighting } from "../codemirror/typst-lang.js";
import { ultimoEditorScrollTo } from "../composables/editorScrollToBus.js";
import { conectarLsp } from "../lsp/client.js";
import { crearFoldingLsp, crearSelectionRangeLsp } from "../lsp/navigation.js";
import { crearSemanticTokens, crearInlayHints, crearDocumentColors, crearCodeActions } from "../lsp/presentation.js";

const props = defineProps({
  modelValue: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
  // Plan 15 F5: slug/codigo/tipo del recurso que este editor tiene abierto -- para filtrar el
  // evento clic→cursor (editor-scroll-to) y reaccionar solo si es de ESTE recurso, no del de
  // otra pestaña/vista. Opcionales por si algún editor no participa de clic→cursor.
  slug: { type: String, default: null },
  codigo: { type: String, default: null },
  tipo: { type: String, default: "doc" }, // "doc" | "plantilla" -- debe calzar con recurso_tipo del evento
});

const emit = defineEmits(["update:modelValue", "salto-no-editable", "clic-en-editor"]);

const host = ref(null);
let view = null;
const lspConexion = ref(null); // { client, uri, cerrar() } | null -- ver conectarLsp(). ref()
// a propósito (no `let` plano): el botón de esquema (template) necesita reaccionar cuando
// conectarLsp() resuelve de forma asíncrona tras el montaje.
let folding = null; // { extension, refrescar(view) } | null -- ver crearFoldingLsp()
let semanticTokens = null; // { extension, refrescar(view) } | null
let inlayHints = null; // { extension, refrescar(view), alternar(view) } | null
let documentColors = null; // { extension, refrescar(view) } | null
let temporizadorFolding = null;
const inlayHintsActivos = ref(true);
const editableCompartment = new Compartment();
const lspCompartment = new Compartment(); // Fase 1B: vacío hasta que conectarLsp() resuelve

// Fase 1C: outline (documentSymbol) y quick-open (workspace/symbol) -- @codemirror/lsp-client
// no los cubre, se resuelven acá con client.request() directo (ver lspConexion arriba).
const mostrarEsquema = ref(false);
const simbolos = ref([]); // [{nombre, detalle, kind, depth, from}]
const mostrarQuickOpen = ref(false);
const consultaQuickOpen = ref("");
const resultadosQuickOpen = ref([]);
let temporizadorQuickOpen = null;

// LSP SymbolKind (subconjunto usado por tinymist) -- solo para un ícono/etiqueta legible.
const KIND_ETIQUETA = {
  2: "módulo", 5: "clase", 6: "método", 12: "función", 13: "variable", 14: "constante", 15: "cadena", 23: "campo",
};

function posDesdeLsp(doc, pos) {
  if (pos.line + 1 > doc.lines) return doc.length;
  const l = doc.line(pos.line + 1);
  return Math.min(l.from + pos.character, l.to);
}

function aplanarSimbolos(items, depth, doc, out) {
  for (const s of items || []) {
    const rango = s.selectionRange || s.range;
    out.push({
      nombre: s.name,
      detalle: s.detail || KIND_ETIQUETA[s.kind] || "",
      depth,
      from: rango ? posDesdeLsp(doc, rango.start) : 0,
    });
    if (s.children?.length) aplanarSimbolos(s.children, depth + 1, doc, out);
  }
  return out;
}

function alternarInlayHints() {
  if (!view || !inlayHints) return;
  inlayHintsActivos.value = inlayHints.alternar(view);
}

async function alternarEsquema() {
  mostrarQuickOpen.value = false;
  mostrarEsquema.value = !mostrarEsquema.value;
  if (!mostrarEsquema.value || !lspConexion.value || !view) return;
  try {
    const resultado = await lspConexion.value.client.request("textDocument/documentSymbol", {
      textDocument: { uri: lspConexion.value.uri },
    });
    simbolos.value = aplanarSimbolos(resultado, 0, view.state.doc, []);
  } catch {
    simbolos.value = [];
  }
}

function saltarASimbolo(sim) {
  if (!view) return;
  view.dispatch({ selection: { anchor: sim.from }, scrollIntoView: true });
  view.focus();
  mostrarEsquema.value = false;
}

function abrirQuickOpen() {
  if (!lspConexion.value) return false;
  mostrarEsquema.value = false;
  mostrarQuickOpen.value = true;
  consultaQuickOpen.value = "";
  resultadosQuickOpen.value = [];
  return true;
}

function onQuickOpenInput() {
  if (temporizadorQuickOpen) clearTimeout(temporizadorQuickOpen);
  temporizadorQuickOpen = setTimeout(async () => {
    if (!lspConexion.value) return;
    try {
      resultadosQuickOpen.value = await lspConexion.value.client.request("workspace/symbol", {
        query: consultaQuickOpen.value,
      }) || [];
    } catch {
      resultadosQuickOpen.value = [];
    }
  }, 200);
}

function saltarAResultadoQuickOpen(r) {
  // D4: un símbolo definido en otro archivo (p. ej. lib.typ desde el editor de documentos) no
  // se abre -- mismo criterio que jumpToDefinition del paquete (workspace por defecto, sin
  // displayFile propio). Solo se salta si es del archivo que este editor edita.
  if (!view || !lspConexion.value || r.location?.uri !== lspConexion.value.uri) {
    mostrarQuickOpen.value = false;
    return;
  }
  const pos = posDesdeLsp(view.state.doc, r.location.range.start);
  view.dispatch({ selection: { anchor: pos }, scrollIntoView: true });
  view.focus();
  mostrarQuickOpen.value = false;
}

const prefersDark = window.matchMedia?.("(prefers-color-scheme: dark)").matches ?? false;

const theme = EditorView.theme({
  "&": { height: "100%", fontSize: "0.9rem" },
  ".cm-scroller": { fontFamily: "var(--mono)", lineHeight: "1.5", overflow: "auto" },
  ".cm-content": { padding: "1em 0", caretColor: "var(--text)" },
  ".cm-gutters": { backgroundColor: "var(--bg-panel)", color: "var(--text-dim)", border: "none" },
}, { dark: prefersDark });

onMounted(() => {
  view = new EditorView({
    parent: host.value,
    state: EditorState.create({
      doc: props.modelValue,
      extensions: [
        lineNumbers(),
        history(),
        codeFolding(),
        foldGutter(),
        keymap.of([...defaultKeymap, ...historyKeymap, ...foldKeymap]),
        typstLanguage,
        typstHighlighting(prefersDark),
        EditorView.lineWrapping,
        theme,
        editableCompartment.of(EditorView.editable.of(!props.disabled)),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            const value = update.state.doc.toString();
            if (value !== props.modelValue) emit("update:modelValue", value);
            // Fase 1C/1D: refrescar folding/semantic tokens/inlay hints/colores tras cada
            // cambio (debounce -- todas son peticiones de red, no se piden en cada tecla).
            if (folding || semanticTokens || inlayHints || documentColors) {
              if (temporizadorFolding) clearTimeout(temporizadorFolding);
              temporizadorFolding = setTimeout(() => {
                folding?.refrescar(view);
                semanticTokens?.refrescar(view);
                inlayHints?.refrescar(view);
                documentColors?.refrescar(view);
              }, 600);
            }
          }
        }),
        // Fase 3.2 de tinymist-implementation-plan.md: jump automático editor→preview al clic
        // (sin botón, sin atajo -- reemplaza el salto explícito de Plan 15 F6). Dispara SOLO en
        // clic de posicionamiento: una selección no vacía (arrastre, doble-clic que selecciona
        // palabra) descarta el disparo. Tipear, mover el cursor con flechas o scrollear no pasan
        // por acá -- el disparador es únicamente el evento DOM "click".
        EditorView.domEventHandlers({
          click(_ev, vista) {
            const sel = vista.state.selection.main;
            if (!sel.empty) return false;
            const linea = vista.state.doc.lineAt(sel.head);
            emit("clic-en-editor", { line: linea.number - 1, character: sel.head - linea.from });
            return false; // no consumir el evento: el posicionamiento normal sigue su curso
          },
        }),
        lspCompartment.of([]),
      ],
    }),
  });

  // Fase 1B: conexión LSP asíncrona -- el editor ya está usable con StreamLanguage (Etapa 10)
  // mientras tanto; si conectarLsp() resuelve, se agregan diagnósticos/completion/hover/
  // signatureHelp + navegación (F12 definición, Shift-F12 referencias, F2 rename -- Fase 1C,
  // ambas del paquete oficial, D4-seguras por defecto: su Workspace por defecto no abre/edita
  // archivos sin una vista activa, así que un salto a lib.typ desde el editor de documentos
  // simplemente no hace nada en vez de abrirlo). Degradación obligatoria: si falla o tinymist
  // no está disponible, el editor sigue funcionando exactamente igual que hoy.
  if (props.slug && props.codigo) {
    conectarLsp(props.slug, props.codigo, props.tipo).then((conexion) => {
      if (!conexion || !view) {
        conexion?.cerrar();
        return;
      }
      lspConexion.value = conexion;
      folding = crearFoldingLsp(conexion.client, conexion.uri);
      semanticTokens = crearSemanticTokens(conexion.client, conexion.uri);
      inlayHints = crearInlayHints(conexion.client, conexion.uri);
      documentColors = crearDocumentColors(conexion.client, conexion.uri);
      view.dispatch({
        effects: lspCompartment.reconfigure([
          conexion.client.plugin(conexion.uri, "typst"),
          keymap.of([...jumpToDefinitionKeymap, ...findReferencesKeymap, ...renameKeymap]),
          crearSelectionRangeLsp(conexion.client, conexion.uri),
          folding.extension,
          semanticTokens.extension,
          inlayHints.extension,
          documentColors.extension,
          crearCodeActions(conexion.client, conexion.uri),
          // Fase 1C: quick-open de símbolos (workspace/symbol). Ctrl+T -- no es un atajo de
          // navegador reservado en la mayoría de sistemas, a diferencia de Ctrl+O/Ctrl+N.
          // Fase 1D: formatear (Ctrl-Shift-f, pedido explícito del plan -- no el Shift-Alt-f
          // por defecto del paquete). Sin format-on-save (decisión ya tomada, invasivo).
          keymap.of([
            { key: "Ctrl-t", run: abrirQuickOpen, preventDefault: true },
            { key: "Ctrl-Shift-f", run: formatDocument, preventDefault: true },
          ]),
        ]),
      });
      folding.refrescar(view);
      semanticTokens.refrescar(view);
      inlayHints.refrescar(view);
      documentColors.refrescar(view);
    });
  }
});

watch(
  () => props.modelValue,
  (nuevo) => {
    if (!view) return;
    const actual = view.state.doc.toString();
    if (nuevo !== actual) {
      view.dispatch({ changes: { from: 0, to: actual.length, insert: nuevo } });
    }
  },
);

watch(
  () => props.disabled,
  (disabled) => {
    view?.dispatch({ effects: editableCompartment.reconfigure(EditorView.editable.of(!disabled)) });
  },
);

// Plan 15 F5: clic→cursor. El evento llega con recurso_tipo/slug/nombre + start:[fila,col]
// (0-based, confirmado en plan15_notas.md §4.1 contra el código fuente de tinymist). Se
// ignora si no es de este recurso (p. ej. un documento resolvió a lib.typ de una plantilla, o
// el usuario tiene otro documento/plantilla abierto) o si este editor no participa (slug/codigo
// no provistos, ver arriba).
watch(ultimoEditorScrollTo, (evento) => {
  if (!evento || !view || !props.slug || !props.codigo) return;
  if (evento.recurso_tipo !== props.tipo || evento.slug !== props.slug || evento.nombre !== props.codigo) return;
  // H2 (tinymist-implementation-plan.md, Fase 3.1): el clic resolvió a un archivo que este
  // editor no edita (p. ej. lib.typ desde el editor de documentos, D4) -- comportamiento
  // definitivo, no un paliativo: nunca se abre/mueve el cursor a ese otro archivo.
  if (evento.es_editable !== true) {
    emit("salto-no-editable");
    return;
  }
  if (!evento.start) return;
  const [fila, columna] = evento.start;
  const linea = view.state.doc.line(Math.min(fila + 1, view.state.doc.lines));
  const pos = Math.min(linea.from + columna, linea.to);
  view.dispatch({
    selection: { anchor: pos },
    scrollIntoView: true,
  });
  view.focus();
});

onUnmounted(() => {
  if (temporizadorFolding) clearTimeout(temporizadorFolding);
  if (temporizadorQuickOpen) clearTimeout(temporizadorQuickOpen);
  view?.destroy();
  lspConexion.value?.cerrar();
});
</script>

<template>
  <div class="code-editor-wrap">
    <div ref="host" class="code-editor-host"></div>
    <button
      v-if="lspConexion"
      class="code-editor-esquema-btn"
      title="Esquema del documento (símbolos)"
      @click="alternarEsquema"
    >≡</button>
    <button
      v-if="lspConexion"
      class="code-editor-inlay-btn"
      :title="inlayHintsActivos ? 'Ocultar pistas de parámetros' : 'Mostrar pistas de parámetros'"
      @click="alternarInlayHints"
    >{{ inlayHintsActivos ? "🏷" : "🏷̶" }}</button>
    <div v-if="mostrarEsquema" class="code-editor-panel code-editor-esquema">
      <div class="code-editor-panel-header">
        <strong>Esquema</strong>
        <button @click="mostrarEsquema = false">✕</button>
      </div>
      <div v-if="!simbolos.length" class="empty-state">Sin símbolos.</div>
      <ul v-else class="code-editor-lista-simbolos">
        <li
          v-for="(s, i) in simbolos"
          :key="i"
          :style="{ paddingLeft: `${0.6 + s.depth * 1}em` }"
          @click="saltarASimbolo(s)"
        >
          {{ s.nombre }}
          <span v-if="s.detalle" class="code-editor-simbolo-detalle">{{ s.detalle }}</span>
        </li>
      </ul>
    </div>
    <div v-if="mostrarQuickOpen" class="code-editor-panel code-editor-quickopen">
      <div class="code-editor-panel-header">
        <input
          v-model="consultaQuickOpen"
          type="text"
          placeholder="Buscar símbolo en el workspace…"
          autofocus
          @input="onQuickOpenInput"
          @keydown.escape="mostrarQuickOpen = false"
        />
        <button @click="mostrarQuickOpen = false">✕</button>
      </div>
      <div v-if="!resultadosQuickOpen.length" class="empty-state">Sin resultados.</div>
      <ul v-else class="code-editor-lista-simbolos">
        <li v-for="(r, i) in resultadosQuickOpen" :key="i" @click="saltarAResultadoQuickOpen(r)">
          {{ r.name }}
          <span class="code-editor-simbolo-detalle">{{ KIND_ETIQUETA[r.kind] || "" }}</span>
        </li>
      </ul>
    </div>
  </div>
</template>

<style>
.code-editor-wrap {
  position: relative;
  height: 100%;
  min-height: 0;
}

.code-editor-host {
  height: 100%;
  min-height: 0;
}

.code-editor-host .cm-editor {
  height: 100%;
}

.code-editor-esquema-btn {
  position: absolute;
  top: 0.5em;
  right: 0.5em;
  z-index: 5;
  opacity: 0.85;
}

.code-editor-inlay-btn {
  position: absolute;
  top: 0.5em;
  right: 3em;
  z-index: 5;
  opacity: 0.85;
}

.code-editor-panel {
  position: absolute;
  top: 0.5em;
  right: 0.5em;
  z-index: 10;
  width: min(22em, 80%);
  max-height: min(28em, 80%);
  overflow-y: auto;
  background: var(--bg-panel);
  border: 1px solid var(--border);
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
}

.code-editor-panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5em;
  padding: 0.4em 0.6em;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  background: var(--bg-panel);
}

.code-editor-panel-header input {
  flex: 1;
  font: inherit;
  background: var(--bg);
  color: var(--text);
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 0.3em 0.5em;
}

.code-editor-lista-simbolos {
  list-style: none;
  margin: 0;
  padding: 0.3em 0;
}

.code-editor-lista-simbolos li {
  padding: 0.3em 0.6em;
  cursor: pointer;
  font-family: var(--mono);
  font-size: 0.85rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.code-editor-lista-simbolos li:hover {
  background: var(--bg);
}

.code-editor-simbolo-detalle {
  color: var(--text-dim);
  margin-left: 0.5em;
  font-size: 0.8em;
}

/* Fase 1D: semantic tokens -- "pisan" (mayor especificidad, no solo orden) el color de
   StreamLanguage (Etapa 10, typst-lang.js) cuando el servidor da una clasificación más
   precisa; mismos matices ya usados por esa clasificación para no introducir una paleta
   nueva, solo refinar (p. ej. distinguir función definida por el usuario de variable). */
.cm-content .cm-lsp-comment { color: var(--text-dim); font-style: italic; }
.cm-content .cm-lsp-string { color: #98c379; }
.cm-content .cm-lsp-keyword { color: #c678dd; font-weight: 600; }
.cm-content .cm-lsp-operator { color: var(--text); }
.cm-content .cm-lsp-number,
.cm-content .cm-lsp-bool { color: #d19a66; }
.cm-content .cm-lsp-function,
.cm-content .cm-lsp-decorator { color: #61afef; }
.cm-content .cm-lsp-type,
.cm-content .cm-lsp-namespace { color: #e5c07b; }
.cm-content .cm-lsp-escape,
.cm-content .cm-lsp-link,
.cm-content .cm-lsp-ref,
.cm-content .cm-lsp-label { color: #56b6c2; }
.cm-content .cm-lsp-raw { color: #98c379; font-family: var(--mono); }
.cm-content .cm-lsp-heading,
.cm-content .cm-lsp-marker,
.cm-content .cm-lsp-term { color: #e06c75; font-weight: 600; }
.cm-content .cm-lsp-error { text-decoration: underline wavy var(--danger); }

.cm-lsp-inlay-hint {
  color: var(--text-dim);
  background: var(--bg);
  border-radius: 3px;
  padding: 0 0.3em;
  font-size: 0.8em;
  margin: 0 0.15em;
  user-select: none;
}

.cm-lsp-color-swatch {
  display: inline-block;
  width: 0.8em;
  height: 0.8em;
  border-radius: 3px;
  border: 1px solid var(--border);
  margin-right: 0.2em;
  cursor: pointer;
  vertical-align: middle;
}
</style>
