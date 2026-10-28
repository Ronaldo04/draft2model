import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
from tests import test_revision_lecturas as fixtures
from tests import test_revision_visual as httpfixtures


class LecturasHTTPTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.LecturasWebTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.app=self.fixture.app;self.app._lecturas=self.fixture.service
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')

    def request(self,*args,**kwargs):return httpfixtures.HTTPRevisionTests.request(self,*args,**kwargs)

    def test_leer_importar_revisar_normalizar_y_exportar_sin_copiar_respuesta(self):
        with patch('subprocess.Popen',side_effect=AssertionError('Preparar no abre motor')):
            status,raw,_=self.request('POST','/api/lectura/preparar',self.fixture.body)
        self.assertEqual(status,201,raw);prepared=json.loads(raw)
        body={'caso':self.fixture.caso,'trabajo':prepared['id'],'huella_preparacion':prepared['huella_preparacion'],
              'expediente_sha256':prepared['expediente_sha256'],'confirmacion_explicita':False}
        self.assertEqual(self.request('POST','/api/lectura/ejecutar',body)[0],409)
        status,raw,_=self.request('POST','/api/lectura/ejecutar',{**body,'confirmacion_explicita':True})
        self.assertEqual(status,201,raw);self.fixture.finish(prepared)
        status,raw,_=self.request('GET','/api/lectura/trabajo?'+urlencode({'caso':body['caso'],'trabajo':prepared['id']}))
        self.assertEqual(status,200,raw);job=json.loads(raw)
        self.assertTrue(job['lectura_verificada']);self.assertEqual(job['modo_ejecucion'],'doble')
        self.assertNotIn('id_proceso',raw.decode());self.assertNotIn(str(self.app.raiz),raw.decode())
        fp=job['expediente_sha256'];proof=self.app.mapeos.fuente(body['caso'],job['analisis'],expediente_sha256=fp)
        mapping={'contrato':'draft2model.mapeo_resultados_etabs','version':'0.1.0','caso':body['caso'],
            'datos_sinteticos':True,'huella_configuracion':proof['configuracion']['huella'],
            'sha256_respuesta':job['sha256_respuesta'],
            'modelo':{'archivo':'analisis_etabs/'+job['analisis']+'/analizado.edb','sha256':job['sha256_edb']},
            'unidades_api_esperadas':'kN_m_C','version_etabs_esperada':proof['version_etabs'],
            'selectores':[{'id':'DX','variable':'deriva','caso':'EST','direccion':'X','ubicacion':'N1',
                'tabla':'Story Drifts','filtros':{'OutputCase':'EST','Story':'N1','Direction':'X'},'campo_valor':'Drift','unidad_origen':'1'}],
            'revision':{'estado':'borrador','aprobacion':None}}
        status,raw,_=self.request('POST','/api/mapeo/importar-lectura',{'caso':body['caso'],
            'trabajo_lectura':job['id'],'expediente_sha256':fp,'mapeo_json':json.dumps(mapping)})
        self.assertEqual(status,201,raw);draft=json.loads(raw)
        self.assertEqual(draft['lectura'],'lectura_aceptada_verificada')
        base=lambda item:{'caso':body['caso'],'version':item['id'],'expediente_sha256':fp,'huella_mapeo':item['huella_mapeo']}
        with patch('subprocess.Popen',side_effect=AssertionError('Mapeos y exportación no abren motor')):
            revised=self.app.mapeos.revisar({**base(draft),'mapeo_json':json.dumps(mapping)})
            self.assertEqual(revised['procedencia_lectura'],draft['procedencia_lectura'])
            approved=self.app.mapeos.aprobar({**base(revised),'revisor':'Prueba software','fecha':'2026-10-17',
                'motivo':'Fila fabricada','alcance':'Solo software sintético','confirmacion_explicita':True})
            normalized=self.app.mapeos.normalizar({**base(approved),'clave_solicitud':'f'*32,'confirmacion_explicita':True})
            panel=self.app.paneles.crear({'caso':body['caso'],'resultado':normalized['resultado'],
                'expediente_sha256':fp,'analisis':job['analisis']})
            html=self.app.paneles.archivo(body['caso'],panel['id'],expediente_sha256=fp)
        self.assertTrue(html.startswith(b'<!doctype html>'));self.assertFalse(panel['aprueba_resultados'])
        # La procedencia se revalida, incluso después de aprobar el mapeo.
        record,_=self.fixture.service._leer(body['caso'],job['id'])
        receipt=self.fixture.service._carpeta(body['caso'],job['id'])/'aceptacion_web.json'
        receipt.write_bytes(b'[]')
        with self.assertRaises(ValueError):self.app.mapeos.consultar(body['caso'],approved['id'],expediente_sha256=fp)

    def test_sesion_campos_y_sin_descarga_de_respuesta_privada(self):
        self.assertEqual(self.request('POST','/api/lectura/preparar',self.fixture.body,headers={'X-Revision-Session':'otro'})[0],403)
        self.assertEqual(self.request('POST','/api/lectura/preparar',{**self.fixture.body,'id_proceso':1})[0],409)
        self.assertEqual(self.request('GET','/api/lectura/respuesta?caso='+self.fixture.caso)[0],404)
