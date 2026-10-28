# Conversión web de lecturas revisadas a geometría borrador

La pantalla local incluye **De lecturas revisadas a geometría borrador**. Permite seleccionar una extracción comprobada, consultar sus candidatos revisados, declarar un manifiesto físico completo, crear otra conversión y consultar su historial. Importar la geometría al historial geométrico es una acción posterior con huella exacta y confirmación booleana explícita. No registra aprobaciones ni habilita modelado automáticamente.

El núcleo se reutiliza sin cambios: `conversion_geometria.convertir_lecturas`, `gestion_extraccion.cargar_version`/`validar_version`, `extraccion_preliminar.exportar_revisados` y `gestion_geometria.importar_geometria`/`consultar_version`. No se infieren coordenadas, ejes, conectividad, escala, espesores ni unidades a partir de imágenes. No se contactan proveedores, ETABS ni otros procesos.

## Operación en pantalla

1. Abrir el expediente y revisar las lecturas mediante el flujo existente. Seleccionar explícitamente la versión de extracción en la sección de conversión.
2. Consultar los candidatos revisados mostrados y declarar el JSON completo de `draft2model.conversion_geometria` v0.1.0 conforme a `CONVERSION_GEOMETRIA.md`. El editor comienza vacío; no se insertan valores físicos de ejemplo. Cada medida requiere candidato revisado o declaración justificada con referencias revisadas. Desconocidos, pendientes y rechazados no se convierten en longitudes conocidas.
3. **Crear conversión comprobada sin importar geometría** publica archivos nuevos. Muestra geometría, correspondencias, procedencia sintética cuando corresponda y huella de la conversión. El historial permite abrir versiones anteriores.
4. Contrastar el resultado y marcar la declaración explícita antes de **Importar geometría borrador al historial**. Cambiar el manifiesto, la extracción o la conversión elimina la confirmación. Un manifiesto editado debe convertirse de nuevo antes de importar.
5. La importación emite `d2m-geometry-created` y la aplicación vuelve a consultar el historial geométrico. Abre la nueva geometría en borrador, con la casilla de aprobación desmarcada. La revisión y aprobación geométricas posteriores siguen siendo independientes.

## Contratos HTTP / Python

Todos los cuerpos tienen campos exactos. Análisis, proveedor, rutas locales y aprobaciones no forman parte de estos contratos. Los identificadores de extracción/conversión son UUID32 hexadecimales minúsculos; el caso debe ser un expediente registrado y la huella SHA256 debe coincidir con el manifiesto vigente.

| HTTP | Método de `ServicioConversion(app)` | Entrada |
| --- | --- | --- |
| `POST /api/conversion/crear` | `crear(body)` | `{caso, extraccion, expediente_sha256, manifiesto_json}` |
| `GET /api/conversiones` | `listar(caso, *, expediente_sha256)` | query caso/expediente_sha256 |
| `GET /api/conversion` | `consultar(caso, version, *, expediente_sha256)` | query caso/version/expediente_sha256 |
| `POST /api/conversion/importar-geometria` | `importar_geometria(body)` | `{caso, version, expediente_sha256, huella_conversion, confirmacion_explicita:true}` |

POST correcto devuelve 201; GET correcto 200. Sesión/origen ajenos reciben 403. Solicitud o fuentes inválidas reciben 409 con mensajes sanitizados del controlador. Se aplica el límite HTTP existente de 2 MiB; `manifiesto_json` admite hasta 1500 KiB UTF-8 y usa JSON estricto sin claves repetidas ni valores no finitos.

Crear y consultar devuelven:

```text
{id, caso, extraccion, expediente_sha256, huella_conversion, sha256_geometria,
 manifiesto, geometria, trazabilidad,
 vigente:true, estado:'borrador', aprobacion:null,
 disponible_para_modelado:false, aviso}
```

`trazabilidad` proyecta exclusivamente IDs de extracción/exportación, naturaleza sintética, operador e identidad declarada no verificada, alcance, ejes, escala, correspondencias y `aprobacion_ingenieria:null`. No publica rutas privadas ni los registros internos de originales. `manifiesto` conserva las declaraciones recibidas y `geometria` es el contrato borrador completo. Los textos declarados por el operador no se consideran identidad autenticada ni revisión profesional.

Listar devuelve `{caso, expediente_sha256, versiones:[{id, extraccion, vigente:true, estado:'borrador'}]}`. Una conversión web alterada aparece como `{id, vigente:false, problemas:['conversion_no_vigente']}`. El historial web incluye las conversiones con registro `web.json`; los artefactos CLI previos mantienen su recorrido CLI y no se elevan automáticamente a versiones web comprobadas.

Importar devuelve `{caso, conversion, geometria, expediente_sha256, estado:'borrador', aprobacion:null, disponible_para_modelado:false}`. El evento `d2m-geometry-created` transporta ese resultado. La aplicación comprueba caso/huella/estado antes de refrescar y descarta respuestas tardías de otro contexto.

## Persistencia e integridad

El núcleo publica cuatro archivos nuevos en `conversiones_geometria/<UUID>`: `manifiesto.json`, `geometria.json`, `trazabilidad.json` y `exportacion.json`. El manifiesto conserva los bytes exactos recibidos. El servicio añade `web.json`, con caso, extracción, huella de expediente, hashes de la extracción/version fuente y hashes de los cuatro artefactos. `huella_conversion` es SHA256 del registro web canónico; importar exige esa huella seleccionada.

Consultar/importar vuelven a comprobar originales y extracción mediante APIs públicas; reconstruyen la exportación revisada con la función pública pura y la contrastan con el snapshot. Comprueban la exportación conservada por su UUID/hash, trazabilidad, geometría, estado borrador, procedencia, unidades y huellas. Releen fuentes y bytes exactos al terminar. Rechazan enlaces, rutas ajenas, tipos malformados, identificadores inválidos y mezcla de casos. No reejecutan la conversión durante una consulta.

Las escrituras se serializan con `app.lock`; importar comparte además un bloqueo de sistema `conversion_web.lock` dentro del caso. Antes de importar se conserva `importacion_pendiente.json`; después de comprobar la nueva versión geométrica y revalidar la conversión se escribe `importacion_web.json`. Repetir una importación aceptada devuelve el mismo ID geométrico, comprobándolo de nuevo, sin crear otra versión. Si hubo interrupción sin recibo, los reintentos quedan rechazados para evitar duplicar automáticamente un borrador; se conserva el marcador para revisión externa. No hay operación automática de recuperación o aprobación.

Los hashes son controles de coherencia local, no una firma externa frente a la reescritura deliberada de todos los archivos y registros. Una creación interrumpida puede conservar una exportación o conversión nativa sin registro web; no se presenta como conversión web válida. Crear de nuevo es una nueva versión deliberada; no se declara idempotencia de esa acción.

## Verificación focal

```powershell
$env:TEMP = Join-Path (Get-Location) 'tmp'
$env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m unittest tests.test_revision_conversion tests.test_conversion_geometria -v
& 'C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests/revision_conversion_frontend.cjs
```

Las pruebas usan documentos, lecturas y declaraciones exclusivamente sintéticos. Cubren recorrido de servicio y HTTP, conservación exacta, historial, importación borrador/replay, rechazo de fuente/artefactos/huella/confirmación/caso/IDs alterados, interrupción y no repetición, selección explícita, edición sin importar, bus de refresco geométrico y descartes de éxito/error por caso/versión. No acreditan ingeniería, uso de proveedor/ETABS ni inspección de navegador real.

Pasada focal final del 18 de octubre de 2026: **17 pruebas Python OK en 14.946 s** (7 servicio/HTTP nuevas y 10 del núcleo existente), sin omisiones; **10/10 comprobaciones Node correctas**. No se ejecutó la suite completa.
