# Auditoría del recorrido web integrado (solo lectura) — Claude

- **Ruta del proyecto:** `D:/RONALDO CUCHILLA/1. RONALDO CUCHILLA/2. INGENIERÍA CIVIL DOCS AND PROJECTS/AECODE CURSOS/AECODE AI TALENT/PROYECTO FINAL`
- **Encargo:** `seguimiento/ENCARGO_CLAUDE_AUDITORIA_WEB.md`.
- **Fecha:** 2026-10-17, hora local de cierre 23:51.
- **Único archivo escrito:** este documento. No modifiqué producto, pruebas ni seguimiento.
  - Las reproducciones se hicieron con scripts propios en el scratchpad de la sesión, fuera del proyecto, sobre copias temporales de la fixture sintética (`tests.fixture_etabs.extraer_evidencia`).
- **No ejecutado:**
  - ETABS real, proveedor, red, instalaciones y la suite completa.
  - Navegador real. La UI se ejercitó en `node:vm` con DOM simulado.
- **Alcance de las conclusiones:** este documento no declara un cierre global. Describe lo que se leyó y se reprodujo en el estado de los archivos indicado más abajo.

## 1. Resumen

| ID | Severidad | Tipo | Área | Efecto observable |
|---|---|---|---|---|
| H1 | Media | Defecto reproducido | Normalización (servidor y UI) | Una normalización interrumpida deja un resultado vigente sin recibo. Al recargar, la UI genera otra clave y publica un segundo resultado del mismo mapeo aprobado. |
| H2 | Baja–media | Defecto reproducido | Eventos de la UI (análisis → lecturas y mapeos) | Pulsar «Actualizar» en Análisis, o su sondeo de 4 s, borra la lectura preparada y confirmada y el mapeo abierto en otras secciones. |
| H3 | Baja | Defecto reproducido | Listado de paneles | `listar(resultado=A)` incluye paneles rotos de **otros** resultados como «sin vigencia». |
| H4 | Baja | Defecto reproducido | Selección de resultados (UI) | Tras un relistado que marca el resultado abierto como «requiere revisión», la tabla, la descarga y la selección de panel e informe siguen ligadas a él. |

**Ninguno produce aprobación falsa.** En todos los casos el servidor vuelve a verificar antes de crear un panel o un informe. Ninguna proyección pública devuelve `aprueba_resultados: true`.

## 2. Hallazgos reproducidos

### H1 — Normalización interrumpida: resultado huérfano vigente y duplicado al recargar (Media)

**Archivos y líneas**
- `draft2model/revision_mapeos.py:223-230`:
  - `normalizar` publica `normalizaciones_resultados/<clave>/solicitud.json` (l. 223) **antes** de `registrar_resultados` (l. 225).
  - Después llama a `_cargar` y a `verificar_evidencia` (l. 227).
  - Solo al final escribe `aceptacion.json` (l. 230).
- `draft2model/revision_web/mapeos.js:18` y `:24`:
  - `clearRecord()` pone `normalizationKey=null`.
  - `open()` llama a `clearRecord()`.
  - Por eso recargar o reabrir el mapeo genera una clave nueva en la l. 77 (`normalizationKey??=crypto.randomUUID()`).
- `draft2model/revision_visual.py:486`: el 409 genérico de POST dice textualmente «Recarga la versión antes de reintentar.».

**Disparador**
1. Cualquier excepción o corte del proceso después de que `registrar_resultados` publique el resultado y antes de escribir `aceptacion.json`. Por ejemplo, `verificar_evidencia` falla o el EDB se toca en esa ventana.
2. El usuario sigue el mensaje de la UI y recarga el mapeo.
3. Vuelve a normalizar.

**Efecto reproducido**

En `repro_normalizacion.py` se aplica un patch a `revision_mapeos.verificar_evidencia` con `OSError` una vez y se llama a `normalizar`. Resultado:

```
tras_interrupcion_resultados_nuevos ['4e5bb2a8…']
recibo_existe False
misma_clave_rechazada ValueError Archivo ausente o enlazado.
nueva_clave_resultado 5af1185c…
resultados_nuevos_total 2
REPRODUCIDO
```

- `ServicioResultados.listar_resultados` devuelve **los dos** resultados nuevos con `vigente: True` y `estado: paquete_verificado`. Son indistinguibles del que sí tiene recibo.
- Con la misma clave, el reintento queda bloqueado para siempre y solo muestra un mensaje genérico. La única salida que ofrece la UI, recargar, elude la protección contra repetición.
- La no repetición automática con la misma clave es deliberada y está cubierta por `test_normalizacion_interrumpida_no_se_repite_automaticamente`. Lo que falla es la combinación con la UI y la falta de marca del resultado huérfano.

**Prueba mínima propuesta** (en `tests/test_revision_mapeos.py`):
1. Aprobar un mapeo.
2. Aplicar un patch a `draft2model.revision_mapeos.verificar_evidencia` con `side_effect=OSError` y llamar a `normalize(approved)`.
3. Llamar a `normalize(approved, clave_solicitud='c'*32)`.
4. Esperar el rechazo con un código del tipo `normalizacion_pendiente`. Otra opción es que `listar_resultados` marque el resultado sin recibo como no vigente.

Hoy la prueba encuentra 2 resultados nuevos.

**Correcciones posibles, a decisión de Codex:**
- Un marcador de normalización pendiente por mapeo o caso, análogo a `operacion_pendiente.json` de ejecución, que bloquee nuevas claves.
- O registrar en `solicitud.json` el resultado destino y exponer `requiere_recuperacion`.
- En la UI, no regenerar `normalizationKey` mientras el mapeo y la huella sean los mismos.

### H2 — Reabrir un trabajo de análisis borra el estado de Lecturas y Mapeos (Baja–media)

**Archivos y líneas**
- `draft2model/revision_web/analisis.js:13`:
  - `resetJob()` emite `d2m-analysis` con `detail:null`.
  - Lo llama `open()` (l. 19), que a su vez se ejecuta al pulsar «Actualizar» (l. 53 → `listing` → l. 30), en cada sondeo de 4 s mientras el trabajo está `en_ejecucion` (l. 22) y después de ejecutar (l. 51).
- `draft2model/revision_web/lecturas.js:33-37`: ante `d2m-analysis` se ejecutan `ticket++`, `key=null` y `reset()`, con estos efectos:
  - `job=null`, se desmarca la confirmación y se detiene el sondeo de la lectura (`read++`, `clearTimeout`).
  - Se vacían `lecturaCasos` y, con `detail:null`, también `lecturaAnalisis`.
- `draft2model/revision_web/mapeos.js:43`: ante `d2m-analysis` se ejecutan `clearRecord()` y `ticket++`. `current` pasa a `null`, se deshabilitan Guardar y Aprobar, y se pierde `normalizationKey`.

**Disparador**
1. El usuario tiene abierto un trabajo de análisis, que es lo que llena `lecturaAnalisis`.
2. Prepara una lectura, marca la confirmación y abre un mapeo en borrador.
3. Pulsa «Actualizar» en Análisis, o el análisis sigue `en_ejecucion` y el sondeo lo reabre.

**Efecto reproducido**

`repro_eventos.cjs` carga `analisis.js`, `lecturas.js` y `mapeos.js` en un mismo contexto con un bus de eventos real. Resultado:

```
antes   {"lecturaEjecutar":false,"lecturaDetalle":true,"mapeoGuardar":false,"lecturaCasos":"EST"}
despues {"lecturaEjecutar":true,"lecturaDetalle":false,"mapeoGuardar":true,"lecturaCasos":""}
REPRODUCIDO
```

- Por lectura de código, sin reproducir: si el sondeo cae mientras `/api/lectura/ejecutar` está en curso, `fresh(own,caso)` en `lecturas.js:52` descarta la respuesta. El servidor ya lanzó la lectura y la UI no la muestra hasta que el usuario reabre la versión.
- No hay aprobación falsa: el servidor exige huella y confirmación. El efecto es la pérdida del trabajo de UI y la confusión sobre el estado.

**Prueba mínima propuesta:** un `.cjs` que cargue juntos `analisis.js`, `lecturas.js` y `mapeos.js` con el mismo `window` y compruebe que, al refrescar el mismo trabajo de análisis (mismo `id` y `corrida_id`), no cambian `lecturaEjecutar.disabled` ni `mapeoGuardar.disabled`.

Las pruebas actuales cargan cada módulo por separado, así que no detectan esta interacción.

### H3 — `ServicioPaneles.listar` mezcla paneles de otros resultados (Baja)

**Archivo y línea:** `draft2model/revision_paneles.py:316-318`.
- Si `_cargar` falla, la fila `{"id", "vigente": False}` se añade **antes** de saber a qué resultado pertenece el panel.
- El filtro `meta["resultado"] == resultado` (l. 319-320) solo se aplica a los paneles válidos.

**Disparador:** en el mismo caso existe un panel de otro resultado B cuya carga falla, por ejemplo porque B perdió vigencia o sus fuentes cambiaron.

**Efecto reproducido** (`repro_paneles.py`, una copia de un panel válido con `resultado` cambiado en el manifiesto):

```
listado [{"id":"8e7ca4f9…","vigente":true,…},{"id":"9708598c…","vigente":false,"problemas":["version_no_vigente"]}]
REPRODUCIDO
```

- La lista del resultado A muestra un panel ajeno marcado como «sin vigencia» (`paneles.js:31`). Si el usuario lo selecciona, solo obtiene un error.
- `listar` vuelve a renderizar cada panel del caso dos veces, en `_comprobar_html` y en la segunda verificación. El coste es O(paneles del caso) por cada listado, no O(paneles del resultado).

**Patrón análogo, solo hipótesis:** `draft2model/revision_entregables.py:93` (`listar` de informes) tiene la misma forma. No lo reproduje.

**Prueba mínima propuesta:** crear un panel válido, clonar la carpeta con otro uuid y otro `resultado` en el manifiesto, y comprobar que `listar(CASO, RESULTADO)` no contiene el clon. Hoy lo contiene.

### H4 — Resultado abierto que pierde vigencia sigue activo en la UI (Baja)

**Archivo y líneas:** `draft2model/revision_web/resultados.js:27-28`. En `listing()`, si el `id` anterior sigue en la lista, solo se restaura `value`. No se vuelve a abrir aunque la nueva fila tenga `vigente:false`.

**Disparadores:**
- `d2m-model-created`, que llega después de una construcción.
- `d2m-result-created`, cuando el resultado preferido no está vigente.

**Efecto reproducido** (`repro_resultados.cjs`):

```
opcion 7777… · requiere revisión
estado 1 versión(es) conservada(s).
descarga_habilitada true seleccion true
ultimo_d2m_result_con_registro true
REPRODUCIDO
```

- La tabla sigue mostrando los datos verificados anteriormente.
- «Descargar» (l. 80-83) serializa la copia del cliente con el nombre `resultados-comprobados.json`.
- `paneles.js` e `informes.js` conservan `selected` con ese resultado.
- Crear un panel o un informe falla en el servidor porque `_fuente` llama a `consultar_resultado`. No hay publicación falsa, solo una indicación engañosa en la UI.

**Prueba mínima propuesta:** abrir el resultado R, relistar con `vigente:false` y esperar que `resultadoDescargar.disabled===true` y que el último `d2m-result` tenga `detail===null`.

## 3. Hipótesis no reproducidas y límites documentados

1. **Mensajes crudos en `error_worker.json`.** Hipótesis de exposición; límite actual.
   - Dónde: `revision_ejecucion.py:398-399`, `revision_lecturas.py:245-246` y `revision_analisis.py:246-247` guardan `str(error)`, que puede contener rutas absolutas privadas.
   - Lo verificado: con `grep` en `draft2model/`, ninguna ruta HTTP ni ningún empaquetador lee `error_worker.json` ni `evento_*.json`. Las respuestas públicas usan códigos (`_publico`).
   - Riesgo restante: solo si alguien comparte la carpeta privada del caso. No lo cuento como fuga.
2. **`do_POST` no captura `KeyError`.** Hipótesis.
   - Dónde: `revision_visual.py:483-486` captura `ValueError`, `RuntimeError`, `OSError`, `TypeError` y `RecursionError`, pero no `KeyError`.
   - Un `KeyError` que escape de un servicio cortaría la conexión sin JSON y la UI mostraría «Failed to fetch».
   - No encontré un disparador concreto: los servicios revisados validan las claves o envuelven `KeyError`.
3. **Sin clave de idempotencia en `/api/panel/crear`, `/api/mapeo/importar*` ni `/api/mapeo/revisar`.** Límite de diseño.
   - Si se pierde la respuesta HTTP y el usuario reintenta, se crea otra versión con nuevo uuid.
   - `busy` evita el doble clic. No hay aprobación implicada.
4. **La descarga de resultados no conserva los bytes originales.** Observación.
   - `resultados.js:82` vuelve a serializar `record.datos` con `JSON.stringify(...,2)`.
   - El archivo descargado no coincide con el SHA-256 publicado de `resultados.json`, aunque su nombre sugiere «comprobados».
5. **Fallo antiguo del panel.** No lo informo como pendiente, según indica el encargo.
   - `_comprobar_html` vuelve a generar el HTML completo con el generador confiable y lo compara byte a byte.
   - `_cargar` y `archivo` releen el manifiesto, el HTML y las fuentes antes y después.
   - Lo confirmé leyendo `revision_paneles.py:230-249`, `251-281` y `327-338`.

## 4. Áreas revisadas sin hallazgos

- **HTTP** (`revision_visual.py`):
  - Token `X-Revision-Session`, Host, Origin y `Sec-Fetch-Site` en `permitido()`.
  - En POST: Origin exacto y JSON de hasta 2 MiB.
  - CSP y no-store.
  - Panel e informe se sirven como adjuntos con nombre derivado de un uuid validado.
  - Los errores salen como 409 con mensaje genérico o código.
- **Construcción** (`revision_ejecucion.py`):
  - Campos exactos e idempotencia por `(caso, clave)` con SHA del payload; si la misma clave llega con otros datos, se rechaza con `clave_reutilizada_con_otros_datos`.
  - `BEGIN IMMEDIATE` y un índice único sobre el estado `en_ejecucion`.
  - `confirmacion_explicita is True`, huella de preparación y huella del expediente.
  - Revalidación completa antes de cada fase del worker.
- **Consultas tras reinicio:** `_huerfano` toma el lease y, si el trabajo sigue `en_ejecucion` sin dueño, lo marca `incierto` y crea `operacion_pendiente.json`. Ese archivo bloquea nuevas ejecuciones con `motor_incierto`, y `requiere_recuperacion` se expone.
- **Lecturas** (`revision_lecturas.py`):
  - Idempotencia de `preparar`, límite de rutas de 260 caracteres y comprobación estricta del paquete de lectura (estados de casos = 4).
  - `respuesta_bytes` y las consultas devuelven códigos públicos.
- **Mapeos** (`revision_mapeos.py`):
  - La importación y la revisión solo aceptan borradores.
  - La aprobación exige `confirmacion_explicita`, un borrador sin cambios con la huella declarada y una fecha ISO.
  - `_cargar` verifica la cadena de padres sin aprobación heredada distinta.
  - La normalización exige `aprobacion_vigente`, un recibo que valida el mapeo y la evidencia del análisis, y `aprueba_resultados:false` con `conformidad_normativa:'no_evaluada'`. El defecto de H1 está en la ventana previa al recibo.
- **Paneles:** creación atómica por `rename`, rechazo de rutas locales en el HTML, enlaces y junctions rechazados, y verificación de bytes completos.
- **Descartes tardíos en la UI:**
  - `epoch` y `pageEpoch` en `app.js`.
  - `ticket` y `fresh()` en `paneles.js`, `informes.js`, `lecturas.js`, `mapeos.js`, `analisis.js`, `construccion.js` y `revision_modelo.js`.
  - `resultTicket` y `modelTicket` en `resultados.js`.
  - Las pruebas `.cjs` existentes las cubren y pasan (sección 5).
- **Confirmaciones explícitas en la UI:** casillas de geometría, construcción, análisis, lectura, revisión de modelo (cinco controles y declaración) y mapeo (aprobación y normalización). Todas se desmarcan cuando el JSON o la selección cambian.
- **Aprobación falsa:** ninguna proyección revisada devuelve `aprueba_resultados`, `aprueba_modelo` ni `aprueba_ingenieria` en `true`.

## 5. Pruebas ejecutadas

Todas se ejecutaron con `TEMP=TMP=workspace/tmp`.

| Prueba | Resultado observado |
|---|---|
| `node tests/revision_lecturas_frontend.cjs` | «14/14 comprobaciones de lecturas correctas» |
| `node tests/revision_mapeos_frontend.cjs` | OK |
| `node tests/revision_paneles_frontend.cjs` | OK |
| `node tests/revision_resultados_frontend.cjs` | OK |
| `node tests/revision_analisis_frontend.cjs` | OK |
| `python -m unittest` con `test_revision_paneles`, `test_revision_paneles_http`, `test_revision_mapeos`, `test_revision_mapeos_http`, `test_revision_lecturas` y `test_revision_lecturas_http` | `Ran 37 tests in 77.856s — OK` |
| Reproducción H1: `repro_normalizacion.py`, que hereda `MapeosTests` | REPRODUCIDO |
| Reproducción H2: `repro_eventos.cjs` | REPRODUCIDO. El primer intento, sin un trabajo de análisis abierto, no reproducía; el escenario real exige tener uno abierto. |
| Reproducción H3: `repro_paneles.py` | REPRODUCIDO |
| Reproducción H4: `repro_resultados.cjs` | REPRODUCIDO |

## 6. Límites de lo revisado

- **Estado de los archivos:** `ls -l` a las 23:51.
  - Durante la auditoría, Codex modificó `revision_visual.py` y `revision_web/app.js` (23:47) y añadió `revision_web/ingreso.js`.
  - Volví a comprobar que los fragmentos citados de `revision_visual.py` (l. 483-486) y de los servicios siguen iguales.
  - **No revisé** `ingreso.js` ni `revision_ingreso.py`: son nuevos y no forman parte de la cadena del encargo.
- **Revisado solo de forma parcial:**
  - `configuracion.js`.
  - `revision_analisis.py` y `revision_aprobacion_modelo.py`: los consulté con `grep` en los puntos de `error_worker` y de la aprobación, sin leerlos completos.
  - `revision_entregables.py`: solo `listar` y `crear`.
- **Sin navegador real:** las reproducciones de UI usan `node:vm` con un DOM mínimo. No cubren el renderizado, el foco ni la descarga real de blobs.
- **Transportes:** la ejecución con doble Python y las fixtures sintéticas no demuestran el comportamiento de ETABS real. No atribuyo a ETABS ningún resultado de esos transportes.
- **Pruebas no ejecutadas:** la suite completa, las pruebas HTTP de construcción y análisis, y las pruebas de resultados en Python.
