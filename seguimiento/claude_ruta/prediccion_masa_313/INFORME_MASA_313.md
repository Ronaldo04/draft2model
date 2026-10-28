# Masa 313: predicción independiente de extremos VS

Sin ETABS, APIs ni modelo manual. Solo lectura. La tolerancia 0,001 no cambia. Los resultados originales no se modifican y la ingeniería no queda aprobada.

## Separación predicción / contraste

1. `REGLA_PREREGISTRADA_313.md` (SHA `c5919d39…`, sellada en `REGLA_PREREGISTRADA_313.sha256`).
   - La regla sale del *CSI Analysis Reference Manual* instalado con ETABS 21, tema «End Offsets»:
     - M1: distancia del joint a la cara de la conexión;
     - M2: máxima dimensión de los demás elementos conectados;
     - M3: longitud libre mínima del 1 %, con reducción proporcional.
   - Abstenciones A1 (columna con inserción), A2 (extremo solo con muros o losas) y A3 (sección no rectangular o frame inclinado).
   - Variante R-max declarada de antemano.
   - Transparencia: antes de sellar ya había visto los totales observados de 4 vigas en el resumen 278 (sin valores por extremo). No intervinieron en la regla.
2. `predictor_313.py` → `PREDICCION_313.json`, sellados en `PREDICCION_SELLADA_313.sha256` antes del contraste.
   - Entradas: solo el plan del modelo analizado `0f372713`: puntos, frames, rectángulos, inserciones y áreas.
   - El plan no tiene `SetLocalAxes` ni `SetEndLengthOffset`: ángulo 0 y opción Auto.
   - Una prueba estática comprueba que el predictor no menciona lecturas, pesos ni offsets del solver.
3. `contraste_313.py` → `CONTRASTE_313.json`: comparación posterior con la tabla nativa de offsets de la lectura `6da62ea3…`, tolerancia ±0,0005 m declarada antes.

## Resultado (45 vigas VS-15X30, peso 1,08 kN/m)

| | Vigas | Extremos nativos (m) | Peso (kN) |
|---|---|---|---|
| Acuerdo R-cara | 33 | 5,022 | 5,424 (79,0 % de 6,861) |
| Desacuerdo | 8 | 0,531 nativo frente a 1,466 predicho | +1,010 de exclusión sobrestimada |
| Abstención A2 | 4 | 0,800 | 0,864 sin predecir |
| Total | 45 | 6,353 | 6,861 |

La variante R-max coincide en 37. Solo se informa: elegirla después del contraste sería ajustar.

## Desacuerdos: Auto no se determina con las fuentes disponibles

- **D1** (3 vigas en Y, L = 0,313 m; VS-Z*-A-10/21/32): la suma de caras (0,15 + 0,20) supera L. El manual (M3) indica reducir a 0,99·L, pero ETABS registra **0 / 0**.
- **D2** (5 vigas en Y, L ≈ 0,107 y 0,113 m; tope en un solo extremo): M3 predice 0,1059 y 0,1119; ETABS registra 0,105 y 0,111. La diferencia de 0,0009 m supera el redondeo de la tabla. En vigas en X con el mismo patrón (L = 0,186), M3 sí coincide.
- **A2** (4 vigas, extremo J en muro): el manual no dice si los muros cuentan. A posteriori, ETABS registra 0 en ese extremo. Se mantiene la abstención; no se reescribe la regla.

Información que permitiría continuar sin ajustar a los resultados:
- documentación de CSI o una prueba controlada en ETABS (fuera de este perímetro) sobre el tratamiento Auto cuando ioff + joff ≥ L en uno o en ambos extremos;
- documentación de CSI sobre si los muros (shell) intervienen;
- documentación del valor exacto del tope (1 % de L, u otra regla, para piezas cortas en Y).

## Residuo global

`RESIDUO_GLOBAL_313.json`: desfase de CM 6,868112 kN − diferencia VS de la tabla 6,86126 − suma no-VS (−0,000025) = **0,006877 kN**.
- Las demás 18 secciones coinciden con la tabla nativa en ≤ 5·10⁻⁵ kN cada una.
- El residuo supera las cotas comprobadas de redondeo: 19 × 0,00005 = 0,00095 kN de la tabla de materiales y 0,00005 kN del CM de ETABS. **No es redondeo ni peso propio por sección.**
- Queda en otra componente de CM (carga D superpuesta, 7450 `SetLoadUniform` de área, o la definición del libro).
- Para localizarlo hace falta una reacción o resumen nativo por patrón (D sin peso propio) o una tabla de cargas de área asignadas; no existe en las lecturas archivadas revisadas.

## Propuesta de integración (para Codex)

- Usar el predictor solo como contraste independiente con estado por viga (acuerdo, desacuerdo o abstención). No incorporarlo al libro como «masa verificada» mientras D1, D2 y A2 sigan sin regla documentada.
- El contraste global del libro sigue **no_coherente**. La conciliación 278 sigue siendo retrospectiva, no predictiva.

## Pruebas

`test_predictor_313.py`: 7 pruebas con mini-planes sintéticos:
- orientación X/Y de la columna;
- viga colineal sin apoyo y viga perpendicular;
- viga oblicua;
- tope del 1 %;
- abstenciones A1/A2;
- sección distinta;
- independencia estática del código.

## Fuentes revisadas

- `seguimiento/REVISION_EXTREMOS_278.json`, `BALANCE_MASA_GRAVEDAD_268.json`, `REVISION_MATERIALES_272.json`, `revisar_extremos_278.py`;
- el plan `0f372713`;
- la lectura `6da62ea3…`, solo en el contraste;
- el manual CSI instalado.
