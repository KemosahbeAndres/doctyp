#!/usr/bin/env python3
"""
doctyp_sync — cuenta remota + sincronización bidireccional CLI↔servidor (`doctyp login`/
`logout`/`sync`).

Cliente HTTP mínimo sobre `urllib.request` (stdlib, sin dependencias externas -- mismo
principio que ya aplica `doctyp_ws_client.py` para WebSocket): reutiliza los endpoints ya
existentes de `doctyp_web.py` (login, listado de orgs, lectura de archivos) más los agregados
para esto (`GET .../sync/manifiesto`, `POST .../documentos/<codigo>/sync`,
`POST .../plantillas/<nombre>/sync`).

La URL del servidor es fija (no configurable por el usuario -- decisión explícita): la única
vía de escape es DOCTYP_REMOTE_HOST_OVERRIDE, sin documentar al usuario final, exclusivamente
para pruebas automatizadas (mismo patrón que DOCTYP_DOCS_ROOT/DOCTYP_ORGS_DIR).
"""
from __future__ import annotations
import base64
import datetime
import hashlib
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

import doctyp as core

EventoSync = Callable[[dict], None]

DOCTYP_REMOTE_HOST = os.environ.get("DOCTYP_REMOTE_HOST_OVERRIDE") or "https://doctyp.tinorte.cl"


class SyncError(Exception):
    def __init__(self, mensaje: str, status: int | None = None):
        super().__init__(mensaje)
        self.status = status


# ── Cliente HTTP ───────────────────────────────────────────────────────────────────────────

def _url(ruta: str) -> str:
    return f"{DOCTYP_REMOTE_HOST.rstrip('/')}{ruta}"


def _peticion(metodo: str, ruta: str, cookie: str | None = None, cuerpo: dict | None = None,
              timeout: float = 20.0):
    """Devuelve (status, headers, bytes_crudos). No decodifica JSON acá -- algunos endpoints
    (GET .../archivo/<ruta>) devuelven binario, no JSON."""
    datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
    req = urllib.request.Request(_url(ruta), data=datos, method=metodo)
    if datos is not None:
        req.add_header("Content-Type", "application/json")
    if cookie:
        req.add_header("Cookie", f"doctyp_session={cookie}")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.headers, resp.read()
    except urllib.error.HTTPError as e:
        crudo = e.read()
        mensaje = crudo.decode("utf-8", errors="replace")
        try:
            mensaje = json.loads(mensaje).get("error", mensaje)
        except (json.JSONDecodeError, AttributeError):
            pass
        raise SyncError(f"{e.code} {mensaje}", status=e.code)
    except urllib.error.URLError as e:
        raise SyncError(f"no se pudo conectar a {DOCTYP_REMOTE_HOST}: {e.reason}")
    except OSError as e:
        # Timeouts de LECTURA (servidor lento/caído a mitad de respuesta, ya conectado) llegan
        # como TimeoutError/socket.timeout crudos, NO como URLError -- urllib solo envuelve en
        # URLError los fallos ANTES de mandar la petición (h.request()); getresponse() está
        # fuera de ese try/except en la stdlib, así que un timeout leyendo la respuesta se
        # propaga tal cual. TimeoutError/ConnectionError/etc. son subclases de OSError (y
        # URLError igual lo es, pero ya la capturó la except de arriba primero).
        raise SyncError(f"se perdió la conexión con {DOCTYP_REMOTE_HOST}: {e}")


def _peticion_json(metodo: str, ruta: str, cookie: str | None = None, cuerpo: dict | None = None):
    _status, _headers, crudo = _peticion(metodo, ruta, cookie, cuerpo)
    if not crudo:
        return {}
    try:
        return json.loads(crudo.decode("utf-8"))
    except json.JSONDecodeError:
        raise SyncError("respuesta inválida del servidor (no era JSON)")


def login(email: str, password: str) -> tuple[dict, str]:
    """POST /api/auth/login -- devuelve (usuario_publico, cookie_de_sesion). No guarda nada acá
    (ver guardar_sesion): este módulo separa "hablar con el servidor" de "qué se persiste"."""
    _status, headers, crudo = _peticion(
        "POST", "/api/auth/login", cuerpo={"email": email, "password": password})
    set_cookie = headers.get("Set-Cookie")
    if not set_cookie or "doctyp_session=" not in set_cookie:
        raise SyncError("el servidor no devolvió una cookie de sesión")
    cookie = set_cookie.split("doctyp_session=", 1)[1].split(";", 1)[0]
    usuario = json.loads(crudo.decode("utf-8"))["usuario"]
    return usuario, cookie


def logout_remoto(cookie: str) -> None:
    try:
        _peticion("POST", "/api/auth/logout", cookie)
    except SyncError:
        pass  # best-effort -- cerrar sesión local no debe depender de que el servidor responda


# ── Sesión local (settings.json → local.sesion_remota) ─────────────────────────────────────

def sesion_activa() -> dict | None:
    return core.cargar_settings().get("local", {}).get("sesion_remota")


def guardar_sesion(email: str, cookie: str, orgs: list[str] | None = None) -> None:
    email = email.strip().lower()
    settings = core.cargar_settings()
    settings.setdefault("local", {})["sesion_remota"] = {
        "email": email, "cookie": cookie, "orgs": orgs or [],
    }
    _recordar_correo(settings, email)
    core.guardar_settings(settings)


def _recordar_correo(settings: dict, email: str) -> None:
    """Upsert en settings.json → local.correos_conocidos -- SOLO el correo y cuándo se usó por
    última vez, sin cookie (a diferencia de sesion_remota): alimenta el submenú 'Cambiar de
    usuario' del icono de bandeja (doctyp_tray.py) como un atajo para no reescribir el correo,
    NUNCA como un cambio de cuenta sin contraseña -- decisión explícita del usuario, cambiar de
    usuario siempre vuelve a pedir la clave."""
    local = settings.setdefault("local", {})
    conocidos = local.setdefault("correos_conocidos", [])
    ahora = datetime.datetime.now().isoformat(timespec="seconds")
    for entrada in conocidos:
        if entrada["email"] == email:
            entrada["ultimo_uso"] = ahora
            return
    conocidos.append({"email": email, "ultimo_uso": ahora})


def correos_conocidos() -> list[str]:
    """Correos que se han logueado alguna vez en este equipo (más recientes primero) -- ver
    _recordar_correo."""
    settings = core.cargar_settings()
    conocidos = settings.get("local", {}).get("correos_conocidos", [])
    return [e["email"] for e in sorted(conocidos, key=lambda e: e.get("ultimo_uso", ""), reverse=True)]


def _actualizar_orgs_sesion(orgs: list[str]) -> None:
    """sincronizar_todo() ya sabe qué organizaciones tiene la cuenta -- se refresca acá para que
    docs_root_org() (doctyp.py) siga sabiendo, sin red, a qué organizaciones les toca carpeta
    por usuario (una cuenta puede sumar/perder organizaciones entre un login y el siguiente)."""
    settings = core.cargar_settings()
    sesion = settings.get("local", {}).get("sesion_remota")
    if sesion is not None:
        sesion["orgs"] = orgs
        core.guardar_settings(settings)


def org_en_sesion(slug: str) -> bool:
    """True si `slug` es una de las organizaciones de la cuenta remota activa -- usado por
    cmd_nuevo (doctyp.py) para decidir si delega la creación al servidor."""
    sesion = sesion_activa()
    return sesion is not None and slug in (sesion.get("orgs") or [])


def borrar_sesion() -> None:
    settings = core.cargar_settings()
    settings.get("local", {}).pop("sesion_remota", None)
    core.guardar_settings(settings)


def device_id_local() -> str:
    """UUID persistido en settings.json → local.device_id, generado la primera vez que se
    necesita. Estable entre invocaciones -- lo que distingue a ESTE equipo de otro para el
    bloqueo de edición del servidor (ver doctyp_web.py: _verificar_y_refrescar_bloqueo)."""
    import uuid
    settings = core.cargar_settings()
    local = settings.setdefault("local", {})
    if not local.get("device_id"):
        local["device_id"] = uuid.uuid4().hex
        core.guardar_settings(settings)
    return local["device_id"]


# ── Archivos: listar local / bajar / subir ──────────────────────────────────────────────────

def _listar_archivos_locales(carpeta: Path) -> list[str]:
    """Mismo criterio de exclusión que _listar_archivos_carpeta en doctyp_web.py (.snapshots/,
    ocultos, .pdf) pero SIN excluir el .typ/lib.typ principal -- acá viaja junto con el resto en
    un solo POST .../sync, a diferencia del navegador (que lo pide aparte como texto)."""
    if not carpeta.is_dir():
        return []
    out = []
    for p in carpeta.rglob("*"):
        if not p.is_file() or p.suffix.lower() == ".pdf":
            continue
        rel = p.relative_to(carpeta)
        partes = rel.parts
        if partes[0] == core.SNAPSHOTS_DIRNAME or any(parte.startswith(".") for parte in partes):
            continue
        out.append(rel.as_posix())
    return sorted(out)


def _bajar_carpeta(cookie: str, ruta_archivos: str, ruta_archivo_tpl: str, carpeta: Path,
                    principal_rel: str, principal_ruta: str) -> None:
    """Descarga completa: el archivo principal (.typ/lib.typ, vía su endpoint de texto propio)
    más el resto del árbol (vía la lista de archivos + uno por uno). Usado tanto para
    documentos como para plantillas -- ambos exponen el mismo par de endpoints genéricos desde
    la Etapa 11 (api_doc_archivos/api_template_archivos)."""
    carpeta.mkdir(parents=True, exist_ok=True)
    contenido = _peticion_json("GET", principal_ruta, cookie)["contenido"]
    core._escribir_texto_atomico(carpeta / principal_rel, contenido)
    for rel in _peticion_json("GET", ruta_archivos, cookie):
        rel_codificado = "/".join(urllib.parse.quote(parte) for parte in rel.split("/"))
        _status, _headers, datos = _peticion("GET", f"{ruta_archivo_tpl}/{rel_codificado}", cookie)
        destino = carpeta / rel
        destino.parent.mkdir(parents=True, exist_ok=True)
        core._escribir_bytes_atomico(destino, datos)


def _subir_carpeta(cookie: str, ruta_sync: str, carpeta: Path,
                    renombrados: list[dict] | None = None) -> None:
    """`renombrados` ([{'de', 'a'}], opcional) son pares detectados por _detectar_renombres --
    el servidor los aplica como Path.rename() puro (api_doc_sync, doctyp_web.py) ANTES de
    escribir `archivos`, así que el destino ('a') se excluye de `archivos` acá: su contenido no
    cambió, solo el nombre, no hace falta retransferir los bytes."""
    renombrados = renombrados or []
    excluir = {p["a"] for p in renombrados}
    archivos = {}
    for rel in _listar_archivos_locales(carpeta):
        if rel in excluir:
            continue
        archivos[rel] = base64.b64encode((carpeta / rel).read_bytes()).decode("ascii")
    if not archivos and not renombrados:
        return
    _peticion_json("POST", ruta_sync, cookie,
                    {"archivos": archivos, "renombrados": renombrados, "device_id": device_id_local()})


def _hash_carpeta(carpeta: Path) -> str | None:
    """Espejo exacto de _hash_carpeta en doctyp_web.py, sobre el mismo listado que ya usa
    _subir_carpeta (_listar_archivos_locales -- ya incluye el .typ/lib.typ principal, mismas
    exclusiones que el servidor) -- contenido idéntico produce el mismo hash en ambos lados."""
    archivos = _listar_archivos_locales(carpeta)
    if not archivos:
        return None
    h = hashlib.sha256()
    for rel in archivos:
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256((carpeta / rel).read_bytes()).digest())
    return h.hexdigest()


def _hashes_por_archivo_local(carpeta: Path) -> dict[str, str]:
    """Espejo cliente de _hashes_por_archivo en doctyp_web.py -- sha256 por archivo (ruta
    relativa → hex), mismo listado que _listar_archivos_locales. Base de la detección de
    renombres por contenido (ver _detectar_renombres)."""
    return {rel: hashlib.sha256((carpeta / rel).read_bytes()).hexdigest()
            for rel in _listar_archivos_locales(carpeta)}


def _detectar_renombres(locales: dict[str, str], remotos: dict[str, str]) -> list[dict]:
    """Empareja por contenido (sha256) los archivos que solo existen en un lado -- mismo
    principio que usa git para detectar renombres, sin necesitar ninguna marca persistida (el
    contenido no cambió, solo el nombre, así que no hace falta rastrear identidad -- alcanza con
    comparar bytes). Devuelve pares {'local': ruta, 'remoto': ruta}; el llamador
    (sincronizar_documento) decide la dirección 'de'/'a' según quién gane el sync."""
    solo_locales = {r: h for r, h in locales.items() if r not in remotos}
    solo_remotos = {r: h for r, h in remotos.items() if r not in locales}
    por_hash_remoto: dict[str, list[str]] = {}
    for ruta, h in solo_remotos.items():
        por_hash_remoto.setdefault(h, []).append(ruta)
    pares = []
    usados: set[str] = set()
    for ruta_local, h in solo_locales.items():
        candidatos = [r for r in por_hash_remoto.get(h, []) if r not in usados]
        if candidatos:
            ruta_remota = candidatos[0]
            usados.add(ruta_remota)
            pares.append({"local": ruta_local, "remoto": ruta_remota})
    return pares


def _renombres_detectados(cookie: str, slug: str, codigo_base: str, carpeta: Path) -> list[dict]:
    """Best-effort: si el endpoint de hashes falla (servidor viejo sin el endpoint, red), no
    bloquea el sync normal -- detectar renombres es un plus, no un requisito para sincronizar."""
    try:
        remotos_hash = _peticion_json(
            "GET", f"/api/orgs/{slug}/documentos/{codigo_base}/archivos-hash", cookie)
    except SyncError:
        return []
    return _detectar_renombres(_hashes_por_archivo_local(carpeta), remotos_hash)


# ── Sincronización ───────────────────────────────────────────────────────────────────────────

def _notificar(on_evento: EventoSync | None, *, tipo: str, slug: str, nombre: str,
                accion: str, archivo_principal: Path) -> None:
    """Reporta una transferencia real (subida/bajada) a quien esté escuchando -- hoy solo el
    daemon (para el tooltip de la bandeja, ver doctyp_tray.py), pero es un callback genérico
    para no acoplar doctyp_sync.py a Qt. No-op si no hay callback (CLI actual) o si el archivo
    principal no quedó en disco por algún motivo."""
    if on_evento is None:
        return
    try:
        tamano = archivo_principal.stat().st_size
    except OSError:
        return
    on_evento({
        "tipo": tipo, "slug": slug, "nombre": nombre, "accion": accion,
        "archivo": archivo_principal.name, "tamano": tamano,
        "cuando": datetime.datetime.now(),
    })


def _respaldar_documento_perdedor(carpeta: Path, codigo_base: str) -> None:
    """El lado que pierde un conflicto (mtime más antiguo) se respalda ANTES de sobrescribir --
    nunca se descarta en silencio. No es un snapshot 'oficial' (no bumpea version: ni entra al
    índice de versiones) -- solo una copia de seguridad con nombre que se distingue de un save
    real, mismo directorio .snapshots/ que ya existe en cada documento."""
    typ_path = carpeta / f"{codigo_base}.typ"
    if not typ_path.exists():
        return
    snapshots = carpeta / core.SNAPSHOTS_DIRNAME
    snapshots.mkdir(exist_ok=True)
    marca = datetime.datetime.now().strftime("%Y%m%dT%H%M%S")
    shutil.copy2(typ_path, snapshots / f"{codigo_base}_conflicto-sync_{marca}.typ")


def crear_documento_remoto(slug: str, payload: dict) -> dict:
    """POST /api/orgs/<slug>/documentos -- crea el documento EN EL SERVIDOR primero (correlativo
    asignado ahí, de forma atómica) para 'doctyp new' con sesión remota activa (ver
    doctyp.py: cmd_nuevo) -- evita que dos equipos offline elijan el mismo correlativo. Devuelve
    la entrada de registro que arma el servidor (trae codigo_base/correlativo/año ya resueltos)."""
    sesion = sesion_activa()
    if sesion is None:
        raise SyncError("no hay sesión remota activa")
    return _peticion_json("POST", f"/api/orgs/{slug}/documentos", sesion["cookie"], payload)


def bajar_documento_completo(slug: str, codigo_base: str) -> Path:
    """Descarga completa de un documento que el servidor acaba de crear (ver
    crear_documento_remoto) -- materializa la carpeta local con la plantilla que copió el
    servidor, para que 'doctyp new' no dependa de que la plantilla local esté igual de
    actualizada."""
    sesion = sesion_activa()
    if sesion is None:
        raise SyncError("no hay sesión remota activa")
    carpeta = core.docs_root_org(slug) / codigo_base
    _bajar_carpeta(
        sesion["cookie"],
        f"/api/orgs/{slug}/documentos/{codigo_base}/archivos",
        f"/api/orgs/{slug}/documentos/{codigo_base}/archivo",
        carpeta, f"{codigo_base}.typ", f"/api/orgs/{slug}/documentos/{codigo_base}/typ",
    )
    return carpeta


def _mirror_registro_local_doc(slug: str, remoto: dict) -> None:
    """Tras un pull, refleja en el org.json LOCAL los campos de registro que ya trajo el
    manifiesto (codigo_base/área/tipo/categoría/año/correlativo/título/plantilla/versiones) --
    sin esto, 'doctyp list'/'save'/'edit'/'compile' no encuentran localmente un documento que
    se acaba de bajar por primera vez. `autor_id`/`equipo_id` quedan tal cual vengan del
    servidor aunque el org local todavía no tenga ese autor/equipo reflejado (sincronizar la
    lista de autores/equipos de la organización queda fuera de alcance de este trabajo -- ver
    plan)."""
    campos = {k: v for k, v in remoto.items() if k != "mtime"}
    if not core.org_existe(slug):
        import doctyp_db as _db
        _db.crear_org_vacia(slug, slug)
    org = core.cargar_org(slug)
    org["documentos"] = [d for d in org["documentos"] if d["codigo_base"] != campos["codigo_base"]]
    org["documentos"].append(campos)
    core.guardar_org(slug, org)


# ── Renombre de documento (doctyp change) ───────────────────────────────────────────────────

def renombrar_documento_remoto(slug: str, codigo_anterior: str, codigo_nuevo: str) -> None:
    """Propaga al servidor un renombre de documento ya hecho localmente (doctyp change) --
    POST .../documentos/<codigo_anterior>/renombrar. Lanza SyncError si falla (red, o 409 si el
    código nuevo ya existe en el servidor por otra vía)."""
    sesion = sesion_activa()
    if sesion is None:
        raise SyncError("no hay sesión remota activa")
    _peticion_json("POST", f"/api/orgs/{slug}/documentos/{codigo_anterior}/renombrar",
                    sesion["cookie"], {"codigo_nuevo": codigo_nuevo})


def encolar_renombre_pendiente(slug: str, codigo_anterior: str, codigo_nuevo: str) -> None:
    """Registra en settings.json → local.renombres_pendientes un renombre que todavía no se
    pudo avisar al servidor (sin sesión activa en el momento de 'doctyp change', o falló la
    llamada inmediata) -- sincronizar_todo() lo procesa en el próximo sync, antes de la
    reconciliación normal por codigo_base (ver _procesar_renombres_pendientes)."""
    settings = core.cargar_settings()
    local = settings.setdefault("local", {})
    pendientes = local.setdefault("renombres_pendientes", [])
    pendientes.append({"slug": slug, "codigo_anterior": codigo_anterior, "codigo_nuevo": codigo_nuevo})
    core.guardar_settings(settings)


def _renombres_pendientes() -> list[dict]:
    settings = core.cargar_settings()
    return list(settings.get("local", {}).get("renombres_pendientes", []))


def _quitar_renombre_pendiente(entrada: dict) -> None:
    settings = core.cargar_settings()
    local = settings.setdefault("local", {})
    local["renombres_pendientes"] = [p for p in local.get("renombres_pendientes", []) if p != entrada]
    core.guardar_settings(settings)


def _procesar_renombres_pendientes(cookie: str) -> None:
    """Corre ANTES del bucle normal de sincronizar_todo() -- por cada renombre encolado
    (offline en el momento de 'doctyp change'), si el servidor todavía tiene el código viejo
    registrado se le avisa recién ahora; si ya tiene el código nuevo (otro equipo lo sincronizó
    primero, o un intento previo parcial ya lo dejó consistente) no hace falta nada. En ambos
    casos se limpia la entrada -- después de esto, la reconciliación normal encuentra
    codigo_nuevo en ambos lados como cualquier documento existente, sin ruta especial."""
    for entrada in _renombres_pendientes():
        slug = entrada["slug"]
        try:
            manifiesto = _peticion_json("GET", f"/api/orgs/{slug}/sync/manifiesto", cookie)
        except SyncError:
            continue  # sin red -- se reintenta en el próximo sync, la entrada queda encolada
        codigos_remotos = {d["codigo_base"] for d in manifiesto["documentos"]}
        if entrada["codigo_anterior"] in codigos_remotos:
            try:
                renombrar_documento_remoto(slug, entrada["codigo_anterior"], entrada["codigo_nuevo"])
            except SyncError as e:
                print(f"  advertencia: no se pudo propagar el renombre pendiente de "
                      f"{entrada['codigo_anterior']} ({e}); se reintenta después")
                continue
        _quitar_renombre_pendiente(entrada)


def sincronizar_documento(slug: str, codigo_base: str, on_evento: EventoSync | None = None) -> None:
    """Sincroniza UN documento (usado tras new/save/compile/add -- no vale la pena barrer todas
    las organizaciones por un solo cambio). Silencioso si no hay sesión activa: el llamador
    decide si eso amerita una advertencia. `on_evento` es opcional (ver _notificar) -- ningún
    llamador de la CLI lo pasa, así que su comportamiento no cambia."""
    sesion = sesion_activa()
    if sesion is None:
        return
    cookie = sesion["cookie"]
    carpeta = core.docs_root_org(slug) / codigo_base
    ruta_typ = f"/api/orgs/{slug}/documentos/{codigo_base}/typ"
    ruta_archivos = f"/api/orgs/{slug}/documentos/{codigo_base}/archivos"
    ruta_archivo = f"/api/orgs/{slug}/documentos/{codigo_base}/archivo"
    ruta_sync = f"/api/orgs/{slug}/documentos/{codigo_base}/sync"

    try:
        manifiesto = _peticion_json("GET", f"/api/orgs/{slug}/sync/manifiesto", cookie)
    except SyncError:
        raise
    remoto = next((d for d in manifiesto["documentos"] if d["codigo_base"] == codigo_base), None)
    typ_local = carpeta / f"{codigo_base}.typ"

    if remoto is None:
        if typ_local.exists():
            _subir_carpeta(cookie, ruta_sync, carpeta)
            _notificar(on_evento, tipo="documento", slug=slug, nombre=codigo_base,
                       accion="subida", archivo_principal=typ_local)
        return
    if not typ_local.exists():
        _bajar_carpeta(cookie, ruta_archivos, ruta_archivo, carpeta,
                        f"{codigo_base}.typ", ruta_typ)
        _mirror_registro_local_doc(slug, remoto)
        _notificar(on_evento, tipo="documento", slug=slug, nombre=codigo_base,
                   accion="bajada", archivo_principal=typ_local)
        return

    hash_local = _hash_carpeta(carpeta)
    if hash_local is not None and hash_local == remoto.get("hash"):
        return  # contenido idéntico -- no-op real: sin escritura, sin tocar mtime, sin llamar a /sync

    mtime_local = typ_local.stat().st_mtime
    renombres = _renombres_detectados(cookie, slug, codigo_base, carpeta)
    if mtime_local >= remoto["mtime"]:
        try:
            _subir_carpeta(cookie, ruta_sync, carpeta,
                            renombrados=[{"de": p["remoto"], "a": p["local"]} for p in renombres])
        except SyncError as e:
            if e.status == 423:
                print(f"  {codigo_base}: en edición en otro equipo, no se sube esta vez")
                return
            raise
        _notificar(on_evento, tipo="documento", slug=slug, nombre=codigo_base,
                   accion="subida", archivo_principal=typ_local)
    else:
        # Aplicar los renombres detectados EN LOCAL antes de bajar: si no, el archivo con el
        # nombre viejo queda huérfano (la descarga solo escribe/sobrescribe, nunca borra -- ver
        # _bajar_carpeta) y el nombre nuevo se baja completo como si fuera contenido nuevo.
        for par in renombres:
            origen, destino = carpeta / par["local"], carpeta / par["remoto"]
            if origen.is_file() and not destino.exists():
                destino.parent.mkdir(parents=True, exist_ok=True)
                origen.rename(destino)
        _respaldar_documento_perdedor(carpeta, codigo_base)
        _mirror_registro_local_doc(slug, remoto)
        _bajar_carpeta(cookie, ruta_archivos, ruta_archivo, carpeta,
                        f"{codigo_base}.typ", ruta_typ)
        _notificar(on_evento, tipo="documento", slug=slug, nombre=codigo_base,
                   accion="bajada", archivo_principal=typ_local)


def _sincronizar_plantilla(slug: str, nombre: str, remoto: dict | None,
                            on_evento: EventoSync | None = None) -> None:
    carpeta = core.plantilla_dir(slug, nombre)
    sesion = sesion_activa()
    cookie = sesion["cookie"]
    lib_local = carpeta / "lib.typ"
    ruta_archivos = f"/api/orgs/{slug}/plantillas/{nombre}/archivos"
    ruta_archivo = f"/api/orgs/{slug}/plantillas/{nombre}/archivo"
    ruta_lib = f"/api/orgs/{slug}/plantillas/{nombre}/lib-typ"
    ruta_sync = f"/api/orgs/{slug}/plantillas/{nombre}/sync"

    if remoto is None:
        if lib_local.exists():
            _subir_carpeta(cookie, ruta_sync, carpeta)
            _notificar(on_evento, tipo="plantilla", slug=slug, nombre=nombre,
                       accion="subida", archivo_principal=lib_local)
        return
    if not lib_local.exists():
        _bajar_carpeta(cookie, ruta_archivos, ruta_archivo, carpeta, "lib.typ", ruta_lib)
        _notificar(on_evento, tipo="plantilla", slug=slug, nombre=nombre,
                   accion="bajada", archivo_principal=lib_local)
        return

    hash_local = _hash_carpeta(carpeta)
    if hash_local is not None and hash_local == remoto.get("hash"):
        return  # contenido idéntico -- no-op real, mismo criterio que sincronizar_documento

    mtime_local = lib_local.stat().st_mtime
    if mtime_local >= remoto["mtime"]:
        _subir_carpeta(cookie, ruta_sync, carpeta)
        _notificar(on_evento, tipo="plantilla", slug=slug, nombre=nombre,
                   accion="subida", archivo_principal=lib_local)
    else:
        # Sin respaldo automático: las plantillas ya tienen su propio historial manual
        # (`doctyp template save` / "Guardar plantilla"), y el daemon corre cada
        # INTERVALO_SEGUNDOS -- versionar acá inundaba .snapshots/ con una copia por tick.
        _bajar_carpeta(cookie, ruta_archivos, ruta_archivo, carpeta, "lib.typ", ruta_lib)
        _notificar(on_evento, tipo="plantilla", slug=slug, nombre=nombre,
                   accion="bajada", archivo_principal=lib_local)


def sincronizar_todo(on_evento: EventoSync | None = None) -> list[str]:
    """`doctyp login`/`doctyp sync`: todas las organizaciones de la cuenta remota. Devuelve la
    lista de slugs sincronizados (para el mensaje de confirmación del comando). `on_evento`
    (opcional) recibe un dict por cada transferencia real -- hoy solo lo usa el daemon en
    segundo plano para alimentar el tooltip de la bandeja del sistema (doctyp_tray.py); la CLI
    (cmd_sync/cmd_login) no lo pasa, así que su salida no cambia."""
    sesion = sesion_activa()
    if sesion is None:
        raise SyncError("no hay sesión remota activa (usa 'doctyp login <email>')")
    cookie = sesion["cookie"]

    _procesar_renombres_pendientes(cookie)

    orgs = _peticion_json("GET", "/api/orgs", cookie)
    # Antes del primer docs_root_org() de este barrido: doctyp.py lo consulta para decidir si
    # esta organización usa carpeta por usuario (ver sanear_usuario_email/docs_root_org).
    _actualizar_orgs_sesion([o["slug"] for o in orgs])
    for org in orgs:
        slug = org["slug"]
        if not core.org_existe(slug):
            import doctyp_db as _db
            _db.crear_org_vacia(slug, org.get("nombre") or slug)
        manifiesto = _peticion_json("GET", f"/api/orgs/{slug}/sync/manifiesto", cookie)
        carpeta_org = core.docs_root_org(slug)

        remotos_doc = {d["codigo_base"]: d for d in manifiesto["documentos"]}
        locales_doc = {p.name for p in carpeta_org.iterdir() if p.is_dir()} if carpeta_org.exists() else set()
        for codigo_base in sorted(remotos_doc.keys() | locales_doc):
            try:
                sincronizar_documento(slug, codigo_base, on_evento=on_evento)
            except SyncError as e:
                print(f"  advertencia: {slug}/{codigo_base} no se sincronizó ({e})")
                continue

        remotos_tpl = {t["nombre"]: t for t in manifiesto["plantillas"]}
        base_tpl = core.org_dir(slug) / "templates"
        locales_tpl = {p.name for p in base_tpl.iterdir() if p.is_dir()} if base_tpl.exists() else set()
        for nombre in sorted(remotos_tpl.keys() | locales_tpl):
            _sincronizar_plantilla(slug, nombre, remotos_tpl.get(nombre), on_evento=on_evento)

    return [o["slug"] for o in orgs]
