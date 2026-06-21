// ============================================================
// Informe Técnico N°22/2026
// Justificación Modificación de Contrato — Ampliación de Plazo
// SLEP Chinchorro — Unidad de Tecnologías de la Información
// ============================================================

// --- Configuración de Página ---
#set page(
  paper: "us-legal",
  margin: (top: 3.5cm, bottom: 2.5cm, left: 2.5cm, right: 2.5cm),
  header: context {
    let page-num = counter(page).get().first()
    if page-num > 1 {
      align(center)[
        #image("Images/isologo_2.png", width: 4cm)
      ]
    }
  },
  footer: context {
    let page-num = counter(page).get().first()
    if page-num > 1 {
      grid(
        columns: (1fr, auto),
        [#text(size: 9pt, fill: rgb("737373"))[Unidad de Tecnologías de la Información — Informe Técnico N°22/2026]],
        [#text(size: 9pt)[#counter(page).display()]],
      )
    }
  },
)

// --- Fuentes ---
#set text(
  font: ("Museo Sans", "Liberation Sans"),
  size: 11pt,
  lang: "es",
)

// --- Colores Institucionales ---
#let azul-chinchorro = rgb("0F68B5")
#let gris-suave      = rgb("737373")
#let fondo-tabla     = rgb("F5F7FA")

// --- Párrafos ---
#set par(justify: true, leading: 0.65em, spacing: 0.8em)

// --- Numeración de títulos (desactivada, usaremos numeración romana manual) ---
#set heading(numbering: none)

// --- Estilo de encabezados ---
#show heading.where(level: 1): it => {
  v(10pt)
  text(size: 13pt, weight: "bold")[#it.body]
  v(6pt)
}
#show heading.where(level: 2): it => {
  v(8pt)
  text(size: 11pt, weight: "bold")[#it.body]
  v(4pt)
}

// --- Helper: Tabla Institucional ---
#let inst-table(columns: (1fr, 1fr), headers, rows) = {
  set text(size: 10pt)
  table(
    columns: columns,
    fill: (x, y) => if y == 0 { azul-chinchorro } else if calc.odd(y) { fondo-tabla } else { white },
    stroke: rgb("CCCCCC"),
    inset: 8pt,
    ..headers.map(h => text(fill: white, weight: "bold")[#h]),
    ..rows.flatten(),
  )
}

// --- Helper: Caja de condición/dato ---
#let dato-box(body) = block(
  width: 100%,
  inset: (x: 12pt, y: 10pt),
  radius: 4pt,
  stroke: azul-chinchorro,
  fill: azul-chinchorro.lighten(92%),
  above: 6pt,
  below: 6pt,
)[#body]

// ============================================================
// PORTADA
// ============================================================
#set page(header: none, footer: none)

#v(1cm)
#grid(
  columns: (auto, 1fr, auto),
  image("Images/logoslepch.png", width: 3cm),
  [],
  image("Images/logo-chinchorro.png", width: 8cm),
)

#v(3cm)

#line(length: 120%, stroke: 1pt + azul-chinchorro)
#v(1.5cm)

#text(size: 28pt, weight: "bold")[Informe Técnico N°22/2026]
#v(0.6cm)
#text(size: 18pt, fill: gris-suave)[Justificación Modificación de Contrato]
#v(0.3cm)
#text(size: 16pt)[Ampliación de Plazo]
#v(0.4cm)
#text(size: 13pt, fill: gris-suave)[
  "Servicios de Conectividad de Internet y Telefonía Fija, \
  Edificio Central SLEP Chinchorro, Codpa N°2173"
]
#v(1.2cm)
#line(length: 40%, stroke: 1pt + azul-chinchorro)

#v(1fr)

#align(right)[
  #text(size: 14pt, weight: "bold")[Unidad de Tecnologías de la Información] \
  #text(size: 14pt)[Subdirección de Planificación y Control de Gestión] \
  #text(size: 14pt)[Servicio Local de Educación Pública de Chinchorro] \
  #v(0.4cm)
  #text(size: 14pt, weight: "bold")[Roberto I. Vargas Vargas] \
  #text(size: 10pt)[Técnico de Soporte Informático] \
  #v(0.8cm)
  #text(size: 14pt)[Arica, 25 de mayo del 2026]
]

// ============================================================
// CUERPO DEL INFORME
// ============================================================
#pagebreak()
#set page(
  background: place(top + center, dy: 0.2cm)[
    #image("Images/isologo_2.png", width: 4cm)
  ],
  footer: context {
    grid(
      columns: (1fr, auto),
      [#text(size: 9pt, fill: rgb("888888"))[Informe Técnico N°22/2026 - UTI]],
      [#text(size: 9pt)[#counter(page).display()]],
    )
  },
)

#counter(page).update(1)

// ============================================================
// I. ANTECEDENTES
// ============================================================
= I. ANTECEDENTES

Mediante Resolución Exenta N°2740 de 2023, de fecha 27 de marzo de 2023, el Servicio Local de Educación Pública Chinchorro aprobó las bases de licitación pública ID N°1084148-17-LE23 para la contratación de servicios de conectividad de internet y telefonía fija para el edificio central ubicado en Codpa N°2173, ciudad de Arica.

A través de Resolución Exenta N°3153 de 2023, de fecha 11 de abril de 2023, se adjudicó dicha licitación al proveedor GTD Telesat S.A. (RUT 96.721.280-6), por un valor mensual neto de \$1.253.832 (valor mensual con IVA: \$1.492.060), emitiéndose la Orden de Compra N°1084148-53-SE23 con fecha 12 de abril de 2023, aceptada por el proveedor ese mismo día.

Conforme a lo consignado en el Certificado de Recepción Conforme emitido con fecha 14 de agosto de 2023 por el Profesional Encargado T.I. de este Servicio Local, Daniel Miranda Candia, y específicamente a lo señalado en sus observaciones, el servicio de internet fue completamente implementado a partir del *01 de julio de 2023*, fecha desde la cual el contrato se encuentra en plena ejecución. En consecuencia, el plazo de 36 meses establecido en las bases se computa desde dicha fecha, con vencimiento el *30 de junio de 2026*.

Mediante Resolución Exenta N°9487 de 2024, de fecha 31 de diciembre de 2024, se autorizó el cambio de razón social del proveedor de GTD Telesat S.A. (RUT 96.721.280-6) a *GTD Intesis S.A. (RUT 78.159.800-3)*, producto de la fusión de ambas sociedades, emitiéndose en consecuencia la Orden de Compra N°1084148-3-SE25 de fecha 10 de enero de 2025, a nombre del nuevo RUT del proveedor, para cubrir los períodos pendientes de pago bajo el contrato vigente.

El contrato actualmente en vigor vence el *30 de junio de 2026*, encontrándose este Servicio Local en proceso de gestión de un nuevo proceso licitatorio para la contratación definitiva de los servicios de conectividad de internet y telefonía fija del edificio central, el cual aún no ha sido publicado. 

#v(0.5cm)

*Solicitud de compra para nuevo proceso contractual.*

- Código Compra: INT-2026-0067
- Nombre Compra: SERVICIO DE INTERNET FIBRA ÓPTICA DEDICADA Y TELEFONÍA FIJA (ADM. CENTRAL) POR 12 MESES

// ============================================================
// II. OBJETO DEL INFORME
// ============================================================
#pagebreak()
= II. OBJETO DEL INFORME

El presente informe tiene por objeto fundamentar y recomendar la modificación del contrato originado en la licitación pública ID N°1084148-17-LE23, en virtud de lo establecido en el numeral 10.4.1 de las Bases Administrativas, con el fin de ampliar su plazo de vigencia en *3 meses adicionales*, extendiéndolo desde el *01 de julio de 2026* hasta el *30 de septiembre de 2026*, o hasta la adjudicación y entrada en vigencia del nuevo contrato que se obtenga mediante licitación pública, lo que ocurra primero, con un valor mensual neto de \$1.253.832 (\$1.492.060 con IVA), y un monto adicional máximo de \$3.761.496 neto (\$4.476.180 con IVA).

#v(1cm)

// ============================================================
// III. FUNDAMENTOS TÉCNICOS Y JURÍDICOS
// ============================================================
= III. FUNDAMENTOS TÉCNICOS Y JURÍDICOS



== 3.1 Habilitación normativa

El numeral 10.4.1 de las Bases Administrativas de la licitación pública ID N°1084148-17-LE23 establece que el Servicio Local podrá modificar el contrato cuando sea necesario para el estricto cumplimiento de éste, mediante resolución fundada, publicada dentro de las 24 horas posteriores a su firma, y siempre que exista mutuo acuerdo entre las partes contratantes y la modificación no signifique una alteración de fondo de lo convenido.

En el caso que nos ocupa, la modificación propuesta consiste exclusivamente en una ampliación del plazo de vigencia del contrato, manteniéndose íntegramente las condiciones técnicas y económicas originalmente pactadas, por lo que no constituye una alteración de fondo de lo convenido.

#v(0.5cm)

== 3.2 Necesidad de la modificación — Continuidad operacional

El contrato vigente expirará el 30 de junio de 2026. Este Servicio Local se encuentra actualmente gestionando un nuevo proceso de licitación pública para la contratación definitiva de los servicios de conectividad de internet y telefonía fija del edificio central, sin embargo dicho proceso aún no ha sido publicado. Los plazos mínimos contemplados en la Ley N°19.886 y su Reglamento para un proceso de licitación pública hacen imposible contar con un nuevo contrato vigente antes del vencimiento del actual, por lo que la modificación propuesta resulta necesaria para asegurar la continuidad operacional del Servicio Local durante el período de transición.

#v(0.5cm)

== 3.3 Criticidad del servicio

Los servicios de conectividad de internet y telefonía fija constituyen componentes críticos para la continuidad operacional del edificio central del SLEP Chinchorro, toda vez que permiten el funcionamiento de servicios institucionales esenciales para la gestión administrativa, técnica, comunicacional y operativa del Servicio Local.

En particular, dichos servicios soportan:

- *La intranet institucional del Servicio*, correspondiente a una plataforma web de uso transversal, utilizada por funcionarios de los establecimientos educacionales dependientes y por funcionarios de la gestión central del Servicio Local, cuyo acceso depende de la disponibilidad de conectividad de red e internet.

- *El sistema de control de asistencia del personal*, correspondiente a un servicio de red centralizado y de uso transversal, al cual se conectan los establecimientos educacionales dependientes y las unidades de gestión central del Servicio Local, permitiendo el registro, consulta, validación y administración de la asistencia de más de 3.000 funcionarios.

- *La conectividad de la red interna del edificio central*, necesaria para el acceso a servicios, recursos compartidos, sistemas institucionales y herramientas de trabajo utilizadas por las distintas unidades del Servicio.

- *El acceso a plataformas internas y externas de gestión institucional*, utilizadas para el desarrollo de procesos administrativos, financieros, técnicos y de coordinación con otras instituciones públicas.

- *El servicio de telefonía fija*, compuesto por 20 anexos destinados a la comunicación institucional con establecimientos educacionales dependientes, proveedores, organismos públicos y otros actores relevantes.

#v(0.2cm)

En consecuencia, una eventual interrupción de estos servicios afectaría de manera directa e inmediata la continuidad operacional del Servicio Local, dificultando el cumplimiento oportuno de sus funciones administrativas, técnicas y de coordinación institucional como sostenedor de los establecimientos educacionales de las comunas de Arica, Camarones, Putre y General Lagos.

#v(0.5cm)

== 3.4 Desempeño del proveedor

GTD Intesis S.A. (ex GTD Telesat S.A., RUT 78.159.800-3) ha prestado el servicio de manera satisfactoria durante toda la vigencia del contrato con este Servicio Local, contando con recepciones conformes emitidas periódicamente por la Contraparte Técnica, sin que haya sido necesario aplicar multas ni sanciones por incumplimiento en el marco del presente contrato. Lo anterior acredita su idoneidad para continuar prestando el servicio durante el período de ampliación propuesto.

#v(0.5cm)

== 3.5 Proporcionalidad de la modificación

La ampliación propuesta es de 3 meses, lo que representa un incremento acotado y proporcional respecto al contrato original de 36 meses. El proveedor GTD Intesis S.A. confirmó la mantención de la tarifa vigente para el período de ampliación, fijando la renta mensual en *\$1.253.832 neto* (\$1.492.060 con IVA), manteniendo el presupuesto mensual original del servicio. El monto total máximo asciende a *\$3.761.496 neto* (\$4.476.180 con IVA). Dicho ajuste fue comunicado formalmente por el ejecutivo comercial del proveedor y se encuentra respaldado por cotización en papel que se adjunta como antecedente.

// ============================================================
// IV. CONDICIONES DE LA MODIFICACIÓN PROPUESTA
// ============================================================
#pagebreak()
= IV. CONDICIONES DE LA MODIFICACIÓN PROPUESTA

#dato-box[
  #inst-table(
    columns: (1fr, 1.8fr),
    ("Ítem", "Detalle"),
    (
      [*Proveedor*],                      [GTD Intesis S.A. (ex GTD Telesat S.A.), RUT 78.159.800-3],
      [*Servicio*],                        [Conectividad de internet y telefonía fija, Edificio Central SLEP Chinchorro, Codpa N°2173],
      [*Plazo original*],                  [01 de julio de 2023 al 30 de junio de 2026 (36 meses)],
      [*Ampliación*],                      [3 meses adicionales],
      [*Nuevo plazo de vigencia*],         [01 de julio de 2023 al 30 de septiembre de 2026],
      [*Período de ampliación*],           [01 de julio de 2026 al 30 de septiembre de 2026, o hasta la adjudicación y entrada en vigencia del nuevo contrato licitado, *lo que ocurra primero*],
      [*Valor mensual neto*],              [\$1.253.832],
      [*Valor mensual con IVA*],           [\$1.492.060],
      [*Monto adicional máximo neto*],     [\$3.761.496],
      [*Monto adicional máximo con IVA*],  [\$4.476.180],
      [*Imputación presupuestaria*],       [Ítem 2205007 "Acceso a Internet", Subvención Resto, Subtítulo 22],
      [*Modalidad de formalización*],      [Resolución Exenta fundada, publicada en portal Mercado Público dentro de las 24 horas posteriores a su firma, conforme al numeral 10.4.1 de las Bases Administrativas],
    ),
  )
]

#v(1cm)

// ============================================================
// V. RECOMENDACIÓN
// ============================================================
= V. RECOMENDACIÓN

Por los fundamentos técnicos y jurídicos expuestos en el presente informe, el suscrito recomienda aprobar la modificación del contrato originado en la licitación pública ID N°1084148-17-LE23, consistente en la ampliación de su plazo de vigencia en 3 meses adicionales, extendiéndolo hasta el *30 de septiembre de 2026*, o hasta la adjudicación y entrada en vigencia del nuevo contrato que se obtenga mediante licitación pública, lo que ocurra primero, manteniéndose íntegramente las condiciones técnicas y económicas originalmente pactadas.

#v(4cm)

#align(center)[
  #line(length: 50%, stroke: 0.5pt + gris-suave)
  #v(0.3cm)
  #text(weight: "bold")[ROBERTO I. VARGAS VARGAS] \
  #text(size: 10pt)[Técnico de Soporte Informático] \
  #text(size: 10pt)[Unidad de Tecnologías de la Información] \
  #text(size: 10pt)[Subdirección de Planificación y Control de Gestión] \
  #text(size: 10pt)[Servicio Local de Educación Pública Chinchorro]
]

// ============================================================
// ANEXOS
// ============================================================
#pagebreak()
= ANEXOS

- Orden de Compra N°1084148-53-SE23 (2023)
- Orden de Compra N°1084148-3-SE25 (2025)
- Resolución Exenta N°9487 de 2024 (Cambio de Razón Social)
- Resolución Exenta N°3153 de 2023 (Adjudica Licitación)
- Resolución Exenta N°2740 de 2023 (Bases Administrativas)
- Primer Certificado de Recepción Conforme (Agosto 2023)
- Cotización del Proveedor