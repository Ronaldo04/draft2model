# Plan geométrico previo al adaptador ETABS

Estado: **propuesta inicial v0.1**, 15 de octubre de 2026. Transforma el [contrato de geometría](CONTRATO_GEOMETRIA.md) en superficies 3D trazables, en metros, para preparar un futuro adaptador ETABS.

**No** abre ETABS, no llama a su API, no genera un modelo analizable y no valida la estructura. `ejecutable_en_etabs` es siempre `false`.

Implementación: [`draft2model/plan_modelado.py`](../draft2model/plan_modelado.py). Pruebas: [`tests/test_plan_modelado.py`](../tests/test_plan_modelado.py). Ejemplo: [`examples/plan_modelado_sintetico.json`](../examples/plan_modelado_sintetico.json).

Este trabajo activa, solo para trabajo local, la propuesta de [TAREA_PLAN_MODELADO.md](TAREA_PLAN_MODELADO.md). Sus instrucciones de clonado, ramas y publicación no se aplicaron.

## Función

```python
from draft2model.plan_modelado import preparar_plan_modelado
plan = preparar_plan_modelado(geometria)  # dict con un contrato draft2model.geometria v0.1
```

Es una función pura:

- no modifica la entrada;
- no lee ni escribe archivos;
- no usa red, ETABS ni estado externo;
- devuelve un diccionario independiente de la entrada, sin referencias compartidas, serializable con JSON estricto (sin `NaN` ni `Infinity`) y determinista, sin marcas de tiempo.

Reutiliza `validar_geometria()` y su copia `geometria_m`, ya normalizada a metros. No duplica la validación. Las coordenadas son las del contrato (x, y en planta; z es la cota del nivel), nunca coordenadas de imagen.

## Estados de origen

| `estado_origen` | Condición | Superficies |
| --- | --- | --- |
| `inconsistente` | El validador informa errores. | Ninguna. Se devuelve un diagnóstico con errores y bloqueos. |
| `consistente_con_faltantes` | Hay faltantes declarados o derivados. | Solo los muros con todos sus datos; el resto queda en `omisiones`. |
| `consistente_completa_sin_aprobacion_vigente` | Sin faltantes; la geometría no está aprobada o su aprobación no corresponde a la huella actual. | Todas las calculables. |
| `consistente_completa_con_aprobacion_vigente` | El validador indica `disponible_para_modelado`. | Todas las calculables. |

`origen.validacion` incluye del validador: `consistente`, `disponible_para_modelado`, `datos_sinteticos`, `errores`, `advertencias`, `faltantes` y `bloqueos`.

`origen.revision` resume el estado de revisión de la geometría (`estado`, `aprobacion_registrada`, `aprobacion_vigente`) sin copiar quién aprobó ni la fecha. **El plan no hereda esa aprobación:** `aprobacion_plan` es `null` y ningún estado de revisión se modifica.

## Contrato del plan v0.1

| Campo | Contenido |
| --- | --- |
| `contrato`, `version_contrato` | `draft2model.plan_modelado`, `0.1.0`. |
| `caso` | `id` de la geometría, o `null` si no se puede leer. |
| `ejecutable_en_etabs` | Siempre `false`. |
| `estado_origen`, `origen` | Estado anterior; contrato, versión y `huella_contenido` de la geometría (`null` si es inconsistente); resumen de validación y revisión. |
| `unidades` | `longitud: m`, `area: m2` y `unidad_longitud_origen` (`m`, `cm` o `mm`). |
| `procedencia` | Copia de la procedencia de la geometría, incluida la marca `sintetico`. |
| `orden_vertices` | `inicio_inferior`, `fin_inferior`, `fin_superior`, `inicio_superior`. |
| `superficies[]` | Una por muro calculable (ver abajo). |
| `omisiones[]` | Muros sin superficie, con su motivo. |
| `cobertura` | `completa`, `parcial` o `sin_superficies`, respecto de los muros declarados. |
| `bloqueos`, `limitaciones` | Motivos por los que el plan no es utilizable en ETABS y alcance del artefacto. |
| `aprobacion_plan` | Siempre `null`. |

Cada superficie contiene:

- `muro_id`, `nodo_inicio`, `nodo_fin`, `nivel_inferior` y `nivel_superior`;
- `espesor_m`, `longitud_m` (distancia en planta), `altura_m` (diferencia de cotas) y `area_bruta_m2` (longitud × altura);
- `vertices_m`: cuatro puntos `[x, y, z]`:
  `[[xi, yi, z_inf], [xf, yf, z_inf], [xf, yf, z_sup], [xi, yi, z_sup]]`;
- `procedencia` del muro o, si no la declara, la del contrato, con `procedencia_declarada_en: muro | contrato`;
- `observaciones`, si existen, y `naturaleza: propuesta_geometrica`.

**Omisiones:**

- `datos_faltantes`: lista los campos ausentes (`muros/<id>.espesor` o `niveles/<id>.cota`). No se completan ni se estiman.
- `calculo_derivado_no_valido`: el área bruta no es representable aunque longitud y altura sean finitas y positivas. Puede desbordar (`1e200 × 1e200` da infinito) o subdesbordar (`1e-200 × 1e-200` da `0.0`). `valores_no_validos` lo indica, por ejemplo `["area_bruta_m2"]`. El valor no se serializa ni se sustituye, y el área no se añade al contrato geométrico.

### Representabilidad numérica

Los problemas de representación de la geometría de origen los rechaza el validador ([contrato geométrico](CONTRATO_GEOMETRIA.md#representabilidad-numérica)):

- enteros fuera de binary64 (`10**1000`);
- normalización que convierte en `0` un valor distinto de cero;
- nodos o cotas que colapsan tras normalizar;
- longitud o altura no finitas.

En esos casos el plan queda `inconsistente`, sin superficies ni omisiones, con los errores del validador en `origen.validacion.errores`. Lo mismo ocurre con `unidad_longitud` de un tipo JSON inválido (lista, objeto, `null`, booleano o número): el plan informa `unidad_longitud_origen: null` y no lanza excepciones.

El plan toma longitud y altura de `derivados_m` del validador, que ahora están garantizadas como finitas y positivas. Solo el área es un cálculo propio y se comprueba por separado. Por precaución, también vuelve a comprobar longitud, altura y espesor antes de emitir una superficie.

Los resultados son aritmética de coma flotante sin redondear. Por eso el ejemplo muestra `7.800000000000001` como área de 3.0 × 2.6: no se aplica tolerancia ni redondeo, para no introducir criterios arbitrarios.

## Lo que el plan no es

- Las superficies son **propuestas geométricas**: no equivalen a objetos de área, secciones ni ejes locales de ETABS. El orden de vértices no define la orientación local.
- Faltan representación estructural, materiales, secciones, cargas, masa, condiciones de borde, diafragmas y la verificación del adaptador.
- El área bruta no descuenta aberturas y **no determina peso, masa ni resistencia**.
- El contrato de geometría v0.1 no define si los nodos son el eje o una cara del muro. La superficie pasa por los nodos y el espesor se informa sin desplazarla.
- No se infieren tipología, materiales, cargas, parámetros sísmicos ni admisibilidad por número de pisos, y no hay fórmulas de diseño ni reglas normativas.

## Ejemplo reproducible

El ejemplo se genera desde [`examples/geometria_sintetica.json`](../examples/geometria_sintetica.json), sin modificarlo:

```powershell
.\.venv\Scripts\python.exe -m draft2model.plan_modelado examples\geometria_sintetica.json --salida examples\plan_modelado_sintetico.json --sobrescribir
```

Sin `--sobrescribir`, el comando no reemplaza una salida existente. El archivo se escribe en UTF-8 con saltos de línea LF, para que sea idéntico byte a byte en cualquier sistema.

Códigos de retorno:

- 0: plan generado;
- 1: entrada ilegible (incluye claves repetidas o `NaN`) o salida existente;
- 2: geometría inconsistente; se escribe el diagnóstico.

Resultado esperado:

- `estado_origen`: `consistente_con_faltantes`;
- `cobertura`: `parcial`;
- superficies M1, M2 y M3;
- **una omisión esperada**: M4, por `datos_faltantes`, `muros/M4.espesor` (declarado como faltante en la geometría sintética);
- `procedencia.tipo: sintetico` y `datos_sinteticos: true`.

La prueba `test_ejemplo_reproducible_desde_geometria_sintetica` compara el archivo versionado con el plan regenerado y comprueba que la entrada no cambia.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_plan_modelado -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las 20 pruebas usan geometrías sintéticas con valores exactos en binario, para comparar sin tolerancias. Cubren:

- vértices y orden explícitos; muro oblicuo 3-4-5; cota negativa;
- equivalencia m/cm/mm;
- referencias rotas, longitud nula, altura nula o negativa y entradas que no son objeto;
- espesor o cota faltantes y propuestas parciales; faltante general;
- aprobación ausente, vigente y desactualizada;
- entrada intacta y salida sin referencias compartidas;
- determinismo y JSON estricto;
- origen inconsistente por desbordamiento de longitud o altura, subdesbordamiento, colapso tras normalizar y enteros enormes;
- `unidad_longitud` con tipos JSON inválidos;
- área no representable (infinita o cero) con longitud y altura finitas, como omisión explícita;
- reproducción del ejemplo y del comando.

## Historial del cambio compartido

La primera versión del plan (15 de octubre de 2026) señaló que `validacion_geometria` podía entregar `derivados_m` con `inf` y que su `a_dict()` no era JSON estricto. En la revisión se reprodujeron además dos fallos:

- `OverflowError` con enteros enormes;
- `TypeError` en el plan con `unidad_longitud` de tipo lista.

Los tres quedaron corregidos en el validador y en el plan. Las pruebas que antes aceptaban esos casos se sustituyeron por regresiones que exigen su rechazo controlado.
