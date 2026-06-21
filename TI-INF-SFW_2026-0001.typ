// TI-INF-SFW_2026-0001  ·  generado por doc.py
#import "lib.typ": *

#let meta = crear-meta((
  area: "TI", tipo: "INF", categoria: "SFW",
  anio: 2026, correlativo: 1, version: "1.0", fecha-codigo: "20260620",
  tipo-largo: "Informe Técnico",
  titulo: "Informe de Avance Modulo Identity Provisioning para PGI", subtitulo: "SLEP Chinchorro",
  estado: "BORRADOR", clasificacion: "INTERNO",
  autor: "Andrés Cubillos Salazar", cargo-autor: "Técnico de Soporte Informático", correo-autor: "andres.cubillos@epchinchorro.cl",
))
#show: report.with(meta: meta)

#s-ficha(meta, rama-git: "doc/TI-INF-SFW-2026-0001")
#pagebreak()
#s-versiones((
  ("v1.0", "2026-06-20", "Andrés Cubillos Salazar", "Versión inicial."),
))
#pagebreak()
#s-distribucion((
  ("Equipo TI", "Operación documental", "Receptor principal"),
  ("Subdirección de Planificación y Control de Gestión", "Supervisión", "Copia informativa"),
  ("Archivo Institucional", "Custodia", "Archivo institucional"),
))
#pagebreak()
#s-indice()
#pagebreak()

= Resumen ejecutivo
// TODO: 1–3 párrafos con el propósito, alcance y resultado principal.

= Antecedentes y motivación
== Contexto institucional
// TODO
== Problema o necesidad identificada
// TODO

= Objetivo
== Objetivo general
// TODO
== Objetivos específicos
// TODO

= Alcance
== Dentro del alcance
// TODO
== Fuera del alcance
// TODO

= Marco normativo y referencial
== Normativa legal aplicable
// TODO
== Estándares técnicos aplicables
// TODO

= Metodología
// TODO

= Desarrollo técnico
// TODO: cuerpo principal del informe.

= Análisis de impacto
== Confidencialidad
// TODO
== Integridad
// TODO
== Disponibilidad
// TODO

= Conclusiones
// TODO

#pagebreak()

= Recomendaciones
#tabla-prioridad((
  ("1", "Acción recomendada.", "Alta", "Responsable"),
))
#pagebreak()
= Glosario y acrónimos
#tabla(
  columns: (auto, 1fr),
  ("Término", "Definición"),
  (
    ("SLEP", "Servicio Local de Educación Pública."),
    ("TI", "Tecnologías de la Información."),
  ),
)
#pagebreak()
= Referencias
// TODO
#pagebreak()
= Anexos
== Anexo A. Documentos de respaldo
// TODO
#pagebreak()




== Anexo B. Firmas
#firmas-estandar(meta)
