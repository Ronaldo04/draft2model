# Preparación y registro visual desde la CLI principal

Los módulos visuales existentes se integran en tres comandos locales. Ninguno llama a un proveedor, requiere clave o transmite imágenes. La ejecución externa continúa separada y no se activa por preparar un paquete, plan o respuesta.

## 1. Preparar el paquete

Usar los identificadores de una revisión documental y recortes ya generados del caso. Son los nombres de sus carpetas, de 32 caracteres hexadecimales:

```powershell
.\.venv\Scripts\python.exe -m draft2model preparar-vision --caso CASO --revision ID_REVISION --recortes ID_RECORTE_1 ID_RECORTE_2
```

Los marcadores deben reemplazarse por los identificadores reales. No se admiten rutas en esos argumentos. La revisión se encuentra en `data/private/CASO/revision_documental/ID_REVISION/revision.json`; los recortes, en `recortes/ID_RECORTE/recorte.json`.

El comando vuelve a comprobar originales, vistas, transformaciones y recortes mediante `entrada_vision`. Devuelve el ID y la ruta del nuevo `vision/solicitudes/ID_PAQUETE/solicitud.json`. No infiere lecturas ni selecciona automáticamente regiones.

## 2. Preparar OpenAI sin clave

```powershell
.\.venv\Scripts\python.exe -m draft2model preparar-openai --caso CASO --solicitud ID_PAQUETE --modelo IDENTIFICADOR_MODELO --max-tokens 4096 --detalle high
```

El modelo debe indicarse explícitamente; preparar no verifica disponibilidad en una cuenta ni compatibilidad real. Los límites locales y el costo desconocido conservan el comportamiento del [cliente OpenAI](CONEXION_OPENAI.md).

Devuelve un plan nuevo bajo `vision/planes_openai/ID_PLAN/plan.json`, en estado `preparado_sin_envio`. No crea un intento. No imprime ni persiste el cuerpo base64 o una clave API. La futura ejecución explícita sigue documentada por separado en CONEXION_OPENAI.md y no se ha realizado con el piloto.

## 3. Registrar una respuesta disponible como archivo

```powershell
.\.venv\Scripts\python.exe -m draft2model registrar-respuesta-vision --caso CASO --solicitud ID_PAQUETE --respuesta RUTA_RESPUESTA_JSON --proveedor ORIGEN_DECLARADO --modelo MODELO_DECLARADO
```

Recibe el contrato `draft2model.respuesta_vision`, no la envoltura completa de Responses API ni una extracción preliminar ya adaptada. El esquema está descrito en [ENTRADA_VISION.md](ENTRADA_VISION.md). Debe corresponder al ID y huella del paquete.

Conserva respuesta original, extracción pendiente y registro. Las regiones se convierten de imagen a página visible mediante el módulo existente. Proveedor y modelo son declaraciones: importar un archivo no autentica su origen ni demuestra que hubo una llamada real.

Por defecto no se crea una versión de extracción. Para registrar además esa versión se añade `--importar`; luego puede abrirse en la interfaz de revisión o usarse con los comandos de extracción. Ninguna lectura se marca como revisada y no se aprueba ingeniería.

Para pruebas añadir `--modo-prueba`: procedencia y método se marcan sintéticos. Esta opción es incompatible con `--importar`; no convierte simulaciones en lecturas reales del caso.

## Fallos e integridad

- Caso, revisión, recortes y paquete deben pertenecer al mismo expediente. Se rechazan IDs inválidos, recortes repetidos y carpetas o archivos seleccionados que sean enlaces/aliases. No se sobrescriben artefactos anteriores.
- Se conservan alcance y `fuera_mvp_declarado`. Una muestra fuera del MVP no se vuelve apta por preparar o importar una extracción.
- Código 0: operación local completada. Código 1: precondición, validación o E/S impiden completar la operación. `argparse` usa 2 para argumentos incorrectos.
- Si se solicitó `--importar`, la adaptación puede guardarse correctamente y fallar la importación posterior. En ese caso devuelve 2, muestra la ruta conservada y no repite operaciones ni borra la respuesta. Resolver el problema y usar `importar-extraccion --caso CASO --entrada RUTA_EXTRACCION_GUARDADA`. No hace falta repetir un registro ni una llamada externa.
- Las comprobaciones de rutas no bloquean sustituciones concurrentes de carpetas por otro proceso local. Los hashes tampoco autentican identidades ni protegen contra una reescritura deliberada de todas las evidencias.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_cli_vision.py -v
```

PDF y respuestas sintéticos: preparación sin clave/red, estado sin intento, registro con y sin importación, conservación de pendientes y alcance, simulaciones, recuperación tras fallo local, límites, modelos explícitos, IDs/rutas, fuentes alteradas y respuesta de otro paquete. No acreditan llamadas reales, precisión de IA ni conversión de lecturas a geometría.
