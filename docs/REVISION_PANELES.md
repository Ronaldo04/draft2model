# Paneles técnicos persistidos

Estado: **entrega local de Claude, 18 de octubre de 2026, pendiente de revisión e integración HTTP/UI por Codex.** `ServicioPaneles(app)` conserva versiones del panel técnico HTML de un resultado vigente del expediente, con evidencia de análisis opcional y seleccionada explícitamente. Permite consulta, listado y descarga comprobadas.

No recalcula resultados ni los aprueba.

| Archivo | Contenido |
| --- | --- |
| [`draft2model/revision_paneles.py`](../draft2model/revision_paneles.py) | `ServicioPaneles`, `ErrorPaneles` y el contrato del manifiesto. |
| [`tests/test_revision_paneles.py`](../tests/test_revision_paneles.py) | 11 pruebas focales sobre copias temporales de `tests.fixture_etabs.extraer_evidencia`. |

No se modificó ningún otro archivo.

**APIs reutilizadas, todas públicas:**

- de la app: `app.expediente`, `app.resultados.consultar_resultado` y `app.lock`;
- `evidencia_analisis.verificar_evidencia` y `huella_evidencia`;
- `panel_tecnico.crear_panel`;
- `gestion_extraccion.json_desde_bytes`, para JSON estricto.

`revision_entregables.py` sirvió solo como referencia; no se usan sus métodos privados.

## Contrato

```python
from draft2model.revision_paneles import ServicioPaneles, ErrorPaneles
servicio = ServicioPaneles(app)   # app: RevisionLocal (raiz, lock, expediente, resultados)

panel = servicio.crear({"caso": caso, "resultado": uuid32, "expediente_sha256": huella64, "analisis": None | uuid32})
servicio.listar(caso, resultado, expediente_sha256=huella64)   # {"caso","resultado","expediente_sha256","versiones":[...]}
servicio.consultar(caso, version, expediente_sha256=huella64)  # proyección pública
servicio.archivo(caso, version, expediente_sha256=huella64)    # bytes del panel.html comprobado
```

**Cuerpo de `crear`:** exactamente `{caso, resultado, expediente_sha256, analisis}`. Faltar o sobrar una clave se rechaza. `resultado` y `analisis` son UUID32 en minúsculas, y `analisis` puede ser `null`.

**Proyección** (respuesta de `crear` y `consultar`), sin rutas locales:

- identificación: `id`, `caso`, `resultado`, `analisis`, `expediente_sha256`, `huella_resultados`, `creado_utc`, `sha256_html`;
- `fuentes`: `sha256_resultados`, `geometria_id`, `sha256_geometria`, `huella_evidencia` y `sha256_edb_analizado` (las dos últimas son `null` sin análisis);
- `estados`: ver abajo;
- `vigente: true`;
- `evidencia_analisis`: el snapshot de `verificar_evidencia` sin rutas, o `null`;
- `aprueba_resultados: false`, `aprueba_ingenieria: false` y `aviso`.

**`listar`:** una fila por versión `<uuid32>` de `paneles/`:

- válida y de ese resultado: `{id, vigente: true, analisis, creado_utc, estados}`;
- no válida: `{id, vigente: false, problemas: ["version_no_vigente"]}`, sin detalles;
- válida pero de otro resultado: no aparece;
- los temporales `.panel-*` y los nombres ajenos se ignoran.

**Errores:** siempre `ErrorPaneles`, subclase de `ValueError`, con mensajes sin rutas. Los errores internos (`OSError`, `KeyError`, `TypeError`…) se traducen a un mensaje genérico que pide volver a consultar el expediente.

**Estados**, siempre separados; nada se aprueba automáticamente:

| Estado | Valor |
| --- | --- |
| `calculo` | `completado_verificado` con análisis vinculado; `sin_vinculo_de_analisis` sin él. |
| `revision_resultados` | `pendiente` |
| `conformidad_normativa` | `no_evaluada` |
| `reglas` | `pendientes`: el panel se genera sin reglas y muestra "Evaluación pendiente". |

## Persistencia

```
<caso>/paneles/<uuid32>/
  panel.html        salida exacta de crear_panel (resultados, geometría y evidencia opcional)
  manifiesto.json   draft2model.panel_persistido 0.1.0
```

El manifiesto tiene exactamente estos campos: `contrato`, `version`, `id`, `caso`, `resultado`, `analisis`, `expediente_sha256`, `huella_resultados`, `fuentes` (los cinco campos anteriores), `artefacto` (`{"panel.html": sha256}`), `estados`, `creado_utc`, `aprueba_resultados: false` y `aprueba_ingenieria: false`.

**Publicación:** se construye en un temporal `.panel-*` dentro de `paneles/` y se publica con un único `rename` a un `uuid4` nuevo. Si el destino ya existe, se rechaza. Nunca se sobrescriben originales ni versiones anteriores, y un fallo no deja una versión visible.

## Comprobaciones

**Antes de publicar, al consultar y al descargar:**

1. **Expediente:** huella de 64 hexadecimales igual a la actual (`app.expediente`). La raíz y el caso no son enlaces, y el caso es hijo directo de la raíz.
2. **Resultado:** `app.resultados.consultar_resultado` debe aceptarlo (vigencia completa de normalización y evidencia). Además, `resultados.json` en disco debe ser idéntico a los datos consultados y la geometría citada debe tener su SHA256.
3. **Análisis, si se pide:** solo `<caso>/analisis_etabs/<uuid32>`. La carpeta y sus hijos no pueden ser enlaces o junctions. `verificar_evidencia` lo revalida contra **ese resultado exacto**, de modo que un análisis de otro modelo, una mezcla o un EDB alterado se rechazan.
4. **Panel generado:** no contiene la ruta de la raíz ni la del caso, tampoco escapada en JSON. Su bloque de datos incrustado debe coincidir exactamente con lo esperado: resultados y huella vigentes, `evaluacion: null`, número de muros de la geometría y evidencia idéntica a la recalculada.
5. **Publicación:** las fuentes se recalculan y deben ser idénticas a las del inicio.

**Además, al consultar y al descargar:**

- La versión es UUID32 y la carpeta no es un enlace. Contiene exactamente `panel.html` y `manifiesto.json`, ambos archivos regulares sin enlaces.
- El manifiesto se lee como JSON estricto y se comprueban **tipos y claves exactas** de todos sus bloques **antes** de usar `.items()`, `.get()` o un índice.
- El caso, el id y el expediente coinciden. Las huellas tienen formato válido, la evidencia es coherente con `analisis` (`null` sin análisis) y los flags de aprobación son falsos.
- El SHA256 de `panel.html` coincide con el manifiesto.
- `huella_resultados`, `fuentes` y `estados` del manifiesto son iguales a los recalculados de las fuentes vigentes. El bloque incrustado vuelve a compararse (punto 4), así que un HTML editado con el manifiesto rehecho también se rechaza.
- Las fuentes se recalculan otra vez al terminar. En `archivo()`, además, los bytes devueltos se releen y se vuelve a ejecutar toda la consulta **después** de leerlos.

**Lock:** todas las operaciones se hacen bajo `app.lock`. Es reentrante, por lo que `crear` puede llamar a `consultar` dentro del mismo lock.

## Pruebas

Desde la raíz del proyecto, con `TEMP`/`TMP` en `tmp` del espacio de trabajo:

```powershell
$env:TEMP = "$PWD\tmp\claude_paneles_temp"; $env:TMP = $env:TEMP
.\.venv\Scripts\python.exe -m unittest tests.test_revision_paneles -v
```

Entrega original de Claude: 11 pruebas declaradas correctas. Verificación independiente de Codex del 17 de octubre (Lima): primera ejecución079 con una omisión por permisos de enlaces; repetición fuera del aislamiento080: 11 pruebas correctas en4.692s, sin omisiones. Después se detectaron y corrigieron dos brechas; véase actualización de integración al final. Ninguna prueba conecta ETABS ni usa red. Cubren:

- **Sin análisis:** estados pendientes, `sin_vinculo_de_analisis`, evaluación pendiente en el HTML, datos incrustados iguales al resultado consultado, SHA256 del HTML y ausencia de rutas en la proyección y en el HTML.
- **Con análisis válido:** la evidencia es igual a `verificar_evidencia`, el estado es `completado_verificado` y la revisión sigue pendiente. Con el EDB analizado alterado, consultar y descargar se rechazan y el listado lo marca como no vigente.
- **Mezclas:** se rechazan el análisis real de otro modelo (`otro_analisis/28f6…`) y un análisis que no está en `<caso>/analisis_etabs`.
- **Listado y nueva versión:** dos versiones distintas, la primera intacta byte a byte, sin temporales residuales y con los nombres ajenos ignorados.
- **HTML alterado:** se rechaza, también cuando se edita el valor incrustado y se rehace el hash del manifiesto.
- **Manifiesto** con artefacto en lista, fuentes como texto, estados en lista, manifiesto en lista, otro resultado, aprobación, revisión "aprobado", evidencia inventada, otro expediente o una clave extra: todo se rechaza sin excepciones internas. Restaurado, vuelve a validar.
- **Fuentes alteradas:** `resultados.json` y geometría (al restaurarlos, vuelve a descargar) y original del expediente (cambia la huella).
- **Fuente cambiada durante la descarga:** detectada por la revalidación final.
- **Cuerpo, rutas e ids rechazados:** `../`, mayúsculas, otro caso, huella falsa o corta, `analisis` no textual, claves de más o de menos, versiones con `../` o inexistentes.
- **Enlaces:** `analisis_etabs` y `paneles` como junction o symlink, rechazados sin escribir en el destino enlazado. Esta prueba se omite si el sistema no permite crear ninguno.
- **Lock:** uso de `app.lock` en crear, descargar y listar.

## Limitaciones

- **Alcance:** el panel muestra resultados y, opcionalmente, la evidencia de cálculo. No revisa resultados, no evalúa normativa, no aplica reglas (siempre pendientes) ni aprueba ingeniería. La identidad del revisor del modelo sigue siendo declarada.
- **Autenticidad:** las huellas detectan cambios y mezclas, pero no autentican al productor ni impiden una reescritura coherente de todas las fuentes y del expediente.
- **Vigencia y coste:** una versión deja de ser válida en cuanto cambia cualquier fuente o el expediente; no se repara ni se regenera sola. Cada consulta o descarga recalcula la vigencia del resultado y, si hay análisis, la evidencia completa. Con expedientes grandes puede tardar.
- **Concurrencia:** el lock de la app protege dentro de un mismo proceso, no frente a otros procesos que escriban el expediente. Un cambio externo durante la operación se detecta por las comprobaciones repetidas, pero puede quedar una carpeta vacía `paneles/` si `crear` falla tras crearla.
- **Integración:** HTTP/UI conectados por Codex. Para descargar se sugiere `Content-Type: text/html; charset=utf-8` con `Content-Disposition: attachment` y el id de la versión como nombre. Las respuestas de error deben usar el mensaje de `ErrorPaneles`, que no contiene rutas.


## Integración y revisión independiente, 17 de octubre de 2026 (Lima)

`RevisionLocal.paneles` está conectado a POST `/api/panel/crear` y GET `/api/paneles`, `/api/panel`, `/api/panel/archivo`. GET usa caso, expediente_sha256 y resultado para listado o version para consulta/descarga. El HTML se entrega como attachment; no se relaja CSP de la aplicación. La pantalla selecciona evidencia opcional, crea otra versión, consulta historial y descarga HTML para abrir localmente. Descarta respuestas y errores obsoletos al cambiar caso/versión.

La revisión cruzada encontró que comprobar solo JSON embebido permitía cambiar el shell ejecutable y rehacer su hash. Ahora se exige igualdad byte a byte con una generación confiable completa. Cambiar la plantilla invalida los paneles antiguos hasta establecer una política explícita de versiones del generador; no se migran silenciosamente. También se detectó una carrera durante la segunda validación de descarga: ahora se releen bytes exactos de manifiesto/HTML y se comparan ambas cargas, además de fuentes.

Cuatro regresiones nuevas elevan las pruebas del servicio a15. La pasada del subagente dio14 correctas y1 omitida por permisos de enlaces; no se acredita como15 ejecutadas. Integración HTTP081:6 pruebas de panel/informe correctas en5.126s (anterior al refuerzo posterior del servicio). Node `tests/revision_paneles_frontend.cjs`: respuestas tardías/error, descarga vigente y reinicio correctos. Repetición final del servicio y HTTP registrada por Codex en RETOMAR.md. No se ha ejecutado ETABS real mediante esta integración ni inspeccionado visualmente la pantalla nueva.
