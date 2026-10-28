# Conversión explícita de lecturas revisadas a geometría

Estado: implementación local verificable, 16 de octubre de 2026.

`draft2model/conversion_geometria.py` convierte una versión de extracción comprobada y un manifiesto de correspondencias declarado por el operador en una geometría `draft2model.geometria` v0.1.0. La salida está en **borrador y sin aprobación**; puede importarse con `gestion_geometria.importar_geometria`. Revisa lecturas y transforma unidades físicas, pero no interpreta automáticamente planos ni decide conectividad.

## Recorrido reproducible sin servicios externos

Con el entorno instalado y desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m examples.conversion_sintetica.crear_demo --raiz tmp/demo_conversion --caso conversion-demo-sintetica
```

El ejemplo crea un PDF sintético, lo registra, genera su revisión documental, importa cuatro candidatos sintéticos, registra revisiones explícitas de esas lecturas, ejecuta la conversión y finalmente importa la geometría como versión geométrica comprobada. Devuelve IDs y ruta de resultados en JSON. `comprobacion_correcta` debe ser `true`, `datos_sinteticos` debe ser `true` y `disponible_para_modelado` debe ser **`false`**, porque no se aprueba ingeniería.

No sobrescribe casos existentes. Para repetir, usar otra raíz o `--caso`. El manifiesto de referencia está en `examples/conversion_sintetica/manifiesto.json`; el script adapta su caso y conserva los otros campos. La lámina y los valores son exclusivamente de prueba de software; su conectividad y coordenadas son declaraciones del ejemplo.

## Uso sobre una versión existente

La conversión recibe una raíz privada, un caso y el ID de una **versión de extracción registrada**. No acepta un JSON de exportación suelto como prueba de integridad:

```powershell
.\.venv\Scripts\python.exe -m draft2model.conversion_geometria --raiz data/private --caso CASO --extraccion VERSION_EXTRACCION --manifiesto ruta/manifiesto.json
```

Códigos de salida: `0` conversión publicada; `1` solicitud, archivo o escritura inválidos; `2` evidencia o manifiesto rechazados. `--help` describe los argumentos. La CLI vive en este módulo y no modifica el despachador `draft2model.__main__`.

API equivalente:

```python
from pathlib import Path
from draft2model.conversion_geometria import convertir_lecturas
from draft2model.gestion_geometria import importar_geometria

resultado = convertir_lecturas(Path("data/private"), "CASO", "VERSION_EXTRACCION", Path("manifiesto.json"))
version = importar_geometria(Path("data/private"), "CASO", resultado.ruta / "geometria.json")
assert version.comprobacion.correcta
assert not version.comprobacion.validacion["disponible_para_modelado"]
```

La aprobación geométrica posterior debe seguir su operación explícita de revisión y aprobación. Confirmar una lectura no constituye aprobación técnica de la geometría, del modelo ni de la estructura.

## Manifiesto v0.1.0

Todos los campos son explícitos; los campos desconocidos o ausentes se rechazan. Consultar el ejemplo JSON completo antes de preparar un caso.

| Campo | Requisito |
| --- | --- |
| `contrato`, `version_contrato` | `draft2model.conversion_geometria`, `0.1.0`. |
| `caso` | Mismo identificador que la extracción comprobada. |
| `datos_sinteticos` | Booleano declarado por el operador, nunca inferido de la palabra `expediente`. |
| `operador_declarado` | Texto no vacío. Identidad no autenticada. |
| `procedencia` | Exactamente `tipo` y `descripcion`. Tipo `sintetico` si la marca es `true`; `plano` si es `false`. |
| `unidad_longitud` | `m`, `cm` o `mm`; unidad única de salida geométrica. |
| `sistema_coordenadas` | Exactamente `cartesiano_ortogonal`. |
| `ejes` | Textos no vacíos `origen`, `direccion_x` y `direccion_y`, declarados por el operador. |
| `escala` | `metodo: coordenadas_fisicas_declaradas` y `descripcion` no vacía. No hay medición de píxeles ni conversión desde un denominador de escala gráfico. |
| `niveles` | Lista no vacía de `{id, cota}`. |
| `nodos` | Lista no vacía de `{id, x, y}`. |
| `muros` | Lista no vacía de `{id, nodo_inicio, nodo_fin, nivel_inferior, nivel_superior, espesor, referencias}`. La conectividad y las referencias se declaran explícitamente. |

Cada cota, coordenada o espesor admite exactamente una de estas dos formas:

```json
{"candidato": "C001"}
```

Utiliza el `valor_revisado` y la `unidad_revisada` de una **cota** revisada con evidencia completamente comprobada. Solo acepta números finitos conocidos y unidades físicas admitidas. No usa el valor propuesto cuando hay una revisión.

```json
{"valor": 0, "unidad": "m", "justificacion": "Origen elegido por el operador", "referencias": ["C001"]}
```

Esta segunda forma declara un valor físico del operador y registra referencias revisadas de contexto. Las referencias no demuestran que ese valor se leyó literalmente del candidato: la trazabilidad lo identifica como `declaracion_operador`. Permite fijar un origen, una alineación o una coordenada obtenida por trabajo externo, sin atribuir el cálculo al software. Todas las referencias deben existir y estar revisadas; se exige justificación explícita. El operador asume la correspondencia entre esas referencias y el valor que declara.

Las referencias de un muro son el contexto de la conectividad declarada. El software verifica que sus extremos y niveles existan y que su longitud, altura y espesor sean positivos según el contrato; no infiere qué línea del plano es un muro ni comprueba semánticamente esa conectividad frente a la imagen.

## Comprobación y resultados persistidos

Antes de convertir se carga la versión con la gestión de extracciones y se recomprueban originales, revisiones documentales, imágenes citadas y huellas. Se utiliza `exportar_revisados` con su inventario comprobado, y se rechaza toda referencia a candidatos pendientes, rechazados o inexistentes. Cada referencia utilizada debe tener `estado_referencia: comprobada`; una comprobación parcial no basta.

La gestión pública de exportaciones se ejecuta de nuevo antes de publicar y se compara la exportación resultante con la prevista. También se contrastan los bytes persistidos de la exportación con el registro generado. La salida geométrica se comprueba con `validar_geometria`; esta primera versión exige geometría completa, sin valores críticos desconocidos ni faltantes. No completa datos ausentes.

Los valores pasan por una conversión explícita entre `m`, `cm` y `mm`. Se rechazan booleanos, números no finitos, enteros fuera de representabilidad exacta binary64 y conversiones que desbordan o convierten un valor distinto de cero en cero. El validador geométrico aplica después sus controles de representabilidad y geometría básica.

Cada conversión crea una carpeta nueva, sin sobrescribir:

```text
<raiz>/<caso>/conversiones_geometria/<uuid>/
  geometria.json
  trazabilidad.json
  manifiesto.json
  exportacion.json
```

`manifiesto.json` conserva los bytes exactos de entrada; `exportacion.json`, los de la exportación comprobada. `trazabilidad.json` contiene el ID del caso, extracción, exportación y conversión, SHA256 de ambos archivos y de la geometría, huella del contenido geométrico, huella del expediente, alcance original, procedencia de extracción, naturaleza sintética declarada, operador declarado, ejes y escala. Cada campo transformado registra ruta, modo de obtención, candidatos, valor y unidad de origen y destino. Cada muro registra por separado la conectividad declarada. La geometría conserva exclusivamente los campos de su contrato, y el registro de trazabilidad queda separado.

Las escrituras de la conversión reutilizan la publicación atómica de la gestión de extracciones. Si el manifiesto se rechaza no se publica geometría. Una exportación ya creada antes de detectar un cambio concurrente o un fallo de escritura puede permanecer como registro independiente; no significa que exista una conversión aceptada.

## Naturaleza de los datos y límites

La gestión existente admite en casos privados extracciones de `procedencia.tipo: expediente`, pero no registra por sí misma si el contenido de los PDFs es real o sintético. `expediente` describe el contenedor y no demuestra realidad. Por eso el manifiesto exige una declaración explícita de naturaleza y la conserva. Si una extracción o cualquiera de sus candidatos exportados declara un método sintético, no se admite producir geometría de tipo `plano`. Las contradicciones entre marca y procedencia se rechazan. El ejemplo conserva métodos y geometría sintéticos.

La identidad del operador y la naturaleza declarada **no se autentican**; el software no puede determinar si un archivo sin marca sintética corresponde realmente a una obra. Tampoco detecta una declaración falsa coherente con todos los registros alterados. No convierte unidades desconocidas, píxeles, bbox o proporciones de imagen en metros. No interpreta escala gráfica, rotación, conectividad, aberturas, elementos de confinamiento ni cargas. No genera ni ejecuta ETABS.

Persisten los límites de concurrencia de la gestión local: no hay bloqueo entre procesos ni firma externa de los archivos. Las huellas registran evidencia de las entradas exactas al momento de la conversión; no son una autenticación criptográfica de personas ni una garantía contra reescrituras coherentes completas posteriores. Este módulo no agrega un comando de revalidación de conversiones ya guardadas; conservar las entradas y volver a ejecutar sobre la versión vigente permite obtener una nueva conversión comprobada.

## Evidencia de validación

Se ejecutó el ejemplo completo con `--raiz tmp/conversion_demo_verificada --caso conversion-demo-sintetica`: expediente, revisión documental, cuatro candidatos revisados, exportación, conversión e importación geométrica finalizaron con comprobación correcta y modelado bloqueado por ausencia de aprobación. IDs observados: extracción `c95cb92a53bf4c1daf8cfc7d937f384b`, conversión `cf271c59abad4880809001c926ca2854`, geometría `2e82e7f8ebef484aa2e9653a889cd03e`. Estos datos están en `tmp/` y no forman una dependencia del ejemplo.

La combinación de `tests.test_conversion_geometria`, `tests.test_gestion_geometria` y `tests.test_validacion_geometria` pasó **69 pruebas, 1 omitida** por restricciones para crear enlaces. Las 10 pruebas nuevas cubren el recorrido integrado, equivalencia de salida `m/cm/mm`, trazabilidad y hashes, geometría borrador, candidatos excluidos, evidencias alteradas, exportación alterada durante publicación, unidades desconocidas, IDs y conectividad inválidos, píxeles y escala no admitidos, valores críticos desconocidos y números inválidos, naturaleza sintética y códigos de la CLI.

En el sandbox de Windows se fijó `tempfile.tempdir` dentro del proyecto para evitar errores de permisos al renombrar temporales del sistema:

```powershell
.\.venv\Scripts\python.exe -c "import pathlib,tempfile,unittest; p=pathlib.Path('tmp/pruebas_conversion'); p.mkdir(parents=True,exist_ok=True); tempfile.tempdir=str(p.resolve()); r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromNames(['tests.test_conversion_geometria','tests.test_gestion_geometria','tests.test_validacion_geometria'])); raise SystemExit(not r.wasSuccessful())"
```
