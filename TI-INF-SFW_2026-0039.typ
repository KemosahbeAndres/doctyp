// TI-INF-SFW_2026-0002  ·  generado por doctyp
#import "lib.typ": *

#let meta = crear-meta((
  area: "TI", tipo: "INF", categoria: "RED",
  anio: 2026, correlativo: 39, version: "1.0.0", fecha-codigo: "20260623",
  tipo-largo: "Informe Técnico",
  titulo: "Propuesta de Mejora y Ampliación de Red",
  subtitulo: "Escuela Carlos Condell de la Haza (G-8)",
  estado: "BORRADOR", clasificacion: "INTERNO",
  autor: "Andrés Cubillos Salazar", cargo-autor: "Tecnico de Soporte Informático", correo-autor: "andres.cubillos@epchinchorro.cl",
))
#show: report.with(meta: meta)

#s-indice()
#pagebreak()

= Resumen ejecutivo
Con fecha martes 09 de junio de 2026, personal de la Unidad de Tecnologías de la Información del SLEP Chinchorro realizó una visita técnica a la Escuela Carlos Condell de la Haza (G-8) con el objetivo de evaluar el estado de la infraestructura de red inalámbrica. Durante la visita se identificaron tres problemáticas principales: (1) zonas del establecimiento sin cobertura Wi-Fi; (2) un equipo de enrutamiento principal de generación antigua cuya capacidad resulta insuficiente frente al volumen actual de dispositivos conectados; y (3) tres puntos de acceso inalámbrico (AP) en estado de deterioro que comprometen la continuidad operativa.

El parque tecnológico de la escuela ha crecido con la incorporación reciente de tablets para uso pedagógico, que se suman a los equipos preexistentes (tablets y laptops), incrementando la demanda sobre una infraestructura de red que no ha sido dimensionada para soportar dicha carga. El presente informe describe los hallazgos de la visita y propone la renovación del equipo principal, el reemplazo de los AP deteriorados y la instalación de nuevos puntos de acceso para eliminar las zonas sin cobertura, asegurando la continuidad de las actividades administrativas y docentes del establecimiento.

#pagebreak()
= Antecedentes
== Contexto
La Escuela Carlos Condell de la Haza (G-8) es un establecimiento educacional que forma parte de la red de escuelas administradas por el Servicio Local de Educación Pública de Chinchorro (SLEP Chinchorro). Cuenta con infraestructura de red inalámbrica orientada a dar soporte tanto a las actividades pedagógicas de los docentes y sus estudiantes como a las labores administrativas de los funcionarios del establecimiento.

En el marco de los planes de mejoramiento del equipamiento tecnológico impulsados por el SLEP Chinchorro, el establecimiento ha recibido recientemente un nuevo lote de tablets de uso pedagógico, que se suman al parque existente compuesto por tablets y laptops. Esta ampliación del parque tecnológico de usuario final ha incrementado la demanda sobre la infraestructura de red, poniendo en evidencia las limitaciones del equipamiento instalado.

== Problema
La visita técnica del martes 09 de junio de 2026 permitió identificar las siguientes deficiencias en la infraestructura de red inalámbrica del establecimiento:

- *Zonas sin cobertura Wi-Fi:* Se detectaron sectores del establecimiento donde la señal inalámbrica es inexistente o insuficiente para operar de forma normal. Esto impide el uso efectivo de los dispositivos tecnológicos en dichas áreas, limitando el aprovechamiento del equipamiento disponible y restringiendo el desarrollo de actividades pedagógicas que requieren conectividad.

- *Equipo de enrutamiento principal obsoleto:* El router instalado corresponde a una generación anterior, con capacidades de procesamiento y de gestión de conexiones simultáneas insuficientes para la cantidad actual de dispositivos clientes. La reciente incorporación de nuevas tablets agrava esta situación, generando degradación del rendimiento y cortes de conectividad que afectan tanto a funcionarios como a docentes.

- *Puntos de acceso inalámbrico deteriorados:* Se identificaron tres AP/repetidores que presentan desgaste físico o fallas intermitentes, comprometiendo la calidad de la señal en las zonas que cubren. La falla total de cualquiera de estos equipos implicaría la pérdida de conectividad en los sectores que dependen de ellos, afectando directamente la continuidad operativa del establecimiento.

La combinación de estos factores configura un escenario de riesgo operativo que exige atención prioritaria para garantizar el normal funcionamiento de las labores pedagógicas y administrativas de la escuela.

#pagebreak()
= Objetivos
== Objetivo general
Mejorar y ampliar la infraestructura de red inalámbrica de la Escuela Carlos Condell de la Haza (G-8) mediante la renovación del equipamiento central y la expansión de la cobertura Wi-Fi, asegurando la continuidad operativa del establecimiento y el soporte adecuado al parque tecnológico actual y su crecimiento proyectado.

== Objetivos específicos
- *Modernizar la base actual:* Cambiar los equipos desgastados para asegurar una conexión rápida y estable en las oficinas y salas principales, permitiendo que funcionarios y docentes operen sin interrupciones y con la capacidad suficiente para soportar la totalidad de los dispositivos del establecimiento.
- *Ampliar el alcance:* Instalar nuevos puntos de acceso para dar cobertura Wi-Fi total a las zonas que hoy están desconectadas, habilitando el uso efectivo de los recursos tecnológicos en todo el establecimiento.
- *Renovar los AP deteriorados:* Reemplazar los tres puntos de acceso en mal estado para eliminar el riesgo de pérdida de conectividad en zonas críticas y garantizar la continuidad de las actividades de docentes y funcionarios.
- *Escalar la red:* Implementar un equipo de enrutamiento de mayor capacidad que soporte el volumen actual de dispositivos clientes y permita absorber futuras incorporaciones de equipamiento tecnológico sin degradación del servicio.

#pagebreak()
= Propuesta técnica
== Itemizado del Equipamiento
Para dar respuesta a las problemáticas identificadas, se propone la adquisición e instalación del siguiente equipamiento:

#tabla(
  columns: (auto, 1fr, auto, auto),
  ("#", "Descripción", "Cantidad", "Prioridad"),
  (
    ("1", "UDM-PRO — Router de alto rendimiento Unifi Dream Machine Pro, compatible con UNIFI.", "1", "Alta"),
    ("2", "U6-PRO — Access Point Indoor Wi-Fi 6 similar a UBIQUITI U6-PRO, compatible con UNIFI.", "4", "Alta"),
    ("3", "LOCO5AC — Antena PtP 5 GHz 13 dBi con RJ45 y PoE 24 V, similar a UBIQUITI LOCO 5AC (NS-5ACL).", "2", "Alta"),
    ("4", "UB-AM — Soporte universal abatible 50 cm para muro, similar a UBIQUITI UB-AM. (Uno por AP instalado.)", "2", "Alta"),
    ("5", "WUP-01 — Patchcord 10 cm CAT6 RJ45 blanco, similar a UBIQUITI WUP-01.", "40", "Media"),
    ("6", "UDC-0 — Cable directo 50 cm SFP+ 10 Gbps, similar a UBIQUITI UACC-DAC-SFP10-0.5M.", "1", "Media"),
    ("7", "PP624L — Patch panel 24 puertos RJ45 CAT6 UTP 1U certificado UL, similar a LINKMADE PP624L.", "1", "Media"),
    ("8", "RG8CH — PDU 8 tomas Schuko 10 A Rack 1U con interruptor y luz piloto, similar a LINKMADE RG8CH.", "1", "Media"),
    ("9", "RAP-1C — Tapa ciega 1U con apertura de cepillo para rack 19\", similar a LINKMADE RAP-1C.", "1", "Baja"),
  ),
)

#pagebreak()

== Diagrama Unilineal
La arquitectura propuesta contempla un diseño jerárquico. En el nivel central se instalará el nuevo router/firewall principal, conectado a la red WAN del establecimiento y al switch de distribución. En el nivel de acceso, los AP se distribuirán mediante cableado estructurado desde el switch, reduciendo al mínimo la dependencia de repetidores inalámbricos en cascada, los cuales degradan el rendimiento de la señal.

Los tres AP de reemplazo se ubicarán en las posiciones de los equipos deteriorados, garantizando la continuidad de la cobertura existente. Los AP adicionales se instalarán en los sectores sin cobertura identificados en la visita.

#aviso(tipo: "advertencia", titulo: "Diagrama pendiente", [El diagrama unilineal definitivo se incluirá en la siguiente versión de este informe, una vez completado el levantamiento de la infraestructura del establecimiento.])

== Diagrama de Cobertura
Durante la visita se identificaron visualmente las zonas sin cobertura Wi-Fi. El plano de cobertura definitivo se elaborará a partir de los planos del establecimiento y de los resultados del _site survey_, el cual determinará la ubicación óptima de los nuevos puntos de acceso para lograr cobertura continua en todos los sectores del edificio.

#aviso(tipo: "advertencia", titulo: "Plano pendiente", [El plano de cobertura Wi-Fi se incorporará en la siguiente versión del informe, previo levantamiento de planos y realización del _site survey_.])

#pagebreak()

= Costos estimados
Los valores presentados a continuación son referenciales y se basan en precios de mercado a la fecha del informe. Los montos definitivos estarán sujetos al proceso de adquisición que corresponda.

#tabla(
  columns: (auto, 1fr, auto, auto, auto),
  ("#", "Descripción", "Cant.", "Precio unit. (c/IVA)", "Total (c/IVA)"),
  (
    ("1", "UDM-PRO — Router Unifi Dream Machine Pro", "1", "$750.000", "$750.000"),
    ("2", "U6-PRO — AP Indoor Wi-Fi 6", "4", "$290.000", "$1.160.000"),
    ("4", "LOCO5AC — Antena PtP 5 GHz 13 dBi", "1", "$80.000", "$80.000"),
    ("5", "PP624L — Patch panel 24p RJ45 CAT6 UTP 1U", "1", "$38.000", "$38.000"),
    ("6", "RG8CH — PDU 8 tomas Schuko Rack 1U", "1", "$33.000", "$33.000"),
    ("7", "UDC-0 — Cable directo 50 cm SFP+ 10 Gbps", "1", "$29.000", "$29.000"),
    ("8", "RAP-1C — Tapa ciega 1U con cepillo para rack", "1", "$13.000", "$13.000"),
    ("9", "UB-AM — Soporte abatible para muro (por AP)", "Por definir", "$12.000", "Por definir"),
    ("10", "WUP-01 — Patchcord 10 cm CAT6 RJ45 blanco", "40", "$4.000", "$160.000"),
    ("", "*Subtotal (cantidades fijas)*", "", "", "*$1.973.000*"),
    ("", "*Total proyecto*", "", "", "*Por definir*"),
  ),
)

#aviso(tipo: "info", titulo: "Precios de Mercado", [Los costos expresados en esta tabla son precios de mercado obtenidos por un análisis de proveedores especializados en tecnología.])

#pagebreak()
= Conclusiones
La visita técnica realizada al establecimiento confirmó la existencia de deficiencias en la infraestructura de red inalámbrica que representan un riesgo concreto para la continuidad operativa. El crecimiento del parque tecnológico de usuario final —impulsado por la incorporación de nuevas tablets— ha superado la capacidad del equipamiento instalado, evidenciando la urgencia de una intervención oportuna.

La modernización del router principal y la renovación de los tres AP deteriorados constituyen acciones de carácter prioritario: su omisión puede derivar en interrupciones del servicio que afecten directamente a docentes y funcionarios en sus actividades cotidianas. La expansión de cobertura hacia las zonas actualmente sin señal complementa esta intervención, permitiendo el aprovechamiento efectivo de los recursos tecnológicos ya adquiridos por el establecimiento.

La red del establecimiento se encuentra en una fase de crecimiento activo junto con el parque de equipamiento de usuario final. Abordar este proyecto en el corto plazo permitirá dotar al establecimiento de una infraestructura dimensionada para soportar la demanda actual y con capacidad para absorber las incorporaciones futuras de dispositivos, sin comprometer la calidad del servicio prestado.

#pagebreak()
= Recomendaciones
#tabla-prioridad((
  ("1", "Reemplazar el router principal por equipo adquirido (Ubiquiti UDM Pro).", "Alta", "Unidad TI"),
  ("2", "Instalar nuevos AP Wi-Fi en las zonas sin cobertura identificadas.", "Alta", "Unidad TI"),
  ("3", "Renovar los tres AP Wi-Fi deteriorados en zonas críticas del establecimiento.", "Media", "Unidad TI"),

))
#pagebreak()

= Glosario y acrónimos
#tabla(
  columns: (auto, 1fr),
  ("Término", "Definición"),
  (
    ("AP", "Access Point (Punto de acceso inalámbrico): dispositivo que permite la conexión de equipos a una red Wi-Fi."),
    ("QoS", "Quality of Service (Calidad de Servicio): mecanismo que prioriza el tráfico de red para garantizar el rendimiento de aplicaciones críticas."),
    ("SLEP", "Servicio Local de Educación Pública."),
    ("TI", "Tecnologías de la Información."),
    ("WAN", "Wide Area Network (Red de Área Amplia): enlace de conectividad a Internet provisto por el ISP del establecimiento."),
    ("ISP", "Proveedor de Internet (Internet Service Provider)."),
  ),
)
#pagebreak()
#s-ficha(meta, rama-git: "doc/TI-INF-RED-2026-0039")
#pagebreak()
#s-versiones((
  ("v1.0.0", "2026-06-23", "Andres Cubillos Salazar", "Versión inicial. Cotización base de equipamiento sin instalación."),
))
#pagebreak()
/*#s-distribucion((
  ("Establecimiento", "Beneficiario", "Receptor principal"),
  ("Subdirección de Planificación y Control de Gestión", "Supervisión", "Copia informativa"),
  ("Unidad TI", "Custodia", "Archivo institucional"),
))
#pagebreak()
*/
