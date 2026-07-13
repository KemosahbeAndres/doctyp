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

/** Compila el lib.typ en edición sobre un documento de muestra. Devuelve un Blob o lanza
 * Error con el mensaje de typst si falla la compilación (mismo patrón que compilarVistaPrevia). */
export async function vistaPreviaPlantilla(slug, nombre, contenido) {
  const res = await fetch(`/api/orgs/${enc(slug)}/plantillas/${enc(nombre)}/vista-previa`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contenido }),
  });
  if (!res.ok) {
    let mensaje = `error ${res.status}`;
    try {
      mensaje = (await res.json()).error || mensaje;
    } catch {
      // sin cuerpo JSON
    }
    throw new Error(mensaje);
  }
  return res.blob();
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

/** Compila el texto en edición a un PDF temporal. Devuelve un Blob (no JSON, a diferencia de
 * request()) o lanza Error con el mensaje de typst si falla la compilación. */
export async function compilarVistaPrevia(slug, codigo, contenido) {
  const res = await fetch(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/vista-previa`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contenido }),
  });
  if (!res.ok) {
    let mensaje = `error ${res.status}`;
    try {
      mensaje = (await res.json()).error || mensaje;
    } catch {
      // sin cuerpo JSON
    }
    throw new Error(mensaje);
  }
  return res.blob();
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
