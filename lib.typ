// ============================================================
// lib.typ — Plantilla Institucional SLEP Chinchorro · Unidad TI
// Reproduce TI-MAN-GOB_2026-0020 v2.0 (Manual de Normas Gráficas SLEP 2026).
//
// Toda la PRESENTACIÓN vive en este archivo. Un informe solo aporta `meta` + prosa.
//
// ── ESQUELETO DE USO (copiar en tu informe.typ) ─────────────────────────────
//   #import "lib.typ": *
//
//   #let meta = crear-meta((
//     area: "TI", tipo: "INF", categoria: "SEG",
//     correlativo: 23, version: "1.0", fecha-codigo: "20260601",
//     titulo: "Título del informe", subtitulo: "Subtítulo · SLEP Chinchorro",
//     estado: "BORRADOR", clasificacion: "INTERNO",
//     autor: "Nombre Apellido", cargo-autor: "Cargo", correo-autor: "x@epchinchorro.cl",
//   ))
//   #show: report.with(meta: meta)            // portada + estilos (contraportada al final)
//
//   #s-ficha(meta, rama-git: "doc/...")       // 1. Ficha de control
//   #s-versiones((                            // 2. Control de versiones
//     ("v1.0", "2026-06-01", "Autor", "Versión inicial."),
//   ))
//   #s-distribucion((                         // 3. Distribución
//     ("Equipo TI", "Operación documental", "Receptor principal"),
//   ))
//   #s-indice()                               // 4. Tabla de contenido
//
//   = Resumen ejecutivo
//   ...prosa...
//   = Antecedentes y motivación
//   == Contexto institucional
//   ...
//   = Recomendaciones
//   #tabla-prioridad((
//     ("1", "Acción recomendada.", "Alta", "Responsable"),
//   ))
//   = Anexos
//   == Anexo B. Firmas
//   #firmas-estandar(meta)
// ─────────────────────────────────────────────────────────────────────────────
// ============================================================

// ------------------------------------------------------------
// 1. PALETA INSTITUCIONAL
// ------------------------------------------------------------
#let marino       = rgb("283A77")   // azul institucional (portada, títulos, tablas)
#let azul-bandera = rgb("0A4FB0")   // azul vivo de la franja-bandera
#let azul-acento  = rgb("2F6BC0")   // enlaces / valores destacados
#let rojo-acento  = rgb("E2231A")   // detalle bandera / badge de página
#let verde        = rgb("3FA34D")   // estado APROBADO / recomendación
#let gris-texto   = rgb("6B7280")   // texto secundario
#let gris-borde   = rgb("D7DAE2")   // bordes de tabla
#let fondo-label  = rgb("EEF1F8")   // fondo columna-etiqueta en ficha
#let fondo-cebra  = rgb("F6F8FB")   // fila cebra

// Colores de bloques de aviso  (borde, fondo, acento)
#let _aviso-cfg = (
  info:           (azul-acento, rgb("EEF3FB"), azul-acento,        "ℹ"),
  warning:    (rgb("E0A100"), rgb("FBF4DD"), rgb("B7860B"),    "⚠"),
  danger:         (rgb("D64541"), rgb("FBECEC"), rgb("B0322F"),    "⛔"),
  success:  (verde, rgb("EDF6EE"), rgb("2E7D34"),            "✓"),
)
// Colores de prioridad (para tablas de recomendaciones)
#let prio = (
  Alta:  rgb("F6C7C5"),
  Media: rgb("FBE6A2"),
  Baja:  rgb("CDE8CF"),
)

// ------------------------------------------------------------
// 2. METADATOS POR DEFECTO
// ------------------------------------------------------------
#let meta-default = (
  // -- Código documental: AREA-TIPO-CAT_AAAA-NNNN_vX.Y_AAAAMMDD --
  area:         "TI",        // área emisora
  tipo:         "PLA",       // INF, MAN, POL, PRO, PLA, EVL, ETT, ACT
  categoria:    "GOB",       // categoría temática (3 letras): GOB, SEG, RED, PRV...
  anio:         2026,
  correlativo:  1,           // entero → 4 dígitos
  version:      "1.0",
  fecha-codigo: "20260101",  // YYYYMMDD,
  fecha: datetime.today().display(),

  // -- Presentación / portada --
  tipo-largo:   "Informe Técnico",   // rótulo superior izq. de portada (MANUAL, INFORME...)
  titulo:       "Título del Documento",
  subtitulo:    "Subtítulo",

  // -- Estado / clasificación --
  estado:        "BORRADOR",  // BORRADOR | EN REVISIÓN | APROBADO
  clasificacion: "INTERNO",   // PÚBLICO | INTERNO | RESERVADO | CONFIDENCIAL

  // -- Autoría / control --
  autor:        "Nombre Apellido",
  cargo-autor:  "Cargo",
  correo-autor: "correo@epchinchorro.cl",
  revisor:      "Jefatura Unidad TI",
  cargo-revisor:"Jefe(a) de Tecnologías de la Información",
  aprobador:    "Subdirección de Planificación y Control de Gestión",
  cargo-aprob:  "Subdirector(a)",

  // -- Identidad institucional --
  unidad:       "Unidad de Tecnologías de la Información",
  subdireccion: "Subdirección de Planificación y Control de Gestión",
  institucion:  "Servicio Local de Educación Pública Chinchorro",
  comunas:      "Arica · Camarones · General Lagos · Putre",
  correo-inst:  "informatica@epchinchorro.cl",
  sitio-inst:   "slepchinchorro.gob.cl",

  // -- Branding --
  logos: (
    slepchinchorro: "Images/logo-chinchorro.png",
    slep:    "Images/logoslepch.png",      // logo color (portada + header)
    isologo: "Images/isologo_2.png",       // marca pequeña (no usada por defecto)
  ),

  // -- Estructura --
  contraportada: true,   // false para omitir la contraportada
)

// ------------------------------------------------------------
// 3. UTILIDADES
// ------------------------------------------------------------
#let _merge-meta(user) = {
  let m = meta-default + user
  m.logos = meta-default.logos + user.at("logos", default: (:))
  m
}
// Construye el meta completo (defaults + overrides). Úsalo en el documento.
#let crear-meta(user) = _merge-meta(user)

#let codigo-base(meta) = {
  let n = str(meta.correlativo)
  while n.len() < 4 { n = "0" + n }
  meta.area + "-" + meta.tipo + "-" + meta.categoria + "_" + str(meta.anio) + "-" + n
}
#let codigo-completo(meta) = codigo-base(meta) + "_v" + meta.version + "_" + meta.fecha-codigo

// Badge genérico
#let badge(txt, fondo) = box(
  fill: fondo, inset: (x: 7pt, y: 2.5pt), radius: 3pt,
  text(fill: white, weight: "bold", size: 8pt, tracking: 0.3pt)[#upper(txt)],
)
#let _color-estado(s) = if upper(s) == "APROBADO" { verde } else if upper(s) == "EN REVISIÓN" { rgb("E0A100") } else { gris-texto }
#let badge-estado(s)        = badge(s, _color-estado(s))
#let badge-clasificacion(c) = badge(c, azul-acento)

// Franja-bandera (recreada con formas; evita depender de un asset externo)
#let franja-bandera() = box(width: 3.6cm, height: 0.78cm, radius: 2pt, clip: true, stroke: none)[
  #grid(
    columns: (1fr, 1.4fr),
    rows: 100%,
    rect(width: 100%, height: 100%, fill: azul-bandera, stroke: none)[
      #align(center + horizon)[#text(fill: white, size: 13pt)[★]]
    ],
    rect(width: 100%, height: 100%, fill: rojo-acento, stroke: none),
  )
]

// Barra "GOBIERNO DE CHILE"
#let gobierno-bar(oscuro: false) = {
  let col = if oscuro { white } else { marino }
  align(center)[
    #box(baseline: -3pt, line(length: 0.9cm, stroke: 1.2pt + rojo-acento))
    #h(5pt)
    #text(fill: col, weight: "bold", size: 9pt, tracking: 1pt)[GOBIERNO #text(weight: "regular")[DE] CHILE]
    #h(5pt)
    #box(baseline: -3pt, line(length: 0.9cm, stroke: 1.2pt + rojo-acento))
  ]
}

// ------------------------------------------------------------
// 4. PORTADA  (página azul marino, sin numeración)
// ------------------------------------------------------------
#let portada(meta) = page(
  fill: marino, margin: (x: 2.4cm, top: 1.6cm, bottom: 1.4cm),
  header: none,
  footer: gobierno-bar(oscuro: true),
)[
  #align(center)[#franja-bandera()]
  #v(0.4cm)
  #grid(
    columns: (1fr, 1fr),
    text(fill: white, weight: "bold", size: 11pt, tracking: 2pt)[#upper(meta.tipo-largo)],
    align(right)[#text(fill: rgb("AEB8D6"), size: 10pt, tracking: 1pt)[· #upper(meta.clasificacion)]],
  )
  #v(0.5cm)
  #image(meta.logos.slep, height: 2.6cm)
  #v(0.8fr)

  // Badge de código
  #box(fill: rgb(255, 255, 255, 18), inset: (x: 12pt, y: 8pt), radius: 4pt)[
    #text(fill: white, weight: "bold", size: 11pt)[#codigo-base(meta)]
    #text(fill: rgb("AEB8D6"), size: 11pt)[ · v#meta.version · #meta.fecha]
  ]
  #v(0.5cm)
  #upper(text(fill: white, weight: "bold", size: 38pt)[#meta.titulo]) \
  #v(0.4cm)
  #text(fill: rgb("C2CCE6"), size: 17pt)[#meta.subtitulo]
  
  #v(2fr)
#align(center)[
  #text(fill: rgb("AEB8D6"), weight: "bold", size: 10.5pt)[#meta.unidad] \
  #text(fill: rgb("AEB8D6"), size: 10.5pt)[#meta.subdireccion] \
  #text(fill: rgb("C2CCE6"), size: 12pt, weight: "bold")[#meta.institucion]
  ]
  #v(0.4cm)
]

// ------------------------------------------------------------
// 5. CONTRAPORTADA  (página azul marino, sin numeración)
// ------------------------------------------------------------
#let contraportada(meta) = page(
  fill: marino, margin: (x: 2.4cm, top: 1.6cm, bottom: 1.4cm),
  header: none,
  footer: {
    grid(
      columns: (1fr, auto),
      text(fill: rgb("8E98BC"), size: 8pt)[#codigo-completo(meta) · #meta.anio],
      text(fill: rgb("8E98BC"), size: 8pt)[#meta.correo-inst · #meta.sitio-inst],
    )
    v(2pt)
    gobierno-bar(oscuro: true)
  },
)[
  #align(center)[#franja-bandera()]
  #v(1fr)
  #align(center)[
    #text(fill: white, weight: "bold", size: 30pt, tracking: 1pt)[TRABAJANDO #text(weight: "regular")[PARA] USTED]
    #v(1.2cm)
    #text(fill: rgb("C2CCE6"), weight: "bold", size: 10pt, tracking: 2pt)[SERVICIO LOCAL DE EDUCACIÓN PÚBLICA] \
    #v(0.1cm)
    #text(fill: rgb(255, 255, 255, 0), stroke: 0.8pt + white, weight: "bold", size: 40pt, tracking: 3pt)[CHINCHORRO]
    #v(0.2cm)
    #text(fill: white, weight: "bold", size: 11pt)[#meta.comunas]
  ]
  #v(0.8cm)
  #align(center)[
    #block(width: 80%)[
      #text(fill: rgb("AEB8D6"), size: 9pt)[
        Documento de uso institucional. Su reproducción debe respetar las condiciones de
        #upper(meta.clasificacion) establecidas por la #meta.unidad.
      ]
    ]
  ]
  #v(1fr)
]

// ------------------------------------------------------------
// 6. FUNCIÓN PRINCIPAL — #show: report.with(meta: (...))
// ------------------------------------------------------------
#let report(meta: (:), doc) = {
  let meta = _merge-meta(meta)

  // -- Tipografía --
  set text(font: ("Museo Sans", "Liberation Sans"), size: 10.5pt, lang: "es", fill: rgb("1A1A1A"))
  set par(justify: true, leading: 0.62em, spacing: 0.9em)
  set list(indent: 6pt, spacing: 0.7em)
  set enum(indent: 6pt, spacing: 0.7em)

  // -- Encabezados numerados (1, 1.1) en azul marino con regla --
  set heading(numbering: "1.1")
  show heading.where(level: 1): it => {
    v(14pt)
    block(below: 6pt)[
      #text(size: 18pt, weight: "bold", fill: marino)[
        #if it.numbering != none { counter(heading).display(); h(4pt) }
        #it.body
      ]
    ]
    line(length: 3.1cm, stroke: 2.5pt + marino)
    v(8pt)
  }
  show heading.where(level: 2): it => {
    v(9pt)
    text(size: 12.5pt, weight: "bold", fill: marino)[
      #counter(heading).display() #h(3pt) #it.body
    ]
    v(1pt)
    block(below: 5pt)[#line(length: 1.9cm, stroke: 0.7pt + gris-borde)]
  }

  // -- Página interior (header + footer institucionales) --
  set page(
    paper: "us-letter",
    margin: (top: 3cm, bottom: 2.4cm, left: 2.3cm, right: 2.3cm),
    header: context {
      grid(
        columns: (auto, 1fr),
        align(left + horizon)[#image(meta.logos.slepchinchorro, height: 1.5cm)],
        align(right + horizon)[
          #text(size: 8.5pt, fill: gris-texto, weight: "bold")[#meta.unidad] \
          #text(size: 8.5pt, fill: gris-texto)[#meta.subdireccion]
        ],
      )
      line(length: 100%, stroke: 0.5pt + gris-borde)
    },
    footer: context {
      line(length: 100%, stroke: 0.5pt + gris-borde)
      v(2pt)
      grid(
        columns: (1fr, 1fr, 1fr),
        align(left)[
          #text(fill: marino, weight: "bold", size: 8pt)[#codigo-base(meta)]
          #text(fill: gris-texto, size: 8pt)[ · v#meta.version]
        ],
        align(center)[#text(fill: marino, weight: "bold", size: 8pt, tracking: 0.5pt)[GOBIERNO DE CHILE]],
        align(right)[
          #box(fill: marino, inset: (x: 6pt, y: 2pt), radius: 1pt)[
            #text(fill: white, weight: "bold", size: 8pt)[#counter(page).display()]
          ]#box(fill: rojo-acento, height: 1.1em, width: 4pt)
        ],
      )
    },
  )

  // Portada (página 1, no numerada visualmente)
  portada(meta)

  // Cuerpo (comienza en página 2, como el manual de referencia)
  doc

  if meta.contraportada { contraportada(meta) }
}

// ============================================================
// 7. COMPONENTES DE CONTENIDO
// ============================================================

// --- Tabla institucional genérica (cabecera marino + cebra) ---
#let tabla(columns: auto, headers, rows) = {
  set text(size: 9.5pt)
  table(
    columns: columns,
    stroke: 0.5pt + gris-borde,
    inset: (x: 8pt, y: 7pt),
    fill: (x, y) => if y == 0 { marino } else if calc.odd(y) { white } else { fondo-cebra },
    ..headers.map(h => text(fill: white, weight: "bold")[#h]),
    ..rows.flatten(),
  )
}

// --- Tabla clave/valor (ficha de control: sin cabecera, etiqueta tintada) ---
#let tabla-kv(filas) = {
  set text(size: 9.5pt)
  table(
    columns: (5.2cm, 1fr),
    stroke: 0.5pt + gris-borde,
    inset: (x: 8pt, y: 6pt),
    fill: (x, y) => if x == 0 { fondo-label } else { white },
    ..filas.map(((k, v)) => (
      text(fill: marino, weight: "bold")[#k],
      v,
    )).flatten(),
  )
}

// --- Ficha de control documental (sección 1) ---
#let ficha-control(meta, rama-git: none) = {
  let filas = (
    ("Tipo de documento", meta.tipo-largo),
    ("Código base",        text(fill: marino, weight: "bold")[#codigo-base(meta)]),
    ("Código completo",    raw(codigo-completo(meta))),
    ("Título",             meta.titulo),
    ("Versión",            "v" + meta.version),
    ("Fecha de emisión",   meta.fecha-codigo),
    ("Estado",             badge-estado(meta.estado)),
    ("Clasificación",      badge-clasificacion(meta.clasificacion)),
    ("Área emisora",       meta.unidad),
    ("Subdirección",       meta.subdireccion),
    ("Institución",        meta.institucion),
    ("Autor",              [#meta.autor \ #text(size: 8.5pt, fill: gris-texto)[#meta.cargo-autor · #meta.correo-autor]]),
    ("Revisor",            [#meta.revisor \ #text(size: 8.5pt, fill: gris-texto)[#meta.cargo-revisor]]),
    ("Aprobador",          [#meta.aprobador \ #text(size: 8.5pt, fill: gris-texto)[#meta.cargo-aprob]]),
  )
  if rama-git != none { filas.push(("Rama Git", raw(rama-git))) }
  tabla-kv(filas)
}

// --- Bloque de aviso (info | advertencia | riesgo | recomendacion) ---
#let aviso(tipo: "info", titulo: none, cuerpo) = {
  let (borde, fondo, acento, icono) = _aviso-cfg.at(tipo)
  block(
    width: 100%, fill: fondo, radius: 3pt,
    inset: (left: 12pt, rest: 10pt),
    stroke: (left: 3pt + borde),
  )[
    #if titulo != none {
      text(fill: acento, weight: "bold")[#icono #h(3pt) #titulo]
      v(3pt)
    }
    #set text(size: 9.5pt)
    #cuerpo
  ]
}

// --- Firmas tripartitas (Anexo C) ---
// firmantes: lista de (rol, nombre, cargo)
#let firmas(firmantes) = {
  set text(size: 9.5pt)
  grid(
    columns: firmantes.map(_ => 1fr),
    column-gutter: 0.8cm,
    ..firmantes.map(f => align(center)[
      #text(fill: marino, weight: "bold", size: 10pt, tracking: 0.5pt)[#upper(f.rol)]
      #v(1.6cm)
      #line(length: 85%, stroke: 0.6pt + gris-texto)
      #v(3pt)
      #text(weight: "bold")[#f.nombre] \
      #text(size: 8.5pt, fill: gris-texto)[#f.cargo]
    ]),
  )
}

// --- Tabla de contenido institucional ---
#let indice() = {
  show outline.entry.where(level: 1): it => { 
    v(2pt);
    strong(it);
  }
  outline(title: none, indent: 1.2em, depth: 2)
}

// ============================================================
// 8. SECCIONES CANÓNICAS (título oficial + componente, listas para usar)
//    Estos atajos emiten el encabezado numerado y su tabla. Las secciones
//    de prosa (Resumen, Antecedentes, etc.) las escribe el autor con `= ...`.
// ============================================================

// 1 · Ficha de control documental
#let s-ficha(meta, rama-git: none) = {
  heading(level: 1)[Ficha de control documental]
  ficha-control(meta, rama-git: rama-git)
}

// 2 · Control de versiones — filas: (versión, fecha, autor, descripción)
#let s-versiones(filas) = {
  heading(level: 1)[Control de versiones]
  tabla(
    columns: (auto, auto, 1fr, 2.4fr),
    ("Versión", "Fecha", "Autor", "Descripción del cambio"),
    filas,
  )
}

// 3 · Distribución — filas: (nombre, rol, tipo)
#let s-distribucion(filas) = {
  heading(level: 1)[Distribución]
  tabla(
    columns: (1.4fr, 1.2fr, 1fr),
    ("Nombre", "Rol", "Tipo"),
    filas,
  )
}

// 4 · Tabla de contenido
#let s-indice() = {
  heading(numbering: none, level: 1, outlined: false)[Tabla de contenido]
  indice()
}

// Firmas tripartitas derivadas de `meta` (Anexo B/C). Equivale a `firmas(...)`
// con autor → Elaborado, revisor → Revisado, aprobador → Aprobado.
#let firmas-estandar(meta) = firmas((
  (rol: "Elaborado por", nombre: meta.autor,     cargo: meta.cargo-autor),
  (rol: "Revisado por",  nombre: meta.revisor,   cargo: meta.cargo-revisor),
  (rol: "Aprobado por",  nombre: meta.aprobador, cargo: meta.cargo-aprob),
))

// Tabla de recomendaciones con celda de prioridad coloreada automáticamente.
// filas: (n, recomendación, prioridad, responsable); prioridad ∈ "Alta"|"Media"|"Baja".
#let tabla-prioridad(filas) = {
  set text(size: 9.5pt)
  table(
    columns: (auto, 2.4fr, auto, 1.2fr),
    stroke: 0.5pt + gris-borde,
    inset: (x: 8pt, y: 7pt),
    fill: (x, y) => if y == 0 { marino } else if calc.odd(y) { white } else { fondo-cebra },
    text(fill: white, weight: "bold")[N°],
    text(fill: white, weight: "bold")[Recomendación],
    text(fill: white, weight: "bold")[Prioridad],
    text(fill: white, weight: "bold")[Responsable],
    ..filas.map(((n, rec, pri, resp)) => (
      [#n],
      rec,
      table.cell(fill: prio.at(pri, default: white))[*#pri*],
      resp,
    )).flatten(),
  )
}
