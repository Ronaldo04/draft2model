"""Datos enteramente fabricados; no requiere ETABS ni carpetas privadas."""
import copy
import json
from pathlib import Path
import unittest

from draft2model.resultados_estructurales import (
    ErrorResultados, comparar_resultados, huella_declaracion, huella_resultados, validar_resultados,
)

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


def fixture():
    return json.loads((EXAMPLES / 'resultados_estructurales_sinteticos.json').read_text(encoding='utf-8'))


def tolerancias():
    return {v: {'absoluta': 0.01, 'relativa': 0.02, 'umbral_cero': 0.001, 'unidad': u}
            for v, u in fixture()['unidades'].items()}


def aprobar(data):
    data['revision'] = {'estado': 'aprobado', 'aprobacion': {
        'revisor_declarado': 'Fixture sintética', 'fecha': '2026-10-16',
        'motivo': 'Pruebas de software.', 'alcance': 'Solo fixture.',
        'huella_contenido': huella_declaracion(data)}}
    return data


def equivalencia(actual, referencia, tol=None):
    def ref(data):
        return {k: copy.deepcopy(data[k]) for k in ('corrida_id', 'geometria', 'configuracion')} | {'huella': huella_resultados(data)}
    return aprobar({'contrato': 'draft2model.equivalencia_resultados', 'version_contrato': '0.1.0',
        'id': 'equivalencia-fixture', 'actual': ref(actual), 'referencia': ref(referencia),
        'unidades': copy.deepcopy(actual['unidades']),
        'tolerancias': copy.deepcopy(tol if tol is not None else tolerancias()),
        'casos': [{'actual': a['id'], 'referencia': r['id'], 'justificacion': 'Mismo caso fabricado.'}
                  for a, r in zip(actual['casos'], referencia['casos'])],
        'hipotesis': {'actual': ['Base fabricada de prueba.'], 'referencia': ['Base fabricada de prueba.'],
                      'justificacion': 'Ambas fixtures fabricadas, sin análisis estructural.'},
        'justificacion': 'Equivalencia declarada únicamente para pruebas.'})


class ResultadosTests(unittest.TestCase):
    def compare(self, actual, reference, tol=None, eq=None, **options):
        return comparar_resultados(actual, reference, tol or tolerancias(), eq or equivalencia(actual, reference, tol),
            huella_actual_esperada=options.get('huella_actual', huella_resultados(actual)),
            huella_referencia_esperada=options.get('huella_referencia', huella_resultados(reference)))

    def test_fixture_valida_sin_mutar(self):
        data = fixture(); before = copy.deepcopy(data)
        self.assertTrue(validar_resultados(data)['correcta'])
        self.assertEqual(data, before)
        self.assertTrue(self.compare(data, data)['dentro_tolerancias'])

    def test_invalidos_no_numericos_identidad_y_omisiones(self):
        mutations = [lambda d: d['resultados'][0].update(valor=True),
            lambda d: d['resultados'][0].update(valor=float('nan')),
            lambda d: d['resultados'][0].update(valor=10**400),
            lambda d: d['resultados'][0].update(valor=None),
            lambda d: d['resultados'].append(copy.deepcopy(d['resultados'][0])),
            lambda d: d['resultados'][0].update(caso=[]),
            lambda d: d['unidades'].update(deriva=[]),
            lambda d: d['geometria'].update(sha256='bad'),
            lambda d: d.update(datos_sinteticos=False),
            lambda d: d.update(creado_utc='2026-10-16T12:00:00')]
        for mutation in mutations:
            data = fixture(); mutation(data)
            self.assertFalse(validar_resultados(data)['correcta'])

    def test_referencias_esperadas_y_huellas(self):
        data = fixture()
        expected = {k: copy.deepcopy(data[k]) for k in ('geometria', 'configuracion')}
        self.assertTrue(validar_resultados(data, referencias_esperadas=expected)['correcta'])
        expected['configuracion']['sha256'] = '0'*64
        self.assertFalse(validar_resultados(data, referencias_esperadas=expected)['correcta'])
        with self.assertRaises(ErrorResultados):
            self.compare(data, data, huella_actual='0'*64)

    def test_limite_tolerancia_y_absoluta_cerca_cero(self):
        reference = fixture(); reference['resultados'][2]['valor'] = 0
        actual = copy.deepcopy(reference); actual['resultados'][2]['valor'] = 0.01
        comparison = self.compare(actual, reference)
        row = next(x for x in comparison['comparaciones'] if x['variable'] == 'cortante')
        self.assertEqual(row['estado'], 'dentro_tolerancia')
        self.assertEqual(row['tolerancia_aplicada'], 0.01)
        self.assertTrue(row['cerca_de_cero'])
        actual['resultados'][2]['valor'] = 0.01000001
        self.assertFalse(self.compare(actual, reference)['dentro_tolerancias'])
        reference['resultados'][2]['valor'] = 100
        actual['resultados'][2]['valor'] = 102
        self.assertTrue(self.compare(actual, reference)['dentro_tolerancias'])
        actual['resultados'][2]['valor'] = 102.000001
        self.assertFalse(self.compare(actual, reference)['dentro_tolerancias'])

    def test_referencia_manual_equivalente_con_config_geometria_y_casos_distintos(self):
        actual = fixture(); reference = fixture()
        actual['motor'] = {'tipo': 'real', 'nombre': 'ETABS', 'version': 'declarada-A'}
        reference['motor'] = {'tipo': 'real', 'nombre': 'ETABS-manual', 'version': 'declarada-B'}
        reference['corrida_id'] = 'manual-002'
        reference['configuracion'] = {'id': 'manual-config', 'sha256': 'f'*64}
        reference['geometria'] = {'id': 'manual-geo', 'sha256': 'e'*64}
        reference['casos'][0]['id'] = 'MANUAL-X'
        for row in reference['resultados']:
            row['caso'] = 'MANUAL-X'
        eq = equivalencia(actual, reference)
        result = self.compare(actual, reference, eq=eq)
        self.assertTrue(result['dentro_tolerancias'])
        self.assertEqual(result['equivalencia']['referencia']['configuracion']['id'], 'manual-config')
        eq['hipotesis']['actual'].append('Cambio no revisado.')
        with self.assertRaises(ErrorResultados):
            self.compare(actual, reference, eq=eq)

    def test_no_comparar_simulacion_y_real_ni_unidades_incompatibles(self):
        actual = fixture(); reference = fixture()
        reference['motor']['tipo'] = 'real'
        with self.assertRaises(ErrorResultados):
            self.compare(actual, reference)
        reference = fixture(); reference['unidades']['cortante'] = 'N'
        reference['resultados'][2]['unidad'] = 'N'
        with self.assertRaises(ErrorResultados):
            self.compare(actual, reference)

    def test_equivalencia_obsoleta_mapeo_incompleto_y_tolerancias_invalidas(self):
        actual = fixture(); ref = fixture(); eq = equivalencia(actual, ref)
        ref['resultados'][0]['valor'] = 0.6
        with self.assertRaises(ErrorResultados):
            self.compare(actual, ref, eq=eq)
        eq = equivalencia(actual, ref); eq['casos'] = []; aprobar(eq)
        with self.assertRaises(ErrorResultados):
            self.compare(actual, ref, eq=eq)
        for value in (-1, True, float('inf')):
            tol = tolerancias(); tol['deriva']['absoluta'] = value
            with self.assertRaises(ErrorResultados):
                self.compare(actual, ref, tol=tol, eq=equivalencia(actual, ref))

    def test_faltante_no_pasa_y_omisiones_conservadas(self):
        actual = fixture(); ref = fixture()
        actual['resultados'][0].update(valor=None, motivo_omision='Modo no obtenido.')
        result = self.compare(actual, ref)
        self.assertFalse(result['comparacion_completa'])
        self.assertFalse(result['dentro_tolerancias'])
        self.assertIn('faltante', [x['estado'] for x in result['comparaciones']])
        self.assertEqual(result['omisiones_actuales'], actual['omisiones'])
        actual['resultados'] = []; ref['resultados'] = []
        self.assertFalse(self.compare(actual, ref)['dentro_tolerancias'])


if __name__ == '__main__':
    unittest.main()
