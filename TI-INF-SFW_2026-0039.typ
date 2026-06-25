// TI-INF-SFW_2026-0002  ·  generado por doctyp
#import "lib.typ": *

#let meta = crear-meta((
  area: "TI", tipo: "INF", categoria: "RED",
  anio: 2026, correlativo: 39, version: "1.1", fecha-codigo: "20260623",
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
El presente informe tiene por objetivo *proponer una mejora y actualización tencológica*, despues de una revisión del estado actual, de la infraestructura de red para la Escuela Carlos Condell de la Haza (G-8) garantizando la continuidad operativa del establecimiento ante el crecimiento de su parque tecnológico.

El diagnóstico realizado durante la *visita técnica del martes 09 de junio de 2026 identificó tres problemáticas* críticas:

1. Zonas del establecimiento sin cobertura Wi-Fi que impiden el uso efectivo de los dispositivos pedagógicos en esas áreas.

2. Router principal de generación antigua con capacidad insuficiente para la cantidad actual de dispositivos conectados, lo que genera cortes, lentitud y degradación de la conectividad a Internet.

3. Tres puntos de acceso Wi-Fi (AP) en estado de deterioro físico, cuya eventual falla total implicaría la pérdida de conectividad en sectores críticos. 

Estas deficiencias se agravan por la incorporación reciente de nuevas tablets de uso pedagógico, que han aumentado la demanda sobre una infraestructura no dimensionada para absorberla.

Frente a este escenario, *se propone una renovación de los equipos de red actuales por unos equipos de nueva generación y de alto rendimiento*. También será necesario el reemplazo de los tres AP deteriorados y la instalación de un nuevo punto de acceso Wi-Fi para eliminar las zonas sin cobertura.

El costo referencial del equipamiento, basado en precios de mercado a la fecha del informe, asciende a *\$3.445.000*. Como Unidad de Tecnologías de la Información le recomendamos realizar estas mejoras pues garantizarán una conectividad estable y dimensionada para el parque tecnológico actual y su crecimiento proyectado.

#pagebreak()
= Antecedentes
== Contexto
La Escuela Carlos Condell de la Haza (G-8) es un establecimiento educacional que forma parte de la red de escuelas administradas por el Servicio Local de Educación Pública de Chinchorro (SLEP Chinchorro). Cuenta con infraestructura de red inalámbrica orientada a dar soporte tanto a las actividades pedagógicas de los docentes y sus estudiantes como a las labores administrativas de los funcionarios del establecimiento.

En el marco de los planes de mejoramiento del equipamiento tecnológico impulsados por el SLEP Chinchorro, el establecimiento ha recibido recientemente un nuevo lote de tablets de uso pedagógico, que se suman al parque existente compuesto por tablets y laptops. Esta ampliación del parque tecnológico de usuario final ha incrementado la demanda sobre la infraestructura de red, poniendo en evidencia las limitaciones del equipamiento instalado.

== Problema
La visita técnica del martes 09 de junio de 2026 permitió identificar las siguientes deficiencias en la infraestructura de red inalámbrica del establecimiento:

=== Zonas sin cobertura Wi-Fi
Se detectaron sectores del establecimiento donde la señal inalámbrica es inexistente o insuficiente para operar de forma normal. Esto impide el uso efectivo de los dispositivos tecnológicos en dichas áreas, limitando el aprovechamiento del equipamiento disponible y restringiendo el desarrollo de actividades pedagógicas que requieren conectividad.

#figure(
  image("/img-39/zonas_sin_cobertura.png", height: 8cm, fit: "contain"),
  caption: [Zonas sin cobertura Wi-Fi]
)
#pagebreak()

#figure(
  image("/img-39/cobertura_actual.png", height: 8cm, fit: "contain"),
  caption: [Cobertura Wi-Fi actualmente]
)

=== Equipo de enrutamiento principal obsoleto 
El router instalado corresponde a una generación anterior, con capacidades de procesamiento y de gestión de conexiones simultáneas insuficientes para la cantidad actual de dispositivos clientes. La reciente incorporación de nuevas tablets agrava esta situación, generando degradación del rendimiento y cortes de conectividad que afectan tanto a funcionarios como a docentes.

#figure(
  image("/img-39/rack principal.jpeg", height: 10cm),
  caption: [Rack Principal de la Escuela.]
)
#pagebreak()

#figure(
  image("/img-39/rack mineduc.jpeg", height:8cm),
  caption: [Rack Internet Mineduc.]
)

=== Puntos de acceso inalámbrico deteriorados
Se identificaron tres AP/repetidores que presentan desgaste físico o fallas intermitentes, comprometiendo la calidad de la señal en las zonas que cubren. La falla total de cualquiera de estos equipos implicaría la pérdida de conectividad en los sectores que dependen de ellos, afectando directamente la continuidad operativa del establecimiento.

#figure(
  image("img-39/consola_unifi.png", height: 8cm),
  caption: [Consola Unifi con listado de equipos.]
)

La combinación de estos factores configura un escenario de riesgo operativo que exige atención prioritaria para garantizar el normal funcionamiento de las labores pedagógicas y administrativas de la escuela.


#pagebreak()
= Objetivos
Considerando las deficienas encontradas en la infraestructura de red y para asegurar la continuidad operativa del establecimiento con su creciente parque tecnológico, se pueden establecer los siguientes objetivos:

== Objetivo general
Mejorar y ampliar la infraestructura de red inalámbrica de la Escuela Carlos Condell de la Haza (G-8) mediante la renovación del equipamiento central y la expansión de la cobertura Wi-Fi.

== Objetivos específicos

- *Renovar los AP deteriorados:* Reemplazar los tres puntos de acceso en mal estado para eliminar el riesgo de pérdida de conectividad en zonas críticas y garantizar la continuidad de las actividades de docentes y funcionarios.

- *Ampliar el alcance:* Instalar nuevos puntos de acceso para dar cobertura Wi-Fi total a las zonas que hoy están desconectadas.

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
    ("2", "U6-PRO — Access Point Indoor Wi-Fi 6 5/2,4 GHz, 1×1000-RJ45 PoE+, compatible con UNIFI, similar a UBIQUITI U6-PRO.", "4", "Alta"),
    ("3", "Access Point Exterior Wi-Fi 6 5/2,4 GHz, 1×1000-RJ45 PoE+, compatible con UNIFI, similar a UBIQUITI U6-MESH-PRO.", "2", "Alta"),
    ("4", "Antena PtP 5 GHz 13 dBi, 1×1000-RJ45, PoE 24 V, similar a UBIQUITI LOCO 5AC (NS-5ACL).", "2", "Alta"),
    ("5", "Inyector PoE 48 VDC 15,3 W 0,32 A Gigabit 802.3af, requiere cable Trébol C5, similar a UBIQUITI.", "2", "Alta"),
    ("6", "UPS 2200 VA, 1200 W, 2×9 Ah, 130WH, 2×C13, 4×IH-Chile, 1×C14, AVR, similar a FORZA FX-2200LCD-C.", "1", "Alta"),
    ("7", "Cable directo 50 cm SFP+ 10 Gbps, similar a UBIQUITI UACC-DAC-SFP10-0.5M.", "2", "Media"),
    ("8", "Soporte universal abatible 50 cm para muro, similar a UBIQUITI UB-AM.", "2", "Media"),
    ("9", "Patchcord 10 cm CAT6 RJ45 blanco, similar a UBIQUITI WUP-01.", "40", "Media"),
    ("10", "Tapa negra 1U con apertura de cepillo para rack 19\", similar a LINKMADE RAP-1C.", "1", "Baja"),
    ("11", "PP624L — Patch panel 24 puertos RJ45 CAT6 UTP 1U certificado UL, similar a LINKMADE PP624L.", "1", "Media"),
  ),
)

El patch panel responde al estado del gabinete secundario del establecimiento, donde la ausencia de un punto de terminación estructurado genera un cableado desordenado que dificulta la identificación de conexiones y eleva el riesgo de errores en cualquier intervención de mantenimiento. Su instalación permitirá organizar y etiquetar correctamente los cables del nivel de acceso, facilitando la operación y el soporte futuro de la red.

#pagebreak()

== Topología de Red
La arquitectura propuesta reemplaza la dependencia de repetidores inalámbricos en cascada —principal causa de la degradación actual— por un diseño donde cada AP se conecta al switch mediante cableado estructurado. El UDM-PRO centraliza la gestión de toda la red desde una única consola UNIFI, lo que simplifica la operación y permite detectar fallas con rapidez. Las antenas PtP LOCO5AC resuelven los sectores sin cableado disponible y los AP exteriores U6-MESH-PRO eliminan las zonas sin cobertura identificadas en la visita.

El siguiente diagrama ilustra la topología lógica y física de la red propuesta:

#figure(
  image("img-39/topologia_propuesta.png", height: 10cm, fit:"contain"),
  caption: [Topología de red propuesta]
)
#pagebreak()

== Diagrama de Cobertura
El diagrama de cobertura permite validar que la disposición propuesta de los AP elimina las zonas sin señal detectadas durante la visita, garantizando conectividad en todos los sectores del establecimiento. La cobertura estimada en banda 5 GHz —la utilizada prioritariamente para actividades pedagógicas— confirma que el diseño alcanza los espacios donde hoy no existe señal o esta es insuficiente:

#figure(
  image("img-39/cobertura_wifi_5g.png", height: 10cm),
  caption: [Cobertura Wi-Fi estimada — banda 5 GHz]
)

#pagebreak()

== Distribución en Gabinetes
Como parte de la propuesta, se establece una separación clara de responsabilidades entre los dos gabinetes del establecimiento. *El gabinete de Mineduc albergará exclusivamente el módem del Proyecto CpE2030 del Mineduc*, sin ningún otro equipo ni cableado adicional; su función es únicamente proveer el enlace de Internet institucional y no debe intervenirse ni compartirse con equipamiento de la red interna del establecimiento. Todo el equipamiento activo y el cableado estructurado de la red interna —incluyendo el UDM-PRO, el switch, los patch panels y la UPS— se centralizarán en el rack principal, que operará como el único punto de gestión y distribución de la red. Esta centralización simplifica el mantenimiento, reduce los puntos de falla y permite al personal de TI intervenir la infraestructura desde un único lugar.

El diagrama siguiente muestra la distribución propuesta de los equipos dentro del rack principal:

#figure(
  image("img-39/distribucion_rack.png", height: 14cm),
  caption: [Distribución planificada en Rack Principal]
)

#pagebreak()

= Costos estimados
Los valores presentados a continuación son referenciales y se basan en precios de mercado a la fecha del informe. Los montos definitivos estarán sujetos al proceso de adquisición que corresponda.

#tabla(
  columns: (auto, 1fr, auto, auto, auto),
  ("#", "Descripción", "Cant.", "Precio unit. (c/IVA)", "Total (c/IVA)"),
  (
    ("1", "Router Unifi Dream Machine Pro", "1", "$750.000", "$750.000"),
    ("2", "AP Indoor Wi-Fi 6", "4", "$290.000", "$1.160.000"),
    ("3", "AP Exterior Wi-Fi 6", "2", "$381.000", "$762.000"),
    ("4", "Antena PtP 5 GHz 13 dBi", "2", "$80.000", "$160.000"),
    ("5", "Inyector PoE 48 VDC Gigabit 802.3af", "2", "$15.000", "$30.000"),
    ("6", "UPS 2200 VA / 1200 W AVR", "1", "$290.000", "$290.000"),
    ("7", "Cable directo 50 cm SFP+ 10 Gbps", "2", "$29.000", "$58.000"),
    ("8", "Soporte abatible 50 cm para muro", "2", "$12.000", "$24.000"),
    ("9", "Patchcord 10 cm CAT6 RJ45 blanco", "40", "$4.000", "$160.000"),
    ("10", "Tapa negra 1U con cepillo para rack 19\"", "1", "$13.000", "$13.000"),
    ("11", "Patch panel 24p RJ45 CAT6 UTP 1U certificado UL", "1", "$38.000", "$38.000"),
    ("", "*Total proyecto*", "", "", "*$3.445.000*"),
  ),
)

#aviso(tipo: "info", titulo: "Precios de Mercado", [Los costos expresados en esta tabla son precios de mercado obtenidos por un análisis de proveedores especializados en tecnología.])

#aviso(tipo: "warning", titulo: "Solicitud de Compra", [Antes de realizar o subir una solicitud de compra por favor solicitar a la Unidad de Tecnologías de la Información las Especificaciones Técnicas de los items a travez del correo: *soporte.informatica\@epchinchorro.cl*.])

#pagebreak()
= Conclusiones
La red inalámbrica de la Escuela Carlos Condell de la Haza presenta deficiencias concretas que ya están afectando la operación del establecimiento: zonas sin cobertura, un router que no da abasto con los dispositivos actuales y tres AP en mal estado que pueden fallar en cualquier momento. La incorporación de nuevas tablets no hizo más que acelerar un problema que el equipamiento instalado no está en condiciones de absorber.

La propuesta presentada en este informe resuelve cada uno de estos puntos con equipamiento de nueva generación, centraliza la gestión en un único rack principal y libera el gabinete de Mineduc de cualquier uso distinto al enlace institucional. El costo total referencial asciende a \$3.445.000 y contempla además la organización del cableado mediante un patch panel, aspecto que hoy también representa un riesgo operativo.

Ejecutar este proyecto en el corto plazo es la acción correcta: los equipos actuales no tienen margen de mejora y cualquier falla adicional tendrá impacto directo en docentes y funcionarios.

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
#s-ficha(meta)
#pagebreak()
#s-versiones((
  ("v1.1", "2026-06-25", "Andres Cubillos Salazar", "Ampliación del proyecto a provisión e instalación."),
  ("v1.0", "2026-06-23", "Andres Cubillos Salazar", "Versión inicial. Cotización base de equipamiento sin instalación."),
))
#pagebreak()

#s-distribucion((
  ("Establecimiento", "Beneficiario", "Receptor principal"),
  ("Subdirección de Planificación y Control de Gestión", "Supervisión", "Copia informativa"),
  ("Unidad TI", "Custodia", "Archivo institucional"),
))

