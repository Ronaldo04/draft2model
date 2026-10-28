# Diagnóstico 310 — contraste Poppler

Responsable: Claude. 309 intacto. Sin APIs, ETABS, cálculos ni regeneración del expediente; producto y entregas sin cambios.

## Entradas verificadas

- PDF 09d3 SHA256 `ca4fc143…acf9` (coincide). Poppler `pdftoppm` 26.07.0 en `C:/Users/HP/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/` (no instalado nada).
- PNG de Codex: `tmp/pdfs/revision_310/poppler-7.png` (`08f96efc…`), `poppler-8.png` (`1c551d41…`), 794×1123 a 96 dpi.

## 1. La discrepancia no está en los píxeles

- Mi render Poppler 26.07.0 a 96 dpi de p7/p8, **aislado y secuencial**, es **idéntico byte a byte** a los PNG de Codex. Mismos píxeles.
- Revisión visual ampliada ×3 del recorte izquierdo de los dos primeros bloques de `poppler-7.png` de Codex (`codex_poppler7_recorte_izq_x3.png`): se leen completos «Estado: evaluado», «Fórmula: 4.5 * x + 0.0», «Fuente de regla DECLARADA» en ambos bloques.
- Comprobación de **forma** (no solo tinta; `comparar_prefijos_forma.py`): para cada línea, IoU binarizado (±2 px) de cada uno de los 4 primeros caracteres frente a MuPDF al mismo dpi y posición de la primera columna con tinta.
  - p7: 37 líneas; primer carácter IoU ≥ 0.95 en todas; desplazamiento de la primera tinta **0 px en todas**. «Estado» [1.0, 0.81, 1.0, 1.0], «Fórmula» [1.0, 0.85, 0.93, 1.0], «Fuente» [1.0, 0.90, 0.79, 0.90].
  - p8: 35 líneas; primer carácter IoU ≥ 0.92; desplazamiento 0 px.
  - Las líneas marcadas (IoU < 0.5 en algún carácter) son glifos finos con hinting distinto («r» de «Peruano», hashes en monoespaciada) y el pie (fuente sustituida). Un prefijo omitido daría IoU ≈ 0 y primera tinta desplazada unos 25–30 px; no ocurre en ninguna línea.
- Hipótesis (no verificada) para «do:/ula:/te de regla»: la pérdida equivale a recortar unos 25–30 px a la izquierda del texto en la zona superior. Es coherente con un recorte o superposición del visor usado para mirar el PNG, no con el PNG.

## 2. Diferencia real y específica de Poppler: la fuente del pie

- Avisos `No display font for 'Symbol'` / `'ArialUnicode'`: aparecen con un PDF mínimo **con** pie `insert_text` (Helvetica base-14 no incrustada) y **no** aparecen en el mismo PDF sin pie (`aviso_con_pie_helv.pdf` / `aviso_sin_pie.pdf`). Causa: Poppler en Windows intenta sustituir la Helvetica no incrustada del pie. Solo afecta al pie, que en Poppler se ve correcto (`poppler7_pie_x3.png`).
- CFF sin ROS: hipótesis no demostrada como causa de nada visible; el cuerpo se dibuja igual en los tres motores.

## 3. Candidato mínimo (aislado, no integrado)

`pdf_candidato_310.py`: copia de `_pdf` con **un único cambio**: el pie usa `insert_font(fontname="D2MPie", fontbuffer=pymupdf.Font("helv").buffer)`, es decir, el Nimbus Sans Regular que PyMuPDF ya trae y que el cuerpo ya incrusta. No añade archivos de fuente ni licencias nuevas.

Parche propuesto para `draft2model/informe.py::_pdf`, dentro del bucle de páginas:

```python
pie = pymupdf.Font("helv").buffer          # fuera del bucle
p.insert_font(fontname="D2MPie", fontbuffer=pie)
p.insert_text((42,pagina.height-25), f'Draft2Model | Informe preliminar | {i+1} / {len(doc)}', fontsize=8, color=(.3,.4,.45), fontname="D2MPie")
```

Verificación (generado desde el `informe.html` publicado, sin expediente):
- La base reconstruida `_pdf(informe.html)` es idéntica en píxeles al PDF publicado en las 8 páginas (MuPDF 96 dpi): el procedimiento es fiel.
- Candidato frente al original:
  - texto extraído idéntico en las 8 páginas;
  - 18 evaluaciones, 10 False / 8 True, 24 «kN», NO COHERENTE y 8 pies iguales (`contenido_original_vs_candidato.json`).
- Por motor:
  - **Poppler 26.07.0:** sin avisos Symbol/ArialUnicode. El cuerpo es idéntico byte a byte; solo cambian las filas del pie (y 811–818 pt) en las 8 páginas. Pie legible.
  - **MuPDF 1.28.2:** idéntico en píxeles en las 8 páginas.
  - **Windows.Data.Pdf:** p7/p8 solo cambian en las filas del pie.

## Archivos

- `comparar_prefijos_forma.py`, `forma_poppler_codex_p7/p8.json`, `forma_poppler_candidato_p7/p8.json`.
- `codex_poppler7_recorte_izq_x3.png`, `poppler7_pie_x3.png`, `mupdf7_pie_x3.png`, `poppler_candidato7_pie_x3.png`.
- `aviso_sin_pie.pdf`, `aviso_con_pie_helv.pdf`.
- `pdf_candidato_310.py`, `base_reconstruida.pdf`, `candidato_310.pdf`, `contenido_original_vs_candidato.json`.
- `renders/`: Poppler original aislado y secuencial con stderr, Poppler candidato, MuPDF, Windows candidato.

## Límites

- No se declara compatibilidad universal (sin pdf.js ni Acrobat).
- IoU frente a MuPDF tolera diferencias de hinting; no es OCR.
- El candidato corrige solo la sustitución de la fuente del pie; no se demostró defecto de prefijos que corregir.

## Siguiente acción

Codex decide si integra el cambio del pie en `_pdf` (más una prueba que exija fuentes incrustadas en todas las páginas). Para la observación «do:/ula:», mirar el PNG en otro visor a tamaño 1:1, o recortar con `comparar_prefijos_forma.py` y registrar el visor usado.
