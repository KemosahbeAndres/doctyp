#!/usr/bin/env python3
"""
doctyp — Generador de informes para la plantilla Typst del SLEP Chinchorro (Unidad TI).

Comando global: se instala como `doctyp` (symlink en ~/.local/bin) y se invoca desde cualquier
carpeta. El documento .typ se crea EN EL DIRECTORIO ACTUAL (donde se llama el comando), mientras
que la plantilla (lib.typ), los logos (Images/) y el registro de correlativos viven junto al
script (SCRIPT_DIR).

Crea un archivo .typ con la nomenclatura oficial (AREA-TIPO-CAT_AAAA-NNNN) y la estructura
canónica, asignando el correlativo de forma SECUENCIAL automática (global anual). La fuente de
verdad del correlativo y de las versiones es `doctyp-registro.json`, junto al script.

Uso rápido:
    doctyp nuevo "Auditoría de respaldos"               # título posicional + defaults de autoría
    doctyp nuevo --t "Manual de red" --tipo MAN --categoria RED
    doctyp save 1 --m "Corrige sección de alcance"      # sube versión (1.0.0 -> 1.0.1) del doc 0001
    doctyp listar

El título acepta posicional, --titulo o --t. Sin título, se pide de forma interactiva.
No requiere paquetes externos (solo stdlib).
"""
from __future__ import annotations
import argparse, json, re, sys, subprocess, datetime
from pathlib import Path

# Ubicación real del script (resuelve el symlink). Aquí viven lib.typ, Images/ y el registro.
SCRIPT_DIR = Path(__file__).resolve().parent
REGISTRO = "doctyp-registro.json"

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


# ----------------------------------------------------------------------
# Registro JSON (fuente de verdad de correlativos y versiones)
# ----------------------------------------------------------------------
def registro_path(script_dir: Path) -> Path:
    return script_dir / REGISTRO


def cargar_registro(script_dir: Path) -> dict:
    """Carga doctyp-registro.json; si no existe o está corrupto, estructura vacía."""
    p = registro_path(script_dir)
    if not p.exists():
        return {"documentos": []}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        sys.exit(f"ERROR: no se pudo leer el registro {p}: {e}")
    data.setdefault("documentos", [])
    return data


def guardar_registro(script_dir: Path, data: dict) -> None:
    registro_path(script_dir).write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def next_correlativo_json(registro: dict, anio: int, fallback: int = 0) -> int:
    """Siguiente correlativo del año: máximo entre el JSON y `fallback` (escaneo), + 1."""
    nums = [d["correlativo"] for d in registro["documentos"] if d.get("anio") == anio]
    base = max([fallback, *nums]) if (nums or fallback) else 0
    return base + 1


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


def compilar_typ(out_file: Path) -> None:
    """Compila un .typ a PDF con el binario typst (si está disponible)."""
    try:
        subprocess.run(["typst", "compile", str(out_file)], check=True)
        print(f"✔ Compilado: {out_file.with_suffix('.pdf')}")
    except FileNotFoundError:
        print("⚠ 'typst' no está instalado; omito la compilación.")
    except subprocess.CalledProcessError as e:
        print(f"⚠ Error de compilación: {e}")


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
    print(f"\nPróximo correlativo para {anio}: {next_correlativo_json(registro, anio):04d}")


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

    # Carpeta de salida: el directorio actual (CWD), o --dir relativo a él.
    out_dir = (Path.cwd() / args.dir).resolve()

    # Correlativo: el JSON es la fuente de verdad; respaldo con un escaneo del CWD para no
    # pisar un .typ que ya exista en la carpeta con el mismo año.
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

    if args.compilar:
        compilar_typ(out_file)


def cmd_save(args):
    registro = cargar_registro(SCRIPT_DIR)
    anio = args.anio or datetime.date.today().year
    docs = [d for d in registro["documentos"]
            if d.get("correlativo") == args.correlativo and d.get("anio") == anio]
    if not docs:
        sys.exit(f"ERROR: no hay documento con correlativo {args.correlativo:04d} (año {anio}) "
                 f"en el registro. Revisa con 'doctyp listar'.")
    if len(docs) > 1:
        sys.exit(f"ERROR: hay {len(docs)} documentos con correlativo {args.correlativo:04d} "
                 f"(año {anio}). Resuelve el duplicado en {registro_path(SCRIPT_DIR)}.")
    doc = docs[0]

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

    if args.compilar:
        compilar_typ(typ_path)


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generador de informes de la plantilla SLEP Chinchorro.")
    p.add_argument("--lib", default="lib.typ", help="Nombre del archivo de plantilla (junto al script). Por defecto: lib.typ")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("listar", help="Lista documentos existentes y el próximo correlativo.")
    pl.add_argument("--anio", type=int, help="Año a consultar (por defecto, el actual).")
    pl.set_defaults(func=cmd_listar)

    pn = sub.add_parser("nuevo", help="Crea un nuevo documento .typ con correlativo secuencial.")
    pn.add_argument("titulo_pos", nargs="?", metavar="TÍTULO",
                    help="Título del documento (posicional). Equivale a --titulo / --t.")
    pn.add_argument("--titulo", "--t", dest="titulo",
                    help="Título (si falta, se toma del posicional o se pide interactivo).")
    pn.add_argument("--tipo", default="INF", help=f"Tipo: {', '.join(TIPOS)}. Por defecto: INF")
    pn.add_argument("--categoria", default="SFW", help=f"Categoría: {', '.join(sorted(CATEGORIAS))}. Por defecto: SFW")
    pn.add_argument("--subtitulo", help="Subtítulo de portada.")
    pn.add_argument("--area", default="TI", help="Área emisora. Por defecto: TI")
    pn.add_argument("--anio", type=int, help="Año (por defecto, el de --fecha o el actual).")
    pn.add_argument("--correlativo", type=int, help="Forzar correlativo (por defecto: secuencial automático).")
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
    pn.add_argument("--dir", default=".", help="Subdirectorio de salida (relativo al directorio actual). Por defecto: .")
    pn.add_argument("--compilar", action="store_true", help="Compilar a PDF tras crear (requiere typst).")
    pn.add_argument("--forzar", action="store_true", help="Sobrescribir si el archivo ya existe.")
    pn.set_defaults(func=cmd_nuevo)

    ps = sub.add_parser("save", help="Sube la versión de un documento (bump del patch) y registra el cambio.")
    ps.add_argument("correlativo", type=int, metavar="CORRELATIVO",
                    help="Número correlativo del documento a versionar (p. ej. 1 o 0001).")
    ps.add_argument("--mensaje", "--m", dest="mensaje", required=True,
                    help="Mensaje descriptivo de la nueva versión.")
    ps.add_argument("--anio", type=int, help="Año del documento (por defecto, el actual).")
    ps.add_argument("--compilar", action="store_true", help="Compilar a PDF tras versionar (requiere typst).")
    ps.set_defaults(func=cmd_save)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
