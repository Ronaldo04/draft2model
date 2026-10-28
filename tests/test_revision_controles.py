"""Servicio y HTTP de controles postsolver sobre una lectura aceptada con transporte Python doble (sin ETABS)."""
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from draft2model import controles_analisis as nucleo
from urllib.parse import urlencode

from draft2model import evidencia_analisis as evidencia
from draft2model.revision_controles import ErrorControles, ServicioControles
from tests import test_revision_lecturas as lecturas
from tests import test_revision_visual as httpfixtures


def selector(tabla, campo='Drift', unidad='kN'):
    return {'tabla': tabla, 'campo_caso': 'OutputCase', 'campo': campo, 'unidad': unidad,
            'filtros': {'OutputCase': 'EST', 'Story': 'N1', 'Direction': 'X'}}


def controles():
    # Tablas del transporte DOBLE: 'Drift' no es una fuerza real; solo prueba la cadena de software.
    return [{'id': 'MOD', 'tipo': 'participacion_modal', 'caso': 'EST', 'aplica': False, 'critico': False,
             'motivo': 'EST estático de prueba: sin lectura modal en esta corrida sintética.',
             'fuente_criterio': 'SOLO prueba de software.', 'parametros': {}},
            {'id': 'EQ', 'tipo': 'equilibrio', 'caso': 'EST', 'aplica': True, 'critico': True,
             'motivo': 'Balance aritmético sintético entre dos tablas del doble.',
             'fuente_criterio': 'SOLO prueba de software; no tolerancia de ingeniería.',
             'parametros': {'cargas': [{'selector': selector('Story Drifts'), 'factor': 1}],
                            'reacciones': [{'selector': selector('Base Reactions'), 'factor': -1}],
                            'unidad': 'kN', 'tolerancia_absoluta': 0, 'tolerancia_relativa': 0, 'escala_referencia': 1}},
            {'id': 'SOLVER', 'tipo': 'advertencias_solver', 'caso': None, 'aplica': True, 'critico': True,
             'motivo': 'Revisar avisos de la fuente declarada de prueba.', 'fuente_criterio': 'SOLO prueba.',
             'parametros': {'codigos_admitidos': []}}]


class ControlesWebTests(unittest.TestCase):
    def setUp(self):
        self.lect = lecturas.LecturasWebTests('test_confirmacion_aceptacion_bytes_y_reinicio'); self.lect.setUp()
        self.addCleanup(self.lect.doCleanups)
        self.app = self.lect.app; self.caso = self.lect.caso; self.fp = self.app.expediente(self.caso)[2]
        self.app._lecturas = self.lect.service  # misma instancia que aceptó la lectura (fábrica doble)
        prepared = self.lect.prepare(tablas=['Story Drifts', 'Base Reactions']); self.lect.execute(prepared)
        self.job = self.lect.finish(prepared); self.assertEqual(self.job['estado'], 'aceptado')
        self.service = ServicioControles(self.app)
        self.server = SimpleNamespace(revision=self.app, token='prueba', origen='http://127.0.0.1:8766')

    def solver(self, advertencias=()):
        proof = evidencia.verificar_analisis_aceptado(self.app.raiz, self.caso, self.app.raiz/self.caso/'analisis_etabs'/self.job['analisis'])
        return json.dumps({'contrato': 'draft2model.avisos_solver_declarados', 'version': '0.1.0',
                           'corrida_analisis': self.job['analisis'], 'modelo_id': proof['modelo_id'],
                           'sha256_edb': proof['sha256_edb_analizado'], 'casos': ['EST'],
                           'origen_declarado': 'Fuente SOLO SINTÉTICA de prueba; no captura real del solver.',
                           'advertencias': list(advertencias)})

    def body(self, **cambios):
        return {'caso': self.caso, 'expediente_sha256': self.fp, 'lectura': self.job['id'], 'sha256_respuesta': self.job['sha256_respuesta'],
                'avisos_solver_json': self.solver(), 'revisor_declarado': 'Revisor declarado de prueba', 'fecha': '2026-10-18',
                'alcance': 'Solo cadena de software con datos sintéticos.', 'controles': controles(), 'confirmacion_explicita': True, **cambios}

    def request(self, *args, **kwargs):
        return httpfixtures.HTTPRevisionTests.request(self, *args, **kwargs)

    def test_registro_consulta_reinicio_y_proyeccion_sin_bytes(self):
        item = self.service.crear(self.body())
        c = item['contenido']
        self.assertEqual([r['estado'] for r in c['controles']], ['no_aplicable', 'satisfactorio', 'satisfactorio'])
        self.assertTrue(c['apto_proyeccion_controlado']); self.assertEqual(c['controles_solo_declarados'], ['SOLVER'])
        self.assertEqual(c['controles'][2]['verificacion'], 'declarada_no_verificada')
        self.assertEqual(item['estado_motor'], 'csi_4_terminado_no_equivale_a_controlado')
        self.assertFalse(item['aprueba_resultados']); self.assertTrue(item['datos_sinteticos'])
        text = json.dumps(item)
        self.assertNotIn('bytes_base64', text); self.assertNotIn(str(self.app.raiz), text)
        self.assertEqual(ServicioControles(self.app).consultar(self.caso, item['id'], expediente_sha256=self.fp), item)
        rows = self.service.listar(self.caso, expediente_sha256=self.fp)
        self.assertEqual(rows['versiones'][0]['id'], item['id']); self.assertFalse(rows['seleccion_automatica'])

    def test_sin_fuente_solver_critico_sin_datos_no_controlado(self):
        item = self.service.crear(self.body(avisos_solver_json=None))
        c = item['contenido']
        self.assertEqual(c['controles'][2]['estado'], 'sin_datos'); self.assertEqual(c['faltantes_criticos'], ['SOLVER'])
        self.assertFalse(c['apto_proyeccion_controlado'])
        item = self.service.crear(self.body(avisos_solver_json=self.solver([{'caso': 'EST', 'codigo': 'W9', 'texto': 'Aviso sintético.'}])))
        self.assertEqual(item['contenido']['controles'][2]['estado'], 'discrepante'); self.assertFalse(item['contenido']['apto_proyeccion_controlado'])

    def test_rechazos_de_vinculo_confirmacion_y_declaracion(self):
        from uuid import uuid4
        prepared = self.lect.prepare(tablas=['Story Drifts'], clave_solicitud=uuid4().hex)  # preparada, no aceptada
        for cambios in ({'confirmacion_explicita': False}, {'sha256_respuesta': '0'*64}, {'lectura': prepared['id']},
                        {'expediente_sha256': '0'*64}, {'lectura': '../x'}, {'extra': 1}, {'controles': controles()[1:]},
                        {'avisos_solver_json': '{"contrato":"otro"}'}, {'fecha': '2026-02-30'}):
            with self.subTest(cambios=cambios), self.assertRaises(ErrorControles):
                self.service.crear({**self.body(), **cambios})
        base = self.app.raiz/self.caso/'controles_analisis'
        self.assertFalse(base.exists() and any(p.name[:1] != '.' for p in base.iterdir()))

    def test_registro_o_lectura_alterados_invalidan(self):
        item = self.service.crear(self.body()); folder = self.app.raiz/self.caso/'controles_analisis'/item['id']
        doc = json.loads((folder/'controles.json').read_text(encoding='utf-8'))
        doc['controles'][1]['estado'] = 'discrepante'
        raw = (json.dumps(doc, sort_keys=True, ensure_ascii=False, indent=2)+'\n').encode()
        original = ((folder/'controles.json').read_bytes(), (folder/'version.json').read_bytes())
        (folder/'controles.json').write_bytes(raw)
        meta = json.loads(original[1]); import hashlib; meta['sha256_controles'] = hashlib.sha256(raw).hexdigest()
        (folder/'version.json').write_text(json.dumps(meta), encoding='utf-8')
        with self.assertRaises(ErrorControles):
            self.service.consultar(self.caso, item['id'], expediente_sha256=self.fp)  # hash rehecho pero no reproducible
        (folder/'controles.json').write_bytes(original[0]); (folder/'version.json').write_bytes(original[1])
        self.assertTrue(self.service.consultar(self.caso, item['id'], expediente_sha256=self.fp)['vigente'])
        respuesta = self.app.raiz/self.caso/'lecturas_etabs'/self.job['lectura_id']/'respuesta.json'
        respuesta.write_bytes(respuesta.read_bytes()+b' ')
        with self.assertRaises(ErrorControles):
            self.service.consultar(self.caso, item['id'], expediente_sha256=self.fp)
        self.assertFalse(self.service.listar(self.caso, expediente_sha256=self.fp)['versiones'][0]['vigente'])

    def test_fuente_cambia_despues_del_recalculo_no_es_vigente(self):
        item = self.service.crear(self.body())
        path = self.app.raiz/self.caso/'lecturas_etabs'/self.job['lectura_id']/'respuesta.json'
        original = path.read_bytes(); validar = nucleo.validar_controles
        def cambiar(*args, **kwargs):
            value = validar(*args, **kwargs)
            path.write_bytes(original+b'\n')
            return value
        try:
            with patch.object(nucleo, 'validar_controles', side_effect=cambiar):
                with self.assertRaises(ErrorControles):
                    self.service.consultar(self.caso, item['id'], expediente_sha256=self.fp)
        finally:
            path.write_bytes(original)
        self.assertTrue(self.service.consultar(self.caso, item['id'], expediente_sha256=self.fp)['vigente'])

    def test_http_rutas_sesion_y_limite(self):
        status, raw, _ = self.request('POST', '/api/controles/crear', self.body()); self.assertEqual(status, 201, raw)
        item = json.loads(raw)
        q = lambda kind, **kw: '/api/controles/'+kind+'?'+urlencode({'caso': self.caso, 'expediente_sha256': self.fp, **kw})
        status, raw, _ = self.request('GET', q('historial')); self.assertEqual(status, 200); self.assertEqual(json.loads(raw)['versiones'][0]['id'], item['id'])
        status, raw, _ = self.request('GET', q('version', version=item['id'])); self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)['sha256_controles'], item['sha256_controles']); self.assertNotIn(b'bytes_base64', raw)
        self.assertEqual(self.request('GET', q('historial'), headers={'X-Revision-Session': 'otra'})[0], 403)
        self.assertEqual(self.request('POST', '/api/controles/crear', self.body(), headers={'Origin': 'http://evil.test'})[0], 403)
        self.assertEqual(self.request('POST', '/api/controles/crear', {**self.body(), 'alcance': 'x'*(3*1024*1024)})[0], 413)
        status, raw, _ = self.request('POST', '/api/controles/crear', {**self.body(), 'confirmacion_explicita': False})
        self.assertEqual(status, 409); self.assertIn('Confirma', json.loads(raw)['error'])
        status, raw, _ = self.request('GET', '/controles.js'); self.assertEqual(status, 200); self.assertIn(b'/api/controles/crear', raw)


if __name__ == '__main__':
    unittest.main()
