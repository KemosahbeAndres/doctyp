<script setup>
import { ref, onMounted, onUnmounted, watch } from "vue";
import { Compartment, EditorState } from "@codemirror/state";
import { EditorView, keymap, lineNumbers } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { typstLanguage, typstHighlighting } from "../codemirror/typst-lang.js";
import { ultimoEditorScrollTo } from "../composables/editorScrollToBus.js";

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

const emit = defineEmits(["update:modelValue"]);

const host = ref(null);
let view = null;
const editableCompartment = new Compartment();

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
        keymap.of([...defaultKeymap, ...historyKeymap]),
        typstLanguage,
        typstHighlighting(prefersDark),
        EditorView.lineWrapping,
        theme,
        editableCompartment.of(EditorView.editable.of(!props.disabled)),
        EditorView.updateListener.of((update) => {
          if (update.docChanged) {
            const value = update.state.doc.toString();
            if (value !== props.modelValue) emit("update:modelValue", value);
          }
        }),
      ],
    }),
  });
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
  view?.destroy();
});

// Plan 15 F6: expone la posición actual del cursor (línea/columna 0-based, mismo criterio que
// editorScrollTo) para el salto explícito editor→preview.
defineExpose({
  getPosicionCursor: () => {
    if (!view) return null;
    const pos = view.state.selection.main.head;
    const linea = view.state.doc.lineAt(pos);
    return { line: linea.number - 1, character: pos - linea.from };
  },
});
</script>

<template>
  <div ref="host" class="code-editor-host"></div>
</template>

<style>
.code-editor-host {
  height: 100%;
  min-height: 0;
}

.code-editor-host .cm-editor {
  height: 100%;
}
</style>
