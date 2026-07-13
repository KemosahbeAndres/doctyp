<script setup>
import { ref, onMounted, onUnmounted, watch } from "vue";
import { Compartment, EditorState } from "@codemirror/state";
import { EditorView, keymap, lineNumbers } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap } from "@codemirror/commands";
import { typstLanguage, typstHighlighting } from "../codemirror/typst-lang.js";

const props = defineProps({
  modelValue: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
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

onUnmounted(() => {
  view?.destroy();
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
