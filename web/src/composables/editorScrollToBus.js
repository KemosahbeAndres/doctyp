import { ref } from "vue";

// Plan 15 F5: clic→cursor. El evento "editor-scroll-to" llega por SSE (/api/events) hasta
// App.vue (donde ya vive la suscripción SSE existente, ver App.vue), pero quien debe reaccionar
// es CodeEditor.vue, varios niveles más abajo del árbol de componentes (App -> vista de
// documentos -> DocEditor -> CodeEditor). El proyecto no usa un store (Vuex/Pinia) para esto,
// así que en vez de tunelizar la prop/evento por cada nivel intermedio, este módulo expone un
// ref reactivo compartido (un "bus" mínimo de un solo mensaje) que cualquier componente puede
// importar directamente.
export const ultimoEditorScrollTo = ref(null);

/** Llamado desde App.vue al recibir el evento SSE. */
export function emitirEditorScrollTo(datos) {
  // Nueva referencia de objeto en cada emisión (incluso si el filepath/línea se repiten) para
  // que un watch() en el consumidor siempre dispare, aunque el usuario haga clic dos veces
  // seguidas sobre el mismo punto.
  ultimoEditorScrollTo.value = { ...datos, _ts: Date.now() };
}
