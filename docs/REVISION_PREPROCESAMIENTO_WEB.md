# Preprocesamiento registrado integrado con recortes y paquetes visuales

Backend local implementado el 18 de octubre de 2026 y extendido con servicio web y controles de fotografía montados en la revisión local. Las rutas HTTP las integra el coordinador; esta entrega verificó el servicio Python y los controles/eventos JavaScript sin navegador, red, llamadas al proveedor, OCR ni ETABS. No se acepta un PNG corregido como si fuera un original nuevo.

## API de servicio

Módulo `draft2model.revision_preprocesamiento`:

```python
from draft2model.revision_preprocesamiento import (
    informacion_original, registrar_preprocesamiento,
    consultar_preprocesamiento, historial_preprocesamientos,
)

info = informacion_original(expediente, "L0001")
registro = registrar_preprocesamiento(
    expediente, "L0001", config,
    revisor_declarado="Nombre declarado", motivo="Rectificación y contraste elegidos explícitamente",
)
version_id = registro.parent.name
consulta = consultar_preprocesamiento(expediente, version_id)
historial = historial_preprocesamientos(expediente, archivo_id="L0001")
```

- `expediente`: ruta al `expediente.json` registrado; `archivo_id`: identidad del original PNG/JPEG, página 1.
- `config`: exactamente el objeto del [core de preprocesamiento](PREPROCESAMIENTO.md), con `rotacion_grados`, `contraste` y `perspectiva`; las esquinas se expresan sobre **píxeles del original almacenado, sin aplicar EXIF**. Máximo 64 KiB serializados.
- `registrar_preprocesamiento` devuelve la ruta de `registro.json`. Cada publicación conserva una versión nueva; no sobrescribe las anteriores. Revisor y motivo no vacíos son obligatorios; la identidad es declarada y no autenticada.
- `consultar_preprocesamiento` devuelve `{id, ruta, registro, config, transformacion, imagen_bytes}`. `ruta` es `Path` e `imagen_bytes` son bytes PNG para uso interno: no serializarlos directamente como JSON. Para HTTP, devolver solo `id/registro/config/transformacion` y servir la imagen después de esta consulta verificadora.
- `historial_preprocesamientos` devuelve una lista ordenada de `{id,registro,config,transformacion}`, serializable como JSON. Verifica todas las versiones; no oculta una corrupta. El filtro de archivo se aplica sobre versiones comprobadas.
- `informacion_original` devuelve identidad y hashes del original/expediente, alcance y `exif_original`, incluidas dimensiones almacenadas/orientadas y matrices afines. Permite configurar el selector gráfico sin adivinar dimensiones ni orientación.

`ValueError` indica configuración, evidencia, identidad, vínculo, tipo o transformación inválidos; los errores de lectura/escritura pueden ser `OSError`. El lector JSON compartido también puede informar `ErrorGestion` ante JSON ilegible, duplicado o no finito. Ningún resultado rechazado debe mostrarse como una publicación o consulta aceptada.

## Publicación, identidad e integridad

```text
<caso>/preprocesamientos/<SHA256_de_registro.json>/
  imagen.png
  config.json
  transformacion.json
  registro.json
```

El ID es **64 caracteres hexadecimales**, SHA256 de los bytes exactos de `registro.json`; no es UUID. Las rutas HTTP o selectores deben aceptar ese ID como cadena opaca y conservarlo al elegir la versión. Los recortes siguen usando sus propios UUIDs habituales.

El registro cita caso, archivo original, página, hashes del original y expediente, alcance exacto, revisor/motivo/fecha, hashes de los tres artefactos y metadatos EXIF originales. `transformacion.json` conserva el registro completo del core: homografías original→derivado y derivado→original, dimensiones, orden de operaciones y versión de Pillow. `escala_metrica` permanece null y `mejora_precision_vision` permanece `no_evaluada`.

La consulta comprueba el ID de contenido antes de usar el registro, valida expediente/original vigente, vuelve a renderizar mediante el core desde el original, exige igualdad exacta de PNG/configuración/registro de transformaciones y sus hashes, y recomprueba fuentes y archivos al terminar. Reescribir configuración, PNG, matrices y hashes de forma coherente **no** valida el ID ya publicado: cambia el hash del registro y se rechaza. Rehacer únicamente hashes no acredita que el PNG proceda del render reproducible.

Las rutas, directorios y archivos deben ser de tipo esperado y no resolver mediante symlinks/junctions/reparse points, ni salir de su caso. Los límites del core siguen aplicándose: PNG/JPEG estático, hasta 100 MB y 20 millones de píxeles, lado máximo 16000, perspectiva convexa explícita y numéricamente estable. No se instalan dependencias ni se envían archivos.

La publicación utiliza carpeta temporal y rename del almacenamiento local existente. Recomprueba antes y después de publicar. Si una fuente cambia después del rename, la operación falla y puede quedar una carpeta invalidada para inspección; su consulta vuelve a rechazarla. No se presenta esa carpeta como resultado aceptado. Un fallo de disco en el core ocurre dentro del temporal del servicio y no sustituye versiones previas.

## Orientación EXIF y perspectiva: una sola composición

Hay tres espacios diferentes, todos en píxeles de bordes continuos:

1. **O:** original tal como está almacenado, antes de EXIF. El core recibe las esquinas en este espacio y nunca aplica orientación automática.
2. **D:** derivado después de perspectiva → rotación horaria explícita → contraste. La rotación explícita es decisión del operador; no se suma automáticamente la rotación EXIF. El PNG generado elimina EXIF para que navegador/lector no vuelva a orientar sus píxeles.
3. **V:** original EXIF orientado, espacio ya usado por el visor, los recortes raster existentes y las evidencias `pagina_visible_normalizada`.

Si el selector gráfico muestra el preview orientado V, debe convertir las esquinas mediante `exif_original.pagina_visible_a_original_px` antes de enviarlas como configuración O. También debe conservar su orden SI,SD,ID,II **en O**; una reflexión EXIF puede invertir el orden del polígono y requiere reordenar sus vértices en el selector. La API no corrige ni interpreta silenciosamente ese orden: el core rechaza cuadriláteros cruzados o con orientación incorrecta. Rotaciones admitidas siguen siendo 0/90/180/270; contraste `(0,5]`.

Sea D la matriz `origen_a_salida` del core, E la matriz EXIF de O→V y A la transformación de píxeles del recorte conservado→D, incluyendo floor/ceil del bbox y reducción LANCZOS. La homografía de evidencia es:

```text
p_recorte → V = E × inversa(D) × A × [x,y,1]
```

Se divide por la tercera coordenada homogénea. `preprocesamiento.transformar_punto` y el helper existente `recortes.punto_a_pagina` realizan ese cálculo; no hace falta implementar otro motor geométrico. También se conserva la inversa V→píxel de recorte. La reversibilidad de coordenadas no recupera píxeles perdidos por recorte/remuestreo/contraste ni prueba precisión métrica.

## Elegir una versión en recortes y paquetes

```python
from draft2model.recortes import generar_recorte
from draft2model.entrada_vision import preparar_paquete, cargar_paquete, adaptar_respuesta

recorte = generar_recorte(
    expediente, "L0001", 1, [0.1, 0.2, 0.8, 0.9],
    preprocesamiento_id=version_id,
)
solicitud = preparar_paquete(expediente, revision_documental, [recorte])
datos, sha256_solicitud, manifest, archivos = cargar_paquete(expediente, solicitud)
```

Al seleccionar un derivado, el bbox solicitado pertenece a **D completo**, normalizado entre 0 y 1. Omitir `preprocesamiento_id` conserva el comportamiento PDF/raster anterior. Los derivados solo se admiten para originales raster, página 1. El recorte no vuelve a aplicar EXIF al PNG derivado.

Nuevos campos del recorte derivado:

| Campo | Significado |
| --- | --- |
| `tipo_fuente` | `raster_preprocesado`. |
| `preprocesamiento_id`, `preprocesamiento_registro_sha256` | ID y ancla exacta del registro publicado. |
| `preprocesamiento_archivo_id`, `preprocesamiento_imagen_sha256` | Identidad original del servicio y hash del PNG derivado completo. |
| `bbox_derivado_normalizada`, `bbox_derivado_px` | Selección solicitada y límites enteros reales en D. |
| `dimensiones_derivado_px` | Dimensiones de D después de rotar. |
| `pixel_a_derivado_px` | Afín `[a,b,c,d,e,f]` desde el PNG de recorte real a D. |
| `tipo_transformacion` | `homografia_3x3`. |
| `pixel_a_pagina_visible` | **Matriz 3×3** E×inversa(D)×A hacia V; no la afín de seis valores del recorrido anterior. |
| `pagina_visible_a_pixel` | Inversa 3×3 de la anterior. |
| `poligono_pagina_visible_px` | Cuatro esquinas del PNG conservado mapeadas a V. |
| `pagina_visible_px` | Dimensiones del ORIGINAL EXIF orientado V, nunca las del derivado. |
| `bbox_normalizada` | Envolvente rectangular de las cuatro esquinas mapeadas a V, normalizada por las dimensiones originales orientadas. |

El campo `sistema_coordenadas` continúa siendo `pagina_visible_normalizada` del original; `espacio_pagina_visible` continúa siendo `raster_px_exif_orientado`. Las matrices afines de EXIF originales también se conservan. No hay puntos PDF en registros derivados raster. El helper `punto_a_pagina` bifurca por `tipo_fuente` y conserva las afines PDF/raster anteriores sin reinterpretarlas.

Los paquetes siguen incluyendo un contexto documental del original, y pueden mezclar recortes originales y derivados del mismo archivo conservando un solo contexto. Cada imagen REC derivada lleva su ID/hashes de preprocesamiento, espacio original y homografía. La solicitud incorpora como fuentes los cuatro artefactos del derivado; preparar/cargar verifican la cadena, vuelven a renderizar, y comprueban al terminar las huellas de todas las fuentes y copias.

La adaptación de respuestas transforma **las cuatro esquinas** de cada bbox de evidencia y conserva su envolvente rectangular en V. Esto cubre perspectivas y reflexiones; no usa solamente dos esquinas ni interpola el bbox solicitado. El contrato de extracción continúa citando `archivo_id`, `original_sha256`, `recorte_id` e `imagen_sha256` del recorte. Las lecturas permanecen pendientes y no se cambian datos desconocidos ni unidades. El polígono exacto se conserva en el registro de recorte; el contrato de evidencia existente representa su envolvente, que puede contener una zona adicional del original. Solo se toleran residuos numéricos menores de 1e-9 en el borde `[0,1]`; regiones que salen efectivamente del original se rechazan.

## Verificación y límites

Una primera pasada focal de seis suites dio **66 pruebas OK en 33.418 s**, sin omisiones. Cubre las dos suites nuevas, core de preprocesamiento, recortes raster, recortes PDF y entrada visual existentes. Se añadieron después regresiones de modificación del derivado durante rasterización/publicación y se repitieron exclusivamente las dos suites nuevas: **15 pruebas OK en 17.948 s**, salida 0. Las pruebas son patrones sintéticos; no evalúan mejora de precisión de un proveedor ni legibilidad de planos reales.

```powershell
.\.venv\Scripts\python.exe -c "import pathlib,tempfile,unittest; p=pathlib.Path('tmp/pruebas_preprocesados'); p.mkdir(parents=True,exist_ok=True); tempfile.tempdir=str(p.resolve()); suites=['tests.test_revision_preprocesamiento','tests.test_recortes_preprocesados','tests.test_preprocesamiento','tests.test_recortes_raster','tests.test_recortes','tests.test_entrada_vision']; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromNames(suites)); raise SystemExit(not r.wasSuccessful())"
```

No existe firma externa ni autenticación del operador: un actor que reconstruya y reemplace toda la cadena con IDs nuevos puede fabricar otra historia. El ID de contenido sí impide aceptar una versión publicada cuyo contenido cambió, incluso si el render es coherente. No hay bloqueo contra un proceso hostil que modifique/restaure archivos entre comprobaciones; se realizan controles antes/después, sin afirmar protección transaccional del sistema operativo.

El servicio reproduce imágenes para verificar integridad y puede costar tiempo proporcional al número y tamaño de versiones; no usar el historial completo como polling rápido del visor. Un cambio de Pillow o de su render puede invalidar reproducción exacta: conservar el entorno reproducible. El historial no convierte imágenes ni medidas a metros, no cambia evidencia original y no confiere aprobación técnica.

## Servicio web y controles montados

`ServicioPreparacion` en `revision_preparacion.py` añade los métodos siguientes. La huella abreviada como **fp** en este documento se envía siempre con el nombre existente **`expediente_sha256`**; no se admite un campo alternativo `fp` ni campos extra.

| Ruta prevista/montada por el coordinador | Método de servicio | Entrada exacta |
| --- | --- | --- |
| `POST /api/visual/preprocesar` | `preprocesar(body)` | `{caso, expediente_sha256, archivo, config, revisor_declarado, motivo}`. |
| `GET /api/visual/original-raster` | `original_raster(caso, archivo, *, expediente_sha256)` | Query caso, archivo y expediente_sha256. |
| `GET /api/visual/preprocesamiento` | `preprocesamiento(caso, version, *, expediente_sha256)` | Query caso, version (64 hex) y expediente_sha256. |
| `GET /api/visual/preprocesado-imagen` | `imagen_preprocesada(caso, version, *, expediente_sha256)` | Igual; devuelve bytes PNG verificados, tipo HTTP `image/png`. |
| `GET /api/visual/preprocesamientos` | `preprocesamientos(caso, archivo, *, expediente_sha256)` | Query caso, archivo y expediente_sha256. Devuelve `{caso,archivo_id,expediente_sha256,versiones:[...]}`. |
| `POST /api/visual/recortar` | `recortar(body)` | Campos anteriores del recorte `{caso,expediente_sha256,archivo,pagina,bbox,dpi,etiqueta}` y opcionalmente **`preprocesamiento`** (64 hex). |

Las proyecciones de versión contienen `{id,caso,archivo_id,expediente_sha256,registro,config,transformacion,estado,aprueba_ingenieria,escala_metrica,mejora_precision_vision}`. No contienen `Path`, bytes de imagen, carpetas privadas ni `transformacion.original` (que en el registro interno identifica la ruta original). Se conservan hashes, dimensiones y matrices. La consulta vuelve a verificar la evidencia después de obtener los bytes; la imagen no se sirve desde una ruta arbitraria del cliente.

El selector de derivados del recorte es opcional para mantener los recorridos PDF/raster anteriores. Si se elige, el bbox recibido pertenece a D, mientras `bbox_normalizada` de respuesta sigue perteneciendo al original V; también se devuelven `bbox_derivado_normalizada`, ID de derivado, dimensiones y matrices para que la interfaz pueda explicarlo. Consultar la imagen o metadatos de un recorte derivado reproduce ahora su cadena, en vez de acreditar únicamente el hash PNG. Cambiar su homografía o intentar ocultar sus marcadores como si fuera un recorte original se rechaza. Los recortes originales conservan su revisión geométrica al preparar paquetes según el contrato previo.

Los nuevos métodos utilizan el mismo bloqueo local y las comprobaciones de vigencia de `ServicioPreparacion`: caso y todos sus originales deben seguir correspondiendo a la huella seleccionada. El handler HTTP debe conservar el token/same-origin, límites de carga, traducción de errores y cabeceras privadas ya usados por los endpoints visuales. No hay transmisión externa en estas rutas.

### Interfaz y eventos

`revision_web/preprocesamiento.js` está cargado con `defer` después de `preparacion.js`. La sección `fotoPanel` y `window.preprocessControls?.()` están montadas en `index.html` y `app.js`; no se modificó el contenido de contexto ni explicaciones. El panel ofrece selección de archivo raster, consulta de original/EXIF, formulario de perspectiva/rotación/contraste explícitos, revisor/motivo, historial de versiones, preview verificado y recorte normalizado del derivado. Las esquinas se introducen manualmente en O; no es un editor gráfico que transforme silenciosamente selecciones del visor.

El módulo utiliza `api()` y `action()` existentes. Los campos se deshabilitan durante acciones, y antes de cualquier recorte exige una versión consultada y una imagen comprobada. Consultar original o historial nunca publica. Se descartan respuestas o errores tardíos cuando cambian caso, huella, archivo o versión; se revocan object URLs al cerrar/cambiar selección. No inserta metadatos con `innerHTML`.

Tras conservar un recorte derivado emite:

```javascript
new CustomEvent('d2m-visual-crop', {detail: {
  caso, expediente_sha256,
  recorte: {id, caso, expediente_sha256, preprocesamiento_id /* y proyección del servicio */}
}})
```

El listener mínimo añadido a `preparacion.js` valida caso, huella y UUID de recorte, actualiza el listado existente y **añade** ese recorte a la selección, conservando revisión documental y selecciones anteriores. No crea un paquete ni inicia un envío. El usuario sigue pulsando el botón existente para preparar el paquete local y los controles del proveedor continúan separados.

### Pruebas de esta integración web

- Python focal: **9 pruebas OK en 8.602 s**, cuatro nuevas de servicio de derivados y cinco de preparación compatible. Después se endureció el rechazo de degradar el tipo derivado a original y se repitió su regresión específica: **1 OK en 1.544 s**.
- Node: **11/11** nuevas, incluyendo IDs HTML únicos, carga defer, formularios exactos, bbox no válido, contexto EXIF sin doble rotación, respuestas tardías, revocación de blobs e integración de selecciones con preparación.
- Node de preparación existente: **13/13**, conservando selección, vigencia y manejo de respuestas obsoletas.
- Se corrigió un error ASCII en un literal bytes del archivo de prueba antes de ejecutar la pasada Python correcta. No se ejecutó la suite completa, navegador/CU, proveedor, red o ETABS. Las pruebas HTTP de los handlers montados pertenecen al coordinador.

```powershell
.\.venv\Scripts\python.exe -c "import pathlib,tempfile,unittest; p=pathlib.Path('tmp/pruebas_web_derivados'); p.mkdir(parents=True,exist_ok=True); tempfile.tempdir=str(p.resolve()); r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromNames(['tests.test_revision_preparacion_derivados','tests.test_revision_preparacion'])); raise SystemExit(not r.wasSuccessful())"
node tests/revision_preprocesamiento_frontend.cjs
node tests/revision_preparacion_frontend.cjs
```

### Fragmento HTML de montaje

El bloque completo está instalado en `revision_web/index.html`, entre la preparación visual y el panel de proveedor. Para moverlo a otra presentación hay que conservar todos sus IDs y el enlace de controles/eventos; no duplicar el bloque. La carga requerida es:

```html
<script src="/preparacion.js"></script>
<script src="/preprocesamiento.js" defer></script>
```

Fragmento concreto instalado (formularios manuales, sin contenido del contexto ni de explicaciones):

```html
 <section id="fotoPanel" class="geometry" aria-label="Preparación explícita de fotografías">
  <h2>Preparar una fotografía registrada</h2>
  <p>Conserva el original y crea un derivado con perspectiva, rotación y contraste declarados. Esta preparación es local; no fija escala en metros ni acredita mejora de precisión.</p>
  <label for="fotoArchivo">Original PNG/JPEG</label><select id="fotoArchivo" disabled><option value="">Selecciona original raster</option></select>
  <button id="fotoConsultar" type="button" disabled>Consultar dimensiones, EXIF e historial</button>
  <details><summary>Identidad y coordenadas del original</summary><pre id="fotoOriginalInfo"></pre></details>
  <form id="fotoTransformarForm">
   <p class="hint">Las esquinas se expresan en píxeles del archivo almacenado, antes de EXIF: origen superior izquierdo, X derecha, Y abajo. El visor general puede estar orientado por EXIF; consulta las dimensiones y matrices anteriores. No se añade rotación automática.</p>
   <div class="two"><div><label for="fotoRotacion">Rotación horaria explícita</label><select id="fotoRotacion" required disabled><option value="0">0°</option><option value="90">90°</option><option value="180">180°</option><option value="270">270°</option></select></div><div><label for="fotoContraste">Factor de contraste (1 conserva)</label><input id="fotoContraste" type="number" min="0.000001" max="5" step="any" value="1" required disabled></div></div>
   <label><input id="fotoPerspectiva" type="checkbox" disabled>Rectificar cuatro esquinas explícitas</label>
   <fieldset id="fotoEsquinas" hidden><legend>Perspectiva sobre el original almacenado, antes de rotar</legend>
    <div class="two"><div><label for="fotoX0">Superior izquierda · X (px)</label><input id="fotoX0" type="number" min="0" step="any" disabled></div><div><label for="fotoY0">Superior izquierda · Y (px)</label><input id="fotoY0" type="number" min="0" step="any" disabled></div></div>
    <div class="two"><div><label for="fotoX1">Superior derecha · X (px)</label><input id="fotoX1" type="number" min="0" step="any" disabled></div><div><label for="fotoY1">Superior derecha · Y (px)</label><input id="fotoY1" type="number" min="0" step="any" disabled></div></div>
    <div class="two"><div><label for="fotoX2">Inferior derecha · X (px)</label><input id="fotoX2" type="number" min="0" step="any" disabled></div><div><label for="fotoY2">Inferior derecha · Y (px)</label><input id="fotoY2" type="number" min="0" step="any" disabled></div></div>
    <div class="two"><div><label for="fotoX3">Inferior izquierda · X (px)</label><input id="fotoX3" type="number" min="0" step="any" disabled></div><div><label for="fotoY3">Inferior izquierda · Y (px)</label><input id="fotoY3" type="number" min="0" step="any" disabled></div></div>
    <div class="two"><div><label for="fotoAncho">Ancho rectificado antes de rotar (px)</label><input id="fotoAncho" type="number" min="2" max="16000" step="1" disabled></div><div><label for="fotoAlto">Alto rectificado antes de rotar (px)</label><input id="fotoAlto" type="number" min="2" max="16000" step="1" disabled></div></div>
   </fieldset>
   <label for="fotoRevisor">Operador/revisor declarado</label><input id="fotoRevisor" required maxlength="150" disabled>
   <label for="fotoMotivo">Motivo de la transformación explícita</label><textarea id="fotoMotivo" rows="2" maxlength="2000" required disabled></textarea>
   <button id="fotoRegistrar" type="submit" disabled>Conservar nuevo derivado sin aprobación de ingeniería</button>
  </form>
  <label for="fotoVersion">Derivados verificados del original seleccionado</label><select id="fotoVersion" disabled><option value="">Sin selección</option></select>
  <button id="fotoCargar" type="button" disabled>Comprobar y mostrar derivado</button>
  <img id="fotoPreview" alt="Derivado raster verificado, con transformación explícita" hidden style="max-width:100%;max-height:500px;object-fit:contain">
  <details><summary>Configuración y matrices del derivado</summary><pre id="fotoDetalle"></pre></details>
  <form id="fotoRecorteForm">
   <p>La región siguiente se expresa sobre el derivado mostrado, normalizada de 0 a 1. La evidencia del paquete vuelve al original registrado mediante la transformación conservada.</p>
   <div class="two"><div><label for="fotoBX0">Izquierda (x0)</label><input id="fotoBX0" type="number" min="0" max="1" step="any" value="0" required disabled></div><div><label for="fotoBY0">Arriba (y0)</label><input id="fotoBY0" type="number" min="0" max="1" step="any" value="0" required disabled></div></div>
   <div class="two"><div><label for="fotoBX1">Derecha (x1)</label><input id="fotoBX1" type="number" min="0" max="1" step="any" value="1" required disabled></div><div><label for="fotoBY1">Abajo (y1)</label><input id="fotoBY1" type="number" min="0" max="1" step="any" value="1" required disabled></div></div>
   <label for="fotoEtiqueta">Etiqueta del recorte derivado</label><input id="fotoEtiqueta" value="Región de fotografía preparada" maxlength="150" required disabled>
   <button id="fotoRecortar" type="submit" disabled>Conservar recorte y añadirlo a selección del paquete</button>
  </form>
  <p id="fotoEstado" role="status">Selecciona un original raster para declarar una transformación.</p>
 </section>
```
