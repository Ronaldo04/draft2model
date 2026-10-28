# Evaluador de lecturas de visión v0.1

Implementado para pruebas reproducibles de software; evaluación del piloto real pendiente. No llama a proveedores, no ejecuta OCR o ETABS y no genera una referencia humana. Complementa el [protocolo de evaluación](EVALUACION_VISION.md).

Código: [evaluacion_vision.py](../draft2model/evaluacion_vision.py). Pruebas: [test_evaluacion_vision.py](../tests/test_evaluacion_vision.py).

## Entradas

1. **Referencia revisada declarada**: contrato `draft2model.referencia_vision`, versión `0.1.0`. Incluye caso, procedencia, alcance, coordenadas, revisión declarada y observaciones. Cada observación tiene `id`, `tipo`, `valor`, `unidad`, `legibilidad` y lista `evidencia` con las reglas del contrato de extracción. Legibilidad: `legible` exige valor, `ilegible` exige null y `ambigua` se excluye de las métricas de observaciones. Las unidades desconocidas siguen explícitas.
2. **Extracción preliminar**: contrato existente, sin transformarlo a geometría. El evaluador utiliza siempre `valor_propuesto` y `unidad`, aun cuando haya correcciones o rechazos registrados. Así la puntuación inicial permanece separada de la lectura corregida.
3. **Correspondencias revisadas declaradas**: contrato `draft2model.correspondencias_vision`, versión `0.1.0`. Incluye caso, SHA256 canónico de referencia y extracción, revisión declarada, `pares` y `sin_respaldo`. Si las entradas cambian, deben revisarse las correspondencias y sus huellas.

La revisión declarada tiene `estado: revisado`, `revisor_declarado` y fecha AAAA-MM-DD; no verifica identidad ni competencia. Para expedientes reales, una propuesta de otro modelo no se convierte en referencia humana por llenar este bloque.

Cada par declara `observacion_id`, `candidato_id`, `principal`, `evidencia_correcta`, `indice_evidencia_referencia` e `indice_evidencia_candidato`. Los índices comienzan en cero. Una observación emparejada tiene exactamente un candidato principal; los adicionales se registran como duplicados. Un candidato no puede asignarse a dos observaciones.

El emparejamiento no se deduce por valor ni por proximidad. Lo decide la revisión del documento y sus regiones, antes de puntuar. `evidencia_correcta: true` exige el mismo archivo, página, hash y solapamiento positivo de regiones, sin tolerancias inventadas. Estas son comprobaciones necesarias; la confirmación de que la imagen respalda la lectura sigue siendo declarada por quien revisa. Si la localización es incorrecta, puede mantenerse la correspondencia con `evidencia_correcta: false` para medir el error.

`sin_respaldo` lista candidatos clasificados explícitamente como propuestas sin observación válida que los respalde. Un candidato sin emparejar no se considera automáticamente falso positivo: en una referencia parcial podría corresponder a una observación aún no anotada. Queda en `sin_clasificar`.

## Resultados

Las proporciones incluyen numerador y denominador. Con denominador cero devuelven `null`, nunca 0 % o 100 % por defecto.

| Resultado | Denominador y alcance |
| --- | --- |
| Cobertura | Observaciones legibles e ilegibles evaluables; una omisión cuenta como no cubierta. |
| Exactitud de valor legible emparejado | Observaciones legibles con candidato principal. Debe leerse junto con cobertura para no ocultar omisiones. |
| Exactitud de unidad emparejada | Observaciones no ambiguas con candidato principal; cuenta unidades desconocidas aparte. |
| Lecturas completas sobre legibles | Todas las observaciones legibles. Exige valor, unidad y evidencia correctos; las omisiones son fallos. |
| Abstenciones | Null correcto sobre ilegibles; null incorrecto sobre legibles. Una omisión no se acredita como abstención correcta. |
| Evidencia confirmada sobre emitidos | Pares con evidencia declarada correcta / todos los candidatos emitidos. Los no clasificados no reciben crédito; no equivale a exactitud de localización sobre todos los candidatos. |
| Duplicados, sin respaldo y sin clasificar | Listas separadas; no se mezclan ni se excluyen silenciosamente de la salida. |

Las métricas de observaciones también se entregan por tipo y lámina. La agrupación por lámina utiliza la primera evidencia de cada observación como región principal; evidencias adicionales pueden documentar notas o unidades. Valores numéricos se comparan directamente, sin conversión de unidades ni redondeo; textos se comparan exactamente, sin normalizar espacios o mayúsculas.

Se conservan procedencia, alcance, huellas y revisiones declaradas. `aprobacion_ingenieria` siempre es null. La evaluación compara JSON y no vuelve a abrir originales ni comprobar sus hashes físicos; eso corresponde al ingreso/revisión/gestión de evidencia.

## Ejemplo reproducible

Usar [referencia sintética](../examples/referencia_vision_sintetica.json), [extracción sintética existente](../examples/extraccion_sintetica.json) y [correspondencias sintéticas](../examples/correspondencias_vision_sinteticas.json). Los hashes de la evidencia son ficticios, no documentos reales.

```powershell
.\.venv\Scripts\python.exe -m draft2model.evaluacion_vision --referencia examples/referencia_vision_sintetica.json --extraccion examples/extraccion_sintetica.json --correspondencias examples/correspondencias_vision_sinteticas.json --salida tmp/evaluacion_vision_sintetica.json
```

El resultado sintético tiene cobertura 4/5, exactitud de valor 3/3 entre legibles emparejados y lecturas completas 2/4 entre todos los legibles. Esto demuestra por qué una exactitud condicionada alta no basta. No es precisión medida de ningún modelo de IA.

La salida no sobrescribe archivos existentes. Código de salida 0: reporte generado; 1: entradas inválidas, reporte existente o error de escritura; 2: argumentos CLI inválidos. La CLI es independiente y no modifica `draft2model/__main__.py`.

## Pendientes

- Preparar y revisar las observaciones reales del piloto y sus correspondencias.
- Generar candidatos con un modelo de visión, registrando imágenes, modelo, prompt y consumo.
- Ejecutar la comparación real, conservar propuestas originales y medir tiempo/costo con información de la corrida.
- Evaluar luego el efecto de correcciones humanas por separado. v0.1 solo puntúa propuestas originales.

La evaluación de una extracción inválida falla y no produce métricas aparentes. La tasa de respuestas estructuradas válidas sobre varias corridas, tiempo, costo y esfuerzo humano deben medirse en el registro de experimentos; este evaluador no inventa esos datos ni descarta corridas fallidas de un estudio.
