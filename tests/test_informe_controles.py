"""Informe con controles postsolver seleccionados: opt-in exacto, revalidación, aprobación hija y compatibilidad.

La proyección de controles se construye con el núcleo real ligado a la evidencia del resultado; solo se
sustituye ServicioControles.consultar (la cadena lectura→controles real está en test_revision_controles).
"""
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from draft2model import controles_analisis as nucleo
from draft2model.evidencia_analisis import verificar_evidencia
from draft2model.revision_controles import ErrorControles, proyeccion_publica
from draft2model.revision_entregables import ServicioEntregables
from draft2model.revision_visual import RevisionLocal
from tests.fixture_etabs import extraer_evidencia

CASO = 'demo-integrada-sintetica'; RESULTADO = '72c06efb3bfe477bb1fe565809aeddec'; ANALISIS = 'adf97fbc232141e8ae687872c0d71232'
CID = 'c'*32; LECTURA = 'e'*32


def enc(v): return json.dumps(v, ensure_ascii=False).encode('utf-8')


class InformeControlesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        bundle = extraer_evidencia(Path(temp.name).resolve()/'f'); self.app = RevisionLocal(bundle/'private')
        self.run = self.app.raiz/CASO/'analisis_etabs'/ANALISIS; shutil.copytree(bundle/'analisis'/ANALISIS, self.run)
        self.fp = self.app.expediente(CASO)[2]; self.service = ServicioEntregables(self.app)
        for target in ('subprocess.Popen', 'urllib.request.urlopen', 'socket.create_connection'):
            guard = patch(target, side_effect=AssertionError('Sin red ni procesos')); guard.start(); self.addCleanup(guard.stop)
        ev = verificar_evidencia(self.app.raiz, CASO, RESULTADO, self.run)
        modelo = {'id': ev['modelo']['modelo_id'], 'sha256_edb': ev['analisis']['sha256_edb_analizado']}
        tables = [{'clave': 'Base Reactions', 'version_tabla': 1, 'campos': ['OutputCase', 'FX'], 'filas': [{'OutputCase': 'EST', 'FX': '-10'}]},
                  {'clave': 'Cargas_SOLO_DOBLE', 'version_tabla': 1, 'campos': ['OutputCase', 'FX'], 'filas': [{'OutputCase': 'EST', 'FX': '10'}]}]
        raw = enc({'contrato': 'draft2model.etabs_respuesta', 'version_contrato': '0.1.0', 'operacion': 'leer_tablas', 'estado': 'ok',
                   'modo_ejecucion': 'doble', 'id_solicitud': 'd'*32, 'avisos': ['Aviso del lector sintético.'],
                   'datos': {'corrida_analisis_id': ANALISIS, 'sha256_modelo_verificado': modelo['sha256_edb'], 'unidades': 'kN_m_C',
                             'casos': ['EST'], 'combinaciones': [], 'estado_casos': {'EST': 4}, 'tablas': tables}})
        sel = lambda t: {'tabla': t, 'campo_caso': 'OutputCase', 'campo': 'FX', 'unidad': 'kN', 'filtros': {'OutputCase': 'EST'}}
        decl = {'caso': CASO, 'expediente_sha256': self.fp, 'corrida_analisis': ANALISIS, 'lectura': 'd'*32, 'modelo': modelo,
                'datos_sinteticos': True, 'casos': ['EST'], 'sha256_respuesta': hashlib.sha256(raw).hexdigest(), 'sha256_avisos_solver': None,
                'revisor_declarado': 'Revisor declarado sintético', 'fecha': '2026-10-18', 'alcance': 'Solo software sintético.',
                'controles': [{'id': 'MOD', 'tipo': 'participacion_modal', 'caso': 'EST', 'aplica': False, 'critico': False,
                               'motivo': 'EST estático sintético.', 'fuente_criterio': 'Prueba.', 'parametros': {}},
                              {'id': 'EQ', 'tipo': 'equilibrio', 'caso': 'EST', 'aplica': True, 'critico': True, 'motivo': 'Balance sintético.',
                               'fuente_criterio': 'SOLO prueba.', 'parametros': {'cargas': [{'selector': sel('Cargas_SOLO_DOBLE'), 'factor': 1}],
                               'reacciones': [{'selector': sel('Base Reactions'), 'factor': 1}], 'unidad': 'kN', 'tolerancia_absoluta': 0.01,
                               'tolerancia_relativa': 0, 'escala_referencia': 10}},
                              {'id': 'SOLVER', 'tipo': 'advertencias_solver', 'caso': None, 'aplica': True, 'critico': True,
                               'motivo': 'Sin fuente solver aportada.', 'fuente_criterio': 'Prueba.', 'parametros': {'codigos_admitidos': []}}]}
        doc = nucleo.crear_controles(decl, raw)
        self.proj = {'id': CID, 'caso': CASO, 'expediente_sha256': self.fp, 'creado_utc': '2026-10-18T00:00:00+00:00',
                     'sha256_controles': hashlib.sha256(json.dumps(doc, sort_keys=True).encode()).hexdigest(), 'lectura': LECTURA,
                     'analisis': ANALISIS, 'modelo': modelo, 'casos': ['EST'], 'datos_sinteticos': True, 'vigente': True,
                     'contenido': proyeccion_publica(doc), 'estado_motor': 'csi_4_terminado_no_equivale_a_controlado',
                     'seleccion_automatica': False, 'aprueba_resultados': False, 'conformidad_normativa': 'no_evaluada', 'verificacion_profesional': False}
        self.estado = {'valido': True}

        def consultar(_self, caso, version, *, expediente_sha256):
            if not self.estado['valido'] or version != CID or caso != CASO or expediente_sha256 != self.fp:
                raise ErrorControles('Controles sin vigencia.')
            return copy.deepcopy(self.proj)
        guard = patch('draft2model.revision_controles.ServicioControles.consultar', consultar); guard.start(); self.addCleanup(guard.stop)

    def body(self, **extra):
        return {'caso': CASO, 'resultado': RESULTADO, 'expediente_sha256': self.fp, 'analisis': ANALISIS,
                'contexto': {'titulo': 'Informe con controles', 'hipotesis': ['Datos sintéticos.'], 'faltantes': ['Revisión real.'], 'sitio': None}, **extra}

    def ref(self): return {'id': CID, 'sha256_controles': self.proj['sha256_controles']}

    def test_opt_in_exacto_render_y_aprobacion_hija(self):
        item = self.service.crear(self.body(controles_analisis=self.ref()))
        self.assertEqual(item['controles_analisis_seleccionados'], self.ref())
        self.assertEqual(item['controles_analisis'], {'estado_global': 'sin_datos', 'apto_proyeccion_controlado': False})
        report = json.loads(self.service.archivo(CASO, item['id'], 'json', expediente_sha256=self.fp))
        self.assertEqual(report['controles_analisis']['id'], CID); self.assertNotIn('bytes_base64', json.dumps(report))
        html = self.service.archivo(CASO, item['id'], 'html', expediente_sha256=self.fp).decode('utf-8')
        for text in ('Controles internos postsolver seleccionados', 'NO APTO', 'CSI 4 solo indica terminación', 'Faltantes críticos: SOLVER',
                     'DATOS SINTÉTICOS', 'Avisos del lector (no son log del solver)'):
            self.assertIn(text, html)
        child = self.service.aprobar({'caso': CASO, 'version': item['id'], 'expediente_sha256': self.fp, 'sha256_informe': item['archivos']['informe.json'],
                                      'revisor_declarado': 'R', 'fecha': '2026-10-18', 'motivo': 'Documental', 'confirmacion_explicita': True})
        self.assertEqual(child['controles_analisis_seleccionados'], self.ref()); self.assertFalse(child['aprueba_resultados'])

    def test_rechazos_y_fuente_invalidada(self):
        for extra in ({'controles_analisis': {'id': CID, 'sha256_controles': '0'*64}}, {'controles_analisis': None},
                      {'controles_analisis': {**self.ref(), 'x': 1}}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.service.crear(self.body(**extra))
        with self.assertRaises(ValueError):
            self.service.crear(self.body(analisis=None, controles_analisis=self.ref()))
        otro = copy.deepcopy(self.proj); otro['analisis'] = 'f'*32; otro['contenido']['declaracion']['corrida_analisis'] = 'f'*32
        saved = self.proj; self.proj = otro
        with self.assertRaises(ValueError):
            self.service.crear(self.body(controles_analisis={'id': CID, 'sha256_controles': otro['sha256_controles']}))
        self.proj = saved
        item = self.service.crear(self.body(controles_analisis=self.ref()))
        self.estado['valido'] = False
        approve = {'caso': CASO, 'version': item['id'], 'expediente_sha256': self.fp, 'sha256_informe': item['archivos']['informe.json'],
                   'revisor_declarado': 'R', 'fecha': '2026-10-18', 'motivo': 'M', 'confirmacion_explicita': True}
        for call in (lambda: self.service.consultar(CASO, item['id'], expediente_sha256=self.fp),
                     lambda: self.service.archivo(CASO, item['id'], 'pdf', expediente_sha256=self.fp), lambda: self.service.aprobar(approve)):
            with self.assertRaises(ValueError):
                call()
        self.estado['valido'] = True
        self.assertEqual(self.service.consultar(CASO, item['id'], expediente_sha256=self.fp)['id'], item['id'])

    def test_compatibilidad_sin_controles(self):
        item = self.service.crear(self.body())
        self.assertNotIn('controles_analisis_seleccionados', item)
        report = json.loads(self.service.archivo(CASO, item['id'], 'json', expediente_sha256=self.fp))
        self.assertNotIn('controles_analisis', report)


if __name__ == '__main__':
    unittest.main()
