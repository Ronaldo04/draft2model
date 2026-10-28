# Construcción deliberada desde el servicio web

Implementado el 17 de octubre de 2026 en `draft2model/revision_ejecucion.py`. Este servicio completa preparación y ejecución asíncrona de construcción con los adaptadores existentes. No realiza análisis, no declara conformidad normativa y no aprueba geometría, configuración, modelo o resultados. Las rutas HTTP y la pantalla se integran por separado.

## Contrato para el manejador HTTP

Instanciar una vez `ServicioEjecucion(app)`, con el mismo `RevisionLocal` de la revisión. El modo productivo predeterminado es real mediante Windows PowerShell5.1 y los scripts existentes. Las fábricas opcionales del constructor son dependencias Python para pruebas, nunca campos aceptados del navegador. No existe una opción HTTP para elegir proceso, comando, DLL, modo doble o carpeta de salida.

Métodos:

```python
preparar(body: dict) -> dict
ejecutar(body: dict) -> dict
consultar(caso: str, trabajo: str) -> dict
listar(caso: str) -> dict
```

Rutas propuestas: POST `/api/construccion/preparar`, POST `/api/construccion/ejecutar`, GET `/api/construccion/trabajo?caso=...&trabajo=...`, GET `/api/construccion/trabajos?caso=...`. Aplicar los mismos controles de sesión, Host, Origin y límite JSON del servidor actual.

Estas rutas ya están conectadas en `revision_visual.py`, con inicialización del servicio al usarlo. La pantalla `construccion.js` consume la configuración abierta/comprobada/aprobada, exige plantilla del caso y opciones explícitas, conserva la clave de preparación tras un error de conexión y separa preparación de confirmación/ejecución. Consulta trabajos conservados; mientras uno está en ejecución actualiza su estado cada cuatro segundos, sin volver a ejecutarlo. Al cambiar expediente/versión descarta consultas tardías y limpia la confirmación. Un modelo aceptado refresca el selector de modelos. La inspección visual y la ejecución real de esta nueva vía siguen pendientes.

`preparar` requiere **exactamente**:

```json
{
  "caso": "sintetico-001",
  "configuracion_version": "0123456789abcdef0123456789abcdef",
  "plantilla_relativa": "plantillas/base.edb",
  "expediente_sha256": "SHA256 del expediente abierto",
  "clave_solicitud": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "opciones": {
    "tipo_shell_muro": "ShellThin",
    "gravedad_programa_m_s2": 9.80665
  }
}
```

Los valores del ejemplo son de software; el servicio no decide parámetros de ingeniería. `configuracion_version` es el UUID de la versión registrada/aprobada, no `configuracion.id`. `clave_solicitud` es una clave de idempotencia de32 hexadecimales minúsculos, única dentro del caso. El mismo payload con esa clave devuelve el trabajo existente; otra configuración/opción/huella con la misma clave se rechaza. No crear una clave nueva como reintento automático tras incertidumbre.

`plantilla_relativa` es una ruta canónica con separadores `/` dentro del mismo caso, sin `..`, enlaces ni rutas de unidad/absolutas. El archivo debe ser `.edb` y su SHA256 coincidir exactamente con la plantilla declarada en la configuración aprobada. No se aceptan artefactos externos aunque coincida su nombre. El servicio fija por sí mismo un destino nuevo `trabajos_construccion/<trabajoUUID>/modelo_construido.edb` dentro del caso.

Opciones admitidas: `tipo_shell_muro`, `gravedad_programa_m_s2`, `parametros_modales`, `amortiguamiento_funciones`, `excentricidad_espectral`, `respuesta_rigida_espectral`. Se delegan su validez/aplicabilidad al generador del plan; no se añaden decisiones de ingeniería predeterminadas. Se rechazan `destino_guardado`, `id_proceso` y cualquier campo no previsto.

`ejecutar` requiere **exactamente**:

```json
{
  "caso": "sintetico-001",
  "trabajo": "UUID devuelto por preparar",
  "huella_preparacion": "SHA256 devuelto por preparar",
  "expediente_sha256": "SHA256 del expediente abierto",
  "confirmacion_explicita": true
}
```

La respuesta devuelve inmediatamente el identificador y estado `en_ejecucion`; el trabajo continúa en un worker. Repetir la solicitud para un trabajo ya iniciado/terminal consulta ese mismo estado y no lanza un segundo worker. La confirmación explícita y las huellas siguen siendo obligatorias al repetir.

`preparar`, `ejecutar` y `consultar` retornan las mismas claves exactas:

```python
{
    'id': trabajo_uuid, 'caso': caso, 'configuracion_version': version_uuid,
    'expediente_sha256': sha_expediente, 'huella_preparacion': sha_preparacion,
    'huella_plan': huella_plan, 'operaciones_totales': numero_operaciones,
    'datos_sinteticos': True,
    'estado': 'preparado', 'vigente': True, 'modelo_id': None,
    'problemas': [], 'modo_ejecucion': None,
    'analisis_ejecutado': False, 'aprueba_modelo': False,
    'aprueba_resultados': False, 'requiere_recuperacion': False,
}
```

En éxito, `estado='aceptado'`, `modelo_id` identifica un registro inmutable construido con revisión pendiente y `modo_ejecucion='real'` (`doble` solo en pruebas inyectadas). Se puede abrir después ese modelo desde `ServicioResultados`; no se hereda aprobación de configuración. Las respuestas no incluyen PID, rutas internas, argv, configuración cruda ni mensajes del motor. `listar` retorna `{caso, expediente_sha256, trabajos: [respuesta_anterior, ...]}` en orden de creación de filas.

## Estados y errores

| Estado | Significado y siguiente acción |
| --- | --- |
| `preparado` | Configuración/plan/snapshots conservados; no se contactó ETABS. Hace falta confirmación aparte. |
| `en_ejecucion` | Se reservó exclusión persistente y el worker puede abrir/construir una copia nueva. Consultar estado; no duplicar. |
| `aceptado` | Aceptación integrada, EDB y traza comprobados, entradas revalidadas y modelo inmutable registrado/consultado. No hay análisis ni aprobación del modelo. |
| `fallido_sin_lanzar` | La revalidación inmediatamente anterior a entregar al worker rechazó entradas. No se lanzó proceso. Corregir entradas y preparar un trabajo nuevo explícitamente. |
| `incierto` | Worker interrumpido, apertura no confirmada, fallo parcial, aceptación inválida o finalización no confirmada. Mantener evidencias y realizar recuperación externa; nunca reanudar automáticamente. |

`vigente` describe integridad actual de entradas y, para `aceptado`, del modelo registrado. Es independiente de `estado`: un trabajo incierto puede tener entradas íntegras. Si cambia evidencia, `vigente=false` y `problemas=['entradas_o_evidencias_no_vigentes']`; esto no transforma un fallo en éxito.

`ErrorEjecucion` hereda ValueError y expone `.codigo` con el mismo texto constante de la excepción. El manejador puede devolver HTTP409 con `{error: str(error), codigo: error.codigo}`; no publicar excepciones internas. Códigos principales: `campos_invalidos`, `identificador_invalido`, `opciones_invalidas`, `plantilla_relativa_invalida`, `expediente_cambio`, `configuracion_no_aprobada`, `plantilla_cambio`, `clave_reutilizada_con_otros_datos`, `confirmacion_requerida`, `preparacion_cambio`, `entradas_no_vigentes`, `otra_ejecucion_activa`, `motor_incierto`, `trabajo_ausente`. Los fallos internos se traducen a `preparacion_rechazada`, `consulta_rechazada` o `ejecucion_rechazada`. Las consultas conservan fallos como estados; no publican el contenido privado de `error_worker.json`.

Preflight Windows: si las rutas previstas de solicitud del transporte, copia o salida EDB alcanzan260 caracteres, preparación se rechaza con `ruta_motor_demasiado_larga_use_raiz_mas_corta` antes de contactar ETABS. La aplicación debe ofrecer una raíz de expedientes autorizada más corta para esa situación; no usar enlaces ni cambiar destinos arbitrariamente para eludir el control.

## Persistencia, exclusión y recorrido efectivo

El control está en `<raiz>/.ejecucion_web/trabajos.sqlite3`. SQLite liga caso/clave/payload y tiene un índice único para un trabajo `en_ejecucion` en toda esa raíz. Una lease de sistema operativo `trabajo.lock` permanece adquirida desde la reserva hasta terminar el worker; serializa clientes/procesos de este servicio, incluso si tienen distintos `RevisionLocal.lock`. Se usa además `motor.lock` como bloqueo compartido de los adaptadores de apertura y construcción. Otros clientes del motor deben usar ese mismo bloqueo: SQLite/RLock no sustituyen la exclusión del driver.

No se añadió una segunda máquina de estados a `RegistroCorridas`: sus transiciones no expresan esta combinación de idempotencia, apertura y construcción. Se reutiliza la exclusión de sistema operativo del adaptador y una única tabla propia para este trabajo compuesto. No se modificó `orquestacion.py` ni ningún driver.

La reserva escribe `operacion_pendiente.json` antes de entregar el trabajo al worker. Si el servidor muere, la lease se libera por el sistema operativo y el marcador permanece. Al consultar una fila `en_ejecucion` cuya lease ya no está ocupada, se relee la fila bajo la lease y se convierte en `incierto`; esto también evita sobrescribir un éxito que terminó mientras se consultaba. No se borra el marcador ni se vuelve a ejecutar por reiniciar el servidor. Un nuevo trabajo no se ejecuta mientras exista marcador web o incertidumbre del adaptador.

El worker revalida originales/configuración/plan/plantilla y llama a `AdaptadorEtabs.abrir_copia_plantilla(..., instancia='nueva', solo_preparar=True)`. Después revalida y ejecuta esa solicitud. Exige respuesta de instancia nueva, PID positivo confirmado, modelo abierto exacto y copia SHA256 idéntica. Ese PID propio se pasa a `EjecutorVerificado.preparar`; nunca se usa GetObject/instancia activa por ausencia de PID. `EjecutorVerificado.ejecutar(..., confirmar_mutacion=True)` conserva sus comprobaciones bajo bloqueo, traza, aceptación e incertidumbre.

Solo después de la aceptación integrada se llama a `revision_modelo.registrar`, que vuelve a comprobar plan/configuración/EDB/aceptación/traza, y a `revision_modelo.consultar`. Una revalidación final de entradas precede a la resolución del marcador y al estado aceptado. Este registro deja el modelo pendiente de su revisión propia. No se llama a RunAnalysis ni al analizador.

## Evidencia conservada y recuperación

Cada carpeta `caso/trabajos_construccion/<trabajoUUID>` conserva `preparacion.json`, `configuracion.json`, `expediente.json`, copias de originales en `originales`, `plan.json`, copia de plantilla, salida EDB, referencia de instancia propia y eventos/errores privados. Las huellas se ligan a la preparación; se revalidan antes del lanzamiento y después de construir.

Las solicitudes/respuestas/trazas se guardan en `caso/motor_web/<corridaUUID>`. `apertura_ref.json` y `construccion_ref.json` del trabajo enlazan esos IDs auditables. Se utiliza un grupo plano de corridas para evitar anidar dos UUID y exceder el cwd nativo de Windows. La primera prueba del transporte doble con carpetas anidadas terminó con WinError267; se corrigió esa profundidad y luego se verificó la ruta feliz. No se lanzó ETABS real durante esta entrega.

La recuperación es externa y deliberada: comprobar que la instancia propia ya no está mutando, conservar/archivar marcadores y evidencia con declaración de revisor/motivo, y usar la recuperación del adaptador cuando corresponda. Este servicio no incluye botón para borrar marcadores, cerrar procesos ni reactivar el mismo trabajo. Tras recuperación autorizada se prepara una nueva clave/trabajo; no se reinterpreta el anterior como aceptado. Una interrupción posterior a crear archivos puede dejar una carpeta conservada aunque la publicación en SQLite no terminara: no reutilizarla ni borrarla automáticamente.

Límites: los workers son hilos daemon del servidor, no un servicio externo siempre activo; cerrar el proceso puede interrumpirlos y producir estado incierto. `app.lock` no autentica identidad ni impide cambios externos: las versiones/hashes y las puertas del driver detectan cambios. Preparar trabajos no abre ETABS, pero sí crea evidencia local persistente. La ejecución predeterminada está implementada contra los adaptadores reales; no se acredita un ensayo ETABS real de esta nueva vía por pasar sus pruebas de transporte.

## Verificación focal

```powershell
$env:TEMP = Join-Path (Get-Location) 'tmp'
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m unittest tests.test_revision_ejecucion -v
```

Diez pruebas pasaron en14.370s, sin omisiones en Windows. Usan geometría/configuración sintéticas versionadas y un transporte Python doble con los adaptadores y `EjecutorVerificado` reales. Cubren preparación sin procesos, replay, clave conflictiva, construcción aceptada y modelo pendiente, reinicio/consulta, cambios de entradas sin lanzamiento, falso éxito, fallo parcial/traza, ausencia de PID, exclusión en dos servicios y en otro proceso Python, huérfano sin reintento y preflight de rutas. No conectan ETABS, red ni Computer Use, ni dependen de tmp históricos. No se ejecutó suite completa.

Revisión independiente de Codex: diez pruebas del servicio correctas15.688s (`tmp/revision_ejecucion_codex_058.log`). Nueve pruebas conjuntas HTTP de construcción/resultados/entregables correctas7.167s (`tmp/integracion_construccion_ui_060.log`), con transporte Python doble. `node tests/revision_construccion_frontend.cjs` comprueba preparación sin ejecutar, clave conservada tras error, confirmación explícita, cambios de selección y rechazo de respuestas tardías de éxito/error. Estas pruebas no acreditan el motor real desde la pantalla.
