"""Cobertura de páginas sin candidatos: evidencia real en disco sintético."""
import unittest
from draft2model import gestion_extraccion as g
from draft2model.entrada_vision import adaptar_respuesta, cargar_paquete
from draft2model.recortes import generar_recorte
from tests import test_entrada_vision as fixture


class CoberturaSinLecturasTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.EntradaVisionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        crop2=generar_recorte(self.f.manifest,'L0001',2,[.1,.1,.9,.9],dpi=72)
        self.package=self.f.pack([self.f.crop,crop2]);self.crop2=crop2

    def extraction(self,empty=False):
        response=self.f.response(self.package)
        if empty:
            response['candidatos']=[]
            for row in response['cobertura']:row['estado']='sin_lecturas'
        return adaptar_respuesta(self.f.manifest,self.package,response,proveedor='fixture-sin-red',modelo='SINTETICO',modo_prueba=False)

    def test_importa_cobertura_con_pagina_sin_candidatos(self):
        data=self.extraction()
        self.assertEqual(len(data['cobertura']),2)
        self.assertEqual(len(data['candidatos']),1)
        comp=g.comprobar_evidencia(self.f.case,'sintetico-vision',data)
        self.assertTrue(comp.correcta,comp.a_dict())
        self.assertEqual(len(comp.inventario['recortes']),2)

    def test_sin_candidatos_todavia_comprueba_original_y_recortes(self):
        data=self.extraction(empty=True)
        comp=g.comprobar_evidencia(self.f.case,'sintetico-vision',data)
        self.assertTrue(comp.correcta,comp.a_dict())
        self.assertTrue(any(a['tipo']=='original' for a in comp.archivos_verificados))
        request,_,manifest,_=cargar_paquete(self.f.manifest,self.package)
        original=self.f.case/manifest['archivos'][0]['archivo']
        original.write_bytes(b'ORIGINAL SINTETICO ALTERADO')
        self.assertFalse(g.comprobar_evidencia(self.f.case,'sintetico-vision',data).correcta)

    def test_recorte_sin_lecturas_alterado_no_se_acepta(self):
        import json
        data=self.extraction()
        meta=json.loads(self.crop2.read_text(encoding='utf-8'))
        (self.crop2.parent/meta['imagen']).write_bytes(b'IMAGEN SINTETICA ALTERADA')
        self.assertFalse(g.comprobar_evidencia(self.f.case,'sintetico-vision',data).correcta)


if __name__=='__main__':unittest.main()
