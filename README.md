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
- **Gestión centralizada**: todos los documentos viven en `~/Documentos/doctyp/<año>/`.
- **Versionado semántico** del documento y de su tabla de control de versiones (`save`).
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

---

## Inicio rápido (recomendado)

Clona el repositorio desde GitHub y ejecuta el instalador `init`. Detecta tu distribución,
instala/comprueba las dependencias, instala las fuentes y crea los symlinks del comando:

```bash
git clone https://github.com/KemosahbeAndres/informes-uti-slep-chinchorro.git
cd informes-uti-slep-chinchorro
./init
```

Al terminar, abre una terminal nueva (o recarga el shell) y prueba:

```bash
doctyp list
```

> Si `init` avisa de que `~/.local/bin` no está en el `PATH`, añade la línea que indica a tu
> `~/.bashrc` y reabre la terminal.

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

Comprueba la instalación:

```bash
which doctyp        # → ~/.local/bin/doctyp
doctyp list
```

> El script localiza `lib.typ`, las fuentes y `settings.json` junto a sí mismo (resolviendo el
> symlink), así que funciona desde cualquier carpeta. **No muevas `doctyp.py` fuera del proyecto.**

---

## Uso

### Subcomandos (con alias)

```bash
doctyp list  [--anio 2026]                   # (ls)        lista documentos y el próximo correlativo
doctyp new   "Título" [opciones]             # (n)         crea un informe (tipo INF, categoría SFW por defecto)
doctyp save  <correlativo> --m "mensaje"     # (s)         sube la versión (patch) y registra el cambio
doctyp add                                   # (a)         importa un .typ del directorio actual al registro
doctyp compile <correlativo>                 # (c)         compila a PDF (en Documentos/doctyp/ y copia al CWD)
doctyp edit  <correlativo>                   # (code, e)   abre el .typ en VS Code / editor favorito
doctyp reset [<correlativo>]                 #             fija dónde empieza el correlativo del año (def. 1)
```

### Ejemplos

```bash
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

# Compilar a PDF y abrir en el editor
doctyp compile 1
doctyp edit 1
```

Sin `--titulo`, `new` lo pide de forma interactiva. Defaults de autoría: *Andres Cubillos
Salazar*, *Tecnico de Soporte Informático*, *andres.cubillos@epchinchorro.cl* (ajustables con
`--autor` / `--cargo` / `--correo`).

---

## Dónde se guarda cada cosa

| Elemento | Ubicación |
|---|---|
| Documentos `.typ` y sus PDF | `~/Documentos/doctyp/<año>/<código-base>.typ` |
| Plantilla, fuentes y assets | junto al script (`lib.typ`, `museo-sans/`, `Images/`) |
| Configuración + registro | `settings.json` (junto al script) |

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

## Documentación adicional

Para detalles de la plantilla, la API de componentes y el flujo de co-redacción, ver
[CLAUDE.md](CLAUDE.md).
