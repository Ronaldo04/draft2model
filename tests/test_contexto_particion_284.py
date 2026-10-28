"""Comparación binaria completa del contexto de particiones (candidato Codex 282 integrado): tipos, mutaciones, ciclos, fallback.

Portado de seguimiento/probar_contexto_284.py contra el MÓDULO DEL PRODUCTO; las 5 comparaciones de planes completos no se
repiten (Codex las ejecutó sobre el mismo candidato, sin cambios).
"""
import copy
import unittest
from unittest.mock import patch

from draft2model import particion_superficies as ps
from tests.test_particion_superficies import geometria


def fixture():
    return geometria({'a': (0., 0., 0.), 'b': (1., 0., 0.), 'c': (1., 1., 0.), 'd': (0., 1., 0.)}, ('a', 'b', 'c', 'd'))


class ContextoParticionTests(unittest.TestCase):
    def test_misma_fuente_y_particion_completa(self):
        g = fixture(); ctx = ps._ContextoGeometria(g)
        self.assertEqual(ctx.verificar(g)[0], ps._sha(g))
        self.assertEqual(ps.particionar_superficie(g, 'S1', _contexto=ctx), ps.particionar_superficie(g, 'S1'))

    def test_cambios_numericos_y_de_tipo_se_rechazan(self):
        g = fixture(); ctx = ps._ContextoGeometria(g)
        for value in (True, 1, 1.1, float('nan')):
            changed = copy.deepcopy(g); changed['vertices'][1]['x'] = value
            with self.subTest(value=str(value)), self.assertRaises(ps.ErrorParticion):
                ctx.verificar(changed)

    def test_metadatos_y_ciclos_se_rechazan(self):
        g = fixture(); ctx = ps._ContextoGeometria(g)
        changed = copy.deepcopy(g); changed['procedencia']['descripcion'] = 'Otra fuente'
        with self.assertRaises(ps.ErrorParticion):
            ctx.verificar(changed)
        changed = copy.deepcopy(g); changed['revision']['ciclo'] = changed
        with self.assertRaises(ps.ErrorParticion):
            ctx.verificar(changed)

    def test_orden_distinto_equivalente_y_fallback_completo(self):
        g = fixture(); ctx = ps._ContextoGeometria(g)
        reordered = dict(reversed(list(g.items())))
        self.assertNotEqual(ps._binario_local(g), ps._binario_local(reordered))
        self.assertEqual(ctx.verificar(reordered)[0], ps._sha(g))      # cae a JSON canónico y se acepta como antes
        with patch.object(ps, '_binario_local', return_value=None):
            fallback = ps._ContextoGeometria(g)
            self.assertEqual(fallback.verificar(g)[0], ps._sha(g))
            changed = copy.deepcopy(g); changed['vertices'][1]['x'] = 2.
            with self.assertRaises(ps.ErrorParticion):
                fallback.verificar(changed)

    def test_fuente_no_mutada(self):
        g = fixture(); before = copy.deepcopy(g); ctx = ps._ContextoGeometria(g)
        for _ in range(3):
            ctx.verificar(g)
        self.assertEqual(g, before)


if __name__ == '__main__':
    unittest.main()
