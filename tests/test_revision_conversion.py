"""Conversión web/HTTP sobre lecturas y planos exclusivamente sintéticos."""
import copy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from draft2model import revision_conversion as rc
from draft2model.revision_visual import RevisionLocal
from tests import test_conversion_geometria as fixture
from tests import test_revision_visual as httpfixture


class ConversionWebTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.ConversionTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.app=RevisionLocal(self.fixture.raiz);self.service=self.app.conversion
        self.caso=fixture.CASO;self.case=self.fixture.caso_dir;self.fp=self.app.expediente(self.caso)[2]
        self.body={'caso':self.caso,'extraccion':self.fixture.version.identificador,'expediente_sha256':self.fp,
            'manifiesto_json':json.dumps(self.fixture.manifiesto)}
        self.server=SimpleNamespace(revision=self.app,token='prueba',origen='http://127.0.0.1:8766')

    def request(self,*args,**kwargs):return httpfixture.HTTPRevisionTests.request(self,*args,**kwargs)
    def create(self,**changes):return self.service.crear({**self.body,**changes})
    def consult(self,item):return self.service.consultar(self.caso,item['id'],expediente_sha256=self.fp)
    def import_body(self,item,**changes):return {'caso':self.caso,'version':item['id'],'expediente_sha256':self.fp,
        'huella_conversion':item['huella_conversion'],'confirmacion_explicita':True,**changes}

    def test_crear_consultar_listar_importar_borrador_y_replay(self):
        before=self.app.geometrias(self.caso)
        with patch('subprocess.Popen',side_effect=AssertionError('Sin procesos externos')):
            item=self.create();self.assertEqual(self.app.geometrias(self.caso),before)
            self.assertEqual(self.consult(item),item)
            rows=self.service.listar(self.caso,expediente_sha256=self.fp)['versiones']
            self.assertEqual(rows,[{'id':item['id'],'extraccion':self.body['extraccion'],'vigente':True,'estado':'borrador'}])
            imported=self.service.importar_geometria(self.import_body(item))
            self.assertEqual(self.service.importar_geometria(self.import_body(item)),imported)
        self.assertEqual(imported['estado'],'borrador');self.assertIsNone(imported['aprobacion'])
        self.assertFalse(imported['disponible_para_modelado']);self.assertEqual(len(self.app.geometrias(self.caso)),len(before)+1)
        geo=self.app.geometria(self.caso,imported['geometria'])
        self.assertEqual(geo['datos'],item['geometria']);self.assertEqual(geo['datos']['revision'],{'estado':'borrador','aprobacion':None})
        self.assertTrue(item['trazabilidad']['datos_sinteticos']);self.assertNotIn(str(self.app.raiz),json.dumps(item))
        self.assertEqual((self.case/rc.CARPETA/item['id']/'manifiesto.json').read_bytes(),self.body['manifiesto_json'].encode())

    def test_no_sobrescribe_y_campos_huella_confirmacion_caso_id_rechazados(self):
        item=self.create();before={p.name:p.read_bytes() for p in (self.case/rc.CARPETA/item['id']).iterdir()}
        other=self.create();self.assertNotEqual(item['id'],other['id'])
        self.assertEqual(before,{p.name:p.read_bytes() for p in (self.case/rc.CARPETA/item['id']).iterdir()})
        for changes in ({'confirmacion_explicita':False},{'confirmacion_explicita':1},{'huella_conversion':'0'*64},
                {'version':'../otra'},{'caso':'otro'},{'expediente_sha256':'0'*64},{'extra':'x'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.service.importar_geometria(self.import_body(item,**changes))
        self.assertEqual(self.app.geometrias(self.caso),[])
        manifest=copy.deepcopy(self.fixture.manifiesto);manifest['caso']='otro'
        with self.assertRaises(ValueError):self.create(manifiesto_json=json.dumps(manifest))

    def test_artefactos_fuentes_exportacion_y_tipos_alterados_se_rechazan(self):
        item=self.create();base=self.case/rc.CARPETA/item['id'];trace=json.loads((base/'trazabilidad.json').read_bytes())
        paths=[base/name for name in ('manifiesto.json','geometria.json','trazabilidad.json','exportacion.json','web.json')]
        paths += [self.case/'extracciones_exportadas'/trace['exportacion_id']/'exportacion.json',
                  self.case/'extracciones'/self.body['extraccion']/'extraccion.json',
                  self.case/'originales/lamina-0001.pdf']
        for path in paths:
            raw=path.read_bytes();path.write_bytes(b'[]')
            try:
                with self.subTest(path=path),self.assertRaises(ValueError):self.consult(item)
                with self.assertRaises(ValueError):self.service.importar_geometria(self.import_body(item))
            finally:path.write_bytes(raw)
        self.assertEqual(self.app.geometrias(self.caso),[])

    def test_cambios_concurrentes_rechazados_en_consulta_y_creacion(self):
        item=self.create();path=self.case/rc.CARPETA/item['id']/'geometria.json';real=rc.validar_geometria
        def change(*args):
            result=real(*args);path.write_bytes(path.read_bytes()+b' ');return result
        with patch.object(rc,'validar_geometria',side_effect=change),self.assertRaises(ValueError):self.consult(item)
        real_convert=rc.convertir_lecturas;original=self.case/'originales/lamina-0001.pdf'
        def alter_original(*args):
            result=real_convert(*args);original.write_bytes(original.read_bytes()+b'CAMBIO');return result
        with patch.object(rc,'convertir_lecturas',side_effect=alter_original),self.assertRaises(ValueError):self.create()

    def test_importacion_interrumpida_no_repite_automaticamente(self):
        item=self.create();real=rc.g.importar_geometria
        def partial(*args):
            result=real(*args);raise OSError('Fallo después de publicar borrador')
        with patch.object(rc.g,'importar_geometria',side_effect=partial),self.assertRaises(ValueError):self.service.importar_geometria(self.import_body(item))
        count=len(self.app.geometrias(self.caso));self.assertEqual(count,1)
        with patch.object(rc.g,'importar_geometria',side_effect=AssertionError('No duplicar')),self.assertRaises(ValueError):self.service.importar_geometria(self.import_body(item))
        self.assertEqual(len(self.app.geometrias(self.caso)),count)

    def test_manifiesto_no_infiere_valores_y_rechaza_candidatos_pendientes(self):
        manifest=copy.deepcopy(self.fixture.manifiesto);manifest['niveles'][1]['cota']={'candidato':'C002'}
        with self.assertRaises(ValueError):self.create(manifiesto_json=json.dumps(manifest))
        manifest=copy.deepcopy(self.fixture.manifiesto);manifest['nodos'][0]['x']=None
        with self.assertRaises(ValueError):self.create(manifiesto_json=json.dumps(manifest))
        for value in ('{}','{"caso":"x","caso":"y"}', '[]'):
            with self.subTest(value=value),self.assertRaises(ValueError):self.create(manifiesto_json=value)
        self.assertFalse((self.case/rc.CARPETA).exists())

    def test_http_crear_consultar_importar_sesion_y_assets(self):
        self.assertEqual(self.request('POST','/api/conversion/crear',self.body,headers={'X-Revision-Session':'ajeno'})[0],403)
        status,raw,_=self.request('POST','/api/conversion/crear',self.body);self.assertEqual(status,201,raw);item=json.loads(raw)
        query=urlencode({'caso':self.caso,'version':item['id'],'expediente_sha256':self.fp})
        self.assertEqual(self.request('GET','/api/conversion?'+query)[0],200)
        self.assertEqual(self.request('GET','/api/conversiones?'+query)[0],200)
        self.assertEqual(self.request('POST','/api/conversion/importar-geometria',self.import_body(item,confirmacion_explicita=False))[0],409)
        status,raw,_=self.request('POST','/api/conversion/importar-geometria',self.import_body(item));self.assertEqual(status,201,raw)
        self.assertEqual(json.loads(raw)['estado'],'borrador');self.assertNotIn(str(self.app.raiz),raw.decode())
        status,raw,_=self.request('GET','/conversion.js');self.assertEqual(status,200);self.assertIn(b'd2m-geometry-created',raw)
        status,raw,_=self.request('GET','/');self.assertEqual(status,200);self.assertIn(b'conversionManifiesto',raw)


if __name__=='__main__':unittest.main()
