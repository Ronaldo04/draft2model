"""Geometría de superficies→versión→plan local; datos sintéticos sin motor."""
import copy
import json
import math
import unittest
from draft2model import gestion_geometria as gestion
from draft2model import gestion_planes as planes
from draft2model.geometria_superficies import migrar_a_superficies
from draft2model.plan_modelado import preparar_plan_modelado
from tests import test_plan_modelado as base
from tests import test_gestion_geometria as almacen


def extender(data):
    result = migrar_a_superficies(data)
    factor = {'m': 1, 'cm': 100, 'mm': 1000}[result['unidad_longitud']]
    coords = [(0,0,.5),(2,0,.5),(2,1,1.5),(0,1,1.5)]
    result['vertices'] = [{'id': 'V'+str(i), 'x': x*factor, 'y': y*factor, 'z': z*factor,
                           'procedencia': copy.deepcopy(result['procedencia'])}
                          for i,(x,y,z) in enumerate(coords)]
    result['superficies'] = [{'id': 'S1', 'vertices': ['V0','V1','V2','V3'],
                             'papel_geometrico': 'panel inclinado sintético; sin sección',
                             'procedencia': copy.deepcopy(result['procedencia'])}]
    return result


class PlanSuperficiesTests(unittest.TestCase):
    def test_plan_conserva_contorno_cota_intermedia_area_y_bloqueos(self):
        anterior = None
        for unidad in ('m','cm','mm'):
            source = extender(base.geometria(unidad)); before = copy.deepcopy(source)
            plan = preparar_plan_modelado(source)
            self.assertEqual(source, before)
            self.assertEqual(plan['version_contrato'], '0.2.0')
            self.assertEqual(plan['origen']['version_contrato'], '0.2.0')
            self.assertEqual(plan['cobertura'], 'completa')
            self.assertEqual(len(plan['superficies']), 3)
            panel = next(s for s in plan['superficies'] if 'superficie_id' in s)
            self.assertEqual(panel['vertices_m'][0], [0,0,.5])
            self.assertAlmostEqual(panel['area_geometrica_m2'], 2*math.sqrt(2))
            self.assertEqual(panel['vertices_ids'], ['V0','V1','V2','V3'])
            self.assertEqual(panel['procedencia'], source['superficies'][0]['procedencia'])
            self.assertFalse(plan['ejecutable_en_etabs'])
            self.assertTrue(any('integraci' in b for b in plan['bloqueos']))
            if anterior is not None: self.assertEqual(plan['superficies'], anterior)
            anterior = plan['superficies']

    def test_inconsistencia_no_publica_solo_los_muros_y_omite_panel(self):
        source = extender(base.geometria())
        source['superficies'][0]['vertices'][2] = 'AUSENTE'
        plan = preparar_plan_modelado(source)
        self.assertEqual(plan['cobertura'], 'sin_superficies')
        self.assertEqual(plan['superficies'], [])
        self.assertEqual(plan['estado_origen'], 'inconsistente')

    def test_version_guardada_y_plan_derivado_preservan_contrato_real(self):
        fixture = almacen.CasoGeometria(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        source = extender(fixture.completa())
        version = fixture.importar(fixture.escribir(source))
        consulta = gestion.consultar_version(fixture.raiz, almacen.CASO, version.identificador)
        self.assertTrue(consulta.comprobacion.correcta, consulta.comprobacion.problemas)
        meta = json.loads((version.ruta / gestion.ARCHIVO_METADATOS).read_text(encoding='utf-8'))
        self.assertEqual(meta['contrato_geometria']['version_contrato'], '0.2.0')
        output = planes.generar_plan_version(fixture.raiz, almacen.CASO, version.identificador)
        checked = planes.comprobar_plan(fixture.raiz, almacen.CASO, output.name)
        self.assertTrue(checked['correcta'], checked)
        self.assertEqual(json.loads((output/'plan.json').read_text(encoding='utf-8'))['version_contrato'], '0.2.0')
