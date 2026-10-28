"""Componentes variables y restricción nativa: presión estática, no motor ni ingeniería."""
import copy
import math
import json
from pathlib import Path
import unittest
from draft2model import cargas_liquidos_etabs as p
from draft2model.acciones_liquidos import declarar_acciones_liquidos
from tests.test_acciones_liquidos import entradas
from tests.test_geometria_superficies import ejemplo


class CargasLiquidosTests(unittest.TestCase):
    def prepare(self,geo=None,nivel=1.5,sentido=1):
        g,d,f=entradas(geo,nivel,sentido);linked=declarar_acciones_liquidos(g,d,f)
        before=copy.deepcopy((g,linked,f));result=p.preparar_cargas_no_uniformes(g,linked,f)
        self.assertEqual((g,linked,f),before);self.assertFalse(result['aplicado']);self.assertFalse(result['ejecutable'])
        return result

    def test_muro_triangulo_dry_clamp_y_sentido(self):
        for sentido in (1,-1):
            r=self.prepare(sentido=sentido);c=r['superficies'][0]['componentes'][0]
            self.assertEqual(r['superficies'][0]['cortes_obligatorios_z_m'],[1.5])
            self.assertEqual(c['Dir'],'Global-Y');self.assertEqual(c['C'],10*sentido);self.assertEqual(c['D'],-15*sentido)
            self.assertEqual(p.evaluar_componente(c,[2,0,0]),-15*sentido)
            self.assertEqual(p.evaluar_componente(c,[2,0,1.5]),0)
            self.assertEqual(p.evaluar_componente(c,[2,0,3]),0)

    def test_fondo_gravity_negativo_para_presion_hacia_z_positivo(self):
        r=self.prepare(ejemplo(),nivel=2);c=r['superficies'][0]['componentes'][0]
        self.assertEqual(r['superficies'][0]['cortes_obligatorios_z_m'],[])
        self.assertEqual(c['Dir'],'Gravity');self.assertEqual(c['Restriction'],'Zero Positive Values')
        self.assertEqual(p.evaluar_componente(c,[2,2,0]),-20)

    def test_inclinado_componentes_normales_sin_carga_puntual(self):
        r=self.prepare(ejemplo([(0,0,0),(4,0,0),(4,3,3),(0,3,3)]))
        cs=r['superficies'][0]['componentes'];self.assertEqual({c['Dir'] for c in cs},{'Global-Y','Gravity'})
        for c in cs:self.assertAlmostEqual(p.evaluar_componente(c,[2,.5,.5]),-10/math.sqrt(2))
        self.assertEqual(p.evaluar_componente(cs[0],[2,2,2]),0)
        self.assertNotIn('fuerza_puntual',r)

    def test_fuente_cambiada_rechazo_y_sin_alias(self):
        g,d,f=entradas();linked=declarar_acciones_liquidos(g,d,f)
        f[0]['contenido']['gamma_kn_m3']=11
        with self.assertRaises(p.ErrorCargaLiquido):p.preparar_cargas_no_uniformes(g,linked,f)
        for xyz in ([0,0,float('nan')],[0,True,0]):
            with self.assertRaises(p.ErrorCargaLiquido):p.evaluar_componente({},xyz)

    def test_contrato_contra_esquema_nativo_instalado(self):
        fixture=json.loads((Path(__file__).parent/'fixtures'/'tabla_no_uniforme_etabs21_185.json').read_bytes())
        table=fixture['tabla'];self.assertEqual(table['clave'],p.TABLA);self.assertEqual(table['version'],1)
        fields=dict(zip(table['campos'],table['importables']))
        self.assertTrue(all(fields[k] is True for k in p.CAMPOS))
        units=dict(zip(table['campos'],table['unidades']))
        self.assertEqual(units['C'],'N/mm3');self.assertEqual(units['D'],'N/mm2')


if __name__=='__main__':unittest.main()
