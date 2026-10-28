# Benchmark 311: preparación (sin medición)

Estado: **pendiente de referencia humana**. No existe `referencia_humana.json` ni correspondencias revisadas. Esta carpeta no contiene ni acredita precisión, cobertura o exactitud reales.

## Cohortes (ver `INVENTARIO_COHORTES_311.json`, generado por `inventario_311.py`)

Caso `provisional-001`. Seis peticiones registradas: OpenAI 4/5 y Gemini 2/5 consumidas. **No se ejecuta ninguna petición nueva.**

| Cohorte | Modelo devuelto | Estado | Propuestas originales (antes de corrección) | Láminas |
|---|---|---|---|---|
| openai_1 | gpt-5.4-2026-03-05 | pendiente de revisión | 34 (cota 14, etiqueta 13, elemento 7) | L0001, L0002, L0003 |
| openai_2 | gpt-5.4-2026-03-05 | **fallida** (truncada a 8192 tokens; nada importado) | — | — |
| openai_3 | gpt-5.4-2026-03-05 | pendiente de revisión | 60 (cota 26, elemento 34) | L0001 |
| openai_4 | gpt-5.4-2026-03-05 | pendiente de revisión | 102 (cota 40, etiqueta 54, elemento 8) | L0002, L0003 |
| gemini_1 | gemini-3.8-flash | pendiente de revisión | 32 (cota 19, etiqueta 10, elemento 3) | L0001 |
| gemini_2 | gemini-3.8-flash | **fallida** (71 crudos; validación inicial: 12 inválidos, 0 importados) | — | — |

- Rutas de extracción de cada cohorte: `data/private/provisional-001/vision/respuestas/<id>/extraccion.json`. Ruta y SHA256 en el inventario.
- Comprobado por código:
  - el SHA de `respuesta_api.json` coincide con su recibo;
  - las extracciones son consistentes;
  - los recuentos coinciden con METRICAS_EXTRACCION_09;
  - todos los originales citados pertenecen a las 3 láminas del kit humano.
- **No se suman cohortes**: comparten láminas y recortes. 34 + 60 + 102 + 32 = 228 son registros, no objetos únicos.
- **Registros derivados, no ligados a un recibo**: `34528ff1…` y `f51b8418…`. Son dos copias de una importación web de Gemini 2 con cuarentena: 59 candidatos y 12 en cuarentena, de QA 09/239.
  - Son adaptaciones posteriores a la validación, no propuestas crudas.
  - Incluyen tipos fuera del protocolo (cantidad, propiedad, carga, parámetro, resultado_impreso).
  - Si se evalúan, como cohorte derivada aparte y una sola copia; las 12 en cuarentena no se ocultan.
- Las versiones de `extracciones/` (importaciones y correcciones asistidas, p. ej. la reubicación de C039) **no** son propuestas originales.

## Cuando el usuario entregue `referencia_humana.json`

Ejecutar desde `PROYECTO FINAL`, con `.venv/Scripts/python.exe -X utf8`:

1. Recepción (valida con `evaluacion_vision.validar_referencia` y contra `referencia_humana_308/fuentes.json`):
   `seguimiento/claude_ruta/preparacion_benchmark_311/recepcion_311.py recibir --referencia RUTA/referencia_humana.json --salida tmp/benchmark_311/recepcion.json`
   - Código 0: `protocolo_completo` (≥30 observaciones, 3 clases, 3 láminas) o `referencia_parcial`. Con una parcial, las conclusiones valen solo para su muestra.
   - Código 2: entrada ausente o inválida. Código 3: caso, lámina o hashes incompatibles con el kit.
   - La firma es declarada, no autenticada. El helper nunca completa revisor ni fecha.
2. Sugerencias por cohorte primaria (una ejecución por cohorte; salida nueva, nunca sobrescribe):
   `recepcion_311.py sugerir --referencia REF --extraccion data/private/provisional-001/vision/respuestas/<id>/extraccion.json --cohorte openai_1 --salida tmp/benchmark_311/propuesta_openai_1.json`
   - Empareja solo por archivo, página, `original_sha256`, solapamiento de regiones y tipo. **Nunca por valor.**
   - Todo queda `pendiente`: `principal` y `evidencia_correcta` en null. El evaluador oficial rechaza la propuesta.
   - Lista `candidatos_sin_sugerencia` (posibles sin respaldo o sin clasificar), `observaciones_sin_candidato` (posibles omisiones) y `candidatos_varias_observaciones`.
3. **Decisión humana**: escribir el contrato oficial `draft2model.correspondencias_vision` (pares, principal/duplicado, `evidencia_correcta`, `sin_respaldo`) con la revisión declarada de quien la hizo. No se generan automáticamente.
4. Verificación previa: `recepcion_311.py verificar --referencia REF --extraccion EXT --correspondencias CORR`. Código 4 si están pendientes, si la huella está desactualizada o si son inválidas.
5. Medición oficial, por cohorte y por separado:
   `python -m draft2model.evaluacion_vision --referencia REF --extraccion EXT --correspondencias CORR --salida tmp/benchmark_311/evaluacion_<cohorte>.json`

## Reglas de métricas (sin umbral comercial)

- Cada métrica es numerador / denominador. Con denominador 0, `proporcion` es null: **abstención**, nunca 0 % ni 100 %.
- Falta de referencia o de correspondencias revisadas: no hay métrica.
- Cohortes separadas por proveedor, modelo y petición. Las fallidas se informan como fallos, no como 0 aciertos.
- Se evalúan propuestas **originales**, no valores corregidos.
- Duplicados, omisiones, sin respaldo y sin clasificar se conservan según el contrato.
- Los candidatos de tipos ajenos a las clases de la referencia solo pueden quedar sin respaldo o sin clasificar.
- No ajustar tolerancias ni umbrales mirando resultados.

## Pruebas

`python -m unittest seguimiento/claude_ruta/preparacion_benchmark_311/test_recepcion_311.py`: 9 pruebas con fixtures **sintéticas** (caso «sintetico-311»), entre ellas:
- referencia ausente, plantilla vacía o sin revisión;
- protocolo completo y parcial;
- caso u hash incompatibles;
- sugerencias pendientes sin valor (un candidato con el mismo valor en otra lámina no se sugiere);
- el evaluador rechaza la propuesta;
- huella desactualizada y mezcla de procedencia;
- control positivo sintético;
- la salida no se sobrescribe.

Además, en seco con el kit real y sin referencia: código 2, sin salida.
