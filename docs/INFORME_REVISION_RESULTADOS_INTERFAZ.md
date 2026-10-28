# Uso optativo de la revisión declarada en informes

Esta entrega modifica solo `revision_web/informes.js`, añade su prueba Node y esta guía. No monta HTML, rutas ni servicios y no modifica núcleo, resultados normalizados, `index.html` o `app.js`. Consume el evento `d2m-result-review` del componente de revisión de resultados ya verificado.

## Fragmento opcional para el integrador

Insertar dentro del formulario `informeForm`, antes de «Crear nueva versión de borrador». No usar atributo `checked` ni rellenar una selección a partir del historial.

```html
<fieldset><legend>Revisión de resultados DECLARADA · uso optativo</legend>
 <p>Selecciona manualmente una revisión vigente en su panel y el mismo análisis explícito en este formulario. Recibir esa selección no la incorpora al informe ni constituye revisión profesional autenticada.</p>
 <label class="confirmation">
  <input id="informeUsarRevisionResultados" type="checkbox" disabled>
  Usar esta revisión DECLARADA y su SHA exacto en el próximo borrador, con el mismo resultado, huellas y análisis seleccionados.
 </label>
 <p id="informeRevisionResultadosInfo" role="status" aria-live="polite">Sin revisión incorporada: resultados pendientes en un nuevo informe.</p>
 <details><summary>Revisión candidata, SHA y análisis</summary><pre id="informeRevisionResultadosDatos"></pre></details>
 <p>No autentica identidad o competencia, no certifica seguridad o normativa y no aprueba automáticamente el informe. La evidencia de análisis y el paquete normalizado conservan sus estados nativos.</p>
</fieldset>
```

Estos tres nodos son opcionales. Si aún no están montados, `informes.js` no lanza `TypeError` y conserva el cuerpo y recorrido anteriores. No se requiere otro script, listener del host ni ruta nueva: el archivo escucha el evento y registra el control si existe al cargarlo. Montar el fragmento antes de cargar `informes.js`; si se añade después, recargar el panel completo para enlazar su control.

## Selección y contrato de creación

El evento trae la proyección pública completa de una revisión vigente consultada, con `id`, `sha256_revision`, caso, resultado, análisis, expediente y huellas de resultado/evidencia. Se contrasta con el resultado abierto, las fuentes declaradas en esa proyección y el análisis elegido **manualmente** en `informeAnalisis`, que debe figurar vigente en su listado. Un evento ajeno, sin SHA, con otra huella, sin vigencia o con otro análisis no sirve como respaldo. No se selecciona un análisis por omisión y no se busca una revisión alternativa.

La casilla empieza desmarcada, incluso después de recibir una revisión. Solo al marcarla se añade al cuerpo existente de `POST /api/informe/crear`:

```json
{
  "revision_resultados": {
    "id": "UUID32_DE_REVISION_SELECCIONADA",
    "sha256_revision": "SHA256_EXACTO_DE_SU_CONSULTA"
  }
}
```

Los valores del ejemplo representan el UUID32 y SHA64 reales, no texto literal que deba enviarse. El cuerpo conserva `analisis` como UUID explícito exactamente coincidente. No contiene la declaración, controles ni texto de la revisión. Si no se activa la casilla o no está montada, se **omite** `revision_resultados`: nunca se manda null, false o un objeto vacío. Los campos opcionales de contexto/explicación mantienen su propio uso explícito y `contexto.sitio` sigue null.

Tras crear se exige que el servidor devuelva la misma referencia en `revision_resultados_seleccionada:{id,sha256_revision}`, el mismo análisis y un estado coherente. No se abre como comprobado un informe que perdió, agregó sin pedir o cambió esa referencia. El servicio es responsable de revalidarla desde sus fuentes, no de confiar en el evento del navegador.

## Estado del informe abierto y aprobación documental

La casilla y el evento solo preparan el próximo cuerpo: **no cambian el estado del informe abierto**. Al consultar un informe:

- Sin referencia propia, se conserva `revision_resultados:'pendiente'`.
- Solo se acepta `revision_resultados:'revisados_declarados'` junto a una referencia propia de forma exacta UUID/SHA, mismo caso, resultado/huella, expediente y análisis, y evidencia de análisis con su revisión nativa todavía pendiente.
- Se muestran la referencia conservada y el texto «resultados con revisión DECLARADA propia · identidad profesional no autenticada». No se afirma verificación profesional, resultados aprobados, seguridad o conformidad normativa.

La aprobación documental continúa como otra operación explícita sobre el SHA del informe. La hija debe conservar la referencia ID/SHA exacta y el análisis del padre, además del vínculo documental normal. Un padre pendiente produce hija pendiente; un padre con revisión declarada válida puede producir hija `revisados_declarados`. Ningún checkbox/evento permite elevar una hija pendiente ni sustituir una revisión del padre. La aprobación sigue exclusivamente documental; `aprueba_resultados:false` y `conformidad_normativa:'no_evaluada'` permanecen.

## Invalidación y concurrencia

Un nuevo caso/resultado/huella limpia toda selección. Cambiar realmente la revisión, su SHA o vigencia, el análisis explícito, contexto o explicación desmarca el uso de revisión y consume la confirmación documental. Un evento idéntico conserva las selecciones expresas. Las respuestas y errores de consultas, creación, descargas o aprobación iniciadas con un contexto anterior se descartan mediante los guards existentes; no se reintenta ninguna mutación.

La declaración seleccionada para un próximo borrador queda separada de las referencias del informe almacenado. Cambiar esa candidata no reescribe un informe previo; para aprobarlo se vuelven a comprobar su propia referencia, SHA y fuentes en el servicio. No se modifican los eventos de contexto/explicación ni se incorporan referencias nuevas automáticamente.

## Verificación focal

```powershell
$pruebas=@(
 'tests/revision_informe_revision_resultados_frontend.cjs',
 'tests/revision_informe_contexto_frontend.cjs',
 'tests/revision_aprobacion_informe_frontend.cjs',
 'tests/revision_informes_frontend.cjs'
)
foreach ($prueba in $pruebas) {
 & 'C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' $prueba
 if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
```

**Pasada focal:** nuevos **21/21 OK**, contexto **15/15 OK**, aprobación documental **13/13 OK** y regresión existente de informes OK (cuatro combinaciones de caso/versión y éxito/error). Tras detectar un caso adicional de `null` repetido sin revisión previa, se añadió su regresión y se repitió solo el archivo nuevo: **22/22 OK**; evita descartar falsamente una creación compatible en vuelo. Los módulos reales se ejecutan con DOM/HTTP/eventos simulados; también se prueba ausencia completa de los tres nodos nuevos, cuerpo compatible sin campo nuevo, rechazo de estado revisado sin referencia, hija que cambia SHA, análisis explícito y carreras. No se modificaron pruebas anteriores para hacerlas pasar. Sin HTTP real, red, proveedor, motor, CU ni suite completa.
