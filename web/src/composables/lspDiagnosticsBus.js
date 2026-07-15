import { ref } from "vue";

// Fase 1B de tinymist-implementation-plan.md: publishDiagnostics llega por notificación LSP
// directo al navegador (no por SSE -- a diferencia de compileStatusBus/editorScrollToBus, esto
// viaja por el WebSocket propio de /api/lsp, ver web/src/lsp/client.js).
//
// El servidor manda un publishDiagnostics POR URI, con la lista COMPLETA vigente para ese URI
// en cada aviso (no un delta) -- así que basta con reemplazar la entrada de ese URI en el mapa,
// nunca acumular entre avisos. "Actuales" = lo último que publicó el LSP para el archivo abierto,
// no un historial: si un error se corrige, el próximo publishDiagnostics ya no lo trae y
// desaparece de la lista. Se guarda como mapa (no un solo valor) para que StatusBar.vue pueda
// listar todos los diagnósticos vigentes del archivo que le interesa, no solo un conteo.
export const diagnosticosPorUri = ref(new Map());

export function emitirDiagnostico({ slug, codigo, tipo, uri, diagnosticos }) {
  const mapa = new Map(diagnosticosPorUri.value);
  mapa.set(uri, { slug, codigo, tipo, uri, diagnosticos: diagnosticos || [], _ts: Date.now() });
  diagnosticosPorUri.value = mapa;
}
