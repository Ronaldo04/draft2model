"""Sensibilidad del diagnóstico de malla sintética: no motor ni ingeniería."""
import copy
import unittest
from scripts.evaluar_malla_aberturas_etabs import topologia


def elm(name,points):return {'nombre':name,'puntos':[{'nombre':n,'uv':p} for n,p in points]}


class EvaluacionMallaTests(unittest.TestCase):
    def setUp(self):
        self.a=('A',[0,0]);self.b=('B',[4,0]);self.c=('C',[4,3]);self.d=('D',[0,3])
        self.elements=[elm('T1',[self.a,self.b,self.d]),elm('T2',[self.b,self.c,self.d])]

    def test_dos_triangulos_conformes_y_ausencia_no_equivale_a_comprobacion(self):
        self.assertTrue(topologia(self.elements)['conformidad_geometrica_comprobada'])
        self.assertFalse(topologia([])['conformidad_geometrica_comprobada'])

    def test_nodo_colgante_borde_interior_y_coordenadas_sin_identidad_compartida(self):
        bad=copy.deepcopy(self.elements);bad[1]=elm('T2',[self.b,self.c,self.d,('M',[2,1.5])])
        r=topologia(bad);self.assertTrue(r['nodos_colgantes']);self.assertTrue(r['aristas_sin_pareja_interior'])
        bad=copy.deepcopy(self.elements);bad[1]['puntos'][0]['nombre']='B_otro'
        r=topologia(bad);self.assertTrue(r['coordenadas_con_varios_nombres']);self.assertFalse(r['conformidad_geometrica_comprobada'])

    def test_solape_e_inversion_se_detectan(self):
        bad=copy.deepcopy(self.elements);bad.append(copy.deepcopy(bad[0]))
        r=topologia(bad);self.assertTrue(r['solapes']);self.assertTrue(r['aristas_repetidas'])
        bad=copy.deepcopy(self.elements);bad[1]['puntos'].reverse()
        self.assertTrue(topologia(bad)['elementos_invertidos'])

    def test_nombre_unico_no_puede_representar_dos_coordenadas(self):
        bad=copy.deepcopy(self.elements);bad[1]['puntos'][0]['uv']=[3,0]
        with self.assertRaises(ValueError):topologia(bad)


if __name__=='__main__':unittest.main()
