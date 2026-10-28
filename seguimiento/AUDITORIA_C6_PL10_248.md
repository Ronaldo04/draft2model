# Auditoría geométrica C-6 y PL-10 - 248

Fecha: 2026-10-22. Solo lectura local; sin API, ETABS, GUI, red ni cambios al producto/configuración/cola de Claude. Salidas limitadas a este informe y `tmp/auditoria_c6_pl10_248/`. No es aprobación de ingeniería. No se auditan depósitos completos ni escaleras.

## Dictamen compacto

**C-6:** una instancia física reconocible junto al borde H y la cisterna/escalera. Su cuadro acota **.15 x .75 m**; la planta E01 y ambas plantas E02 dibujan repetidamente un rectángulo de aproximadamente **.20 x .75 m**, con **lado largo paralelo a X/H-I**, no vertical en el papel. La discrepancia de espesor está confirmada por dos tipos de evidencia y no debe ocultarse. E03 planta del 4to nivel no dibuja C-6 en la posición equivalente: **no extenderla por defecto hasta N4**. La huella se puede implementar con procedencia y discrepancia; sección definitiva y extremos verticales no quedan resueltos por una caja ni por el nombre.

**PL-10:** dos instancias físicas largas entre H e I, en los bordes 3 y 1. E01 contiene sus **cuatro caras de contorno**, etiqueta PL-10 y llamada al corte2-2; este corte acota **espesor .10 y altura2.40 desde NFP−.05**, con concreto175. Arquitectura A01 rotula **CERCO H=2.40** en las dos mismas franjas. Por tanto existe evidencia para representar dos cercos/muros de concreto de primer piso; no es necesario solicitar al usuario su ancho/altura inicial. Las huellas se repiten en E02 y E03, pero esa repetición entra en tensión con el corte de altura limitada y el patio frontal abierto de arquitectura: **no demuestra muros de cuatro entrepisos ni justifica extruirlos N0–N4**. La fila PL-10 no existe en el cuadro general de placas, que llega hasta PL-9.

## Fuentes y coordenadas

Todos son PDF de una página en `planos_muestra/proyecto_pueblo_libre/`:

| Lámina | Archivo | SHA-256 | Rotación PDF |
|---|---|---|---|
| E01/L0001 | Estructuras_Pueblo Libre1-Cimentación.pdf | ff669f23633b7c355bc7d89ea60809856df7e29a5b4019204307f7deef9ba8f5 | 0° |
| E02/L0002 | Estructuras_Pueblo Libre1-Model.pdf | d655e6c5f2c8998a2049b300b83a65a62962c5de03a622bfd9978fd4a8f074fa | 270° |
| E03/L0003 | Estructuras_Pueblo Libre1.pdf | fb4284e82b7a55f4faeb4e9917269b37e94336c0788562873385e7e21c67a134 | 0° |
| A01/L0004 | Arquitectura-Model1.pdf | 1f2e8d9c2507cc85bbcd6d6cc9fc217baf4d272c6620417c1985eeb3d4b8be54 | 270° |

Estructura tiene tamaño **visual**3370 x2384pt; todas las coordenadas dadas son puntos visuales, origen arriba-izquierda, X a derecha/Y abajo. Para E02 ya se aplicó `(xvisual,yvisual)=(yraw,2384-xraw)`; no rotar otra vez. Arquitectura visual2384 x1684pt.

Registro métrico E01 compatible con inventario09: `x=(xPDF−364.2)*.012595`, `y=(yPDF−260.48)*.012581`. X parte de A, Y de3 hacia1. Coordenadas de E02/E03 necesitan sus propios orígenes de vista; **no aplicar el origen E01 a otra planta**. La orientación 3↔A arquitectónico permanece hipótesis de piloto; no interviene en identificar ejes estructurales H/I/3/1.

## C-6: evidencia, forma y orientación

| Evidencia | Localización visual, pt | Lectura/derivación |
|---|---|---|
| Cuadro C-6 E01 | recorte(310,1605)–(595,1910) | TextoC-6(.15x.75), cotas independientes .15 y.75; 8barras de1/2; sección rectangular dibujada en el cuadro con lado largo vertical |
| Planta E01 | quad(1556.28,633.92)–(1615.68,649.76) | Primitiva cerrada qu rectangular, no caja inferida; dimensiones derivadas .748x.199m; rótuloC-6 debajo; lado largo horizontal |
| E02 planta1er nivel | quad(1555.96,572.96)–(1615.48,588.80) | Primitiva cerrada rectangular; etiquetaC-6; largo≈.750m/espesor≈.199m |
| E02 planta2do/3er | quad(1552.60,1627.76)–(1612.12,1643.60) | Repite dimensión/orientación junto a los huecos cortados por C-6; etiquetaC-6 |
| E03 planta4to | región(1470,660)–(1690,885) | No hay C-6 ni quad equivalente en posición respecto deH/eje2; borde H y rayado sí visibles |

En E01, coordenadas métricas de caras: **x15.014–15.762; y4.698–4.898m**. Centro geométrico del rectángulo dibujado≈**(15.388,4.798)m**, derivado, no eje acotado. Eje2≈y5m; C-6 está ligeramente hacia el lado3 del centro, proyectándose desde H hacia I. Rectángulo .15x.75 del cuadro y .20x.75 de planta no son equivalentes: diferencia de área .1125 frente a.1500m², antes de efectos de orientación o material. No se elige sección por la caja .748x.20 sin declarar la discrepancia.

La orientación vertical del dibujo del cuadro es solo convención de presentación de sección: **las plantas muestran la rotación física de90° de su lado largo**, que debe traducirse a ejes locales del frame según sus convenciones. No basta clasificarla C-6 ni copiar el giro del cuadro.

### Relación útil con cisterna y límites verticales

E01 coloca C-6 en el extremo izquierdo del lado inferior de la cisterna; C-3 está en el borde izquierdo del lado superior. E03 detalle **TECHO CISTERNA**, recorte(1980,1735)–(2450,2310), repite C-3 arriba/C-6 abajo a la izquierda del claro2.00x2.15m, con borde izquierdo.15 y otros bordes.20 y hueco.55. Esto enlaza la huella y el nombre de C-6 con el depósito sin inventar un apoyo adicional.

La dimensión.20 del borde inferior del detalle de cisterna es compatible con el espesor dibujado alrededor deC-6, pero se refiere al borde del conjunto techo/muro y **no sustituye inequívocamente la cota.15 del cuadro de columna**. A la vez, el extremo izquierdo del detalle es.15, de modo que no procede uniformizar toda la esquina por.20. El conflicto columna/borde del depósito debe conservarse separado de las dimensiones claras del tanque.

E02 acredita presencia de C-6 en las huellas de losa1er y2do/3er nivel; no es un alzado que determine dónde nace ni hasta dónde llega exactamente. E03 detalle de depósito no representa otro C-6 en azotea: es el techo de cisterna, cuyo NFC−2.65 pertenece al depósito. **No trasladar NFC de cisterna al pie deC-6 ni asumir que el detalle la prolonga hastaN4.** Las cotas verticales de C-6 y su conexión a cimiento/techo de cisterna/escalera siguen sin cota propia.

La ausencia en E03 es una limitación concreta de la extensión; no prueba por sí sola demolición/terminación exacta enN3. Si se adopta N0–N3 como idealización provisional deberá etiquetarse como tal. No hay fuente aquí para usar automáticamente la misma cadenaN0–N4 que otras columnas.

## PL-10: dos rectángulos reales, no mera caja envolvente

E01 contiene8 líneas de contorno,4por instancia, de pluma1.32pt; los cierres y caras largas forman rectángulos. Por tanto las listas de vértices siguientes describen las **caras reales observadas**, no una sustitución por bounding-box de una forma irregular.

| Instancia E01 | Vértices visualespt, cierre último→primero | Ubicación |
|---|---|---|
| Superior=L0001-E5 | (1558.56,260.48);(1953.48,260.48);(1953.48,268.40);(1558.56,268.40) | H–I, borde3; espesor hacia interior1 |
| Inferior=L0001-E29 | (1558.56,1047.08);(1953.48,1047.08);(1953.48,1055.12);(1558.56,1055.12) | H–I, borde1; espesor hacia interior3 |

Métricas derivadas: superiorx15.043–20.017, y0–.100m; inferiorx15.043–20.017, y9.896–9.997m. Largo físico dibujado≈**4.974m**, espesor≈**.100/.101m**. La separación nominal entre ejes H/I se registra≈5m, pero no es una cota directa de longitud libre PL-10. Conservar ambos datos y no alargar automáticamente la placa hasta x15.000/20.000. Eje de espesor propuesto por punto medio: y≈.050/9.947m; **los ejes3/1 coinciden aproximadamente con cara exterior, no centro de espesor**.

E01 región superior(1510,220)–(1995,330) muestra etiquetaPL-10 y llamada**2-2** cruzando el muro. Corte2-2 completo, región(2390,140)–(2795,890):

- **.10m de espesor**; **2.40m de altura** desde**NFP−.05** hasta coronación.
- Malla3/8@.25m; dos rótulos de**concreto f'c175kg/cm²**, uno junto al muro elevado y otro junto al bloque enterrado; no es una nota de mortero ni solo solado.
- Cimiento.40m, dimensionado de manera excéntrica respecto al muro; solado C:A1:12 de.05m; cotas.30/.80 bajo piso. Estas dimensiones del cimiento no son sección PL-10.

El enlace planta→llamada2-2 y las cotas del corte dan una fuente local específica, distinta de la nota general de concreto210. No asignar175/210 por prioridad arbitraria sin conservar esta fuente y resolver su alcance en configuración. El cuadro de placas deE01 (recorte815,1695–1585,2200) solo tienePL-1…PL-9: **no copiar aPL-10 el armado dePL-9 ni afirmar que el cuadro contienePL-10**. La malla del corte es evidencia independiente disponible.

### Arquitectura y altura implementable

A01 identifica **CERCO H=2.40** arriba y abajo en las dos mismas franjas de frente: textos visuales(1691.84,329.16)–(1772.51,340.06) y(1691.84,1087.08)–(1772.51,1097.98). Las dos franjas parten del borde2 arquitectónico hacia1, compatible con H↔2/I↔1. Este segundo soporte favorece tratar lasPL-10 como cercos de concreto de primer piso con altura limitada.

Si NFP−.05 y NPT±.00 comparten datum, la coronación derivada sería**+2.35m**; no es una cota impresa dePL-10 ni equivale aN1+2.60. La diferencia de.25m respecto al nivel+2.60 impide conectarla rígidamente a la losa solo por redondeo. Una incorporación sustentada puede conservar pieNFP−.05/altura2.40 y cimiento del detalle como objetos propios, manteniendo explicitados datum/apoyo. No es necesario pedir al usuario el espesor o la altura de este cerco inicial: están impresos.

### Repetición gráfica y ambigüedad de continuidad

| Vista | Rectángulo superior visualpt | Inferior visualpt |
|---|---|---|
| E02 1er nivel | (1558.36,199.52)–(1953.28,207.44) | (1558.36,986.12)–(1953.28,994.16) |
| E02 2do/3er | (1554.88,1254.20)–(1949.80,1262.24) | (1554.88,2040.92)–(1949.80,2048.84) |
| E03 4to nivel | (1558.56,365.12)–(1953.48,373.16) | (1558.56,1151.84)–(1953.48,1159.76) |

En cada vista se ven contornos y etiquetaPL-10; no son simples ejes sin nombre. **Está confirmada la repetición de la huella en todas esas plantas**, lo cual debe declararse y no descartarse selectivamente. Sin embargo no hay en esas vistas un alzado de4muros de altura2.60; H–I es zona frontal abierta, sin losa aligerada rectangular que una ambos laterales. Arquitectura típica/techo dibuja el vacío frontal, y la única altura local de cerco2.40 se refiere al piso base. La interpretación de contornos repetidos como proyección de cierres de lindero frente a muros que suben requiere coordinación; no se resuelve repitiendo el shellN0–N4. Para una representación de primer piso, corte2-2+A01 son fuentes suficientes; para una continuidad estructural vertical hasta azotea falta una elevación/detalle que la confirme y defina coronación/apoyos.

## Qué puede hacerse con los planos, y qué no debe afirmarse

**Deducible/implementable con procedencia:** conservar una C-6 horizontal con huella de tres vistas, sus discrepancias explícitas; conservar dos contornos PL-10 exactos, espesor.10 y detalle local de cerco2.40/concreto175/malla; vincular PL-10 a corte2-2 y C-6 al detalle de columna y a su relación con cisterna. Conectar objetos requiere respetar caras/ejes reales y no extender la losaA–H hastaI porque existan estos elementos.

**Pendientes físicos específicos:** elección justificada de espesor C-6(.15cuadro frente.20 repetido); cotas inferior/superior y anclaje deC-6, particularmente ausencia enE03; alcance vertical dePL-10 si se pretende modelarla por encima del cerco inicial; confirmación de datum y apoyo para insertar top+2.35derivado; coordinación de fuente local concreto175 frente a material general210. No son falta de ubicación o forma en planta: esos datos están en los originales. No se pide información al usuario antes de agotar esas fuentes.

## Auxiliares

`tmp/auditoria_c6_pl10_248/contornos_confirmados_derivados.json` contiene vértices de los3quadsC-6 y8rectángulosPL-10 porvista, con transformación métricaE01 y sus estados. Los8rectángulos representan2instancias repetidas en vistas, **no8placas físicas**. Recortes con nombresE01/E02/E03 conservan los detalles/cuadros y evidencia de ausenciaC-6 enplantaE03. Los JSON preliminares de caras seleccionadas incluyen trazos de texto; **no usarlos como inventario**: la salida limpia es contornos_confirmados_derivados.json y el informe, con coordenadas contrastadas visualmente.
