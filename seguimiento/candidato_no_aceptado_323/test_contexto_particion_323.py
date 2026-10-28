"""La captura rápida conserva tipos y acepta fuentes equivalentes con alias distintos."""
import copy
import unittest
from unittest.mock import patch
from draft2model import particion_superficies as ps
from tests.test_contexto_particion_284 import fixture


class CapturaFormato4(unittest.TestCase):
    def test_contexto_normal_conserva_acierto_binario_tras_validacion(self):
        g=fixture();ctx=ps._ContextoGeometria(g)
        self.assertEqual(ctx._captura_binaria,ps._binario_local(g))
        with patch.object(ps,'_canonico',side_effect=AssertionError('No fallback en un acierto binario')):
            self.assertEqual(ctx.verificar(g)[0],ctx._sha)

    def test_alias_internos_distintos_caen_a_comparacion_canonica(self):
        g=fixture();g['extra_captura']={'uno':[1,2,3],'dos':[1,2,3]}
        shared=copy.deepcopy(g);shared['extra_captura']['dos']=shared['extra_captura']['uno']
        self.assertNotEqual(ps._binario_local(g),ps._binario_local(shared))
        ctx=ps._ContextoGeometria(g)
        self.assertEqual(ctx.verificar(shared)[0],ps._sha(g))
        shared['extra_captura']['dos'][0]=True
        with self.assertRaises(ps.ErrorParticion):ctx.verificar(shared)

    def test_formato4_no_colapsa_numeros_ni_signos(self):
        values=[{'n':False},{'n':0},{'n':0.0},{'n':-0.0},{'n':1},{'n':1.0}]
        self.assertEqual(len({ps._binario_local(x) for x in values}),len(values))

    def test_particion_completa_identica_con_captura_anterior(self):
        import marshal
        g=fixture();new=ps.particionar_superficie(g,'S1',_contexto=ps._ContextoGeometria(g))
        with patch.object(ps,'_binario_local',side_effect=lambda x:marshal.dumps(x,2)):
            old=ps.particionar_superficie(g,'S1',_contexto=ps._ContextoGeometria(g))
        self.assertEqual(new,old)
