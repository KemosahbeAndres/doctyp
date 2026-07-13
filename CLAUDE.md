# CLAUDE.md — doctyp · Plantillas de Informes Técnicos · SLEP Chinchorro (Unidad TI)

> Guía para **Claude Code** en este repositorio. Objetivo: que el usuario y Claude
> **redacten informes técnicos juntos** sobre plantillas Typst que reproducen el
> estándar **TI-MAN-GOB_2026-0020 v2.0** (Manual de Normas Gráficas SLEP 2026).
> Lee este archivo completo antes de crear o editar documentos.
>
> **⚠ Arquitectura v3 (organizaciones).** Este documento describe la arquitectura
> objetivo. Consulta §14 (Estado de implementación) antes de asumir que un comando
> o estructura existe: las etapas no completadas siguen operando con el modelo
> anterior (`settings.json` como registro, documentos planos, snapshots git).

---

## 0. Cómo debe comportarse Claude en este repo

- **`lib.typ` (de cada plantilla) es presentación. NO se edita su estilo** (colores,
  tipografía, portada, márgenes) salvo orden explícita del usuario. Regla del manual §11.2.
- **Cada informe es un archivo `.typ` propio** que importa `lib.typ` (copia local en su
  carpeta) y solo aporta `meta` + prosa.
- **El correlativo NUNCA se inventa:** es secuencial automático **por organización**.
  Genera los documentos con `doctyp` (§5). La fuente de verdad es el `org.json` de la
  organización activa.
- **No compiles automáticamente.** La compilación (§10) la hace el usuario de forma manual;
  no ejecutes `doctyp compile` salvo que lo pida explícitamente. Edita el `.typ` y avisa que
  queda listo para compilar. No afirmes que algo "compila" o "funciona" si no lo compilaste tú.
- **Plan antes de código:** para cambios estructurales, presenta un plan y espera aprobación
  explícita antes de implementar.
- Diffs mínimos; una sola fuente de verdad (todo dato en `meta`; todo registro en `org.json`);
  sin hardcodear estilos.

---

## 1. Estructura del proyecto (v3)

```
.
├── doctyp.py            # CLI (comando global `doctyp`; symlinks: ty, tp, dt).
├── doctyp_web.py         # Backend de `doctyp web` (servidor HTTP + API + SSE, Etapa 4).
├── init                 # Instalador (bash): dependencias + fuentes + symlinks.
├── README.md
├── CLAUDE.md            # Este archivo.
├── settings.json        # SOLO config local: org activa, autor activo, preferencias.
│                        #   Ya NO es registro de documentos (ver org.json).
├── web/                 # SPA Vue 3 (código fuente + dist/) servida por `doctyp web`.
│   └── dist/            # Build estático que sirve el backend.
├── templates_base/      # Esqueletos base para "Nueva plantilla" (Etapa 9), fuera de organizations/:
│   └── minimal/lib.typ  #   sin marca institucional; origen de la opción "en blanco".
└── organizations/       # CONFIG + PLANTILLAS: una carpeta por organización (NO documentos).
    └── <org-slug>/
        ├── org.json     # REGISTRO de la org: metadatos, equipos, autores,
        │                #   documentos y sus versiones. Fuente de verdad. Sin git.
        └── templates/   # Plantillas propias de la organización.
            └── <plantilla>/
                ├── lib.typ
                ├── Images/            # logos y assets de la plantilla
                ├── fonts/             # opcional (ojo licencia Museo Sans — NO redistribuir)
                └── .snapshots/        # historial de versiones de lib.typ (Etapa 9, sin git;
                                       #   único índice, org.json no registra plantillas)
```

**Los documentos NO viven en el repo.** Se guardan en la carpeta **Documentos del usuario**
según el sistema operativo (raíz de documentos = `DOCS_ROOT`):

```
<Documentos>/                        # p. ej. ~/Documentos, ~/Documents, %USERPROFILE%\Documents
└── doctyp/                          # raíz de documentos de doctyp (DOCS_ROOT)
    └── <org-slug>/                  # una carpeta por organización
        └── <código-base>/           # CARPETA POR DOCUMENTO
            ├── <código-base>.typ
            ├── lib.typ              # copia de la plantilla al momento de crear/agregar
            ├── Images/              # assets copiados de la plantilla
            ├── img/                 # imágenes propias del documento
            └── .snapshots/          # snapshots sin git: <código-base>_vX.Y.Z.typ + index.json
```

Resolución de `<Documentos>` (siempre se **busca**, no se asume):
- **Linux:** `xdg-user-dir DOCUMENTS` o parseo de `~/.config/user-dirs.dirs` (clave
  `XDG_DOCUMENTS_DIR`); fallback `~/Documents` (se crea si no existe).
- **Windows:** carpeta conocida *Documents* (registro `Shell Folders → Personal`);
  fallback `%USERPROFILE%\Documents`.
- **macOS:** `~/Documents`.

Principios:
- **Separación config/contenido:** `organizations/` (junto a `doctyp.py`) guarda registro y
  plantillas; `DOCS_ROOT` (`<Documentos>/doctyp/<org-slug>/`) guarda los documentos del usuario.
- **La plantilla se copia a la carpeta del documento** al crearse (`new`) o agregarse (`add`).
  El `.typ` importa con ruta local (`#import "lib.typ"`), por lo que el LSP de Typst resuelve
  sin configuración y compila sin `--root`. Cada documento queda **autocontenido**.
- **`org.json` es la fuente de verdad** de correlativos, versiones y membresías de la org.
  Escrituras atómicas obligatorias (write-temp + rename).
- **Sin git para versionado de documentos:** cada versión se preserva como copia en
  `.snapshots/`. Los comandos `git-*` quedan retirados. Además de la fila en `org.json`
  (fuente de verdad), cada documento guarda `.snapshots/index.json` — un espejo local de solo
  respaldo de `doc["versiones"]`, para que el historial sobreviva aunque `org.json` se pierda;
  ningún comando lo lee en caliente (Etapa 6, ver §14).

---

## 2. Modelo: organizaciones, equipos y autores

- Una **organización** agrupa autores, equipos, plantillas y documentos. Se identifica por
  su **slug** (carpeta en `organizations/`).
- Cada **autor pertenece a exactamente una organización** y puede pertenecer a **0..n equipos**
  dentro de ella.
- Los **equipos** son agrupaciones internas de autores (sin efecto en el correlativo).
- **Modo mono-usuario (vigente):** el usuario es siempre el **autor principal y por defecto**.
  Autores y equipos existen solo como **metadatos organizativos** (ordenar trabajo y documentos);
  las funciones multi-autor / colaboración en equipo **NO están implementadas** — no las asumas
  ni las diseñes de pasada (sin locking, sin permisos, sin sincronización).
- El **correlativo es global-anual por organización**: próximo = (máx. correlativo del año en
  `org.json`) + 1, nunca menor que `config.correlativo_inicio.<año>` si está configurado.
- `settings.json → local` guarda la **org activa** y el **autor activo** (referencia por id a
  un autor del `org.json`). Todos los comandos operan sobre la org activa salvo `--org <slug>`.

### Esquema de `org.json` (resumen)

```json
{
  "schema": 1,
  "slug": "slep-chinchorro",
  "nombre": "SLEP Chinchorro",
  "config": { "correlativo_inicio": { "2026": 1 }, "plantilla_default": "informe-ti" },
  "equipos": [ { "id": "ti", "nombre": "Unidad TI" } ],
  "autores": [
    { "id": "a1", "nombre": "…", "cargo": "…", "correo": "…", "equipos": ["ti"] }
  ],
  "documentos": [
    {
      "codigo_base": "TI-INF-SEG_2026-0023",
      "area": "TI", "tipo": "INF", "categoria": "SEG",
      "anio": 2026, "correlativo": 23,
      "titulo": "…", "autor_id": "a1", "equipo_id": "ti",
      "plantilla": "informe-ti",
      "ruta": "TI-INF-SEG_2026-0023",
      "creado": "…",
      "versiones": [
        { "version": "1.0.0", "fecha": "20260601", "creado": "…",
          "mensaje": "Versión inicial.", "snapshot": ".snapshots/TI-INF-SEG_2026-0023_v1.0.0.typ" }
      ]
    }
  ]
}
```

Las rutas de documentos en `org.json` son **relativas a `DOCS_ROOT/<org-slug>/`** (el nombre de
la carpeta del documento = `codigo_base`); las de plantillas, relativas a la carpeta de la org.
La ruta absoluta se deriva en tiempo de ejecución (portabilidad entre máquinas y SO).

---

## 3. Plantillas por organización

- Viven en `organizations/<org>/templates/<nombre>/` con al menos `lib.typ` e `Images/`.
- `config.plantilla_default` define cuál usa `doctyp new` si no se pasa `--plantilla`.
- Al crear/agregar un documento, **la plantilla se copia completa** a la carpeta del documento.
  Actualizar la plantilla de la org **no modifica documentos ya creados** (inmutabilidad por
  documento); para repropagar hay que hacerlo explícitamente.
- Fuentes: `fonts/` en la plantilla es opcional; **Museo Sans no se redistribuye** (licencia).
  Si falta, fallback a Liberation Sans; `doctyp compile` pasa `--font-path` si existe `fonts/`.

---

## 4. Documentos como carpeta

- Cada documento = carpeta `<Documentos>/doctyp/<org-slug>/<código-base>/` con: el `.typ`,
  la copia de la plantilla (`lib.typ`, `Images/`), `img/` para imágenes propias y `.snapshots/`
  con snapshots. El año ya viene codificado en el `código-base` (no hay subcarpeta por año).
- **Versionado sin git:** en cada `save`/`compile` se copia el `.typ` vigente a
  `.snapshots/<código-base>_v<versión>.typ` **antes** de subir la versión, y se añade la fila
  al `org.json` (fuente de verdad) y a `.snapshots/index.json` (espejo local de solo respaldo,
  mismo shape que `doc["versiones"]` — ver §14 Etapa 6). `history` lista las versiones del
  registro y marca cuáles tienen snapshot; `restore` extrae el snapshot a
  `<código-base>_v<versión>.typ` sin tocar jamás el vigente.
- Referencias en el `.typ` a imágenes propias: ruta relativa `img/<archivo>`.

---

## 5. CLI `doctyp` (Claude Code puede ejecutarlo)

Python estándar (sin dependencias), comando global `doctyp` (symlinks `ty`, `tp`, `dt`).
Sin argumentos muestra el menú interactivo (uso humano); Claude Code usa subcomandos.

### Organizaciones, equipos y autores

```bash
doctyp org new <slug> [--nombre "…"]     # crea organizations/<slug>/ (org.json + templates/) y <Documentos>/doctyp/<slug>/
doctyp org list                          # lista organizaciones (marca la activa)
doctyp org use <slug>                    # fija la org activa (settings.json)
doctyp team new <id> [--nombre "…"]      # crea equipo en la org activa
doctyp team list
doctyp author add                        # alta interactiva de autor (nombre, cargo, correo, equipos)
doctyp author list
doctyp author use <id>                   # fija el autor activo (settings.json)
```

### Plantillas

```bash
doctyp template add <ruta> [--nombre …]        # importa una carpeta de plantilla a la org activa
doctyp template list
doctyp template default <nombre>               # fija config.plantilla_default
doctyp template new <nombre> [--clonar-de …]   # clona otra plantilla, o el esqueleto base en blanco
doctyp template rm <nombre> [--y]              # elimina (bloquea si es la default o la única)
doctyp template save <nombre> --m "…"          # snapshot de lib.typ + registro de versión
doctyp template history <nombre>               # versiones de una plantilla y su snapshot
doctyp template restore <nombre> [--version N] # extrae una versión anterior de lib.typ
```

### Documentos

```bash
doctyp list  [--anio 2026] [--org <slug>]    # (alias: ls)  documentos + próximo correlativo
doctyp new   "Título" [--tipo INF] [--categoria SFW] [--plantilla <nombre>]   # (alias: n)
doctyp save  <doc-ref> --m "mensaje"         # (alias: s)   snapshot + bump patch + registro
doctyp add                                    # (alias: a)   importa un .typ del CWD como carpeta-documento
doctyp compile <doc-ref>                      # (alias: c)   snapshot + compila a PDF en la carpeta del doc
doctyp edit <doc-ref>                         # (alias: code, e, open)
doctyp history <doc-ref>                      # (alias: h, log) versiones y snapshots (✔/–)
doctyp restore <doc-ref> [--pdf] [--stdout]   # extrae versión desde .snapshots/ (nunca sobrescribe)
doctyp reset [<correlativo>]                  # inicio del correlativo del año (org activa)
```

### Web

```bash
doctyp web [--port 8787] [--host 127.0.0.1] [--no-browser]  # (alias: serve)
```

### Sintaxis doc-ref

```
<correlativo>[:<version>][@<año>]     # 39 · 39:1.2 · 39:1.2@2025 · 39@2025  (`/` ≡ `:`)
```

### Cómo lo usa Claude Code
1. `doctyp list` para conocer el próximo correlativo (informativo; no lo fijes a mano).
2. `doctyp new "…"` (ajusta `--tipo`/`--categoria`/`--plantilla` solo si difieren del default).
3. Abre el `.typ` de la carpeta creada y **rellena las secciones `// TODO`** (§8).
4. **No compiles** (§0, §10). Reporta el `codigo-completo` tras cada cambio.
5. Para subir versión: `doctyp save <doc-ref> --m "…"` (snapshot automático en `.snapshots/`).

---

## 6. `doctyp web` (alias `serve`)

- **Backend:** `http.server` de la stdlib (ThreadingHTTPServer). API JSON bajo `/api/…` +
  **SSE** (`/api/events`) para actualizaciones en tiempo real del árbol de carpetas y del
  registro. Sirve `web/dist/` como estáticos.
- **Arranque:** `doctyp web` levanta el servidor y **abre automáticamente el navegador**
  en la URL local (`webbrowser.open`, stdlib). `--no-browser` lo suprime (scripts/headless).
- **Frontend:** SPA **Vue 3** (Vite). Funcionalidad: **gestión completa (CRUD) de autores y
  equipos dentro de cada organización**, gestión de organizaciones y plantillas; explorador
  de carpetas de documentos en tiempo real; edición del `.typ` y metadatos;
  historial/restauración de versiones. Autores/equipos son metadatos organizativos (§2):
  la UI permite crearlos, asignarlos a documentos y filtrarlos, **sin** funciones
  multi-usuario. **Proyectos: funcionalidad futura** (solo placeholder en la UI).
- **Seguridad (obligatorio):** bind por defecto a `127.0.0.1`; toda ruta recibida por la API
  se resuelve y valida contra las **dos raíces permitidas** — `organizations/` (config +
  plantillas) y `DOCS_ROOT` (`<Documentos>/doctyp/`) — sin path traversal fuera de ellas;
  escrituras del registro atómicas; sin ejecución de comandos arbitrarios desde la API; la
  compilación vía web reutiliza exactamente la lógica de `doctyp compile`.
- Claude Code **no levanta el servidor por su cuenta** salvo petición explícita.

---

## 7. Nomenclatura documental

Patrón: `AREA-TIPO-CAT_AAAA-NNNN_vX.Y_AAAAMMDD` → p. ej. `TI-INF-SEG_2026-0023_v1.0_20260601`.

- **`NNNN` es secuencial global anual por organización** (4 dígitos), asignado por `doctyp`.
  No lo inventes.
- `codigo-base(meta)` = `TI-INF-SEG_2026-0023` · `codigo-completo(meta)` = con versión y fecha.
  Se imprimen solos (portada, ficha, footer, contraportada). No los escribas a mano.
- **Tipos:** INF Informe · MAN Manual · POL Política · PRO Procedimiento · PLA Plan ·
  EVL Evaluación · ETT Esp. Técnica · ACT Acta.
- **Categorías (3 letras):** SEG, RED, HRW, SFW, DAT, SRV, PRV, GOB, USR, CPD, BCK, PRY, CAP.

---

## 8. Estructura canónica del informe (orden obligatorio, manual §11.1)

| # | Sección | Cómo se genera |
|---|---|---|
| 1 | Portada | automática (`report`) |
| 2 | Ficha de control documental | `#s-ficha(meta)` |
| 3 | Control de versiones | `#s-versiones(meta, filas)` |
| 4 | Distribución | `#s-distribucion(filas)` |
| 5 | Tabla de contenido | `#s-indice()` |
| 6 | Resumen ejecutivo | `= Resumen ejecutivo` + prosa |
| 7 | Antecedentes y motivación | `= …` + `== Contexto institucional` / `== Problema o necesidad identificada` |
| 8 | Objetivo | `= …` + `== Objetivo general` / `== Objetivos específicos` |
| 9 | Alcance | `= …` + `== Dentro del alcance` / `== Fuera del alcance` |
| 10 | Marco normativo y referencial | `= …` + `== Normativa legal aplicable` / `== Estándares técnicos aplicables` |
| 11 | Metodología | `= …` |
| 12 | Desarrollo técnico | `= …` (cuerpo principal) |
| 13 | Análisis de impacto | `= …` + `== Confidencialidad` / `== Integridad` / `== Disponibilidad` |
| 14 | Conclusiones | `= …` |
| 15 | Recomendaciones | `= …` + `#tabla-prioridad(…)` |
| 16 | Glosario y acrónimos | `= …` + `#tabla(…)` |
| 17 | Referencias | `= …` |
| 18 | Anexos | `= Anexos` + `== Anexo X. …` (incl. `== Anexo B. Firmas` → `#firmas-estandar(meta)`) |
| 19 | Contraportada | automática (`meta.contraportada`) |

Los encabezados se numeran solos (`1`, `1.1`). `doctyp new` ya escribe todo este esqueleto.

> Nota: tras el retiro de git (Etapa 3), `s-ficha` ya no acepta `rama-git:` y la tabla de
> control de versiones ya no muestra tag por fila.

---

## 9. Metadatos (`meta`) — construir SIEMPRE con `crear-meta(...)`

Declara solo lo que cambia; el resto sale de los defaults de la plantilla.

| Clave | Ejemplo | Para qué |
|---|---|---|
| `area` `tipo` `categoria` | `"TI"` `"INF"` `"SEG"` | Código documental (§7) |
| `anio` `correlativo` `version` `fecha-codigo` | `2026` `23` `"1.0"` `"20260601"` | Código documental |
| `tipo-largo` | `"Informe Técnico"` | Rótulo superior de la portada |
| `titulo` `subtitulo` | — | Portada |
| `estado` | `BORRADOR` \| `EN REVISIÓN` \| `APROBADO` | Badge (verde si aprobado) |
| `clasificacion` | `PÚBLICO` \| `INTERNO` \| `RESERVADO` \| `CONFIDENCIAL` | Badge + contraportada |
| `autor` `cargo-autor` `correo-autor` | — | Ficha + firmas (Elaborado). Se rellenan desde el autor activo (`org.json`). |
| `revisor` `cargo-revisor` | — | Ficha + firmas (Revisado) |
| `aprobador` `cargo-aprob` | — | Ficha + firmas (Aprobado) |
| `contraportada` | `true` (def.) | `false` para omitirla |

Ya vienen por defecto (no repetir salvo cambio): `unidad`, `subdireccion`, `institucion`,
`comunas`, `correo-inst`, `sitio-inst`, `logos.slep`, `logos.isologo`.

---

## 10. Compilar (lo hace el usuario, de forma manual)

**Claude Code no ejecuta esto por su cuenta** (§0) salvo petición explícita.

```bash
doctyp compile 23        # snapshot + compila; PDF junto al .typ en la carpeta del documento
```

A mano (desde la carpeta del documento; el import es local, sin `--root`):

```bash
typst compile --font-path fonts TI-INF-SEG_2026-0023.typ
typst watch  TI-INF-SEG_2026-0023.typ      # modo redacción
```

- Requiere **Typst ≥ 0.12**. Museo Sans si está disponible; fallback Liberation Sans.
- En **Fedora/Flatpak** (sandbox de VS Code), usa `flatpak-spawn --host typst …` con archivos
  bajo `$HOME`. `doctyp compile` ya elige la invocación correcta.

---

## 11. API de la plantilla (todo exportado por `lib.typ`)

**Estructura / secciones**
- `crear-meta(dict)` — construye `meta` (defaults + overrides). Úsalo siempre.
- `report` — `#show: report.with(meta:)`. Estilos + portada + contraportada.
- `s-ficha(meta)` · `s-versiones(meta, filas)` · `s-distribucion(filas)` · `s-indice()`.
- `firmas-estandar(meta)` — firmas tripartitas desde `meta`.

**Componentes**
- `tabla(columns:, headers, rows)` — tabla cebra con cabecera marino.
- `tabla-kv(filas)` — 2 columnas etiqueta/valor.
- `tabla-prioridad(filas)` — filas = `(n, recomendación, "Alta"|"Media"|"Baja", responsable)`.
- `aviso(tipo:, titulo:, cuerpo)` — `tipo` ∈ `"info"` `"advertencia"` `"riesgo"` `"recomendacion"`.
- `firmas(lista de (rol, nombre, cargo))` — firmas personalizadas.
- `indice()` · `badge-estado(s)` · `badge-clasificacion(c)` · `codigo-base/completo(meta)`.

**Tokens de color** (usos puntuales, no para redefinir el estilo): `marino`, `azul-acento`,
`rojo-acento`, `verde`, `gris-texto`, `gris-borde`, `fondo-label`, `fondo-cebra`, `prio`.

---

## 12. Flujo de co-redacción con el usuario

Cuando el usuario diga "redactemos un informe sobre X":

1. **Identifica `--tipo` y `--categoria`** (§7) y confirma autoría solo si difiere del autor activo.
2. **Crea el documento con el generador:** `doctyp new "<título>"` (asigna correlativo y crea la
   carpeta autocontenida con la plantilla copiada).
3. **Rellena las secciones `// TODO`** siguiendo la estructura canónica (§8) y la API (§11).
   Imágenes propias del documento → `img/`.
4. **No compiles tú** (§0, §10): deja el `.typ` listo y avisa. El usuario compila con
   `doctyp compile <doc-ref>` cuando quiere revisar; itera sección por sección.
5. Para subir versión sin compilar: `doctyp save <doc-ref> --m "<qué cambió>"` — snapshot en
   `.snapshots/`, bump del patch, fila en `s-versiones`, registro en `org.json`. Reporta el
   `codigo-completo`.

Sugerencia: deja `typst watch <archivo>.typ` corriendo (desde la carpeta del documento).

---

## 13. Edge cases

| Síntoma | Causa | Solución |
|---|---|---|
| `dictionary does not contain key "…"` | `meta` parcial pasado a un helper | Construye `meta` con `crear-meta(…)` |
| `file not found (Images/…)` o import en rojo | la carpeta del documento no tiene la plantilla copiada | Verifica que `lib.typ` e `Images/` estén en la carpeta del documento; re-copia desde `templates/` si faltan |
| Recuadros de logo vacíos | faltan los PNG reales en la plantilla | Copia los logos a `templates/<plantilla>/Images/` (docs nuevos) o a la carpeta del documento |
| Tipografía distinta al estándar | Museo Sans no disponible | Instálala localmente o `--font-path`; fallback Liberation Sans |
| Correlativo repetido o saltado | se asignó a mano o se editó `org.json` | Usa `doctyp`; nunca edites correlativos en `org.json` a mano |
| `restore` aborta | el archivo destino ya existe | Es intencional: `restore` nunca sobrescribe; renombra o borra el restaurado previo |
| `org.json` corrupto | escritura interrumpida (versiones antiguas) | Restaurar desde respaldo; las escrituras son atómicas desde la Etapa 1 |
| `doctyp: command not found` | `~/.local/bin` fuera del PATH | `export PATH="$HOME/.local/bin:$PATH"` en `~/.bashrc` |
| Portada numerada / doble contraportada | se alteró `report` | No edites `report`; no escribas portada/contraportada a mano |
| No encuentra la carpeta Documentos | `xdg-user-dir` ausente o `user-dirs.dirs` sin `XDG_DOCUMENTS_DIR` | Fallback automático a `~/Documents` (se crea); revisa que `DOCS_ROOT` impreso por `doctyp list` sea el esperado |
| El servidor web no responde en la red | bind por defecto a localhost | Es intencional (seguridad); usa `--host` solo bajo criterio del usuario |

---

## 14. Estado de implementación (roadmap por etapas)

Actualiza esta tabla al cerrar cada etapa. Mientras una etapa esté `Pendiente`, sus comandos
y estructuras **no existen** — no los uses ni los des por hechos.

| Etapa | Alcance | Estado |
|---|---|---|
| 1 | Núcleo de organizaciones: `organizations/` (config+plantillas), `org.json`, `org/team/author *`, resolución de `DOCS_ROOT` por SO, migración del registro a la org **`slep-chinchorro`** | **Completada** |
| 2 | Documentos-carpeta en `<Documentos>/doctyp/<org>/` + plantillas por org + copia de plantilla + versionado por snapshots (sin git) | **Completada** |
| 3 | Adaptación de comandos existentes, retiro de git, ajustes de plantilla (`rama-git`), escrituras atómicas | **Completada** |
| 4 | Backend `doctyp web`: API JSON + SSE + estáticos + auto-apertura del navegador | **Completada** |
| 5 | SPA Vue 3: CRUD de autores/equipos por org, orgs/carpetas/documentos + editor | **Completada** |
| 6 | Generacion de snapshots propios. Las versiones futuras se almacenaran en un sistema de control de versiones propio y simple dejando de lado git. generacion de snapshots, similar a git, con algoritmo propio y sistema de gestion de versiones propio pero simple. almacenar snapshots en: 'carpeta de cada documento > .snapshots' y acceder a ellos para verlos y hacer comparaciones (funcionalidad futura).  | **Completada** |
| 7 | Vista de documentos en formato de cuadricula como pantalla principal con una pequeña vista previa de la primera pagina de cada documento de su ultima compilacion o una compilacion temporal del documento actual. Barra de estado inferior indicando la version actual, con desplegable para seleccionar otras versiones y ver sus diferencias con la actual. Tambien la barra de estado indicara si hay cambios y tendra los botones para guardar y para hacer commit de una nueva version. Tambien indicara la cantidad de palabras y otra informacion relevante como tamaño de archivo y un boton para que typst compile. | **Completada** |
| 8 | La vista de documento solo se dividira en dos debajo del navbar: editor y vista previa. La App Web debe mostrar una vista previa del informe/doumento generado para poder editar y visualizar directamente en la interfaz de la misma manera que la app web typst. Se debe generar un compilado fresco on-demand cada vez para mostrar la vista previa, el archivo compilado no se guardara o se guardara de manera temporal con un nombre temporal en el directorio raiz del documento. | **Completada** |
| 9 | Editor de plantillas con CRUD completo y seleccion de plantilla en el modal al crear documento nuevo. Usar vista dividida: editor y vista previa similar a typst. Al editar una plantilla se debera mostrar un documento. Explorar otras soluciones de compilado/precompilado/vistaprevia/cache. | **Completada** |
| 10 | Editor de plantillas en el cliente web debe poder accederse desde pantalla principal con boton junto al boton 'organizacion' y la vista debe ser a pantalla completa como el editor de documentos. El editor de texto/codigo debe mostrar en colores los codigos/funciones/variables de typst como un editor de codigo moderno. La division por colores permite una mejor edicion para el usuario. Usar la convencion de colores de Typst y/o la que usa VSCode con la extension de Typst. | **Completada** |
| 11 | Cambiar renderizado de vista previa en el cliente web (editor documentos y editor plantillas) por un renderizado de typst WASM <typst.ts> dentro del cliente web. El editor debe seguir el documento cuando se haga click en el texto y lo mismo para la vista previa, al hacer click en una seccion o parrafo o titulo/encabezado el editor se debe mover hasta donde este el cursor en la vista previa. Renderizar en HTML <canvas> igual que la app web de typst. El boton de actualizar vista previa debe estar en la barra superior donde esta el nombre del archivo alineado a la derecha. | Pendiente |


**Nota sobre el alcance real de las Etapas 2 y 3** (decisión explícita, amplía lo descrito arriba):
- Todos los comandos (`new`, `save`, `compile`, `edit`, `add`, `delete`, `import`, `history`,
  `restore`, `change`) operan sobre `org.json` y el modelo de carpeta-documento con snapshots
  de archivo (en `.snapshots/` desde la Etapa 6; ver su nota más abajo). `settings.json["documentos"]` (espejo v2) quedó retirado; solo
  `cmd_config_author`/`cmd_reset` (legacy) siguen usando `settings.json` para preferencias
  locales (`local.author`, `local.correlativo_inicio`), sin relación con el registro de
  documentos.
- El único documento previo a la Etapa 2 (`TI-INF-SFW_2026-0001`) se migró al modelo de
  carpeta con `doctyp migrate` antes de retirar el subsistema git; ese comando y todo el
  código de tags/commits (`cmd_git_init`, `_git_snapshot`, etc.) se eliminaron por completo al
  no quedar ningún documento legacy pendiente. `TI-INF-RED_2026-0039` se migró manualmente
  (el comando `migrate` ya no existía) en la Etapa 4, incluyendo la normalización de sus
  referencias de imagen a `img/<archivo>` (antes usaba una carpeta `img-39/` en la raíz del
  repo, con rutas mezcladas absolutas/relativas). Ningún documento legacy queda huérfano.
- `lib.typ` ya no acepta `rama-git:` en `s-ficha` ni muestra tag por versión (ver nota de §8).
- Autoría multi-org: `doctyp author add/list/use` reemplaza a `config-author` (que queda
  marcado `[legacy v2]` en la ayuda, sin alias `author` para evitar el choque de nombres).

**Nota sobre el alcance real de la Etapa 4**:
- Backend implementado en `doctyp_web.py` (archivo nuevo junto a `doctyp.py`, importado
  perezoso desde el subcomando `doctyp web`/`serve`), no dentro de `doctyp.py` — mantiene el
  núcleo CLI enfocado en documentos y evita inflar un único archivo a +3000 líneas, sin dejar
  de ser stdlib puro (sin dependencias externas).
- La API (`/api/orgs`, `/api/orgs/<slug>/documentos/...`) envuelve funciones ya existentes
  del core (`cargar_org`, `guardar_org`, `buscar_doc_org_por_codigo`, `realizar_save_org`,
  `compilar_typ`); no reimplementa lógica de negocio en el handler HTTP.
- SSE en `/api/events` vía polling de mtimes cada 1.5s (sin inotify/watchdog, no son stdlib).
- Seguridad verificada: toda ruta de la API valida el `slug` con `_slug_valido()` y las rutas
  de filesystem con `_resolver_ruta_segura()` contra `organizations/`/`DOCS_ROOT` antes de
  cualquier ramificación por longitud de segmentos (se corrigió un caso donde una ruta con
  muchos segmentos podía caer directo a 404 sin pasar por la validación del slug).
- `web/dist/` (Etapa 5) aún no existe; mientras tanto el servidor sirve un placeholder HTML
  explicando que el backend está activo pero la interfaz no se ha construido.

**Nota sobre el alcance real de la Etapa 5**:
- SPA Vue 3 + Vite en `web/` (código fuente versionado; `web/node_modules/` y `web/dist/` en
  `.gitignore` — el build se genera con `npm install && npm run build`, no se commitea).
- Explorador + editor: lista de documentos de la org activa (tiempo real vía SSE), editor de
  texto crudo del `.typ` con Guardar/Subir versión/Compilar, historial de versiones con vista
  previa de snapshots y "cargar en editor" (equivalente funcional a `restore`, sin duplicar la
  semántica de archivo-nuevo-sin-sobrescribir del CLI: acá el usuario decide explícitamente si
  guarda lo cargado).
- Backend ganó un endpoint de solo lectura, `GET .../historia/<version>/contenido`, que no
  existía — necesario para la vista previa de una versión anterior sin escribir archivos.
- Crear documentos desde la web: `POST /api/orgs/<slug>/documentos` reimplementa la
  orquestación de `cmd_nuevo` (mismas funciones del core), pero **sin** el espejo legacy en
  cwd (`agregar_doctyp_json`) — no tiene sentido para un proceso de servidor sin relación con
  el documento.
- CRUD de autores/equipos: el CLI **nunca tuvo** `editar`/`eliminar` para autores ni equipos
  (solo `add`/`list`/`use`) — se agregaron como funciones de core nuevas (`autor_editar`,
  `autor_eliminar`, `equipo_editar`, `equipo_eliminar`, con sus `_crear`/`_buscar`), con
  validaciones que tampoco existían antes: no se puede eliminar un autor o equipo con
  documentos asignados; eliminar un equipo lo quita en cascada de los autores que lo tenían.
  `cmd_author_add`/`cmd_team_new`/`cmd_template_default` (CLI) se refactorizaron para reusar
  estas mismas funciones en vez de duplicar la lógica.
- Selector de autor activo en la topbar (pedido explícito del usuario): cambiarlo llama
  `POST .../autores/<id>/activar` (equivalente web de `doctyp author use`) y **filtra** el
  explorador de documentos a los del autor activo (`doc.autor_id`). Sin "ver todos" — es el
  comportamiento pedido; documentos sin `autor_id` que calce quedan invisibles hasta
  reasignarlos.
- Fuera de alcance, explícito: importar plantillas desde la web (`template add` necesita una
  ruta del filesystem del servidor; requeriría subida de archivos, una capacidad distinta,
  sigue siendo solo CLI) y eliminar organizaciones (destructivo/irreversible, no pedido).
- Metadatos estructurados: como no hay parser de Typst en el proyecto (deliberado, stdlib
  puro), `extraer_meta_typ`/`actualizar_meta_typ` editan el bloque `crear-meta((...))` por
  regex quirúrgica — mismo patrón que ya usaba `realizar_save_org` para `version:` y
  `#s-versiones`. Preserva los defaults de plantilla: si `revisor`/`aprobador` quedan vacíos y
  no existían en el `.typ`, no se insertan. El campo `titulo` se sincroniza también en
  `org["documentos"]` (evita que `DocList` quede desactualizado). El frontend resincroniza el
  editor de texto crudo con el contenido devuelto tras guardar metadatos, para que un
  "Guardar cambios" posterior no pise el patch con contenido viejo en memoria.

**Nota sobre el alcance real de la Etapa 6**:
- Solo el mecanismo de almacenamiento (decisión explícita del usuario): sigue siendo copias de
  archivo completo, sin direccionamiento por hash ni deduplicación tipo git real — lo único
  que cambia es la carpeta (`versions/` → `.snapshots/`) y que cada documento gana un índice
  local propio, `.snapshots/index.json` (mismo shape que `doc["versiones"]`), escrito por
  `escribir_indice_snapshots()` junto con cada `save`/`compile` y al crear el documento.
- **`org.json` sigue siendo la única fuente de verdad** — el índice local es un espejo de solo
  respaldo (documento autocontenido, sobrevive aunque `org.json` se pierda); ningún código de
  lectura en caliente (`history`, `restore`, la API web) fue modificado ni depende de él.
- "Ver y comparar" (diff entre versiones) queda explícitamente para la Etapa 7, que ya lo
  menciona.
- Los 2 documentos reales (`TI-INF-SFW_2026-0001`, `TI-INF-RED_2026-0039`) tenían carpetas
  `versions/` vacías (ningún `save` había llegado a generar un snapshot) — la migración fue
  crear `.snapshots/` y su `index.json` inicial, sin ningún archivo de snapshot que mover.

**Nota sobre el alcance real de la Etapa 7**:
- La edición del usuario a §14 separó lo que iba a ser una sola etapa en dos: esta Etapa 7 es
  cuadrícula + barra de estado; el panel dividido editor/vista previa en vivo (compilado
  fresco on-demand) quedó explícitamente para la Etapa 8 — **no** se construyó ningún
  renderizador de Typst en vivo en esta etapa.
- Miniatura de la cuadrícula: `generar_miniatura()` (`doctyp.py`) compila la página 1 con
  `typst compile --pages 1` a un PNG oculto junto al `.typ`
  (`.<código-base>.miniatura.png`), cacheado por mtime — no vuelve a invocar typst si la
  miniatura ya es más nueva que el `.typ`. Nunca toca el PDF real que genera "Compilar"
  (acción explícita del usuario, sigue igual). Documento nunca compilado o con error de
  compilación → la API devuelve 404 y el frontend cae a un placeholder ("Sin compilar aún"),
  sin bloquear la cuadrícula.
- Diff de versiones: nuevo, no existía — `api_doc_version_diff` usa `difflib.SequenceMatcher`
  (stdlib) entre el snapshot elegido y el `.typ` vigente, reusando
  `api_doc_version_contenido`/`api_doc_typ_get` ya existentes (no relee archivos aparte).
- Navegación: `App.vue` gana un estado simple `vista` (`grid`/`documento`), sin vue-router
  (no hacía falta deep-linking). La cuadrícula (`DocumentGrid.vue`) reemplaza a `DocList.vue`
  como pantalla principal; la nueva `StatusBar.vue` (barra fija al fondo del editor, con
  desplegable de versión + diff + contador de palabras/tamaño + Guardar/Subir versión/
  Compilar/Metadatos) reemplaza al toolbar de `DocEditor.vue` y a `HistoryPanel.vue`.
  `DocList.vue`/`HistoryPanel.vue` **no se borraron** (quedan sin usar, por si Etapa 8
  reutiliza algo) — evaluar limpieza cuando se confirme que no hace falta nada de ahí.
- Cantidad de palabras y tamaño de archivo se calculan en el cliente sobre el texto en
  edición (no sobre el archivo en disco), igual que el indicador de cambios sin guardar —
  quedan "vivos" mientras se escribe, sin ida y vuelta al servidor.

**Nota sobre el alcance real de la Etapa 8**:
- **No es un renderizador de Typst en WASM/navegador** (tipo `typst.ts`) — el texto del
  roadmap describe exactamente un compilado servidor con archivo temporal ("se guardará de
  manera temporal con un nombre temporal en el directorio raíz del documento"), así que se
  reutiliza `typst compile` (ya dependencia del proyecto) con el mismo patrón que
  `compilar_typ`/`generar_miniatura`.
- `compilar_vista_previa()` (`doctyp.py`) escribe el texto en edición (incluye cambios sin
  guardar) a un `.typ` temporal oculto junto al documento
  (`.<código-base>.preview.typ` → `.<código-base>.preview.pdf`) — **nunca toca el `.typ` real
  ni el PDF de "Compilar"**, y nunca cambia versión ni `org.json`. A diferencia de la
  miniatura, no cachea: recompila "fresco" en cada llamada, tal como pide el texto. Errores de
  compilación devuelven el `stderr` de typst tal cual (`ApiError(422, ...)`), mostrado en el
  panel de vista previa en vez de dejarlo en blanco.
- Gatillo de recompilación (decisión del usuario): **ambos** — debounce automático (~1.2s sin
  escribir, `VistaPrevia.vue`) y botón manual "Actualizar vista previa" que cancela el
  debounce pendiente para evitar una compilación en carrera.
- Render vía `<embed type="application/pdf">` con la salida real de typst (Object URL,
  revocado en cada reemplazo y al desmontar) — sin visor de páginas por imagen ni dependencias
  nuevas de PDF.js; el navegador se encarga del scroll/zoom.
- `DocEditor.vue` pasa de editor a ancho completo a un split de dos columnas
  (`.editor-preview-split`: textarea + `VistaPrevia.vue`), con `StatusBar` sin cambios,
  abarcando el ancho completo debajo del split.

**Nota sobre el alcance real de la Etapa 9**:
- Las plantillas son solo carpetas (`organizations/<org>/templates/<nombre>/`) — **nunca
  tuvieron** fila en `org["documentos"]` ni ningún otro registro en `org.json` más allá de
  `config.plantilla_default`. Su historial de versiones (nuevo en esta etapa) vive
  íntegramente en su propio `.snapshots/index.json`: a diferencia del mismo archivo para
  documentos (que es un respaldo de solo lectura, `org.json` manda), aquí **es la única fuente
  de verdad** — no hay otro lugar donde guardarlo. `guardar_version_plantilla()` (`doctyp.py`)
  snapshotea el `lib.typ` *actual* antes de sobrescribirlo (mismo principio de
  "cerrar la versión anterior" que `realizar_save_org`, pero sin `version:` embebido que
  bumpear — el número de versión vive solo en el índice).
- **"Al editar una plantilla se deberá mostrar un documento"** se resolvió generando, en
  memoria/disco oculto, un documento de muestra ficticio (`_muestra_meta()` +
  `build_typ()`) que importa el `lib.typ` de la plantilla — y delegando la compilación
  íntegramente a `compilar_vista_previa()`/`generar_miniatura()` de la Etapa 8 (ninguna de
  las dos se modificó). `compilar_vista_previa_plantilla()` escribe el `lib.typ` en edición a
  un archivo oculto paralelo (`.<nombre>.preview.lib.typ`) para no pisar jamás el real;
  `generar_miniatura_plantilla()` mantiene un `.typ` de muestra persistente (importa el
  `lib.typ` real) cacheado por mtime, igual que la miniatura de documento.
- **"Crear" una plantilla siempre es clonar algo** (decisión explícita) — `lib.typ` es código
  Typst completo (~350 líneas: paleta, portada, todas las funciones del API de §11); no existe
  un "crear desde cero" real. La opción "en blanco" clona `templates_base/minimal/lib.typ`, un
  esqueleto nuevo (fuera de `organizations/`, junto a `doctyp.py`) que implementa el mismo API
  público sin marca institucional ni imágenes (evita necesitar logos placeholder).
- Eliminar una plantilla (`plantilla_eliminar`, CLI `template rm` / `DELETE
  .../plantillas/<nombre>`) se bloquea si es la `plantilla_default` de la org o si es la única
  plantilla que queda — la org siempre necesita al menos una para `doctyp new`. Documentos ya
  creados con una plantilla eliminada no se ven afectados (la plantilla se copia completa a
  cada documento al crearlo, §3 — inmutabilidad ya existente, no tocada por esta etapa).
- El editor de plantillas (`TemplateEditor.vue`) es un overlay propio (`.modal-box-editor`)
  lanzado desde la pestaña "Plantillas" de `OrgManager.vue` (nota: en la Etapa 10 pasó a ser
  una vista de primer nivel de `App.vue`, ver más abajo). Reusa `VistaPrevia.vue` (Etapa 8) tal
  cual, generalizado con una prop opcional `compilar-fn` (por defecto `compilarVistaPrevia`,
  sin cambio de comportamiento para `DocEditor.vue`) para inyectar
  `vistaPreviaPlantilla` sin duplicar el componente.
- Sin diff de versiones para plantillas (a diferencia de documentos, que sí lo tienen desde la
  Etapa 7) — se dejó fuera de alcance; el historial permite ver/cargar una versión anterior en
  el editor, no compararla línea a línea. El selector de plantilla en `NewDocumentModal.vue`
  ahora se muestra siempre que la org tenga ≥1 plantilla (antes solo con >1).

**Nota sobre el alcance real de la Etapa 10**:
- **Sin paquete de resaltado Typst maduro para CodeMirror 6** — se investigó
  `codemirror-lang-typst` (kxxt): experimental, bindings WASM sin documentación de uso y sin
  releases estables, descartado explícitamente. En su lugar, `web/src/codemirror/typst-lang.js`
  define un modo propio con `StreamLanguage.define(...)` (mecanismo estándar de
  `@codemirror/language` para tokenizers simples estilo regex/estados, sin gramática Lezer
  completa): comentarios `//`/`/* */`, strings, encabezados `=`/`==` (solo fuera de modo
  código), palabras clave tras `#` o dentro de una expresión de código, e identificadores
  seguidos de `(`/`[` coloreados como nombre de función (`variableName.function` vía tags
  reales de `@lezer/highlight`, no la tabla de compatibilidad "legacy" de CM5 — se usan
  directamente `tags.comment`, `tags.keyword`, `tags.heading`, etc.). Verificado con Playwright
  (colores computados por pantalla, no solo lectura de código) contra `lib.typ` real y un
  documento real: los 7 tipos de token (comentario, string, heading, keyword, function,
  variable, bracket/puntuación) renderizan con el color esperado.
- `web/src/components/CodeEditor.vue` (nuevo, wrapper único reusado por `DocEditor.vue` y
  `TemplateEditor.vue` vía `v-model` — evita duplicar el setup de CodeMirror): historial nativo
  (undo/redo), `lineWrapping`, numeración de línea. Reemplaza el `<textarea class="editor-
  textarea">` en ambos editores; el contenedor conserva la clase `editor-textarea` (ahora sobre
  un `<div>` host) para no tocar el layout flex ya existente en `.editor-preview-split`.
- **El editor de plantillas deja de ser modal**: `TemplateEditor.vue` pasa de
  `.modal-backdrop`/`.modal-box-editor` a `.panel-editor` (mismas clases que `DocEditor.vue`,
  sin CSS nueva) y cambia sus emits de `cerrar`/`guardado` a `sucio-cambio`/`guardado` — la
  navegación de "volver" y la confirmación de cambios sin guardar ahora las maneja `App.vue`,
  igual que ya hacía con el editor de documentos.
- **Plantillas pasa a ser una vista de primer nivel**: nuevo botón "Plantillas" en la topbar
  (`App.vue`, junto a "⚙ Organización"), nuevos valores de `vista`
  (`"plantillas"`/`"plantilla"`, además de `"grid"`/`"documento"`) y `PlantillaGrid.vue` (nuevo,
  mismo patrón que `DocumentGrid.vue`, reusando sus clases `.tarjeta-doc`/`.tarjeta-miniatura`).
  La pestaña "Plantillas" de `OrgManager.vue` (Etapa 9) se eliminó por completo —
  `OrgManager.vue` vuelve a tener solo Autores/Equipos; `NewTemplateModal.vue` (Etapa 9, sin
  cambios) ahora se monta desde `App.vue`.
- Verificación: se instaló Playwright + Chromium temporalmente (fuera del repo, en el `/tmp`
  del host) para levantar `doctyp web` en un puerto separado (8799) y navegar la app real
  end-to-end con capturas de pantalla — no quedó ninguna dependencia nueva ni archivo temporal
  en el repositorio ni en `organizations/`.

---

## 15. TL;DR para Claude Code

1. No toques el estilo de `lib.typ` sin orden explícita.
2. Verifica §14 antes de usar comandos v3; si la etapa está pendiente, aplica el flujo anterior.
3. Crea informes con `doctyp new "…"` (correlativo automático por organización; carpeta
   autocontenida con plantilla copiada). Sube versión con `doctyp save <doc-ref> --m "…"`.
4. Rellena los `// TODO` según la estructura canónica (§8) y la API (§11).
5. **No compiles automáticamente** ni levantes `doctyp web` sin petición explícita.
6. Nunca inventes correlativos ni edites `org.json` a mano.