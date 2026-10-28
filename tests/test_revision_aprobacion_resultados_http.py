"""Rutas HTTP de la revisión propia declarada de resultados; fixture portable, transporte en memoria, sin red."""
import json
from pathlib import Path
import shutil
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from draft2model import evidencia_analisis as evidencia
from draft2model.revision_aprobacion_resultados import CONTROLES
from draft2model.revision_visual import RevisionLocal
from tests.fixture_etabs import extraer_evidencia
from tests import test_revision_visual as httpfixtures

CASO = 'demo-integrada-sintetica'
RESULTADO = '72c06efb3bfe477bb1fe565809aeddec'
ANALISIS = 'adf97fbc232141e8ae687872c0d71232'


class RevisionResultadosHTTPTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.bundle = extraer_evidencia(Path(temp.name).resolve()/'f'); self.app = RevisionLocal(self.bundle/'private')
        self.case = self.app.raiz/CASO; self.run = self.case/'analisis_etabs'/ANALISIS
        shutil.copytree(self.bundle/'analisis'/ANALISIS, self.run)
        self.fp = self.app.expediente(CASO)[2]
        self.server = SimpleNamespace(revision=self.app, token='prueba', origen='http://127.0.0.1:8766')
        for target in ('subprocess.Popen', 'urllib.request.urlopen', 'socket.create_connection', 'draft2model.proveedor_openai._http'):
            guard = patch(target, side_effect=AssertionError('Sin red ni procesos')); guard.start(); self.addCleanup(guard.stop)
        data = self.app.resultados.consultar_resultado(CASO, RESULTADO, expediente_sha256=self.fp)
        proof = evidencia.verificar_evidencia(self.app.raiz, CASO, RESULTADO, self.run)
        self.body = {'caso': CASO, 'resultado': RESULTADO, 'analisis': ANALISIS, 'expediente_sha256': self.fp,
                     'huella_resultados': data['huella'], 'huella_evidencia': evidencia.huella_evidencia(proof),
                     'revisor_declarado': 'Revisor declarado de prueba SINTÉTICA', 'fecha': '2026-10-18',
                     'alcance': 'Solo evidencia sintética de software y el resultado EST seleccionado.',
                     'motivo': 'Prueba HTTP del registro declarativo; sin certificación ni revisión física.',
                     'controles': {k: True for k in CONTROLES}, 'faltantes_criticos': [],
                     'observaciones': ['La omisión DY permanece visible.'], 'confirmacion_explicita': True}

    def request(self, *args, **kwargs):
        return httpfixtures.HTTPRevisionTests.request(self, *args, **kwargs)

    def get(self, kind, **params):
        status, raw, _ = self.request('GET', '/api/revision-resultados/'+kind+'?'+urlencode(params))
        return status, json.loads(raw)

    def fuentes(self, **cambios):
        return self.get('fuentes', **{'caso': CASO, 'resultado': RESULTADO, 'analisis': ANALISIS, 'expediente_sha256': self.fp, **cambios})

    def post(self, body, **kw):
        status, raw, _ = self.request('POST', '/api/revision-resultados/registrar', body, **kw)
        return status, json.loads(raw)

    def assertSeguro(self, value):
        text = json.dumps(value, ensure_ascii=False)
        for forbidden in (str(self.bundle), json.dumps(str(self.bundle))[1:-1], 'archivo_motor', 'id_proceso', '"ruta"'):
            self.assertNotIn(forbidden, text)

    def test_fuentes_registro_historial_y_consulta_exacta(self):
        status, source = self.fuentes(); self.assertEqual(status, 200, source)
        self.assertEqual(source['revision_resultados'], 'pendiente'); self.assertEqual(source['controles_requeridos'], list(CONTROLES))
        self.assertTrue(source['datos_sinteticos']); self.assertTrue(source['omisiones'] or source['filas_omitidas'])
        self.assertEqual(source['huella_resultados'], self.body['huella_resultados'])
        status, item = self.post(self.body); self.assertEqual(status, 201, item)
        self.assertEqual(item['revision_resultados'], 'revisados_declarados')
        self.assertFalse(item['aprueba_resultados'] or item['aprueba_informe'] or item['aprueba_ingenieria'])
        self.assertEqual((item['conformidad_normativa'], item['seguridad_estructural']), ('no_evaluada', 'no_certificada'))
        status, rows = self.get('historial', caso=CASO, resultado=RESULTADO, expediente_sha256=self.fp); self.assertEqual(status, 200, rows)
        self.assertFalse(rows['seleccion_automatica']); self.assertEqual([r['id'] for r in rows['versiones']], [item['id']])
        self.assertEqual(rows['versiones'][0]['resumen']['sha256_revision'], item['sha256_revision'])
        status, detail = self.get('version', caso=CASO, revision=item['id'], expediente_sha256=self.fp)
        self.assertEqual(status, 200, detail); self.assertEqual(detail, item)
        status, raw, _ = self.request('GET', '/api/resultado?'+urlencode({'caso': CASO, 'version': RESULTADO, 'expediente_sha256': self.fp}))
        self.assertEqual(json.loads(raw)['revision_resultados'], 'pendiente')  # el resultado nativo no se eleva
        self.assertSeguro([source, item, rows, detail])

    def test_rechazos_de_confirmacion_controles_faltantes_huellas_y_caso(self):
        casos = {'confirmacion_requerida': {'confirmacion_explicita': False},
                 'controles_explicitos_requeridos': {'controles': {**{k: True for k in CONTROLES}, 'revision_tecnica': False}},
                 'faltantes_criticos_declarados': {'faltantes_criticos': ['Falta el periodo fundamental.']},
                 'campos_invalidos': {'ruta': 'C:/x'}}
        for codigo, cambios in casos.items():
            with self.subTest(codigo=codigo):
                status, out = self.post({**self.body, **cambios})
                self.assertEqual((status, out.get('codigo')), (409, codigo)); self.assertSeguro(out)
        for cambios in ({'huella_resultados': '0'*64}, {'huella_evidencia': '0'*64}, {'caso': 'otro-caso'},
                        {'expediente_sha256': '0'*64}, {'analisis': '../x'}):
            with self.subTest(cambios=cambios):
                status, out = self.post({**self.body, **cambios}); self.assertEqual(status, 409, out); self.assertSeguro(out)
        self.assertEqual(self.fuentes(analisis='f'*32)[0], 409)
        self.assertFalse((self.case/'revisiones_resultados').exists() and any(
            p.name[:1] != '.' for p in (self.case/'revisiones_resultados').iterdir()))

    def test_edb_alterado_invalida_fuentes_consulta_e_historial(self):
        status, item = self.post(self.body); self.assertEqual(status, 201)
        edb = self.run/'analizado.edb'; original = edb.read_bytes(); edb.write_bytes(original+b'ALTERADO')
        status, out = self.fuentes(); self.assertEqual(status, 409); self.assertSeguro(out)
        status, out = self.get('version', caso=CASO, revision=item['id'], expediente_sha256=self.fp); self.assertEqual(status, 409)
        status, rows = self.get('historial', caso=CASO, resultado=RESULTADO, expediente_sha256=self.fp)
        self.assertEqual(status, 200); self.assertFalse(rows['versiones'][0]['vigente'])
        self.assertEqual(self.post(self.body)[0], 409)
        edb.write_bytes(original)
        self.assertEqual(self.get('version', caso=CASO, revision=item['id'], expediente_sha256=self.fp)[0], 200)

    def test_sesion_origen_host_y_limite(self):
        url = '/api/revision-resultados/fuentes?'+urlencode({'caso': CASO, 'resultado': RESULTADO, 'analisis': ANALISIS, 'expediente_sha256': self.fp})
        self.assertEqual(self.request('GET', url, headers={'X-Revision-Session': 'otra'})[0], 403)
        self.assertEqual(self.request('GET', url, headers={'Host': 'evil.test'})[0], 403)
        self.assertEqual(self.post(self.body, headers={'Origin': 'http://evil.test'})[0], 403)
        self.assertEqual(self.post(self.body, headers={'X-Revision-Session': 'otra'})[0], 403)
        status, raw, _ = self.request('POST', '/api/revision-resultados/registrar', {**self.body, 'observaciones': ['x'*(3*1024*1024)]})
        self.assertEqual(status, 413)


    def test_componente_servido_y_montado_una_vez(self):
        status, raw, headers = self.request('GET', '/revision_resultados.js')
        self.assertEqual(status, 200); self.assertIn(b'crearRevisionResultados', raw)
        self.assertTrue(headers['Content-Type'].startswith('text/javascript'))
        status, page, _ = self.request('GET', '/'); html = page.decode('utf-8')
        self.assertEqual(html.count('id="rrAnalisis"'), 1); self.assertEqual(html.count('src="/revision_resultados.js"'), 1)
        self.assertLess(html.index('src="/revision_resultados.js"'), html.index('src="/app.js"'))
        for i in ('rrControl_'+k for k in CONTROLES):
            self.assertIn('<input id="'+i+'" type="checkbox" disabled>', html)  # sin controles marcados
        status, app, _ = self.request('GET', '/app.js')
        self.assertEqual(app.count(b'crearRevisionResultados'), 1); self.assertIn(b'window.resultReviewControls?.()', app)

if __name__ == '__main__':
    unittest.main()
