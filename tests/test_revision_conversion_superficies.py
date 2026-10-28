"""Lecturas→superficies→importación HTTP con trazabilidad y fuentes reproducibles."""
import hashlib
import json
import unittest
from draft2model import gestion_geometria as g
from draft2model import revision_conversion as rc
from tests import test_revision_conversion as base
from tests.test_conversion_superficies import manifiesto_superficie


class ConversionSuperficiesHTTPTests(unittest.TestCase):
    def setUp(self):
        self.f = base.ConversionWebTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.manifest = manifiesto_superficie(self.f.fixture.manifiesto)

    def crear(self):
        status, raw, _ = self.f.request('POST','/api/conversion/crear',
            {**self.f.body,'manifiesto_json':json.dumps(self.manifest)})
        self.assertEqual(status,201,raw)
        return json.loads(raw)

    def test_http_conserva_superficie_importa_solo_tras_accion_y_replay(self):
        item = self.crear()
        self.assertEqual(item['geometria']['version_contrato'],'0.2.0')
        self.assertEqual(len(item['geometria']['superficies']),1)
        self.assertEqual(self.f.app.geometrias(self.f.caso),[])
        status, raw, _ = self.f.request('POST','/api/conversion/importar-geometria', self.f.import_body(item))
        self.assertEqual(status,201,raw); imported=json.loads(raw)
        query=g.consultar_version(self.f.app.raiz,self.f.caso,imported['geometria'])
        self.assertTrue(query.comprobacion.correcta)
        self.assertEqual(query.geometria,item['geometria'])
        self.assertEqual(query.geometria['revision'],{'estado':'borrador','aprobacion':None})
        self.assertFalse(query.comprobacion.validacion['disponible_para_modelado'])
        self.assertEqual(self.f.service.importar_geometria(self.f.import_body(item))['geometria'],imported['geometria'])

    def test_artefactos_rehasheados_no_sustituyen_reproduccion_exacta(self):
        item=self.crear(); folder=self.f.case/rc.CARPETA/item['id']
        names=('geometria.json','trazabilidad.json','web.json')
        original={name:(folder/name).read_bytes() for name in names}
        for target in ('geometria','correspondencias'):
            with self.subTest(target=target):
                geometry=json.loads(original['geometria.json']); trace=json.loads(original['trazabilidad.json'])
                receipt=json.loads(original['web.json'])
                if target=='geometria':
                    for vertex in geometry['vertices']: vertex['x']+=1
                else: trace['correspondencias'][0]['modo']='otra_declaracion'
                raw=rc._bytes(geometry); (folder/'geometria.json').write_bytes(raw)
                trace['geometria_sha256']=hashlib.sha256(raw).hexdigest()
                trace['huella_contenido']=rc.huella_contenido(geometry)
                (folder/'trazabilidad.json').write_bytes(rc._bytes(trace))
                for name in ('geometria.json','trazabilidad.json'):
                    receipt['archivos'][name]=hashlib.sha256((folder/name).read_bytes()).hexdigest()
                (folder/'web.json').write_bytes(rc._bytes(receipt))
                with self.assertRaises(ValueError): self.f.consult(item)
                with self.assertRaises(ValueError): self.f.service.importar_geometria(self.f.import_body(item))
                self.assertEqual(self.f.app.geometrias(self.f.caso),[])
                for name,content in original.items(): (folder/name).write_bytes(content)
