"""Pruebas puras: los hosts y volúmenes son escenarios independientes declarados."""
import copy
import math
import unittest
from draft2model.masa_contenido import auditar, ErrorContabilidad


def entrada(suffix='', mode='patron_presion', height=2.22):
    # Oráculo independiente: prisma 2 x 2.15 x h, gamma10, g9.80665.
    volume = 2 * 2.15 * height
    pressure, exclusive = 'H'+suffix, 'M'+suffix
    s = {'deposito': 'D'+suffix, 'estado': 'escenario_sintetico_h_'+str(height),
         'fuente': 'fuente_sintetica_independiente', 'declaracion': 'L'+suffix,
         'volumen_m3': volume, 'peso_especifico_kn_m3': 10.,
         'gravedad_m_s2': 9.80665, 'nivel_libre_z_m': height,
         'modo': mode, 'patron_presion': pressure, 'patron_masa_exclusivo': exclusive,
         'peso_vertical_referencia_kn': 10*volume if mode == 'patron_masa_exclusivo' else None}
    host = {'declaracion': 'L'+suffix, 'patron': pressure, 'superficie': 'FONDO'+suffix,
            'peso_especifico_kn_m3': 10., 'nivel_libre_z_m': height,
            'fuerza_kn': [0., 0., -10*volume], 'fuerza_fuente_kn': [0., 0., -10*volume],
            'error_relativo_max': 0.}
    selected = pressure if mode == 'patron_presion' else exclusive
    return {'escenarios': [s], 'masa': {'metodo': 'patrones', 'masas_puntos': [],
             'gravedad_m_s2': 9.80665, 'factores_patrones': [{'patron': selected, 'factor': 1}]},
            'patrones': [{'id': p, 'multiplicador_peso_propio': 0} for p in (pressure, exclusive)],
            'hosts': [host], 'casos': [], 'combinaciones': []}


class LedgerTests(unittest.TestCase):
    def reject(self, data):
        with self.assertRaises(ErrorContabilidad):
            auditar(**data)

    def test_prisma_presion_oraculo_y_sin_mutacion(self):
        data = entrada(); original = copy.deepcopy(data); result = auditar(**data)
        self.assertEqual(data, original)
        self.assertAlmostEqual(result['peso_total_kn'], 95.46)
        self.assertAlmostEqual(result['escenarios'][0]['volumen_m3'], 9.546)
        self.assertAlmostEqual(result['masa_total_kn_s2_m'], 95.46/9.80665)
        self.assertFalse(result['crea_cargas']); self.assertFalse(result['ejecutable'])

    def test_vacio_explicito_preserva_factor_uno(self):
        data = entrada(height=0); result = auditar(**data)
        self.assertEqual(result['peso_total_kn'], 0); self.assertEqual(result['masa_total_kn_s2_m'], 0)
        data['masa']['factores_patrones'][0]['factor'] = 0; self.reject(data)

    def test_solo_pared_no_representa_peso_en_modo_presion(self):
        data = entrada(); host = data['hosts'][0]
        host['superficie'] = 'PARED'; host['fuerza_kn'] = [20., 0., 0.]
        host['fuerza_fuente_kn'] = [20., 0., 0.]; self.reject(data)

    def test_signo_incorrecto_o_integral_no_conservada(self):
        for change in ('signo', 'fuente', 'error'):
            data = entrada(); host = data['hosts'][0]
            if change == 'signo': host['fuerza_kn'][2] *= -1; host['fuerza_fuente_kn'][2] *= -1
            if change == 'fuente': host['fuerza_fuente_kn'][2] -= 1
            if change == 'error': host['error_relativo_max'] = 1e-3
            self.reject(data)

    def test_factores_parciales_excesivos_omitidos_bool(self):
        for factor in (.25, 2, 0, True, float('nan')):
            data = entrada(); data['masa']['factores_patrones'][0]['factor'] = factor; self.reject(data)
        data = entrada(); data['masa']['factores_patrones'] = []; self.reject(data)

    def test_alternativa_omitida_o_cero_permitida_doble_no(self):
        data = entrada(); data['masa']['factores_patrones'].append({'patron': 'M', 'factor': 0})
        auditar(**data)
        for value in (1, .25, -1):
            data['masa']['factores_patrones'][1]['factor'] = value; self.reject(data)

    def test_masas_explicitas_no_mezcladas(self):
        data = entrada(); data['masa']['masas_puntos'] = [{'punto': 'P1', 'masa': 10}]; self.reject(data)
        data = entrada(); data['masa']['metodo'] = 'explicita'; self.reject(data)

    def test_exclusivo_con_pared_y_peso_referencia(self):
        data = entrada(mode='patron_masa_exclusivo'); host = data['hosts'][0]
        host['superficie'] = 'PARED'; host['fuerza_kn'] = [20., 0., 0.]; host['fuerza_fuente_kn'] = [20., 0., 0.]
        self.assertAlmostEqual(auditar(**data)['peso_total_kn'], 95.46)
        data['escenarios'][0]['peso_vertical_referencia_kn'] = 80; self.reject(data)

    def test_exclusivo_excluye_presion_de_masa(self):
        data = entrada(mode='patron_masa_exclusivo')
        data['masa']['factores_patrones'].append({'patron': 'H', 'factor': 1}); self.reject(data)

    def test_no_doble_peso_en_caso_o_combinacion(self):
        data = entrada(mode='patron_masa_exclusivo')
        def case(ident, patterns):
            return {'id': ident, 'tipo': 'estatico_lineal', 'parametros': {'patrones': [
                {'patron': p, 'factor': 1} for p in patterns]}}
        data['casos'] = [case('C', ['H', 'M'])]; self.reject(data)
        data['casos'] = [case('CP', ['H']), case('CM', ['M'])]
        self.reject(data)  # Patrón exclusivo es solo masa, aun en un caso separado.
        for kind in ('lineal', 'envolvente'):
            data['combinaciones'] = [{'id': 'COMB', 'tipo': kind, 'casos': [
                {'caso': 'CP', 'factor': 1}, {'caso': 'CM', 'factor': 1}]}]; self.reject(data)
        data['combinaciones'] = [{'id': 'C0', 'tipo': 'lineal', 'casos': [
            {'caso': 'CP', 'factor': 1}, {'caso': 'CM', 'factor': 0}]}]; self.reject(data)
        data['casos'][1]['parametros']['patrones'][0]['factor'] = 0
        auditar(**data)  # Coeficiente cero en el propio caso no aplica peso.

    def test_declaracion_patron_gamma_nivel_y_fuente(self):
        for key, value in [('declaracion', 'OTRA'), ('patron', 'OTRO'),
                           ('peso_especifico_kn_m3', 9.81), ('nivel_libre_z_m', 3.)]:
            data = entrada(); data['hosts'][0][key] = value; self.reject(data)
        for key in ('fuente', 'estado', 'deposito', 'modo'):
            data = entrada(); data['escenarios'][0][key] = ''; self.reject(data)
        data = entrada(); data['hosts'] = []; self.reject(data)

    def test_dominio_numerico(self):
        for key in ('volumen_m3', 'peso_especifico_kn_m3', 'gravedad_m_s2', 'nivel_libre_z_m'):
            for value in (True, float('nan'), float('inf')):
                data = entrada(); data['escenarios'][0][key] = value; self.reject(data)
        for key in ('volumen_m3', 'peso_especifico_kn_m3', 'gravedad_m_s2'):
            data = entrada(); data['escenarios'][0][key] = -1; self.reject(data)
        for key in ('peso_especifico_kn_m3', 'gravedad_m_s2'):
            data = entrada(); data['escenarios'][0][key] = 0; self.reject(data)
        data = entrada(); data['escenarios'][0]['gravedad_m_s2'] = 10; self.reject(data)
        data = entrada(); data['escenarios'][0]['volumen_m3'] = 1e308; self.reject(data)

    def test_patron_existente_sin_peso_propio(self):
        data = entrada(); data['patrones'] = []; self.reject(data)
        data = entrada(); data['patrones'][0]['multiplicador_peso_propio'] = 1; self.reject(data)
        data = entrada(); data['escenarios'][0]['patron_masa_exclusivo'] = 'H'; self.reject(data)

    def test_dos_depositos_y_no_estados_simultaneos(self):
        a, b = entrada('1'), entrada('2', mode='patron_masa_exclusivo', height=1.)
        for key in ('escenarios', 'patrones', 'hosts'):
            a[key].extend(b[key])
        a['masa']['factores_patrones'].extend(b['masa']['factores_patrones'])
        result = auditar(**a)
        self.assertAlmostEqual(result['peso_total_kn'], 95.46+43.)
        self.assertEqual(len(result['escenarios']), 2)
        a['escenarios'][1]['deposito'] = 'D1'; self.reject(a)

    def test_host_y_factor_duplicados_y_hosts_ajenos(self):
        data = entrada(); data['hosts'].append(copy.deepcopy(data['hosts'][0])); self.reject(data)
        data = entrada(); data['masa']['factores_patrones'] *= 2; self.reject(data)
        data = entrada(); data['hosts'].extend(entrada('OTRO')['hosts']); self.reject(data)


if __name__ == '__main__':
    unittest.main()
