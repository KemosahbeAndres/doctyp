# Etapa 2 — Documentos-carpeta en DOCS_ROOT (doctyp v3)

> Plan aprobado por el usuario el 2026-07-12. Pendiente de ejecución.
> Retomar con: revisar este archivo, luego implementar siguiendo el mismo patrón que la
> Etapa 1 (sandbox aislado primero, repo real después con confirmación explícita del usuario
> antes de mover archivos reales).

## Contexto

Etapa 1 (completada) construyó el núcleo de organizaciones: `organizations/<slug>/org.json`
como fuente de verdad de correlativos/autores/documentos, con `settings.json["documentos"]`
como espejo v2 para no romper los comandos aún no migrados. Los documentos, sin embargo, siguen
viviendo junto al script (`SCRIPT_DIR`), igual que en v2.

Esta etapa mueve los documentos a carpetas autocontenidas bajo `<Documentos>/doctyp/<org>/`
(§1, §4 de CLAUDE.md), cada una con su copia de la plantilla **incluidas las fuentes**, y añade
el mecanismo de versionado por snapshots de archivo (`versions/`) para documentos nuevos, sin
tocar aún el mecanismo git existente (`_git_snapshot`, `history`, `restore`, `git-init` — eso es
Etapa 3, que hace el retiro formal de git). Por decisión explícita del usuario, se amplía el
alcance en tres puntos: (a) el documento existente (`TI-INF-SFW_2026-0001`) se migra también a
su carpeta en `DOCS_ROOT` en esta misma etapa; (b) `cmd_nuevo`/`cmd_add` ya escriben `versions/`
para documentos nuevos (una porción de lo que formalmente es trabajo de Etapa 3); (c) las
fuentes (`museo-sans/` y `GobCLFontsFiles/`) pasan a ser parte de la plantilla — se copian a
`fonts/` tanto en `organizations/<org>/templates/<nombre>/` como en la carpeta de cada
documento, revirtiendo la nota de CLAUDE.md §3 de que "Museo Sans no se redistribuye" (decisión
explícita del usuario: en este repo las fuentes sí viajan con la plantilla).

## Alcance de esta etapa

1. `organizations/<org>/templates/informe-ti/` — se crea copiando `lib.typ` + `Images/` +
   `fonts/` (unión de `museo-sans/` y `GobCLFontsFiles/`) desde `SCRIPT_DIR` (la plantilla
   actual pasa a vivir "por organización", según CLAUDE.md §3, con fuentes incluidas por
   decisión explícita del usuario).
2. `cmd_nuevo`: en vez de escribir el `.typ` en `SCRIPT_DIR`, crea la carpeta del documento en
   `DOCS_ROOT/<org>/<código-base>/`, copia la plantilla ahí (`lib.typ`, `Images/`, `fonts/`),
   escribe el `.typ` con import local, y crea `versions/` (vacía) + `img/` (vacía).
3. `cmd_add`: mismo tratamiento — al importar un `.typ` del CWD, se le construye la carpeta de
   documento en `DOCS_ROOT/<org>/` con plantilla copiada (incluidas fuentes), en vez de moverlo
   junto al script.
4. `compilar_typ`: en vez de fijar `font_dir = SCRIPT_DIR / "museo-sans"` a secas, usa
   `out_file.parent / "fonts"` si existe (documento con plantilla copiada, layout v3);
   si no existe, cae al comportamiento actual (`SCRIPT_DIR / "museo-sans"`, layout v2) —
   compatibilidad con documentos aún no migrados.
5. `realizar_save`: gana snapshot a `versions/<código-base>_v<versión>.typ` **cuando el
   documento vive bajo DOCS_ROOT** (detectado por convención: existe `versions/` como hermano
   del `.typ`). Si el documento sigue en el layout v2 (junto al script, sin `versions/`), el
   comportamiento no cambia. Esto activa el snapshot de archivo para `save`/`compile` sin
   modificar su lógica de negocio ni su interfaz.
6. `org.json`: cada entrada de documento gana `"plantilla": "informe-ti"` (ya lo escribe
   `cmd_nuevo` desde Etapa 1) y `ruta` pasa a ser relativa a `DOCS_ROOT/<org>/` en vez de
   absoluta a `SCRIPT_DIR` — igual que especifica CLAUDE.md §2 ("las rutas de documentos en
   `org.json` son relativas a `DOCS_ROOT/<org-slug>/`"). Se resuelve a absoluta en runtime con
   un helper nuevo.
7. Migración explícita del documento existente: mueve `TI-INF-SFW_2026-0001.typ` (y su `.pdf`
   si existe) a `DOCS_ROOT/slep-chinchorro/TI-INF-SFW_2026-0001/`, copia la plantilla (con
   fuentes), actualiza `ruta` en `org.json` y en el espejo `settings.json["documentos"]`, y crea
   `versions/` vacía
   (no hay snapshots previos que trasladar: los snapshots existentes de esa versión, si los
   hay, quedan solo en git — no se tocan).

**Fuera de alcance (queda para Etapa 3):** retiro de git, adaptación de `save`/`compile`/`edit`/
`delete`/`import`/`history`/`restore`/`change`/`git-init` para leer `org.json` directamente
(siguen sobre el espejo `settings.json`), eliminación del espejo, escrituras atómicas
generalizadas a todos los registros, ajuste de plantilla (`rama-git` fuera de `s-ficha`).

## Diseño

### Copia de plantilla a `organizations/<org>/templates/<nombre>/`

Nueva función `plantilla_dir(slug, nombre) -> Path` →
`organizations_dir() / slug / "templates" / nombre`.

Nueva función `asegurar_plantilla_org(slug, nombre="informe-ti") -> Path`: si
`organizations/<slug>/templates/<nombre>/lib.typ` no existe, la copia desde `SCRIPT_DIR`:
`lib.typ`, `Images/`, y `fonts/` (unión de `museo-sans/*` y `GobCLFontsFiles/*`, todos los
`.otf`/`.ttf` de ambas carpetas juntos en un solo `fonts/` — decisión explícita del usuario de
que las fuentes viajen con la plantilla, revirtiendo la nota previa de CLAUDE.md §3 sobre no
redistribuir Museo Sans). Usa `shutil.copytree`/`copy2`. Es idempotente (no sobrescribe si ya
existe). Se llama de forma lazy desde `cmd_nuevo`/`cmd_add`/la migración del documento existente.

### Carpeta de documento en `DOCS_ROOT`

Nueva función `carpeta_documento(slug, codigo_base) -> Path` →
`docs_root() / slug / codigo_base` (usa `docs_root()` de Etapa 1, aún sin uso hasta ahora).

Nueva función `crear_carpeta_documento(slug, codigo_base, plantilla_dir) -> Path`:
- Crea `DOCS_ROOT/<slug>/<código-base>/`.
- Copia `lib.typ`, `Images/` y `fonts/` desde `plantilla_dir` (copia por documento, según
  CLAUDE.md §3: "actualizar la plantilla de la org no modifica documentos ya creados" —
  aplica también a las fuentes, que ahora son parte de la plantilla).
- Crea `img/` y `versions/` vacías.
- Devuelve la ruta de la carpeta.

### `compilar_typ` (edición)

Actualmente fija `font_dir = SCRIPT_DIR / "museo-sans"` sin condicionar al documento que se
compila. Pasa a:
- `font_dir = out_file.parent / "fonts"` si existe (documento con plantilla copiada, layout v3
  — incluye tanto Museo Sans como GobCL).
- si no existe, cae a `SCRIPT_DIR / "museo-sans"` (comportamiento actual, layout v2 — documentos
  aún no migrados a carpeta propia).

### `cmd_nuevo` (edición)

Reemplaza el bloque actual que escribe en `out_dir = docs_dir(anio)` (= `SCRIPT_DIR`):
- `plantilla_dir = asegurar_plantilla_org(slug)`.
- `out_dir = crear_carpeta_documento(slug, base, plantilla_dir)` (en vez de `docs_dir(anio)`).
- `lib_import` sigue calculándose con `os.path.relpath` pero ahora entre `out_dir/lib.typ` (ya
  copiado ahí) y el propio `out_dir` → siempre `"lib.typ"` (ruta local, como ya documenta
  CLAUDE.md §1/§4).
- `entrada_org["ruta"]` guarda la ruta **relativa** a `DOCS_ROOT/<slug>/` (es decir, solo
  `base`, el nombre de la carpeta) en vez de la ruta absoluta al `.typ`.
- El espejo `settings.json["documentos"]` conserva `ruta` **absoluta** al `.typ` (formato v2,
  sin cambios) — los comandos legacy no tocados siguen esperando ese formato.
- `fallback = next_correlativo(scan_existing(out_dir, ...))`: `scan_existing` escaneaba
  `SCRIPT_DIR` en busca de `.typ` sueltos como red de seguridad anti-colisión; con el nuevo
  layout esa función pierde sentido para el fallback (ya no hay `.typ` sueltos en `SCRIPT_DIR`
  esperado) — se simplifica a `fallback = 0` (el registro de `org.json` ya es la fuente de
  verdad real; `scan_existing` se deja intacta, sin usarla aquí, por si algún flujo legacy la
  sigue necesitando).

### Resolución de ruta absoluta desde `org.json`

Nueva función `ruta_documento_org(slug, entrada_org) -> Path`: si `entrada_org["ruta"]` es
relativa, la resuelve contra `docs_root() / slug`; si es absoluta (documentos aún no migrados a
esta etapa, o legacy), la usa tal cual. Esto permite convivencia entre documentos ya migrados a
carpeta y los que aún no, dentro del mismo `org.json`, sin romper nada.

### `realizar_save` (edición mínima)

Antes de escribir la nueva versión, calcula `carpeta = typ_path.parent`; si
`(carpeta / "versions").is_dir()`, copia el `.typ` **anterior** (antes de reescribir la
versión) a `versions/<código-base>_v<version_actual>.typ` (snapshot de la versión saliente,
igual criterio que un tag git: se snapshotea lo que se va a superar). Si `versions/` no existe
(documento aún en layout v2), no hace nada — comportamiento actual intacto. `cmd_save` y
`cmd_compile` no cambian: la función que llaman gana el efecto colateral de forma transparente.

### `cmd_add` (edición)

Mismo patrón que `cmd_nuevo`: en vez de `shutil.move(p, dest_dir / f"{base}.typ")` con
`dest_dir = docs_dir(meta["anio"])`, construye la carpeta del documento con
`crear_carpeta_documento` + `asegurar_plantilla_org`, mueve el `.typ` importado ahí, normaliza
su import a `"lib.typ"` (ya lo hace, sigue igual), y registra en `org.json` con `ruta` relativa
+ en el espejo con `ruta` absoluta — mismo split que en `cmd_nuevo`.

### Migración del documento existente

Función `migrar_documento_a_carpeta(slug, entrada_org) -> None`, ejecutada una vez de forma
explícita (no lazy automática, para no mover archivos del usuario sin aviso): mueve el `.typ`
(y el `.pdf` si existe junto a él) desde su ubicación actual (`SCRIPT_DIR`) a
`DOCS_ROOT/<slug>/<código-base>/`, copiando la plantilla con `asegurar_plantilla_org` +
`crear_carpeta_documento`, actualiza `ruta` (relativa) en `org.json` y `ruta` (absoluta) en el
espejo `settings.json`. Se invoca una sola vez, manualmente, para `TI-INF-SFW_2026-0001`
(no se expone como subcomando nuevo — es un paso de migración puntual de esta etapa, ejecutado
igual que se hizo la migración lazy de Etapa 1, pero esta vez explícita porque mueve archivos
del usuario en disco, no solo JSON).

## Archivos afectados

- `doctyp.py`: `asegurar_plantilla_org`, `plantilla_dir`, `carpeta_documento`,
  `crear_carpeta_documento`, `ruta_documento_org` (nuevas); `cmd_nuevo`, `cmd_add`,
  `realizar_save`, `compilar_typ` (editadas, esta última solo para resolver `font_dir` por
  documento). `cmd_save`, `cmd_compile` (sin cambios propios, se benefician de `realizar_save`/
  `compilar_typ` editadas), `cmd_edit`, `cmd_delete`, `cmd_import`, `cmd_history`, `cmd_restore`,
  `cmd_change`, `cmd_git_init`, `_git_snapshot` — **sin cambios de lógica** (siguen sobre el
  espejo v2, que sigue guardando rutas absolutas).
- `organizations/slep-chinchorro/templates/informe-ti/` — nuevo (copia de `lib.typ`, `Images/`,
  `fonts/` con Museo Sans + GobCL).
- `<Documentos>/doctyp/slep-chinchorro/TI-INF-SFW_2026-0001/` — nuevo (documento migrado, con su
  propia copia de `fonts/`).
- `organizations/slep-chinchorro/org.json` y `settings.json` — actualizados por la migración.
- `CLAUDE.md` §3 — la nota "Museo Sans no se redistribuye (licencia)" **se deja intacta**
  (advertencia legal, no se toca sin más contexto). Se agrega una línea nueva aclarando que la
  copia de `fonts/` a `organizations/<org>/templates/<nombre>/` y a cada carpeta de documento es
  un mecanismo local de esta instalación (ambas rutas ya están commiteadas en este repo hoy,
  igual que `museo-sans/`/`GobCLFontsFiles/` en `SCRIPT_DIR` — no cambia nada en `.gitignore`,
  eso no está en el alcance de esta etapa).
- `CLAUDE.md` §14 — marcar Etapa 2 completada, con la misma nota de alcance ampliado que se usó
  para la Etapa 1.

No se toca `lib.typ` de origen (`SCRIPT_DIR/lib.typ` sigue existiendo, solo se copia), ni la
lógica de `build_typ`, ni el esquema de `meta`.

## Verificación

1. Repetir el patrón de la Etapa 1: probar primero en un sandbox aislado (copia de
   `doctyp.py`/`lib.typ`/`Images`/`settings.json`/`organizations/`), y solo después de validar
   ahí, ejecutar contra el repo real con confirmación explícita del usuario antes de mover
   archivos reales.
2. `doctyp new "Prueba etapa 2"` → confirmar que se crea
   `DOCS_ROOT/slep-chinchorro/TI-INF-SFW_2026-NNNN/` con `.typ`, `lib.typ`, `Images/`, `fonts/`
   (con los `.otf` de Museo Sans y GobCL), `img/` y `versions/` (vacía); que el `.typ` compila su
   import como `"lib.typ"` local; que `org.json` guarda `ruta` relativa y el espejo
   `settings.json` guarda `ruta` absoluta.
3. `doctyp list` → sigue mostrando el documento correctamente (usa `ruta_documento_org` o
   directamente los campos de listado, que no dependen de resolver la ruta).
4. `doctyp save <corr> --m "..."` sobre el documento nuevo → confirmar que aparece
   `versions/<código-base>_v<version-anterior>.typ` con el contenido previo a la subida.
5. `doctyp save <corr> --m "..."` sobre el documento migrado en Etapa 1 antes de que esta etapa
   lo mueva (si se prueba en algún punto intermedio) → confirmar que NO falla por falta de
   `versions/` (layout v2 puro sigue funcionando).
6. Migrar `TI-INF-SFW_2026-0001` → confirmar que el `.typ`/`.pdf` aparecen en su carpeta nueva,
   que `SCRIPT_DIR` ya no tiene el `.typ` suelto, que `doctyp list`/`doctyp save 1 --m "..."`
   siguen funcionando apuntando a la nueva ubicación.
7. `doctyp add` sobre un `.typ` de prueba dejado en el CWD → confirmar que termina en su propia
   carpeta bajo `DOCS_ROOT` con plantilla copiada, no junto al script.
8. No se compila ningún `.typ` como parte de la verificación salvo pedido explícito (regla §0).
9. Confirmar que `git status` en el repo real no muestra el `.typ`/`.pdf` del usuario como
   eliminados sin más contexto — se le informa antes de mover archivos reales del usuario.
