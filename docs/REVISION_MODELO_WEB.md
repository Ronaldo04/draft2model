# Revisión propia del modelo desde el servicio web

Servicio `ServicioRevisionModelo(app)` en `draft2model/revision_aprobacion_modelo.py`. Implementado el17 de octubre de2026. No conecta ETABS, no ejecuta análisis, no aprueba resultados ni autentica la identidad/competencia del revisor.

## API para integrar

```python
consultar(caso, modelo, *, expediente_sha256) -> dict
aprobar(body) -> dict
```

`app` proporciona `raiz`, `lock`, `expediente` y `resultados`. El servicio usa `app.lock`, el SHA256 actual del expediente, `app.resultados.consultar_modelo` y las APIs públicas `revision_modelo.consultar`, `aprobar` y `consultar_aprobacion`. No depende de funciones privadas del módulo de revisión.

Propuesta HTTP: GET `/api/modelo/revision?caso=...&modelo=...&expediente_sha256=...`; POST `/api/modelo/aprobar`. Las rutas y la UI las integra el manejador por separado, conservando sus controles existentes de sesión/origen/Host y límites JSON. No se modificaron los archivos de esos componentes en esta entrega.

Integración posterior de Codex: ambas rutas ya están conectadas con controles HTTP existentes. `revision_web/revision_modelo.js` recibe el modelo comprobado, consulta sus aprobaciones propias, muestra la huella y solicita cinco controles independientes más confirmación, revisor, fecha y alcance. Al cambiar modelo/caso invalida la selección y los controles. Siete pruebas del servicio repetidas correctas6.255s (`tmp/revision_aprobacion_modelo_codex_063.log`); dos pruebas HTTP065 correctas1.786s. Node `tests/revision_modelo_frontend.cjs` comprueba respuesta obsoleta, controles, confirmación y limpieza. Sin inspección visual ni análisis por esta nueva vía.

`aprobar` acepta **exactamente**:

```python
{
    'caso': caso,
    'modelo': modelo_uuid,
    'expediente_sha256': sha_expediente,
    'huella_modelo': huella_del_modelo_abierto,
    'revisor': revisor_declarado,
    'fecha': '2026-10-17',
    'alcance': alcance_de_la_revision_propia,
    'controles': {
        'geometria_conectividad': True,
        'materiales_secciones': True,
        'cargas_masa': True,
        'apoyos_diafragmas': True,
        'casos_combinaciones': True,
    },
    'confirmacion_explicita': True,
}
```

Los cinco controles se toman de `revision_modelo.CONTROLES`. Todos deben declararse de forma explícita con booleano `True`: no se acepta entero1, claves faltantes/sobrantes ni controles inferidos. Revisor y alcance son textos no vacíos; la fecha ISO la verifica la API de dominio. El UUID de modelo es de32 hexadecimales minúsculos, el SHA del expediente de64. Cualquier cambio de huella/fuentes obliga a consultar/revisar de nuevo.

## Respuesta exacta

`consultar` devuelve las siguientes claves:

```python
{
    'caso': caso,
    'modelo': modelo_uuid,
    'expediente_sha256': sha_expediente,
    'huella_modelo': huella_modelo,
    'origen': origen_proyectado_de_ServicioResultados,
    'estado': 'pendiente',
    'aprobaciones': [],
    'controles_requeridos': list(revision_modelo.CONTROLES),
    'advertencias': [],
    'identidad_revisor': 'declarada_no_verificada',
    'analisis_ejecutado': False,
    'aprueba_resultados': False,
}
```

El origen contiene únicamente `datos_sinteticos`, `modo`, `huella_plan`, `sha256_modelo`, `configuracion_id`, `huella_configuracion`, `geometria_version_id` y `sha256_geometria`. No se devuelven rutas, `Path`, configuración snapshot, trazas ni comandos.

Cada aprobación propia vigente se representa así:

```python
{
    'id': aprobacion_uuid,
    'sha256_aprobacion': sha_archivo_aprobacion,
    'huella_modelo': huella_modelo,
    'revisor_declarado': revisor,
    'identidad_revisor': 'declarada_no_verificada',
    'fecha': fecha_iso,
    'alcance': alcance,
    'controles': controles_confirmados,
    'autoriza_analisis': True,
}
```

Cuando existe al menos una aprobación **propia** vigente para el modelo/huella seleccionados, `estado` es `aprobado`. Si hay varias se devuelven todas en `aprobaciones`, ordenadas por ID; no se elige una por fecha o por orden de UUID. La futura etapa de análisis tendrá que seleccionar un ID explícito. Geometría y configuración aprobadas permiten consultar el modelo construido, pero no llenan por sí solas esta lista.

`aprobar` devuelve la misma respuesta y añade `aprobacion_registrada`, el UUID de la declaración recién publicada y revalidada. Cada llamada explícita crea una declaración nueva; no hay clave de idempotencia en este contrato. Ante una respuesta interrumpida, consultar las aprobaciones antes de repetir. El modelo base conserva su estado inmutable pendiente; las declaraciones propias están en registros independientes de `aprobaciones_modelo`.

Si alguna carpeta de aprobación del caso con nombre UUID no es verificable, se excluye de la lista vigente y se informa `advertencias: ['aprobaciones_no_verificables_en_caso']`. La advertencia se refiere al caso: no atribuye a este modelo una carpeta cuyo contenido no pudo validarse. Una aprobación de otro modelo nunca se transfiere. Un grupo de aprobaciones enlazado o sustituido por un archivo se rechaza.

## Vigencia y errores

Antes y después de consultar/publicar se comprueban expediente, modelo, geometría/configuración y sus fuentes mediante las APIs del dominio. Las aprobaciones se revalidan otra vez antes de responder. No basta un JSON que diga aprobado: modelo, origen, huella y los cinco controles deben coincidir con el registro propio. Un cambio concurrente detectado después de publicar puede dejar evidencia en disco, pero la operación no responde con aprobación válida.

`ErrorRevisionModelo` hereda ValueError y tiene `.codigo`. Sus mensajes constantes no exponen rutas; HTTP puede traducirlos a409 con `{error: str(error), codigo: error.codigo}`. Códigos: `identificador_invalido`, `huella_expediente_invalida`, `expediente_cambio`, `caso_invalido`, `ruta_no_permitida`, `modelo_cambio`, `directorio_aprobaciones_invalido`, `aprobacion_cambio`, `campos_invalidos`, `confirmacion_requerida`, `controles_explicitos_requeridos`, `declaracion_incompleta`, `revision_modelo_no_vigente`, `aprobacion_rechazada`.

## Verificación focal

```powershell
$env:TEMP = Join-Path (Get-Location) 'tmp'
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m unittest tests.test_revision_aprobacion_modelo -v
```

Siete pruebas pasaron en10.253s sin omisiones. Usan copias verificadas de `tests.fixture_etabs.extraer_evidencia`; no dependen de tmp históricos. Conservan las aprobaciones históricas de la fixture fuera del grupo activo de su copia para verificar pendiente→declaración propia. Comprueban consulta sin escrituras, proyección sin rutas, controles/confirmación exactos, huellas/IDs/casos inválidos, EDB/configuración/original alterados, varias aprobaciones independientes, rechazo de aprobación alterada, cambio concurrente y ausencia de aprobación de resultados/cálculo. No se ejecutó suite completa, ETABS, red ni UI.
