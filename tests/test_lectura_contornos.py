"""Contrato de visión de contornos, con datos sintéticos propios sin I/O."""
import copy
import unittest

from draft2model import lectura_contornos as lc
from draft2model import contratos as c


def caso():
    proc = {'tipo': 'sintetico', 'descripcion': 'Referencia sintética resuelta.'}
    vertices = [{'id': ident, 'x': x, 'y': y, 'z': 0.0, 'procedencia': {**proc, 'referencias': ['COTA_'+ident]}}
                for ident, x, y in [('A', 0.0, 0.0), ('B', 10.0, 0.0), ('C', 0.0, 10.0)]]
    geo = {'contrato': c.CONTRATO_GEOMETRIA, 'version_contrato': '0.3.0', 'id': 'Caso357', 'unidad_longitud': 'm',
           'procedencia': proc, 'niveles': [], 'nodos': [], 'muros': [], 'vertices': vertices,
           'superficies': [{'id': 'BASE', 'vertices': ['A', 'B', 'C'], 'papel_geometrico': 'cara sintética existente', 'procedencia': proc}],
           'aberturas': [], 'faltantes': [{'descripcion': 'Observación previa conservada.'}],
           'revision': {'estado': 'borrador', 'aprobacion': None}}
    plano = {'id': 'PZ0', 'ejes': ['x', 'y'], 'eje_constante': 'z', 'valor_constante': 0.0, 'unidad_longitud': 'm', 'puntos_resueltos': ['A', 'B', 'C']}
    ctx = {'geometria': {'version_id': 'b'*32, 'sha256_geometria': '9'*64, 'huella_contenido': c.huella_contenido(geo),
                          'sha256_geometria_canonica': lc.huella(geo), 'unidad_longitud': 'm', 'datos_sinteticos': True},
           'planos': [plano], 'puntos_resueltos': ['A', 'B', 'C'], 'superficies': ['BASE'], 'frames': [], 'catalogo_vertices': copy.deepcopy(vertices)}
    drawing = {'id': 'D1', 'archivo_id': 'L1', 'pagina': 1, 'bbox_pagina': [0, 0, 1, 1], 'plano_id': 'PZ0',
               'anclas': [{'id': 'R'+ident, 'punto_resuelto': ident, 'uv_local': uv, 'evidencias': ['E1']}
                          for ident, uv in [('A', [0, 1]), ('B', [1, 1]), ('C', [0, 0])]],
               'controles': [], 'puntos': [{'id': ident, 'uv_local': [x/10, 1-y/10], 'relacionados': ['A', 'B', 'C'], 'evidencias': ['E1']}
                  for ident, x, y in [('N1', 6, 6), ('N2', 9, 6), ('N3', 9, 9), ('N4', 6, 9),
                                      ('H1', 7, 7), ('H2', 8, 7), ('H3', 8, 8), ('H4', 7, 8)]]}
    response = {'contrato': lc.CONTRATO, 'version_contrato': lc.VERSION, 'caso': 'Caso357',
                'evidencias': [{'id': 'E1', 'archivo_id': 'L1', 'pagina': 1, 'bbox_normalizada': [.05, .05, .95, .95], 'texto': 'Contorno y vano sintéticos con referencias legibles.'}],
                'dibujos': [drawing], 'elementos': [
                    {'id': 'CARA', 'tipo': 'losa', 'accion': 'nuevo', 'vertices': ['N1', 'N2', 'N3', 'N4'], 'dibujos': ['D1'], 'evidencias': ['E1']},
                    {'id': 'VIGA', 'tipo': 'viga', 'accion': 'nuevo', 'vertices': ['B', 'N3'], 'dibujos': ['D1'], 'evidencias': ['E1']}],
                'aberturas': [{'id': 'VANO', 'host': 'CARA', 'vertices': ['H1', 'H2', 'H3', 'H4'], 'dibujos': ['D1'], 'evidencias': ['E1']}],
                'faltantes': ['Faltante nuevo literal de la lectura.']}
    manifest = {'id': 'Caso357', 'archivos': [{'id': 'L1', 'sha256': 'a'*64}]}
    return geo, response, manifest, ctx


def validar(response=None, ctx=None):
    geo, raw, manifest, context = caso()
    return lc.validar_respuesta(response if response is not None else raw, manifest, {('L1', 1)}, ctx if ctx is not None else context)


class LecturaContornosTests(unittest.TestCase):
    def test_contrato_enriquecimiento_y_no_mutacion(self):
        geo, raw, manifest, ctx = caso(); antes = copy.deepcopy((raw, ctx))
        checked = lc.validar_respuesta(raw, manifest, {('L1', 1)}, ctx)
        self.assertEqual((raw, ctx), antes)
        self.assertEqual(checked['datos']['dibujos'][0]['fuente']['sha256'], 'a'*64)
        self.assertEqual(checked['datos']['dibujos'][0]['plano']['valor_constante'], 0)
        self.assertEqual(checked['revision'], {'estado': 'borrador', 'aprobacion': None})
        self.assertFalse(checked['ejecutable_etabs'])
        self.assertIn('No devuelvas coordenadas físicas', lc.instruccion('Caso357', ctx))

    def test_red_rechaza_metricas_cotas_y_campos_extra(self):
        for mutate in [lambda r:r.update(x=7), lambda r:r['dibujos'][0].update(cota=3),
                       lambda r:r['dibujos'][0]['puntos'][0].update(coordenadas_m=[1, 2, 3])]:
            raw = caso()[1]; mutate(raw)
            with self.assertRaises(ValueError): validar(raw)

    def test_planos_ids_paginas_y_evidencias_ajenos(self):
        for mutate in [lambda r:r['dibujos'][0].update(plano_id='INVENTADO'), lambda r:r['dibujos'][0].update(pagina=2),
                       lambda r:r['dibujos'][0]['anclas'][0].update(punto_resuelto='AJENO'),
                       lambda r:r['elementos'][0].update(evidencias=['AUSENTE']),
                       lambda r:r['elementos'][0].update(vertices=['N1', 'N2', 'AJENO'])]:
            raw = caso()[1]; mutate(raw)
            with self.assertRaises(ValueError): validar(raw)

    def test_bbox_y_uv_fuera_region(self):
        for mutate in [lambda r:r['evidencias'][0].update(bbox_normalizada=[0, 0, 2, 1]),
                       lambda r:r['dibujos'][0].update(bbox_pagina=[.1, .1, .9, .9]),
                       lambda r:r['dibujos'][0]['puntos'][0].update(uv_local=[1.01, .5])]:
            raw = caso()[1]; mutate(raw)
            with self.assertRaises(ValueError): validar(raw)

    def test_sin_anclas_suficientes_conserva_faltante_no_inventa(self):
        raw = caso()[1]; raw['dibujos'][0]['anclas'] = raw['dibujos'][0]['anclas'][:2]
        for p in raw['dibujos'][0]['puntos']: p['relacionados'] = ['A', 'B']
        result = validar(raw)
        self.assertTrue(result['advertencias']); self.assertEqual(len(result['datos']['dibujos'][0]['anclas']), 2)

    def test_controles_repetidos_no_fingen_independencia(self):
        raw = caso()[1]; raw['dibujos'][0]['controles'] = [copy.deepcopy(raw['dibujos'][0]['anclas'][0])]
        with self.assertRaises(ValueError): validar(raw)

    def test_catalogo_espacial_solo_contexto_y_ids_exactos(self):
        ctx = caso()[3]; ctx['catalogo_vertices'].pop()
        with self.assertRaises(ValueError): validar(ctx=ctx)

    def test_abertura_sin_host_y_frame_sin_dos_extremos(self):
        raw = caso()[1]; raw['aberturas'][0]['host'] = 'VIGA'
        with self.assertRaises(ValueError): validar(raw)
        raw = caso()[1]; raw['elementos'][1]['vertices'] = ['A', 'B', 'C']
        with self.assertRaises(ValueError): validar(raw)


if __name__ == '__main__': unittest.main()
