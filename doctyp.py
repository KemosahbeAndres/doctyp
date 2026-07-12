#!/usr/bin/env python3
"""
doctyp — Generador de informes para la plantilla Typst del SLEP Chinchorro (Unidad TI).

Comando global: se instala como `doctyp` (symlink en ~/.local/bin) y se invoca desde cualquier
carpeta. Todos los documentos se gestionan de forma centralizada en SCRIPT_DIR, junto a lib.typ.

Sin argumentos muestra un menú interactivo con todos los comandos disponibles.

Subcomandos (con alias):  list/ls · new/n · save/s · add/a · compile/c ·
                          edit/code/e/open · reset · config-author/author ·
                          git-init · history/h/log · restore

Snapshots de versión con git (rama única + un tag anotado por versión, ver `cmd_git_init`):
    doctyp git-init                                       # habilita/migra el repo (idempotente)
    doctyp history 1                                       # versiones de un doc y su snapshot
    doctyp restore 1:1.2                                   # extrae esa versión sin tocar la vigente
Doc-ref: `<correlativo>[:<version>][@<anio>]` (p. ej. `39`, `39:1.2`, `39:1.2@2025`, `39@2025`).
Si git no está disponible o el directorio no es un repo, todo lo demás sigue funcionando igual
(solo se avisa una vez); nunca se aborta un `save`/`new`/`compile` por falta de git.

Uso rápido:
    doctyp                                                # menú interactivo
    doctyp new "Auditoría de respaldos"                   # título posicional + defaults de autoría
    doctyp n --t "Manual de red" --tipo MAN --categoria RED
    doctyp save 1 --m "Corrige sección de alcance"        # sube versión (1.0.0 -> 1.0.1) del doc 0001
    doctyp compile 1                                      # sube versión (pide mensaje si falta) y compila a PDF
    doctyp edit 1                                         # elige editor de forma interactiva
    doctyp ls

No requiere paquetes externos (solo stdlib).
"""
from __future__ import annotations
import argparse, json, os, re, sys, subprocess, datetime
from pathlib import Path

# La salida lleva emojis (✔ ⚠ …). En la consola de Windows (cp1252 por defecto) eso provocaría
# UnicodeEncodeError; forzamos UTF-8 en stdout/stderr cuando es posible (Python ≥ 3.7).
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, ValueError):
        pass

# Ubicación real del script (resuelve el symlink). Aquí viven lib.typ, Images/ y settings.json.
SCRIPT_DIR = Path(__file__).resolve().parent
REGISTRO = "settings.json"
DOCTYP_JSON = "doctyp.json"

# ----------------------------------------------------------------------
# Tablas oficiales (Anexos A y B del manual TI-MAN-GOB_2026-0020)
# ----------------------------------------------------------------------
TIPOS = {
    "INF": "Informe Técnico", "MAN": "Manual", "POL": "Política",
    "PRO": "Procedimiento", "PLA": "Plan", "EVL": "Evaluación",
    "ETT": "Especificación Técnica", "ACT": "Acta",
}
CATEGORIAS = {"SEG","RED","HRW","SFW","DAT","SRV","PRV","GOB","USR","CPD","BCK","PRY","CAP"}

# Código documental dentro de un nombre de archivo o del contenido
RE_CODE = re.compile(r"([A-Z]{2,4})-([A-Z]{2,4})-([A-Z]{2,4})_(\d{4})-(\d{4})")
RE_ANIO = re.compile(r"anio:\s*(\d{4})")
RE_CORR = re.compile(r"correlativo:\s*(\d+)")


# ── Colores ANSI ──────────────────────────────────────────────────────────────

def _init_color() -> bool:
    """Activa colores ANSI si el terminal los soporta (respeta NO_COLOR)."""
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if os.environ.get("NO_COLOR"):
        return False
    if os.name == "nt":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return "WT_SESSION" in os.environ
    return True

_USE_COLOR = _init_color()

class _C:
    RESET  = "\033[0m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RED    = "\033[31m"
    GREEN  = "\033[32m"
    YELLOW = "\033[33m"
    CYAN   = "\033[36m"

def _c(code: str, text: str) -> str:
    return f"{code}{text}{_C.RESET}" if _USE_COLOR else text

def _ok(msg: str)   -> None: print(f"  {_c(_C.GREEN,  '✔')} {msg}")
def _warn(msg: str) -> None: print(f"  {_c(_C.YELLOW, '!')} {msg}")

def print_banner() -> None:
    titulo = _c(_C.BOLD + _C.CYAN, "doctyp")
    sub    = _c(_C.DIM, "Informes Técnicos · SLEP Chinchorro (Unidad TI)")
    sep    = _c(_C.DIM, "─" * 54)
    print(f"\n  {titulo}  {sub}")
    print(f"  {sep}")


# ── Meta ──────────────────────────────────────────────────────────────────────

def _meta_str(code: str, clave: str) -> str | None:
    """Valor de un campo `clave: "..."` del meta (None si no está)."""
    m = re.search(rf'{clave}:\s*"((?:[^"\\]|\\.)*)"', code)
    return m.group(1).replace('\\"', '"').replace("\\\\", "\\") if m else None


def parse_meta_typ(path: Path) -> dict | None:
    """Extrae del crear-meta de un .typ los campos necesarios para versionar.
    Devuelve None si el archivo no es legible o le falta algún campo requerido."""
    try:
        txt = path.read_text(encoding="utf-8")
    except OSError:
        return None
    code = "\n".join(l for l in txt.splitlines() if not l.lstrip().startswith("//"))

    ma, mc = RE_ANIO.search(code), RE_CORR.search(code)
    if not (ma and mc):
        return None
    d = {"anio": int(ma.group(1)), "correlativo": int(mc.group(1))}
    for clave, dest in (("area", "area"), ("tipo", "tipo"), ("categoria", "categoria"),
                        ("version", "version"), ("titulo", "titulo"), ("autor", "autor")):
        val = _meta_str(code, clave)
        if not val:
            return None
        d[dest] = val
    d["tipo"] = d["tipo"].upper()
    d["categoria"] = d["categoria"].upper()
    d["area"] = d["area"].upper()
    if d["tipo"] not in TIPOS or d["categoria"] not in CATEGORIAS:
        return None
    return d


# ── Utilidades ────────────────────────────────────────────────────────────────

def find_root(start: Path, lib_name: str) -> Path:
    """Sube desde `start` hasta encontrar el directorio que contiene lib.typ."""
    start = start.resolve()
    for d in [start, *start.parents]:
        if (d / lib_name).exists():
            return d
    return start


def scan_existing(root: Path, exclude: set[str] | None = None) -> list[dict]:
    """Documentos existentes detectados (por nombre y por contenido)."""
    exclude = exclude or set()
    found: dict[tuple[int, int], dict] = {}
    for p in root.rglob("*.typ"):
        if p.name in exclude:
            continue
        anio = corr = None
        m = RE_CODE.search(p.stem)
        if m:
            anio, corr = int(m.group(4)), int(m.group(5))
        else:
            try:
                txt = p.read_text(encoding="utf-8")
            except Exception:
                continue
            code = "\n".join(l for l in txt.splitlines() if not l.lstrip().startswith("//"))
            ma, mc = RE_ANIO.search(code), RE_CORR.search(code)
            if ma and mc:
                anio, corr = int(ma.group(1)), int(mc.group(1))
        if anio is not None and corr is not None:
            found[(anio, corr)] = {"anio": anio, "correlativo": corr, "archivo": p.name}
    return sorted(found.values(), key=lambda d: (d["anio"], d["correlativo"]))


def next_correlativo(existing: list[dict], anio: int) -> int:
    nums = [d["correlativo"] for d in existing if d["anio"] == anio]
    return (max(nums) + 1) if nums else 1


def docs_dir(anio: int) -> Path:
    """Carpeta de documentos: junto al script (SCRIPT_DIR), al lado de lib.typ."""
    return SCRIPT_DIR


# ── Registro JSON ─────────────────────────────────────────────────────────────

def registro_path(script_dir: Path) -> Path:
    return script_dir / REGISTRO


def cargar_registro(script_dir: Path) -> dict:
    p = registro_path(script_dir)
    if not p.exists():
        return {"local": {}, "documentos": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        sys.exit(f"ERROR: no se pudo leer la configuración {p}: {e}")
    data.setdefault("local", {})
    data.setdefault("documentos", [])
    return data


def guardar_registro(script_dir: Path, data: dict) -> None:
    registro_path(script_dir).write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def correlativo_inicio(registro: dict, anio: int) -> int | None:
    val = registro.get("local", {}).get("correlativo_inicio", {}).get(str(anio))
    return int(val) if val is not None else None


AUTHOR_DEFAULTS = {
    "autor": "Andres Cubillos Salazar",
    "cargo": "Tecnico de Soporte Informático",
    "correo": "andres.cubillos@epchinchorro.cl",
}


def author_defaults(registro: dict) -> dict:
    guardado = registro.get("local", {}).get("author", {}) or {}
    return {clave: (guardado.get(clave) or AUTHOR_DEFAULTS[clave]) for clave in AUTHOR_DEFAULTS}


def next_correlativo_json(registro: dict, anio: int, fallback: int = 0) -> int:
    nums = [d["correlativo"] for d in registro["documentos"] if d.get("anio") == anio]
    base = max([fallback, *nums]) if (nums or fallback) else 0
    proximo = base + 1
    inicio = correlativo_inicio(registro, anio)
    if inicio is not None and inicio > proximo:
        return inicio
    return proximo


def bump_patch(version: str) -> str:
    """Incrementa el número menor en formato de 2 dígitos: 1.0 -> 1.1."""
    partes = version.lstrip("vV").split(".")
    nums = []
    for x in partes[:2]:
        if not x.isdigit():
            sys.exit(f"ERROR: versión '{version}' no es numérica; no se puede incrementar.")
        nums.append(int(x))
    while len(nums) < 2:
        nums.append(0)
    nums[-1] += 1
    return ".".join(str(n) for n in nums)


# ── Organizaciones (org.json) — Etapa 1 de la arquitectura v3 (ver CLAUDE.md §14) ──────────────
#
# settings.json conserva "documentos" como espejo del formato v2 (deuda explícita, ver
# CLAUDE.md §14): los comandos no migrados aún (save, compile, edit, add, delete, import,
# history, restore, change, git-init) siguen leyendo/escribiendo ese espejo sin cambios.
# org.json es la fuente de verdad para `list`/`new` y para los comandos org/team/author.

ORG_SLUG_DEFAULT = "slep-chinchorro"
ORG_NOMBRE_DEFAULT = "SLEP Chinchorro"
ORGANIZATIONS = "organizations"
ORG_REGISTRO = "org.json"


def organizations_dir() -> Path:
    return SCRIPT_DIR / ORGANIZATIONS


def org_dir(slug: str) -> Path:
    return organizations_dir() / slug


def org_path(slug: str) -> Path:
    return org_dir(slug) / ORG_REGISTRO


def _escribir_json_atomico(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def _org_vacia(slug: str, nombre: str) -> dict:
    return {
        "schema": 1,
        "slug": slug,
        "nombre": nombre,
        "config": {"correlativo_inicio": {}, "plantilla_default": "informe-ti"},
        "equipos": [],
        "autores": [],
        "documentos": [],
    }


def cargar_org(slug: str) -> dict:
    p = org_path(slug)
    if not p.exists():
        sys.exit(f"ERROR: no existe la organización '{slug}' ({p}).")
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        sys.exit(f"ERROR: no se pudo leer {p}: {e}")
    data.setdefault("config", {}).setdefault("correlativo_inicio", {})
    data.setdefault("equipos", [])
    data.setdefault("autores", [])
    data.setdefault("documentos", [])
    return data


def guardar_org(slug: str, data: dict) -> None:
    _escribir_json_atomico(org_path(slug), data)


def listar_orgs() -> list[str]:
    d = organizations_dir()
    if not d.exists():
        return []
    return sorted(p.name for p in d.iterdir() if p.is_dir() and (p / ORG_REGISTRO).exists())


def cargar_settings() -> dict:
    p = registro_path(SCRIPT_DIR)
    if not p.exists():
        return {"local": {}, "documentos": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        sys.exit(f"ERROR: no se pudo leer la configuración {p}: {e}")
    data.setdefault("local", {})
    data.setdefault("documentos", [])
    return data


def guardar_settings(data: dict) -> None:
    _escribir_json_atomico(registro_path(SCRIPT_DIR), data)


def migrar_v2_a_org() -> None:
    """Migración lazy e idempotente: si no existe ninguna organización todavía pero
    settings.json ya tiene datos v2 (documentos y/o autor), los traslada a
    organizations/<ORG_SLUG_DEFAULT>/org.json. settings.json conserva "documentos" como
    espejo (ver nota arriba); solo se le agrega local.org_activa / local.autor_activo."""
    if listar_orgs():
        return

    settings = cargar_settings()
    local = settings.get("local", {})
    docs_v2 = settings.get("documentos", [])

    autor_guardado = local.get("author") or {}
    autor = {
        "id": "a1",
        "nombre": autor_guardado.get("autor") or AUTHOR_DEFAULTS["autor"],
        "cargo": autor_guardado.get("cargo") or AUTHOR_DEFAULTS["cargo"],
        "correo": autor_guardado.get("correo") or AUTHOR_DEFAULTS["correo"],
        "equipos": [],
    }

    org = _org_vacia(ORG_SLUG_DEFAULT, ORG_NOMBRE_DEFAULT)
    org["config"]["correlativo_inicio"] = dict(local.get("correlativo_inicio") or {})
    org["autores"] = [autor]
    org["documentos"] = [
        {
            "codigo_base": d.get("codigo_base"),
            "area": d.get("area"), "tipo": d.get("tipo"), "categoria": d.get("categoria"),
            "anio": d.get("anio"), "correlativo": d.get("correlativo"),
            "titulo": d.get("titulo"), "autor_id": "a1", "equipo_id": None,
            "plantilla": "informe-ti",
            "ruta": d.get("ruta"),
            "creado": d.get("creado"),
            "versiones": d.get("versiones") or [],
        }
        for d in docs_v2
    ]
    guardar_org(ORG_SLUG_DEFAULT, org)

    settings.setdefault("local", {})
    settings["local"]["org_activa"] = ORG_SLUG_DEFAULT
    settings["local"]["autor_activo"] = "a1"
    guardar_settings(settings)


def org_activa_slug() -> str:
    migrar_v2_a_org()
    settings = cargar_settings()
    slug = settings.get("local", {}).get("org_activa")
    if not slug:
        sys.exit("ERROR: no hay organización activa. Usa 'doctyp org use <slug>'.")
    if not org_path(slug).exists():
        sys.exit(f"ERROR: la organización activa '{slug}' no existe.")
    return slug


def next_correlativo_org(org: dict, anio: int, fallback: int = 0) -> int:
    nums = [d["correlativo"] for d in org["documentos"] if d.get("anio") == anio]
    base = max([fallback, *nums]) if (nums or fallback) else 0
    proximo = base + 1
    inicio = org.get("config", {}).get("correlativo_inicio", {}).get(str(anio))
    if inicio is not None and int(inicio) > proximo:
        return int(inicio)
    return proximo


def autor_activo(org: dict) -> dict:
    """Resuelve el autor activo (settings.json → local.autor_activo) dentro de la org dada;
    si no hay coincidencia, cae al primer autor de la org; si la org no tiene autores, cae a
    AUTHOR_DEFAULTS (sin id, org recién creada)."""
    settings = cargar_settings()
    autor_id = settings.get("local", {}).get("autor_activo")
    autores = org.get("autores", [])
    if autor_id:
        for a in autores:
            if a.get("id") == autor_id:
                return a
    if autores:
        return autores[0]
    return {"id": None, **AUTHOR_DEFAULTS, "equipos": []}


def docs_root() -> Path:
    """Resuelve <Documentos>/doctyp/ según el SO (ver CLAUDE.md §1). No se usa aún para mover
    archivos (eso es Etapa 2); por ahora solo queda disponible como utilidad de resolución."""
    home = Path.home()
    if sys.platform.startswith("linux"):
        try:
            r = subprocess.run(["xdg-user-dir", "DOCUMENTS"], capture_output=True,
                                text=True, timeout=3)
            if r.returncode == 0 and r.stdout.strip():
                documentos = Path(r.stdout.strip())
            else:
                raise FileNotFoundError
        except (FileNotFoundError, OSError, subprocess.SubprocessError):
            documentos = None
            cfg = home / ".config" / "user-dirs.dirs"
            if cfg.exists():
                try:
                    txt = cfg.read_text(encoding="utf-8")
                    m = re.search(r'XDG_DOCUMENTS_DIR="([^"]+)"', txt)
                    if m:
                        documentos = Path(m.group(1).replace("$HOME", str(home)))
                except OSError:
                    pass
            if documentos is None:
                documentos = home / "Documents"
    elif sys.platform == "darwin":
        documentos = home / "Documents"
    elif sys.platform.startswith("win"):
        documentos = None
        try:
            import winreg  # type: ignore
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
            ) as key:
                val, _ = winreg.QueryValueEx(key, "Personal")
                documentos = Path(os.path.expandvars(val))
        except OSError:
            pass
        if documentos is None:
            documentos = Path(os.environ.get("USERPROFILE", str(home))) / "Documents"
    else:
        documentos = home / "Documents"

    documentos.mkdir(parents=True, exist_ok=True)
    root = documentos / "doctyp"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _typst_cmd() -> list[str] | None:
    import shutil
    if shutil.which("typst"):
        return ["typst"]
    if Path("/.flatpak-info").exists() and shutil.which("flatpak-spawn"):
        return ["flatpak-spawn", "--host", "typst"]
    return None


def compilar_typ(out_file: Path) -> bool:
    """Compila un .typ a PDF. Devuelve True si tuvo éxito."""
    base = _typst_cmd()
    if base is None:
        _warn("'typst' no disponible (ni en el PATH ni vía flatpak-spawn).")
        return False
    cmd = base + ["compile"]
    font_dir = SCRIPT_DIR / "museo-sans"
    if font_dir.is_dir():
        cmd += ["--font-path", str(font_dir)]
    cmd.append(str(out_file))
    try:
        subprocess.run(cmd, check=True, cwd=str(out_file.parent))
        _ok(f"Compilado: {_c(_C.DIM, str(out_file.with_suffix('.pdf')))}")
        return True
    except subprocess.CalledProcessError as e:
        _warn(f"Error de compilación: {e}")
        return False


# ── Snapshots git ─────────────────────────────────────────────────────────────
# Rama única + un tag anotado por versión de cada documento (`doc/<anio>-<corr:04d>/v<version>`).
# Degradación elegante: si git falta o el directorio no es un repo, los comandos existentes
# siguen funcionando igual; solo se avisa una vez con _warn (nunca se aborta por esto).

def _git_cmd() -> list[str] | None:
    """Prefijo para invocar git (directo o vía flatpak-spawn --host, igual que _typst_cmd)."""
    import shutil
    if shutil.which("git"):
        return ["git"]
    if Path("/.flatpak-info").exists() and shutil.which("flatpak-spawn"):
        return ["flatpak-spawn", "--host", "git"]
    return None


def _git_disponible() -> bool:
    """True si el binario git está disponible (directo o vía flatpak-spawn)."""
    return _git_cmd() is not None


def _git(*args: str, root: Path) -> subprocess.CompletedProcess:
    """Ejecuta `git <args>` con cwd=root. Asume que ya se comprobó `_git_disponible()`."""
    base = _git_cmd() or ["git"]
    return subprocess.run(base + list(args), cwd=str(root), capture_output=True, text=True)


def _git_repo_ok(root: Path) -> bool:
    """True si `root` está dentro de un repositorio git y git está disponible."""
    if not _git_disponible():
        return False
    r = _git("rev-parse", "--is-inside-work-tree", root=root)
    return r.returncode == 0 and r.stdout.strip() == "true"


def _tag_doc(doc: dict, version: str) -> str:
    """Nombre del tag anotado de una versión: doc/<anio>-<correlativo:04d>/v<version>."""
    return f"doc/{doc['anio']}-{doc['correlativo']:04d}/v{version.lstrip('vV')}"


def _git_snapshot(root: Path, doc: dict, version: str, mensaje: str, accion: str,
                   rutas: list[Path]) -> None:
    """Crea un commit + tag anotado para una versión de `doc` (add + commit + tag).
    Degradación elegante: si git no está disponible o `root` no es un repositorio, o si el
    commit falla (nada que commitear, identidad sin configurar, etc.), solo avisa con _warn
    y no aborta — el registro JSON ya quedó guardado antes de llamar a esta función."""
    if not _git_disponible():
        _warn("git no está disponible: no se guardó snapshot de esta versión "
              "(instala git; luego usa 'doctyp git-init').")
        return
    if not _git_repo_ok(root):
        _warn("Este directorio no es un repositorio git: no se guardó snapshot de esta versión "
              "(ejecuta 'doctyp git-init' para habilitarlo).")
        return

    rel = [Path(os.path.relpath(r, root)).as_posix() for r in rutas]
    r_add = _git("add", "--", *rel, root=root)
    if r_add.returncode != 0:
        _warn(f"git add falló, no se guardó snapshot: {r_add.stderr.strip()}")
        return

    corr_str = f"{doc['anio']}-{doc['correlativo']:04d}"
    r_commit = _git("commit", "-m", f"{accion}({corr_str}): {mensaje}", root=root)
    if r_commit.returncode != 0:
        _warn("git commit no se realizó (¿nada que commitear o identidad git sin configurar?): "
              f"{(r_commit.stderr or r_commit.stdout).strip()}")
        return

    tag = _tag_doc(doc, version)
    r_tag = _git("tag", "-a", tag, "-m", mensaje, root=root)
    if r_tag.returncode != 0:
        _warn(f"No se pudo crear el tag '{tag}': {r_tag.stderr.strip()}")
        return
    _ok(f"Snapshot git: {_c(_C.DIM, tag)}")


def agregar_doctyp_json(cwd: Path, correlativo: int, anio: int,
                        nombre_archivo: str, autor: str) -> None:
    """Añade una entrada al doctyp.json del directorio cwd (lo crea si no existe).
    Migra automáticamente el formato anterior (dict plano) a lista.
    No hace nada si cwd es SCRIPT_DIR: el registro ya está en settings.json."""
    if cwd.resolve() == SCRIPT_DIR.resolve():
        return
    path = cwd / DOCTYP_JSON
    try:
        data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    except (json.JSONDecodeError, OSError):
        data = {}

    # Migrar formato anterior (dict plano con "correlativo")
    if isinstance(data.get("correlativo"), int):
        entrada_vieja = {
            "correlativo": data["correlativo"],
            "anio": data.get("anio", anio),
            "fecha_creacion": "",
            "nombre_archivo": "",
            "autor": "",
        }
        data = {"documentos": [entrada_vieja]}
    data.setdefault("documentos", [])

    # Evitar duplicados (mismo correlativo + año)
    if not any(d.get("correlativo") == correlativo and d.get("anio") == anio
               for d in data["documentos"]):
        data["documentos"].append({
            "correlativo": correlativo,
            "anio": anio,
            "fecha_creacion": datetime.datetime.now().isoformat(timespec="seconds"),
            "nombre_archivo": nombre_archivo,
            "autor": autor,
        })

    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _ok(f"Contexto guardado: {_c(_C.DIM, str(path))}")


def leer_doctyp_json(cwd: Path) -> list[dict] | None:
    """Lee doctyp.json del directorio actual.
    Devuelve la lista de entradas o None si no existe, es inválido, o cwd es SCRIPT_DIR
    (ahí el registro ya vive en settings.json; doctyp.json no se lee ni se crea).
    Migra el formato anterior (dict plano) de forma transparente."""
    if cwd.resolve() == SCRIPT_DIR.resolve():
        return None
    path = cwd / DOCTYP_JSON
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        # Formato anterior: dict plano con "correlativo"
        if isinstance(data.get("correlativo"), int):
            return [data]
        docs = data.get("documentos", [])
        if isinstance(docs, list) and docs:
            return docs
    except (json.JSONDecodeError, OSError):
        pass
    return None


def resolver_desde_doctyp_json(cwd: Path, registro: dict, anio_arg: int | None) -> dict:
    """Lee doctyp.json y devuelve el documento del registro seleccionado.
    Si hay una sola entrada la usa directamente; si hay varias pide selección interactiva."""
    entradas = leer_doctyp_json(cwd)
    if not entradas:
        sys.exit(
            f"ERROR: no se proporcionó correlativo y no existe {DOCTYP_JSON} "
            f"en el directorio actual.\n"
            f"  Uso: doctyp <edit|compile> <correlativo>"
        )

    if len(entradas) == 1:
        e = entradas[0]
        corr = e["correlativo"]
        anio = anio_arg or e.get("anio", datetime.date.today().year)
        _ok(f"Usando correlativo {_c(_C.CYAN, f'{corr:04d}')} de {DOCTYP_JSON}")
        return buscar_doc(registro, corr, anio)

    # Múltiples entradas → selección interactiva
    etiquetas = []
    for e in entradas:
        corr_str = f"{e['correlativo']:04d}"
        fecha = e.get("fecha_creacion", "")[:10]
        nombre = e.get("nombre_archivo", "")
        autor = e.get("autor", "")
        etiquetas.append(f"{corr_str}  {nombre}  ·  {fecha}  ·  {autor}")

    idx = _seleccionar(etiquetas, f"Documentos en {DOCTYP_JSON}:")
    if idx is None:
        sys.exit("Cancelado.")

    e = entradas[idx]
    anio = anio_arg or e.get("anio", datetime.date.today().year)
    return buscar_doc(registro, e["correlativo"], anio)


def codigo_base(area, tipo, cat, anio, corr) -> str:
    return f"{area}-{tipo}-{cat}_{anio}-{corr:04d}"


def ty_str(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


# ── Generación del .typ ───────────────────────────────────────────────────────

def build_typ(f: dict, lib_import: str) -> str:
    base = codigo_base(f["area"], f["tipo"], f["categoria"], f["anio"], f["correlativo"])
    rama = "doc/" + base.replace("_", "-")
    fecha_iso = f'{f["fecha"][:4]}-{f["fecha"][4:6]}-{f["fecha"][6:]}'

    meta = []
    meta.append(f'  area: "{f["area"]}", tipo: "{f["tipo"]}", categoria: "{f["categoria"]}",')
    meta.append(f'  anio: {f["anio"]}, correlativo: {f["correlativo"]}, version: "{f["version"]}", fecha-codigo: "{f["fecha"]}",')
    meta.append(f'  tipo-largo: "{ty_str(f["tipo_largo"])}",')
    meta.append(f'  titulo: "{ty_str(f["titulo"])}", subtitulo: "{ty_str(f["subtitulo"])}",')
    meta.append(f'  estado: "{f["estado"]}", clasificacion: "{f["clasificacion"]}",')
    meta.append(f'  autor: "{ty_str(f["autor"])}", cargo-autor: "{ty_str(f["cargo"])}", correo-autor: "{ty_str(f["correo"])}",')
    if f.get("revisor"):
        meta.append(f'  revisor: "{ty_str(f["revisor"])}",')
    if f.get("aprobador"):
        meta.append(f'  aprobador: "{ty_str(f["aprobador"])}",')
    meta_block = "\n".join(meta)

    return f'''// {base}  ·  generado por doctyp
#import "{lib_import}": *

#let meta = crear-meta((
{meta_block}
))
#show: report.with(meta: meta)

#s-ficha(meta, rama-git: "{rama}")
#s-versiones(meta, (
  ("v{f["version"]}", "{fecha_iso}", "{ty_str(f["autor"])}", "Versión inicial."),
))
#s-distribucion((
  ("Equipo TI", "Operación documental", "Receptor principal"),
  ("Subdirección de Planificación y Control de Gestión", "Supervisión", "Copia informativa"),
  ("Archivo Institucional", "Custodia", "Archivo institucional"),
))
#s-indice()

= Resumen ejecutivo
// TODO: 1–3 párrafos con el propósito, alcance y resultado principal.

= Antecedentes y motivación
== Contexto institucional
// TODO
== Problema o necesidad identificada
// TODO

= Objetivo
== Objetivo general
// TODO
== Objetivos específicos
// TODO

= Alcance
== Dentro del alcance
// TODO
== Fuera del alcance
// TODO

= Marco normativo y referencial
== Normativa legal aplicable
// TODO
== Estándares técnicos aplicables
// TODO

= Metodología
// TODO

= Desarrollo técnico
// TODO: cuerpo principal del informe.

= Análisis de impacto
== Confidencialidad
// TODO
== Integridad
// TODO
== Disponibilidad
// TODO

= Conclusiones
// TODO

= Recomendaciones
#tabla-prioridad((
  ("1", "Acción recomendada.", "Alta", "Responsable"),
))

= Glosario y acrónimos
#tabla(
  columns: (auto, 1fr),
  ("Término", "Definición"),
  (
    ("SLEP", "Servicio Local de Educación Pública."),
    ("TI", "Tecnologías de la Información."),
  ),
)

= Referencias
// TODO

= Anexos
== Anexo A. Documentos de respaldo
// TODO
== Anexo B. Firmas
#firmas-estandar(meta)
'''


# ── Editores ──────────────────────────────────────────────────────────────────

def _host_prefix() -> list[str]:
    """Prefijo para ejecutar comandos en el host desde dentro de un sandbox Flatpak."""
    import shutil
    if Path("/.flatpak-info").exists() and shutil.which("flatpak-spawn"):
        return ["flatpak-spawn", "--host"]
    return []


def _host_run_ok(argv: list[str]) -> bool:
    """Ejecuta `argv` (en el host si hace falta) y devuelve True si terminó con código 0."""
    try:
        r = subprocess.run(_host_prefix() + argv, capture_output=True, text=True)
        return r.returncode == 0
    except (FileNotFoundError, OSError):
        return False


_VSCODE_FLATPAK_IDS = ("com.visualstudio.code", "com.vscodium.codium")


def _vscode_flatpak_cmd(path: Path) -> tuple[str, list[str]] | None:
    """Devuelve (nombre, comando) si VS Code o VSCodium está instalado como Flatpak; si no, None."""
    pre = _host_prefix()
    for app_id in _VSCODE_FLATPAK_IDS:
        if _host_run_ok(["flatpak", "info", app_id]):
            label = "VSCodium" if "codium" in app_id else "VS Code"
            return (f"{label}  (Flatpak)", pre + ["flatpak", "run", app_id, str(path)])
    return None


def _detectar_editores(path: Path) -> list[tuple[str, list[str]]]:
    """Detecta todos los editores disponibles para abrir `path`.
    Devuelve lista de (nombre_legible, comando) en orden de preferencia:
    1) VS Code binario · 2) VS Code/VSCodium Flatpak · 3) $VISUAL/$EDITOR · 4) predeterminado."""
    import shutil
    code_exe = "code.cmd" if (os.name == "nt" and not shutil.which("code")) else "code"
    pre = _host_prefix()
    editores: list[tuple[str, list[str]]] = []

    # 1) VS Code como binario en el PATH (host, sandbox, Windows, macOS)
    code_path = shutil.which(code_exe)
    if code_path:
        editores.append(("VS Code", [code_path, str(path)]))
    elif pre and _host_run_ok(["sh", "-c", "command -v code"]):
        editores.append(("VS Code  (host)", pre + ["code", str(path)]))

    # 2) VS Code / VSCodium como Flatpak (caso típico en Fedora)
    if os.name != "nt":
        fp = _vscode_flatpak_cmd(path)
        if fp:
            editores.append(fp)

    # 3) Editor favorito del entorno ($VISUAL o $EDITOR)
    for var in ("VISUAL", "EDITOR"):
        val = os.environ.get(var)
        if val:
            exe = val.split()[0]
            if shutil.which(exe):
                editores.append((f"{exe}  (${var})", val.split() + [str(path)]))
            break

    # 4) App predeterminada del sistema
    if os.name == "nt":
        editores.append(("Predeterminado del sistema  (Windows)", []))
    elif sys.platform == "darwin":
        if shutil.which("open"):
            editores.append(("Predeterminado del sistema  (macOS)", ["open", str(path)]))
    else:
        if shutil.which("xdg-open"):
            editores.append(("Predeterminado del sistema  (xdg-open)", ["xdg-open", str(path)]))
        elif pre and _host_run_ok(["sh", "-c", "command -v xdg-open"]):
            editores.append(("Predeterminado del sistema  (xdg-open host)", pre + ["xdg-open", str(path)]))

    return editores


def _lanzar_editor(nombre: str, editor_cmd: list[str], path: Path) -> bool:
    """Lanza el editor indicado. Devuelve True si tuvo éxito."""
    try:
        if not editor_cmd and os.name == "nt":
            os.startfile(str(path))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(editor_cmd)
        _ok(f"Abriendo en {_c(_C.BOLD, nombre)}")
        return True
    except (FileNotFoundError, OSError) as e:
        _warn(f"No se pudo abrir {_c(_C.BOLD, nombre)}: {e}")
        return False


# ── Subcomandos ───────────────────────────────────────────────────────────────

# ── Organizaciones, equipos y autores (Etapa 1 v3) ──────────────────────────────

def _slug_valido(slug: str) -> bool:
    return bool(re.fullmatch(r"[a-z0-9][a-z0-9-]*", slug))


def cmd_org_new(args):
    slug = args.slug.strip().lower()
    if not _slug_valido(slug):
        sys.exit("ERROR: el slug solo admite minúsculas, dígitos y guiones (p. ej. 'mi-org').")
    if org_path(slug).exists():
        sys.exit(f"ERROR: ya existe una organización '{slug}'.")
    nombre = args.nombre or slug
    org = _org_vacia(slug, nombre)
    guardar_org(slug, org)

    settings = cargar_settings()
    settings.setdefault("local", {})
    if not settings["local"].get("org_activa"):
        settings["local"]["org_activa"] = slug
        guardar_settings(settings)

    _ok(f"Organización creada: {_c(_C.BOLD, slug)} ({nombre})")
    print(f"       {_c(_C.DIM, str(org_path(slug)))}\n")


def cmd_org_list(args):
    migrar_v2_a_org()
    settings = cargar_settings()
    activa = settings.get("local", {}).get("org_activa")
    orgs = listar_orgs()
    if not orgs:
        print(f"\n  {_c(_C.YELLOW, '!')} No hay organizaciones. Usa 'doctyp org new <slug>'.\n")
        return
    print()
    for slug in orgs:
        org = cargar_org(slug)
        marca = _c(_C.GREEN, "●") if slug == activa else " "
        n_docs = len(org.get("documentos", []))
        print(f"  {marca} {_c(_C.BOLD, slug)}  {_c(_C.DIM, org.get('nombre', ''))}"
              f"  {_c(_C.DIM, f'({n_docs} doc.)')}")
    print()


def cmd_org_use(args):
    slug = args.slug.strip().lower()
    if not org_path(slug).exists():
        sys.exit(f"ERROR: no existe la organización '{slug}'.")
    settings = cargar_settings()
    settings.setdefault("local", {})["org_activa"] = slug
    guardar_settings(settings)
    _ok(f"Organización activa: {_c(_C.BOLD, slug)}")


def cmd_team_new(args):
    slug = org_activa_slug()
    org = cargar_org(slug)
    equipo_id = args.id.strip()
    if any(e.get("id") == equipo_id for e in org["equipos"]):
        sys.exit(f"ERROR: ya existe el equipo '{equipo_id}' en '{slug}'.")
    org["equipos"].append({"id": equipo_id, "nombre": args.nombre or equipo_id})
    guardar_org(slug, org)
    _ok(f"Equipo creado: {_c(_C.BOLD, equipo_id)} en {_c(_C.CYAN, slug)}")


def cmd_team_list(args):
    slug = org_activa_slug()
    org = cargar_org(slug)
    if not org["equipos"]:
        print(f"\n  {_c(_C.YELLOW, '!')} La organización '{slug}' no tiene equipos.\n")
        return
    print()
    for e in org["equipos"]:
        print(f"  {_c(_C.BOLD, e.get('id', ''))}  {e.get('nombre', '')}")
    print()


def _proximo_autor_id(org: dict) -> str:
    n = len(org.get("autores", [])) + 1
    existentes = {a.get("id") for a in org.get("autores", [])}
    while f"a{n}" in existentes:
        n += 1
    return f"a{n}"


def cmd_author_add(args):
    slug = org_activa_slug()
    org = cargar_org(slug)
    print(f"\n  {_c(_C.BOLD, 'Nuevo autor en ' + slug)}\n")
    nombre = args.nombre or input("  Nombre: ").strip()
    cargo = args.cargo or input("  Cargo: ").strip()
    correo = args.correo or input("  Correo: ").strip()
    if not nombre:
        sys.exit("ERROR: el nombre del autor es obligatorio.")
    equipos_ids = {e.get("id") for e in org["equipos"]}
    equipos_arg = [e.strip() for e in (args.equipos or "").split(",") if e.strip()]
    for e in equipos_arg:
        if e not in equipos_ids:
            sys.exit(f"ERROR: el equipo '{e}' no existe en '{slug}'.")

    autor = {
        "id": _proximo_autor_id(org),
        "nombre": nombre, "cargo": cargo, "correo": correo,
        "equipos": equipos_arg,
    }
    org["autores"].append(autor)
    guardar_org(slug, org)
    _ok(f"Autor creado: {_c(_C.BOLD, autor['id'])} — {nombre}\n")


def cmd_author_list(args):
    slug = org_activa_slug()
    org = cargar_org(slug)
    settings = cargar_settings()
    activo = settings.get("local", {}).get("autor_activo")
    if not org["autores"]:
        print(f"\n  {_c(_C.YELLOW, '!')} La organización '{slug}' no tiene autores.\n")
        return
    print()
    for a in org["autores"]:
        marca = _c(_C.GREEN, "●") if a.get("id") == activo else " "
        print(f"  {marca} {_c(_C.BOLD, a.get('id', ''))}  {a.get('nombre', '')}"
              f"  {_c(_C.DIM, a.get('cargo', ''))}")
    print()


def cmd_author_use(args):
    slug = org_activa_slug()
    org = cargar_org(slug)
    autor_id = args.id.strip()
    if not any(a.get("id") == autor_id for a in org["autores"]):
        sys.exit(f"ERROR: no existe el autor '{autor_id}' en '{slug}'.")
    settings = cargar_settings()
    settings.setdefault("local", {})["autor_activo"] = autor_id
    guardar_settings(settings)
    _ok(f"Autor activo: {_c(_C.BOLD, autor_id)}")


def cmd_listar(args):
    slug = args.org or org_activa_slug()
    org = cargar_org(slug)
    docs = sorted(org["documentos"], key=lambda d: (d.get("anio", 0), d.get("correlativo", 0)))
    anio = args.anio or datetime.date.today().year

    print(f"\n  {_c(_C.DIM, 'Organización: ' + slug + '  (' + str(org_path(slug)) + ')')}")

    if docs:
        print()
        for d in docs:
            vers = d.get("versiones") or []
            ver_str = _c(_C.DIM, f"  v{vers[-1]['version']}") if vers else ""
            corr_str = f"{d.get('correlativo', 0):04d}"
            print(f"  {_c(_C.CYAN, corr_str)}  "
                  f"{_c(_C.BOLD, d.get('codigo_base', ''))}{ver_str}")
            print(f"        {d.get('titulo', '')}")
    else:
        print(f"\n  {_c(_C.YELLOW, '!')} El registro está vacío (aún no se han creado documentos).")

    inicio = org.get("config", {}).get("correlativo_inicio", {}).get(str(anio))
    if inicio is not None:
        print(f"\n  {_c(_C.DIM, f'Inicio configurado para {anio}: {int(inicio):04d}')}")
    proximo = next_correlativo_org(org, anio)
    print(f"\n  {_c(_C.GREEN, '→')} Próximo correlativo para {anio}: "
          f"{_c(_C.BOLD + _C.CYAN, f'{proximo:04d}')}\n")


def cmd_config_author(args):
    """Pide interactivamente los datos del autor y los guarda en settings.json -> local.author."""
    registro = cargar_registro(SCRIPT_DIR)
    actual = author_defaults(registro)
    campos = (
        ("autor",  "Nombre del autor"),
        ("cargo",  "Cargo del autor"),
        ("correo", "Correo del autor"),
    )
    print(f"\n  {_c(_C.BOLD, 'Configuración del autor')}")
    print(f"  {_c(_C.DIM, 'Guardado en settings.json → local.author')}")
    print(f"  {_c(_C.DIM, 'Deja en blanco para mantener el valor actual.')}\n")
    nuevo = {}
    for clave, etiqueta in campos:
        try:
            resp = input(f"  {etiqueta} ({_c(_C.DIM, actual[clave])}): ").strip()
        except EOFError:
            resp = ""
        nuevo[clave] = resp if resp else actual[clave]

    registro.setdefault("local", {})["author"] = nuevo
    guardar_registro(SCRIPT_DIR, registro)
    print()
    _ok("Autor guardado en settings.json → local.author:")
    print(f"       autor:  {nuevo['autor']}")
    print(f"       cargo:  {nuevo['cargo']}")
    print(f"       correo: {nuevo['correo']}\n")


def cmd_reset(args):
    registro = cargar_registro(SCRIPT_DIR)
    anio = args.anio or datetime.date.today().year
    inicio = args.correlativo if args.correlativo is not None else 1
    if inicio < 1:
        sys.exit("ERROR: el correlativo de inicio debe ser >= 1.")
    registro.setdefault("local", {}).setdefault("correlativo_inicio", {})[str(anio)] = inicio
    guardar_registro(SCRIPT_DIR, registro)
    _ok(f"Inicio de correlativo para {anio} fijado en {_c(_C.CYAN, f'{inicio:04d}')}.")
    print(f"       Próximo: {_c(_C.BOLD + _C.CYAN, f'{next_correlativo_json(registro, anio):04d}')}")
    print(f"       {_c(_C.DIM, str(registro_path(SCRIPT_DIR)))}\n")


def cmd_nuevo(args):
    lib_path = SCRIPT_DIR / args.lib
    if not lib_path.exists():
        sys.exit(f"ERROR: no se encontró {args.lib} junto al script ({SCRIPT_DIR}).")

    tipo = args.tipo.upper()
    cat = args.categoria.upper()
    if tipo not in TIPOS:
        sys.exit(f"ERROR: tipo '{tipo}' inválido. Válidos: {', '.join(TIPOS)}")
    if cat not in CATEGORIAS:
        sys.exit(f"ERROR: categoría '{cat}' inválida. Válidas: {', '.join(sorted(CATEGORIAS))}")

    titulo = args.titulo or args.titulo_pos or input("  Título del documento: ").strip()
    if not titulo:
        sys.exit("ERROR: el título es obligatorio.")

    hoy = datetime.date.today()
    fecha = args.fecha or hoy.strftime("%Y%m%d")
    if not re.fullmatch(r"\d{8}", fecha):
        sys.exit("ERROR: --fecha debe ser AAAAMMDD.")
    anio = args.anio or int(fecha[:4])

    out_dir = docs_dir(anio)
    slug = org_activa_slug()
    org = cargar_org(slug)
    fallback = next_correlativo(scan_existing(out_dir, exclude={args.lib}), anio) - 1
    corr = args.correlativo if args.correlativo is not None else next_correlativo_org(org, anio, fallback)

    autor_org = autor_activo(org)
    autoria = {"autor": autor_org["nombre"], "cargo": autor_org["cargo"], "correo": autor_org["correo"]}
    f = {
        "area": args.area.upper(), "tipo": tipo, "categoria": cat,
        "anio": anio, "correlativo": corr, "version": args.version, "fecha": fecha,
        "tipo_largo": args.tipo_largo or TIPOS[tipo],
        "titulo": titulo,
        "subtitulo": args.subtitulo or "SLEP Chinchorro",
        "estado": args.estado.upper(), "clasificacion": args.clasificacion.upper(),
        "autor": args.autor or autoria["autor"],
        "cargo": args.cargo or autoria["cargo"],
        "correo": args.correo or autoria["correo"],
        "revisor": args.revisor, "aprobador": args.aprobador,
    }

    base = codigo_base(f["area"], tipo, cat, anio, corr)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{base}.typ"
    if out_file.exists() and not args.forzar:
        sys.exit(f"ERROR: {out_file} ya existe. Usa --forzar para sobrescribir.")

    lib_import = os.path.relpath(lib_path, out_dir).replace(os.sep, "/")
    out_file.write_text(build_typ(f, lib_import), encoding="utf-8")

    ahora = datetime.datetime.now().isoformat(timespec="seconds")
    entrada = {
        "codigo_base": base,
        "area": f["area"], "tipo": tipo, "categoria": cat,
        "anio": anio, "correlativo": corr,
        "titulo": titulo, "autor": f["autor"],
        "ruta": str(out_file),
        "creado": ahora,
        "versiones": [{"version": f["version"], "fecha": fecha, "creado": ahora}],
    }

    # org.json (fuente de verdad v3)
    entrada_org = {
        "codigo_base": base,
        "area": f["area"], "tipo": tipo, "categoria": cat,
        "anio": anio, "correlativo": corr,
        "titulo": titulo, "autor_id": autor_org.get("id"), "equipo_id": None,
        "plantilla": "informe-ti",
        "ruta": str(out_file),
        "creado": ahora,
        "versiones": [{"version": f["version"], "fecha": fecha, "creado": ahora}],
    }
    org["documentos"].append(entrada_org)
    guardar_org(slug, org)

    # Espejo v2 en settings.json (deuda explícita, ver CLAUDE.md §14): mantiene funcionando
    # save/compile/edit/etc. sin cambios hasta que la Etapa 3 los migre a org.json.
    settings = cargar_settings()
    settings["documentos"].append(entrada)
    guardar_settings(settings)

    agregar_doctyp_json(Path.cwd(), corr, anio, f"{base}.typ", f["autor"])
    _git_snapshot(SCRIPT_DIR, entrada, f["version"], "Versión inicial.", "new",
                  [out_file, registro_path(SCRIPT_DIR)])

    print()
    _ok(f"Creado: {_c(_C.DIM, str(out_file))}")
    print(f"       {_c(_C.BOLD, 'Código base:')}     {base}")
    print(f"       {_c(_C.BOLD, 'Código completo:')} {base}_v{f['version']}_{fecha}")
    print(f"       {_c(_C.BOLD, 'Correlativo:')}     {_c(_C.CYAN, f'{corr:04d}')} (año {anio})\n")


def buscar_doc(registro: dict, correlativo: int, anio: int) -> dict:
    """Localiza en el registro el documento por correlativo + año, o aborta con error."""
    docs = [d for d in registro["documentos"]
            if d.get("correlativo") == correlativo and d.get("anio") == anio]
    if not docs:
        sys.exit(f"ERROR: no hay documento con correlativo {correlativo:04d} (año {anio}) "
                 f"en el registro. Revisa con 'doctyp list'.")
    if len(docs) > 1:
        sys.exit(f"ERROR: hay {len(docs)} documentos con correlativo {correlativo:04d} "
                 f"(año {anio}). Resuelve el duplicado en {registro_path(SCRIPT_DIR)}.")
    return docs[0]


# Doc-ref: <correlativo>[:<version>][@<anio>] (también acepta "/" como separador de versión).
_RE_DOCREF = re.compile(r"(\d+)(?:[:/]([^@]+))?(?:@(\d{4}))?")


def _parse_docref_partes(ref: str) -> tuple[int, str | None, int]:
    """Descompone una doc-ref en (correlativo, version_o_None, anio) sin tocar el registro.
    Aborta con error si el formato no calza con `<correlativo>[:<version>][@<anio>]`."""
    m = _RE_DOCREF.fullmatch(ref.strip())
    if not m:
        sys.exit(f"ERROR: referencia de documento inválida: '{ref}'. "
                 f"Formato esperado: <correlativo>[:<version>][@<anio>]")
    corr = int(m.group(1))
    version = m.group(2).lstrip("vV") if m.group(2) else None
    anio = int(m.group(3)) if m.group(3) else datetime.date.today().year
    return corr, version, anio


def parse_docref(ref: str, registro: dict) -> tuple[dict, str]:
    """Resuelve una doc-ref `<correlativo>[:<version>][@<anio>]` contra el registro (reusa
    `buscar_doc`). Sin versión explícita usa la más reciente. Aborta con error claro —
    listando las versiones disponibles— si la versión pedida no existe."""
    corr, version, anio = _parse_docref_partes(ref)
    doc = buscar_doc(registro, corr, anio)
    vers = doc.get("versiones") or []
    if version is None:
        if not vers:
            sys.exit(f"ERROR: el documento {corr:04d} (año {anio}) no tiene versiones registradas.")
        return doc, vers[-1]["version"]
    disponibles = [v["version"] for v in vers]
    if version not in disponibles:
        sys.exit(f"ERROR: el documento {corr:04d} (año {anio}) no tiene la versión '{version}'. "
                 f"Disponibles: {', '.join(disponibles) or '(ninguna)'}")
    return doc, version


def pedir_mensaje_version() -> str | None:
    """Pide interactivamente el mensaje de una nueva versión. None si se cancela."""
    try:
        mensaje = input("  Mensaje de la nueva versión: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return None
    if not mensaje:
        sys.exit("ERROR: el mensaje es obligatorio.")
    return mensaje


def realizar_save(doc: dict, mensaje: str) -> tuple[str, str]:
    """Sube el patch de versión de `doc`: actualiza el .typ (campo `version:` y
    tabla `#s-versiones`) y añade la entrada al registro en memoria (`doc["versiones"]`).
    No persiste el registro en disco; el llamador debe hacer `guardar_registro(...)`.
    Devuelve (version_actual, version_nueva)."""
    typ_path = Path(doc["ruta"])
    if not typ_path.exists():
        sys.exit(f"ERROR: el archivo registrado no existe: {typ_path}")
    texto = typ_path.read_text(encoding="utf-8")

    version_actual = doc["versiones"][-1]["version"] if doc.get("versiones") else "1.0"
    version_nueva = bump_patch(version_actual)
    hoy = datetime.date.today()
    fecha = hoy.strftime("%Y%m%d")
    fecha_iso = hoy.strftime("%Y-%m-%d")
    autor = doc.get("autor", "")

    nuevo_texto, n = re.subn(r'(version:\s*")[^"]*(")',
                             lambda m: f'{m.group(1)}{version_nueva}{m.group(2)}',
                             texto, count=1)
    if n == 0:
        sys.exit(f"ERROR: no se encontró el campo 'version:' en {typ_path}.")

    fila = f'  ("v{version_nueva}", "{fecha_iso}", "{ty_str(autor)}", "{ty_str(mensaje)}"),\n'
    nuevo_texto, n = re.subn(r'(#s-versiones\(\s*meta\s*,\s*\(\n)',
                             lambda m: m.group(1) + fila,
                             nuevo_texto, count=1)
    if n == 0:
        sys.exit(f"ERROR: no se encontró el bloque '#s-versiones(meta, (' en {typ_path}. "
                 f"¿El documento usa la firma antigua '#s-versiones((...))'? Actualízalo a "
                 f"'#s-versiones(meta, (...))' (agrega el tag git a la tabla de versiones).")

    typ_path.write_text(nuevo_texto, encoding="utf-8")

    ahora = datetime.datetime.now().isoformat(timespec="seconds")
    doc.setdefault("versiones", []).append({
        "version": version_nueva, "fecha": fecha, "creado": ahora, "mensaje": mensaje,
    })
    return version_actual, version_nueva


def cmd_save(args):
    registro = cargar_registro(SCRIPT_DIR)
    anio = args.anio or datetime.date.today().year

    # Correlativo: si no se pasó por CLI, selección interactiva
    if getattr(args, "correlativo", None) is None:
        docs = sorted(
            [d for d in registro["documentos"] if d.get("anio") == anio],
            key=lambda d: d.get("correlativo", 0),
        )
        if not docs:
            sys.exit(f"ERROR: no hay documentos registrados para {anio}.")
        etiquetas = []
        for d in docs:
            vers = d.get("versiones") or []
            ver_str = f"v{vers[-1]['version']}" if vers else ""
            etiquetas.append(
                f"{d.get('correlativo', 0):04d}  {d.get('codigo_base', '')}  "
                f"{ver_str}  ·  {d.get('titulo', '')}"
            )
        idx = _seleccionar(etiquetas, f"Documentos registrados ({anio}):")
        if idx is None:
            print("  Cancelado.")
            return
        doc = docs[idx]
    else:
        doc = buscar_doc(registro, args.correlativo, anio)

    # Mensaje: si no se pasó por CLI, pedirlo interactivamente
    mensaje = getattr(args, "mensaje", None) or ""
    if not mensaje:
        mensaje = pedir_mensaje_version()
        if mensaje is None:
            return

    version_actual, version_nueva = realizar_save(doc, mensaje)
    guardar_registro(SCRIPT_DIR, registro)
    _git_snapshot(SCRIPT_DIR, doc, version_nueva, mensaje, "save",
                  [Path(doc["ruta"]), registro_path(SCRIPT_DIR)])

    print()
    _ok(f"Versión actualizada: {_c(_C.DIM, 'v' + version_actual)} → "
        f"{_c(_C.BOLD + _C.CYAN, 'v' + version_nueva)}")
    print(f"       Documento: {_c(_C.BOLD, doc['codigo_base'])}")
    print(f"       Archivo:   {_c(_C.DIM, str(Path(doc['ruta'])))}")
    print(f"       Mensaje:   {mensaje}\n")


def cmd_change(args):
    """Cambia el correlativo de un documento registrado."""
    registro = cargar_registro(SCRIPT_DIR)
    anio = args.anio or datetime.date.today().year

    # ── Correlativo anterior ───────────────────────────────────────────────────
    corr_anterior = getattr(args, "correlativo_anterior", None)
    if corr_anterior is None:
        docs = sorted(
            [d for d in registro["documentos"] if d.get("anio") == anio],
            key=lambda d: d.get("correlativo", 0),
        )
        if not docs:
            sys.exit(f"ERROR: no hay documentos registrados para {anio}.")
        etiquetas = [
            f"{d.get('correlativo', 0):04d}  {d.get('codigo_base', '')}  ·  {d.get('titulo', '')}"
            for d in docs
        ]
        idx = _seleccionar(etiquetas, f"Documento a cambiar ({anio}):")
        if idx is None:
            print("  Cancelado.")
            return
        doc = docs[idx]
        corr_anterior = doc["correlativo"]
    else:
        doc = buscar_doc(registro, corr_anterior, anio)

    # ── Correlativo nuevo ──────────────────────────────────────────────────────
    usados = {d["correlativo"] for d in registro["documentos"] if d.get("anio") == anio}
    usados.discard(corr_anterior)

    corr_nuevo = getattr(args, "correlativo_nuevo", None)
    while True:
        if corr_nuevo is None:
            try:
                raw = input(f"  Nuevo correlativo (actual: {corr_anterior:04d}): ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                return
            if not raw.isdigit():
                _warn("Debe ser un número entero positivo.")
                continue
            corr_nuevo = int(raw)
        if corr_nuevo <= 0:
            _warn("El correlativo debe ser >= 1.")
            corr_nuevo = None
            continue
        if corr_nuevo == corr_anterior:
            _warn("El correlativo nuevo es igual al actual. Elige otro.")
            corr_nuevo = None
            continue
        if corr_nuevo in usados:
            _warn(f"El correlativo {corr_nuevo:04d} ya está en uso. Elige otro.")
            corr_nuevo = None
            continue
        break

    # ── Construir nuevos nombres ───────────────────────────────────────────────
    base_nuevo   = codigo_base(doc["area"], doc["tipo"], doc["categoria"], anio, corr_nuevo)
    ruta_antigua = Path(doc["ruta"])
    ruta_nueva   = ruta_antigua.parent / f"{base_nuevo}.typ"

    print(f"\n  {_c(_C.BOLD, 'Cambio de correlativo')}")
    print(f"  De: {_c(_C.DIM,              doc['codigo_base'])}")
    print(f"  A:  {_c(_C.BOLD + _C.CYAN,  base_nuevo)}\n")

    if not ruta_antigua.exists():
        sys.exit(f"ERROR: el archivo registrado no existe: {ruta_antigua}")
    if ruta_nueva.exists() and ruta_nueva.resolve() != ruta_antigua.resolve():
        sys.exit(f"ERROR: ya existe un archivo en la ruta destino: {ruta_nueva}")

    # ── Actualizar contenido del .typ ──────────────────────────────────────────
    texto = ruta_antigua.read_text(encoding="utf-8")

    # 1. Comentario de cabecera: // TI-INF-XXX_2026-NNNN  ·  generado por doctyp
    texto = re.sub(
        rf'(//\s*\S+-\S+-\S+_\d{{4}}-)({corr_anterior:04d})(\b)',
        lambda m: f'{m.group(1)}{corr_nuevo:04d}{m.group(3)}',
        texto, count=1,
    )
    # 2. Campo correlativo en crear-meta
    texto = re.sub(
        r'(correlativo:\s*)\d+',
        lambda m: f'{m.group(1)}{corr_nuevo}',
        texto, count=1,
    )
    # 3. rama-git en s-ficha (reemplaza el número de 4 dígitos al final del path)
    texto = re.sub(
        rf'(rama-git:\s*"[^"]*-)({corr_anterior:04d})(")',
        lambda m: f'{m.group(1)}{corr_nuevo:04d}{m.group(3)}',
        texto,
    )

    ruta_antigua.write_text(texto, encoding="utf-8")
    ruta_antigua.rename(ruta_nueva)
    _ok(f"Archivo: {_c(_C.DIM, ruta_antigua.name)} → {_c(_C.BOLD, ruta_nueva.name)}")

    # ── Renombrar PDFs si existen (con o sin versión en el nombre) ─────────────
    for pdf_viejo in sorted(ruta_antigua.parent.glob(f"{doc['codigo_base']}*.pdf")):
        sufijo = pdf_viejo.name[len(doc["codigo_base"]):]   # "" o " (v1.0)"
        pdf_nuevo = pdf_viejo.parent / f"{base_nuevo}{sufijo}"
        pdf_viejo.rename(pdf_nuevo)
        _ok(f"PDF:     {_c(_C.DIM, pdf_viejo.name)} → {_c(_C.BOLD, pdf_nuevo.name)}")

    # ── Actualizar registro ────────────────────────────────────────────────────
    doc["correlativo"] = corr_nuevo
    doc["codigo_base"] = base_nuevo
    doc["ruta"]        = str(ruta_nueva)
    guardar_registro(SCRIPT_DIR, registro)
    _ok(f"Registro actualizado.")

    # ── Actualizar doctyp.json en el CWD si existe (no aplica en SCRIPT_DIR) ──
    cwd = Path.cwd()
    if cwd.resolve() != SCRIPT_DIR.resolve():
        entradas = leer_doctyp_json(cwd)
        if entradas:
            modificado = False
            for e in entradas:
                if e.get("correlativo") == corr_anterior and e.get("anio") == anio:
                    e["correlativo"]    = corr_nuevo
                    e["nombre_archivo"] = ruta_nueva.name
                    modificado = True
            if modificado:
                (cwd / DOCTYP_JSON).write_text(
                    json.dumps({"documentos": entradas}, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8",
                )
                _ok(f"Actualizado {DOCTYP_JSON} en el directorio actual.")

    print(f"\n  {_c(_C.BOLD, 'Listo.')} "
          f"{_c(_C.DIM, f'{corr_anterior:04d}')} → "
          f"{_c(_C.BOLD + _C.CYAN, f'{corr_nuevo:04d}')}\n")


def cmd_compile(args):
    registro = cargar_registro(SCRIPT_DIR)
    if args.correlativo is None:
        doc = resolver_desde_doctyp_json(Path.cwd(), registro, args.anio)
    else:
        anio = args.anio or datetime.date.today().year
        doc = buscar_doc(registro, args.correlativo, anio)

    typ_path = Path(doc["ruta"])
    if not typ_path.exists():
        sys.exit(f"ERROR: el archivo registrado no existe: {typ_path}")

    # Commit de versión implícito: cada compilación sube el patch antes de generar el PDF,
    # así el documento (portada, ficha, tabla de versiones) siempre refleja la versión compilada.
    mensaje = getattr(args, "mensaje", None) or ""
    if not mensaje:
        mensaje = pedir_mensaje_version()
        if mensaje is None:
            return

    version_actual, version = realizar_save(doc, mensaje)
    guardar_registro(SCRIPT_DIR, registro)
    _ok(f"Versión actualizada: {_c(_C.DIM, 'v' + version_actual)} → "
        f"{_c(_C.BOLD + _C.CYAN, 'v' + version)}")
    _git_snapshot(SCRIPT_DIR, doc, version, mensaje, "save",
                  [typ_path, registro_path(SCRIPT_DIR)])

    pdf_versioned_name = f"{typ_path.stem} (v{version}).pdf"

    print(f"\n  Compilando {_c(_C.BOLD, doc['codigo_base'])} → "
          f"{_c(_C.DIM, pdf_versioned_name)}")
    if not compilar_typ(typ_path):
        sys.exit(1)

    pdf = typ_path.with_suffix(".pdf")
    pdf_versioned = pdf.parent / pdf_versioned_name
    if pdf.exists():
        if pdf_versioned.exists():
            pdf_versioned.unlink()
        pdf.rename(pdf_versioned)
        _ok(f"PDF: {_c(_C.DIM, str(pdf_versioned))}")

    destino_cwd = Path.cwd() / pdf_versioned_name
    if pdf_versioned.exists() and destino_cwd.resolve() != pdf_versioned.resolve():
        import shutil
        shutil.copy2(pdf_versioned, destino_cwd)
        _ok(f"Copiado a: {_c(_C.DIM, str(destino_cwd))}\n")


def cmd_edit(args):
    registro = cargar_registro(SCRIPT_DIR)
    if args.correlativo is None:
        doc = resolver_desde_doctyp_json(Path.cwd(), registro, args.anio)
    else:
        anio = args.anio or datetime.date.today().year
        doc = buscar_doc(registro, args.correlativo, anio)

    typ_path = Path(doc["ruta"])
    if not typ_path.exists():
        sys.exit(f"ERROR: el archivo registrado no existe: {typ_path}")

    agregar_doctyp_json(Path.cwd(), doc["correlativo"], doc["anio"],
                        typ_path.name, doc.get("autor", ""))

    print(f"\n  Documento: {_c(_C.BOLD, doc['codigo_base'])}")
    print(f"  Archivo:   {_c(_C.DIM, str(typ_path))}\n")

    editores = _detectar_editores(typ_path)
    if not editores:
        sys.exit("ERROR: no se encontró ningún editor disponible ($VISUAL/$EDITOR/xdg-open).")

    if len(editores) == 1:
        nombre, editor_cmd = editores[0]
        _lanzar_editor(nombre, editor_cmd, typ_path)
        return

    print(f"  {_c(_C.BOLD, 'Editores encontrados:')}\n")
    for i, (nombre, _) in enumerate(editores, 1):
        tag = _c(_C.DIM, "  (predeterminado)") if i == 1 else ""
        print(f"  {_c(_C.CYAN, str(i))}  {nombre}{tag}")
    print()

    try:
        sel = input(f"  Editor [{_c(_C.CYAN, '1')}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    idx = 0
    if sel and sel.isdigit() and 1 <= int(sel) <= len(editores):
        idx = int(sel) - 1
    elif sel:
        _warn("Opción inválida; usando el predeterminado.")

    nombre, editor_cmd = editores[idx]
    print()
    _lanzar_editor(nombre, editor_cmd, typ_path)


def _seleccionar(opciones: list[str], titulo: str) -> int | None:
    """Muestra un menú numerado y devuelve el índice elegido (0-based) o None si se cancela."""
    print(f"\n  {_c(_C.BOLD, titulo)}")
    for i, etiqueta in enumerate(opciones, 1):
        print(f"  {_c(_C.CYAN, str(i))}  {etiqueta}")
    print()
    while True:
        try:
            sel = input(f"  Selecciona (1-{len(opciones)}, q=cancelar): ").strip()
        except EOFError:
            return None
        if sel.lower() in ("", "q"):
            return None
        if sel.isdigit() and 1 <= int(sel) <= len(opciones):
            return int(sel) - 1
        _warn("Opción inválida.")


def cmd_add(args):
    registro = cargar_registro(SCRIPT_DIR)
    registrados = {d.get("codigo_base") for d in registro["documentos"]}

    cwd = Path.cwd()
    candidatos = []
    for p in sorted(cwd.glob("*.typ")):
        if p.name == args.lib:
            continue
        meta = parse_meta_typ(p)
        if meta is None:
            continue
        base = codigo_base(meta["area"], meta["tipo"], meta["categoria"],
                           meta["anio"], meta["correlativo"])
        if base in registrados:
            continue
        candidatos.append((p, meta, base))

    if not candidatos:
        print(f"  No hay documentos válidos sin registrar en {cwd}.")
        return

    etiquetas = [f"{base}  ·  v{m['version']}  ·  {m['titulo']}  ({p.name})"
                 for p, m, base in candidatos]
    idx = _seleccionar(etiquetas, f"Documentos disponibles en {cwd}:")
    if idx is None:
        print("  Cancelado.")
        return
    p, meta, base = candidatos[idx]

    choque = next((d for d in registro["documentos"]
                   if d.get("anio") == meta["anio"]
                   and d.get("correlativo") == meta["correlativo"]), None)
    if choque:
        sys.exit(f"ERROR: el correlativo {meta['correlativo']:04d} (año {meta['anio']}) ya está "
                 f"registrado por {choque['codigo_base']}. Reasigna el correlativo en el .typ "
                 f"antes de importarlo.")

    import shutil
    dest_dir = docs_dir(meta["anio"])
    dest_dir.mkdir(parents=True, exist_ok=True)
    destino = dest_dir / f"{base}.typ"
    if destino.resolve() != p.resolve():
        shutil.move(str(p), str(destino))
        _ok(f"Movido: {p.name} → {_c(_C.DIM, str(destino))}")
    else:
        print(f"  Ya está en su carpeta: {destino}")

    lib_import = os.path.relpath(SCRIPT_DIR / args.lib, dest_dir).replace(os.sep, "/")
    txt = destino.read_text(encoding="utf-8")
    nuevo, n = re.subn(r'(#import\s+")[^"]*(":\s*\*)',
                       lambda m: f'{m.group(1)}{lib_import}{m.group(2)}', txt, count=1)
    if n and nuevo != txt:
        destino.write_text(nuevo, encoding="utf-8")
        print(f"       Import normalizado a \"{lib_import}\".")

    ahora = datetime.datetime.now().isoformat(timespec="seconds")
    mensaje_import = "Importado al registro."
    entrada = {
        "codigo_base": base,
        "area": meta["area"], "tipo": meta["tipo"], "categoria": meta["categoria"],
        "anio": meta["anio"], "correlativo": meta["correlativo"],
        "titulo": meta["titulo"], "autor": meta["autor"],
        "ruta": str(destino),
        "creado": ahora,
        "versiones": [{"version": meta["version"], "fecha": ahora[:10].replace("-", ""),
                       "creado": ahora, "mensaje": mensaje_import}],
    }
    registro["documentos"].append(entrada)
    guardar_registro(SCRIPT_DIR, registro)
    agregar_doctyp_json(cwd, meta["correlativo"], meta["anio"], f"{base}.typ", meta["autor"])
    _git_snapshot(SCRIPT_DIR, entrada, meta["version"], mensaje_import, "add",
                  [destino, registro_path(SCRIPT_DIR)])

    print()
    _ok(f"Registrado: {_c(_C.BOLD, base)}  (v{meta['version']})")
    print(f"       Archivo:  {_c(_C.DIM, str(destino))}")
    print(f"       Registro: {_c(_C.DIM, str(registro_path(SCRIPT_DIR)))}\n")


def _quitar_de_doctyp_json(cwd: Path, correlativo: int, anio: int) -> bool:
    """Elimina la entrada del doctyp.json del directorio cwd. Devuelve True si lo modificó.
    No hace nada si cwd es SCRIPT_DIR: el registro ya está en settings.json."""
    if cwd.resolve() == SCRIPT_DIR.resolve():
        return False
    entradas = leer_doctyp_json(cwd)
    if not entradas:
        return False
    nuevas = [e for e in entradas
              if not (e.get("correlativo") == correlativo and e.get("anio") == anio)]
    if len(nuevas) == len(entradas):
        return False
    path = cwd / DOCTYP_JSON
    if nuevas:
        path.write_text(
            json.dumps({"documentos": nuevas}, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    else:
        path.unlink()
    return True


def cmd_delete(args):
    """Elimina un documento: archivo .typ, entrada en settings.json y en doctyp.json (si existe)."""
    registro = cargar_registro(SCRIPT_DIR)
    anio = args.anio or datetime.date.today().year
    doc = buscar_doc(registro, args.correlativo, anio)

    typ_path = Path(doc["ruta"])
    base = doc.get("codigo_base", typ_path.stem)

    print(f"\n  {_c(_C.BOLD + _C.RED, 'Eliminar documento')}")
    print(f"  Código:  {_c(_C.BOLD, base)}")
    print(f"  Archivo: {_c(_C.DIM, str(typ_path))}")
    print(f"  Título:  {doc.get('titulo', '')}\n")

    if not args.yes:
        try:
            resp = input(f"  {_c(_C.YELLOW, '¿Confirmar eliminación?')} [s/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if resp not in ("s", "si", "sí", "y", "yes"):
            print("  Cancelado.\n")
            return

    eliminado_typ = False
    if typ_path.exists():
        typ_path.unlink()
        eliminado_typ = True

    pdf_path = typ_path.with_suffix(".pdf")
    eliminado_pdf = False
    if pdf_path.exists():
        pdf_path.unlink()
        eliminado_pdf = True

    registro["documentos"] = [
        d for d in registro["documentos"]
        if not (d.get("correlativo") == doc["correlativo"] and d.get("anio") == doc["anio"])
    ]
    guardar_registro(SCRIPT_DIR, registro)

    eliminado_json = _quitar_de_doctyp_json(Path.cwd(), doc["correlativo"], doc["anio"])

    print()
    if eliminado_typ:
        _ok(f"Archivo eliminado:  {_c(_C.DIM, str(typ_path))}")
    else:
        _warn(f"Archivo no encontrado (ya no existía): {typ_path}")
    if eliminado_pdf:
        _ok(f"PDF eliminado:      {_c(_C.DIM, str(pdf_path))}")
    _ok(f"Eliminado del registro: {_c(_C.DIM, str(registro_path(SCRIPT_DIR)))}")
    if eliminado_json:
        _ok(f"Eliminado de {DOCTYP_JSON} en el directorio actual.")
    print()


def cmd_import(args):
    """Registra un documento del sistema en doctyp.json del directorio actual."""
    registro = cargar_registro(SCRIPT_DIR)
    docs = sorted(registro["documentos"],
                  key=lambda d: (d.get("anio", 0), d.get("correlativo", 0)))
    if not docs:
        sys.exit("ERROR: el registro está vacío (aún no se han creado documentos).")

    anio = args.anio or datetime.date.today().year

    if args.correlativo is not None:
        doc = buscar_doc(registro, args.correlativo, anio)
    else:
        etiquetas = []
        for d in docs:
            vers = d.get("versiones") or []
            ver_str = f"v{vers[-1]['version']}" if vers else ""
            etiquetas.append(
                f"{d.get('correlativo', 0):04d}  {d.get('codigo_base', '')}"
                f"  {ver_str}  ·  {d.get('titulo', '')}"
            )
        idx = _seleccionar(etiquetas, "Documentos registrados en el sistema:")
        if idx is None:
            print("  Cancelado.")
            return
        doc = docs[idx]

    cwd = Path.cwd()
    nombre_archivo = Path(doc["ruta"]).name
    agregar_doctyp_json(cwd, doc["correlativo"], doc["anio"],
                        nombre_archivo, doc.get("autor", ""))

    corr_str = f"{doc['correlativo']:04d}"
    print()
    _ok(f"Importado en {_c(_C.DIM, str(cwd / DOCTYP_JSON))}")
    print(f"       Documento: {_c(_C.BOLD, doc.get('codigo_base', ''))}")
    print(f"       Correlativo: {_c(_C.CYAN, corr_str)} (año {doc['anio']})\n")


def cmd_git_init(args):
    """Inicializa o migra el repositorio git para snapshots de versión. Idempotente:
    puede ejecutarse varias veces sin duplicar tags ni fallar."""
    root = SCRIPT_DIR
    if not _git_disponible():
        sys.exit("ERROR: git no está disponible (ni en el PATH ni vía flatpak-spawn).")

    print(f"\n  {_c(_C.BOLD, 'Inicialización de snapshots git')}")
    print(f"  {_c(_C.DIM, str(root))}\n")

    if _git_repo_ok(root):
        _ok("Ya existe un repositorio git en este directorio.")
    else:
        r = _git("init", root=root)
        if r.returncode != 0:
            sys.exit(f"ERROR: no se pudo inicializar el repositorio: {r.stderr.strip()}")
        _ok("Repositorio git inicializado.")

    # .gitignore: el PDF y los artefactos de Python nunca se versionan.
    gitignore = root / ".gitignore"
    necesarias = ["*.pdf", "__pycache__/"]
    actuales = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    faltantes = [l for l in necesarias if l not in actuales]
    if faltantes:
        with gitignore.open("a", encoding="utf-8") as fh:
            if actuales and actuales[-1].strip() != "":
                fh.write("\n")
            fh.write("\n".join(faltantes) + "\n")
        _ok(f".gitignore actualizado: {', '.join(faltantes)}")
    else:
        _ok(".gitignore ya contiene las reglas necesarias.")

    # Identidad git local (solo si no hay ninguna resoluble, local o global).
    def _config_get(clave: str) -> str:
        r = _git("config", "--get", clave, root=root)
        return r.stdout.strip() if r.returncode == 0 else ""

    if not _config_get("user.name") or not _config_get("user.email"):
        registro = cargar_registro(root)
        autoria = author_defaults(registro)
        _warn("No hay identidad git configurada (user.name/user.email).")
        try:
            resp = input(f"  ¿Configurarla en este repositorio con "
                         f"{autoria['autor']} <{autoria['correo']}>? [S/n]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            resp = "n"
            print()
        if resp in ("", "s", "si", "sí", "y", "yes"):
            _git("config", "user.name", autoria["autor"], root=root)
            _git("config", "user.email", autoria["correo"], root=root)
            _ok("Identidad git configurada a nivel de repositorio (local).")

    # Commit inicial si el working tree tiene cambios pendientes.
    r_status = _git("status", "--porcelain", root=root)
    if r_status.stdout.strip():
        _git("add", "-A", root=root)
        r_commit = _git("commit", "-m", "chore: snapshot inicial de doctyp", root=root)
        if r_commit.returncode == 0:
            _ok("Commit inicial creado con el estado actual del proyecto.")
        else:
            _warn(f"No se pudo crear el commit inicial: "
                  f"{(r_commit.stderr or r_commit.stdout).strip()}")
    else:
        _ok("Working tree limpio; no hace falta commit inicial.")

    # Tags retroactivos: solo la ÚLTIMA versión de cada documento tiene contenido recuperable.
    registro = cargar_registro(root)
    creados = existentes = sin_version = 0
    for doc in registro["documentos"]:
        vers = doc.get("versiones") or []
        if not vers:
            sin_version += 1
            continue
        version = vers[-1]["version"]
        tag = _tag_doc(doc, version)
        existe = _git("rev-parse", "--verify", "--quiet", f"refs/tags/{tag}", root=root)
        if existe.returncode == 0:
            existentes += 1
            continue
        mensaje = vers[-1].get("mensaje") or "Snapshot retroactivo (doctyp git-init)."
        r_tag = _git("tag", "-a", tag, "-m", mensaje, root=root)
        if r_tag.returncode == 0:
            creados += 1
        else:
            _warn(f"No se pudo crear el tag {tag}: {r_tag.stderr.strip()}")

    print()
    extra = f", {sin_version} sin versión registrada" if sin_version else ""
    _ok(f"Tags retroactivos: {creados} creados, {existentes} ya existían{extra}.")
    if creados:
        _warn("Los tags retroactivos apuntan al commit actual: solo la versión VIGENTE de cada "
              "documento quedó con snapshot recuperable. Las versiones intermedias, guardadas "
              "antes de 'git-init', no se pueden reconstruir.")
    print()


def cmd_history(args):
    """Lista las versiones de un documento e indica si tienen snapshot git disponible."""
    registro = cargar_registro(SCRIPT_DIR)
    ref = args.docref
    if ref is None:
        try:
            ref = input("  Documento (correlativo[:version][@anio]): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not ref:
            print("  Cancelado.")
            return

    corr, _version_ignorada, anio = _parse_docref_partes(ref)
    doc = buscar_doc(registro, corr, anio)
    vers = doc.get("versiones") or []

    print(f"\n  {_c(_C.BOLD, doc['codigo_base'])}  ·  {doc.get('titulo', '')}")
    if not vers:
        print(f"  {_c(_C.YELLOW, '!')} Sin versiones registradas.\n")
        return

    con_git = _git_repo_ok(SCRIPT_DIR)
    print()
    for v in reversed(vers):
        tag = _tag_doc(doc, v["version"])
        if con_git:
            r = _git("rev-parse", "--verify", "--quiet", f"refs/tags/{tag}", root=SCRIPT_DIR)
            snap = _c(_C.GREEN, "✔") if r.returncode == 0 else _c(_C.DIM, "–")
        else:
            snap = _c(_C.DIM, "–")
        fecha = v.get("fecha", "")
        fecha_fmt = f"{fecha[:4]}-{fecha[4:6]}-{fecha[6:]}" if len(fecha) == 8 else fecha
        ver_col = _c(_C.BOLD + _C.CYAN, f"v{v['version']:<8}")
        print(f"  {snap}  {ver_col} {fecha_fmt:<12} {v.get('mensaje', '')}")

    if not con_git:
        print(f"\n  {_c(_C.YELLOW, '!')} git no disponible o el directorio no es un repositorio "
              f"— ejecuta 'doctyp git-init' para habilitar snapshots.")
    print()


def cmd_restore(args):
    """Extrae el .typ de una versión anterior desde su snapshot git, sin tocar el vigente."""
    registro = cargar_registro(SCRIPT_DIR)
    root = SCRIPT_DIR

    ref = args.docref
    if ref is None:
        try:
            ref = input("  Documento a restaurar (correlativo[:version][@anio]): ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not ref:
            print("  Cancelado.")
            return

    if not _git_repo_ok(root):
        sys.exit("ERROR: este directorio no es un repositorio git (o git no está disponible). "
                 "Ejecuta 'doctyp git-init' primero.")

    corr, version, anio = _parse_docref_partes(ref)
    doc = buscar_doc(registro, corr, anio)
    vers = doc.get("versiones") or []

    if version is None:
        if len(vers) < 2:
            _warn(f"El documento {doc['codigo_base']} no tiene una versión anterior que "
                  f"restaurar (solo registra {len(vers)} versión(es)).")
            return
        version = vers[-2]["version"]
        _ok(f"Sin versión indicada: se usará la anterior a la vigente "
            f"({_c(_C.CYAN, 'v' + version)}).")
    else:
        disponibles = [v["version"] for v in vers]
        if version not in disponibles:
            sys.exit(f"ERROR: el documento {doc['codigo_base']} no tiene la versión '{version}'. "
                     f"Disponibles: {', '.join(disponibles) or '(ninguna)'}")

    tag = _tag_doc(doc, version)
    r_tag = _git("rev-parse", "--verify", "--quiet", f"refs/tags/{tag}", root=root)
    if r_tag.returncode != 0:
        sys.exit(f"ERROR: no existe el snapshot '{tag}' para esa versión. "
                 f"Usa 'doctyp history {corr}' para ver qué versiones tienen snapshot.")

    ruta = Path(doc["ruta"])
    rel_git = Path(os.path.relpath(ruta, root)).as_posix()
    r_show = _git("show", f"{tag}:{rel_git}", root=root)
    if r_show.returncode != 0:
        sys.exit(f"ERROR: no se pudo leer '{rel_git}' en '{tag}': {r_show.stderr.strip()}")
    contenido = r_show.stdout

    if args.stdout:
        print(contenido, end="" if contenido.endswith("\n") else "\n")
        return

    destino = ruta.parent / f"{doc['codigo_base']}_v{version}.typ"
    if destino.exists():
        sys.exit(f"ERROR: ya existe {destino}; no se sobreescribe. "
                 f"Bórralo o renómbralo antes de restaurar.")
    destino.write_text(contenido, encoding="utf-8")
    print()
    _ok(f"Restaurado: {_c(_C.DIM, str(destino))}  (v{version}, el vigente no se modifica)")

    if args.pdf:
        print(f"\n  Compilando snapshot v{version}...")
        compilar_typ(destino)
    print()


# ── CLI ───────────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="doctyp — Generador de informes de la plantilla SLEP Chinchorro.",
        epilog="Sin argumentos muestra el menú interactivo.",
    )
    p.add_argument("--lib", default="lib.typ",
                   help="Nombre del archivo de plantilla junto al script. Por defecto: lib.typ")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", aliases=["ls"],
                        help="Lista documentos existentes y el próximo correlativo.")
    pl.add_argument("--anio", type=int, help="Año a consultar (por defecto, el actual).")
    pl.add_argument("--org", help="Organización a consultar (por defecto, la activa).")
    pl.set_defaults(func=cmd_listar)

    po = sub.add_parser("org", help="Gestiona organizaciones.")
    po_sub = po.add_subparsers(dest="org_cmd", required=True)

    po_new = po_sub.add_parser("new", help="Crea una nueva organización.")
    po_new.add_argument("slug", metavar="SLUG", help="Identificador (minúsculas, dígitos, guiones).")
    po_new.add_argument("--nombre", help="Nombre visible (por defecto, el slug).")
    po_new.set_defaults(func=cmd_org_new)

    po_list = po_sub.add_parser("list", aliases=["ls"], help="Lista organizaciones.")
    po_list.set_defaults(func=cmd_org_list)

    po_use = po_sub.add_parser("use", help="Fija la organización activa.")
    po_use.add_argument("slug", metavar="SLUG")
    po_use.set_defaults(func=cmd_org_use)

    pt = sub.add_parser("team", help="Gestiona equipos de la organización activa.")
    pt_sub = pt.add_subparsers(dest="team_cmd", required=True)

    pt_new = pt_sub.add_parser("new", help="Crea un equipo.")
    pt_new.add_argument("id", metavar="ID", help="Identificador del equipo.")
    pt_new.add_argument("--nombre", help="Nombre visible (por defecto, el id).")
    pt_new.set_defaults(func=cmd_team_new)

    pt_list = pt_sub.add_parser("list", aliases=["ls"], help="Lista equipos.")
    pt_list.set_defaults(func=cmd_team_list)

    pau = sub.add_parser("author", help="Gestiona autores de la organización activa.")
    pau_sub = pau.add_subparsers(dest="author_cmd", required=True)

    pau_add = pau_sub.add_parser("add", help="Alta interactiva de un autor.")
    pau_add.add_argument("--nombre", help="Nombre del autor.")
    pau_add.add_argument("--cargo", help="Cargo del autor.")
    pau_add.add_argument("--correo", help="Correo del autor.")
    pau_add.add_argument("--equipos", help="Ids de equipo separados por coma.")
    pau_add.set_defaults(func=cmd_author_add)

    pau_list = pau_sub.add_parser("list", aliases=["ls"], help="Lista autores.")
    pau_list.set_defaults(func=cmd_author_list)

    pau_use = pau_sub.add_parser("use", help="Fija el autor activo.")
    pau_use.add_argument("id", metavar="ID")
    pau_use.set_defaults(func=cmd_author_use)

    pn = sub.add_parser("new", aliases=["n"],
                        help="Crea un nuevo documento .typ con correlativo secuencial.")
    pn.add_argument("titulo_pos", nargs="?", metavar="TÍTULO",
                    help="Título del documento (posicional). Equivale a --titulo / --t.")
    pn.add_argument("--titulo", "--t", dest="titulo",
                    help="Título (si falta, se toma del posicional o se pide interactivo).")
    pn.add_argument("--tipo", default="INF",
                    help=f"Tipo: {', '.join(TIPOS)}. Por defecto: INF")
    pn.add_argument("--categoria", default="SFW",
                    help=f"Categoría: {', '.join(sorted(CATEGORIAS))}. Por defecto: SFW")
    pn.add_argument("--subtitulo", help="Subtítulo de portada.")
    pn.add_argument("--area", default="TI", help="Área emisora. Por defecto: TI")
    pn.add_argument("--anio", type=int,
                    help="Año (por defecto, el de --fecha o el actual).")
    pn.add_argument("--correlativo", "--code", type=int, dest="correlativo",
                    help="Forzar correlativo manualmente (por defecto: secuencial automático).")
    pn.add_argument("--version", default="1.0",
                    help="Versión inicial. Por defecto: 1.0")
    pn.add_argument("--fecha", help="Fecha AAAAMMDD. Por defecto: hoy.")
    pn.add_argument("--tipo-largo", dest="tipo_largo",
                    help="Rótulo de portada (por defecto, según --tipo).")
    pn.add_argument("--estado", default="BORRADOR",
                    help="BORRADOR | EN REVISIÓN | APROBADO")
    pn.add_argument("--clasificacion", default="INTERNO",
                    help="PÚBLICO | INTERNO | RESERVADO | CONFIDENCIAL")
    pn.add_argument("--autor", help="Autor (por defecto: settings.json -> local.author).")
    pn.add_argument("--cargo", help="Cargo del autor.")
    pn.add_argument("--correo", help="Correo del autor.")
    pn.add_argument("--revisor", help="Revisor.")
    pn.add_argument("--aprobador", help="Aprobador.")
    pn.add_argument("--forzar", action="store_true",
                    help="Sobrescribir si el archivo ya existe.")
    pn.set_defaults(func=cmd_nuevo)

    ps = sub.add_parser("save", aliases=["s", "commit"],
                        help="Registra una nueva versión de un documento (bump del número menor).")
    ps.add_argument("correlativo", type=int, nargs="?", metavar="CORRELATIVO",
                    help="Número correlativo del documento a versionar. "
                         "Si se omite, se muestra selección interactiva.")
    ps.add_argument("--mensaje", "--m", dest="mensaje",
                    help="Mensaje descriptivo de la nueva versión. Si se omite, se pide interactivo.")
    ps.add_argument("--anio", type=int, help="Año del documento (por defecto, el actual).")
    ps.set_defaults(func=cmd_save)

    pch = sub.add_parser("change",
                         help="Cambia el correlativo de un documento registrado.")
    pch.add_argument("correlativo_anterior", type=int, nargs="?", metavar="CORRELATIVO_ANTERIOR",
                     help="Correlativo actual del documento. Si se omite, selección interactiva.")
    pch.add_argument("correlativo_nuevo", type=int, nargs="?", metavar="CORRELATIVO_NUEVO",
                     help="Nuevo correlativo. Si se omite, se pide interactivo.")
    pch.add_argument("--anio", type=int, help="Año del documento (por defecto, el actual).")
    pch.set_defaults(func=cmd_change)

    pa = sub.add_parser("add", aliases=["a"],
                        help="Importa al registro un documento existente del directorio actual.")
    pa.set_defaults(func=cmd_add)

    pd = sub.add_parser("delete", aliases=["del"],
                        help="Elimina un documento: .typ, registro y doctyp.json.")
    pd.add_argument("correlativo", type=int, metavar="CORRELATIVO",
                    help="Número correlativo del documento a eliminar.")
    pd.add_argument("--anio", type=int, help="Año del documento (por defecto, el actual).")
    pd.add_argument("--y", dest="yes", action="store_true",
                    help="Confirmar sin preguntar.")
    pd.set_defaults(func=cmd_delete)

    pi = sub.add_parser("import", aliases=["i"],
                        help="Añade un documento del registro al doctyp.json del directorio actual.")
    pi.add_argument("correlativo", type=int, nargs="?", metavar="CORRELATIVO",
                    help="Correlativo del documento a importar (si se omite, selección interactiva).")
    pi.add_argument("--anio", type=int, help="Año del documento (por defecto, el actual).")
    pi.set_defaults(func=cmd_import)

    pc = sub.add_parser("compile", aliases=["c"],
                        help="Sube versión (commit implícito) y compila el documento a PDF.")
    pc.add_argument("correlativo", type=int, nargs="?", metavar="CORRELATIVO",
                    help="Número correlativo del documento a compilar. "
                         "Si se omite, se lee de doctyp.json en el directorio actual.")
    pc.add_argument("--mensaje", "--m", dest="mensaje",
                    help="Mensaje de la nueva versión que se sube antes de compilar. "
                         "Si se omite, se pide interactivo.")
    pc.add_argument("--anio", type=int, help="Año del documento (por defecto, el actual).")
    pc.set_defaults(func=cmd_compile)

    pe = sub.add_parser("edit", aliases=["code", "e", "open"],
                        help="Abre el documento en el editor (VS Code por defecto, selección interactiva).")
    pe.add_argument("correlativo", type=int, nargs="?", metavar="CORRELATIVO",
                    help="Número correlativo del documento a abrir. "
                         "Si se omite, se lee de doctyp.json en el directorio actual.")
    pe.add_argument("--anio", type=int, help="Año del documento (por defecto, el actual).")
    pe.set_defaults(func=cmd_edit)

    pca = sub.add_parser("config-author",
                         help="[legacy v2] Configura el autor global (settings.json -> local.author). "
                              "Reemplazado por 'doctyp author add/list/use' (organizaciones v3).")
    pca.set_defaults(func=cmd_config_author)

    pr = sub.add_parser("reset",
                        help="Fija dónde empieza el correlativo del año (en settings.json).")
    pr.add_argument("correlativo", type=int, nargs="?", metavar="CORRELATIVO",
                    help="Número de inicio (por defecto: 1).")
    pr.add_argument("--anio", type=int, help="Año a configurar (por defecto, el actual).")
    pr.set_defaults(func=cmd_reset)

    pgi = sub.add_parser("git-init",
                         help="Inicializa/migra el repositorio git para snapshots de versión.")
    pgi.set_defaults(func=cmd_git_init)

    ph = sub.add_parser("history", aliases=["h", "log"],
                        help="Lista las versiones de un documento y si tienen snapshot git.")
    ph.add_argument("docref", nargs="?", metavar="DOC-REF",
                    help="<correlativo>[:version][@anio]. Si se omite, se pide interactivo.")
    ph.set_defaults(func=cmd_history)

    prs = sub.add_parser("restore",
                         help="Extrae el .typ de una versión anterior desde su snapshot git.")
    prs.add_argument("docref", nargs="?", metavar="DOC-REF",
                     help="<correlativo>[:version][@anio]. Sin versión usa la anterior a la "
                          "vigente. Si se omite todo, se pide interactivo.")
    prs.add_argument("--pdf", action="store_true", help="Compila también la versión restaurada.")
    prs.add_argument("--stdout", action="store_true",
                     help="Imprime el contenido en stdout en vez de escribir un archivo.")
    prs.set_defaults(func=cmd_restore)

    return p


def menu_interactivo() -> None:
    """Menú principal que se muestra cuando doctyp se invoca sin argumentos."""
    print_banner()

    # Resumen rápido del estado
    try:
        slug = org_activa_slug()
        org = cargar_org(slug)
        n_docs = len(org["documentos"])
        anio = datetime.date.today().year
        proximo = next_correlativo_org(org, anio)
        print(f"\n  {_c(_C.DIM, f'org: {slug}  ·  {n_docs} documento(s) registrado(s)')}  ·  "
              f"{_c(_C.DIM, f'próximo: {proximo:04d}  ({anio})')}")
    except Exception:
        print()

    CMDS = [
        ("list",          "ls",              "Listar documentos y el próximo correlativo"),
        ("new",           "n",               "Crear un nuevo documento"),
        ("save",          "s / commit",      "Registrar nueva versión de un documento"),
        ("change",        "",                "Cambiar el correlativo de un documento"),
        ("add",           "a",               "Importar un .typ existente al registro"),
        ("import",        "i",               "Anclar un documento del registro en doctyp.json"),
        ("delete",        "del",             "Eliminar un documento del sistema"),
        ("compile",       "c",               "Subir versión y compilar un documento a PDF"),
        ("edit",          "code / e / open", "Abrir un documento en el editor"),
        ("reset",         "",                "Fijar el inicio del correlativo del año"),
        ("org list",      "",                "Listar organizaciones"),
        ("team list",     "",                "Listar equipos de la organización activa"),
        ("author list",   "",                "Listar autores de la organización activa"),
        ("config-author", "",                "[legacy v2] Configurar el autor global"),
        ("git-init",      "",                "Inicializar/migrar snapshots git"),
        ("history",       "h / log",         "Ver el historial de versiones de un documento"),
        ("restore",       "",                "Restaurar una versión anterior desde su snapshot"),
    ]

    print(f"\n  {_c(_C.BOLD, 'Comandos disponibles:')}\n")
    for i, (cmd, alias, desc) in enumerate(CMDS, 1):
        alias_str = _c(_C.DIM, f"  [{alias}]") if alias else ""
        print(f"  {_c(_C.CYAN, str(i))}  {_c(_C.BOLD, f'{cmd:<14}')}{alias_str}  {desc}")
    print()

    try:
        sel = input(f"  Selecciona [{_c(_C.DIM, f'1-{len(CMDS)}, q=salir')}]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return

    if not sel or sel.lower() == "q":
        return
    if not sel.isdigit() or not (1 <= int(sel) <= len(CMDS)):
        _warn("Opción inválida.")
        return

    cmd_sel = CMDS[int(sel) - 1][0]
    argv = cmd_sel.split(" ")

    # Solicitar argumentos adicionales según el comando
    if cmd_sel == "save":
        print()
        try:
            corr = input("  Correlativo del documento: ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not corr.isdigit():
            _warn("Correlativo inválido.")
            return
        argv.append(corr)
        try:
            msg = input("  Mensaje de la nueva versión: ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not msg:
            _warn("El mensaje es obligatorio.")
            return
        argv += ["--m", msg]

    elif cmd_sel == "import":
        pass  # cmd_import muestra la lista interactiva por sí solo

    elif cmd_sel == "delete":
        print()
        try:
            corr = input("  Correlativo del documento a eliminar: ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not corr.isdigit():
            _warn("Correlativo inválido.")
            return
        argv.append(corr)
        # La confirmación la pide cmd_delete de forma interactiva

    elif cmd_sel in ("edit", "compile"):
        ctx_list = leer_doctyp_json(Path.cwd())
        if ctx_list:
            # doctyp.json disponible: el subcomando resolverá (1 entrada auto, varios interactivo)
            n = len(ctx_list)
            hint = _c(_C.DIM, f"({n} documento(s) en {DOCTYP_JSON} — Enter para usar)")
            print(f"\n  {hint}")
        else:
            # Sin doctyp.json: pedir correlativo obligatorio
            print()
            try:
                corr = input("  Correlativo del documento: ").strip()
            except (EOFError, KeyboardInterrupt):
                return
            if not corr.isdigit():
                _warn("Correlativo inválido.")
                return
            argv.append(corr)

    elif cmd_sel == "reset":
        print()
        try:
            corr = input("  Correlativo de inicio [1]: ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if corr:
            if not corr.isdigit():
                _warn("Correlativo inválido.")
                return
            argv.append(corr)

    elif cmd_sel == "git-init":
        pass  # no requiere argumentos

    elif cmd_sel in ("history", "restore"):
        print()
        try:
            ref = input("  Documento (correlativo[:version][@anio]): ").strip()
        except (EOFError, KeyboardInterrupt):
            return
        if not ref:
            _warn("Referencia de documento requerida.")
            return
        argv.append(ref)
        if cmd_sel == "restore":
            try:
                pdf = input("  ¿Compilar también a PDF? [s/N]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                return
            if pdf in ("s", "si", "sí", "y", "yes"):
                argv.append("--pdf")

    print()
    try:
        parsed = build_parser().parse_args(argv)
        parsed.func(parsed)
    except SystemExit as e:
        if e.code != 0:
            raise


def main():
    if len(sys.argv) == 1:
        menu_interactivo()
        return
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
