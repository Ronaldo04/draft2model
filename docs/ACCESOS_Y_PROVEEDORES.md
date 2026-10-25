# Accesos y proveedores de IA

Estado al 19 de octubre de 2026 (Lima). Esta guía explica qué accesos necesita Draft2Model y cómo ponerlos a disposición del proceso local **sin escribir claves en el chat, en documentos, en archivos del proyecto ni en el historial**. No configura nada por el usuario ni comprueba si existe una clave.

Actualización por petición del usuario: se añadió carga explícita desde el Markdown privado `data/private/credenciales.local.md`; ver [CONFIGURAR_ACCESOS](CONFIGURAR_ACCESOS.md). La vía temporal de esta guía sigue disponible. El cargador no muestra claves ni hace llamadas al comprobar presencia.

## 1. Qué acceso hace falta para cada parte

| Parte | Acceso necesario | Qué **no** hace falta |
| --- | --- | --- |
| Lectura visual de planos y explicaciones | **Un** proveedor de IA con un modelo que acepte imágenes y salida JSON estructurada, más su clave local (ver §2). | Varios proveedores a la vez. |
| ETABS | ETABS instalado con **licencia local**, la DLL `ETABSv1` compatible, una plantilla `.edb` autorizada y un host donde el puente de PowerShell 5.1 pueda ejecutar scripts. | Ninguna clave de API externa. |
| Corpus, reglas y capa de sitio | Archivos locales **revisados**, registrados por el servicio de contexto. | Ningún servicio en la nube obligatorio. |
| Demo, pruebas y revisión local | Nada externo: funcionan sin red, sin claves y sin ETABS. | — |

## 2. Estado real de los proveedores (sin promesas de compatibilidad)

| Proveedor | Variable de proceso | Estado |
| --- | --- | --- |
| OpenAI (Responses API) | `OPENAI_API_KEY` | Adaptador integrado; regresiones locales del ciclo común comprobadas. La copia 146/148 solo acredita el árbol anterior a la ampliación multiproveedor. Sin llamada real con los planos. |
| Gemini (`generateContent`) | `GEMINI_API_KEY` | Integrado en registro, visión, explicaciones, CLI y selectores; pruebas focales con dobles. Detalle `auto`. Sin ensayo API real ni copia global de esta ampliación todavía. |
| Compatible con Chat Completions | `COMPATIBLE_API_KEY` y `D2M_COMPATIBLE_ENDPOINT` | Integrado y probado localmente con dobles; destino HTTPS público explícito terminado en `/chat/completions`. Exige modelo con imágenes y JSON Schema. Sin ensayo API real. |

Guía operativa y límites de los protocolos: [Proveedores de IA](PROVEEDORES_IA.md).

**Reglas de uso de las claves:**
- Las claves **no son intercambiables**: una clave de Gemini no funciona como `OPENAI_API_KEY`, ni a la inversa.
- Tener una clave no garantiza compatibilidad. El modelo elegido debe aceptar imágenes, la salida estructurada que exige el contrato y los límites de la petición. Eso solo lo confirma un ensayo autorizado con esa cuenta.
- No se promete disponibilidad gratuita ni de un modelo concreto sin comprobar la cuenta.
- El nivel gratuito de Gemini **indica no enviar información confidencial**: [condiciones de la Gemini API](https://ai.google.dev/gemini-api/terms) y [comprensión de imágenes](https://ai.google.dev/gemini-api/docs/image-understanding). Antes de transmitir planos privados, quien tenga la autoridad debe decidir si ese nivel es aceptable para el uso declarado del expediente.

## 3. Poner la clave a disposición del servidor, sin persistirla

El servidor lee la variable **de su propio proceso**. Por eso:
- Fijarla en una consola y luego abrir la aplicación con doble clic en `Abrir revision de planos.cmd` **no funciona**: el proceso abierto desde Explorer no hereda la variable temporal de esa otra consola. Un `.cmd` iniciado desde la propia consola sí puede heredarla. El proveedor web respondería `clave_ausente_sin_envio` y las explicaciones quedarían en contingencia `clave_ausente`.
- Hay que **fijar la variable y arrancar el servidor en la misma consola de PowerShell**.

Método válido en **Windows PowerShell 5.1 y en PowerShell 7**, sin mostrar la clave ni guardarla en disco. Cambiar `OPENAI_API_KEY` por `GEMINI_API_KEY` o `ANTHROPIC_API_KEY` o `COMPATIBLE_API_KEY` según el proveedor elegido:

```powershell
$s = Read-Host 'Clave API (no se muestra)' -AsSecureString
$p = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($s)
try { $env:OPENAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($p) }
finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($p); Remove-Variable s, p }
.\.venv\Scripts\python.exe -m draft2model.revision_visual --raiz data/private --puerto 8766
```

**Notas:**
- En PowerShell 7 también sirve `Read-Host … -MaskInput`; no es obligatorio usarlo.
- La variable desaparece al cerrar esa consola.
- No usar `setx`, perfiles, archivos `.env` ni el historial para guardarla.
- Para el envío por CLI, ejecutar el comando de envío en esa misma consola.

## 4. Vías que transmiten datos a un tercero

Cada una es una acción deliberada, con confirmación:

1. **CLI de visión:** `python -m draft2model.proveedor_openai ejecutar --expediente … --plan … --autorizar-envio`. Envía las imágenes del paquete. Ver conexión OpenAI (referencia de desarrollo no distribuida).
2. **Proveedor web:** `POST /api/proveedor/ejecutar`, desde la UI. Envía las imágenes del paquete.
3. **Explicaciones web:** `POST /api/explicaciones/ejecutar`. Envía **texto** derivado de resultados, evaluaciones, fragmentos citables y sitio; no envía imágenes. Sin clave, queda en contingencia determinística y no envía nada.

Preparar planes, consultar, registrar respuestas locales, la demo y las pruebas no transmiten nada.
