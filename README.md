# doctyp — Generador de Informes Técnicos · SLEP Chinchorro (Unidad TI)

`doctyp` es una herramienta de línea de comandos para **redactar, versionar y compilar informes
técnicos** sobre una plantilla [Typst](https://typst.app).

Cada informe es un archivo `.typ` que importa la plantilla `lib.typ` (portada, contraportada,
estilos, componentes) y solo aporta sus metadatos y la prosa. El correlativo documental
(`TI-INF-SFW_2026-0001`) se asigna de forma **secuencial automática** y se lleva en un registro
central, evitando números repetidos o saltados.

---

## Características

- **Comando global** invocable desde cualquier carpeta (`doctyp`, con alias `ty`, `tp`, `dt`).
- **Nomenclatura oficial** automática: `AREA-TIPO-CAT_AAAA-NNNN`.
- **Correlativo secuencial anual**, con punto de inicio configurable (`reset`).
- **Gestión centralizada**: todos los documentos viven junto a la plantilla (`lib.typ`).
- **Versionado semántico** del documento y de su tabla de control de versiones (`save`).
- **Snapshots de versión con git**: cada `new`/`save`/`add` crea un commit y un tag anotado
  recuperable con `history`/`restore` (opcional; se degrada sin errores si no hay git).
- **Compilación a PDF** con resolución correcta de plantilla y fuentes.
- **Apertura en el editor** (VS Code o el favorito del sistema).
- Sin dependencias de Python externas (solo biblioteca estándar).

---

## Stack y tecnologías

| Componente | Uso |
|---|---|
| **Python 3** (≥ 3.10) | CLI `doctyp.py` — solo `stdlib` (argparse, json, pathlib, subprocess). |
| **Typst** (≥ 0.12) | Motor de composición que compila los `.typ` a PDF. |
| **Plantilla `lib.typ`** | Estilos, portada/contraportada y componentes del estándar gráfico. |
| **Fuentes Museo Sans / gobCL** | Tipografía oficial (en `museo-sans/` y `GobCLFontsFiles/`). |
| **VS Code** *(opcional)* | Editor preferido por `doctyp edit`; cae a `$EDITOR`/`xdg-open`. |
| **`settings.json`** | Configuración + registro de correlativos y versiones. |

---

## Dependencias

Necesarias para funcionar:

1. **Python 3** (≥ 3.10) — para ejecutar el script.
2. **Typst** (≥ 0.12) — para compilar a PDF (`doctyp compile`). Las fuentes oficiales (Museo Sans
   y gobCL) vienen en el repositorio; si faltan en el sistema, Typst cae a Liberation Sans sin
   romper el layout.

### Instalación de dependencias por sistema

Instala Python 3 y Typst con el gestor de tu sistema. (`init` / `init.ps1` también lo intentan
por ti; estos comandos son por si prefieres hacerlo a mano o el automático no pudo.)

**Windows** (PowerShell):

```powershell
winget install Python.Python.3.12
winget install Typst.Typst
# Alternativa con Scoop:
#   scoop install python typst
```

**macOS** (Terminal, con [Homebrew](https://brew.sh)):

```bash
brew install python typst
```

**Linux — Fedora / RHEL** (bash):

```bash
sudo dnf install -y python3 typst
```

**Linux — Arch** (bash):

```bash
sudo pacman -S --noconfirm python typst
```

**Linux — Ubuntu / Debian** (bash) — Typst no está en los repos estándar:

```bash
sudo apt-get update
sudo apt-get install -y python3
sudo snap install typst --classic        # o:  cargo install typst-cli
```

**Linux — openSUSE** (bash):

```bash
sudo zypper install -y python3
sudo snap install typst --classic        # o:  cargo install typst-cli
```

> En cualquier sistema, como último recurso para Typst:  `cargo install typst-cli`
> o el binario oficial desde <https://github.com/typst/typst/releases>.

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

1. **Detecta tu sistema** (Ubuntu, Debian, Fedora/RHEL, Arch, openSUSE o macOS) a partir de
   `/etc/os-release` o `uname`.
2. **Comprueba e instala las dependencias** con el gestor de tu sistema:
   - **Python 3** (`apt`/`dnf`/`pacman`/`zypper`/`brew`).
   - **Typst** (`dnf` en Fedora, `pacman` en Arch, `brew` en macOS; `snap` o `cargo` en
     Debian/Ubuntu/SUSE).
   Te pedirá la contraseña de `sudo` solo si hay que instalar algo.
3. **Instala las fuentes oficiales** (Museo Sans y gobCL) en `~/.local/share/fonts`
   (`~/Library/Fonts` en macOS) y refresca la caché de fuentes.
4. **Crea los symlinks** del comando en `~/.local/bin`: `doctyp` y sus alias `ty`, `tp`, `dt`.
5. **Configura los datos del autor** (nombre, cargo, correo) de forma interactiva y los guarda
   globalmente en `settings.json → local.author`. Cada dato muestra el valor actual entre
   paréntesis: si lo dejas en blanco, se mantiene. Volver a ejecutar `init` permite cambiarlos.
   Al crear documentos, `doctyp new` usa estos datos por defecto.
6. **Verifica el `PATH`**: si `~/.local/bin` no está incluido, te muestra la línea exacta para
   añadirlo a tu `~/.bashrc`.

Al terminar, abre una terminal nueva (o recarga el shell) y prueba:

```bash
doctyp list
```

> - Es seguro volver a ejecutar `init`: actualiza symlinks y fuentes sin duplicar nada.
> - Si una dependencia no se pudo instalar automáticamente (p. ej. Typst en Debian/Ubuntu sin
>   `snap`), `init` te indica el comando alternativo; consulta la
>   [instalación manual por distribución](#instalación-manual-por-distribución).
> - Si `init` avisa de que `~/.local/bin` no está en el `PATH`, añade la línea indicada a tu
>   `~/.bashrc` y reabre la terminal.

### Windows (`init.ps1`)

En Windows usa el instalador de PowerShell **`init.ps1`** (equivalente del `init` de Linux). Desde
la carpeta del repositorio, en PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\init.ps1
```

`init.ps1`:

1. **Comprueba e instala Python 3 y Typst**: si faltan, pregunta `¿Instalar? [S/n]` y los instala
   con `winget` (predeterminado: Sí). Si ya están instalados, los omite sin actualizar.
2. **Instala las fuentes oficiales** (Museo Sans + gobCL): pregunta antes de copiar; omite las que
   ya estén instaladas.
3. **Crea lanzadores `.cmd`** (`doctyp`, `ty`, `tp`, `dt`) en `%USERPROFILE%\bin` de forma
   automática (solo los que falten). En Windows no se usan symlinks (requieren privilegios); los
   `.cmd` cumplen la misma función y reenvían todos los argumentos.
4. **Añade `%USERPROFILE%\bin` al `PATH` del usuario** automáticamente si no estaba.
5. **Configura los datos del autor** (igual que en Linux: interactivo, valor actual entre
   paréntesis, en blanco se mantiene) y los guarda en `settings.json → local.author`.

Abre una terminal **nueva** y prueba `doctyp list`. El propio `doctyp.py` ya es multiplataforma:
detecta Typst y el editor (`code`, `$EDITOR` o la app por defecto del sistema) en Windows, macOS
y Linux.

---

## Instalación manual por distribución

Si prefieres no usar `init`, instala las dependencias según tu sistema y luego crea los symlinks
(sección [Instalación del comando](#instalación-del-comando)).

### Ubuntu

```bash
sudo apt-get update
sudo apt-get install -y python3

# Typst no está en los repos estándar; usa snap (o cargo / binario de GitHub):
sudo snap install typst --classic
# Alternativa:  cargo install typst-cli
```

### Debian

```bash
sudo apt-get update
sudo apt-get install -y python3

# Typst no está en los repos estándar; instala con cargo o el binario oficial:
cargo install typst-cli
# Alternativa:  binario desde https://github.com/typst/typst/releases
```

### Fedora

```bash
sudo dnf install -y python3 typst
# Si 'typst' no estuviera en los repos:  cargo install typst-cli
```

> **Nota Flatpak (Fedora):** si ejecutas dentro del sandbox de VS Code y `typst` solo está en el
> host, `doctyp` lo invoca automáticamente con `flatpak-spawn --host typst`. Sin configuración extra.

### Arch

```bash
sudo pacman -S --noconfirm python typst
```

### macOS

```bash
brew install python typst
```

### Windows

```powershell
winget install Python.Python.3.12
winget install Typst.Typst
```

Luego ejecuta `init.ps1` (ver [Windows (`init.ps1`)](#windows-initps1)) para crear los lanzadores
del comando y añadirlos al `PATH`.

---

## Instalación del comando

`init` ya lo hace por ti. Si lo instalas a mano, crea un **symlink** al script en `~/.local/bin`
(que suele estar en el `PATH`), junto con los alias `ty`, `tp` y `dt`:

```bash
# Desde la raíz del proyecto:
chmod +x doctyp.py
mkdir -p ~/.local/bin
for n in doctyp ty tp dt; do
  ln -sf "$(pwd)/doctyp.py" ~/.local/bin/$n
done
```

Si `~/.local/bin` no está en el `PATH`, añádelo a tu shell (`~/.bashrc`) y reabre la terminal:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

**En Windows** (si no usas `init.ps1`), crea un lanzador `.cmd` por cada alias en una carpeta que
esté en el `PATH` (p. ej. `%USERPROFILE%\bin`); cada uno invoca el script:

```bat
@echo off
python "C:\ruta\al\repo\doctyp.py" %*
```

Guarda ese contenido como `doctyp.cmd`, `ty.cmd`, `tp.cmd` y `dt.cmd`. No se usan symlinks en
Windows porque requieren privilegios; los `.cmd` cumplen la misma función.

Comprueba la instalación:

```bash
which doctyp        # → ~/.local/bin/doctyp
doctyp list
```

> El script localiza `lib.typ`, las fuentes y `settings.json` junto a sí mismo (resolviendo el
> symlink), así que funciona desde cualquier carpeta. **No muevas `doctyp.py` fuera del proyecto.**

---

## Uso

### Menú interactivo

Sin argumentos, `doctyp` muestra un **menú interactivo** con todos los comandos disponibles y el estado del registro:

```bash
doctyp
```

```
  doctyp  Informes Técnicos · SLEP Chinchorro (Unidad TI)
  ──────────────────────────────────────────────────────

  3 documento(s) registrado(s)  ·  próximo: 0004  (2026)

  Comandos disponibles:

  1  list            Lista documentos y el próximo correlativo
  2  new             Crear un nuevo documento
  3  save            Subir versión de un documento (patch)
  ...

  Selecciona [1-8, q=salir]:
```

Para los comandos que requieren un correlativo o mensaje, el menú los pide de forma interactiva.

### Subcomandos (con alias)

```bash
doctyp list  [--anio 2026]                   # (ls)              lista documentos y el próximo correlativo
doctyp new   "Título" [opciones]             # (n)               crea un informe (tipo INF, categoría SFW por defecto)
doctyp save  <correlativo> --m "mensaje"     # (s)               sube la versión (patch) y registra el cambio
doctyp add                                   # (a)               importa un .typ del directorio actual al registro
doctyp compile <correlativo>                 # (c)               compila a PDF (junto al .typ y copia al CWD)
doctyp edit  <correlativo>                   # (code, e, open)   abre el .typ con selección interactiva de editor
doctyp reset [<correlativo>]                 #                   fija dónde empieza el correlativo del año (def. 1)
doctyp config-author                         # (author)          configura el autor global (settings.json → local.author)
doctyp git-init                              #                   inicializa/migra el repo git para snapshots (idempotente)
doctyp history <doc-ref>                     # (h, log)          versiones de un documento y si tienen snapshot
doctyp restore <doc-ref> [--pdf] [--stdout]  #                   extrae una versión anterior desde su snapshot git
```

### Ejemplos

```bash
# Menú interactivo (sin argumentos)
doctyp

# Crear un informe (título posicional, o --t / --titulo)
doctyp new "Auditoría de respaldos del Centro de Datos"
doctyp n --t "Manual de red" --tipo MAN --categoria RED

# Forzar un correlativo concreto
doctyp new "Informe especial" --code 50

# Definir desde dónde numerar el año en curso
doctyp reset 100          # el próximo documento será 0100
doctyp reset              # vuelve a 1

# Subir una versión (1.0.0 → 1.0.1) y registrar el cambio
doctyp save 1 --m "Corrige la sección de alcance"

# Compilar a PDF y abrir en el editor (selección interactiva)
doctyp compile 1
doctyp edit 1     # equivalente: doctyp open 1  /  doctyp code 1  /  doctyp e 1
```

Sin `--titulo`, `new` lo pide de forma interactiva. Los **defaults de autoría** salen de
`settings.json → local.author` (lo que configuraste en `init` / `init.ps1` o con
`doctyp config-author`); si ese campo está vacío, se usan los de fábrica (*Andres Cubillos
Salazar*, *Tecnico de Soporte Informático*, *andres.cubillos@epchinchorro.cl*). En cualquier caso
puedes sobrescribirlos por documento con `--autor` / `--cargo` / `--correo`.

Para cambiar el autor global en cualquier momento (interactivo; cada dato muestra el valor actual
entre paréntesis y en blanco se mantiene):

```bash
doctyp config-author
```

---

## Dónde se guarda cada cosa

| Elemento | Ubicación |
|---|---|
| Documentos `.typ` y sus PDF | junto al script, como `<código-base>.typ` |
| Plantilla, fuentes y assets | junto al script (`lib.typ`, `museo-sans/`, `Images/`) |
| Configuración + registro | `settings.json` (junto al script) |

Los documentos se guardan **al lado de la plantilla** (`lib.typ`) a propósito: así el `.typ` la
importa con ruta local (`#import "lib.typ"`), el editor la resuelve sin configuración y compila
sin opciones extra.

El campo `local.correlativo_inicio` de `settings.json` guarda, por año, dónde empieza la
numeración (lo gestiona `doctyp reset`).

---

## Nomenclatura documental

Patrón: `AREA-TIPO-CAT_AAAA-NNNN_vX.Y.Z_AAAAMMDD` → p. ej. `TI-INF-SFW_2026-0001_v1.0.0_20260621`.

- **Tipos:** INF Informe · MAN Manual · POL Política · PRO Procedimiento · PLA Plan ·
  EVL Evaluación · ETT Esp. Técnica · ACT Acta.
- **Categorías:** SEG, RED, HRW, SFW, DAT, SRV, PRV, GOB, USR, CPD, BCK, PRY, CAP.
- **NNNN** es el correlativo secuencial global anual (4 dígitos), asignado automáticamente.

---

## Snapshots con Git

`doctyp` guarda, **opcionalmente**, el contenido de cada versión de un documento en git: una
sola rama (nunca crea ramas por documento) + **un tag anotado por versión**, con el patrón
`doc/<año>-<correlativo:04d>/v<versión>` (p. ej. `doc/2026-0039/v1.2`). El registro de
correlativos y versiones sigue viviendo en `settings.json`; git solo añade la posibilidad de
**recuperar el contenido** de una versión anterior, que de otro modo se pierde al sobrescribir
el `.typ` en cada `save`/`compile`.

### Activarlo

```bash
doctyp git-init
```

Es **idempotente** (puedes correrlo varias veces sin duplicar nada): inicializa el repositorio si
no existe, agrega `*.pdf` y `__pycache__/` al `.gitignore`, ofrece configurar la identidad git
local con los datos de `settings.json → local.author` si falta, hace un commit inicial si hay
cambios pendientes y crea **tags retroactivos** para la **última** versión de cada documento ya
registrado (las versiones intermedias guardadas antes de activar esto no tienen contenido
recuperable).

A partir de ahí, cada `doctyp new`, `doctyp save` y `doctyp compile` crea automáticamente un
commit y su tag; si git no está instalado o el directorio no es un repositorio, estos comandos
**siguen funcionando exactamente igual** (solo se imprime un aviso) — nunca se bloquean por
falta de git.

### Sintaxis doc-ref

Los comandos `history` y `restore` referencian un documento y (opcionalmente) una versión con:

```
<correlativo>[:<version>][@<año>]
```

| Referencia | Significado |
|---|---|
| `39` | doc 0039 del año actual, **última** versión |
| `39:1.2` | doc 0039 del año actual, versión 1.2 |
| `39:1.2@2025` | doc 0039 del año 2025, versión 1.2 |
| `39@2025` | doc 0039 del año 2025, última versión |

(`39/1.2` es equivalente a `39:1.2`; `/` y `:` son intercambiables como separador de versión.)

### Ver historial y restaurar una versión

```bash
doctyp history 39            # lista las versiones y si cada una tiene snapshot (✔/–)
doctyp restore 39:1.2        # extrae esa versión a TI-..._v1.2.typ, sin tocar el vigente
doctyp restore 39            # sin versión: usa la anterior a la vigente
doctyp restore 39:1.2 --pdf     # además la compila a PDF
doctyp restore 39:1.2 --stdout  # imprime el contenido en vez de escribir un archivo
```

`restore` **nunca sobrescribe** el `.typ` vigente ni un archivo restaurado previamente: si el
destino ya existe, se detiene con un error.

---

## Documentación adicional

Para detalles de la plantilla, la API de componentes y el flujo de co-redacción, ver
[CLAUDE.md](CLAUDE.md).
