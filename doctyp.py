#!/usr/bin/env python3
"""
doctyp — Generador de informes para la plantilla Typst del SLEP Chinchorro (Unidad TI).

Comando global: se instala como `doctyp` (symlink en ~/.local/bin) y se invoca desde cualquier
carpeta. Todos los documentos se gestionan de forma centralizada en SCRIPT_DIR, junto a lib.typ.

Sin argumentos muestra un menú interactivo con todos los comandos disponibles.

Subcomandos (con alias):  list/ls · new/n · save/s · add/a · compile/c ·
                          edit/code/e/open · reset · config-author/author

Uso rápido:
    doctyp                                                # menú interactivo
    doctyp new "Auditoría de respaldos"                   # título posicional + defaults de autoría
    doctyp n --t "Manual de red" --tipo MAN --categoria RED
    doctyp save 1 --m "Corrige sección de alcance"        # sube versión (1.0.0 -> 1.0.1) del doc 0001
    doctyp compile 1                                      # compila el doc 0001 a PDF
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


def agregar_doctyp_json(cwd: Path, correlativo: int, anio: int,
                        nombre_archivo: str, autor: str) -> None:
    """Añade una entrada al doctyp.json del directorio cwd (lo crea si no existe).
    Migra automáticamente el formato anterior (dict plano) a lista."""
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
    Devuelve la lista de entradas o None si no existe o es inválido.
    Migra el formato anterior (dict plano) de forma transparente."""
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
#s-versiones((
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

def cmd_listar(args):
    registro = cargar_registro(SCRIPT_DIR)
    docs = sorted(registro["documentos"], key=lambda d: (d.get("anio", 0), d.get("correlativo", 0)))
    anio = args.anio or datetime.date.today().year

    print(f"\n  {_c(_C.DIM, 'Registro: ' + str(registro_path(SCRIPT_DIR)))}")

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

    inicio = correlativo_inicio(registro, anio)
    if inicio is not None:
        print(f"\n  {_c(_C.DIM, f'Inicio configurado para {anio}: {inicio:04d}')}")
    proximo = next_correlativo_json(registro, anio)
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
    registro = cargar_registro(SCRIPT_DIR)
    fallback = next_correlativo(scan_existing(out_dir, exclude={args.lib}), anio) - 1
    corr = args.correlativo if args.correlativo is not None else next_correlativo_json(registro, anio, fallback)

    autoria = author_defaults(registro)
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
    registro["documentos"].append({
        "codigo_base": base,
        "area": f["area"], "tipo": tipo, "categoria": cat,
        "anio": anio, "correlativo": corr,
        "titulo": titulo, "autor": f["autor"],
        "ruta": str(out_file),
        "creado": ahora,
        "versiones": [{"version": f["version"], "fecha": fecha, "creado": ahora}],
    })
    guardar_registro(SCRIPT_DIR, registro)
    agregar_doctyp_json(Path.cwd(), corr, anio, f"{base}.typ", f["autor"])

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
        try:
            mensaje = input("  Mensaje de la nueva versión: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not mensaje:
            sys.exit("ERROR: el mensaje es obligatorio.")

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
    nuevo_texto, n = re.subn(r'(#s-versiones\(\(\n)',
                             lambda m: m.group(1) + fila,
                             nuevo_texto, count=1)
    if n == 0:
        sys.exit(f"ERROR: no se encontró el bloque '#s-versiones((' en {typ_path}.")

    typ_path.write_text(nuevo_texto, encoding="utf-8")

    ahora = datetime.datetime.now().isoformat(timespec="seconds")
    doc.setdefault("versiones", []).append({
        "version": version_nueva, "fecha": fecha, "creado": ahora, "mensaje": mensaje,
    })
    guardar_registro(SCRIPT_DIR, registro)

    print()
    _ok(f"Versión actualizada: {_c(_C.DIM, 'v' + version_actual)} → "
        f"{_c(_C.BOLD + _C.CYAN, 'v' + version_nueva)}")
    print(f"       Documento: {_c(_C.BOLD, doc['codigo_base'])}")
    print(f"       Archivo:   {_c(_C.DIM, str(typ_path))}")
    print(f"       Mensaje:   {mensaje}\n")


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

    version = (doc.get("versiones") or [{}])[-1].get("version", "1.0")
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
    registro["documentos"].append({
        "codigo_base": base,
        "area": meta["area"], "tipo": meta["tipo"], "categoria": meta["categoria"],
        "anio": meta["anio"], "correlativo": meta["correlativo"],
        "titulo": meta["titulo"], "autor": meta["autor"],
        "ruta": str(destino),
        "creado": ahora,
        "versiones": [{"version": meta["version"], "fecha": ahora[:10].replace("-", ""),
                       "creado": ahora, "mensaje": "Importado al registro."}],
    })
    guardar_registro(SCRIPT_DIR, registro)
    agregar_doctyp_json(cwd, meta["correlativo"], meta["anio"], f"{base}.typ", meta["autor"])

    print()
    _ok(f"Registrado: {_c(_C.BOLD, base)}  (v{meta['version']})")
    print(f"       Archivo:  {_c(_C.DIM, str(destino))}")
    print(f"       Registro: {_c(_C.DIM, str(registro_path(SCRIPT_DIR)))}\n")


def _quitar_de_doctyp_json(cwd: Path, correlativo: int, anio: int) -> bool:
    """Elimina la entrada del doctyp.json del directorio cwd. Devuelve True si lo modificó."""
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
    pl.set_defaults(func=cmd_listar)

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
                        help="Compila un documento a PDF (queda junto al .typ).")
    pc.add_argument("correlativo", type=int, nargs="?", metavar="CORRELATIVO",
                    help="Número correlativo del documento a compilar. "
                         "Si se omite, se lee de doctyp.json en el directorio actual.")
    pc.add_argument("--anio", type=int, help="Año del documento (por defecto, el actual).")
    pc.set_defaults(func=cmd_compile)

    pe = sub.add_parser("edit", aliases=["code", "e", "open"],
                        help="Abre el documento en el editor (VS Code por defecto, selección interactiva).")
    pe.add_argument("correlativo", type=int, nargs="?", metavar="CORRELATIVO",
                    help="Número correlativo del documento a abrir. "
                         "Si se omite, se lee de doctyp.json en el directorio actual.")
    pe.add_argument("--anio", type=int, help="Año del documento (por defecto, el actual).")
    pe.set_defaults(func=cmd_edit)

    pca = sub.add_parser("config-author", aliases=["author"],
                         help="Configura el autor global (settings.json -> local.author).")
    pca.set_defaults(func=cmd_config_author)

    pr = sub.add_parser("reset",
                        help="Fija dónde empieza el correlativo del año (en settings.json).")
    pr.add_argument("correlativo", type=int, nargs="?", metavar="CORRELATIVO",
                    help="Número de inicio (por defecto: 1).")
    pr.add_argument("--anio", type=int, help="Año a configurar (por defecto, el actual).")
    pr.set_defaults(func=cmd_reset)

    return p


def menu_interactivo() -> None:
    """Menú principal que se muestra cuando doctyp se invoca sin argumentos."""
    print_banner()

    # Resumen rápido del estado
    try:
        registro = cargar_registro(SCRIPT_DIR)
        n_docs = len(registro["documentos"])
        anio = datetime.date.today().year
        proximo = next_correlativo_json(registro, anio)
        print(f"\n  {_c(_C.DIM, f'{n_docs} documento(s) registrado(s)')}  ·  "
              f"{_c(_C.DIM, f'próximo: {proximo:04d}  ({anio})')}")
    except Exception:
        print()

    CMDS = [
        ("list",          "ls",              "Listar documentos y el próximo correlativo"),
        ("new",           "n",               "Crear un nuevo documento"),
        ("save",          "s / commit",      "Registrar nueva versión de un documento"),
        ("add",           "a",               "Importar un .typ existente al registro"),
        ("import",        "i",               "Anclar un documento del registro en doctyp.json"),
        ("delete",        "del",             "Eliminar un documento del sistema"),
        ("compile",       "c",               "Compilar un documento a PDF"),
        ("edit",          "code / e / open", "Abrir un documento en el editor"),
        ("reset",         "",                "Fijar el inicio del correlativo del año"),
        ("config-author", "author",          "Configurar el autor global"),
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
    argv = [cmd_sel]

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
