# CLAUDE.md — Plantilla de Informes Técnicos · SLEP Chinchorro (Unidad TI)

> Guía para **Claude Code** en este repositorio. Objetivo: que el usuario y Claude
> **redacten informes técnicos juntos** sobre la plantilla `lib.typ`, que reproduce el
> estándar **TI-MAN-GOB_2026-0020 v2.0** (Manual de Normas Gráficas SLEP 2026).
> Lee este archivo completo antes de crear o editar documentos.

---

## 0. Cómo debe comportarse Claude en este repo

- **`lib.typ` es la plantilla (presentación). NO se edita su estilo** (colores, tipografía,
  portada, márgenes) salvo orden explícita del usuario. Regla del manual §11.2.
- **Cada informe es un archivo `.typ` propio** que importa `lib.typ` y solo aporta `meta` + prosa.
- **El correlativo NUNCA se inventa:** es secuencial automático. Genera los documentos con
  `doctyp` (§3) o, si creas el archivo a mano, calcula el siguiente con `doctyp listar`.
  La fuente de verdad del correlativo y de las versiones es `doctyp-registro.json` (junto al script).
- Tras cada cambio, **compila y verifica** (§7). No afirmar que algo funciona sin compilarlo.
- Diffs mínimos; una sola fuente de verdad (todo dato en `meta`); sin hardcodear estilos.

---

## 1. Estructura del proyecto

```
.
├── lib.typ                # PLANTILLA (motor): estilos, portada/contraportada, componentes, atajos.
├── doctyp.py              # CLI que crea informes (comando global `doctyp`; symlink en ~/.local/bin).
├── doctyp-registro.json   # Registro de correlativos y versiones (fuente de verdad; lo gestiona el script).
├── main.typ               # Informe de ejemplo (referencia). No es la plantilla.
├── CLAUDE.md              # Este archivo.
└── Images/
    ├── logoslepch.png   # Logo color SLEP (portada + header)   ← meta.logos.slep
    └── isologo_2.png    # Marca pequeña (reservado)            ← meta.logos.isologo
```

Cada informe se nombra con su **código base**: `TI-<TIPO>-<CAT>_<AAAA>-<NNNN>.typ`.

---

## 2. Crear un informe — dos vías

**Vía A (recomendada): generador `doctyp`** — asigna el correlativo y escribe la estructura.
El documento se crea **en el directorio actual** (donde se llama el comando). Con los defaults
de autoría (Andrés Cubillos), tipo `INF` y categoría `SFW` basta con el título:

```bash
doctyp nuevo "Auditoría de respaldos del Centro de Datos"   # título posicional
doctyp nuevo --t "Manual de red" --tipo MAN --categoria RED  # o con --t / --titulo
```

Para subir la versión de un documento ya creado (bump del patch, `1.0.0 → 1.0.1`), actualiza el
`.typ` y añade una fila a la tabla de control de versiones:

```bash
doctyp save 1 --m "Corrige la sección de alcance"   # 1 = correlativo del documento
```

**Vía B (manual):** crea el `.typ` con este esqueleto (también está embebido en la cabecera de
`lib.typ`). Antes, obtén el correlativo con `doctyp listar`.

```typst
#import "lib.typ": *
#let meta = crear-meta((
  area: "TI", tipo: "INF", categoria: "SEG",
  correlativo: 23, version: "1.0", fecha-codigo: "20260601",
  titulo: "Título", subtitulo: "SLEP Chinchorro",
  estado: "BORRADOR", clasificacion: "INTERNO",
  autor: "Nombre Apellido", cargo-autor: "Cargo", correo-autor: "x@epchinchorro.cl",
))
#show: report.with(meta: meta)

#s-ficha(meta, rama-git: "doc/TI-INF-SEG-2026-0023")
#s-versiones(( ("v1.0", "2026-06-01", "Nombre Apellido", "Versión inicial."), ))
#s-distribucion(( ("Equipo TI", "Operación documental", "Receptor principal"), ))
#s-indice()

= Resumen ejecutivo
...prosa...
= Anexos
== Anexo B. Firmas
#firmas-estandar(meta)
```

La portada y la contraportada se generan solas. No escribas `= Portada` ni `= Contraportada`.

---

## 3. Generador `doctyp`  (Claude Code puede ejecutarlo)

Script en Python estándar (sin dependencias), instalado como **comando global** `doctyp`
(symlink en `~/.local/bin` → `doctyp.py`). Funciona desde cualquier carpeta:

- **Salida en el directorio actual (CWD):** el `.typ` se crea donde se invoca el comando.
- **Plantilla y assets junto al script:** `lib.typ`, `Images/` y el registro viven en el
  directorio real del script (`SCRIPT_DIR`); el `.typ` generado importa `lib.typ` por **ruta
  absoluta**, así Typst resuelve los logos y las fuentes desde cualquier carpeta.
- **Registro central:** `doctyp-registro.json` (en `SCRIPT_DIR`) es la **fuente de verdad** de
  correlativos y versiones de todo el sistema.

### Correlativo secuencial
- **Global anual:** el próximo número = (máximo correlativo del año en el registro JSON) + 1.
- El JSON manda; como respaldo se escanea el CWD para no pisar un `.typ` ya presente con el
  mismo año. Nunca reutiliza un número ya usado.

### Subcomandos
```bash
doctyp listar [--anio 2026]                  # lista documentos del registro y el próximo correlativo
doctyp nuevo  "Título" [opciones]            # crea (tipo INF, categoría SFW por defecto)
doctyp save   <correlativo> --m "mensaje"    # sube versión (patch) y registra el cambio
```
El título de `nuevo` admite tres formas: posicional (`doctyp nuevo "Título"`), `--t "Título"`
o `--titulo "Título"`.

### Opciones de `nuevo`
| Flag | Por defecto | Notas |
|---|---|---|
| `--tipo` | `INF` | INF, MAN, POL, PRO, PLA, EVL, ETT, ACT |
| `--categoria` | `SFW` | SEG, RED, HRW, SFW, DAT, SRV, PRV, GOB, USR, CPD, BCK, PRY, CAP |
| `título` (posicional) / `--titulo` / `--t` | (se pide interactivo) | Título del documento |
| `--subtitulo` | `SLEP Chinchorro` | |
| `--area` | `TI` | |
| `--correlativo` | **secuencial automático** | solo para forzar un número |
| `--version` | `1.0.0` | versión inicial (semántica) |
| `--fecha` | hoy (AAAAMMDD) | |
| `--anio` | el de `--fecha` | |
| `--estado` | `BORRADOR` | BORRADOR \| EN REVISIÓN \| APROBADO |
| `--clasificacion` | `INTERNO` | PÚBLICO \| INTERNO \| RESERVADO \| CONFIDENCIAL |
| `--autor` | `Andres Cubillos Salazar` | autoría |
| `--cargo` | `Tecnico de Soporte Informático` | autoría |
| `--correo` | `andres.cubillos@epchinchorro.cl` | autoría |
| `--revisor` `--aprobador` | defaults de la plantilla | |
| `--dir` | `.` | subdirectorio de salida (relativo al directorio actual) |
| `--compilar` | — | compila a PDF tras crear (requiere `typst`) |
| `--forzar` | — | sobrescribe si el archivo existe |

El archivo se nombra `<código-base>.typ` y la salida indica el código completo asignado.

### Opciones de `save`
Sube la versión de un documento ya registrado: incrementa el **patch** (`1.0.0 → 1.0.1`),
actualiza el campo `version:` del `.typ` y **antepone una fila** a la tabla de control de
versiones (fecha = hoy, autor = el del registro, descripción = el mensaje).

| Flag | Notas |
|---|---|
| `<correlativo>` (oblig.) | Número del documento a versionar (p. ej. `1` o `0001`). Se localiza por el registro JSON. |
| `--m` / `--mensaje` (oblig.) | Descripción de la nueva versión. |
| `--anio` | Año del documento (por defecto, el actual). |
| `--compilar` | Compila a PDF tras versionar. |

### Cómo lo usa Claude Code
1. Ejecuta `doctyp listar` para conocer el próximo correlativo (informativo).
2. Ejecuta `doctyp nuevo "..."` (ajusta `--tipo`/`--categoria`/autoría si hace falta).
3. Abre el `.typ` creado y **rellena las secciones marcadas `// TODO`** con el contenido del usuario.
4. Compila (§7) e itera.

> El script localiza `lib.typ` junto a sí mismo (resolviendo el symlink). No usa `--root`.
> Instalación: `ln -sf "$(pwd)/doctyp.py" ~/.local/bin/doctyp` (requiere `~/.local/bin` en el PATH).

---

## 4. Metadatos (`meta`) — construir SIEMPRE con `crear-meta(...)`

Declara solo lo que cambia; el resto sale de los defaults de la plantilla.

| Clave | Ejemplo | Para qué |
|---|---|---|
| `area` `tipo` `categoria` | `"TI"` `"INF"` `"SEG"` | Código documental (§6) |
| `anio` `correlativo` `version` `fecha-codigo` | `2026` `23` `"1.0"` `"20260601"` | Código documental |
| `tipo-largo` | `"Informe Técnico"` | Rótulo superior de la portada |
| `titulo` `subtitulo` | — | Portada |
| `estado` | `BORRADOR` \| `EN REVISIÓN` \| `APROBADO` | Badge (verde si aprobado) |
| `clasificacion` | `PÚBLICO` \| `INTERNO` \| `RESERVADO` \| `CONFIDENCIAL` | Badge + contraportada |
| `autor` `cargo-autor` `correo-autor` | — | Ficha + firmas (Elaborado) |
| `revisor` `cargo-revisor` | — | Ficha + firmas (Revisado) |
| `aprobador` `cargo-aprob` | — | Ficha + firmas (Aprobado) |
| `contraportada` | `true` (def.) | `false` para omitirla |

Ya vienen por defecto (no repetir salvo cambio): `unidad`, `subdireccion`, `institucion`,
`comunas`, `correo-inst`, `sitio-inst`, `logos.slep`, `logos.isologo`.

---

## 5. Estructura canónica del informe (orden obligatorio, manual §11.1)

| # | Sección | Cómo se genera |
|---|---|---|
| 1 | Portada | automática (`report`) |
| 2 | Ficha de control documental | `#s-ficha(meta, rama-git: ...)` |
| 3 | Control de versiones | `#s-versiones(filas)` |
| 4 | Distribución | `#s-distribucion(filas)` |
| 5 | Tabla de contenido | `#s-indice()` |
| 6 | Resumen ejecutivo | `= Resumen ejecutivo` + prosa |
| 7 | Antecedentes y motivación | `= ...` + `== Contexto institucional` / `== Problema o necesidad identificada` |
| 8 | Objetivo | `= ...` + `== Objetivo general` / `== Objetivos específicos` |
| 9 | Alcance | `= ...` + `== Dentro del alcance` / `== Fuera del alcance` |
| 10 | Marco normativo y referencial | `= ...` + `== Normativa legal aplicable` / `== Estándares técnicos aplicables` |
| 11 | Metodología | `= ...` |
| 12 | Desarrollo técnico | `= ...` (cuerpo principal) |
| 13 | Análisis de impacto | `= ...` + `== Confidencialidad` / `== Integridad` / `== Disponibilidad` |
| 14 | Conclusiones | `= ...` |
| 15 | Recomendaciones | `= ...` + `#tabla-prioridad(...)` |
| 16 | Glosario y acrónimos | `= ...` + `#tabla(...)` |
| 17 | Referencias | `= ...` |
| 18 | Anexos | `= Anexos` + `== Anexo X. ...` (incl. `== Anexo B. Firmas` → `#firmas-estandar(meta)`) |
| 19 | Contraportada | automática (`meta.contraportada`) |

Los encabezados se numeran solos (`1`, `1.1`). `doctyp nuevo` ya escribe todo este esqueleto.

---

## 6. Nomenclatura documental

Patrón: `AREA-TIPO-CAT_AAAA-NNNN_vX.Y_AAAAMMDD` → p. ej. `TI-INF-SEG_2026-0023_v1.0_20260601`.

- **`NNNN` es secuencial global anual** (4 dígitos), asignado por `doctyp` (§3). No lo inventes.
- `codigo-base(meta)` = `TI-INF-SEG_2026-0023` · `codigo-completo(meta)` = con versión y fecha.
  Se imprimen solos (portada, ficha, footer, contraportada). No los escribas a mano.
- **Tipos:** INF Informe · MAN Manual · POL Política · PRO Procedimiento · PLA Plan · EVL Evaluación · ETT Esp. Técnica · ACT Acta.
- **Categorías (3 letras):** SEG, RED, HRW, SFW, DAT, SRV, PRV, GOB, USR, CPD, BCK, PRY, CAP.

---

## 7. Compilar  (hazlo tras cada edición)

```bash
typst compile TI-INF-SEG_2026-0023.typ      # → .pdf
typst watch  TI-INF-SEG_2026-0023.typ       # recompila al guardar (modo redacción)
typst compile --font-path ./fonts <archivo>.typ
```

- Requiere **Typst ≥ 0.12** y, para fidelidad tipográfica, la fuente **Museo Sans**
  (si falta, cae a Liberation Sans; el layout no se rompe).
- Coloca los logos reales en `Images/` antes de la versión final.
- `doctyp nuevo --compilar` compila automáticamente al crear.
- Sin binario, valida con las bindings de Python:
  `pip install typst --break-system-packages && python3 -c "import typst; typst.compile('<archivo>.typ', output='out.pdf')"`

---

## 8. API de la plantilla (todo exportado por `lib.typ`)

**Estructura / secciones**
- `crear-meta(dict)` — construye `meta` (defaults + overrides). Úsalo siempre.
- `report` — `#show: report.with(meta:)`. Estilos + portada + contraportada.
- `s-ficha(meta, rama-git: none)` · `s-versiones(filas)` · `s-distribucion(filas)` · `s-indice()`.
- `firmas-estandar(meta)` — firmas tripartitas desde `meta`.

**Componentes**
- `tabla(columns:, headers, rows)` — tabla cebra con cabecera marino.
- `tabla-kv(filas)` — 2 columnas etiqueta/valor (filas = lista de `(clave, valor)`).
- `tabla-prioridad(filas)` — recomendaciones; filas = `(n, recomendación, "Alta"|"Media"|"Baja", responsable)`.
- `ficha-control(meta, rama-git:)` — tabla de la ficha (la usa `s-ficha`).
- `aviso(tipo:, titulo:, cuerpo)` — `tipo` ∈ `"info"` `"advertencia"` `"riesgo"` `"recomendacion"`.
- `firmas(lista de (rol, nombre, cargo))` — firmas personalizadas.
- `indice()` · `badge-estado(s)` · `badge-clasificacion(c)` · `codigo-base/completo(meta)`.

**Tokens de color** (usos puntuales, no para redefinir el estilo): `marino`, `azul-acento`,
`rojo-acento`, `verde`, `gris-texto`, `gris-borde`, `fondo-label`, `fondo-cebra`, `prio`.

---

## 9. Flujo de co-redacción con el usuario

Cuando el usuario diga “redactemos un informe sobre X”:

1. **Identifica `--tipo` y `--categoria`** (§6) y confirma autor/cargo/correo si no los da.
2. **Crea el archivo con el generador** (asigna el correlativo secuencial y lo deja en el CWD):
   `doctyp nuevo "<título>"` (ajusta `--tipo`/`--categoria`/autoría solo si difieren de los defaults).
3. **Rellena las secciones `// TODO`** del archivo con el contenido del usuario, siguiendo la
   estructura canónica (§5). Usa `aviso(...)` para estados/riesgos y `tabla(...)`/`tabla-prioridad(...)` para datos.
4. **Compila** (§7) y revisa el PDF; corrige e **itera** sección por sección.
5. Al cerrar una versión: `doctyp save <correlativo> --m "<qué cambió>"` sube el patch, actualiza
   el `version:` del `.typ` y añade la fila a `s-versiones` automáticamente. Reporta el `codigo-completo`.

Sugerencia: deja `typst watch <archivo>.typ` corriendo durante la redacción.

---

## 10. Edge cases

| Síntoma | Causa | Solución |
|---|---|---|
| `dictionary does not contain key "..."` | `meta` parcial pasado a un helper | Construye `meta` con `crear-meta(...)` |
| `file not found (Images/...)` | rutas relativas a `lib.typ` | Mantén `lib.typ` y `Images/` juntos en `SCRIPT_DIR`; el `.typ` importa `lib.typ` por ruta absoluta |
| Recuadros de logo vacíos | faltan los PNG reales | Copia `logoslepch.png` (y `isologo_2.png`) a `Images/` |
| Tipografía distinta al estándar | Museo Sans no instalada | Instálala o usa `--font-path`; fallback Liberation Sans |
| Íconos de aviso como cuadros | la fuente fallback no trae ℹ/⚠/⛔/✓ | Con Museo Sans renderizan; o cambia los glifos en `_aviso-cfg` |
| Correlativo repetido o saltado | se asignó a mano | Usa `doctyp` (secuencial automático desde el JSON); no fijes `--correlativo` sin motivo |
| `doctyp` no encuentra `lib.typ` | symlink roto o `lib.typ` movido | Mantén `lib.typ` junto a `doctyp.py`; recrea el symlink con `ln -sf "$(pwd)/doctyp.py" ~/.local/bin/doctyp` |
| `doctyp: command not found` | `~/.local/bin` fuera del PATH | Añádelo en `~/.bashrc`: `export PATH="$HOME/.local/bin:$PATH"` y reabre la terminal |
| Portada numerada / doble contraportada | se alteró `report` | No edites `report`; no escribas portada/contraportada a mano |

---

## 11. TL;DR para Claude Code

1. No toques el estilo de `lib.typ` sin orden explícita.
2. Crea informes con `doctyp nuevo "..."` (correlativo secuencial automático; sale en el CWD).
   Sube versión con `doctyp save <correlativo> --m "..."`.
3. Rellena los `// TODO` siguiendo la estructura canónica (§5) y la API (§8).
4. Compila tras cada cambio (§7) y reporta el `codigo-completo`.
