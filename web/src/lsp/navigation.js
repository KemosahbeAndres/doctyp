// Fase 1C de tinymist-implementation-plan.md: extensiones custom que @codemirror/lsp-client NO
// cubre (definition/references/rename/format sí vienen del paquete, ver CodeEditor.vue) --
// documentSymbol (outline) y workspace/symbol (quick-open) se resuelven con client.request()
// directo desde la UI (Vue, ver CodeEditor.vue); folding y selectionRange sí necesitan
// extensiones propias de CodeMirror porque foldService es SÍNCRONO (Facet que recibe una
// función (state, from, to) => rango) mientras textDocument/foldingRange es async -- se cachean
// los rangos en un StateField y se refrescan por fuera (debounce tras cada cambio).
import { StateField, StateEffect, Prec } from "@codemirror/state";
import { foldService } from "@codemirror/language";
import { keymap } from "@codemirror/view";

const setFoldRanges = StateEffect.define();

const foldRangesField = StateField.define({
  create() { return []; },
  update(rangos, tr) {
    for (const efecto of tr.effects) {
      if (efecto.is(setFoldRanges)) return efecto.value;
    }
    return rangos;
  },
});

function lineColATexto(doc, linea, col) {
  if (linea + 1 > doc.lines) return doc.length;
  const l = doc.line(linea + 1);
  return Math.min(l.from + (col ?? 0), l.to);
}

/** Extensión de folding basada en LSP: StateField con los rangos ya resueltos (async, cacheados)
 * + un foldService síncrono que los consulta. `refrescar(view)` hace la petición real y
 * actualiza el StateField -- se llama al conectar y con debounce tras cada cambio (CodeEditor.vue). */
export function crearFoldingLsp(client, uri) {
  const servicio = foldService.of((state, lineStartPos) => {
    const doc = state.doc;
    const lineaInicio = doc.lineAt(lineStartPos).number - 1; // 0-based, como LSP
    const rangos = state.field(foldRangesField, false) || [];
    const r = rangos.find((x) => x.startLine === lineaInicio);
    if (!r) return null;
    const from = lineColATexto(doc, r.startLine, r.startCharacter ?? doc.line(r.startLine + 1).length);
    const finLinea = Math.min(r.endLine, doc.lines - 1);
    const to = lineColATexto(doc, finLinea, r.endCharacter ?? doc.line(finLinea + 1).length);
    return to > from ? { from, to } : null;
  });

  async function refrescar(view) {
    try {
      const rangos = await client.request("textDocument/foldingRange", { textDocument: { uri } });
      if (!view || !Array.isArray(rangos)) return;
      view.dispatch({ effects: setFoldRanges.of(rangos) });
    } catch {
      // el servidor puede no anunciar foldingRangeProvider, o la petición puede fallar en
      // vivo (documento recién abierto, aún sincronizando) -- sin folding, no rompe el editor.
    }
  }

  return { extension: [foldRangesField, servicio], refrescar };
}

/**
 * Alt-ArrowUp/ArrowDown: expandir/contraer selección vía textDocument/selectionRange. Mantiene
 * una pila de selecciones previas en un cierre (no en StateField -- se reinicia sola en cuanto
 * el cursor se mueve por otra vía, que es el comportamiento esperado de "expand selection").
 */
export function crearSelectionRangeLsp(client, uri) {
  let pila = []; // [{from,to}, ...] de la MÁS chica a la más grande, la actual está al tope

  function limpiarSiCursorSeMovio(view) {
    const sel = view.state.selection.main;
    const tope = pila[pila.length - 1];
    if (!tope || tope.from !== sel.from || tope.to !== sel.to) pila = [];
  }

  async function expandir(view) {
    limpiarSiCursorSeMovio(view);
    if (pila.length === 0) {
      const sel = view.state.selection.main;
      const doc = view.state.doc;
      const linea = doc.lineAt(sel.head);
      let resultado;
      try {
        resultado = await client.request("textDocument/selectionRange", {
          textDocument: { uri },
          positions: [{ line: linea.number - 1, character: sel.head - linea.from }],
        });
      } catch { return false; }
      if (!resultado?.[0]) return false;
      // Aplanar la cadena parent -> hijo en un array chico->grande.
      let nodo = resultado[0];
      const cadena = [];
      while (nodo) {
        const from = lineColATexto(doc, nodo.range.start.line, nodo.range.start.character);
        const to = lineColATexto(doc, nodo.range.end.line, nodo.range.end.character);
        cadena.unshift({ from, to });
        nodo = nodo.parent;
      }
      pila = cadena;
    }
    // Elegir la primera de la pila estrictamente MÁS GRANDE que la selección actual.
    const sel = view.state.selection.main;
    const siguiente = pila.find((r) => r.from <= sel.from && r.to >= sel.to && (r.from < sel.from || r.to > sel.to));
    if (!siguiente) return false;
    view.dispatch({ selection: { anchor: siguiente.from, head: siguiente.to } });
    return true;
  }

  function contraer(view) {
    limpiarSiCursorSeMovio(view);
    const sel = view.state.selection.main;
    const idx = pila.findIndex((r) => r.from === sel.from && r.to === sel.to);
    if (idx <= 0) return false;
    const anterior = pila[idx - 1];
    view.dispatch({ selection: { anchor: anterior.from, head: anterior.to } });
    return true;
  }

  // Prec.highest: Alt-ArrowUp/Down ya están tomados por defaultKeymap (moveLineUp/moveLineDown,
  // @codemirror/commands) -- como ese keymap se registra ANTES en la lista de extensiones
  // (extensions base de CodeEditor.vue, este se agrega después vía lspCompartment), sin
  // precedencia explícita nunca ganaría. El plan pide expresamente Alt+↑/↓ para expandir/
  // contraer selección (Fase 1C); mover línea deja de estar disponible por ese atajo en este
  // editor -- trade-off consciente, no hay combinación libre que no choque con algo (Ctrl-Shift-
  // ArrowUp/Down ya los toma signatureHelp() del propio @codemirror/lsp-client, Shift-Alt-Arrow*
  // ya los toma selectSyntaxLeft/Right).
  const extension = Prec.highest(keymap.of([
    { key: "Alt-ArrowUp", run: (view) => { expandir(view); return true; } },
    { key: "Alt-ArrowDown", run: (view) => { contraer(view); return true; } },
  ]));
  return extension;
}
