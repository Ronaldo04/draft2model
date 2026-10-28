# Parámetros literales hacia preparación 0.5

`draft2model.parametros_a_configuracion.aplicar_parametros(configuracion, lectura_validada, *, elementos_permitidos)` es una función pura para incorporar filas resolubles de `lectura_parametros.validar_respuesta()` a una copia de configuración estructural **0.5.0**. Conserva datos incompletos como pendientes y devuelve siempre un borrador. No abre expedientes, imágenes, APIs ni ETABS.

## Entrada y salida

La configuración debe ser un documento de preparación 0.5 con listas explícitas para fuentes, hipótesis, materiales, secciones, puntos, frames, asignaciones, patrones, cargas y faltantes. Sus unidades deben ser m/kN/s/C. Puede tener datos técnicos pendientes; no se exige aprobación ni consistencia completa para preparar una copia.

`lectura_validada` es el resultado enriquecido del validador de lectura: `datos`, `advertencias`, `faltantes`, `revision` y `ejecutable_etabs: false`. Cada evidencia numérica o de asignación debe referir a su tabla, que conserva `archivo_id`, `pagina`, `bbox_normalizada`, `texto` y `original_sha256`. El módulo comprueba forma, evidencias resolubles, huellas con formato SHA256 y coincidencia de caso; **no autentica que el validador haya sido ejecutado ni vuelve a comprobar los bytes del original**. El servicio debe proporcionar su lectura conservada y vigente.

`elementos_permitidos` debe provenir del registro geométrico comprobado, por ejemplo:

```python
catalogo = {
    "F1": {"tipo": "frame"},
    "P1": {"tipo": "punto"},
    "A1": {"tipo": "superficie", "vertical": False},
    "W1": {"tipo": "superficie", "vertical": True},
}
resultado = aplicar_parametros(configuracion, lectura_validada,
                              elementos_permitidos=catalogo)
borrador = resultado["configuracion"]
```

También admite ID→tipo y un conjunto/lista de IDs. En ese último caso solo obtiene el tipo de colecciones de la configuración; no calcula la orientación de superficies. Para asignar una sección a superficie se necesita `vertical` booleano explícito. La función rechaza un catálogo que contradiga el tipo ya declarado en la configuración. Un frame/punto permitido pero todavía no incorporado a la configuración conserva su asignación/carga como pendiente; este módulo no crea geometría.

La salida contiene `configuracion`, `aplicados`, `faltantes`, `conflictos`, `trazabilidad`, `huella_lectura`, copia íntegra `lectura_conservada`, `revision_configuracion_previa` y `validacion`. `faltantes` incluye el dato literal completo y el ID original propuesto, para que una decisión posterior pueda resolverlo. Los conflictos también quedan en esa lista; nunca se selecciona la última fila contradictoria.

La copia de configuración conserva `datos_sinteticos`, origen geométrico, identidad y datos ajenos a esta operación. La revisión de configuración pasa a `{estado: "borrador", aprobacion: null}`; la revisión previa se conserva fuera del contrato como información, sin activarla. La lectura y su revisión quedan intactas. Un indicador opcional `simulado: true` o `datos_sinteticos` incompatible en el resultado de lectura impide mezclar naturalezas. La ausencia de esos indicadores no acredita que una lectura corresponda a datos reales.

## Materiales sin propiedades inventadas

Se crea un material `isotropo_lineal` solo cuando existen propiedades literales válidas y completas `E`, `poisson` y `peso_especifico`, dentro de la representación del contrato vigente. Se exigen E y peso positivos; `-1 < poisson < 0.5`. La clase `otro`, propiedades desconocidas, duplicadas o unidades incompatibles quedan pendientes.

| Propiedad | Unidades admitidas → salida |
| --- | --- |
| `E` | MPa, kgf/cm2 o kN/m2 → `E_kN_m2` |
| `poisson` | adimensional → `poisson` |
| `peso_especifico` | kgf/m3, tf/m3 o kN/m3 → `peso_kN_m3` |

Se reutilizan `normativa_rne.a_mpa` y su constante dimensional `KGF_CM2_A_MPA`; solo para conversión de unidades, sin usar fórmulas, pesos ni resistencias normativas. No se agrega una fuente normativa cuando no se aplica ninguna norma.

`fc`, `fm` o `fy` aislados no producen E, G, Poisson ni peso. Tampoco se crea un material vacío que impida la creación posterior desde UI349. Se conserva un pendiente con el ID propuesto y todos sus valores/evidencias. Las resistencias presentes junto a propiedades mecánicas completas se conservan como datos literales en fuentes y en la lectura; no se convierten en propiedades resistentes del modelo elástico.

Después de crear externamente un material completo con **ese mismo ID**, puede reaplicarse **la misma lectura conservada**, sin otra llamada a IA. El conversor usa el material ya resuelto si es completo y no contradice ninguna propiedad mecánica literal presente; mantiene su fuente original. Entonces vuelve a intentar secciones y asignaciones. Esta operación no atribuye al material existente una fórmula de derivación nueva ni aprueba su origen.

## Secciones y asignaciones

No se sustituyen formas ni se adivinan parámetros. Las dimensiones de longitud admiten m, cm o mm y se normalizan con `contratos.DIVISORES_A_METROS`.

| Lectura | Tipo de configuración | Parámetros obligatorios |
| --- | --- | --- |
| rectangular | `frame_rectangular` | ancho, alto |
| L | `frame_l_concreto` | alto, ancho, espesor_ala, espesor_alma, espejo_eje_2, espejo_eje_3; material identificado como concreto |
| muro | `shell_muro` | espesor |
| losa_maciza | `shell_losa_homogenea` | espesor |
| losa_aligerada_unidireccional | `shell_losa_nervada_v1` | alto_total, capa, ancho_nervio_superior, ancho_nervio_inferior, separacion, direccion_nervios, angulo_ejes_locales_grados |
| losa_aligerada_bidireccional | `shell_losa_casetonada_v1` | alto_total, capa, ancho_nervio_superior, ancho_nervio_inferior, separacion_1, separacion_2, angulo_ejes_locales_grados |

Los espejos necesitan 0/1 adimensionales explícitos y se convierten en booleanos; la dirección de nervios necesita 1/2 adimensionales. El ángulo necesita grados explícitos en `[-180,180)`. Se comprueban espesores de L menores que sus dimensiones exteriores, capa menor que alto y nervios menores que cada separación. Parámetros sobrantes sin aplicación inequívoca dejan la sección pendiente. No se crea inserción de frames, orientación local ni otras decisiones ausentes.

Las secciones requieren un material completo disponible y sin conflicto. Frame admite rectangular o L; muro admite `shell_muro`; superficie vertical admite `shell_muro`, y superficie no vertical admite maciza o los tipos aligerados. No se aplica automáticamente una sección a todos los elementos de su clase.

IDs existentes con valores distintos conservan el registro previo y generan conflicto. Una asignación nula de preparación puede completarse. Una asignación real a otra sección permanece intacta. Si dos filas de una lectura asignan secciones distintas al mismo elemento, **ninguna se aplica**. La existencia del mismo ID con valores compatibles permite reaplicar sin duplicar registros ni cambiar su fuente anterior.

## Cargas externas explícitas

Se convierten únicamente cargas `muerta` o `viva` de magnitud positiva finita, dirección literal `global_z_negativa`, alcance delimitado y lista no vacía de elementos permitidos del mismo tipo. Lista vacía, elemento ajeno, tipos mezclados, unidad incompatible, duplicados o dirección desconocida conservan la fila pendiente. Agua y `otro` requieren su contrato físico específico, sin convertir presión hidrostática en carga uniforme.

El filtro conservador de alcance deja pendiente texto que contenga las palabras `general`, `global`, `edificio`, `todos`, `todas`, `todo`, `toda`, `desconocido` o `desconocida`. No distribuye cargas de alcance general al edificio ni interpreta ambientes. El servicio puede revisar/delimitar el alcance mediante el procedimiento de lectura correspondiente; no debe sustituir ese texto automáticamente para pasar el filtro.

Se admiten kN/kgf/tf por punto, kN/m–kgf/m–tf/m por frame y kN/m2–kgf/m2–tf/m2 por muro/superficie. El vector queda `[0,0,-magnitud]`, en sistema global. No hay conversiones de kg a fuerza ni áreas de reparto inferidas.

Cada carga leída crea un **patrón externo dedicado** con `multiplicador_peso_propio: 0`. Esta decisión autorizada aísla exclusivamente la carga externa documentada y evita sumar peso propio dentro de ese patrón; **no declara la política de peso propio del edificio**. Se conserva una hipótesis con fuente y un faltante de política global de peso propio/masa. No se modifican ni crean masa, gravedad, factores de masa, casos ni combinaciones. Los IDs de patrón/carga son deterministas y cada fila se verifica completamente antes de incorporar sus cargas; un conflicto no sobrescribe cargas existentes ni aplica parte de la fila.

## Trazabilidad, reaplicación y límites

Se agrega una fuente por cantidad y por fila; la fuente de material/sección agrega también las evidencias de todas sus cantidades. `descripcion` conserva un JSON canónico con dato, ruta y evidencias enriquecidas. `referencia` señala la lectura por huella y ruta. `sha256` identifica el JSON canónico de **los datos de lectura enriquecidos**, mientras cada evidencia conserva aparte `original_sha256`. Los IDs de fuente incluyen lectura y snapshot para evitar confundir dos versiones con un dato parcial idéntico. No se añaden citas normativas ficticias.

La configuración conserva faltantes con fuente y ruta deterministas, cuyo sufijo `lectura_<hash>` identifica el dato propuesto pendiente. En cada reaplicación se recalculan solo esos faltantes de la misma lectura; los faltantes anteriores ajenos permanecen. Reaplicar sin cambios produce la misma configuración; reaplicar después de completar datos compatibles permite progresar. La lista `aplicados` distingue `incorporado`, `ya_existente` y `resuelto_en_configuracion`.

`validacion` procede de `modelo_estructural.validar_configuracion` **sin geometría externa**. Informa errores/faltantes reales del contrato, incluidos los de una preparación incompleta; no acredita origen geométrico, orientación, conexiones, malla ni disponibilidad para ejecutar. La función siempre devuelve `completa: false`, `ejecutable_etabs: false`, `aprueba_lecturas: false` y `aprueba_ingenieria: false`. La integración deberá conservar la lectura y el resultado, verificar su vigencia y continuar los pasos explícitos de revisión/preparación.

Pruebas focales exclusivamente sintéticas:

```powershell
.venv/Scripts/python.exe -B -m unittest tests.test_parametros_a_configuracion -v
```

Recibo de pruebas y hashes: `seguimiento/PARAMETROS_CONFIGURACION_351.json`. No acredita suite completa, planos reales, UI/API integrada ni ETABS.
