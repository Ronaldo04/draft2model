# Componente de revisión declarada de resultados

Entrega sin montaje automático: `draft2model/revision_web/revision_resultados.js`, pruebas Node y esta guía. No modifica HTTP, `index.html`, `app.js`, informes ni el servicio Python. No crea la carpeta `draft2model/web`: la ruta fue corregida por el integrador a `revision_web`.

## Exportación y dependencias

El archivo funciona como script clásico sin build y como CommonJS en Node:

```javascript
// Navegador: cargar /revision_resultados.js antes de este montaje.
const revisionResultados = D2MRevisionResultados.crearRevisionResultados({
  get: $,                    // id -> elemento existente
  api,                       // async (ruta, cuerpo?) -> Response; sesión/origen del host
  options,                   // (select, [[valor, texto], ...])
  getContext: () => docs,     // null o {caso, expediente_sha256}
  isBusy: () => busy,         // solo estado de controles; action gobierna exclusión global
  action,                    // async callback con exclusión/estado ocupado del host
  message,                   // (texto, esError)
  events: window,            // addEventListener/removeEventListener
  emit: (tipo, detalle) => window.dispatchEvent(new CustomEvent(tipo, {detail: detalle})),
});
window.resultReviewControls = revisionResultados.controles;
// Añadir window.resultReviewControls?.() al controls() del host.
// Registrar revision_resultados.js en WEB_ASSETS y agregar el script una sola vez.
```

Las dependencias obligatorias son `get`, `api`, `options`, `getContext` y `emit`. El componente no consulta nada hasta recibir un resultado válido y no lee globals `docs`, `busy` o funciones del host por su cuenta. Para desmontar: `revisionResultados.dispose()` elimina todos sus listeners, descarta respuestas en vuelo y emite null si había una selección publicada.

Opcionalmente se puede inyectar `cargarAnalisis(contextoResultado)`, que devuelve una promesa de `{versiones:[{id,vigente,...}]}`. Sin esa dependencia usa la consulta ya existente `GET /api/analisis?caso&resultado&expediente_sha256`, cuyo listado verifica el vínculo entre resultado y análisis. No toma la instancia activa ni el último trabajo, y no invoca un motor. El selector de análisis siempre empieza vacío.

Métodos públicos, todos independientes de una pantalla concreta: `actualizar()`, `consultarFuentes()`, `consultarRevision()`, `registrar()`, `seleccionarResultado(detail)`, `cambiarCaso()`, `controles()` y `dispose()`. Las operaciones async manejan sus errores vigentes mediante `message` y `rrEstado`; no reintentan mutaciones. Se recomienda montar una sola instancia por fragmento para evitar listeners duplicados.

## Fragmento HTML para montar

Insertar este bloque una sola vez junto al panel de resultados. No tiene controles marcados ni campos de declaración rellenados. Los dos JSON requieren entrada explícita, incluido `[]` cuando corresponda.

```html
<section class="geometry" aria-label="Revisión propia declarada de resultados">
 <h2>Revisión declarada del resultado y análisis seleccionados</h2>
 <p>No autentica identidad o competencia, no certifica completitud física ni seguridad y no aprueba informe o normativa. El software no decide qué omisión es crítica.</p>
 <p id="rrResultado">Abre un resultado normalizado vigente.</p>
 <p id="rrNativo">Estado nativo del resultado: pendiente.</p>
 <label for="rrAnalisis">Análisis explícito vinculado a este resultado</label>
 <select id="rrAnalisis" disabled><option value="">Selecciona análisis explícito</option></select>
 <button id="rrFuentes" type="button" disabled>Consultar y comprobar fuentes</button>
 <button id="rrActualizar" type="button" disabled>Revalidar historial sin registrar</button>
 <details><summary>Huellas, casos, unidades, advertencias, omisiones y filas null</summary><pre id="rrFuenteDatos"></pre></details>
 <fieldset><legend>Seis controles propios, declarados individualmente</legend>
  <label><input id="rrControl_unidades" type="checkbox" disabled>Declaro revisadas las unidades y sus correspondencias exactas.</label>
  <label><input id="rrControl_casos" type="checkbox" disabled>Declaro revisados los casos seleccionados y su análisis completo.</label>
  <label><input id="rrControl_filtros" type="checkbox" disabled>Declaro revisados filtros, selectores y correspondencias de tablas.</label>
  <label><input id="rrControl_omisiones" type="checkbox" disabled>Declaro revisadas todas las advertencias, omisiones y filas sin valor.</label>
  <label><input id="rrControl_consistencia_modelo" type="checkbox" disabled>Declaro contrastada la consistencia con el modelo y evidencia seleccionados.</label>
  <label><input id="rrControl_revision_tecnica" type="checkbox" disabled>Declaro realizada la revisión técnica con el alcance escrito, sin delegarla a IA.</label>
 </fieldset>
 <label for="rrRevisor">Revisor declarado</label><input id="rrRevisor" maxlength="150" disabled>
 <label for="rrFecha">Fecha de la revisión declarada</label><input id="rrFecha" type="date" disabled>
 <label for="rrAlcance">Alcance concreto de revisión</label><textarea id="rrAlcance" maxlength="4000" rows="3" disabled></textarea>
 <label for="rrMotivo">Motivo y revisión realizada</label><textarea id="rrMotivo" maxlength="4000" rows="3" disabled></textarea>
 <label for="rrObservaciones">Observaciones propias, lista JSON explícita</label><textarea id="rrObservaciones" rows="3" spellcheck="false" placeholder='["Observación del revisor"] o []' disabled></textarea>
 <label for="rrCriticos">Faltantes críticos declarados, lista JSON explícita</label><textarea id="rrCriticos" rows="3" spellcheck="false" placeholder='[] solo si declaras que no quedan faltantes críticos en tu alcance' disabled></textarea>
 <p>Un faltante crítico declarado bloquea el registro. Las observaciones nuevas no sustituyen las advertencias y omisiones de la fuente; una fila null conserva su motivo.</p>
 <label><input id="rrConfirmar" type="checkbox" disabled>Confirmo esta declaración, los seis controles y las huellas exactas del resultado y análisis mostrados. Mi identidad es declarada; no certifico seguridad ni conformidad normativa mediante este registro.</label>
 <button id="rrRegistrar" type="button" disabled>Registrar una revisión declarada nueva e inmutable</button>
 <label for="rrVersion">Revisión conservada para consultar, selección manual</label>
 <select id="rrVersion" disabled><option value="">Sin selección</option></select>
 <p id="rrEstado" role="status" aria-live="polite">Selecciona resultado y análisis explícitos.</p>
 <details><summary>Declaración consultada, SHA exacto y fuentes conservadas</summary><pre id="rrRevisionDatos"></pre></details>
</section>
```

## Eventos y comportamiento

El componente escucha los eventos reales `d2m-case` y `d2m-result`. Este último trae `{version,record}` del resultado normalizado verificado; se requieren caso/fp actuales, UUID, huella válida, vigencia y `aprueba_resultados:false`. No cambia el resultado nativo: siempre presenta su revisión nativa pendiente y mantiene separada la revisión propia seleccionada.

Después se elige análisis manualmente y se consultan sus fuentes. Los seis controles permanecen desmarcados; no se rellenan revisor, fecha, alcance, motivo o listas desde un registro previo. Se muestran íntegros los datos recibidos de fuentes, incluidas advertencias, omisiones, filas null, naturaleza sintética y evidencias. No se infieren variables aplicables o parámetros físicos.

Registrar exige controles True individuales, fecha real, campos completos, listas JSON explícitas, `faltantes_criticos:[]` y confirmación separada. El cuerpo usa las huellas de las fuentes abiertas, no las de una versión anterior ni un valor inferido. La confirmación se consume; después de registrar se vuelven a desmarcar los controles. El registro retornado **no se selecciona ni publica**: el operador debe elegirlo manualmente en historial y reconsultarlo.

Solo esa consulta vigente y concordante con resultado/análisis/fp/huellas e inventario de archivos emite:

```javascript
window.addEventListener('d2m-result-review', event => {
  const revision = event.detail; // proyección pública completa del backend, o null
  if (!revision) return;         // invalidar la selección del consumidor
  // Selección explícita: revision.id y revision.sha256_revision.
  // No convertir este evento en aprobación automática del informe o normativa.
});
```

La proyección conserva `revision_resultados:'revisados_declarados'`, `vigente:true`, `sha256_revision` y los avisos, con `aprueba_resultados:false`, `aprueba_informe:false`, `aprueba_ingenieria:false` y `conformidad_normativa:'no_evaluada'`. Emite null al invalidarse. Revalidar la misma revisión exacta no emite un falso null ni un cambio idéntico.

Cambiar caso, resultado/huella o análisis borra fuentes, declaración del formulario, controles, confirmación y revisión seleccionada, e invalida consultas en vuelo. Una versión distinta descarta consultas/error de la anterior. Cambiar un campo o control consume la confirmación; editar la declaración nueva no reescribe una revisión histórica. Cambiar bytes/huellas de fuentes o relistar una versión inválida limpia la selección publicada. Un fallo de registro no se reintenta: se indica consultar historial antes de otra declaración porque el servidor pudo haber publicado antes de perderse la respuesta.

## Rutas y contrato del host

| Operación | Ruta y parámetros |
|---|---|
| Fuentes | `GET /api/revision-resultados/fuentes?caso&resultado&analisis&expediente_sha256` |
| Historial | `GET /api/revision-resultados/historial?caso&resultado&expediente_sha256` |
| Versión | `GET /api/revision-resultados/version?caso&revision&expediente_sha256` |
| Registro | `POST /api/revision-resultados/registrar` |

GET usa los nombres de query indicados con sus valores codificados. POST tiene exactamente `{caso,resultado,analisis,expediente_sha256,huella_resultados,huella_evidencia,revisor_declarado,fecha,alcance,motivo,controles:{unidades,casos,filtros,omisiones,consistencia_modelo,revision_tecnica},faltantes_criticos,observaciones,confirmacion_explicita:true}`. Límites y respuestas son los de [REVISION_APROBACION_RESULTADOS.md](REVISION_APROBACION_RESULTADOS.md). `api` debe rechazar errores HTTP con mensajes públicos sanitizados y conservar sesión/origen/no-store; el componente nunca recibe credenciales, rutas locales o funciones de transporte.

La integración HTTP, el fragmento y el hook global de controles los monta el integrador. Esta entrega no altera el informe ni selecciona una revisión para él; los consumidores deben volver a validar caso, resultado, análisis y SHA según su propio contrato.

## Verificación focal

```powershell
& 'C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests/revision_aprobacion_resultados_frontend.cjs
```

**Una pasada: 21/21 OK.** Factory real en CommonJS y exportación browser en VM, DOM accesible por controles/labels del fragmento, eventos y HTTP simulados. Cubre controles False, listas explícitas, fuentes completas con null, confirmación, cuerpo exacto, selección manual/SHA, conservación del estado nativo, revalidación sin falso reset, fuente alterada, historial inválido, carreras por caso/resultado/huella/análisis/versión, exclusión de doble registro, error sin reintento y desmontaje. No se ejecutó suite completa, red, navegador, proveedor ni motor.
