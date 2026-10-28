# Contabilidad del contenido líquido

La biblioteca draft2model.masa_contenido comprueba coherencia declarada entre inventario, presión y fuente de masa. No modifica configuración ni genera cargas. Desde 258 está enlazada al contrato 0.5 y al plan (ver «Integración en el flujo general»); la lectura de masa ensamblada en ETABS sigue pendiente. Disponer de esta biblioteca no demuestra que el modelo incluya el agua.

## Función y contrato

`python
from draft2model.masa_contenido import auditar, ErrorContabilidad
`

`auditar(escenarios, *, masa, patrones, hosts, casos, combinaciones)` devuelve un inventario calculado o lanza `ErrorContabilidad`. No modifica los argumentos.

El consumidor debe tratar por separado la ausencia confirmada de depósitos: no llamar con una lista vacía ni crear masas ficticias. Una evaluación exige al menos un escenario identificado y **un único estado por depósito**; estados alternativos del mismo depósito se evalúan en llamadas separadas. Los nombres de patrones/declaraciones no se pueden compartir entre depósitos, evitando sumar dos veces una contribución declarada. Esto no permite reconocer depósitos físicos duplicados con IDs distintos: resolver identidad es obligación del integrador.

Cada escenario declara explícitamente:

| Campo | Dominio/unidad |
| --- | --- |
| deposito, estado, fuente, declaracion | Textos no vacíos; `fuente` es referencia documental declarada, no fuente autenticada por este módulo. |
| volumen_m3 | Finito, >=0. Es inventario declarado/revisable, no volumen calculado aquí. |
| peso_especifico_kn_m3 | Finito, >0. |
| gravedad_m_s2 | Finita, >0, igual a `masa.gravedad_m_s2`. |
| nivel_libre_z_m | Finito; debe coincidir exactamente con los hosts. |
| modo | `patron_presion` o `patron_masa_exclusivo`, sin valor predeterminado. |
| patron_presion | ID existente de patrón, con multiplicador de peso propio 0. |
| patron_masa_exclusivo | ID existente y distinto, con multiplicador de peso propio 0; o `None` si no existe alternativa y el modo es presión. |
| peso_vertical_referencia_kn | Magnitud no negativa en modo exclusivo, igual a gammaV. En modo presión debe ser `None`. |

Se calcula `W=gamma*V` en kN y `M=W/g` en kN·s²/m. Se rechazan booleanos, NaN, infinitos, productos/sumas no representables y dominios inválidos. La tolerancia de balances es `1e-9 * max(1,abs(a),abs(b))`, computacional, no tolerancia de ingeniería. El factor elegido debe ser **exactamente 1**; no se redondea un factor parcial a 100%.

`masa` contiene `metodo='patrones'`, `gravedad_m_s2`, `masas_puntos=[]` y `factores_patrones=[{patron,factor},...]`. No admite método explícito ni masas puntuales mezcladas. El patrón elegido debe aparecer con factor1 y la alternativa debe estar omitida o con factor0. Patrones sin relación con los depósitos pueden existir en la fuente de masa; este módulo no audita su física ni el peso propio estructural global.

`patrones` es la lista `{id,multiplicador_peso_propio}` (admite campos adicionales). Todos los patrones referidos por masa o casos deben existir. Para los dos patrones de contenido declarados, el multiplicador de peso propio debe ser exactamente0.

## Dos modos, sin conversión automática

- **patron_presion**: usa el patrón hidrostático ya existente como representación de contenido para masa. Requiere hosts de `preparar_liquidos` ligados a la misma declaración/patrón/gamma/nivel; fuerzas XYZ conservadas contra `fuerza_fuente_kn` y `error_relativo_max<=1e-9`. La suma vertical debe ser `Fz=-gammaV`. Una pared sola con Fz0 y V>0 falla; un fondo con signo invertido falla. No se agrega una carga gravitacional adicional.
- **patron_masa_exclusivo**: usa el patrón exclusivo declarado, con referencia de peso vertical `gammaV`; el patrón de presión queda fuera de masa o con factor0. Puede haber presión únicamente de paredes, siempre ligada a la declaración, pero el peso independiente debe declararse. Por política de patrón **solo para masa**, se prohíbe su uso con coeficiente no nulo en TODO caso estático, aun sin presión o sin combinación conjunta. **No se crean nodos, fuerzas ni transporte del peso de referencia**: quedan a cargo de la integración posterior.

Para cada modo se exige al menos un host vinculado, incluso en estado vacío; un host de fondo seco con fuerzas0 documenta el caso vacío. No se inventa una declaración ni se interpretan listas ausentes como vacío confirmado. Los hosts no cubiertos por ningún escenario se rechazan. La suma de pesos/masas del inventario calculado abarca solamente el inventario de los escenarios de la llamada.

## Casos y combinaciones

Se reciben las listas **completas** de configuración: casos `{id,tipo,parametros}` y combinaciones `{id,tipo,casos:[{caso,factor}]}`. Para `estatico_lineal`, `parametros.patrones` contiene `{patron,factor}`. Se reconocen `modal_eigen` y `espectro_respuesta` sin expandirlos a patrones estáticos. Las combinaciones solo admiten referencias a casos, no combinaciones anidadas; se rechazan referencias desconocidas y duplicadas.

La guarda es una política de exclusividad del patrón solo para masa: usa presencia de factores no nulos y no permite ocultar uso estático mediante cancelaciones de signo ni coeficiente cero de una combinación que referencia un caso con peso exclusivo. Rechaza ese caso aunque no se ejecute o figure en una rama separada de una envolvente. **Una envolvente no suma necesariamente sus ramas: el rechazo no es una prueba matemática de duplicación estática**, sino incumplimiento de la política solo para masa. Un coeficiente cero en el propio caso no aplica ese patrón y se admite. La política deberá acordarse antes de integrar.

## Ejemplo independiente y ejecución

El oráculo sintético del test es un prisma **2×2.15×h2.22 m**, gamma10 kN/m³, g9.80665 m/s²:

```text
V = 9.546 m³
W = 95.46 kN
M = 95.46 / 9.80665 kN·s²/m
Fz del fondo seleccionado = -95.46 kN
```

Es un escenario matemático identificado, **no una afirmación sobre dimensiones o llenado del depósito real del piloto**. El fixture `entrada()` del archivo de pruebas muestra el contrato completo de llamada. No importa datos del producto ni reutiliza su calculador como oráculo.

Desde la raíz del proyecto:

```powershell
python -B -m unittest tests.test_masa_contenido -v
```

Resultado local: **15 tests OK**. Incluyen prisma, vacío, solo pared, signos, conservación, factores0/.25/2, alternativa omitida/0, mezcla de masas, referencias de hosts, fuentes/estados vacíos, NaN/bool/inf, gamma/g/V inválidos, overflow, patrones con peso propio, doble host, dos depósitos, estados alternativos simultáneos y doble peso estático por caso/combinación.

## Límites de la comprobación

1. No reconstruye recinto ni verifica volumen, cierre/cobertura de fondo, normales o coordenadas de piezas. El balance Fz es condición necesaria, no prueba suficiente de geometría. Un registro inventado que cierre aritméticamente puede pasar: se requiere vinculación por huellas y regeneración desde `preparar_liquidos` a cargo del integrador.
2. Comprueba fuerzas declaradas de los hosts, no el EDB, la tabla aplicada, momentos ni masa realmente ensamblada. No autentica `fuente`, revisión o estado de llenado.
3. El peso vertical de referencia exclusivo es una declaración de magnitud: no prueba distribución a nodos, destino de cargas, caso transportado ni lectura independiente. No es una segunda ejecución ni un sustituto de ese desarrollo.
4. No determina cómo ETABS convierte el patrón hidrostático a masa ni acredita por un balance global su distribución física o grados de libertad. No habilita por sí mismo la ruta de presión para producción.
5. No audita duplicación física escondida en otros patrones, masas de material, inventarios faltantes o una lista incompleta de casos/combinaciones. Se necesita un libro completo de contribuciones y entradas ligadas a versiones vigentes.
6. No incluye hidrodinámica, oleaje, interacción fluido-estructura ni validación normativa. No altera las pruebas estáticas206/210 ni hereda de ellas una aprobación del contenido100%.

Los retornos marcan `aprueba_ingenieria=False`, `crea_cargas=False`, `ejecutable=False`. Antes de conectar esta biblioteca al contrato/plan/transporte, coordinar sus archivos con Claude; esta biblioteca250 solo añade archivos independientes.

## Integración en el flujo general (258)

La configuración 0.5 admite la clave opcional `liquidos.contenido`, con un registro por depósito:

| Campo | Valor |
| --- | --- |
| deposito, fuente, motivo | Texto; `fuente` es un id de `fuentes`. |
| estado | `lleno` (nivel libre declarado en su escenario), `vacio`, `desconocido` o `ausente_confirmado`. |
| declaracion, modo | `lleno`/`vacio`: id de una declaración de `liquidos.declaraciones` y `patron_presion` o `patron_masa_exclusivo`. Los otros dos estados exigen `null`. |
| volumen_m3 | Inventario declarado (0 en `vacio`); `null` en `desconocido`/`ausente_confirmado`. |
| patron_masa_exclusivo, peso_vertical_referencia_kn | Como en la biblioteca. |

El validador (`modelo_estructural._ValidadorLiquidos.contenido`):

- exige un estado por depósito y que toda declaración de líquido tenga estado;
- registra `desconocido` como faltante, que bloquea el adaptador (no se asume vacío ni lleno);
- con geometría y malla, regenera las presiones (`liquidos_malla.preparar_liquidos`) y llama a `auditar`;
- publica el inventario en `ResultadoModelo.contenido_masa`, con `masa_nativa_verificada: false`.

El plan 0.5 copia ese inventario en `contenido_masa`, ligado por `huella_liquidos` a las filas de presión del mismo plan. Sin la
clave, la salida del validador y del plan no cambia.

La masa ENSAMBLADA en ETABS sigue pendiente de acreditar tras el análisis (`masa_ensamblada`). Pruebas:
`tests/test_contenido_liquidos_258.py`.
