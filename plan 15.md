# PLAN 15 — Preview vía servidor standalone (`tinymist preview`) lanzado por `doctyp`, jump bidireccional clic↔cursor, y eliminación de scroll sync

> **Audiencia:** agente ejecutor (Claude Sonnet) trabajando sobre el repositorio de `doctyp`.
> **Prerrequisito de lectura:** `CLAUDE.md` del repo (protocolo de build, convenciones, estado de la Etapa 12) y el informe técnico de la Etapa 12.2/12.3 (por qué `data-span` está muerto en el WASM de npm).
> **Estado esperado al terminar:** `doctyp web` lanza y supervisa un subproceso `tinymist preview`; la vista previa del navegador la sirve ese subproceso (no typst.ts); clic en la vista previa mueve el cursor del editor a la línea/columna exacta; una acción explícita del editor salta/resalta la posición en la vista previa; la sincronización automática de scroll de la Etapa 12.1 queda eliminada.

---

## 0. Decisión arquitectónica (contexto para el ejecutor)

La investigación de la Etapa 12.2/12.3 confirmó que el paquete npm `@myriaddreamin/typst.ts` **no puede** producir el mapeo render↔fuente (`SHOULD_ATTACH_DEBUG_INFO = false`, constante de compilación en las 4 rutas de export). La resolución posición↔span solo existe del lado Rust nativo. El binario `tinymist` expone exactamente eso como servidor standalone (`tinymist preview archivo.typ`): render SVG incremental por WebSocket (*data plane*) + protocolo de navegación bidireccional por WebSocket (*control plane*), heredado de typst-preview.

**Restricciones impuestas por el usuario:**
1. `tinymist` NO se usa como LSP ni como herramienta de edición. Solo como subproceso servidor de preview, invisible para el usuario. El editor sigue siendo el de `doctyp web`.
2. La sincronización automática de scroll editor↔preview (Etapa 12.1) se **elimina** — se desfasa respecto al contenido renderizado. Se reemplaza por saltos explícitos (clic y comando), que son precisos porque los resuelve el compilador.
3. `doctyp` es el punto de entrada único: lanzar `doctyp web` debe dejar todo funcionando sin pasos manuales (asumiendo binario instalado, ver F1).

**Reglas globales para el ejecutor:**
- NO adivinar flags de CLI ni esquemas de mensajes: verificarlos empíricamente (F0) antes de escribir código que dependa de ellos. Las referencias de §7 son *best-effort* de documentación pública y DEBEN confirmarse contra la versión instalada.
- Trabajar por fases en orden. Cada fase tiene criterio de verificación propio; no avanzar sin cumplirlo.
- Commits atómicos por fase, mensaje `plan15/F<n>: <descripción>`.
- No tocar los `.typ` del usuario ni el pipeline de guardado/versionado existente de doctyp. La preview es una capa aparte.

---

## 1. Alcance / No-alcance

**Alcance:**
- Gestión del binario `tinymist` (detección, versión mínima, mensaje de instalación).
- Subproceso: lanzamiento, puertos, ciclo de vida, reinicio, apagado limpio.
- Reemplazo del pipeline de render de la Etapa 12.1 (typst.ts en navegador) por el frontend/data-plane de tinymist para la vista previa.
- Cliente del control plane en el frontend de doctyp: clic→cursor, cursor→preview (explícito), archivos en memoria (compilar contenido no guardado).
- Eliminación del scroll sync automático.
- Modo legacy detrás de flag para no perder el render typst.ts existente.

**No-alcance (explícito):**
- Cualquier funcionalidad LSP (diagnósticos, autocompletado, hover) — prohibido en este plan.
- Export a PDF/PNG vía tinymist — doctyp mantiene su pipeline actual de compilación para outputs.
- Scroll sync automático "mejorado" — no se reintroduce en ninguna forma.

---

## 2. F0 — Reconocimiento y verificación empírica (sin escribir código de producción)

Objetivo: fijar los datos de los que depende el resto del plan.

1. **Inventario del repo.** Localizar y anotar en un archivo de trabajo `plan15_notas.md` (temporal, no commitear):
   - Módulo/comando que implementa `doctyp web` (servidor HTTP local + frontend del editor).
   - Componente del frontend donde vive la vista previa typst.ts de la Etapa 12.1 (montaje de `renderSvg`, worker/compilador WASM, etc.).
   - Código de scroll sync de la Etapa 12.1: listeners de scroll del editor y/o del contenedor de preview que muevan al otro lado. Anotar rutas y líneas exactas.
   - Cómo obtiene el frontend el contenido actual del buffer del editor (para F6).
2. **Binario.** Verificar `tinymist -V` en el entorno. Si no está: instalar la última versión estable desde GitHub Releases de `Myriad-Dreamin/tinymist` (binario standalone para Linux x86_64) SOLO en el entorno de desarrollo; el manejo para usuarios finales es F1.
3. **Superficie del CLI.** Ejecutar `tinymist preview --help` y volcar la salida completa a las notas. Identificar los flags reales para:
   - host/puerto del servidor HTTP de archivos estáticos (frontend de preview),
   - host/puerto del *data plane* (WebSocket de SVG),
   - host/puerto del *control plane* (WebSocket de editor),
   - no abrir navegador automáticamente,
   - renderizado parcial (viewport) si existe,
   - flags de fuentes/root del proyecto (deben apuntar al mismo root que usa doctyp para compilar).
   Nombres esperados (VERIFICAR, no asumir): `--data-plane-host`, `--control-plane-host`, `--no-open` o equivalente, `--partial-rendering`, `--root`, `--font-path`.
4. **Protocolo real.** Lanzar manualmente `tinymist preview` sobre un `.typ` de prueba, abrir la URL servida en Chromium (Playwright, instalación temporal como en la Etapa 12.2 — no commitear), y:
   - Conectarse al control plane con un cliente WebSocket de prueba (script desechable).
   - Hacer clic en el panel de preview y capturar el mensaje JSON que emite el servidor hacia el "editor" (esperado: evento tipo `editorScrollTo` con `filepath`, `start: [línea, col]`, `end: [línea, col]` — VERIFICAR nombres y formato 0-based/1-based).
   - Enviar los mensajes de la dirección inversa (esperados: `panelScrollTo` y `changeCursorPosition` con `filepath`, `line`, `character`) y confirmar el efecto visual en la preview.
   - Enviar `updateMemoryFiles` / `syncMemoryFiles` con contenido modificado y confirmar que la preview recompila sin tocar disco. Capturar también el evento `syncEditorChanges` (el servidor pidiendo re-sincronización completa).
   - Documentar TODOS los esquemas confirmados en las notas; §7 de este plan se corrige contra esa evidencia.

**Criterio de salida F0:** notas con (a) mapa del código a tocar, (b) flags confirmados, (c) esquemas de mensajes confirmados con ejemplos JSON reales capturados.

---

## 3. F1 — Gestión del binario `tinymist`

1. Nuevo módulo en doctyp (p. ej. `doctyp/preview/binary.py`):
   - `find_tinymist() -> Path | None`: orden de búsqueda: (1) variable de config de doctyp (`preview.tinymist_path` en el mecanismo de configuración existente del proyecto — usar el que ya haya, no inventar uno nuevo), (2) `shutil.which("tinymist")`.
   - `check_version(path) -> str`: ejecuta `-V`, parsea versión, valida contra `MIN_TINYMIST_VERSION` (constante; fijarla a la versión verificada en F0).
2. Si no se encuentra o la versión es insuficiente: `doctyp web` arranca igual en **modo legacy** (preview typst.ts actual, ver F8) y muestra un aviso claro en terminal y en la UI con la instrucción de instalación (URL de releases + `preview.tinymist_path`). No descargar binarios automáticamente en esta etapa (decisión: menos superficie de fallo y de seguridad; puede ser un plan futuro).
3. Tests: unit tests del parseo de versión y del orden de resolución (mock de `which`/config).

**Criterio de salida F1:** con binario presente se resuelve ruta+versión; sin binario, `doctyp web` no crashea y degrada a legacy con aviso.

---

## 4. F2 — Subproceso: lanzamiento y ciclo de vida

1. Módulo `doctyp/preview/server.py` con clase `PreviewServer`:
   - `start(main_typ: Path, root: Path)`: lanza `tinymist preview` con los flags confirmados en F0, bindeando **solo a 127.0.0.1** y con **puertos efímeros** (puerto 0 si el CLI lo soporta — verificar; si no, buscar puertos libres con `socket` y pasarlos explícitos, con reintento ante colisión).
   - Captura de stdout/stderr a un buffer/log accesible con `doctyp web --verbose` (o el flag de logging que ya exista).
   - Descubrimiento de URLs: parsear del stdout las URLs/puertos reales anunciados por el proceso (verificar formato en F0) y exponerlas: `static_url`, `data_plane_ws`, `control_plane_ws`.
   - `stop()`: `SIGTERM`, espera acotada (2 s), `SIGKILL` de respaldo. Registrar con `atexit` y en los manejadores de señal existentes de `doctyp web` — **cero procesos huérfanos**.
   - Supervisión: si el proceso muere, reintentar N=3 veces con backoff; tras agotar, notificar a la UI y degradar a legacy.
   - Cambio de documento activo en doctyp → reiniciar el subproceso con el nuevo `main.typ` (el CLI standalone fija el entrypoint al lanzar; verificar en F0 si existe comando de cambio en caliente antes de asumir reinicio).
2. Endpoint interno en el servidor HTTP de doctyp (p. ej. `GET /api/preview/info`) que devuelve `{enabled, static_url, data_plane_ws, control_plane_ws}` para que el frontend se configure sin hardcodear puertos.
3. Tests: arranque/parada limpia, colisión de puertos, kill externo del proceso → reinicio, `atexit`.

**Criterio de salida F2:** `doctyp web` deja el subproceso corriendo, `/api/preview/info` responde URLs válidas, cerrar doctyp (Ctrl+C incluido) no deja procesos vivos (`pgrep tinymist` limpio).

---

## 5. F3 — Vista previa servida por tinymist en la UI de doctyp

1. Sustituir el contenedor de render de la Etapa 12.1 por un `<iframe>` que cargue `static_url` (frontend de preview de tinymist, que se conecta solo al data plane y renderiza el SVG incremental). Mantener el layout editor|preview actual.
2. Ajustes de integración visual mínimos (tamaño del iframe, fondo). NO modificar el frontend interno de tinymist en esta fase; si más adelante se quiere theming, será plan aparte.
3. El código typst.ts de la Etapa 12.1 NO se borra: queda detrás del flag legacy (F8).

**Criterio de salida F3:** editar y guardar el `.typ` (aún sin memoria en vivo, eso es F6) actualiza la preview del iframe; el render es visualmente equivalente o superior al de typst.ts.

---

## 6. F4 — Cliente del control plane en el frontend de doctyp

1. Nuevo módulo JS/TS del frontend (p. ej. `previewBridge`): abre WebSocket a `control_plane_ws` (obtenido de `/api/preview/info`), con reconexión exponencial y estado visible (conectado/desconectado) en la UI.
2. Router de mensajes entrantes según los esquemas confirmados en F0 (referencia §7). Ignorar con log silencioso los eventos no manejados (`compileStatus` puede aprovecharse para el indicador de estado si doctyp ya tiene uno).
3. Al conectar (y al recibir `syncEditorChanges`): enviar sincronización completa de archivos en memoria (ver F6) para que servidor y editor partan del mismo estado.

**Criterio de salida F4:** con `doctyp web` abierto, la consola de desarrollo muestra conexión estable al control plane y los mensajes fluyen (verificable con logs de debug del bridge).

---

## 7. F5 — Clic→cursor (preview → editor)

1. Al recibir el evento de salto a fuente (esperado `editorScrollTo`; usar el nombre/formato confirmado en F0): 
   - Validar que `filepath` corresponde al documento (o a un archivo del proyecto abierto; si doctyp web es mono-archivo, ignorar rutas ajenas con aviso en log).
   - Convertir línea/columna al sistema de coordenadas del editor de doctyp (¡confirmar 0-based vs 1-based en F0!).
   - Mover el cursor, seleccionar el rango `start..end` si viene rango, hacer scroll del editor a la posición y dar foco al editor.
2. Nota de comportamiento: en tinymist/typst-preview el gesto puede ser clic simple o requerir modificador según versión — respetar el gesto que el frontend embebido emita por defecto; no interceptar eventos dentro del iframe.
3. Prueba manual guiada (documentar en notas): clic en una palabra en medio de un párrafo en la página 2+ de un documento multipágina → el cursor cae en esa palabra (precisión de carácter esperada por diseño del resolvedor de spans).

**Criterio de salida F5:** demo reproducible del salto exacto en documento multipágina, incluyendo contenido dentro de tablas y headings.

---

## 8. F6 — Editor→preview: archivos en memoria y salto explícito

1. **Memoria (reemplaza el "compilar al tipear" de typst.ts):** en cada cambio del buffer del editor, con debounce (reusar el debounce existente de la Etapa 12.1 si lo hay; si no, 150–300 ms), enviar el evento de actualización de archivos en memoria (`updateMemoryFiles` con `{ruta_absoluta: contenido}` — formato confirmado en F0). El guardado real en disco sigue el flujo actual de doctyp sin cambios.
2. **Salto explícito cursor→preview:** NO automático en scroll (regla del usuario). Implementar como acción deliberada:
   - Comando/botón "Ver en preview" + atajo (proponer `Ctrl+Alt+J`; ajustar a la convención de atajos existente) → envía el evento de salto a documento (`panelScrollTo` con `filepath/line/character` del cursor actual).
   - Opcional de bajo costo si el protocolo lo soporta (confirmado en F0): enviar `changeCursorPosition` en el mismo debounce del punto 1 para que la preview muestre el **indicador visual** de posición del cursor, sin hacer scroll. Si en pruebas produce cualquier movimiento no solicitado del panel, desactivarlo por defecto.
3. Tests frontend (unit): serialización de eventos, debounce, y que el scroll del editor NO dispara ningún mensaje al control plane.

**Criterio de salida F6:** tipear actualiza la preview sin guardar; el comando de salto lleva la preview a la posición del cursor; hacer scroll en el editor no mueve la preview jamás.

---

## 9. F7 — Eliminación del scroll sync (Etapa 12.1)

1. Con el mapa de F0.1: eliminar por completo los listeners y la lógica de sincronización automática de scroll editor↔preview (ambas direcciones si existieran). No dejar el código comentado: borrar; el historial vive en git.
2. Eliminar también cualquier opción de configuración/UI asociada al scroll sync, y sus menciones en la ayuda/docs del repo.
3. Verificar que no queden efectos residuales: scroll libre e independiente en ambos paneles, en modo nuevo y en modo legacy.

**Criterio de salida F7:** `grep` del repo sin referencias al scroll sync; QA manual: scrollear 10 páginas en el editor no altera la preview y viceversa.

---

## 10. F8 — Flag legacy y limpieza

1. Flag `doctyp web --legacy-preview` (y/o config `preview.engine = "tinymist" | "typst-ts"`): selecciona en el arranque qué pipeline se monta. Default: `tinymist` si el binario está disponible (F1); fallback automático a legacy si no.
2. En modo legacy: preview typst.ts de la Etapa 12.1 tal como está hoy **pero ya sin scroll sync** (F7 aplica a ambos modos) y sin las funciones de jump (no disponibles ahí, por el informe 12.2).
3. Actualizar `CLAUDE.md` §14 (estado de la Etapa 12): 12.2/12.3 pasan de "bloqueadas" a "resueltas vía Plan 15 (servidor standalone)"; documentar el nuevo subsistema (módulos, flags, protocolo, versión mínima de tinymist) y la eliminación del scroll sync.
4. Borrar `plan15_notas.md` y cualquier artefacto temporal (Playwright, scripts de prueba desechables) antes del commit final.

**Criterio de salida F8:** ambos modos operativos conmutables por flag; documentación actualizada; árbol de trabajo limpio.

---

## 11. §7 Referencia de protocolo (best-effort — CORREGIR CON F0 ANTES DE USAR)

Mensajes JSON sobre el WebSocket del control plane (nombres heredados de typst-preview; la versión instalada manda):

| Dirección | Evento | Payload esperado | Uso en este plan |
|---|---|---|---|
| servidor→editor | `editorScrollTo` | `{filepath, start:[l,c], end:[l,c]}` | F5: clic→cursor |
| servidor→editor | `syncEditorChanges` | `{}` | F4/F6: re-sincronizar memoria completa |
| servidor→editor | `compileStatus` | `{kind}` | opcional: indicador de estado |
| editor→servidor | `syncMemoryFiles` | `{files:{ruta:contenido}}` | F4: al conectar |
| editor→servidor | `updateMemoryFiles` | `{files:{ruta:contenido}}` | F6: al tipear (debounced) |
| editor→servidor | `removeMemoryFiles` | `{files:[rutas]}` | al cerrar/descartar buffer |
| editor→servidor | `panelScrollTo` | `{filepath, line, character}` | F6: salto explícito |
| editor→servidor | `changeCursorPosition` | `{filepath, line, character}` | F6: indicador (opcional) |

Rutas: absolutas y consistentes con el `--root` pasado al subproceso. Confirmar en F0 la base de índices (0/1) de líneas y columnas en cada dirección — es la fuente de bugs off-by-one más probable del plan.

---

## 12. Criterios de aceptación globales

1. `doctyp web` con tinymist instalado: preview en vivo al tipear (sin guardar), clic→cursor con precisión de carácter, salto explícito cursor→preview, cero scroll sync automático, apagado sin procesos huérfanos.
2. `doctyp web` sin tinymist: modo legacy funcional con aviso claro, sin scroll sync, sin crashes.
3. Todo bindeado a localhost; ningún puerto expuesto fuera de 127.0.0.1.
4. Suite de tests del repo en verde + tests nuevos de F1/F2/F6.
5. `CLAUDE.md` refleja el estado real.

## 13. Riesgos y mitigaciones

- **Flags/protocolo distintos a lo documentado** → F0 obligatoria antes de codificar; §7 es referencia, no contrato.
- **Cambio de formato entre versiones de tinymist** → versión mínima pinneada (F1) y verificación de versión al arrancar.
- **Rutas relativas/absolutas inconsistentes en memoria** → normalizar siempre a absolutas respecto al root del proyecto en el bridge.
- **Regresión de UX por perder scroll sync** → mitigada por diseño: el salto explícito + clic→cursor son el reemplazo aprobado por el usuario.
- **Multi-archivo (imports)** → `updateMemoryFiles` soporta múltiples rutas; si doctyp web hoy es mono-buffer, dejar el soporte multi-archivo declarado como extensión natural, no implementarlo aquí.