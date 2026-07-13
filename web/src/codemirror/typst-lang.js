// Modo Typst liviano para CodeMirror 6 (Etapa 10). No hay paquete maduro de resaltado Typst
// para CM6 -- codemirror-lang-typst (kxxt) es experimental, usa bindings WASM sin
// documentación de uso y sin releases estables, así que en vez de depender de él escribimos
// un tokenizer simple sobre StreamLanguage (mecanismo estándar de @codemirror/language para
// modos "legacy-style", sin gramática Lezer completa). No es un parser real de Typst: solo
// resuelve lo suficiente para colorear comentarios, strings, encabezados, palabras clave y
// nombres de función/variable en modo código (#...). Sin folding/lint/autocompletado (fuera
// de alcance, ver CLAUDE.md §14 Etapa 10).
import { HighlightStyle, StreamLanguage, syntaxHighlighting } from "@codemirror/language";
import { tags as t } from "@lezer/highlight";

const KEYWORDS = new Set([
  "let", "show", "set", "import", "include", "if", "else", "for", "while",
  "return", "none", "true", "false", "and", "or", "not", "in", "as", "break", "continue",
]);

function startState() {
  return { inBlockComment: false, inCode: false, depth: 0 };
}

function token(stream, state) {
  if (state.inBlockComment) {
    if (stream.match(/^[^]*?\*\//)) {
      state.inBlockComment = false;
    } else {
      stream.skipToEnd();
    }
    return "comment";
  }
  // Una expresión de código (#...) sin paréntesis/corchetes abiertos termina al pasar de línea.
  if (state.inCode && state.depth <= 0 && stream.sol()) {
    state.inCode = false;
  }

  if (stream.match("/*")) {
    state.inBlockComment = true;
    return "comment";
  }
  if (stream.match("//")) {
    stream.skipToEnd();
    return "comment";
  }
  if (stream.match(/^"(?:[^"\\]|\\.)*"?/)) {
    return "string";
  }
  if (stream.match(/^`[^`]*`?/)) {
    return "monospace";
  }
  if (!state.inCode && stream.sol() && stream.match(/^=+(?=[ \t]|$)/)) {
    stream.skipToEnd();
    return "heading";
  }
  if (!state.inCode && stream.eat("#")) {
    state.inCode = true;
    state.depth = 0;
    if (stream.match(/^[A-Za-z_][\w-]*/)) {
      const word = stream.current().slice(1);
      return KEYWORDS.has(word) ? "keyword" : "variableName.function";
    }
    return "operator";
  }
  if (state.inCode) {
    if (stream.match(/^\d+(\.\d+)?(deg|fr|pt|mm|cm|in|em|%)?/)) {
      return "number";
    }
    if (stream.match(/^[A-Za-z_][\w-]*/)) {
      const word = stream.current();
      if (KEYWORDS.has(word)) return "keyword";
      const next = stream.peek();
      return next === "(" || next === "[" ? "variableName.function" : "variableName";
    }
    if (stream.match(/^[{(\[]/)) {
      state.depth++;
      return "bracket";
    }
    if (stream.match(/^[})\]]/)) {
      state.depth = Math.max(0, state.depth - 1);
      return "bracket";
    }
    if (stream.match(/^[,.:;]/)) {
      return "punctuation";
    }
  }
  if (stream.match(/^[^#=/"`]+/)) {
    return null;
  }
  stream.next();
  return null;
}

export const typstLanguage = StreamLanguage.define({ name: "typst", startState, token });

function buildHighlightStyle(pal) {
  return HighlightStyle.define([
    { tag: t.comment, color: pal.comment, fontStyle: "italic" },
    { tag: t.string, color: pal.string },
    { tag: t.monospace, color: pal.string },
    { tag: t.heading, color: pal.heading, fontWeight: "bold" },
    { tag: t.keyword, color: pal.keyword, fontWeight: "bold" },
    { tag: t.function(t.variableName), color: pal.function },
    { tag: t.variableName, color: pal.variable },
    { tag: t.number, color: pal.number },
    { tag: t.operator, color: pal.punctuation },
    { tag: t.punctuation, color: pal.punctuation },
    { tag: t.bracket, color: pal.punctuation },
  ]);
}

// Paleta aproximada a la de la extensión Typst de VSCode.
const PALETTE_LIGHT = {
  comment: "#6b7280", string: "#2f6bc0", heading: "#1a3d8f", keyword: "#a03daa",
  function: "#8b5a00", number: "#0a7a45", variable: "#1a1a1a", punctuation: "#6b7280",
};
const PALETTE_DARK = {
  comment: "#8b95a5", string: "#79b8ff", heading: "#7aa2ff", keyword: "#d792e0",
  function: "#e0b25a", number: "#7ee0a8", variable: "#e6e6e6", punctuation: "#9aa3b2",
};

const highlightStyleLight = buildHighlightStyle(PALETTE_LIGHT);
const highlightStyleDark = buildHighlightStyle(PALETTE_DARK);

/** Extensión de resaltado según el esquema de color activo (media query, sin toggle manual). */
export function typstHighlighting(prefersDark) {
  return syntaxHighlighting(prefersDark ? highlightStyleDark : highlightStyleLight);
}
