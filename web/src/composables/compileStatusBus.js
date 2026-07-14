import { ref } from "vue";

// Fase 2.1 de tinymist-implementation-plan.md (H1): el evento "compile-status" llega por SSE
// (/api/events) hasta App.vue, pero quien debe reaccionar es StatusBar.vue/TemplateEditor.vue,
// varios niveles más abajo del árbol de componentes -- mismo patrón que editorScrollToBus.js
// (Plan 15 F5), un "bus" mínimo de un solo mensaje en vez de tunelizar por cada nivel intermedio.
export const ultimoCompileStatus = ref(null);

/** Llamado desde App.vue al recibir el evento SSE. */
export function emitirCompileStatus(datos) {
  ultimoCompileStatus.value = { ...datos, _ts: Date.now() };
}
