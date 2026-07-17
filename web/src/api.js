const enc = encodeURIComponent;

// Auth (Etapa 20). request() no necesita `credentials: "include"` -- la SPA se sirve desde el
// mismo origin que la API, así que el navegador ya adjunta la cookie de sesión (HttpOnly,
// SameSite=Lax) sola. La única diferencia con las demás llamadas es que un 401 aquí no es un
// error de la operación pedida sino la señal de "no hay sesión" -- ver useAuth.js.
export function authBootstrap() {
  return request("/api/auth/bootstrap");
}

export function authCrearPrimerUsuario(email, nombre, password) {
  return request("/api/auth/primer-usuario", {
    method: "POST",
    body: JSON.stringify({ email, nombre, password }),
  });
}

export function authRegistrar(email, nombre, password) {
  return request("/api/auth/registro", {
    method: "POST",
    body: JSON.stringify({ email, nombre, password }),
  });
}

export function authFijarPasswordInicial(userId, password) {
  return request("/api/auth/fijar-password-inicial", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, password }),
  });
}

export function authLogin(email, password) {
  return request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function authLogout() {
  return request("/api/auth/logout", { method: "POST" });
}

export function authYo() {
  return request("/api/auth/yo");
}

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

/** Fase 3.3: escritura cruda de lib.typ para el autoguardado (SIN versión/snapshot) --
 * distinto de guardarPlantillaLibTyp, que siempre versiona. */
export function putPlantillaLibTypContenido(slug, nombre, contenido) {
  return request(`/api/orgs/${enc(slug)}/plantillas/${enc(nombre)}/lib-typ-contenido`, {
    method: "PUT",
    body: JSON.stringify({ contenido }),
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

/** Convierte un File/Blob a su contenido base64 puro (sin el prefijo "data:...;base64,"). */
function _archivoABase64(file) {
  return new Promise((resolve, reject) => {
    const lector = new FileReader();
    lector.onload = () => resolve(String(lector.result).split(",", 2)[1] || "");
    lector.onerror = () => reject(new Error("no se pudo leer el archivo"));
    lector.readAsDataURL(file);
  });
}

/** Sube una imagen a Images/ de la plantilla (FileTreeSidebar.vue). El cuerpo viaja en JSON
 * con el contenido en base64 -- el proyecto es stdlib puro en el backend, sin parser
 * multipart/form-data ya escrito (ver api_template_archivo_subir en doctyp_web.py). */
export async function subirImagenPlantilla(slug, nombre, file) {
  const contenido_base64 = await _archivoABase64(file);
  return request(`/api/orgs/${enc(slug)}/plantillas/${enc(nombre)}/archivo`, {
    method: "POST",
    body: JSON.stringify({ nombre_archivo: file.name, contenido_base64 }),
  });
}

/** Elimina un archivo de soporte ya subido a la plantilla (p. ej. "Images/logo.png"). */
export function eliminarArchivoPlantilla(slug, nombre, ruta) {
  const partes = ruta.split("/").map(enc).join("/");
  return request(`/api/orgs/${enc(slug)}/plantillas/${enc(nombre)}/archivo/${partes}`, {
    method: "DELETE",
  });
}

/** Renombra una imagen ya subida a Images/ de la plantilla (FileTreeSidebar.vue). */
export function renombrarArchivoPlantilla(slug, nombre, ruta, nombreNuevo) {
  const partes = ruta.split("/").map(enc).join("/");
  return request(`/api/orgs/${enc(slug)}/plantillas/${enc(nombre)}/archivo/${partes}`, {
    method: "PUT",
    body: JSON.stringify({ nombre_nuevo: nombreNuevo }),
  });
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

// Invitar = agregar directo a un usuario que YA existe en el sistema (sin correo, sin paso de
// aceptación -- ver el plan de registro/invitaciones). Cualquier miembro de la organización
// puede invitar.
export function invitarMiembro(slug, email, role = "member") {
  return request(`/api/orgs/${enc(slug)}/miembros`, {
    method: "POST",
    body: JSON.stringify({ email, role }),
  });
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

/** Sube una imagen a img/ del documento (imágenes propias, distintas de Images/ que trae la
 * plantilla copiada -- ver §4 CLAUDE.md). Mismo criterio que subirImagenPlantilla. */
export async function subirImagenDoc(slug, codigo, file) {
  const contenido_base64 = await _archivoABase64(file);
  return request(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/archivo`, {
    method: "POST",
    body: JSON.stringify({ nombre_archivo: file.name, contenido_base64 }),
  });
}

/** Renombra una imagen ya subida a img/ del documento (FileTreeSidebar.vue). */
export function renombrarArchivoDoc(slug, codigo, ruta, nombreNuevo) {
  const partes = ruta.split("/").map(enc).join("/");
  return request(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/archivo/${partes}`, {
    method: "PUT",
    body: JSON.stringify({ nombre_nuevo: nombreNuevo }),
  });
}

/** Elimina un archivo de soporte ya subido al documento (p. ej. "img/foto.png"). */
export function eliminarArchivoDoc(slug, codigo, ruta) {
  const partes = ruta.split("/").map(enc).join("/");
  return request(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/archivo/${partes}`, {
    method: "DELETE",
  });
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

/** Fase 1B: {enabled, uri} -- uri es el archivo que este editor debe abrir vía LSP (el .typ
 * principal para documentos, lib.typ para plantillas -- D4, mismo criterio que la preview).
 * enabled:false si tinymist no está disponible (degrada a StreamLanguage sin LSP). */
export function getLspInfo(slug, codigo, tipo) {
  return request(`/api/lsp/info?slug=${enc(slug)}&codigo=${enc(codigo)}&tipo=${enc(tipo)}`);
}

/** Fase 1D (D5): exportación rápida vía tinymist (pdf/text/markdown -- sin versión/snapshot,
 * distinta de "Compilar"). Descarga el archivo directo en el navegador (Content-Disposition). */
export async function exportarLsp(slug, codigo, tipo, formato) {
  const res = await fetch("/api/lsp/exportar", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ slug, codigo, tipo, formato }),
  });
  if (!res.ok) {
    let mensaje = `error ${res.status}`;
    try { mensaje = (await res.json())?.error || mensaje; } catch { /* sin cuerpo JSON */ }
    throw new Error(mensaje);
  }
  const disposicion = res.headers.get("Content-Disposition") || "";
  const m = disposicion.match(/filename="([^"]+)"/);
  const nombre = m ? m[1] : `export.${formato}`;
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = nombre;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
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
