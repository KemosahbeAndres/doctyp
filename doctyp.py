#!/usr/bin/env python3
"""
doctyp — Generador de informes para la plantilla Typst del SLEP Chinchorro (Unidad TI).

Comando global: se instala como `doctyp` (symlink en ~/.local/bin) y se invoca desde cualquier
carpeta. Todos los documentos se gestionan de forma centralizada en <Documentos>/doctyp/<año>/
(creados, importados, editados, compilados). La plantilla (lib.typ), los logos (Images/) y la
configuración/registro (settings.json) viven junto al script.

Crea un archivo .typ con la nomenclatura oficial (AREA-TIPO-CAT_AAAA-NNNN) y la estructura
canónica, asignando el correlativo de forma SECUENCIAL automática (global anual). La fuente de
verdad del correlativo y de las versiones es `settings.json`, junto al script.

Subcomandos (con alias):  list/ls · new/n · save/s · add/a · compile/c · edit/code/e · reset

Uso rápido:
    doctyp new "Auditoría de respaldos"                 # título posicional + defaults de autoría
    doctyp n --t "Manual de red" --tipo MAN --categoria RED
    doctyp new "Otro informe" --code 50                 # fuerza el correlativo a 0050
    doctyp save 1 --m "Corrige sección de alcance"      # sube versión (1.0.0 -> 1.0.1) del doc 0001
    doctyp add                                          # importa un .typ del CWD al registro
    doctyp compile 1                                    # compila el doc 0001 a PDF (junto al .typ)
    doctyp edit 1                                       # abre el doc 0001 en VS Code / editor favorito
    doctyp reset 100                                    # el próximo correlativo del año será 0100
    doctyp ls

El título acepta posicional, --titulo o --t. Sin título, se pide de forma interactiva.
No requiere paquetes externos (solo stdlib).
"""
from __future__ import annotations
import argparse, json, os, re, sys, subprocess, datetime
from pathlib import Path

# Ubicación real del script (resuelve el symlink). Aquí viven lib.typ, Images/ y settings.json.
SCRIPT_DIR = Path(__file__).resolve().parent
REGISTRO = "settings.json"

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


# ----------------------------------------------------------------------
# Utilidades
# ----------------------------------------------------------------------
def find_root(start: Path, lib_name: str) -> Path:
    """Sube desde `start` hasta encontrar el directorio que contiene lib.typ."""
    start = start.resolve()
    for d in [start, *start.parents]:
        if (d / lib_name).exists():
            return d
    return start  # fallback: directorio actual


def scan_existing(root: Path, exclude: set[str] | None = None) -> list[dict]:
    """Documentos existentes detectados (por nombre y por contenido).
    Ignora el propio lib.typ y las líneas comentadas (// ...)."""
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
            # Excluir líneas comentadas (esqueletos de ejemplo, etc.)
            code = "\n".join(l for l in txt.splitlines() if not l.lstrip().startswith("//"))
            ma, mc = RE_ANIO.search(code), RE_CORR.search(code)
            if ma and mc:
                anio, corr = int(ma.group(1)), int(mc.group(1))
        if anio is not None and corr is not None:
            found[(anio, corr)] = {"anio": anio, "correlativo": corr, "archivo": p.name}
    return sorted(found.values(), key=lambda d: (d["anio"], d["correlativo"]))


def next_correlativo(existing: list[dict], anio: int) -> int:
    """Siguiente correlativo secuencial para el año (máximo del año + 1)."""
    nums = [d["correlativo"] for d in existing if d["anio"] == anio]
    return (max(nums) + 1) if nums else 1


def documentos_dir() -> Path:
    """Carpeta «Documentos» del sistema. Usa xdg-user-dir (en el host si estamos en Flatpak),
    con fallback a ~/Documentos o ~/Documents."""
    import shutil
    for base in (["xdg-user-dir", "DOCUMENTS"],
                 ["flatpak-spawn", "--host", "xdg-user-dir", "DOCUMENTS"]):
        if shutil.which(base[0]):
            try:
                r = subprocess.run(base, capture_output=True, text=True)
                ruta = r.stdout.strip()
                if r.returncode == 0 and ruta and ruta != str(Path.home()):
                    return Path(ruta)
            except (OSError, FileNotFoundError):
                pass
    for cand in (Path.home() / "Documentos", Path.home() / "Documents"):
        if cand.is_dir():
            return cand
    return Path.home() / "Documentos"


def docs_dir(anio: int) -> Path:
    """Carpeta donde se gestionan los documentos: <Documentos>/doctyp/<año>/.
    Todos los .typ viven aquí (creados, importados, editados, compilados)."""
    return documentos_dir() / "doctyp" / str(anio)


# ----------------------------------------------------------------------
# Registro JSON (fuente de verdad de correlativos y versiones)
# ----------------------------------------------------------------------
def registro_path(script_dir: Path) -> Path:
    return script_dir / REGISTRO


def cargar_registro(script_dir: Path) -> dict:
    """Carga settings.json; si no existe o está corrupto, estructura vacía.
    Estructura: {"local": {"correlativo_inicio": {<año>: N}}, "documentos": [...]}."""
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
    """Inicio de correlativo configurado por `reset` para el año (o None si no hay)."""
    val = registro.get("local", {}).get("correlativo_inicio", {}).get(str(anio))
    return int(val) if val is not None else None


def next_correlativo_json(registro: dict, anio: int, fallback: int = 0) -> int:
    """Siguiente correlativo del año: máximo entre el JSON, `fallback` (escaneo) y el inicio
    configurado por `reset` (si lo hay), + 1. El inicio fija el MÍNIMO del próximo número."""
    nums = [d["correlativo"] for d in registro["documentos"] if d.get("anio") == anio]
    base = max([fallback, *nums]) if (nums or fallback) else 0
    proximo = base + 1
    inicio = correlativo_inicio(registro, anio)
    if inicio is not None and inicio > proximo:
        return inicio
    return proximo


def bump_patch(version: str) -> str:
    """Incrementa el último número de una versión semántica: 1.0.0 -> 1.0.1.
    Tolera versiones de 2 partes (1.0 -> 1.0.1) normalizándolas a 3."""
    partes = version.lstrip("vV").split(".")
    nums = []
    for x in partes:
        if not x.isdigit():
            sys.exit(f"ERROR: versión '{version}' no es numérica; no se puede incrementar.")
        nums.append(int(x))
    while len(nums) < 3:
        nums.append(0)
    nums[-1] += 1
    return ".".join(str(n) for n in nums)


def _typst_cmd() -> list[str] | None:
    """Prefijo de comando para invocar typst.
    - Si `typst` está en el PATH (uso normal en el host), lo usa directo.
    - Si no, y estamos dentro de un sandbox Flatpak con `flatpak-spawn`, cae al typst del host.
    Devuelve None si no hay forma de ejecutar typst."""
    import shutil
    if shutil.which("typst"):
        return ["typst"]
    if Path("/.flatpak-info").exists() and shutil.which("flatpak-spawn"):
        return ["flatpak-spawn", "--host", "typst"]
    return None


def compilar_typ(out_file: Path) -> bool:
    """Compila un .typ a PDF (el PDF queda junto al .typ). Devuelve True si tuvo éxito.

    Usa `--root /` porque el .typ importa lib.typ por ruta absoluta (Typst trata `/` como la raíz
    del proyecto, no del sistema; con `--root /` la raíz del proyecto es la del filesystem y la
    ruta absoluta resuelve). Pasa `--font-path` a la carpeta de fuentes para fidelidad tipográfica."""
    base = _typst_cmd()
    if base is None:
        print("⚠ 'typst' no está disponible (ni en el PATH ni vía flatpak-spawn); omito la compilación.")
        return False
    cmd = base + ["compile", "--root", "/"]
    font_dir = SCRIPT_DIR / "museo-sans"
    if font_dir.is_dir():
        cmd += ["--font-path", str(font_dir)]
    cmd.append(str(out_file))
    # Ejecuta con cwd en la carpeta del .typ (siempre bajo SCRIPT_DIR, visible para el host).
    # Con flatpak-spawn --host, el cwd del sandbox (p. ej. /tmp/...) puede no existir en el host.
    try:
        subprocess.run(cmd, check=True, cwd=str(out_file.parent))
        print(f"✔ Compilado: {out_file.with_suffix('.pdf')}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠ Error de compilación: {e}")
        return False


def codigo_base(area, tipo, cat, anio, corr) -> str:
    return f"{area}-{tipo}-{cat}_{anio}-{corr:04d}"


def ty_str(s: str) -> str:
    """Escapa una cadena para un literal de Typst."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


# ----------------------------------------------------------------------
# Generación del .typ
# ----------------------------------------------------------------------
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


# ----------------------------------------------------------------------
# Subcomandos
# ----------------------------------------------------------------------
def cmd_listar(args):
    registro = cargar_registro(SCRIPT_DIR)
    docs = sorted(registro["documentos"], key=lambda d: (d.get("anio", 0), d.get("correlativo", 0)))
    anio = args.anio or datetime.date.today().year
    print(f"Registro: {registro_path(SCRIPT_DIR)}")
    if docs:
        print("\nDocumentos registrados (año · correlativo · título · ruta):")
        for d in docs:
            print(f"  {d.get('anio')} · {d.get('correlativo', 0):04d} · {d.get('titulo','')} · {d.get('ruta','')}")
    else:
        print("\nEl registro está vacío (aún no se han creado documentos).")
    inicio = correlativo_inicio(registro, anio)
    if inicio is not None:
        print(f"\nInicio de correlativo configurado para {anio}: {inicio:04d}")
    print(f"\nPróximo correlativo para {anio}: {next_correlativo_json(registro, anio):04d}")


def cmd_reset(args):
    registro = cargar_registro(SCRIPT_DIR)
    anio = args.anio or datetime.date.today().year
    inicio = args.correlativo if args.correlativo is not None else 1
    if inicio < 1:
        sys.exit("ERROR: el correlativo de inicio debe ser >= 1.")
    registro.setdefault("local", {}).setdefault("correlativo_inicio", {})[str(anio)] = inicio
    guardar_registro(SCRIPT_DIR, registro)
    print(f"✔ Inicio de correlativo para {anio} fijado en {inicio:04d}.")
    print(f"  Próximo documento: {next_correlativo_json(registro, anio):04d}")
    print(f"  Guardado en: {registro_path(SCRIPT_DIR)} (local.correlativo_inicio)")


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

    titulo = args.titulo or args.titulo_pos or input("Título del documento: ").strip()
    if not titulo:
        sys.exit("ERROR: el título es obligatorio.")

    hoy = datetime.date.today()
    fecha = args.fecha or hoy.strftime("%Y%m%d")
    if not re.fullmatch(r"\d{8}", fecha):
        sys.exit("ERROR: --fecha debe ser AAAAMMDD.")
    anio = args.anio or int(fecha[:4])

    # Carpeta de salida: <Documentos>/doctyp/<año>/ (centralizada, no el CWD).
    out_dir = docs_dir(anio)

    # Correlativo: el registro es la fuente de verdad; respaldo con un escaneo de la carpeta del
    # año para no pisar un .typ que ya exista allí.
    registro = cargar_registro(SCRIPT_DIR)
    fallback = next_correlativo(scan_existing(out_dir, exclude={args.lib}), anio) - 1
    corr = args.correlativo if args.correlativo is not None else next_correlativo_json(registro, anio, fallback)

    f = {
        "area": args.area.upper(), "tipo": tipo, "categoria": cat,
        "anio": anio, "correlativo": corr, "version": args.version, "fecha": fecha,
        "tipo_largo": args.tipo_largo or TIPOS[tipo],
        "titulo": titulo,
        "subtitulo": args.subtitulo or "SLEP Chinchorro",
        "estado": args.estado.upper(), "clasificacion": args.clasificacion.upper(),
        "autor": args.autor, "cargo": args.cargo, "correo": args.correo,
        "revisor": args.revisor, "aprobador": args.aprobador,
    }

    base = codigo_base(f["area"], tipo, cat, anio, corr)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{base}.typ"
    if out_file.exists() and not args.forzar:
        sys.exit(f"ERROR: {out_file} ya existe. Usa --forzar para sobrescribir.")

    # Import por ruta absoluta al lib.typ del proyecto: funciona desde cualquier carpeta y
    # Typst resuelve Images/ y fuentes relativo a lib.typ.
    lib_import = lib_path.as_posix()
    out_file.write_text(build_typ(f, lib_import), encoding="utf-8")

    # Registrar el documento (fuente de verdad del correlativo y de las versiones).
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

    print(f"✔ Creado: {out_file}")
    print(f"  Código base:     {base}")
    print(f"  Código completo: {base}_v{f['version']}_{fecha}")
    print(f"  Correlativo asignado: {corr:04d} (año {anio})")
    print(f"  Registrado en:   {registro_path(SCRIPT_DIR)}")


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
    doc = buscar_doc(registro, args.correlativo, anio)

    typ_path = Path(doc["ruta"])
    if not typ_path.exists():
        sys.exit(f"ERROR: el archivo registrado no existe: {typ_path}")
    texto = typ_path.read_text(encoding="utf-8")

    version_actual = doc["versiones"][-1]["version"] if doc.get("versiones") else "1.0.0"
    version_nueva = bump_patch(version_actual)
    hoy = datetime.date.today()
    fecha = hoy.strftime("%Y%m%d")
    fecha_iso = hoy.strftime("%Y-%m-%d")
    autor = doc.get("autor", "")

    # 1) Actualizar el campo `version: "..."` dentro de crear-meta.
    nuevo_texto, n = re.subn(r'(version:\s*")[^"]*(")',
                             lambda m: f'{m.group(1)}{version_nueva}{m.group(2)}',
                             texto, count=1)
    if n == 0:
        sys.exit(f"ERROR: no se encontró el campo 'version:' en {typ_path}.")

    # 2) Insertar una fila nueva al inicio del bloque #s-versiones((...)).
    fila = f'  ("v{version_nueva}", "{fecha_iso}", "{ty_str(autor)}", "{ty_str(args.mensaje)}"),\n'
    nuevo_texto, n = re.subn(r'(#s-versiones\(\(\n)',
                             lambda m: m.group(1) + fila,
                             nuevo_texto, count=1)
    if n == 0:
        sys.exit(f"ERROR: no se encontró el bloque '#s-versiones((' en {typ_path}.")

    typ_path.write_text(nuevo_texto, encoding="utf-8")

    # 3) Registrar la nueva versión en el JSON.
    ahora = datetime.datetime.now().isoformat(timespec="seconds")
    doc.setdefault("versiones", []).append({
        "version": version_nueva, "fecha": fecha, "creado": ahora, "mensaje": args.mensaje,
    })
    guardar_registro(SCRIPT_DIR, registro)

    print(f"✔ Versión actualizada: v{version_actual} → v{version_nueva}")
    print(f"  Documento: {doc['codigo_base']}")
    print(f"  Archivo:   {typ_path}")
    print(f"  Mensaje:   {args.mensaje}")


def cmd_compile(args):
    registro = cargar_registro(SCRIPT_DIR)
    anio = args.anio or datetime.date.today().year
    doc = buscar_doc(registro, args.correlativo, anio)

    typ_path = Path(doc["ruta"])
    if not typ_path.exists():
        sys.exit(f"ERROR: el archivo registrado no existe: {typ_path}")

    print(f"Compilando {doc['codigo_base']} → {typ_path.with_suffix('.pdf').name}")
    if not compilar_typ(typ_path):
        sys.exit(1)

    # El PDF queda junto al .typ (en Documentos/doctyp/); además se copia al CWD para tenerlo a mano.
    pdf = typ_path.with_suffix(".pdf")
    destino_cwd = Path.cwd() / pdf.name
    if pdf.exists() and destino_cwd.resolve() != pdf.resolve():
        import shutil
        shutil.copy2(pdf, destino_cwd)
        print(f"✔ Copiado a: {destino_cwd}")


def _host_prefix() -> list[str]:
    """Prefijo para ejecutar comandos en el host. Si estamos dentro de un sandbox Flatpak con
    flatpak-spawn, antepone `flatpak-spawn --host`; en el host normal, lista vacía."""
    import shutil
    if Path("/.flatpak-info").exists() and shutil.which("flatpak-spawn"):
        return ["flatpak-spawn", "--host"]
    return []


def _host_run_ok(argv: list[str]) -> bool:
    """Ejecuta `argv` (en el host si hace falta) y devuelve True si terminó con código 0.
    Útil para sondear existencia de comandos/apps de forma fiable: `flatpak info <id>` o
    `sh -c 'command -v <cmd>'` devuelven 0 solo si la app/comando existe. (No se mira stdout
    porque algunos comandos —p. ej. `flatpak info`— escriben en stderr o nada relevante.)"""
    try:
        r = subprocess.run(_host_prefix() + argv, capture_output=True, text=True)
        return r.returncode == 0
    except (FileNotFoundError, OSError):
        return False


# IDs Flatpak conocidos de VS Code (y derivados), en orden de preferencia.
_VSCODE_FLATPAK_IDS = ("com.visualstudio.code", "com.vscodium.codium")


def _vscode_flatpak_cmd(path: Path) -> tuple[str, list[str]] | None:
    """Si VS Code (o VSCodium) está instalado como Flatpak, devuelve (nombre, comando) para
    abrir `path` con él; si no, None. Funciona tanto desde el host como desde el sandbox."""
    pre = _host_prefix()
    for app_id in _VSCODE_FLATPAK_IDS:
        if _host_run_ok(["flatpak", "info", app_id]):
            return (f"flatpak:{app_id}", pre + ["flatpak", "run", app_id, str(path)])
    return None


def _abrir_en_editor(path: Path) -> bool:
    """Abre `path` en VS Code si está disponible; si no, en el editor favorito
    ($VISUAL/$EDITOR) o, como último recurso, con xdg-open. Devuelve True si lanzó algo."""
    import shutil
    pre = _host_prefix()
    candidatos: list[tuple[str, list[str]]] = []  # (nombre legible, comando)

    # 1) VS Code como binario en el PATH (sandbox o host).
    if shutil.which("code"):
        candidatos.append(("code", ["code", str(path)]))
    elif pre and _host_run_ok(["sh", "-c", "command -v code"]):
        candidatos.append(("code (host)", pre + ["code", str(path)]))
    # 2) VS Code / VSCodium instalado como Flatpak (caso típico en Fedora).
    vscode_fp = _vscode_flatpak_cmd(path)
    if vscode_fp:
        candidatos.append(vscode_fp)
    # 3) Editor favorito del entorno.
    for var in ("VISUAL", "EDITOR"):
        val = os.environ.get(var)
        if val:
            candidatos.append((val.split()[0], val.split() + [str(path)]))
            break
    # 4) Último recurso: la app predeterminada del sistema.
    if shutil.which("xdg-open"):
        candidatos.append(("xdg-open", ["xdg-open", str(path)]))
    elif pre and _host_run_ok(["sh", "-c", "command -v xdg-open"]):
        candidatos.append(("xdg-open (host)", pre + ["xdg-open", str(path)]))

    for nombre, cmd in candidatos:
        try:
            subprocess.Popen(cmd)
            print(f"✔ Abriendo en: {nombre}")
            return True
        except (FileNotFoundError, OSError):
            continue
    return False


def cmd_edit(args):
    registro = cargar_registro(SCRIPT_DIR)
    anio = args.anio or datetime.date.today().year
    doc = buscar_doc(registro, args.correlativo, anio)

    typ_path = Path(doc["ruta"])
    if not typ_path.exists():
        sys.exit(f"ERROR: el archivo registrado no existe: {typ_path}")

    print(f"Documento {doc['codigo_base']}: {typ_path}")
    if not _abrir_en_editor(typ_path):
        sys.exit("ERROR: no se encontró VS Code ni un editor ($VISUAL/$EDITOR/xdg-open).")


def _seleccionar(opciones: list[str], titulo: str) -> int | None:
    """Muestra un menú numerado y devuelve el índice elegido (o None si se cancela).
    El usuario teclea el número de la lista y Enter; 'q' o vacío cancela."""
    print(titulo)
    for i, etiqueta in enumerate(opciones, 1):
        print(f"  [{i}] {etiqueta}")
    while True:
        try:
            sel = input(f"Selecciona (1-{len(opciones)}, q para cancelar): ").strip()
        except EOFError:
            return None
        if sel.lower() in ("", "q"):
            return None
        if sel.isdigit() and 1 <= int(sel) <= len(opciones):
            return int(sel) - 1
        print("  Opción inválida.")


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
            continue  # ya está en el registro
        candidatos.append((p, meta, base))

    if not candidatos:
        print(f"No hay documentos válidos sin registrar en {cwd}.")
        return

    etiquetas = [f"{base}  ·  v{m['version']}  ·  {m['titulo']}  ({p.name})"
                 for p, m, base in candidatos]
    idx = _seleccionar(etiquetas, f"\nDocumentos disponibles en {cwd}:")
    if idx is None:
        print("Cancelado.")
        return
    p, meta, base = candidatos[idx]

    # Conservar el correlativo del meta; avisar si choca con otro del registro (mismo año).
    choque = next((d for d in registro["documentos"]
                   if d.get("anio") == meta["anio"]
                   and d.get("correlativo") == meta["correlativo"]), None)
    if choque:
        sys.exit(f"ERROR: el correlativo {meta['correlativo']:04d} (año {meta['anio']}) ya está "
                 f"registrado por {choque['codigo_base']}. Reasigna el correlativo en el .typ "
                 f"antes de importarlo.")

    # Mover a <Documentos>/doctyp/<año>/ con el nombre estándar <código-base>.typ (sobrescribe).
    import shutil
    dest_dir = docs_dir(meta["anio"])
    dest_dir.mkdir(parents=True, exist_ok=True)
    destino = dest_dir / f"{base}.typ"
    if destino.resolve() != p.resolve():
        shutil.move(str(p), str(destino))
        print(f"✔ Movido: {p.name} → {destino}")
    else:
        print(f"  Ya está en su carpeta: {destino}")

    # Registrar como documento, reconstruyendo el historial de versiones desde la versión actual.
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

    print(f"✔ Registrado: {base}  (v{meta['version']})")
    print(f"  Archivo:   {destino}")
    print(f"  Registro:  {registro_path(SCRIPT_DIR)}")


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generador de informes de la plantilla SLEP Chinchorro.")
    p.add_argument("--lib", default="lib.typ", help="Nombre del archivo de plantilla (junto al script). Por defecto: lib.typ")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("list", aliases=["ls"], help="Lista documentos existentes y el próximo correlativo.")
    pl.add_argument("--anio", type=int, help="Año a consultar (por defecto, el actual).")
    pl.set_defaults(func=cmd_listar)

    pn = sub.add_parser("new", aliases=["n"], help="Crea un nuevo documento .typ con correlativo secuencial.")
    pn.add_argument("titulo_pos", nargs="?", metavar="TÍTULO",
                    help="Título del documento (posicional). Equivale a --titulo / --t.")
    pn.add_argument("--titulo", "--t", dest="titulo",
                    help="Título (si falta, se toma del posicional o se pide interactivo).")
    pn.add_argument("--tipo", default="INF", help=f"Tipo: {', '.join(TIPOS)}. Por defecto: INF")
    pn.add_argument("--categoria", default="SFW", help=f"Categoría: {', '.join(sorted(CATEGORIAS))}. Por defecto: SFW")
    pn.add_argument("--subtitulo", help="Subtítulo de portada.")
    pn.add_argument("--area", default="TI", help="Área emisora. Por defecto: TI")
    pn.add_argument("--anio", type=int, help="Año (por defecto, el de --fecha o el actual).")
    pn.add_argument("--correlativo", "--code", type=int, dest="correlativo",
                    help="Forzar correlativo manualmente (por defecto: secuencial automático).")
    pn.add_argument("--version", default="1.0.0", help="Versión inicial (semántica). Por defecto: 1.0.0")
    pn.add_argument("--fecha", help="Fecha AAAAMMDD. Por defecto: hoy.")
    pn.add_argument("--tipo-largo", dest="tipo_largo", help="Rótulo de portada (por defecto, según --tipo).")
    pn.add_argument("--estado", default="BORRADOR", help="BORRADOR | EN REVISIÓN | APROBADO")
    pn.add_argument("--clasificacion", default="INTERNO", help="PÚBLICO | INTERNO | RESERVADO | CONFIDENCIAL")
    pn.add_argument("--autor", default="Andres Cubillos Salazar")
    pn.add_argument("--cargo", default="Tecnico de Soporte Informático")
    pn.add_argument("--correo", default="andres.cubillos@epchinchorro.cl")
    pn.add_argument("--revisor", help="Revisor (si se omite, usa el default de la plantilla).")
    pn.add_argument("--aprobador", help="Aprobador (si se omite, usa el default de la plantilla).")
    pn.add_argument("--forzar", action="store_true", help="Sobrescribir si el archivo ya existe.")
    pn.set_defaults(func=cmd_nuevo)

    ps = sub.add_parser("save", aliases=["s"], help="Sube la versión de un documento (bump del patch) y registra el cambio.")
    ps.add_argument("correlativo", type=int, metavar="CORRELATIVO",
                    help="Número correlativo del documento a versionar (p. ej. 1 o 0001).")
    ps.add_argument("--mensaje", "--m", dest="mensaje", required=True,
                    help="Mensaje descriptivo de la nueva versión.")
    ps.add_argument("--anio", type=int, help="Año del documento (por defecto, el actual).")
    ps.set_defaults(func=cmd_save)

    pa = sub.add_parser("add", aliases=["a"], help="Importa al registro un documento existente del directorio actual.")
    pa.set_defaults(func=cmd_add)

    pc = sub.add_parser("compile", aliases=["c"], help="Compila un documento a PDF (queda junto al .typ).")
    pc.add_argument("correlativo", type=int, metavar="CORRELATIVO",
                    help="Número correlativo del documento a compilar (p. ej. 1 o 0001).")
    pc.add_argument("--anio", type=int, help="Año del documento (por defecto, el actual).")
    pc.set_defaults(func=cmd_compile)

    pe = sub.add_parser("edit", aliases=["code", "e"],
                        help="Abre el documento en VS Code o en el editor favorito.")
    pe.add_argument("correlativo", type=int, metavar="CORRELATIVO",
                    help="Número correlativo del documento a abrir (p. ej. 1 o 0001).")
    pe.add_argument("--anio", type=int, help="Año del documento (por defecto, el actual).")
    pe.set_defaults(func=cmd_edit)

    pr = sub.add_parser("reset", help="Fija dónde empieza el correlativo del año (en settings.json).")
    pr.add_argument("correlativo", type=int, nargs="?", metavar="CORRELATIVO",
                    help="Número de inicio (por defecto: 1).")
    pr.add_argument("--anio", type=int, help="Año a configurar (por defecto, el actual).")
    pr.set_defaults(func=cmd_reset)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
