# Informe técnico — Etapa 12.2/12.3: por qué click-to-jump (clic↔cursor) no es implementable con el paquete actual

> Alcance de este documento: explica en detalle **por qué** la sincronización clic→cursor
> (clic en la vista previa mueve el cursor del editor) y cursor→clic (mover el cursor resalta
> la posición en la vista previa) están bloqueadas con `@myriaddreamin/typst.ts` en su versión
> actual, qué se probó exactamente, con qué resultado, y qué alternativas quedan abiertas.
> Es un documento de investigación para decidir el siguiente paso — no describe una
> funcionalidad implementada. El estado operativo de la Etapa 12 vive en `CLAUDE.md` §14.

---

## 1. Resumen ejecutivo

- **Clic→cursor** (clic en el documento renderizado → mueve el cursor del editor a esa línea)
  requiere que el renderer marque cada elemento visual con su ubicación de origen en el código
  fuente (`archivo:línea:columna`). El mecanismo que existe para esto en Typst.ts es el
  atributo `data-span` sobre los nodos SVG.
- **Se confirmó, leyendo el código fuente en Rust de Typst.ts (no solo el wrapper JS), que
  `data-span` está deshabilitado de forma permanente en el binario que se publica a npm.** No
  es una opción de configuración ausente: es una constante de compilación (`SHOULD_ATTACH_DEBUG_INFO`)
  fijada a `false` en las cuatro rutas de exportación existentes en el repositorio. Ninguna
  combinación de API JavaScript puede activarla contra el paquete publicado.
- **Cursor→clic** (mover el cursor del editor → resalta/hace scroll a esa posición en la vista
  previa) no depende de `data-span`, pero tampoco existe una función inversa nativa
  ("línea de código → posición en el documento renderizado") en la API pública del compilador.
  Sigue siendo alcanzable por una vía indirecta (ver §6), pero no se implementó todavía.
- Conclusión: **no es un problema de nuestro código ni de cómo lo usamos** — es una limitación
  real y verificada del paquete de terceros en su versión publicada actual (`0.7.0`, y también
  se confirmó en el candidato a release más reciente, `0.8.0-rc3`).

---

## 2. Qué es `data-span` y por qué es la pieza que falta

Typst.ts compila un documento a un **artefacto vectorial** (formato `"vector"`) y luego lo
renderiza. Al renderizar a SVG, cada elemento visual (texto, forma, imagen) puede llevar un
atributo `data-span` con un identificador hexadecimal que codifica su ubicación en el código
fuente `.typ` original. Con ese atributo:

- Un clic sobre un elemento → se lee su `data-span` → se resuelve con
  `RenderSession.getSourceLoc(path)` → se obtiene la ubicación fuente exacta.
- Sin ese atributo, un clic sobre el SVG solo entrega coordenadas de píxel — no hay forma de
  saber a qué línea del `.typ` corresponden esas coordenadas.

Encontramos evidencia de que este mecanismo existe porque el propio `.wasm` del renderer trae
embebido, como recurso interno, un script de JavaScript de referencia
(identificado en el código minificado por la función `typstProcessSvg`) que ya sabe leer
`data-span` y resolver el salto — es decir, la demo oficial de Typst.ts sí usa esta
funcionalidad en algún contexto. El problema es reproducir las condiciones bajo las que ese
atributo se genera.

---

## 3. Pruebas realizadas y resultado de cada una

Todas las pruebas se hicieron contra una instancia real de `doctyp web` (Chromium vía
Playwright, instalado temporalmente y no incluido en el repositorio), inspeccionando el DOM
resultante en vivo — no son conjeturas de lectura de código.

### 3.1 — Render por defecto (`renderSvg`/`renderToSvg`, compilación simple)

```js
const { result } = await compiler.compile({ mainFilePath: "/main.typ", format: "vector" });
const svgTexto = await renderer.renderSvg({ artifactContent: result });
```

**Resultado:** el SVG se genera correctamente (documento completo, paginado, con estilos), pero
al inspeccionar los atributos `data-*` de cada elemento solo aparecen:
- `data-tid` — hash de identidad usado para reconciliar parches incrementales (diffing), **no**
  es información de posición.
- `data-hint` — usado para selección/copia de texto.

`data-span` **no aparece en ningún elemento**.

### 3.2 — `renderToSvg` (variante que escribe directo al DOM desde Rust)

```js
await renderer.renderToSvg({ container: contenedor, artifactContent });
```

**Resultado:** además de no producir `data-span`, esta variante **panickea de forma
reproducible**:

```
panicked at packages/renderer/src/render/svg.rs:132:18:
called `Option::unwrap()` on a `None` value
```

Tras el panic, la sesión WASM queda corrupta: cualquier intento posterior de usarla falla con
`attempted to take ownership of Rust value while it was borrowed`. Por esta razón la Etapa 12.1
usa `renderSvg` (que retorna un string y no toca el DOM desde Rust) en vez de `renderToSvg`.

### 3.3 — Compilación incremental con `setAttachDebugInfo(true)`

Es el único método relacionado con "debug info" que expone el wrapper JS
(`IncrementalServer.setAttachDebugInfo`), así que era el candidato más obvio:

```js
await compiler.withIncrementalServer(async (srv) => {
  srv.setAttachDebugInfo(true);
  return compiler.compile({
    mainFilePath: "/main.typ",
    incrementalServer: srv,
    diagnostics: "unix",
  });
});
```

**Resultado:** el artefacto se genera sin errores, pero el SVG resultante sigue mostrando
únicamente `data-tid` y `data-hint`. `setAttachDebugInfo(true)` no tiene efecto observable en
la salida.

### 3.4 — Modo DOM (`renderDom`/`mount_dom`), intento 1: uso directo

```js
const doc = await renderer.renderDom({ container: div, artifactContent });
```

**Resultado:** el documento nunca llega a pintarse. En la consola aparece
`"viewport-change before initialization"` de forma indefinida — el módulo interno se queda en
estado `moduleInitialized = false` para siempre. Investigando el código fuente del wrapper
(`contrib/dom/typst-doc.mjs`) se determinó que el modo DOM espera un **protocolo de
actualización incremental explícito**: hay que empujar el artefacto con
`doc.addChangement(['new', artefacto])` y disparar `doc.addViewportChange()` — pasar
`artifactContent` en las opciones de `renderDom` no basta por sí solo.

### 3.5 — Modo DOM, intento 2: protocolo completo, pero fuera de la sesión válida

```js
const doc = await renderer.renderDom({ container: div, artifactContent });
doc.addChangement(["new", artifactContent]);
doc.addViewportChange();
```

**Resultado:** falla con `Error: Attempt to use a moved value`. Causa: `renderDom({artifactContent})`
crea internamente una sesión efímera (`withinOptionSession` → `runWithSession`) que se **libera
automáticamente** (`session.free()`) apenas la función `renderDom` retorna — cualquier llamada
posterior sobre el objeto devuelto opera sobre una sesión ya destruida.

### 3.6 — Modo DOM, intento 3: protocolo completo dentro de la sesión

Se movió toda la lógica (montaje, push del artefacto, cambio de viewport, inspección) **dentro
del callback** de `runWithSession`, para operar mientras la sesión sigue viva:

```js
await renderer.runWithSession({ format: "vector", artifactContent }, async (session) => {
  const doc = await renderer.renderDom({ renderSession: session, container: div });
  doc.addChangement(["new", artifactContent]);
  await esperar(300);
  doc.addViewportChange();
  await esperar(2000);
  // inspección de atributos data-* aquí
});
```

**Resultado:** panic fatal de Rust, distinto al de §3.2:

```
panicked at crates/conversion/vec2dom/src/dom.rs:91:18:
called `Result::unwrap()` on an `Err` value: JsValue(undefined)
[pageerror] unreachable
```

Un trap `unreachable` en WebAssembly es un error fatal del módulo — no hay forma de recuperarse
sin recargar el WASM desde cero. Confirma que el modo DOM, en las condiciones que logramos
reproducir, no es utilizable de forma segura para nuestro caso (compilación puntual, no un
servidor sirviendo diffs incrementales en vivo, que es el escenario para el que este modo fue
diseñado).

### 3.7 — Repetición de 3.1, 3.3 y 3.6 contra la versión más reciente publicada (`0.8.0-rc3`)

Antes de descartar la vía de "quizás sea un bug ya corregido en una versión más nueva", se
instaló temporalmente (`npm install --no-save`, sin modificar `package.json`) la última
versión disponible en el registro de npm en el momento de la investigación:

```
@myriaddreamin/typst-ts-renderer@0.8.0-rc3
@myriaddreamin/typst-ts-web-compiler@0.8.0-rc3
@myriaddreamin/typst.ts@0.8.0-rc3
```

**Resultado:** exactamente los mismos síntomas que en `0.7.0` — `data-span` ausente en el
render simple, y el mismo panic `unreachable` en el modo DOM. Se restauró la versión estable
`0.7.0` (la que sí funciona de forma confiable para renderizado sin click-to-jump) al terminar
la prueba.

---

## 4. Causa raíz (confirmada leyendo el código fuente en Rust)

Dado que ninguna combinación de API JS activaba `data-span`, se clonó superficialmente el
repositorio fuente (`github.com/Myriad-Dreamin/typst.ts`, clon temporal `--depth 1`, revisado
y eliminado al terminar — no forma parte de este repositorio) para inspeccionar directamente
dónde y bajo qué condición se escribe ese atributo.

**Hallazgo:**

```rust
// crates/conversion/vec2svg/src/backend/mod.rs
fn attach_debug_info(&mut self, ctx: &mut C, span_id: u64) {
    if ctx.should_attach_debug_info() {
        self.attributes.push(("data-span", format!("{span_id:x}")));
    }
}
```

`should_attach_debug_info()` depende de una constante asociada al tipo `ExportFeature`:

```rust
// crates/conversion/vec2svg/src/frontend/context.rs
fn should_attach_debug_info(&self) -> bool {
    Feat::SHOULD_ATTACH_DEBUG_INFO && self.should_attach_debug_info
}
```

Y `SHOULD_ATTACH_DEBUG_INFO` está definida, **hardcodeada a `false`**, en las cuatro
implementaciones de `ExportFeature` que existen actualmente en el repositorio:

| Archivo | Implementación | Valor |
|---|---|---|
| `crates/conversion/vec2svg/src/lib.rs` | `DefaultExportFeature` | `false` |
| `crates/conversion/vec2svg/src/lib.rs` | `SvgExportFeature` | `false` |
| `crates/conversion/vec2svg/src/frontend/incremental.rs` | `IncrementalExportFeature` | `false` |
| `crates/conversion/vec2dom/src/svg_backend.rs` | `IncrementalSvgExportFeature` (modo DOM) | `false` |

**No existe ninguna implementación en el repositorio con este valor en `true`.** Esto explica
por qué:

- `setAttachDebugInfo(true)` (§3.3) no tuvo efecto: ese método solo controla el segundo término
  del `&&` (`self.should_attach_debug_info`, un flag de instancia); el primer término
  (`Feat::SHOULD_ATTACH_DEBUG_INFO`, la constante de tipo) sigue siendo `false` sin importar el
  flag de instancia, y `false && x` es siempre `false`.
- Ni el backend SVG ni el backend DOM pueden producir `data-span`: ambos tienen la constante en
  `false`.
- El script `typstProcessSvg` embebido en el `.wasm` (que sí sabe leer `data-span`) es, con esta
  evidencia, código correspondiente a una build distinta a la que efectivamente se publica en
  los paquetes de npm consumidos por este proyecto — probablemente construida con un
  `ExportFeature` propio (quizás específico del servicio typst.app/la demo oficial) que no
  forma parte del código open-source publicado, o que requiere compilar el WASM manualmente
  con esa constante cambiada.

**Esto es una limitación de diseño/build del paquete, no un bug que dependa de la versión ni
de cómo se invoca la API desde JavaScript.**

---

## 5. Por qué esto también bloquea cursor→clic (la dirección inversa)

Aunque cursor→clic no depende directamente de `data-span`, la vía más natural para
implementarla (usar la misma información de mapeo posición↔fuente, en la dirección contraria)
queda cerrada por la misma causa: si el renderer no anota qué elemento visual corresponde a qué
span de código, tampoco hay manera de, dada una línea de código, encontrar su elemento visual
correspondiente para hacerle scroll/resaltado — la relación es simétrica y depende del mismo
mecanismo deshabilitado.

---

## 6. Alternativas para desbloquear (ninguna implementada todavía)

### 6.1 — Compilar el WASM desde un fork propio (mayor esfuerzo, control total)

Clonar `Myriad-Dreamin/typst.ts`, cambiar `SHOULD_ATTACH_DEBUG_INFO` a `true` en
`vec2svg/src/lib.rs` (`SvgExportFeature`, que es la que usa `renderSvg`/`renderToSvg`), y
compilar el `.wasm` localmente con `wasm-pack` (requiere toolchain de Rust + wasm-pack, no
disponible en este entorno de desarrollo). Ventaja: resuelve el problema en su origen exacto,
sin rodeos. Desventaja: mantener un fork y su pipeline de build a largo plazo; el `.wasm` del
compilador ya pesa ~28 MB sin cambios, y no se puede predecir el impacto de tamaño/rendimiento
de esta rama de código sin probarlo.

### 6.2 — Reportar/pedir el flag upstream

Abrir un issue en `Myriad-Dreamin/typst.ts` pidiendo exponer `SHOULD_ATTACH_DEBUG_INFO` (o un
`ExportFeature` alternativo con `data-span` activado) como build publicado en npm, o al menos
como opción de runtime en vez de constante de compilación. Ventaja: si se acepta, beneficia a
cualquier consumidor del paquete y no requiere mantenimiento propio. Desventaja: depende de
terceros, sin garantía de tiempos ni de que se acepte.

### 6.3 — Metadata por párrafo + `query()` (viable sin tocar el paquete, mecanismo ya confirmado)

Ya validado que `compiler.query({selector})` existe y está expuesto en el wrapper JS (mismo
mecanismo que `typst query` por CLI). Esta vía no depende de `data-span` en absoluto:

1. Antes de compilar (solo en la copia en memoria usada para la vista previa del navegador,
   **nunca en el `.typ` real del usuario ni en lo que se guarda**), insertar un marcador
   invisible (`#metadata(..) <marca-N>` o similar) delante de cada párrafo/bloque relevante del
   documento.
2. Tras compilar, usar `query()` para pedir la posición (`page`, `x`, `y`) de cada marca —
   Typst expone esto de forma nativa vía `locate()`/`here().position()`, que es exactamente lo
   que `query()` resuelve por CLI.
3. Con esa tabla marca→posición, se puede resolver **cursor→clic** con precisión exacta por
   párrafo (ya estaba planeado para la Etapa 12.3, sin relación con el bloqueo de `data-span`).
4. Para **clic→cursor**, la misma técnica podría invertirse de forma aproximada: dado un clic
   en coordenadas `(page, x, y)`, encontrar la marca más cercana en esa página y saltar a su
   línea — es una aproximación por párrafo/bloque, no una resolución exacta por carácter como
   sería posible con `data-span`, pero no depende de ninguna funcionalidad deshabilitada del
   paquete.

Esta es la vía más realista a corto plazo, aunque entrega precisión de párrafo en vez de
precisión de carácter para la dirección clic→cursor.

---

## 7. Qué no se investigó todavía

- No se probó overridear el `.wasm` con un build casero (requiere Rust + wasm-pack en el
  entorno, no configurado en este proyecto).
- No se revisó si existe algún paquete/fork de terceros en npm que sí publique el WASM con
  `data-span` activado.
- No se exploró a fondo `getSemanticTokens()`/`getAst()` del compilador (información de
  posición del *código fuente*, no del render) como insumo para una heurística distinta —
  se descartaron por inspección rápida al no aportar la correlación con el render, pero no se
  probaron exhaustivamente.

---

## 8. Referencias de código consultadas

- `node_modules/@myriaddreamin/typst.ts/dist/esm/{compiler,renderer,dom}.d.mts` — superficie
  pública documentada del wrapper.
- `node_modules/@myriaddreamin/typst.ts/dist/esm/{compiler,renderer}.mjs` — implementación real
  del wrapper (no solo tipos).
- `node_modules/@myriaddreamin/typst.ts/dist/esm/contrib/dom/typst-doc.mjs` — lógica del modo
  DOM (`TypstDocumentContext`, protocolo `addChangement`/`addViewportChange`).
- `strings` sobre `node_modules/@myriaddreamin/typst-ts-renderer/pkg/typst_ts_renderer_bg.wasm`
  — extracción del script `typstProcessSvg` embebido y confirmación de los atributos
  (`data-span`, `data-tid`, `data-hint`) presentes en el binario.
- Clon temporal de `github.com/Myriad-Dreamin/typst.ts` (`--depth 1`, eliminado tras la
  investigación) — `crates/conversion/vec2svg/src/backend/mod.rs`,
  `crates/conversion/vec2svg/src/frontend/context.rs`, `crates/conversion/vec2svg/src/lib.rs`,
  `crates/conversion/vec2svg/src/frontend/incremental.rs`,
  `crates/conversion/vec2dom/src/svg_backend.rs`, `packages/compiler/src/incr.rs`.

Todas las pruebas de comportamiento en vivo (§3) se ejecutaron contra `doctyp web` real
(Chromium vía Playwright, instalado temporalmente y no incluido en el repositorio) — no son
conjeturas basadas solo en lectura de código.
