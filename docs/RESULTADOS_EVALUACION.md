# Resultados declarados, reglas configuradas y comparación

Estado: contrato local `0.1.0`, validado con datos fabricados. No ejecuta ETABS, no importa automáticamente tablas de un motor y no certifica seguridad estructural. Los nombres `real` y `simulacion` describen la procedencia declarada; el software no autentica al productor. Un JSON bien formado no demuestra que un análisis haya ocurrido.

## Resultados

`draft2model.resultados_estructurales` exige:

- `contrato: "draft2model.resultados_estructurales"`, `version_contrato: "0.1.0"`, `corrida_id`, `caso_id` y `creado_utc` ISO con zona UTC.
- `geometria: {id, sha256}`: el ID debe ser la versión geométrica exacta y el hash los bytes de su `geometria.json` guardado. No confundir con la huella del contenido geométrico que excluye revisión.
- `configuracion: {id, sha256}`: el ID declarado en `draft2model.modelo_estructural`; `sha256` es el valor de `modelo_estructural.huella_configuracion`, canónico sin `revision`. Este hash es diferente del hash de los bytes del archivo.
- `motor: {tipo: "real" | "simulacion", nombre, version}` y `datos_sinteticos` booleano. Una simulación exige `datos_sinteticos: true`; un motor real puede analizar un modelo sintético y conservar esa marca.
- `casos[]: {id, tipo, descripcion}` declara los casos de análisis. No son tipos de carga inferidos ni combinaciones creadas por este módulo.
- `unidades: {periodo: "s", deriva: "1", cortante: "N" | "kN"}`. Deriva es razón adimensional; `0.002` no equivale a `0.002 %`. No hay conversión implícita.
- `resultados[]: {id, variable, caso, direccion, ubicacion, valor, unidad}`. `variable` es `periodo`, `deriva` o `cortante`. La combinación variable/caso/dirección/ubicación es única. Ubicación puede identificar un modo, nivel o base; la correspondencia física se declara externamente. Los periodos presentes deben ser positivos; los otros valores pueden conservar su signo. No se calculan envolventes automáticamente.
- `valor: null` exige `motivo_omision`; una fila ausente también se distingue de cero. `advertencias[]` y `omisiones[]` conservan textos explícitos, incluidas limitaciones de cobertura. Las listas pueden estar vacías cuando así se declara.

Los campos desconocidos, IDs repetidos, referencias SHA256 mal formadas, booleanos numéricos y valores no finitos se rechazan. `cargar_json` reutiliza el parser estricto del proyecto y rechaza claves duplicadas. `huella_resultados(data)` cubre el JSON canónico completo, incluidos motor, referencias, advertencias y omisiones.

`validar_resultados(data, referencias_esperadas=...)` devuelve `{correcta, errores, huella}`; `exigir_resultados` eleva `ErrorResultados` ante problemas. El argumento opcional debe contener ambas referencias exactas `{geometria: {id, sha256}, configuracion: {id, sha256}}`. El llamador debe obtenerlas de sus artefactos previamente verificados; el módulo no abre expedientes ni confía en referencias solo porque tengan 64 caracteres hexadecimales.

## Reglas y evaluación

`draft2model.reglas_estructurales` contiene `id`, `datos_sinteticos`, `reglas[]` y `revision`. Cada regla declara:

```json
{
  "id": "R-D",
  "variable": "deriva",
  "unidad": "1",
  "formula": {"expresion": "factor * x + desplazamiento", "factor": 1, "desplazamiento": 0},
  "limite": 0.003,
  "comparador": "<=",
  "aplicabilidad": {"aplica": true, "casos": ["SX"], "direcciones": ["X"], "ubicaciones": ["N1"], "motivo": "Selector de prueba fabricado."},
  "fuente": {"titulo": "Fixture sin valor normativo", "edicion": "sintética 0.1", "apartado": "R-D", "referencia": "Solo prueba de software"}
}
```

El valor `0.003` de este ejemplo es arbitrario y carece de valor normativo. El módulo no suministra límites de ninguna norma. Todo uso técnico requiere fuentes, edición, apartados, aplicabilidad y parámetros seleccionados y revisados por el responsable correspondiente.

La única fórmula admitida es `factor * x + desplazamiento`, aplicada al valor de la variable; factor es adimensional y desplazamiento/límite tienen la unidad declarada. No usa `eval` ni ejecuta expresiones externas. La igualdad es numérica exacta sobre los valores representados, sin tolerancia tácita. Comparadores admitidos: `<`, `<=`, `==`, `>=`, `>`.

`revision` admite borrador con aprobación `null`, o aprobado con:

```json
{"estado": "aprobado", "aprobacion": {"revisor_declarado": "...", "fecha": "2026-10-16", "motivo": "...", "alcance": "...", "huella_contenido": "SHA256..."}}
```

`huella_declaracion(reglas)` cubre todos los campos excepto `revision`. Cualquier cambio de reglas, límites, fuente o aplicabilidad invalida la aprobación anterior. Revisor, competencia y aprobación son declarados, sin firma ni autenticación. La aprobación fabricada de la fixture únicamente permite probar el contrato.

`validar_reglas` devuelve consistencia y vigencia de la aprobación. `evaluar_resultados(resultados, reglas, *, huella_resultados_esperada, huella_reglas_esperada, referencias_esperadas=None)` exige ambas huellas exactas y reglas aprobadas de manera declarada. Rechaza unidades incompatibles y reglas sintéticas sobre datos no sintéticos o viceversa.

Para cada producto cartesiano explícito caso/dirección/ubicación:

- `evaluado`: indica `relacion_limite` **debajo**, **en** o **sobre**, junto con `satisface_regla_configurada` booleano. Estar debajo no implica satisfacer un comparador `>=`.
- `faltante`: no existe fila o contiene `null`; el resultado de la regla es `null`, nunca aprobado tácitamente.
- `no_aplicable`: la propia configuración declara `aplica: false` con motivo; el resultado de la regla también es `null`. No se confunde con dato faltante.

La salida conserva referencias, hashes, fuentes, aprobación de reglas, motor, sintéticos, advertencias y omisiones. No modifica entradas ni guarda archivos. No produce un dictamen global de seguridad. No conocer una norma o una variable no genera un criterio sustituto.

## Comparación contra referencia manual o independiente

`comparar_resultados(actual, referencia, tolerancias, equivalencia, *, huella_actual_esperada, huella_referencia_esperada)` compara dos corridas conservando sus hashes. Se admite diferente motor por nombre/versión y diferentes versiones/hashes de geometría y configuración, porque una referencia manual equivalente puede tener otro proceso de creación. Nunca se admite mezclar `simulacion` con `real`, marcas sintéticas distintas o casos de proyecto distintos.

Se exige una declaración revisada `draft2model.equivalencia_resultados` `0.1.0`, no una equivalencia inferida de valores parecidos:

```python
declaracion = {
    "contrato": "draft2model.equivalencia_resultados", "version_contrato": "0.1.0", "id": "comparacion-001",
    "actual": {"corrida_id": actual["corrida_id"], "huella": huella_resultados(actual),
               "geometria": actual["geometria"], "configuracion": actual["configuracion"]},
    "referencia": {"corrida_id": referencia["corrida_id"], "huella": huella_resultados(referencia),
                   "geometria": referencia["geometria"], "configuracion": referencia["configuracion"]},
    "unidades": actual["unidades"],
    "casos": [{"actual": "SX", "referencia": "SX-MANUAL", "justificacion": "Correspondencia revisada..."}],
    "hipotesis": {"actual": ["Hipótesis documentada..."], "referencia": ["Hipótesis documentada..."],
                  "justificacion": "Explicación técnica de equivalencia..."},
    "tolerancias": tolerancias,
    "justificacion": "Alcance y fundamento de la equivalencia...",
    "revision": {"estado": "borrador", "aprobacion": None}
}
```

La aprobación explícita usa los mismos campos declarados anteriores y `huella_declaracion(declaracion)`. Debe cubrir la declaración completa, incluyendo tolerancias. El software verifica que las referencias coincidan con las dos corridas abiertas y que el mapeo de casos sea uno a uno y cubra todos los casos. Unidades deben coincidir exactamente; dirección y ubicación conservan sus nombres exactos. La equivalencia física de hipótesis y ubicación requiere revisión humana: los textos y hashes no la demuestran.

Cada variable requiere `{absoluta, relativa, umbral_cero, unidad}` explícitos, finitos y no negativos; no hay valores predeterminados:

```python
tolerancias = {
    "periodo": {"absoluta": 0.01, "relativa": 0.02, "umbral_cero": 0.001, "unidad": "s"},
    "deriva": {"absoluta": 0.0001, "relativa": 0.02, "umbral_cero": 0.00001, "unidad": "1"},
    "cortante": {"absoluta": 0.1, "relativa": 0.02, "umbral_cero": 0.01, "unidad": "kN"}
}
```

Estos valores también son ejemplos fabricados. El criterio es `abs(actual-referencia) <= max(absoluta, relativa*abs(referencia))`; si `abs(referencia) <= umbral_cero`, usa exclusivamente la tolerancia absoluta. Absoluta y umbral_cero están en la unidad de la variable; relativa es razón adimensional. La frontera se incluye. No se divide por cero.

La comparación cubre la unión de filas de ambos contratos. Una fila faltante/null nunca pasa; dos contratos sin filas no generan éxito vacío. `comparacion_completa` describe esa cobertura de filas declaradas, sin acreditar que todas las salidas físicas necesarias estén presentes. Las omisiones de ambos análisis siguen en el informe. El resultado numérico de la comparación no valida hipótesis, cargas ni modelación.

## Reproducir con fixtures

Desde la raíz del proyecto:

```powershell
.\.venv\Scripts\python.exe -m draft2model.resultados_estructurales examples/resultados_estructurales_sinteticos.json
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_resultados_estructurales.py -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_evaluacion_estructural.py -v
```

Evaluación reproducible desde Python:

```python
from draft2model.resultados_estructurales import cargar_json, huella_resultados, huella_declaracion
from draft2model.evaluacion_estructural import evaluar_resultados
r = cargar_json("examples/resultados_estructurales_sinteticos.json")
reglas = cargar_json("examples/reglas_estructurales_sinteticas.json")
informe = evaluar_resultados(r, reglas, huella_resultados_esperada=huella_resultados(r),
                            huella_reglas_esperada=huella_declaracion(reglas))
```

CLI de evaluación: `python -m draft2model.evaluacion_estructural RESULTADOS.json REGLAS.json --huella-resultados SHA256_COMPLETO --huella-reglas SHA256_SIN_REVISION`. Imprime JSON y exige ambas huellas que el usuario pretende evaluar.

Las referencias de las dos fixtures son **placeholders sintéticos**, no identifican versiones reales del piloto ni configuraciones ejecutables. Todos sus números y aprobaciones son fabricados para comprobar el software. Las pruebas cubren fronteras debajo/en/sobre, cinco comparadores, fórmula, faltantes, aplicabilidad, unidades, fuentes, revisión/huella obsoleta, cambios, procedencia, mapeo de casos, equivalencia con referencias distintas, tolerancias cerca de cero y desbordamientos. No prueban el adaptador de un motor ni resultados ETABS reales.
