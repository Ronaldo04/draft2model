# Proveedor visual web: trabajos preparados y envío deliberado

- **Ruta:** `D:/RONALDO CUCHILLA/1. RONALDO CUCHILLA/2. INGENIERÍA CIVIL DOCS AND PROJECTS/AECODE CURSOS/AECODE AI TALENT/PROYECTO FINAL`.
- **Servicio:** `draft2model/revision_proveedor.py`, clase `ServicioProveedor(app, transporte=None)`. Codex conecta la parte HTTP y la UI.
- **Archivos sin tocar:** `proveedor_openai.py`, `revision_visual.py` y `revision_web/`.

## Reutilización

- **Del cliente existente:** se reutilizan `preparar_plan`, `preparar_peticion` y `ejecutar_plan`. No hay lógica de petición, esquema ni lectura de respuesta duplicada.
- **Intento único:** `ejecutar_plan` es quien abre `intento.json` en modo exclusivo, de modo que un plan admite un solo intento aunque lo lancen procesos distintos.
- **Paquete vigente:** se comprueba con `app.preparacion.paquete`, que a su vez usa `cargar_paquete`.
- **Persistencia:** los trabajos se guardan en `<raiz>/.proveedor_web/trabajos.sqlite3`.
  - Hay una restricción UNIQUE sobre `(caso, clave)`, con el SHA-256 del payload, y un índice único sobre el estado `en_ejecucion`.
  - Cada trabajo tiene una carpeta con `preparacion.json` y un archivo `evento_*.json` por transición. Estos archivos solo se crean, nunca se sobrescriben.
- **Exclusión:** se usa el control propio `.proveedor_web/proveedor.lock`, con `BloqueoExclusivo`. No se toma el lease de ETABS ni se tocan procesos.

## Contrato (cuerpos públicos)

| Operación | Cuerpo exacto |
|---|---|
| `preparar(body)` | `{caso, expediente_sha256, paquete (uuid32), modelo, opciones:{max_tokens 256–16384, detalle low/high/auto, timeout_s 1–180}, clave_solicitud (uuid32)}` |
| `ejecutar(body)` | `{caso, trabajo, huella_preparacion, expediente_sha256, confirmacion_explicita: true}` |
| `recuperar(body)` | `{caso, trabajo, huella_preparacion, confirmacion_explicita: true, resolucion: "cerrar_sin_reintento"}` |
| `consultar(caso, trabajo)` / `listar(caso)` | Lectura. Si encuentra un huérfano, lo marca `incierto`. |

**Reglas del contrato:**
- `modelo` es el identificador declarado por el usuario. El servicio no infiere ninguno ni tiene uno predeterminado.
- Los errores se lanzan como `ErrorProveedorWeb(codigo)`, que es un `ValueError`. HTTP puede devolver 409 con ese código. Los códigos son:
  - `clave_reutilizada_con_otros_datos`, `clave_ausente_sin_envio`, `confirmacion_requerida`, `preparacion_cambio`
  - `entradas_no_vigentes`, `incertidumbre_pendiente_en_caso`, `otro_envio_activo`
  - y los genéricos `*_rechazada`.
- **Proyección pública.** Contiene:
  - identificadores y hashes de solicitud, plan y petición;
  - `modelo_declarado` (declarado) frente a `observado.modelo_devuelto` (observado), y `observado.usage`, `respuesta_id_declarado` y `duracion_api_segundos`;
  - `costo_estimado: null`, porque no hay tarifa configurada;
  - `modo` (`transporte_prueba_python` o `real`) y `proveedor_declarado` (`simulado` u `openai`);
  - `llamada_real_acreditada`, que solo vale `true` con `modo:"real"` y el estado `completado_verificado`;
  - `aprueba_ingenieria:false` y `aprueba_resultados:false`.
- **Lo que nunca sale:** rutas, endpoint, encabezados, transporte, comandos ni la clave.
  - `OPENAI_API_KEY` solo se comprueba por presencia, y únicamente al ejecutar en modo real.
  - El transporte de pruebas recibe `(payload, timeout)`, nunca la clave.
  - Preparar y consultar funcionan aunque falte la clave.

## Estados

| Estado | Evidencia | ¿Bloquea el caso? |
|---|---|---|
| `preparado` | Plan local sin envío. | No |
| `en_ejecucion` | Hay un worker vivo con el control tomado. | Sí |
| `completado_verificado` | Se verifican el resultado del cliente, `respuesta_api.json`, `registro.json` y `extraccion.json` con sus SHA-256. Se revalidan el paquete y el plan después del envío. | No |
| `fallido_sin_envio` | Falló una revalidación antes del intento: no existe `intento.json` del plan. | No |
| `respuesta_rechazada` | Hubo envío y se conservó la respuesta, pero no se aceptó: era inválida o incompleta, o las fuentes cambiaron durante el envío. | No |
| `incierto` | Hay intento registrado pero no hay respuesta conservada (timeout, corte o pérdida), o el trabajo quedó `en_ejecucion` sin worker tras un reinicio. | **Sí** |
| `incierto_resuelto` | Cierre explícito sin reintento. Se conserva la evidencia. | No |

**Comportamiento sin reenvío:**
- No hay reintentos automáticos.
- Ejecutar un trabajo que no está `preparado` devuelve su estado sin volver a enviar.
- Con un trabajo `incierto` o `en_ejecucion` en el caso, cualquier otro trabajo del mismo caso falla con `incertidumbre_pendiente_en_caso`, aunque tenga una clave nueva y aunque haya habido un reinicio.
- `recuperar` solo pasa a `completado_verificado` si el resultado privado existente se verifica por completo. En cualquier otro caso cierra como `incierto_resuelto` sin enviar nada.

## Salida privada para conectar con ServicioRespuestas

Al completar, el cliente deja tres grupos de archivos en el caso:
- `vision/planes_openai/<plan>/plan.json` y `intento.json`.
- `vision/intentos_openai/<intento>/resultado.json`, `respuesta_api.json` y `respuesta_visual.json`.
- `vision/respuestas/<id>/respuesta_original.json`, `extraccion.json` y `registro.json`. Aquí `proveedor_declarado` y `modo_prueba` reflejan el transporte.

La proyección expone `respuesta_visual: {id, sha256_extraccion}`.

**Pendiente para Codex:**
- Esa carpeta **no** tiene `origen_web.json`, así que `ServicioRespuestas.listar` la mostrará como no vigente hasta que una acción separada la vincule.
- El traslado a revisión debe ser una acción explícita.

## Pruebas

Comando:

```bash
TEMP=$PWD/workspace/tmp TMP=$PWD/workspace/tmp python -m unittest tests.test_revision_proveedor tests.test_proveedor_openai
```

Resultado: 25 OK (9 nuevas y 16 existentes del cliente).
- En todas las pruebas, `proveedor_openai._http` y `subprocess.Popen` lanzan `AssertionError`, y `OPENAI_API_KEY` está vacía, salvo en una prueba que define una clave falsa.
- Esa prueba comprueba que la clave falsa no aparece en ningún JSON ni SQLite.

Qué cubren:
- Preparar sin clave ni red, con idempotencia, reutilización de clave con otros datos y opciones o identificadores inválidos.
- Consultar y listar tras reinicio.
- Confirmación, huella y clave ausente sin crear intento.
- Ejecución completa con transporte Python, sin reenvío.
- Respuesta inválida que no bloquea el caso.
- Timeout que queda `incierto`: no se relanza, bloquea una clave nueva y se recupera de forma explícita.
- Recuperación con evidencia completa.
- Huérfano tras reinicio.
- Plan alterado antes y durante el envío, y paquete alterado.

## Límites

- No se hizo ninguna prueba con la API real ni con red. El transporte Python nunca acredita una llamada real.
- **Modo real web:** Codex añadió la opción compatible `importar_automaticamente` al cliente. Este servicio la fija en `False`; conserva `respuesta_pendiente_revision` sin importar automáticamente. Vincular la respuesta y trasladar su extracción son acciones explícitas posteriores. La CLI conserva su comportamiento anterior. Ver VINCULO_PROVEEDOR_REVISION.md.
- **Respuesta HTTP no 2xx en modo real:** el cliente no conserva su cuerpo, así que el trabajo queda `incierto` de forma conservadora y se resuelve con `recuperar`.
- **Control propio del proveedor:** permite un solo envío a la vez en toda la raíz.
- **No verificado:** integración HTTP y UI, suite completa, ETABS y Computer Use.
