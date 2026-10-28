# Proveedor visual: interfaz deliberada

El panel consume `ServicioProveedor` mediante una instancia lazy estable de `RevisionLocal.proveedor`. Preparar conserva plan, petición y huellas localmente: no exige clave ni llama al proveedor. No hay campo de credencial en la pantalla. La ejecución de producción usa la credencial del entorno del servidor y requiere una segunda acción explícita que advierte transmisión de imágenes/solicitud a OpenAI y posibles costos. No se calcula ni presenta una estimación económica.

## Contrato HTTP

Se conserva seguridad loopback, origen/sesión, límites JSON y `no-store`. GET retorna 200, POST aceptado 201, rechazo 409 con `{error:codigo,codigo}` para `ErrorProveedorWeb`, origen/sesión inválidos 403. No se permite transportar una función Python, credencial, URL ni ruta mediante estos cuerpos.

* `POST /api/proveedor/preparar`: cuerpo exacto `{caso,expediente_sha256,paquete,modelo,opciones:{max_tokens,detalle,timeout_s},clave_solicitud}`. Paquete y clave son UUID32. Modelo debe declararse; tokens enteros 256–16384, detalle `low|high|auto`, espera entera 1–180 s. Los campos empiezan vacíos. El cliente conserva la clave al repetir el mismo contenido después de un fallo de red; cambiar contenido genera otra clave. No se ejecuta automáticamente al preparar.
* `GET /api/proveedor/trabajos?caso=…`: `{caso,expediente_sha256,trabajos:[proyeccion]}`.
* `GET /api/proveedor/trabajo?caso=…&trabajo=…`: proyección pública del trabajo. Consultar puede reconocer un worker huérfano como incierto; nunca reenvía.
* `POST /api/proveedor/ejecutar`: cuerpo exacto `{caso,trabajo,huella_preparacion,expediente_sha256,confirmacion_explicita:true}`. Solo habilitado para trabajo preparado vigente cuyo paquete, solicitud, modelo y opciones coinciden con la selección explícita actual. La confirmación se consume al ejecutar. El servicio conserva su exclusión e idempotencia: nunca envía dos veces un trabajo.
* `POST /api/proveedor/recuperar`: cuerpo exacto `{caso,trabajo,huella_preparacion,confirmacion_explicita:true,resolucion:'cerrar_sin_reintento'}`. Se habilita solo para un trabajo incierto seleccionado, con confirmación independiente. Acepta evidencia conservada completa o cierra como incierto resuelto; no vuelve a enviar, no garantiza que no hubo costo.

La proyección contiene `id,caso,paquete,expediente_sha256,modelo_declarado,opciones,huella_preparacion,sha256_solicitud,sha256_plan,sha256_peticion,estado,vigente,problemas,requiere_recuperacion,modo,proveedor_declarado,llamada_real_acreditada,observado,costo_estimado,respuesta_visual,resolucion,aprueba_ingenieria:false,aprueba_resultados:false`. `observado` conserva modelo devuelto, ID declarado, uso y huella/duración observados; no contiene credenciales, imágenes ni rutas. `costo_estimado` es null. Estados: `preparado`, `en_ejecucion`, `completado_verificado`, `fallido_sin_envio`, `respuesta_rechazada`, `incierto`, `incierto_resuelto`.

## Respuesta y revisión separadas

`POST /api/respuestas/vincular-proveedor` consume el puente público `ServicioRespuestas.vincular_proveedor` con cuerpo exacto `{caso,expediente_sha256,trabajo,huella_preparacion,confirmacion_explicita:true}`. Requiere trabajo completado verificado y vigente con respuesta visual. Retorna la respuesta detallada pendiente, con `origen:'proveedor_verificado'`, `trabajo_proveedor`, `llamada_real_acreditada`, `transmision_externa`, `modo_prueba` y huella de extracción. La vinculación es otra confirmación independiente; no importa al historial ni aprueba.

El cliente comprueba identidad y modo del vínculo antes de emitir `d2m-response-created`. `respuestas.js` actualiza y abre el registro comprobado del mismo caso/huella. Su botón posterior de importación conserva huella y confirmación propias. Las pruebas sintéticas siguen no trasladables; el origen local declarado sigue sin acreditar llamada real. El backend de proveedor/respuestas y el cliente nativo no se modificaron en esta integración; el puente y la conservación sin autoimportar fueron entregados por el integrador.

## Carreras y sondeo

Solo se sondea el trabajo seleccionado `en_ejecucion`, cada cuatro segundos, hasta 30 consultas. Cambiar caso, paquete o trabajo cancela el temporizador y descarta respuestas/errores anteriores. Al terminar o fallar se detiene; agotado el límite, actualizar historial permite seguir consultando sin ejecutar. Consultar el mismo estado no borra otros paneles, emite cambios de análisis ni consume una confirmación del mismo trabajo/huella/estado/vigencia. Cambios reales invalidan confirmaciones. No hay reintento automático de preparación, ejecución, recuperación o vínculo.

## Verificación focal

Con `TEMP`/`TMP` dentro de `workspace/tmp`:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_revision_proveedor_http tests.test_revision_respuestas_http -v
& 'C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests/revision_proveedor_frontend.cjs
& 'C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests/revision_respuestas_frontend.cjs
```

Resultado: **7 Python OK (7.361 s)**, **14/14 Node proveedor** y **11/11 Node respuestas**. Se hizo una pasada Python; Node requirió corregir el doble DOM para que `replaceChildren` restableciera el valor seleccionado como un `<select>` real, y pasó al repetir las pruebas focales. HTTP usa parser en memoria y transporte Python sintético con guardas contra HTTP real/procesos y clave vacía. Node ejecuta los tres módulos reales con bus compartido, HTTP/DOM simulados y temporizadores controlados. Comprueba clave estable, confirmación, recuperación sin reenvío, origen real frente a sintético, vínculo sin importación, sondeo acotado y carreras. No se activó red, credencial, navegador ni ETABS; no se verificó una llamada real y no se ejecutó suite completa.
