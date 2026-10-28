"""Integración HTTP en memoria: planes sin clave y ejecución sintética Python."""
import json
from types import SimpleNamespace
from urllib.parse import urlencode
import unittest
from tests import test_revision_proveedor as fixtures
from tests import test_revision_visual as http


class ProveedorHTTPTests(unittest.TestCase):
    request=http.HTTPRevisionTests.request

    def setUp(self):
        self.fixture=fixtures.ProveedorWebTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.app=self.fixture.app
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')

    def prepare(self):
        status,raw,_=self.request('POST','/api/proveedor/preparar',self.fixture.body())
        self.assertEqual(status,201,raw);return json.loads(raw)

    def execution(self,item):return {'caso':item['caso'],'trabajo':item['id'],'expediente_sha256':item['expediente_sha256'],
        'huella_preparacion':item['huella_preparacion'],'confirmacion_explicita':True}

    def query(self,item):return '/api/proveedor/trabajo?'+urlencode({'caso':item['caso'],'trabajo':item['id']})

    def test_preparacion_sin_clave_idempotencia_listado_y_assets(self):
        self.assertIsNone(self.app._proveedor);item=self.prepare();self.assertEqual(self.prepare()['id'],item['id'])
        self.assertEqual(item['estado'],'preparado');self.assertFalse(item['llamada_real_acreditada']);self.assertIsNone(item['costo_estimado'])
        status,raw,headers=self.request('GET',self.query(item));self.assertEqual(status,200);self.assertEqual(json.loads(raw),item);self.assertEqual(headers['Cache-Control'],'no-store')
        status,raw,_=self.request('GET','/api/proveedor/trabajos?'+urlencode({'caso':item['caso']}));self.assertEqual(status,200);self.assertEqual(len(json.loads(raw)['trabajos']),1)
        status,raw,_=self.request('POST','/api/proveedor/ejecutar',self.execution(item));self.assertEqual(status,409)
        self.assertEqual(json.loads(raw)['codigo'],'clave_ausente_sin_envio');self.assertEqual(self.app.proveedor.consultar(item['caso'],item['id'])['estado'],'preparado')
        self.assertFalse((self.fixture.fixture.case/'vision/intentos_openai').exists())
        for route in ('/proveedor.js','/'):
            status,raw,_=self.request('GET',route);self.assertEqual(status,200);self.assertIn(b'proveedorPreparar',raw)

    def test_catalogo_html_refleja_protocolos_y_capacidades_sin_credenciales(self):
        from draft2model.proveedores import CATALOGO
        from html.parser import HTMLParser
        class Opciones(HTMLParser):
            def __init__(self):
                super().__init__(); self.valores = []
            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                if tag == 'option' and 'data-detalle-auto' in a:
                    self.valores.append((a['value'], a['data-detalle-auto']))
        status, raw, _ = self.request('GET', '/')
        self.assertEqual(status, 200)
        parser = Opciones(); parser.feed(raw.decode('utf-8'))
        from draft2model.politica_uso_ia import PROVEEDORES_AUTORIZADOS  # ruta 201: solo Google/OpenAI operativos
        esperado = [(p.id, str(p.detalle_auto).lower()) for p in CATALOGO.values() if p.id in PROVEEDORES_AUTORIZADOS]
        self.assertEqual(parser.valores, esperado * 2)
        self.assertNotIn(b'__OPCIONES_IA__', raw)

    def test_ejecucion_sintetica_confirmada_sin_segundo_envio(self):
        transport=fixtures.Transporte(self.fixture.api());self.app._proveedor=self.fixture.service(transport);item=self.prepare();body=self.execution(item)
        for changes in ({'confirmacion_explicita':False},{'huella_preparacion':'0'*64}):
            self.assertEqual(self.request('POST','/api/proveedor/ejecutar',{**body,**changes})[0],409)
        self.assertEqual(transport.llamadas,[])
        status,raw,_=self.request('POST','/api/proveedor/ejecutar',body);self.assertEqual(status,201,raw)
        self.app.proveedor._threads[item['id']].join(20);self.assertFalse(self.app.proveedor._threads[item['id']].is_alive())
        status,raw,_=self.request('GET',self.query(item));self.assertEqual(status,200);done=json.loads(raw)
        self.assertEqual(done['estado'],'completado_verificado');self.assertEqual(done['modo'],'transporte_prueba_python')
        self.assertFalse(done['llamada_real_acreditada'] or done['aprueba_ingenieria'] or done['aprueba_resultados']);self.fixture.assertSinPrivados(done)
        self.assertEqual(self.request('POST','/api/proveedor/ejecutar',body)[0],201);self.assertEqual(len(transport.llamadas),1)
        link={'caso':item['caso'],'expediente_sha256':item['expediente_sha256'],'trabajo':item['id'],
            'huella_preparacion':item['huella_preparacion'],'confirmacion_explicita':True}
        self.assertEqual(self.request('POST','/api/respuestas/vincular-proveedor',{**link,'confirmacion_explicita':False})[0],409)
        status,raw,_=self.request('POST','/api/respuestas/vincular-proveedor',link);self.assertEqual(status,201,raw)
        linked=json.loads(raw);self.assertEqual(linked['origen'],'proveedor_verificado');self.assertEqual(linked['trabajo_proveedor'],item['id'])
        self.assertTrue(linked['modo_prueba']);self.assertFalse(linked['traslado_permitido'] or linked['transmision_externa'] or linked['llamada_real_acreditada'])
        self.assertEqual(self.app.documentos(item['caso'])['versiones'],[])
        self.assertEqual(self.request('POST','/api/respuestas/vincular-proveedor',link)[0],201);self.assertEqual(len(transport.llamadas),1)

    def test_recuperacion_incierta_no_reenvia(self):
        transport=fixtures.Transporte(error=TimeoutError('doble sintético'));self.app._proveedor=self.fixture.service(transport);item=self.prepare()
        self.assertEqual(self.request('POST','/api/proveedor/ejecutar',self.execution(item))[0],201)
        self.app.proveedor._threads[item['id']].join(20);self.assertFalse(self.app.proveedor._threads[item['id']].is_alive())
        status,raw,_=self.request('GET',self.query(item));self.assertEqual(status,200);self.assertEqual(json.loads(raw)['estado'],'incierto')
        body={'caso':item['caso'],'trabajo':item['id'],'huella_preparacion':item['huella_preparacion'],'confirmacion_explicita':True,'resolucion':'cerrar_sin_reintento'}
        for changes in ({'confirmacion_explicita':False},{'resolucion':'reenviar'}):
            self.assertEqual(self.request('POST','/api/proveedor/recuperar',{**body,**changes})[0],409)
        status,raw,_=self.request('POST','/api/proveedor/recuperar',body);self.assertEqual(status,201,raw)
        self.assertEqual(json.loads(raw)['estado'],'incierto_resuelto');self.assertEqual(len(transport.llamadas),1)

    def test_sesion_origen_campos_y_error_publico(self):
        for headers in ({'X-Revision-Session':'otro'},{'Origin':'https://ajeno.invalid'}):
            self.assertEqual(self.request('POST','/api/proveedor/preparar',self.fixture.body(),headers)[0],403)
        for change in ({'modelo':''},{'paquete':'../otro'},{'OPENAI_API_KEY':'no-permitida'}):
            status,raw,_=self.request('POST','/api/proveedor/preparar',{**self.fixture.body(),**change});self.assertEqual(status,409)
            self.assertIn('codigo',json.loads(raw));self.fixture.assertSinPrivados(json.loads(raw))
        self.assertEqual(self.request('GET','/api/proveedor/trabajo?'+urlencode({'caso':self.fixture.caso,'trabajo':'../otro'}))[0],409)

if __name__=='__main__':unittest.main()
