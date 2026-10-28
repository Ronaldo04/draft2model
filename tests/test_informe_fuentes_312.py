"""El PDF debe conservar sus pies sin depender de fuentes del visor."""
import unittest
import unicodedata
import pymupdf
from draft2model.informe import _pdf


class FuentesInforme(unittest.TestCase):
    def test_fuentes_incrustadas_y_pie_en_cada_pagina(self):
        paragraph='Información sintética: unidades kN, valores 0.748 y límites declarados. '
        html='<html><body>'+''.join('<p>'+paragraph*8+'</p>' for _ in range(30))+'</body></html>'
        with pymupdf.open(stream=_pdf(html),filetype='pdf') as doc:
            self.assertGreater(len(doc),1)
            for index,page in enumerate(doc):
                with self.subTest(pagina=index+1):
                    text=unicodedata.normalize('NFKC',page.get_text())
                    self.assertIn(f'Draft2Model | Informe preliminar | {index+1} / {len(doc)}',text)
                    for font in page.get_fonts(full=True):
                        self.assertTrue(doc.extract_font(font[0])[3],
                                        f'Fuente no incrustada en página{index+1}: {font[3]}')


if __name__=='__main__':
    unittest.main()
