# PLAN-V4.md — Dockerización, PostgreSQL, Auth, Proyectos y Diagramas

> **Estado: APROBADO** (2026-07-14; actualizado 2026-07-15 — dos clientes web
> separados e integración por deep link, ver §0). Plan de arquitectura v4 para
> `doctyp`. Extiende la arquitectura v3 (CLAUDE.md). Las etapas nuevas (18–23)
> continúan la numeración de CLAUDE.md §14 y deben registrarse ahí al cerrarse.
> (Renumeradas desde 17–22: la Etapa 17 quedó ocupada por las mejoras de UX del
> 2026-07-15, ya cerradas en CLAUDE.md §14.)
>
> **Regla vigente:** plan antes de código. Cada etapa presenta su desglose y
> espera aprobación explícita antes de implementar.

---

## 0. Decisiones de alcance

- **Opción B (transicional):** el backend Python (`doctyp_web.py`) **no se elimina ni se
  reescribe ahora**. Se containeriza intacto como *doc-service* interno. Un backend nuevo
  en **Node** actúa como servicio principal y proxea hacia él. El port de módulos
  Python→Node se hará gradualmente, endpoint por endpoint, en etapas futuras.
- El **CLI sigue funcionando** sobre `org.json`; a futuro quedará obsoleto o se conectará
  al backend (trabajo colaborativo post-VPS). **Sin sincronización bidireccional**
  BD↔`org.json`.
- **Fuentes de verdad divididas durante la transición:**
  - PostgreSQL → identidad (users/sessions), organizaciones/equipos (lado servidor),
    proyectos, diagramas, IPAM, catálogo, costos.
  - `org.json` (doc-service Python) → registro documental, correlativos, versiones de
    documentos, plantillas — hasta que se porte.
  - Node guarda solo la **referencia** (`documents.codigo_base`) para enlazar documentos
    a proyectos sin duplicar el registro.
- **Sin proxy propio:** el VPS ya tiene un reverse proxy. El backend Node es el único
  puerto expuesto del compose; el proxy del VPS apunta a él.
- **Base de datos: PostgreSQL 16.**
- **Dos clientes web SEPARADOS (decidido 2026-07-15, reemplaza "SPA existente extendida"):**
  - **Cliente de proyectos** — SPA Vue 3 **nueva e independiente** (dashboard, proyectos,
    hitos/tareas, y a futuro diagramas/IPAM/costos). Servida por Node.
  - **Cliente doctyp** — la SPA existente (`web/`), **intacta como app aparte**, con su
    backend Python + tinymist + WebSockets. No se fusionan.
  - **Integración por deep link (opción B1, descartadas iframe y componentes compartidos):**
    el cliente de proyectos abre el editor de un informe en **otra pestaña** vía la URL
    `/documentos/<codigo_base>` de doctyp (rutas reales desde la Etapa 17 de CLAUDE.md).
    El contrato entre módulos es `documents.codigo_base` + esa URL — sin código compartido,
    sin acoplar builds. Para mostrar informes *en contexto* dentro de proyectos se embeben
    solo **artefactos de solo lectura** vía proxy de Node (miniatura, PDF compilado,
    historial/meta), nunca el editor. Opcional y barato: query param `?proyecto=<id>` para
    que doctyp muestre un link "← Volver al proyecto".
    Motivo del descarte: el editor es una rebanada vertical (LSP por WS, buses singleton,
    SSE en la raíz, iframe de tinymist, proceso único de preview/LSP por sesión) — extraerlo
    a un paquete compartido acopla los dos clientes; el iframe embebe una SPA completa con
    iframe anidado y doble topbar.
- Los autores pasan a ser **usuarios/miembros**: usuario = autor = miembro de equipo.

---

## 1. Stack

| Capa | Tecnología | Justificación |
|---|---|---|
| Backend nuevo | Node 22 + TypeScript + **Fastify** | Ligero, validación por JSON Schema/TypeBox, SSE/WS sin fricción |
| ORM / migraciones | **Drizzle ORM + Drizzle Kit** | SQL-first, tipado estricto, migraciones versionadas en el repo |
| Auth | Sesiones de servidor: cookie `httpOnly` + tabla `sessions`; hash **Argon2id** | SPA same-origin → sesiones revocables, más simples que JWT |
| BD | **PostgreSQL 16** (JSONB para modelos de diagrama y specs de catálogo; tipos nativos `CIDR`/`INET`/`MACADDR` para IPAM) | |
| Doc-service | `doctyp_web.py` intacto (Python 3.12 + typst + tinymist) | Opción B: no perder el código Python |
| Frontend proyectos | Vue 3 + Vite (**SPA nueva**, p. ej. `web-proyectos/`) + **Pinia** + **Vue Router** | Cliente independiente: login/dashboard/proyectos (§0) |
| Frontend doctyp | SPA Vue 3 existente (`web/`), **sin cambios estructurales** | Ya tiene vue-router (CLAUDE.md Etapa 17); solo recibe el deep link |
| Editor de diagramas | **Konva (vue-konva)** como base única | Planimetría a escala es el caso dominante; capas nativas mapean 1:1 con capas red/cctv |
| Cálculo RF | Web Worker en frontend, modelo **Multi-Wall (COST 231)** | Heatmap sin bloquear la UI |

---

## 2. Topología Docker

```
docker-compose.yml
├── db            → postgres:16-alpine (solo red interna, volumen pgdata, healthcheck)
├── backend       → Node 22 + Fastify (ÚNICO puerto expuesto; el proxy del VPS apunta aquí)
│                    · /            → estáticos de la SPA de PROYECTOS (nueva, §0)
│                    · /api/v1/*    → lógica nueva (auth, proyectos, diagramas, IPAM, costos)
│                    · /docs/*      → proxy COMPLETO al doc-service: la SPA doctyp existente
│                                     (que doctyp_web.py ya sirve), su API (/api/…), el
│                                     WebSocket del LSP (/api/lsp) y el SSE (/api/events)
└── doc-service   → doctyp_web.py intacto (solo red interna, sin exposición)
                     imagen python:3.12-slim + binarios typst y tinymist
                     + pdftoppm/mutool (render PDF) — DWG llega en Etapa 23
                     volúmenes: docs_data, orgs_data, fuentes
```

- **Autorización siempre en Node antes de proxear**; el doc-service confía en la red
  interna del compose (equivalente al bind 127.0.0.1 actual).
- **Ambos clientes bajo el mismo dominio/sesión** (cookie httpOnly de Node): el deep link
  proyectos→doctyp (§0) hereda la sesión sin SSO adicional.
- **⚠ Punto técnico a resolver en la Etapa 18 (Docker):** la vista previa de tinymist usa
  un **puerto dinámico propio** (static server + data plane WS, ver CLAUDE.md Etapa 15)
  que hoy funciona porque navegador y proceso comparten host. Dentro del compose ese
  puerto queda en la red interna: hay que proxearlo (Node o el propio doc-service como
  túnel) o publicarlo de forma controlada. Es prerrequisito del editor en Docker,
  independiente de la decisión de clientes separados.
- **Museo Sans se monta como volumen desde el host/VPS — NUNCA dentro de una imagen**
  (hallazgo de auditoría: licencia de fuente no redistribuible).
- Imágenes multi-stage: frontend (Vite build → estáticos servidos por Node),
  backend (tsc → node:22-slim).
- `compose.override.yml` para desarrollo: hot-reload (Vite dev server + tsx watch),
  puertos expuestos, seeds.
- Migraciones al arranque del backend (`drizzle-kit migrate`) con advisory lock de
  Postgres (evita carreras entre réplicas).
- Backups: `pg_dump` programado + volúmenes de documentos (los `.typ` siguen en
  filesystem; la BD guarda registro y metadatos).

---

## 3. Esquema de base de datos

### 3.1 Identidad y acceso (Funcionalidad 1)

```
users(id, email UNIQUE, password_hash, nombre, cargo, activo, created_at)
sessions(id, user_id FK, token_hash, expires_at, ip, user_agent)
organizations(id, slug UNIQUE, nombre, sigla, config JSONB)  -- config: { "iva_pct": 19, ... }
org_members(org_id, user_id, role ENUM[owner,admin,member,viewer], PK(org_id,user_id))
teams(id, org_id FK, nombre, descripcion)
team_members(team_id, user_id, role ENUM[lead,member])
```

- Middleware resuelve `(user, org, team)` por request; toda entidad cuelga de `org_id`
  y toda query filtra por membresía (autorización en aplicación; **RLS de Postgres como
  endurecimiento futuro**, no bloqueante).
- Migración: autores existentes en `org.json` → `users` con password de primer inicio.

### 3.2 Documentos (referencia, no registro)

```
documents(id, org_id, codigo_base UNIQUE(org_id), correlativo, tipo, categoria,
          titulo, autor_id FK users, equipo_id FK teams, plantilla, path_rel,
          project_id FK NULLABLE, estado, created_at)
document_versions(id, document_id, version, mensaje, snapshot_path, hash, created_at)
correlative_counters(org_id, anio, ultimo)   -- asignación con SELECT ... FOR UPDATE
```

- `correlative_counters` con `FOR UPDATE` cierra la condición de carrera del correlativo
  (hallazgo de auditoría). **Aplica cuando el registro se porte a Node**; mientras tanto
  el correlativo lo sigue asignando el doc-service (`org.json`), y esta tabla queda
  preparada para la transición.
- `project_id` NULLABLE → documentos sueltos permitidos.

### 3.3 Proyectos (Funcionalidad 2)

```
projects(id, org_id, team_id FK, nombre, descripcion, objetivos TEXT,
         estado ENUM[borrador,activo,pausado,cerrado,cancelado],
         fecha_inicio, fecha_fin_estimada)
milestones(id, project_id, nombre, fecha, estado, orden)
tasks(id, project_id, titulo, descripcion,
      estado ENUM[pendiente,en_curso,bloqueada,hecha],
      assignee_id FK users, milestone_id FK NULLABLE, due_date, orden)
project_members(project_id, user_id, rol)
```

**Dashboard (vista principal de la SPA de PROYECTOS, §0):** dos focos — proyectos activos
(hitos próximos, mis tareas) y documentos recientes/en borrador (datos vía referencia
`codigo_base` + artefactos read-only proxeados; editar abre doctyp en otra pestaña).
El grid de documentos de doctyp **no se toca**: sigue siendo la vista principal de su
propia app.

### 3.4 Diagramas (Funcionalidad 3 — esqueleto)

```
diagrams(id, org_id, project_id FK NULLABLE, nombre,
         tipo ENUM[red,cctv,mixto], sitio)
floors(id, diagram_id, nombre, orden, plano_fondo_path, escala_px_por_metro,
       conos_cctv_activos BOOL, heatmap_activo BOOL)
layers(id, diagram_id, nombre,
       tecnologia ENUM[red,cctv,atenuacion,electrico,...], visible_default)
diagram_versions(id, diagram_id, numero, mensaje, modelo JSONB,
                 render_svg_path, bom JSONB, costo_neto, costo_iva, costo_total,
                 created_at, created_by FK users)
floor_locks(floor_id PK, user_id FK, acquired_at, heartbeat_at)
document_diagram_links(document_id, diagram_version_id, PK(...))
```

- **Modelo JSONB inmutable por versión**: elementos, posiciones, rutas de cableado,
  asignaciones IP, muros de atenuación. El informe enlaza una `diagram_version`
  específica (el usuario decide cuál) y la importa como SVG/PNG renderizado del snapshot
  (Typst lo embebe directo).
- **BOM materializado por versión** (metros de UTP/fibra/canalización + equipos):
  costos reproducibles aunque el catálogo cambie precio después.
- **Bloqueo por piso** con heartbeat: el frontend renueva cada 30 s; el lock expira a
  los 90 s sin señal (cubre pestañas cerradas). Adquisición atómica:
  `INSERT ... ON CONFLICT DO NOTHING`.

### 3.5 Catálogo y costos

```
catalog_items(id, org_id, categoria ENUM[switch,router,ap,antena_ptp,camara,nvr,
              gabinete,cable_utp,fibra,canalizacion,...],
              nombre, marca, modelo, specs JSONB,
              unidad ENUM[unidad,metro],
              costo_neto NUMERIC(12,2), moneda CHAR(3) DEFAULT 'CLP', vigente)
catalog_price_history(catalog_item_id, costo_neto, fecha)
attenuation_materials(id, org_id, nombre, db_24ghz, db_5ghz)  -- editable por org
```

- **Esquema de atributos por categoría** (specs JSONB validado contra plantilla de
  categoría — las plantillas se especifican después, decisión pendiente de detalle).
- Specs RF para AP/antena PTP: `potencia_tx_dbm`, `ganancia_dbi`, `frecuencia_mhz`,
  `sensibilidad_dbm`. Specs CCTV: `fov_grados`, `alcance_m`, resolución, IR.
- **Costos: solo equipos por ahora.** Neto + IVA automático (`organizations.config.iva_pct`,
  default 19). Subtotales en UI siempre **IVA incluido**, con desglose disponible.

### 3.6 IPAM (gestión de subredes completa)

```
subnets(id, org_id, cidr CIDR, vlan_id INT, nombre, gateway INET, descripcion,
        parent_id FK NULLABLE)                    -- jerarquía: supernet → subredes
ip_assignments(id, subnet_id FK, ip INET UNIQUE(subnet_id),
               tipo ENUM[estatica,dhcp_range,reservada],
               element_ref TEXT NULLABLE,   -- id del elemento en el JSONB del diagrama
               diagram_id FK NULLABLE, hostname, mac MACADDR NULLABLE)
```

- Operadores nativos de Postgres (`<<`, `&&`) para contención y solapamiento:
  detección de conflictos y **siguiente-IP-libre** son queries, no lógica de aplicación.
- Endpoints: crear/subdividir subredes, next-free, conflictos, ocupación por subred.
- La validación IP/máscara/VLAN corre en backend como módulo TypeScript puro al guardar
  versión de diagrama.

---

## 4. Editor de diagramas (Konva)

### 4.1 Estructura de capas por piso

```
Stage (por piso activo)
├── Layer fondo         (imagen calibrada, opacidad ajustable)
├── Layer atenuación    (muros/obstáculos — editable, ocultable; UNA por piso, fija)
├── Layer red           (equipos + rutas de cableado)
├── Layer cctv          (cámaras + conos FOV, activables por piso)
├── Layer heatmap RF    (imagen generada por el worker, activable por piso)
└── Layer UI            (selección, snapping, medición)
```

- Vistas "red" / "cctv" / "mixta" = toggles de visibilidad de capas.
- Conos de visión CCTV derivados de specs del catálogo (FOV°, alcance m), con toggle
  por piso.

### 4.2 Fondos de plano

Calibración manual siempre: 2 puntos + distancia real → `escala_px_por_metro`.

| Formato | Pipeline | Nota |
|---|---|---|
| PNG | directo | — |
| PDF | render server-side a PNG (`pdftoppm`/mutool) con selección de página | — |
| DWG | `dwg2dxf` (LibreDWG, GPL — se invoca como binario, no se enlaza) → `dxf-parser` → SVG/PNG | *Best effort* (líneas, polilíneas, arcos, textos). Si un DWG complejo falla, el usuario exporta PDF/PNG desde AutoCAD |

### 4.3 Planimetría de cableado

- Longitud = polilínea 2D × escala del piso + `holgura_pct` (por ruta o default de org)
  + `delta_vertical_m` **opcional por ruta** (lo indica el usuario; default 0 — no todo
  tiene delta).
- Tipos de ruta: canalización EMT/PVC, soterrada, bandeja, **enlace aéreo**, directa —
  cada tipo asociado a su ítem de catálogo para el BOM (UTP, fibra óptica, etc.).

### 4.4 Propagación RF (AP y enlaces PTP)

- **Capa de atenuación por piso** (obligatoria en el modelo): muros (polilíneas) y
  obstáculos (polígonos) con material → dB (tabla `attenuation_materials`, valores de
  referencia: hormigón ~12 dB, tabique yeso ~3 dB, vidrio ~2 dB, metal ~26 dB a 2.4/5 GHz).
- **Motor Multi-Wall (COST 231)** en Web Worker: por celda de una grilla (resolución
  configurable, ej. 0,25 m), FSPL + Σ atenuación de muros cruzados (raycast AP→celda)
  → RSSI → color. Heatmap pintado en canvas offscreen, montado como imagen en su capa
  Konva.
- **PTP exterior:** FSPL + despeje de zona de Fresnel entre antenas con obstáculos
  marcados.
- **Etiqueta obligatoria** en UI y exportación: *"proyección teórica — no reemplaza
  site survey"*.
- Riesgo conocido: grilla fina en pisos grandes → downsampling progresivo (se resuelve
  en Etapa 23, no antes).

---

## 5. Roadmap (etapas 18–23, continúa CLAUDE.md §14; renumeradas 2026-07-15, ver cabecera)

| Etapa | Alcance | Estado |
|---|---|---|
| 18 | **Docker + esqueleto Node:** compose (db / backend / doc-service), Fastify + TypeScript + Drizzle, migraciones iniciales, proxy completo al doc-service (SPA doctyp + API + WS/SSE + puerto de preview de tinymist, ver ⚠ en §2), esqueleto de la SPA de proyectos servida por Node. Sin auth (todo detrás de flag dev) | Pendiente |
| 19 | **Auth:** users/sessions (cookie httpOnly, Argon2id), login/logout, RBAC org/team, migración autores `org.json` → users, guard de sesión delante del proxy al doc-service. Login/logout en la SPA de proyectos + Pinia + Vue Router | Pendiente |
| 20 | **Proyectos + dashboard:** projects/milestones/tasks/project_members, enlace opcional documento↔proyecto (referencia por `codigo_base`), dashboard principal en la SPA de proyectos (proyectos activos, mis tareas, documentos recientes con artefactos read-only), deep link "editar informe" → doctyp en otra pestaña (§0) | Pendiente |
| 21 | **Esqueleto diagramas:** modelo BD (diagrams/floors/layers/versions/catalog), fondos PNG+PDF con calibración, editor Konva mínimo (capas, colocar equipos, muros de atenuación), versionado JSONB+SVG, bloqueo por piso, enlace a proyectos | Pendiente |
| 22 | **Planimetría + IPAM + costos:** rutas con cálculo de metros (holgura + delta vertical), subredes/asignación IP (tipos INET/CIDR), BOM con neto+IVA, importación de versión de diagrama a informes (vía doc-service) | Pendiente |
| 23 | **RF + CCTV + DWG:** motor Multi-Wall en worker, heatmap AP y PTP/Fresnel, conos CCTV, pipeline DWG→DXF, tabla de materiales de atenuación editable | Pendiente |

**Reglas de cierre por etapa:**
1. Actualizar esta tabla y CLAUDE.md §14.
2. Migraciones Drizzle versionadas en el repo.
3. Mientras una etapa esté `Pendiente`, sus comandos, tablas y endpoints **no existen**
   — no asumirlos ni referenciarlos como hechos.

---

## 6. Pendientes explícitos (no bloquean)

- RLS de Postgres como endurecimiento de autorización.
- Rate-limit en login.
- Especificación detallada de plantillas de atributos por categoría de catálogo
  (se define con el usuario antes de la Etapa 21/22).
- Port gradual del doc-service Python a Node (post-Etapa 23, sin fecha).
- Conexión del CLI al backend (trabajo colaborativo post-VPS, sin fecha).