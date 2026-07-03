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

El costo referencial del equipamiento a adquirir, basado en precios de mercado a la fecha del informe, asciende a *\$1.888.811*, mientras que el costo de instalación (cableado, canalización, mano de obra y puntos eléctricos/HDMI de los proyectores) asciende a *\$4.698.100*, para un *total general de \$6.586.911*. Estos montos no incluyen el equipamiento ya financiado por el proyecto GORE. Como Unidad de Tecnologías de la Información le recomendamos realizar estas mejoras pues garantizarán una conectividad estable y dimensionada para el parque tecnológico actual y su crecimiento proyectado.

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
    ("10", "Cámara IP de seguridad interior 5MP, PoE, IP67, IK10, similar a DAHUA DH-IPC-HFW5859T (compatible con el NVR y las cámaras aportadas por el proyecto GORE).", "1"),
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
    ("6", "Cámara IP de seguridad interior, DAHUA DH-IPC-HFW5859T.", "4"),
    ("7", "Grabador NVR con disco duro (HDD), DAHUA DHI-NVR4108HS-8P-4KS3.", "1"),
    ("8", "Proyector ultracorto Epson EB-685W con Wi-Fi.", "10"),
  ),
)

#aviso(tipo: "info", titulo: "Equipamiento GORE", [Los equipos listados en esta tabla no se incluyen en el costo estimado del proyecto, ya que fueron financiados mediante el proyecto GORE BIP 40065439-0 y están disponibles para su instalación.])

== Trabajos a Realizar
El proveedor contratado ejecutará los siguientes trabajos bajo supervisión técnica de la Unidad TI:

=== Red de datos e infraestructura Wi-Fi
- Montaje físico del equipamiento activo (UDM-Pro, switch, UPS y patch panel) en rack principal.
- Tendido y certificación de cableado estructurado CAT6 a los puntos de acceso definidos en la topología.
- Instalación de AP Indoor en las zonas sin cobertura identificadas.
- Reemplazo de los tres AP Indoor deteriorados.
- Instalación del AP Exterior en la zona exterior identificada.
- Despliegue y alineación de antenas PtP para los sectores sin cableado disponible.
- Integración de los equipos aportados por el proyecto GORE (UDM-Pro, switch, UPS, AP) al sistema UNIFI.
- Organización y etiquetado del cableado existente en rack principal mediante el patch panel.
- Pruebas de funcionamiento y entrega formal a la Unidad TI.

=== Sistema de vigilancia
- Instalación de 4 cámaras IP en los puntos definidos por la Unidad TI.
- Tendido de cableado de red CAT6 desde el grabador NVR a cada cámara.
- Instalación y configuración del grabador NVR con disco duro (HDD).

=== Proyectores de sala
- Instalación de 10 proyectores ultracortos Epson EB-685W con Wi-Fi.
- Fabricación e instalación del sistema de fijación estructural del proyector en cada sala, conforme a lo indicado en el aviso siguiente.
- Instalación integral (canalizada) de cableado HDMI y de energía eléctrica desde el punto de alimentación más cercano hasta la ubicación del proyector sobre la pizarra, dado que al ser equipos de tiro ultracorto se montan en altura y no cuentan con dichos puntos disponibles en esa posición.
- Tendido y certificación de punto de red CAT6 por sala de proyección (donde el equipo lo requiera).
- Configuración de conectividad de red de los proyectores según los parámetros de la Unidad TI.

#aviso(tipo: "warning", titulo: "Fijación en muros de material ligero", [Los muros del establecimiento donde se instalarán los proyectores son de vulcanita u otro material ligero, por lo que no admiten un anclaje directo del equipo ni de su soporte. El proveedor deberá fabricar e instalar, según las condiciones particulares de cada sala, una placa metálica pasante que sujete el muro por ambas caras (interior y exterior) o un soporte de techo fabricado en metal que sostenga el equipo de forma segura. La solución estructural aplicada en cada sala queda a criterio y responsabilidad del proveedor al momento de la instalación.])

== Topología de Red
La arquitectura propuesta reemplaza la dependencia de repetidores inalámbricos en cascada —principal causa de la degradación actual— por un diseño donde cada AP se conecta al switch mediante cableado estructurado. 

El UDM-PRO centraliza la gestión de toda la red desde una única consola UNIFI, lo que simplifica la operación y permite detectar fallas con rapidez. Las antenas PtP LOCO5AC resuelven los sectores sin cableado disponible y los AP exteriores U6-MESH-PRO eliminan las zonas sin cobertura identificadas en la visita.

El siguiente diagrama ilustra la topología lógica y física de la red propuesta:

#figure(
  image("img-39/topologia_propuesta.png", height: 8cm, fit:"contain"),
  caption: [Topología de red propuesta]
)

== Diagrama de Cobertura Wi-Fi
El diagrama de cobertura permite validar que la disposición propuesta de los AP elimina las zonas sin señal detectadas durante la visita, garantizando conectividad en todos los sectores del establecimiento. 

La cobertura estimada en banda 5 GHz (utilizada para actividades pedagógicas) confirma que el diseño alcanza los espacios donde hoy no existe señal o esta es insuficiente:

#figure(
  image("img-39/cobertura_wifi_5g.png", height: 8cm),
  caption: [Cobertura Wi-Fi estimada — banda 5 GHz]
)

#pagebreak()

== Distribución en Gabinetes
Como parte de la propuesta, se establece una separación clara de responsabilidades entre los dos gabinetes del establecimiento. *El gabinete de Mineduc albergará exclusivamente el módem del Proyecto CpE2030 del Mineduc*, sin ningún otro equipo ni cableado adicional; su función es únicamente proveer el enlace de Internet institucional y no debe intervenirse ni compartirse con equipamiento de la red interna del establecimiento. Todo el equipamiento activo y el cableado estructurado de la red interna —incluyendo el UDM-PRO, el switch, los patch panels y la UPS— se centralizarán en el rack principal, que operará como el único punto de gestión y distribución de la red. Esta centralización simplifica el mantenimiento, reduce los puntos de falla y permite al personal de TI intervenir la infraestructura desde un único lugar.

El diagrama siguiente muestra la distribución propuesta de los equipos dentro del rack principal:


#figure(
  image("img-39/rack_propuesto_1.1.png", height: 14cm),
  caption: [Distribución planificada en Rack Principal]
)

#pagebreak()


== Distribución de Cámaras de seguridad
La ubicación de las 4 cámaras IP interiores DAHUA DH-IPC-HFW5859T aportadas por el proyecto GORE se definió priorizando los accesos principales, los pasillos de mayor tránsito y los sectores donde se concentra equipamiento tecnológico sensible, con el objetivo de resguardar tanto la integridad de los usuarios como la del parque tecnológico del establecimiento. Cada cámara se conectará mediante cableado estructurado CAT6 al grabador NVR DAHUA DHI-NVR4108HS-8P-4KS3, que centralizará el almacenamiento y la gestión del sistema de vigilancia. La disposición final de los puntos de cámara, validada junto a la dirección del establecimiento, se ilustra en el siguiente diagrama:

#figure(
  image("img-39/distribucion_camaras.png"),
  caption: [Distribución de cámaras de seguridad]
)

== Instalación de Proyectores

=== Distribución de proyectores

Los 10 proyectores ultracortos Epson EB-685W con Wi-Fi aportados por el proyecto GORE se distribuirán en las salas de clases definidas por la dirección del establecimiento, priorizando aquellas con mayor uso pedagógico diario. Dada su naturaleza de tiro ultracorto, cada equipo se monta en altura, sobre la pizarra de la sala respectiva, lo que minimiza las sombras proyectadas por el docente y optimiza el aprovechamiento del espacio disponible. La conectividad de red de cada proyector se gestionará vía Wi-Fi según los parámetros definidos por la Unidad TI. Las particularidades constructivas de las salas —detalladas en la sección "Trabajos a Realizar"— condicionan tanto la fijación del equipo como el tendido de energía y HDMI hasta su ubicación final. La disposición específica por sala se muestra en el siguiente diagrama:

#figure(
  image("img-39/distribucion-proyectores.png", height: 8cm),
  caption: [Distribución de proyectores]
)

=== Posición en aulas
Los proyectores deben quedar ubicados según la ilustración a continuación.

#figure(
  image("img-39/ilustracion_proyector.png", height: 8cm),
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
    ("4", "Inyector PoE 48 VDC Gigabit 802.3af", "1", "$15.000", "$15.000"),
    ("5", "Cable directo 50 cm SFP+ 10 Gbps", "2", "$29.000", "$58.000"),
    ("6", "Soporte abatible 50 cm para muro", "2", "$12.000", "$24.000"),
    ("7", "Patchcord 10 cm CAT6 RJ45 blanco", "40", "$4.000", "$160.000"),
    ("8", "Tapa negra 1U con cepillo para rack 19\"", "1", "$13.000", "$13.000"),
    ("9", "Patch panel 24p RJ45 CAT6 UTP 1U certificado UL", "1", "$38.000", "$38.000"),
    ("10", "Cámara IP interior 5MP PoE IP67 IK10", "1", "$169.811", "$169.811"),
    ("", "*Subtotal equipamiento*", "", "", "*$1.888.811*"),
  ),
)

#aviso(tipo: "info", titulo: "Precios de Mercado", [Los costos expresados en esta tabla son precios de mercado obtenidos por un análisis de proveedores especializados en tecnología.])

== Costo de Instalación
La instalación fue dimensionada según el diseño de red elaborado en Unifi Design, que determinó los metrajes de cableado y canalización requeridos para interconectar cámaras, puntos de acceso y antenas, y según estimaciones de la Unidad TI para la mano de obra y los puntos de conexión de los proyectores.

=== Cableado y canalización de datos
Según el diseño de red (Unifi Design), la interconexión de cámaras, puntos de acceso y antenas requiere 420 metros de cable UTP Cat6 LSZH (libre de halógeno) 100% cobre y 130 metros de canalización metálica EMT para la protección y el ordenamiento del cableado.

#tabla(
  columns: (auto, 1fr, auto, auto, auto),
  ("#", "Descripción", "Cant.", "Precio unit. (c/IVA)", "Total (c/IVA)"),
  (
    ("1", "Cable UTP Cat6 LSZH (libre de halógeno) 100% cobre", "420 m", "$700", "$294.000"),
    ("2", "Canalización metálica EMT con accesorios (uniones, conectores, fijaciones)", "130 m", "$5.000", "$650.000"),
    ("", "*Subtotal material cableado y canalización*", "", "", "*$944.000*"),
  ),
)

#aviso(tipo: "info", titulo: "Referencia de precio", [El precio del cable UTP Cat6 LSZH 100% cobre (\$700 el metro) y de la canalización EMT (\$5.000 el metro, con accesorios) corresponden a valores entregados directamente por la Unidad TI y se cobran de forma independiente entre sí.])

=== Mano de obra — Canalización y cableado de datos
El tendido del cableado UTP no se cobra por separado: al instalar la canalización EMT, el cableado se pasa en la misma intervención, ahorrando tiempo de instalación. Por esto, la mano de obra se calcula únicamente sobre los 130 metros de canalización EMT, a \$8.000 el metro, incorporando un 30% de margen de error (169 metros equivalentes) para imprevistos de trazado.

#tabla(
  columns: (auto, 1fr, auto, auto, auto),
  ("#", "Descripción", "Cant.", "Precio unit. (c/IVA)", "Total (c/IVA)"),
  (
    ("1", "Instalación de canalización EMT (incluye tendido simultáneo del cableado UTP), 130 m + 30% margen", "169 m", "$8.000", "$1.352.000"),
    ("", "*Subtotal mano de obra cableado de datos*", "", "", "*$1.352.000*"),
  ),
)

=== Mano de obra — Instalación de equipos
Se estima \$41.000 por unidad para la instalación física (montaje, fijación y puesta en servicio) de los equipos que requieren manipulación individual: las antenas PtP con su soporte, los puntos de acceso interiores y exteriores (Mesh), y los proyectores. Este valor es independiente del costo de cableado y canalización de las secciones anteriores.

#tabla(
  columns: (auto, 1fr, auto, auto, auto),
  ("#", "Descripción", "Cant.", "Precio unit. (c/IVA)", "Total (c/IVA)"),
  (
    ("1", "Instalación de antena PtP con soporte", "2", "$41.000", "$82.000"),
    ("2", "Instalación de AP interior", "4", "$41.000", "$164.000"),
    ("3", "Instalación de AP exterior (Mesh)", "2", "$41.000", "$82.000"),
    ("4", "Instalación de proyector ultracorto", "10", "$41.000", "$410.000"),
    ("", "*Subtotal mano de obra instalación de equipos*", "", "", "*$738.000*"),
  ),
)

=== Puntos eléctricos para proyectores
Cada uno de los 10 proyectores requiere un punto de energía dedicado, ya que se instalan en altura sobre la pizarra sin un punto eléctrico cercano disponible. Se considera un trazado de 20 metros de canalización EMT por proyector, con 3 conductores EVAFlex (fase, neutro y tierra) libres de halógeno de 2,5 mm² y el enchufe embutido correspondiente.

#tabla(
  columns: (auto, 1fr, auto, auto, auto),
  ("#", "Descripción", "Cant.", "Precio unit. (c/IVA)", "Total (c/IVA)"),
  (
    ("1", "Canalización EMT con accesorios (20 m x 10 proyectores)", "200 m", "$5.000", "$1.000.000"),
    ("2", "Cable EVAFlex libre de halógeno 2,5 mm² (3 conductores x 20 m x 10 proyectores)", "600 m", "$500", "$300.000"),
    ("3", "Enchufe embutido con placa", "10", "$3.990", "$39.900"),
    ("", "*Subtotal puntos eléctricos (10 proyectores)*", "", "", "*$1.339.900*"),
  ),
)

#aviso(tipo: "info", titulo: "Referencia de precio — Cable EVAFlex", [El valor del cable EVAFlex libre de halógeno 2,5 mm² (\$500 el metro, IVA incluido) se estimó en base a precios de mercado nacional (cable H07Z1-K 2,5 mm² desde \$424 a \$535 el metro según formato). El enchufe embutido con placa (\$3.990) corresponde a un valor de mercado para tomacorrientes tipo Bticino o equivalente.])

=== Puntos HDMI para proyectores
Al ser proyectores de tiro ultracorto instalados sobre la pizarra, cada sala requiere un punto HDMI dedicado. Se considera una canaleta Legrand de 10 metros por proyector para la conducción visible del cableado, un cable HDMI de 10 metros tendido dentro de la canaleta, un módulo HDMI (keystone) en el punto de conexión y un cable HDMI de 3 metros para la conexión del equipo del docente.

#tabla(
  columns: (auto, 1fr, auto, auto, auto),
  ("#", "Descripción", "Cant.", "Precio unit. (c/IVA)", "Total (c/IVA)"),
  (
    ("1", "Canaleta Legrand 20x12 mm (10 m x 10 proyectores)", "100 m", "$1.145", "$114.500"),
    ("2", "Cable HDMI 10 m (tendido en canaleta)", "10", "$9.990", "$99.900"),
    ("3", "Módulo HDMI (keystone) para punto de conexión", "10", "$6.990", "$69.900"),
    ("4", "Cable HDMI 3 m (conexión del equipo del docente)", "10", "$3.990", "$39.900"),
    ("", "*Subtotal puntos HDMI (10 proyectores)*", "", "", "*$324.200*"),
  ),
)

#aviso(tipo: "info", titulo: "Referencia de precio — Canaleta y HDMI", [Precios de mercado nacional: canaleta Legrand 20x12 mm desde \$1.145 el metro, cable HDMI 10 m desde \$9.990, módulo HDMI keystone desde \$6.990 y cable HDMI 3 m desde \$3.990.])

== Costo Total del Proyecto
#tabla(
  columns: (auto, 1fr, auto),
  ("#", "Componente", "Total (c/IVA)"),
  (
    ("1", "Equipamiento a adquirir", "$1.888.811"),
    ("2", "Material cableado y canalización de datos", "$944.000"),
    ("3", "Mano de obra — canalización y cableado de datos", "$1.352.000"),
    ("4", "Mano de obra — instalación de equipos", "$738.000"),
    ("5", "Puntos eléctricos para proyectores (material)", "$1.339.900"),
    ("6", "Puntos HDMI para proyectores (material)", "$324.200"),
    ("", "*Total general del proyecto*", "*$6.586.911*"),
  ),
)

#aviso(tipo: "warning", titulo: "Solicitud de Compra", [Antes de realizar o subir una solicitud de compra por favor solicitar a la Unidad de Tecnologías de la Información las Especificaciones Técnicas de los items a travez del correo: *soporte.informatica\@epchinchorro.cl*.])

#pagebreak()
= Conclusiones
La red inalámbrica de la Escuela Carlos Condell de la Haza presenta deficiencias concretas que ya están afectando la operación del establecimiento: zonas sin cobertura, un router que no da abasto con los dispositivos actuales y tres AP en mal estado que pueden fallar en cualquier momento. La incorporación de nuevas tablets no hizo más que acelerar un problema que el equipamiento instalado no está en condiciones de absorber.

La propuesta presentada en este informe resuelve cada uno de estos puntos mediante un proyecto de *provisión e instalación* que combina el equipamiento a adquirir con los equipos ya disponibles del proyecto GORE (BIP 40065439-0). La solución centraliza la gestión en un único rack principal y libera el gabinete de Mineduc de cualquier uso distinto al enlace institucional. El costo total referencial del proyecto asciende a \$6.586.911, compuesto por \$1.888.811 de equipamiento y \$4.698.100 de instalación (cableado y canalización de datos, mano de obra de montaje y puesta en servicio, y los puntos eléctricos y HDMI dedicados de cada proyector), y contempla además la organización del cableado mediante un patch panel, aspecto que hoy también representa un riesgo operativo.

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

