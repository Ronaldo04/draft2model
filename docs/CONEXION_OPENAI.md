# Primer conector OpenAI: preparación y ejecución explícita

Implementado y probado sin red el 15 de octubre de 2026. No se ha ejecutado una llamada real ni medido precisión sobre planos. El usuario eligió preparar OpenAI y todavía no dispone de clave API. El modelo queda configurable, sin valor predeterminado.

Código: [proveedor_openai.py](../draft2model/proveedor_openai.py). Pruebas: [test_proveedor_openai.py](../tests/test_proveedor_openai.py). Utiliza la biblioteca estándar de Python y las dependencias ya instaladas.

## Conexión preparada

El conector prepara peticiones de [Responses API](https://developers.openai.com/api/reference/python/resources/responses/methods/create), con imágenes PNG codificadas en base64 según [Images and vision](https://developers.openai.com/api/docs/guides/images-vision). Solicita [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) mediante esquema JSON estricto; las comprobaciones de unidades, referencias y geometría de evidencia siguen ejecutándose localmente.

Envía únicamente el prompt y las imágenes del paquete seleccionado, con etiquetas de archivo/página. No envía todos los expedientes, referencias de evaluación, claves ni rutas locales. Las imágenes sí pueden contener información privada y deben revisarse antes de autorizar un envío.

Se solicita `store: false`; esto describe la opción de la petición y no promete ausencia de todos los registros del proveedor. No se usan herramientas remotas, archivos subidos por otra API, URLs externas de imágenes ni reintentos automáticos.

## 1. Preparar un plan sin clave ni red

Primero crear un paquete con [entrada_vision](ENTRADA_VISION.md). Luego:

```powershell
.\.venv\Scripts\python.exe -m draft2model.proveedor_openai preparar --expediente data/private/CASO/expediente.json --solicitud data/private/CASO/vision/solicitudes/PAQUETE/solicitud.json --modelo IDENTIFICADOR_MODELO --max-tokens 4096
```

`IDENTIFICADOR_MODELO` es un marcador que debe sustituirse por un ID disponible en la cuenta y compatible con imágenes y salida estructurada. La compatibilidad del modelo y los permisos de la cuenta se comprueban en la futura prueba real; no se infieren de una suscripción al chat ni de las pruebas unitarias.

El plan queda en `vision/planes_openai/<uuid>/plan.json`. Registra modelo, endpoint fijo de OpenAI, huella exacta de petición, imágenes y sus hashes, bytes, detalle y límite de salida. No guarda claves ni el cuerpo base64. Preparar no llama a la API ni requiere clave.

Límites locales actuales: 16 imágenes, 40 MiB de petición JSON y 256–16384 tokens de salida. No son límites universales del proveedor. El máximo de salida **no** limita el costo total de entrada e imágenes. No se inventa costo: `costo_estimado` permanece null hasta disponer de tarifas y consumo aplicables.

## 2. Configurar la clave localmente cuando exista

Obtener una clave desde la [configuración de claves de OpenAI Platform](https://platform.openai.com/api-keys). No pegarla en el chat ni en archivos del proyecto. En PowerShell 7, dentro de la misma consola que ejecutará el cliente:

```powershell
$env:OPENAI_API_KEY = Read-Host 'Clave API de OpenAI' -MaskInput
```

El conector lee la variable de proceso `OPENAI_API_KEY`; no busca claves en archivos personales ni carga `.env`. No es necesario configurarla para preparar planes o ejecutar las pruebas sin red.

## 3. Revisar y ejecutar un plan concreto

Revisar modelo, imágenes, límite y costo antes de ejecutar. El único comando que puede transmitir imágenes es:

```powershell
.\.venv\Scripts\python.exe -m draft2model.proveedor_openai ejecutar --expediente data/private/CASO/expediente.json --plan data/private/CASO/vision/planes_openai/PLAN/plan.json --autorizar-envio
```

La autorización se refiere a las imágenes de ese plan. Sin ella o sin clave, no se crea un intento ni se transmite nada. El endpoint es fijo; una configuración modificada o una redirección HTTP se rechaza.

Cada plan admite un solo intento. La apertura exclusiva de `intento.json` evita dos envíos concurrentes del mismo plan. Si falta el resultado final, el estado puede ser incierto; no asumir que no hubo consumo ni borrar el marcador para reintentar. Una nueva llamada requiere revisar el intento y preparar otro plan.

## Resultado y enlace con la gestión de Claude

El intento se conserva bajo `vision/intentos_openai/<uuid>/`:

| Archivo | Evidencia |
| --- | --- |
| `respuesta_api.json` | Respuesta completa recibida cuando es JSON utilizable; no se guardan encabezados de autenticación ni cuerpos de errores HTTP. |
| `respuesta_visual.json` | Contenido JSON de lectura extraído de una respuesta completa. |
| `resultado.json` | Estado, duración de llamada y duración total, consumo informado o null, huellas, modelo solicitado/devuelto y enlaces a extracción/versiones. |

Si la respuesta es completa y válida, se adapta con `entrada_vision`, se guarda su extracción pendiente y se importa mediante `gestion_extraccion`. El resultado registra el ID de versión que se puede consultar, corregir y exportar con los comandos de [CLI_EXTRACCION.md](CLI_EXTRACCION.md). No se marca ningún candidato como revisado ni se aprueba ingeniería.

En el registro de `entrada_vision`, `transmision_externa: false` se refiere al propio módulo, que solo adapta archivos; el envío previo y su estado se registran en el resultado del cliente OpenAI. El campo `alcance_declaracion_transmision` explicita esa diferencia.

Una respuesta incompleta, rechazada, ambigua, con JSON inválido o evidencia incompatible no se importa. Se conserva lo recibido que sea posible registrar y se informa el fallo. Si la adaptación se guardó pero falló la importación local, el resultado conserva su ruta: debe resolverse ese error antes de considerar una nueva llamada, pues repetir la API no es necesario para reintentar una importación local.

El consumo ausente es null, no cero. La duración total incluye adaptación e importación; `duracion_api_segundos` mide únicamente la llamada. Un timeout no confirma ausencia de consumo. No se calculan importes monetarios con un precio supuesto.

## Pruebas y límites de lo comprobado

- Preparación sin clave y sin red; imágenes, etiquetas, esquema, modelo y huellas.
- Falta de autorización/clave, cambios de petición, un intento por plan y ausencia de reintentos.
- HTTP sustituido para comprobar el recorrido respuesta -> extracción -> importación -> corrección -> exportación, con PDF sintético.
- Transporte inyectado marcado como simulación: no se importa como extracción real.
- Respuestas incompletas, rechazo, JSON duplicado, salida de herramienta, evidencia de contexto y timeout.
- Consumo ausente, conservación de respuesta y detección de eco accidental de una credencial.

Los fixtures no representan llamadas reales ni precisión de IA. La ejecución real, modelo elegido, costos y referencia manual del piloto permanecen pendientes. La aprobación de ingeniería sigue separada.

CLI: 0 indica plan preparado o respuesta real importada pendiente de revisión; 1 indica precondición/argumentos de datos o E/S fallidos; 2 indica intento registrado que no completó la importación. `argparse` también utiliza 2 para opciones incorrectas.
