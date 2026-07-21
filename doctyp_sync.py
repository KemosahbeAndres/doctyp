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
import json
import os
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import doctyp as core

DOCTYP_REMOTE_HOST = os.environ.get("DOCTYP_REMOTE_HOST_OVERRIDE") or "https://doctyp.tinorte.cl"


class SyncError(Exception):
    pass


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
        raise SyncError(f"{e.code} {mensaje}")
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
    settings = core.cargar_settings()
    settings.setdefault("local", {})["sesion_remota"] = {
        "email": email, "cookie": cookie, "orgs": orgs or [],
    }
    core.guardar_settings(settings)


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


def _subir_carpeta(cookie: str, ruta_sync: str, carpeta: Path) -> None:
    archivos = {}
    for rel in _listar_archivos_locales(carpeta):
        archivos[rel] = base64.b64encode((carpeta / rel).read_bytes()).decode("ascii")
    if not archivos:
        return
    _peticion_json("POST", ruta_sync, cookie, {"archivos": archivos})


# ── Sincronización ───────────────────────────────────────────────────────────────────────────

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


def sincronizar_documento(slug: str, codigo_base: str) -> None:
    """Sincroniza UN documento (usado tras new/save/compile/add -- no vale la pena barrer todas
    las organizaciones por un solo cambio). Silencioso si no hay sesión activa: el llamador
    decide si eso amerita una advertencia."""
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
        return
    if not typ_local.exists():
        _bajar_carpeta(cookie, ruta_archivos, ruta_archivo, carpeta,
                        f"{codigo_base}.typ", ruta_typ)
        _mirror_registro_local_doc(slug, remoto)
        return

    mtime_local = typ_local.stat().st_mtime
    if mtime_local >= remoto["mtime"]:
        _subir_carpeta(cookie, ruta_sync, carpeta)
    else:
        _respaldar_documento_perdedor(carpeta, codigo_base)
        _mirror_registro_local_doc(slug, remoto)
        _bajar_carpeta(cookie, ruta_archivos, ruta_archivo, carpeta,
                        f"{codigo_base}.typ", ruta_typ)


def _sincronizar_plantilla(slug: str, nombre: str, remoto: dict | None) -> None:
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
        return
    if not lib_local.exists():
        _bajar_carpeta(cookie, ruta_archivos, ruta_archivo, carpeta, "lib.typ", ruta_lib)
        return

    mtime_local = lib_local.stat().st_mtime
    if mtime_local >= remoto["mtime"]:
        _subir_carpeta(cookie, ruta_sync, carpeta)
    else:
        # A diferencia de documentos, una plantilla SÍ tiene un mecanismo de versión propio
        # (guardar_version_plantilla) que ya snapshotea el contenido actual antes de
        # sobrescribir -- se reutiliza tal cual en vez de duplicar la lógica de respaldo.
        contenido_remoto = _peticion_json("GET", ruta_lib, cookie)["contenido"]
        core.guardar_version_plantilla(slug, nombre, contenido_remoto,
                                        "Respaldo automático por sincronización (conflicto)")
        _bajar_carpeta(cookie, ruta_archivos, ruta_archivo, carpeta, "lib.typ", ruta_lib)


def sincronizar_todo() -> list[str]:
    """`doctyp login`/`doctyp sync`: todas las organizaciones de la cuenta remota. Devuelve la
    lista de slugs sincronizados (para el mensaje de confirmación del comando)."""
    sesion = sesion_activa()
    if sesion is None:
        raise SyncError("no hay sesión remota activa (usa 'doctyp login <email>')")
    cookie = sesion["cookie"]

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
            sincronizar_documento(slug, codigo_base)

        remotos_tpl = {t["nombre"]: t for t in manifiesto["plantillas"]}
        base_tpl = core.org_dir(slug) / "templates"
        locales_tpl = {p.name for p in base_tpl.iterdir() if p.is_dir()} if base_tpl.exists() else set()
        for nombre in sorted(remotos_tpl.keys() | locales_tpl):
            _sincronizar_plantilla(slug, nombre, remotos_tpl.get(nombre))

    return [o["slug"] for o in orgs]
