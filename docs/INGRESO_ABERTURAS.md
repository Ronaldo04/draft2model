# Ingreso y contraste visual de aberturas

Incremento local de software: geometría 0.3, manifiesto de conversión 0.3 y correspondencia visual 0.4. Los números de versión pertenecen a contratos distintos. La correspondencia 0.3 anterior continúa describiendo superficies **sin huecos** de geometría 0.2 en una base 3D declarada. No se reinterpreta ni se modifica ningún archivo guardado de versiones anteriores.

## Conversión de lecturas revisadas

El manifiesto 0.3 conserva todos los campos del manifiesto 0.2 y exige `aberturas` como lista explícita, posiblemente vacía. Cada entrada tiene exactamente:

```json
{"id":"A1","superficie":"S1","vertices":["H1","H2","H3","H4"],"referencias":["C004"]}
```

Los vértices siguen la declaración física del manifiesto de superficies: XYZ desde candidatos tipo cota revisados o medidas del operador con unidad, justificación y referencias revisadas. No se convierten bbox/píxeles en metros. La abertura enlaza una anfitriona y contorno, y exige sus propias referencias de lectura revisadas/comprobadas; no copia automáticamente la referencia del piso. El registro de procedencia de la abertura conserva esas referencias. La traza añade `modo: conectividad_abertura_declarada`, `superficie`, `vertices`, `ruta` y `referencias`. Ninguna conectividad/material/función resistente se obtiene por inferencia.

`conversion_geometria._construir(exportacion, manifiesto)` genera geometría 0.3 y trazas, que valida integralmente. `comprobar_reproduccion` reconstruye exactamente ambas desde la exportación/manifiesto conservados. El servicio de revisión mantiene sus verificaciones de archivos, expediente, extracción, exportación y huellas, antes y después de procesar. Eliminar un hueco o cambiar su traza, aunque se recalculen hashes locales, no reproduce la declaración fuente y se rechaza.

Rutas existentes sin cambios: `/api/conversion/crear`, `/api/conversion`, `/api/conversiones`, `/api/conversion/importar-geometria`. Crear/consultar una conversión no importa ni aprueba geometría. La importación sigue siendo otra acción confirmada sobre ID y huella exactos, y produce borrador sin disponibilidad de modelado. El cliente conserva selección, confirmación y guardas contra respuestas obsoletas; muestra cuándo conserva aberturas explícitas.

## CSV y XLSX supervisados

`importacion_tabular.colecciones_tabulares(metadata)` selecciona exclusivamente por la versión declarada en el JSON:

| Geometría | CSV / hojas XLSX exactas |
| --- | --- |
| 0.1 | niveles, nodos, muros |
| 0.2 | anteriores, vertices, superficies |
| 0.3 | anteriores, aberturas |

Para 0.3 la sexta tabla tiene las columnas obligatorias `id,superficie,vertices,procedencia`. Las celdas `vertices` y `procedencia` usan JSON estricto, igual que las tablas previas: sin claves duplicadas, NaN/Infinity, fórmulas ni objetos de otro esquema. La lista vacía de aberturas se declara con tabla/hoja vacía **con cabecera**, no omitiendo el archivo. Los metadatos contienen todos los campos raíz salvo las seis colecciones, con revisión borrador y aprobación null.

`convertir_tablas(metadata, tablas)` produce geometría 0.3 íntegra y validada, sin repararla ni inferir medidas. `leer_tablas_xlsx(..., colecciones=(...))` admite exactamente la selección declarada; su valor predeterminado conserva las tres hojas históricas. Se mantienen los límites anteriores de archivo/ZIP/XML/celdas/filas, rechazo de fórmulas, hojas extra/ocultas, macros, XML inseguro, rutas y vínculos externos. Añadir una hoja admitida no relaja esas guardas.

El CLI existente incorpora `--aberturas` para la versión 0.3, o `--xlsx` con sus seis hojas; conserva salida exclusiva y rechazo de mezclar formatos. Las rutas web `/api/tabular/crear`, `/api/tabular/version`, `/api/tabular/historial`, `/api/tabular/importar` conservan el cuerpo previo. El recibo de almacenamiento mantiene su versión histórica 0.1, mientras `version_contrato` de la respuesta declara la versión geométrica real y el resumen incluye `aberturas`. Cada consulta vuelve a convertir los bytes fuente y contrasta la geometría guardada; modificarla coherentemente con un hash nuevo no evita esa reproducción. Importar sigue siendo otra acción confirmada y no aprueba el borrador.

## Correspondencia visual 0.4

Usa los mismos campos de la solicitud de superficies anterior: `caso`, expediente SHA, ID/huella/SHA de geometría, original/página, `version_contrato`, `plano`, `superficies`, tres `anclas` de vértice y declaración/confirmación. **No** admite una lista parcial de huecos suministrada por el operador: se incorporan obligatoriamente todas las aberturas de las anfitrionas expresamente seleccionadas. El cuerpo declara `version_contrato: "0.4.0"` y requiere geometría 0.3.

`plano` puede ser exactamente `{"tipo":"horizontal","cota_m":2.6}` o la base ortonormal 3D existente, con origen XYZ y U/V unitarios/ortogonales declarados, sin valores predeterminados. Todas las superficies y todos sus huecos deben pertenecer a ese plano. El plano horizontal exige Z exacto; la base 3D aplica los criterios computacionales documentados de escala/ULP y epsilon 1e-12, también por contorno de abertura. No se aplana una abertura ni se corrige una base inválida. Los criterios de huecos quedan en `base_vista.criterios_coplanaridad_aberturas[superficie][abertura]` para base 3D.

**Anclas:** solo vértices del contorno exterior de anfitrionas expresamente seleccionadas. Un vértice de abertura, un nodo legado o uno de una superficie no seleccionada se rechazan como ancla. Tres anclas no colineales y sus puntos visibles normalizados declaran la transformación afín; no acreditan escala física ni documentación del elemento. La posición física procede de la geometría y la correspondencia visual es una declaración adicional.

La correspondencia conservada fija versión geométrica 0.3 y el mapa `aberturas: {"S1":["A1"]}`. Se reproduce ese mapa contra todas las anfitrionas seleccionadas, además de la base, transformación, fuentes y huellas existentes. Un formato anterior no puede registrar/consultar geometría 0.3: se rechaza explícitamente, incluso si tiene muros legados, para no ocultar huecos. El esquema muestra por anfitriona su contorno, procedencia, áreas bruta/huecos/neta y todos los objetos de abertura con sus IDs/XYZ/procedencia. La consulta añade sus proyecciones individuales; los puntos fuera de imagen se conservan sin recortar y mencionan anfitriona/abertura/vértice.

El esquema métrico y la superposición sobre la imagen usan para cada anfitriona un SVG `path` con subcontornos cerrados y `fill-rule="evenodd"`: el hueco es transparente y deja ver la página. Se dibujan sus bordes, sin generar un piso lleno. El detalle presenta área bruta, total de huecos, área neta, IDs, anfitriona y procedencias. Las coordenadas siguen el orden declarado. Los formatos previos conservan su representación anterior. El cliente elige correspondencia 0.4 según geometría 0.3, preserva selección/guardas de obsolescencia y bloquea el modo histórico de muros para esa geometría.

Las consultas conservan la comprobación posterior al renderizado de la página: original, preview, geometría, correspondencia y metadatos deben permanecer vigentes. Una mutación durante el render invalida el resultado. La vista no constituye malla, sección física, aprobación de ingeniería ni disponibilidad ETABS.

## Integración de interfaz y verificación

No se necesitan nuevos controles ni IDs HTML: se reutilizan vista horizontal, base 3D, selección de anfitriona y anclas externas. Codex puede actualizar el texto del ingreso a tres/cinco/seis tablas y explicar el vacío visual; no necesita un selector manual de huecos. Este incremento no edita `index.html` ni las pruebas JS compartidas.

Pruebas focales reproducibles desde la raíz:

```powershell
$env:TEMP=(Resolve-Path tmp).Path
$env:TMP=$env:TEMP
.venv/Scripts/python.exe -m unittest tests.test_ingreso_aberturas tests.test_superposicion_aberturas -v
```

Cubren CSV/XLSX/CLI equivalentes, JSON/fórmulas/versiones/colecciones estrictas, registro/importación separada y replay, lectura HTTP de los tres servicios, trazas de evidencia, eliminación de huecos con hashes recalculados, horizontal/cm/inclinado/vertical, plano/huella/anclas inválidos, registros alterados y mutación durante render. Las regresiones focales de los módulos anteriores y los clientes se registran con comandos/logs en `tmp/entrega_ingreso_aberturas.json`. Los harness suplementarios `tmp/ingreso_superposicion_harness.cjs` y `tmp/ingreso_tabular_harness.cjs` extienden los existentes sin editarlos: verifican `evenodd`/dos subcontornos/áreas, base vertical, modo incompatible y selección seis tablas. Codex puede trasladar esos casos a las pruebas compartidas bajo su propiedad y hacer QA de navegador real.

No se ha ejecutado red/API, ETABS, instalación ni suite global. Tampoco se ha acreditado el recorrido de los planos reales. Configuración/operaciones ETABS con huecos, malla, cargas, idealización de aligerados y demás componentes físicos siguen siendo trabajo material del goal; este ingreso no los habilita ni los sustituye.
