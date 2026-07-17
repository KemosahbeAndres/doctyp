#!/usr/bin/env python3
"""
doctyp_web — Backend HTTP de `doctyp web` (Etapa 4 de la arquitectura v3, ver CLAUDE.md §6).

Servidor stdlib puro (http.server.ThreadingHTTPServer): API JSON bajo /api/... que envuelve
la lógica ya existente de doctyp.py (nunca reimplementa lógica de negocio aquí), SSE en
/api/events para notificar cambios en org.json/documentos, y estáticos desde web/dist/ (o un
placeholder si la Etapa 5 aún no generó el build). `cmd_web` compila la SPA (npm install +
npm run build sobre web/) antes de levantar el servidor, salvo --no-build o si no hay npm.

Seguridad: bind por defecto a 127.0.0.1; toda ruta se resuelve y valida contra las dos raíces
permitidas (organizations/ y DOCS_ROOT) sin path traversal; escrituras atómicas (reusa
_escribir_json_atomico de doctyp.py); sin ejecución de comandos arbitrarios; compilar vía web
reutiliza exactamente compilar_typ().

No requiere paquetes externos (solo stdlib).
"""
from __future__ import annotations
import base64, binascii, datetime, difflib, http.client, http.cookies, json, mimetypes, os, queue, shutil, subprocess, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote

import doctyp as core
import doctyp_auth as auth
from doctyp_preview_binary import resolver_tinymist_utilizable
from doctyp_preview_server import PreviewServer, PreviewServerError
from doctyp_lsp_server import LspServer, LspServerError
import doctyp_ws_server as ws_server
import doctyp_ws_client as ws_client

WEB_DIR = core.SCRIPT_DIR / "web"
WEB_DIST = WEB_DIR / "dist"

# ── Plan 15: vista previa vía tinymist (F2/F3, extendido a plantillas) ────────────────────
# Instancia única (un documento O una plantilla en preview a la vez -- ver PreviewServer).
# Cambiar de recurso activo reinicia el subproceso (mismo criterio de "una preview a la vez"
# que la Etapa 12 typst.ts). None si tinymist no está disponible o si nunca se pidió una
# preview todavía (modo legacy hasta entonces). La clave es ("doc"|"plantilla", slug, nombre)
# para no confundir un documento y una plantilla que compartan nombre.
_preview_lock = threading.Lock()
_preview_actual: PreviewServer | None = None
_preview_recurso_actual: tuple[str, str, str] | None = None
_preview_legacy_forzado = False  # `doctyp web --legacy-preview` (Plan 15 F8)

# Proxy del data plane de tinymist preview: `tinymist preview` valida el Origin de sus conexiones
# WebSocket contra una lista fija de excepciones (127.0.0.1, vscode-webview, Gitpod, ...) --
# bindearlo a 0.0.0.0 y exponerlo tras un dominio propio "no está soportado y no lo estará"
# (issue #2105 de Myriad-Dreamin/tinymist). Por eso Traefik ya NO le habla directo al data plane
# (ver docker-compose.yml): le habla a este mismo proceso con el Host público de la preview, y
# _proxy_preview() reenvía a 127.0.0.1:<puerto>, presentando el Origin que tinymist sí acepta --
# mismo truco que ya usa PreviewServer._conectar_control_plane() para el control plane. None si
# DOCTYP_PREVIEW_PUBLIC_URL no está fijada (desarrollo local sin Docker/Traefik): esta ruta nunca
# se activa en ese caso, cero cambio de comportamiento.
_PREVIEW_PUBLIC_HOST = urlsplit(os.environ.get("DOCTYP_PREVIEW_PUBLIC_URL", "")).hostname

# ── Registro/invitaciones: autorización por membresía ──────────────────────────────────────
# `_cargar_org_api` (usada por ~47 funciones api_*) necesita saber quién es el usuario de la
# sesión actual para validar membresía, pero esas funciones son de módulo (no métodos de
# _DoctypRequestHandler) -- en vez de agregar un parámetro `user_id` a cada una, un
# threading.local (mismo patrón que doctyp_db.py: _local para conexiones SQLite -- un hilo por
# request en ThreadingHTTPServer) guarda el usuario vigente, fijado una vez en _api() junto a
# self._usuario_sesion.
_hilo_usuario = threading.local()


def _usuario_id_actual() -> str | None:
    return getattr(_hilo_usuario, "user_id", None)

# `doctyp web --verbose`: accesos HTTP (log_message, silenciado por defecto) + salida en vivo
# de los subprocesos tinymist (preview/lsp), que hasta ahora solo se guardaba en memoria
# (PreviewServer.log_lines) y nunca llegaba a `docker compose logs` -- sin esto, un tinymist
# colgado o que nunca llega a arrancar es indistinguible de "nadie abrió el editor todavía".
_VERBOSE = False

# ── Fase 1A de tinymist-implementation-plan.md: proceso único `tinymist lsp` de la sesión ──
# A diferencia de PreviewServer (una instancia por documento/plantilla, se reinicia al cambiar),
# el LSP es UN SOLO proceso para toda la sesión de `doctyp web` -- cambiar de documento/
# plantilla activo llama `LspServer.cambiar_root()` (workspace/didChangeWorkspaceFolders,
# confirmado soportado, ver lsp-capabilities-0.15.2.json), nunca relanza el proceso.
_lsp_lock = threading.Lock()
_lsp_actual: LspServer | None = None
# Conexión WS del navegador actualmente asociada al proceso LSP (ver _lsp_bridge/_on_lsp_reiniciado
# más abajo) -- una sola a la vez, mismo criterio de "un recurso activo" del resto del módulo.
_lsp_conexion_activa: ws_server.WebSocketServerConnection | None = None

# workspace/executeCommand a evaluar en el paso 0 (tinymist-implementation-plan.md §2, Fase
# 1D): allowlist explícita -- el puente NO debe volverse un ejecutor arbitrario (CLAUDE.md §6).
# Solo los comandos que el plan ya nombra como necesarios para sub-fases futuras (1D/1E); nada
# más pasa, aunque el binario anuncie más en executeCommandProvider.commands.
_ALLOWLIST_COMANDOS_LSP = frozenset({
    "tinymist.doStartPreview", "tinymist.doKillPreview", "tinymist.scrollPreview",
    "tinymist.pinMain", "tinymist.getDocumentMetrics", "tinymist.doClearCache",
    "tinymist.exportPdf", "tinymist.exportSvg", "tinymist.exportPng",
    "tinymist.exportMarkdown", "tinymist.exportText",
})

_PLACEHOLDER_HTML = b"""<!doctype html>
<html><head><meta charset="utf-8"><title>doctyp web</title></head>
<body style="font-family: sans-serif; max-width: 40em; margin: 4em auto; line-height: 1.5;">
<h1>doctyp web</h1>
<p>Backend activo. La interfaz (SPA, Etapa 5) aun no esta construida en <code>web/dist/</code>.</p>
<p>Puedes verificar la API directamente: <a href="/api/orgs">/api/orgs</a></p>
</body></html>
"""


# ── Seguridad: resolución de rutas contra raíces permitidas ───────────────────────────────

class PathTraversalError(Exception):
    """Se lanza cuando una ruta pedida por la API cae fuera de las raíces permitidas."""


def _resolver_ruta_segura(base_permitida: Path, *partes: str) -> Path:
    """Construye una ruta a partir de `base_permitida` + `partes` (componentes ya separados,
    nunca una ruta cruda con '/' del cliente) y valida que el resultado sea la base o un
    descendiente de ella. Lanza PathTraversalError si no lo es."""
    base = base_permitida.resolve()
    for parte in partes:
        if not parte or parte in (".", "..") or "/" in parte or "\\" in parte:
            raise PathTraversalError(f"componente de ruta inválido: {parte!r}")
    candidato = base.joinpath(*partes).resolve()
    if candidato != base and base not in candidato.parents:
        raise PathTraversalError(f"ruta fuera de la raíz permitida: {candidato}")
    return candidato


def _slug_seguro(slug: str) -> str:
    if not core._slug_valido(slug):
        raise PathTraversalError(f"slug inválido: {slug!r}")
    return slug


# ── Helpers de la API (envuelven funciones ya existentes de doctyp.py) ────────────────────

class ApiError(Exception):
    def __init__(self, status: int, mensaje: str):
        super().__init__(mensaje)
        self.status = status
        self.mensaje = mensaje


def _es_miembro(org: dict, user_id: str) -> bool:
    return any(a.get("user_id") == user_id for a in org.get("autores", []))


def _verificar_miembro(org: dict) -> None:
    """Autorización por membresía (registro/invitaciones): sin esto, cualquier usuario
    autenticado podía cargar cualquier organización con solo conocer el slug -- ver el hallazgo
    documentado en el plan de esta funcionalidad. `user_id` es None solo en rutas públicas que
    no deberían llegar hasta acá (defensivo, no se espera que ocurra en la práctica)."""
    user_id = _usuario_id_actual()
    if user_id is not None and not _es_miembro(org, user_id):
        raise ApiError(403, "no tienes acceso a esta organización")


def _autor_de_sesion(org: dict) -> dict:
    """El autor SIEMPRE es el propio usuario de la sesión dentro de esta organización -- nunca
    algo elegible a mano (decisión tomada con el usuario: nadie puede operar como otro autor/
    usuario). _cargar_org_api ya exige membresía antes de que esto se llame, así que el usuario
    de sesión siempre debería aparecer en org["autores"]; el fallback a core.autor_activo (lee
    settings.json) solo cubre el caso defensivo de que no sea así."""
    user_id = _usuario_id_actual()
    if user_id is not None:
        for a in org.get("autores", []):
            if a.get("user_id") == user_id:
                return a
    return core.autor_activo(org)


def _cargar_org_api(slug: str) -> dict:
    _slug_seguro(slug)
    _resolver_ruta_segura(core.organizations_dir(), slug)
    if not core.org_existe(slug):
        raise ApiError(404, f"no existe la organización '{slug}'")
    org = core.cargar_org(slug)
    _verificar_miembro(org)
    return org


def _doc_o_404(org: dict, codigo_base: str) -> dict:
    doc = core.buscar_doc_org_por_codigo(org, codigo_base)
    if doc is None:
        raise ApiError(404, f"no existe el documento '{codigo_base}'")
    return doc


def api_orgs_list() -> list[dict]:
    user_id = _usuario_id_actual()
    activa = None
    if user_id is not None:
        import doctyp_db as _db
        activa = _db.obtener_org_activa(user_id)
    out = []
    for slug in core.listar_orgs():
        org = core.cargar_org(slug)
        if user_id is not None and not _es_miembro(org, user_id):
            continue
        out.append({
            "slug": slug, "nombre": org.get("nombre", slug),
            "activa": slug == activa, "documentos": len(org.get("documentos", [])),
        })
    return out


def api_org_get(slug: str) -> dict:
    org = _cargar_org_api(slug)
    return {
        "slug": org["slug"], "nombre": org.get("nombre", slug),
        "config": org.get("config", {}), "equipos": org.get("equipos", []),
        "autores": org.get("autores", []),
    }


def _crear_org_con_admin(slug: str, nombre: str, usuario: dict, *, tipo: str | None = None) -> str:
    """Crea una organización vacía y deja a `usuario` como admin de inmediato -- usada tanto por
    el registro (organización personal autocreada) como por 'Nueva organización' (api_org_new),
    que antes NO vinculaba al creador (bug pre-existente: con el fix de autorización por
    membresía, sin esto el creador no podría ni ver la org que acaba de crear). Devuelve el id
    interno de la organización creada."""
    import doctyp_db as _db
    org_id = _db.crear_org_vacia(slug, nombre)
    org = core.cargar_org(slug)
    if tipo:
        org["config"]["tipo"] = tipo
    org["autores"].append({
        "id": core._proximo_autor_id(org),
        "nombre": usuario["nombre"], "cargo": usuario.get("cargo") or "",
        "correo": usuario.get("email") or usuario.get("correo") or "",
        "equipos": [], "user_id": usuario["id"], "role": "admin",
    })
    core.guardar_org(slug, org)
    return org_id


def api_org_new(payload: dict) -> dict:
    slug = (payload.get("slug") or "").strip().lower()
    if not core._slug_valido(slug):
        raise ApiError(400, "el slug solo admite minúsculas, dígitos y guiones (p. ej. 'mi-org')")
    if core.org_existe(slug):
        raise ApiError(400, f"ya existe una organización '{slug}'")
    nombre = payload.get("nombre") or slug
    import doctyp_db as _db
    user_id = _usuario_id_actual()
    usuario = _db.obtener_usuario(user_id) if user_id else None
    if usuario is not None:
        org_id = _crear_org_con_admin(slug, nombre, usuario)
        if _db.obtener_org_activa(user_id) is None:
            _db.fijar_org_activa(user_id, org_id)
    else:
        _db.crear_org_vacia(slug, nombre)
    return {"slug": slug, "nombre": nombre}


def api_org_activar(slug: str) -> dict:
    _cargar_org_api(slug)  # ya valida membresía -- no se puede "activar" una org ajena
    user_id = _usuario_id_actual()
    if user_id is not None:
        import doctyp_db as _db
        _db.fijar_org_activa(user_id, _db.obtener_org_id(slug))
    return {"ok": True, "org_activa": slug}


def api_org_miembro_agregar(slug: str, payload: dict) -> dict:
    """Invitar = agregar directo a un usuario que YA existe en el sistema (decisión tomada con
    el usuario: sin infraestructura de email en el proyecto, sin paso de aceptación). Cualquier
    miembro de la organización puede invitar -- _cargar_org_api ya exige que quien invita sea
    miembro."""
    org = _cargar_org_api(slug)
    if org.get("config", {}).get("tipo") == "personal":
        raise ApiError(400, "una organización personal no admite invitados")
    email = (payload.get("email") or "").strip().lower()
    if not email:
        raise ApiError(400, "el correo es obligatorio")
    import doctyp_db as _db
    encontrado = _db.obtener_usuario_por_email(email)
    if encontrado is None:
        raise ApiError(404, f"no existe ningún usuario con el correo '{email}'")
    if _es_miembro(org, encontrado["id"]):
        raise ApiError(409, "ese usuario ya es miembro de la organización")
    role = payload.get("role") or "member"
    if role not in ("admin", "member"):
        raise ApiError(400, "role inválido (admin o member)")
    org["autores"].append({
        "id": core._proximo_autor_id(org),
        "nombre": encontrado["nombre"], "cargo": encontrado.get("cargo") or "",
        "correo": encontrado.get("correo") or encontrado.get("email") or "",
        "equipos": [], "user_id": encontrado["id"], "role": role,
    })
    core.guardar_org(slug, org)
    return {"ok": True}


def api_docs_list(slug: str) -> list[dict]:
    org = _cargar_org_api(slug)
    return sorted(org["documentos"], key=lambda d: (d.get("anio", 0), d.get("correlativo", 0)))


def api_tipos_documento() -> dict:
    return {
        "tipos": core.TIPOS, "categorias": sorted(core.CATEGORIAS),
        "estados": list(core.ESTADOS), "clasificaciones": list(core.CLASIFICACIONES),
    }


def api_doc_new(slug: str, payload: dict) -> dict:
    """Crea un documento nuevo (equivalente web de `doctyp new`). Reutiliza las mismas
    funciones de doctyp.py que `cmd_nuevo`, pero sin el espejo legacy en cwd (`doctyp.py`
    solo lo escribe para uso desde la CLI; aquí el cwd del servidor no tiene relación con el
    documento)."""
    org = _cargar_org_api(slug)

    titulo = (payload.get("titulo") or "").strip()
    if not titulo:
        raise ApiError(400, "el título es obligatorio")

    tipo = (payload.get("tipo") or "INF").upper()
    if tipo not in core.TIPOS:
        raise ApiError(400, f"tipo '{tipo}' inválido. Válidos: {', '.join(core.TIPOS)}")
    categoria = (payload.get("categoria") or "SFW").upper()
    if categoria not in core.CATEGORIAS:
        raise ApiError(400, f"categoría '{categoria}' inválida. Válidas: {', '.join(sorted(core.CATEGORIAS))}")
    area = (payload.get("area") or "TI").upper()

    plantilla = payload.get("plantilla") or org.get("config", {}).get("plantilla_default", "informe-ti")

    hoy = datetime.date.today()
    fecha = hoy.strftime("%Y%m%d")
    anio = hoy.year
    corr = core.next_correlativo_org(org, anio)

    autor_org = _autor_de_sesion(org)
    f = {
        "area": area, "tipo": tipo, "categoria": categoria,
        "anio": anio, "correlativo": corr, "version": "1.0", "fecha": fecha,
        "tipo_largo": core.TIPOS[tipo],
        "titulo": titulo,
        "subtitulo": payload.get("subtitulo") or "SLEP Chinchorro",
        "estado": "BORRADOR", "clasificacion": "INTERNO",
        "autor": autor_org["nombre"], "cargo": autor_org["cargo"], "correo": autor_org["correo"],
        "revisor": None, "aprobador": None,
    }

    base = core.codigo_base(area, tipo, categoria, anio, corr)
    dest_dir = core.crear_carpeta_documento(slug, base, plantilla)
    out_file = dest_dir / f"{base}.typ"
    out_file.write_text(core.build_typ(f, "lib.typ"), encoding="utf-8")

    ahora = datetime.datetime.now().isoformat(timespec="seconds")
    entrada_org = {
        "codigo_base": base,
        "area": area, "tipo": tipo, "categoria": categoria,
        "anio": anio, "correlativo": corr,
        "titulo": titulo, "autor_id": autor_org.get("id"), "equipo_id": None,
        "plantilla": plantilla,
        "ruta": base,
        "creado": ahora,
        "versiones": [{"version": f["version"], "fecha": fecha, "creado": ahora}],
    }
    org["documentos"].append(entrada_org)
    core.guardar_org(slug, org)
    core.escribir_indice_snapshots(dest_dir, entrada_org)
    return entrada_org


def api_doc_get(slug: str, codigo_base: str) -> dict:
    org = _cargar_org_api(slug)
    return _doc_o_404(org, codigo_base)


def _ruta_typ_segura(slug: str, codigo_base: str) -> Path:
    """Resuelve el .typ vigente de un documento, validado contra DOCS_ROOT."""
    _resolver_ruta_segura(core.docs_root(), slug, codigo_base, f"{codigo_base}.typ")
    return core.doc_dir(slug, codigo_base) / f"{codigo_base}.typ"


def api_doc_typ_get(slug: str, codigo_base: str) -> str:
    org = _cargar_org_api(slug)
    _doc_o_404(org, codigo_base)
    ruta = _ruta_typ_segura(slug, codigo_base)
    if not ruta.exists():
        raise ApiError(404, f"el archivo del documento no existe: {ruta}")
    return ruta.read_text(encoding="utf-8")


# ── Plan 15 F2/F3: gestión de la instancia de PreviewServer (una a la vez) ────────────────

def _lsp_root_y_editable(tipo: str, slug: str, nombre: str) -> tuple[Path, Path]:
    """Resuelve (root del workspace, archivo editable) para (tipo, slug, nombre) -- compartido
    entre GET /api/lsp/info (Fase 1B, resuelve el URI antes de conectar) y GET /api/lsp (Fase
    1A, el puente WS, que solo necesita el root para lanzar/reasociar el proceso)."""
    if tipo == "plantilla":
        root = _plantilla_o_404(slug, nombre)
        archivo_editable = root / "lib.typ"
    else:
        org = _cargar_org_api(slug)
        _doc_o_404(org, nombre)
        ruta = _ruta_typ_segura(slug, nombre)
        root = ruta.parent
        archivo_editable = ruta
    return root, archivo_editable.resolve()


def _archivo_editable_para(tipo: str, slug: str, nombre: str, main_typ: Path) -> Path:
    """El archivo que el usuario realmente edita (D4): el .typ principal para documentos;
    `lib.typ` -- no `main_typ`, que ahí es el .typ de MUESTRA -- para plantillas. Compartido
    entre el bridge de preview (H2, Fase 3.1) y el endpoint /api/lsp/info (Fase 1B) para no
    duplicar la distinción doc/plantilla en dos lugares."""
    return (
        core.plantilla_dir(slug, nombre) / "lib.typ" if tipo == "plantilla" else main_typ
    ).resolve()


def _asegurar_preview_generico(
    tipo: str, slug: str, nombre: str, main_typ: Path, root: Path,
) -> PreviewServer | None:
    """Devuelve el PreviewServer activo para (tipo, slug, nombre), arrancándolo o
    reiniciándolo si hace falta. `tipo` es "doc" o "plantilla" (evita ambigüedad si un
    documento y una plantilla comparten nombre). None si tinymist no está disponible O si
    `--legacy-preview` lo forzó (F8) -- en ambos casos el frontend degrada a typst.ts."""
    global _preview_actual, _preview_recurso_actual

    if _preview_legacy_forzado:
        return None

    clave = (tipo, slug, nombre)
    with _preview_lock:
        if _preview_recurso_actual == clave and _preview_actual is not None \
                and _preview_actual.is_running:
            return _preview_actual

        if resolver_tinymist_utilizable() is None:
            return None

        if not main_typ.exists():
            raise ApiError(404, f"el archivo no existe: {main_typ}")

        if _preview_actual is not None:
            _preview_actual.stop()

        font_dir = root / "fonts"
        nuevo = PreviewServer(
            main_typ=main_typ,
            root=root,
            font_dir=font_dir if font_dir.is_dir() else None,
            verbose=_VERBOSE,
        )
        # F5: clic→cursor -- el control plane vive en el backend (decisión confirmada con el
        # usuario, ver F0 §5); acá se reexpone editorScrollTo hacia el frontend por SSE
        # (/api/events, ya existente) en vez de exponer un WebSocket nuevo. Se agrega
        # tipo/slug/nombre porque el frontend no conoce la ruta absoluta en disco -- comparar
        # por esos campos es más simple y robusto que comparar filepaths.
        # H2 (tinymist-implementation-plan.md, Fase 3.1): el archivo "editable" para el usuario
        # difiere de `main_typ` en el caso de plantillas -- `main_typ` ahí es el .typ de MUESTRA
        # materializado en disco (ver _asegurar_preview_plantilla), NO lib.typ, que es lo que el
        # usuario realmente edita. Sin esta distinción, un clic sobre contenido generado por
        # lib.typ (portada, ficha, tablas) resolvía a una línea de lib.typ que el editor de
        # documentos interpretaba como si fuera del .typ principal -- por D4 (cabecera del plan),
        # lib.typ nunca se edita/visualiza desde el editor de documentos, así que ese salto debe
        # descartarse, no aplicarse.
        archivo_editable = _archivo_editable_para(tipo, slug, nombre, main_typ)

        def _bridge_scroll_to(datos, _editable=archivo_editable):
            try:
                es_editable = Path(datos.get("filepath", "")).resolve() == _editable
            except OSError:
                es_editable = False
            _emitir_evento_sse({
                "tipo": "editor-scroll-to", "recurso_tipo": tipo, "slug": slug, "nombre": nombre,
                "es_editable": es_editable, **datos,
            })

        nuevo.on_editor_scroll_to = _bridge_scroll_to
        # H1 (tinymist-implementation-plan.md, Fase 2.1): el callback existía en PreviewServer
        # desde Plan 15 F2 pero nunca se cableaba -- los errores de compilación en vivo no
        # llegaban nunca a la UI propia (StatusBar), solo al frontend embebido de tinymist
        # dentro del iframe.
        nuevo.on_compile_status = lambda kind: _emitir_evento_sse(
            {"tipo": "compile-status", "recurso_tipo": tipo, "slug": slug, "nombre": nombre, "kind": kind}
        )
        try:
            nuevo.start()
        except PreviewServerError as e:
            core._warn(f"no se pudo iniciar tinymist preview para '{nombre}': {e}")
            _preview_actual = None
            _preview_recurso_actual = None
            return None

        _preview_actual = nuevo
        _preview_recurso_actual = clave
        if _VERBOSE:
            core._ok(f"Preview tinymist iniciada: {tipo}/{nombre} "
                     f"(puerto datos {nuevo.data_plane_port}).")
        return nuevo


def _asegurar_preview_doc(slug: str, codigo_base: str) -> PreviewServer | None:
    ruta = _ruta_typ_segura(slug, codigo_base)
    return _asegurar_preview_generico("doc", slug, codigo_base, ruta, ruta.parent)


def _asegurar_preview_plantilla(slug: str, nombre: str) -> PreviewServer | None:
    """A diferencia de un documento, `main_typ` es el .typ de MUESTRA materializado en disco
    (ver core.asegurar_muestra_typ) -- el archivo que el usuario edita es lib.typ, importado
    por la muestra, no el documento principal en sí (mismo patrón que el preview typst.ts,
    Etapa 11, que ya distinguía "main.typ virtual" de "lib.typ en edición")."""
    _cargar_org_api(slug)
    _plantilla_o_404(slug, nombre)
    muestra = core.asegurar_muestra_typ(slug, nombre)
    if muestra is None:
        raise ApiError(404, f"la plantilla '{nombre}' no tiene lib.typ")
    return _asegurar_preview_generico("plantilla", slug, nombre, muestra, core.plantilla_dir(slug, nombre))


# Fase 1D (D5, exportadores rápidos): solo pdf/text/markdown -- svg/png quedan fuera por una
# limitación real de tinymist 0.15.2 encontrada en vivo (ver nota de la Etapa 16 en CLAUDE.md):
# para documentos multi-página exigen una plantilla de numeración ({p}) en la ruta de salida, y
# ni `arguments[1]` (extraOpts) ni `workspace/didChangeConfiguration` lograron fijar esa ruta en
# las pruebas -- solo se pudo hacer funcionar la ruta "natural" de un archivo único.
_EXPORTADORES = {
    "pdf": ("tinymist.exportPdf", ".pdf", "application/pdf"),
    "text": ("tinymist.exportText", ".txt", "text/plain; charset=utf-8"),
    "markdown": ("tinymist.exportMarkdown", ".md", "text/markdown; charset=utf-8"),
}


def _archivo_compilable_para(tipo: str, slug: str, nombre: str) -> Path:
    """El archivo que tinymist debe compilar para exportar/previsualizar: el .typ principal
    para documentos; el .typ de MUESTRA (no lib.typ, que no es compilable por sí solo) para
    plantillas -- mismo criterio que _asegurar_preview_plantilla."""
    if tipo == "plantilla":
        muestra = core.asegurar_muestra_typ(slug, nombre)
        if muestra is None:
            raise ApiError(404, f"la plantilla '{nombre}' no tiene lib.typ")
        return muestra
    return _ruta_typ_segura(slug, nombre)


def api_lsp_exportar(slug: str, codigo: str, tipo: str, formato: str) -> tuple[bytes, str, str]:
    """POST /api/lsp/exportar -- Fase 1D, D5 (exportación rápida, sin versión/snapshot,
    rotulada explícitamente distinta de "Compilar" -- CLAUDE.md §0/§14). Devuelve (bytes,
    content_type, nombre_para_la_descarga)."""
    if formato not in _EXPORTADORES:
        raise ApiError(400, f"formato de exportación no soportado: {formato}")
    comando, ext, content_type = _EXPORTADORES[formato]

    root, _archivo_editable = _lsp_root_y_editable(tipo, slug, codigo)
    archivo = _archivo_compilable_para(tipo, slug, codigo)
    if not archivo.exists():
        raise ApiError(404, f"el archivo no existe: {archivo}")

    font_dir = root / "fonts"
    lsp = _asegurar_lsp(root, font_dir if font_dir.is_dir() else None)
    if lsp is None:
        raise ApiError(503, "tinymist no está disponible para exportar (sin instalar o --legacy-preview).")

    # tinymist escribe SIEMPRE en la ruta "natural" (mismo nombre base que el .typ, con la
    # extensión del formato) -- para documentos eso coincide con el <código-base>.pdf/.txt/.md
    # que también usan "Compilar"/otros flujos oficiales. Se respalda lo que hubiera ahí, se
    # deja que tinymist escriba, se lee el resultado, y se restaura el respaldo (o se borra si
    # no había nada) -- nunca debe quedar el artefacto de exportación pisando algo oficial.
    ruta_natural = archivo.with_suffix(ext)
    respaldo = ruta_natural.with_name(ruta_natural.name + ".doctyp-respaldo-export")
    habia_respaldo = False
    if ruta_natural.exists():
        shutil.move(str(ruta_natural), str(respaldo))
        habia_respaldo = True
    try:
        resultado = lsp.ejecutar_comando(comando, [str(archivo)], timeout=30.0)
        ruta_generada = Path(resultado.get("path") or ruta_natural)
        if not ruta_generada.exists():
            raise ApiError(500, "la exportación no generó el archivo esperado")
        contenido = ruta_generada.read_bytes()
    except LspServerError as e:
        raise ApiError(500, f"error al exportar: {e}")
    finally:
        try:
            ruta_natural.unlink(missing_ok=True)
        except OSError:
            pass
        if habia_respaldo:
            shutil.move(str(respaldo), str(ruta_natural))

    return contenido, content_type, f"{archivo.stem}{ext}"


def api_lsp_info(slug: str | None, codigo: str | None, tipo: str) -> dict:
    """GET /api/lsp/info?slug=...&codigo=...&tipo=doc|plantilla -- Fase 1B: el frontend necesita
    el URI del archivo ANTES de conectar el WebSocket (para textDocument/didOpen), y saber si
    tinymist está disponible para degradar (sin LSP: sin diagnósticos/completion/hover, el
    editor sigue funcionando con StreamLanguage, Etapa 10)."""
    if not slug or not codigo or tipo not in ("doc", "plantilla"):
        return {"enabled": False}
    if resolver_tinymist_utilizable() is None:
        return {"enabled": False}
    try:
        _root, archivo_editable = _lsp_root_y_editable(tipo, slug, codigo)
    except ApiError:
        return {"enabled": False}
    if not archivo_editable.exists():
        return {"enabled": False}
    return {"enabled": True, "uri": archivo_editable.as_uri()}


def api_preview_info(slug: str | None, codigo_base: str | None) -> dict:
    """GET /api/preview/info?slug=...&codigo=... -- arranca/reutiliza la preview de ese
    documento y devuelve las URLs que el frontend necesita (F2 punto 2 del plan)."""
    if not slug or not codigo_base:
        return {"enabled": False}
    servidor = _asegurar_preview_doc(slug, codigo_base)
    if servidor is None:
        return {"enabled": False}
    return servidor.info()


def api_preview_info_plantilla(slug: str | None, nombre: str | None) -> dict:
    """GET /api/preview/plantilla/info?slug=...&nombre=... -- equivalente a api_preview_info
    pero para plantillas (ver _asegurar_preview_plantilla: usa el .typ de muestra materializado
    en disco, no el lib.typ que el usuario edita directamente)."""
    if not slug or not nombre:
        return {"enabled": False}
    servidor = _asegurar_preview_plantilla(slug, nombre)
    if servidor is None:
        return {"enabled": False}
    return servidor.info()


def _preview_activa_para(tipo: str, slug: str, nombre: str) -> PreviewServer | None:
    if _preview_recurso_actual != (tipo, slug, nombre) or _preview_actual is None \
            or not _preview_actual.is_running:
        return None
    return _preview_actual


def api_preview_update_memory(slug: str, codigo_base: str, contenido: str) -> dict:
    """POST /api/preview/memory -- F6: recompila el .typ en memoria en el subproceso tinymist
    SIN tocar el archivo en disco (verificado en F0/F2). Si la preview de este documento no
    está activa (p. ej. el usuario nunca la abrió, o cayó tinymist), no hace nada -- no es un
    error: la próxima vez que se pida /api/preview/info arrancará ya con el contenido guardado
    en disco, que sigue siendo la fuente de verdad."""
    with _preview_lock:
        servidor = _preview_activa_para("doc", slug, codigo_base)
        if servidor is None:
            return {"ok": False, "motivo": "preview no activa para este documento"}
        ruta = _ruta_typ_segura(slug, codigo_base)
        try:
            servidor.send_update_memory_files({str(ruta): contenido})
        except PreviewServerError as e:
            return {"ok": False, "motivo": str(e)}
        return {"ok": True}


def api_preview_update_memory_plantilla(slug: str, nombre: str, contenido: str) -> dict:
    """POST /api/preview/plantilla/memory -- F6 para plantillas: el usuario edita lib.typ (no
    el main.typ de la preview, que es la muestra) -- se envía el lib.typ editado en memoria;
    tinymist lo recompila porque la muestra lo importa (#import "lib.typ": *, ver
    core.build_typ). El archivo de muestra en disco NO se toca -- solo lib.typ vía memoria."""
    with _preview_lock:
        servidor = _preview_activa_para("plantilla", slug, nombre)
        if servidor is None:
            return {"ok": False, "motivo": "preview no activa para esta plantilla"}
        lib_path = core.plantilla_dir(slug, nombre) / "lib.typ"
        try:
            servidor.send_update_memory_files({str(lib_path): contenido})
        except PreviewServerError as e:
            return {"ok": False, "motivo": str(e)}
        return {"ok": True}


def api_preview_jump(slug: str, codigo_base: str, line: int, character: int) -> dict:
    """POST /api/preview/jump -- F6: salto explícito editor->preview (acción deliberada, NO se
    dispara en cada movimiento de cursor -- ver plan 15.md §8 punto 2, regla del usuario de no
    reintroducir sincronización automática). No garantiza un salto visible: el servidor ignora
    en silencio posiciones que no resuelven a un span (comportamiento confirmado en F0/F5)."""
    with _preview_lock:
        servidor = _preview_activa_para("doc", slug, codigo_base)
        if servidor is None:
            return {"ok": False, "motivo": "preview no activa para este documento"}
        ruta = _ruta_typ_segura(slug, codigo_base)
        try:
            servidor.send_panel_scroll_to(str(ruta), line, character)
        except PreviewServerError as e:
            return {"ok": False, "motivo": str(e)}
        return {"ok": True}


def api_preview_jump_plantilla(slug: str, nombre: str, line: int, character: int) -> dict:
    """POST /api/preview/plantilla/jump -- salto explícito para plantillas. line/character son
    posiciones dentro de lib.typ (el archivo que el usuario edita)."""
    with _preview_lock:
        servidor = _preview_activa_para("plantilla", slug, nombre)
        if servidor is None:
            return {"ok": False, "motivo": "preview no activa para esta plantilla"}
        lib_path = core.plantilla_dir(slug, nombre) / "lib.typ"
        try:
            servidor.send_panel_scroll_to(str(lib_path), line, character)
        except PreviewServerError as e:
            return {"ok": False, "motivo": str(e)}
        return {"ok": True}


def _detener_preview_activa() -> None:
    """Apagado limpio del subproceso al cerrar `doctyp web` (cmd_web, finally)."""
    global _preview_actual, _preview_recurso_actual
    with _preview_lock:
        if _preview_actual is not None:
            _preview_actual.stop()
        _preview_actual = None
        _preview_recurso_actual = None


# ── Fase 1A: ciclo de vida del proceso único `tinymist lsp` ────────────────────────────────

def _asegurar_lsp(root: Path, font_dir: Path | None) -> LspServer | None:
    """Arranca el proceso LSP si es la primera vez, o reusa el vigente reasociando su `root`
    (workspace/didChangeWorkspaceFolders) si cambió -- nunca relanza el proceso mientras siga
    vivo. None si tinymist no está disponible (mismo criterio de degradación que la preview).

    Si el proceso YA existía pero cayó (`is_running` False), en vez de crear una instancia
    LspServer nueva se reusa la misma y se llama a start() -- necesario porque
    LspServer._on_proceso_caido() (auto-reinicio, ver doctyp_lsp_server.py) también reusa la
    instancia; si acá se creara una nueva quedarían dos objetos con el mismo `root`, uno de ellos
    huérfano."""
    global _lsp_actual
    with _lsp_lock:
        if resolver_tinymist_utilizable() is None:
            return None
        if _lsp_actual is not None and _lsp_actual.is_running:
            try:
                _lsp_actual.cambiar_root(root)
            except LspServerError as e:
                core._warn(f"no se pudo reasociar el root del LSP: {e}")
            return _lsp_actual
        if _lsp_actual is not None:
            try:
                _lsp_actual.start()
                _lsp_actual.resetear_reintentos()
            except LspServerError as e:
                core._warn(f"no se pudo reiniciar tinymist lsp: {e}")
                return None
            return _lsp_actual
        nuevo = LspServer(root=root, font_dir=font_dir, verbose=_VERBOSE)
        nuevo.on_reiniciado = _on_lsp_reiniciado
        try:
            nuevo.start()
        except LspServerError as e:
            core._warn(f"no se pudo iniciar tinymist lsp: {e}")
            return None
        _lsp_actual = nuevo
        return nuevo


def _on_lsp_reiniciado() -> None:
    """Callback de LspServer.on_reiniciado (auto-reinicio tras una caída, ver
    doctyp_lsp_server.py: _on_proceso_caido). El proceso nuevo no tiene memoria del anterior
    (perdió el `didOpen` de cualquier documento abierto), y la conexión WS del navegador que
    siga bloqueada en `conexion.leer_mensaje()` (_lsp_bridge) esperando algo del navegador nunca
    se enteraría del reinicio por sí sola si el usuario no está tipeando -- se fuerza su cierre
    acá (frame CLOSE, ver WebSocketServerConnection.cerrar()) para que el cliente JS
    (conectarLsp, con el callback `onDesconectado` de CodeEditor.vue) reconecte y vuelva a hacer
    didOpen contra el proceso nuevo."""
    with _lsp_lock:
        conexion = _lsp_conexion_activa
    if conexion is not None:
        conexion.cerrar()


def _detener_lsp_activo() -> None:
    """Apagado limpio del proceso LSP al cerrar `doctyp web` (cmd_web, finally) -- mismo
    criterio que _detener_preview_activa()."""
    global _lsp_actual
    with _lsp_lock:
        if _lsp_actual is not None:
            _lsp_actual.stop()
        _lsp_actual = None


def _lsp_resp_workspace_configuration(datos: dict) -> list:
    items = (datos.get("params") or {}).get("items") or []
    return [None] * len(items)


def _lsp_resp_null(datos: dict):
    return None


# Las 3 excepciones donde el backend SÍ interpreta el protocolo (tinymist-implementation-plan.md
# Fase 1A punto 4): peticiones server→client que el cliente web no maneja -- si no se respondieran
# acá, tinymist se quedaría esperando indefinidamente una respuesta que nunca llega del navegador.
_LSP_RESPUESTAS_LOCALES = {
    "workspace/configuration": _lsp_resp_workspace_configuration,
    "client/registerCapability": _lsp_resp_null,
    "window/workDoneProgress/create": _lsp_resp_null,
}


def api_doc_typ_put(slug: str, codigo_base: str, contenido: str) -> dict:
    org = _cargar_org_api(slug)
    _doc_o_404(org, codigo_base)
    ruta = _ruta_typ_segura(slug, codigo_base)
    if not ruta.parent.exists():
        raise ApiError(404, f"la carpeta del documento no existe: {ruta.parent}")
    # Fase 3.3 (H): escritura atómica -- la frecuencia de escritura sube con el autoguardado a
    # 300ms, mismo criterio que org.json (write-temp + rename, nunca un write_text() directo).
    core._escribir_texto_atomico(ruta, contenido)
    # El polling de mtimes de /api/events (_eventos_loop) NO detecta esto: escanea mtime de
    # DIRECTORIOS, que no cambia al modificar un archivo existente -- evento explícito para que
    # StatusBar/otras pestañas se enteren sin esperar (o sin nunca enterarse) del próximo tick.
    _emitir_evento_sse({"tipo": "doc-saved", "slug": slug, "codigo": codigo_base})
    return {"ok": True}


def api_doc_meta_get(slug: str, codigo_base: str) -> dict:
    org = _cargar_org_api(slug)
    _doc_o_404(org, codigo_base)
    ruta = _ruta_typ_segura(slug, codigo_base)
    if not ruta.exists():
        raise ApiError(404, f"el archivo del documento no existe: {ruta}")
    return core.extraer_meta_typ(ruta)


def api_doc_meta_put(slug: str, codigo_base: str, cambios: dict) -> dict:
    org = _cargar_org_api(slug)
    doc = _doc_o_404(org, codigo_base)
    ruta = _ruta_typ_segura(slug, codigo_base)
    if not ruta.exists():
        raise ApiError(404, f"el archivo del documento no existe: {ruta}")
    nuevo_texto = core.actualizar_meta_typ(ruta, cambios)
    if "titulo" in cambios and cambios["titulo"] and doc.get("titulo") != cambios["titulo"]:
        doc["titulo"] = cambios["titulo"]
        core.guardar_org(slug, org)
    return {"meta": core.extraer_meta_typ(ruta), "contenido": nuevo_texto}


def api_doc_historia(slug: str, codigo_base: str) -> list[dict]:
    org = _cargar_org_api(slug)
    doc = _doc_o_404(org, codigo_base)
    dest_dir = core.doc_dir(slug, codigo_base)
    out = []
    for v in reversed(doc.get("versiones") or []):
        snapshot = v.get("snapshot")
        existe = bool(snapshot) and (dest_dir / snapshot).exists()
        out.append({**v, "snapshot_disponible": existe})
    return out


def api_doc_version_contenido(slug: str, codigo_base: str, version: str) -> str:
    """Lee el snapshot de una versión anterior (solo lectura; nunca escribe archivos, a
    diferencia de `cmd_restore` en doctyp.py)."""
    org = _cargar_org_api(slug)
    doc = _doc_o_404(org, codigo_base)
    vers = {v["version"]: v for v in (doc.get("versiones") or [])}
    v = vers.get(version)
    if v is None:
        raise ApiError(404, f"la versión '{version}' no existe para '{codigo_base}'")
    snapshot = v.get("snapshot")
    if not snapshot:
        raise ApiError(404, f"la versión '{version}' no tiene snapshot disponible")
    dest_dir = core.doc_dir(slug, codigo_base)
    snap_path = dest_dir / snapshot
    if not snap_path.exists():
        raise ApiError(404, f"el snapshot registrado no existe en disco: {snap_path}")
    return snap_path.read_text(encoding="utf-8")


def api_doc_version_diff(slug: str, codigo_base: str, version: str) -> dict:
    """Diff línea por línea entre el snapshot de `version` y el .typ vigente, con difflib
    (stdlib). Reusa api_doc_version_contenido/api_doc_typ_get -- no relee archivos aparte."""
    anterior = api_doc_version_contenido(slug, codigo_base, version)
    vigente = api_doc_typ_get(slug, codigo_base)
    lineas_a = anterior.splitlines()
    lineas_b = vigente.splitlines()
    sm = difflib.SequenceMatcher(None, lineas_a, lineas_b)
    filas = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            filas += [{"tipo": "igual", "texto": l} for l in lineas_a[i1:i2]]
        elif tag == "delete":
            filas += [{"tipo": "eliminada", "texto": l} for l in lineas_a[i1:i2]]
        elif tag == "insert":
            filas += [{"tipo": "agregada", "texto": l} for l in lineas_b[j1:j2]]
        elif tag == "replace":
            filas += [{"tipo": "eliminada", "texto": l} for l in lineas_a[i1:i2]]
            filas += [{"tipo": "agregada", "texto": l} for l in lineas_b[j1:j2]]
    return {"version": version, "filas": filas}


def api_doc_miniatura(slug: str, codigo_base: str) -> Path:
    org = _cargar_org_api(slug)
    _doc_o_404(org, codigo_base)
    ruta = _ruta_typ_segura(slug, codigo_base)
    if not ruta.exists():
        raise ApiError(404, f"el archivo del documento no existe: {ruta}")
    cache = core.generar_miniatura(ruta)
    if cache is None:
        raise ApiError(404, "no se pudo generar la miniatura (typst no disponible o falló la compilación)")
    return cache


def _listar_archivos_carpeta(base_dir: Path, excluir: set[str]) -> list[str]:
    """Lista rutas relativas (posix) de los archivos bajo base_dir para que el navegador arme
    el "proyecto" del compilador Typst-WASM (Etapa 11): excluye .snapshots/, archivos ocultos,
    los nombres en `excluir` (el .typ/lib.typ que viaja como texto en vivo, no desde disco) y
    los `.pdf` (salidas de "Compilar", nunca referenciadas desde un .typ -- fetchearlas sería
    puro desperdicio, y algunas quedan con nombres heredados no estándar en documentos
    migrados manualmente antes de la Etapa 2, p. ej. con espacios en el nombre)."""
    if not base_dir.is_dir():
        return []
    out = []
    for p in base_dir.rglob("*"):
        if not p.is_file() or p.suffix.lower() == ".pdf":
            continue
        rel = p.relative_to(base_dir)
        partes = rel.parts
        if partes[0] == core.SNAPSHOTS_DIRNAME or any(parte.startswith(".") for parte in partes):
            continue
        rel_str = rel.as_posix()
        if rel_str in excluir:
            continue
        out.append(rel_str)
    return sorted(out)


def api_doc_archivos(slug: str, codigo_base: str) -> list[str]:
    org = _cargar_org_api(slug)
    _doc_o_404(org, codigo_base)
    dest_dir = core.doc_dir(slug, codigo_base)
    return _listar_archivos_carpeta(dest_dir, excluir={f"{codigo_base}.typ"})


def api_doc_archivo(slug: str, codigo_base: str, ruta: list[str]) -> Path:
    org = _cargar_org_api(slug)
    _doc_o_404(org, codigo_base)
    _resolver_ruta_segura(core.docs_root(), slug, codigo_base, *ruta)
    destino = core.doc_dir(slug, codigo_base).joinpath(*ruta)
    if not destino.is_file():
        raise ApiError(404, f"no existe el archivo '{'/'.join(ruta)}'")
    return destino


def api_doc_archivo_subir(slug: str, codigo_base: str, payload: dict) -> dict:
    """POST .../documentos/<codigo_base>/archivo -- sube una imagen a img/ del documento (§4
    CLAUDE.md: imágenes propias del documento, distintas de Images/ que trae la plantilla
    copiada). Mismo criterio que api_template_archivo_subir (JSON+base64, sin multipart)."""
    org = _cargar_org_api(slug)
    _doc_o_404(org, codigo_base)
    nombre_archivo = (payload.get("nombre_archivo") or "").strip()
    if not nombre_archivo:
        raise ApiError(400, "el nombre del archivo es obligatorio")
    nombre_archivo = Path(nombre_archivo).name
    extension = Path(nombre_archivo).suffix.lower()
    if extension not in _EXTENSIONES_IMAGEN:
        raise ApiError(400, f"extensión no permitida: '{extension}' (usa png/jpg/jpeg/svg/webp/gif)")
    contenido_b64 = payload.get("contenido_base64") or ""
    try:
        datos = base64.b64decode(contenido_b64, validate=True)
    except (binascii.Error, ValueError):
        raise ApiError(400, "contenido_base64 inválido")
    if not datos:
        raise ApiError(400, "el archivo está vacío")
    if len(datos) > _MAX_BYTES_IMAGEN:
        raise ApiError(400, f"el archivo supera el máximo de {_MAX_BYTES_IMAGEN // (1024*1024)} MB")
    _resolver_ruta_segura(core.docs_root(), slug, codigo_base, "img", nombre_archivo)
    destino = core.doc_dir(slug, codigo_base) / "img" / nombre_archivo
    core._escribir_bytes_atomico(destino, datos)
    _emitir_evento_sse({"tipo": "doc-saved", "slug": slug, "codigo": codigo_base})
    return {"ok": True, "ruta": f"img/{nombre_archivo}"}


def api_doc_archivo_eliminar(slug: str, codigo_base: str, ruta: list[str]) -> dict:
    """DELETE .../documentos/<codigo_base>/archivo/<ruta...> -- por ahora solo se expone desde
    el modal de imágenes (borra un archivo ya subido a img/), mismo criterio que
    api_template_archivo_eliminar."""
    org = _cargar_org_api(slug)
    _doc_o_404(org, codigo_base)
    _resolver_ruta_segura(core.docs_root(), slug, codigo_base, *ruta)
    destino = core.doc_dir(slug, codigo_base).joinpath(*ruta)
    if not destino.is_file():
        raise ApiError(404, f"no existe el archivo '{'/'.join(ruta)}'")
    destino.unlink()
    _emitir_evento_sse({"tipo": "doc-saved", "slug": slug, "codigo": codigo_base})
    return {"ok": True}


def api_doc_archivo_renombrar(slug: str, codigo_base: str, ruta: list[str], nombre_nuevo: str) -> dict:
    """PUT .../documentos/<codigo_base>/archivo/<ruta...> -- renombra una imagen ya subida a
    img/ (§4 CLAUDE.md). Solo dentro de img/ -- el sidebar de archivos (solo lectura para todo
    lo demás) es el único llamador; se valida acá también por si la API se llama a mano."""
    org = _cargar_org_api(slug)
    _doc_o_404(org, codigo_base)
    if not ruta or ruta[0] != "img":
        raise ApiError(400, "solo se pueden renombrar archivos dentro de img/")
    nombre_nuevo = (nombre_nuevo or "").strip()
    if not nombre_nuevo:
        raise ApiError(400, "el nombre nuevo es obligatorio")
    nombre_nuevo = Path(nombre_nuevo).name
    extension = Path(nombre_nuevo).suffix.lower()
    if extension not in _EXTENSIONES_IMAGEN:
        raise ApiError(400, f"extensión no permitida: '{extension}' (usa png/jpg/jpeg/svg/webp/gif)")
    _resolver_ruta_segura(core.docs_root(), slug, codigo_base, *ruta)
    origen = core.doc_dir(slug, codigo_base).joinpath(*ruta)
    if not origen.is_file():
        raise ApiError(404, f"no existe el archivo '{'/'.join(ruta)}'")
    _resolver_ruta_segura(core.docs_root(), slug, codigo_base, "img", nombre_nuevo)
    destino = core.doc_dir(slug, codigo_base) / "img" / nombre_nuevo
    if destino.exists():
        raise ApiError(400, f"ya existe un archivo llamado '{nombre_nuevo}'")
    origen.rename(destino)
    _emitir_evento_sse({"tipo": "doc-saved", "slug": slug, "codigo": codigo_base})
    return {"ok": True, "ruta": f"img/{nombre_nuevo}"}


def api_doc_save(slug: str, codigo_base: str, mensaje: str) -> dict:
    if not mensaje:
        raise ApiError(400, "el mensaje es obligatorio")
    org = _cargar_org_api(slug)
    doc = _doc_o_404(org, codigo_base)
    dest_dir = core.doc_dir(slug, codigo_base)
    if not (dest_dir / f"{codigo_base}.typ").exists():
        raise ApiError(404, f"el archivo del documento no existe en {dest_dir}")
    version_actual, version_nueva = core.realizar_save_org(dest_dir, doc, mensaje)
    core.guardar_org(slug, org)
    return {"version_actual": version_actual, "version_nueva": version_nueva}


def api_doc_compile(slug: str, codigo_base: str, mensaje: str | None) -> dict:
    org = _cargar_org_api(slug)
    doc = _doc_o_404(org, codigo_base)
    dest_dir = core.doc_dir(slug, codigo_base)
    typ_path = dest_dir / f"{codigo_base}.typ"
    if not typ_path.exists():
        raise ApiError(404, f"el archivo del documento no existe: {typ_path}")
    if not mensaje:
        raise ApiError(400, "el mensaje es obligatorio para compilar (sube versión antes de exportar)")
    version_actual, version = core.realizar_save_org(dest_dir, doc, mensaje)
    core.guardar_org(slug, org)
    ok = core.compilar_typ(typ_path)
    if not ok:
        raise ApiError(500, "la compilación falló (revisa que Typst esté disponible)")
    pdf = typ_path.with_suffix(".pdf")
    return {"version_actual": version_actual, "version": version, "pdf": pdf.name if pdf.exists() else None}


def api_templates_list(slug: str) -> list[dict]:
    org = _cargar_org_api(slug)
    default = org.get("config", {}).get("plantilla_default")
    base = core.org_dir(slug) / "templates"
    nombres = sorted(p.name for p in base.iterdir() if p.is_dir()) if base.exists() else []
    return [{"nombre": n, "default": n == default} for n in nombres]


def api_template_default(slug: str, nombre: str) -> dict:
    org = _cargar_org_api(slug)
    core.plantilla_fijar_default(org, nombre)
    core.guardar_org(slug, org)
    return {"plantilla_default": org["config"]["plantilla_default"]}


def _plantilla_dir_segura(slug: str, nombre: str) -> Path:
    """Resuelve la carpeta de una plantilla, validada contra organizations/ (sin path
    traversal). No valida que exista -- cada endpoint decide si eso es un 404 o no."""
    _resolver_ruta_segura(core.organizations_dir(), slug, "templates", nombre)
    return core.plantilla_dir(slug, nombre)


def _plantilla_o_404(slug: str, nombre: str) -> Path:
    destino = _plantilla_dir_segura(slug, nombre)
    if not (destino / "lib.typ").exists():
        raise ApiError(404, f"no existe la plantilla '{nombre}' en '{slug}'")
    return destino


def api_template_new(slug: str, payload: dict) -> dict:
    """Crea una plantilla nueva (equivalente web de `doctyp template new`): clonando otra
    plantilla de la org, o el esqueleto mínimo de templates_base/ si no se indica origen."""
    _cargar_org_api(slug)
    nombre = (payload.get("nombre") or "").strip()
    if not nombre:
        raise ApiError(400, "el nombre de la plantilla es obligatorio")
    _plantilla_dir_segura(slug, nombre)
    clonar_de = payload.get("clonar_de")
    if clonar_de:
        origen = _plantilla_o_404(slug, clonar_de)
    else:
        origen = core.TEMPLATES_BASE_DIR / core.PLANTILLA_MINIMA
    destino = core.plantilla_clonar(slug, nombre, origen)
    return {"nombre": nombre, "ruta": str(destino)}


def api_template_libtyp_get(slug: str, nombre: str) -> dict:
    _cargar_org_api(slug)
    destino = _plantilla_o_404(slug, nombre)
    return {"contenido": (destino / "lib.typ").read_text(encoding="utf-8")}


def api_template_libtyp_put(slug: str, nombre: str, contenido: str, mensaje: str) -> dict:
    if not mensaje:
        raise ApiError(400, "el mensaje es obligatorio")
    _cargar_org_api(slug)
    _plantilla_o_404(slug, nombre)
    return core.guardar_version_plantilla(slug, nombre, contenido, mensaje)


def api_template_libtyp_contenido_put(slug: str, nombre: str, contenido: str) -> dict:
    """PUT .../lib-typ-contenido -- Fase 3.3 (extensión a plantillas, decisión del usuario
    2026-07-14): escritura cruda de lib.typ SIN crear versión/snapshot, para el autoguardado a
    300ms. Endpoint nuevo, distinto de PUT .../lib-typ (que siempre versiona vía
    guardar_version_plantilla) -- mismo par content-PUT/version-POST que ya existe para
    documentos (api_doc_typ_put vs. api_doc_save)."""
    _cargar_org_api(slug)
    destino = _plantilla_o_404(slug, nombre)
    core._escribir_texto_atomico(destino / "lib.typ", contenido)
    _emitir_evento_sse({"tipo": "plantilla-guardada", "slug": slug, "nombre": nombre})
    return {"ok": True}


def api_template_delete(slug: str, nombre: str) -> dict:
    org = _cargar_org_api(slug)
    _plantilla_o_404(slug, nombre)
    core.plantilla_eliminar(org, nombre)
    return {"ok": True}


def api_template_miniatura(slug: str, nombre: str) -> Path:
    _cargar_org_api(slug)
    _plantilla_o_404(slug, nombre)
    cache = core.generar_miniatura_plantilla(slug, nombre)
    if cache is None:
        raise ApiError(404, "no se pudo generar la miniatura (typst no disponible o falló la compilación)")
    return cache


def api_template_archivos(slug: str, nombre: str) -> list[str]:
    _cargar_org_api(slug)
    dest_dir = _plantilla_o_404(slug, nombre)
    return _listar_archivos_carpeta(dest_dir, excluir={"lib.typ"})


def api_template_archivo(slug: str, nombre: str, ruta: list[str]) -> Path:
    _cargar_org_api(slug)
    _plantilla_o_404(slug, nombre)
    _resolver_ruta_segura(core.organizations_dir(), slug, "templates", nombre, *ruta)
    destino = core.plantilla_dir(slug, nombre).joinpath(*ruta)
    if not destino.is_file():
        raise ApiError(404, f"no existe el archivo '{'/'.join(ruta)}'")
    return destino


# Extensiones de imagen aceptadas al subir a Images/ de una plantilla -- mismo criterio que el
# resto del proyecto (logos/isologos, ver §3 CLAUDE.md); SVG incluido porque el manual permite
# isologos vectoriales, pero PDF/otros formatos de #image() quedan fuera a propósito (esto es
# "subir imágenes", no un gestor de archivos genérico).
_EXTENSIONES_IMAGEN = frozenset({".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif"})
_MAX_BYTES_IMAGEN = 15 * 1024 * 1024  # cota de cordura (15 MB) contra un base64 gigante por error


def api_template_archivo_subir(slug: str, nombre: str, payload: dict) -> dict:
    """POST .../plantillas/<nombre>/archivo -- sube una imagen a Images/ de la plantilla.
    El cuerpo viaja en JSON (nombre_archivo + contenido en base64) en vez de multipart/form-data
    -- el proyecto es stdlib puro (CLAUDE.md §6) y no hay parser multipart ya escrito; el
    frontend arma el base64 con FileReader antes de mandarlo (ver SubirImagenesModal.vue)."""
    _cargar_org_api(slug)
    _plantilla_o_404(slug, nombre)
    nombre_archivo = (payload.get("nombre_archivo") or "").strip()
    if not nombre_archivo:
        raise ApiError(400, "el nombre del archivo es obligatorio")
    # Solo el nombre base -- una imagen sube a Images/ directo, nunca a una subcarpeta (evita
    # que un nombre con "../" o "/" intente escapar de Images/ antes incluso de resolver rutas).
    nombre_archivo = Path(nombre_archivo).name
    extension = Path(nombre_archivo).suffix.lower()
    if extension not in _EXTENSIONES_IMAGEN:
        raise ApiError(400, f"extensión no permitida: '{extension}' (usa png/jpg/jpeg/svg/webp/gif)")
    contenido_b64 = payload.get("contenido_base64") or ""
    try:
        datos = base64.b64decode(contenido_b64, validate=True)
    except (binascii.Error, ValueError):
        raise ApiError(400, "contenido_base64 inválido")
    if not datos:
        raise ApiError(400, "el archivo está vacío")
    if len(datos) > _MAX_BYTES_IMAGEN:
        raise ApiError(400, f"el archivo supera el máximo de {_MAX_BYTES_IMAGEN // (1024*1024)} MB")
    _resolver_ruta_segura(core.organizations_dir(), slug, "templates", nombre, "Images", nombre_archivo)
    destino = core.plantilla_dir(slug, nombre) / "Images" / nombre_archivo
    core._escribir_bytes_atomico(destino, datos)
    _emitir_evento_sse({"tipo": "plantilla-guardada", "slug": slug, "nombre": nombre})
    return {"ok": True, "ruta": f"Images/{nombre_archivo}"}


def api_template_archivo_eliminar(slug: str, nombre: str, ruta: list[str]) -> dict:
    """DELETE .../plantillas/<nombre>/archivo/<ruta...> -- por ahora solo se expone desde el
    modal de imágenes (borra un archivo ya subido a Images/), mismo criterio de ruta segura que
    api_template_archivo (lectura)."""
    _cargar_org_api(slug)
    _plantilla_o_404(slug, nombre)
    _resolver_ruta_segura(core.organizations_dir(), slug, "templates", nombre, *ruta)
    destino = core.plantilla_dir(slug, nombre).joinpath(*ruta)
    if not destino.is_file():
        raise ApiError(404, f"no existe el archivo '{'/'.join(ruta)}'")
    destino.unlink()
    _emitir_evento_sse({"tipo": "plantilla-guardada", "slug": slug, "nombre": nombre})
    return {"ok": True}


def api_template_archivo_renombrar(slug: str, nombre: str, ruta: list[str], nombre_nuevo: str) -> dict:
    """PUT .../plantillas/<nombre>/archivo/<ruta...> -- renombra una imagen ya subida a Images/.
    Mismo criterio que api_doc_archivo_renombrar."""
    _cargar_org_api(slug)
    _plantilla_o_404(slug, nombre)
    if not ruta or ruta[0] != "Images":
        raise ApiError(400, "solo se pueden renombrar archivos dentro de Images/")
    nombre_nuevo = (nombre_nuevo or "").strip()
    if not nombre_nuevo:
        raise ApiError(400, "el nombre nuevo es obligatorio")
    nombre_nuevo = Path(nombre_nuevo).name
    extension = Path(nombre_nuevo).suffix.lower()
    if extension not in _EXTENSIONES_IMAGEN:
        raise ApiError(400, f"extensión no permitida: '{extension}' (usa png/jpg/jpeg/svg/webp/gif)")
    _resolver_ruta_segura(core.organizations_dir(), slug, "templates", nombre, *ruta)
    origen = core.plantilla_dir(slug, nombre).joinpath(*ruta)
    if not origen.is_file():
        raise ApiError(404, f"no existe el archivo '{'/'.join(ruta)}'")
    _resolver_ruta_segura(core.organizations_dir(), slug, "templates", nombre, "Images", nombre_nuevo)
    destino = core.plantilla_dir(slug, nombre) / "Images" / nombre_nuevo
    if destino.exists():
        raise ApiError(400, f"ya existe un archivo llamado '{nombre_nuevo}'")
    origen.rename(destino)
    _emitir_evento_sse({"tipo": "plantilla-guardada", "slug": slug, "nombre": nombre})
    return {"ok": True, "ruta": f"Images/{nombre_nuevo}"}


def api_template_muestra(slug: str, nombre: str) -> str:
    """Texto del documento de muestra (Etapa 9: build_typ + _muestra_meta) que el navegador usa
    como `main.typ` al previsualizar una plantilla vía Typst-WASM (Etapa 11) -- el lib.typ en
    edición viaja aparte, como el `texto` en vivo del editor."""
    _cargar_org_api(slug)
    _plantilla_o_404(slug, nombre)
    return core.build_typ(core._muestra_meta(), "lib.typ")


def api_template_historia(slug: str, nombre: str) -> list[dict]:
    _cargar_org_api(slug)
    dest_dir = _plantilla_o_404(slug, nombre)
    out = []
    for v in core.listar_versiones_plantilla(slug, nombre):
        snapshot = v.get("snapshot")
        existe = bool(snapshot) and (dest_dir / snapshot).exists()
        out.append({**v, "snapshot_disponible": existe})
    return out


def api_template_historia_contenido(slug: str, nombre: str, version: str) -> str:
    _cargar_org_api(slug)
    _plantilla_o_404(slug, nombre)
    try:
        version_int = int(version)
    except ValueError:
        raise ApiError(400, f"versión inválida: '{version}'")
    return core.contenido_version_plantilla(slug, nombre, version_int)


def api_equipos_list(slug: str) -> list[dict]:
    return _cargar_org_api(slug).get("equipos", [])


def api_equipo_new(slug: str, payload: dict) -> dict:
    org = _cargar_org_api(slug)
    equipo = core.equipo_crear(org, payload.get("id", ""), payload.get("nombre"))
    core.guardar_org(slug, org)
    return equipo


def api_equipo_editar(slug: str, equipo_id: str, payload: dict) -> dict:
    org = _cargar_org_api(slug)
    equipo = core.equipo_editar(org, equipo_id, nombre=payload.get("nombre"))
    core.guardar_org(slug, org)
    return equipo


def api_equipo_eliminar(slug: str, equipo_id: str) -> dict:
    org = _cargar_org_api(slug)
    core.equipo_eliminar(org, equipo_id)
    core.guardar_org(slug, org)
    return {"ok": True}


def api_autores_list(slug: str) -> list[dict]:
    org = _cargar_org_api(slug)
    activo_id = _autor_de_sesion(org).get("id")
    return [{**a, "activo": a.get("id") == activo_id} for a in org.get("autores", [])]


def api_autor_new(slug: str, payload: dict) -> dict:
    org = _cargar_org_api(slug)
    autor = core.autor_crear(org, payload.get("nombre", ""), payload.get("cargo", ""),
                              payload.get("correo", ""), payload.get("equipos") or [])
    core.guardar_org(slug, org)
    return autor


def api_autor_editar(slug: str, autor_id: str, payload: dict) -> dict:
    org = _cargar_org_api(slug)
    autor = core.autor_editar(org, autor_id, nombre=payload.get("nombre"),
                               cargo=payload.get("cargo"), correo=payload.get("correo"),
                               equipos_ids=payload.get("equipos"))
    core.guardar_org(slug, org)
    return autor


def api_autor_eliminar(slug: str, autor_id: str) -> dict:
    org = _cargar_org_api(slug)
    core.autor_eliminar(org, autor_id)
    core.guardar_org(slug, org)
    settings = core.cargar_settings()
    if settings.get("local", {}).get("autor_activo") == autor_id:
        del settings["local"]["autor_activo"]
        core.guardar_settings(settings)
    return {"ok": True}


# ── SSE: detección de cambios por polling de mtimes (sin inotify/watchdog) ────────────────

_sse_lock = threading.Lock()
_sse_colas: set[queue.Queue] = set()


def _snapshot_mtimes() -> dict[str, float]:
    snap: dict[str, float] = {}
    # Etapa 19: org.json ya no existe (archivado como .migrated tras `doctyp migrate`), así que
    # el mtime del registro ya no es por-organización -- se usa el mtime de doctyp.db como señal
    # gruesa "algo cambió en el registro" para todas las orgs (cualquier escritura, sea de la
    # org que sea, toca el mismo archivo). Sobre-notifica entre orgs distintas (el cliente
    # simplemente vuelve a pedir su propia org), nunca sub-notifica.
    import doctyp_db as _db
    try:
        db_mtime = _db.db_path().stat().st_mtime
    except OSError:
        db_mtime = 0.0
    for slug in core.listar_orgs():
        snap[f"org:{slug}"] = db_mtime
        root = core.docs_root_org(slug)
        try:
            with os.scandir(root) as it:
                mtimes = [e.stat().st_mtime for e in it if e.is_dir()]
        except OSError:
            mtimes = []
        snap[f"docs:{slug}"] = max(mtimes) if mtimes else 0.0
    return snap


def _emitir_evento_sse(evento: dict) -> None:
    """Empuja `evento` a todas las conexiones SSE activas de inmediato (a diferencia de
    _eventos_loop, que solo revisa periódicamente cambios de mtimes). Usado por el bridge de
    Plan 15 F4/F5 para propagar editorScrollTo (clic→cursor) sin esperar al próximo tick del
    polling -- la latencia ahí importa para que el salto del cursor se sienta inmediato."""
    payload = f"data: {json.dumps(evento, ensure_ascii=False)}\n\n".encode("utf-8")
    with _sse_lock:
        colas = list(_sse_colas)
    for cola in colas:
        # H3 (tinymist-implementation-plan.md, Fase 2.2): la cola tiene maxsize (ver _sse()) --
        # un cliente que dejó de leer (pestaña congelada, red pausada) no debe acumular eventos
        # sin límite. Descartar el evento para ESE cliente es correcto: todos los eventos
        # actuales son re-sincronizables (org-changed/docs-changed disparan una recarga
        # completa; editor-scroll-to/compile-status son puntuales y el próximo evento reemplaza
        # al perdido).
        try:
            cola.put_nowait(payload)
        except queue.Full:
            pass


def _eventos_loop(intervalo: float = 1.5) -> None:
    anterior = _snapshot_mtimes()
    while True:
        time.sleep(intervalo)
        actual = _snapshot_mtimes()
        cambios = {k: v for k, v in actual.items() if anterior.get(k) != v}
        if cambios:
            evento = {"tipo": "org-changed" if any(k.startswith("org:") for k in cambios)
                       else "docs-changed", "claves": sorted(cambios)}
            _emitir_evento_sse(evento)
        anterior = actual


# ── Handler HTTP ────────────────────────────────────────────────────────────────────────

class _DoctypRequestHandler(BaseHTTPRequestHandler):
    server_version = "doctyp-web/1.0"

    def log_message(self, fmt, *args):
        if _VERBOSE:
            super().log_message(fmt, *args)  # accesos HTTP normales de BaseHTTPRequestHandler

    def _json(self, status: int, data) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, mensaje: str) -> None:
        self._json(status, {"error": mensaje})

    def _binario(self, status: int, cuerpo: bytes, content_type: str, nombre_descarga: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(cuerpo)))
        if nombre_descarga:
            self.send_header("Content-Disposition", f'attachment; filename="{nombre_descarga}"')
        self.end_headers()
        self.wfile.write(cuerpo)

    def _leer_cuerpo_json(self) -> dict:
        largo = int(self.headers.get("Content-Length", 0) or 0)
        if largo == 0:
            return {}
        crudo = self.rfile.read(largo)
        try:
            return json.loads(crudo.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ApiError(400, "cuerpo JSON inválido")

    # ── Sesión (Etapa 20) ──────────────────────────────────────────────────────────────
    def _token_sesion(self) -> str | None:
        crudo = self.headers.get("Cookie")
        if not crudo:
            return None
        galletas = http.cookies.SimpleCookie()
        galletas.load(crudo)
        item = galletas.get(auth.SESSION_COOKIE)
        return item.value if item else None

    def _usuario_actual(self) -> dict | None:
        return auth.usuario_de_sesion(self._token_sesion())

    def _fijar_cookie_sesion(self, token: str) -> None:
        max_age = auth.SESSION_TTL_HORAS * 3600
        self.send_header(
            "Set-Cookie",
            f"{auth.SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={max_age}",
        )

    def _borrar_cookie_sesion(self) -> None:
        self.send_header("Set-Cookie", f"{auth.SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0")

    def _json_con_cookie(self, status: int, data, set_cookie: str | None = None,
                          borrar_cookie: bool = False) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if set_cookie:
            self._fijar_cookie_sesion(set_cookie)
        if borrar_cookie:
            self._borrar_cookie_sesion()
        self.end_headers()
        self.wfile.write(body)

    # ── Auth (Etapa 20) ────────────────────────────────────────────────────────────────
    def _api_auth(self, metodo: str, segs: list[str]) -> None:
        if segs == ["bootstrap"] and metodo == "GET":
            self._json(200, auth.bootstrap_estado())
            return

        if segs == ["primer-usuario"] and metodo == "POST":
            cuerpo = self._leer_cuerpo_json()
            try:
                usuario = auth.crear_primer_usuario(
                    cuerpo.get("email", ""), cuerpo.get("nombre", ""), cuerpo.get("password", ""))
            except auth.AuthError as e:
                raise ApiError(e.status, e.mensaje)
            _, token = auth.login(usuario["email"], cuerpo["password"], self._ip_cliente(),
                                   self.headers.get("User-Agent", ""))
            self._json_con_cookie(201, {"usuario": auth.usuario_publico(usuario)}, set_cookie=token)
            return

        if segs == ["registro"] and metodo == "POST":
            cuerpo = self._leer_cuerpo_json()
            try:
                usuario = auth.registrar_usuario(
                    cuerpo.get("email", ""), cuerpo.get("nombre", ""), cuerpo.get("password", ""))
            except auth.AuthError as e:
                raise ApiError(e.status, e.mensaje)
            # Organización personal autocreada (única, solo el dueño es miembro -- "invitar"
            # rechaza explícitamente las orgs tipo=personal, ver api_org_miembro_agregar) --
            # slug con sufijo aleatorio: no depende del nombre, sin colisiones.
            import uuid
            import doctyp_db as _db
            slug = f"personal-{uuid.uuid4().hex[:8]}"
            org_id = _crear_org_con_admin(slug, "Personal", usuario, tipo="personal")
            _db.fijar_org_activa(usuario["id"], org_id)
            _, token = auth.login(usuario["email"], cuerpo["password"], self._ip_cliente(),
                                   self.headers.get("User-Agent", ""))
            self._json_con_cookie(201, {"usuario": auth.usuario_publico(usuario)}, set_cookie=token)
            return

        if segs == ["fijar-password-inicial"] and metodo == "POST":
            cuerpo = self._leer_cuerpo_json()
            try:
                auth.fijar_password_primer_login(cuerpo.get("user_id", ""), cuerpo.get("password", ""))
            except auth.AuthError as e:
                raise ApiError(e.status, e.mensaje)
            self._json(200, {"ok": True})
            return

        if segs == ["login"] and metodo == "POST":
            cuerpo = self._leer_cuerpo_json()
            try:
                usuario, token = auth.login(cuerpo.get("email", ""), cuerpo.get("password", ""),
                                             self._ip_cliente(), self.headers.get("User-Agent", ""))
            except auth.AuthError as e:
                raise ApiError(e.status, e.mensaje)
            self._json_con_cookie(200, {"usuario": auth.usuario_publico(usuario)}, set_cookie=token)
            return

        if segs == ["logout"] and metodo == "POST":
            auth.logout(self._token_sesion())
            self._json_con_cookie(200, {"ok": True}, borrar_cookie=True)
            return

        if segs == ["yo"] and metodo == "GET":
            usuario = self._usuario_actual()
            if usuario is None:
                raise ApiError(401, "no autenticado")
            self._json(200, {"usuario": auth.usuario_publico(usuario)})
            return

        raise ApiError(404, "ruta de auth desconocida")

    def _ip_cliente(self) -> str:
        return self.client_address[0] if self.client_address else ""

    def _despachar(self, metodo: str) -> None:
        partes_url = urlsplit(self.path)
        # self.path llega percent-encoded (p. ej. espacios como %20 en nombres de archivo con
        # espacios); urlsplit() no decodifica -- hay que hacerlo explícitamente antes de usar
        # los segmentos como componentes de ruta o identificadores.
        segs = [unquote(s) for s in partes_url.path.split("/") if s]

        try:
            if segs and segs[0] == "api":
                self._api(metodo, segs[1:], parse_qs(partes_url.query))
            else:
                self._estaticos(segs)
        except ApiError as e:
            self._error(e.status, e.mensaje)
        except PathTraversalError as e:
            self._error(400, f"ruta inválida: {e}")
        except SystemExit as e:
            # Funciones "clásicas" del core (buscar_doc_org, etc.) usan sys.exit() en error.
            self._error(400, str(e.code) if e.code else "error de solicitud")
        except FileNotFoundError as e:
            self._error(404, str(e))
        except Exception as e:  # noqa: BLE001 - no debe tumbar el hilo del servidor
            self._error(500, f"error interno: {e}")

    def _es_preview_proxy(self) -> bool:
        """True si esta petición llegó con el Host público de la vista previa de tinymist --
        ver _PREVIEW_PUBLIC_HOST y _proxy_preview() más abajo."""
        if _PREVIEW_PUBLIC_HOST is None:
            return False
        host = (self.headers.get("Host") or "").split(":")[0].lower()
        return host == _PREVIEW_PUBLIC_HOST.lower()

    def do_GET(self):
        if self._es_preview_proxy():
            self._proxy_preview("GET")
            return
        partes_url = urlsplit(self.path)
        if partes_url.path in ("/api/events", "/api/lsp"):
            # No pasan por _despachar()/_api() (SSE y el bridge WS necesitan control fino de
            # la respuesta) -- la sesión se exige aquí directo, mismo criterio de la Etapa 20
            # que el resto de /api/... (salvo auth/bootstrap/login).
            if self._usuario_actual() is None:
                self._error(401, "no autenticado")
                return
            if partes_url.path == "/api/events":
                self._sse()
            else:
                self._lsp_bridge(parse_qs(partes_url.query))
            return
        self._despachar("GET")

    def do_POST(self):
        if self._es_preview_proxy():
            self._proxy_preview("POST")
            return
        self._despachar("POST")

    def _proxy_preview(self, metodo: str) -> None:
        """Proxy transparente HTTP+WS hacia el data plane de `tinymist preview` (127.0.0.1,
        mismo contenedor/proceso) para el tráfico que llega con el Host público de la preview --
        ver _PREVIEW_PUBLIC_HOST arriba. No pasa por el sistema de sesión/auth (ya no lo hacía
        antes tampoco: la cookie de sesión no cruza de dominio sin `Domain=` explícito, así que
        esto no es una regresión de seguridad)."""
        servidor_activo = _preview_actual
        if servidor_activo is None or not servidor_activo.is_running:
            self._error(502, "no hay vista previa activa en este momento")
            return
        puerto = servidor_activo.data_plane_port
        if ws_server.es_peticion_upgrade(self.headers):
            self._proxy_preview_ws(puerto)
        else:
            self._proxy_preview_http(metodo, puerto)

    def _proxy_preview_http(self, metodo: str, puerto: int) -> None:
        largo = int(self.headers.get("Content-Length", 0) or 0)
        cuerpo = self.rfile.read(largo) if largo else None
        cabeceras_saltar = {"host", "connection"}
        cabeceras = {k: v for k, v in self.headers.items() if k.lower() not in cabeceras_saltar}
        try:
            conn = http.client.HTTPConnection("127.0.0.1", puerto, timeout=15)
            conn.request(metodo, self.path, body=cuerpo, headers=cabeceras)
            resp = conn.getresponse()
            cuerpo_resp = resp.read()
            cabeceras_resp = resp.getheaders()
            estado = resp.status
            conn.close()
        except OSError as e:
            self._error(502, f"no se pudo conectar al data plane de tinymist: {e}")
            return
        self.send_response(estado)
        for k, v in cabeceras_resp:
            if k.lower() not in ("connection", "transfer-encoding", "content-length", "date"):
                self.send_header(k, v)
        self.send_header("Content-Length", str(len(cuerpo_resp)))
        self.end_headers()
        self.wfile.write(cuerpo_resp)

    def _proxy_preview_ws(self, puerto: int) -> None:
        if not ws_server.realizar_handshake(self.headers, self.wfile):
            self._error(400, "handshake WebSocket inválido")
            return
        servidor = ws_server.WebSocketServerConnection(self.rfile, self.wfile)
        cliente = ws_client.WebSocketClient(
            host="127.0.0.1", port=puerto, path=self.path,
            origin=f"http://127.0.0.1:{puerto}",
            on_message=lambda payload, es_binario: servidor.enviar_datos(payload, es_binario),
            on_close=servidor.cerrar,
        )
        try:
            cliente.conectar()
        except (ws_client.WebSocketError, OSError):
            servidor.cerrar()
            return
        try:
            while True:
                mensaje = servidor.leer_mensaje()
                if mensaje is None:
                    break
                opcode, payload = mensaje
                try:
                    cliente.enviar_datos(payload, ws_server.es_binario(opcode))
                except (ws_client.WebSocketError, OSError):
                    break
        finally:
            cliente.cerrar()

    def do_PUT(self):
        self._despachar("PUT")

    def do_DELETE(self):
        self._despachar("DELETE")

    # ── Ruteo de la API ────────────────────────────────────────────────────────────────
    # Rutas de /api/... que NO exigen sesión (Etapa 20): bootstrap y login la necesitan
    # precisamente para poder crear la primera sesión; el resto de la API sí la exige.
    _RUTAS_PUBLICAS = {
        ("auth", "bootstrap"), ("auth", "primer-usuario"),
        ("auth", "fijar-password-inicial"), ("auth", "login"), ("auth", "registro"),
    }

    def _api(self, metodo: str, segs: list[str], query: dict) -> None:
        ruta = tuple(segs[:2])
        if ruta not in self._RUTAS_PUBLICAS:
            usuario = self._usuario_actual()
            if usuario is None:
                raise ApiError(401, "no autenticado")
            self._usuario_sesion = usuario  # disponible para endpoints que necesiten el autor
            _hilo_usuario.user_id = usuario["id"]

        if segs and segs[0] == "auth":
            self._api_auth(metodo, segs[1:])
            return

        if segs and segs[0] == "tipos-documento" and len(segs) == 1 and metodo == "GET":
            self._json(200, api_tipos_documento())
            return

        if segs and segs[0] == "lsp" and len(segs) == 2 and segs[1] == "info" and metodo == "GET":
            slug = (query.get("slug") or [None])[0]
            codigo = (query.get("codigo") or [None])[0]
            tipo = (query.get("tipo") or ["doc"])[0]
            self._json(200, api_lsp_info(slug, codigo, tipo))
            return

        if segs and segs[0] == "lsp" and len(segs) == 2 and segs[1] == "exportar" and metodo == "POST":
            cuerpo = self._leer_cuerpo_json()
            slug = cuerpo.get("slug")
            codigo = cuerpo.get("codigo")
            tipo = cuerpo.get("tipo", "doc")
            formato = cuerpo.get("formato")
            if not slug or not codigo or not formato:
                raise ApiError(400, "faltan slug/codigo/formato")
            contenido, content_type, nombre = api_lsp_exportar(slug, codigo, tipo, formato)
            self._binario(200, contenido, content_type, nombre_descarga=nombre)
            return

        if segs and segs[0] == "preview" and len(segs) == 2 and segs[1] == "info" and metodo == "GET":
            slug = (query.get("slug") or [None])[0]
            codigo = (query.get("codigo") or [None])[0]
            self._json(200, api_preview_info(slug, codigo))
            return

        if segs and segs[0] == "preview" and len(segs) == 2 and segs[1] == "memory" and metodo == "POST":
            cuerpo = self._leer_cuerpo_json()
            slug = cuerpo.get("slug")
            codigo = cuerpo.get("codigo")
            contenido = cuerpo.get("contenido")
            if not slug or not codigo or contenido is None:
                raise ApiError(400, "faltan slug/codigo/contenido")
            self._json(200, api_preview_update_memory(slug, codigo, contenido))
            return

        if segs and segs[0] == "preview" and len(segs) == 2 and segs[1] == "jump" and metodo == "POST":
            cuerpo = self._leer_cuerpo_json()
            slug = cuerpo.get("slug")
            codigo = cuerpo.get("codigo")
            line = cuerpo.get("line")
            character = cuerpo.get("character")
            if not slug or not codigo or line is None or character is None:
                raise ApiError(400, "faltan slug/codigo/line/character")
            self._json(200, api_preview_jump(slug, codigo, line, character))
            return

        # Vista previa de PLANTILLAS (mismo API que documentos, ver _asegurar_preview_plantilla)
        if segs and segs[0] == "preview" and len(segs) == 3 and segs[1] == "plantilla" \
                and segs[2] == "info" and metodo == "GET":
            slug = (query.get("slug") or [None])[0]
            nombre = (query.get("nombre") or [None])[0]
            self._json(200, api_preview_info_plantilla(slug, nombre))
            return

        if segs and segs[0] == "preview" and len(segs) == 3 and segs[1] == "plantilla" \
                and segs[2] == "memory" and metodo == "POST":
            cuerpo = self._leer_cuerpo_json()
            slug = cuerpo.get("slug")
            nombre = cuerpo.get("nombre")
            contenido = cuerpo.get("contenido")
            if not slug or not nombre or contenido is None:
                raise ApiError(400, "faltan slug/nombre/contenido")
            self._json(200, api_preview_update_memory_plantilla(slug, nombre, contenido))
            return

        if segs and segs[0] == "preview" and len(segs) == 3 and segs[1] == "plantilla" \
                and segs[2] == "jump" and metodo == "POST":
            cuerpo = self._leer_cuerpo_json()
            slug = cuerpo.get("slug")
            nombre = cuerpo.get("nombre")
            line = cuerpo.get("line")
            character = cuerpo.get("character")
            if not slug or not nombre or line is None or character is None:
                raise ApiError(400, "faltan slug/nombre/line/character")
            self._json(200, api_preview_jump_plantilla(slug, nombre, line, character))
            return

        if not segs or segs[0] != "orgs":
            self._error(404, "ruta de API desconocida")
            return

        if len(segs) == 1:  # /api/orgs
            if metodo == "GET":
                self._json(200, api_orgs_list())
            elif metodo == "POST":
                cuerpo = self._leer_cuerpo_json()
                self._json(201, api_org_new(cuerpo))
            else:
                self._error(405, "método no soportado")
            return

        slug = _slug_seguro(segs[1])
        if len(segs) == 2:  # /api/orgs/<slug>
            self._json(200, api_org_get(slug))
            return

        if len(segs) == 3 and segs[2] == "activar" and metodo == "POST":
            self._json(200, api_org_activar(slug))
            return

        if len(segs) == 3 and segs[2] == "miembros" and metodo == "POST":
            cuerpo = self._leer_cuerpo_json()
            self._json(201, api_org_miembro_agregar(slug, cuerpo))
            return

        recurso = segs[2]
        if recurso == "documentos":
            if len(segs) == 3:  # /api/orgs/<slug>/documentos
                if metodo == "GET":
                    self._json(200, api_docs_list(slug))
                elif metodo == "POST":
                    cuerpo = self._leer_cuerpo_json()
                    self._json(201, api_doc_new(slug, cuerpo))
                else:
                    self._error(405, "método no soportado")
                return
            codigo_base = segs[3]
            if len(segs) == 4:  # /api/orgs/<slug>/documentos/<codigo_base>
                self._json(200, api_doc_get(slug, codigo_base))
                return
            sub = segs[4]
            if sub == "typ" and len(segs) == 5:
                if metodo == "GET":
                    self._json(200, {"contenido": api_doc_typ_get(slug, codigo_base)})
                elif metodo == "PUT":
                    cuerpo = self._leer_cuerpo_json()
                    self._json(200, api_doc_typ_put(slug, codigo_base, cuerpo.get("contenido", "")))
                else:
                    self._error(405, "método no soportado")
                return
            if sub == "meta" and len(segs) == 5:
                if metodo == "GET":
                    self._json(200, api_doc_meta_get(slug, codigo_base))
                elif metodo == "PUT":
                    cuerpo = self._leer_cuerpo_json()
                    self._json(200, api_doc_meta_put(slug, codigo_base, cuerpo))
                else:
                    self._error(405, "método no soportado")
                return
            if sub == "historia" and len(segs) == 5 and metodo == "GET":
                self._json(200, api_doc_historia(slug, codigo_base))
                return
            if sub == "historia" and len(segs) == 7 and segs[6] == "contenido" and metodo == "GET":
                version = segs[5]
                self._json(200, {"contenido": api_doc_version_contenido(slug, codigo_base, version)})
                return
            if sub == "historia" and len(segs) == 7 and segs[6] == "diff" and metodo == "GET":
                version = segs[5]
                self._json(200, api_doc_version_diff(slug, codigo_base, version))
                return
            if sub == "save" and len(segs) == 5 and metodo == "POST":
                cuerpo = self._leer_cuerpo_json()
                self._json(200, api_doc_save(slug, codigo_base, cuerpo.get("mensaje", "")))
                return
            if sub == "compile" and len(segs) == 5 and metodo == "POST":
                cuerpo = self._leer_cuerpo_json()
                self._json(200, api_doc_compile(slug, codigo_base, cuerpo.get("mensaje")))
                return
            if sub == "miniatura" and len(segs) == 5 and metodo == "GET":
                ruta_png = api_doc_miniatura(slug, codigo_base)
                self._binario(200, ruta_png.read_bytes(), "image/png")
                return
            if sub == "archivos" and len(segs) == 5 and metodo == "GET":
                self._json(200, api_doc_archivos(slug, codigo_base))
                return
            if sub == "archivo" and len(segs) >= 6 and metodo == "GET":
                ruta_archivo = api_doc_archivo(slug, codigo_base, segs[5:])
                tipo, _ = mimetypes.guess_type(ruta_archivo.name)
                self._binario(200, ruta_archivo.read_bytes(), tipo or "application/octet-stream")
                return
            if sub == "archivo" and len(segs) == 5 and metodo == "POST":
                cuerpo = self._leer_cuerpo_json()
                self._json(201, api_doc_archivo_subir(slug, codigo_base, cuerpo))
                return
            if sub == "archivo" and len(segs) >= 6 and metodo == "DELETE":
                self._json(200, api_doc_archivo_eliminar(slug, codigo_base, segs[5:]))
                return
            if sub == "archivo" and len(segs) >= 6 and metodo == "PUT":
                cuerpo = self._leer_cuerpo_json()
                self._json(200, api_doc_archivo_renombrar(slug, codigo_base, segs[5:], cuerpo.get("nombre_nuevo", "")))
                return
            self._error(404, "ruta de API desconocida")
            return

        if recurso == "plantillas":
            if len(segs) == 3:
                if metodo == "GET":
                    self._json(200, api_templates_list(slug))
                elif metodo == "POST":
                    cuerpo = self._leer_cuerpo_json()
                    self._json(201, api_template_new(slug, cuerpo))
                else:
                    self._error(405, "método no soportado")
                return
            nombre = segs[3]
            if len(segs) == 4:
                if metodo == "DELETE":
                    self._json(200, api_template_delete(slug, nombre))
                else:
                    self._error(405, "método no soportado")
                return
            sub = segs[4]
            if sub == "default" and len(segs) == 5 and metodo == "POST":
                self._json(200, api_template_default(slug, nombre))
                return
            if sub == "lib-typ" and len(segs) == 5:
                if metodo == "GET":
                    self._json(200, api_template_libtyp_get(slug, nombre))
                elif metodo == "PUT":
                    cuerpo = self._leer_cuerpo_json()
                    self._json(200, api_template_libtyp_put(
                        slug, nombre, cuerpo.get("contenido", ""), cuerpo.get("mensaje", "")))
                else:
                    self._error(405, "método no soportado")
                return
            if sub == "lib-typ-contenido" and len(segs) == 5 and metodo == "PUT":
                # Fase 3.3: autoguardado -- distinto de PUT .../lib-typ (que siempre versiona).
                cuerpo = self._leer_cuerpo_json()
                self._json(200, api_template_libtyp_contenido_put(slug, nombre, cuerpo.get("contenido", "")))
                return
            if sub == "miniatura" and len(segs) == 5 and metodo == "GET":
                ruta_png = api_template_miniatura(slug, nombre)
                self._binario(200, ruta_png.read_bytes(), "image/png")
                return
            if sub == "archivos" and len(segs) == 5 and metodo == "GET":
                self._json(200, api_template_archivos(slug, nombre))
                return
            if sub == "archivo" and len(segs) >= 6 and metodo == "GET":
                ruta_archivo = api_template_archivo(slug, nombre, segs[5:])
                tipo, _ = mimetypes.guess_type(ruta_archivo.name)
                self._binario(200, ruta_archivo.read_bytes(), tipo or "application/octet-stream")
                return
            if sub == "archivo" and len(segs) == 5 and metodo == "POST":
                cuerpo = self._leer_cuerpo_json()
                self._json(201, api_template_archivo_subir(slug, nombre, cuerpo))
                return
            if sub == "archivo" and len(segs) >= 6 and metodo == "DELETE":
                self._json(200, api_template_archivo_eliminar(slug, nombre, segs[5:]))
                return
            if sub == "archivo" and len(segs) >= 6 and metodo == "PUT":
                cuerpo = self._leer_cuerpo_json()
                self._json(200, api_template_archivo_renombrar(slug, nombre, segs[5:], cuerpo.get("nombre_nuevo", "")))
                return
            if sub == "muestra" and len(segs) == 5 and metodo == "GET":
                self._json(200, {"contenido": api_template_muestra(slug, nombre)})
                return
            if sub == "historia" and len(segs) == 5 and metodo == "GET":
                self._json(200, api_template_historia(slug, nombre))
                return
            if sub == "historia" and len(segs) == 7 and segs[6] == "contenido" and metodo == "GET":
                version = segs[5]
                self._json(200, {"contenido": api_template_historia_contenido(slug, nombre, version)})
                return
            self._error(404, "ruta de API desconocida")
            return

        if recurso == "equipos":
            if len(segs) == 3:
                if metodo == "GET":
                    self._json(200, api_equipos_list(slug))
                elif metodo == "POST":
                    cuerpo = self._leer_cuerpo_json()
                    self._json(201, api_equipo_new(slug, cuerpo))
                else:
                    self._error(405, "método no soportado")
                return
            if len(segs) == 4:
                equipo_id = segs[3]
                if metodo == "PUT":
                    cuerpo = self._leer_cuerpo_json()
                    self._json(200, api_equipo_editar(slug, equipo_id, cuerpo))
                elif metodo == "DELETE":
                    self._json(200, api_equipo_eliminar(slug, equipo_id))
                else:
                    self._error(405, "método no soportado")
                return
            self._error(404, "ruta de API desconocida")
            return

        if recurso == "autores":
            if len(segs) == 3:
                if metodo == "GET":
                    self._json(200, api_autores_list(slug))
                elif metodo == "POST":
                    cuerpo = self._leer_cuerpo_json()
                    self._json(201, api_autor_new(slug, cuerpo))
                else:
                    self._error(405, "método no soportado")
                return
            autor_id = segs[3]
            if len(segs) == 4:
                if metodo == "PUT":
                    cuerpo = self._leer_cuerpo_json()
                    self._json(200, api_autor_editar(slug, autor_id, cuerpo))
                elif metodo == "DELETE":
                    self._json(200, api_autor_eliminar(slug, autor_id))
                else:
                    self._error(405, "método no soportado")
                return
            self._error(404, "ruta de API desconocida")
            return

        self._error(404, "ruta de API desconocida")

    # ── SSE ────────────────────────────────────────────────────────────────────────────
    def _sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        cola: queue.Queue = queue.Queue(maxsize=100)  # H3: acotada, ver _emitir_evento_sse
        with _sse_lock:
            _sse_colas.add(cola)
        try:
            while True:
                try:
                    payload = cola.get(timeout=15)
                except queue.Empty:
                    payload = b": ping\n\n"
                self.wfile.write(payload)
                self.wfile.flush()
        except (BrokenPipeError, ConnectionResetError, OSError):
            pass
        finally:
            with _sse_lock:
                _sse_colas.discard(cola)

    # ── Fase 1A: puente WS crudo navegador↔`tinymist lsp` (GET /api/lsp) ─────────────────
    def _lsp_bridge(self, query: dict) -> None:
        slug = (query.get("slug") or [None])[0]
        tipo = (query.get("tipo") or ["doc"])[0]
        codigo = (query.get("codigo") or [None])[0]
        if not slug or not codigo or tipo not in ("doc", "plantilla"):
            self._error(400, "faltan/son inválidos slug/codigo/tipo")
            return

        try:
            root, _archivo_editable = _lsp_root_y_editable(tipo, slug, codigo)
        except ApiError as e:
            self._error(e.status, e.mensaje)
            return

        if not ws_server.es_peticion_upgrade(self.headers):
            self._error(400, "se esperaba una petición de upgrade a WebSocket")
            return
        if not ws_server.realizar_handshake(self.headers, self.wfile):
            self._error(400, "handshake WebSocket inválido")
            return

        font_dir = root / "fonts"
        lsp = _asegurar_lsp(root, font_dir if font_dir.is_dir() else None)
        if lsp is None:
            # El handshake ya se aceptó (101) -- cerrar la conexión WS con un mensaje de error
            # JSON-RPC propio en vez de dejar al navegador esperando indefinidamente.
            conexion = ws_server.WebSocketServerConnection(self.rfile, self.wfile)
            conexion.enviar_texto(json.dumps({
                "jsonrpc": "2.0", "method": "$/doctyp/lspNoDisponible", "params": {},
            }))
            conexion.cerrar()
            return

        conexion = ws_server.WebSocketServerConnection(self.rfile, self.wfile)

        def _hacia_navegador(datos: dict) -> None:
            metodo = datos.get("method")
            if metodo in _LSP_RESPUESTAS_LOCALES and "id" in datos:
                # Excepción 2 de la Fase 1A: responder localmente, tinymist nunca ve al
                # navegador para estos 3 métodos (ver _LSP_RESPUESTAS_LOCALES).
                try:
                    lsp.enviar_crudo(json.dumps({
                        "jsonrpc": "2.0", "id": datos["id"],
                        "result": _LSP_RESPUESTAS_LOCALES[metodo](datos),
                    }, ensure_ascii=False).encode("utf-8"))
                except LspServerError:
                    pass
                return
            conexion.enviar_texto(json.dumps(datos, ensure_ascii=False))

        # Reconexión (Fase 1A punto 4): reasociar esta conexión nueva como la activa para el
        # proceso LSP vivo -- no hace falta un segundo `initialize`, el backend ya lo hizo una
        # vez al arrancar el proceso. `_lsp_conexion_activa` se guarda además de `on_message`
        # para que _on_lsp_reiniciado() pueda cerrarla directamente si el proceso se reinicia
        # solo mientras el navegador está inactivo (ver ese callback más arriba).
        global _lsp_conexion_activa
        with _lsp_lock:
            lsp.on_message = _hacia_navegador
            _lsp_conexion_activa = conexion

        try:
            while True:
                mensaje = conexion.leer_mensaje()
                if mensaje is None:
                    break
                _opcode, payload = mensaje
                try:
                    datos = json.loads(payload.decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError):
                    continue
                metodo = datos.get("method")
                if metodo == "workspace/executeCommand":
                    # Excepción 1 de la Fase 1A: allowlist -- el puente no debe volverse un
                    # ejecutor arbitrario (CLAUDE.md §6).
                    comando = (datos.get("params") or {}).get("command")
                    if comando not in _ALLOWLIST_COMANDOS_LSP:
                        if "id" in datos:
                            conexion.enviar_texto(json.dumps({
                                "jsonrpc": "2.0", "id": datos["id"],
                                "error": {"code": -32601, "message": f"comando no permitido: {comando}"},
                            }))
                        continue
                elif metodo == "initialize":
                    # Fase 1B: @codemirror/lsp-client hace SIEMPRE su propio initialize al
                    # conectar (no hay forma de desactivarlo desde su config) -- pero el proceso
                    # tinymist ya fue inicializado UNA vez por el backend al arrancar (Fase 1A) y
                    # LSP no permite un segundo initialize sobre la misma sesión. Se responde acá
                    # mismo con las capabilities ya cacheadas, sin reenviar nada a tinymist.
                    if "id" in datos:
                        resultado = {"capabilities": lsp.capabilities or {}}
                        if lsp.server_info:
                            resultado["serverInfo"] = lsp.server_info
                        conexion.enviar_texto(json.dumps({
                            "jsonrpc": "2.0", "id": datos["id"], "result": resultado,
                        }, ensure_ascii=False))
                    continue
                elif metodo == "shutdown":
                    # Mismo motivo: el ciclo de vida del proceso lo controla el backend
                    # (_detener_lsp_activo(), finally de cmd_web) -- un `disconnect()` del
                    # cliente JS no debe apagar el proceso que otras pestañas siguen usando.
                    if "id" in datos:
                        conexion.enviar_texto(json.dumps({
                            "jsonrpc": "2.0", "id": datos["id"], "result": None,
                        }))
                    continue
                elif metodo in ("initialized", "exit"):
                    continue  # notificaciones -- se descartan, sin reenviar ni responder
                try:
                    lsp.enviar_crudo(payload)
                except LspServerError:
                    break
        finally:
            with _lsp_lock:
                if lsp.on_message is _hacia_navegador:
                    lsp.on_message = None
                if _lsp_conexion_activa is conexion:
                    _lsp_conexion_activa = None

    # ── Estáticos (web/dist/, o placeholder si aún no existe la Etapa 5) ──────────────
    def _estaticos(self, segs: list[str]) -> None:
        if not (WEB_DIST / "index.html").exists():
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(_PLACEHOLDER_HTML)))
            self.end_headers()
            self.wfile.write(_PLACEHOLDER_HTML)
            return

        try:
            destino = _resolver_ruta_segura(WEB_DIST, *segs) if segs else WEB_DIST / "index.html"
        except PathTraversalError:
            self._error(400, "ruta inválida")
            return
        if destino.is_dir():
            destino = destino / "index.html"
        if not destino.exists():
            destino = WEB_DIST / "index.html"  # fallback SPA

        tipos = {".html": "text/html", ".js": "application/javascript", ".css": "text/css",
                 ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png",
                 ".wasm": "application/wasm", ".ttf": "font/ttf"}
        content_type = tipos.get(destino.suffix, "application/octet-stream")
        cuerpo = destino.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)


# ── Arranque ───────────────────────────────────────────────────────────────────────────

def _build_frontend() -> None:
    """Compila la SPA (web/ -> web/dist/) con npm antes de levantar el servidor.

    Se salta si no hay npm disponible o no existe web/package.json (entornos donde
    el frontend aun no se agrego); en ese caso el servidor sirve el placeholder.
    """
    pkg_json = WEB_DIR / "package.json"
    if not pkg_json.exists():
        return

    npm = shutil.which("npm")
    if not npm:
        core._warn("npm no esta disponible en PATH; se omite el build de la SPA "
                    "(se sirve el placeholder).")
        return

    node_modules = WEB_DIR / "node_modules"
    if not node_modules.exists() or pkg_json.stat().st_mtime > node_modules.stat().st_mtime:
        print(f"  {core._c(core._C.DIM, 'Instalando dependencias de la SPA (npm install)...')}")
        subprocess.run([npm, "install"], cwd=str(WEB_DIR), check=True)

    print(f"  {core._c(core._C.DIM, 'Compilando la SPA (npm run build)...')}")
    subprocess.run([npm, "run", "build"], cwd=str(WEB_DIR), check=True)
    core._ok("Build de la SPA lista.")


def cmd_web(args) -> None:
    global _preview_legacy_forzado, _VERBOSE
    host = args.host or "127.0.0.1"
    port = args.port or 8787
    _preview_legacy_forzado = getattr(args, "legacy_preview", False)
    if _preview_legacy_forzado:
        core._warn("--legacy-preview: se usará la vista previa typst.ts (sin clic↔cursor).")
    _VERBOSE = getattr(args, "verbose", False)
    if _VERBOSE:
        core._warn("--verbose: se verán accesos HTTP y la salida en vivo de tinymist (preview/lsp).")

    if not getattr(args, "no_build", False):
        try:
            _build_frontend()
        except subprocess.CalledProcessError as e:
            core._warn(f"Build de la SPA fallo ({e}); se sirve el contenido de web/dist/ "
                        "existente (o el placeholder) sin actualizar.")

    servidor = ThreadingHTTPServer((host, port), _DoctypRequestHandler)
    servidor.daemon_threads = True

    hilo_eventos = threading.Thread(target=_eventos_loop, daemon=True)
    hilo_eventos.start()

    # Etapa 18: en contenedor, `docker stop`/`restart` mandan SIGTERM (no SIGINT) al proceso
    # PID 1 -- sin este handler, Python lo ignora por defecto, serve_forever() nunca retorna, y
    # el orquestador espera el grace period completo y termina en SIGKILL, saltándose el
    # `finally` de abajo (mismo problema que un `pkill -9` manual, ya documentado en CLAUDE.md
    # §14/Etapa 15 como fuente de procesos tinymist huérfanos). Traducir SIGTERM a la misma
    # excepción que ya maneja Ctrl+C reusa el único camino de shutdown limpio que existe.
    import signal as _signal

    def _on_sigterm(signum, frame):
        raise KeyboardInterrupt

    _signal.signal(_signal.SIGTERM, _on_sigterm)

    url = f"http://{host}:{port}/"
    core._ok(f"Servidor doctyp web escuchando en {core._c(core._C.BOLD, url)}")
    if not getattr(args, "no_browser", False):
        webbrowser.open(url)

    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        print()
        core._ok("Servidor detenido.")
    finally:
        _detener_preview_activa()  # Plan 15 F2: cero procesos tinymist huérfanos al salir.
        _detener_lsp_activo()  # Fase 1A: idem para el proceso `tinymist lsp`.
        servidor.server_close()
