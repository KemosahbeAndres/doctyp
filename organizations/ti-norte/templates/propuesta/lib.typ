// ============================================================
// lib.typ — Esqueleto mínimo (sin marca institucional)
// Implementa el mismo API público que una plantilla completa (CLAUDE.md §11), con
// estilos neutros y sin logos/colores propios. Punto de partida para "Nueva plantilla
// en blanco" — clónalo y reemplaza colores/portada/logos según se necesite.
// ============================================================

#let gris-texto  = rgb("6B7280")
#let gris-borde  = rgb("D7DAE2")
#let fondo-label = rgb("EEF1F8")
#let fondo-cebra = rgb("F6F8FB")
#let marino      = rgb("1A1A1A")
#let azul-acento = rgb("1A1A1A")
#let rojo-acento = rgb("B0322F")
#let verde       = rgb("2E7D34")

#let prio = (
  Alta:  rgb("F6C7C5"),
  Media: rgb("FBE6A2"),
  Baja:  rgb("CDE8CF"),
)

#let meta-default = (
  area: "TI", tipo: "INF", categoria: "RED",
  anio: 2026, correlativo: 1, version: "1.0", fecha-codigo: "20260101",
  fecha: datetime.today().display(),
  tipo-largo: "Documento",
  titulo: "Título del documento", subtitulo: "Subtítulo",
  estado: "BORRADOR", clasificacion: "INTERNO",
  autor: "Nombre Apellido", cargo-autor: "Cargo", correo-autor: "correo@ejemplo.cl",
  revisor: "", cargo-revisor: "",
  aprobador: "", cargo-aprob: "",
  unidad: "", subdireccion: "", institucion: "", comunas: "",
  correo-inst: "", sitio-inst: "",
  logos: (:),
  contraportada: true,
)

#let _merge-meta(user) = {
  let m = meta-default + user
  m.logos = meta-default.logos + user.at("logos", default: (:))
  m
}
#let crear-meta(user) = _merge-meta(user)

#let codigo-base(meta) = {
  let n = str(meta.correlativo)
  while n.len() < 4 { n = "0" + n }
  meta.area + "-" + meta.tipo + "-" + meta.categoria + "_" + str(meta.anio) + "-" + n
}
#let codigo-completo(meta) = codigo-base(meta) + "_v" + meta.version + "_" + meta.fecha-codigo

#let badge(txt, fondo) = box(
  fill: fondo, inset: (x: 7pt, y: 2.5pt), radius: 3pt,
  text(fill: white, weight: "bold", size: 8pt, tracking: 0.3pt)[#upper(txt)],
)
#let _color-estado(s) = if upper(s) == "APROBADO" { verde } else if upper(s) == "EN REVISIÓN" { rgb("E0A100") } else { gris-texto }
#let badge-estado(s)        = badge(s, _color-estado(s))
#let badge-clasificacion(c) = badge(c, azul-acento)

#let portada(meta) = page(
  margin: (x: 2.4cm, top: 3cm, bottom: 2.4cm),
  fill: rgb("232838"),
  background: place(top + left)[
  #polygon(
    (0pt, 20%), (80%, 20%), (80%, 40%), (0pt, 40%),
    fill: rgb("efb817"),
  )
]
)[
  
  #align(left + top)[
    #image("Images/logo_w.png", height: 2cm)
    #v(1cm)
    #text(weight: "bold", size: 10pt, tracking: 1pt)[#upper(meta.tipo-largo)]
    #v(0.5cm)
    #text(weight: "bold", size: 26pt)[#meta.titulo]
    #v(0.3cm)
    #text(size: 14pt, )[#meta.subtitulo]
    #v(10.5cm)
    #text(size: 10pt, fill: white)[#codigo-base(meta) · v#meta.version · #meta.fecha]
  ]
]

#let contraportada(meta) = page(margin: (x: 2.4cm, top: 3cm, bottom: 2.4cm))[
  #align(center + horizon)[
    #text(size: 9pt, fill: gris-texto)[#codigo-completo(meta) · #meta.anio]
  ]
]

#let report(meta: (:), doc) = {
  let meta = _merge-meta(meta)
  set text(font: ("Liberation Sans",), size: 10.5pt, lang: "es")
  set par(justify: true, leading: 0.62em, spacing: 0.9em)
  set heading(numbering: "1.1")
  show heading.where(level: 1): it => {
    v(14pt)
    block(below: 6pt)[
      #text(size: 16pt, weight: "bold")[
        #if it.numbering != none { counter(heading).display(); h(4pt) }
        #it.body
      ]
    ]
    line(length: 3.1cm, stroke: 1.5pt + gris-texto)
    v(8pt)
  }
  show heading.where(level: 2): it => {
    v(9pt)
    text(size: 12pt, weight: "bold")[#counter(heading).display() #h(3pt) #it.body]
  }
  set page(
    paper: "us-letter",
    margin: (top: 2.4cm, bottom: 2.2cm, left: 2.3cm, right: 2.3cm),
    footer: context {
      line(length: 100%, stroke: 0.5pt + gris-borde)
      v(2pt)
      grid(
        columns: (1fr, 1fr, 1fr),
        align(left)[#text(size: 8pt, fill: rgb("232838"))[#codigo-base(meta) · v#meta.version]],
        [],
        align(right)[#text(size: 8pt, fill: rgb("232838"))[#counter(page).display()]],
      )
    },
  )
  portada(meta)
  doc
  if meta.contraportada { contraportada(meta) }
}

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

#let tabla-kv(filas) = {
  set text(size: 9.5pt)
  table(
    columns: (5.2cm, 1fr),
    stroke: 0.5pt + gris-borde,
    inset: (x: 8pt, y: 6pt),
    fill: (x, y) => if x == 0 { fondo-label } else { white },
    ..filas.map(((k, v)) => (text(weight: "bold")[#k], v)).flatten(),
  )
}

#let ficha-control(meta) = {
  let filas = (
    ("Tipo de documento", meta.tipo-largo),
    ("Código base",        text(weight: "bold")[#codigo-base(meta)]),
    ("Código completo",    raw(codigo-completo(meta))),
    ("Título",             meta.titulo),
    ("Versión",            "v" + meta.version),
    ("Fecha de emisión",   meta.fecha-codigo),
    ("Estado",             badge-estado(meta.estado)),
    ("Clasificación",      badge-clasificacion(meta.clasificacion)),
    ("Autor",              [#meta.autor \ #text(size: 8.5pt, fill: gris-texto)[#meta.cargo-autor · #meta.correo-autor]]),
    ("Revisor",            [#meta.revisor \ #text(size: 8.5pt, fill: gris-texto)[#meta.cargo-revisor]]),
    ("Aprobador",          [#meta.aprobador \ #text(size: 8.5pt, fill: gris-texto)[#meta.cargo-aprob]]),
  )
  tabla-kv(filas)
}

#let aviso(tipo: "info", titulo: none, cuerpo) = {
  block(
    width: 100%, fill: fondo-label, radius: 3pt,
    inset: (left: 12pt, rest: 10pt),
    stroke: (left: 3pt + gris-texto),
  )[
    #if titulo != none {
      text(weight: "bold")[#titulo]
      v(3pt)
    }
    #set text(size: 9.5pt)
    #cuerpo
  ]
}

#let firmas(firmantes) = {
  set text(size: 9.5pt)
  grid(
    columns: firmantes.map(_ => 1fr),
    column-gutter: 0.8cm,
    ..firmantes.map(f => align(center)[
      #text(weight: "bold", size: 10pt, tracking: 0.5pt)[#upper(f.rol)]
      #v(1.6cm)
      #line(length: 85%, stroke: 0.6pt + gris-texto)
      #v(3pt)
      #text(weight: "bold")[#f.nombre] \
      #text(size: 8.5pt, fill: gris-texto)[#f.cargo]
    ]),
  )
}

#let indice() = {
  show outline.entry.where(level: 1): it => { v(2pt); strong(it) }
  outline(title: none, indent: 1.2em, depth: 2)
}

#let s-ficha(meta) = {
  heading(level: 1)[Ficha de control documental]
  ficha-control(meta)
}

#let s-versiones(meta, filas) = {
  heading(level: 1)[Control de versiones]
  tabla(
    columns: (auto, auto, 1fr, 2.4fr),
    ("Versión", "Fecha", "Autor", "Descripción del cambio"),
    filas.map(((version, fecha, autor, descripcion)) => (version, fecha, autor, descripcion)),
  )
}

#let s-distribucion(filas) = {
  heading(level: 1)[Distribución]
  tabla(columns: (1.4fr, 1.2fr, 1fr), ("Nombre", "Rol", "Tipo"), filas)
}

#let s-indice() = {
  heading(numbering: none, level: 1, outlined: false)[Contenido]
  indice()
}

#let firmas-estandar(meta) = firmas((
  (rol: "Elaborado por", nombre: meta.autor,     cargo: meta.cargo-autor),
  (rol: "Revisado por",  nombre: meta.revisor,   cargo: meta.cargo-revisor),
  (rol: "Aprobado por",  nombre: meta.aprobador, cargo: meta.cargo-aprob),
))

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
      [#n], rec, table.cell(fill: prio.at(pri, default: white))[*#pri*], resp,
    )).flatten(),
  )
}
