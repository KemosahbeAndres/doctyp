#!/usr/bin/env python3
"""
doctyp_db — Acceso a datos SQLite (Etapa 19 de PLAN-V4.md), reemplaza org.json como fuente
de verdad de organizaciones, equipos, autores/usuarios, plantillas, documentos y versiones.

Diseño clave para no reescribir cada sitio de doctyp.py/doctyp_web.py que hoy manipula el
dict de org.json: `cargar_org(slug)` devuelve un dict con la MISMA forma que tenía org.json,
y `guardar_org(slug, dict)` lo persiste completo dentro de una transacción (reemplaza
equipos/autores/documentos/versiones de esa org por el contenido del dict). Todo el código
que ya sabe mutar ese dict (autor_crear, equipo_editar, cmd_nuevo, etc.) sigue funcionando
sin cambios; solo cambia dónde vive el dato.

El único punto que sí necesita una vía transaccional propia (no basta con round-trip de
dict) es la asignación de correlativo: `asignar_correlativo(slug, anio)` hace
BEGIN IMMEDIATE + lee máximo + escribe en una sola transacción, cerrando la condición de
carrera que tenía next_correlativo_org() sobre el dict en memoria.

No requiere paquetes externos (sqlite3 es stdlib).
"""
from __future__ import annotations
import json, os, sqlite3, sys, threading
from pathlib import Path
from contextlib import contextmanager

SCHEMA_VERSION = 1

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS meta (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT UNIQUE,
    password_hash TEXT,
    nombre        TEXT NOT NULL,
    cargo         TEXT,
    correo        TEXT,
    activo        INTEGER NOT NULL DEFAULT 1,
    org_activa_id TEXT REFERENCES organizations(id) ON DELETE SET NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token_hash  TEXT NOT NULL UNIQUE,
    expires_at  TEXT NOT NULL,
    ip          TEXT,
    user_agent  TEXT,
    created_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS api_tokens (
    id            TEXT PRIMARY KEY,
    user_id       TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    nombre        TEXT,
    token_hash    TEXT NOT NULL UNIQUE,
    scopes        TEXT,
    expires_at    TEXT,
    last_used_at  TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS organizations (
    id          TEXT PRIMARY KEY,
    slug        TEXT UNIQUE NOT NULL,
    nombre      TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS org_members (
    org_id   TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id  TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    autor_id TEXT NOT NULL,
    role     TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('admin','member')),
    PRIMARY KEY (org_id, user_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_org_members_autor ON org_members(org_id, autor_id);

CREATE TABLE IF NOT EXISTS teams (
    id          TEXT NOT NULL,
    org_id      TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    nombre      TEXT NOT NULL,
    PRIMARY KEY (org_id, id)
);

CREATE TABLE IF NOT EXISTS team_members (
    org_id   TEXT NOT NULL,
    team_id  TEXT NOT NULL,
    autor_id TEXT NOT NULL,
    PRIMARY KEY (org_id, team_id, autor_id),
    FOREIGN KEY (org_id, team_id) REFERENCES teams(org_id, id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS templates (
    org_id     TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    nombre     TEXT NOT NULL,
    es_default INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (org_id, nombre)
);

CREATE TABLE IF NOT EXISTS documents (
    id           TEXT PRIMARY KEY,
    org_id       TEXT NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    codigo_base  TEXT NOT NULL,
    area         TEXT, tipo TEXT, categoria TEXT,
    anio         INTEGER NOT NULL,
    correlativo  INTEGER NOT NULL,
    titulo       TEXT,
    autor_id     TEXT,
    equipo_id    TEXT,
    plantilla    TEXT,
    ruta         TEXT,
    creado       TEXT,
    UNIQUE(org_id, codigo_base)
);
CREATE INDEX IF NOT EXISTS idx_documents_org_anio ON documents(org_id, anio);

CREATE TABLE IF NOT EXISTS document_versions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    version      TEXT NOT NULL,
    fecha        TEXT,
    creado       TEXT,
    mensaje      TEXT,
    snapshot     TEXT,
    orden        INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_versions_doc ON document_versions(document_id, orden);

CREATE TABLE IF NOT EXISTS correlative_counters (
    org_id  TEXT NOT NULL,
    anio    INTEGER NOT NULL,
    ultimo  INTEGER NOT NULL,
    PRIMARY KEY (org_id, anio)
);
"""


def db_path() -> Path:
    """Ubicación de doctyp.db. Override vía DOCTYP_DB_PATH (Etapa 18, contenedor)."""
    override = os.environ.get("DOCTYP_DB_PATH")
    if override:
        return Path(override)
    from doctyp import SCRIPT_DIR  # import perezoso: evita ciclo doctyp<->doctyp_db
    return SCRIPT_DIR / "doctyp.db"


_local = threading.local()
# `doctyp_web.py` corre en ThreadingHTTPServer: sqlite3 prohíbe usar una conexión fuera del
# hilo que la creó, así que cada hilo obtiene su propia conexión (thread-local) contra el
# mismo archivo -- WAL + BEGIN IMMEDIATE siguen siendo quienes serializan las escrituras
# reales entre conexiones/hilos/procesos, no un lock de Python.


def _connect() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is not None:
        return conn
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA_SQL)
    _migrar_columnas_nuevas(conn)
    conn.execute(
        "INSERT OR IGNORE INTO meta(clave, valor) VALUES ('schema_version', ?)",
        (str(SCHEMA_VERSION),),
    )
    _local.conn = conn
    return conn


def _migrar_columnas_nuevas(conn: sqlite3.Connection) -> None:
    """`CREATE TABLE IF NOT EXISTS` no altera una tabla ya creada -- las columnas nuevas
    agregadas después del primer despliegue necesitan un ALTER TABLE explícito, idempotente
    (se corre en cada conexión, revisa PRAGMA table_info antes de intentarlo)."""
    columnas = {r["name"] for r in conn.execute("PRAGMA table_info(users)")}
    if "org_activa_id" not in columnas:
        conn.execute(
            "ALTER TABLE users ADD COLUMN org_activa_id TEXT "
            "REFERENCES organizations(id) ON DELETE SET NULL"
        )


@contextmanager
def _tx(conn: sqlite3.Connection | None = None, immediate: bool = False):
    """Transacción explícita. `immediate=True` para operaciones que necesitan serializarse
    de verdad (asignación de correlativo) -- BEGIN IMMEDIATE toma el lock de escritura ya al
    empezar, en vez de esperar a la primera escritura (evita la ventana de carrera de
    'deferred' que es el modo por defecto de sqlite3)."""
    c = conn or _connect()
    c.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    try:
        yield c
        c.execute("COMMIT")
    except Exception:
        c.execute("ROLLBACK")
        raise


# ── Organizaciones: compat dict-shape con org.json (ver docstring del módulo) ─────────────

def listar_orgs() -> list[str]:
    conn = _connect()
    rows = conn.execute("SELECT slug FROM organizations ORDER BY slug").fetchall()
    return [r["slug"] for r in rows]


def existe_org(slug: str) -> bool:
    conn = _connect()
    return conn.execute("SELECT 1 FROM organizations WHERE slug = ?", (slug,)).fetchone() is not None


def crear_org_vacia(slug: str, nombre: str) -> str:
    """Devuelve el id interno (UUID) de la organización recién creada -- lo necesitan los
    llamadores que además deben vincular a un usuario como miembro (ver
    doctyp_web.py: _crear_org_con_admin) sin depender de una segunda consulta."""
    import uuid, datetime
    org_id = str(uuid.uuid4())
    conn = _connect()
    with _tx(conn):
        conn.execute(
            "INSERT INTO organizations(id, slug, nombre, config_json, created_at) VALUES (?,?,?,?,?)",
            (org_id, slug, nombre,
             json.dumps({"correlativo_inicio": {}, "plantilla_default": "informe-ti"}),
             datetime.datetime.now().isoformat(timespec="seconds")),
        )
    return org_id


def _org_id(conn: sqlite3.Connection, slug: str) -> str:
    row = conn.execute("SELECT id FROM organizations WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        sys.exit(f"ERROR: no existe la organización '{slug}'.")
    return row["id"]


def obtener_org_id(slug: str) -> str | None:
    """Variante pública/no-fatal de _org_id -- para llamadores que ya validaron que la org existe
    (p. ej. doctyp_web.py: api_org_activar, tras _cargar_org_api) y solo necesitan el id interno
    para guardar una referencia (org_activa_id)."""
    conn = _connect()
    row = conn.execute("SELECT id FROM organizations WHERE slug = ?", (slug,)).fetchone()
    return row["id"] if row else None


def cargar_org(slug: str) -> dict:
    """Reconstruye el dict con forma de org.json a partir de la BD."""
    conn = _connect()
    org_row = conn.execute("SELECT * FROM organizations WHERE slug = ?", (slug,)).fetchone()
    if org_row is None:
        sys.exit(f"ERROR: no existe la organización '{slug}'.")
    org_id = org_row["id"]
    config = json.loads(org_row["config_json"] or "{}")
    config.setdefault("correlativo_inicio", {})
    config.setdefault("plantilla_default", "informe-ti")

    equipos = []
    for t in conn.execute("SELECT * FROM teams WHERE org_id = ? ORDER BY id", (org_id,)):
        equipos.append({"id": t["id"], "nombre": t["nombre"]})

    equipos_por_autor: dict[str, list[str]] = {}
    for tm in conn.execute("SELECT * FROM team_members WHERE org_id = ?", (org_id,)):
        equipos_por_autor.setdefault(tm["autor_id"], []).append(tm["team_id"])

    autores = []
    for om in conn.execute(
        """SELECT om.autor_id, om.role, u.nombre, u.cargo, u.correo, u.email, u.id AS user_id
           FROM org_members om JOIN users u ON u.id = om.user_id
           WHERE om.org_id = ? ORDER BY om.autor_id""",
        (org_id,),
    ):
        autores.append({
            "id": om["autor_id"],
            "nombre": om["nombre"],
            "cargo": om["cargo"] or "",
            "correo": om["correo"] or om["email"] or "",
            "equipos": equipos_por_autor.get(om["autor_id"], []),
            "user_id": om["user_id"],
            "role": om["role"],
        })

    documentos = []
    for d in conn.execute(
        "SELECT * FROM documents WHERE org_id = ? ORDER BY anio, correlativo", (org_id,)
    ):
        versiones = []
        for v in conn.execute(
            "SELECT * FROM document_versions WHERE document_id = ? ORDER BY orden",
            (d["id"],),
        ):
            entry = {"version": v["version"], "fecha": v["fecha"], "creado": v["creado"]}
            if v["mensaje"] is not None:
                entry["mensaje"] = v["mensaje"]
            if v["snapshot"] is not None:
                entry["snapshot"] = v["snapshot"]
            versiones.append(entry)
        documentos.append({
            "codigo_base": d["codigo_base"],
            "area": d["area"], "tipo": d["tipo"], "categoria": d["categoria"],
            "anio": d["anio"], "correlativo": d["correlativo"],
            "titulo": d["titulo"], "autor_id": d["autor_id"], "equipo_id": d["equipo_id"],
            "plantilla": d["plantilla"], "ruta": d["ruta"], "creado": d["creado"],
            "versiones": versiones,
        })

    return {
        "schema": 1,
        "slug": slug,
        "nombre": org_row["nombre"],
        "config": config,
        "equipos": equipos,
        "autores": autores,
        "documentos": documentos,
    }


def guardar_org(slug: str, data: dict) -> None:
    """Reemplaza equipos/autores/plantillas/documentos/versiones de la org por el contenido
    del dict, dentro de una sola transacción. autores[] sin user_id asociado (autor creado
    solo como metadato organizativo, sin cuenta de login todavía) generan un usuario interno
    'sin credenciales' (password_hash NULL, sin email) para conservar la invariante
    usuario=autor de la Etapa 20 sin bloquear el modo mono-usuario actual."""
    import uuid, datetime
    conn = _connect()
    with _tx(conn):
        org_id = _org_id(conn, slug)
        conn.execute(
            "UPDATE organizations SET nombre = ?, config_json = ? WHERE id = ?",
            (data.get("nombre", slug), json.dumps(data.get("config", {}), ensure_ascii=False), org_id),
        )

        conn.execute("DELETE FROM teams WHERE org_id = ?", (org_id,))
        conn.execute("DELETE FROM team_members WHERE org_id = ?", (org_id,))
        for eq in data.get("equipos", []):
            conn.execute(
                "INSERT INTO teams(id, org_id, nombre) VALUES (?,?,?)",
                (eq["id"], org_id, eq.get("nombre") or eq["id"]),
            )

        conn.execute("DELETE FROM org_members WHERE org_id = ?", (org_id,))
        for autor in data.get("autores", []):
            autor_id = autor["id"]
            user_id = autor.get("user_id")
            if not user_id:
                existente = conn.execute(
                    "SELECT user_id FROM org_members WHERE org_id = ? AND autor_id = ?",
                    (org_id, autor_id),
                ).fetchone()
                if existente:
                    user_id = existente["user_id"]
                else:
                    email = autor.get("correo") or None
                    row = None
                    if email:
                        row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
                    if row:
                        user_id = row["id"]
                    else:
                        user_id = str(uuid.uuid4())
                        conn.execute(
                            """INSERT INTO users(id, email, password_hash, nombre, cargo, correo,
                                                  activo, created_at)
                               VALUES (?,?,NULL,?,?,?,1,?)""",
                            (user_id, email, autor.get("nombre") or "", autor.get("cargo") or "",
                             autor.get("correo") or "",
                             datetime.datetime.now().isoformat(timespec="seconds")),
                        )
            else:
                conn.execute(
                    "UPDATE users SET nombre = ?, cargo = ?, correo = ? WHERE id = ?",
                    (autor.get("nombre") or "", autor.get("cargo") or "", autor.get("correo") or "",
                     user_id),
                )
            role = autor.get("role") or "member"
            conn.execute(
                "INSERT INTO org_members(org_id, user_id, autor_id, role) VALUES (?,?,?,?)",
                (org_id, user_id, autor_id, role),
            )
            for eq_id in autor.get("equipos", []):
                conn.execute(
                    "INSERT OR IGNORE INTO team_members(org_id, team_id, autor_id) VALUES (?,?,?)",
                    (org_id, eq_id, autor_id),
                )

        docs_existentes = {
            r["codigo_base"]: r["id"]
            for r in conn.execute("SELECT codigo_base, id FROM documents WHERE org_id = ?", (org_id,))
        }
        codigos_nuevos = {d["codigo_base"] for d in data.get("documentos", [])}
        for codigo, doc_id in docs_existentes.items():
            if codigo not in codigos_nuevos:
                conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

        for doc in data.get("documentos", []):
            doc_id = docs_existentes.get(doc["codigo_base"])
            if doc_id is None:
                doc_id = str(uuid.uuid4())
                conn.execute(
                    """INSERT INTO documents(id, org_id, codigo_base, area, tipo, categoria,
                                              anio, correlativo, titulo, autor_id, equipo_id,
                                              plantilla, ruta, creado)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (doc_id, org_id, doc["codigo_base"], doc.get("area"), doc.get("tipo"),
                     doc.get("categoria"), doc["anio"], doc["correlativo"], doc.get("titulo"),
                     doc.get("autor_id"), doc.get("equipo_id"), doc.get("plantilla"),
                     doc.get("ruta"), doc.get("creado")),
                )
            else:
                conn.execute(
                    """UPDATE documents SET area=?, tipo=?, categoria=?, anio=?, correlativo=?,
                                             titulo=?, autor_id=?, equipo_id=?, plantilla=?, ruta=?
                       WHERE id = ?""",
                    (doc.get("area"), doc.get("tipo"), doc.get("categoria"), doc["anio"],
                     doc["correlativo"], doc.get("titulo"), doc.get("autor_id"),
                     doc.get("equipo_id"), doc.get("plantilla"), doc.get("ruta"), doc_id),
                )
                conn.execute("DELETE FROM document_versions WHERE document_id = ?", (doc_id,))
            for i, v in enumerate(doc.get("versiones", [])):
                conn.execute(
                    """INSERT INTO document_versions(document_id, version, fecha, creado,
                                                       mensaje, snapshot, orden)
                       VALUES (?,?,?,?,?,?,?)""",
                    (doc_id, v["version"], v.get("fecha"), v.get("creado"),
                     v.get("mensaje"), v.get("snapshot"), i),
                )


def asignar_correlativo(slug: str, anio: int, fallback: int = 0) -> int:
    """Asigna el siguiente correlativo del año de forma transaccional (BEGIN IMMEDIATE):
    cierra la condición de carrera que tenía next_correlativo_org() sobre el dict en memoria
    (PLAN-V4.md §0.2). No se usa junto con guardar_org() en la misma operación de alta de
    documento: el caller llama esto primero para obtener el número, luego construye el
    documento y hace guardar_org() -- la fila de correlative_counters queda como tope
    incluso si guardar_org() todavía no insertó el documento (evita reutilizar el número si
    la escritura del .typ falla después de reservarlo)."""
    conn = _connect()
    with _tx(conn, immediate=True):
        org_id = _org_id(conn, slug)
        config = json.loads(
            conn.execute("SELECT config_json FROM organizations WHERE id = ?", (org_id,)).fetchone()["config_json"]
            or "{}"
        )
        inicio = (config.get("correlativo_inicio") or {}).get(str(anio))

        row = conn.execute(
            "SELECT ultimo FROM correlative_counters WHERE org_id = ? AND anio = ?",
            (org_id, anio),
        ).fetchone()
        max_doc = conn.execute(
            "SELECT MAX(correlativo) AS m FROM documents WHERE org_id = ? AND anio = ?",
            (org_id, anio),
        ).fetchone()["m"] or 0
        actual = max(row["ultimo"] if row else 0, max_doc, fallback)
        proximo = actual + 1
        if inicio is not None and int(inicio) > proximo:
            proximo = int(inicio)

        if row is None:
            conn.execute(
                "INSERT INTO correlative_counters(org_id, anio, ultimo) VALUES (?,?,?)",
                (org_id, anio, proximo),
            )
        else:
            conn.execute(
                "UPDATE correlative_counters SET ultimo = ? WHERE org_id = ? AND anio = ?",
                (proximo, org_id, anio),
            )
        return proximo


# ── Usuarios (Etapa 20) ────────────────────────────────────────────────────────────────────

def contar_usuarios() -> int:
    conn = _connect()
    return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def obtener_usuario_por_email(email: str) -> dict | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    return dict(row) if row else None


def obtener_usuario(user_id: str) -> dict | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    return dict(row) if row else None


def listar_usuarios() -> list[dict]:
    conn = _connect()
    return [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY created_at")]


def crear_usuario(email: str, nombre: str, password_hash: str | None,
                   cargo: str = "", correo: str | None = None) -> dict:
    import uuid, datetime
    conn = _connect()
    uid = str(uuid.uuid4())
    with _tx(conn):
        conn.execute(
            """INSERT INTO users(id, email, password_hash, nombre, cargo, correo, activo, created_at)
               VALUES (?,?,?,?,?,?,1,?)""",
            (uid, email, password_hash, nombre, cargo, correo or email,
             datetime.datetime.now().isoformat(timespec="seconds")),
        )
    return obtener_usuario(uid)


def fijar_password(user_id: str, password_hash: str) -> None:
    conn = _connect()
    with _tx(conn):
        conn.execute("UPDATE users SET password_hash = ? WHERE id = ?", (password_hash, user_id))


def fijar_org_activa(user_id: str, org_id: str | None) -> None:
    """Preferencia de organización activa POR USUARIO (Etapa de registro/invitaciones) -- a
    diferencia de settings.json (`local.org_activa`), que solo aplica al CLI de un operador
    local, sin relación con el modelo multi-usuario del servidor web."""
    conn = _connect()
    with _tx(conn):
        conn.execute("UPDATE users SET org_activa_id = ? WHERE id = ?", (org_id, user_id))


def obtener_org_activa(user_id: str) -> str | None:
    """Devuelve el SLUG (no el id interno) de la organización activa del usuario, o None si no
    tiene ninguna fijada o la que tenía fijada ya no existe."""
    conn = _connect()
    row = conn.execute(
        """SELECT o.slug FROM users u JOIN organizations o ON o.id = u.org_activa_id
           WHERE u.id = ?""",
        (user_id,),
    ).fetchone()
    return row["slug"] if row else None


def agregar_miembro_org(slug: str, user_id: str, autor_id: str, role: str = "member") -> None:
    conn = _connect()
    with _tx(conn):
        org_id = _org_id(conn, slug)
        conn.execute(
            "INSERT OR REPLACE INTO org_members(org_id, user_id, autor_id, role) VALUES (?,?,?,?)",
            (org_id, user_id, autor_id, role),
        )


# ── Sesiones ────────────────────────────────────────────────────────────────────────────

def crear_sesion(user_id: str, token_hash: str, expires_at: str,
                  ip: str | None = None, user_agent: str | None = None) -> str:
    import uuid, datetime
    conn = _connect()
    sid = str(uuid.uuid4())
    with _tx(conn):
        conn.execute(
            """INSERT INTO sessions(id, user_id, token_hash, expires_at, ip, user_agent, created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (sid, user_id, token_hash, expires_at, ip, user_agent,
             datetime.datetime.now().isoformat(timespec="seconds")),
        )
    return sid


def obtener_sesion_por_token_hash(token_hash: str) -> dict | None:
    conn = _connect()
    row = conn.execute("SELECT * FROM sessions WHERE token_hash = ?", (token_hash,)).fetchone()
    return dict(row) if row else None


def eliminar_sesion(token_hash: str) -> None:
    conn = _connect()
    with _tx(conn):
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))


def purgar_sesiones_expiradas(ahora_iso: str) -> None:
    conn = _connect()
    with _tx(conn):
        conn.execute("DELETE FROM sessions WHERE expires_at < ?", (ahora_iso,))


# ── Migración desde org.json (doctyp migrate) ──────────────────────────────────────────────

def migrar_desde_json(organizations_dir: Path, verbose: bool = True) -> dict:
    """Importa cada organizations/<slug>/org.json a la BD (idempotente: si la org ya existe
    en la BD, la actualiza en vez de duplicarla -- usa guardar_org sobre datos ya cargados).
    Devuelve un resumen {slug: {"autores": n, "documentos": n, "equipos": n}} para --check."""
    resumen = {}
    if not organizations_dir.exists():
        return resumen
    for org_dir in sorted(organizations_dir.iterdir()):
        json_path = org_dir / "org.json"
        if not json_path.exists():
            continue
        data = json.loads(json_path.read_text(encoding="utf-8"))
        slug = data["slug"]
        if not existe_org(slug):
            crear_org_vacia(slug, data.get("nombre", slug))
        guardar_org(slug, data)
        resumen[slug] = {
            "autores": len(data.get("autores", [])),
            "equipos": len(data.get("equipos", [])),
            "documentos": len(data.get("documentos", [])),
        }
        if verbose:
            print(f"  migrado: {slug} — autores={resumen[slug]['autores']} "
                  f"equipos={resumen[slug]['equipos']} documentos={resumen[slug]['documentos']}")
    return resumen


def verificar_migracion(organizations_dir: Path) -> bool:
    """--check: compara conteos BD vs. org.json.migrated (o org.json si no se archivó aún)
    sin modificar nada. Devuelve True si todo coincide."""
    ok = True
    for org_dir in sorted(organizations_dir.iterdir()):
        json_path = org_dir / "org.json"
        migrated_path = org_dir / "org.json.migrated"
        src = json_path if json_path.exists() else migrated_path
        if not src.exists():
            continue
        data = json.loads(src.read_text(encoding="utf-8"))
        slug = data["slug"]
        if not existe_org(slug):
            print(f"  ✗ {slug}: no existe en la BD")
            ok = False
            continue
        db_data = cargar_org(slug)
        checks = (
            ("autores", len(data.get("autores", [])), len(db_data["autores"])),
            ("equipos", len(data.get("equipos", [])), len(db_data["equipos"])),
            ("documentos", len(data.get("documentos", [])), len(db_data["documentos"])),
        )
        for campo, esperado, real in checks:
            if esperado != real:
                print(f"  ✗ {slug}.{campo}: esperado {esperado}, en BD {real}")
                ok = False
        if all(esperado == real for _, esperado, real in checks):
            print(f"  ✔ {slug}: autores={checks[0][1]} equipos={checks[1][1]} documentos={checks[2][1]}")
    return ok
