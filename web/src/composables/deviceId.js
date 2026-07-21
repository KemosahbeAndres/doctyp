// Identificador propio de ESTE navegador/equipo, persistido en localStorage -- espejo de
// device_id_local() en doctyp_sync.py (mismo propósito: distinguir "el mismo equipo que ya
// tiene el bloqueo de edición" de "otro equipo", ver doctyp_web.py: _verificar_y_refrescar_bloqueo).
export function obtenerDeviceId() {
  let id = localStorage.getItem("doctyp_device_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("doctyp_device_id", id);
  }
  return id;
}
