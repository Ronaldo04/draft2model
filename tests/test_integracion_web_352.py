"""Parser HTTP real y servicios en disco sintético; sin proveedores ni ETABS."""
import json
from types import SimpleNamespace
import unittest
from urllib.parse import urlencode

from tests import test_revision_politicas_malla as mesh
from tests import test_revision_visual as http
from tests.test_gestion_geometria import CASO


class IntegracionWeb352Tests(unittest.TestCase):
    def setUp(self):
        self.fixture=mesh.RevisionPoliticasMallaTests()
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.client=http.HTTPRevisionTests()
        self.client.server=SimpleNamespace(revision=self.fixture.app,token='solo-prueba-sintetica',origen='http://127.0.0.1:8766')

    def test_malla_previsualizar_y_aplicar_por_rutas_reales(self):
        body=self.fixture.solicitud()
        status,raw,_=self.client.request('POST','/api/politicas-malla/previsualizar',body)
        self.assertEqual(status,201,raw);view=json.loads(raw)
        self.assertTrue(view['politicas_completas'])
        apply={**body,'confirmacion_explicita':True,'huella_propuesta':view['huella_propuesta'],'sha256_algoritmo':view['sha256_algoritmo']}
        status,raw,_=self.client.request('POST','/api/politicas-malla/aplicar',apply,headers={'Origin':'https://otro.test'})
        self.assertEqual(status,403)
        status,raw,_=self.client.request('POST','/api/politicas-malla/aplicar',apply)
        self.assertEqual(status,201,raw)
        child=json.loads(raw);self.assertNotEqual(child['id'],body['version'])
        self.assertEqual(child['datos']['revision'],{'estado':'borrador','aprobacion':None})

    def test_parametros_rutas_y_assets_integrados_sin_envio(self):
        query=urlencode({'caso':CASO,'expediente_sha256':self.fixture.fp})
        status,raw,_=self.client.request('GET','/api/parametros/historial?'+query)
        self.assertEqual(status,200,raw);self.assertEqual(json.loads(raw),{'trabajos':[]})
        for route in ('preparar','ejecutar','recuperar','aplicar'):
            status,_,_=self.client.request('POST','/api/parametros/'+route,{})
            self.assertEqual(status,409,route)
        status,index,_=self.client.request('GET','/')
        self.assertEqual(status,200)
        for asset in ('parametros.js','politicas_malla.js'):
            self.assertIn(('src="/'+asset+'"').encode(),index)
            status,raw,_=self.client.request('GET','/'+asset)
            self.assertEqual(status,200);self.assertGreater(len(raw),100)


class IntegracionDigitizacion355Tests(unittest.TestCase):
    def setUp(self):
        from tests import test_revision_digitizacion as dig
        dig.TMP_BASE.mkdir(parents=True,exist_ok=True)
        self.dig=dig;self.fixture=dig.RevisionDigitizacionTests()
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.client=http.HTTPRevisionTests()
        self.client.server=SimpleNamespace(revision=self.fixture.app,token='solo-prueba-sintetica',origen='http://127.0.0.1:8766')

    def test_preparar_consultar_historial_y_asset_sin_aprobar(self):
        f=self.fixture;version,geo=f._importar_geo(self.dig._geometria_v03_base())
        base={'caso':self.dig.CASO,'expediente_sha256':f.fp}
        body={**base,'geometria':version,'huella_geometria':geo['huella'],'sha256_geometria':geo['sha256_geometria'],
              'fuente':f._fuente_base(con_sha=False),'plano':f._plano_z0()}
        status,raw,_=self.client.request('POST','/api/digitizacion/preparar',body)
        self.assertEqual(status,201,raw);record=json.loads(raw)
        self.assertFalse(record['disponible_para_modelado']);self.assertFalse(record['aprueba_ingenieria'])
        status,raw,_=self.client.request('GET','/api/digitizacion/registro?'+urlencode({**base,'id':record['id']}))
        self.assertEqual(status,200,raw);self.assertEqual(json.loads(raw)['id'],record['id'])
        status,raw,_=self.client.request('GET','/api/digitizacion/historial?'+urlencode(base))
        self.assertEqual(status,200,raw);self.assertIn(record['id'],raw.decode())
        status,_,_=self.client.request('POST','/api/digitizacion/calcular',{})
        self.assertEqual(status,409)
        status,raw,_=self.client.request('GET','/digitizacion.js')
        self.assertEqual(status,200);self.assertIn(b'd2m-digitizacion-propuesta',raw)


if __name__=='__main__':unittest.main()
