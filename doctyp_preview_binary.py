#!/usr/bin/env python3
"""
doctyp_preview_binary — Plan 15 F1: localización y verificación del binario `tinymist`.

`tinymist` se usa ÚNICAMENTE como subproceso servidor de preview (`tinymist preview`), nunca
como LSP ni herramienta de edición (ver `plan 15.md` §0). Este módulo solo resuelve *dónde* está
el binario y si su versión alcanza el mínimo soportado; el lanzamiento del subproceso vive en
`doctyp_preview_server.py` (F2).

Orden de resolución (igual criterio que el resto de `doctyp`: config local antes que PATH):
  1. `settings.json -> local.preview_tinymist_path` (mismo mecanismo de config ya usado por
     `local.org_activa`/`local.autor_activo`, ver doctyp.py cargar_settings/guardar_settings).
  2. `shutil.which("tinymist")`.

No descarga binarios automáticamente (decisión explícita del plan: menor superficie de fallo y
de seguridad). Si no se encuentra o la versión es insuficiente, el llamador (doctyp_web.py)
degrada a modo legacy (preview typst.ts existente) con un aviso -- ver F8.
"""
from __future__ import annotations
import re
import shutil
import subprocess
from pathlib import Path

import doctyp as core

# Versión mínima verificada empíricamente en la Etapa "Plan 15 F0" (ver plan15_notas.md): el
# protocolo de control/data plane confirmado ahí corresponde a esta versión exacta. Versiones
# anteriores no se probaron; versiones posteriores deberían mantener el protocolo (heredado de
# typst-preview desde hace varias versiones) pero no hay garantía sin volver a verificar.
MIN_TINYMIST_VERSION = (0, 15, 2)

_VERSION_RE = re.compile(r"(\d+)\.(\d+)\.(\d+)")


def _parsear_version(salida: str) -> tuple[int, int, int] | None:
    """Extrae (mayor, menor, parche) de la salida de `tinymist -V` (formato: 'tinymist X.Y.Z')."""
    m = _VERSION_RE.search(salida)
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), int(m.group(3)))


def find_tinymist() -> Path | None:
    """Resuelve la ruta al binario tinymist, o None si no se encuentra por ningún medio."""
    settings = core.cargar_settings()
    ruta_config = settings.get("local", {}).get("preview_tinymist_path")
    if ruta_config:
        p = Path(ruta_config).expanduser()
        if p.is_file():
            return p
        core._warn(f"local.preview_tinymist_path apunta a '{p}', que no existe. Se ignora.")

    encontrado = shutil.which("tinymist")
    return Path(encontrado) if encontrado else None


def check_version(path: Path) -> tuple[int, int, int] | None:
    """Ejecuta `<path> -V` y devuelve la versión parseada, o None si falla/no se puede parsear."""
    try:
        resultado = subprocess.run(
            [str(path), "-V"], capture_output=True, text=True, timeout=5, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if resultado.returncode != 0:
        return None
    return _parsear_version(resultado.stdout.strip() or resultado.stderr.strip())


def version_str(v: tuple[int, int, int]) -> str:
    return f"{v[0]}.{v[1]}.{v[2]}"


def resolver_tinymist_utilizable() -> tuple[Path, tuple[int, int, int]] | None:
    """Punto de entrada único para doctyp_preview_server.py: encuentra el binario Y valida que
    su versión sea suficiente. Devuelve (ruta, version) o None (registra el motivo con _warn)."""
    ruta = find_tinymist()
    if ruta is None:
        core._warn(
            "No se encontró el binario 'tinymist' (ni en local.preview_tinymist_path ni en "
            "PATH). La vista previa usará el motor typst.ts existente (modo legacy). Para "
            "habilitar la vista previa con clic↔cursor, instala tinymist desde "
            "https://github.com/Myriad-Dreamin/tinymist/releases y fija su ruta con "
            "'local.preview_tinymist_path' en settings.json, o agrégalo al PATH."
        )
        return None

    version = check_version(ruta)
    if version is None:
        core._warn(f"No se pudo determinar la versión de tinymist en '{ruta}'. Se usa modo legacy.")
        return None

    if version < MIN_TINYMIST_VERSION:
        core._warn(
            f"tinymist {version_str(version)} en '{ruta}' es anterior a la versión mínima "
            f"soportada ({version_str(MIN_TINYMIST_VERSION)}). Se usa modo legacy. Actualiza "
            "desde https://github.com/Myriad-Dreamin/tinymist/releases."
        )
        return None

    return ruta, version
