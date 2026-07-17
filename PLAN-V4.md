# PLAN-V4.md — doctyp: Dockerización, Registro en SQLite, Multiusuario, CLI Remoto y API de Composición

> **Estado: APROBADO** (2026-07-14; reestructurado 2026-07-15 — separación en dos
> proyectos independientes; actualizado mismo día — **SQLite como fuente de verdad
> única, se elimina `org.json`**, ver §0 y §3). Plan de arquitectura v4 para `doctyp`.
> Extiende la arquitectura v3 (CLAUDE.md). Las etapas nuevas (18–22) continúan la
> numeración de CLAUDE.md §14 y deben registrarse ahí al cerrarse.
>
> **Regla vigente:** plan antes de código. Cada etapa presenta su desglose y espera
> aprobación explícita antes de implementar.

---

## 0. Decisiones estructurales (2026-07-15)

### 0.1 Dos proyectos independientes

El plan v4 original se divide en dos sistemas independientes, cada uno con su propio
repositorio, gestión en Claude, despliegue en el servidor y ciclo de vida:

1. **doctyp (este repo):** motor documental. Se dockeriza, migra su registro a
   **SQLite**, y gana **multiusuario** (email como identificador; las organizaciones
   agrupan usuarios), **CLI conectado al servidor** y una **API de composición de
   documentos** para consumidores externos (bloques JSON → Typst → PDF).
2. **Netdesk (repo nuevo, plan propio — `NETDESK-PLAN-V1.md`):** gestor de proyectos
   y diagramas de red/CCTV. **Consume doctyp exclusivamente vía API** — nunca toca su
   filesystem ni su base de datos.

Contratos entre sistemas: API HTTP de doctyp + `codigo_base` como referencia de
documento + **email** como identificador común de usuario + `slug` como identificador
común de organización. Deep link Netdesk→doctyp: `/documentos/<codigo_base>` en otra
pestaña; sin código compartido.

### 0.2 SQLite como fuente de verdad única (reemplaza `org.json`)

**`org.json` se elimina.** Todo el registro — organizaciones, equipos,
usuarios/autores, plantillas, documentos, versiones y correlativos — vive en una base
de datos **SQLite** (`doctyp.db`, módulo `sqlite3` de la stdlib — se mantiene el
principio stdlib-only, cero dependencias nuevas).

- **En la BD:** registro y metadatos (todo lo que hoy está en `org.json`) + identidad
  (usuarios, sesiones, tokens).
- **En el filesystem (sin cambios):** los archivos `.typ` de documentos, las carpetas
  `img/`, los snapshots de `.snapshots/`, y las plantillas (`lib.typ` y compañía) —
  la BD guarda sus rutas relativas, nunca su contenido.
- **`settings.json` se conserva** con su rol v3 estricto: **solo configuración local
  del cliente** (org activa, autor activo en modo local, preferencias, `local.remote`).
  No es registro ni fuente de verdad de datos.
- **Beneficios directos** (cierran hallazgos de la auditoría de una vez):
  - Correlativos con transacción (`BEGIN IMMEDIATE` + `UPDATE`) → sin condición de
    carrera.
  - Escrituras ACID con WAL → sin registros corruptos ni necesidad del patrón de
    escritura atómica de JSON.
  - Concurrencia multiusuario real sin locks de archivo artesanales.
  - Integridad referencial (FKs) entre orgs/usuarios/documentos/versiones.
- **Migración:** comando único `doctyp migrate` (idempotente) que importa
  `organizations/*/org.json` → `doctyp.db` y archiva los JSON como
  `org.json.migrated` (respaldo de solo lectura, no se vuelve a leer).
- El **modo local del CLI usa la misma BD** (`doctyp.db` junto a `doctyp.py`): local y
  servidor comparten esquema y código de acceso; la única diferencia es dónde corre.

---

## 1. Stack (doctyp)

| Capa | Tecnología | Justificación |
|---|---|---|
| Backend | `doctyp_web.py` (Python 3.12, stdlib) + módulos nuevos de registro, auth y composición | No perder el código Python; principio stdlib-only |
| Base de datos | **SQLite** (`sqlite3`, stdlib) — `doctyp.db`, modo WAL. **Fuente de verdad única** del registro e identidad | §0.2 |
| Frontend | SPA Vue 3 existente (`web/`), extendida con login/logout y gestión de usuarios | Sin cambios estructurales |
| CLI | `doctyp.py`: modo local (misma BD local) y modo remoto (cliente HTTP `urllib`, stdlib) | Trabajo colaborativo contra el servidor |
| Compilación | typst + tinymist (binarios en la imagen) | Sin cambios |

---

## 2. Topología Docker

```
docker-compose.yml
└── doctyp   → único servicio (python:3.12-slim)
               + binarios typst y tinymist
               + fuentes Liberation (Museo Sans montada por volumen, NUNCA en la imagen*)
               puerto interno: 8787 — SIN mapeo fijo al host: el VPS corre Traefik,
               que descubre el contenedor (provider Docker + labels) y le rutea el
               tráfico por la red compartida; no se implementa proxy propio
               volúmenes:
                 · data       → doctyp.db (WAL) + organizations/ (plantillas)
                 · docs_data  → DOCS_ROOT (documentos, img/, .snapshots/)
                 · fonts      → fuentes licenciadas del host
```

\* Hallazgo de auditoría: la licencia de Museo Sans no permite redistribuirla dentro
de una imagen.

- **`DOCS_ROOT` en contenedor:** variable de entorno `DOCTYP_DOCS_ROOT` (nueva, con
  fallback a la resolución por SO actual) apuntando al volumen `docs_data`. Análogo
  `DOCTYP_DB_PATH` para ubicar `doctyp.db` en el volumen `data`.
- **Bind:** `DOCTYP_BIND` (default actual `127.0.0.1`; en contenedor `0.0.0.0` — la
  exposición real la controla Traefik, no un mapeo de puertos del host).
- **Traefik (reverse proxy del VPS, ya instalado):** el servicio NO publica puerto en
  el host — se une a la red externa de Traefik y declara labels
  (`traefik.enable=true`, router con la regla de dominio, `…services.…loadbalancer.
  server.port=8787`). Traefik detecta el contenedor al levantarse y le asigna la
  ruta/TLS; da igual qué puerto efímero tenga hacia afuera. Ventaja directa: **una
  sola instancia central del servidor** atendida por dominio, que es justamente lo que
  garantiza el **correlativo global por organización** (§3: todos los usuarios crean
  documentos contra la misma BD, `BEGIN IMMEDIATE` en `correlative_counters`).
- **Preview de tinymist detrás de Traefik — resuelto (2026-07-17, ver DESPLIEGUE.md):**
  decisión final del usuario, distinta a la primera hipótesis de este documento (proxy
  interno bajo `/preview/…`, descartada). En vez de tunelizar por Python, el data plane
  de tinymist (`doctyp_preview_server.py`) pasa de puerto **aleatorio** a un puerto
  **fijo** (`DOCTYP_PREVIEW_DATA_PORT`, default `37800`), bindeado a `0.0.0.0`
  (`DOCTYP_PREVIEW_BIND`) para que sea alcanzable desde otro contenedor. Traefik declara
  un **segundo router+service** sobre el mismo contenedor (`docker-compose.yml`:
  `traefik.http.routers.doctyp-preview...`, `loadbalancer.server.port=37800`) apuntando
  a un subdominio dedicado (`doctyp-preview.<dominio>`) — mismo patrón que Traefik
  documenta oficialmente para exponer más de un puerto de un mismo servicio Docker.
  `PreviewServer.info()` reporta `DOCTYP_PREVIEW_PUBLIC_URL` (ese subdominio) como
  `static_url` en vez de `127.0.0.1:<puerto>`; sin esa variable (desarrollo local, fuera
  de Docker) el comportamiento no cambia. El control plane (WebSocket que solo habla
  `doctyp_web.py`, nunca el navegador) sigue interno en `127.0.0.1` con puerto
  aleatorio, sin cambios. La exclusión mutua "una preview a la vez" que ya garantizaba
  `_asegurar_preview_generico()` (`doctyp_web.py`) es lo que hace seguro reusar un
  puerto fijo entre reinicios del subproceso — verificado en vivo con tinymist real:
  arranque, HTTP 200 del data plane, `stop()` limpio, y un segundo arranque en el mismo
  puerto sin colisión.
- `compose.override.yml` para desarrollo: montaje del código, `--no-build`, Vite dev
  server, puertos extra.
- **Backups:** `sqlite3 doctyp.db ".backup ..."` programado (backup en caliente,
  consistente con WAL) + volúmenes `docs_data` y plantillas. Un solo archivo de BD
  simplifica todo el plan de respaldo.

---

## 3. Registro en SQLite (Etapa 19) — esquema

```
-- Identidad y acceso
users(id, email UNIQUE, password_hash NULLABLE, nombre, cargo, activo, created_at)
      -- password_hash NULL = usuario local sin credenciales (CLI monousuario)
sessions(id, user_id FK, token_hash, expires_at, ip, user_agent)     -- SPA (cookie)
api_tokens(id, user_id FK, nombre, token_hash, scopes, expires_at,
           last_used_at)                                             -- CLI y Netdesk (Bearer)

-- Registro (reemplaza org.json)
organizations(id, slug UNIQUE, nombre, sigla, config_json)
org_members(org_id, user_id, role TEXT CHECK(role IN ('admin','member')),
            PK(org_id, user_id))        -- reemplaza autores[]: usuario = autor = miembro
teams(id, org_id FK, nombre, descripcion)
team_members(team_id, user_id, PK(team_id, user_id))
templates(id, org_id FK, nombre UNIQUE(org_id), path_rel, es_default)
documents(id, org_id FK, codigo_base UNIQUE(org_id), correlativo, anio,
          tipo, categoria, titulo, autor_id FK users, equipo_id FK teams NULLABLE,
          template_id FK, path_rel, estado, desacoplado BOOL DEFAULT 0, created_at)
document_versions(id, document_id FK, version, mensaje, snapshot_rel, hash,
                  created_by FK users, created_at)
correlative_counters(org_id, anio, ultimo, PK(org_id, anio))
```

- **Reglas invariantes de v3 que se conservan tal cual:** correlativo global-anual-
  secuencial auto-asignado (ahora con `BEGIN IMMEDIATE`; NUNCA se inventa), rutas
  relativas para portabilidad, documentos-carpeta autocontenidos, snapshots en
  `.snapshots/`, `lib.typ` intocable.
- **Validaciones existentes migran a constraints/lógica sobre la BD:** no eliminar
  autor/equipo con documentos asignados (FK + chequeo), unicidad de código por org
  (UNIQUE), sanitización de títulos antes de escribir.
- El core (`doctyp.py`) reemplaza las funciones de lectura/escritura de `org.json` por
  un módulo de acceso a datos (`doctyp_db.py`) usado por CLI, backend web y API — una
  sola implementación.
- **Migración `doctyp migrate`:** importa cada `org.json`, crea `users` desde
  `autores[]` (email obligatorio; si falta, lo pide interactivamente), archiva los
  JSON como `*.migrated`. Idempotente y verificable (`doctyp migrate --check` compara
  conteos).

---

## 4. Multiusuario (Etapa 20)

- **Email = identificador único de usuario** en todo el ecosistema (doctyp y Netdesk).
- **Hash de password:** `hashlib.scrypt` (stdlib; Argon2id requeriría dependencia
  externa).
- **Autorización:** un usuario accede a una org si figura en `org_members`. Roles:
  `admin` (gestiona miembros/equipos/plantillas) y `member` (documenta).
- **Alta de usuarios:** los creados por la migración reciben invitación con token de
  un solo uso para fijar su password (pasan de `password_hash NULL` a credencial real).
- **Arranque y primer login (bootstrap):** los usuarios SON los autores (ya es el
  modelo: `org_members` reemplaza `autores[]`). Dos casos que el login debe resolver
  sin intervención manual sobre la BD:
  1. **Sin usuarios** (`users` vacía, instalación nueva): la SPA muestra una pantalla
     de configuración inicial — crear el primer usuario (nombre, email, password) —
     en lugar del login; ese usuario queda como `admin`. En el CLI local, cualquier
     comando que requiera autor dispara el alta interactiva equivalente.
  2. **Único usuario sin password** (`password_hash NULL`, típico tras
     `doctyp migrate` desde el modo monousuario): la pantalla de login lo detecta y
     le pide **crear su password en ese primer login**, directamente y sin token de
     invitación (no hay otro usuario que se la envíe ni riesgo de suplantación: es
     el único). El flujo de invitación con token queda reservado para las altas en
     orgs que ya tienen más de un usuario.
- Sesiones: cookie `httpOnly` + `SameSite=Lax`; login/logout en la SPA; todas las
  rutas `/api/…` exigen sesión o Bearer token (salvo `/api/login` y salud).
- Rate-limit simple en login (contador en memoria por IP; suficiente detrás del proxy).
- **SPA:** vistas de login, perfil (password, tokens de API) y administración de
  usuarios de la org (solo `admin`). El selector de "autor activo" desaparece para
  usuarios normales: **el autor es el usuario logueado**; `admin` conserva la vista de
  todos los documentos.

---

## 5. CLI conectado al servidor (Etapa 21)

El CLI conserva el **modo local** (misma `doctyp.db` local, §0.2) y gana un **modo
remoto**:

```
doctyp login <url>            # email+password → api_token guardado en settings.json
                              # (local.remote = {url, token})
doctyp logout                 # revoca el token en el servidor y lo borra localmente
doctyp remote status          # servidor, usuario, org activa remota
```

- Con `local.remote` configurado, los comandos (`list`, `new`, `save`, `compile`,
  `org/team/author *`) operan **contra la API** (`urllib.request`). Flag `--local`
  fuerza el modo local.
- **Flujo remoto:** `new` crea el documento en el servidor; `pull <ref>` descarga el
  `.typ` (y su plantilla) a una carpeta de trabajo local; `save` sube contenido y
  versiona server-side; `compile` local (typst instalado) o remoto (`--server`,
  descarga el PDF).
- **Cada usuario guarda su información en el servidor:** la identidad del token define
  el autor; el CLI no escribe la BD del servidor directamente, solo vía API.
- Conflictos: `save` envía el hash de la versión base; si el servidor tiene una más
  nueva, rechaza con 409 → `pull` primero (sin merge automático — simple y explícito).
- El modo local queda en mantenimiento (vía offline / monousuario), sin features
  nuevas.

---

## 6. API de composición de documentos (Etapa 22)

API pública (autenticada por Bearer token) pensada para **Netdesk** y cualquier
consumidor futuro. Permite redactar informes según las plantillas de doctyp **sin
saber Typst**.

### 6.1 Endpoints

```
POST   /api/v1/orgs/<slug>/documentos                    # crear desde plantilla (meta JSON)
GET    /api/v1/orgs/<slug>/documentos/<codigo>           # metadatos + estado
PUT    /api/v1/orgs/<slug>/documentos/<codigo>/bloques   # cuerpo completo como JSON de bloques
GET    /api/v1/orgs/<slug>/documentos/<codigo>/bloques   # último JSON de bloques guardado
POST   /api/v1/orgs/<slug>/documentos/<codigo>/imagenes  # multipart → img/ del documento,
                                                         # devuelve {ref} para bloques figura
POST   /api/v1/orgs/<slug>/documentos/<codigo>/versiones # commit de versión (mensaje)
GET    /api/v1/orgs/<slug>/documentos/<codigo>/pdf       # compila on-demand y devuelve el PDF
GET    /api/v1/orgs/<slug>/plantillas                    # plantillas disponibles
```

### 6.2 Esquema de bloques (contrato JSON, versionado)

```json
{
  "schema_version": 1,
  "bloques": [
    { "tipo": "titulo",  "nivel": 1, "texto": "Diagnóstico de red" },
    { "tipo": "parrafo", "texto": "El establecimiento presenta…" },
    { "tipo": "lista",   "ordenada": false, "items": ["Switch core", "12 AP"] },
    { "tipo": "cita",    "texto": "…", "fuente": "TI-MAN-GOB_2026-0020" },
    { "tipo": "figura",  "ref": "img/diagrama-v3.svg", "caption": "Topología propuesta",
                         "ancho_pct": 80 },
    { "tipo": "tabla",   "cabecera": ["Ítem", "Cant."], "filas": [["UTP cat6", "305 m"]] },
    { "tipo": "salto" }
  ]
}
```

- Tipos mínimos v1: `titulo` (niveles 1–3), `parrafo`, `lista`, `cita`, `figura`,
  `tabla`, `salto`. Extensible por `schema_version` (el servidor rechaza versiones
  que no entiende).
- Marcas inline mínimas y seguras: `**negrita**`, `_cursiva_`, `` `código` ``
  (subconjunto Markdown → Typst). Todo lo demás se **escapa**: el traductor sanitiza
  para que un consumidor de la API **no pueda inyectar código Typst**.

### 6.3 Traducción y coexistencia con edición manual

- Módulo nuevo `doctyp_bloques.py`: traducción **determinista** JSON→Typst. El JSON se
  persiste en la carpeta del documento (`bloques.json`, snapshoteado junto al `.typ`
  en cada versión).
- El cuerpo generado se escribe entre marcadores en el `.typ`:
  `// <doctyp:bloques>` … `// </doctyp:bloques>` (regex anclada, mismo patrón
  quirúrgico de `actualizar_meta_typ`). La prosa manual fuera de los marcadores **se
  preserva**.
- Si un usuario edita manualmente **dentro** de los marcadores desde el editor doctyp,
  el documento se marca `desacoplado = 1` (columna de `documents`): el siguiente
  `PUT /bloques` exige `?forzar=true` para sobrescribir (Netdesk muestra la
  advertencia).
- Los diagramas de Netdesk llegan como **imágenes ya renderizadas** (SVG/PNG del
  snapshot de versión) vía el endpoint de imágenes + bloque `figura`. doctyp no conoce
  el modelo del diagrama.

---

## 7. Roadmap (etapas 18–22, continúa CLAUDE.md §14)

| Etapa | Alcance | Estado |
|---|---|---|
| 18 | **Docker:** Dockerfile + compose (servicio único, sin puerto publicado en el host: labels de Traefik + red compartida, ⚠ §2), `DOCTYP_DOCS_ROOT`/`DOCTYP_DB_PATH`/`DOCTYP_ORGS_DIR`/`DOCTYP_SETTINGS_PATH`/`DOCTYP_BIND`, fuentes por volumen, override de desarrollo, verificación real con podman (build, CLI, auth, persistencia entre restarts, shutdown limpio), **subdominio dedicado para la preview de tinymist** (`DOCTYP_PREVIEW_DATA_PORT`/`DOCTYP_PREVIEW_BIND`/`DOCTYP_PREVIEW_PUBLIC_URL` + segundo router de Traefik, ver nota) | **Completada** |
| 19 | **Registro en SQLite:** esquema §3, módulo `doctyp_db.py` (acceso único para CLI/web/API), reemplazo de lectura/escritura de `org.json` en el core, correlativos transaccionales, `doctyp migrate` (+ `--check`), archivo de los JSON como `*.migrated` | **Completada** |
| 20 | **Multiusuario:** users/sessions (scrypt), email como identificador, login/logout en la SPA, **bootstrap** (sin usuarios → crear el primero como admin; único usuario sin password → fijarla en el primer login, ver §4) | **Completada** (alcance reducido — ver nota: sin `api_tokens`, sin roles/admin de usuarios en la SPA, sin invitaciones, sin rate-limit persistente) |
| 21 | **CLI remoto:** `doctyp login/logout/remote`, comandos contra la API (`--local` como escape), flujo pull/save con detección de conflicto por hash, compilación remota opcional | Pendiente (fuera de alcance por decisión explícita del usuario, 2026-07-17) |
| 22 | **API de composición:** endpoints v1, esquema de bloques (`schema_version` 1), traductor `doctyp_bloques.py` con sanitización anti-inyección Typst, marcadores en `.typ`, subida de imágenes, endpoint PDF, estado `desacoplado` | Pendiente (fuera de alcance por decisión explícita del usuario, 2026-07-17) |

**Nota sobre el alcance real de las Etapas 18-20** (ejecutadas juntas el 2026-07-17, sesión
larga; decisión explícita del usuario de dejar fuera las Etapas 21/22 — CLI remoto y API de
composición — y de cerrar solo motor de datos + login + Docker "para tener algo corriendo hoy"):

- **Etapa 19 (SQLite):** `doctyp_db.py` (nuevo) implementa el esquema de §3 con una capa de
  compatibilidad deliberada: `cargar_org(slug)`/`guardar_org(slug, dict)` devuelven/reciben
  el mismo shape de dict que tenía `org.json`, en vez de que cada función de `doctyp.py`/
  `doctyp_web.py` hable SQL directo. Esto evitó reescribir los ~54 sitios que ya llamaban
  `cargar_org`/`guardar_org` (incluye `autor_crear`, `equipo_editar`, `buscar_doc_org`, etc.)
  — el único cambio real en esos módulos fue swap del backend de almacenamiento, no de su
  API. La única vía que sí necesitó ruta transaccional propia (no bastaba el round-trip de
  dict) es el correlativo: `asignar_correlativo(slug, anio)` hace `BEGIN IMMEDIATE` + lee
  máximo + escribe en una sola transacción — verificado con 20 asignaciones concurrentes
  reales (hilos Python) sin duplicados ni saltos. `doctyp migrate` (nuevo subcomando)
  importa cada `org.json`, crea la fila en la BD, y renombra el original a
  `org.json.migrated` (respaldo de solo lectura); `--check` compara conteos sin escribir.
  **Bug pre-existente encontrado y corregido durante la verificación** (no introducido por
  esta etapa, pero solo se manifestaba con una org recién creada sin autores — caso que
  nunca se había probado hasta ahora): `autor_activo()` (`doctyp.py`) caía a
  `AUTHOR_DEFAULTS` usando la clave `autor` (shape v2 de `settings.json → local.author`) en
  vez de `nombre` (shape real del modelo de organizaciones), reventando `cmd_nuevo` con
  `KeyError: 'nombre'` en cualquier org sin autores. Corregido para traducir correctamente.
  Verificado exhaustivamente contra una **copia aislada** de los datos reales del usuario
  (`organizations/` + `~/Documentos/doctyp/`, nunca los originales): migración con
  reconstrucción byte-a-byte idéntica (config, documentos, versiones, autores), CLI completo
  (`list`/`new`/`save`/`team new`/`history`), y `doctyp web` con API+SSE reales.
- **Etapa 20 (login):** `doctyp_auth.py` (nuevo) implementa exactamente lo pedido — scrypt
  para hash de password, sesiones por cookie `HttpOnly`+`SameSite=Lax` (14 días), rate-limit
  simple en memoria por IP, y el bootstrap de dos casos decidido con el usuario (§4): sin
  usuarios → alta del primer usuario como admin implícito; único usuario sin password (caso
  real tras `doctyp migrate` desde monousuario) → fijar password en el primer login sin
  token de invitación. **Recortado del alcance original de §4/§7** (explícitamente, para
  caber en el tiempo disponible): sin tabla `api_tokens` (innecesaria sin Etapa 21/22 — CLI
  remoto y API pública, que son las que la iban a consumir), sin columna `role`/vista de
  administración de usuarios en la SPA (con un solo usuario típico hoy, no bloquea), sin
  invitaciones con token (solo aplica a altas en orgs con 2+ usuarios, no es el caso de
  arranque), rate-limit en memoria del proceso (se resetea con cada restart del contenedor,
  no persistente — suficiente para el volumen actual, revisar si el tráfico crece). Todas las
  rutas `/api/...` (incluye SSE y el bridge WS de tinymist LSP) exigen sesión salvo
  `/api/auth/bootstrap|primer-usuario|fijar-password-inicial|login`. Frontend: `useAuth.js`
  (mismo patrón "bus" de módulo-singleton que `useOrgContext.js`), `LoginView.vue` (una sola
  vista para los 3 modos: alta del primer usuario, fijar password inicial, login normal),
  guard de navegación en `router.js`, botón "Salir" + nombre del usuario en la topbar de
  `App.vue`. Verificado end-to-end con `curl` real contra `doctyp web` (bootstrap, alta,
  fijar password, login, cookie, acceso protegido, logout, invalidación de sesión) y build
  real de la SPA (`npm run build` sin errores) — **sin verificación visual en navegador**
  (Playwright no estaba instalado en esta sesión y instalarlo + descargar Chromium no era
  compatible con el plazo "hoy"; el código de los componentes Vue se revisó a mano).
- **Etapa 18 (Docker):** `Dockerfile` (multi-stage: `node:20-slim` para el build de la SPA +
  `python:3.12-slim` runtime con `typst` y `tinymist` descargados de sus releases oficiales
  de GitHub, mismo mecanismo que ya usa `init`), `docker-compose.yml` (sin puerto publicado,
  labels de Traefik, red externa `traefik`, volúmenes `data`/`docs_data`/`fonts`) y
  `compose.override.yml` (desarrollo local: publica `127.0.0.1:8787`, monta el código fuente,
  reemplaza la red `traefik` por la red default de compose ya que esa red externa no existe
  fuera del VPS). **Verificado de extremo a extremo con podman real** (`flatpak-spawn --host`,
  ver nota de metodología abajo): build completo, `doctyp org new`/`template new`/`new` desde
  dentro del contenedor, auth completo vía API, y **persistencia real entre restarts** de
  `doctyp.db`, los documentos y `settings.json` (los tres viven bajo el volumen `data`).
  **Dos bugs reales de Docker encontrados y corregidos:**
  (1) `organizations/` se copiaba a la imagen con `COPY` — se retiró: vive enteramente en el
  volumen `data` para que un rebuild nunca pise plantillas ya creadas por el usuario.
  (2) `docker stop`/`restart` mandan **SIGTERM** (no SIGINT) al proceso `PID 1`; sin manejarlo,
  Python lo ignoraba, `serve_forever()` nunca retornaba, y el orquestador esperaba el grace
  period completo (10s) antes de forzar SIGKILL — saltándose el `finally` que detiene
  `tinymist`/el LSP (mismo problema de huérfanos que CLAUDE.md ya documentaba para
  `pkill -9` manual, ahora también posible vía Docker). Fix en `cmd_web`
  (`doctyp_web.py`): handler de `SIGTERM` que reusa la misma excepción que ya maneja Ctrl+C.
  Verificado: `docker kill -s TERM` produce "Servidor detenido." y exit 0; `docker restart`
  pasó de ~10.2s (timeout + SIGKILL) a ~0.2s.
  **Vista previa de tinymist detrás de Traefik: resuelto en un pase posterior (mismo
  día).** La primera versión de esta nota decía "pendiente, no bloqueante" (túnel bajo
  `/preview/…`) — el usuario, al desplegar de verdad en el VPS, pidió en su lugar un
  subdominio dedicado (`doctyp-preview.tinorte.cl`). Ver el detalle completo en §2 (nota
  "Preview de tinymist detrás de Traefik — resuelto") y DESPLIEGUE.md.
- **Nueva variable de entorno no listada originalmente en §2:** `DOCTYP_SETTINGS_PATH`
  (`doctyp.py: registro_path()`) — sin ella, `settings.json` (org/autor activos) vivía en
  `/app` (no persistido) y se perdía en cada restart del contenedor aunque `doctyp.db` y los
  documentos sí sobrevivieran. Ahora apunta a `/data/settings.json`, dentro del volumen `data`
  ya existente (no fue necesario un volumen nuevo).
- **Nota de metodología:** toda la verificación de esta sesión se hizo contra **copias
  aisladas** de los datos reales del usuario en el scratchpad de la sesión (nunca contra
  `organizations/`/`~/Documentos/doctyp/` originales) y, para Docker, contra **volúmenes
  podman nuevos y vacíos** (nunca bind-mounts a rutas reales del host). Se encontró y limpió
  de inmediato un incidente menor durante las primeras pruebas: antes de aislar `DOCTYP_
  DOCS_ROOT`/`DOCTYP_ORGS_DIR` con variables de entorno, un `doctyp new` de prueba escribió
  una carpeta de documento ficticia (`TI-INF-SFW_2026-0040`, sin registro en `org.json`) bajo
  el `~/Documentos/doctyp/slep-chinchorro/` real — se detectó de inmediato (el registro real
  nunca la referenció) y se borró antes de continuar; no afectó ningún documento real.
  Confirmado con `git status` + inspección de `~/Documentos/doctyp/` al cierre de la sesión
  que no queda ningún rastro.
- **`npm install` en `web/`** se re-ejecutó durante esta sesión (drift preexistente: el
  `package.json` ya declaraba `vue-router` desde la Etapa 17, pero `node_modules/` no lo
  tenía instalado) — no relacionado con el trabajo de esta sesión, solo destrabó el build.

**Reglas de cierre por etapa:**
1. Actualizar esta tabla y CLAUDE.md §14 (incluye reescribir en CLAUDE.md toda
   referencia a `org.json` cuando cierre la Etapa 19).
2. Mientras una etapa esté `Pendiente`, sus comandos, tablas y endpoints **no existen**
   — no asumirlos ni referenciarlos como hechos.

---

## 8. Pendientes explícitos (no bloquean)

- Scopes finos en `api_tokens` (v1: token de acceso completo del usuario).
- Bloques adicionales del esquema (v2): `nota`, `codigo`, `ecuacion`, `anexo`.
- Retiro definitivo del modo local del CLI (sin fecha).
- Si el volumen multiusuario crece más allá de lo que SQLite+WAL maneja cómodo
  (decenas de escritores concurrentes), la salida natural es PostgreSQL — el módulo
  `doctyp_db.py` concentra el acceso justamente para que ese cambio sea localizado.