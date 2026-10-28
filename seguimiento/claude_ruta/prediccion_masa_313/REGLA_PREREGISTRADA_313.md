# Regla pre-registrada 313 (escrita ANTES de leer offsets nativos)

Fuente de la regla: *CSI Analysis Reference Manual* instalado con ETABS 21 (`C:/Program Files/Computers and Structures/ETABS 21/Manuals/CSI Analysis Reference.pdf`), tema «End Offsets», pp. 127–129 de la numeración del manual (pp. 150–152 del PDF):
- (M1) «ioff … is the distance from the joint to the face of the connection for the given element».
- (M2) Automáticos: «based on the maximum Section dimensions of all other elements that connect to that element at a common joint».
- (M3) Si la longitud libre resultara < 1 % de L, se reducen ambos offsets proporcionalmente hasta Lc = 0,01·L.

Entradas del predictor: SOLO el plan del modelo analizado (`modelos_construidos/0f372713…/plan.json`):
- coordenadas de puntos (`cPointObj.AddCartesian`);
- conectividad y sección de frames (`cFrameObj.AddByPoint`);
- dimensiones (`cPropFrame.SetRectangle`: T3, T2);
- puntos de inserción (`cFrameObj.SetInsertionPoint`);
- ausencia de `SetLocalAxes` y de `SetEndLengthOffset`, es decir, ángulo 0 y opción Auto.

Ningún peso, offset, tabla ni recibo del solver entra en el predictor.

## Regla primaria (R-cara)

Para cada viga VS y cada extremo (joint), con los demás FRAMES conectados en ese joint:
- **Columna vertical** con ejes locales por defecto (ángulo 0): local 2 = +X global y T3 a lo largo de local 2; local 3 = +Y y T2. Es un rectángulo de T3 (en X) × T2 (en Y) centrado en el joint. La contribución es la distancia del joint a la cara del rectángulo **a lo largo del eje de la viga**: min((T3/2)/|ux|, (T2/2)/|uy|), con u el vector unitario horizontal de la viga.
- **Otra viga horizontal** en el joint: rectángulo de ancho T2 transversal a su eje. La contribución es la distancia a su cara lateral a lo largo del eje de la viga: (T2/2)/|sen α|, con α el ángulo entre ambas vigas. Si es colineal (sen α ≈ 0), aporta 0 (continuidad, no apoyo).
- Offset del extremo = máximo de las contribuciones (M1 + M2). Sin frames conectados, 0.
- Después se aplica M3 por viga.

## Abstenciones pre-declaradas (no se adivina)

- **A1:** el joint tiene una columna con `SetInsertionPoint` (desplazamiento cardinal). El manual no dice si la cara se mide desde la sección desplazada o centrada en el joint.
- **A2:** el extremo no conecta con ningún frame, pero el plan define áreas (muros o losas) que tocan ese punto. El manual habla de «elements» sin precisar si los muros (shell) cuentan.
- **A3:** columna no vertical o sección no rectangular. No ocurre si el plan solo define rectángulos y columnas verticales; se comprueba.

Además de la primaria, el informe incluye una variante de sensibilidad **declarada de antemano**, R-max: media dimensión máxima max(T3,T2)/2 sin proyectar. Se informa pero no se elige mirando el contraste.

## Contraste (después y por separado)

Comparar por extremo y por viga con los offsets nativos de la lectura archivada `6da62ea3…` (tabla «Frame Assignments - End Length Offsets»), con tolerancia de redondeo de tabla ±0,0005 m declarada ahora. Los desacuerdos y abstenciones se informan, no se corrigen.
