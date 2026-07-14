# tinymist-implementation-plan.md — Auditoría y plan de implementación

> **Fecha de auditoría:** 2026-07-14 · **Base auditada:** rama `master` + working tree
> (commit `6e3bc7a` + cambios sin commitear en `DocEditor.vue`/`TemplateEditor.vue`).
> **tinymist de referencia:** 0.15.2 (mínimo verificado en `doctyp_preview_binary.py`).
>
> Documento de trabajo para ejecutar otro día. Sigue la regla del repo (CLAUDE.md §0):
> **plan antes de código**. Decisiones ya tomadas por el usuario (2026-07-14):
> 1. **Adopción completa del LSP de tinymist al 100 % de sus capacidades** (Fase 1).
> 2. **D4 resuelta:** SIN pestaña secundaria de `lib.typ` en el editor de documentos —
>    `lib.typ` es plantilla y se edita solo desde el editor de plantillas; ni editar ni
>    visualizar su código desde el editor de documentos (tampoco al hacer clic en
>    contenido generado por la plantilla).
> 3. **D5 resuelta:** SÍ ofrecer los exportadores rápidos de tinymist.
> 4. **Autoguardado:** 300 ms después de la última edición, el documento se guarda a
>    disco y se levantan los eventos pertinentes (Fase 3.3).
> 5. **Jump bidireccional automático e implícito, sin botón:** el salto ocurre en el
>    momento del clic, tanto en el editor como en el render (Fase 3.2). Esto **revierte**
>    la regla anterior de "salto solo explícito" (Plan 15 §8/F7) — ver H6.

---

## 0. Corrección de premisas (leer primero)

El encargo original describía una pila que **no es la de este repo**:

| Premisa del encargo | Realidad del repo |
|---|---|
| Proxy WebSocket en **Node.js** que hace spawn de tinymist | Backend **Python stdlib puro** (`doctyp_web.py` + `doctyp_preview_server.py`); Node solo existe para el build de Vite. Regla del proyecto: sin dependencias externas en el backend. |
| Frontend con `@codemirror/lsp-client` o transporte LSP propio | CodeMirror 6 **sin ninguna integración LSP**. No se envía `didOpen`/`didChange`/`didSave`/`didClose` porque no hay cliente ni servidor LSP en ejecución. |
| Tinymist como LSP + preview | Tinymist se usa **únicamente** como `tinymist preview` standalone (decisión explícita del Plan 15 §0, documentada en `doctyp_preview_server.py:14-15`). |
| Túnel WS navegador↔tinymist | El navegador **nunca** habla WebSocket con tinymist: el *control plane* lo sostiene el backend (`doctyp_ws_client.py`) y los eventos llegan al frontend por **SSE** (`/api/events`). El *data plane* sí llega al navegador, pero dentro del `<iframe>` con el frontend propio de tinymist. |

Consecuencia: las preguntas de la auditoría sobre "protocolo LSP estándar" y "parseo
JSON-RPC" no aplican al estado actual — no hay JSON-RPC en ninguna parte. Se responden
como **brecha de capacidades** (Fase 1) en vez de como defectos de una implementación
existente.

---

## 1. Diagnóstico actual

### 1.1 Fortalezas (no tocar sin motivo)

- **Ciclo de vida del subproceso: sólido.** `PreviewServer` (`doctyp_preview_server.py`)
  resuelve correctamente los tres problemas duros que este tipo de integración suele
  fallar:
  - *Puertos:* tinymist hace `.unwrap()` del bind y aborta con SIGABRT ante colisión; el
    módulo sondea puertos libres reales (`_puerto_libre()`, bind a puerto 0) y los pasa
    explícitos con `--data-plane-host`/`--control-plane-host`. Correcto y ya verificado
    empíricamente (dos instancias con puertos "por defecto" colisionan).
  - *Caídas dobles:* la caída la observan dos hilos (lector de stdout y cliente WS);
    la guarda `_reiniciando` + contador `_generacion` evita el doble reinicio. Bien
    razonado y comentado.
  - *Apagado:* `stop()` hace `terminate()` → `wait(2s)` → `kill()`; además el propio
    tinymist se autoapaga si el control plane se cierra (confirmado en F0). `doctyp web`
    llama `_detener_preview_activa()` en su `finally`. **Sin fuga de huérfanos en el
    flujo normal.** La única vía de fuga conocida es `kill -9` al proceso Python (saltea
    el `finally`) — ya documentada en CLAUDE.md §14; ver mitigación opcional en Fase 2.4.
- **Diseño "control plane en el backend": correcto.** tinymist se autoapaga por completo
  si su control plane se desconecta; anclarlo al backend (no al navegador) hace que la
  preview sobreviva a recargas de página. Es la decisión arquitectónica clave y está bien
  tomada.
- **Memoria en vivo sin tocar disco:** `updateMemoryFiles` con debounce de 300 ms
  (`DocEditor.vue:149-159`) recompila el contenido no guardado sin escribir el `.typ`.
  Equivale funcionalmente al `didChange` de un LSP para el caso de uso actual.
- **Backward sync (preview→editor) funciona de punta a punta:** clic en el iframe →
  `src-point` por data plane (frontend embebido de tinymist) → `editorScrollTo` por
  control plane → `on_editor_scroll_to` → `_emitir_evento_sse()` (push inmediato, sin
  esperar el tick de polling de 1.5 s — bien) → SSE → `App.vue` → bus
  (`editorScrollToBus.js`) → `watch` en `CodeEditor.vue:83-95` → `dispatch({selection,
  scrollIntoView})`. Latencia dominada por un hop SSE local: despreciable.
- **Cliente WS (`doctyp_ws_client.py`):** correcto para su propósito declarado (frames
  de texto pequeños, ping/pong, close). Sin buffering intermedio: `recv` directo →
  callback. No hay retraso artificial de parseo.

### 1.2 Hallazgos (defectos y brechas, por severidad)

**H1 — `on_compile_status` nunca se cablea (brecha funcional real).**
`PreviewServer` expone el callback (`doctyp_preview_server.py:94`) y lo invoca al recibir
`compileStatus` del control plane (`:214-215`), pero `_asegurar_preview_generico()`
(`doctyp_web.py:241-293`) solo asigna `on_editor_scroll_to`. Resultado: **los errores de
compilación en vivo no llegan nunca a la UI propia** (StatusBar) — el usuario solo los ve
si el frontend embebido de tinymist los muestra dentro del iframe. Es el equivalente a
"diagnósticos en tiempo real" de la auditoría, ya pagado y sin usar. Arreglo barato
(Fase 2.1).

**H2 — clic→cursor puede saltar al archivo equivocado (bug latente).**
El evento `editorScrollTo` trae `filepath` (el archivo real que resolvió tinymist), pero
ni el bridge (`doctyp_web.py:281-283`) ni `CodeEditor.vue:83-95` lo comparan con el
archivo en edición: el filtro es solo por `(recurso_tipo, slug, nombre)`, etiquetados al
*arrancar* la preview. Si el usuario hace clic sobre contenido generado por `lib.typ`
(portada, ficha, tablas — la mayor parte visual de un informe), tinymist resuelve el span
a `lib.typ` de la carpeta del documento y el editor **mueve el cursor a esa
línea/columna dentro del `.typ` principal**, que es otra cosa. Para plantillas es al
revés y hoy funciona de casualidad: el usuario edita `lib.typ` y la muestra importa
`lib.typ`, así que los clics que resuelven a la muestra deberían ignorarse y los que
resuelven a `lib.typ` aplicarse. Arreglo en Fase 3.1.

**H3 — colas SSE sin cota ni limpieza verificable.**
`_sse_colas` son `queue.Queue()` sin `maxsize` (`doctyp_web.py:~783`). Un cliente SSE que
deja de leer (pestaña congelada, red pausada) acumula eventos indefinidamente. Riesgo
bajo en localhost mono-usuario, pero es un leak silencioso. Verificar además que la cola
se retire del set cuando la conexión muere a mitad de un `write` (el handler debe hacer
`finally: _sse_colas.discard(cola)`). Fase 2.2.

**H4 — restos de depuración y fricciones menores.**
- `App.vue:242`: `console.log("[DEBUG] editor-scroll-to …") // TEMP` — retirar.
- `resolver_tinymist_utilizable()` ejecuta `tinymist -V` (subproceso) en **cada**
  `GET /api/preview/info` y en cada relanzamiento (`_tinymist_path()`); cachear el
  resultado por proceso (invalidar solo si cambia `settings.json`) ahorra ~10-50 ms por
  apertura de editor. Fase 2.3.
- Cambiar de documento reinicia el subproceso completo (~1-3 s) y cambia el puerto del
  data plane → el iframe recarga desde cero. Es el diseño acordado ("una preview a la
  vez"); no es un bug, pero la Fase 1 (LSP unificado) lo eliminaría de raíz — ver §2.

**H5 — el cliente WS no soporta fragmentación (limitación aceptada… hasta la Fase 1).**
`_leer_frame()` (`doctyp_ws_client.py:104-117`) declara explícitamente que no maneja
mensajes fragmentados. Para el control plane actual (JSON corto) es correcto. Si se
reutiliza este transporte para LSP (respuestas de `completion` pueden superar cientos de
KB), la fragmentación y los frames >64 KB pasan a ser obligatorios. No arreglar ahora;
condición de entrada de la Fase 1.

**H6 — Forward sync: hoy explícito (botón/Ctrl+Alt+J); regla REVERTIDA por el usuario.**
En el código actual `panelScrollTo` solo se envía con Ctrl+Alt+J / botón, siguiendo la
regla del Plan 15 §8/F7 ("nada de sincronización automática"). El usuario **revirtió esa
regla el 2026-07-14** con un alcance preciso: el jump debe ser **automático e implícito
al momento del clic** (clic en el editor → preview salta; clic en el render → cursor
salta), **sin botón**. Sigue SIN haber sincronización por scroll ni por movimiento de
cursor con teclado — el disparador es únicamente el clic. Implementación en Fase 3.2;
al ejecutarla, actualizar también la nota de la Etapa 15 en CLAUDE.md §14 para que la
regla escrita no contradiga el comportamiento. Nota técnica: `changeCursorPosition`
sigue deshabilitado server-side en tinymist 0.15.2, así que la dirección editor→preview
se hace con el mismo `panelScrollTo` actual, disparado por el clic.

### 1.3 Respuesta directa a las 4 preguntas de la auditoría

1. **LSP estándar:** no existe. Ni notificaciones, ni diagnósticos LSP, ni
   autocompletado, ni hover. Es la brecha principal → Fase 1 (**decidida**: adopción
   completa del LSP, ver ahí).
2. **Sincronización bidireccional:** backward (preview→editor) funciona con la latencia
   mínima posible para esta arquitectura (push SSE inmediato), con el bug H2 pendiente.
   Forward existe hoy solo como salto explícito; por decisión nueva del usuario pasa a
   ser automático al clic, sin botón (H6 / Fase 3.2).
3. **Gestión de recursos:** correcta (ver 1.1); sin huérfanos salvo `kill -9`;
   mitigación opcional en Fase 2.4.
4. **Rendimiento:** sin buffering innecesario ni retrasos de parseo detectables; los
   costos reales son `tinymist -V` repetido (H4) y el reinicio por cambio de documento
   (aceptado por diseño; lo elimina la Fase 1 si se aprueba).

---

## 2. Roadmap de implementación

### Fase 1 — Adopción COMPLETA del LSP de tinymist (✅ DECIDIDA por el usuario)

**Decisión tomada (2026-07-14):** el editor debe usar `tinymist lsp` de forma completa,
aprovechando el 100 % de sus funcionalidades. Las antiguas decisiones D1-D3 quedan así:

- **D1 (¿LSP?): resuelta — sí, completo.**
- **D2 (transporte): adoptada la opción (a)** — upgrade WebSocket dentro del propio
  `http.server` (`GET /api/lsp` → handshake RFC 6455 servidor, espejo del ya escrito en
  `doctyp_ws_client._handshake`, secuestrando `self.connection`). Mismo puerto, stdlib
  puro, coherente con la cultura del repo. Requiere aceptar frames **enmascarados**
  entrantes, enviar sin máscara y **fragmentación** en ambos lados (H5). La alternativa
  POST+SSE queda descartada salvo bloqueo imprevisto.
- **D3 (cliente CodeMirror): híbrido** — `@codemirror/lsp-client` (paquete oficial) para
  el núcleo que cubra (completion, hover, diagnostics, signature help, rename…) +
  **extensiones propias** para todo lo que el paquete no implemente (semantic tokens,
  inlay hints, folding, code lens, document colors, outline…). **Antes de escribir código,
  verificar la superficie real del paquete contra sus `.d.ts` instalados** (disciplina de
  la Etapa 10); si resulta inmaduro, puente manual completo con las piezas estándar de
  CodeMirror (`@codemirror/lint`, `@codemirror/autocomplete`, `hoverTooltip`, etc.) —
  cambia el pegamento, no el plan.

**Definición operativa de "100 %":** el universo de funcionalidades NO se asume de
memoria — se toma de la respuesta `initialize` (ServerCapabilities) del binario
instalado (≥ 0.15.2). El **paso 0 obligatorio** de esta fase es capturar ese JSON
(snippet §3.5), volcarlo a un archivo de trabajo y convertirlo en checklist: cada
capability anunciada debe quedar *implementada*, *mapeada a una función ya existente de
doctyp* (p. ej. save/compile propios) o *descartada con motivo escrito* (p. ej.
específica de VS Code). La matriz de las sub-fases 1B-1D es la esperada para tinymist
0.15.x y se ajusta a lo observado en el paso 0.

---

#### Fase 1A — Transporte e infraestructura (prerrequisito de todo lo demás)

1. **`doctyp_ws_server.py`** (nuevo, stdlib): lado servidor RFC 6455 — validar cabeceras
   de upgrade, responder `101` con `Sec-WebSocket-Accept`, leer frames enmascarados,
   escribir sin máscara, ping/pong/close, **fragmentación y frames de 64 bits** (las
   respuestas de `completion`/`semanticTokens` pueden superar cientos de KB).
2. **Fragmentación también en `doctyp_ws_client.py`** (H5) — mantiene simetría y
   desbloquea reutilizarlo si hiciera falta.
3. **`doctyp_lsp_server.py`** (nuevo): gestor del subproceso `tinymist lsp` por **stdio
   binario** (`text=False`, a diferencia del `Popen` de preview) con framing LSP
   (`Content-Length: N\r\n\r\n{json}`, snippet §3.4). Mismo patrón de ciclo de vida ya
   probado en `PreviewServer`: contador de generación, reintentos con backoff, `stop()`
   en el `finally` de `cmd_web`, arranque perezoso al abrir el primer editor. **Un solo
   proceso LSP por sesión de `doctyp web`.**
4. **Endpoint `GET /api/lsp`** (upgrade WS) — puente **crudo** JSON-RPC navegador↔stdio.
   El backend no interpreta el protocolo salvo tres excepciones:
   - *allowlist* de `workspace/executeCommand` (la API no debe volverse un ejecutor
     arbitrario — CLAUDE.md §6): permitir solo los comandos `tinymist.*` que las
     sub-fases 1D/1E usan explícitamente;
   - responder localmente los server→client requests que el cliente web no maneje
     (`workspace/configuration`, `client/registerCapability`,
     `window/workDoneProgress/create`) para que el servidor no quede colgado esperando;
   - reconexión: si el navegador recarga, el proceso LSP sobrevive (mismo principio que
     el control plane de preview). LSP **no permite** un segundo `initialize` sobre la
     misma sesión, así que el puente debe reasociar la conexión WS nueva a la sesión LSP
     viva (el `initialize` lo hace el backend una sola vez, al arrancar el proceso) y el
     frontend solo reabre sus documentos con `didOpen` para reconverger estado.
5. **Workspace/roots:** intentar **un** proceso con `workspace/didChangeWorkspaceFolders`
   al cambiar de documento/plantilla activos (verificar que tinymist lo anuncie en
   capabilities); *fallback* si no lo soporta: reiniciar el LSP al cambiar de root —
   aceptable, es exactamente lo que ya hace la preview hoy.
6. **`initializationOptions` / `workspace/didChangeConfiguration`:** configurar desde el
   backend (única fuente de verdad, mismo criterio que `settings.json`):
   `fontPaths` (= `fonts/` del documento si existe, mismo criterio que `--font-path` de
   la preview), `formatterMode: "typstyle"`, `semanticTokens: "enable"`,
   `exportPdf: "never"` (**el PDF oficial lo produce solo `doctyp compile`**, con su
   versionado — el LSP no debe escribir PDFs por su cuenta), y opciones de completion
   según lo que exponga la versión instalada.

#### Fase 1B — Núcleo de edición (paridad con un IDE)

| Capability | Integración en el editor |
|---|---|
| `textDocument/didOpen`/`didChange` (incremental)/`didSave`/`didClose` | Ciclo de vida completo desde `CodeEditor.vue`, **reusando el `updateListener` existente** (no crear un segundo listener). `didSave` en `guardarCambios()`; `didClose` en `onUnmounted`. Snippet §3.3. |
| `publishDiagnostics` (push) | `@codemirror/lint` (subrayados + gutter) + contador de errores/avisos en `StatusBar.vue`. Reemplaza el rol de "diagnósticos" que hoy solo cubre parcialmente `compileStatus` (H1) — ambos conviven: compileStatus es estado de la preview, diagnostics es estado del código. |
| `completion` (+ `completionItem/resolve`) | `@codemirror/autocomplete` con los `triggerCharacters` que anuncie el servidor (`#`, `.`, `@`, `/`…); soportar snippets (`insertTextFormat: 2`) con `snippet()` de CodeMirror. Debe completar símbolos del `lib.typ` local (`tabla`, `aviso`, `crear-meta`…) — es la prueba de que el root está bien. |
| `hover` | `hoverTooltip` con render del markdown de respuesta. |
| `signatureHelp` | Tooltip de firma al tipear `(`/`,` (trigger chars de capabilities). |
| `documentHighlight` | Ocurrencias del símbolo bajo el cursor → decorations sutiles. |

#### Fase 1C — Navegación y símbolos

| Capability | Integración |
|---|---|
| `definition` / `declaration` / `references` | Mismo archivo → mover cursor (reusar el mecanismo de `editorScrollToBus`). **Otro archivo (típicamente el `lib.typ` local del documento)** → **NO se abre ni se muestra** (✅ D4 resuelta: `lib.typ` es plantilla y solo se edita/visualiza desde el editor de plantillas). El resultado que apunte fuera del archivo en edición se descarta con un aviso no intrusivo ("Definido en la plantilla (lib.typ) — edítala desde el editor de plantillas"). En el editor de **plantillas** el mismo salto sí opera, porque ahí el archivo en edición ES `lib.typ`. |
| `documentSymbol` | Panel *outline* plegable (headings + funciones) con clic→salto; vive junto al editor, colapsable desde StatusBar. |
| `workspace/symbol` | Quick-open de símbolos (Ctrl+T) sobre el workspace activo. |
| `foldingRange` | `foldService` de `@codemirror/language` alimentado por el servidor (headings, bloques de código, funciones largas de `lib.typ`). |
| `selectionRange` | "Expandir selección" (Alt+↑ / Alt+↓). |
| `documentLink` (si se anuncia) | Links clicables en `#link(...)`, imports y rutas `img/…`. |

#### Fase 1D — Presentación avanzada y refactor

| Capability | Integración |
|---|---|
| `semanticTokens` (full + delta) | Decorations de CodeMirror pintadas desde los tokens del servidor. **Convive con `typst-lang.js`** (Etapa 10): el StreamLanguage da color inmediato al tipear; los tokens semánticos, más precisos, pisan encima al llegar. No borrar `typst-lang.js` — es también el modo sin LSP (ver "degradación" abajo). |
| `inlayHint` | Widgets inline (nombres de parámetros, tipos) con toggle en StatusBar (pueden estorbar en prosa). |
| `documentColor` + `colorPresentation` | Swatches sobre `rgb("…")`/`luma(…)`/tokens de color de `lib.typ`, con picker al clic — especialmente útil en el editor de plantillas. |
| `codeAction` | Menú contextual/bombilla (subir/bajar nivel de heading, refactors que ofrezca la versión). Filtrar acciones cuyo `command` no esté en la allowlist del puente. |
| `codeLens` | Widgets sobre líneas. **Mapear, no duplicar:** los lens de preview de tinymist se re-mapean a los flujos propios de doctyp; los de export se conectan a la "exportación rápida" de D5 (ver abajo) en vez de ejecutar el comando VS Code que traen. |
| `rename` + `prepareRename` | Diálogo de renombrar símbolo. El `WorkspaceEdit` resultante se aplica **solo a archivos abiertos en el editor**; si toca archivos no abiertos, abrirlos primero o abortar con aviso — nunca escribir a disco por fuera de la vista del usuario. |
| `formatting` (typstyle) | Botón "Formatear" en StatusBar + atajo Ctrl+Shift+F + opción *format-on-save* desactivada por defecto (con el autoguardado de Fase 3.3, "on save" significa "en cada autoguardado" — mantenerla apagada salvo pedido explícito, formatear mientras se tipea sería invasivo). |
| `experimental/onEnter` (si se anuncia) | Keymap de Enter (continuación de comentarios/listas) con prioridad sobre el Enter por defecto. |

**Comandos `workspace/executeCommand` a evaluar en el paso 0** (allowlist candidata):
`tinymist.doStartPreview` / `tinymist.doKillPreview` / `tinymist.scrollPreview` (1E),
`tinymist.pinMain` (fijar el main al cambiar de documento sin tocar roots),
`tinymist.getDocumentMetrics` (contador de palabras del *documento renderizado* —
candidato a reemplazar el conteo en cliente de StatusBar, hoy sobre el texto crudo),
`tinymist.doClearCache`. Exportadores (`tinymist.exportPdf`/`Svg`/`Png`/`Markdown`/
`Text`): ✅ **D5 resuelta — SÍ se ofrecen todos**, como menú "Exportar…" en StatusBar,
rotulado explícitamente como **exportación rápida** (sin versión, sin snapshot, sin fila
en `org.json`) para que no se confunda con "Compilar" (el flujo versionado oficial,
`doctyp compile`, que queda intacto como única vía del PDF oficial). Detalles: el
archivo exportado se ofrece como **descarga** (el comando devuelve/escribe una ruta en
el servidor; el backend la sirve una vez y la borra o la escribe con nombre
oculto/temporal en la carpeta del documento, mismo patrón que la miniatura) — nunca debe
pisar el `<código-base>.pdf` que genera "Compilar". Todos estos comandos entran en la
allowlist del puente.

**Degradación (obligatoria, mismo criterio que `--legacy-preview`):** si `tinymist` no
está instalado o el WS del LSP no conecta, el editor funciona exactamente como hoy
(StreamLanguage + sin diagnósticos). Nueva bandera `doctyp web --no-lsp` para forzarlo.
Nada del núcleo de guardar/versionar/compilar puede depender del LSP.

#### Fase 1E — Unificación de la preview bajo el proceso LSP

Objetivo: retirar `PreviewServer` standalone y que el **mismo** proceso `tinymist lsp`
sirva la preview de sus documentos abiertos (así opera la extensión de VS Code), lo que
elimina de raíz el reinicio de subproceso por cambio de documento (H4) y el doble
proceso tinymist. (`updateMemoryFiles` ya habrá desaparecido antes, en la Fase 3.3: el
autoguardado escribe a disco y tinymist recompila desde ahí; con 1B, `didChange` además
mantiene el estado en memoria del LSP.)

1. **Verificación de protocolo primero** (misma disciplina que F0 del Plan 15 — en vivo,
   no por lectura): firma real de `tinymist.doStartPreview` en la versión instalada
   (¿acepta `--data-plane-host`? ¿devuelve los puertos?), cómo llegan `editorScrollTo`/
   `compileStatus` en modo LSP (¿siguen por control plane WS aparte, o como
   notificaciones LSP custom?), y comportamiento al cerrar (¿`doKillPreview` basta?).
   Documentar los hallazgos en el archivo de trabajo de la fase.
2. Migrar `_asegurar_preview_generico()` a `executeCommand` sobre el proceso LSP; los
   endpoints públicos que sigan vivos (`/api/preview/info|jump` — `memory` ya se retiró
   en la Fase 3.3) **mantienen su contrato** hacia el frontend (jump se re-mapea a
   `tinymist.scrollPreview` o al mecanismo que confirme el paso 1).
3. Retirar `doctyp_preview_server.py` + `doctyp_preview_binary.py` solo cuando la
   paridad esté verificada (checklist §4.2-4.4 en verde sobre el modo unificado);
   `doctyp_ws_client.py` se retira si el paso 1 confirma que ya nada usa el control
   plane WS.
4. **Riesgo asumido:** si la firma/protocolo no es viable en la versión instalada, se
   mantienen los dos procesos (LSP + preview standalone) — conviven sin conflicto y el
   resto de la Fase 1 no depende de esta unificación.

### Fase 2 — Robustez de la conexión de preview (sin decisiones, ejecutable ya)

Las banderas de arranque actuales (`preview --root … --data-plane-host 127.0.0.1:N
--control-plane-host 127.0.0.1:N --no-open --verbose --font-path …`) son correctas; esta
fase no las cambia.

1. **Cablear `compileStatus` → SSE → StatusBar (H1).** En `_asegurar_preview_generico()`,
   junto al `on_editor_scroll_to` existente:
   asignar `nuevo.on_compile_status` emitiendo `{"tipo": "compile-status",
   "recurso_tipo": tipo, "slug": slug, "nombre": nombre, "kind": kind}`; en `App.vue`
   reexponerlo por un bus análogo a `editorScrollToBus.js` (o el mismo módulo con un
   segundo ref) y mostrar en `StatusBar.vue` un indicador Compilando/OK/Error. Los
   `kind` reales que emite tinymist deben confirmarse en vivo (se esperan
   `Compiling`/`CompileSuccess`/`CompileError`); registrar lo observado en el commit.
2. **Acotar y limpiar colas SSE (H3).** `queue.Queue(maxsize=100)` + `put_nowait` con
   `except queue.Full: pass` (descartar el evento para ese cliente muerto es correcto:
   todos los eventos actuales son re-sincronizables); confirmar `finally:
   _sse_colas.discard(...)` en el handler de `/api/events`.
3. **Cachear `resolver_tinymist_utilizable()` (H4)** en variable de módulo con
   invalidación por mtime de `settings.json`.
4. **(Opcional) Guardia anti-huérfanos para `kill -9`:** pasar
   `start_new_session=True` en el `Popen` y escribir un pidfile en el scratchpad; al
   arrancar `doctyp web`, si el pidfile apunta a un `tinymist preview` vivo cuyo padre ya
   no existe, terminarlo. Alternativa Linux-only más limpia: `prctl(PR_SET_PDEATHSIG)`
   vía `preexec_fn` con `ctypes` — decidir en el momento; no bloquea nada más.
5. **Retirar el `console.log` TEMP de `App.vue:242` (H4).**

### Fase 3 — Sincronización bidireccional y autoguardado

*(Decisiones del usuario 2026-07-14: jump automático e implícito al clic — sin botón —
y autoguardado a 300 ms. La antigua regla F7 de "salto solo explícito" queda revertida
en los términos de H6: el disparador es el clic, nunca el scroll ni el cursor por
teclado.)*

1. **Arreglar el salto a archivo equivocado (H2).** Backend: en el bridge de
   `editorScrollTo`, comparar `datos["filepath"]` con el archivo que el usuario edita y
   etiquetar el evento:
   - documentos: archivo editado = `main_typ` → `es_editable = (Path(datos["filepath"]).resolve() == main_typ.resolve())`
   - plantillas: archivo editado = `lib.typ` de la plantilla (¡no la muestra!) →
     comparar contra `core.plantilla_dir(slug, nombre) / "lib.typ"`.
   Frontend (`CodeEditor.vue`): ignorar eventos con `es_editable !== true`, mostrando el
   aviso no intrusivo de D4 ("Definido en la plantilla (lib.typ) — edítala desde el
   editor de plantillas"). Es el comportamiento **definitivo**, no un paliativo: por D4
   nunca se abre `lib.typ` desde el editor de documentos. Snippet en §3.2.
2. **Jump editor→preview automático al clic (sin botón).**
   - **Quitar** el botón "Ver posición del cursor" y el toolbar asociado de
     `TinymistPreview.vue`, el atajo global Ctrl+Alt+J y `onKeydownGlobal` en
     `DocEditor.vue`/`TemplateEditor.vue`. El emit `saltar-aqui` desaparece.
   - **Disparador nuevo:** clic real dentro del editor — `EditorView.domEventHandlers({
     click })` en `CodeEditor.vue` (snippet §3.7). En el handler: si la selección
     resultante es vacía (clic de posicionamiento, no un arrastre de selección ni
     doble-clic que selecciona palabra), obtener línea/columna y llamar al mismo
     `POST /api/preview/jump` actual. Tipear, mover el cursor con flechas o scrollear
     **no** dispara nada.
   - La dirección preview→editor ya es automática al clic (mecanismo actual); queda
     igual. Sin feedback visual del salto: al ser implícito, el "silencio" del servidor
     ante posiciones no mapeables es aceptable y no se inventa un ACK que el protocolo
     no tiene.
3. **Autoguardado a 300 ms (reemplaza el debounce de `updateMemoryFiles`).**
   Cumple en espíritu la Etapa 14 pendiente del roadmap ("el debounce no debe
   re-renderizar sino guardar; después de guardar, re-renderizar") — al implementarse,
   actualizar CLAUDE.md §14.
   - **Flujo:** 300 ms después de la última edición → `PUT .../typ` (el endpoint
     existente) → al confirmar, `original = texto` (el estado `sucio` se vuelve
     transitorio). tinymist detecta el cambio en disco y recompila la preview solo —
     el debounce de `actualizarMemoriaPreview` en `DocEditor.vue:149-159` **se retira**
     (y `/api/preview/memory` queda obsoleto; retirarlo aquí o a más tardar en 1E).
   - **Eventos pertinentes:** ojo, el polling de mtimes de `/api/events` NO detecta
     ediciones de contenido (escanea mtime de *directorios*, que no cambia al modificar
     un archivo existente) — `api_doc_typ_put` debe emitir explícitamente un SSE nuevo
     `doc-saved {slug, codigo}` vía `_emitir_evento_sse()` (patrón ya existente), del
     que se cuelgan StatusBar (indicador y timestamp) y cualquier vista abierta. Con la
     Fase 1B activa, el frontend envía además `textDocument/didSave` al LSP tras cada
     autoguardado.
   - **Robustez:** al subir la frecuencia de escritura, `api_doc_typ_put` pasa a
     escritura atómica (write-temp + rename, mismo criterio que `org.json`). Si el PUT
     falla, el estado queda sucio, se muestra el error en StatusBar y el siguiente ciclo
     de edición reintenta. No se autoguarda mientras `ocupado` (subir versión/compilar
     en vuelo); se reprograma. *Flush* inmediato (sin esperar los 300 ms) al salir de la
     vista, en `beforeunload`, y antes de "Subir versión"/"Compilar" (estos ya guardan
     si `sucio` — se conserva como cinturón).
   - **UI:** el botón "Guardar" de StatusBar se retira o se convierte en indicador
     ("Guardando…" / "Guardado ✓ hh:mm:ss"). "Subir versión" y "Compilar" siguen siendo
     las únicas acciones que crean versiones/snapshots — **el autoguardado jamás bumpea
     versión ni toca `org.json`**.
   - **Alcance:** editor de **documentos** (lo pedido). El editor de plantillas mantiene
     guardado explícito por ahora: autoguardar `lib.typ` afecta a todos los documentos
     futuros de la org y merece su propia decisión — dejar anotado como pregunta al
     usuario cuando se llegue aquí.

### Orden recomendado de ejecución

1. **Fase 2** (una sesión, todo mecánico).
2. **Fase 3** completa (una o dos sesiones): 3.1 (fix H2 + aviso D4), 3.2 (jump
   automático al clic, retiro del botón/atajo) y 3.3 (autoguardado + evento `doc-saved`
   + escritura atómica). Todo esto es independiente del LSP y mejora el editor de
   inmediato.
3. **Fase 1A** (transporte + proceso LSP + puente; incluye el paso 0 de captura de
   capabilities) — sin esto no hay nada que mostrar.
4. **Fase 1B** (núcleo: sync de documentos, diagnósticos, completion, hover, firmas) —
   primer hito visible; validar con §4.5 antes de seguir.
5. **Fase 1C** (navegación/símbolos; D4 ya resuelta: sin pestaña de lib.typ).
6. **Fase 1D** (semantic tokens, inlay hints, colores, code actions/lens, rename,
   formateo, exportación rápida — D5 ya resuelta: se ofrecen todos los exportadores).
7. **Fase 1E** (unificación de la preview) — al final, cuando el LSP ya esté estable;
   su paso 1 de verificación de protocolo puede adelantarse en paralelo a 1C/1D.

Cada sub-fase de la 1 cierra con su bloque de pruebas de §4.5 en verde y con la
checklist de capabilities (paso 0) actualizada (implementado / mapeado / descartado
con motivo).

---

## 3. Snippets de referencia

> Adaptados a la pila real (Python stdlib + Vue/CodeMirror 6). Son referencia de diseño:
> verificar APIs contra el código vigente al implementar, no pegar a ciegas.

### 3.1 Backend — cablear `compileStatus` (Fase 2.1, `doctyp_web.py`)

```python
# En _asegurar_preview_generico(), junto al on_editor_scroll_to existente:
nuevo.on_compile_status = lambda kind: _emitir_evento_sse(
    {"tipo": "compile-status", "recurso_tipo": tipo, "slug": slug,
     "nombre": nombre, "kind": kind}
)
```

### 3.2 Backend — etiqueta `es_editable` en editorScrollTo (Fase 3.1)

```python
# _asegurar_preview_generico() ya conoce main_typ y tipo. El archivo "editable" difiere:
# doc → el .typ principal; plantilla → lib.typ (la muestra materializada NO es editable).
if tipo == "plantilla":
    archivo_editable = core.plantilla_dir(slug, nombre) / "lib.typ"
else:
    archivo_editable = main_typ

def _bridge_scroll_to(datos, _editable=archivo_editable.resolve()):
    try:
        es_editable = Path(datos.get("filepath", "")).resolve() == _editable
    except OSError:
        es_editable = False
    _emitir_evento_sse({"tipo": "editor-scroll-to", "recurso_tipo": tipo,
                        "slug": slug, "nombre": nombre,
                        "es_editable": es_editable, **datos})

nuevo.on_editor_scroll_to = _bridge_scroll_to
```

```js
// CodeEditor.vue — en el watch(ultimoEditorScrollTo, ...), tras el filtro por recurso:
if (evento.es_editable !== true) return; // clic resolvió a lib.typ u otro archivo
```

### 3.3 Frontend — notificaciones LSP desde CodeMirror (Fase 1, referencia)

```ts
// Transporte WS mínimo compatible con la forma de Transport de @codemirror/lsp-client
// (verificar la firma exacta contra los .d.ts instalados antes de usar — ver D3).
function crearTransporteLSP(url: string) {
  const ws = new WebSocket(url);
  const handlers = new Set<(msg: string) => void>();
  ws.onmessage = (ev) => handlers.forEach((h) => h(ev.data));
  return {
    send(message: string) { ws.send(message); },       // JSON-RPC crudo, string
    subscribe(handler: (value: string) => void) { handlers.add(handler); },
    unsubscribe(handler: (value: string) => void) { handlers.delete(handler); },
  };
}

// Ciclo de vida del documento (si se opta por el puente manual en vez de lsp-client):
// didOpen al montar, didChange incremental desde el updateListener YA existente en
// CodeEditor.vue (no crear un segundo listener), didSave en guardarCambios(),
// didClose en onUnmounted.
const uri = `file://${rutaAbsolutaDelTyp}`; // el backend la expone en /api/preview/info
let version = 1;
enviar("textDocument/didOpen", {
  textDocument: { uri, languageId: "typst", version, text: textoInicial },
});
// dentro de EditorView.updateListener.of(update => { ... }):
if (update.docChanged) {
  const cambios: object[] = [];
  update.changes.iterChanges((fromA, toA, _fromB, _toB, inserted) => {
    const d0 = update.startState.doc;
    cambios.push({
      range: { start: posALineaCol(d0, fromA), end: posALineaCol(d0, toA) },
      text: inserted.toString(),
    });
  });
  enviar("textDocument/didChange", {
    textDocument: { uri, version: ++version }, contentChanges: cambios,
  });
}
```

### 3.4 Backend — framing JSON-RPC sobre stdio de `tinymist lsp` (Fase 1, referencia)

```python
def _leer_mensaje_lsp(stdout) -> bytes | None:
    """Framing LSP: cabeceras 'Content-Length: N' + \r\n\r\n + N bytes de JSON."""
    largo = None
    while True:
        linea = stdout.readline()
        if not linea:
            return None                      # el proceso cerró stdout
        if linea in (b"\r\n", b"\n"):
            break                            # fin de cabeceras
        nombre, _, valor = linea.partition(b":")
        if nombre.strip().lower() == b"content-length":
            largo = int(valor.strip())
    if largo is None:
        return None
    return stdout.read(largo)                # bytes exactos; NO usar readline aquí

def _enviar_mensaje_lsp(stdin, payload: bytes) -> None:
    stdin.write(b"Content-Length: %d\r\n\r\n%s" % (len(payload), payload))
    stdin.flush()                            # sin flush hay buffering => latencia
```

*(Nota de rendimiento pedida por la auditoría: el único buffering peligroso en todo el
diseño es olvidar `flush()` en stdin del LSP y no usar `bufsize` binario en el `Popen` —
el `Popen` del LSP debe ser binario (`text=False`), a diferencia del de preview.)*

### 3.5 Paso 0 de la Fase 1 — capturar las capabilities reales (referencia)

```python
# Script de trabajo (scratchpad, no del repo): arranca `tinymist lsp`, hace initialize y
# vuelca ServerCapabilities a JSON. La checklist "100%" de la Fase 1 se genera de AQUÍ,
# no de la memoria ni de la documentación.
import json, subprocess
from pathlib import Path

proc = subprocess.Popen(["tinymist", "lsp"], stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE, bufsize=0)  # binario, sin buffering
root = Path("~/Documentos/doctyp/slep-chinchorro/TI-INF-RED_2026-0039").expanduser()
peticion = json.dumps({
    "jsonrpc": "2.0", "id": 1, "method": "initialize",
    "params": {
        "processId": None,
        "rootUri": root.as_uri(),
        "workspaceFolders": [{"uri": root.as_uri(), "name": root.name}],
        # capabilities de cliente "maximalistas": declarar soporte de todo lo que el
        # frontend planea implementar (semanticTokens, inlayHint, foldingRange, …) para
        # que el servidor anuncie el máximo — un cliente tímido recibe menos capabilities.
        "capabilities": {"textDocument": {}, "workspace": {}},
        "initializationOptions": {},
    },
}).encode()
proc.stdin.write(b"Content-Length: %d\r\n\r\n%s" % (len(peticion), peticion))
respuesta = _leer_mensaje_lsp(proc.stdout)  # framing de §3.4
print(json.dumps(json.loads(respuesta)["result"]["capabilities"], indent=2))
# Guardar la salida como lsp-capabilities-<version>.json junto al plan y derivar la
# checklist. Repetir si se actualiza tinymist. Incluir también experimental/* y la lista
# de executeCommandProvider.commands (de ahí sale la allowlist del puente).
```

### 3.6 Frontend — diagnósticos LSP → CodeMirror (Fase 1B, referencia)

```ts
// Si @codemirror/lsp-client ya trae esto, usar lo suyo; este es el fallback manual.
import { setDiagnostics } from "@codemirror/lint";

const SEVERIDAD = ["error", "error", "warning", "info", "hint"] as const; // LSP 1-4

function alRecibirPublishDiagnostics(view: EditorView, params: any, uriPropio: string) {
  if (params.uri !== uriPropio) return;           // diagnósticos de lib.typ → otra pestaña
  const doc = view.state.doc;
  const diagnosticos = params.diagnostics.map((d: any) => {
    const desde = doc.line(d.range.start.line + 1).from + d.range.start.character;
    const hasta = doc.line(d.range.end.line + 1).from + d.range.end.character;
    return {
      from: Math.min(desde, doc.length),
      to: Math.min(Math.max(hasta, desde), doc.length),
      severity: SEVERIDAD[d.severity ?? 1],
      message: d.message,
      source: d.source ?? "tinymist",
    };
  });
  view.dispatch(setDiagnostics(view.state, diagnosticos));
  // Además: emitir el conteo {errores, avisos} hacia StatusBar (bus, mismo patrón que
  // editorScrollToBus.js).
}
```

### 3.7 Frontend — jump automático al clic + autoguardado (Fase 3.2/3.3, referencia)

```js
// CodeEditor.vue — extensión nueva en el array de extensions del EditorView.
// Dispara SOLO en clic de posicionamiento: selección vacía descarta arrastres de
// selección y doble-clic (que seleccionan texto). Teclado y scroll no pasan por aquí.
EditorView.domEventHandlers({
  click(_ev, view) {
    const sel = view.state.selection.main;
    if (!sel.empty) return false;
    const linea = view.state.doc.lineAt(sel.head);
    emit("clic-en-editor", { line: linea.number - 1, character: sel.head - linea.from });
    return false; // no consumir el evento: el posicionamiento normal sigue su curso
  },
}),
// DocEditor.vue escucha @clic-en-editor y llama saltarAPosicionPreview(...) directamente
// (el actual saltarEnPreview() sin el atajo ni el botón). getPosicionCursor() puede
// retirarse si nadie más lo usa.
```

```js
// DocEditor.vue — el watch(texto) actual (DocEditor.vue:149-159) cambia de acción:
// ya no envía updateMemoryFiles; guarda a disco. Mismo debounce de 300 ms.
let temporizadorGuardado = null;
watch(texto, () => {
  if (!props.codigo) return;
  if (temporizadorGuardado) clearTimeout(temporizadorGuardado);
  temporizadorGuardado = setTimeout(autoguardar, 300);
});

async function autoguardar() {
  if (!sucio.value || ocupado.value) return;      // ocupado: se reintenta en la próxima edición
  const contenido = texto.value;                   // capturar ANTES del await
  try {
    await putTyp(props.slug, props.codigo, contenido);
    if (texto.value === contenido) original.value = contenido; // no marcar limpio si ya tipeó más
    // (con Fase 1B) → enviar textDocument/didSave al LSP aquí.
  } catch (e) {
    mensaje.value = `Autoguardado falló: ${e.message}`;   // queda sucio; próximo ciclo reintenta
    mensajeEsError.value = true;
  }
}
// Flush sin debounce: beforeunload, al salir de la vista, y al inicio de
// subirVersion()/compilarDoc() (que ya guardan si sucio — se conserva).
```

---

## 4. Pruebas y validación manual

Prerrequisitos: `tinymist` ≥ 0.15.2 en PATH, `doctyp web` levantado, un documento real
(p. ej. `TI-INF-RED_2026-0039`). Cerrar siempre con **Ctrl+C** (regla vigente: `kill -9`
saltea la limpieza).

### 4.1 Click-to-jump (preview → editor) — Fases 2/3

1. Abrir el documento; esperar el iframe de la preview.
2. Clic sobre un párrafo de **prosa del cuerpo** → el cursor de CodeMirror debe quedar en
   la línea/columna correspondiente del `.typ`, con scroll y foco. Repetir el mismo clic
   dos veces seguidas: debe reaccionar ambas (el bus fuerza referencia nueva por `_ts`).
3. **Regresión H2:** clic sobre la **portada** o la ficha (contenido generado por
   `lib.typ`) → el cursor **no debe moverse** (antes del fix saltaba a una línea sin
   relación). En el editor de plantillas, el caso espejo: clic en prosa de la muestra no
   mueve nada; clic en elementos definidos en `lib.typ` sí.
4. Latencia percibida: el salto debe sentirse inmediato (<200 ms). Si no, revisar que el
   evento salga por `_emitir_evento_sse` (push) y no por el tick de polling de 1.5 s.

### 4.2 Jump automático editor → preview (Fase 3.2)

1. **Clic** sobre un heading o párrafo del cuerpo en el editor → la preview scrollea a
   esa posición **inmediatamente, sin botón ni atajo** (el botón "Ver posición del
   cursor" y Ctrl+Alt+J ya no existen — verificar que se retiraron de la UI).
2. Clic sobre una línea no mapeable (línea en blanco, exactamente el `=` de un
   heading) → sin salto y **sin error** en consola (comportamiento esperado del servidor).
3. **Solo el clic dispara:** mover el cursor con flechas, tipear, o scrollear el editor
   **no** produce ningún salto. Seleccionar texto arrastrando o con doble-clic tampoco
   (la selección no vacía descarta el disparo).
4. Bidireccionalidad en la misma sesión: clic en el render → cursor salta al editor;
   clic en el editor → render salta. Ambos implícitos, sin acción intermedia.

### 4.3 Autoguardado y compileStatus (Fases 3.3 y 2.1)

1. Tipear un cambio visible y dejar de tipear → a los ~300 ms el `.typ` en disco
   contiene el cambio (verificar con `cat`/mtime), el StatusBar pasa por "Guardando…" →
   "Guardado ✓", y la preview lo refleja tras recompilar (tinymist detecta el archivo).
2. El autoguardado **no** crea versiones: `doctyp history <ref>` y `org.json` quedan
   idénticos tras muchas ediciones; solo "Subir versión"/"Compilar" agregan filas.
3. Evento SSE: con una segunda pestaña del navegador abierta en la app, el autoguardado
   de la primera dispara `doc-saved` visible en la segunda (el polling de mtimes por sí
   solo no lo detectaría — es el criterio de que el evento explícito funciona).
4. Fallo de guardado: detener `doctyp web` momentáneamente (o simular un 500) mientras
   se tipea → StatusBar muestra el error y el documento queda marcado sucio; al volver
   el backend y seguir tipeando, el siguiente ciclo guarda y limpia el estado.
5. Interacción con acciones: iniciar "Subir versión" con tipeo reciente → no hay carrera
   (el flush previo guarda y el autoguardado no corre mientras `ocupado`).
6. `compileStatus` (Fase 2.1): introducir `#let x = (` → StatusBar en estado de error
   (evento `compile-status`); corregirlo → vuelve a OK. Antes del fix H1 esto no llegaba
   a la UI propia: es el criterio de aceptación.

### 4.4 Gestión de procesos

1. `pgrep -a tinymist` con la preview abierta → exactamente 1 proceso.
2. Cambiar a otro documento → sigue habiendo exactamente 1 (el anterior se detuvo).
3. Recargar la pestaña del navegador → el proceso **sobrevive** (control plane en backend).
4. `kill <pid-de-tinymist>` a mano → el backend lo reintenta (warn en consola, backoff
   0.5/1/2 s) y la preview vuelve sola; matarlo 4 veces seguidas → deja de reintentar con
   aviso claro.
5. Ctrl+C a `doctyp web` → `pgrep tinymist` vacío. (Con la Fase 2.4: también tras
   `kill -9` + re-arranque de `doctyp web`.)

### 4.5 LSP — Fase 1A/1B (núcleo; validar antes de seguir a 1C)

1. **Paso 0 hecho:** existe `lsp-capabilities-<version>.json` capturado del binario real
   y la checklist derivada de él — sin esto la fase no arranca.
2. **Ciclo de documentos:** abrir un documento → log del puente muestra `didOpen`;
   tipear → `didChange` incrementales con `version` creciente; cada autoguardado
   (Fase 3.3) → `didSave`; volver a la grilla → `didClose`; reabrir → `didOpen` con
   estado limpio.
3. **Reconexión:** F5 en el navegador con el editor abierto → el proceso `tinymist lsp`
   **no** se reinicia (mismo PID), el frontend reabre con `didOpen` y todo lo demás
   sigue funcionando. Ctrl+C a `doctyp web` → `pgrep tinymist` vacío (ambos procesos,
   LSP y preview, hasta que 1E los unifique).
4. **Diagnósticos:** `#let x = (` → subrayado + gutter + contador en StatusBar en <1 s
   tras dejar de tipear; corregir → desaparece. Diagnósticos cuyo `uri` sea `lib.typ`
   (u otro archivo) **no** se pintan en el editor del documento (D4: lib.typ no se
   visualiza ahí); en el editor de plantillas, los de `lib.typ` sí.
5. **Completion:** tipear `#tab` → `tabla`, `tabla-kv`, `tabla-prioridad` (símbolos del
   `lib.typ` local = prueba de root correcto); `#aviso(t` → parámetros con snippet;
   latencia objetivo <150 ms en localhost.
6. **Hover:** sobre `#tabla(` → firma/documentación; sobre una variable propia → su
   definición.
7. **Signature help:** dentro de `#tabla(columns: …, |)` al tipear `,` → tooltip con el
   parámetro activo resaltado.
8. **Degradación:** `doctyp web --no-lsp` (o sin binario) → el editor funciona como hoy
   (resaltado StreamLanguage, sin diagnósticos), sin errores en consola, y
   guardar/versionar/compilar intactos.

### 4.6 LSP — Fase 1C (navegación)

1. **Definición, mismo archivo:** Ctrl+clic (o atajo) sobre una variable definida en el
   propio `.typ` → cursor salta a la definición.
2. **Definición, otro archivo (D4):** Ctrl+clic sobre `tabla` en el editor de
   **documentos** → **no** se abre nada; aparece el aviso "Definido en la plantilla
   (lib.typ) — edítala desde el editor de plantillas" y el cursor no se mueve. En el
   editor de **plantillas**, el mismo salto dentro de `lib.typ` sí funciona.
3. **Referencias:** sobre la definición de una función de `lib.typ` → lista con todos
   los usos en el documento; clic en cada una salta correctamente.
4. **Outline:** el panel muestra la jerarquía de headings (§8: Resumen ejecutivo,
   Antecedentes, …) y clic en una entrada mueve el cursor.
5. **Folding:** los headings y bloques largos muestran control de plegado y plegar no
   corrompe la edición posterior.
6. **workspace/symbol:** Ctrl+T + "prioridad" → encuentra `tabla-prioridad` en lib.typ.

### 4.7 LSP — Fase 1D (presentación y refactor)

1. **Semantic tokens:** abrir `lib.typ` → los colores mejoran respecto al StreamLanguage
   (p. ej. parámetros vs variables distinguidos); tipear rápido no produce parpadeo
   (los tokens llegan async y pisan encima sin borrar el color base).
2. **Inlay hints:** en `#tabla(2, "a", "b")` aparecen los nombres de parámetro; el
   toggle de StatusBar los oculta/muestra.
3. **Colores:** los literales de la paleta de `lib.typ` (`marino`, `rgb("…")`) muestran
   swatch; cambiar un color con el picker edita el texto correctamente. (Regla vigente:
   *Claude* no toca la paleta — el picker es para el usuario.)
4. **Rename:** renombrar una variable local → todas las ocurrencias del archivo cambian;
   un rename que tocaría un archivo no abierto → aviso, sin escritura silenciosa a disco.
5. **Formatear:** botón/Ctrl+Shift+F sobre un bloque desalineado → typstyle lo formatea;
   deshacer (Ctrl+Z) lo revierte en un solo paso.
6. **Code actions/lens:** sobre un heading → acciones de nivel disponibles; ningún lens
   dispara comandos fuera de la allowlist (verificar en el log del puente).
7. **Seguridad del puente:** enviar a mano por el WS un `workspace/executeCommand` con
   un comando fuera de la allowlist → el puente lo rechaza y queda registrado.

### 4.8 LSP — Fase 1E (preview unificada)

1. Re-correr **completa** la batería §4.2-4.4 sobre el modo unificado (clic→cursor,
   salto explícito, memoria en vivo vía `didChange`, compileStatus).
2. `pgrep -a tinymist` → exactamente **un** proceso sirviendo LSP **y** preview.
3. Cambiar de documento → la preview cambia **sin** reinicio de proceso (mismo PID) y
   en menos tiempo que el modo standalone (~1-3 s hoy).
4. Editar sin guardar → la preview refleja el cambio vía `didChange` (ya no existe
   `POST /api/preview/memory` efectivo) y el `.typ` en disco no cambia.
