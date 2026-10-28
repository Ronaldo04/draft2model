# Aprobación documental propia de informes

`ServicioEntregables.aprobar(body)` registra una aprobación **exclusivamente documental y declarada** mediante `informe.aprobar_informe`. No aprueba resultados, no acredita revisión profesional, no evalúa conformidad normativa y no certifica seguridad estructural. Las identidades y competencias no están autenticadas. Las pruebas sintéticas únicamente verifican software.

## API Python

El cuerpo debe tener exactamente estos campos; no acepta rutas ni campos adicionales:

```python
borrador = app.entregables.consultar(caso, version, expediente_sha256=fp)
aprobado = app.entregables.aprobar({
    "caso": caso,
    "version": version,
    "expediente_sha256": fp,
    "sha256_informe": borrador["archivos"]["informe.json"],
    "revisor_declarado": "Identidad declarada del revisor documental",
    "fecha": "2026-10-18",
    "motivo": "Descripción concreta de la revisión documental",
    "confirmacion_explicita": True,
})
```

`app.entregables` representa la instancia de `ServicioEntregables` correspondiente; también puede construirse `ServicioEntregables(app)`. `sha256_informe` es el SHA256 de los **bytes exactos** del JSON del borrador consultado, no la huella del contenido sin revisión. La confirmación debe ser el booleano `True`; `1`, texto `"true"`, `False` y ausencia se rechazan. Revisor y motivo deben ser textos no vacíos y la fecha debe tener formato ISO válido.

El resultado conserva el esquema de `consultar` y agrega `estado: "aprobado"` y:

```json
{"padre": {"id": "ID_DEL_BORRADOR", "sha256_informe": "SHA256_JSON_PADRE", "sha256_paquete": "SHA256_BYTES_PAQUETE_JSON_PADRE"}}
```

Se conserva `aprueba_resultados: false`, `revision_resultados: "pendiente"` y `conformidad_normativa: "no_evaluada"`. Las secciones del informe y sus estados pendientes permanecen idénticos a los del padre. Solo cambia el bloque `revision` del informe; la nueva aprobación se vincula a su contenido mediante la función del núcleo. Crear después otro informe siempre produce un borrador: no hereda esta aprobación.

## Versiones, integridad y límites

- Solo se admite **borrador → nueva versión aprobada**. No se vuelve a aprobar una versión aprobada ni se permite un padre aprobado. La profundidad máxima es un vínculo, lo que impide ciclos y cadenas arbitrarias. Varias aprobaciones declaradas independientes pueden partir del mismo borrador vigente; no se fusionan ni sustituyen.
- Se conservan intactos el borrador, su JSON, HTML, PDF y `paquete.json`. La hija tiene ID aleatorio nuevo y se publica mediante renombrado de una carpeta de staging propia. No se sobrescriben destinos existentes.
- Antes de publicar se verifican resultados, geometría, evidencia de análisis seleccionada, expediente y todos los hashes. Se vuelve a consultar el padre y se exige igualdad exacta, incluido el hash de los bytes de su paquete. El staging se consulta con las mismas reglas y se releen sus archivos al final. Tras publicar se consulta otra vez la nueva versión.
- `consultar`, `listar` y `archivo` aceptan la hija únicamente si su aprobación documental es válida, el contenido coincide con el padre salvo `revision`, el padre sigue vigente y fuentes/resultados permanecen exactos. La consulta vuelve a comprobar fuentes y padre y relee los bytes del paquete y de los tres artefactos antes de devolver datos. La descarga vuelve a consultar después de leer sus bytes.
- Una alteración del padre, de un artefacto, de los resultados o de la evidencia invalida la hija. El listado puede mostrar `vigente: false`; no repara huellas ni transfiere aprobación automáticamente.

El servicio trabaja bajo el bloqueo local existente. No bloquea escrituras de otros procesos a nivel de sistema de archivos; un cambio detectado después de publicar puede dejar una versión almacenada pero inválida que se rechazará al consultar. Los hashes y revisores declarados no protegen contra un actor local que reconstruya todos los archivos y registros. El núcleo no requiere red ni conexión ETABS; la interfaz local descrita a continuación reutiliza su API pública sin modificar el servicio.

## HTTP e interfaz local

`POST /api/informe/aprobar` recibe exactamente el cuerpo de la API Python anterior. Reutiliza sesión local, origen permitido, límite JSON y protección loopback del servidor. Retorna **201** con la consulta de la nueva hija; un rechazo de contrato, confirmación, SHA, vigencia o fuentes devuelve **409** con error sanitizado, y sesión/origen inválidos **403**. No recibe rutas. `POST /api/informe/crear` sigue creando borradores sin heredar la aprobación.

El panel de informes conserva la selección explícita de resultados y permite abrir un borrador vigente. El bloque «Aprobación DOCUMENTAL propia del informe» muestra el SHA256 de los bytes JSON consultados, pide revisor declarado, fecha ISO válida y motivo, y exige otra confirmación. La identidad y competencia profesional no se autentican. Editar esos datos o el contexto del formulario consume la confirmación; cambiar versión, caso o huella de expediente limpia la selección aprobable. No se ofrece aprobar una hija ya aprobada.

Tras aprobar se comprueba el vínculo de padre y SHA y que resultados/normativa sigan pendientes. El historial se actualiza, distingue `borrador` de `aprobado DOCUMENTAL`, abre la nueva hija y dirige las descargas JSON/PDF a su UUID. El padre permanece conservado. Los endpoints existentes `GET /api/informes`, `GET /api/informe` y `GET /api/informe/archivo` conservan sus parámetros `caso`, `expediente_sha256`, `resultado` en el historial y `version`/`formato` según operación.

«Comprobar historial» revalida sin aprobar ni crear. Una versión sin vigencia no se abre como preferida ni conserva SHA, descarga o permiso de aprobación. Un fallo actual al consultar, aprobar o descargar invalida esos controles; respuestas y errores obsoletos por caso/versión/huella se descartan. La aprobación puede haberse publicado aunque una respuesta llegue tarde: se recupera consultando el historial, nunca aprobando automáticamente. No se añade garantía de idempotencia al núcleo: varias acciones deliberadas pueden generar hijas independientes.

## Pruebas focales

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_revision_aprobacion_informe tests.test_revision_entregables -v
```

Se comprueban confirmación/hash/campos, aprobación propia sin herencia, preservación del padre, listados y descargas, fuente alterada, padre alterado, contenido distinto aunque tenga nueva aprobación válida, ciclos/cadenas y cambio del padre durante exportación sin publicar ni dejar staging. Las pruebas existentes de entregables cubren regresión de borradores y evidencia seleccionada.

En sandbox Windows los temporales del sistema pueden impedir el renombrado atómico (`WinError 5`). En ese caso usar una carpeta temporal autorizada del workspace, sin sustituir la publicación atómica ni relajar pruebas. El bloqueo ambiental no es un resultado aprobado.

Verificación focal HTTP/UI de la integración, con `TEMP` y `TMP` establecidos en `workspace/tmp`:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_revision_aprobacion_informe_http tests.test_revision_entregables_http -v
& 'C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests/revision_aprobacion_informe_frontend.cjs
& 'C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests/revision_informes_frontend.cjs
```

**Resultado: 7 Python OK (9.772 s), 13/13 Node de aprobación y regresión Node de consultas/descargas OK.** Una pasada Python; Node se repitió después de corregir el doble HTTP para serializar el cuerpo recibido entre contextos VM, sin cambiar producto por ese fallo del doble. Se comprueban hija/descargas/padre intacto, falta de confirmación, SHA y datos alterados, origen/sesión, fuentes y padre alterados, confirmación consumida al editar, fechas imposibles, no reaprobar, relistado inválido y carreras por caso/versión/huella. HTTP se ejecuta en memoria y los datos son sintéticos portables; no se usó red, proveedor, ETABS, CU ni suite completa.
