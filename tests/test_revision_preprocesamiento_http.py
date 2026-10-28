"""Fotos→derivado→recorte→paquete por HTTP local en memoria, sin proveedor."""
import json
from types import SimpleNamespace
from urllib.parse import urlencode
import unittest
from unittest.mock import patch
from draft2model.revision_visual import RevisionLocal
from tests import test_revision_preprocesamiento as fixture
from tests import test_revision_visual as http


class PreprocesamientoHTTPTests(unittest.TestCase):
    request=http.HTTPRevisionTests.request

    def setUp(self):
        self.fixture=fixture.CasoPreprocesado();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.app=RevisionLocal(self.fixture.case.parent);self.caso=self.fixture.case.name
        self.base={'caso':self.caso,'expediente_sha256':self.app.expediente(self.caso)[2]}
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')
        guard=patch('subprocess.Popen',side_effect=AssertionError('Sin procesos ni proveedor'))
        guard.start();self.addCleanup(guard.stop)

    def get(self,name,**extra):return self.request('GET','/api/visual/'+name+'?'+urlencode({**self.base,**extra}))

    def post(self,name,**extra):
        status,raw,_=self.request('POST','/api/visual/'+name,{**self.base,**extra})
        self.assertEqual(status,201,raw);return json.loads(raw)

    def test_original_exif_derivado_y_paquete_sin_cambiar_original(self):
        status,raw,_=self.get('original-raster',archivo='L0001');self.assertEqual(status,200)
        self.assertIn('exif_original',json.loads(raw))
        item=self.post('preprocesar',archivo='L0001',config=self.fixture.config,revisor_declarado='Prueba sintética',motivo='Ensayo')
        self.assertEqual(len(item['id']),64);self.assertFalse(item['aprueba_ingenieria'])
        self.assertNotIn(str(self.app.raiz),json.dumps(item))
        status,raw,headers=self.get('preprocesado-imagen',version=item['id'])
        self.assertEqual(status,200);self.assertTrue(raw.startswith(b'\x89PNG'));self.assertEqual(headers['Cache-Control'],'no-store')
        self.assertEqual(self.get('preprocesamientos',archivo='L0001')[0],200)
        crop=self.post('recortar',archivo='L0001',pagina=1,bbox=[0.1,0.1,0.9,0.9],dpi=150,
            etiqueta='Recorte derivado sintético',preprocesamiento=item['id'])
        self.assertEqual(crop['tipo_fuente'],'raster_preprocesado');self.assertEqual(crop['preprocesamiento_id'],item['id'])
        packet=self.post('preparar',revision=self.fixture.revision.parent.name,recortes=[crop['id']])
        self.assertEqual(packet['recortes'],[crop['id']]);self.assertFalse(packet['transmision_externa'])
        self.assertEqual(self.fixture.original.read_bytes(),self.fixture.original_bytes)

    def test_origen_sesion_identificadores_y_fuentes_alteradas(self):
        body={**self.base,'archivo':'L0001','config':self.fixture.config,'revisor_declarado':'Prueba','motivo':'Ensayo'}
        for headers in ({'Origin':'https://ajeno.invalid'},{'X-Revision-Session':'ajeno'}):
            self.assertEqual(self.request('POST','/api/visual/preprocesar',body,headers)[0],403)
        for ident in ('../otra','0'*32,'0'*64):self.assertEqual(self.get('preprocesamiento',version=ident)[0],409)
        item=self.post('preprocesar',archivo='L0001',config=self.fixture.config,revisor_declarado='Prueba',motivo='Ensayo')
        self.fixture.original.write_bytes(b'alterado')
        self.assertEqual(self.get('preprocesamiento',version=item['id'])[0],409)
        self.assertEqual(self.get('preprocesado-imagen',version=item['id'])[0],409)
