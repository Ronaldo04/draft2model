# Protocolo Anthropic Messages

Estado al 19 de octubre de 2026. Adaptador **implementado y probado solo con dobles locales**: sin clave, sin llamada real y sin modelo seleccionado. Todavía **no está registrado** en `draft2model/proveedores.py`. Codex se encarga del registro, la variable `ANTHROPIC_API_KEY`, el uso, el id, el modelo y `detalle_auto=True`. Hasta entonces, no es un proveedor seleccionable.

Módulo: [`draft2model/proveedor_anthropic.py`](../draft2model/proveedor_anthropic.py). Pruebas: [`tests/test_proveedor_anthropic.py`](../tests/test_proveedor_anthropic.py).

## 1. Interfaz (igual que `proveedor_gemini`)

| Elemento | Comportamiento |
|---|---|
| `ENDPOINT` | Fijo: `https://api.anthropic.com/v1/messages`. |
| `endpoint(modelo)` | Valida el identificador (`[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}`, sin `/` ni query) y devuelve `ENDPOINT`. No hay modelo predeterminado. |
| `convertir_peticion(payload)` | Recibe la petición interna común y devuelve el envoltorio local `{model, body}`. El SHA local cubre ambos; solo se transmite `body`. |
| `_http(envoltorio, key, timeout)` | Un único POST. Devuelve un `dict` JSON estricto. |
| `leer_respuesta_api(response)` | Devuelve el único objeto JSON final o lanza `ErrorProveedor`. |
| `restricciones_trasladadas(esquema)` | Auxiliar de solo lectura. Lista `[ruta, palabra, valor]` de lo que no viaja como restricción. |

## 2. Conversión

Entrada esperada:
- `model`;
- `input` con los roles `developer` y `user`, cuyas partes son `input_text` e `input_image` (`data:image/png;base64,…`);
- `max_output_tokens` entre 256 y 16384;
- `text.format` con `type: json_schema`, `name`, `strict: true` y `schema`.

`store` se acepta y se **descarta**: no se atribuye a Anthropic la semántica `store=false` de OpenAI.

Cuerpo enviado (claves exactas):

```json
{"model": "<id explícito>", "max_tokens": 4096,
 "system": "<textos developer unidos con una línea en blanco>",
 "messages": [{"role": "user", "content": [
   {"type": "text", "text": "Imagen r1 · …"},
   {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": "<b64>"}}]}],
 "output_config": {"format": {"type": "json_schema", "schema": {"…": "copia transformada"}}}}
```

**Rechazos en la conversión:**
- **Campos:** claves ajenas en la petición (`tools`, `tool_choice`…), partes de tipo distinto a texto o imagen, imágenes fuera del rol `user`, roles distintos de `developer` y `user`, instrucciones después del contenido (no se reordena), texto vacío, falta de instrucciones o de contenido.
- **Detalle:** `detail` distinto de `auto`. `low` y `high` no tienen equivalencia declarada.
- **Imágenes:** URL remotas o tipos que no sean PNG en base64; contenido sin firma o cabecera IHDR PNG.
- **Límites locales conservadores**, alineados con la documentación pública de visión y Messages y **no verificados con API real**:
  - más de 5 MiB por imagen;
  - un lado de más de 8000 px;
  - más de 100 imágenes, o más de 20 con un lado mayor de 2000 px;
  - un cuerpo de más de 32 000 000 bytes.
- **Esquema:** palabras clave desconocidas, objetos sin `additionalProperties: false` y `format` fuera de la lista admitida.

No se añade `thinking` ni `effort`. El adaptador no fija parámetros de razonamiento.

## 3. Tratamiento del JSON Schema

Fuentes primarias citadas en el encargo (verificadas por Codex el 19 de octubre; no se consultaron desde aquí, sin red): [structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) y [visión](https://platform.claude.com/docs/en/build-with-claude/vision).

El adaptador trabaja sobre una **copia profunda**. El esquema original de `esquema_respuesta` o `esquema_llm` no se modifica, y las pruebas lo comprueban con igualdad exacta.

| Clase | Palabras clave |
|---|---|
| Se envían sin cambios | `type`, `properties`, `required`, `additionalProperties` (solo `false`), `items`, `enum`, `const`, `anyOf`, `allOf`, `description`, `title`, `format` (`date-time`, `time`, `date`, `duration`, `email`, `hostname`, `uri`, `ipv4`, `ipv6`, `uuid`), `minItems` con valor 0 o 1. |
| **Se trasladan** a `description` (lista exacta) | `minimum`, `maximum`, `exclusiveMinimum`, `exclusiveMaximum`, `multipleOf`, `minLength`, `maxLength`, `maxItems`, y `minItems` con valor distinto de 0 o 1. |
| Se rechazan | Cualquier otra palabra: `pattern`, `oneOf`, `$ref`, `$defs`, `not`, `uniqueItems`, `patternProperties`, `prefixItems`… También `additionalProperties` distinto de `false`. |

El texto añadido a la descripción es: `Restricciones validadas localmente (no aplicadas por la API): minItems=4; maxItems=4.`

**Caso real del contrato de visión.** En `bbox_imagen_normalizada` se trasladan `minItems=4` y `maxItems=4`, y en sus elementos `minimum=0` y `maximum=1`. `evidencia.minItems=1` viaja sin cambios. El esquema de explicaciones no tiene traslados.

**Qué no se declara.** La API no garantiza esas restricciones trasladadas. La conformidad la decide la **validación local** existente, que no se modifica. Por ejemplo, `registrar_respuesta` en `draft2model/entrada_vision.py` aplica `_bbox` a `bbox_imagen_normalizada`: exige 4 números y comprueba el rango 0–1 con área positiva. El esquema simplificado no prueba por sí solo el cumplimiento.

## 4. Transporte (`_http`)

- **Cabeceras:** `x-api-key`, `anthropic-version: 2023-06-01` (la firma oficial) y `Content-Type: application/json`. La clave nunca va en la URL, en archivos ni en mensajes de error.
- **Antes de enviar,** vuelve a validar el cuerpo:
  - claves exactas y modelo igual al del envoltorio;
  - un único turno `user`;
  - solo bloques `text` e `image` en base64 PNG;
  - `output_config.format` de tipo `json_schema`.
- **Rechaza antes de enviar:** un timeout que no sea entero entre 1 y 180, y una clave vacía o con saltos de línea.
- **Un intento:** sin reintentos ni redirecciones (`base._SinRedireccion`). La respuesta se lee con un límite de `MAX_BYTES` + 1 y se interpreta como JSON estricto con `base._loads`: sin claves duplicadas ni valores no finitos, en UTF-8 y como objeto.
- **HTTP de error:** `ErrorProveedor` con `http_status` y, si el cuerpo trae un `error.type` con forma de identificador (`[a-z_]{1,64}`), con `tipo_error`. No se conserva el mensaje, el cuerpo ni las cabeceras. Sin `http_status` (red, timeout, `OSError`), el consumo es **incierto** y no se reintenta.

## 5. Lectura de la respuesta

Se exige:
- `type: message`;
- `role: assistant`;
- ausencia de `error`;
- `stop_reason == "end_turn"`. Se rechazan `refusal`, `max_tokens`, `tool_use`, `pause_turn`, `stop_sequence`, `model_context_window_exceeded` y la ausencia de valor, sin importar salida parcial.

Tratamiento de los bloques de `content`:
- **`text`:** sin citas ni claves extra.
- **`thinking`** (`thinking` como cadena y `signature` opcional) y **`redacted_thinking`** (`data`): se aceptan **separados**. Nunca son salida ni se ejecutan.
- **Cualquier otro** (`tool_use`, `server_tool_use`, `fallback`…): se rechaza.

Debe quedar exactamente **un** texto final, que debe ser un objeto JSON estricto.

## 6. Pruebas y resultado

Ejecución focal sin red: `socket.create_connection`, `socket.socket.connect` y `subprocess.Popen` se bloquean en cada prueba. `TEMP` y `TMP` apuntan a `tmp/anthropic_qa`.

```
python -m unittest tests.test_proveedor_anthropic -v
```

Resultado: **11 pruebas OK, código 0** (Python 3.11.15). Log: `tmp/anthropic_qa/pruebas.log`.

Cobertura:
- conversión exacta;
- copia del esquema y lista de traslados;
- esquema de explicaciones;
- rechazos de la conversión;
- límite de cuerpo;
- cabeceras y cuerpo enviados;
- un solo intento sin redirección;
- error HTTP saneado;
- incertidumbre;
- rechazos previos al envío;
- JSON estricto en el transporte;
- razonamiento separado;
- `stop_reason` y bloques no admitidos.

**Son dobles, no prueba real.** No acreditan que un modelo o una cuenta Anthropic acepten este cuerpo, ni los límites de tamaño, ni la calidad de lectura.

## 7. Límites y pendientes

- **Integración pendiente (Codex):** el registro, `ANTHROPIC_API_KEY`, el mapeo de `usage`, `model` e `id`, `detalle_auto=True` y la UI. Sin eso, `preparar_peticion` no puede seleccionar este protocolo.
- **Sin ensayo real:** no se envió ninguna petición ni se leyó ninguna clave. La compatibilidad de un modelo concreto (visión y `output_config.format`) debe comprobarse en un envío autorizado, con su costo.
- **Límites de tamaño y dimensiones:** son locales y conservadores. Si la fuente primaria cambia, se ajustan en el módulo.
- **Sin parámetros opcionales:** no se usan streaming, herramientas, `fallbacks`, betas ni razonamiento configurado. Un modelo que exija streaming para salidas largas no está cubierto, y con `max_tokens` ≤ 16384 no debería hacer falta.
