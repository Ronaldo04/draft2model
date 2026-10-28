# Revisión de paginación del informe PDF

Se corrigió exclusivamente la presentación PDF en `draft2model/informe.py`; no se modificaron validación, contratos, cifras, fuentes ni declaraciones de revisión/aprobación.

## Defecto reproducido

El informe de la fixture integrada conservado en:

```text
tmp/recorrido_interfaz_122/fixture/private/demo-integrada-sintetica/informes/25601212acda459ca9555c56d53f5213/informe.pdf
```

tenía tres páginas: el título **5. Cortante basal por dirección** quedaba al pie de la página 1 y la tabla empezaba en la 2; **Abstenciones** quedaba al pie de la 2 y su texto empezaba en la 3. `page-break-after: avoid` de los encabezados y `page-break-inside: avoid` del div no evitaron esos huérfanos en el renderer instalado, PyMuPDF/MuPDF 1.28.2. Los archivos originales de la fixture no se modificaron.

Se conserva la advertencia de no envolver tablas con otra tabla: esa alternativa ya había perdido contenido al cruzar páginas. La reparación tampoco corta HTML en secciones independientes, rasteriza textos, cambia el tamaño de letra o fuerza cada sección a una hoja propia.

## Solución y APIs comprobadas

Se utilizan las APIs públicas del paquete instalado: `Story`, `Story.body`, `Xml.find/find_next/first_child/next`, `Xml.get_attributes/set_attribute`, `Story.write` con `writer=None` y callback `positionfn`. Se inspeccionaron su implementación/docstrings locales y se hicieron experimentos de colocación antes de integrarlas. La medición usa las mismas dimensiones A4 y márgenes que el PDF final.

1. Antes de colocar contenido se añaden IDs internos a cada cadena de encabezados y al primer párrafo, primer ítem de lista o primera **fila de datos** de la tabla que les sigue. La fila de encabezado de tabla no cuenta como dato.
2. `Story.write(None, rectfn, positionfn=...)` distribuye el documento completo sin escribir PDF y permite conocer en qué página comienza cada ancla.
3. Si un encabezado y ese primer contenido están en páginas diferentes, se establece `page-break-before: always` **solo en el primer encabezado del primer grupo afectado** y se vuelve a distribuir todo el documento. Se resuelven los grupos en orden, para no introducir saltos posteriores que ya no sean necesarios después del primero.
4. Cuando todas las anclas coinciden en página se crea otra instancia de Story con esos mismos saltos y se escribe el PDF normalmente. Las tablas y listas extensas continúan paginándose: solo se conserva el comienzo con su título.

No se usan tablas envolventes ni callbacks privados de dibujo. Los IDs y estilos de paginación se añaden al DOM interno del PDF; el contrato JSON, la representación HTML publicada, sus cifras y su texto permanecen intactos.

### Dos detalles del binding local que originaban la reparación parcial fallida

- En la versión instalada, llamar `Xml.set_pagebreak_before()` a un elemento que tenía ID y carecía de style produjo un estilo como `titulo;page-break-before: always`: `add_style()` obtenía indebidamente el valor de otro atributo. El renderer emitía error CSS. La solución usa `get_attributes().get("style", "")` y `set_attribute("style", ...)` con un estilo explícito.
- La implementación parcial concatenaba un punto y coma al principio cuando el estilo anterior estaba vacío. MuPDF rechazaba `;page-break-before: always`, no aplicaba el salto y el guard informaba que el bloque excedía la página. Se corrigió la construcción para añadir separador únicamente cuando existe estilo previo. El estilo previo se preserva.
- El DOM editable de Story se consume al distribuir; `reset()` no lo reconstruyó en el experimento local. Por eso cada medición y la escritura final parten de una instancia nueva, con anclas y saltos deterministas.

## Evidencia de contenido y presentación

Resultados nuevos, sin sobrescribir la fixture:

```text
tmp/pdfs/qa_paginacion_flujo_v2/informe.pdf
tmp/pdfs/qa_paginacion_flujo_v2/pagina-1.png
tmp/pdfs/qa_paginacion_flujo_v2/pagina-2.png
tmp/pdfs/qa_paginacion_flujo_v2/pagina-3.png
tmp/pdfs/qa_paginacion_flujo_v2/validacion.json
```

Se inspeccionaron visualmente los tres PNGs: márgenes, tablas y pies legibles, sin solapamientos, recortes visibles ni bloques perdidos. Se mantienen **tres páginas**. Sección 5 y sus filas VX/VY están en página 2; Abstenciones y su primer cuerpo están en página 3. La página 2 conserva el encabezado de explicación junto con su primer párrafo; no se movió cada sección a una página aislada.

Comparación de todo el texto extraído del PDF original y el nuevo, normalizado NFKC y omitiendo únicamente pies de página: **598 tokens antes, 598 después, ningún token perdido ni añadido**. El log conserva también los SHA256:

| Artefacto | SHA256 |
| --- | --- |
| PDF original de la fixture | `7fc2526a671c7f388c0281d075ae34989d3fe9307ee55e6fa5278fccbe4f0d77` |
| PDF QA nuevo | `c3a400140686b7833fef8a61ae628b7270a6d5218f50cfd48da926b15f72bd04` |

`qa_paginacion_flujo_v1` corresponde al intento parcial que detectó el error CSS y se interrumpió; no contiene un PDF aceptado. La evidencia final es v2.

## Pruebas focales

Ejecución: **19 pruebas OK en 5.553 s**, salida 0; cuatro nuevas de paginación, las catorce existentes de informe y el recorrido integrado representativo de cifras/citas/huellas/PDF/SQLite. No se ejecutó la suite completa, ETABS, proveedor, navegador/CU ni se instalaron dependencias.

Las pruebas nuevas extraen las páginas reales del PDF y comprueban que los títulos comparten página con la primera fila o el primer texto. Varían el relleno previo para cruzar límites diferentes, comprueban ausencia de recorte fuera del área de página y conservan exactamente una vez cada ID/etiqueta de una tabla de **120 filas** y una lista de **140 ítems**. También comprueban cifras, omisiones y etiqueta de abstención, cadena de encabezados, estilos previos y que el informe de entrada no se modifica. No son pruebas que repitan o comparen strings CSS.

```powershell
.\.venv\Scripts\python.exe -c "import pathlib,tempfile,unittest; p=pathlib.Path('tmp/pruebas_paginacion'); p.mkdir(parents=True,exist_ok=True); tempfile.tempdir=str(p.resolve()); names=['tests.test_informe_paginacion','tests.test_informe','tests.test_flujo_integrado.FlujoIntegradoTests.test_recorrido_cifras_citas_huellas_pdf_y_sqlite']; r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromNames(names)); raise SystemExit(not r.wasSuccessful())"
```

## Límites

La solución está orientada al HTML estructurado generado por este módulo: encabezados, párrafos, listas y tablas de resultados. No es un paginador general para HTML arbitrario o contenido multimedia. Si el propio comienzo de un grupo no puede convivir en el área completa de una página, o el renderer no conserva sus anclas, se informa un error en vez de omitir contenido o afirmar que quedó bien. Sigue aplicándose el límite existente de 200 páginas.

Hay una medición adicional por cada salto necesario y una instancia de Story por pasada; documentos extensos pueden tardar más, sin cambiar fuentes o cifras para hacerlos caber. Una actualización del renderer debe repetir las pruebas de páginas y la inspección visual. La corrección de presentación no acredita resultados estructurales, conformidad normativa ni aprobación del informe.
