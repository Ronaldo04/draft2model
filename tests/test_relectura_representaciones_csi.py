"""Comparación física de representaciones nativas191/192; dobles, sin ETABS/red."""
import copy
import unittest
from draft2model import verificacion_modelo_guardado as v
from tests.test_verificacion_modelo_guardado import Planes, modelo_desde_expectativa, lecturas, CRITERIOS


class RepresentacionesTests(Planes,unittest.TestCase):
    def test_same_load_and_oriented_cycle_but_wrong_sign_or_projection_rejected(self):
        exp = v.expectativa_desde_plan(self.plan02())
        model = modelo_desde_expectativa(exp)
        before = copy.deepcopy(model)
        for area, puntos in model['areas']['puntos'].items():
            model['areas']['puntos'][area] = puntos[1:]+puntos[:1]
        converted = 0
        for items in model['cargas_area'].values():
            for row in items:
                if row['dir'] == 6 and row['csys'] == 'Global':
                    row['dir'] = 10; row['valor'] = -row['valor']; converted += 1
        self.assertGreater(converted,0)
        snapshot = copy.deepcopy(model)
        result = v.comparar(exp,lecturas(model),CRITERIOS)
        self.assertEqual(result['estado'],'verificado',result)
        self.assertEqual(model,snapshot)
        self.assertNotEqual(model,before)
        for failure in ('signo','proyeccion','orientacion'):
            bad = copy.deepcopy(model)
            if failure == 'orientacion':
                a=next(iter(bad['areas']['puntos']));bad['areas']['puntos'][a].reverse()
            else:
                row=next(r for rs in bad['cargas_area'].values() for r in rs if r['dir']==10)
                if failure=='signo': row['valor']=-row['valor']
                else: row['dir']=11
            r=v.comparar(exp,lecturas(bad),CRITERIOS)
            self.assertEqual(r['estado'],'discrepancias',r)

    def test_no_normalization_of_local_or_moment_loads(self):
        for category, row in [('cargas_area',{'csys':'Local','dir':10,'valor':3}),
                              ('cargas_frame',{'csys':'Global','dir':10,'tipo':2,'val1':3,'val2':4})]:
            self.assertEqual(v.carga_vertical_global(row,category),row)
        source={'csys':'Global','dir':11,'tipo':1,'val1':3,'val2':4}
        target=v.carga_vertical_global(source,'cargas_frame')
        self.assertEqual((target['dir'],target['val1'],target['val2']),(9,-3,-4))
        self.assertEqual(source['dir'],11)


if __name__=='__main__':unittest.main()
