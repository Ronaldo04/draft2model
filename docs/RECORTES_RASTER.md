# Recortes raster trazables y paquetes visuales locales

`recortes.generar_recorte()` admite originales PNG/JPEG registrados, además del recorrido PDF existente. La rama raster usa una sola página, aplica `ImageOps.exif_transpose` y convierte a RGB, igual que `revision_documental.revisar_expediente()` y el visor local. Conserva los originales exactos y no produce datos de ingeniería ni aprobaciones.

## API y recorrido

```python
from draft2model.recortes import generar_recorte
from draft2model.entrada_vision import preparar_paquete, cargar_paquete, adaptar_respuesta

recorte = generar_recorte(manifiesto, 'L0001', 1, [0.1, 0.2, 0.8, 0.7])
solicitud = preparar_paquete(manifiesto, revision_documental, [recorte])
datos, sha256_solicitud, expediente, archivos = cargar_paquete(manifiesto, solicitud)
# Una respuesta local debe citar el ID y SHA256 exactos de esa solicitud.
extraccion = adaptar_respuesta(manifiesto, solicitud, respuesta,
    proveedor='origen-declarado', modelo='modelo-declarado', modo_prueba=True)
```

No requiere proveedor, clave, envío ni proceso externo. `adaptar_respuesta` solo adapta una respuesta suministrada; no genera candidatos. En pruebas `modo_prueba=True` conserva marca sintética. Los valores desconocidos continúan siendo null, las unidades desconocidas permanecen declaradas y todos los candidatos quedan en revisión pendiente con historial vacío. `registrar_respuesta()` conserva además los bytes originales de la respuesta en una carpeta nueva y su registro mantiene `aprobacion_ingenieria:null`.

`generar_recorte()` devuelve `<caso>/recortes/<UUID>/recorte.json` junto con `recorte.png`. Cada llamada crea otro UUID y no sobrescribe las versiones previas. `preparar_paquete()` conserva sus artefactos habituales en `vision/solicitudes/<UUID>`.

El parámetro `dpi` de `generar_recorte` conserva la validación y el comportamiento PDF existente. En raster no determina resolución, tamaño físico ni escala; no se publica como DPI de render raster. El recorte usa píxeles de la imagen orientada y solo reduce resolución cuando supera su presupuesto de píxeles.

## Contrato raster explícito

Se conserva `sistema_coordenadas: pagina_visible_normalizada`, usado por candidatos y visor. Una coordenada normalizada se refiere siempre a la imagen completa orientada EXIF: origen superior izquierdo, X derecha e Y abajo.

El registro raster tiene los campos comunes de un recorte —versión, UUID, caso, archivo, página, etiqueta, hashes, alcance, bbox, imagen y estado— y estos campos geométricos:

| Campo | Significado |
| --- | --- |
| `tipo_fuente` | `raster`. |
| `espacio_pagina_visible` | `raster_px_exif_orientado`. |
| `pagina_visible_px` | Ancho/alto después de aplicar EXIF. |
| `dimensiones_original_px` | Ancho/alto del raster almacenado antes de EXIF. |
| `orientacion_exif` | Entero 1–8; si falta el tag se usa 1. |
| `dpi_original_declarado` | Metadato del archivo o null; nunca se interpreta como escala física. |
| `original_a_pagina_visible_px` | Matriz afín reversible desde los bordes de píxel originales. |
| `pagina_visible_a_original_px` | Inversa de la matriz anterior. |
| `bbox_pagina_visible_px` | Límites enteros del recorte en la imagen orientada. |
| `dimensiones_px` | Ancho/alto del PNG de recorte conservado. |
| `pixel_a_pagina_visible` | Transformación de píxeles del PNG conservado a píxeles de imagen orientada. |
| `remuestreo` | `LANCZOS_si_reduccion`. |
| `escala_geometrica` | Siempre null. |

Todas las matrices afines tienen orden `[a,b,c,d,e,f]`: `x'=a*x+c*y+e`, `y'=b*x+d*y+f`. Operan sobre **bordes** de píxel: el centro del píxel `(i,j)` está en `(i+0.5,j+0.5)`. Las matrices EXIF incluyen rotaciones, reflexiones y transposiciones; no son medidas métricas.

El bbox se rasteriza con `floor` en sus límites iniciales y `ceil` en los finales. Por ello puede incluir una franja exterior inferior a un píxel por lado. La adaptación utiliza la transformación del PNG realmente conservado, incluido redondeo/reducción, y luego divide por `pagina_visible_px`; no interpola directamente el bbox solicitado. No recorta silenciosamente evidencia fuera de página.

En la solicitud visual, cada imagen `REC` raster lleva `tipo_fuente`, `espacio_pagina_visible`, `pagina_visible_px` y `pixel_a_pagina_visible`. **No tiene `pagina_visible_pt`.** Los recortes PDF mantienen su contrato en puntos PDF sin cambiar esos puntos por píxeles. `punto_a_pagina()` devuelve unidades de la página visible declarada: puntos en PDF, píxeles orientados en raster.

## Verificación e integridad

Preparar y cargar comprueban expediente, originales y hashes de todas las fuentes. La carga también vuelve a vincular la revisión documental y los recortes embebidos con sus registros conservados, y contrasta las transformaciones de cada imagen con el registro fuente.

Para raster, se reproduce el recorte desde el original y se comparan el PNG, dimensiones, EXIF, matrices y metadatos. El contexto se reproduce con el EXIF/RGB/thumbnail del documento registrado; se comprueban sus dimensiones originales, orientación y DPI declarado sin atribuirles significado físico. Mezclar registros PDF/raster, orientaciones, dimensiones, PNG de otra fuente o transformaciones modificadas se rechaza, incluso si se rehace el hash de la solicitud. La aplicación vuelve a comprobar fuentes y bytes de solicitud, integridad, prompt e imágenes copiadas al terminar la carga, para detectar cambios durante la operación.

Las rutas no pueden salir de su carpeta autorizada ni resolverse mediante enlaces. Cambios de originales o de metadatos invalidan los paquetes anteriores. Los hashes no constituyen firma externa ni protegen frente a un actor que reconstruya deliberadamente toda la evidencia coherente.

## Límites deliberados

- JPEG/PNG estático, página 1 exclusivamente; se rechazan PNG animados y EXIF fuera de 1–8.
- Original raster máximo 128 MiB y 40 millones de píxeles; PNG de recorte máximo 8 millones de píxeles. Si es necesario se reduce con LANCZOS, conservando transformación exacta al espacio original. No se amplía el raster.
- El contexto usa las vistas documentales registradas, de hasta 4096 píxeles por lado. El visor puede usar otro tamaño de presentación: las coordenadas normalizadas corresponden al mismo espacio EXIF orientado.
- No integra todavía imágenes derivadas por `preprocesamiento.procesar_imagen()` con perspectiva/contraste. Hacerlo requiere declarar, conservar y verificar su cadena adicional de transformaciones; no se acepta una imagen corregida como si fuera el original registrado.
- No añade carga web, selector gráfico de recortes, ejecución de proveedor, OCR, escala en metros ni conversión/aprobación de geometría. La integración HTTP/UI pertenece al servicio posterior.

## Pruebas focales

```powershell
$env:TEMP = Join-Path (Get-Location) 'tmp'
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m unittest tests.test_recortes_raster tests.test_recortes tests.test_entrada_vision -v
```

Datos exclusivamente sintéticos. Se cubren PNG/JPEG y las ocho orientaciones EXIF, matrices y píxeles reales, contexto redondeado, bbox y reducción, originales intactos, versión nueva, límites, animación, mezcla de fuentes, hashes/transformaciones reescritos, cambios durante preparación/carga y respuesta pendiente. La misma ejecución repite las pruebas existentes de recortes PDF y entrada visual; no usa red, proveedor, ETABS ni Computer Use.

Resultado focal final del 17 de octubre de 2026: **41 pruebas OK en 19.275 s**, sin omisiones (12 nuevas raster y 29 existentes).
