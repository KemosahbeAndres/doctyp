// Cliente Typst-WASM (Etapa 11): compila y renderiza a <canvas> en el navegador, reemplazando
// el mecanismo de la Etapa 8 (POST al servidor -> `typst compile` -> PDF -> <embed>). Solo la
// vista previa en vivo cambia; "Compilar" (PDF real) y las miniaturas siguen siendo
// server-side (doctyp.py: compilar_typ/generar_miniatura), sin cambios.
//
// API real de @myriaddreamin/typst.ts verificada leyendo sus .d.ts (no está en el README):
// createTypstCompiler().addSource(path, texto) / .mapShadow(path, Uint8Array) / .compile(...)
// createTypstRenderer().renderToCanvas({container, artifactContent, backgroundColor})
//
// Fuentes: solo Liberation Sans, bundleada localmente (decisión del usuario -- sin depender de
// internet ni tocar la licencia de Museo Sans, que no se redistribuye). `assets: false` evita
// que loadFonts() descargue además las fuentes por defecto de typst.ts desde GitHub.
import { createTypstCompiler, createTypstRenderer, loadFonts } from "@myriaddreamin/typst.ts";
import compilerWasm from "@myriaddreamin/typst-ts-web-compiler/pkg/typst_ts_web_compiler_bg.wasm?url";
import rendererWasm from "@myriaddreamin/typst-ts-renderer/pkg/typst_ts_renderer_bg.wasm?url";

let compilerPromise = null;
let rendererPromise = null;

function getCompiler() {
  if (!compilerPromise) {
    compilerPromise = (async () => {
      const compiler = createTypstCompiler();
      await compiler.init({
        getModule: () => compilerWasm,
        beforeBuild: [
          loadFonts(["/fonts/LiberationSans-Regular.ttf", "/fonts/LiberationSans-Bold.ttf"], {
            assets: false,
          }),
        ],
      });
      return compiler;
    })();
  }
  return compilerPromise;
}

function getRenderer() {
  if (!rendererPromise) {
    rendererPromise = (async () => {
      const renderer = createTypstRenderer();
      await renderer.init({ getModule: () => rendererWasm });
      return renderer;
    })();
  }
  return rendererPromise;
}

const decoder = new TextDecoder();

// El compiler/renderer son singletons compartidos por todas las vistas previas activas; sus
// métodos (addSource/mapShadow/compile) mutan estado interno, así que dos compilaciones
// concurrentes (p. ej. el compile inmediato al montar + el debounce de 1.2s justo después,
// que en documentos grandes alcanzan a solaparse) pueden interleavarse y corromper el
// resultado. Se serializan encadenando cada llamada a la promesa de la anterior.
let colaCompilacion = Promise.resolve();

/**
 * Compila un proyecto Typst en memoria y lo renderiza dentro de `contenedor`.
 *
 * @param {string} mainTexto - contenido del `/main.typ` virtual.
 * @param {{ruta: string, bytes: Uint8Array}[]} archivos - archivos de soporte (lib.typ,
 *   Images/*, img/*): los `.typ` se agregan como fuente (texto), el resto como shadow binario.
 * @param {HTMLElement} contenedor - elemento donde se renderizan los <canvas> por página.
 * @returns {Promise<{ok: true} | {ok: false, diagnosticos: string[]}>}
 */
export function compilarYRenderizar(args) {
  const tarea = colaCompilacion.then(() => _compilarYRenderizar(args));
  colaCompilacion = tarea.catch(() => {}); // un rechazo no debe trabar la cola siguiente
  return tarea;
}

async function _compilarYRenderizar({ mainTexto, archivos, contenedor }) {
  const compiler = await getCompiler();
  const renderer = await getRenderer();

  compiler.addSource("/main.typ", mainTexto);
  for (const { ruta, bytes } of archivos) {
    const path = `/${ruta}`;
    if (ruta.endsWith(".typ")) {
      compiler.addSource(path, decoder.decode(bytes));
    } else {
      compiler.mapShadow(path, bytes);
    }
  }

  const { result, diagnostics, hasError } = await compiler.compile({
    mainFilePath: "/main.typ",
    format: "vector",
    diagnostics: "unix",
  });

  if (hasError || !result) {
    return { ok: false, diagnosticos: diagnostics || ["Error de compilación."] };
  }

  contenedor.innerHTML = "";
  await renderer.renderToCanvas({
    container: contenedor,
    artifactContent: result,
    backgroundColor: "#ffffff",
  });
  return { ok: true };
}

/** Limpia los shadow files de un proyecto anterior (cambio de documento/plantilla). */
export async function reiniciarProyecto() {
  const compiler = await getCompiler();
  compiler.resetShadow();
}
