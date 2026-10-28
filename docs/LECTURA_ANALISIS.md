# Lectura de tablas desde un análisis aceptado

Implementado el17 de octubre de2026. `LectorAnalisis` abre el EDB analizado en su carpeta original mediante una instancia nueva propia, comprueba versión/unidades/casos y lee tablas. No copia el EDB, no recalcula, no guarda ni selecciona una instancia activa/histórica. No normaliza ni aprueba resultados. La clase reutiliza transporte, timeout, exclusión y recuperación de `AdaptadorEtabs`; el script nativo está separado en `scripts/leer_analisis_etabs.ps1`.

## API pública para verificar el análisis sin resultados

```python
evidencia_analisis.verificar_analisis_aceptado(raiz, caso, corrida: Path) -> dict
```

Solo admite una corrida localizada exactamente en `<raiz>/<caso>/analisis_etabs/<UUID32>`: nombres y rutas controlados, sin enlaces/reparse points. Verifica internamente aceptación, solicitud/respuesta, EDB analizado, copia de entrada y revisión propia de modelo/configuración/geometría/fuentes. Vuelve a comprobar bytes antes de responder y no escribe archivos ni contacta ETABS. No exige resultado normalizado.

Proyección exacta sin rutas ni PID:

```python
{
    'caso': caso, 'corrida_id': corrida_uuid, 'modo': 'real',
    'datos_sinteticos': True,
    'modelo_id': modelo_uuid, 'huella_modelo': huella_modelo,
    'aprobacion_id': aprobacion_uuid, 'sha256_aprobacion': sha_aprobacion,
    'sha256_edb_analizado': sha_edb, 'sha256_entrada': sha_entrada,
    'sha256_aceptacion': sha_aceptacion_analisis,
    'sha256_solicitud': sha_solicitud_analisis,
    'sha256_respuesta': sha_respuesta_analisis,
    'version_etabs': version_motor,
    'casos': ['EST'], 'estados_casos': {'EST': 4},
    'configuracion': {'id': configuracion_id_interno, 'huella': huella_configuracion},
    'geometria': {'id': geometria_version_uuid, 'sha256': sha_geometria},
    'analisis_ejecutado': True, 'aprueba_resultados': False,
}
```

El ejemplo separa modo real y naturaleza sintética, y no selecciona casos técnicos por defecto. Los estados de aceptación y respuesta deben ser enteros CSI4; se rechazan tipos y versiones contractuales incoherentes. Errores: `ErrorEvidenciaAnalisis` con mensaje fijo sin rutas. Se añadió esta API sin cambiar el comportamiento de las APIs anteriores de resultados/vínculo.

## Preparación y ejecución del lector

```python
from draft2model.lectura_analisis import LectorAnalisis, configuracion_real

# Crear previamente el directorio autorizado dentro del caso.
config = configuracion_real(caso_dir / 'lecturas_etabs', bloqueo_motor_compartido)
lector = LectorAnalisis(config)
preparada = lector.preparar_lectura(
    raiz, caso, caso_dir / 'analisis_etabs' / analisis_uuid,
    tablas=tablas_elegidas_explicitas,
    casos=casos_elegidos_explicitos,
)
# La preparación anterior no inició ningún proceso.
respuesta = lector.ejecutar_lectura(preparada, confirmar_lectura=True)
```

`preparar_lectura` exige listas no vacías, sin duplicados, y casos que pertenezcan al análisis aceptado. No se admiten combinaciones por ahora. El modo del transporte debe coincidir con el del análisis; el doble solo admite datos sintéticos. No se aceptan PID históricos ni rutas del EDB elegidas por el usuario: la ruta se deriva del análisis controlado.

El transporte debe estar dentro del mismo caso y sin enlaces. Se recomienda el grupo plano `caso/lecturas_etabs/<lecturaUUID>` para no anidar UUID innecesariamente. Preflight rechaza rutas de solicitud/EDB de260 o más caracteres en Windows antes de lanzar procesos. No se crea una copia `entrada.edb` en la lectura: el modelo se abre desde `analisis_etabs/<analisisUUID>/analizado.edb`, manteniendo su directorio de resultados auxiliares.

La preparación retorna `PreparacionLectura`, con campos `solicitud`, `raiz`, `caso`, `corrida_analisis`, `evidencia`, `bytes_solicitud`, `argv`. `solicitud` conserva el objeto `SolicitudPreparada` del adaptador: ID, carpeta, solicitud/respuesta y contenido. Este objeto y sus rutas son internos; no serializarlos directamente a HTTP. `evidencia` es la proyección pública del análisis anterior.

`ejecutar_lectura` es una operación síncrona de biblioteca. Una capa web debe ejecutarla en su worker, conservar trabajos/idempotencia y adquirir **también** la lease/marcador de `app.ejecucion` durante todo el recorrido. El `bloqueo_motor_compartido` debe ser exactamente `app.ejecucion.motor_lock`; la clase toma ese bloqueo del adaptador y usa su marcador de incertidumbre. No elegir otro bloqueo para eludir un trabajo activo o incierto.

La confirmación explícita `True` se exige en todos los modos. Una preparación solo puede ejecutarse con el mismo lector que la creó y una sola vez. Se revalidan solicitud/comando, snapshot, modelo/aprobación/fuentes y EDB antes de lanzar, bajo la exclusión y después de leer.

## Instancia propia, lectura y cierre

El script verifica primero SHA256 de solicitud, EDB y aceptación de análisis. Valida esquema de solicitud y casos; no evalúa código ni despacha nombres arbitrarios de métodos. Crea un objeto nuevo mediante `Helper.CreateObjectProgID` y `ApplicationStart`, exige identificar una única creación nueva y fija su handle de proceso junto con PID y hora de inicio para trazabilidad. No llama a GetObject/GetObjectProcess ni usa una instancia activa por omisión.

Abre el EDB original y exige la ruta exacta, casos persistidos con estado 4 y la misma versión de ETABS.

**Unidades** (ruta 201, revisión R208-01):
- ETABS 21.1 reabre el EDB en sus unidades de base de datos (observado N_mm_C).
- Igual que `analizar_modelo_etabs.ps1`, el lector registra las unidades al abrir (traza `unidades_api`) y fija `kN_m_C` como **unidades de presentación** de su instancia propia, que se cierra sin guardar. Después exige `kN_m_C` antes de leer.
- Si no se pueden fijar, falla sin recalcular ni guardar.
- El EDB y la aceptación se comprueban por SHA antes y después.

**`resultados_api`** (opcional, solo `["BaseReact"]`): lectura tipada de `cAnalysisResults.BaseReact` para los casos seleccionados, con dobles serializados como texto `R` invariante, sin el redondeo de la tabla de visualización.
- La respuesta incluye las unidades, el punto de reacción, los casos seleccionados y las filas.
- `_comprobar_datos` rechaza: la falta cuando se pide, la presencia sin pedirse, otros casos, otras unidades, valores no finitos o no textuales, y campos extra. La copia del EDB por sí sola no acredita disponibilidad de resultados auxiliares.

Se comprueban tablas disponibles, campos y tamaños de arrays CSI. Se conserva texto crudo, orden de campos y filas; no se interpretan valores ni se calculan envolventes. Las filas se filtran por `OutputCase`; únicamente para `Modal Periods And Frequencies` y `Modal Participating Mass Ratios` se admite `Case`. Tablas sin campo de caso admitido se rechazan. La validación Python exige tablas solicitadas exactas, filas del esquema correcto y casos seleccionados; la revisión del mapeo sigue siendo una etapa independiente.

Después de la lectura se verifican nuevamente modelo, casos y hashes. El cierre usa `ApplicationExit(false)` solamente sobre el objeto COM recién creado cuya propiedad se confirmó, sin guardar. Se exige que el proceso propio siga correspondiendo a su creación y se confirma su salida con el handle. No se mata ni se conecta a un proceso por PID histórico. Si no se identificó propiedad, se pierde el proceso o no se confirma cierre, no se acepta la lectura y se conserva incertidumbre para recuperación externa.

## Respuesta canónica y artefactos

`ejecutar_lectura` retorna `RespuestaPuente` con `operacion='leer_tablas'`. El archivo `respuesta.json` mantiene el contrato `draft2model.etabs_respuesta` v0.1.0, modo configurado, ID de lectura, estado, avisos y `fin_utc` UTC válido. `datos` contiene campos compatibles con el normalizador:

```python
{
    'modelo': ruta_absoluta_interna_del_edb_analizado,
    'version_etabs': version_verificada,
    'unidades': 'kN_m_C',
    'casos': casos_seleccionados, 'combinaciones': [],
    'estado_casos': {caso: 4 for caso in casos_seleccionados},
    'tablas': [{'clave': tabla, 'version_tabla': version_csi, 'campos': campos,
                'numero_registros_api': numero_original,
                'registros_descartados_por_caso': numero_descartado, 'filas': filas}],
    'instancia': 'nueva', 'id_proceso': pid_propio, 'inicio_proceso_utc': inicio_utc,
    'instancia_cerrada': True, 'sha256_modelo_verificado': sha_edb,
    'corrida_analisis_id': analisis_uuid,
    'analisis_ejecutado': False, 'aprueba_resultados': False,
}
```

Los campos de rutas/PID son evidencia interna, no una proyección HTTP. `analisis_ejecutado=false` significa que **esta lectura** no ejecutó análisis; el análisis fuente permanece registrado como ejecutado. La capa web puede proyectar ID/estado/hashes/version/unidades/casos/tablas y ocultar los campos de conexión.

Cada carpeta de lectura conserva:

- `solicitud.json`, `respuesta.json`: bytes originales del transporte.
- `evidencia_analisis.json`: snapshot público previo.
- `traza_lectura.jsonl`: trazabilidad nativa de creación/cierre o error.
- `aceptacion_lectura.json`: aceptación Python después de comprobar respuesta y fuentes.
- `estado_motor_resuelto.json` y logs del adaptador.

La aceptación tiene exactamente `aceptada`, `operacion`, `modo`, `lectura_id`, `corrida_analisis_id`, `sha256_aceptacion_analisis`, `sha256_edb`, `sha256_solicitud`, `sha256_respuesta`, `casos`, `instancia_nueva_cerrada`, `analisis_ejecutado`, `aprueba_resultados`. En fallo se conserva `lectura_no_aceptada.json`; el marcador compartido de incertidumbre permanece. No se borra evidencia ni se reintenta automáticamente. Los errores de transporte y tiempo son los mismos del adaptador, con artefactos privados conservados.

## Retomar y normalizar sin motor

Una lectura posterior a reiniciar el servidor se prepara de nuevo desde el análisis aceptado y crea otra instancia propia; no necesita que siga vivo el proceso que calculó. Si existe incertidumbre pendiente, primero hace falta recuperación externa. Un contexto de preparación no se reconstruye desde archivos para reejecutar una mutación desconocida; se conservan las solicitudes anteriores y se crea una nueva deliberadamente.

Una respuesta ya aceptada puede normalizarse sin ETABS, junto con mapeo revisado y fuentes vigentes. El mapeo debe referir `modelo.archivo='analisis_etabs/<analisisUUID>/analizado.edb'`, SHA exacto y SHA de `respuesta.json`, sin `archivo_motor` externo. `registrar_resultados` conserva el paquete canónico; `verificar_evidencia` demuestra después que corresponde a la misma corrida de análisis, configuración, geometría, casos y EDB. La lectura no crea ni aprueba ese mapeo.

## Verificación de esta entrega

```powershell
$env:TEMP = Join-Path (Get-Location) 'tmp'
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m unittest tests.test_verificacion_analisis tests.test_lectura_analisis -v
```

Doce pruebas correctas en26.889s, sin omisiones. Incluyen fixture portable conservada para la API pública y modelos/análisis sintéticos nuevos con transporte Python doble para el lector. Cubren preparación sin procesos, fuentes alteradas, modo/casos/filas/version/unidades/instancia/cierre incoherentes, timestamps, solicitud alterada, falso éxito, timeout, lectura modal y rechazo de trabajo externo. Una prueba completa lee mediante doble, normaliza con el módulo real sin motor y comprueba `verificar_evidencia`.

Se verificó además sintaxis con el parser de Windows PowerShell5.1 y firmas SDK por metadatos (`OpenFile`, `ApplicationExit`, `GetCaseStatus`, `GetTableForDisplayArray`), sin crear COM. Una comprobación estática protege ausencia de llamadas de cálculo, guardado, copia EDB o conexión a instancia activa. No se ejecutó ETABS real, red, Computer Use ni suite completa; queda pendiente el ensayo autorizado de esta vía nativa con motor real.
