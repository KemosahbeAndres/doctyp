// TI-INF-SFW_2026-0002  ·  generado por doctyp
#import "lib.typ": *

#let meta = crear-meta((
  area: "TI", tipo: "INF", categoria: "RED",
  anio: 2026, correlativo: 39, version: "1.1", fecha-codigo: "20260623",
  tipo-largo: "Propuesta",
  titulo: "Propuesta de mejora y ampliación de infraestructura tecnológica",
  subtitulo: "Escuela Carlos Condell de la Haza (G-8)",
  estado: "BORRADOR", clasificacion: "INTERNO",
  autor: "Andrés Cubillos Salazar", cargo-autor: "Tecnico de Soporte Informático", correo-autor: "andres.cubillos@epchinchorro.cl",
))
#show: report.with(meta: meta)

#s-indice()
#pagebreak()

= Resumen ejecutivo
El presente informe tiene por objetivo *proponer una mejora y actualización tecnológica*, despues de una revisión del estado actual, de la infraestructura de red para la Escuela Carlos Condell de la Haza (G-8) garantizando la continuidad operativa del establecimiento ante el crecimiento de su parque tecnológico.

El diagnóstico realizado durante la *visita técnica del martes 09 de junio de 2026 identificó tres problemáticas* críticas:

1. Zonas del establecimiento sin cobertura Wi-Fi que impiden el uso efectivo de los dispositivos pedagógicos en esas áreas.
2. Router principal de generación antigua con capacidad insuficiente para la cantidad actual de dispositivos conectados, lo que genera cortes, lentitud y degradación de la conectividad a Internet.
3. Tres puntos de acceso Wi-Fi (AP) en estado de deterioro físico, cuya eventual falla total implicaría la pérdida de conectividad en sectores críticos. 

Estas deficiencias se agravan por la incorporación reciente de nuevas tablets de uso pedagógico, que han aumentado la demanda sobre una infraestructura no dimensionada para absorberla.

Frente a este escenario, *se propone un proyecto de provisión e instalación de equipamiento de red de nueva generación*. Esto incluye el reemplazo de los AP deteriorados, la cobertura de las zonas sin señal y la integración del router UDM-Pro y demás equipos ya adquiridos mediante el proyecto GORE (*BIP 40065439-0*). Dado que la Unidad TI no dispone del personal para ejecutar la instalación en el plazo requerido, se propone externalizar esta tarea a un proveedor especializado bajo supervisión técnica del área.

El costo referencial del equipamiento a adquirir, basado en precios de mercado a la fecha del informe, asciende a *\$1.954.000*, mientras que el costo de instalación (red, CCTV y proyectores) asciende a *\$3.884.100*, para un *total general de \$5.838.100*. Estos montos no incluyen el equipamiento ya financiado por el proyecto GORE. Como Unidad de Tecnologías de la Información le recomendamos realizar estas mejoras pues garantizarán una conectividad estable y dimensionada para el parque tecnológico actual y su crecimiento proyectado.

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
  caption: [Zonas sin cobertura Wi-Fi.]
)
#pagebreak()

#figure(
  image("/img-39/cobertura_actual.png", height: 8cm, fit: "contain"),
  caption: [Cobertura Wi-Fi actualmente.]
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
  caption: [Rack instalado por Mineduc.]
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

- *Renovar y ampliar la cobertura Wi-Fi:* Reemplazar los tres puntos de acceso en mal estado e instalar nuevos AP en las zonas sin señal, garantizando cobertura total del establecimiento y eliminando el riesgo de pérdida de conectividad en zonas críticas.

- *Escalar la red:* Integrar el router Ubiquiti UDM-Pro (disponible mediante el proyecto GORE BIP 40065439-0) como equipo central de la red, garantizando la capacidad necesaria para el volumen actual de dispositivos y las incorporaciones futuras.

- *Externalizar la instalación:* Contratar a un proveedor especializado para ejecutar la instalación completa del equipamiento, reduciendo los tiempos de implementación y liberando a la Unidad TI de tareas operativas que exceden su capacidad disponible.

#pagebreak()
= Propuesta técnica
== Alcance del Proyecto: Provisión e Instalación
Este proyecto contempla tanto la *provisión* (adquisición) del equipamiento detallado en las secciones siguientes, como su *instalación* completa en las dependencias del establecimiento.

Dado que la Unidad de Tecnologías de la Información no cuenta con los recursos de personal ni el tiempo disponible para ejecutar la instalación en el plazo requerido, se propone *externalizar la instalación* mediante la contratación de un proveedor especializado que ejecute el trabajo de forma oportuna y bajo supervisión técnica de la Unidad TI.

La supervisión técnica, la validación de la configuración y la recepción conforme del proyecto quedarán a cargo de la Unidad de Tecnologías de la Información del SLEP Chinchorro.

== Equipamiento a Adquirir
Para dar respuesta a las problemáticas identificadas, se propone la adquisición e instalación del siguiente equipamiento:

#tabla(
  columns: (auto, 1fr, auto),
  ("#", "Descripción", "Cantidad"),
  (
    ("1", "Access Point Indoor Wi-Fi 6 5/2,4 GHz, 1×Gigabit-RJ45 PoE+, compatible con UNIFI, similar a UBIQUITI U6-PRO.", "3"),
    ("2", "Access Point Exterior Wi-Fi 6 5/2,4 GHz, 1×Gigabit-RJ45 PoE+, compatible con UNIFI, similar a UBIQUITI U6-MESH-PRO.", "1"),
    ("3", "Antena PtP 5GHz 13dBi Gigabit PoE24V (airMAXac compatible) similar a UBIQUITI LOCO 5AC.", "2"),
    ("4", "Inyector PoE 24VDC 7W Gigabit 0,3A (cable poder trebol incluido) similar a UBIQUITI POE-24-7W.", "2"),
    ("5", "Cable directo 50cm SFP+ 10 Gbps, similar a UBIQUITI UACC-DAC-SFP10-0.5M.", "2"),
    ("6", "Soporte universal abatible 50cm para muro, similar a UBIQUITI UB-AM.", "2"),
    ("7", "Patchcord 10cm CAT6 RJ45 blanco, similar a UBIQUITI WUP-01.", "40"),
    ("8", "Tapa negra 1U con apertura de cepillo para rack 19\", similar a LINKMADE RAP-1C.", "1"),
    ("9", "Patch panel 24 puertos RJ45 CAT6 UTP 1U certificado UL, similar a LINKMADE PP624L.", "1"),
    ("10", "Cámara IP de seguridad 8MP PoE IP67 IK10, similar a DAHUA DH-IPC-HFW5859T (compatible con el NVR y las cámaras aportadas por el proyecto GORE).", "1"),
    ("11", "Cable HDMI 3 mts 4K 2.0 blindado", "10"),
  ),
)

#pagebreak()

== Equipamiento Aportado por Proyecto GORE (BIP 40065439-0)
El siguiente equipamiento ya fue adquirido en el marco del proyecto del Gobierno Regional (GORE), código BIP 40065439-0, y será incorporado a este proyecto sin costo adicional:

#tabla(
  columns: (auto, 1fr, auto),
  ("#", "Descripción", "Cantidad"),
  (
    ("1", "Access Point Indoor Wi-Fi 6, UBIQUITI U6-PRO.", "1"),
    ("2", "Access Point Exterior Wi-Fi 6, UBIQUITI UAP-AC-MESH-PRO.", "1"),
    ("3", "Router Unifi Dream Machine Pro (UDM-Pro).", "1"),
    ("4", "UPS de respaldo 1KVA, ENERSAVE ESOL RTH-C 1KVA.", "1"),
    ("5", "Switch Ubiquiti 16 puertos PoE.", "1"),
    ("6", "Cámara IP de seguridad, DAHUA DH-IPC-HFW5859T.", "4"),
    ("7", "Grabador NVR con disco duro (HDD), DAHUA DHI-NVR4108HS-8P-4KS3.", "1"),
    ("8", "Proyector ultracorto Epson EB-685W con Wi-Fi.", "10"),
  ),
)

#aviso(tipo: "info", titulo: "Equipamiento GORE", [Los equipos listados en esta tabla no se incluyen en el costo estimado del proyecto, ya que fueron financiados mediante el proyecto GORE BIP 40065439-0 y están disponibles para su instalación.])

== Instalación de la Infraestructura de Red
El proveedor contratado ejecutará los siguientes trabajos bajo supervisión técnica de la Unidad TI:

- Montaje físico del equipamiento activo en rack principal.
- Tendido y certificación de cableado estructurado a los puntos de acceso definidos en la topología.
- Instalación y reemplazo de los AP Indoor en las zonas identificadas en los diagramas.
- Instalación de los AP Exterior en las zonas identificadas en los diagramas.
- Despliegue y alineación de antenas PtP para los sectores sin cableado disponible.
- Organización y etiquetado del cableado existente en rack principal mediante el patch panel.
- Pruebas de funcionamiento y entrega formal a la Unidad TI.

#aviso(tipo: "info", titulo: "Configuración de los equipos", [
  La Unidad de Tecnologias de la Información del SLEP Chinchorro se encargara de la configuración de los equipos instalados (UDM-Pro, switch, UPS, AP, proyectores) al sistema UNIFI y/o a la red de datos del establecimiento.
])

=== Cableado y Canalización
Todo el cableado de cámaras, puntos de acceso, antenas y proyectores (energía y video) debe quedar canalizado con tubos metálicos EMT en exteriores y canaleta blanca en interiores, según las normas de canalizado eléctrico y de corrientes débiles vigentes. Según el diseño de red (Unifi Design), la interconexión de cámaras, puntos de acceso y antenas requiere las siguientes cantidades apróximadas de cable UTP Cat6 LSZH (libre de halógeno) 100% cobre y de canalización metálica EMT:

#tabla(
  columns: (auto, 1fr, auto),
  ("#", "Descripción", "Cantidad"),
  (
    ("1", "Cable UTP Cat6 LSZH (libre de halógeno) 100% cobre", "220 mts."),
    ("2", "Canalización metálica EMT con accesorios (uniones, conectores, fijaciones)", "180 mts."),
  ),
)

#aviso(tipo: "warning", titulo: "Separación de canalizaciones", [
  La canalización de datos (cámaras, AP, antenas) y la de energía/video de los proyectores deben tenderse en tubos o canaletas independientes, evitando compartir un mismo ducto entre corrientes fuertes y corrientes débiles.
])

=== Topología de Red
La arquitectura propuesta reemplaza la dependencia de repetidores inalámbricos en cascada —principal causa de la degradación actual— por un diseño donde cada AP se conecta al switch mediante cableado estructurado. 

El UDM-PRO centraliza la gestión de toda la red desde una única consola UNIFI, lo que simplifica la operación y permite detectar fallas con rapidez. Las antenas PtP LOCO5AC resuelven los sectores de dificil acceso para cablear y los AP exteriores U6-MESH-PRO eliminan las zonas sin cobertura identificadas en la visita.

El siguiente diagrama ilustra la topología lógica de la red propuesta:

#figure(
  image("img-39/topologia_propuesta.png", height: 10cm, fit:"contain"),
  caption: [Topología de red propuesta]
)

#pagebreak()

=== Diagrama de Cobertura Wi-Fi
El diagrama de cobertura permite validar que la disposición propuesta de los AP elimina las zonas sin señal detectadas durante la visita, garantizando conectividad en todos los sectores del establecimiento. 

La cobertura estimada en banda 5 GHz (utilizada para actividades pedagógicas) confirma que el diseño alcanza los espacios donde hoy no existe señal o esta es insuficiente:

#figure(
  image("img-39/cobertura_wifi_5g.png", height: 10cm),
  caption: [Cobertura Wi-Fi estimada — banda 5 GHz]
)

#pagebreak()

=== Distribución en Gabinetes
Como parte de la propuesta, se establece una separación clara de responsabilidades entre los dos gabinetes del establecimiento. *El gabinete de Mineduc albergará exclusivamente el módem del Proyecto CpE2030 del Mineduc*, sin ningún otro equipo ni cableado adicional; su función es únicamente proveer el enlace de Internet institucional y no debe intervenirse ni compartirse con equipamiento de la red interna del establecimiento. Todo el equipamiento activo y el cableado estructurado de la red interna —incluyendo el UDM-PRO, el switch, los patch panels y la UPS— se centralizarán en el rack principal, que operará como el único punto de gestión y distribución de la red. Esta centralización simplifica el mantenimiento, reduce los puntos de falla y permite al personal de TI intervenir la infraestructura desde un único lugar.

El diagrama siguiente muestra la distribución propuesta de los equipos dentro del rack principal:


#figure(
  image("img-39/rack_propuesto_1.1.png", height: 14cm),
  caption: [Distribución planificada en Rack Principal]
)

#pagebreak()


== Instalación de Cámaras de seguridad
La ubicación de las 5 cámaras IP DAHUA DH-IPC-HFW5859T aportadas se definió priorizando los accesos principales, los pasillos de mayor tránsito y los sectores donde se concentra equipamiento tecnológico sensible, con el objetivo de resguardar tanto la integridad de los usuarios como la del parque tecnológico del establecimiento. Cada cámara se conectará mediante cableado estructurado CAT6 al grabador NVR DAHUA DHI-NVR4108HS-8P-4KS3, que centralizará el almacenamiento y la gestión del sistema de vigilancia. La disposición final de los puntos de cámara, validada junto a la dirección del establecimiento, se ilustra en el siguiente diagrama:

#figure(
  image("img-39/distribucion_camaras.png"),
  caption: [Distribución de cámaras de seguridad]
)

== Instalación de Proyectores

=== Tareas
Cada proyector, al ser de tiro ultracorto, se monta en altura sobre la pizarra y no cuenta en esa posición con punto eléctrico ni punto de video disponible, por lo que ambos deben tenderse de forma canalizada desde el punto más cercano existente. Esta instalación incluye la fijación estructural del equipo, el punto de energía y el punto de video HDMI; no incluye mobiliario docente ni el equipo del proyector, aportado por el proyecto GORE.

Por tratarse de instalaciones más sensibles que el resto del proyecto, deben cumplir como mínimo:

- *Energía:* circuito dedicado con protección termomagnética y diferencial, puesta a tierra verificada, conductor libre de halógeno y enchufe embutido con placa homologada; sin empalmes expuestos.
- *Video:* canalización separada de la línea de energía para evitar interferencia electromagnética, conector/keystone certificado, respeto del radio de curvatura mínimo del cable y verificación de señal (sin pérdida ni parpadeo) antes de la entrega.

#aviso(tipo: "danger", titulo: "Fijación en muros de material ligero", [
  Los muros del establecimiento donde se instalarán los proyectores pueden ser de adobe, madera, vulcanita u otro material ligero, por lo que no admiten un anclaje directo y firme del equipo ni de su soporte.

  El proveedor deberá fabricar e instalar, según las condiciones particulares de cada sala, una placa metálica o de madera pasante que sujete el muro por ambas caras (interior y exterior), un soporte de techo fabricado en metal que sostenga el equipo de forma segura si la estructura del edificio lo permite o cualquier tipo de anclaje que asegure la sujeción y evite posibles caidas o desprendimiento de los equipos.

  *La solución estructural aplicada en cada sala queda a criterio y responsabilidad del proveedor al momento de la instalación.*
])


=== Distribución

Los 10 proyectores ultracortos Epson EB-685W con Wi-Fi aportados por el proyecto GORE se distribuirán en las salas de clases definidas por la dirección del establecimiento, priorizando aquellas con mayor uso pedagógico diario. Dada su naturaleza de tiro ultracorto, cada equipo se monta en altura, sobre la pizarra de la sala respectiva, lo que minimiza las sombras proyectadas por el docente y optimiza el aprovechamiento del espacio disponible. La conectividad de red de cada proyector se gestionará vía Wi-Fi según los parámetros definidos por la Unidad TI. Las particularidades constructivas de las salas —detalladas en la sección "Trabajos a Realizar"— condicionan tanto la fijación del equipo como el tendido de energía y HDMI hasta su ubicación final. La disposición específica por sala se muestra en el siguiente diagrama:

#figure(
  image("img-39/distribucion-proyectores.png", height: 8cm),
  caption: [Distribución de proyectores]
)

=== Posición
Los proyectores deben quedar ubicados según la ilustración a continuación. El punto de conexión de video para el profesor debe quedar en una ubicación cómoda para él y que no interfiera con el desarrollo de sus clases. Esta imagen es solo de referencia pues cada sala de clases es diferente.

#figure(
  image("img-39/ilustracion_proyector.png", height: 9cm),
  caption: [Ilustración generada con Nano Banana 2.]
)


#pagebreak()

= Costos estimados
Los valores presentados a continuación son referenciales y se basan en precios de mercado a la fecha del informe. Los montos definitivos estarán sujetos al proceso de adquisición y contratación que corresponda. El presupuesto se organiza en dos componentes: el *costo de equipamiento* a adquirir y el *costo de instalación* (materiales y mano de obra) necesario para dejar el proyecto completamente operativo.

== Costo de Equipamiento
#tabla(
  columns: (auto, 1fr, auto, auto, auto),
  ("#", "Descripción", "Cant.", "Precio unit. (c/IVA)", "Total (c/IVA)"),
  (
    ("1", "AP Indoor Wi-Fi 6", "3", "$290.000", "$870.000"),
    ("2", "AP Exterior Wi-Fi 6", "1", "$381.000", "$381.000"),
    ("3", "Antena PtP 5 GHz 13 dBi", "2", "$80.000", "$160.000"),
    ("4", "Inyector PoE 24VDC Gigabit 802.3af", "2", "$15.000", "$30.000"),
    ("5", "Cable directo 50 cm SFP+ 10 Gbps", "2", "$29.000", "$58.000"),
    ("6", "Soporte abatible 50 cm para muro", "2", "$12.000", "$24.000"),
    ("7", "Patchcord 10 cm CAT6 RJ45 blanco", "40", "$4.000", "$160.000"),
    ("8", "Tapa negra 1U con cepillo para rack 19\"", "1", "$13.000", "$13.000"),
    ("9", "Patch panel 24p RJ45 CAT6 UTP 1U certificado UL", "1", "$38.000", "$38.000"),
    ("10", "Cámara IP interior 8MP PoE IP67 IK10", "1", "$170.000", "$170.000"),
    ("11", "Cable HDMI 3 mts 4K 2.0 blindado", "10", "$5.000", "$50.000"),
    ("", "SUBTOTAL", "", "", "*$1.954.000*"),
  ),
)

#aviso(tipo: "info", titulo: "Precios de Mercado", [Los costos expresados en esta tabla son precios de mercado obtenidos por un análisis de proveedores especializados en tecnología como LinkStore (https://www.lk.cl).])

#pagebreak()

== Costo de Instalación
La instalación fue dimensionada según el diseño de red elaborado en Unifi Design, que determinó los metrajes de cableado y canalización requeridos, y según estimaciones de la Unidad TI para la mano de obra y los puntos de conexión de los proyectores:

#tabla-kv((
  ("Canalización y cableado", "$3.400.000"),
  ("Instalación de equipos de Red", "$360.000"),
  ("Instalación sistema de videovigilancia ", "$240.000"),
  ("Montaje de proyectores", "$410.000"),
  ("Puntos eléctricos y de video para proyectores", "$700.000"),
  ("*SUBTOTAL*", "*$5.110.000*"),
))

== Costo Total del Proyecto
#tabla(
  columns: (auto, 1fr, auto),
  ("#", "Item", "Total (c/IVA)"),
  (
    ("1", "Costo de equipamiento", "$1.954.000"),
    ("2", "Costo de instalación (red, CCTV y proyectores)", "$5.110.000"),
    ("", "*Total general del proyecto*", "*$7.064.000*"),
  ),
)

#aviso(tipo: "warning", titulo: "Solicitud de Compra", [Antes de realizar o subir una solicitud de compra por favor solicitar a la Unidad de Tecnologías de la Información las Especificaciones Técnicas de los items a travez del correo: *soporte.informatica\@epchinchorro.cl*.])

#pagebreak()
= Conclusiones
La red inalámbrica de la Escuela Carlos Condell de la Haza presenta deficiencias concretas que ya están afectando la operación del establecimiento: zonas sin cobertura, un router que no da abasto con los dispositivos actuales y tres AP en mal estado que pueden fallar en cualquier momento. La incorporación de nuevas tablets no hizo más que acelerar un problema que el equipamiento instalado no está en condiciones de absorber.

La propuesta presentada en este informe resuelve cada uno de estos puntos mediante un proyecto de *provisión e instalación* que combina el equipamiento a adquirir con los equipos ya disponibles del proyecto GORE (BIP 40065439-0). La solución centraliza la gestión en un único rack principal y libera el gabinete de Mineduc de cualquier uso distinto al enlace institucional. El costo total referencial del proyecto asciende a \$5.838.100, compuesto por \$1.954.000 de equipamiento y \$3.884.100 de instalación (red, CCTV y proyectores, incluyendo materiales de cableado y canalización, mano de obra de montaje y puesta en servicio, y los puntos eléctricos y HDMI dedicados de cada proyector), y contempla además la organización del cableado mediante un patch panel, aspecto que hoy también representa un riesgo operativo.

Externalizar la instalación es la vía correcta para ejecutar este proyecto en el menor tiempo posible: permite aprovechar el equipamiento GORE ya disponible, reduce la carga operativa sobre la Unidad TI y garantiza una implementación técnica que la dotación actual de personal no puede absorber sin afectar otras labores del área.

#pagebreak()
= Recomendaciones
#tabla-prioridad((
  ("1", "Contratar proveedor especializado para la provisión e instalación del equipamiento propuesto.", "Alta", "Unidad TI / Adquisiciones"),
  ("2", "Integrar el equipamiento GORE (UDM-Pro, switch, UPS, AP) al sistema UNIFI durante la instalación.", "Alta", "Proveedor / Unidad TI"),
  ("3", "Instalar AP Wi-Fi en las zonas sin cobertura y reemplazar los tres AP deteriorados.", "Alta", "Proveedor / Unidad TI"),
  ("4", "Organizar el cableado del gabinete principal mediante la instalación del patch panel.", "Media", "Proveedor / Unidad TI"),
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

