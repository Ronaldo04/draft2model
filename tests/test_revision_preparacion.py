import base64
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode
import pymupdf
from tests import test_revision_ingreso as fixture_ingreso
from tests import test_revision_visual as httpfixtures
from draft2model import revision_preparacion as preparation


class PreparacionWebTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_ingreso.IngresoWebTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.app=self.fixture.app;body=self.fixture.body
        with pymupdf.open() as doc:
            page=doc.new_page(width=200,height=160);page.insert_text((20,30),'PLANO SINTETICO')
            pdf=doc.tobytes()
        body['archivos'].append({'nombre':'plano.pdf','contenido_base64':base64.b64encode(pdf).decode()})
        self.ingreso=self.app.ingreso.registrar(body);self.caso=body['caso'];self.fp=self.ingreso['expediente_sha256']
        self.base={'caso':self.caso,'expediente_sha256':self.fp};self.revision=self.ingreso['revision_documental']
        self.service=self.app.preparacion
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')

    def request(self,*args,**kwargs):return httpfixtures.HTTPRevisionTests.request(self,*args,**kwargs)
    def url(self,kind,**extra):return '/api/visual/'+kind+'?'+urlencode({**self.base,**extra})
    def crop(self,archivo='L0001',**extra):return self.service.recortar({**self.base,'archivo':archivo,'pagina':1,'bbox':[.1,.1,.8,.8],'dpi':150,'etiqueta':'Región sintética',**extra})
    def prepare(self,*crops):return self.service.preparar({**self.base,'revision':self.revision,'recortes':[c['id'] for c in crops]})

    def test_pdf_raster_paquete_local_y_nuevas_versiones(self):
        with patch('subprocess.Popen',side_effect=AssertionError('Preparación sin procesos ni proveedor')):
            raster=self.crop();pdf=self.crop('L0002');packet=self.prepare(raster,pdf)
        self.assertEqual(raster['tipo_fuente'],'raster');self.assertEqual(pdf['tipo_fuente'],'pdf')
        self.assertIsNone(raster['escala_geometrica']);self.assertFalse(packet['transmision_externa'] or packet['aprueba_ingenieria'])
        self.assertEqual(len(packet['imagenes']),4);self.assertEqual(packet['estado'],'preparado_sin_envio')
        self.assertNotIn(str(self.app.raiz),json.dumps(packet));self.assertNotEqual(self.crop()['id'],raster['id'])
        history=self.service.listar(self.caso,expediente_sha256=self.fp)
        self.assertEqual(len(history['recortes']),3);self.assertTrue(history['paquetes'][0]['vigente'])
        other=self.service.revisar(self.base);self.assertNotEqual(other['id'],self.revision)
        self.assertEqual(other['resumen']['paginas_renderizadas'],2)

    def test_transformacion_previa_pendiente_y_rechazada_al_preparar(self):
        crop=self.crop();path=self.app.raiz/self.caso/'recortes'/crop['id']/'recorte.json'
        data=json.loads(path.read_bytes());data['pixel_a_pagina_visible'][0]*=2;path.write_text(json.dumps(data))
        pending=self.service.recorte(self.caso,crop['id'],expediente_sha256=self.fp)
        self.assertEqual(pending['estado'],'pendiente_revision_humana')
        with self.assertRaises(ValueError):self.prepare(crop)
        self.assertFalse((self.app.raiz/self.caso/'vision/solicitudes').exists())

    def test_imagen_paquete_y_original_alterados_sin_vigencia(self):
        crop=self.crop();packet=self.prepare(crop)
        image=self.app.raiz/self.caso/'recortes'/crop['id']/'recorte.png';raw=image.read_bytes();image.write_bytes(b'alterado')
        self.assertEqual(self.request('GET',self.url('imagen',version=crop['id']))[0],409)
        self.assertFalse(self.service.listar(self.caso,expediente_sha256=self.fp)['paquetes'][0]['vigente'])
        image.write_bytes(raw)
        original=self.app.raiz/self.caso/'originales/lamina-0001.png';original.write_bytes(b'alterado')
        self.assertEqual(self.request('GET',self.url('paquete',version=packet['id']))[0],409)

    def test_http_preparar_consultar_historial_y_campos(self):
        crop=self.crop();body={**self.base,'revision':self.revision,'recortes':[crop['id']]}
        self.assertEqual(self.request('POST','/api/visual/preparar',body,headers={'X-Revision-Session':'otro'})[0],403)
        self.assertEqual(self.request('POST','/api/visual/preparar',{**body,'proveedor':'externo'})[0],409)
        status,raw,_=self.request('POST','/api/visual/preparar',body);self.assertEqual(status,201,raw);packet=json.loads(raw)
        for kind,extra in (('historial',{}),('paquete',{'version':packet['id']}),('revision',{'version':self.revision})):
            status,raw,_=self.request('GET',self.url(kind,**extra));self.assertEqual(status,200,raw);self.assertNotIn(str(self.app.raiz),raw.decode())
        status,raw,headers=self.request('GET',self.url('imagen',version=crop['id']))
        self.assertEqual(status,200,raw);self.assertTrue(raw.startswith(b'\x89PNG'));self.assertEqual(headers['Content-Type'],'image/png')
        self.assertEqual(self.request('GET',self.url('recorte',version='../fuera'))[0],409)
        self.assertEqual(self.request('POST','/api/visual/preparar',{**body,'recortes':[crop['id'],crop['id']]})[0],409)
        # Tipos ajenos conservados en disco se traducen a un error HTTP, sin caída del handler.
        path=self.app.raiz/self.caso/'recortes'/crop['id']/'recorte.json';path.write_bytes(b'[]')
        self.assertEqual(self.request('GET',self.url('recorte',version=crop['id']))[0],409)

    def test_consulta_recorte_rechaza_cambio_de_original_durante_lectura(self):
        crop=self.crop();original=self.app.raiz/self.caso/'originales/lamina-0001.png'
        read=preparation._leer;altered=False
        def changing(path):
            nonlocal altered
            raw=read(path)
            if path.name=='recorte.png' and not altered:
                altered=True;original.write_bytes(b'alterado durante lectura')
            return raw
        with patch.object(preparation,'_leer',side_effect=changing):
            with self.assertRaises(ValueError):self.service.recorte(self.caso,crop['id'],expediente_sha256=self.fp)
