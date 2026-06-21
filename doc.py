#!/usr/bin/env python3
"""
doc.py — Generador de informes para la plantilla Typst del SLEP Chinchorro (Unidad TI).

Crea un archivo .typ con la nomenclatura oficial (AREA-TIPO-CAT_AAAA-NNNN) y la estructura
canónica, asignando el correlativo de forma SECUENCIAL automática (global anual: el siguiente
número = máximo correlativo existente para ese año + 1).

Uso rápido:
    python doc.py nuevo --tipo INF --categoria SEG --titulo "Auditoría de respaldos" \\
                           --autor "Nombre Apellido" --cargo "Ingeniero" --correo "x@epchinchorro.cl"
    python doc.py listar

Sin --titulo, lo pide de forma interactiva. No requiere paquetes externos (solo stdlib).
python docctl.py nuevo --tipo INF --categoria SEG \
  --titulo "Auditoría de respaldos del Centro de Datos" \
  --autor "Roberto I. Vargas Vargas" --cargo "Técnico" --correo "x@epchinchorro.cl"
"""
from __future__ import annotations
import argparse, os, re, sys, subprocess, datetime
from pathlib import Path

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


def codigo_base(area, tipo, cat, anio, corr) -> str:
    return f"{area}-{tipo}-{cat}_{anio}-{corr:04d}"


def ty_str(s: str) -> str:
    """Escapa una cadena para un literal de Typst."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


# ----------------------------------------------------------------------
# Generación del .typ
# ----------------------------------------------------------------------
def build_typ(f: dict, rel_lib: str) -> str:
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

    return f'''// {base}  ·  generado por doc.py
#import "{rel_lib}": *

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
    root = find_root(Path(args.root), args.lib)
    existing = scan_existing(root, exclude={args.lib})
    anio = args.anio or datetime.date.today().year
    print(f"Raíz del proyecto: {root}")
    if existing:
        print("\nDocumentos detectados (año · correlativo · archivo):")
        for d in existing:
            print(f"  {d['anio']} · {d['correlativo']:04d} · {d['archivo']}")
    else:
        print("\nNo se detectaron documentos con nomenclatura.")
    print(f"\nPróximo correlativo para {anio}: {next_correlativo(existing, anio):04d}")


def cmd_nuevo(args):
    root = find_root(Path(args.root), args.lib)
    lib_path = root / args.lib
    if not lib_path.exists():
        sys.exit(f"ERROR: no se encontró {args.lib} en {root}. Usa --root/--lib.")

    tipo = args.tipo.upper()
    cat = args.categoria.upper()
    if tipo not in TIPOS:
        sys.exit(f"ERROR: tipo '{tipo}' inválido. Válidos: {', '.join(TIPOS)}")
    if cat not in CATEGORIAS:
        sys.exit(f"ERROR: categoría '{cat}' inválida. Válidas: {', '.join(sorted(CATEGORIAS))}")

    titulo = args.titulo or input("Título del documento: ").strip()
    if not titulo:
        sys.exit("ERROR: el título es obligatorio.")

    hoy = datetime.date.today()
    fecha = args.fecha or hoy.strftime("%Y%m%d")
    if not re.fullmatch(r"\d{8}", fecha):
        sys.exit("ERROR: --fecha debe ser AAAAMMDD.")
    anio = args.anio or int(fecha[:4])

    existing = scan_existing(root, exclude={args.lib})
    corr = args.correlativo if args.correlativo is not None else next_correlativo(existing, anio)

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
    out_dir = (root / args.dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{base}.typ"
    if out_file.exists() and not args.forzar:
        sys.exit(f"ERROR: {out_file} ya existe. Usa --forzar para sobrescribir.")

    rel_lib = os.path.relpath(lib_path, out_dir).replace(os.sep, "/")
    out_file.write_text(build_typ(f, rel_lib), encoding="utf-8")

    print(f"✔ Creado: {out_file}")
    print(f"  Código base:     {base}")
    print(f"  Código completo: {base}_v{f['version']}_{fecha}")
    print(f"  Correlativo asignado: {corr:04d} (año {anio})")

    if args.compilar:
        try:
            subprocess.run(["typst", "compile", str(out_file)], check=True)
            print(f"✔ Compilado: {out_file.with_suffix('.pdf')}")
        except FileNotFoundError:
            print("⚠ 'typst' no está instalado; omito la compilación.")
        except subprocess.CalledProcessError as e:
            print(f"⚠ Error de compilación: {e}")


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Generador de informes de la plantilla SLEP Chinchorro.")
    p.add_argument("--root", default=".", help="Raíz del proyecto (donde está lib.typ). Por defecto: .")
    p.add_argument("--lib", default="lib.typ", help="Nombre del archivo de plantilla. Por defecto: lib.typ")
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("listar", help="Lista documentos existentes y el próximo correlativo.")
    pl.add_argument("--anio", type=int, help="Año a consultar (por defecto, el actual).")
    pl.set_defaults(func=cmd_listar)

    pn = sub.add_parser("nuevo", help="Crea un nuevo documento .typ con correlativo secuencial.")
    pn.add_argument("--tipo", required=True, help=f"Tipo: {', '.join(TIPOS)}")
    pn.add_argument("--categoria", required=True, help=f"Categoría: {', '.join(sorted(CATEGORIAS))}")
    pn.add_argument("--titulo", help="Título (si falta, se pide de forma interactiva).")
    pn.add_argument("--subtitulo", help="Subtítulo de portada.")
    pn.add_argument("--area", default="TI", help="Área emisora. Por defecto: TI")
    pn.add_argument("--anio", type=int, help="Año (por defecto, el de --fecha o el actual).")
    pn.add_argument("--correlativo", type=int, help="Forzar correlativo (por defecto: secuencial automático).")
    pn.add_argument("--version", default="1.0", help="Versión. Por defecto: 1.0")
    pn.add_argument("--fecha", help="Fecha AAAAMMDD. Por defecto: hoy.")
    pn.add_argument("--tipo-largo", dest="tipo_largo", help="Rótulo de portada (por defecto, según --tipo).")
    pn.add_argument("--estado", default="BORRADOR", help="BORRADOR | EN REVISIÓN | APROBADO")
    pn.add_argument("--clasificacion", default="INTERNO", help="PÚBLICO | INTERNO | RESERVADO | CONFIDENCIAL")
    pn.add_argument("--autor", default="Nombre Apellido")
    pn.add_argument("--cargo", default="Cargo")
    pn.add_argument("--correo", default="informatica@epchinchorro.cl")
    pn.add_argument("--revisor", help="Revisor (si se omite, usa el default de la plantilla).")
    pn.add_argument("--aprobador", help="Aprobador (si se omite, usa el default de la plantilla).")
    pn.add_argument("--dir", default=".", help="Subdirectorio de salida (relativo a la raíz). Por defecto: .")
    pn.add_argument("--compilar", action="store_true", help="Compilar a PDF tras crear (requiere typst).")
    pn.add_argument("--forzar", action="store_true", help="Sobrescribir si el archivo ya existe.")
    pn.set_defaults(func=cmd_nuevo)
    return p


def main():
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
