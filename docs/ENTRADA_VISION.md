# Entrada y salida de visión multimodal v0.1

> **Contrato 0.2.0 (encargo 07):** tipos semánticos, texto literal, cobertura por recorte, reclasificación y reubicación revisadas. Ver LECTURAS_SEMANTICAS (referencia de desarrollo no distribuida). Lo descrito abajo para 0.1.0 sigue siendo válido para artefactos guardados.

Implementado: preparación local de imágenes y adaptación de respuestas JSON de origen declarado. **No hay conexión a un proveedor ni lectura automática con un modelo en este módulo.** La selección de recortes sigue siendo manual.

## Flujo disponible

1. Seleccionar una revisión documental y uno o más recortes del mismo expediente.
2. Verificar expediente vigente, autorización declarada, alcance, hashes de originales, metadatos, dimensiones, rotación y PNG.
3. Reproducir el render desde el PDF y contrastar PNG y transformación. Esto permite detectar una vista de contexto alterada incluso si el informe antiguo no registró su hash.
4. Crear un paquete local con una vista general por página seleccionada y los recortes. No se redimensionan las imágenes ni se altera el PDF.
5. Conservar prompt, imágenes, metadatos y huellas. El futuro adaptador de proveedor podrá enviar imágenes y prompt, previa configuración del servicio.
6. Recibir una respuesta JSON, comprobar identificador/huella de solicitud y adaptar sus regiones al contrato de extracción preliminar.
7. Guardar respuesta original, extracción pendiente y registro en una carpeta nueva. Después, la gestión de extracciones podrá importar el JSON, revisar lecturas y crear sus versiones.

## Paquete

Se guarda bajo `data/private/<caso>/vision/solicitudes/<uuid>/`:

| Archivo | Contenido |
| --- | --- |
| `solicitud.json` | Identificador de solicitud, alcance, imágenes, hashes, fuentes y metadatos de coordenadas. |
| `prompt.txt` | Instrucciones independientes del proveedor; formatos de respuesta e identificadores de imágenes. |
| `integridad.json` | SHA256 de solicitud y prompt. |
| `imagenes/*.png` | Copias exactas de vistas generales y recortes comprobados. |

El UUID de la carpeta identifica la entrega local; el identificador de solicitud aparece dentro del JSON y es el que debe devolver la respuesta. Las huellas detectan cambios respecto de lo registrado; no son firmas digitales ni protegen contra una reescritura deliberada de todos los registros.

Las imágenes de contexto tienen IDs `CTX0001`, etc., y no admiten evidencia precisa en esta versión. Los recortes tienen IDs `REC0001`, etc. La lectura localizada debe indicar un recorte. El prompt no incluye nombres originales de PDF ni rutas locales; las propias imágenes sí pueden contener datos privados, por lo que el paquete permanece excluido del repositorio y no se transmite automáticamente.

## Respuesta

La raíz exige `contrato: draft2model.respuesta_vision`, `version_contrato: 0.1.0`, `solicitud_id`, `solicitud_sha256` y `candidatos`. El prompt generado contiene el ID y hash exactos que se deben devolver.

Cada candidato exige `id`, `tipo`, `valor_propuesto`, `unidad` y `evidencia`. Opcionales: `texto_fuente` y `confianza` numérica de 0 a 1. Cada evidencia exige `imagen_id` y `bbox_imagen_normalizada`.

Ejemplo de forma, con identificadores que deben sustituirse por los de la solicitud concreta:

```json
{
  "contrato": "draft2model.respuesta_vision",
  "version_contrato": "0.1.0",
  "solicitud_id": "ID_DE_LA_SOLICITUD",
  "solicitud_sha256": "SHA256_DE_LA_SOLICITUD",
  "candidatos": [{
    "id": "C001", "tipo": "cota", "valor_propuesto": null,
    "unidad": "desconocida",
    "evidencia": [{"imagen_id": "REC0001", "bbox_imagen_normalizada": [0.1, 0.1, 0.2, 0.2]}]
  }]
}
```

Estas regiones y valores son ejemplos de formato, no lecturas del piloto. Se permite `candidatos: []`. No se convierte texto como `"2.60"` en un número, ni se completan unidades ausentes. JSON con claves repetidas, NaN, Markdown envolvente o campos de aprobación se rechaza.

## Coordenadas

La respuesta utiliza coordenadas normalizadas **sobre la imagen del recorte**. La adaptación las convierte a píxeles de esa imagen, aplica `pixel_a_pagina_visible` y divide por las dimensiones de la página visible en puntos. La salida utiliza `pagina_visible_normalizada`, compatible con el contrato existente.

Esto respeta la rotación PDF y el redondeo real de los límites del raster. Interpolar únicamente entre las esquinas de la región solicitada puede desplazar la lectura y no se utiliza. No se infiere escala estructural ni se convierten píxeles a metros.

Si el relleno del raster lleva una región más allá de la página, se rechaza; no se recortan coordenadas silenciosamente. Debe revisarse la región o seleccionar otro recorte. La comparación de matrices utiliza un epsilon numérico de serialización, no una tolerancia dimensional de ingeniería.

## Uso local

Preparación (sustituir las rutas por registros existentes del expediente):

```powershell
.\.venv\Scripts\python.exe -m draft2model.entrada_vision preparar --expediente data/private/CASO/expediente.json --revision data/private/CASO/revision_documental/RUN/revision.json --recortes data/private/CASO/recortes/RECORTE/recorte.json
```

Registrar una respuesta recibida desde un proveedor o una prueba:

```powershell
.\.venv\Scripts\python.exe -m draft2model.entrada_vision registrar-respuesta --expediente data/private/CASO/expediente.json --solicitud data/private/CASO/vision/solicitudes/PAQUETE/solicitud.json --respuesta RUTA_RESPUESTA.json --proveedor IDENTIFICADOR_PROVEEDOR --modelo IDENTIFICADOR_MODELO
```

Los identificadores de proveedor y modelo son declarados; este módulo no acredita su autenticidad. Para respuestas simuladas es obligatorio utilizar `--modo-prueba`: marca procedencia y método como sintéticos. No presentar una simulación como extracción real ni importarla a un flujo que exige procedencia de expediente.

El resultado se guarda en `vision/respuestas/<uuid>/` como `respuesta_original.json`, `extraccion.json` y `registro.json`. La extracción siempre inicia pendiente, sin historial aprobado. No se sobrescriben entregas anteriores. Una respuesta inválida no produce extracción; el archivo de respuesta original aportado por el usuario permanece intacto para registrar el fallo del experimento.

Código de salida 0: operación local completada; 1: datos, integridad o escritura inválidos; 2: argumentos incorrectos. No se modifica el manifiesto ni las fuentes. Antes de adaptar se vuelven a comprobar sus huellas; si cambiaron, hay que preparar una nueva solicitud. Las comprobaciones no bloquean físicamente todos los archivos frente a ediciones concurrentes posteriores.

## Verificado y pendiente

- Pruebas con PDF sintético: cuatro rotaciones, transformación desplazada, redondeo de píxeles, datos desconocidos, respuesta vacía, integridad, rechazo de evidencia de contexto y CLI.
- Preparación local comprobada con el piloto: tres vistas generales y siete recortes, conservando `fuera_mvp_declarado`. No se generaron lecturas ni se enviaron archivos.
- Las dependencias de render están fijadas en requirements; si cambia la versión del renderizador y produce otros PNG, regenerar revisión y recortes en vez de eludir la verificación.
- El primer cliente OpenAI (referencia de desarrollo no distribuida) permite preparar planes y prevé un envío explícito con registro de respuesta, tiempos y consumo informado. Se probó sin red. Pendientes: clave, modelo, compatibilidad y límites reales del servicio, costo y ejecución con el piloto. Este módulo no acredita por sí solo extracción real ni precisión.
- Pendiente: referencia humana del piloto y evaluación de respuestas originales con el evaluador de lecturas (referencia de desarrollo no distribuida).
- Pendiente: detección automática de regiones, recortes de fuentes raster y traducción revisada a geometría.
