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
doctyp web [--port 8787] [--host 127.0.0.1] [--no-browser] [--no-build] [--legacy-preview]  # (alias: serve)
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
- **Arranque:** `doctyp web` primero compila la SPA (`npm install` si falta `web/node_modules`,
  luego `npm run build` sobre `web/`) y después levanta el servidor, **abriendo automáticamente
  el navegador** en la URL local (`webbrowser.open`, stdlib). El build se omite solo si no hay
  `npm` en el PATH, si falta `web/package.json`, o si se pasa `--no-build` (usa `web/dist/` tal
  cual, o el placeholder). `--no-browser` suprime la apertura del navegador (scripts/headless).
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
- **Vista previa (Etapa 15, extendida tras cerrarla):** tanto el editor de **documentos** como
  el editor de **plantillas** usan `tinymist preview` como servidor standalone (subproceso
  supervisado por `doctyp_preview_server.py`), con clic↔cursor bidireccional real y
  **autoguardado a 300 ms** (Etapa 16 Fase 3 — ver más abajo; reemplaza la "memoria en vivo" y
  el "salto explícito con botón/Ctrl+Alt+J" que tenía la Etapa 15 original: el jump editor→
  preview ahora es automático al clic, sin botón) — ver la nota de la Etapa 15 en §14 para el
  protocolo/arquitectura base, y la de la Etapa 16 para lo que cambió después. Degrada
  automáticamente a la vista previa typst.ts (Etapa 12) por editor si `tinymist` no está
  instalado, o si se pasa `--legacy-preview`. Indicador de estado de compilación en vivo
  (Compilando/OK/Error) y de guardado ("Guardando…"/"Guardado ✓ hh:mm:ss") en ambos editores.
- **LSP de tinymist (Etapa 16, Fases 1A-1D completadas):** `doctyp web` gestiona un proceso
  único `tinymist lsp` por sesión (`doctyp_lsp_server.py`, framing `Content-Length` por stdio),
  expuesto al navegador vía `GET /api/lsp` (WebSocket propio, `doctyp_ws_server.py` — RFC 6455
  servidor, sin dependencias externas) y consumido en `CodeEditor.vue` con el paquete oficial
  `@codemirror/lsp-client` + extensiones propias (`web/src/lsp/`). Diagnósticos, autocompletado,
  hover, signature help, ir a definición/referencias, rename, formatear (Ctrl+Shift+F),
  esquema del documento (botón "≡"), quick-open de símbolos (Ctrl+T), folding, expandir/
  contraer selección (Alt+↑/↓), semantic tokens, inlay hints (toggle), colores con selector,
  code actions (Ctrl+.) y exportación rápida (PDF/texto/markdown, menú en la barra de estado)
  — todo con degradación automática si `tinymist` no está disponible (el editor sigue
  funcionando con el resaltado StreamLanguage de la Etapa 10). La vista previa (arriba) sigue
  siendo un proceso `tinymist preview` aparte, decisión deliberada — ver Fase 1E en §14.
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
| `doctyp web` avisa "No se encontró el binario 'tinymist'" aunque ya lo instalaste | El terminal integrado de VS Code corre en un sandbox Flatpak cuyo `PATH` no incluye `~/.local/bin` (mismo problema que `typst`, §10) | Ya resuelto: `find_tinymist()` (`doctyp_preview_binary.py`) revisa `~/.local/bin/tinymist` como fallback aunque no esté en el `PATH` del sandbox (Etapa 16). Si persiste, corre `doctyp web` desde una terminal fuera del sandbox, o fija `local.preview_tinymist_path` en `settings.json` |

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
| 11 | Cambiar renderizado de vista previa en el cliente web (editor documentos y editor plantillas) por un renderizado de typst WASM (typst.ts) dentro del cliente web, a HTML `<canvas>`, con el mismo botón de actualizar vista previa en la barra de estado. Sin click-to-jump (ver Etapa 12). | **Completada** |
| 12 | Sincronización bidireccional clic↔cursor entre el editor y la vista previa (click-to-jump) vía typst.ts/canvas en el navegador. **Reemplazada por la Etapa 15** (ver nota debajo de la tabla): 12.1-12.4 quedan como historial (canvas→SVG, bloqueo de `data-span`, scroll sync ya retirado en 15/F7); 12.2/12.3 (clic↔cursor) se resolvieron por una vía distinta (servidor `tinymist preview` standalone, no typst.ts en el navegador). Aplica solo cuando un editor cae al modo legacy typst.ts (tinymist no instalado, o `--legacy-preview`) — por defecto, tanto documentos como plantillas usan el motor de la Etapa 15 (ver su addendum "plantillas ya no quedan fuera"). | Reemplazada por Etapa 15 |
| 13 | FIX. En el canvas de renderizado no puede hacerse scroll horizontal, el documento debe ocupar todo el espacio en ese eje. | Pendiente (aplica solo al modo legacy typst.ts, ver Etapa 15) |
| 14 | FIX. El debounce no debe re-renderizar el documento sino guardar el documento en caso que tenga cambios. Si el documento tiene cambios se guarda y despues de guardar se re-renderiza el documento. | Pendiente (aplica solo al modo legacy typst.ts, ver Etapa 15) |
| 15 | Preview vía servidor standalone (`tinymist preview`) lanzado por `doctyp`: clic↔cursor bidireccional real, memoria en vivo (sin guardar), salto explícito editor→preview, eliminación del scroll sync automático (Etapa 12.4). Ver nota debajo de la tabla y `plan15_progreso.md` (registro completo de la ejecución, incluye hallazgos de protocolo y bugs corregidos). | **Completada** |
| 16 | Auditoría y plan de continuación sobre la Etapa 15 (`tinymist-implementation-plan.md`, en la raíz del repo): Fase 2 (robustez de la preview, sin decisiones) → Fase 3 (fix clic→archivo equivocado, jump automático al clic sin botón, autoguardado a 300 ms) → Fase 1 (adopción completa de `tinymist lsp`: diagnósticos, completion, hover, navegación, semantic tokens, rename, formateo, exportadores rápidos). Decisiones ya tomadas por el usuario: LSP al 100 %, sin pestaña de `lib.typ` en el editor de documentos, sí exportadores rápidos, autoguardado 300 ms (documentos **y plantillas**, decidido 2026-07-14), jump automático e implícito al clic, y (2026-07-14) mantener la preview en su propio proceso en vez de unificarla bajo el LSP (Fase 1E). Ver nota debajo de la tabla para el detalle de lo ejecutado. | **Completada** (Fase 1E: decisión explícita de no migrar, ver nota) |
| 17 | Serie de mejoras de UX pedidas directamente por el usuario (2026-07-15, sin documento de plan previo): atajos en el editor de código (Ctrl/Cmd+S guarda, Tab indenta); imágenes propias de **documentos** (antes solo plantillas tenían gestión de imágenes); split editor/vista previa 60/40 (antes 50/50); **router de la SPA** (`vue-router`: `/documentos`, `/plantillas`, `/organizacion`) con página completa de gestión de organización (reemplaza el modal `OrgManager.vue`); **sidebar de archivos de solo lectura** con gestión de imágenes integrada (subir/renombrar/eliminar, reemplaza por completo el modal de imágenes agregado en esta misma etapa). Ver nota debajo de la tabla. | **Completada** |
| 18 | **Docker** (PLAN-V4.md §2, §7): Dockerfile + docker-compose.yml + compose.override.yml, sin puerto publicado (Traefik descubre el servicio por red compartida). Ver PLAN-V4.md §7 para el detalle de la ejecución (2026-07-17) — el túnel de preview de tinymist bajo `/preview/…` queda pendiente. | **Completada** (parcial, ver PLAN-V4.md §7) |
| 19 | **Registro en SQLite** (PLAN-V4.md §3, §7): `doctyp_db.py` reemplaza `org.json` como fuente de verdad de organizaciones/equipos/autores/documentos/versiones/correlativos; `doctyp migrate` (+ `--check`) archiva los JSON como `*.migrated`. **A partir de aquí, toda referencia a `org.json` en este documento (§0, §1, §2, §4, etc.) es histórica** — el registro vive en `doctyp.db`, ver PLAN-V4.md §3/§7 para el detalle. | **Completada** (2026-07-17, ver PLAN-V4.md §7) |
| 20 | **Login básico** (PLAN-V4.md §4, §7): `doctyp_auth.py`, scrypt, sesiones por cookie, bootstrap (sin usuarios → alta del primer usuario; único usuario sin password → fijarla en el primer login). Alcance recortado respecto al plan original (sin `api_tokens`, sin roles/admin en la SPA, sin invitaciones) — ver PLAN-V4.md §7 para el detalle y lo que falta. | **Completada** (alcance reducido, ver PLAN-V4.md §7) |
| 21 | **Icono de bandeja del sistema** para `doctyp_sync_daemon.py` (pedido explícito del usuario, 2026-07-21, Fedora/KDE Plasma, extendido 2026-07-22): tooltip y menú con usuario logueado y último documento/plantilla sincronizado (nombre, tamaño, fecha/hora); submenú "Cambiar de usuario" (siempre pide contraseña, ver nota) y "Cerrar sesión". El daemon posee el icono directamente (mismo proceso, sin IPC), vía `PySide6` (Qt) — degrada a headless si falta la dependencia o no hay sesión gráfica. Ver notas debajo de la tabla. | **Completada** (ver notas — verificación visual/clics reales en KDE pendiente por el usuario) |
| 22 | **Sincronización consciente de renombres** (pedido explícito del usuario, 2026-07-22): renombrar un documento (`doctyp change`) o una imagen dentro de su carpeta (a mano, en el explorador de archivos) ya no se sincroniza como "borrar + crear nuevo" — se propaga/detecta como el renombre que es, sin duplicar ni dejar huérfanos. Alcance: solo documentos (plantillas fuera de alcance, confirmado con el usuario). Ver nota debajo de la tabla. | **Completada** (verificado end-to-end con un servidor de prueba real, ver nota) |
| 23 | **Sincronización consciente de eliminaciones** (pedido explícito del usuario, 2026-07-22, extiende la Etapa 22): eliminar una imagen dentro de la carpeta de un documento (local o remoto) ya no la deja huérfana en el otro lado ni la resucita en el próximo sync — se mueve a una carpeta `.trash/` (nunca se borra de verdad) para poder recuperarla a mano. Requirió agregar una referencia local de "última vez que ambos lados estuvieron de acuerdo" (`.ultimo-sync.json` por documento) — sin eso no se puede distinguir de forma segura un archivo eliminado de uno genuinamente nuevo. Ver nota debajo de la tabla. | **Completada** (verificado end-to-end con un servidor de prueba real, ver nota) |


**Nota sobre el alcance real de la Etapa 12** (investigación hecha leyendo el paquete instalado
— `node_modules/@myriaddreamin/**/*.mjs`, `strings` sobre los `.wasm` — Y verificando cada
hipótesis con Playwright real contra `doctyp web`, no solo por lectura de código):

- **12.1 completada.** `renderToCanvas` (Etapa 11) es canvas puro: no adjunta ninguna
  posición-fuente a los píxeles, así que no hay forma de mapear clic→cursor con ese modo. Se
  reemplazó por `renderer.renderSvg({artifactContent})` (`client.js`, `_compilarYRenderizar` →
  `renderEnContenedor`), que retorna un string SVG completo (`<svg class="typst-doc">` con un
  `<g class="pagina-typst">` por página, clase agregada a mano tras insertar el SVG) e
  `innerHTML` sobre el contenedor. Verificado con Playwright que el resultado visual es
  equivalente al canvas anterior en documento real y en plantilla (capturas descartadas tras
  validar, no quedaron en el repo).
  - **Se descartó `renderToSvg`** (la variante que manipula el `container` real directamente
    desde Rust, en vez de retornar un string): panickea de forma reproducible en
    `@myriaddreamin/typst-ts-renderer@0.7.x` (`Option::unwrap() on a None value` en
    `render/svg.rs:132`), deja la sesión WASM corrupta (`attempted to take ownership of Rust
    value while it was borrowed` en la siguiente llamada) y el contenedor queda oculto por
    `error.value` con ese mensaje. `renderSvg` (string + `innerHTML` manual) evita ese código y
    no ha mostrado el problema.
  - **Se descartó el modo `renderDom`/`mount_dom`** (viewport incremental): confirmado con
    Playwright que sin implementar el protocolo completo de actualización incremental
    (`doc.addChangement(['new'|'diff-v1', artefacto])` seguido de `doc.addViewportChange()`,
    ver `contrib/dom/typst-doc.mjs`) el documento nunca se pinta — se queda en
    `moduleInitialized=false` para siempre (log `"viewport-change before initialization"`),
    incluso pasando `artifactContent` directo en `renderDom(...)`. Ese modo está diseñado para
    servir diffs incrementales desde un servidor en vivo, no para "aquí está todo el artefacto,
    píntalo de una vez" (nuestro caso).
- **12.2 (clic→cursor) BLOQUEADA — causa raíz confirmada, no es cuestión de configuración.**
  Se probó exhaustivamente contra el wrapper npm (todo verificado con Playwright real, no solo
  lectura de código): `renderSvg`/`renderToSvg` con compilación simple; la misma compilación
  envuelta en `compiler.withIncrementalServer(srv => { srv.setAttachDebugInfo(true); ... })`
  (el único método de "debug info" expuesto, en `IncrementalServer`); y `renderDom` completando
  correctamente su protocolo de inicialización (`renderer.runWithSession({format, artifactContent}, session => { renderDom({renderSession: session, container}); doc.addChangement(['new', artifactContent]); doc.addViewportChange(); ... })`
  — todo dentro del callback de `runWithSession`, porque la sesión se libera apenas ese
  callback retorna). En los tres casos solo aparecen `data-tid` (identidad para diffing) y
  `data-hint`, nunca `data-span`. Se probó también actualizando a `@myriaddreamin/typst-ts-*@0.8.0-rc3`
  (el más reciente publicado, vía `npm install --no-save` en un entorno aislado) — mismo
  resultado. El intento de `renderDom` además reveló dos panics de Rust reproducibles y
  distintos (`Option::unwrap() on a None value` en `render/svg.rs:132` vía `renderToSvg`, y
  `Result::unwrap() on an Err value` + trap `unreachable` en `crates/conversion/vec2dom/src/dom.rs:91`
  vía el modo DOM), en ambas versiones probadas — el modo DOM no es seguro de usar en este
  wrapper para nuestro caso (compilación puntual, no servidor incremental en vivo).
  **Causa raíz encontrada clonando el repo fuente** (`github.com/Myriad-Dreamin/typst.ts`,
  clon superficial `--depth 1`, revisado y borrado tras la investigación): el atributo
  `data-span` lo escribe `attach_debug_info()` en
  `crates/conversion/vec2svg/src/backend/mod.rs:558-561`, condicionado a
  `ctx.should_attach_debug_info()`, que a su vez depende de la constante de compilación
  `Feat::SHOULD_ATTACH_DEBUG_INFO`. Esa constante está **hardcodeada a `false` en las cuatro
  implementaciones de `ExportFeature` que existen en el repo** (`vec2svg/src/lib.rs` ×2,
  `vec2svg/src/frontend/incremental.rs`, `vec2dom/src/svg_backend.rs`) — tanto para el backend
  SVG como para el DOM. No es una opción de runtime: es imposible de activar desde JS contra el
  binario publicado en npm, sin importar la API usada. El script `typstProcessSvg` (que sí sabe
  leer `data-span`, visto embebido en el propio `.wasm`) es código vestigial de una build
  distinta a la publicada.
  **Vías para desbloquear** (ninguna intentada aún): (a) compilar el WASM desde un fork de Rust
  con ese `const` en `true`; (b) abrir issue/PR upstream pidiendo exponerlo en runtime; (c)
  resolver clic→cursor con la misma técnica de metadata+`query()` planeada para 12.3
  (aplicada también en esta dirección, en vez de solo cursor→preview).
- **12.3 (cursor→preview)**: sigue siendo válida la vía de metadata por párrafo +
  `compiler.query({selector})` (confirmado que `query()` existe en el wrapper, aunque no se ha
  probado en la práctica todavía) — no depende de `data-span`, así que no está bloqueada por el
  hallazgo de arriba.
- **12.4 completada.** Scroll sincronizado "a la par" (misma posición relativa, misma
  velocidad) entre el editor de código y la vista previa, en ambas direcciones, con rueda del
  mouse o barra de scroll. Implementado en `web/src/composables/useScrollSync.js`: sincroniza
  por **fracción de scroll** (`scrollTop / (scrollHeight - clientHeight)`), no por píxeles 1:1,
  porque el editor (texto plano) y la vista previa (documento paginado) casi nunca tienen la
  misma altura total — igualar la fracción es la única forma de que ambos paneles lleguen al
  inicio/final juntos. Guarda anti-loop simple (`origen`) para que el eco del scroll
  sincronizado no dispare un segundo ciclo. `CodeEditor.vue` expone `getScroller()` →
  `EditorView.scrollDOM` (API real de CodeMirror 6, confirmada en sus `.d.ts`);
  `TypstCanvasPreview.vue` expone `getScroller()` → el mismo `<div ref="contenedor">` donde se
  inyecta el SVG (ya tiene `overflow:auto`, no hizo falta un elemento nuevo). Cableado en
  `DocEditor.vue` y `TemplateEditor.vue`. Detalle importante: en ambos editores los hijos
  `CodeEditor`/`TypstCanvasPreview` están detrás de un `v-if` (`!codigo` en `DocEditor`,
  `cargando` en `TemplateEditor`) que en el primer render los mantiene fuera del DOM — conectar
  los listeners solo en `onMounted` del padre no alcanza; hace falta además un `watch` sobre la
  condición que los revela (`props.codigo` / `cargando`) con `nextTick` antes de reconectar.
  Verificado con Playwright: sincronización en ambas direcciones con diferencia de fracción
  ~0.00003–0.00008 (redondeo de píxeles del navegador, no un defecto) en documento real y en
  plantilla.
- **12.5**: pulido y verificación final, incluida una revisión de si el cambio a `renderSvg`
  afecta el tiempo de "primer vistazo" optimizado en la Etapa 11 (el cache de artefactos WASM
  sigue aplicando sin cambios; solo cambió la etapa de *render* final).
- **⚠ Retirado en la Etapa 15 (F7)**: el scroll sync de 12.4 (`useScrollSync.js`,
  `getScroller()` en `CodeEditor.vue`/`TypstCanvasPreview.vue`) se **eliminó por completo** del
  editor de documentos al migrar a tinymist, y también del editor de plantillas (aunque siga en
  typst.ts) porque el motivo original — "se desfasa respecto al contenido renderizado" — aplica
  igual ahí. No queda código de esto en el repo; ver Etapa 15 más abajo.

**Nota sobre el alcance real de la Etapa 15** (`tinymist preview` como servidor standalone de
vista previa; investigación y ejecución completas en `plan15_notas.md`/`plan15_progreso.md` —
ambos archivos de trabajo, no forman parte del código, conservar o borrar a criterio del
usuario):
- **Arquitectura real**: `doctyp_web.py` lanza y supervisa `tinymist preview` (nuevos módulos
  `doctyp_preview_binary.py` — localización/versión del binario — y `doctyp_preview_server.py` —
  ciclo de vida del subproceso, reintentos, puertos). El **control plane** (WebSocket JSON de
  navegación) lo mantiene vivo el **backend**, no el navegador — decisión explícita del usuario
  tras confirmar que `tinymist preview` se autoapaga por completo si esa conexión se cierra. El
  bridge hacia el frontend reusa el mecanismo SSE ya existente (`/api/events`), no expone un
  WebSocket nuevo.
- **Cliente WebSocket propio** (`doctyp_ws_client.py`): el proyecto es stdlib puro (sin
  dependencias externas) y Python no trae cliente WS, así que se implementó uno mínimo (RFC
  6455: handshake + framing de frames de texto/binario/ping-pong/close) en vez de agregar una
  dependencia — decisión confirmada con el usuario.
- **Protocolo real** (confirmado contra `tinymist 0.15.2`, no asumido): dos WebSockets —
  *data plane* (mismo puerto sirve también el HTML estático del preview; framing binario
  `"<prefijo>,<payload>"`) y *control plane* (JSON `{"event": "...", ...}`). Clic→cursor:
  el frontend embebido de tinymist manda `src-point {page_no,x,y}` por el data plane → el
  servidor resuelve y responde `editorScrollTo {filepath,start:[fila,col],end:[...]}` (0-based)
  por el control plane. Editor→preview: `panelScrollTo {filepath,line,character}` por el control
  plane → `jump "<pagina> <x> <y>"` (texto plano, no JSON) por el data plane.
  `changeCursorPosition` está deshabilitado server-side ("temporarily disabled to improve
  overall performance") — no se implementó, no tiene efecto en esta versión.
- **Puertos**: `tinymist preview` sin flags de host explícitos NO garantiza puertos libres
  entre instancias (se probó: dos instancias simultáneas intentaron los mismos puertos "por
  defecto" y colisionaron) — `doctyp_preview_server.py` sondea puertos libres reales
  (`socket.bind(("127.0.0.1", 0))`) y los pasa explícitos. Además, `tinymist` hace `.unwrap()`
  sobre el bind del socket y aborta con SIGABRT (no error recuperable) ante cualquier colisión
  — de ahí la importancia de evitarla, no solo manejarla después.
- **Endpoints nuevos en `doctyp_web.py`**: `GET /api/preview/info?slug=&codigo=` (arranca/
  reutiliza la preview de ese documento, devuelve `{enabled, static_url}`); `POST
  /api/preview/memory` (contenido no guardado → recompila en memoria, verificado que no toca
  el `.typ` en disco); `POST /api/preview/jump` (salto explícito). Una sola instancia de
  `PreviewServer` a la vez (mismo criterio que la preview de la Etapa 12 typst.ts) — cambiar de
  documento activo detiene la anterior y lanza una nueva.
- **Frontend**: `TinymistPreview.vue` reemplaza a `TypstCanvasPreview.vue` en `DocEditor.vue`
  (documentos) — monta un `<iframe>` con el `static_url`. Si tinymist no está disponible (sin
  binario, o `doctyp web --legacy-preview`), degrada a `TypstCanvasPreview`/typst.ts sin
  clic↔cursor. `editorScrollToBus.js` es un bus mínimo (un solo `ref` reactivo) para que el
  evento SSE, recibido en `App.vue` (raíz del árbol), llegue hasta `CodeEditor.vue` sin
  tunelizar por cada componente intermedio — el proyecto no usa un store (Vuex/Pinia).
- **⚠ Nota superada — plantillas ya NO quedan fuera del alcance.** Al cerrar la Etapa 15,
  `TemplateEditor.vue` sí quedó en modo legacy typst.ts, por el motivo descrito abajo. En un
  commit posterior (`0b59d0f`, fuera de las fases F0-F8 registradas en `plan15_progreso.md`) se
  extendió: `TemplateEditor.vue` usa `TinymistPreview` por defecto igual que `DocEditor.vue`
  (clic↔cursor, memoria en vivo con debounce de 300 ms vía `actualizarMemoriaPreviewPlantilla`,
  salto explícito con botón/Ctrl+Alt+J), degradando a `TypstCanvasPreview` solo si tinymist no
  está disponible. El bloqueo original — sin ruta de archivo persistente para
  `tinymist preview --root` — se resolvió reusando `core.asegurar_muestra_typ()` (ya existente
  desde la Etapa 9/11 para el modo typst.ts), que materializa el documento de muestra en disco
  junto a la plantilla; `_asegurar_preview_plantilla()` en `doctyp_web.py` la reusa tal cual, sin
  necesitar una decisión de diseño nueva. Texto original de la nota, conservado como historial:
  *"`TemplateEditor.vue` (plantillas) queda fuera del alcance, en modo legacy typst.ts sin
  clic↔cursor: su vista previa es un documento de muestra generado en memoria
  (`core.build_typ(_muestra_meta(), "lib.typ")`), sin una ruta de archivo persistente que darle
  a `tinymist preview --root` — extenderlo requiere decidir dónde materializar ese documento de
  muestra en disco, una decisión de diseño no cubierta por el plan original."*
- **Flag `doctyp web --legacy-preview`**: fuerza typst.ts aunque tinymist esté disponible.
  Config `local.preview_tinymist_path` en `settings.json` (mismo patrón que
  `local.org_activa`/`local.autor_activo`) para fijar la ruta del binario si no está en el PATH.
- **Verificación**: toda la investigación y cada fase se probaron contra una instalación real
  de `tinymist 0.15.2` (descargada temporalmente para desarrollo, fuera del repo) y Playwright
  real contra `doctyp web` levantado de verdad — no solo lectura de código. Se encontraron y
  corrigieron 3 bugs reales durante la implementación (deadlock de lock no reentrante en
  `PreviewServer.start()`, doble reinicio por condición de carrera entre el lector de stdout y
  el cliente WS, colisión de puertos por defecto) — detalle completo en `plan15_progreso.md`.
  **Importante para depuración futura de este subsistema**: cerrar siempre `doctyp web` con
  SIGINT (Ctrl+C), nunca `pkill -9` directo al proceso Python — eso saltea el `finally` que
  detiene el subproceso `tinymist` y puede dejar procesos huérfanos relanzándose solos vía el
  mecanismo de reintento automático.

**Nota sobre el alcance real de la Etapa 16** (auditoría y plan de continuación sobre la Etapa
15, documento de trabajo `tinymist-implementation-plan.md` en la raíz del repo — decisiones ya
tomadas por el usuario el 2026-07-14, ver cabecera de ese archivo. **Todo el plan está
ejecutado**: Fase 2, Fase 3, y las cinco sub-fases de la Fase 1 (paso 0, 1A-1D implementadas;
1E investigada con decisión explícita de NO migrar — ver el cierre de esta nota).

- **Fase 2 completada (H1, H3, H4 del plan; sin decisiones pendientes):** `compileStatus`
  cableado a SSE → `StatusBar.vue`/`TemplateEditor.vue` (indicador "Compilando…/Vista previa
  OK/Error de compilación"); colas SSE acotadas (`maxsize=100` + `put_nowait`/`except Full`);
  `resolver_tinymist_utilizable()` cacheado por mtime de `settings.json`; retirado el
  `console.log` `TEMP` de `App.vue`. Detalle igual al de la primera ejecución de esta nota
  (sin cambios adicionales en esta sesión).

- **Paso 0 de la Fase 1 — capabilities reales capturadas.** `tinymist lsp` **no estaba
  instalado como binario CLI** (ni en el PATH del sandbox ni en el del host) — se localizó el
  binario real que sí existe en la máquina: el que trae empaquetado la extensión de VS Code,
  `~/.var/app/com.visualstudio.code/data/vscode/extensions/myriad-dreamin.tinymist-0.15.2-linux-x64/out/tinymist`
  (versión 0.15.2, la misma que `MIN_TINYMIST_VERSION`). Se lanzó `initialize` contra ese
  binario real (script de trabajo en el scratchpad, no en el repo) y se volcó la respuesta a
  `lsp-capabilities-0.15.2.json` (junto al plan, como pide el paso 0). Hallazgos que corrigen
  supuestos del plan: **sin** `completionItem/resolve`, **sin** `declaration` ni
  `callHierarchy`, `semanticTokensProvider` solo `full+delta` (**sin** `range`),
  `positionEncoding: "utf-16"`, `textDocumentSync.change: 2` (incremental),
  `workspace.workspaceFolders.changeNotifications: true` (confirma que
  `workspace/didChangeWorkspaceFolders` sirve para cambiar de root sin relanzar el proceso —
  ver Fase 1A). `executeCommandProvider.commands` trae 29 comandos `tinymist.*` reales; la
  allowlist implementada (`_ALLOWLIST_COMANDOS_LSP`, `doctyp_web.py`) solo habilita los 11 que
  el plan ya nombraba como necesarios para 1D/1E (exportadores, preview, `pinMain`,
  `getDocumentMetrics`, `doClearCache`) — el resto del catálogo real queda documentado en el
  JSON pero fuera de la allowlist hasta que una sub-fase futura los necesite explícitamente.

- **Fase 1A completada (transporte + infraestructura del LSP, sin frontend consumidor
  todavía):**
  - `doctyp_ws_server.py` (nuevo): lado servidor RFC 6455 sobre stdlib puro, espejo de
    `doctyp_ws_client.py` (Plan 15 F2) — a diferencia del cliente, este SÍ reensambla
    fragmentación de entrada (frames de continuación) y exige frames enmascarados del
    navegador (RFC 6455 §5.1); el envío propio no fragmenta (la longitud extendida de 64 bits
    ya cubre payloads grandes en un solo frame).
  - `doctyp_lsp_server.py` (nuevo): clase `LspServer`, gestiona `tinymist lsp` por **stdio
    binario** (`text=False`, framing `Content-Length`, distinto del `Popen` de texto de
    `PreviewServer`). Un solo proceso por sesión de `doctyp web`: `start()` hace el
    `initialize`/`initialized` una vez (ids "backend-owned" con enteros **negativos**, para no
    colisionar nunca con los ids del navegador, que convencionalmente empiezan en 1);
    `cambiar_root()` reasocia el mismo proceso a otro documento/plantilla vía
    `workspace/didChangeWorkspaceFolders` **sin relanzar** (confirmado en el paso 0); `stop()`
    hace `shutdown`/`exit` antes de terminar el proceso.
  - `GET /api/lsp` (`doctyp_web.py`, método `_lsp_bridge` del handler): valida `slug`/`codigo`/
    `tipo`, resuelve el `root` (carpeta del documento, o `plantilla_dir` para plantillas —
    mismo criterio que la preview), hace el handshake WS y bombea JSON-RPC crudo
    navegador↔`tinymist lsp`. El backend interpreta el protocolo en exactamente **3
    excepciones** (nada más — CLAUDE.md §6, sin ejecución arbitraria): (1) allowlist de
    `workspace/executeCommand` (comando fuera de la lista → error `-32601` devuelto directo al
    navegador, nunca llega a tinymist); (2) responde localmente `workspace/configuration`
    (`null` por item), `client/registerCapability` y `window/workDoneProgress/create` (si no se
    respondieran, tinymist quedaría esperando una respuesta que el navegador no sabe dar); (3)
    reconexión — recargar la página reasocia la conexión WS nueva al proceso LSP vivo
    (`lsp.on_message` se reapunta), sin un segundo `initialize` (LSP no lo permite sobre la
    misma sesión). `_detener_lsp_activo()` se llama en el `finally` de `cmd_web`, mismo patrón
    que `_detener_preview_activa()`.
  - **Frontend: ninguno todavía.** El endpoint existe y funciona, pero no hay cliente
    CodeMirror/`@codemirror/lsp-client` conectado (eso es Fase 1B) — `/api/lsp` es
    infraestructura probada, no una funcionalidad visible para el usuario aún.
  - **Verificado en vivo** (con el binario real de la extensión VS Code, vía un shim de PATH
    temporal fuera del repo — no se modificó `settings.json`): `LspServer.start()` en
    aislamiento (initialize en 0.04 s, capabilities recibidas, `cambiar_root()` reasocia sin
    relanzar, `stop()` limpio); `doctyp web` levantado en un puerto de prueba (8799) con un
    cliente WS propio (script de trabajo, no en el repo) conectado a `ws://.../api/lsp` que
    completó `didOpen` + `textDocument/documentSymbol` (9 símbolos reales del documento
    `TI-INF-RED_2026-0039`), confirmó el rechazo `-32601` de un comando fuera de la allowlist
    (`tinymist.doInitTemplate`), y confirmó que reconectar a otro recurso (`tipo=plantilla`)
    reusa el mismo PID sin relanzar. Apagado con SIGINT: `pgrep tinymist`/`pgrep "doctyp.py
    web"` vacíos, sin huérfanos. `py_compile` y `npm run build` (66 módulos) sin errores.

- **Fase 3 completada (H2, H6/salto automático, autoguardado — decisiones ya tomadas por el
  usuario, sin bloqueos):**
  - **3.1 — H2 arreglado.** `_asegurar_preview_generico()` (`doctyp_web.py`) ahora calcula
    `archivo_editable` (el `.typ` principal para documentos; `lib.typ` de la plantilla, no la
    muestra, para plantillas) y etiqueta cada `editor-scroll-to` con `es_editable`. Verificado
    con un test unitario directo sobre la lógica de comparación de rutas (sin necesitar un
    clic real dentro del iframe): clic en el archivo editable → `True`; clic en el otro
    (`lib.typ` desde documentos, o la muestra desde plantillas) → `False`, en los 4 casos
    cruzados. `CodeEditor.vue` ignora el salto si `es_editable !== true` y emite
    `salto-no-editable`; `DocEditor.vue` muestra el aviso no intrusivo ("Definido en la
    plantilla (lib.typ) — edítala desde el editor de plantillas"); `TemplateEditor.vue` lo
    ignora en silencio (ahí no hay "otro editor" al que mandar al usuario).
  - **3.2 — jump automático al clic, sin botón.** Se retiró el botón "Ver posición del cursor
    (Ctrl+Alt+J)" de `TinymistPreview.vue`, el atajo global y `onKeydownGlobal` de
    `DocEditor.vue`/`TemplateEditor.vue`, y `getPosicionCursor()`/`defineExpose` de
    `CodeEditor.vue` (sin más consumidores). Nuevo: `EditorView.domEventHandlers({click})` en
    `CodeEditor.vue` emite `clic-en-editor` **solo** en clic de posicionamiento (selección
    vacía — descarta arrastres y doble-clic que seleccionan palabra); `DocEditor.vue`/
    `TemplateEditor.vue` llaman `saltarAPosicionPreview(Plantilla)` directo desde ese handler.
    La dirección preview→editor no cambió (ya era automática al clic, Plan 15 F5).
  - **3.3 — autoguardado a 300 ms, documentos Y plantillas** (decisión del usuario 2026-07-14,
    cierra la pregunta que el plan dejaba abierta — ver punto 6 de la cabecera de
    `tinymist-implementation-plan.md`). Reemplaza tanto el botón "Guardar" (retirado de
    `StatusBar.vue`, convertido en indicador "Guardando…"/"Guardado ✓ hh:mm:ss") como el
    debounce de `updateMemoryFiles` de Plan 15 F6 (`actualizarMemoriaPreview(Plantilla)` ya no
    se llama desde ningún componente — los endpoints `POST /api/preview/memory` y
    `.../plantilla/memory` siguen existiendo en el backend, sin retirar, tal como el plan
    permite "a más tardar en 1E"). Documentos usan el `PUT .../typ` ya existente
    (`api_doc_typ_put`, ahora con **escritura atómica** vía `core._escribir_texto_atomico`,
    nueva función write-temp+rename genérica junto a `_escribir_json_atomico`). Plantillas
    necesitaban una vía nueva: `PUT .../lib-typ` **siempre** versiona (`guardar_version_plantilla`,
    Etapa 9) — inválido para autoguardar cada 300 ms — así que se agregó
    `PUT .../plantillas/<nombre>/lib-typ-contenido` (`api_template_libtyp_contenido_put`,
    escritura atómica, **sin** versión/snapshot), dejando "Guardar plantilla" (con mensaje) como
    la única vía que versiona, igual criterio que "Subir versión" en documentos. Ambos PUT
    emiten un evento SSE nuevo (`doc-saved` / `plantilla-guardada`) porque el polling de mtimes
    de `/api/events` no detecta ediciones de contenido (solo mtime de directorios) — `App.vue`
    los usa para refrescar `cargarDocs()`/`cargarPlantillas()` en otras pestañas/vistas. Guardas
    de carrera implementadas tal como especifica el snippet del plan: `contenido` capturado
    ANTES del `await`, solo se marca limpio si `texto.value` no cambió durante la escritura; si
    `ocupado` (Subir versión/Compilar en vuelo) el autoguardado se reprograma en vez de
    perderse; `subirVersion`/`compilarDoc`/`guardar` (plantillas) cancelan el temporizador
    pendiente antes de escribir ellos mismos (ya escribían si `sucio`, se conserva como
    cinturón); flush inmediato en `beforeunload` y al desmontar el componente (salir de la
    vista). El autoguardado **nunca** bumpea versión ni toca `org.json`/el índice de snapshots
    de la plantilla.
  - **Verificado en vivo contra `doctyp web` real** (puerto de prueba 8799, binario real de la
    extensión VS Code): `PUT .../typ` con contenido nuevo → releído desde disco coincide,
    evento SSE `doc-saved` recibido, contenido restaurado al original al terminar (no se dejó
    ningún cambio permanente en los documentos reales del usuario). `PUT .../lib-typ-contenido`
    → releído coincide, **el conteo de versiones de la plantilla no cambió** (criterio de
    aceptación: el autoguardado no debe versionar), evento SSE `plantilla-guardada` recibido,
    contenido restaurado. `py_compile` y `npm run build` sin errores.
  - **No verificado con un navegador real (sin Playwright en esta sesión):** el disparo del
    clic (`domEventHandlers` de CodeMirror), la reactividad de los indicadores en
    `StatusBar.vue`/`TemplateEditor.vue`, y el comportamiento visual del jump automático en el
    iframe de tinymist. La lógica de backend que sostiene todo eso sí se verificó en vivo (ver
    arriba); lo pendiente es específicamente la capa de interacción DOM/Vue en un navegador.
    Señalar si quieres una pasada con Playwright (`doctyp web` + Chromium temporal, mismo
    patrón que la Etapa 10) para cerrar esa verificación.

- **Bug real encontrado y corregido tras cerrar lo de arriba: `tinymist` no se encontraba
  dentro del sandbox Flatpak de VS Code aunque SÍ estaba instalado.** El usuario reportó
  `doctyp web` avisando "No se encontró el binario 'tinymist'" en su terminal real. Investigado
  en vivo: el binario ya existía en `~/.local/bin/tinymist` (versión 0.15.2, correcta) — el
  problema era que `find_tinymist()` (`doctyp_preview_binary.py`) solo probaba
  `shutil.which("tinymist")`, y el `PATH` del sandbox Flatpak del terminal integrado de VS Code
  no incluye `~/.local/bin` (mismo tipo de problema que `typst`, ya documentado en §10/§13 —
  pero confirmado que ejecutar el binario por **ruta completa** sí funciona sin
  `flatpak-spawn --host`, a diferencia de `typst`: `~/.local/bin` SÍ es visible/ejecutable
  dentro del sandbox, solo no está en su `PATH`). Fix: `find_tinymist()` ahora prueba
  `~/.local/bin/tinymist` como fallback directo si `shutil.which()` falla. Verificado en vivo
  contra `doctyp web` real (sin ningún shim de PATH): `/api/preview/info` pasó de degradar a
  legacy a `{"enabled": true, ...}`, con el proceso `tinymist preview` real corriendo desde
  `~/.local/bin/tinymist`; apagado limpio con SIGINT, sin huérfanos. Fila nueva en la tabla de
  Edge Cases (§13).
- **`init`/`init.ps1` ahora instalan tinymist automáticamente** (pedido explícito del usuario:
  "asegúrate que el binario se descargue al inicializar doctyp en un equipo por primera vez" —
  **revierte** la decisión de Plan 15 F1 de "no descargar binarios automáticamente"). Usan el
  instalador oficial de tinymist (`tinymist-installer.sh`/`.ps1`, generado por `cargo-dist`,
  publicado como asset de cada release en GitHub — detecta arquitectura/SO solo, sin que
  `doctyp` tenga que mapear nombres de asset a mano) con `TINYMIST_INSTALL_DIR` fijado al mismo
  directorio donde ya se instalan los symlinks/lanzadores de `doctyp` (`~/.local/bin` en
  bash, `%USERPROFILE%\bin` en PowerShell) y `TINYMIST_NO_MODIFY_PATH=1` (el paso de PATH del
  propio script ya se encarga). Versión pineada a `0.15.2` en ambos scripts (duplicada a mano,
  no leída de `MIN_TINYMIST_VERSION` en Python -- decisión deliberada por simplicidad, ver el
  comentario en el código; mantenerlas en sincronía si se actualiza la versión mínima). Solo
  instala si `tinymist` no se encuentra ya (`command -v`/`Get-Command`); si falla la descarga
  (sin red, GitHub inalcanzable), avisa y continúa -- `doctyp web` degrada a typst.ts igual que
  siempre, no es un requisito duro. **Verificado en vivo (bash, Linux x86_64):** instalación
  real contra el release v0.15.2 real de GitHub, binario funcional resultante (`tinymist -V`
  correcto). **No verificado (`init.ps1`, Windows):** sin entorno Windows/PowerShell disponible
  en esta sesión para probarlo; implementado siguiendo el mismo patrón documentado del
  instalador oficial (env vars `TINYMIST_INSTALL_DIR`/`TINYMIST_NO_MODIFY_PATH`, idénticas en
  ambos scripts según su propio código fuente), pero sin ejecución real que lo confirme.

- **Fase 1B completada — núcleo de edición, usando el paquete oficial `@codemirror/lsp-client`
  (D3 resuelta: no hizo falta puente manual, el paquete cubre didOpen/didChange/didSave/
  didClose vía su `Workspace` por defecto, diagnósticos, completion, hover y signatureHelp de
  una vez).**
  - `web/src/lsp/transport.js`: adapta un `WebSocket` del navegador a la forma `Transport`
    exacta que pide la librería (`{send, subscribe, unsubscribe}`); `web/src/lsp/client.js`:
    `conectarLsp(slug, codigo, tipo)` resuelve el URI vía `GET /api/lsp/info` (nuevo endpoint,
    devuelve el archivo editable — D4, mismo criterio que H2), abre el WebSocket, crea el
    `LSPClient` con `serverDiagnostics()`/`hoverTooltips()`/`serverCompletion()`/
    `signatureHelp()`, y expone un handler de `textDocument/publishDiagnostics` propio (además
    del interno del paquete) que alimenta `web/src/composables/lspDiagnosticsBus.js` para el
    contador de errores/avisos en `StatusBar.vue`/`TemplateEditor.vue`.
  - **Hallazgo de protocolo que obligó a un ajuste en el backend:** `LSPClient.connect()`
    siempre manda su propio `initialize` (no hay forma de desactivarlo desde la config), pero
    el proceso `tinymist lsp` ya fue inicializado UNA vez por el backend al arrancar (Fase 1A) y
    LSP no permite un segundo `initialize` sobre la misma sesión. Se agregó una 4ª/5ª excepción
    al puente (`doctyp_web.py: _lsp_bridge`, junto a la allowlist de `executeCommand` y las 3
    respuestas locales de la Fase 1A): `initialize` se responde con las capabilities ya
    cacheadas (`LspServer.capabilities`/`server_info`, sin tocar tinymist); `shutdown` responde
    `null` local (el ciclo de vida del proceso lo sigue controlando solo el backend,
    `_detener_lsp_activo()`); `initialized`/`exit` del navegador se descartan sin reenviar.
  - `CodeEditor.vue` conecta de forma asíncrona en `onMounted` (el editor ya es usable con
    StreamLanguage mientras tanto) y agrega las extensiones LSP vía un `Compartment` una vez
    que `conectarLsp()` resuelve — degradación obligatoria intacta: sin tinymist o si falla la
    conexión, el editor sigue exactamente igual que antes de la Etapa 16.
  - **Verificado en vivo con Playwright** (org de prueba aislada, ver nota de metodología más
    abajo): diagnósticos aparecen/desaparecen correctamente al introducir/corregir un error de
    sintaxis; autocompletado con `#tab` sugiere `tabla`/`tabla-kv`/`tabla-prioridad` (símbolos
    propios de `lib.typ`, prueba de que el root es correcto) junto a `table`/`table.paren`
    (builtins); hover sobre `report.with` muestra la firma real de tipos que devuelve tinymist.

- **Fase 1C completada — navegación y símbolos.**
  - `definition`/`references`/`rename` ya venían del paquete (Fase 1B: `jumpToDefinitionKeymap`
    F12, `findReferencesKeymap` Shift-F12, `renameKeymap` F2) — D4 la cubre gratis el
    `Workspace` por defecto del paquete: `displayFile()`/`updateFile()` sin una vista activa
    para ese archivo simplemente no hacen nada, así que un salto a `lib.typ` desde el editor de
    documentos no abre ni edita nada, sin código adicional.
  - `documentSymbol` (outline) y `workspace/symbol` (quick-open) NO los cubre el paquete —
    `web/src/lsp/navigation.js` no los necesitó (se resuelven con `client.request()` directo
    desde `CodeEditor.vue`): botón "≡" flotante abre un panel con el esquema completo del
    documento (headings + variables, aplanado con indentación); Ctrl+T abre un quick-open con
    debounce de 200 ms.
  - `foldingRange`: `foldService` de `@codemirror/language` es **síncrono**
    (`(state, from, to) => rango`) pero la petición LSP es async — se cachean los rangos en un
    `StateField` (`crearFoldingLsp`), refrescado al conectar y con debounce de 600 ms tras cada
    cambio (mismo temporizador que semantic tokens/inlay hints/colores, Fase 1D).
  - `selectionRange` (Alt+↑ expandir / Alt+↓ contraer): **bug encontrado y corregido** —
    `Alt-ArrowUp`/`Alt-ArrowDown` ya estaban tomados por `defaultKeymap`
    (`@codemirror/commands`: `moveLineUp`/`moveLineDown`), y como ese keymap se registra antes
    en la lista de extensiones, ganaba por precedencia aunque el nuevo keymap se agregara
    después. Fix: `Prec.highest()` sobre el keymap de selectionRange. Trade-off consciente:
    mover línea deja de estar disponible por Alt+↑/↓ en este editor (no hay combinación libre
    que no choque con algo — `Ctrl-Shift-ArrowUp/Down` ya los toma `signatureHelp()` del propio
    paquete, `Shift-Alt-Arrow*` ya los toma `selectSyntaxLeft/Right`).
  - **`workspace/symbol` devuelve `[]` siempre en tinymist 0.15.2** — confirmado por protocolo
    crudo (cliente WS propio, no solo el navegador), incluso con query vacía y buscando un
    heading que sí existe en el archivo abierto. No es un bug de esta integración; queda
    documentado como limitación del servidor. La función sigue en la UI (Ctrl+T), solo no
    tiene resultados que mostrar hasta que tinymist la implemente funcionalmente.
  - **Verificado en vivo con Playwright:** el esquema mostró la estructura canónica completa
    del informe (§8: Resumen ejecutivo, Antecedentes…, Anexo B. Firmas — 28 símbolos); folding
    con marcador real en el gutter; `selectionRange` confirmado por protocolo crudo (devuelve
    una cadena `parent` anidada real) y por el atajo aplicando una selección real tras el fix
    de precedencia.

- **Fase 1D completada — presentación avanzada, refactor y exportación rápida (D5).**
  - `web/src/lsp/presentation.js` (nuevo): semantic tokens (decorations con clases `.cm-lsp-*`
    que conviven con `typst-lang.js`/StreamLanguage — la Etapa 10 sigue dando color inmediato
    al tipear, semantic tokens lo refina cuando llega la respuesta async); inlay hints
    (widgets con toggle, botón dedicado en `CodeEditor.vue`); document colors (swatch clicable
    antes de cada literal de color + `<input type="color">` nativo, aplica el cambio vía
    `colorPresentation`); code actions (`Ctrl+.`, lista las acciones disponibles y aplica la
    elegida solo si el `WorkspaceEdit` toca el archivo abierto — D4, mismo criterio que rename/
    jump). Los cuatro se refrescan igual que folding: al conectar y con debounce de 600 ms.
  - `formatDocument` del paquete oficial, atajo **Ctrl+Shift+F** (pedido explícito del plan, no
    el `Shift-Alt-f` por defecto del paquete) — sin format-on-save, formatear sigue siendo una
    acción deliberada.
  - **Exportadores rápidos (D5): `pdf`, `text` y `markdown` implementados; `svg`/`png` NO
    (limitación real de tinymist 0.15.2, no una decisión de alcance).** Investigación en vivo
    (protocolo crudo, no solo lectura de código):
    - `workspace/executeCommand` con `tinymist.exportPdf`/`exportText`/`exportMarkdown` exige
      `arguments[0]` como **ruta de archivo plana**, NO un URI `file://` — pasar el URI produce
      un error de "output path is relative" con una ruta duplicada sin sentido. No documentado
      en ninguna parte encontrada; se dedujo leyendo el código fuente del bundle de la
      extensión de VS Code instalada (`exportCommand()` en su `extension.js`).
    - `svg`/`png` exigen una plantilla de numeración de página (`{p}`/`{0p}`) en la ruta de
      salida para documentos multi-página (que un informe siempre es: portada + ficha +
      contenido + contraportada). Se probó redirigir esa ruta vía `arguments[1]` (`extraOpts`)
      y vía `workspace/didChangeConfiguration` (`{"exportSvg": {"output": "..."}}`) — **ninguna
      de las dos tuvo efecto observable**; el comando siempre usa su ruta "natural" (mismo
      nombre base que el `.typ`, con la extensión del formato). Sin una forma confirmada de
      fijar esa plantilla, `svg`/`png` quedan fuera del menú "Exportar…" (solo pdf/texto/
      markdown) — señalar si se quiere retomar esta investigación.
    - `markdown` puede fallar en documentos con configuración de página dentro de contenedores
      (`report.with(meta:)` la define) — error real de tinymist ("page configuration is not
      allowed inside of containers"), no un bug de la integración; se propaga tal cual al
      usuario si ocurre.
    - **La ruta "natural" de pdf/text coincide con el `<código-base>.pdf`/`.txt` que otros
      flujos usan** (para documentos, el mismo nombre que "Compilar" genera). `api_lsp_exportar`
      (`doctyp_web.py`) respalda cualquier archivo preexistente en esa ruta antes de invocar el
      comando, lee el resultado, y SIEMPRE restaura el respaldo (o borra el artefacto si no
      había nada) en un `finally` — nunca queda pisando algo oficial. Nuevo endpoint
      `POST /api/lsp/exportar` (`{slug, codigo, tipo, formato}` → binario con
      `Content-Disposition: attachment`, `web/src/api.js: exportarLsp()` dispara la descarga
      real en el navegador vía `URL.createObjectURL`). Para plantillas, exporta la MUESTRA
      (documento ficticio que importa `lib.typ`), no `lib.typ` directamente (no es compilable
      por sí solo) — `_archivo_compilable_para()`, mismo criterio que la preview.
    - `LspServer.ejecutar_comando()` (nuevo, `doctyp_lsp_server.py`): wrapper público sobre
      `_peticion_backend()` (ids negativos, sin colisión con el navegador) para que
      `doctyp_web.py` invoque `workspace/executeCommand` directamente, sin pasar por el
      WebSocket del navegador — el export lo dispara el backend, no el frontend por su cuenta.
  - **Verificado en vivo:** export PDF real (6 páginas) y texto plano (contenido real
      extraído) vía `curl` contra el endpoint, con la carpeta del documento confirmada limpia
      después (sin `.pdf`/`.txt` residual); export PDF desde el editor de **plantillas** vía
      Playwright disparó una descarga real (`informe-ti.muestra.pdf`); semantic tokens pintó
      137 elementos reales; inlay hints mostró 4 pistas reales (`meta:`, `filas:`, etc.) y el
      toggle los ocultó/mostró correctamente; colores mostró 11 swatches reales en `lib.typ`
      (paleta de la plantilla); formatear cambió contenido real desalineado tras Ctrl+Shift+F.

- **Fase 1E — investigada en vivo, decisión explícita del usuario (2026-07-14): NO migrar.**
  `tinymist.doStartPreview` **sí funciona** invocado como `workspace/executeCommand` sobre el
  proceso `tinymist lsp` ya vivo (recibe argumentos CLI tal cual, ej.
  `[ruta_typ, "--data-plane-host", "...", "--no-open"]`, y devuelve `{dataPlanePort,
  staticServerAddr, ...}` sin lanzar un segundo binario) — confirma que la unificación es
  técnicamente viable. **Lo que NO se pudo confirmar:** si `editorScrollTo` (clic↔cursor, la
  función que más se usa de la preview hoy) llega igual en este modo embebido — la prueba en
  vivo (simular `src-point` sobre el data plane devuelto) no mostró ninguna notificación LSP
  correspondiente, pero es inconclusa, no negativa: el documento de prueba disponible en ese
  momento no tenía prosa real en una posición conocida (mismo problema que ya documentó el
  Plan 15 F4 con el mismo tipo de documento). Dado que esta fase toca directamente un mecanismo
  de preview que ya está **funcionando y verificado** (Etapa 15, y el fix de PATH del sandbox
  Flatpak de esta misma sesión), y que el propio plan sanciona explícitamente mantener los dos
  procesos si la unificación no se confirma limpiamente ("conviven sin conflicto y el resto de
  la Fase 1 no depende de esta unificación"), el usuario decidió **no migrar por ahora** en vez
  de arriesgar una función que ya funciona al cierre de una sesión larga. `PreviewServer`
  (`doctyp_preview_server.py`) y `doctyp_preview_binary.py` **se mantienen** — no retirar. Si se
  retoma esta fase más adelante, el punto de partida es confirmar cómo llega `editorScrollTo`
  en modo `doStartPreview` contra un documento con prosa real y clics en píxeles precisos
  (Playwright, no simulación directa del data plane).

**Nota de metodología (Fase 1B-1E, aplica a toda la Etapa 16):** toda la verificación en vivo
de esta etapa se hizo contra una **organización de prueba aislada** (`prueba-playwright`,
creada con `doctyp org new`/`doctyp template new`/`doctyp new` — no contra `slep-chinchorro`),
después de un incidente real: una prueba de Playwright con autocompletado + deshacer (Ctrl+Z)
vació por completo el documento real `TI-INF-SFW_2026-0001` (el historial de deshacer de
CodeMirror incluye la carga inicial del contenido como un paso más, así que un Ctrl+Z de más
borra el documento entero) y el autoguardado de la Fase 3.3 escribió ese estado vacío a disco.
Se reconstruyó con el mismo generador de esqueleto que usa `doctyp new` (mismos metadatos que
`org.json`, con datos de relleno ya que el documento era en sí un documento de prueba desde su
creación, sin contenido real que recuperar) — confirmado con `typst compile` que el resultado
es válido. Desde entonces, cualquier prueba que involucre clics/escritura/atajos de teclado
reales se hace contra la organización de prueba aislada, nunca contra datos reales del usuario.

**Nota sobre el alcance real de la Etapa 17** (serie de pedidos directos del usuario en una
sola sesión, 2026-07-15 — sin documento de plan para las dos primeras piezas, con plan +
aprobación explícita del usuario para el router y para el sidebar de archivos, siguiendo la
regla de §0 "Plan antes de código" para cambios estructurales):

- **Atajos en `CodeEditor.vue`**: `Mod-s` (Ctrl+S en Windows/Linux, Cmd+S en macOS) fuerza un
  flush inmediato del autoguardado a 300 ms que ya existía desde la Etapa 16 (Fase 3.3) — no es
  un mecanismo de guardado nuevo, solo un atajo que llama al mismo `flushGuardado()` de
  `DocEditor.vue`/`TemplateEditor.vue` sin esperar el debounce; `preventDefault` evita que el
  navegador abra su diálogo "Guardar página como". `indentWithTab` (`@codemirror/commands`)
  agregado al keymap para que Tab indente/desindente la línea o selección — antes no hacía nada.
- **Imágenes propias de documentos** (antes solo existía para plantillas, vía el modal de
  imágenes original de la Etapa 9): nuevos `api_doc_archivo_subir`/`api_doc_archivo_eliminar`
  (`doctyp_web.py`), mismo patrón que sus equivalentes de plantilla pero apuntando a `img/` en
  vez de `Images/` (§4). En un primer momento el modal `SubirImagenesModal.vue` se generalizó
  con una prop `tipo` (`"doc"|"plantilla"`) para servir a ambos — **ese modal se retiró por
  completo más tarde en la misma etapa**, ver el sidebar de archivos más abajo.
- **Split editor/vista previa 60/40** (antes 50/50, sin cambios desde que existe el panel
  dividido de la Etapa 8): `flex: 60 1 0` / `flex: 40 1 0` en `.editor-textarea`/`.vista-previa`
  (`style.css`) — aplica a documentos y plantillas por igual, ambos comparten esas clases.
- **Router de la SPA** (`vue-router@4`, modo `history`): antes la navegación era un `ref` local
  `vista` en `App.vue` (decisión explícita de la Etapa 7 de no usar router, "no hacía falta
  deep-linking" — **superada**, ver anotación en la nota de la Etapa 7). Rutas:
  `/documentos`, `/documentos/:codigo`, `/plantillas`, `/plantillas/:nombre`, `/organizacion`
  (`/` redirige a `/documentos`).
  - **Decisión de diseño**: la organización activa NO va en la URL — sigue siendo estado
    global (mismo concepto que `settings.json → local.org_activa`), no un parámetro de ruta.
  - **Hallazgo que obligó a un cambio en `vite.config.js`**: `base: "./"` (rutas relativas)
    rompe cualquier ruta anidada al refrescar directo (`/documentos/XXX`) — el HTML serviría
    `./assets/...`, que el navegador resuelve mal contra la ruta anidada. El backend
    (`doctyp_web.py: _estaticos`) **ya** hacía fallback a `index.html` para cualquier GET no
    reconocido (comentario `# fallback SPA` preexistente, sin usar hasta ahora) — el único fix
    necesario fue `base: "/"` (rutas absolutas), consistente con que `index.html` ya usa
    `/src/main.js` absoluto en dev.
  - **Estado compartido**: nuevo `web/src/composables/useOrgContext.js`, mismo patrón "bus" de
    módulo-singleton que `editorScrollToBus.js`/`compileStatusBus.js` (el proyecto no usa store,
    ver nota Etapa 5) — el topbar (fuera del `<router-view>`) y las vistas (dentro) necesitan el
    mismo estado (org/autor/docs/plantillas activos) sin prop-drilling a través del router.
  - **Vistas nuevas** (`web/src/views/`): `DocumentosGridView`, `DocumentoEditorView`,
    `PlantillasGridView`, `PlantillaEditorView`, `OrganizacionView` — envuelven los componentes
    existentes (`DocEditor.vue`, `TemplateEditor.vue`, etc.) sin tocar su lógica interna. Las
    guardas de "cambios sin guardar" que antes vivían en `App.vue` (confirm antes de cambiar de
    vista) pasaron a `onBeforeRouteLeave`/`onBeforeRouteUpdate` de vue-router en cada vista de
    editor.
  - **`OrganizacionView.vue` reemplaza al modal `OrgManager.vue`** (retirado): página completa
    con 3 tabs — **Organización** (nueva: lista de orgs, cambiar activa, crear nueva — antes
    solo estaba en el selector del topbar), **Autores**, **Equipos** (CRUD sin cambios respecto
    al modal original).
  - **Bug encontrado y corregido tras el primer build**: al refrescar directo en
    `/documentos/:codigo` (o `/plantillas/:nombre`, o `/organizacion`), `orgSlug` todavía es
    `null` (se llena de forma asíncrona en `App.vue: onMounted`) pero `DocEditor.vue`/
    `TemplateEditor.vue` disparan su fetch inicial de inmediato al montar, produciendo
    `"no existe la organización 'null'"`. Fix: guarda `v-if="!orgSlug"` (con
    "Cargando organización…") en `DocumentoEditorView.vue`/`PlantillaEditorView.vue` antes de
    montar el editor real, y un `watch(orgSlug, cargarEquipos)` en `OrganizacionView.vue` para
    el mismo caso.
- **Sidebar de archivos de solo lectura** (`FileTreeSidebar.vue` + `FileTreeNode.vue`, nuevos):
  árbol completo de la carpeta del documento/plantilla (visualización únicamente — nada de
  código ni `lib.typ` es editable desde ahí), montado dentro de `DocEditor.vue`/
  `TemplateEditor.vue` (no en las vistas del router, para conservar acceso a
  `tinymistPreviewRef` y poder refrescar la vista previa al cambiar una imagen). **Reemplaza
  por completo al modal de imágenes** (`SubirImagenesModal.vue`, eliminado) — decisión
  confirmada explícitamente con el usuario en vez de mantener ambas UIs para la misma acción.
  - Solo los archivos dentro de la carpeta de imágenes propia son mutables — `img/` en
    documentos, `Images/` en plantillas (mismo criterio que ya regía el modal retirado); todo
    lo demás del árbol (el `.typ`, `lib.typ`, `Images/` copiada *dentro* de un documento,
    `fonts/`) se ve pero sin acciones.
  - **Nuevo: renombrar imágenes** (no existía en el modal original) —
    `api_doc_archivo_renombrar`/`api_template_archivo_renombrar` (`doctyp_web.py`, ruteo
    `PUT .../archivo/<ruta...>`, body `{nombre_nuevo}`): rechaza si la ruta no empieza en la
    carpeta mutable, valida extensión de imagen, 404 si el origen no existe, 400 si el destino
    ya existe, `Path.rename()` simple (no hace falta escritura atómica, no reescribe
    contenido). Confirmación vía `window.prompt`/`window.confirm`, mismo criterio que el resto
    de la app (sin modales de confirmación dedicados).
  - Nuevo layout `.editor-body` (`style.css`): sidebar (ancho fijo 260px, mismo lenguaje visual
    que `.panel-docs` ya existente) + `.editor-preview-split` (60/40 sin cambios) como hijos.
    `StatusBar`/la barra de plantilla quedan debajo, ancho completo, sin cambios.
- **Verificación de esta etapa**: `npm run build` y `python3 -m py_compile doctyp_web.py` sin
  errores tras cada pieza. **No se verificó en vivo con Playwright/navegador real** (a
  diferencia de la metodología de la Etapa 16) — quedó ofrecido al usuario en cada pieza, sin
  que lo pidiera explícitamente durante la sesión.

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
  (no hacía falta deep-linking). **⚠ Superado en la Etapa 17**: se agregó `vue-router` (rutas
  reales `/documentos`, `/plantillas`, `/organizacion`) — ver esa nota más abajo; el estado
  `vista` ya no existe en `App.vue`. La cuadrícula (`DocumentGrid.vue`) reemplaza a `DocList.vue`
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

**Nota sobre el alcance real de la Etapa 11**:
- **Sin click-to-jump** (decisión ya tomada con el usuario, dividida en una Etapa 12 nueva):
  investigué el ecosistema **typst.ts** instalándolo y leyendo sus `.d.ts` reales (no solo el
  README) — el wrapper Vue3 oficial (`@myriaddreamin/typst.vue3`) está `[WIP]` y se descartó;
  el click-to-jump bidireccional no está documentado en ningún paquete público. Dato para la
  Etapa 12: `RenderSession.getSourceLoc(path: Uint32Array): string | undefined` existe en el
  renderer (`@myriaddreamin/typst.ts`, `dist/esm/renderer.d.mts`) — es la pieza de bajo nivel
  que probablemente hará falta para la dirección clic→cursor.
- **API real usada** (`createTypstCompiler()`/`createTypstRenderer()` del paquete core
  `@myriaddreamin/typst.ts`, no el wrapper WIP): `compiler.addSource(path, texto)` para
  archivos de texto (`main.typ`, `lib.typ`), `compiler.mapShadow(path, Uint8Array)` para
  binarios (`Images/*`), `compiler.compile({mainFilePath, format:'vector', diagnostics:'unix'})`
  → artefacto vectorial + diagnósticos legibles, `renderer.renderToCanvas({container,
  artifactContent, backgroundColor})` — gestiona la paginación a `<canvas>` sin código propio de
  bajo nivel. Todo vive en `web/src/typst-wasm/client.js` (singleton: reinicializar los ~28 MB
  del compilador por cada apertura de editor sería inaceptable).
- **Los binarios `.wasm` (~28 MB compilador + ~1 MB renderer) no se versionan** — se importan
  con el sufijo `?url` de Vite directo desde `node_modules/@myriaddreamin/...`, que los copia a
  `dist/assets/` con hash en cada build (mismo principio que `web/dist/`/`web/node_modules/`:
  build artifacts, no código fuente). Solo las fuentes Liberation Sans (~825 KB, licencia SIL
  OFL, redistribución explícitamente permitida) se versionan en `web/public/fonts/`, junto a su
  `LICENSE.txt`.
- **Solo Liberation Sans en la vista previa en vivo** (decisión ya tomada) — `loadFonts(...,
  {assets: false})` evita que typst.ts descargue además sus fuentes por defecto desde GitHub;
  verificado con Playwright que no hay peticiones de red fuera de `127.0.0.1` al compilar.
  "Compilar" (PDF real, `doctyp.py: compilar_typ`) y las miniaturas
  (`generar_miniatura`/`generar_miniatura_plantilla`) siguen usando `typst` en el servidor sin
  cambios, con Museo Sans si está instalada — puede haber diferencias cosméticas menores entre
  la vista previa en vivo y el PDF final mientras tanto.
- **Backend nuevo, genérico para documentos y plantillas** (`doctyp_web.py`): `GET
  .../archivos` (manifiesto de rutas relativas, excluyendo `.snapshots/`, ocultos y el
  archivo que viaja como texto en vivo) y `GET .../archivo/<ruta...>` (bytes crudos, con
  `mimetypes.guess_type` para el content-type) — el navegador arma el "proyecto" del
  compilador con esto. Para plantillas se agregó además `GET .../plantillas/<nombre>/muestra`
  (mismo `build_typ(_muestra_meta(), "lib.typ")` de la Etapa 9, sin reimplementarlo en JS). El
  servidor de estáticos ganó `.wasm: "application/wasm"` en su mapa de tipos (antes caía a
  `application/octet-stream`, más lento para `WebAssembly.instantiateStreaming`).
- **Limpieza**: `VistaPrevia.vue`, `compilar_vista_previa()` y
  `compilar_vista_previa_plantilla()` (Etapa 8/9) se eliminaron por completo junto con los
  endpoints `POST .../vista-previa` — sin ningún llamador tras el cambio. `compilar_typ()` /
  `generar_miniatura()` / `generar_miniatura_plantilla()` no se tocaron.

**Bug encontrado y corregido (2026-07-21, fuera de cualquier etapa numerada): el daemon de
sincronización inundaba `.snapshots/` de plantillas con "respaldos" automáticos.** Cada tick de
`doctyp_sync_daemon.py` (cada `INTERVALO_SEGUNDOS` = 5s) que resolvía un conflicto de
sincronización de una plantilla (mtime local más antiguo que el remoto, contenido distinto)
llamaba a `core.guardar_version_plantilla(..., "Respaldo automático por sincronización
(conflicto)")` (`doctyp_sync.py: _sincronizar_plantilla`, antes de este fix) — a diferencia del
mismo caso para documentos (`_respaldar_documento_perdedor`, una copia simple sin indexar), para
plantillas esto creaba una versión real e indexada en `.snapshots/index.json` en CADA tick que
detectaba diferencia, no solo en conflictos genuinos poco frecuentes. Con el daemon corriendo
en segundo plano de forma continua, esto llegó a generar 110 versiones espurias
(`lib_v1.typ`…`lib_v110.typ`) en la plantilla `informe-ti` de `slep-chinchorro` en menos de un
día. El usuario no quiere respaldos automáticos de plantillas en absoluto — ya tienen
versionado manual (`doctyp template save` / "Guardar plantilla" en la web) para rollback. Fix:
`_sincronizar_plantilla` ahora solo descarga y sobrescribe `lib.typ` en ese caso, sin llamar a
`guardar_version_plantilla` (`doctyp_sync.py:358-361`). El respaldo de documentos
(`_respaldar_documento_perdedor`) no se tocó — no fue el problema reportado, y no es un
snapshot indexado (no aparece en `template history`/`doc history`). Limpieza de los datos ya
generados: el usuario borró manualmente los `lib_v*.typ` sobrantes; `.snapshots/index.json` de
`informe-ti` se reescribió a mano para reflejar solo los 2 snapshots que quedaron en disco
(`lib_v1.typ` del 2026-07-20, `lib_v2.typ` — renombrado desde el `lib_v110.typ` que sobrevivió
— del 2026-07-21), sin usar ningún comando (no existe un comando de "compactar" el índice).

**Nota sobre el alcance real de la Etapa 21** (icono de bandeja del sistema, pedido explícito
del usuario 2026-07-21, plan discutido y aprobado antes de implementar — CLAUDE.md §0):

- **`doctyp_tray.py` (nuevo)**: todo lo específico de Qt vive acá, para no acoplar
  `doctyp_sync.py`/`doctyp_sync_daemon.py` a `PySide6` — es la **única dependencia Python fuera
  de stdlib de todo el proyecto** (decisión explícita del usuario: Qt, no GTK, porque su
  escritorio es KDE Plasma — `$XDG_CURRENT_DESKTOP=KDE`, sesión Wayland — y KDE soporta
  `QSystemTrayIcon`/StatusNotifierItem nativamente, sin necesitar una extensión como sí haría
  falta en GNOME estándar). El import de `PySide6` está detrás de un `try/except ImportError` a
  nivel de módulo (`_PYSIDE_DISPONIBLE`), y las clases que heredan de tipos de Qt
  (`DoctypTrayIcon`) quedan definidas condicionalmente dentro de ese guard — el módulo importa
  limpio aunque `PySide6` no esté instalado.
- **Guard de disponibilidad de tres capas** (`disponible()`): (a) `PySide6` importó bien, (b)
  `DISPLAY`/`WAYLAND_DISPLAY` seteado en el entorno (evita que Qt intente conectarse sin sesión
  gráfica — riesgo real bajo el `systemd --user` del autoarranque, `init` §7, que no siempre
  hereda el entorno de la sesión de escritorio), (c) tras crear `QApplication`,
  `QSystemTrayIcon.isSystemTrayAvailable()` es `True`. Si cualquiera falla,
  `doctyp_sync_daemon.py: _loop_con_bandeja` devuelve `False` sin efectos secundarios y
  `ejecutar_foreground()` cae al loop headless de siempre — el daemon nunca deja de sincronizar
  por esto, con o sin icono.
- **El daemon posee el icono directamente** (decisión explícita del usuario: sin IPC, sin
  segundo proceso). `_loop_con_bandeja()` reemplaza el `while` + `time.sleep` habitual por
  `QApplication.exec()` con un `QTimer` (cada `INTERVALO_SEGUNDOS`) que llama a `un_tick()`, más
  un segundo `QTimer` corto (300 ms) cuyo único propósito es dejar que el intérprete de Python
  atienda `SIGTERM`/`SIGINT` a tiempo (el loop C++ de Qt bloquea el chequeo de señales de
  Python; sin ese timer frecuente, `Ctrl+C`/`doctyp logout` podrían demorar hasta 5s en
  surtir efecto).
- **Qué muestra el tooltip**: usuario logueado (`sync.sesion_activa()["email"]`), y del último
  documento/plantilla realmente transferido (no de cada tick — la mayoría son no-ops por hash
  igual, `doctyp_sync.py:384-386`): tipo, nombre, archivo, tamaño legible (B/KB/MB/GB) y
  fecha/hora, más si el último intento de sincronización fue exitoso o falló. Para esto,
  `sincronizar_documento`/`_sincronizar_plantilla`/`sincronizar_todo` (`doctyp_sync.py`) ganaron
  un parámetro opcional `on_evento` (default `None`) que se invoca solo tras una transferencia
  real (nunca en el `return` temprano por hash idéntico) — la CLI (`cmd_sync`/`cmd_login`,
  `doctyp.py`) no lo pasa, así que su comportamiento no cambió. `un_tick()` ahora devuelve
  `(ok, detalle)` en vez de nada, para que la rama gráfica sepa qué mostrar; el loop headless
  sigue ignorando el valor de retorno.
- **Menú contextual mínimo** (clic derecho): "Sincronizar ahora" (dispara `un_tick()` fuera del
  timer) y "Salir" — un icono de bandeja sin forma de cerrarlo desde la UI obligaría a matar el
  proceso por terminal, así que se incluyó por defecto sin que el usuario lo pidiera
  explícitamente (señalado en el plan antes de implementar, no fue una sorpresa).
- **Icono dibujado en runtime** (`QPainter` sobre un `QPixmap`, glifo simple: cuadrado
  redondeado azul con una "d" blanca) — sin asset binario nuevo en el repo; no existía ningún
  logo/favicon propio de la app (fuera de los institucionales de cada organización, que no
  aplican acá porque el icono representa el daemon, no una org en particular).
- **`init`**: nuevo paso 4b (mismo patrón best-effort que tinymist, paso 4) que intenta
  `pkg_install python3-pyside6` en Fedora (nombre de paquete sin verificar contra el repo real
  al escribir esto) y si falla cae a `pip install --user PySide6-Essentials` (paquete más
  liviano que `PySide6` completo — solo trae QtCore/QtGui/QtWidgets, lo único que usa
  `doctyp_tray.py`, sin QtQml/QtQuick/Designer). Si ambos fallan, solo avisa y continúa — nunca
  aborta la instalación. `init.ps1` (Windows) **no se tocó** — el pedido del usuario fue
  específicamente Fedora/Linux; el guard de `disponible()` ya hace que Windows sin `PySide6`
  siga funcionando en modo headless sin cambios.
- **Verificado en esta sesión**: `python3 -m py_compile` sobre los 4 archivos tocados;
  `PySide6-Essentials` instalado real (vía pip) en el entorno de trabajo y probado en vivo —
  `QApplication` se conecta al compositor Wayland real (`app.platformName() == "wayland"`), y
  el daemon completo (`python3 doctyp.py _sync-daemon`) corrido en primer plano confirma la
  secuencia esperada: intenta la rama con bandeja, cae a headless limpiamente, tickea con la
  nueva firma de `on_evento`/`(ok, detalle)` sin errores, y se apaga limpio con `SIGTERM`
  (pidfile borrado, log "daemon detenido").
  **No verificado con el icono real visible en la bandeja de KDE**: el entorno de trabajo de
  esta sesión corre dentro de un sandbox Flatpak (el mismo que ya afecta a `typst`/`tinymist`,
  ver §10/§13) cuyo proxy de D-Bus (`DBUS_SESSION_BUS_ADDRESS=unix:path=/run/flatpak/bus`) no
  expone `org.kde.StatusNotifierWatcher` — `QSystemTrayIcon.isSystemTrayAvailable()` da `False`
  ahí aunque la conexión a Wayland funciona bien, así que el daemon cae a headless también en
  este sandbox (una demostración en vivo de que el fallback funciona, pero no del icono en sí).
  Falta que el usuario corra `python3 doctyp.py _sync-daemon` (o `doctyp sync`) directo en su
  terminal real (fuera de cualquier sandbox) y confirme visualmente: el icono aparece en la
  bandeja de KDE, el hover muestra el tooltip esperado, y el menú contextual funciona (ver
  incrementos posteriores más abajo — el menú original "Sincronizar ahora"/"Salir" ya no es el
  actual).
- **Sin tocar durante esta etapa**: `_respaldar_documento_perdedor` (backup de documentos en
  conflicto de sync, sin relación con este pedido); ningún cambio de estilo/UI de la SPA web
  (el pedido fue exclusivamente sobre el daemon nativo, no sobre `doctyp web`).

**Incremento 2026-07-22 (a): logging del fallback silencioso.** El usuario confirmó el icono
funcionando en su KDE real, pero un segundo intento (`doctyp sync`, sesión ya activa) no
mostró ícono ni ningún aviso. Causa: `_loop_con_bandeja` solo logueaba si `tray.iniciar()`
lanzaba una excepción — un `return False` limpio (por `disponible()`/`isSystemTrayAvailable()`
devolviendo `False`) caía al modo headless en silencio total, sin forma de distinguir "no
aplica en este sistema" de "algo está roto". Fix: `doctyp_tray.py` gana
`motivo_no_disponible() -> str` (mensaje legible para cada causa: PySide6 no instalado, sin
`DISPLAY`/`WAYLAND_DISPLAY`, o ninguna de las dos costosas de chequear); `_loop_con_bandeja`
ahora loguea SIEMPRE una línea explicando el resultado, sea `"icono de bandeja iniciado"` o
`"bandeja del sistema no disponible (...)"`. (La causa real en la máquina del usuario resultó
ser la primera categoría — el daemon que seguía vivo era un proceso arrancado ANTES de que
existiera el código del ícono, Python no hace hot-reload — no un problema de disponibilidad;
confirmado con el usuario, resuelto con `doctyp logout` + `doctyp login` para relanzarlo.)

**Incremento 2026-07-22 (b): cambio de usuario, estado de sync en el menú, cerrar sesión.**
Sobre la base ya funcionando, pedido explícito del usuario — plan discutido y aprobado antes de
implementar (CLAUDE.md §0), con un ajuste tras la primera versión del plan: **cambiar de
usuario SIEMPRE pide contraseña**, incluso para una cuenta ya usada antes en este equipo — no
hay cookies cacheadas por cuenta ni cambio instantáneo, decisión explícita del usuario que
simplificó el diseño original (que sí las cacheaba).

- **`doctyp_sync.py`**: nuevo `settings.json → local.correos_conocidos` — lista de
  `{email, ultimo_uso}`, **sin cookie** (a diferencia de `sesion_remota`, que sigue siendo la
  única cookie guardada en texto plano). `guardar_sesion()` (ya existente, usada tanto por la
  CLI como por el daemon) hace upsert ahí en cada login exitoso — alimenta el submenú sin
  duplicar lógica entre CLI y bandeja. `correos_conocidos()` nueva, más recientes primero.
- **`doctyp_tray.py`**: glifo del icono cambiado de `"d"` a `"D"`. Nuevo `_DialogoLogin`
  (`QDialog`: correo + contraseña + botones Entrar/Cancelar) — el mismo diálogo sirve para
  "Otro usuario…" (correo vacío) y para un clic sobre un correo conocido (correo prellenado,
  pero la contraseña se pide igual). Es bloqueante (`QDialog.exec()`, la llamada de red ocurre
  en el hilo principal de Qt) — deliberado, el daemon no tiene hilos de trabajo y añadir uno
  solo para un formulario que el usuario abre a propósito es sobre-ingeniería. Menú
  reconstruido: dos líneas deshabilitadas arriba (`Usuario: …` / `Última sync: …`, esta última
  reusa el mismo resumen de una línea que ya arma el tooltip, factorizado a
  `_resumen_evento()` para no mantener el formato en dos lugares), "Sincronizar ahora", submenú
  "Cambiar de usuario" (reconstruido en `aboutToShow` para no quedar desactualizado tras un
  login nuevo), y "Cerrar sesión" reemplazando a "Salir".
- **`doctyp_sync_daemon.py`** (`_loop_con_bandeja`): nuevos closures `_login` (llama
  `sync.login`, si OK hace `sync.guardar_sesion` y dispara un tick inmediato; a diferencia de
  `cmd_login` de la CLI, que bloquea con `sys.exit` si ya hay otra sesión activa, acá se permite
  reemplazarla directo — es un cambio deliberado desde el menú, no hace falta el mismo candado),
  `_listar_usuarios` (`sync.correos_conocidos()`, el ícono ya filtra el correo activo antes de
  mostrarlo), y `_cerrar_sesion` (`sync.logout_remoto` best-effort + `sync.borrar_sesion` +
  `icono.hide()` + `app.quit()` — mismo efecto neto que `doctyp logout`, disparado desde el
  menú en vez de una señal; **no** toca `correos_conocidos`, decisión explícita del usuario: la
  cuenta sigue disponible para volver a loguearse más rápido, solo que pidiendo contraseña de
  nuevo).
- **Verificado en esta sesión**: `python3 -m py_compile` sobre los 3 archivos; prueba aislada
  de `guardar_sesion`/`correos_conocidos` contra un `settings.json` temporal (normalización de
  correo, upsert sin duplicados, orden por uso más reciente) sin tocar la sesión real del
  usuario; construcción real de `DoctypTrayIcon`/`_DialogoLogin` (con `QApplication` real
  contra el mismo Wayland del sandbox) ejercitando tooltip, las dos líneas de menú, el submenú
  reconstruido (excluye correctamente al usuario activo), y la validación del formulario
  (campos vacíos no llaman a `on_login`); `ejecutar_foreground()` corrido de punta a punta con
  `DOCTYP_SETTINGS_PATH` apuntando a un archivo aislado (para no volver a pisar el daemon real
  del usuario como pasó una vez en la Etapa 21 original) — arranca, loguea el motivo de caer a
  headless, tickea sin errores, cierra limpio.
  **No verificado con clics reales en la bandeja de KDE de verdad** (mismo límite del sandbox
  Flatpak de siempre — `isSystemTrayAvailable()` da `False` acá): abrir el diálogo con
  `dialogo.exec()` real, clic en un correo conocido del submenú, y "Cerrar sesión" apagando
  efectivamente el daemon y quitando el ícono quedan pendientes de confirmación del usuario en
  su terminal real.

**Nota sobre el alcance real de la Etapa 22** (sincronización consciente de renombres, pedido
explícito del usuario 2026-07-22 — plan discutido y aprobado antes de implementar, CLAUDE.md
§0). Dos bugs reales confirmados leyendo el código antes de tocar nada: `doctyp change` (único
mecanismo de renombre de documento, cambia `codigo_base` renombrando la carpeta completa)
nunca avisaba al servidor, así que el siguiente sync resucitaba el código viejo (lo volvía a
bajar) Y subía el código nuevo como documento distinto (duplicado); `_subir_carpeta`/
`_bajar_carpeta` nunca borran nada (solo escriben/sobrescriben), así que renombrar a mano un
archivo dentro de `img/` dejaba el nombre viejo huérfano en el lado que no lo renombró, además
de re-transferir el contenido (idéntico) bajo el nombre nuevo como si fuera nuevo. Alcance
confirmado con el usuario: **solo documentos** — las plantillas no tienen ningún mecanismo de
rename hoy y quedan fuera.

- **Parte A — renombre de documento completo, propagación explícita (no heurística).**
  `doctyp change` es la única fuente de este renombre y la máquina que lo ejecuta ya sabe el
  código viejo y el nuevo en el momento exacto en que pasa — no hace falta detectarlo, alcanza
  con avisarle al servidor. La mecánica de mover archivos (carpeta, `.typ`, PDFs, actualizar el
  comentario de cabecera y el campo `correlativo:`) se extrajo de `cmd_change` a
  `core.renombrar_carpeta_documento(slug, codigo_anterior, codigo_nuevo)` (`doctyp.py`), reusada
  tanto por el CLI como por el nuevo endpoint `POST /api/orgs/<slug>/documentos/<codigo_actual>/renombrar`
  (`doctyp_web.py: api_doc_renombrar`) — evita duplicar esa lógica en dos lugares. La fila en
  `doctyp.db` se actualiza con `doctyp_db.renombrar_documento_codigo()` (nueva): un `UPDATE`
  dedicado por `id`, a propósito **sin pasar por el upsert genérico de `guardar_org()`**, que
  matchea filas por `codigo_base` — confirmado leyendo su lógica (`doctyp_db.py:402-433`) que un
  cambio de código ahí se ve como "borrar la fila vieja, crear una nueva" (pierde el `id` interno
  y requeriría reconstruir `document_versions`); la operación dedicada preserva ambos intactos.
  `cmd_change` (`doctyp.py`), tras actualizar el registro local, propaga de inmediato si hay
  sesión activa (`sync.renombrar_documento_remoto`, mismo criterio best-effort que
  `_sincronizar_si_hay_sesion`); si no hay sesión (offline) o la llamada falla, encola el
  renombre en `settings.json → local.renombres_pendientes`
  (`sync.encolar_renombre_pendiente`) — `sincronizar_todo()` los procesa PRIMERO, antes de la
  reconciliación normal por `codigo_base` (`_procesar_renombres_pendientes`, `doctyp_sync.py`):
  si el remoto todavía tiene el código viejo, le avisa recién ahí; si ya tiene el código nuevo
  (otro equipo ya lo sincronizó, o un intento previo parcial), no hace falta nada — en ambos
  casos limpia la entrada. Después de esto, la reconciliación normal encuentra el código nuevo
  en ambos lados como cualquier documento existente, sin ruta especial.
- **Parte B — renombre de archivo dentro de la carpeta (imágenes), detección por hash de
  contenido.** A diferencia de A, acá no hay una acción deliberada que avise — el usuario
  renombra un archivo en su explorador y listo. Mismo principio que usa `git` para detectar
  renombres, sin necesitar ninguna marca persistida: si un archivo desaparece de un lado y
  aparece uno con el MISMO sha256 bajo otro nombre en el lado contrario, es un renombre.
  `_hash_carpeta()` (`doctyp_web.py`) ya calculaba un hash agregado de toda la carpeta a partir
  de hashes por archivo — se factorizó a `_hashes_por_archivo()` (devuelve el detalle, no solo
  el agregado) sin cambiar el resultado de `_hash_carpeta` (verificado: mismo algoritmo, ahora
  compuesto a partir del dict en vez de recalcular inline). Nuevo endpoint de solo lectura
  `GET .../documentos/<codigo_base>/archivos-hash` expone ese detalle — endpoint NUEVO en vez de
  agregarle hashes a `GET .../archivos` (que ya consume el compilador WASM del navegador,
  Etapa 11, esperando `list[str]`; cambiar su forma de respuesta arriesgaba romperlo sin
  necesidad). `doctyp_sync.py` gana el espejo cliente (`_hashes_por_archivo_local`) y
  `_detectar_renombres(locales, remotos)` (empareja por hash los archivos que solo existen en
  un lado). `sincronizar_documento()`, justo antes de la subida/bajada de contenido (rama de
  conflicto por mtime — las otras dos ramas, documento 100% nuevo en un lado, no tienen nada
  con qué comparar y no aplican), llama a `_renombres_detectados()` (best-effort: si el
  endpoint falla, sigue con el sync normal, detectar renombres es un plus, no un requisito) y
  aplica el resultado según quién gane: si sube, `_subir_carpeta()` manda un nuevo campo
  `renombrados: [{de, a}]` en el payload de `/sync` — el destino ('a') se excluye de los bytes
  de `archivos` (contenido idéntico, no hace falta retransferirlo) — y `api_doc_sync`
  (`doctyp_web.py`) aplica `Path.rename()` por cada par ANTES de escribir el resto, sin bytes de
  por medio; si baja, se aplica el mismo `Path.rename()` en LOCAL antes de la descarga completa.
  Archivos sin match de hash siguen exactamente igual que antes (archivo nuevo real → se sube/
  baja completo) — esto no introduce borrado general de archivos ausentes, sigue siendo aditivo
  salvo en el caso específico de un renombre detectado.
- **Verificado end-to-end con un servidor real** (no solo lectura de código ni pruebas
  unitarias): se montó un servidor `doctyp_web.py` de prueba completo (usuario, organización,
  documento con una imagen en `img/`, todo aislado vía `DOCTYP_DB_PATH`/`DOCTYP_ORGS_DIR`/
  `DOCTYP_DOCS_ROOT`/`DOCTYP_SETTINGS_PATH`/`DOCTYP_REMOTE_HOST_OVERRIDE` — sin tocar
  `slep-chinchorro` ni ningún dato real) y se ejercitaron los cinco escenarios reales: (1) sync
  inicial baja el documento completo con su imagen; (2) renombrar la imagen en LOCAL y
  sincronizar deja el servidor con únicamente el nombre nuevo (sin duplicado ni huérfano); (3)
  `doctyp change` con sesión activa deja el servidor con un único documento bajo el código
  nuevo; (4) el mismo renombre sin sesión activa (`encolar_renombre_pendiente`) se resuelve
  correctamente en el siguiente `sincronizar_todo()`, también sin duplicar; (5) renombrar la
  imagen en el SERVIDOR (dirección de bajada) deja el lado local con únicamente el nombre nuevo.
  Los cinco escenarios pasaron. Scripts de prueba descartados tras validar (no quedaron en el
  repo).
- **Sin tocar en esta etapa**: plantillas (confirmado fuera de alcance); borrado general de
  archivos ausentes (la detección de renombre solo actúa sobre pares con hash idéntico — un
  archivo que de verdad se borró en un lado sigue sin propagarse como borrado en el otro, mismo
  comportamiento aditivo de siempre, no fue lo que se pidió). **⚠ Superado en la Etapa 23**: el
  usuario pidió exactamente ese caso a continuación — ver esa nota.

**Nota sobre el alcance real de la Etapa 23** (sincronización consciente de eliminaciones,
pedido explícito del usuario 2026-07-22, extiende directamente la Etapa 22 — plan discutido y
aprobado antes de implementar, CLAUDE.md §0; se trató con el mismo cuidado que cualquier
operación destructiva, aunque el resultado nunca borra de verdad).

- **Por qué hace falta más que comparar los dos lados (a diferencia del renombre).** La
  detección de renombres (Etapa 22) compara SOLO el presente: un archivo que aparece solo-local
  y otro solo-remoto con el MISMO hash es inequívocamente un renombre, sin importar el
  historial. Una eliminación no tiene esa señal — un archivo que existe solo en un lado puede
  ser (a) uno recién creado ahí que todavía no se sincronizó, o (b) uno que existía en ambos
  lados y se borró en el otro. Sin más información, equivocarse en cualquier dirección es
  grave: tratar (a) como eliminación manda a la papelera un archivo nuevo real; tratar (b) como
  "hay que copiarlo" resucita algo que el usuario borró a propósito. La única forma correcta de
  distinguirlos es un punto de referencia de "qué se sabía la última vez que ambos lados
  estuvieron de acuerdo" — el mismo problema que resuelven git/rsync/Dropbox con un ancestro
  común. Antes de esta etapa, `doctyp_sync.py` no guardaba ningún estado así.
- **`.ultimo-sync.json`** (nuevo, dentro de cada carpeta de documento, oculto -- ya queda
  excluido de `_listar_archivos_locales`/`_listar_archivos_carpeta` igual que `.snapshots/`,
  cualquier ruta que empiece con `.`): `{ruta: sha256}` de todos los archivos tal como quedaron
  la última vez que el documento terminó de sincronizar en cualquier dirección — push, pull, o
  el no-op cuando el hash agregado ya coincidía (`sincronizar_documento`, `doctyp_sync.py`,
  todos los puntos de salida exitosos). Si no existe (documento sincronizado antes de esta
  etapa, o primera vez), la detección de eliminación simplemente no dispara hasta el primer
  sync exitoso que lo cree — comportamiento seguro por defecto, sin falsos positivos en la
  transición.
- **`_detectar_renombres` (Etapa 22) se generalizó a `_detectar_cambios_archivos(locales,
  remotos, base)`** (`doctyp_sync.py`): primero empareja renombres exactamente igual que antes;
  sobre lo que queda sin emparejar, compara contra `base` -- si una ruta estaba ahí y el lado
  que todavía la tiene no le cambió el hash desde el último sync, su ausencia en el otro lado es
  una eliminación real (no un archivo nuevo, que nunca habría estado en `base`; no uno editado
  después del último sync, que ya no calzaría con el hash de `base` -- ahí se deja para el flujo
  normal en vez de arriesgar un borrado sobre algo modificado). Devuelve `eliminados_local`
  (rutas que ya no están en local -- hay que avisarle al servidor) y `eliminados_remoto` (rutas
  que ya no están en el servidor -- hay que aplicarlo en local), además de `renombres`.
- **Nunca se borra de verdad, en ningún lado.** `eliminados_local` viaja en un campo nuevo
  `eliminados` del payload de `POST .../documentos/<codigo>/sync` (`_subir_carpeta`, junto al
  `renombrados` que ya existía); `api_doc_sync` (`doctyp_web.py`) los mueve a
  `dest_dir/.trash/<nombre>_eliminado_<marca>.<ext>` (mismo criterio de marca de tiempo que
  `_respaldar_typ_antes_de_sync`) en vez de `Path.unlink()`. `eliminados_remoto` se aplica en
  LOCAL con el mismo criterio (`_mover_a_trash`, espejo cliente/servidor) antes de la bajada
  completa -- el pedido explícito solo exigía la papelera en remoto, pero aplicar lo mismo en
  local es igual de barato y evita que un archivo eliminado remotamente quede huérfano en el
  equipo que lo recibe. `.trash/` queda excluido de los listados de archivos igual que
  `.snapshots/`, así que no reaparece como "archivo nuevo" en el siguiente sync. No hay comando
  de "restaurar desde `.trash`" (no se pidió una UX de recuperación, solo que quedara
  recuperable) ni política de limpieza de `.trash/` (no se pidió).
- **Alcance**: solo archivos DENTRO de la carpeta de un documento, nunca el `.typ` principal --
  borrar el `.typ` es borrar el documento entero, ya cubierto por `doctyp delete`, no por este
  mecanismo de archivos sueltos (imágenes). Documentos, no plantillas (mismo alcance ya
  confirmado en la Etapa 22).
- **Verificado end-to-end con un servidor real** (mismo montaje que la Etapa 22: usuario, org,
  documento con dos imágenes, todo aislado vía `DOCTYP_DB_PATH`/`DOCTYP_ORGS_DIR`/
  `DOCTYP_DOCS_ROOT`/`DOCTYP_SETTINGS_PATH`/`DOCTYP_REMOTE_HOST_OVERRIDE`, sin tocar
  `slep-chinchorro`): (1) eliminar una imagen en LOCAL y sincronizar deja el servidor con la
  otra imagen únicamente, la eliminada en `.trash/` del servidor con su contenido intacto, sin
  duplicar; (2) un segundo sync no la resucita; (3) eliminar la imagen restante en el SERVIDOR y
  sincronizar deja local sin esa imagen, movida a `.trash/` local, sin volver a subirse sola;
  (4) un archivo genuinamente nuevo se sube normal, nunca se confunde con una eliminación. Los
  cuatro escenarios pasaron. Scripts de prueba descartados tras validar (no quedaron en el
  repo).

---

## 15. TL;DR para Claude Code

1. No toques el estilo de `lib.typ` sin orden explícita.
2. Verifica §14 antes de usar comandos v3; si la etapa está pendiente, aplica el flujo anterior.
3. Crea informes con `doctyp new "…"` (correlativo automático por organización; carpeta
   autocontenida con plantilla copiada). Sube versión con `doctyp save <doc-ref> --m "…"`.
4. Rellena los `// TODO` según la estructura canónica (§8) y la API (§11).
5. **No compiles automáticamente** ni levantes `doctyp web` sin petición explícita.
6. Nunca inventes correlativos ni edites `org.json` a mano.