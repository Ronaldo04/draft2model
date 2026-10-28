# Informe con revisión declarada de resultados seleccionada

La selección es opcional y explícita. No hereda la última revisión, no cambia el paquete normalizado ni su evidencia y no certifica competencia, completitud física, normativa o seguridad. Sin la clave opcional se conserva la forma anterior del informe y de su respuesta pública.

## Contrato para el formulario de informes

`ServicioEntregables.crear(body)` acepta los campos existentes `caso`, `resultado`, `expediente_sha256`, `contexto`, `analisis`, la opción existente `referencias` y, de forma independiente:

```json
"revision_resultados": {
  "id": "UUID32 seleccionado de revisiones_resultados",
  "sha256_revision": "SHA256 de la revisión consultada"
}
```

Los valores del ejemplo son marcadores, no identificadores utilizables. Si no se selecciona revisión, **omitir la clave**; `null`, `false`, listas, campos adicionales o huellas incorrectas se rechazan. Con selección, `analisis` debe contener el UUID exacto del análisis de esa revisión; null no sirve. Caso, expediente, resultado, naturaleza, indicadores, configuración, geometría y evidencia deben coincidir con las fuentes vigentes comprobadas por `ServicioRevisionResultados.consultar`.

El coordinador HTTP/UI monta el opt-in sobre su endpoint existente de creación; esta entrega no cambia rutas ni otros servicios. No enviar un snapshot desde el navegador. Consultar el registro seleccionado antes de construir `{id,sha256_revision}` y no elegir automáticamente la primera o última revisión.

Respuesta de crear/consultar/aprobar con selección:

```text
revision_resultados: 'revisados_declarados'
revision_resultados_seleccionada: {id,sha256_revision}
aprueba_resultados: false
conformidad_normativa: 'no_evaluada'
evidencia_analisis.estados.revision_resultados: 'pendiente'
```

Sin selección, `revision_resultados` sigue siendo `'pendiente'` y `revision_resultados_seleccionada` no existe. El estado proyectado es separado del estado nativo pendiente; no se reescribe la evidencia ni `siete_resultados.estado_modelo_analisis`.

## Persistencia y uso

`paquete.json` conserva `revision_resultados:{id,sha256_revision}`. `informe.json` conserva, en su clave `revision_resultados`, la proyección completa e inmutable devuelta por el servicio: declaración, fuentes, huellas, naturaleza, advertencias, omisiones, filas omitidas y avisos. `huellas.revision_resultados` vincula ese snapshot al contenido del informe y a la aprobación documental propia.

Crear, consultar, descargar y aprobar reconsultan la revisión exacta, antes/después de sus comprobaciones y de la preparación del paquete. Una revisión, fuente, EDB o inventario de bytes obsoleto invalida también el informe y su descarga aunque sus archivos publicados conserven sus SHA. La validación semántica del JSON no acredita por sí sola autenticidad ni vigencia en disco.

La aprobación documental crea una hija; conserva referencia y snapshot exactos y verifica de nuevo el padre. No aprueba resultados ni cambia su revisión propia. No permite sustituir la revisión seleccionada por otra declaración equivalente.

HTML/PDF presentan «Revisión DECLARADA», origen ID/SHA, resultado/análisis, revisor y fecha declarados, alcance, motivo, controles, observaciones, lista explícita vacía de faltantes críticos y advertencias/omisiones nativas. Lista vacía no significa completitud y una fila null permanece null. Las identidades y competencia siguen declaradas, sin autenticación.

## API del núcleo

`crear_informe(..., fuente_revision_resultados=fuente)` y `exportar_informe(..., fuente_revision_resultados=fuente)` reciben una fuente viva **solo del backend**:

```python
fuente = {
    'app': app,                         # aplicación local de confianza
    'caso': caso,
    'id': id_revision,
    'sha256_revision': sha_consultado,
    'expediente_sha256': fp,
}
```

El núcleo instancia `ServicioRevisionResultados(app)` y consulta sus archivos y fuentes; un snapshot o callback arbitrario no sustituye esa fuente. También se debe aportar la fuente de `evidencia_analisis` y geometría exacta ya requeridas. La exportación de un informe con selección sin esta fuente se rechaza. `validar_informe` comprueba coherencia del snapshot reconstruyendo el registro y su SHA con el contrato nativo, además del vínculo a resultados/evidencia; no consulta disco ni equivale a exportación vigente.

El servicio reutiliza los validadores y serialización del contrato nativo de revisión. No ejecuta motor, procesos, proveedor ni red. La paginación existente no se modifica.

## Comprobación focal y límites

Las pruebas nuevas usan la fixture conservada del análisis sintético, bloquean red/procesos y verifican selección explícita, ausencia de autoselección, conservación de bytes nativos, contenido HTML/PDF, hija documental, errores de contrato/hash/caso/análisis, alteraciones de revisión/resultado/EDB y cambio durante render. El log focal se registra junto al resultado de ejecución, sin atribuir ingeniería a la fixture.

Una pasada focal de `tests.test_informe_revision_resultados`, `tests.test_revision_entregables` y `tests.test_informe`: **25 OK, 87.369 s**, log `tmp/informe_revision_resultados_130.log`. Después se fortaleció únicamente la regresión de snapshot inventado para reconstruir también su SHA nativo coherente: la validación semántica pasa y el servicio rechaza la fuente inventada; ese método focal vuelve a pasar en `tmp/informe_revision_resultados_fuente_130.log`.

Comando reproducible, con temporales dentro del workspace:

```powershell
.\.venv\Scripts\python.exe -c "import tempfile,pathlib,unittest;tempfile.tempdir=str(pathlib.Path('tmp').resolve());s=unittest.defaultTestLoader.loadTestsFromNames(['tests.test_informe_revision_resultados','tests.test_revision_entregables','tests.test_informe']);r=unittest.TextTestRunner(verbosity=2).run(s);raise SystemExit(not r.wasSuccessful())"
```

Se mantienen los límites del servicio nativo: identidad declarada, sin firmas ni bloqueo global frente a un escritor externo. Un actor con escritura total puede reconstruir registros y huellas. Los cambios observados durante las revalidaciones se rechazan; no se promete eliminar todo TOCTOU local. Un fallo antes de publicar el staging no produce una versión válida; si una fuente cambia después de publicar, la versión queda almacenada pero su consulta y descarga fallan.
