"""Reutilización pura por contexto: fuente completa, aislamiento, límites y conservación exacta."""
import copy
import unittest
from unittest.mock import patch
from draft2model import particion_superficies as ps
from tests.test_contexto_particion_284 import fixture


class CacheParticiones(unittest.TestCase):
    def setUp(self):
        self.g=fixture();self.ctx=ps._ContextoGeometria(self.g)

    def run_part(self, g=None):
        return ps.particionar_superficie(self.g if g is None else g,'S1',_contexto=self.ctx)

    def test_acierto_con_fuente_completa_y_sin_recalculo(self):
        expected=ps.particionar_superficie(self.g,'S1')
        first=self.run_part()
        with patch.object(self.ctx,'verificar',wraps=self.ctx.verificar) as verify:
            with patch.object(ps,'_area2',side_effect=AssertionError('No repetir cálculo puro')):
                second=self.run_part()
            verify.assert_called_once_with(self.g)
        self.assertEqual(first,expected);self.assertEqual(second,expected)
        self.assertEqual(list(first),list(second))

    def test_resultado_mutable_no_contamina_el_siguiente(self):
        first=self.run_part();expected=copy.deepcopy(first)
        first['nodos'][0]['xyz_m'][0]=123
        first['celdas'].clear()
        self.assertEqual(self.run_part(),expected)

    def test_fuente_mutada_no_usa_cache(self):
        self.run_part()
        for kind in ('numero','tipo','metadatos'):
            g=copy.deepcopy(self.g)
            if kind=='numero':g['vertices'][0]['x']=3.
            elif kind=='tipo':g['vertices'][0]['x']=False
            else:g['procedencia']['descripcion']='Otra fuente'
            with self.subTest(kind=kind),self.assertRaises(ps.ErrorParticion):self.run_part(g)

    def test_corrupcion_se_descarta_y_recalcula(self):
        expected=self.run_part();raw,digest,weight=self.ctx._particiones['S1']
        self.ctx._particiones['S1']=(raw+b' ',digest,weight)
        with patch.object(ps,'_area2',wraps=ps._area2) as calc:
            self.assertEqual(self.run_part(),expected)
            self.assertGreater(calc.call_count,0)
        self.assertEqual(self.ctx._particiones_bytes,weight)

    def test_aciertos_concurrentes_son_copias_independientes(self):
        from concurrent.futures import ThreadPoolExecutor
        expected=self.run_part();weight=self.ctx._particiones_bytes
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda _:self.run_part(),range(12)))
        self.assertTrue(all(x==expected for x in results))
        results[0]['nodos'].clear()
        self.assertEqual(results[1],expected)
        self.assertEqual(self.ctx._particiones_bytes,weight)

    def test_limite_y_contextos_independientes(self):
        with patch.object(ps,'MAX_PARTICIONES_BYTES',1):
            expected=self.run_part()
            self.assertEqual(self.ctx._particiones_bytes,0)
            self.assertFalse(self.ctx._particiones)
        self.assertEqual(self.run_part(),expected)
        other=ps._ContextoGeometria(self.g)
        self.assertFalse(other._particiones)
        self.assertIsNot(other._particiones,self.ctx._particiones)

    def test_lru_expulsa_y_recalcula_sin_perder_geometria(self):
        g=copy.deepcopy(self.g);ids=[]
        for vertex in list(g['vertices']):
            item=copy.deepcopy(vertex);item['id']+='2';item['x']+=2.
            ids.append(item['id']);g['vertices'].append(item)
        surface=copy.deepcopy(g['superficies'][0]);surface['id']='S2';surface['vertices']=ids
        g['superficies'].append(surface);ctx=ps._ContextoGeometria(g)
        self.assertTrue(ctx._validacion.consistente)
        with patch.object(ps,'MAX_PARTICIONES_ENTRADAS',1):
            first=ps.particionar_superficie(g,'S1',_contexto=ctx)
            ps.particionar_superficie(g,'S2',_contexto=ctx)
            self.assertEqual(list(ctx._particiones),['S2'])
            with patch.object(ps,'_area2',wraps=ps._area2) as calc:
                self.assertEqual(ps.particionar_superficie(g,'S1',_contexto=ctx),first)
                self.assertGreater(calc.call_count,0)
            self.assertEqual(list(ctx._particiones),['S1'])
