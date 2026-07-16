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
               puerto expuesto: 8787 (el reverse proxy del VPS apunta aquí; no se
               implementa proxy propio)
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
  exposición real la controla el mapeo de puertos y el proxy del VPS).
- **⚠ Punto técnico a resolver en la Etapa 18:** la vista previa de tinymist usa un
  **puerto dinámico propio** (static server + data plane WS, CLAUDE.md Etapa 15) que
  hoy funciona porque navegador y proceso comparten host. En Docker ese puerto queda
  dentro del contenedor: hay que **tunelizarlo a través de doctyp_web.py** (proxy
  HTTP/WS interno bajo `/preview/…`) o publicar un rango de puertos controlado.
  Prerrequisito del editor en Docker.
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
| 18 | **Docker:** Dockerfile + compose (servicio único), `DOCTYP_DOCS_ROOT`/`DOCTYP_DB_PATH`/`DOCTYP_BIND`, túnel del puerto de preview de tinymist (⚠ §2), fuentes por volumen, override de desarrollo, verificación de que la app se levanta tal cual está hoy | Pendiente |
| 19 | **Registro en SQLite:** esquema §3, módulo `doctyp_db.py` (acceso único para CLI/web/API), reemplazo de lectura/escritura de `org.json` en el core, correlativos transaccionales, `doctyp migrate` (+ `--check`), archivo de los JSON como `*.migrated` | Pendiente |
| 20 | **Multiusuario:** users/sessions/api_tokens (scrypt), email como identificador, login/logout + perfil + admin de usuarios en la SPA, roles en `org_members`, invitaciones con token de un solo uso, rate-limit login | Pendiente |
| 21 | **CLI remoto:** `doctyp login/logout/remote`, comandos contra la API (`--local` como escape), flujo pull/save con detección de conflicto por hash, compilación remota opcional | Pendiente |
| 22 | **API de composición:** endpoints v1, esquema de bloques (`schema_version` 1), traductor `doctyp_bloques.py` con sanitización anti-inyección Typst, marcadores en `.typ`, subida de imágenes, endpoint PDF, estado `desacoplado` | Pendiente |

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