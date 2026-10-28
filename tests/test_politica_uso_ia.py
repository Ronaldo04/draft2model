import unittest
from draft2model.politica_uso_ia import exigir_autorizacion, FINALIDAD_AUTORIZADA


class PoliticaTests(unittest.TestCase):
    def test_solo_google_y_openai_para_planos(self):
        for proveedor in ('openai','gemini'):
            exigir_autorizacion(proveedor,FINALIDAD_AUTORIZADA)
        for proveedor,fin in [('anthropic',FINALIDAD_AUTORIZADA),('openai_compatible',FINALIDAD_AUTORIZADA),
                              ('openai','programacion'),('gemini','explicacion_resultados'),('openai','documentacion')]:
            with self.subTest(proveedor=proveedor,fin=fin),self.assertRaises(ValueError):
                exigir_autorizacion(proveedor,fin)
