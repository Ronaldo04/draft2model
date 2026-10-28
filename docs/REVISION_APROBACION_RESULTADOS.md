# Revisión propia declarada de resultados

`draft2model.revision_aprobacion_resultados.ServicioRevisionResultados(app)` conserva una declaración nueva e inmutable sobre un resultado normalizado y un análisis completo **seleccionados explícitamente**. No ejecuta ETABS, no reescribe los resultados y no usa IA para declarar controles. No aprueba un informe ni decide conformidad normativa o seguridad estructural.

## API pública para integrar

```python
service = ServicioRevisionResultados(app)
fuentes = service.consultar_fuentes(caso, resultado_uuid, analisis_uuid,
                                  expediente_sha256=fp)
revision = service.registrar({
    'caso': caso,
    'resultado': resultado_uuid,
    'analisis': analisis_uuid,
    'expediente_sha256': fp,
    'huella_resultados': fuentes['huella_resultados'],
    'huella_evidencia': fuentes['huella_evidencia'],
    'revisor_declarado': 'Identidad declarada de quien revisa',
    'fecha': '2026-10-18',
    'alcance': 'Alcance concreto de las filas y casos revisados',
    'motivo': 'Descripción concreta de la revisión realizada',
    'controles': {
        'unidades': True,
        'casos': True,
        'filtros': True,
        'omisiones': True,
        'consistencia_modelo': True,
        'revision_tecnica': True,
    },
    'faltantes_criticos': [],
    'observaciones': ['Observación explícita del revisor, si corresponde'],
    'confirmacion_explicita': True,
})
detalle = service.consultar(caso, revision['id'], expediente_sha256=fp)
historial = service.listar(caso, resultado_uuid, expediente_sha256=fp)
```

Los campos de `registrar` son **exactamente** los del ejemplo. No se admiten rutas, opciones de motor, campos adicionales ni referencias a resultados de otro caso. Los UUID son 32 hexadecimales en minúscula y los SHA/huellas 64. Confirmación y los seis controles deben ser exactamente `True`; faltantes, controles adicionales, `False`, `1` o texto se rechazan. Los controles se exportan también en la constante pública `CONTROLES`.

Revisor: texto de 1–150 caracteres no vacío; alcance/motivo: 1–4000 cada uno; fecha: fecha ISO real `AAAA-MM-DD`. `observaciones` y `faltantes_criticos` son listas explícitas de hasta 100 textos no vacíos de hasta 2000 caracteres. `observaciones` puede estar vacía. **`faltantes_criticos` debe estar presente y vacía**: cualquier falta crítica declarada bloquea el registro.

## Qué se verifica y qué declara la persona

Se reutilizan exclusivamente las APIs públicas `app.resultados.consultar_resultado`, `evidencia_analisis.verificar_analisis_aceptado`, `verificar_evidencia` y `huella_evidencia`. Se verifican publicación normalizada, configuración/geometría/originales, mapeo y correspondencias, modelo/revisión propia, EDB leído y analizado, entrada, solicitud/respuesta/aceptación, naturaleza sintética, versión ETABS y casos completos CSI **entero 4**. La corrida solo puede ser `<caso>/analisis_etabs/<UUID>`; no se usa PID histórico ni instancia activa.

No basta con un paquete válido o un JSON de éxito. El resultado debe contener indicadores, ser vigente y corresponder al análisis, modelo y EDB exactos. Se conservan todos los SHA de archivos del paquete normalizado; incluso cambiar sus bytes sin cambiar el JSON semántico invalida una revisión anterior. Las fuentes se contrastan antes/después de preparar la publicación y al consultar; las revisiones listadas se revalidan otra vez antes de devolver el historial.

El software **no determina qué omisión es crítica para ingeniería**, qué variables son aplicables a un caso ni si el alcance profesional es suficiente. Esa clasificación requiere conocimiento externo al registro y se declara explícitamente mediante alcance, controles, observaciones y `faltantes_criticos`. No se inventan umbrales ni se exige periodo a una corrida EST. Una fila null con motivo puede permanecer revisada dentro del alcance declarado, conservando su omisión; no se convierte en número ni en prueba de completitud. Si quien revisa declara una falta crítica, debe resolverla antes de registrar. La identidad y competencia no están autenticadas, y una lista vacía no acredita completitud física ni seguridad.

## Respuestas exactas

`consultar_fuentes` es solo lectura y devuelve:

```text
{caso, resultado, analisis, expediente_sha256, huella_resultados,
 huella_evidencia, archivos_resultado:{nombre:sha256},
 analisis_aceptado:<proyección pública sin rutas>, evidencia:<evidencia pública>,
 datos_sinteticos, unidades, casos, advertencias, omisiones, indicadores,
 filas_omitidas, controles_requeridos:[...CONTROLES],
 revision_resultados:'pendiente', identidad_revisor:'declarada_no_verificada',
 conformidad_normativa:'no_evaluada', aprueba_resultados:false,
 aprueba_informe:false, aviso}
```

`registrar` y `consultar` devuelven la misma proyección de revisión:

```text
{id, caso, resultado, analisis, expediente_sha256, huella_resultados,
 huella_evidencia, sha256_revision, creado_utc, vigente:true,
 estado:'revision_declarada_vigente', revision_resultados:'revisados_declarados',
 declaracion:{revisor_declarado, fecha, alcance, motivo, controles,
              faltantes_criticos:[], observaciones:[...]},
 fuentes:<snapshot completo de consultar_fuentes sin sus campos de presentación>,
 identidad_revisor:'declarada_no_verificada',
 competencia_revisor:'declarada_no_verificada', verificacion_profesional:false,
 aprueba_resultados:false, aprueba_informe:false, aprueba_ingenieria:false,
 conformidad_normativa:'no_evaluada', seguridad_estructural:'no_certificada', aviso}
```

`fuentes` conserva resultado/análisis/fp y huellas, inventario SHA, análisis aceptado, evidencia vinculada, naturaleza, unidades/casos, **todas** las advertencias y omisiones nativas, todas las filas y las filas null con su motivo. Las observaciones nuevas no sustituyen advertencias/omisiones. Las huellas no autentican a quien produce o revisa.

`listar(caso, resultado, expediente_sha256=fp)` devuelve:

```text
{caso, resultado, expediente_sha256,
 versiones:[{id,vigente:true,problemas:[],resumen:{analisis,huella_resultados,
    huella_evidencia,sha256_revision,revision_resultados,declaracion}}
    | {id,vigente:false,problemas:['revision_no_vigente'],resumen:null}],
 seleccion_automatica:false, conformidad_normativa:'no_evaluada'}
```

No elige la última versión ni hereda revisiones entre análisis/resultados/casos. El consumidor debe seleccionar un UUID y consultar esa revisión vigente con su SHA exacto antes de usarla. El estado nativo de `ServicioResultados` permanece `revision_resultados:'pendiente'`; esta entrega solo permite proyectar una revisión propia seleccionada. No modifica HTTP/UI, informes ni contratos normalizados existentes.

## Persistencia y errores

Cada revisión se conserva en `<caso>/revisiones_resultados/<UUID>/` con `revision.json` y `version.json`. Este último vincula ID/caso/resultado/análisis/fp con `sha256_revision` de los bytes exactos. Se prepara en staging `.rev-*`, verifica con las mismas reglas y publica mediante rename; no sobrescribe versiones. La consulta exige conjunto exacto de archivos, declaración válida, snapshot actual idéntico y relectura final de ambos archivos. Se rechazan symlinks/junctions en raíz/caso/grupo/versiones y componentes comprobados. No se devuelve ninguna ruta interna, PID ni excepción del motor.

`ErrorRevisionResultados(codigo)` expone solo un código público. Para HTTP futuro, rechazos de contrato/vigencia pueden mapearse a 409: `campos_invalidos`, `identificador_invalido`, `huella_invalida`, `confirmacion_requerida`, `controles_explicitos_requeridos`, `declaracion_incompleta`, `fecha_invalida`, `observaciones_invalidas`, `faltantes_criticos_declarados`, `huellas_no_coinciden`, `resultado_cambio`, `fuentes_cambiaron`, `fuentes_no_vigentes`, `revision_no_vigente`, `registro_alterado`, `registro_cambio`, `registro_rechazado`, `consulta_rechazada`, entre otros códigos sanitizados del mismo módulo. No se infiere aprobación tras un error.

Se usa `app.lock`, sin bloqueo global entre procesos que escriban arbitrariamente fuentes. Las revalidaciones detectan cambios observados; no eliminan todo TOCTOU frente a un actor local. Si una fuente cambia después de publicar, puede quedar una revisión almacenada inválida: consultar la rechaza y listar la marca sin vigencia. Los registros no son firmas digitales ni autenticación y un actor con escritura total puede reconstruir archivos/hashes. Repetir `registrar` genera otra declaración independiente; no se promete idempotencia.

## Pruebas focales

Con temporales cortos dentro del workspace:

```powershell
$env:TEMP=Join-Path (Get-Location) 'tmp'
$env:TMP=$env:TEMP
.\.venv\Scripts\python.exe -m unittest tests.test_revision_aprobacion_resultados -v
```

La fixture se extrae desde `tests.fixture_etabs.extraer_evidencia`; la aceptación sintética conservada se copia al grupo controlado del caso. Las pruebas bloquean red/procesos y no crean valores de ingeniería. Cubren revisión/consulta/listado sin alterar el paquete, fuente/modelo/EDB/respuesta/aceptación alterados, confirmación, controles exactos, faltantes críticos, observaciones, IDs/huellas/caso, registros malformados, bytes alterados, cambio durante verificación, relectura final y enlace de grupo (skip explícito si el sandbox no permite crearlo). No se ejecuta ETABS, red, proveedor, CU ni suite completa.

Resultado: **9 pruebas, 8 OK y 1 skip explícito por Windows 1314 al crear enlace; 24.966 s.** Se corrigió primero un literal `bytes` de la prueba que contenía una tilde y bloqueaba su importación; no se había ejecutado ningún ensayo en ese intento. Después se ampliaron las regresiones de EDB del modelo y de enrutamiento de un registro alterado a otro resultado, ejecutando solo esos dos métodos focales (el primero: 1 OK, 3.766 s), sin repetir suite completa. El segundo evita que alterar solo el resultado de la declaración oculte una revisión inválida perteneciente al historial seleccionado.
