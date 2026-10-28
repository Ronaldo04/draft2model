"""310: candidato aislado (no integrado). Copia de draft2model.informe._pdf con UN cambio: el pie de página usa una fuente
INCRUSTADA en vez de la Helvetica base-14 no incrustada.

La fuente incrustada es el programa Nimbus Sans Regular que PyMuPDF ya trae (pymupdf.Font("helv").buffer) y que el cuerpo del
informe ya incrusta vía Story: no añade archivos de fuente nuevos ni licencias distintas a las ya presentes en el PDF.

Uso diagnóstico: python pdf_candidato_310.py HTML_PUBLICADO SALIDA_BASE.pdf SALIDA_CANDIDATO.pdf
(no regenera el expediente; parte del informe.html ya publicado).
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import pymupdf
from draft2model.informe import _pdf, _story_paginada, AVISO


def _pdf_candidato(contenido_html):
    import io
    buffer = io.BytesIO()
    pagina = pymupdf.paper_rect("a4")
    area = pymupdf.Rect(42, 42, pagina.width - 42, pagina.height - 48)

    def rectangulo(numero, previo):
        if numero >= 200:
            raise ValueError("Informe supera 200 páginas.")
        return pagina, area, None
    story = _story_paginada(contenido_html, rectangulo)
    writer = pymupdf.DocumentWriter(buffer)
    try:
        story.write(writer, rectangulo)
    finally:
        writer.close()
    pie = pymupdf.Font("helv").buffer   # Nimbus Sans Regular incluido en PyMuPDF (ya incrustado por Story en el cuerpo)
    with pymupdf.open(stream=buffer.getvalue(), filetype="pdf") as doc:
        for i, p in enumerate(doc):
            p.insert_font(fontname="D2MPie", fontbuffer=pie)   # 310: pie con fuente incrustada (antes /helv base-14)
            p.insert_text((42, pagina.height - 25), f'Draft2Model | Informe preliminar | {i+1} / {len(doc)}', fontsize=8,
                          color=(.3, .4, .45), fontname="D2MPie")
        doc.set_metadata({"title": "Draft2Model - Informe preliminar", "author": "Draft2Model", "subject": AVISO})
        return doc.tobytes(garbage=4, deflate=True)


if __name__ == "__main__":
    html = Path(sys.argv[1]).read_text(encoding="utf-8")
    Path(sys.argv[2]).write_bytes(_pdf(html))
    Path(sys.argv[3]).write_bytes(_pdf_candidato(html))
    print("ok")
