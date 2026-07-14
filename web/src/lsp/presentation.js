// Fase 1D de tinymist-implementation-plan.md: presentación avanzada y refactor -- semantic
// tokens, inlay hints, document colors y code actions no los cubre @codemirror/lsp-client (a
// diferencia de diagnostics/completion/hover/signatureHelp/rename/format/jump-to-definition,
// Fase 1B/1C), así que se implementan acá con StateField + decorations, mismo patrón que
// folding (lsp/navigation.js): la petición LSP es async, se cachea el resultado y se pinta de
// forma síncrona en cada redibujado.
import { StateField, StateEffect, RangeSetBuilder } from "@codemirror/state";
import { Decoration, EditorView, WidgetType, keymap } from "@codemirror/view";

function posDesdeLsp(doc, pos) {
  if (pos.line + 1 > doc.lines) return doc.length;
  const l = doc.line(pos.line + 1);
  return Math.min(l.from + pos.character, l.to);
}

// ── Semantic tokens ─────────────────────────────────────────────────────────────────────
// "Convive con typst-lang.js" (plan): decorations con !important pisan el color de la Etapa 10
// cuando el servidor da una clasificación más precisa; el StreamLanguage sigue dando color
// inmediato al tipear mientras la respuesta del servidor (async) no ha llegado.
const TOKEN_CLASE = {
  comment: "cm-lsp-comment", string: "cm-lsp-string", keyword: "cm-lsp-keyword",
  operator: "cm-lsp-operator", number: "cm-lsp-number", function: "cm-lsp-function",
  decorator: "cm-lsp-decorator", type: "cm-lsp-type", namespace: "cm-lsp-namespace",
  bool: "cm-lsp-bool", escape: "cm-lsp-escape", link: "cm-lsp-link", raw: "cm-lsp-raw",
  label: "cm-lsp-label", ref: "cm-lsp-ref", heading: "cm-lsp-heading", marker: "cm-lsp-marker",
  term: "cm-lsp-term", error: "cm-lsp-error",
};

const setTokenDecos = StateEffect.define();
const tokenDecosField = StateField.define({
  create() { return Decoration.none; },
  update(decos, tr) {
    for (const efecto of tr.effects) if (efecto.is(setTokenDecos)) return efecto.value;
    return decos.map(tr.changes);
  },
  provide: (f) => EditorView.decorations.from(f),
});

export function crearSemanticTokens(client, uri) {
  let tokenTypes = [];
  try {
    tokenTypes = client.serverCapabilities?.semanticTokensProvider?.legend?.tokenTypes || [];
  } catch { /* sin legend -- se queda sin pintar nada, no rompe */ }

  async function refrescar(view) {
    let resultado;
    try {
      resultado = await client.request("textDocument/semanticTokens/full", { textDocument: { uri } });
    } catch { return; }
    const data = resultado?.data;
    if (!view || !Array.isArray(data)) return;
    const doc = view.state.doc;
    const builder = new RangeSetBuilder();
    let linea = 0, col = 0;
    const marcas = [];
    for (let i = 0; i + 4 < data.length + 1; i += 5) {
      const deltaLinea = data[i], deltaCol = data[i + 1], largo = data[i + 2], tipoIdx = data[i + 3];
      linea = deltaLinea === 0 ? linea : linea + deltaLinea;
      col = deltaLinea === 0 ? col + deltaCol : deltaCol;
      const nombreTipo = tokenTypes[tipoIdx];
      const clase = TOKEN_CLASE[nombreTipo];
      if (!clase) continue;
      const from = posDesdeLsp(doc, { line: linea, character: col });
      const to = Math.min(from + largo, doc.length);
      if (to > from) marcas.push({ from, to, clase });
    }
    marcas.sort((a, b) => a.from - b.from || a.to - b.to);
    for (const m of marcas) builder.add(m.from, m.to, Decoration.mark({ class: m.clase }));
    view.dispatch({ effects: setTokenDecos.of(builder.finish()) });
  }

  return { extension: tokenDecosField, refrescar };
}

// ── Inlay hints ──────────────────────────────────────────────────────────────────────────
class InlayHintWidget extends WidgetType {
  constructor(texto) { super(); this.texto = texto; }
  eq(otro) { return otro.texto === this.texto; }
  toDOM() {
    const span = document.createElement("span");
    span.className = "cm-lsp-inlay-hint";
    span.textContent = this.texto;
    return span;
  }
}

const setInlayDecos = StateEffect.define();
const inlayEnabled = StateEffect.define();
const inlayDecosField = StateField.define({
  create() { return { decos: Decoration.none, activo: true }; },
  update(estado, tr) {
    let { decos, activo } = estado;
    for (const efecto of tr.effects) {
      if (efecto.is(setInlayDecos)) decos = efecto.value;
      if (efecto.is(inlayEnabled)) activo = efecto.value;
    }
    if (tr.docChanged) decos = decos.map(tr.changes);
    return { decos, activo };
  },
  provide: (f) => EditorView.decorations.from(f, (e) => (e.activo ? e.decos : Decoration.none)),
});

export function crearInlayHints(client, uri) {
  async function refrescar(view) {
    const doc = view.state.doc;
    let resultado;
    try {
      resultado = await client.request("textDocument/inlayHint", {
        textDocument: { uri },
        range: { start: { line: 0, character: 0 }, end: { line: doc.lines - 1, character: doc.line(doc.lines).length } },
      });
    } catch { return; }
    if (!view || !Array.isArray(resultado)) return;
    const builder = new RangeSetBuilder();
    const ordenados = [...resultado].sort((a, b) => {
      const pa = posDesdeLsp(doc, a.position), pb = posDesdeLsp(doc, b.position);
      return pa - pb;
    });
    for (const h of ordenados) {
      const pos = posDesdeLsp(doc, h.position);
      const texto = typeof h.label === "string" ? h.label : (h.label || []).map((p) => p.value).join("");
      builder.add(pos, pos, Decoration.widget({ widget: new InlayHintWidget(texto), side: 1 }));
    }
    view.dispatch({ effects: setInlayDecos.of(builder.finish()) });
  }

  function alternar(view) {
    const activo = view.state.field(inlayDecosField).activo;
    view.dispatch({ effects: inlayEnabled.of(!activo) });
    return !activo;
  }

  return { extension: inlayDecosField, refrescar, alternar };
}

// ── Document colors ──────────────────────────────────────────────────────────────────────
class ColorSwatchWidget extends WidgetType {
  constructor(css, onClick) { super(); this.css = css; this.onClick = onClick; }
  eq(otro) { return otro.css === this.css; }
  toDOM() {
    const span = document.createElement("span");
    span.className = "cm-lsp-color-swatch";
    span.style.background = this.css;
    span.title = this.css;
    span.onclick = (ev) => { ev.preventDefault(); ev.stopPropagation(); this.onClick(); };
    return span;
  }
  ignoreEvent() { return false; }
}

function rgbaCss(c) {
  const r = Math.round(c.red * 255), g = Math.round(c.green * 255), b = Math.round(c.blue * 255);
  return `rgba(${r}, ${g}, ${b}, ${c.alpha})`;
}

const setColorDecos = StateEffect.define();
const colorDecosField = StateField.define({
  create() { return Decoration.none; },
  update(decos, tr) {
    for (const efecto of tr.effects) if (efecto.is(setColorDecos)) return efecto.value;
    return decos.map(tr.changes);
  },
  provide: (f) => EditorView.decorations.from(f),
});

export function crearDocumentColors(client, uri) {
  async function refrescar(view) {
    let resultado;
    try {
      resultado = await client.request("textDocument/documentColor", { textDocument: { uri } });
    } catch { return; }
    if (!view || !Array.isArray(resultado)) return;
    const doc = view.state.doc;
    const builder = new RangeSetBuilder();
    const ordenados = [...resultado].sort((a, b) => posDesdeLsp(doc, a.range.start) - posDesdeLsp(doc, b.range.start));
    for (const item of ordenados) {
      const from = posDesdeLsp(doc, item.range.start);
      const css = rgbaCss(item.color);
      builder.add(from, from, Decoration.widget({
        widget: new ColorSwatchWidget(css, () => abrirPicker(view, client, uri, item)),
        side: -1,
      }));
    }
    view.dispatch({ effects: setColorDecos.of(builder.finish()) });
  }

  async function abrirPicker(view, client, uri, item) {
    const input = document.createElement("input");
    input.type = "color";
    const c = item.color;
    const hex = (n) => Math.round(n * 255).toString(16).padStart(2, "0");
    input.value = `#${hex(c.red)}${hex(c.green)}${hex(c.blue)}`;
    input.style.position = "fixed";
    input.style.opacity = "0";
    document.body.appendChild(input);
    input.addEventListener("change", async () => {
      const hexVal = input.value;
      const r = parseInt(hexVal.slice(1, 3), 16) / 255;
      const g = parseInt(hexVal.slice(3, 5), 16) / 255;
      const b = parseInt(hexVal.slice(5, 7), 16) / 255;
      try {
        const presentaciones = await client.request("textDocument/colorPresentation", {
          textDocument: { uri },
          color: { red: r, green: g, blue: b, alpha: c.alpha },
          range: item.range,
        });
        const p = presentaciones?.[0];
        if (p) {
          const doc = view.state.doc;
          const from = posDesdeLsp(doc, item.range.start);
          const to = posDesdeLsp(doc, item.range.end);
          view.dispatch({ changes: { from, to, insert: p.label } });
        }
      } catch { /* el servidor puede no soportar colorPresentation para este caso */ }
      input.remove();
    });
    input.click();
  }

  return { extension: colorDecosField, refrescar };
}

// ── Code actions ("bombilla") ───────────────────────────────────────────────────────────
// Ctrl-. (VS Code / muchos editores): pide code actions para la línea/selección del cursor y
// las muestra en un <select> nativo temporal (sin dependencias de UI nuevas) -- se elige una
// aplicando su `edit` (WorkspaceEdit) SOLO si toca el archivo abierto (D4, mismo criterio que
// jumpToDefinition/rename del paquete: nunca se escribe a disco por fuera de la vista del
// usuario). `command`, si lo trae la acción, se filtra por la MISMA allowlist del bridge
// (doctyp_web.py) -- si no está permitido, el propio backend lo rechaza con -32601.
export function crearCodeActions(client, uri) {
  async function ejecutar(view) {
    const sel = view.state.selection.main;
    const doc = view.state.doc;
    const desde = doc.lineAt(sel.from), hasta = doc.lineAt(sel.to);
    let acciones;
    try {
      acciones = await client.request("textDocument/codeAction", {
        textDocument: { uri },
        range: {
          start: { line: desde.number - 1, character: sel.from - desde.from },
          end: { line: hasta.number - 1, character: sel.to - hasta.from },
        },
        context: { diagnostics: [] },
      });
    } catch { return true; }
    if (!acciones?.length) return true;

    const etiqueta = window.prompt(
      "Code actions disponibles (escribe el número):\n" +
      acciones.map((a, i) => `${i + 1}. ${a.title}`).join("\n"),
    );
    const idx = parseInt(etiqueta, 10) - 1;
    const accion = acciones[idx];
    if (!accion) return true;

    const edit = accion.edit;
    if (edit?.changes?.[uri]) {
      const cambios = edit.changes[uri]
        .slice()
        .sort((a, b) => posDesdeLsp(doc, b.range.start) - posDesdeLsp(doc, a.range.start));
      view.dispatch({
        changes: cambios.map((c) => ({
          from: posDesdeLsp(doc, c.range.start), to: posDesdeLsp(doc, c.range.end), insert: c.newText,
        })),
      });
    } else if (edit && Object.keys(edit.changes || {}).some((u) => u !== uri)) {
      window.alert("Esta acción modifica otro archivo (posiblemente lib.typ) -- no se aplica desde este editor.");
    }
    return true;
  }

  return keymap.of([{ key: "Ctrl-.", run: (view) => { ejecutar(view); return true; } }]);
}
