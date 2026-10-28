"""Afines sintéticos: no leen planos, claves ni ejecutan servicios/ETABS."""
import copy
import json
import math
import unittest

from draft2model.digitizacion_calibrada import calibrar_digitizacion, ErrorDigitizacion, CONTRATO, VERSION


def caso(matriz=((8, 2, 10), (-3, 12, -7)), unidad='m', controles=False):
    fuente = {'original_id': 'sintetico', 'sha256': 'a'*64, 'pagina': 1,
              'dibujo_id': 'planta-a', 'bbox_pagina': [0.1, 0.2, 0.9, 0.8]}
    propuesta = {'contrato': CONTRATO, 'version': VERSION, 'id': 'sintetico-350',
                'fuente': copy.deepcopy(fuente),
                'plano': {'id': 'XY-1', 'ejes': ['x', 'y'], 'eje_constante': 'z',
                          'valor_constante': 260 if unidad == 'cm' else 2600 if unidad == 'mm' else 2.6,
                          'unidad_longitud': unidad},
                'limites': {'residuo_ajuste_max_m': 0.02, 'error_control_max_m': 0.03,
                            'incertidumbre_max_m': 0.1, 'localizacion_uv': 0.001,
                            'referencia_m': 0.005, 'condicion_max': 100,
                            'escala_min_m_por_uv': 0.001, 'escala_max_m_por_uv': 1000,
                            'coordenada_abs_max_m': 10000}, 'anclas': [], 'controles': [],
                'puntos': [{'id': 'P', 'uv_local': [0.3, 0.4], 'fuente': copy.deepcopy(fuente),
                            'plano_id': 'XY-1', 'relacionados': ['R0', 'R1']}]}
    registro = {}
    divisor = {'m': 1, 'cm': 100, 'mm': 1000}[unidad]
    coords = [[0, 0], [1, 0], [0, 1]]
    if controles:
        coords += [[0.2, 0.1], [0.6, 0.1], [0.2, 0.6]]
    for i, uv in enumerate(coords):
        ident = f'R{i}'
        registro[ident] = {'coordenadas': [divisor*(f[0]*uv[0]+f[1]*uv[1]+f[2]) for f in matriz],
                           'unidad_longitud': unidad, 'plano': copy.deepcopy(propuesta['plano']), 'fuente': copy.deepcopy(fuente),
                           'huella_resolucion': str(i)*64, 'referencias': [f'cota-{i}']}
        propuesta['anclas' if i < 3 else 'controles'].append(
            {'id': f'A{i}', 'punto_resuelto': ident, 'uv_local': uv,
             'fuente': copy.deepcopy(fuente), 'plano_id': 'XY-1'})
    return propuesta, fuente, registro


def ejecutar(c):
    p, f, r = c
    return calibrar_digitizacion(p, fuente_vigente=f, puntos_resueltos=r)


class DigitizacionCalibradaTests(unittest.TestCase):
    def rechaza(self, c, codigo=None):
        with self.assertRaises(ErrorDigitizacion) as cm:
            ejecutar(c)
        if codigo:
            self.assertEqual(cm.exception.codigo, codigo)
        json.dumps(cm.exception.detalles, allow_nan=False)
        return cm.exception

    def test_afin_escala_rotacion_cizalla_traslacion_y_sin_aprobacion(self):
        c = caso()
        antes = copy.deepcopy(c)
        r = ejecutar(c)
        p = r['puntos'][0]
        self.assertAlmostEqual(p['coordenadas_m']['x'], 13.2)
        self.assertAlmostEqual(p['coordenadas_m']['y'], -3.1)
        self.assertEqual(p['coordenadas_m']['z'], 2.6)
        self.assertAlmostEqual(p['uv_pagina'][0], 0.34)
        self.assertAlmostEqual(p['uv_pagina'][1], 0.44)
        self.assertTrue(r['calculo_posible'])
        self.assertFalse(r['exactitud_verificada_en_controles'])
        self.assertFalse(r['disponible_para_modelado'])
        self.assertEqual(r['revision'], {'estado': 'borrador', 'aprobacion': None})
        self.assertGreater(p['incertidumbre']['indicador_m'], 0)
        self.assertFalse(p['extrapolacion'])
        self.assertEqual(c, antes)
        json.dumps(r, allow_nan=False)

    def test_cm_mm_equivalentes_a_m_y_elevacion_explicita(self):
        base = ejecutar(caso())['puntos'][0]['coordenadas_m']
        for unidad in ['cm', 'mm']:
            c = caso(unidad=unidad)
            self.assertEqual(ejecutar(c)['puntos'][0]['coordenadas_m'], base)
        c = caso()
        c[0]['plano'].update(ejes=['x', 'z'], eje_constante='y')
        for punto in c[2].values():
            punto['plano'] = copy.deepcopy(c[0]['plano'])
        p = ejecutar(c)['puntos'][0]['coordenadas_m']
        self.assertEqual(p['y'], 2.6)
        self.assertAlmostEqual(p['z'], -3.1)

    def test_rotacion_de_90_grados_y_traslacion(self):
        r = ejecutar(caso(matriz=((0, -10, 5), (10, 0, -4))))
        p = r['puntos'][0]['coordenadas_m']
        self.assertAlmostEqual(p['x'], 1)
        self.assertAlmostEqual(p['y'], -1)
        self.assertAlmostEqual(r['transformacion']['escalas_singulares_m_por_uv'][0], 10)

    def test_controles_no_participan_en_ajuste_y_verifican_solo_sus_puntos(self):
        c = caso(controles=True)
        r = ejecutar(c)
        self.assertTrue(r['exactitud_verificada_en_controles'])
        self.assertEqual(len(r['anclas']), 3)
        matriz = r['transformacion']['matriz_local_a_m']
        c[2]['R3']['coordenadas'][0] += 0.04
        r = ejecutar(c)
        self.assertFalse(r['exactitud_verificada_en_controles'])
        self.assertEqual(r['transformacion']['matriz_local_a_m'], matriz)
        self.assertAlmostEqual(r['error_control_max_m'], 0.04)

    def test_un_control_no_acredita_exactitud(self):
        c = caso(controles=True)
        c[0]['controles'] = c[0]['controles'][:1]
        self.assertFalse(ejecutar(c)['exactitud_verificada_en_controles'])

    def test_controles_colineales_no_acreditan_exactitud(self):
        c = caso(controles=True)
        for i, item in enumerate(c[0]['controles']):
            item['uv_local'] = [0.2 + 0.1*i, 0.2]
            u, v = item['uv_local']
            c[2][item['punto_resuelto']]['coordenadas'] = [8*u+2*v+10, -3*u+12*v-7]
        self.assertFalse(ejecutar(c)['exactitud_verificada_en_controles'])

    def test_control_con_misma_resolucion_se_rechaza(self):
        c = caso(controles=True)
        c[2]['R3']['referencias'] = ['cota-0']
        self.rechaza(c, 'control_dependiente')

    def test_control_fisico_duplicado_no_es_independiente(self):
        c = caso(controles=True)
        c[2]['R3']['coordenadas'] = c[2]['R0']['coordenadas'][:]
        self.rechaza(c, 'referencia_repetida')

    def test_ajuste_con_ancla_extra_y_residuo(self):
        c = caso(controles=True)
        extra = c[0]['controles'].pop(0)
        c[0]['anclas'].append(extra)
        c[2]['R3']['coordenadas'][0] += 0.01
        r = ejecutar(c)
        self.assertGreater(r['residuo_ajuste_max_m'], 0)
        self.assertLess(r['residuo_ajuste_max_m'], 0.02)
        c[2]['R3']['coordenadas'][0] += 1
        error = self.rechaza(c, 'residuo_excesivo')
        self.assertGreater(error.detalles['residuo_max_m'], 0.02)

    def test_tres_anclas_no_son_validacion_aunque_residuo_cero(self):
        r = ejecutar(caso(matriz=((10, 0, 0), (0, 10, 0))))
        self.assertEqual(r['residuo_ajuste_max_m'], 0)
        self.assertFalse(r['exactitud_verificada_en_controles'])

    def test_fuente_modificada_cada_identidad(self):
        for campo, valor in [('sha256', 'b'*64), ('original_id', 'otro'), ('pagina', 2),
                             ('dibujo_id', 'detalle'), ('bbox_pagina', [0, 0, 1, 1])]:
            c = caso()
            c[1][campo] = valor
            self.rechaza(c, 'fuente_no_vigente')

    def test_ancla_de_otra_fuente_o_plano(self):
        for destino in ['ancla', 'registro', 'punto']:
            c = caso()
            item = c[0]['anclas'][0] if destino == 'ancla' else c[2]['R0'] if destino == 'registro' else c[0]['puntos'][0]
            if destino == 'registro':
                item['plano']['valor_constante'] += 1
            else:
                item['plano_id'] = 'otro'
            self.rechaza(c, 'fuente_mezclada')

    def test_anclas_fuente_sha_o_bbox_distinto_no_se_mezclan(self):
        for campo, valor in [('sha256', 'b'*64), ('pagina', 2), ('dibujo_id', 'detalle'),
                             ('bbox_pagina', [0, 0, 1, 1])]:
            c = caso(); c[0]['anclas'][0]['fuente'][campo] = valor
            self.rechaza(c, 'fuente_mezclada')

    def test_no_reutiliza_plano_con_igual_id_y_otra_cota(self):
        c = caso(); c[2]['R1']['plano']['valor_constante'] = 5
        self.rechaza(c, 'fuente_mezclada')

    def test_booleano_no_suplanta_pagina_entera_en_referencia(self):
        c = caso(); c[0]['anclas'][0]['fuente']['pagina'] = True
        self.rechaza(c, 'pagina')

    def test_uv_fuera_del_dibujo(self):
        for coleccion in ['anclas', 'puntos']:
            c = caso()
            c[0][coleccion][0]['uv_local'] = [1.001, 0.5]
            self.rechaza(c, 'fuera_dibujo')

    def test_anclas_colineales_y_casi_colineales(self):
        for y in [0, 1e-10]:
            c = caso()
            c[0]['anclas'][2]['uv_local'] = [0.5, y]
            self.rechaza(c, 'anclas_degeneradas')

    def test_transformacion_degenerada_o_fuera_escala(self):
        for m in [((10, 5, 0), (0, 0, 0)), ((10000, 0, 0), (0, 10, 0))]:
            c = caso(matriz=m, controles=True)
            c[0]['anclas'].append(c[0]['controles'].pop(0))
            c[0]['controles'] = []
            self.rechaza(c, 'transformacion_degenerada')

    def test_limites_no_positivos_nan_bool_y_desconocidos(self):
        for campo in caso()[0]['limites']:
            for valor in [0, -1, float('nan'), float('inf'), True, 10**1000]:
                c = caso(); c[0]['limites'][campo] = valor
                self.rechaza(c, 'numero')
        c = caso(); c[0]['limites']['inventado'] = 1
        self.rechaza(c, 'contrato')

    def test_limite_fisico_y_faltantes(self):
        c = caso(); c[0]['limites']['coordenada_abs_max_m'] = 2
        self.rechaza(c, 'limite_fisico')
        c = caso(); del c[0]['plano']['valor_constante']
        self.rechaza(c, 'contrato')
        c = caso(); c[0]['anclas'] = c[0]['anclas'][:2]
        self.rechaza(c, 'anclas_insuficientes')

    def test_extrapolacion_e_incertidumbre_fuera_de_limite(self):
        c = caso(); c[0]['puntos'][0]['uv_local'] = [1, 1]
        c[0]['limites']['incertidumbre_max_m'] = 0.001
        p = ejecutar(c)['puntos'][0]
        self.assertTrue(p['extrapolacion'])
        self.assertFalse(p['incertidumbre']['dentro_limite'])
        self.assertGreater(p['incertidumbre']['amplificacion'], 1)

    def test_huella_cubre_coordenadas_resueltas_y_referencias(self):
        c = caso(); h = ejecutar(c)['huella_entrada']
        c[2]['R0']['referencias'] = ['otra-cota']
        self.assertNotEqual(ejecutar(c)['huella_entrada'], h)
        self.assertEqual(ejecutar(c)['huella_entrada'], ejecutar(c)['huella_entrada'])

    def test_rechaza_aprobacion_inyectada_y_unidad_omitida(self):
        c = caso(); c[0]['revision'] = {'estado': 'aprobado'}
        self.rechaza(c, 'contrato')
        c = caso(); del c[2]['R0']['unidad_longitud']
        self.rechaza(c, 'contrato')

    def test_no_finito_en_punto_y_esquema_hostil(self):
        c = caso(); c[2]['R0']['coordenadas'][0] = float('nan')
        self.rechaza(c, 'numero')
        for valor in [None, [], {}, True]:
            c = caso(); c[0]['plano']['unidad_longitud'] = valor
            self.rechaza(c)


if __name__ == '__main__':
    unittest.main()
