# Proveedores de IA intercambiables

Estado: integración local en curso, 19 de octubre de 2026. No se ha transmitido el paquete de referencia a ninguna API. Las pruebas con dobles no verifican disponibilidad, cuotas, calidad visual ni costos de una cuenta real.

El registro `draft2model/proveedores.py` define protocolos revisados. Se elige proveedor y modelo explícitamente para cada preparación. Una clave habilita su credencial; un protocolo nuevo necesita un adaptador. El proyecto no garantiza que cualquier modelo acepte imágenes o el contrato JSON exigido.

| Identificador | Protocolo y destino | Variable de clave | Detalle visual |
| --- | --- | --- | --- |
| `openai` | Responses, destino fijo OpenAI | `OPENAI_API_KEY` | `low`, `high`, `auto` |
| `gemini` | `generateContent`, destino fijo Google | `GEMINI_API_KEY` | `auto`; no se equipara `low/high` con una resolución Google |
| `anthropic` | Messages, destino fijo Anthropic | `ANTHROPIC_API_KEY` | `auto`; restricciones JSON no admitidas se describen en una copia, validación local original obligatoria |
| `openai_compatible` | Chat Completions, URL HTTPS pública configurada | `COMPATIBLE_API_KEY` | El servidor debe admitir el valor elegido |

## Configuración local

Configure solo la variable del proveedor que vaya a usar, sin escribir claves en el chat o en archivos. [Accesos y proveedores](ACCESOS_Y_PROVEEDORES.md) contiene entrada oculta compatible con PowerShell 5.1 y arranque en la misma consola.

Para Chat Completions, configure también `D2M_COMPATIBLE_ENDPOINT`, por ejemplo `https://servicio.example.org/v1/chat/completions`, usando la URL real oficial de su operador. No se admiten HTTP, usuario/clave en URL, query, fragmentos, puertos distintos de 443 ni destinos locales o IP privadas. Este adaptador corresponde a servicios remotos. El servidor debe admitir imágenes de datos PNG y `response_format` con JSON Schema estricto; no basta con que acepte texto.

`D2M_COMPATIBLE_TOKEN_FIELD` permite `max_tokens` (predeterminado) o `max_completion_tokens` según el contrato del operador. No se prueban variantes automáticamente. Cambiar destino, modelo, proveedor u opciones exige otra preparación y confirmación.

## Uso

En revisión visual, seleccione proveedor, nombre exacto del modelo y opciones. Prepare primero; compruebe el destino y los datos del trabajo antes de confirmar el envío. Visión y explicaciones tienen selecciones independientes. La ausencia de clave no cambia de proveedor: visión conserva el plan sin envío; explicaciones conserva la contingencia local.

Preparación por CLI, sin clave ni envío:

```powershell
.\.venv\Scripts\python.exe -m draft2model preparar-proveedor --caso provisional-001 --solicitud ID_PAQUETE --proveedor gemini --modelo MODELO_DE_SU_CUENTA --detalle auto
```

Los marcadores `ID_PAQUETE` y `MODELO_DE_SU_CUENTA` deben reemplazarse. `preparar-openai` se conserva como alias anterior. El comando de ejecución común deriva el proveedor del plan; aunque el módulo conserva su nombre histórico, no fuerza OpenAI:

```powershell
.\.venv\Scripts\python.exe -m draft2model.proveedor_openai ejecutar --expediente RUTA_EXPEDIENTE_JSON --plan RUTA_PLAN_JSON --autorizar-envio
```

Ese último comando sí transmite los datos y puede consumir cuota o generar costo. La ejecución CLI conserva su importación histórica al caso; la interfaz web separa ejecución, vínculo e importación. Cada respuesta sigue pendiente de revisión.

## Garantías y límites

La huella de preparación incluye protocolo, destino, modelo, imágenes/texto y esquema. No hay cambio automático de proveedor o modelo, redirecciones HTTP ni reintentos automáticos tras un envío incierto. Las credenciales se leen solo del proceso y viajan en cabeceras; no forman parte del plan o URL.

Se exige una respuesta final completa con un único objeto JSON estricto. Rechazos, truncamiento, herramientas y claves JSON duplicadas no se aceptan como extracción válida. El contrato local original se valida además del formato de la API. Los esquemas no sustituyen revisión visual ni ingeniería.

El costo estimado puede ser desconocido; `null` no significa gratuito. La disponibilidad gratuita de Gemini depende de la cuenta y del modelo. Revise las [condiciones oficiales](https://ai.google.dev/gemini-api/terms) antes de enviar planos confidenciales.

Evidencia local: `seguimiento/INTEGRACION_MULTIPROVEEDOR_152.json`, `seguimiento/COORDINACION_CLAUDE_153.json` y pruebas focales conservadas en `tmp/catalogo_154_python.log`, `tmp/catalogo_154_node.log`, `tmp/compatible_154_python.log` y `tmp/cli_catalogo_154.log`. Falta verificar el árbol final en copia limpia y realizar el ensayo real autorizado.
