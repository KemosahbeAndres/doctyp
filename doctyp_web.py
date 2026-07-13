#!/usr/bin/env python3
"""
doctyp_web — Backend HTTP de `doctyp web` (Etapa 4 de la arquitectura v3, ver CLAUDE.md §6).

Servidor stdlib puro (http.server.ThreadingHTTPServer): API JSON bajo /api/... que envuelve
la lógica ya existente de doctyp.py (nunca reimplementa lógica de negocio aquí), SSE en
/api/events para notificar cambios en org.json/documentos, y estáticos desde web/dist/ (o un
placeholder si la Etapa 5 aún no generó el build).

Seguridad: bind por defecto a 127.0.0.1; toda ruta se resuelve y valida contra las dos raíces
permitidas (organizations/ y DOCS_ROOT) sin path traversal; escrituras atómicas (reusa
_escribir_json_atomico de doctyp.py); sin ejecución de comandos arbitrarios; compilar vía web
reutiliza exactamente compilar_typ().

No requiere paquetes externos (solo stdlib).
"""
from __future__ import annotations
import json, os, queue, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

import doctyp as core

WEB_DIST = core.SCRIPT_DIR / "web" / "dist"

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


def _cargar_org_api(slug: str) -> dict:
    _slug_seguro(slug)
    _resolver_ruta_segura(core.organizations_dir(), slug)
    if not core.org_path(slug).exists():
        raise ApiError(404, f"no existe la organización '{slug}'")
    return core.cargar_org(slug)


def _doc_o_404(org: dict, codigo_base: str) -> dict:
    doc = core.buscar_doc_org_por_codigo(org, codigo_base)
    if doc is None:
        raise ApiError(404, f"no existe el documento '{codigo_base}'")
    return doc


def api_orgs_list() -> list[dict]:
    activa = core.cargar_settings().get("local", {}).get("org_activa")
    out = []
    for slug in core.listar_orgs():
        org = core.cargar_org(slug)
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


def api_docs_list(slug: str) -> list[dict]:
    org = _cargar_org_api(slug)
    return sorted(org["documentos"], key=lambda d: (d.get("anio", 0), d.get("correlativo", 0)))


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


def api_doc_typ_put(slug: str, codigo_base: str, contenido: str) -> dict:
    org = _cargar_org_api(slug)
    _doc_o_404(org, codigo_base)
    ruta = _ruta_typ_segura(slug, codigo_base)
    if not ruta.parent.exists():
        raise ApiError(404, f"la carpeta del documento no existe: {ruta.parent}")
    ruta.write_text(contenido, encoding="utf-8")
    return {"ok": True}


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


def api_equipos_list(slug: str) -> list[dict]:
    return _cargar_org_api(slug).get("equipos", [])


def api_autores_list(slug: str) -> list[dict]:
    return _cargar_org_api(slug).get("autores", [])


# ── SSE: detección de cambios por polling de mtimes (sin inotify/watchdog) ────────────────

_sse_lock = threading.Lock()
_sse_colas: set[queue.Queue] = set()


def _snapshot_mtimes() -> dict[str, float]:
    snap: dict[str, float] = {}
    for slug in core.listar_orgs():
        p = core.org_path(slug)
        try:
            snap[f"org:{slug}"] = p.stat().st_mtime
        except OSError:
            continue
        root = core.docs_root_org(slug)
        try:
            with os.scandir(root) as it:
                mtimes = [e.stat().st_mtime for e in it if e.is_dir()]
        except OSError:
            mtimes = []
        snap[f"docs:{slug}"] = max(mtimes) if mtimes else 0.0
    return snap


def _eventos_loop(intervalo: float = 1.5) -> None:
    anterior = _snapshot_mtimes()
    while True:
        time.sleep(intervalo)
        actual = _snapshot_mtimes()
        cambios = {k: v for k, v in actual.items() if anterior.get(k) != v}
        if cambios:
            evento = {"tipo": "org-changed" if any(k.startswith("org:") for k in cambios)
                       else "docs-changed", "claves": sorted(cambios)}
            payload = f"data: {json.dumps(evento, ensure_ascii=False)}\n\n".encode("utf-8")
            with _sse_lock:
                colas = list(_sse_colas)
            for cola in colas:
                cola.put(payload)
        anterior = actual


# ── Handler HTTP ────────────────────────────────────────────────────────────────────────

class _DoctypRequestHandler(BaseHTTPRequestHandler):
    server_version = "doctyp-web/1.0"

    def log_message(self, fmt, *args):
        pass  # silencioso; evita ruido en stdout durante uso normal

    def _json(self, status: int, data) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: int, mensaje: str) -> None:
        self._json(status, {"error": mensaje})

    def _leer_cuerpo_json(self) -> dict:
        largo = int(self.headers.get("Content-Length", 0) or 0)
        if largo == 0:
            return {}
        crudo = self.rfile.read(largo)
        try:
            return json.loads(crudo.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise ApiError(400, "cuerpo JSON inválido")

    def _despachar(self, metodo: str) -> None:
        partes_url = urlsplit(self.path)
        segs = [s for s in partes_url.path.split("/") if s]

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

    def do_GET(self):
        partes_url = urlsplit(self.path)
        if partes_url.path == "/api/events":
            self._sse()
            return
        self._despachar("GET")

    def do_POST(self):
        self._despachar("POST")

    def do_PUT(self):
        self._despachar("PUT")

    # ── Ruteo de la API ────────────────────────────────────────────────────────────────
    def _api(self, metodo: str, segs: list[str], query: dict) -> None:
        if not segs or segs[0] != "orgs":
            self._error(404, "ruta de API desconocida")
            return

        if len(segs) == 1:  # /api/orgs
            self._json(200, api_orgs_list())
            return

        slug = _slug_seguro(segs[1])
        if len(segs) == 2:  # /api/orgs/<slug>
            self._json(200, api_org_get(slug))
            return

        recurso = segs[2]
        if recurso == "documentos":
            if len(segs) == 3:  # /api/orgs/<slug>/documentos
                self._json(200, api_docs_list(slug))
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
            if sub == "historia" and len(segs) == 5 and metodo == "GET":
                self._json(200, api_doc_historia(slug, codigo_base))
                return
            if sub == "save" and len(segs) == 5 and metodo == "POST":
                cuerpo = self._leer_cuerpo_json()
                self._json(200, api_doc_save(slug, codigo_base, cuerpo.get("mensaje", "")))
                return
            if sub == "compile" and len(segs) == 5 and metodo == "POST":
                cuerpo = self._leer_cuerpo_json()
                self._json(200, api_doc_compile(slug, codigo_base, cuerpo.get("mensaje")))
                return
            self._error(404, "ruta de API desconocida")
            return

        if recurso == "plantillas" and len(segs) == 3:
            self._json(200, api_templates_list(slug))
            return
        if recurso == "equipos" and len(segs) == 3:
            self._json(200, api_equipos_list(slug))
            return
        if recurso == "autores" and len(segs) == 3:
            self._json(200, api_autores_list(slug))
            return

        self._error(404, "ruta de API desconocida")

    # ── SSE ────────────────────────────────────────────────────────────────────────────
    def _sse(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.end_headers()

        cola: queue.Queue = queue.Queue()
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
                 ".json": "application/json", ".svg": "image/svg+xml", ".png": "image/png"}
        content_type = tipos.get(destino.suffix, "application/octet-stream")
        cuerpo = destino.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)


# ── Arranque ───────────────────────────────────────────────────────────────────────────

def cmd_web(args) -> None:
    host = args.host or "127.0.0.1"
    port = args.port or 8787

    servidor = ThreadingHTTPServer((host, port), _DoctypRequestHandler)
    servidor.daemon_threads = True

    hilo_eventos = threading.Thread(target=_eventos_loop, daemon=True)
    hilo_eventos.start()

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
        servidor.server_close()
