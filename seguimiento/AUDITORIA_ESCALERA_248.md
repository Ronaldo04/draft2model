# Auditoría de escalera del piloto - 248

Fecha: 2026-10-22. Lectura de los seis PDF originales, una página por archivo. Sin cambios de producto/configuración, sin GUI, red, API ni ETABS. Auxiliares: `tmp/auditoria_escalera_248/` (manifiesto SHA256, texto, palabras y renders/crops).

## Conclusión práctica

La escalera **no es un hueco vacío**: E-02 contiene su planta y dos detalles resistentes, con garganta inclinada de 0.15 m, armadura y encuentros en apoyos. A-02/A-03 definen un trazado de retorno en U, con giros y pasos laterales alrededor de un ojo, ancho acotado de 1.20 m y huellas de 0.25 m en las zonas indicadas. No es defendible cerrar todavía todos sus vértices XYZ: faltan el reparto vertical por tramo y la correspondencia completa de los apoyos, y existe una discontinuidad documental en la llegada al techo.

## Fuentes y sistema de referencia de evidencia

`sourceSHA` significa SHA256 de los bytes del PDF original. Todas las referencias siguientes son página **1**. Los bbox están en **puntos PDF de la página orientada como se ve**, origen superior izquierdo, formato `[x0,y0,x1,y1]`; no son coordenadas del edificio. A-01/A-02/A-03/E-02 tienen rotación PDF 270°, E-01/E-03 0°. La extracción de texto nativa no aplica esa rotación: para localizar sus palabras en este sistema se utilizó `Rect(word_bbox) * page.rotation_matrix`. Tamaños visibles: A = 2384×1684 pt; E = 3370×2384 pt.

| Clave | Archivo en `planos_muestra/proyecto_pueblo_libre/` | sourceSHA |
| --- | --- | --- |
| A01 | Arquitectura-Model1.pdf | `1f2e8d9c2507cc85bbcd6d6cc9fc217baf4d272c6620417c1985eeb3d4b8be54` |
| A02 | Arquitectura-Model2.pdf | `f63d63ce7674c21b3437145cfde2f6ab66abe814c445c5c65873db99067b87bf` |
| A03 | Arquitectura-Model3.pdf | `ead656045a3c95739e2bd7cab3c5daddb6d1e42ebaa7aaf9afb6c34be07dce4a` |
| E01 | Estructuras_Pueblo Libre1-Cimentación.pdf | `ff669f23633b7c355bc7d89ea60809856df7e29a5b4019204307f7deef9ba8f5` |
| E02 | Estructuras_Pueblo Libre1-Model.pdf | `d655e6c5f2c8998a2049b300b83a65a62962c5de03a622bfd9978fd4a8f074fa` |
| E03 | Estructuras_Pueblo Libre1.pdf | `fb4284e82b7a55f4faeb4e9917269b37e94336c0788562873385e7e21c67a134` |

| Evidencia | Fuente/bbox visible pt | Auxiliar |
| --- | --- | --- |
| S1: primer acceso y primer tramo | A01 `[1478.1,488.4,2002.6,976.7]` | A01_escalera.png |
| S2: planta típica de escalera | A02 `[1525.8,488.4,1907.2,943.0]` | A02_escalera.png |
| S3: llegada de escalera a techo | A03 `[1525.8,488.4,1907.2,943.0]` | A03_escalera.png |
| S4: detalle resistente tramos 1 y 2 | E02 `[2123.1,953.6,2999.3,1835.7]` | E02_detalle.png |
| S5: planta escalera 2do/3er nivel | E02 `[1415.4,1454.2,1752.4,1859.5]` | E02_planta.png |
| S6: zona homóloga 4to nivel | E03 `[1381.7,500.6,1752.4,953.6]` | E03_planta.png |
| S7: contexto de cimentación | E01 `[1381.7,381.4,1786.1,929.8]` | E01_contexto.png |
| S8: secciones de vigas/apoyos | E02 `[2123.1,155.0,3066.7,762.9]` | E02_cortes.png |

## Datos confirmados por lectura visual

| Dato | Valor/lectura | Evidencia y restricción |
| --- | --- | --- |
| Existencia resistente | Detalle titulado `ESCALERA TIPICA S/C=200 Kg/m2`, con TRAMO 1 y TRAMO 2 | S4. La sobrecarga es una anotación del plano; no se ejecutó cálculo ni se resolvió si se aplica sobre proyección o superficie inclinada. |
| Espesor inclinado | `0.15 m`, medido normal al intradós inclinado en ambos detalles | S4. No confundir con los 17 cm del aligerado general. |
| Zona horizontal izquierda | Cota vertical `0.20 m` en el extremo horizontal izquierdo de ambos esquemas | S4. No generalizar automáticamente ese espesor a todos los descansos y encuentros: el extremo derecho no tiene esa misma cota explícita. |
| Armadura dibujada | `Ø3/8" @ .20`, malla arriba y abajo en el extremo izquierdo y barras en rampa/encuentros | S4. Permite reconocer continuidad material, no fijar por sí sola empotramiento ideal. |
| Extremo derecho | Ambos esquemas llegan a elemento vertical con llamada `CORTE 2-2` y cota local de 0.50 m | S4. S8 representa corte 2-2 con ancho .10 y profundidad `.50 ó .40`; la localización/nivel concreto requiere resolver el detalle. |
| Extremo izquierdo | TRAMO1 llama `CORTE 3-3`; TRAMO2 `CORTE 3-3 ó 10-10` | S4. S8 muestra 3-3 de .15×.45; no se encontró un detalle 10-10 en estas seis láminas. No sustituir por otra sección sin aprobación. |
| Trazado superior | Retorno U: tramo lateral inferior, giro, tramo longitudinal exterior, giro y lateral superior; ojo central y conexión al hall | S2/S3 y S5. Los dos esquemas longitudinales de S4 no bastan para deducir por sí solos todos esos encuentros espaciales. |
| Ancho acotado | `1.20 m`, en la franja exterior y en la franja superior perpendicular | S2/S3. Es una cota directa en esos lugares; no demuestra que toda la primera escalera, pasamanos o ancho libre terminado sea idéntico. |
| Huellas acotadas | `0.25 m`, cadena de tres pasos en dirección horizontal y cadena en dirección vertical | S2/S3. No hay contrahuella numérica en estos planos. |
| Numeración visible A01 | 1 a 9 antes del símbolo de corte | S1. Es solo la porción vista del primer tramo, no nueve peldaños totales entre pisos. |
| Numeración visible A02 | 1 a 15 en franja inferior; 16 a 19 arriba; 20 a 22 en franja exterior antes del corte | S2. Planta típica para segundo, tercero y cuarto piso, con representación superpuesta de llegada/salida; no sumar los visibles como peldaños de un solo entrepiso. |
| Numeración visible A03 | 50,51,52 arriba; 53 a 60 en tramo exterior; 61 a 64 en franja inferior | S3. Confirma continuidad de la numeración y giro de llegada, no especifica por sí sola el conteo de contrahuellas de cada piso. |
| Nivel primer piso | Hall/acceso N.P.T. ±0.00 | A01; texto de nivel visible bbox `[1522.9,731.7,1555.3,742.7]`, próximo a S1. |
| Nivel típico escrito | Hall N.P.T. +2.60 | A02; bbox texto `[1530.2,720.1,1558.9,731.1]`. La lámina agrupa tres pisos, pero imprime ese nivel singular. |
| Nivel de techo escrito | N.T.T. +10.40 | A03, texto bbox `[850.9,704.8,876.4,715.8]` (zona central de techo; ver render completo plano3_p1.png). |
| Contexto de apoyos en planta | C-3 en bordes de llegada; C-6 en ojo/zona intermedia; llamadas de corte 3 y franja horizontal rayada adyacente | S5. Son referencias geométricas, no autorización para unir todo a C-6 o asignar restricciones cinemáticas. Su sección se audita por otro agente. |
| Diferencia de representación por nivel | E02 dibuja escalera exterior en la planta 2do/3er; E03 no la prolonga en su planta 4to nivel, aunque conserva la franja rayada adyacente | S5/S6 y renders completos. A03 sí dibuja llegada al techo. Es omisión/discrepancia de documentación a resolver. |

## Derivaciones que pueden usarse solo como candidatas revisables

- El ancho transversal de la envolvente U en la zona acotada resulta **1.95 m = 3×0.25 + 1.20**, a partir de la cadena horizontal S2/S3. Es una suma de cotas, no una cota total independiente. No extender ese valor al tramo largo inferior de A02, que sobresale en la representación de la llegada.
- Si se confirma un módulo vertical uniforme de 2.60 m, las cotas intermedias candidatas serían +5.20 y +7.80, y cuatro módulos alcanzan +10.40. La concordancia aritmética con A03 no convierte esos niveles intermedios en cotas impresas ni determina descansos.
- Una lectura de 64 contrahuellas acumuladas hasta +10.40 daría 0.1625 m por contrahuella; **no está confirmada**: 64 es numeración de dibujo, y se desconoce su convención y el reparto entre pisos. No incorporar ese valor a geometría real sin revisar cortes/contar elevaciones.
- Puede trazarse un sistema local de planta con origen sobre el borde interior junto al hall y eje transversal hacia la franja exterior, pero hace falta registrar su transformación a ejes estructurales. Las letras/números de arquitectura y estructuras no se deben identificar por igualdad de etiqueta.

## Hipótesis que no deben pasar a configuración

- Dos rampas rectas simétricas con descanso a media altura. El plano arquitectónico muestra cambios de dirección y la documentación no fija esos niveles.
- Repetir una escalera idéntica en todos los pisos, incluido techo. A01 difiere en la parte representada; A02 agrupa pisos; A03 y E03 no coinciden en continuidad representada.
- Tomar `.80`, `.70`, `.60`, `.50` o `.40` de S4 como longitudes completas de descansos: están dibujadas en zonas de barras/encuentros y deben distinguirse de geometría libre/longitudes de desarrollo. No existe una cadena de luces completas del tramo en ese detalle.
- Tomar la cisterna dibujada en E01 como hueco, apoyo o cimentación completa de la escalera; S7 se presenta solo como contexto. No se duplicó la auditoría de depósitos ni la de C6/PL10.
- Declarar apoyos articulados, empotrados, deslizantes o diafragma rígido por defecto. El armado muestra continuidad, pero no define una liberación de modelo.

## Faltantes irreducibles para cerrar XYZ y conectividad

1. Cortes arquitectónicos A-A y B-B llamados en las plantas, o levantamiento/detalle de escalera que indique **número de contrahuellas por tramo, contrahuella, cotas de cada giro/descanso y llegada**. Esos cortes no están incluidos en A01-A03.
2. Correspondencia del detalle TRAMO1/TRAMO2 con cada porción de la U y cada piso, incluyendo la primera llegada y la llegada al techo. Resolver la continuidad A03/E03 con el proyectista/documento revisado.
3. Polígonos de descansos y sus espesores locales, luces reales y cotas hasta caras de apoyo. La cota e=.15 de rampas sí está disponible; las zonas horizontales necesitan identificación por elemento.
4. Identificación de los elementos físicos que reciben cada borde: llamadas 2-2/3-3/10-10, ubicación y profundidad aplicable `.50 ó .40`, continuidad con franja de losa/hall, y transformación arquitectura-estructuras. El detalle 10-10 no se localizó entre las seis hojas.
5. Criterio de idealización aprobado: superficies inclinadas/descansos, rigidez fuera de plano, vínculo al edificio, peso de peldaños/acabados y sobrecarga de escalera. No resolverlo suprimiendo la escalera o sustituyéndola por carga sin trazabilidad.

## Integración recomendada sin ocultar la escalera

Conservar una entidad de escalera pendiente con evidencia S1-S8, trazado de planta por nivel y zonas resistentes diferenciadas: rampas e=.15, horizontales identificados, conexiones físicas pendientes. Separar el ojo realmente vacío de la superficie escalonada y de la franja de llegada. Hasta cerrar los faltantes, no publicar un modelo como geométricamente completo ni inventar los XYZ de los descansos. Si el contrato actual no soporta esos elementos, registrar esa limitación expresamente y mantener la escalera como requisito pendiente, en vez de borrar su masa/rigidez/conectividad de manera silenciosa.

El manifiesto y los crops permiten reproducir la lectura sobre fuentes originales. El render visual fue realizado con PyMuPDF/Pillow en modo local; no se confió solo en texto extraído. Esta auditoría no valida diseño, resistencia ni ejecución real.
