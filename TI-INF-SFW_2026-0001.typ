// TI-INF-SFW_2026-0001  ·  generado por doctyp
#import "lib.typ": *

#let meta = crear-meta((
  area: "TI", tipo: "INF", categoria: "SFW",
  anio: 2026, correlativo: 1, version: "1.0.0", fecha-codigo: "20260621",
  tipo-largo: "Informe Técnico",
  titulo: "Informe de prueba", subtitulo: "Empresa",
  estado: "BORRADOR", clasificacion: "INTERNO",
  autor: "John Doe", cargo-autor: "Tecnico", correo-autor: "john.doe@mail.com",
))
#show: report.with(meta: meta)

#s-ficha(meta, rama-git: "doc/TI-INF-SFW-2026-0001")
#s-versiones(meta, (
  ("v1.0.0", "2026-06-21", "John Doe", "Versión inicial."),
))
#s-distribucion((
  ("Equipo TI", "Operación documental", "Receptor principal"),
  ("Subdirección de Planificación y Control de Gestión", "Supervisión", "Copia informativa"),
  ("Archivo Institucional", "Custodia", "Archivo institucional"),
))
#s-indice()

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

= Recomendaciones
#tabla-prioridad((
  ("1", "Acción recomendada.", "Alta", "Responsable"),
))

= Glosario y acrónimos
#tabla(
  columns: (auto, 1fr),
  ("Término", "Definición"),
  (
    ("SLEP", "Servicio Local de Educación Pública."),
    ("TI", "Tecnologías de la Información."),
  ),
)

= Referencias
// TODO

= Anexos
== Anexo A. Documentos de respaldo
// TODO
== Anexo B. Firmas
#firmas-estandar(meta)
