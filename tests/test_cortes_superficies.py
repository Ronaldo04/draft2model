import copy
import unittest
from collections import Counter
from draft2model.cortes_superficies import cortar_malla_por_niveles,ErrorCorte
from draft2model.particion_superficies import particionar_superficie
from draft2model.triangulacion_particiones import triangular_particion
from tests.test_geometria_aberturas import ejemplo
from tests.test_particion_superficies import area3
from scripts.evaluar_malla_aberturas_etabs import topologia


class CortesTests(unittest.TestCase):
    def test_dos_niveles_ambas_regiones_area_y_nodos_compartidos(self):
        for transform in (lambda x,y:(x,0,y),lambda x,y:(x,y,y)):
            g=ejemplo(transformar=transform);p=particionar_superficie(g,'S1');t=triangular_particion(g,p)
            before=copy.deepcopy(t);r=cortar_malla_por_niveles(t['nodos'],t['triangulos'],[1.5,2.5]);self.assertEqual(t,before)
            nodes={n['id']:n['xyz_m'] for n in r['nodos']};edges=Counter()
            self.assertEqual(len(set(tuple(v) for v in nodes.values())),len(nodes))
            for tri in r['triangulos']:
                z=[nodes[n][2] for n in tri['nodos']]
                self.assertFalse(any(min(z)<h<max(z) for h in (1.5,2.5)))
                edges.update(zip(tri['nodos'],tri['nodos'][1:]+tri['nodos'][:1]))
            self.assertAlmostEqual(sum(area3([nodes[n] for n in c['nodos']]) for c in r['triangulos']),p['cobertura']['area_neta_m2'])
            for (a,b),count in edges.items():self.assertEqual(count,1)
            # Una arista que discurre por el interior del nivel libre debe tener ambos lados.
            shared=[(a,b) for a,b in edges if nodes[a][2]==nodes[b][2]==1.5]
            self.assertTrue(shared)
            for a,b in shared:self.assertEqual(edges[(b,a)],1)
            self.assertEqual(r,cortar_malla_por_niveles(t['nodos'],t['triangulos'],[1.5,2.5]))
            for levels in ([1,2],[1.5,2.5]):
                rr=cortar_malla_por_niveles(t['nodos'],t['triangulos'],levels)
                nn={n['id']:n['xyz_m'] for n in rr['nodos']}
                # Ambos casos tienen z creciendo con la coordenada v del contorno.
                elements=[{'nombre':c['id'],'puntos':[{'nombre':n,'uv':[nn[n][0],nn[n][2]]} for n in c['nodos']]} for c in rr['triangulos']]
                self.assertTrue(topologia(elements)['conformidad_geometrica_comprobada'])

    def test_niveles_duplicados_no_finitos_y_mesh_degenerado(self):
        ns=[{'id':'A','xyz_m':[0,0,0]},{'id':'B','xyz_m':[1,0,0]},{'id':'C','xyz_m':[0,0,1]}];ts=[{'id':'T','nodos':['A','B','C']}]
        for h in ([1,1],[float('nan')],[True]):
            with self.assertRaises(ErrorCorte):cortar_malla_por_niveles(ns,ts,h)
        ns[-1]['xyz_m']=[2,0,0]
        with self.assertRaises(ErrorCorte):cortar_malla_por_niveles(ns,ts,[.5])


if __name__=='__main__':unittest.main()
