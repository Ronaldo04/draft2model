"""Asignaciones observadas en ETABS real; sin red ni nueva ejecución del motor."""
import copy
import json
from pathlib import Path
import unittest
from decimal import Decimal

from draft2model.relectura_presion import normalizar_tabla_no_uniforme, comparar_tabla_no_uniforme
from draft2model.cargas_liquidos_etabs import ErrorCargaLiquido


class RelecturaPresionTests(unittest.TestCase):
    def setUp(self):
        self.tabla = json.loads((Path(__file__).parent/'fixtures/tabla_presion_real_186.json').read_bytes())['tabla']

    def comparar(self, observada, esperada=None):
        return comparar_tabla_no_uniforme(esperada or self.tabla, observada,
                                         patrones=['HIDRO'], tolerancia_absoluta=1e-10)

    def test_native_22_triangles_and_independent_known_coefficients(self):
        original = copy.deepcopy(self.tabla)
        filas = normalizar_tabla_no_uniforme(self.tabla)['filas']
        self.assertEqual(len(filas), 22)
        self.assertEqual({r['UniqueName'] for r in filas}, {'CELDA'+str(i) for i in range(1,23)})
        for r in filas:
            self.assertEqual([r[k] for k in ('A','B','C','D')], [0,0,10,-15])
            self.assertEqual(r['Restriction'], 'Zero Positive Values')
            self.assertEqual(r['Dir'], 'Global-Y')
        result = self.comparar(self.tabla)
        self.assertTrue(result['asignaciones_coinciden'])
        self.assertFalse(result['equilibrio_verificado'])
        self.assertEqual(self.tabla, original)

    def test_reopened_n_mm_pressure_dimensions_and_column_order(self):
        t = copy.deepcopy(self.tabla)
        t['unidades'] = 'N_mm_C'
        width = len(t['campos'])
        for i in range(t['registros']):
            t['datos'][i*width+t['campos'].index('C')] = '.00001'
            t['datos'][i*width+t['campos'].index('D')] = '-.015'
        self.assertTrue(self.comparar(t)['asignaciones_coinciden'])
        # A mistaken force-only conversion must fail even if both signs match.
        t['datos'][t['campos'].index('C')] = '.01'
        self.assertFalse(self.comparar(t)['asignaciones_coinciden'])

    def test_coverage_missing_extra_direction_and_restriction(self):
        n = len(self.tabla['campos'])
        for tipo in ('faltante', 'extra', 'signo', 'direccion'):
            with self.subTest(tipo=tipo):
                t = copy.deepcopy(self.tabla)
                if tipo == 'faltante':
                    t['datos'] = t['datos'][n:]; t['registros'] -= 1
                elif tipo == 'extra':
                    row = t['datos'][:n]
                    row[t['campos'].index('UniqueName')] = 'OTRO'
                    t['datos'] += row; t['registros'] += 1
                else:
                    campo, valor = ('Restriction', 'Zero Negative Values') if tipo == 'signo' else ('Dir', 'Global-X')
                    t['datos'][t['campos'].index(campo)] = valor
                self.assertFalse(self.comparar(t)['asignaciones_coinciden'])

    def test_malformed_or_ambiguous_table_rejected(self):
        for tipo in ('duplicado','cortada','unidad','nan','columna','bool','version'):
            with self.subTest(tipo=tipo):
                t = copy.deepcopy(self.tabla)
                if tipo == 'duplicado':
                    t['datos'] += t['datos'][:len(t['campos'])]; t['registros'] += 1
                elif tipo == 'cortada': t['datos'].pop()
                elif tipo == 'unidad': t['unidades'] = 'kip_ft_F'
                elif tipo == 'columna': t['campos'][0] = 'UniqueName'
                elif tipo == 'bool': t['registros'] = True
                elif tipo == 'version': t['version'] = True
                else: t['datos'][t['campos'].index('C')] = 'NaN'
                with self.assertRaises(ErrorCargaLiquido): normalizar_tabla_no_uniforme(t)

    def test_explicit_scope_tolerance_and_unrelated_patterns(self):
        t = copy.deepcopy(self.tabla)
        row = t['datos'][:len(t['campos'])]
        row[t['campos'].index('LoadPattern')] = 'OTRO'
        t['datos'] += row; t['registros'] += 1
        r = self.comparar(t)
        self.assertTrue(r['asignaciones_coinciden']); self.assertEqual(r['registros_ajenos'], 1)
        for patterns, tolerance in (([],0),(['HIDRO'],True),(['HIDRO'],-1),(['HIDRO'],float('inf')),(['HIDRO','HIDRO'],0)):
            with self.assertRaises(ErrorCargaLiquido):
                comparar_tabla_no_uniforme(self.tabla,t,patrones=patterns,tolerancia_absoluta=tolerance)

    def test_all_supported_units_nonzero_abc_and_reordered_columns(self):
        canonical = {'version':1, 'unidades':'kN_m_C', 'registros':1,
                     'campos':['UniqueName','LoadPattern','Dir','A','B','C','D','Restriction'],
                     'datos':['P1','HIDRO','Gravity','2','-3','10','-15','Zero Positive Values']}
        for force, f in [('N',Decimal('.001')),('kN',Decimal(1))]:
            for length, l in [('m',Decimal(1)),('cm',Decimal('.01')),('mm',Decimal('.001'))]:
                t = copy.deepcopy(canonical); t['unidades'] = force+'_'+length+'_C'
                for k in ('A','B','C','D'):
                    i = t['campos'].index(k)
                    t['datos'][i] = str(Decimal(t['datos'][i])*l**(2 if k=='D' else 3)/f)
                t['campos'].reverse(); t['datos'].reverse()
                with self.subTest(units=t['unidades']):
                    self.assertTrue(self.comparar(t,canonical)['asignaciones_coinciden'])


if __name__ == '__main__': unittest.main()
