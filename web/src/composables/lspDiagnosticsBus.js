import { ref } from "vue";

// Fase 1B de tinymist-implementation-plan.md: publishDiagnostics llega por notificación LSP
// directo al navegador (no por SSE -- a diferencia de compileStatusBus/editorScrollToBus, esto
// viaja por el WebSocket propio de /api/lsp, ver web/src/lsp/client.js). Mismo patrón de "bus"
// mínimo de un solo mensaje que los otros dos, para que StatusBar.vue/TemplateEditor.vue puedan
// mostrar un contador de errores/avisos sin que CodeEditor.vue conozca esos componentes.
export const ultimoDiagnostico = ref(null); // { uri, diagnosticos: [...], _ts }

export function emitirDiagnostico(datos) {
  ultimoDiagnostico.value = { ...datos, _ts: Date.now() };
}
