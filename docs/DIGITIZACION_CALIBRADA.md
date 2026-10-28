# Digitización calibrada local v0.1

`draft2model.digitizacion_calibrada.calibrar_digitizacion(propuesta, *, fuente_vigente, puntos_resueltos)` es una función pura que transforma propuestas visuales locales en coordenadas métricas en borrador. No abre imágenes, archivos, proveedores ni ETABS; no extrae coordenadas de píxeles ni asigna una escala nominal. Las coordenadas de IA por sí solas nunca fijan metros: se exigen al menos tres correspondencias con puntos métricos previamente resueltos.

La integración debe obtener `fuente_vigente` desde el original realmente verificado y `puntos_resueltos` desde su registro de resolución vigente, ajenos a la propuesta de IA. **La igualdad de metadatos o una cadena SHA256 no comprueban los bytes del original ni la autenticidad de una resolución.** Esa comprobación pertenece al servicio llamante. No pasar como registro confiable las coordenadas generadas por la misma propuesta visual.

## Contrato cerrado

Todos los objetos exigen exactamente las claves indicadas, sin adicionales. No hay valores por defecto. Entrada JSON, números finitos binary64, identificadores de 1–128 caracteres `[A-Za-z0-9_.:-]`, huellas SHA256 hexadecimales en minúsculas. Las listas numéricas deben ser listas JSON.

| Objeto | Claves y contenido |
| --- | --- |
| `propuesta` | `contrato: "draft2model.digitizacion_calibrada"`, `version: "0.1.0"`, `id`, `fuente`, `plano`, `limites`, `anclas`, `controles`, `puntos` |
| `fuente` / `fuente_vigente` | `original_id`, `sha256`, `pagina` (entero desde 1), `dibujo_id`, `bbox_pagina: [x0,y0,x1,y1]`. BBox no vacío, contenido en página normalizada `[0,1]²`. |
| `plano` | `id`, `ejes` (`["x","y"]`, `["x","z"]` o `["y","z"]`), `eje_constante` (el tercero), `valor_constante`, `unidad_longitud` (`m`, `cm` o `mm`). No se inventa la cota del plano ni se crea un nivel. |
| Cada ancla / control | `id`, `punto_resuelto` (clave del registro externo), `uv_local: [u,v]`, `fuente`, `plano_id` |
| `puntos_resueltos[id]` | `coordenadas: [a,b]` en los dos ejes declarados, `unidad_longitud`, `plano` completo idéntico al declarado, `fuente`, `huella_resolucion`, `referencias` (IDs documentales no vacíos y únicos). La huella identifica la resolución conservada por el servicio; el módulo no reproduce su algoritmo. |
| Cada punto nuevo | `id`, `uv_local`, `fuente`, `plano_id`, `relacionados` (IDs distintos de puntos resueltos usados como anclas/controles; al menos uno) |

`uv_local` expresa la posición dentro del bbox **de un dibujo**, con origen superior izquierdo, u hacia la derecha y v hacia abajo. Debe estar en `[0,1]²`; no expresa píxeles ni posición de toda la página. La salida conserva `uv_local`, añade `uv_pagina = [x0+u(x1-x0), y0+v(y1-y0)]` y coordenadas cartesianas en metros.

Original, SHA, página, dibujo y bbox deben coincidir exactamente en todo el cálculo. Cada ancla/control resuelto debe pertenecer también al mismo plano completo, incluida su cota y unidad. Una calibración no se transmite a otro detalle, página, planta ni versión del original. Planos inclinados con una base 3D arbitraria quedan fuera de esta versión.

## Límites obligatorios

`limites` exige estas nueve claves, todas numéricas, positivas y finitas:

| Campo | Significado |
| --- | --- |
| `residuo_ajuste_max_m` | Máxima distancia euclídea del ajuste a sus anclas; excederla rechaza el cálculo y conserva diagnóstico en la excepción. |
| `error_control_max_m` | Distancia máxima admisible a controles excluidos del ajuste. |
| `incertidumbre_max_m` | Límite del indicador por punto; excederlo conserva el borrador con `dentro_limite: false`. |
| `localizacion_uv` | Incertidumbre declarada de localización, como radio euclídeo en el dibujo normalizado; ≤1. Se aplica a anclas y puntos propuestos. |
| `referencia_m` | Incertidumbre declarada de los puntos métricos resueltos, en los dos ejes del plano. |
| `condicion_max` | Máximo cociente singular del diseño de anclas y de la parte lineal afín; ≥1. |
| `escala_min_m_por_uv`, `escala_max_m_por_uv` | Intervalo de escalas singulares de la transformación; mínimo estrictamente menor que máximo. |
| `coordenada_abs_max_m` | Máximo valor absoluto permitido en referencias, cota constante y puntos transformados. Admite coordenadas negativas y cero. |

Son criterios declarados del caso y del cálculo, **no límites normativos ni aprobación de ingeniería**. El módulo no propone valores físicos por defecto. Exige entre 3 y 1000 anclas, hasta 1000 controles y entre 1 y 10000 puntos nuevos. Los valores que se pierden a cero al convertir unidades se rechazan.

## Cálculo y exactitud

Se ajusta `[a,b] = A·[u,v] + t`. Para tres anclas se reutiliza `revision_superposicion.transformacion`, incluyendo su rechazo previo de forma triangular `<1e-3` en ambos espacios. Con anclas extra se calcula mínimos cuadrados sobre **todas** las anclas, centrando las coordenadas locales; no se selecciona a posteriori el subconjunto que más convenga. Se verifican rango, no colinealidad, condición, escalas singulares y residuos. Se admiten rotación, traslación, escala y cizalla; no perspectiva ni deformación local del papel.

`calculo_posible: true` significa que el ajuste pasó estos requisitos y sus residuos. No significa exactitud documental. Cada ancla y control conserva punto resuelto, coordenadas métricas, ubicación local, referencias, huella, predicción y distancia residual. Se conserva una `huella_entrada` del JSON canónico, incluyendo el registro efectivamente usado, metadatos vigentes y límites.

Los controles nunca participan en el ajuste. Para `exactitud_verificada_en_controles: true` se exigen al menos tres controles no colineales y bien condicionados, errores ≤ `error_control_max_m`, IDs, ubicaciones y coordenadas físicas distintos de las anclas y entre controles; sus IDs documentales de resolución tampoco pueden compartir referencias con las anclas. Tres anclas con residuo cero, anclas extra utilizadas en ajuste, uno/dos controles o controles colineales no acreditan exactitud.

Esta bandera acredita **únicamente el contraste numérico en los controles declarados**, nunca todos los puntos nuevos ni la autenticidad de correspondencias/evidencias. La separación de referencias no demuestra independencia estadística ni ausencia de errores comunes de la documentación. Un error de control conserva cálculo y propuesta con la bandera en falso. Ninguna bandera elimina el estado borrador.

Por punto se informa `extrapolacion`, según el casco convexo de anclas, sin asumir continuidad. También se entrega el indicador:

`I(p) = ||A||₂ · localizacion_uv · (1 + Σ|wᵢ(p)|) + (referencia_m + residuo_ajuste_max_observado_m) · Σ|wᵢ(p)| + error_control_max_observado_m`.

`wᵢ` son los pesos de predicción afín de mínimos cuadrados. Su amplificación aumenta fuera de la distribución de anclas. Sin controles, el último término es cero **por ausencia de observaciones**, no por exactitud; en el resumen `error_control_max_m` es `null`. El indicador es conservador e indicativo, no un intervalo estadístico ni cota garantizada. Solo cubre los dos ejes ajustados; la cota constante es declarada, sin incertidumbre verificada. No cubre correspondencias erróneas, errores sistemáticos ni deformación no afín. No se debe acreditar una tolerancia global con él.

## Uso e integración

```python
from draft2model.digitizacion_calibrada import calibrar_digitizacion, ErrorDigitizacion

# Objetos construidos por el servicio, según el contrato anterior.
try:
    resultado = calibrar_digitizacion(propuesta,
                                     fuente_vigente=original_comprobado,
                                     puntos_resueltos=registro_resuelto_vigente)
except ErrorDigitizacion as error:
    diagnostico = {"codigo": error.codigo, "mensaje": str(error), "detalles": error.detalles}
```

Las entradas permanecen intactas y la salida puede serializarse con `json.dumps(..., allow_nan=False)`. No hay persistencia ni endpoints en este módulo. El servicio deberá conservar la propuesta/registro que corresponden a la huella, comprobar la vigencia antes de incorporar puntos y mantener separados puntos calculados, controles y resoluciones originales. Esta etapa no crea superficies, conexiones, niveles, materiales, cargas, suelo ni aprobaciones. La salida siempre contiene `revision: {estado: "borrador", aprobacion: null}` y `disponible_para_modelado: false`.

Prueba focal reproducible, exclusivamente sintética:

```powershell
.venv/Scripts/python.exe -B -m unittest tests.test_digitizacion_calibrada -v
```

El recibo de esta revisión está en `seguimiento/DIGITIZACION_CALIBRADA_350.json`, con resultados y SHA256 del código, pruebas y guía. No acredita integración de UI/API, planos reales, suite completa ni ejecución ETABS.
