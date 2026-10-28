# Servicio local de consulta de resultados y modelos

Implementado el 17 de octubre de 2026 en `draft2model/revision_resultados.py`. Solo lectura; no construye, analiza, normaliza, genera entregables ni aprueba. Usa la fixture sintética portable capturada en ETABS21.1 para verificar consultas sin conectar el motor.

## Integración HTTP

Instanciar `ServicioResultados(app)`, donde app proporciona `raiz`, `lock` y `expediente(caso)`. Todos los métodos adquieren `app.lock`, validan el expediente y vuelven a comprobar su SHA256 después de verificar las versiones.

| Ruta GET propuesta | Llamada |
| --- | --- |
| `/api/resultados?caso=...` | `listar_resultados(caso)` |
| `/api/resultado?caso=...&version=...&expediente_sha256=...` | `consultar_resultado(caso, version, expediente_sha256=...)` |
| `/api/modelos?caso=...` | `listar_modelos(caso)` |
| `/api/modelo?caso=...&version=...&expediente_sha256=...` | `consultar_modelo(caso, version, expediente_sha256=...)` |

Las rutas las integra el manejador HTTP por separado. Mantener controles existentes de sesión/origen/Host y no registrar los datos privados. `ErrorResultados` hereda ValueError y tiene mensajes constantes sin rutas; puede traducirse a 409. No reenviar excepciones internas. No se agrega ninguna operación POST.

Los IDs de versión deben ser cadenas de 32 hexadecimales minúsculos. Los detalles requieren SHA256 de expediente de 64 hexadecimales minúsculos y concordante con el listado; cambios durante la consulta también rechazan el resultado. Se rechazan archivos/directorios enlazados o reparse points y directorios de versiones sustituidos por archivos.

## Contratos exactos

Ambos listados retornan exactamente `{caso, expediente_sha256, versiones}`. `versiones` está ordenado por ID; cada fila contiene exactamente `{id, vigente, problemas, resumen}`. No se infiere antigüedad del UUID. Una versión inválida queda visible así:

```json
{"id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","vigente":false,"problemas":["version_no_vigente"],"resumen":null}
```

Una carpeta de grupo ausente retorna `versiones: []`; un grupo alterado/enlazado se rechaza. Un detalle ausente o sin vigencia se rechaza, en lugar de devolver cifras antiguas.

Resumen válido de resultado: `{creado_utc, motor, datos_sinteticos, configuracion_id, corrida_tablas_id, estado: "paquete_verificado", analisis_vinculado: false, aprueba_resultados: false}`. Resumen válido de modelo: todos los campos del `origen` proyectado descrito abajo, más `{estado: "modelo_verificado", revision: "pendiente", aprobacion: null, analisis_vinculado: false, aprueba_resultados: false}`.

Detalle de resultado: claves exactas `id`, `caso`, `expediente_sha256`, `vigente`, `estado`, `huella`, `datos`, `metadatos`, `analisis_vinculado`, `evidencia_analisis`, `revision_resultados`, `conformidad_normativa`, `aprueba_resultados`.

```python
{
    'id': resultado_id, 'caso': caso, 'expediente_sha256': sha_expediente,
    'vigente': True, 'estado': 'paquete_verificado', 'huella': huella_resultados,
    'datos': contrato_resultados_estructurales,
    'metadatos': {
        'configuracion_id': configuracion_id_interno,
        'huella_configuracion': huella_configuracion,
        'geometria_version_id': geometria_id,
        'sha256_geometria': sha_geometria,
        'sha256_edb_leido': sha_edb,
        'corrida_tablas_id': corrida_lectura_id,
        'mapeo_revision_vigente': True,
    },
    'analisis_vinculado': False, 'evidencia_analisis': None,
    'revision_resultados': 'pendiente', 'conformidad_normativa': 'no_evaluada',
    'aprueba_resultados': False,
}
```

`datos` es el contrato normalizado completo ya verificado, no la respuesta CSI, el mapeo o la configuración snapshot crudos. `huella` es semántica; no confundirla con SHA256 de bytes. `configuracion_id` es la identidad interna de configuración, no el UUID de una carpeta versionada.

Detalle de modelo: claves exactas `id`, `caso`, `expediente_sha256`, `vigente`, `estado`, `huella_modelo`, `origen`, `revision`, `aprobacion`, `analisis_vinculado`, `aprueba_resultados`.

```python
{
    'id': modelo_id, 'caso': caso, 'expediente_sha256': sha_expediente,
    'vigente': True, 'estado': 'modelo_verificado', 'huella_modelo': huella_modelo,
    'origen': {
        'datos_sinteticos': True, 'modo': 'real',
        'huella_plan': huella_plan, 'sha256_modelo': sha_edb_construido,
        'configuracion_id': configuracion_id_interno,
        'huella_configuracion': huella_configuracion,
        'geometria_version_id': geometria_id, 'sha256_geometria': sha_geometria,
    },
    'revision': 'pendiente', 'aprobacion': None,
    'analisis_vinculado': False, 'aprueba_resultados': False,
}
```

El ejemplo combina motor real con datos sintéticos porque son dimensiones distintas. La consulta de modelo no busca ni hereda aprobaciones existentes. El EDB de modelo construido y el EDB analizado de los resultados son artefactos diferentes: no exigir igualdad entre sus SHA256.

## Política de verificación

Se reutilizan únicamente las APIs públicas `evidencia_analisis.verificar_resultado_normalizado` y `revision_modelo.consultar`. El verificador del resultado comprueba paquete, configuración/geometría/originales, mapeo, copia EDB y rederivación de tablas; el de modelo verifica configuración/plan, aceptación integrada, EDB y traza. No se leen rutas históricas externas declaradas por la fixture. El servicio proyecta campos permitidos y nunca devuelve `Path`, rutas de archivos, mapeo/trazabilidad/respuesta CSI ni configuración cruda. Los textos del contrato normalizado conservan sus valores originales.

`vigente` expresa que esa versión sigue verificándose contra sus entradas, no que sea la configuración elegida actualmente en un formulario. El SHA del manifiesto evita mezclar una consulta con un expediente cambiado; no inventa una referencia histórica al manifiesto dentro de contratos que no la almacenan. El bloqueo local no sustituye una transacción frente a otro proceso que edite archivos; las APIs del dominio hacen su verificación y se comprueba nuevamente el manifiesto antes de responder.

Un paquete normalizado válido **no acredita análisis vinculado**. Para una capa posterior, una corrida seleccionada explícitamente deberá pasar `verificar_evidencia`; no usar el ID de lectura como si fuera la corrida de análisis. Esta capa siempre devuelve `analisis_vinculado: false`, resultados pendientes y normativa no evaluada. Consultar no registra decisiones de ingeniería.

## Pruebas focales

```powershell
$env:TEMP = Join-Path (Get-Location) 'tmp'
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m unittest tests.test_revision_resultados -v
```

Ocho pruebas verifican la fixture portable sin escrituras, correlación de configuración/geometría entre modelos y resultados, aprobación no heredada, proyección sin rutas, alteraciones de paquetes/modelo/original, aislamiento de casos, IDs inválidos, huella desactualizada o cambiada durante consulta, directorios alterados, reparse points y grupos ausentes. La comprobación de reparse point usa un doble de metadatos de Windows, sin requerir permiso para crear symlinks. No ejecutan ETABS/red/UI ni dependen de temporales de sesiones anteriores.
