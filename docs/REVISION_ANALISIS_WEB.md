# Análisis deliberado desde la revisión web

Servicio `ServicioAnalisis(app, fabrica_analizador=None)` en `draft2model/revision_analisis.py`, implementado el17 de octubre de2026. Selecciona un modelo construido y una aprobación propia explícitos. Prepara un trabajo persistente y, solo mediante otra solicitud confirmada, ejecuta `AnalizadorEtabs` en un worker. No normaliza resultados, no ejecuta reglas ni aprueba resultados/informes.

## API HTTP para integrar

```python
preparar(body) -> dict
ejecutar(body) -> dict
consultar(caso, trabajo) -> dict
listar(caso) -> dict
```

Rutas sugeridas: POST `/api/analisis/preparar`, POST `/api/analisis/ejecutar`, GET `/api/analisis/trabajo?caso=...&trabajo=...`, GET `/api/analisis/trabajos?caso=...`. No reemplazar GET `/api/analisis`, que ya consulta vínculos entre resultados normalizados y corridas para los informes. El manejador/UI se integran por separado; conservar controles de sesión, origen, Host y tamaño JSON existentes.

Integración posterior de Codex: estas rutas ya están conectadas con inicialización lazy en `RevisionLocal`, bajo controles HTTP existentes. La pantalla `analisis.js` recibe la revisión propia del modelo, exige seleccionar una aprobación sin valor preseleccionado, prepara sin motor y separa confirmación/ejecución. Consulta el estado cada cuatro segundos durante ejecución; cambiar modelo/aprobación limpia la confirmación. Quince pruebas de servicio/HTTP pasaron en29.285s (`tmp/revision_analisis_codex_067.log`), usando el analizador con transporte Python doble. Node `tests/revision_analisis_frontend.cjs` comprueba selección explícita, preparación, confirmación y cambio de modelo. No acredita un ensayo real del nuevo recorrido ni inspección visual.

`preparar` exige exactamente:

```python
{
    'caso': caso,
    'modelo': modelo_uuid,
    'aprobacion': aprobacion_propia_uuid,
    'expediente_sha256': sha_del_expediente_abierto,
    'clave_solicitud': clave_uuid32,
}
```

Los IDs son32 hexadecimales minúsculos. El modelo se consulta mediante `app.resultados` y la aprobación mediante la API pública `revision_modelo.consultar_aprobacion`; debe corresponder al modelo y huella exactos. No se toma la última aprobación ni se hereda la de geometría/configuración. La misma clave/payload dentro de un caso devuelve el trabajo ya registrado; la misma clave con otros datos se rechaza. Preparar no inicia procesos ni calcula.

`ejecutar` exige exactamente:

```python
{
    'caso': caso,
    'trabajo': trabajo_uuid,
    'huella_preparacion': sha_de_la_preparacion_abierta,
    'expediente_sha256': sha_del_expediente_abierto,
    'confirmacion_explicita': True,
}
```

Solo se inicia un trabajo preparado, con preparación/fuentes vigentes y exclusión global disponible. El retorno inmediato indica `en_ejecucion` e ID; la consulta posterior muestra el progreso. Repetir ejecución sobre el mismo trabajo iniciado/terminal consulta su estado, sin otro lanzamiento. La confirmación y las huellas siguen siendo obligatorias al repetir. No existe campo HTTP para elegir PID, casos, comando, modo, DLL, timeout o carpeta de salida.

## Respuesta exacta

`preparar`, `ejecutar` y `consultar` devuelven estas claves:

```python
{
    'id': trabajo_uuid,
    'caso': caso,
    'modelo': modelo_uuid,
    'aprobacion': aprobacion_uuid,
    'expediente_sha256': sha_expediente,
    'huella_preparacion': sha_preparacion,
    'huella_modelo': huella_modelo,
    'sha256_aprobacion': sha_aprobacion,
    'datos_sinteticos': True,
    'casos': ['EST'],
    'estado': 'preparado',
    'vigente': True,
    'corrida_id': None,
    'estados_casos': {},
    'modo_ejecucion': None,
    'analisis_ejecutado': False,
    'calculo_verificado': False,
    'resultado_normalizado': False,
    'aprueba_resultados': False,
    'revision_resultados': 'pendiente',
    'conformidad_normativa': 'no_evaluada',
    'requiere_recuperacion': False,
    'problemas': [],
}
```

El ejemplo muestra casos de prueba, no una selección técnica predeterminada. `casos` siempre procede de la configuración del modelo aprobado. El ID de corrida es distinto del de trabajo y pasa a estar disponible cuando el worker prepara el analizador. En éxito: `estado='aceptado'`, `estados_casos` contiene exactamente los casos declarados con estado CSI entero4, y `modo_ejecucion` indica `real` o `doble` de prueba. El modo no se deduce de la naturaleza sintética de los datos: un cálculo real puede usar fixture sintética.

`analisis_ejecutado=true` registra la finalización aceptada de esa ejecución histórica. `calculo_verificado=true` requiere además que sus fuentes y artefactos sigan vigentes en esta consulta. Si cambian después, el estado histórico puede conservarse como aceptado mientras `vigente=false`, `calculo_verificado=false` y `problemas=['entradas_o_evidencias_no_vigentes']`. No presentar ese caso como resultado vigente.

`resultado_normalizado` y `aprueba_resultados` son siempre false. El cálculo no crea filas normalizadas, no evalúa normativa ni revisa resultados. No se devuelven rutas internas, PID, comandos, mensajes del motor, configuración cruda ni tablas. `listar` retorna `{caso, expediente_sha256, trabajos: [respuestas_anteriores]}` en orden de creación de filas.

## Estados y errores

Se reutiliza la máquina persistente de `ServicioEjecucion` sin modificar ese módulo:

| Estado | Significado |
| --- | --- |
| `preparado` | Modelo/aprobación/configuración/expediente capturados y comprobados; ningún proceso iniciado. |
| `en_ejecucion` | Reserva global adquirida; el worker puede preparar e iniciar una instancia propia de análisis. |
| `aceptado` | `AnalizadorEtabs` aceptó entrada, salida y casos, se revalidaron fuentes y se conservó un recibo ligado a los artefactos. |
| `fallido_sin_lanzar` | Revalidación anterior al worker rechazó fuentes; no se inició proceso. |
| `incierto` | Interrupción, cálculo/aceptación no confirmados, fallo parcial o finalización no verificable. Conservar evidencia y recuperar externamente. |

`ErrorAnalisis` hereda `ErrorEjecucion`/ValueError y expone `.codigo` con mensaje constante sin rutas. HTTP puede responder409 con `{error: error.codigo, codigo: error.codigo}`. Además de los códigos compartidos de construcción (`campos_invalidos`, `identificador_invalido`, `expediente_cambio`, `confirmacion_requerida`, `preparacion_cambio`, `entradas_no_vigentes`, `otra_ejecucion_activa`, `motor_incierto`, `trabajo_ausente`, `clave_reutilizada_con_otros_datos`), incorpora `aprobacion_de_otro_modelo`, `aprobacion_no_vigente`, `fuentes_cambiaron`, `casos_invalidos`, `modelo_doble_no_ejecutable_real`, `snapshot_alterado` y los rechazos de aceptación/artefactos. Los fallos internos de preparación se traducen a `preparacion_rechazada`; consultas/ejecución conservan el manejo genérico compartido.

## Persistencia, motor y exclusión compartida

El servicio toma **las mismas rutas** `base`, `lease`, `motor_lock` y `pendiente` de `app.ejecucion`, sin crear un motor paralelo. La base de filas de análisis es `<raiz>/.ejecucion_web/analisis.sqlite3`; la lease y marcador son exactamente `trabajo.lock` y `operacion_pendiente.json` de construcción. Sus dos bases no autorizan ejecuciones simultáneas: la lease de sistema operativo precede al lanzamiento y permanece tomada hasta terminar el worker; el marcador sobrevive a una interrupción. Los adaptadores usan el mismo `motor.lock`.

Un trabajo de construcción activo bloquea análisis y viceversa, aun entre procesos/clientes distintos de la misma raíz. Otros clientes externos deben usar también el bloqueo de motor compartido. El RLock local coordina solicitudes de esa app, mientras la lease protege el recorrido compuesto entre procesos.

Los snapshots del trabajo están en `caso/trabajos_analisis/<trabajoUUID>`: `modelo.edb`, `version_modelo.json`, `configuracion.json`, `aprobacion.json`, `expediente.json`, `preparacion.json`, eventos y errores privados. `preparacion.json` liga SHA256 de esos snapshots. Antes de lanzar y después de ejecutar se revalidan modelo/aprobación propios, geometría/configuración/originales vinculados y bytes capturados.

Las corridas efectivas se escriben en `caso/analisis_etabs/<corridaUUID>`, sin otro UUID padre para el transporte. Es el grupo que `ServicioEntregables` puede inspeccionar posteriormente. Preflight Windows rechaza rutas previstas de solicitud/respuesta/entrada/EDB de260 o más caracteres antes de iniciar motor, con `ruta_motor_demasiado_larga_use_raiz_mas_corta`.

El worker llama `AnalizadorEtabs.preparar_analisis` y `ejecutar_analisis(..., confirmar_analisis=True)`. El analizador existente crea la instancia nueva propia y copia de entrada; no se elige una instancia activa del usuario ni se suministra PID desde el navegador. La aceptación del driver exige EDB/entrada/casos terminados y conserva incertidumbre ante fallos. El servicio además coteja contratos/versiones, IDs, modelo/aprobación/huellas, modo/naturaleza, guardado, casos y estados enteros4 entre solicitud, respuesta y aceptación; no acepta un JSON que solo declare éxito.

Tras éxito se crea `aceptacion_web.json`, con hashes de solicitud, respuesta, aceptación, entrada y EDB analizado. Su SHA queda ligado al registro persistente del trabajo. La consulta posterior comprueba recibo, bytes y coherencia semántica junto a fuentes actuales. Se validan tipos antes de acceder a objetos/arrays: metadata malformada invalida la consulta y no produce AttributeError HTTP.

No se usa una función privada de `evidencia_analisis` ni se fabrica un contrato de resultados. La futura normalización tendrá que leer tablas y seleccionar correspondencias revisadas; solo entonces se podrá demostrar vínculo resultado/análisis mediante las APIs de evidencia existentes.

## Reinicio y límites

Los workers son hilos daemon. No se reanudan al reiniciar el servidor. Una fila en ejecución sin lease ocupada pasa a incierto al consultar; se conserva el marcador. Mientras exista incertidumbre web o del adaptador se bloquean nuevos lanzamientos de ambos servicios. La recuperación exige comprobación externa y conservación/archivo de evidencia; no hay una acción de este servicio que borre marcadores, cierre ETABS o reintente automáticamente. Tras una recuperación autorizada se prepara un trabajo nuevo con clave distinta.

El constructor admite `fabrica_analizador(work, motor_lock)` únicamente por Python para pruebas controladas. El producto predeterminado usa el analizador real con su script existente. Una fábrica doble solo admite fuente de modo doble y datos sintéticos; no se transforma evidencia real en doble de manera implícita. No se ejecutó ETABS real para verificar esta nueva vía.

## Pruebas focales

```powershell
$env:TEMP = Join-Path (Get-Location) 'tmp'
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m unittest tests.test_revision_analisis -v
```

Trece pruebas pasaron en25.636s sin omisiones en Windows. Las fixtures generan geometría/modelo/aprobación sintéticos nuevos a partir de ejemplos del repositorio, sin rutas tmp de sesiones previas. Usan `AnalizadorEtabs` y su aceptación real de software con transporte Python doble; no sustituyen el analizador por un mock que declare aceptación.

Cubren preparación sin procesos, replay/conflicto, confirmación, mezcla modelo/aprobación, alteración de fuentes antes y durante transporte, cálculo aceptado sin normalización, estados incompletos, salida abrupta, reinicio preparado/huérfano, tampering de los cinco artefactos, tipos malformados aun recalculando el hash del recibo, aprobación con controles de tipo incorrecto, preflight y exclusión contra construcción mediante otro proceso Python. No se ejecutó suite completa, ETABS, red, UI ni Computer Use.
