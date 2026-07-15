// Fase 1B de tinymist-implementation-plan.md: transporte WebSocket para @codemirror/lsp-client
// (paquete oficial). El backend (doctyp_web.py, _lsp_bridge) hace de puente crudo JSON-RPC
// hacia el proceso `tinymist lsp` -- acá solo se adapta un WebSocket del navegador a la forma
// `Transport` que la librería espera: `{send(string), subscribe(fn), unsubscribe(fn)}`, sin
// tocar el contenido de los mensajes (ya son JSON-RPC sin cabeceras LSP en este lado).

/** Arma la URL ws(s)://.../api/lsp?slug=&codigo=&tipo= -- mismo origen que el resto de la API. */
export function urlLsp(slug, codigo, tipo) {
  const protocolo = location.protocol === "https:" ? "wss:" : "ws:";
  const params = new URLSearchParams({ slug, codigo, tipo });
  return `${protocolo}//${location.host}/api/lsp?${params}`;
}

/** Abre el WebSocket y resuelve una vez que está listo para enviar (evento "open") -- conectar
 * el LSPClient ANTES de que esté abierto haría fallar su `initialize` inmediato. */
export function abrirWebSocketLsp(url, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    const limite = setTimeout(() => {
      ws.close();
      reject(new Error("tiempo de espera agotado conectando al LSP"));
    }, timeoutMs);
    ws.addEventListener("open", () => { clearTimeout(limite); resolve(ws); }, { once: true });
    ws.addEventListener("error", () => {
      clearTimeout(limite);
      reject(new Error("no se pudo conectar al WebSocket del LSP"));
    }, { once: true });
  });
}

/** Envuelve un WebSocket ya abierto en la forma `Transport` de @codemirror/lsp-client.
 * `onCerrado`: se llama una vez si el WS se cierra por cualquier motivo que NO sea un
 * `cerrar()` explícito del propio cliente (ver client.js) -- p. ej. el backend cerró la
 * conexión porque `tinymist lsp` cayó (doctyp_web.py: `except LspServerError: break` en
 * `_lsp_bridge`). El transporte no sabe reconectar por sí mismo; solo avisa. */
export function crearTransporteWS(ws, onCerrado) {
  const handlers = new Set();
  let cerradoPorNosotros = false;
  ws.addEventListener("message", (ev) => {
    for (const h of handlers) h(ev.data);
  });
  ws.addEventListener("close", () => {
    if (!cerradoPorNosotros && onCerrado) onCerrado();
  });
  return {
    send(mensaje) {
      if (ws.readyState !== WebSocket.OPEN) {
        throw new Error("WebSocket del LSP no está abierto");
      }
      ws.send(mensaje);
    },
    subscribe(handler) { handlers.add(handler); },
    unsubscribe(handler) { handlers.delete(handler); },
    _marcarCierreExplicito() { cerradoPorNosotros = true; },
  };
}
