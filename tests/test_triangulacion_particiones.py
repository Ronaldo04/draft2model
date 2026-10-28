"""Triángulos verificables con comprobaciones independientes, sin motor ni red."""
import copy
from collections import Counter
import unittest
from draft2model.particion_superficies import particionar_superficie
from draft2model.triangulacion_particiones import triangular_particion,ErrorTriangulacion
from tests.test_geometria_aberturas import ejemplo,agregar
from tests.test_particion_superficies import area3,cruz,sub,punto


class TriangulacionTests(unittest.TestCase):
    def test_orientaciones_unidades_huecos_y_nodos_colineales(self):
        for transform in (lambda x,y:(x,y,0),lambda x,y:(x,0,y),lambda x,y:(x,y,y)):
            for unidad in ('m','cm','mm'):
                with self.subTest(transform=transform,unidad=unidad):
                    g=ejemplo(unidad,transform);agregar(g,[(2.5,.5),(3.5,.5),(3.5,1.5),(2.5,1.5)],'A2',transformar=transform)
                    p=particionar_superficie(g,'S1');before=copy.deepcopy((g,p))
                    t=triangular_particion(g,p);self.assertEqual((g,p),before)
                    nodes={n['id']:n['xyz_m'] for n in t['nodos']};normal=t['superficie']['normal_unitaria']
                    self.assertAlmostEqual(sum(area3([nodes[n] for n in c['nodos']]) for c in t['triangulos']),p['cobertura']['area_neta_m2'])
                    used={n for c in t['triangulos'] for n in c['nodos']};self.assertEqual(used,set(nodes))
                    edges=Counter((a,b) for c in t['triangulos'] for a,b in zip(c['nodos'],c['nodos'][1:]+c['nodos'][:1]))
                    boundary={tuple(e) for chain in t['cadenas_contorno'] for e in zip(chain['nodos'],chain['nodos'][1:])}
                    for edge,count in edges.items():
                        self.assertEqual(count,1)
                        if edge not in boundary and edge[::-1] not in boundary:self.assertEqual(edges[edge[::-1]],1)
                    for c in t['triangulos']:
                        a,b,d=[nodes[n] for n in c['nodos']]
                        self.assertGreater(punto(cruz(sub(b,a),sub(d,a)),normal),0)
                    self.assertEqual(t,triangular_particion(g,p));self.assertFalse(t['ejecutable'])

    def test_rechaza_particion_rehash_y_fuente_cambiada(self):
        g=ejemplo();p=particionar_superficie(g,'S1')
        for modify in (lambda x:x['nodos'][0]['xyz_m'].__setitem__(0,99),lambda x:x['celdas'][0]['nodos'].pop(),lambda x:x.update(ejecutable=0)):
            bad=copy.deepcopy(p);modify(bad)
            with self.assertRaises(ErrorTriangulacion):triangular_particion(g,bad)
        g['procedencia']['descripcion']='Otra procedencia'
        with self.assertRaises(ErrorTriangulacion):triangular_particion(g,p)


if __name__=='__main__':unittest.main()
