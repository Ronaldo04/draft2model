# Auditoría independiente de diagonales - 245

Fecha: 2026-10-21. Alcance: lectura local de E01/E02, contraste gráfico con A01/A02 y consulta de INVENTARIO_GEOMETRICO_09.json, geometria_09.py y calibración BORRADOR_CASO_08.json. Sin API, ETABS ni Computer Use. Sin cambios al producto ni archivos de Claude. No constituye aprobación de ingeniería.

## Resultado accionable

Se distinguen **dos tramos físicos inclinados**, uno superior y otro inferior, entre ejes estructurales B-C, simétricos respecto del eje 2. Cada uno es la **rama inclinada de una PL-4 quebrada**, con un cimiento corrido exterior. No son dos nuevos muros de albañilería que deban añadirse automáticamente al inventario: las placas respectivas **ya están** como `L0001-E8` y `L0001-E19`, con cajas 2.553–4.703 x 2.148–3.723 m y 2.553–4.705 x 6.273–7.848 m. La pendiente del inventario corresponde a completar las **franjas diagonales de cimiento** y a conservar las ramas oblicuas del contorno, no a crear placas duplicadas por separado.

La identificación tiene tres apoyos: (1) doble borde grueso que enlaza sin corte con el contorno rotulado PL-4 en E01; (2) repetición de la misma rama y etiqueta PL-4 en ambas plantas de E02; (3) marca 5-5 sobre la zona oblicua y detalle CORTE 5-5 que dibuja un muro de concreto de .10 m sobre cimiento .50 m. No se infiere un muro solo porque exista una franja de cimentación.

## Fuentes, orientación y escala

Originales de una página bajo `planos_muestra/proyecto_pueblo_libre/`:

- E01: `Estructuras_Pueblo Libre1-Cimentación.pdf`, SHA-256 ff669f23633b7c355bc7d89ea60809856df7e29a5b4019204307f7deef9ba8f5; rotación PDF 0°, tamaño visual 3370 x 2384 pt.
- E02: `Estructuras_Pueblo Libre1-Model.pdf`, SHA-256 d655e6c5f2c8998a2049b300b83a65a62962c5de03a622bfd9978fd4a8f074fa; rotación PDF 270°, tamaño visual 3370 x 2384 pt. Coordenadas siguientes **ya rotadas**, origen arriba-izquierda: `(xvisual,yvisual)=(yraw,2384-xraw)`. No aplicar la rotación otra vez.
- Arquitectura A01/A02: `Arquitectura-Model1.pdf` / `Arquitectura-Model2.pdf`; rotación 270°, visual 2384 x 1684 pt. Se usan para corroborar el quiebre y ángulo, no para imponer espesor sobre estructura.

Para que las coordenadas métricas sean compatibles con el inventario 09 se reutilizó **exactamente su convención**: `x=(xPDF-364.2)*0.012595`, `y=(yPDF-260.48)*0.012581` en E01; y crece de 3 hacia 1. Los factores proceden del registro del borrador 08 y están redondeados en inventario_09.py. La orientación 3↔A sigue siendo hipótesis de piloto según auditoría 237; no afecta a la identificación de los dos tramos en coordenadas estructurales. Las medidas siguientes son derivadas del dibujo, no cotas impresas, salvo las indicadas como leídas.

## Extremos y ancho de las dos ramas PL-4

Las parejas de segmentos de abajo son **bordes del contorno**, no ejes de muro ni líneas de cota. Grosor de pluma vectorial 1.32 pt no equivale a espesor físico.

| Tramo | Borde 1 PDF visual E01, pt | Borde 2 PDF visual E01, pt | Posición |
|---|---|---|---|
| D-superior | (578.76,540.68) → (638.76,447.20) | (566.88,544.52) → (634.32,439.28) | B-C; entre 3 y 2; próximo al quiebre de dormitorio principal/dormitorio 1 |
| D-inferior | (566.88,770.96) → (634.32,876.32) | (578.76,774.80) → (638.76,868.28) | B-C; entre 2 y 1; quiebre inferior equivalente |

Los extremos de un **eje aproximado** se obtienen promediando extremos correspondientes de las caras. Son útiles para ubicación y longitud, pero no sustituyen el contorno poligonal PL-4, que incluye brazos horizontal y vertical:

| Tramo | Eje aproximado en PDF, pt | Extremos métricos derivados, m | Largo aproximado |
|---|---|---|---|
| D-superior | (572.82,542.60) → (636.54,443.24) | (2.628,3.549) → (3.430,2.299) | 1.485 m |
| D-inferior | (572.82,772.88) → (636.54,872.30) | (2.628,6.447) → (3.430,7.697) | 1.486 m |

El ancho normal entre las dos caras da **0.0998 / 0.0999 m**. Esto concuerda con **.10 leída** en CORTE 5-5. El ancho no se obtiene restando coordenadas x: la rama está inclinada. La longitud depende de la convención de extremo en el encuentro quebrado; no es una luz libre acotada. Se recomienda retener las coordenadas PDF y contorno, y redondear a centímetros al usar estas derivaciones.

## Cimiento corrido diagonal: objeto separado de la placa

En E01, bordes exteriores de pluma .84 pt:

| Tramo | Borde exterior 1, pt | Borde exterior 2, pt |
|---|---|---|
| Superior | (618.48,434.60) → (555.48,532.88) | (647.88,463.04) → (592.68,549.08) |
| Inferior | (555.48,782.72) → (618.48,881.00) | (647.88,852.44) → (592.68,766.40) |

La distancia normal del par superior deriva aproximadamente **0.505 m**, compatible con **.50 impresa** en CORTE 5-5. El par inferior es su réplica casi especular. Los segmentos exteriores enlazan con las franjas verticales/horizontales de cimiento; por sus remates a inglete, promediar sus extremos no produce necesariamente el mismo eje que el muro superior. No copiar el eje de franja como eje del muro sin comprobar excentricidad.

E01 marca 5-5 cruzando ambas ramas oblicuas. El corte correspondiente, región visual aproximada `(2790,140)-(3060,890)`, muestra: muro .10; altura 2.40 sobre NFP -0.05; malla 3/8 @0.25 m; cimiento .50; concreto f'c=175 kg/cm² y subcimiento corrido. Estos son **datos leídos del detalle**. Se observan dos rótulos de concreto175, uno a la altura del fuste elevado y otro junto al bloque enterrado; por tanto no parece un rótulo único restringido al subcimiento, que tiene su propia nota C:H1:12+30%PG. Sin embargo no hay una llamada inequívoca desde cada PL-4 de planta a una especificación de material del fuste completo: la llamada5-5 atraviesa el conjunto muro/cimiento. Conservar la localización de ambos rótulos y la ambigüedad de alcance frente a la tabla general de placas antes de asignar material a toda PL-4. No convertir automáticamente PL-4 en albañilería ni asignar f'c=210 por la nota general, ignorando la llamada local de 175.

## Continuidad en E02 y contraste arquitectónico

E02 contiene dos plantas: superior ALIGERADO 1ER NIVEL y inferior ALIGERADO 2DO Y 3ER NIVEL. En ambas aparecen las dos ramas PL-4, no solo su cimentación. Coordenadas de sus bordes más allá de las X de huecos y rayados:

| Planta E02 | Rama superior: dos caras, pt visuales | Rama inferior: dos caras, pt visuales |
|---|---|---|
| 1er nivel | (634.12,378.32)→(566.68,483.56); (578.56,479.72)→(638.56,386.24) | (638.56,807.32)→(578.56,713.84); (566.68,710.00)→(634.12,815.36) |
| 2do/3er nivel | (575.20,1534.52)→(635.08,1441.04); (630.76,1433.00)→(563.20,1538.36) | (563.20,1764.80)→(630.76,1870.04); (635.08,1862.12)→(575.20,1768.64) |

Cada planta tiene su propia traslación en la hoja. **No usar el origen PDF E01 directamente en E02.** La coincidencia de forma, doble cara, ubicación B-C, llamadas PL-4 y contacto con los brazos vertical/horizontal constituye evidencia gráfica de continuidad en las plantas de losa indicadas. No demuestra por sí sola continuidad exacta de todo el fuste, ausencia de vanos verticales ni una elevación libre de 2.60 m: eso requiere la asignación de niveles del piloto y revisión del detalle. Esta auditoría no revisó continuidad hasta E03/azotea.

A01 y A02 muestran el mismo quiebre alrededor de los dormitorios y la anotación angular **57°19'** junto a los lados inclinados (región visual aproximada `(520,450)-(720,965)`). Esto corrobora ubicación/forma. La representación arquitectónica incluye .15 cerca de la cara vertical y puertas colindantes; no prueba un espesor normal .15 del tramo diagonal. Si el modelo de arquitectura presupone .15 uniforme y estructura .10, registrar la diferencia y privilegiar la llamada estructural local para un borrador estructural, sin declarar resuelta la coordinación de especialidades.

## Faltantes deducibles frente a datos realmente necesarios

**Deducibles de los planos actuales:**

1. Digitalizar las dos franjas diagonales exteriores como cimientos, con ancho nominal .50 y procedencia CORTE 5-5; la banda vectorial ya proporciona sus bordes.
2. Conservar en E8/E19 la rama oblicua y sus brazos como un polígono PL-4; si se discretiza en paneles, cortar por encuentros y evitar sumar otra vez la misma longitud/masa. Los pares de caras y extremos están arriba. **No usar la caja envolvente como contorno real:** contiene grandes áreas vacías y produciría una placa rectangular inexistente. El JSON auxiliar PL4_vertices_derivados.json conserva vértices ordenados PDF/m de los ciclos cerrados, sus segmentos brutos y la arista parcialmente superpuesta de E19, sin modificar el inventario.
3. Usar .10 como espesor leído del detalle 5-5, separado de .10 medido gráficamente y .50 del cimiento. Vincular las llamadas de detalle y tabla a cada instancia.
4. Registrar continuidad de la huella PL-4 en las dos plantas E02 y consultar E03 antes de extenderla hasta azotea. Las X de huecos y rayados no son muros diagonales adicionales.

**Requieren definición técnica o evidencia adicional antes de afirmar certeza:**

1. Resolver alcance de concreto175 del corte5-5 frente a nota general210/tabla de placas para asignar material definitivo. La fuente local existe; no es ausencia total de f'c.
2. Determinar panelización, nodos de encuentro, continuidad vertical efectiva, vanos y altura libre de estas PL-4. El patrón de losas no es un alzado de muros.
3. Mantener hipótesis de cotas5.20/7.80 y orientación global3↔A; esta revisión de diagonales simétricas no aporta un segundo discriminante de orientación.
4. Si se requiere un plano coordinado arquitectura-estructura, confirmar la diferencia de espesor local y las jambas/puertas; no convertir automáticamente la huella del cimiento en un tabique o muro de albañilería.

## Evidencia conservada

Auxiliares exclusivamente en `tmp/auditoria_diagonales_245/`: E01_diagonales.png, E01_corte55_completo.png, E02_diagonales_1er.png, E02_diagonales_2do3er.png, Arquitectura-Model1_diagonales.png, Arquitectura-Model2_diagonales.png; E01_diagonales_vector.json y E02_diagonales_vector.json conservan segmentos seleccionados por región y longitud. Los JSON también contienen trazos de corte, huecos y rayados: no son un detector ni un inventario adicional de muros.

**Conclusión:** dos ramas inclinadas de dos PL-4 existentes, más sus dos franjas de cimiento. Geometría horizontal, ancho local y presencia en E02 están respaldados por varias evidencias; material final, detalle de encuentros y extensión vertical siguen separados como decisiones pendientes.

### Vértices para implementación posterior

`tmp/auditoria_diagonales_245/PL4_vertices_derivados.json` contiene ambos contornos cerrados de10 lados y transformaciones métricas compatibles con inventario09. E8 tiene10 segmentos directos. E19 contiene11 segmentos brutos: diez forman un ciclo y el undécimo se superpone parcialmente a un borde; el bruto se preserva, el ciclo propuesto lo identifica expresamente. El área real derivada de cada polígono es 0.312m² (E8) y0.315m² (E19); la caja envolvente es aproximadamente3.39m². Esta diferencia demuestra por qué una caja no sirve como superficie de placa. Los vértices son contorno horizontal: una posterior representación en shell vertical requiere definición de ejes, panelización y encuentros, no extruir la caja.
