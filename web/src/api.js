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

export function getHistoria(slug, codigo) {
  return request(`/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/historia`);
}

export async function getVersionContenido(slug, codigo, version) {
  const data = await request(
    `/api/orgs/${enc(slug)}/documentos/${enc(codigo)}/historia/${enc(version)}/contenido`,
  );
  return data.contenido;
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
