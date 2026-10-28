"""Servicio de informes con contexto verificado y explicación; fixture sintética, dobles Python, sin red."""
import base64
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from draft2model.revision_contexto import ServicioContexto
from draft2model.revision_entregables import ServicioEntregables
from draft2model.revision_explicaciones import ServicioExplicaciones
from draft2model.revision_visual import RevisionLocal
from tests.fixture_etabs import extraer_evidencia
from tests.test_revision_contexto import CASO, RESULTADO, TEXTO, capa, corpus, reglas
from tests.test_revision_explicaciones import FRAGMENTO, Transporte, api


class InformeContextoTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.bundle = extraer_evidencia(Path(temp.name).resolve()/'fixture')
        self.app = RevisionLocal(self.bundle/'private')
        self.fp = self.app.expediente(CASO)[2]; self.case = self.app.raiz/CASO
        for target in ('draft2model.proveedor_openai._http', 'subprocess.Popen', 'urllib.request.urlopen',
                       'socket.create_connection'):
            guard = patch(target, side_effect=AssertionError('Sin red ni procesos')); guard.start(); self.addCleanup(guard.stop)
        env = patch.dict('os.environ', {'OPENAI_API_KEY': ''}); env.start(); self.addCleanup(env.stop)
        self.ctx = ServicioContexto(self.app); base = {'caso': CASO, 'expediente_sha256': self.fp}
        self.huella = self.app.resultados.consultar_resultado(CASO, RESULTADO, expediente_sha256=self.fp)['huella']
        self.corpus = self.ctx.registrar_corpus({**base, 'manifiesto_json': json.dumps(corpus()),
            'archivos': [{'nombre': 'fuente.txt', 'contenido_base64': base64.b64encode(TEXTO.encode()).decode()}]})
        self.rec = self.ctx.recuperar({**base, 'corpus': self.corpus['id'], 'consulta': 'deriva', 'limite': 3, 'resultado': RESULTADO})
        self.rules = self.ctx.registrar_reglas({**base, 'reglas_json': json.dumps(reglas(1.0))})
        self.ev = self.ctx.evaluar({**base, 'resultado': RESULTADO, 'reglas': self.rules['id'],
                                    'huella_resultados': self.huella, 'huella_reglas': self.rules['huella']})
        self.site = self.ctx.consultar_sitio({**base, 'sitio': self.ctx.registrar_sitio({**base, 'capa_json': json.dumps(capa())})['id'],
                                              'longitud': 1, 'latitud': 1, 'resultado': None})
        self.service = ServicioEntregables(self.app)

    def refs(self, explicacion=None, **cambios):
        return {'evaluacion': self.ev['id'], 'recuperacion': self.rec['id'], 'sitio': self.site['id'],
                'explicacion': explicacion, **cambios}

    def body(self, referencias=None, sitio=None):
        body = {'caso': CASO, 'resultado': RESULTADO, 'expediente_sha256': self.fp, 'analisis': None,
                'contexto': {'titulo': 'Informe sintético con contexto', 'hipotesis': ['Datos fabricados.'],
                             'faltantes': ['Revisión real pendiente.'], 'sitio': sitio}}
        if referencias is not None:
            body['referencias'] = referencias
        return body

    def explicacion(self, transporte=None, **derivados):
        service = ServicioExplicaciones(self.app, transporte)
        item = service.preparar({'caso': CASO, 'expediente_sha256': self.fp, 'resultado': RESULTADO, 'huella_resultados': self.huella,
                                 'derivados': {'recuperacion': self.rec['id'], 'evaluacion': self.ev['id'], 'sitio': self.site['id'], **derivados},
                                 'modelo': 'modelo-declarado-fixture', 'opciones': {'max_tokens': 512, 'timeout_s': 20},
                                 'clave_solicitud': format(len(service.listar(CASO)['trabajos'])+1, '032x')})
        service.ejecutar({'caso': CASO, 'trabajo': item['id'], 'huella_preparacion': item['huella_preparacion'],
                          'expediente_sha256': self.fp, 'confirmacion_explicita': True})
        thread = service._threads.get(item['id'])
        if thread:
            thread.join(30)
        return service.consultar(CASO, item['id'])

    def archivo(self, item, formato):
        return self.service.archivo(CASO, item['id'], formato, expediente_sha256=self.fp)

    def assertSinRutas(self, data):
        text = json.dumps(data, ensure_ascii=False)
        self.assertNotIn(str(self.app.raiz), text); self.assertNotIn(json.dumps(str(self.app.raiz))[1:-1], text)

    def test_recorrido_completo_llm_consulta_descarga_y_aprobacion(self):
        job = self.explicacion(Transporte(api()))
        self.assertEqual(job['estado'], 'completado_llm_verificado')
        item = self.service.crear(self.body(self.refs(job['id'])))
        self.assertEqual(item['referencias']['explicacion'], job['id'])
        self.assertEqual(item['explicacion']['modo'], 'llm_verificado'); self.assertFalse(item['explicacion']['generacion_llm_real'])
        self.assertEqual(item['contexto_verificado']['sitio']['id'], self.site['id'])
        self.assertFalse(item['aprueba_resultados']); self.assertEqual(item['conformidad_normativa'], 'no_evaluada')
        report = json.loads(self.archivo(item, 'json'))
        self.assertEqual(report['evaluacion'], self.ev['salida']); self.assertEqual(report['fuentes']['citas'][0]['texto'], FRAGMENTO)
        self.assertEqual(report['contexto']['sitio'], self.site['salida'])
        html = self.archivo(item, 'html').decode('utf-8')
        for text in ('CONSULTA DE COBERTURA COMPROBADA', 'TRANSPORTE DE PRUEBA, NO ES UNA LLAMADA REAL', FRAGMENTO, 'R-V / EST / X / base'):
            self.assertIn(text, html)
        self.assertTrue(self.archivo(item, 'pdf').startswith(b'%PDF'))
        child = self.service.aprobar({'caso': CASO, 'version': item['id'], 'expediente_sha256': self.fp,
                                      'sha256_informe': item['archivos']['informe.json'], 'revisor_declarado': 'Revisor declarado',
                                      'fecha': '2026-10-18', 'motivo': 'Revisión documental', 'confirmacion_explicita': True})
        self.assertEqual(child['estado'], 'aprobado'); self.assertEqual(child['padre']['id'], item['id'])
        self.assertEqual(child['referencias'], item['referencias']); self.assertFalse(child['aprueba_resultados'])
        approved = json.loads(self.archivo(child, 'json'))
        self.assertEqual({k: v for k, v in approved.items() if k != 'revision'}, {k: v for k, v in report.items() if k != 'revision'})
        rows = self.service.listar(CASO, RESULTADO, expediente_sha256=self.fp)['versiones']
        self.assertEqual(sorted(r['estado'] for r in rows), ['aprobado', 'borrador'])
        self.assertSinRutas([item, child, rows])

    def test_contingencia_y_abstencion(self):
        job = self.explicacion()  # sin clave ni transporte: contingencia determinística
        self.assertEqual(job['estado'], 'contingencia')
        item = self.service.crear(self.body(self.refs(job['id'])))
        html = self.archivo(item, 'html').decode('utf-8')
        self.assertIn('CONTINGENCIA DETERMINÍSTICA (api_restringida_a_revision_planos)', html); self.assertIn('NO ES GENERACIÓN LLM', html)
        self.assertNotIn('LLM REAL', html)
        vacia = self.ctx.recuperar({'caso': CASO, 'expediente_sha256': self.fp, 'corpus': self.corpus['id'],
                                    'consulta': 'capacidad portante geotécnica', 'limite': 3, 'resultado': None})
        item = self.service.crear(self.body(self.refs(recuperacion=vacia['id'], sitio=None, evaluacion=None)))
        report = json.loads(self.archivo(item, 'json'))
        self.assertEqual(report['fuentes']['citas'], []); self.assertIsNone(report['reglas'])
        self.assertIn('No se aportaron citas verificadas', self.archivo(item, 'html').decode('utf-8'))

    def test_fuente_o_trabajo_cambiados_invalidan_consulta_descarga_y_aprobacion(self):
        job = self.explicacion(Transporte(api()))
        item = self.service.crear(self.body(self.refs(job['id'])))
        rules = self.case/'contexto/reglas'/self.rules['id']/'reglas.json'
        original = rules.read_bytes(); rules.write_bytes(original+b' ')
        approve = {'caso': CASO, 'version': item['id'], 'expediente_sha256': self.fp, 'sha256_informe': item['archivos']['informe.json'],
                   'revisor_declarado': 'R', 'fecha': '2026-10-18', 'motivo': 'M', 'confirmacion_explicita': True}
        for call in (lambda: self.service.consultar(CASO, item['id'], expediente_sha256=self.fp),
                     lambda: self.archivo(item, 'pdf'), lambda: self.service.aprobar(approve)):
            with self.assertRaises(ValueError):
                call()
        self.assertFalse(self.service.listar(CASO, RESULTADO, expediente_sha256=self.fp)['versiones'][0]['vigente'])
        rules.write_bytes(original)
        self.assertEqual(self.service.consultar(CASO, item['id'], expediente_sha256=self.fp)['id'], item['id'])
        salida = self.app.raiz/'.explicaciones_web/trabajos'/job['id']/'salida.json'
        salida.write_bytes(salida.read_bytes().replace(b'0.0 kN', b'9.9 kN'))
        with self.assertRaises(ValueError):
            self.service.consultar(CASO, item['id'], expediente_sha256=self.fp)

    def test_referencias_ajenas_mal_formadas_o_texto_arbitrario(self):
        job = self.explicacion(Transporte(api()), sitio=None)
        for refs in (self.refs(job['id']),                          # explicación con otros derivados
                     self.refs(evaluacion=self.rec['id']),           # tipo cambiado
                     self.refs(sitio='../x'), {**self.refs(), 'texto': 'x'}, self.refs(explicacion='f'*32)):
            with self.subTest(refs=refs), self.assertRaises(ValueError):
                self.service.crear(self.body(refs))
        with self.assertRaises(ValueError):
            self.service.crear(self.body(self.refs(), sitio=self.site['salida']))  # sitio pegado
        with self.assertRaises(ValueError):
            self.service.crear({**self.body(self.refs()), 'explicacion': {'texto': 'verificado'}})
        original = self.ctx.consultar_derivado

        def otro_resultado(caso, version, *, expediente_sha256):
            value = original(caso, version, expediente_sha256=expediente_sha256)
            if value['tipo'] == 'recuperacion':
                value = {**value, 'fuentes': {**value['fuentes'], 'resultado': {'id': 'e'*32, 'huella': '0'*64}}}
            return value
        self.app.contexto = self.ctx
        with patch.object(self.ctx, 'consultar_derivado', side_effect=otro_resultado):
            with self.assertRaises(ValueError):
                self.service.crear(self.body(self.refs()))
        self.assertFalse((self.case/'informes').exists() and any(p.name[:1] != '.' for p in (self.case/'informes').iterdir()))

    def test_compatibilidad_sin_referencias(self):
        item = self.service.crear(self.body())
        self.assertNotIn('referencias', item); self.assertNotIn('explicacion', item)
        report = json.loads(self.archivo(item, 'json'))
        self.assertNotIn('contexto_verificado', report); self.assertEqual(report['evaluacion']['estado'], 'pendiente')


if __name__ == '__main__':
    unittest.main()
