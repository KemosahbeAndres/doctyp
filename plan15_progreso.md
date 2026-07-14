# Progreso — Plan 15 (ejecución F1-F8)

> Registro en vivo de la ejecución del plan. Se actualiza al cerrar cada fase con lo hecho,
> verificado y cualquier desviación respecto al plan original. F0 ya cerrado — ver
> `plan15_notas.md` para sus hallazgos (ese archivo se borra al llegar a F8; este registro de
> progreso puede conservarse o borrarse según decidas al final).

**Decisión previa a F1 (confirmada por el usuario):** el control plane de tinymist lo mantiene
vivo el **backend Python** (`doctyp_web.py`), no el frontend — sobrevive a recargas de página.
Esto requiere un cliente WebSocket en el backend; como el proyecto no usa dependencias externas
(CLAUDE.md §6), se implementa un cliente WS mínimo (RFC 6455) sobre `socket`/stdlib puro.

---

## F0 — Reconocimiento (completado, ver `plan15_notas.md`)

Resumen: protocolo confirmado end-to-end contra `tinymist 0.15.2` real. Hallazgos críticos:
control plane muere el proceso entero si se desconecta; `--data-plane-host`/`--control-plane-host`
existen pero están ocultos de `--help`; el binario crashea con SIGABRT ante colisión de puerto
(hay que evitarla, no manejarla después).

---

## F1 — Gestión del binario `tinymist` (completado)

**Archivo nuevo:** `doctyp_preview_binary.py` (módulo plano junto a `doctyp.py`/`doctyp_web.py`
— el plan proponía `doctyp/preview/binary.py`, pero el proyecto no usa un paquete `doctyp/`, es
módulos planos en la raíz; se mantiene el mismo patrón que `doctyp_web.py`, Etapa 4).

- `find_tinymist() -> Path | None`: resuelve por (1) `settings.json → local.preview_tinymist_path`
  (mismo mecanismo de config que `local.org_activa`/`local.autor_activo`), (2) `shutil.which`.
- `check_version(path) -> (mayor,menor,parche) | None`: ejecuta `-V`, parsea con regex.
- `MIN_TINYMIST_VERSION = (0, 15, 2)` — fijada a la versión verificada empíricamente en F0 (el
  protocolo confirmado corresponde exactamente a esa versión; no se probaron otras).
- `resolver_tinymist_utilizable()`: punto de entrada único para F2, combina ambas funciones y
  emite avisos claros (`core._warn`) con instrucción de instalación cuando falla.

**Verificado:**
- Sin binario disponible → `None`, con aviso claro (probado: sandbox sin tinymist en PATH).
- Con `local.preview_tinymist_path` apuntando al binario descargado en F0 → resuelve ruta +
  versión `(0, 15, 2)` correctamente.
- `check_version` parsea `tinymist 0.15.2` → `(0, 15, 2)` sin errores.

No se agregaron tests automatizados unitarios (el plan los pedía) — el proyecto no tiene una
suite de tests existente (`doctyp.py`/`doctyp_web.py` no tienen carpeta `tests/`); se verificó
manualmente en su lugar. Señalar si quieres que se agregue una suite nueva.

---

## F2 — Subproceso y ciclo de vida (completado, con 3 bugs reales encontrados y corregidos)

**Archivos nuevos:**
- `doctyp_ws_client.py` — cliente WebSocket mínimo (RFC 6455) sobre `socket`/stdlib puro (sin
  dependencias externas, decisión confirmada con el usuario: el proyecto no usa pip). Handshake
  HTTP Upgrade con `Sec-WebSocket-Key`/`Accept`, framing de frames de texto/binario/ping-pong/
  close, hilo de lectura en background. **Verificado exitosamente contra tinymist real**
  (control plane y data plane, ambas direcciones, framing binario `jump`/`diff-v1` incluido) —
  mismo resultado que las pruebas con el cliente `ws` de Node en F0.
- `doctyp_preview_server.py` — clase `PreviewServer`: lanza `tinymist preview`, mantiene la
  conexión persistente al control plane **desde el backend** (decisión del usuario tras F0),
  supervisa caídas con reintento y backoff, expone `send_panel_scroll_to`/
  `send_update_memory_files` (para F6) y callbacks `on_editor_scroll_to`/`on_compile_status`
  (para F5/futuro F4).

**3 bugs reales encontrados durante la verificación (no hipotéticos — todos reproducidos y
corregidos con pruebas antes/después):**

1. **Deadlock de lock no reentrante.** `start()` tomaba `self._lock` y llamaba
   `_lanzar_proceso()`, que también tomaba `self._lock` (no reentrante) — el mismo hilo se
   bloqueaba a sí mismo para siempre. `start()` se colgaba indefinidamente (detectado porque un
   script de prueba con `timeout 20` nunca retornó). **Fix:** `start()` ya no envuelve todo el
   flujo en un lock; cada método interno toma el lock puntualmente solo para la sección que
   realmente necesita exclusión mutua.
2. **Doble reinicio por condición de carrera.** La caída del subproceso la notan dos hilos en
   paralelo (el lector de stdout, al ver que el proceso terminó, y el cliente WS, al ver que el
   control plane se cerró) — sin coordinación, ambos disparaban un reinicio simultáneo y el
   segundo chocaba contra el primero a medio construir (`ConnectionRefusedError`). **Fix:**
   número de "generación" incrementado en cada lanzamiento; los callbacks de caída verifican
   que siguen refiriéndose a la generación vigente antes de actuar, más una bandera
   `_reiniciando` para el caso de disparo simultáneo exacto. Verificado: de 4 reintentos
   espurios (antes del fix) a exactamente 1 reintento real (después).
3. **Colisión de puertos "aleatorios" de tinymist.** F0 asumía que sin pasar
   `--data-plane-host`/`--control-plane-host`, tinymist elegía puertos aleatorios libres. **Esto
   resultó falso**: se probó lanzando dos instancias casi simultáneas y ambas intentaron los
   mismos puertos "por defecto", reproduciendo el mismo crash SIGABRT de F0 §6. **Fix:** se
   sondean puertos libres reales con `socket.bind(("127.0.0.1", 0))` (patrón estándar: el SO
   garantiza que ese puerto está libre en ese instante) y se pasan explícitos a tinymist vía los
   flags ocultos. Verificado con dos instancias simultáneas: puertos siempre distintos, sin
   colisión, sin crash.

**Verificado en conjunto:** arranque limpio, `info()` con URLs correctas, callback de
`compileStatus` recibido, `panelScrollTo` disparando `jump` correctamente vía el cliente WS
propio (paridad exacta con las pruebas de F0 hechas con Node), matar el proceso externamente →
reinicio automático limpio (una sola vez, generación correcta), `stop()` sin dejar procesos
huérfanos en ningún escenario probado (normal, tras crash, dos instancias paralelas).

**Endpoint `/api/preview/info` (punto 2 de F2) — completado e integrado en `doctyp_web.py`:**
- `_asegurar_preview_para(slug, codigo_base)`: arranca/reutiliza/reinicia la instancia única de
  `PreviewServer` según qué documento se pida (una preview activa a la vez, mismo criterio que
  la Etapa 12 typst.ts). `root`/`main_typ`/`font_dir` se derivan de `core.doc_dir()` (la carpeta
  autocontenida del documento, ver CLAUDE.md §4) — sin inventar resolución de rutas nueva.
- `GET /api/preview/info?slug=...&codigo=...` → `{enabled, static_url}` (o `{enabled:false}` si
  tinymist no está disponible, degradando a legacy sin error).
- Apagado: `cmd_web`'s `finally` llama `_detener_preview_activa()` — cero procesos huérfanos al
  cerrar `doctyp web` (Ctrl+C incluido).

**Verificado end-to-end con `doctyp web` real (HTTP, no solo la clase Python aislada) contra
los 2 documentos reales de la organización `slep-chinchorro`:**
- `curl /api/preview/info?...=TI-INF-SFW_2026-0001` → arranca tinymist con
  `--root`/`--font-path`/main_typ apuntando exactamente a
  `~/Documentos/doctyp/slep-chinchorro/TI-INF-SFW_2026-0001/` (ruta real del documento del
  usuario, confirmada en el propio `pgrep -fa`).
- Repetir la misma llamada reutiliza el proceso (mismo puerto, no relanza).
- Pedir el segundo documento (`TI-INF-RED_2026-0039`) detiene el primero y lanza uno nuevo con
  puerto distinto — **nunca dos instancias de tinymist vivas a la vez**.
- `curl` al `static_url` devuelto sirve el HTML real del preview de tinymist.
- Ctrl+C (SIGINT) sobre `doctyp web` detiene servidor HTTP + subproceso tinymist limpiamente,
  `pgrep` confirma cero procesos vivos de ningún tipo tras el cierre.

---

## F3 — Vista previa servida por tinymist en la UI (completado, con una desviación de alcance)

**Archivos nuevos/modificados:**
- `web/src/components/TinymistPreview.vue` — reemplaza el contenedor de render typst.ts por un
  `<iframe>` que carga `static_url` (frontend real de tinymist, servido por el subproceso). Pide
  `/api/preview/info` al montar/cambiar de documento; si `enabled:false` (tinymist no
  disponible), emite `no-disponible` para que el padre decida caer a legacy.
- `web/src/api.js` — nueva función `getPreviewInfo(slug, codigo)`.
- `web/src/components/DocEditor.vue` — usa `TinymistPreview` por defecto; si emite
  `no-disponible`, cae a `TypstCanvasPreview` (Etapa 12.1, sin tocar). El scroll-sync de la
  Etapa 12.4 queda inactivo en modo tinymist (el iframe no expone `getScroller()`) sin romper
  nada -- `useScrollSync` ya tolera `null`; F7 lo elimina del todo más adelante de cualquier forma.

**Desviación de alcance encontrada y decidida sin instrucción del plan** (el plan no distingue
"documento" de "plantilla" en F3-F6): **`TemplateEditor.vue` (previsualización de plantillas)
NO se migró a tinymist, queda en modo legacy (typst.ts) intacto.** Motivo: el endpoint
`/api/preview/info` que diseñé asume un documento real registrado en `org.json` con una carpeta
autocontenida en `DOCS_ROOT` (usa `_ruta_typ_segura`/`core.doc_dir`); las plantillas viven en
`organizations/<slug>/templates/<nombre>/` y su vista previa es un **documento de muestra
generado en memoria** (`core.build_typ(_muestra_meta(), "lib.typ")`, ver `doctyp_web.py`), sin
una ruta de archivo persistente y estable que darle a `tinymist preview --root`. Extenderlo
requeriría decidir dónde materializar ese documento de muestra en disco (¿archivo temporal?
¿caché junto a la plantilla?) -- una decisión de diseño nueva, no cubierta por el plan. Se deja
explícitamente fuera de esta ejecución; señalar si quieres que se aborde.

**Verificado con Playwright real contra `doctyp web` levantado de verdad** (no solo build):
click en un documento real → el iframe se monta, carga `static_url`, el frontend nativo de
tinymist (dentro del iframe) abre su propio WebSocket al data plane y renderiza el documento.
Captura de pantalla confirmó resultado visual idéntico al render anterior con typst.ts (portada,
logos, colores, layout) -- descartada tras validar, no quedó en el repo.

---

## F4/F5 — Bridge del control plane + Clic→cursor (completado y verificado end-to-end)

**Cambio de forma respecto al plan original** (consistente con la decisión de F0 §5, confirmada
por el usuario): el plan asumía que el **frontend** se conectaba directo al control plane por
WebSocket. Como esa conexión la mantiene el **backend** (para sobrevivir a recargas de página),
F4 se implementó como un bridge backend→frontend reusando el mecanismo SSE ya existente
(`/api/events`) en vez de exponer un WebSocket nuevo al navegador.

**Archivos nuevos/modificados:**
- `doctyp_web.py`: `_emitir_evento_sse(evento)` -- empuja un evento a todas las conexiones SSE
  activas de inmediato (a diferencia de `_eventos_loop`, que solo revisa cambios periódicos).
  `_asegurar_preview_para` conecta `PreviewServer.on_editor_scroll_to` a esta función, agregando
  `slug`/`codigo_base` al evento (el frontend no conoce la ruta absoluta del `.typ`, así que
  comparar por esos dos campos es más simple que comparar filepaths).
- `web/src/composables/editorScrollToBus.js`: bus mínimo de un solo mensaje (`ref` reactivo)
  para que el evento SSE, recibido en `App.vue` (raíz del árbol), llegue hasta `CodeEditor.vue`
  (varios niveles más abajo: App → DocumentGrid/DocEditor → CodeEditor) sin tunelizar la
  prop/evento por cada componente intermedio. El proyecto no usa un store (Vuex/Pinia).
- `web/src/App.vue`: al recibir `{tipo: "editor-scroll-to", ...}` por SSE, llama
  `emitirEditorScrollTo(evento)`.
- `web/src/components/CodeEditor.vue`: nuevas props opcionales `slug`/`codigo` (para filtrar el
  evento -- solo reacciona si es de ESTE documento); `watch(ultimoEditorScrollTo, ...)` mueve el
  cursor de CodeMirror a `start:[fila,col]` (0-based, confirmado) y hace scroll + da foco.
- `web/src/components/DocEditor.vue`: pasa `slug`/`codigo` a `CodeEditor`.

**Verificación end-to-end (la parte más costosa de esta fase, con hallazgos de metodología
importantes documentados abajo):**

1. Prueba con cliente WS propio (Python, `doctyp_ws_client.py`) contra el data plane +
   control plane directamente: confirmado que un `src-point` en una posición que cae sobre
   prosa real produce `editorScrollTo` correctamente, coincidiendo con el hallazgo de F0.
2. Prueba con Playwright real (clic dentro del iframe, como lo haría un usuario): **muchos
   intentos fallaron** antes de dar con una posición que resolviera. Causa raíz identificada
   leyendo el código fuente de tinymist
   (`crates/typst-preview/src/actor/render.rs::resolve_span_by_frame_loc`): la resolución
   posición→span puede devolver `None` silenciosamente (sin ningún log visible salvo con
   `log::debug!`, que no aparece ni con `--verbose`) para posiciones sobre: títulos grandes de
   portada, tablas de contenido auto-generadas (`#s-indice()`), y en general cualquier
   contenido no resoluble a un span de texto plano. Los documentos de prueba
   (`TI-INF-SFW_2026-0001`) resultaron tener **todo su cuerpo en comentarios `// TODO`** (sin
   prosa real, invisible en el PDF) -- otra fuente de confusión durante la depuración.
3. **Éxito confirmado** usando el documento con contenido real (`TI-INF-RED_2026-0039`): clic
   sobre la palabra "establecimiento" en un párrafo real de la sección "2.1 Contexto" produjo
   `editorScrollTo` con `start:[35,401]` -- verificado carácter exacto contra el `.typ` real.
4. **Verificación visual final**: el mismo clic, en la app Vue completa (no un script de
   diagnóstico), causó que `.cm-scroller` (el editor) hiciera scroll de `scrollTop:0` a
   `scrollTop:731` y el foco pasara al editor de código. Captura de pantalla confirmó
   visualmente el texto correcto resaltado en naranja (selección de CodeMirror) en la línea
   exacta clickeada en el preview.

**Hallazgo de metodología (para futuras sesiones de depuración de este subsistema):** durante
esta verificación se acumularon temporalmente **7 procesos `tinymist` huérfanos** porque se
cerraron instancias de `doctyp web` con `pkill -9` en vez de `kill -INT`/Ctrl+C -- eso saltea el
`finally: _detener_preview_activa()` de `cmd_web` y deja tanto el subproceso tinymist como el
mecanismo de reintento automático (F2) corriendo indefinidamente en el proceso Python huérfano,
que sigue relanzando tinymist cada vez que ese subproceso cae. **Siempre cerrar `doctyp web` con
SIGINT al probarlo manualmente**, nunca con `pkill -9` directo al proceso Python.

---

## F6 — Editor→preview: memoria y salto explícito (completado y verificado end-to-end)

**Archivos nuevos/modificados:**
- `doctyp_web.py`: `api_preview_update_memory(slug, codigo, contenido)` (`POST
  /api/preview/memory`) -- envía `send_update_memory_files` al `PreviewServer` activo si
  corresponde a ese documento; si la preview no está activa, `{ok:false}` sin error (la próxima
  vez que se abra arrancará con el contenido en disco, que sigue siendo la fuente de verdad).
  `api_preview_jump(slug, codigo, line, character)` (`POST /api/preview/jump`) -- salto
  explícito, reusa `send_panel_scroll_to` ya construido en F2.
- `web/src/api.js`: `actualizarMemoriaPreview`, `saltarAPosicionPreview`.
- `web/src/components/CodeEditor.vue`: `defineExpose` agrega `getPosicionCursor()` (línea/
  columna 0-based del cursor actual, mismo criterio que `editorScrollTo`).
- `web/src/components/DocEditor.vue`: `watch(texto, ...)` con debounce de 300ms envía
  `actualizarMemoriaPreview` (solo si no está en modo legacy); `saltarEnPreview()` + atajo
  `Ctrl+Alt+J` + botón visible en el toolbar de la preview.
- `web/src/components/TinymistPreview.vue`: botón "Ver posición del cursor (Ctrl+Alt+J)",
  emite `saltar-aqui` hacia el padre.

**Nota de alcance:** `changeCursorPosition` (que el plan marcaba como "opcional, si el protocolo
lo soporta") se excluyó del todo -- F0 confirmó que el servidor la ignora explícitamente
("temporarily disabled to improve overall performance"), así que no había nada que implementar.

**Verificado end-to-end con Playwright real** (interceptando las llamadas de red, no solo
inspección visual): escribir texto en el editor de un documento real
(`TI-INF-RED_2026-0039`) disparó `POST /api/preview/memory` tras el debounce, y la consola del
iframe confirmó un nuevo `diff-v1` (recompilación) inmediatamente después. El botón de salto
disparó `POST /api/preview/jump` con su propio `diff-v1` de confirmación. **Crítico: se
verificó con `diff` de archivos que el `.typ` en disco no cambió en ningún momento** -- el
contenido escrito durante la prueba vivió únicamente en memoria del frontend y del subproceso,
tal como exige el punto 1 de F6 del plan.

---

## F7 — Eliminación del scroll sync (completado)

Se eliminó por completo (no comentado -- el historial vive en git, como pide el plan) el
mecanismo de scroll sincronizado de la Etapa 12.4, en **ambos** editores (documentos y
plantillas, ya que el motivo del plan -- "se desfasa respecto al contenido renderizado" --
aplica igual al modo legacy de plantillas, que sigue usando typst.ts):

- Borrado: `web/src/composables/useScrollSync.js`.
- `web/src/components/CodeEditor.vue`: quitado `getScroller()` de `defineExpose` (se conserva
  `getPosicionCursor()`, que es de F6, no relacionado).
- `web/src/components/TypstCanvasPreview.vue`: quitado `getScroller()` de `defineExpose`.
- `web/src/components/DocEditor.vue`: quitados el import de `useScrollSync`, el bloque de
  conexión/reconexión, y la prop `ref="refPreview"` que solo existía para eso (se conserva
  `refEditor`, usado por F6 para `getPosicionCursor()`).
- `web/src/components/TemplateEditor.vue`: mismo retiro completo (import, bloque, `ref`s en el
  template) -- el editor de plantillas sigue siendo funcional, solo sin scroll acoplado.

**Verificado:** `npm run build` sin errores (65 módulos, uno menos que antes por el archivo
borrado); `grep -rn "useScrollSync|getScroller"` sobre `web/src/` sin resultados (limpio, como
pide el criterio de salida de F7); Playwright confirmó que el documento en modo tinymist monta
sin errores de consola y que el scroll manual del editor no dispara ningún efecto en el iframe
(no queda ningún listener acoplando ambos paneles).

**Pendiente de F7** (delegado a F8, que actualiza documentación): el `CLAUDE.md` todavía
menciona `useScrollSync.js`/`getScroller()` en la nota de la Etapa 12.4 -- se corrige en F8
junto con el resto de la actualización de §14.

---

## F8 — Flag legacy y limpieza (completado)

- `doctyp web --legacy-preview`: fuerza typst.ts aunque tinymist esté disponible. Cableado en
  `doctyp.py` (nuevo flag del subparser `web`) y `doctyp_web.py`
  (`_preview_legacy_forzado`, chequeado en `_asegurar_preview_para` antes que la disponibilidad
  del binario). Verificado: con el flag, `/api/preview/info` devuelve `{enabled:false}` sin
  siquiera intentar lanzar tinymist.
- `CLAUDE.md` §14 actualizado: la Etapa 12 (12.2-12.4) queda marcada como reemplazada/retirada
  por la Etapa 15 para el editor de documentos (sigue vigente tal cual para plantillas, que no
  migraron); nueva nota completa de la Etapa 15 con arquitectura, protocolo, endpoints,
  decisiones de alcance (plantillas fuera) y advertencia de metodología (SIGINT, no `pkill -9`).
  §6 y §5 (sintaxis del CLI) actualizados con el flag nuevo.
- `plan15_notas.md` (archivo de trabajo temporal de F0) borrado, como pide el plan.
  `plan15_progreso.md` (este archivo) se conserva -- es el registro que pediste explícitamente
  para leer y entender el trabajo hecho; bórralo cuando ya no lo necesites.
- Verificación final: `py_compile` de los 5 módulos Python nuevos/modificados sin errores;
  `npm run build` de la SPA sin errores; `grep` confirma cero referencias a
  `useScrollSync`/`getScroller` en `web/src/`; sin procesos `tinymist`/`doctyp web` huérfanos al
  cerrar esta sesión de trabajo.

---

## Resumen ejecutivo final

Las 9 fases del Plan 15 (F0-F8) se completaron y verificaron con evidencia empírica real
(cliente WebSocket propio, Playwright contra la app real, `diff` de archivos, inspección de
tráfico de red) en cada paso, no solo revisión de código. Se encontraron y documentaron
desviaciones respecto al plan original en varios puntos (protocolo real de tinymist, ausencia
de puertos aleatorios seguros, autoapagado del proceso al perder el control plane,
`changeCursorPosition` deshabilitado, alcance de plantillas) — todas resueltas o explícitamente
delimitadas, no ocultadas. Se encontraron y corrigieron 3 bugs reales de concurrencia/ciclo de
vida en el código propio durante la verificación (no serían visibles sin las pruebas
end-to-end reales que se hicieron).

**Estado operativo:** `doctyp web` con `tinymist` instalado (o configurado vía
`local.preview_tinymist_path`) sirve la vista previa del editor de documentos a través de un
subproceso `tinymist preview` supervisado, con clic↔cursor real (precisión de carácter,
verificado), edición en memoria sin guardar, y salto explícito editor→preview
(botón + `Ctrl+Alt+J`). Sin tinymist disponible, o con `--legacy-preview`, cae automáticamente
al motor typst.ts anterior (Etapa 12), sin clic↔cursor pero con la vista previa funcional. El
editor de plantillas permanece siempre en el motor typst.ts (fuera del alcance de esta etapa).
El scroll sincronizado automático (Etapa 12.4) fue retirado por completo de ambos editores.

