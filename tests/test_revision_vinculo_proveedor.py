"""Integración de respuestas con dobles Python/HTTP; jamás usa red real."""
import json
import unittest
from unittest.mock import patch

from draft2model.revision_respuestas import ServicioRespuestas
from tests import test_revision_proveedor as fixture


class VinculoProveedorTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture.ProveedorWebTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.app=self.fixture.app;self.service=ServicioRespuestas(self.app)
        self.caso=self.fixture.caso;self.fp=self.fixture.fp

    def preparar(self,real_branch=False):
        provider=self.fixture.service(None if real_branch else fixture.Transporte(self.fixture.api()))
        self.app._proveedor=provider
        plan=provider.preparar(self.fixture.body())
        _,job=self.fixture.run_job(provider,plan)
        self.assertEqual(job['estado'],'completado_verificado')
        return job

    def body(self,job,**changes):
        return {'caso':self.caso,'expediente_sha256':self.fp,'trabajo':job['id'],
                'huella_preparacion':job['huella_preparacion'],'confirmacion_explicita':True,**changes}

    def consultar(self,ident):return self.service.consultar(self.caso,ident,expediente_sha256=self.fp)

    def test_vinculo_simulado_replay_y_sin_importacion(self):
        job=self.preparar()
        self.assertFalse((self.fixture.fixture.case/'extracciones').exists())
        item=self.service.vincular_proveedor(self.body(job))
        self.assertEqual(item,self.service.vincular_proveedor(self.body(job)))
        self.assertEqual(item['origen'],'proveedor_verificado');self.assertTrue(item['modo_prueba'])
        self.assertFalse(item['llamada_real_acreditada'] or item['transmision_externa'] or item['aprueba_ingenieria'])
        self.assertFalse(item['traslado_permitido'])
        self.fixture.assertSinPrivados(item)

    def test_confirmacion_hash_trabajo_no_completado_y_fuentes_alteradas(self):
        provider=self.fixture.service(fixture.Transporte(self.fixture.api()));self.app._proveedor=provider
        plan=provider.preparar(self.fixture.body())
        with self.assertRaises(ValueError):self.service.vincular_proveedor(self.body(plan))
        _,job=self.fixture.run_job(provider,plan)
        for changes in ({'confirmacion_explicita':False},{'confirmacion_explicita':1},
                        {'huella_preparacion':'0'*64},{'expediente_sha256':'0'*64},{'trabajo':'../otra'}):
            with self.subTest(changes=changes),self.assertRaises(ValueError):
                self.service.vincular_proveedor(self.body(job,**changes))
        item=self.service.vincular_proveedor(self.body(job))
        original=self.fixture.fixture.case/'vision/respuestas'/item['id']/'respuesta_original.json'
        original.write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError):self.consultar(item['id'])

    def test_rama_http_sustituida_conserva_respuesta_hasta_accion_separada(self):
        # Ejercita la rama sin transporte inyectado con _http reemplazado; no acredita llamada real.
        with patch.dict('os.environ',{'OPENAI_API_KEY':'clave-falsa-test'}),\
                patch('draft2model.proveedor_openai._http',return_value=self.fixture.api()) as http:
            job=self.preparar(real_branch=True)
        self.assertEqual(http.call_count,1)
        case=self.fixture.fixture.case
        self.assertFalse((case/'extracciones').exists())
        attempts=list((case/'vision/intentos_openai').glob('*/resultado.json'))
        report=json.loads(attempts[0].read_bytes())
        self.assertEqual(report['estado'],'respuesta_pendiente_revision');self.assertIsNone(report['version_importada'])
        item=self.service.vincular_proveedor(self.body(job))
        self.assertFalse((case/'extracciones').exists())
        imported=self.service.importar({'caso':self.caso,'expediente_sha256':self.fp,'respuesta':item['id'],
            'sha256_extraccion':item['sha256_extraccion'],'confirmacion_explicita':True})
        self.assertEqual(imported['estado'],'pendiente_revision')
        self.assertTrue((case/'extracciones'/imported['extraccion']).is_dir())
        with patch('draft2model.revision_respuestas.importar_extraccion',side_effect=AssertionError('No duplicar')):
            replay=self.service.importar({'caso':self.caso,'expediente_sha256':self.fp,'respuesta':item['id'],
                'sha256_extraccion':item['sha256_extraccion'],'confirmacion_explicita':True})
        self.assertEqual(replay,imported)

