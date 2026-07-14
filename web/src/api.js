const enc = encodeURIComponent;

async function request(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  let data = null;
  try {
    data = await res.json();
  } catch {
    // respuesta sin cuerpo JSON (no debería ocurrir en /api/...)
  }
  if (!res.ok) {
    throw new Error(data?.error || `error ${res.status}`);
  }
  return data;
}

export function listOrgs() {
  return request("/api/orgs");
}

export function getOrg(slug) {
  return request(`/api/orgs/${enc(slug)}`);
}

export function crearOrg(payload) {
  return request("/api/orgs", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function activarOrg(slug) {
  return request(`/api/orgs/${enc(slug)}/activar`, { method: "POST" });
}

export function listDocs(slug) {
  return request(`/api/orgs/${enc(slug)}/documentos`);
}

export function crearDocumento(slug, payload) {
  return request(`/api/orgs/${enc(slug)}/documentos`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getTiposDocumento() {
  return request("/api/tipos-documento");
}

export function listPlantillas(slug) {
  return request(`/api/orgs/${enc(slug)}/plantillas`);
}

export function fijarPlantillaDefault(slug, nombre) {
  return request(`/api/orgs/${enc(slug)}/plantillas/${enc(nombre)}/default`, { method: "POST" });
}

export function crearPlantilla(slug, payload) {
  return request(`/api/orgs/${enc(slug)}/plantillas`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function eliminarPlantilla(slug, nombre) {
  return request(`/api/orgs/${enc(slug)}/plantillas/${enc(nombre)}`, { method: "DELETE" });
}

export async function getPlantillaLibTyp(slug, nombre) {
  const data = await request(`/api/orgs/${enc(slug)}/plantillas/${enc(nombre)}/lib-typ`);
  return data.contenido;
}

export function guardarPlantillaLibTyp(slug, nombre, contenido, mensaje) {
  return request(`/api/orgs/${enc(slug)}/plantillas/${enc(nombre)}/lib-typ`, {
    method: "PUT",
    body: JSON.stringify({ contenido, mensaje }),
  });
}

/** URL de la miniatura (page 1 del documento de muestra) para usar directo en <img src>. */
export function urlMiniaturaPlantilla(slug, nombre) {
  return `/api/orgs/${enc(slug)}/plantillas/${enc(nombre)}/miniatura`;
}

/** Lista de rutas relativas de los archivos de soporte de una plantilla (Images/*, etc. --
 * excluye lib.typ, que viaja como texto en vivo). Para armar el proyecto del compilador
 * Typst-WASM en el navegador (Etapa 11). */
export function getArchivosPlantilla(slug, nombre) {
  return request(`/api/orgs/${enc(slug)}/plantillas/${enc(nombre)}/archivos`);
}

/** Bytes crudos de un archivo de soporte de una plantilla. */
export async function getArchivoPlantilla(slug, nombre, ruta) {
  const partes = ruta.split("/").map(enc).join("/");
  const res = await fetch(`/api/orgs/${enc(slug)}/plantillas/${enc(nombre)}/archivo/${partes}`);
  if (!res.ok) throw new Error(`no se pudo cargar '${ruta}' (error ${res.status})`);
  return new Uint8Array(await res.arrayBuffer());
}

/** Documento de ejemplo (build_typ + _muestra_meta, Etapa 9) usado como main.typ virtual al
 * previsualizar una plantilla. */
export async function getMuestraPlantilla(slug, nombre) {
  const data = await request(`/api/orgs/${enc(slug)}/plantillas/${enc(nombre)}/muestra`);
  return data.contenido;
}

export function getHistoriaPlantilla(slug, nombre) {
  return request(`/api/orgs/${enc(slug)}/plantillas/${enc(nombre)}/historia`);
}

export async function getVersionContenidoPlantilla(slug, nombre, version) {
  const data = await request(
    `/api/orgs/${enc(slug)}/plantillas/${enc(nombre)}/historia/${enc(version)}/contenido`,
  );
  return data.contenido;
}

export function listEquipos(slug) {
  return request(`/api/orgs/${enc(slug)}/equipos`);
}

export function crearEquipo(slug, payload) {
  return request(`/api/orgs/${enc(slug)}/equipos`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function editarEquipo(slug, id, payload) {
  return request(`/api/orgs/${enc(slug)}/equipos/${enc(id)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function eliminarEquipo(slug, id) {
  return request(`/api/orgs/${enc(slug)}/equipos/${enc(id)}`, { method: "DELETE" });
}

export function listAutores(slug) {
  return request(`/api/orgs/${enc(slug)}/autores`);
}

export function crearAutor(slug, payload) {
  return request(`/api/orgs/${enc(slug)}/autores`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function editarAutor(slug, id, payload) {
  return request(`/api/orgs/${enc(slug)}/autores/${enc(id)}`, {
    method: "PUT",
    body: JSON.stringify(payload),
  });
}

export function eliminarAutor(slug, id) {
  return request(`/api/orgs/${enc(slug)}/autores/${enc(id)}`, { method: "DELETE" });
}

export function activarAutor(slug, id) {
  return request(`/api/orgs/${enc(slug)}/autores/${enc(id)}/activar`, { method: "POST" });
}

export function getDoc(slug, codigo) {
  return request(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}`);
}

export async function getTyp(slug, codigo) {
  const data = await request(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/typ`);
  return data.contenido;
}

export function putTyp(slug, codigo, contenido) {
  return request(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/typ`, {
    method: "PUT",
    body: JSON.stringify({ contenido }),
  });
}

export function getMetaDoc(slug, codigo) {
  return request(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/meta`);
}

export function putMetaDoc(slug, codigo, cambios) {
  return request(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/meta`, {
    method: "PUT",
    body: JSON.stringify(cambios),
  });
}

export function getHistoria(slug, codigo) {
  return request(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/historia`);
}

export async function getVersionContenido(slug, codigo, version) {
  const data = await request(
    `/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/historia/${enc(version)}/contenido`,
  );
  return data.contenido;
}

export function getVersionDiff(slug, codigo, version) {
  return request(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/historia/${enc(version)}/diff`);
}

/** URL de la miniatura (page 1) para usar directo en <img src>. */
export function urlMiniatura(slug, codigo) {
  return `/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/miniatura`;
}

/** Lista de rutas relativas de los archivos de soporte de un documento (Images/*, img/*,
 * lib.typ -- excluye el .typ principal, que viaja como texto en vivo). Para armar el proyecto
 * del compilador Typst-WASM en el navegador (Etapa 11). */
export function getArchivosDoc(slug, codigo) {
  return request(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/archivos`);
}

/** Bytes crudos de un archivo de soporte de un documento. */
export async function getArchivoDoc(slug, codigo, ruta) {
  const partes = ruta.split("/").map(enc).join("/");
  const res = await fetch(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/archivo/${partes}`);
  if (!res.ok) throw new Error(`no se pudo cargar '${ruta}' (error ${res.status})`);
  return new Uint8Array(await res.arrayBuffer());
}

export function guardarVersion(slug, codigo, mensaje) {
  return request(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/save`, {
    method: "POST",
    body: JSON.stringify({ mensaje }),
  });
}

export function compilar(slug, codigo, mensaje) {
  return request(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/compile`, {
    method: "POST",
    body: JSON.stringify({ mensaje }),
  });
}

/** Plan 15 F3: arranca/reutiliza la vista previa vía tinymist para (slug, codigo) y devuelve
 * {enabled, static_url} -- enabled:false si tinymist no está disponible (modo legacy). */
export function getPreviewInfo(slug, codigo) {
  return request(`/api/preview/info?slug=${enc(slug)}&codigo=${enc(codigo)}`);
}

/** Plan 15 F6: recompila el contenido no guardado en el subproceso de preview (sin tocar
 * disco). {ok:false} si la preview de este documento no está activa -- no es un error. */
export function actualizarMemoriaPreview(slug, codigo, contenido) {
  return request("/api/preview/memory", {
    method: "POST",
    body: JSON.stringify({ slug, codigo, contenido }),
  });
}

/** Plan 15 F6: salto explícito cursor->preview. line/character son 0-based (mismo criterio
 * que editorScrollTo). {ok:false} si la preview no está activa o la posición no resuelve a
 * ningún span visible (comportamiento normal del servidor, no error). */
export function saltarAPosicionPreview(slug, codigo, line, character) {
  return request("/api/preview/jump", {
    method: "POST",
    body: JSON.stringify({ slug, codigo, line, character }),
  });
}

/** Equivalentes a getPreviewInfo/actualizarMemoriaPreview/saltarAPosicionPreview, pero para
 * plantillas -- ver _asegurar_preview_plantilla en doctyp_web.py (usa el .typ de muestra
 * materializado en disco; line/character son posiciones dentro de lib.typ, el archivo que el
 * usuario edita, no el main.typ de la preview). */
export function getPreviewInfoPlantilla(slug, nombre) {
  return request(`/api/preview/plantilla/info?slug=${enc(slug)}&nombre=${enc(nombre)}`);
}

export function actualizarMemoriaPreviewPlantilla(slug, nombre, contenido) {
  return request("/api/preview/plantilla/memory", {
    method: "POST",
    body: JSON.stringify({ slug, nombre, contenido }),
  });
}

export function saltarAPosicionPreviewPlantilla(slug, nombre, line, character) {
  return request("/api/preview/plantilla/jump", {
    method: "POST",
    body: JSON.stringify({ slug, nombre, line, character }),
  });
}

/** Se suscribe a /api/events (SSE). Devuelve una función para cancelar la suscripción. */
export function suscribirEventos(onEvento) {
  const fuente = new EventSource("/api/events");
  fuente.onmessage = (msg) => {
    try {
      onEvento(JSON.parse(msg.data));
    } catch {
      // pings (": ping") u otros mensajes no-JSON se ignoran
    }
  };
  return () => fuente.close();
}
