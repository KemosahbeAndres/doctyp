// Fase 1B de tinymist-implementation-plan.md: conexión LSP para un archivo editado en
// CodeEditor.vue, usando el paquete oficial @codemirror/lsp-client (D3 de la cabecera del plan
// -- verificado que cubre didOpen/didChange/didSave/didClose vía su Workspace por defecto,
// diagnósticos, completion, hover, signatureHelp, formatting, rename y jump-to-definition/
// references de una vez, sin necesitar puente manual para eso).
import { LSPClient, serverDiagnostics, hoverTooltips, serverCompletion, signatureHelp } from "@codemirror/lsp-client";
import { getLspInfo } from "../api.js";
import { abrirWebSocketLsp, crearTransporteWS, urlLsp } from "./transport.js";
import { emitirDiagnostico } from "../composables/lspDiagnosticsBus.js";

/**
 * Intenta conectar el LSP para (slug, codigo, tipo). Devuelve null si tinymist no está
 * disponible o la conexión falla -- degradación obligatoria (Fase 1B): el editor sigue
 * funcionando con el resaltado StreamLanguage de la Etapa 10, sin diagnósticos/completion/hover.
 */
export async function conectarLsp(slug, codigo, tipo) {
  let info;
  try {
    info = await getLspInfo(slug, codigo, tipo);
  } catch {
    return null;
  }
  if (!info?.enabled || !info.uri) return null;

  let ws;
  try {
    ws = await abrirWebSocketLsp(urlLsp(slug, codigo, tipo));
  } catch {
    return null;
  }

  const transport = crearTransporteWS(ws);
  const client = new LSPClient({
    extensions: [serverDiagnostics(), hoverTooltips(), serverCompletion(), signatureHelp()],
    // Los diagnósticos también se pintan en el editor vía serverDiagnostics() (arriba); este
    // handler solo extrae el conteo para el indicador de StatusBar.vue/TemplateEditor.vue --
    // devuelve `false` para que el handler propio de serverDiagnostics() también corra.
    // slug/codigo/tipo se agregan acá (no solo uri) para que StatusBar.vue/TemplateEditor.vue
    // filtren igual que compileStatusBus/editorScrollToBus, en vez de comparar URIs a mano.
    notificationHandlers: {
      "textDocument/publishDiagnostics": (_client, params) => {
        emitirDiagnostico({ slug, codigo, tipo, uri: params.uri, diagnosticos: params.diagnostics || [] });
        return false;
      },
    },
  });

  try {
    client.connect(transport);
    await client.initializing;
  } catch {
    try { ws.close(); } catch { /* ya cerrado */ }
    return null;
  }

  return {
    client,
    uri: info.uri,
    cerrar() {
      try { client.disconnect(); } catch { /* ya desconectado */ }
      try { ws.close(); } catch { /* ya cerrado */ }
    },
  };
}
