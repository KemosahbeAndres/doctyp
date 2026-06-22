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
  `doctyp` (§3) o, si creas el archivo a mano, calcula el siguiente con `doctyp list`.
  La fuente de verdad del correlativo y de las versiones es `settings.json` (junto al script).
- Tras cada cambio, **compila y verifica** (§7). No afirmar que algo funciona sin compilarlo.
- Diffs mínimos; una sola fuente de verdad (todo dato en `meta`); sin hardcodear estilos.

---

## 1. Estructura del proyecto

```
.
├── lib.typ          # PLANTILLA (motor): estilos, portada/contraportada, componentes, atajos.
├── doctyp.py        # CLI que crea informes (comando global `doctyp`; symlink en ~/.local/bin).
├── init             # Instalador (bash): dependencias + fuentes + symlinks. Ejecutar una vez tras clonar.
├── README.md        # Descripción, instalación por distro y uso.
├── settings.json    # Config + registro de doctyp: inicio de correlativo (local), correlativos y versiones.
├── main.typ         # Informe de ejemplo (referencia). No es la plantilla.
├── CLAUDE.md        # Este archivo.
└── Images/
    ├── logoslepch.png   # Logo color SLEP (portada + header)   ← meta.logos.slep
    └── isologo_2.png    # Marca pequeña (reservado)            ← meta.logos.isologo
```

Los **documentos generados se guardan en `SCRIPT_DIR`** (junto a `lib.typ`), como
`<código-base>.typ`. Viven al lado de la plantilla para que el `.typ` la importe con ruta
local (`#import "lib.typ"`): así el editor (LSP de Typst) la resuelve sin configuración y
compila sin `--root`.

Cada informe se nombra con su **código base**: `TI-<TIPO>-<CAT>_<AAAA>-<NNNN>.typ`.

---

## 2. Crear un informe — dos vías

**Vía A (recomendada): generador `doctyp`** — asigna el correlativo y escribe la estructura.
El documento se crea de forma centralizada en **`<Documentos>/doctyp/<año>/`**, no en el CWD.
Con los defaults de autoría (de `settings.json → local.author`; ver `config-author`), tipo `INF`
y categoría `SFW` basta con el título:

```bash
doctyp new "Auditoría de respaldos del Centro de Datos"   # título posicional (alias: doctyp n)
doctyp n --t "Manual de red" --tipo MAN --categoria RED    # o con --t / --titulo
```

Para subir la versión de un documento ya creado (bump del patch, `1.0.0 → 1.0.1`), actualiza el
`.typ` y añade una fila a la tabla de control de versiones:

```bash
doctyp save 1 --m "Corrige la sección de alcance"   # 1 = correlativo del documento (alias: doctyp s)
```

**Vía B (manual):** crea el `.typ` con este esqueleto (también está embebido en la cabecera de
`lib.typ`). Antes, obtén el correlativo con `doctyp list`.

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
(symlink en `~/.local/bin` → `doctyp.py`), con alias equivalentes **`ty`**, **`tp`** y **`dt`**
(symlinks al mismo script). Funciona desde cualquier carpeta:

- **Gestión centralizada en `SCRIPT_DIR`:** todos los documentos (creados, importados, editados,
  compilados) viven junto a la plantilla, no en el CWD. El `.typ` importa `lib.typ` con ruta
  **local** (`#import "lib.typ"`); por eso el editor lo resuelve sin configuración y compila sin
  `--root`. (Typst rechaza imports que escapen del root del proyecto, así que la plantilla debe
  estar en la misma carpeta que el documento.)
- **Plantilla y assets junto al script:** `lib.typ`, `Images/`, las fuentes y `settings.json`
  viven en `SCRIPT_DIR`; Typst resuelve `Images/` y las fuentes relativo a `lib.typ`.
- **Config + registro central:** `settings.json` (en `SCRIPT_DIR`) es la **fuente de verdad** de
  correlativos y versiones; guarda la `ruta` de cada `.typ`. El campo `local.correlativo_inicio`
  (por año) define dónde empieza la numeración (ver `reset`).

### Correlativo secuencial
- **Global anual:** el próximo número = (máximo correlativo del año en el registro) + 1, pero
  nunca menor que `local.correlativo_inicio.<año>` si está configurado (ver `reset`).
- El registro manda; como respaldo se escanea `<Documentos>/doctyp/<año>/` para no pisar un
  `.typ` ya presente con el mismo año. Nunca reutiliza un número ya usado.

### Menú interactivo
Sin argumentos, `doctyp` muestra un menú numerado con todos los comandos disponibles y el estado
del registro (documentos registrados y próximo correlativo). Los comandos que requieren correlativo
o mensaje los solicitan de forma interactiva desde el propio menú. Claude Code puede usar los
subcomandos directamente por línea de comandos; el menú es para uso humano.

### Subcomandos
```bash
doctyp list  [--anio 2026]                   # (alias: ls)            lista documentos y el próximo correlativo
doctyp new   "Título" [opciones]             # (alias: n)             crea (tipo INF, categoría SFW por defecto)
doctyp save  <correlativo> --m "mensaje"     # (alias: s)             sube versión (patch) y registra el cambio
doctyp add                                   # (alias: a)             mueve un .typ del CWD junto a la plantilla y lo registra
doctyp compile <correlativo>                 # (alias: c)             compila a PDF (junto al .typ y copia al CWD)
doctyp edit <correlativo>                    # (alias: code, e, open) abre el .typ con selección interactiva de editor
doctyp reset [<correlativo>]                 #                        fija dónde empieza el correlativo del año (def. 1)
doctyp config-author                         # (alias: author)        configura el autor global (settings.json → local.author)
```
El título de `new` admite tres formas: posicional (`doctyp new "Título"`), `--t "Título"`
o `--titulo "Título"`.

### Opciones de `nuevo`
| Flag | Por defecto | Notas |
|---|---|---|
| `--tipo` | `INF` | INF, MAN, POL, PRO, PLA, EVL, ETT, ACT |
| `--categoria` | `SFW` | SEG, RED, HRW, SFW, DAT, SRV, PRV, GOB, USR, CPD, BCK, PRY, CAP |
| `título` (posicional) / `--titulo` / `--t` | (se pide interactivo) | Título del documento |
| `--subtitulo` | `SLEP Chinchorro` | |
| `--area` | `TI` | |
| `--correlativo` / `--code` | **secuencial automático** | fuerza un número manualmente (p. ej. `--code 50`) |
| `--version` | `1.0.0` | versión inicial (semántica) |
| `--fecha` | hoy (AAAAMMDD) | |
| `--anio` | el de `--fecha` | |
| `--estado` | `BORRADOR` | BORRADOR \| EN REVISIÓN \| APROBADO |
| `--clasificacion` | `INTERNO` | PÚBLICO \| INTERNO \| RESERVADO \| CONFIDENCIAL |
| `--autor` | `settings.json → local.author` (o `Andres Cubillos Salazar`) | autoría; el default global lo fija `config-author`/`init` |
| `--cargo` | `settings.json → local.author` (o `Tecnico de Soporte Informático`) | autoría |
| `--correo` | `settings.json → local.author` (o `andres.cubillos@epchinchorro.cl`) | autoría |
| `--revisor` `--aprobador` | defaults de la plantilla | |
| `--forzar` | — | sobrescribe si el archivo existe |

> El `.typ` se crea siempre en `<Documentos>/doctyp/<año>/`, no en el CWD.
> Para compilar usa `doctyp compile <correlativo>` (la compilación no está dentro de `new`/`save`).

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

### Subcomando `add`
Importa al registro un documento `.typ` que existe en el **directorio actual** (p. ej. uno
creado a mano o traído de otra parte). `doctyp add` (sin argumentos):
- Lista solo los `.typ` del CWD que tienen `crear-meta` **completo** (area, tipo, categoría,
  año, correlativo, versión, título, autor) y que **aún no están** en el registro.
- Permite elegir uno tecleando su número (`q` cancela).
- **Mueve el archivo** junto a la plantilla (`SCRIPT_DIR/<código-base>.typ`, sobrescribe si ya
  existe), **normaliza su import a `"lib.typ"`** y lo registra, conservando el correlativo del
  meta; si ese correlativo choca con otro del registro, avisa y no importa.

Tras `add`, el documento queda gestionado como cualquier otro: `doctyp save <correlativo> ...`
funciona sobre él.

### Subcomando `compile`
`doctyp compile <correlativo>` localiza el documento en el registro y lo compila a PDF. El PDF
queda **junto al `.typ` (en `SCRIPT_DIR`)** y, además, se **copia al CWD** donde se ejecutó.
Detalles de la invocación (en `compilar_typ`):
- **Sin `--root`**: el `.typ` importa `lib.typ` con ruta local, así que Typst resuelve todo desde
  la carpeta del documento (que es `SCRIPT_DIR`).
- **`--font-path <SCRIPT_DIR>/museo-sans`**: fuentes Museo Sans para fidelidad tipográfica.
- **`cwd` = carpeta del `.typ`** (`SCRIPT_DIR`, bajo `$HOME`): con `flatpak-spawn --host`, el cwd
  del sandbox (p. ej. `/tmp/...`) puede no existir en el host; ejecutar en `SCRIPT_DIR` lo evita.
- **Flatpak (Fedora):** si `typst` no está en el PATH del sandbox pero sí en el host, usa
  `flatpak-spawn --host typst`. En una terminal normal del host se usa `typst` directo.

### Subcomando `reset`
`doctyp reset [<correlativo>]` fija dónde empieza la numeración del año en `settings.json`
(`local.correlativo_inicio.<año>`). Sin argumento, el inicio vuelve a **1**; con `doctyp reset 50`
el próximo documento del año será `0050`. El inicio actúa como **mínimo**: nunca retrocede sobre
correlativos ya usados (si ya existe el 0101, el próximo seguirá siendo 0102 aunque fijes 1).
Usa `--anio` para configurar otro año.

### Subcomando `edit`
`doctyp edit <correlativo>` (alias `code`, `e`, `open`) detecta todos los editores disponibles y
muestra un **menú de selección interactiva** (predeterminado: el primero encontrado, que suele
ser VS Code). Los editores se detectan en este orden:
1. **VS Code binario** `code` en el PATH (sandbox, terminal integrada o host con `code` instalado).
2. **VS Code / VSCodium como Flatpak** (`com.visualstudio.code` / `com.vscodium.codium`): se lanza
   con `flatpak run <id>`. Es el caso típico en Fedora, donde **no** hay binario `code` en el PATH.
3. **Editor favorito** `$VISUAL` / `$EDITOR`.
4. **App predeterminada del sistema**: `xdg-open` (Linux), `open` (macOS) u `os.startfile`
   (Windows). En Windows también detecta `code.cmd`.

Si solo se detecta un editor, se abre directamente sin preguntar. Si hay varios, se muestra la
lista numerada y el usuario elige (Enter acepta el predeterminado). La detección usa `flatpak-spawn
--host` dentro de un sandbox Flatpak.

### Subcomando `config-author`
`doctyp config-author` (alias `author`) configura **globalmente** los datos del autor (nombre,
cargo, correo) y los guarda en `settings.json → local.author`. Es interactivo: cada dato muestra
el valor actual entre paréntesis y, si lo dejas en blanco, se mantiene. Estos valores son el
**default de autoría** de `doctyp new` (sobre ellos siempre ganan `--autor`/`--cargo`/`--correo`).
Lo invocan `init` (Linux/macOS) e `init.ps1` (Windows); volver a ejecutarlos permite cambiarlos.

### Cómo lo usa Claude Code
1. Ejecuta `doctyp list` para conocer el próximo correlativo (informativo).
2. Ejecuta `doctyp new "..."` (ajusta `--tipo`/`--categoria`/autoría si hace falta).
3. Abre el `.typ` creado y **rellena las secciones marcadas `// TODO`** con el contenido del usuario.
4. Compila con `doctyp compile <correlativo>` (§7) e itera.

> El script localiza `lib.typ` junto a sí mismo (resolviendo el symlink). No usa `--root`.
> Instalación: `for n in doctyp ty tp dt; do ln -sf "$(pwd)/doctyp.py" ~/.local/bin/$n; done`
> (requiere `~/.local/bin` en el PATH). `ty`, `tp` y `dt` son alias del mismo comando.

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

Los encabezados se numeran solos (`1`, `1.1`). `doctyp new` ya escribe todo este esqueleto.

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

**Recomendado:** `doctyp compile <correlativo>` — localiza el documento por el registro, le pasa
`--font-path` automáticamente y deja el PDF junto al `.typ` (§3, subcomando `compile`).

```bash
doctyp compile 23                            # vía el generador (maneja fuentes y entorno)
```

A mano (el import a `lib.typ` es local, así que no hace falta `--root`; ejecuta desde `SCRIPT_DIR`):

```bash
typst compile --font-path museo-sans TI-INF-SEG_2026-0023.typ   # → .pdf
typst watch  TI-INF-SEG_2026-0023.typ                           # modo redacción
```

- Requiere **Typst ≥ 0.12** y, para fidelidad tipográfica, la fuente **Museo Sans** en
  `museo-sans/` (si falta, cae a Liberation Sans; el layout no se rompe).
- En **Fedora/Flatpak** (sandbox de VS Code), si `typst` no está en el PATH, usa
  `flatpak-spawn --host typst ...` con archivos bajo `$HOME` (`/tmp` del sandbox no lo ve el host).
  `doctyp compile` ya elige la invocación correcta.
- Coloca los logos reales en `Images/` antes de la versión final.
- La compilación vive solo en `doctyp compile <correlativo>` (no hay `--compilar` en `new`/`save`).

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
2. **Crea el archivo con el generador** (asigna el correlativo y lo deja en `<Documentos>/doctyp/<año>/`):
   `doctyp new "<título>"` (ajusta `--tipo`/`--categoria`/autoría solo si difieren de los defaults).
3. **Rellena las secciones `// TODO`** del archivo con el contenido del usuario, siguiendo la
   estructura canónica (§5). Usa `aviso(...)` para estados/riesgos y `tabla(...)`/`tabla-prioridad(...)` para datos.
4. **Compila** con `doctyp compile <correlativo>` (§7) y revisa el PDF; corrige e **itera** sección por sección.
5. Al cerrar una versión: `doctyp save <correlativo> --m "<qué cambió>"` sube el patch, actualiza
   el `version:` del `.typ` y añade la fila a `s-versiones` automáticamente. Reporta el `codigo-completo`.

Sugerencia: deja `typst watch <archivo>.typ` corriendo (desde `SCRIPT_DIR`) durante la redacción.

---

## 10. Edge cases

| Síntoma | Causa | Solución |
|---|---|---|
| `dictionary does not contain key "..."` | `meta` parcial pasado a un helper | Construye `meta` con `crear-meta(...)` |
| `file not found (Images/...)` o import en rojo | el `.typ` no está junto a `lib.typ` | El documento y `lib.typ` deben estar en la misma carpeta (`SCRIPT_DIR`); el import es local `"lib.typ"` |
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
2. Crea informes con `doctyp new "..."` (correlativo automático; se guarda en `<Documentos>/doctyp/<año>/`).
   Sube versión con `doctyp save <correlativo> --m "..."`. Subcomandos con alias: `list/ls`,
   `new/n`, `save/s`, `add/a`, `compile/c`, `edit/code/e/open`.
3. Rellena los `// TODO` siguiendo la estructura canónica (§5) y la API (§8).
4. Compila con `doctyp compile <correlativo>` tras cada cambio (§7) y reporta el `codigo-completo`.
