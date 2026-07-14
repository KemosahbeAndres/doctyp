// Cliente Typst-WASM (Etapa 11): compila y renderiza en el navegador, reemplazando el
// mecanismo de la Etapa 8 (POST al servidor -> `typst compile` -> PDF -> <embed>). Solo la
// vista previa en vivo cambia; "Compilar" (PDF real) y las miniaturas siguen siendo
// server-side (doctyp.py: compilar_typ/generar_miniatura), sin cambios.
//
// API real de @myriaddreamin/typst.ts verificada leyendo sus .d.ts y el código compilado en
// node_modules (no está en el README): createTypstCompiler().addSource(path, texto) /
// .mapShadow(path, Uint8Array) / .compile(...); createTypstRenderer().renderToSvg({container,
// artifactContent}) (Etapa 12.1 -- antes renderToCanvas, ver más abajo).
//
// Fuentes: solo Liberation Sans, bundleada localmente (decisión del usuario -- sin depender de
// internet ni tocar la licencia de Museo Sans, que no se redistribuye). `assets: false` evita
// que loadFonts() descargue además las fuentes por defecto de typst.ts desde GitHub.
//
// Rendimiento de "primer vistazo" (informado por el usuario): la primera vez que se abre un
// documento o plantilla, la carga perezosa del WASM (compiler + renderer + fuentes) se solapa
// con la compilación del documento en sí, y el usuario espera varios segundos con el canvas en
// blanco. Dos mitigaciones, ambas en este módulo:
//   1. `precargarWasm()` -- se llama una vez al arrancar la app (main.js), en background e
//      idle, para que el WASM ya esté listo cuando el usuario abre el primer documento.
//   2. Cache de artefactos compilados (`cacheArtefactos`, clave "<slug>/<codigo>") -- guarda el
//      último `artifactContent` (formato "vector") junto con un hash del input que lo produjo.
//      `prefetch()` compila en background al pasar el mouse sobre una tarjeta en la grilla, y
//      `compilarYRenderizar()` primero intenta renderizar desde cache (instantáneo) mientras
//      re-compila en segundo plano por si el contenido cambió desde el prefetch.
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

/**
 * Calienta el compiler y el renderer WASM sin compilar nada todavía. Pensado para llamarse una
 * vez al arrancar la app, en background, para que el costo de carga del WASM no se sume al de
 * la primera compilación real cuando el usuario abre un documento.
 */
export function precargarWasm() {
  return Promise.all([getCompiler(), getRenderer()]);
}

const decoder = new TextDecoder();

// El compiler/renderer son singletons compartidos por todas las vistas previas activas; sus
// métodos (addSource/mapShadow/compile) mutan estado interno, así que dos compilaciones
// concurrentes (p. ej. el compile inmediato al montar + el debounce de 1.2s justo después,
// que en documentos grandes alcanzan a solaparse) pueden interleavarse y corromper el
// resultado. Se serializan encadenando cada llamada a la promesa de la anterior.
let colaCompilacion = Promise.resolve();

function encolar(tareaFn) {
  const tarea = colaCompilacion.then(tareaFn);
  colaCompilacion = tarea.catch(() => {}); // un rechazo no debe trabar la cola siguiente
  return tarea;
}

/** clave -> { hash, artifactContent } del último compilado exitoso de ese documento/plantilla. */
const cacheArtefactos = new Map();

function claveCache(slug, codigo) {
  return `${slug}/${codigo}`;
}

/** Hash barato (no criptográfico) del contenido + rutas de archivos, para invalidar la cache. */
function hashEntrada(mainTexto, archivos) {
  let h = 2166136261;
  const mezclar = (s) => {
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
  };
  mezclar(mainTexto);
  for (const { ruta, bytes } of archivos) {
    mezclar(ruta);
    mezclar(String(bytes.length));
  }
  return h >>> 0;
}

async function compilarSolo(compiler, mainTexto, archivos) {
  compiler.addSource("/main.typ", mainTexto);
  for (const { ruta, bytes } of archivos) {
    const path = `/${ruta}`;
    if (ruta.endsWith(".typ")) {
      compiler.addSource(path, decoder.decode(bytes));
    } else {
      compiler.mapShadow(path, bytes);
    }
  }
  return compiler.compile({
    mainFilePath: "/main.typ",
    format: "vector",
    diagnostics: "unix",
  });
}

// Etapa 12.1: renderToCanvas (Etapa 11) no deja ninguna posición-fuente en los píxeles del
// canvas. `renderToSvg` (formato "vector", mismo artefacto ya compilado) produce en cambio un
// único <svg class="typst-doc"> con un <g> hijo directo por página -- estructura confirmada
// extrayendo strings del propio typst_ts_renderer_bg.wasm (no está documentado en ningún
// .d.ts). No usamos el modo `renderDom`/`mount_dom` (viewport incremental vía
// addChangement(['new'|'diff-v1', data]) + addViewportChange(); confirmado con Playwright que
// sin ese protocolo el documento nunca se pinta, se queda en moduleInitialized=false): está
// pensado para servir actualizaciones incrementales desde un servidor en vivo, no para "aquí
// está todo el artefacto, píntalo de una vez", que es nuestro caso.
//
// Nota para la Etapa 12.2 (click-to-jump): confirmado con Playwright que NI `renderSvg` /
// `renderToSvg` (con o sin `compiler.withIncrementalServer()` + `setAttachDebugInfo(true)`) NI
// `renderDom` producen el atributo `data-span` en esta versión (0.7.x) del paquete -- solo
// aparecen `data-tid` (identidad para diffing) y `data-hint`. El script de referencia
// "typstProcessSvg" embebido en el .wasm (que sí sabe leer `data-span`) es de la demo oficial
// con un pipeline de compilación distinto (probablemente vía `typst-cli`/servidor con
// `--source-map` o equivalente, no expuesto por este wrapper npm) -- pendiente de investigar
// antes de poder implementar clic->cursor con precisión exacta.
async function renderEnContenedor(renderer, artifactContent, contenedor) {
  // `renderToSvg` (que manipula el contenedor directamente desde Rust) panickea de forma
  // reproducible en @myriaddreamin/typst-ts-renderer 0.7.x ("Option::unwrap() on a None value"
  // en render/svg.rs:132), dejando la sesión WASM corrupta. `renderSvg` (retorna el string SVG
  // completo, sin tocar el DOM desde Rust) evita ese código y funciona de forma confiable.
  const svgTexto = await renderer.renderSvg({ artifactContent });
  contenedor.innerHTML = svgTexto;
  const raiz = contenedor.querySelector("svg.typst-doc");
  if (raiz) {
    for (const hijo of raiz.children) {
      if (hijo.tagName === "g") hijo.classList.add("pagina-typst");
    }
  }

  // EXPERIMENTO TEMPORAL 12.2 (round 2): completar el protocolo real de mount_dom -- empujar
  // el artefacto vía addChangement(['new', data]) (lo que hace internamente processQueue() al
  // recibir un evento 'new'/'diff-v1', ver contrib/dom/typst-doc.mjs) en vez de solo llamar
  // addViewportChange() como en el intento anterior (que se quedaba en moduleInitialized=false).
  window.__probarRenderDom2 = async () => {
    const div = document.createElement("div");
    div.style.cssText = "position:fixed;top:0;left:0;width:600px;height:800px;background:#eee;z-index:99999;overflow:auto;";
    document.body.appendChild(div);
    const doc = await renderer.renderDom({ container: div, artifactContent });
    doc.addChangement(["new", artifactContent]);
    await new Promise((r) => setTimeout(r, 300));
    doc.addViewportChange();
    await new Promise((r) => setTimeout(r, 2000));
    const primerG = div.querySelector(".typst-dom-page");
    const atributos = new Set();
    primerG?.querySelectorAll("*").forEach((el) => {
      for (const a of el.attributes) if (a.name.startsWith("data-")) atributos.add(a.name);
    });
    return {
      atributos: [...atributos],
      htmlLen: div.innerHTML.length,
      tieneDomPage: !!primerG,
      numDomPages: div.querySelectorAll(".typst-dom-page").length,
    };
  };
}

/**
 * Compila un proyecto Typst en memoria (sin renderizar) y, si tuvo éxito, lo deja en cache
 * para que una llamada posterior a `compilarYRenderizar` con el mismo contenido renderice al
 * instante. Pensado para lanzarse en background (hover sobre una tarjeta, por ejemplo) sin
 * bloquear la UI ni requerir un `contenedor` todavía montado.
 *
 * @param {string} slug
 * @param {string} codigo
 * @param {string} mainTexto
 * @param {{ruta: string, bytes: Uint8Array}[]} archivos
 */
export function prefetch(slug, codigo, mainTexto, archivos) {
  const clave = claveCache(slug, codigo);
  const hash = hashEntrada(mainTexto, archivos);
  if (cacheArtefactos.get(clave)?.hash === hash) return Promise.resolve(); // ya en cache

  return encolar(async () => {
    // Puede haber quedado obsoleto mientras esperaba en la cola (otro prefetch/compile ganó).
    if (cacheArtefactos.get(clave)?.hash === hash) return;
    try {
      const compiler = await getCompiler();
      const { result, hasError } = await compilarSolo(compiler, mainTexto, archivos);
      if (!hasError && result) {
        cacheArtefactos.set(clave, { hash, artifactContent: result });
      }
    } catch {
      // el prefetch es una optimización silenciosa; los errores reales se ven al abrir de verdad
    }
  });
}

/**
 * Compila un proyecto Typst en memoria y lo renderiza dentro de `contenedor`. Si ya hay un
 * artefacto en cache para (slug, codigo) que coincide con el contenido actual, renderiza desde
 * cache primero (instantáneo) y evita recompilar. Si el contenido cambió, compila y actualiza
 * la cache como siempre.
 *
 * @param {string} mainTexto - contenido del `/main.typ` virtual.
 * @param {{ruta: string, bytes: Uint8Array}[]} archivos - archivos de soporte (lib.typ,
 *   Images/*, img/*): los `.typ` se agregan como fuente (texto), el resto como shadow binario.
 * @param {HTMLElement} contenedor - elemento donde se monta el SVG del documento renderizado.
 * @returns {Promise<{ok: true} | {ok: false, diagnosticos: string[]}>}
 */
export function compilarYRenderizar(args) {
  return encolar(() => _compilarYRenderizar(args));
}

async function _compilarYRenderizar({ slug, codigo, mainTexto, archivos, contenedor }) {
  const clave = slug != null && codigo != null ? claveCache(slug, codigo) : null;
  const hash = hashEntrada(mainTexto, archivos);
  const enCache = clave ? cacheArtefactos.get(clave) : null;

  const renderer = await getRenderer();

  if (enCache?.hash === hash) {
    await renderEnContenedor(renderer, enCache.artifactContent, contenedor);
    return { ok: true };
  }

  const compiler = await getCompiler();
  const { result, diagnostics, hasError } = await compilarSolo(compiler, mainTexto, archivos);

  if (hasError || !result) {
    return { ok: false, diagnosticos: diagnostics || ["Error de compilación."] };
  }

  if (clave) cacheArtefactos.set(clave, { hash, artifactContent: result });

  await renderEnContenedor(renderer, result, contenedor);
  return { ok: true };
}

/** Limpia los shadow files de un proyecto anterior (cambio de documento/plantilla). Encolado
 * junto con compilaciones/prefetches para no pisar un proyecto que otra tarea esté armando. */
export function reiniciarProyecto() {
  return encolar(async () => {
    const compiler = await getCompiler();
    compiler.resetShadow();
  });
}
