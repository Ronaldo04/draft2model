# Regla 314: documentación específica de ETABS (NO es un ensayo ciego)

**Declaración.** Esta regla se escribe después de conocer los resultados de 313 (33 acuerdos, 8 desacuerdos y 4 abstenciones, y los patrones D1/D2/A2). Una huella demuestra integridad, no cronología. La regla se deriva solo de la documentación citada; donde esta calla, se abstiene en lugar de elegir la opción que mejor coincide.

## Corrección de la base documental de 313

El manual usado en 313 (*CSI Analysis Reference*, p. 128) atribuye la regla automática a la interfaz de **SAP2000**. No prueba la implementación de ETABS 21. Además, R-max 37 incluía 4 abstenciones: sobre las 41 no abstenidas coincide en 33, igual que R-cara. No hay mejora comparable.

## Fuente específica de ETABS

- Ayuda ETABS «End Length Offsets» (Assign > Frame > End Length Offsets): https://docs.csiamerica.com/help-files/etabs/Menus/Assign/Frame/End_Length_Offset.htm
- Consultada el 2026-10-24 en la web oficial. La página no indica versión.
- El `ETABS.chm` instalado no se pudo extraer con `hh.exe` en este entorno, así que no se contrastó su texto local.
- Contenido pertinente, parafraseado:
  - (E1) «Automatic from Connectivity» es la opción por defecto.
  - (E2) Para **vigas**, el offset de cada extremo se basa en la **máxima dimensión de sección de las columnas** conectadas a ese extremo.
  - (E3) Controla la **columna inferior**; la superior se ignora.
  - (E4) Las diagonales tienen offset cero y no intervienen.
- **No especifica:**
  - si muros u otras vigas intervienen;
  - el efecto de la orientación o de los puntos de inserción;
  - la regla cuando los offsets superan la longitud;
  - el tratamiento del peso propio;
  - la conversión exacta de «máxima dimensión» a longitud de offset.

## Regla 314 (R-ETABS)

Para cada viga VS (frame horizontal) y cada extremo (joint J):

1. **Columnas inferiores** = frames verticales cuyo punto superior es J. Las columnas por encima se ignoran (E3) y las demás vigas no cuentan (E2).
2. Si hay columnas inferiores, el offset del extremo es **max(T3, T2)/2** de la mayor de ellas.
   - Interpretación declarada: la sección está centrada en el joint y el offset es media dimensión máxima (E2), sin proyección por orientación, porque la página no la menciona.
   - Esta conversión ½·dimensión es una inferencia: la página dice «se basa en», no da la fórmula.
3. Sin columna inferior, offset 0 (E2: solo columnas).

## Abstenciones (no documentado)

- **B1:** columna inferior con `SetInsertionPoint`; la página no trata las inserciones.
- **B2:** suma de offsets ≥ L; la página no da límite. No se aplica el tope del 1 % de SAP2000.
- **B3:** el extremo no tiene columna inferior y el punto pertenece a áreas (muro o losa). Se desconoce si los muros intervienen.
- **B4:** sección no rectangular o frame inclinado.

Extremos con columna inferior y además áreas en el punto: se predicen y se marcan «salvedad_muro», porque E2 los cubre y la página no dice que el muro anule la columna.

## Contraste

Se hará después, por extremo y por viga, sobre la **misma población de 45 vigas** para R-cara (313) y R-ETABS (314), con denominadores explícitos y tolerancia de redondeo de tabla ±0,0005 m. Las abstenciones se informan aparte y no cuentan como acuerdos.
