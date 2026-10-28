# Servicio web de lectura deliberada

`draft2model.revision_lecturas.ServicioLecturas(app, fabrica_lector=None)` conserva trabajos sin conectar al motor durante la preparación. La fábrica es inyección Python para pruebas; el producto usa `LectorAnalisis` con transporte nativo real. No se admiten fábricas, comandos, rutas, PID ni opciones de motor desde HTTP.

La lectura abre el EDB aceptado en su carpeta original mediante una instancia nueva propia y exige su cierre confirmado. No calcula, guarda, normaliza ni aprueba resultados. El PID queda exclusivamente en la evidencia privada del lector, nunca se utiliza para reanudar.

## Contrato Python / HTTP a integrar

El servicio no registra rutas HTTP. Las siguientes operaciones son aptas para los controladores del integrador. Los cuerpos tienen claves exactas; los identificadores de análisis, trabajo y solicitud son UUID de 32 caracteres hexadecimales minúsculos.

Preparar, sin procesos:

```python
servicio.preparar({
    'caso': 'caso-seleccionado',
    'analisis': 'a' * 32,
    'expediente_sha256': '<sha256 vigente>',
    'clave_solicitud': 'b' * 32,
    'tablas': ['Story Drifts'],
    'casos': ['EST'],
})
```

Tablas y casos son listas explícitas no vacías, sin duplicados. Solo se admiten casos del análisis verificado; no se seleccionan combinaciones. La misma clave y cuerpo devuelve el mismo trabajo revalidado. Cambiar el cuerpo manteniendo la clave produce `clave_reutilizada_con_otros_datos`.

Ejecutar, con respuesta inmediata y worker independiente:

```python
servicio.ejecutar({
    'caso': 'caso-seleccionado',
    'trabajo': '<id devuelto>',
    'huella_preparacion': '<huella devuelta>',
    'expediente_sha256': '<sha256 seleccionado>',
    'confirmacion_explicita': True,
})
servicio.consultar('caso-seleccionado', '<id trabajo>')
servicio.listar('caso-seleccionado')
```

`listar` devuelve `{caso, expediente_sha256, trabajos: [...]}`. Preparar, ejecutar y consultar devuelven la misma proyección:

```json
{
  "id": "<UUID trabajo>",
  "caso": "caso-seleccionado",
  "analisis": "<UUID análisis>",
  "lectura_id": null,
  "expediente_sha256": "<SHA256>",
  "huella_preparacion": "<SHA256>",
  "estado": "preparado",
  "vigente": true,
  "casos": ["EST"],
  "tablas": ["Story Drifts"],
  "datos_sinteticos": false,
  "modo_ejecucion": "real",
  "sha256_respuesta": null,
  "sha256_edb": "<SHA256 EDB analizado>",
  "lectura_verificada": false,
  "datos_tablas": null,
  "analisis_ejecutado": false,
  "aprueba_resultados": false,
  "resultado_normalizado": false,
  "requiere_recuperacion": false,
  "problemas": []
}
```

`lectura_id` aparece al preparar el lector dentro del worker. En `aceptado` vigente, `lectura_verificada=true`, hay `sha256_respuesta` y `datos_tablas` contiene exactamente `{unidades, version_etabs, casos, estado_casos, tablas}`. Los nombres de tablas, campos, filtros de caso y filas se conservan como los entregó el lector; no se renombran ni se convierten valores. La proyección excluye modelo, rutas, PID y mensajes del motor. Los valores de las celdas de tablas son texto original o null.

La selección actual de caso/análisis debe coincidir antes de habilitar la ejecución en UI. Una consulta histórica no implica una nueva selección ni confirmación. Los tres indicadores `analisis_ejecutado`, `aprueba_resultados` y `resultado_normalizado` permanecen siempre false: describen esta operación de lectura.

`respuesta_bytes(caso, trabajo, *, expediente_sha256)` devuelve los bytes originales de la respuesta canónica del lector, solo para trabajo aceptado con evidencia y fuentes nuevamente verificadas. Es una API interna de transferencia al borrador de mapeo; esos bytes contienen la trazabilidad privada de la instancia y del modelo. No exponerlos directamente como JSON público ni descarga sin sanitizar. Su SHA coincide con `sha256_respuesta`.

## Estados, errores y recuperación

| Estado persistente | Significado |
| --- | --- |
| `preparado` | Selección y snapshots conservados, sin procesos. |
| `en_ejecucion` | Worker conserva exclusión global; consultar para conocer el avance. |
| `aceptado` | Respuesta y aceptación del lector verificadas, instancia propia cerrada y fuentes vigentes al aceptar. |
| `fallido_sin_lanzar` | Revalidación anterior al worker rechazó entradas alteradas. |
| `incierto` | Worker interrumpido, error, timeout o aceptación no confirmada; exige recuperación externa. |

`vigente` expresa verificación actual de las entradas/evidencias, separada del estado histórico. Un paquete aceptado posteriormente alterado conserva estado histórico `aceptado`, pero devuelve `vigente=false`, `lectura_verificada=false`, `datos_tablas=null` y problema `entradas_o_evidencias_no_vigentes`. Un estado incierto puede tener fuentes vigentes y sigue exigiendo recuperación.

Las operaciones emiten `ErrorLecturas`, subclase de `ErrorEjecucion`, con `.codigo` público constante. El manejador HTTP existente puede traducirlo a **409**; éxito de preparar/ejecutar/consultar/listar es **200**. La comprobación de sintaxis JSON del controlador queda fuera del servicio. Códigos específicos incluyen `campos_invalidos`, `identificador_invalido`, `seleccion_invalida`, `casos_de_otro_analisis`, `confirmacion_requerida`, `preparacion_cambio`, `clave_reutilizada_con_otros_datos`, `entradas_no_vigentes`, `otra_ejecucion_activa`, `motor_incierto`, `lectura_no_aceptada`, `respuesta_no_verificable` y `ruta_motor_demasiado_larga_use_raiz_mas_corta`. Otros rechazos internos se reducen a `preparacion_rechazada`, `consulta_rechazada` o `ejecucion_rechazada`, sin rutas ni excepciones del motor.

Repetir ejecutar en un estado distinto de preparado devuelve su proyección y no relanza. Reiniciar el servidor no reanuda trabajos: un trabajo en ejecución sin lease ocupado pasa a incierto y conserva/crea el marcador compartido. No hay endpoint de desbloqueo automático ni borrado de incertidumbre.

## Persistencia y verificación

Se comparte exactamente `app.ejecucion.lease`, `.motor_lock` y `.pendiente`. La base propia es `.ejecucion_web/lecturas.sqlite3`; la exclusión del lease es entre procesos y servicios. Los grupos del caso son `trabajos_lecturas/<UUID>` y `lecturas_etabs/<UUID lector>`. Se rechazan enlaces/reparse points y rutas nativas no utilizables por MAX_PATH antes del motor.

El trabajo conserva `preparacion.json`, `evidencia_analisis.json`, `expediente.json`, eventos inmutables y, al aceptar, `aceptacion_web.json` cuya huella queda en SQLite. La corrida conserva los artefactos del lector, incluido `aceptacion_lectura.json`. El servicio comprueba solicitud exacta, identidad de análisis, versión/unidades, EDB, hashes, modo, instancia nueva/cerrada, casos con estado entero 4 y esquema/casos de cada fila. Revalida públicamente `verificar_analisis_aceptado` antes y después, y relee los bytes exactos para detectar cambios durante la consulta. No depende de APIs privadas del lector ni del verificador de análisis.

## Verificación focal

```powershell
$env:TEMP = Join-Path (Get-Location) 'tmp'
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m unittest tests.test_revision_lecturas -v
```

Las pruebas usan el lector real con transporte Python y datos exclusivamente sintéticos: preparación sin proceso, confirmación, replay, aceptación, respuesta original, reinicio, fuentes/snapshots/tipos/recibos alterados, cierre/casos/modo/falso éxito, timeout, ausencia de escrituras en consultas aceptadas, relectura final y exclusión con análisis desde otro proceso. No ejecutan ETABS, red, Computer Use ni suite completa. La ejecución nativa real sigue requiriendo validación deliberada en el entorno del usuario; estas pruebas no acreditan resultados de ingeniería.

Resultado focal del 17 de octubre de 2026: **12 pruebas OK, 54.488 s**, sin omisiones, con TEMP/TMP dentro de `tmp` del workspace.


## Integración por Codex

Rutas conectadas: POST `/api/lectura/preparar`, `/api/lectura/ejecutar`; GET `/api/lectura/trabajo?caso&trabajo`, `/api/lectura/trabajos?caso`. Servicio lazy `RevisionLocal.lecturas`, misma exclusión que construcción/análisis. No existe ruta de descarga de respuesta privada. Pantalla lecturas.js exige selección y confirmación separadas, historial/polling sin relanzar y ofrece traslado al mapeo solo para lectura aceptada vigente del caso. POST `/api/mapeo/importar-lectura` realiza traslado interno comprobado. Pruebas independientes082:12 OK54.959s sin omisiones; integración083:8 pruebas conjuntas OK35.098s, con transporte Python doble. Nueva vía nativa ETABS y visual de pantalla pendientes.
