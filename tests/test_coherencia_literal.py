"""Coherencia del literal declarado; estas pruebas no demuestran precisión OCR."""
import copy
import unittest

from draft2model.coherencia_literal import alertas_cota_literal
from draft2model.extraccion_preliminar import validar_extraccion
from tests.test_extraccion_preliminar import ejemplo


class CoherenciaLiteralTests(unittest.TestCase):
    def alerts(self, texto, valor=2.6, unidad='m', **extra):
        return {code for code, _ in alertas_cota_literal(dict(
            tipo='cota', texto_fuente=texto, valor_propuesto=valor, unidad=unidad, **extra))}

    def test_decimal_comma_sign_and_adjacent_unit(self):
        for text, value in [('2,60 m', 2.6), ('2.60m', 2.6), ('−.40 cm', -.4), ('+2.60 m.', 2.6)]:
            with self.subTest(text=text):
                unit = 'cm' if 'cm' in text else 'm'
                self.assertEqual(self.alerts(text, value, unit), set())

    def test_conversion_is_not_literal_reading(self):
        self.assertEqual(self.alerts('260 cm', 2.6, 'm'),
                         {'valor_sin_correspondencia_literal', 'unidad_sin_respaldo_literal'})

    def test_missing_units_are_not_silently_assumed(self):
        self.assertEqual(self.alerts('2.60'), {'unidad_sin_respaldo_literal'})
        self.assertEqual(self.alerts('2.60', unidad='desconocida'), set())

    def test_area_and_density_units_do_not_support_length(self):
        for text in ('2.60 m2', '2.60 m²', '2.60 m3', '2.60 m³', '2.60 m/s'):
            self.assertIn('unidad_sin_respaldo_literal', self.alerts(text))

    def test_uninterpreted_notation_does_not_create_false_numeric_conflicts(self):
        for text, value in [('1/2 cm', .5), ('2e3 cm', 2000), ('1,500 cm', 1500)]:
            self.assertNotIn('valor_sin_correspondencia_literal', self.alerts(text, value, 'cm'))

    def test_null_legacy_and_other_types_unchanged(self):
        self.assertEqual(self.alerts('ilegible', None), set())
        self.assertEqual(alertas_cota_literal({'tipo': 'cota', 'valor_propuesto': 2.6}), [])
        self.assertEqual(alertas_cota_literal({'tipo': 'elemento', 'texto_fuente': 'C-1',
                                            'valor_propuesto': 'C-1', 'unidad': 'no_aplica'}), [])

    def test_legacy_automatic_unit_without_literal_is_flagged_without_rewriting(self):
        candidate = {'tipo': 'cota', 'valor_propuesto': 2.6, 'unidad': 'm', 'metodo': {'tipo': 'vision'}}
        self.assertEqual(alertas_cota_literal(candidate)[0][0], 'unidad_sin_texto_fuente')
        self.assertNotIn('texto_fuente', candidate)
        candidate['metodo']['tipo'] = 'manual'
        self.assertEqual(alertas_cota_literal(candidate), [])

    def test_validation_exposes_alerts_without_changing_or_approving_candidates(self):
        data = ejemplo()
        candidate = data['candidatos'][0]
        candidate.update(tipo='cota', valor_propuesto=2.6, unidad='m', texto_fuente='260 cm')
        before = copy.deepcopy(data)
        result = validar_extraccion(data)
        self.assertTrue(result.consistente)
        codes = {a.codigo for a in result.advertencias}
        self.assertTrue({'valor_sin_correspondencia_literal', 'unidad_sin_respaldo_literal'} <= codes)
        self.assertEqual(data, before)


if __name__ == '__main__':
    unittest.main()
