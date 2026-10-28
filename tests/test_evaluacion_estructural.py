"""Fronteras numéricas, aplicabilidad y aprobación de reglas fabricadas."""
import copy
import json
from pathlib import Path
import unittest

from draft2model.evaluacion_estructural import ErrorEvaluacion, evaluar_resultados, validar_reglas
from draft2model.resultados_estructurales import huella_declaracion, huella_resultados

EXAMPLES = Path(__file__).resolve().parents[1] / 'examples'


def fixture(name):
    return json.loads((EXAMPLES / name).read_text(encoding='utf-8'))


def approve(data):
    data['revision']['aprobacion']['huella_contenido'] = huella_declaracion(data)


class EvaluacionTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture('resultados_estructurales_sinteticos.json')
        self.rules = fixture('reglas_estructurales_sinteticas.json')

    def evaluate(self, **extra):
        options = {'huella_resultados_esperada': huella_resultados(self.data),
                   'huella_reglas_esperada': huella_declaracion(self.rules)}
        options.update(extra)
        return evaluar_resultados(self.data, self.rules, **options)

    def test_fixture_y_pureza_trazabilidad(self):
        before = copy.deepcopy((self.data, self.rules))
        result = self.evaluate()
        self.assertTrue(all(x['satisface_regla_configurada'] for x in result['evaluaciones']))
        self.assertEqual(result['motor']['tipo'], 'simulacion')
        self.assertTrue(result['datos_sinteticos'])
        self.assertEqual(result['huella_resultados'], huella_resultados(self.data))
        self.assertEqual(result['configuracion'], self.data['configuracion'])
        self.assertEqual(before, (self.data, self.rules))
        result['advertencias'].append('Cambio de salida.')
        self.assertEqual(before, (self.data, self.rules))

    def test_debajo_en_sobre_y_cinco_comparadores(self):
        for op in ('<', '<=', '==', '>=', '>'):
            self.rules['reglas'][0]['comparador'] = op; approve(self.rules)
            for value, relation in ((0.5, 'debajo'), (1.0, 'en'), (1.5, 'sobre')):
                self.data['resultados'][0]['valor'] = value
                output = self.evaluate()['evaluaciones'][0]
                self.assertEqual(output['relacion_limite'], relation)
                expected = {'<': value < 1, '<=': value <= 1, '==': value == 1, '>=': value >= 1, '>': value > 1}[op]
                self.assertEqual(output['satisface_regla_configurada'], expected)

    def test_formula_lineal_explicita(self):
        self.rules['reglas'][0]['formula'].update(factor=2.0, desplazamiento=0.25)
        approve(self.rules)
        item = self.evaluate()['evaluaciones'][0]
        self.assertEqual(item['valor_evaluado'], 1.25)
        self.assertEqual(item['relacion_limite'], 'sobre')

    def test_faltante_null_y_no_aplicable_diferenciados(self):
        self.data['resultados'][0].update(valor=None, motivo_omision='Modo omitido.')
        self.rules['reglas'][1]['aplicabilidad']['aplica'] = False
        self.rules['reglas'][2]['aplicabilidad']['ubicaciones'] = ['base-ausente']
        approve(self.rules)
        output = self.evaluate()['evaluaciones']
        self.assertEqual([x['estado'] for x in output], ['faltante', 'no_aplicable', 'faltante'])
        self.assertTrue(all(x['satisface_regla_configurada'] is None for x in output))
        self.assertEqual(output[0]['motivo'], 'Modo omitido.')

    def test_borrador_aprobacion_y_cambios_bloqueados(self):
        self.rules['revision'] = {'estado': 'borrador', 'aprobacion': None}
        self.assertTrue(validar_reglas(self.rules)['correcta'])
        with self.assertRaises(ErrorEvaluacion):
            self.evaluate()
        self.setUp(); self.rules['reglas'][0]['limite'] = 22
        with self.assertRaises(ErrorEvaluacion):
            self.evaluate()
        self.setUp()
        with self.assertRaises(ErrorEvaluacion):
            self.evaluate(huella_resultados_esperada='0'*64)
        with self.assertRaises(ErrorEvaluacion):
            self.evaluate(huella_reglas_esperada='0'*64)

    def test_procedencia_unidades_fuente_formula_y_fecha_invalidas(self):
        self.rules['datos_sinteticos'] = False; approve(self.rules)
        with self.assertRaises(ErrorEvaluacion):
            self.evaluate()
        self.setUp(); self.rules['reglas'][2]['unidad'] = 'N'; approve(self.rules)
        with self.assertRaises(ErrorEvaluacion):
            self.evaluate()
        for mutation in (lambda r: r['reglas'][0]['formula'].update(expresion='eval(x)'),
                         lambda r: r['reglas'][0]['fuente'].update(apartado=''),
                         lambda r: r['reglas'][0].update(limite=True),
                         lambda r: r['revision']['aprobacion'].update(fecha='ayer')):
            self.setUp(); mutation(self.rules)
            self.assertFalse(validar_reglas(self.rules)['correcta'])

    def test_desbordamiento_rechazado(self):
        self.rules['reglas'][0]['formula']['factor'] = 1e308; approve(self.rules)
        self.data['resultados'][0]['valor'] = 1e308
        with self.assertRaises(ErrorEvaluacion):
            self.evaluate()
        self.rules['reglas'][0]['formula']['factor'] = 10**308; approve(self.rules)
        self.data['resultados'][0]['valor'] = 10**308
        with self.assertRaises(ErrorEvaluacion):
            self.evaluate()


if __name__ == '__main__':
    unittest.main()
