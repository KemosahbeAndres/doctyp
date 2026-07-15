# doctyp — Generador de Informes Técnicos · SLEP Chinchorro (Unidad TI)

`doctyp` es una herramienta para **redactar, versionar y compilar informes técnicos** sobre
plantillas [Typst](https://typst.app), con dos formas de uso:

- **CLI** (`doctyp`, alias `ty`, `tp`, `dt`): gestión de organizaciones, plantillas y
  documentos desde la terminal.
- **App web** (`doctyp web`): editor completo en el navegador — resaltado de sintaxis,
  LSP de Typst (tinymist), vista previa en vivo con clic↔cursor, autoguardado, gestión de
  imágenes y versionado.

Cada informe es una **carpeta autocontenida** con su archivo `.typ`, una copia local de la
plantilla (`lib.typ` + `Images/`), sus imágenes propias (`img/`) y su historial de versiones
(`.snapshots/`). El correlativo documental (`TI-INF-SFW_2026-0001`) se asigna de forma
**secuencial automática por organización** y se lleva en un registro central (`org.json`),
evitando números repetidos o saltados.

---

## Características

- **Organizaciones**: cada una agrupa sus autores, equipos, plantillas y documentos, con
  correlativo secuencial anual propio y punto de inicio configurable (`reset`).
- **Nomenclatura oficial** automática: `AREA-TIPO-CAT_AAAA-NNNN`.
- **Documentos autocontenidos**: la plantilla se copia a la carpeta del documento al
  crearlo — el editor y Typst resuelven todo con rutas locales, sin configuración.
- **Versionado semántico sin git**: cada `save`/`compile` guarda un snapshot del `.typ` en
  `.snapshots/`, recuperable con `history`/`restore`.
- **Plantillas por organización** con su propio historial de versiones y editor web.
- **App web completa** (ver [sección dedicada](#app-web-doctyp-web)): editor con LSP,
  vista previa tinymist, sidebar de archivos, exportación rápida y CRUD de la organización.
- **Compilación a PDF** con resolución correcta de plantilla y fuentes.
- Sin dependencias de Python externas (solo biblioteca estándar).

---

## Stack y tecnologías

| Componente | Uso |
|---|---|
| **Python 3** (≥ 3.10) | CLI (`doctyp.py`) y backend web (`doctyp_web.py`) — solo `stdlib`. |
| **Typst** (≥ 0.12) | Motor de composición que compila los `.typ` a PDF. |
| **tinymist** (0.15.x) | LSP de Typst + vista previa en vivo de la app web (`init` lo instala). |
| **Vue 3 + Vite** | SPA de la app web (`web/`); se compila con npm al arrancar `doctyp web`. |
| **CodeMirror 6** | Editor de código de la app web (resaltado Typst + cliente LSP). |
| **Plantillas `lib.typ`** | Estilos, portada/contraportada y componentes del estándar gráfico. |
| **`org.json`** | Registro por organización: documentos, correlativos, versiones, autores, equipos. |
| **`settings.json`** | Solo configuración local: organización activa, autor activo, preferencias. |

---

## Dependencias

1. **Python 3** (≥ 3.10) — CLI y backend web.
2. **Typst** (≥ 0.12) — compilación a PDF (`doctyp compile`). Si las fuentes oficiales
   (Museo Sans) no están disponibles, Typst cae a Liberation Sans sin romper el layout.
3. **Node.js + npm** *(opcional, solo para la app web)* — `doctyp web` compila la SPA
   automáticamente (`npm install` + `npm run build`) al arrancar. Sin npm, sirve el último
   build existente en `web/dist/` (o un placeholder).
4. **tinymist** *(opcional, recomendado)* — LSP y vista previa en vivo de la app web.
   `init`/`init.ps1` lo instalan automáticamente; sin él, la app web degrada a una vista
   previa WASM (typst.ts) sin clic↔cursor ni LSP.

### Instalación de dependencias por sistema

Instala Python 3 y Typst con el gestor de tu sistema. (`init` / `init.ps1` también lo intentan
por ti; estos comandos son por si prefieres hacerlo a mano o el automático no pudo.)

**Windows** (PowerShell):

```powershell
winget install Python.Python.3.12
winget install Typst.Typst
winget install OpenJS.NodeJS.LTS      # opcional, para la app web
```

**macOS** (Terminal, con [Homebrew](https://brew.sh)):

```bash
brew install python typst node
```

**Linux — Fedora / RHEL** (bash):

```bash
sudo dnf install -y python3 typst nodejs
```

**Linux — Arch** (bash):

```bash
sudo pacman -S --noconfirm python typst nodejs npm
```

**Linux — Ubuntu / Debian** (bash) — Typst no está en los repos estándar:

```bash
sudo apt-get update
sudo apt-get install -y python3 nodejs npm
sudo snap install typst --classic        # o:  cargo install typst-cli
```

> En cualquier sistema, como último recurso para Typst: `cargo install typst-cli` o el binario
> oficial desde <https://github.com/typst/typst/releases>. Para tinymist:
> <https://github.com/Myriad-Dreamin/tinymist/releases>.

---

## Inicio rápido con `init` (recomendado)

El repositorio incluye un script **`init`** que deja todo listo en un solo paso. Clónalo desde
GitHub y ejecútalo:

```bash
git clone https://github.com/KemosahbeAndres/doctyp.git doctyp
cd doctyp
./init
```

Si el archivo no tuviera permiso de ejecución, dáselo antes con `chmod +x init` (o ejecútalo como
`bash init`).

### Qué hace `init`

1. **Detecta tu sistema** (Ubuntu, Debian, Fedora/RHEL, Arch, openSUSE o macOS).
2. **Comprueba e instala Python 3 y Typst** con el gestor de tu sistema. Pide la contraseña
   de `sudo` solo si hay que instalar algo.
3. **Instala tinymist** (versión pineada, binario oficial desde GitHub releases) en
   `~/.local/bin` si no está ya instalado. Si la descarga falla (sin red), avisa y continúa:
   la app web funciona igual con la vista previa alternativa.
4. **Crea los symlinks** del comando en `~/.local/bin`: `doctyp` y sus alias `ty`, `tp`, `dt`.
5. **Configura los datos del autor** (nombre, cargo, correo) de forma interactiva. Cada dato
   muestra el valor actual entre paréntesis: si lo dejas en blanco, se mantiene.
6. **Verifica el `PATH`**: si `~/.local/bin` no está incluido, te muestra la línea exacta para
   añadirlo a tu `~/.bashrc`.

> Las fuentes oficiales (Museo Sans + gobCL) **no se instalan en el sistema**: viven en la
> carpeta `fonts/` de cada plantilla y `doctyp compile` las pasa a Typst con `--font-path`.

Al terminar, abre una terminal nueva (o recarga el shell) y prueba:

```bash
doctyp list
```

> - Es seguro volver a ejecutar `init`: actualiza symlinks y binarios sin duplicar nada.
> - Si una dependencia no se pudo instalar automáticamente, `init` te indica el comando
>   alternativo.

### Windows (`init.ps1`)

En Windows usa el instalador de PowerShell **`init.ps1`** (equivalente del `init` de Linux).
Desde la carpeta del repositorio, en PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\init.ps1
```

`init.ps1` comprueba e instala Python 3 y Typst (con `winget`, preguntando antes), instala
tinymist en `%USERPROFILE%\bin`, crea los lanzadores `.cmd` (`doctyp`, `ty`, `tp`, `dt`) en esa
misma carpeta, la añade al `PATH` del usuario si faltaba y configura los datos del autor.
Abre una terminal **nueva** y prueba `doctyp list`.

---

## Uso del CLI

Sin argumentos, `doctyp` muestra un **menú interactivo**. Para scripts y uso directo, los
subcomandos:

### Organizaciones, equipos y autores

```bash
doctyp org new <slug> [--nombre "…"]     # crea la organización (registro + carpeta de documentos)
doctyp org list                          # lista organizaciones (marca la activa)
doctyp org use <slug>                    # fija la organización activa
doctyp team new <id> [--nombre "…"]      # crea un equipo en la org activa
doctyp team list
doctyp author add                        # alta interactiva de autor (nombre, cargo, correo, equipos)
doctyp author list
doctyp author use <id>                   # fija el autor activo
```

### Plantillas

```bash
doctyp template add <ruta> [--nombre …]        # importa una carpeta de plantilla a la org activa
doctyp template list
doctyp template default <nombre>               # fija la plantilla por defecto de la org
doctyp template new <nombre> [--clonar-de …]   # clona otra plantilla, o el esqueleto en blanco
doctyp template rm <nombre> [--y]              # elimina (bloquea si es la default o la única)
doctyp template save <nombre> --m "…"          # snapshot de lib.typ + registro de versión
doctyp template history <nombre>               # versiones de la plantilla
doctyp template restore <nombre> [--version N] # extrae una versión anterior de lib.typ
```

### Documentos

```bash
doctyp list  [--anio 2026] [--org <slug>]    # (ls)   documentos + próximo correlativo
doctyp new   "Título" [--tipo INF] [--categoria SFW] [--plantilla <nombre>]   # (n)
doctyp save  <doc-ref> --m "mensaje"         # (s)    snapshot + sube versión (patch)
doctyp add                                   # (a)    importa un .typ del CWD como carpeta-documento
doctyp compile <doc-ref>                     # (c)    snapshot + compila a PDF
doctyp edit <doc-ref>                        # (e)    abre el .typ en el editor
doctyp history <doc-ref>                     # (h)    versiones y snapshots (✔/–)
doctyp restore <doc-ref> [--pdf] [--stdout]  #        extrae una versión (nunca sobrescribe)
doctyp reset [<correlativo>]                 #        inicio del correlativo del año (org activa)
```

### Sintaxis doc-ref

```
<correlativo>[:<version>][@<año>]
```

| Referencia | Significado |
|---|---|
| `39` | doc 0039 del año actual, **última** versión |
| `39:1.2` | doc 0039 del año actual, versión 1.2 |
| `39:1.2@2025` | doc 0039 del año 2025, versión 1.2 |
| `39@2025` | doc 0039 del año 2025, última versión |

(`39/1.2` es equivalente a `39:1.2`; `/` y `:` son intercambiables.)

### Ejemplos

```bash
# Crear la organización y dejarla activa
doctyp org new mi-org --nombre "Mi Organización"
doctyp org use mi-org

# Crear un informe (la plantilla se copia a la carpeta del documento)
doctyp new "Auditoría de respaldos del Centro de Datos"
doctyp n --t "Manual de red" --tipo MAN --categoria RED

# Definir desde dónde numerar el año en curso
doctyp reset 100          # el próximo documento será 0100

# Subir una versión (1.0.0 → 1.0.1) con snapshot automático
doctyp save 1 --m "Corrige la sección de alcance"

# Compilar a PDF / ver historial / recuperar una versión
doctyp compile 1
doctyp history 1
doctyp restore 1:1.0      # extrae esa versión a un archivo nuevo, sin tocar el vigente
```

Los **defaults de autoría** salen del autor activo de la organización (`doctyp author use`);
puedes sobrescribirlos por documento con `--autor` / `--cargo` / `--correo`.

---

## App web (`doctyp web`)

```bash
doctyp web [--port 8787] [--host 127.0.0.1] [--no-browser] [--no-build] [--legacy-preview]
```

Al arrancar compila la SPA (si hay `npm`), levanta el servidor local y **abre el navegador**
automáticamente. Por seguridad escucha solo en `127.0.0.1` (usa `--host` bajo tu criterio).

### Navegación (URLs reales)

| Ruta | Vista |
|---|---|
| `/documentos` | Cuadrícula de documentos (miniaturas de la primera página) |
| `/documentos/<código>` | Editor del documento |
| `/plantillas` | Cuadrícula de plantillas |
| `/plantillas/<nombre>` | Editor de la plantilla |
| `/organizacion` | Gestión de organizaciones, autores y equipos |

Las URLs sobreviven al refresco y se pueden guardar/compartir como marcadores. La barra
superior permite cambiar de organización y de autor activo (la cuadrícula filtra los
documentos del autor activo).

### Editor de documentos y plantillas

- **Editor de código** (CodeMirror 6): resaltado de sintaxis Typst, numeración de líneas,
  plegado de secciones.
- **LSP de Typst (tinymist)**: diagnósticos en vivo, autocompletado, hover, firma de
  funciones, ir a definición (F12), referencias (Shift+F12), renombrar (F2), formatear
  (Ctrl+Shift+F), esquema del documento (botón "≡"), símbolos (Ctrl+T), pistas de
  parámetros, selector de color y code actions (Ctrl+.).
- **Vista previa en vivo** (tinymist, split 60/40 editor/render): clic en el render mueve
  el cursor en el código y viceversa; indicador de estado de compilación
  (Compilando…/OK/Error).
- **Autoguardado a 300 ms** tras dejar de escribir (indicador "Guardando…"/"Guardado ✓").
  **Ctrl+S** (Cmd+S en macOS) fuerza el guardado inmediato; **Tab** indenta la selección.
- **Sidebar de archivos** (izquierda): árbol de solo lectura de la carpeta del documento o
  plantilla, para ver la estructura al referenciar imágenes (`img/…`, `Images/…`). Desde
  ahí se **suben, renombran y eliminan imágenes** (arrastrar y soltar, o botón "+") — solo
  imágenes en la carpeta propia (`img/` en documentos, `Images/` en plantillas); el resto
  del árbol es solo visualización.
- **Barra de estado**: versión actual, ver/comparar versiones anteriores (diff línea a
  línea), **exportación rápida** a PDF/texto/Markdown (sin subir versión), contador de
  palabras y tamaño, diagnósticos.
- **Acciones de versión** (cabecera): "Subir versión" (snapshot + registro con mensaje),
  "Compilar" (versión + PDF oficial), "Metadatos" (editar `meta` con formulario).

Si tinymist no está instalado (o se pasa `--legacy-preview`), el editor sigue funcionando
con resaltado propio y una vista previa WASM (typst.ts), sin LSP ni clic↔cursor.

### Gestión de la organización (`/organizacion`)

Página completa con tres pestañas: **Organización** (listar, crear y cambiar la activa),
**Autores** y **Equipos** (CRUD completo; no se puede eliminar un autor o equipo con
documentos asignados).

---

## Dónde se guarda cada cosa

| Elemento | Ubicación |
|---|---|
| Documentos (carpetas autocontenidas) | `<Documentos>/doctyp/<org-slug>/<código-base>/` |
| Registro de la organización | `organizations/<org-slug>/org.json` (junto al script) |
| Plantillas de la organización | `organizations/<org-slug>/templates/<nombre>/` |
| Configuración local (org/autor activos) | `settings.json` (junto al script) |

Cada carpeta de documento contiene: el `.typ`, la copia de la plantilla (`lib.typ`,
`Images/`, `fonts/` si aplica), `img/` para imágenes propias y `.snapshots/` con el
historial de versiones. La carpeta `<Documentos>` se resuelve según el sistema
(`xdg-user-dir` en Linux, *Documents* en Windows/macOS).

**`org.json` es la fuente de verdad** del registro: no edites correlativos ni versiones a
mano — usa siempre `doctyp`.

---

## Nomenclatura documental

Patrón: `AREA-TIPO-CAT_AAAA-NNNN_vX.Y_AAAAMMDD` → p. ej. `TI-INF-SFW_2026-0001_v1.0_20260621`.

- **Tipos:** INF Informe · MAN Manual · POL Política · PRO Procedimiento · PLA Plan ·
  EVL Evaluación · ETT Esp. Técnica · ACT Acta.
- **Categorías:** SEG, RED, HRW, SFW, DAT, SRV, PRV, GOB, USR, CPD, BCK, PRY, CAP.
- **NNNN** es el correlativo secuencial **global anual por organización** (4 dígitos),
  asignado automáticamente.

---

## Versionado por snapshots (sin git)

Cada `doctyp save` y `doctyp compile` (y "Subir versión"/"Compilar" en la app web) copia el
`.typ` vigente a `.snapshots/<código-base>_v<versión>.typ` **antes** de subir la versión, y
registra la fila en `org.json` (más un índice local de respaldo, `.snapshots/index.json`,
para que el historial sobreviva junto al documento).

```bash
doctyp history 39            # lista las versiones y si cada una tiene snapshot (✔/–)
doctyp restore 39:1.2        # extrae esa versión a TI-..._v1.2.typ, sin tocar el vigente
doctyp restore 39:1.2 --pdf     # además la compila a PDF
doctyp restore 39:1.2 --stdout  # imprime el contenido en vez de escribir un archivo
```

`restore` **nunca sobrescribe** el `.typ` vigente ni un archivo restaurado previamente: si el
destino ya existe, se detiene con un error. El autoguardado de la app web escribe el archivo
en disco pero **nunca** crea versiones — eso solo lo hacen `save`/`compile`/"Subir versión".

Las plantillas se versionan igual (`doctyp template save/history/restore`, o "Guardar
plantilla" en la app web).

---

## Documentación adicional

- [CLAUDE.md](CLAUDE.md) — arquitectura v3 (organizaciones), API de la plantilla, estructura
  canónica del informe y estado de implementación por etapas.
- [PLAN-V4.md](PLAN-V4.md) — plan aprobado de la arquitectura v4 (Docker, PostgreSQL, auth,
  módulo de proyectos y diagramas).
