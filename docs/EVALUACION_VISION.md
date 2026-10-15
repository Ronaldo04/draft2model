# Evaluación inicial de visión multimodal

Estado: protocolo preparado; extracción visual y evaluación aún no ejecutadas.

El [evaluador de lecturas](EVALUADOR_VISION.md) está implementado con ejemplos sintéticos, correspondencias explícitas y métricas reproducibles. La referencia real y las corridas con visión siguen pendientes.

La [preparación de entrada y adaptación de respuestas](ENTRADA_VISION.md) conserva imágenes y coordenadas en paquetes locales. No realiza llamadas a modelos.

## Objetivo

Medir si un modelo de visión interpreta cotas, etiquetas y elementos de planos con evidencia localizable. La primera prueba no genera geometría ni modelos ETABS. OCR es apoyo opcional; la prueba base utiliza visión sin OCR para poder medir su aporte por separado.

El caso provisional-001 conserva `fuera_mvp_declarado`. Sus resultados solo acreditan procesamiento del documento; no demuestran desempeño para albañilería confinada de uno o dos niveles ni validación estructural.

## Muestra y referencia

Utilizar los tres documentos y los siete recortes locales registrados. Preparar una referencia manual de al menos 30 observaciones, distribuida entre cotas, etiquetas y elementos y entre las tres láminas. Incluir datos legibles, ilegibles y unidades no indicadas. Si una categoría no aparece, registrarlo y no inventar observaciones para completar cuotas.

La plantilla [referencia_vision.csv](../examples/referencia_vision.csv) está vacía: no contiene valores extraídos. Copiarla a `data/private/provisional-001/evaluacion_vision/` para anotar el piloto. Cada observación identifica archivo, página, recorte y región en `pagina_visible_normalizada`. Las coordenadas se refieren a la página completa, incluso al leer un recorte. Registrar los hashes del original y de la imagen consultada.

`valor_referencia_json` contiene un número JSON para cotas, una cadena JSON para etiquetas/elementos o `null` para ilegibles. Las unidades son `m`, `cm`, `mm`, `desconocida` o `no_aplica`. No deducir metros a partir de una cifra aislada. Una unidad explícita en una nota general solo puede aplicarse registrando también esa evidencia.

La referencia requiere revisión humana antes de puntuar. Una lectura producida por otro modelo se conserva como propuesta, no como verdad de referencia. Registrar revisor declarado, fecha y discrepancias pendientes; las observaciones ambiguas no se incluyen en exactitud numérica.

## Ejecución comparable

1. Conservar la referencia aparte de la entrada del modelo para evitar que reciba las respuestas.
2. Probar primero vista general para contexto y luego los recortes para lectura detallada. Pedir valores, unidades y evidencia; permitir `null` y `desconocida`.
3. Guardar proveedor, identificador exacto del modelo, fecha, parámetros, prompt completo, hashes de las imágenes enviadas, respuesta original, tiempo y consumo informado por la API. El proveedor todavía no está seleccionado ni conectado.
4. Adaptar la respuesta al contrato de extracción preliminar sin completar datos faltantes. Si el proveedor devuelve coordenadas del recorte, transformarlas a la página mediante la transformación registrada; no confundir píxeles o coordenadas del recorte con coordenadas de página.
5. Validar el registro con el inventario local antes de revisar valores. Conservar respuestas inválidas y errores; no descartarlos del denominador.
6. Comparar con la referencia antes de corregir candidatos. Conservar por separado resultados originales y resultados posteriores a revisión humana.

Toda ejecución con un proveedor externo requiere definir acceso, costo y qué archivos se enviarán. Este protocolo no transmite planos ni necesita credenciales.

## Mediciones

La referencia delimita regiones y observaciones evaluables. Emparejar por archivo, página, tipo y región, y confirmar manualmente correspondencias ambiguas. No emparejar únicamente por valor: una misma cota puede repetirse. Registrar el criterio de coincidencia espacial antes de evaluar.

| Medición | Cálculo o registro |
| --- | --- |
| Cobertura | Observaciones de referencia con candidato correspondiente / observaciones evaluables. |
| Exactitud de valor | Coincidencias exactas / observaciones legibles con candidato. Para cotas comparar números sin conversión de unidades; para texto conservar lectura original y documentar cualquier normalización. |
| Exactitud de unidad | Unidades correctas / observaciones emparejadas; informar `desconocida` por separado. |
| Lecturas correctas completas | Observaciones con valor, unidad y evidencia correctos / observaciones legibles evaluables. Una omisión cuenta como fallo. |
| Evidencia utilizable | Candidatos con archivo, página y región correctos / candidatos emitidos. Un hash coincidente no prueba que la región respalde el valor. |
| Duplicados y propuestas sin respaldo | Contar por separado duplicados y candidatos que no corresponden a ninguna observación dentro de las regiones evaluadas; revisar antes de clasificarlos. |
| Abstención | Contar `null` correctos sobre ilegibles y `null` incorrectos sobre legibles. |
| Respuesta estructurada | Ejecuciones que cumplen el contrato / ejecuciones realizadas. |
| Esfuerzo de revisión | Candidatos corregidos, rechazados y tiempo de revisión registrado. |
| Costo y tiempo | Consumo reportado, costo según tarifa documentada y duración por ejecución. No estimar consumo ausente como cero. |

Informar conteos y denominadores por tipo y lámina, además del total. Una muestra pequeña no permite afirmar precisión general. No hay un umbral aprobado para automatizar geometría; deberá definirse tras la prueba inicial.

## Entregables y siguiente decisión

- Referencia anotada y revisada, guardada en privado.
- Respuestas originales, candidatos validados y comparación antes de correcciones.
- Lista de errores: lecturas, unidades, omisiones, duplicados y localización.
- Decisión documentada sobre ampliar recortes, mejorar el prompt o comparar otro modelo. Una comparación posterior con OCR debe usar las mismas observaciones y distinguir el aporte adicional.

La revisión de lecturas no equivale a aprobación de ingeniería. La conversión a geometría exige después relaciones espaciales, escala, niveles y los controles del contrato geométrico.
