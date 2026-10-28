# Diagnóstico 309 — compatibilidad del PDF (páginas 7/8)

Responsable: Claude. Solo lectura del informe publicado; sin regenerar el expediente, sin APIs, ETABS ni cálculos.

## Entrada verificada

- `tmp/recorrido_09d3/resultados/informe/informe.pdf`, SHA256 `ca4fc1432c509af1bc944f376e8f60f4a16f94fc3a8eff4e63b59ef2dbb5acf9` (coincide), 8 páginas, PDF 1.7.
- Entorno: Python 3.10.5; PyMuPDF/MuPDF 1.28.2 (mismo pin en `requirements*` y en el entorno offline 303). Poppler **no instalado** (sin `pdftoppm`/`pdffonts`); `pdftotext` disponible es **Xpdf 4.00** (Glyph & Cog), no Poppler. Segundo motor de render usado: **Windows.Data.Pdf** (WinRT de Windows 11), ya instalado.

## Resultado: no se reproduce pérdida de prefijos

| Prueba | Resultado |
|---|---|
| MuPDF 1.28.2, páginas 7/8, aislado vs secuencial (72/96/150 dpi) | píxeles idénticos |
| Renders de Codex `tmp/pdfs/revision_302/pagina-7/8.png` (×1.2) y `pagina7/8_aislada.png` (×1.5) | **idénticos byte a byte** a mi reproducción MuPDF; visualmente completos |
| Windows.Data.Pdf, páginas 7/8, aislado vs secuencial | solo ruido de antialiasing (Δmáx 43/255; ≤453 bytes) |
| Tinta en la caja de los 3 primeros caracteres de cada línea (361 líneas, p1–p8), MuPDF y Windows | 0 líneas sin tinta; mínimo 20 px por prefijo |
| Texto extraído p7/p8: MuPDF vs Xpdf 4.00 | idéntico tras normalizar espacios (2842 / 2564 caracteres) |
| Contenido | 18 encabezados de evaluación; 10 `False.` y 8 `True.`; masa NO COHERENTE; 8 pies `n / 8` |

Conclusión: los píxeles de los renders de Codex contienen el texto completo; la observación de «prefijos incompletos» no está en esos archivos. Lo más probable es un artefacto de la visualización (reducción de imagen en el visor o lectura visual), no un defecto del PDF. No se pudo contrastar con Poppler (no instalado); los avisos Symbol/ArialUnicode de Poppler no corresponden a fuentes de este PDF (ninguna Symbol/ArialUnicode en recursos); hipótesis no verificada: aviso genérico de inicialización de fuentes base de Poppler en Windows o sustitución de la Helvetica no incrustada del pie.

## Hallazgos estructurales (riesgos reales, no defecto visible reproducido)

1. **CFF sin ROS dentro de CIDFontType0/`CIDFontType0C`** en las tres fuentes Nimbus (y en el caso mínimo con Charis): comportamiento del escritor MuPDF Story. PDF 1.7 no define ese caso; PDF 2.0 lo define (CID = índice de glifo). Motores antiguos o estrictos podrían mapear glifos distinto — afectaría a todas las páginas, no solo 7/8.
2. **ToUnicode único (xref 4) compartido** por Bold, Regular y Mono tras `garbage=4`: válido porque los flujos eran idénticos; la extracción es correcta en dos motores.
3. **Pie con Helvetica base-14 no incrustada** (`insert_text`): los visores la sustituyen; solo afecta al pie.
4. **Ligaduras** «ﬁ/ﬂ» (U+FB01/FB02) en el texto extraíble (p7: 12, p8: 7): `conﬁgurada` no coincide con búsquedas de «configurada». No es pérdida de prefijo. Story ignora `font-variant-ligatures:none` y `font-feature-settings:'liga' 0` (prueba aislada); mitigación en consumidores: normalización NFKC.
5. Recursos deduplicados por `garbage=4` (p1/3/5/6/7 comparten xref 14 con F0=Bold; p2/4 xref 17 con F0=Regular): coherentes con su propio contenido; q/Q equilibrados; un recorte por página (42,42,511,752); ningún texto del cuerpo fuera del recorte.

## Corrección candidata

**No procede parche del generador**: no hay defecto reproducido que corregir y los cambios posibles (otra fuente, ligaduras) no se verifican con Story 1.28.2. No se modificó producto ni entregas.

## Archivos (carpeta `seguimiento/claude_ruta/diagnostico_pdf_309/`)

- `analizar_glifos.py` → `glifos_original.json` (todas las CID con ancho W en p1–p8).
- `render_windows_pdf.ps1` (segundo motor), `renders/` (MuPDF y Windows, p7/p8 aislado/secuencial; Windows p1–p8).
- `comparar_png.py`, `tinta_prefijos.py` → `tinta_prefijos_original.json`.
- `caso_minimo.py` → `caso_minimo.pdf`, `caso_minimo_estructura.json`.
- `ligaduras.py` → `ligaduras.json`; `xpdf_p7.txt`, `xpdf_p8.txt`.

## Límites

Sin Poppler, pdf.js ni Acrobat: no se declara compatibilidad universal. Sin OCR: la prueba de tinta acredita que se dibuja algo en la caja del prefijo, no su forma; la revisión visual de p7/p8 (MuPDF y Windows) sí mostró los prefijos completos.

## Siguiente acción concreta

Si el usuario o la referencia humana ven prefijos cortados, registrar el visor exacto (nombre/versión), zoom y una captura nativa sin reescalar, y ejecutar `tinta_prefijos.py` sobre ese render; con Poppler disponible, renderizar p7/p8 con `pdftoppm -r 96` y comparar con `comparar_png.py`.
