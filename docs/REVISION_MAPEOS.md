# Correspondencias revisadas y normalización desde web

`ServicioMapeos` conserva configuración, respuesta de tablas y mapeo como versiones inmutables dentro de `caso/mapeos_resultados/<uuid>`. Cada revisión conserva al padre; aprobar crea una versión nueva del mismo contenido con declaración propia de revisor, fecha, motivo, alcance y huella. No aprueba resultados estructurales.

Primero se comprueba un análisis aceptado del mismo caso mediante `verificar_analisis_aceptado`. El mapeo debe citar exactamente `analisis_etabs/<analisisUUID>/analizado.edb`, su SHA256, configuración y respuesta. La respuesta conserva su modo declarado, versión, casos terminados y unidades. No se aceptan rutas arbitrarias del navegador, combinaciones ni una respuesta de otro modelo. La importación de JSON es una lectura conservada declarada; por sí sola no autentica que un productor ejecutara el lector.

La interfaz recibe el análisis aceptado seleccionado, o permite introducir su UUID explícitamente. Seleccionar el JSON de respuesta prepara un borrador con referencias y `selectores:[]`; el usuario debe declarar los selectores completos. Cada selector incluye id, variable (`periodo`, `deriva` o `cortante`), caso, dirección, ubicación, tabla, filtros exactos, campo numérico y unidad de origen. Las dos tablas modales admitidas usan `Case` para periodos modales; los demás selectores requieren `OutputCase`. No se infieren ejes, envolventes ni pasos. Cero filas se conserva como ausencia; varias filas rechazan el selector.

Guardar el borrador ejecuta la previsualización offline y muestra valores/correspondencias sin publicar resultados. Cambiar el JSON invalida los botones de aprobación y normalización hasta guardar y comprobar otra versión. La declaración de aprobación y la confirmación de publicar resultados son acciones independientes. Al publicar, se abre el resultado comprobado en la sección de resultados para poder generar el informe.

Rutas bajo sesión local, Host/Origin y límite JSON:

- GET `/api/mapeo/fuente?caso&analisis&expediente_sha256`: proyección del análisis comprobado.
- GET `/api/mapeos?caso&expediente_sha256` y `/api/mapeo?caso&version&expediente_sha256`.
- POST `/api/mapeo/importar`: `{caso,analisis,expediente_sha256,respuesta_json,mapeo_json}`.
- POST `/api/mapeo/revisar`: `{caso,version,expediente_sha256,huella_mapeo,mapeo_json}`; revisión en borrador.
- POST `/api/mapeo/aprobar`: base de revisión más `{revisor,fecha,motivo,alcance,confirmacion_explicita:true}`, sin mapeo_json.
- POST `/api/mapeo/normalizar`: base de revisión más `{clave_solicitud,confirmacion_explicita:true}`, sin mapeo_json.

Normalizar revalida snapshots, toda la cadena y fuentes; requiere mapeo aprobado. `normalizaciones_resultados/<claveUUID>` conserva solicitud y aceptación ligadas a la versión y al resultado publicado. La misma clave y entradas devuelve el resultado comprobado sin repetir. Un fallo después de reservar la operación deja evidencia pendiente; repetir no relanza automáticamente. La exclusión de sistema operativo `normalizacion.lock` ordena clientes/procesos del mismo caso. El paso no contacta ETABS ni comparte su motor.

`registrar_resultados` genera el paquete canónico; `verificar_evidencia` comprueba después su vínculo exacto con el análisis. Los valores permanecen sin revisión y la conformidad normativa no evaluada. Los hashes detectan cambios, sin autenticar al productor o al revisor. La consulta vuelve a comparar snapshots y metadatos después de previsualizar, evitando mezclar un mapeo antiguo con valores de un archivo cambiado.

Validación: seis pruebas de servicio/HTTP correctas en16.846s (`tmp/revision_mapeos_concurrencia_076.log`), con capturas de motor real sobre datos sintéticos, completamente offline. Cubren versiones, revisión/aprobación propia, previsualización, publicación, idempotencia, recibo ajeno, cambio de fuente, snapshot/padre alterados, interrupción y cambio durante previsualización. Node `tests/revision_mapeos_frontend.cjs` pasó controles, descarte de error tardío, cambios sin aprobar, confirmación y clave de reintento. Falta inspección visual de esta pantalla y conectar el lector nativo al flujo para prescindir de la importación manual.


## Transferencia de lectura aceptada

POST `/api/mapeo/importar-lectura` acepta exactamente `{caso, trabajo_lectura, expediente_sha256, mapeo_json}`. Revalida el trabajo aceptado y respuesta canónica dentro del servidor, sin exponer los bytes privados al navegador. Conserva `lectura:{trabajo,lectura_id,sha256_respuesta}` en version.json y en revisiones/aprobaciones posteriores; consultar revalida el trabajo y bytes originales. La proyección distingue `lectura_aceptada_verificada` de `respuesta_conservada_declarada` y ofrece procedencia_lectura sin rutas. El modo real/doble permanece en la evidencia de análisis: aceptar un transporte de prueba no acredita lectura física de ETABS. Versiones antiguas sin campo lectura se conservan como respuesta declarada.

Prueba HTTP083 recorre análisis previo doble → lectura explícita → transferencia → revisión → aprobación de correspondencias → normalización → panel vinculado, comprobando rechazo tras alterar recibo de lectura. Ocho pruebas conjuntas de integración/mapeos OK35.098s. Los selectores siguen siendo explícitos; no se infieren filas, modos ni direcciones.


## Recuperación de una publicación interrumpida

Una operación conserva solicitud, inventario previo y snapshots antes de normalizar. Si falta un recibo válido, bloquear nuevas claves evita duplicar resultados tras recargar el navegador. ServicioResultados no presenta como vigente el candidato aún no aceptado por esa operación web. El recibo exige evidencia íntegra y vínculo a solicitud/mapeo/resultado, no solo un estado o su existencia.

GET `/api/normalizacion/estado` informa pendientes y candidatos; POST `/api/normalizacion/recuperar` exige caso, expediente_sha256, clave_solicitud, resultado (UUID o null) y confirmacion_explicita:true. Un único candidato exacto puede revalidarse y aceptarse sin recalcular; null cancela solo un intento sin resultado y con inventario previo conocido. Se conserva toda evidencia. Un recibo inválido anterior se archiva antes del nuevo commit, sin borrarlo. En operaciones antiguas sin inventario y sin candidato no se inventa una cancelación: se necesita revisar la evidencia conservada.

La pantalla exige operación, acción y confirmación renovada al cambiar acción; consultar nunca relanza. Recuperar no aprueba valores estructurales. Diez pruebas servicio/HTTP099 correctas en26.401s; Node recuperación11/11. Paneles e informes filtran por resultado antes de incluir versiones rotas. La primera corrección del filtro de informes se aplicó al listado de análisis por una coincidencia de contexto; regresiones096 lo detectaron y fue corregido, once pruebas097 correctas en14.599s.
