# Respuestas visuales locales en HTTP y web

La pantalla registra un JSON local contra el paquete visual vigente seleccionado en «Preparar evidencias visuales». No ejecuta un proveedor ni acredita una llamada anterior. Proveedor y modelo son nombres declarados. La selección explícita distingue prueba sintética de respuesta local declarada del expediente. Registrar y trasladar al historial son acciones independientes.

## Contrato HTTP

Todos los endpoints usan la sesión local, origen permitido, respuestas `no-store` y los límites JSON del servidor. Las mutaciones retornan 201, las consultas 200; falta de sesión/origen retorna 403 y contrato, asociación o vigencia rechazados retornan 409 con error sanitizado. No se admiten rutas de archivos suministradas por el cliente.

* `POST /api/respuesta/registrar`: cuerpo exacto `{caso, expediente_sha256, paquete, respuesta_json, proveedor_declarado, modelo_declarado, modo_prueba}`. `paquete` es el UUID contenedor seleccionado; su `solicitud_id` puede ser diferente. `respuesta_json` es texto JSON completo de hasta 1.5 MiB; proveedor/modelo son textos explícitos y `modo_prueba` es booleano estricto.
* `GET /api/respuestas?caso=…&expediente_sha256=…`: `{caso, expediente_sha256, versiones:[{id,vigente,paquete?,estado?}]}`. Las versiones inválidas solo conservan `id` y `vigente:false`.
* `GET /api/respuesta?caso=…&expediente_sha256=…&version=…`: misma respuesta detallada que registrar, `{id,caso,expediente_sha256,paquete,sha256_extraccion,extraccion,proveedor_declarado,modelo_declarado,modo_prueba,origen:'respuesta_local_declarada',transmision_externa:false,traslado_permitido,estado:'pendiente_revision',aprueba_ingenieria:false}`. El servicio existente vuelve a comprobar paquete, solicitud, respuesta y extracción adaptada.
* `POST /api/respuesta/importar`: cuerpo exacto `{caso,expediente_sha256,respuesta,sha256_extraccion,confirmacion_explicita:true}`. Retorna `{caso,extraccion,estado:'pendiente_revision',aprueba_ingenieria:false}`. La huella es la de la extracción abierta; no se deriva del editor de registro. Una prueba sintética no puede trasladarse al expediente y su control permanece deshabilitado.

## Cliente y límites

`respuestas.js` consume `d2m-visual-package`, muestra paquete/solicitud/huella y conserva el texto crudo del JSON. Cambiar paquete invalida archivos y registros en vuelo. Cambiar caso o versión descarta respuestas y errores tardíos; un relistado no vigente limpia detalle y confirmación. Consultar o relistar nunca registra ni importa. El archivo local se lee dentro del navegador, con límite previo y comprobación posterior del texto UTF-8 al registrar.

Tras un traslado comprobado, emite `d2m-extraction-created` con `{caso,extraccion,estado,aprueba_ingenieria,expediente_sha256}`. `app.js` actualiza el historial de extracciones del mismo caso/huella con guardas de selección y secuencia, conservando la selección actual. La persona selecciona después la extracción pendiente para revisarla; el evento no aprueba candidatos, geometría, modelos ni resultados.

Los registros y traslados reutilizan `ServicioRespuestas` sin modificarlo. No se añade una garantía de idempotencia a sus mutaciones: repetir una acción deliberadamente puede conservar otra versión. No se incorpora autenticación de proveedor/revisor, envío externo, ejecución ETABS ni evaluación de ingeniería. Esta contingencia no sustituye una futura integración deliberada de proveedor.

## Verificación focal

Con `TEMP` y `TMP` establecidos en `workspace/tmp`:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_revision_respuestas tests.test_revision_respuestas_http -v
& 'C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests/revision_respuestas_frontend.cjs
```

Resultado: **7 pruebas Python OK (4.277 s)** y **10/10 Node OK**, una pasada final. HTTP en memoria comprueba el flujo nativo portable, origen/sesión, campos/huella/confirmación, alteraciones de fuente, prueba no trasladable y publicación de assets. Node ejecuta `app.js` y `respuestas.js` juntos con bus de eventos real y DOM/HTTP simulados; comprueba separación de acciones, historial pendiente, declaraciones visibles, límites, carreras por caso/versión/paquete y ausencia de evento tras importación obsoleta. No se abrió navegador, proceso ETABS ni conexión externa.
