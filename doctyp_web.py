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
import datetime, difflib, json, mimetypes, os, queue, shutil, subprocess, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, parse_qs, unquote

import doctyp as core

WEB_DIR = core.SCRIPT_DIR / "web"
WEB_DIST = WEB_DIR / "dist"

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


def api_org_new(payload: dict) -> dict:
    slug = (payload.get("slug") or "").strip().lower()
    if not core._slug_valido(slug):
        raise ApiError(400, "el slug solo admite minúsculas, dígitos y guiones (p. ej. 'mi-org')")
    if core.org_path(slug).exists():
        raise ApiError(400, f"ya existe una organización '{slug}'")
    nombre = payload.get("nombre") or slug
    org = core._org_vacia(slug, nombre)
    core.guardar_org(slug, org)

    settings = core.cargar_settings()
    settings.setdefault("local", {})
    if not settings["local"].get("org_activa"):
        settings["local"]["org_activa"] = slug
        core.guardar_settings(settings)
    return {"slug": slug, "nombre": nombre}


def api_org_activar(slug: str) -> dict:
    _cargar_org_api(slug)
    settings = core.cargar_settings()
    settings.setdefault("local", {})["org_activa"] = slug
    core.guardar_settings(settings)
    return {"ok": True, "org_activa": slug}


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

    autor_org = core.autor_activo(org)
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


def api_doc_typ_put(slug: str, codigo_base: str, contenido: str) -> dict:
    org = _cargar_org_api(slug)
    _doc_o_404(org, codigo_base)
    ruta = _ruta_typ_segura(slug, codigo_base)
    if not ruta.parent.exists():
        raise ApiError(404, f"la carpeta del documento no existe: {ruta.parent}")
    ruta.write_text(contenido, encoding="utf-8")
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
    activo_id = core.autor_activo(org).get("id")
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


def api_autor_activar(slug: str, autor_id: str) -> dict:
    org = _cargar_org_api(slug)
    core.autor_buscar(org, autor_id)
    settings = core.cargar_settings()
    settings.setdefault("local", {})["autor_activo"] = autor_id
    core.guardar_settings(settings)
    return {"ok": True, "autor_activo": autor_id}


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

    def _binario(self, status: int, cuerpo: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(cuerpo)))
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

    def do_DELETE(self):
        self._despachar("DELETE")

    # ── Ruteo de la API ────────────────────────────────────────────────────────────────
    def _api(self, metodo: str, segs: list[str], query: dict) -> None:
        if segs and segs[0] == "tipos-documento" and len(segs) == 1 and metodo == "GET":
            self._json(200, api_tipos_documento())
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
            if len(segs) == 5 and segs[4] == "activar" and metodo == "POST":
                self._json(200, api_autor_activar(slug, autor_id))
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

    if not (WEB_DIR / "node_modules").exists():
        print(f"  {core._c(core._C.DIM, 'Instalando dependencias de la SPA (npm install)...')}")
        subprocess.run([npm, "install"], cwd=str(WEB_DIR), check=True)

    print(f"  {core._c(core._C.DIM, 'Compilando la SPA (npm run build)...')}")
    subprocess.run([npm, "run", "build"], cwd=str(WEB_DIR), check=True)
    core._ok("Build de la SPA lista.")


def cmd_web(args) -> None:
    host = args.host or "127.0.0.1"
    port = args.port or 8787

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
