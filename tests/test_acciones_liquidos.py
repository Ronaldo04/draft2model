"""Integrales hidrostáticas analíticas sintéticas: sin planos reales, red, solver ni cargas aplicadas."""
import copy
import math
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from draft2model import acciones_liquidos as a
from tests.test_geometria_superficies import ejemplo as superficie
from tests.test_geometria_aberturas import ejemplo as con_hueco


def entradas(geo=None,nivel=3,sentido=1):
    geo=geo or superficie([(0,0,0),(4,0,0),(4,0,3),(0,0,3)])
    geo.update(version_contrato='0.3.0');geo.setdefault('aberturas',[])
    revision={'estado':'revisado','declarada_por':'Prueba sintética','fecha':'2026-10-20','motivo':'Solo software.'}
    fuentes=[{'id':'F1','contenido':{'tipo':'caso_analitico_sintetico','gamma_kn_m3':10},'revision':revision}]
    d={'contrato':a.CONTRATO,'version_contrato':a.VERSION,'id':'L1','nivel_libre_z_m':nivel,
       'peso_especifico_kn_m3':10,'origen_momentos_m':[0,0,0],
       'superficies':[{'superficie':'S1','sentido_normal':sentido,'fuentes':['F1']}],
       'revision':{**revision,'fuentes':['F1']}}
    return geo,d,fuentes


class LiquidosTests(unittest.TestCase):
    def setUp(self):
        for target in ('urllib.request.urlopen','socket.create_connection','subprocess.Popen'):
            guard=patch(target,side_effect=AssertionError('Sin red ni procesos'))
            guard.start();self.addCleanup(guard.stop)

    def calcular(self,*args,**kwargs):
        g,d,f=entradas(*args,**kwargs);antes=copy.deepcopy((g,d,f))
        declarada=a.declarar_acciones_liquidos(g,d,f)
        out=a.calcular_acciones_liquidos(g,declarada,f)
        self.assertEqual((g,d,f),antes);self.assertFalse(out['aplicado']);self.assertFalse(out['ejecutable'])
        self.assertIsNone(out['aprobacion_ingenieria'])
        return out['superficies'][0]

    def vector(self,actual,expected):
        for x,y in zip(actual,expected):self.assertAlmostEqual(x,y,places=9)

    def test_rectangulo_vertical_triangular_y_origen_momentos(self):
        r=self.calcular()
        self.assertAlmostEqual(r['integral_presion_neta_kn'],180)
        self.vector(r['fuerza_kn'],[0,-180,0]);self.vector(r['centro_presion_m'],[2,0,1])
        self.vector(r['momento_kn_m'],[180,0,-360])
        g,d,f=entradas();d['origen_momentos_m']=[1,2,3]
        out=a.calcular_acciones_liquidos(g,a.declarar_acciones_liquidos(g,d,f),f)
        self.vector(out['momento_total_kn_m'],[-360,0,-180])

    def test_parcialmente_sumergido_y_seco(self):
        r=self.calcular(nivel=1.5)
        self.assertAlmostEqual(r['area_sumergida_neta_m2'],6)
        self.assertAlmostEqual(r['integral_presion_neta_kn'],45)
        self.vector(r['centro_presion_m'],[2,0,.5])
        for nivel in (0,-2):
            r=self.calcular(nivel=nivel);self.assertEqual(r['integral_presion_neta_kn'],0)
            self.assertIsNone(r['centro_presion_m']);self.vector(r['fuerza_kn'],[0,0,0])

    def test_hueco_completo_y_parcial_no_se_rellena(self):
        g=con_hueco(transformar=lambda x,y:(x,0,y))
        r=self.calcular(g)
        self.assertAlmostEqual(r['area_sumergida_neta_m2'],11)
        self.assertAlmostEqual(r['integral_presion_neta_kn'],165)
        self.vector(r['momento_kn_m'],[475/3,0,-337.5])
        r=self.calcular(g,nivel=1.5)
        self.assertAlmostEqual(r['area_sumergida_neta_m2'],5.5)
        self.assertAlmostEqual(r['integral_presion_neta_kn'],43.75)
        self.assertEqual(r['aberturas_ids'],['A1'])
        self.assertTrue(any(v['origen']['tipo']=='interseccion_calculada_no_medida'
                            for c in r['contornos'] for t in c['triangulos'] for v in t['region_sumergida']))

    def test_fondo_uniforme_y_normal_invertida(self):
        r=self.calcular(superficie(),nivel=2)
        self.vector(r['fuerza_kn'],[0,0,240]);self.vector(r['centro_presion_m'],[2,1.5,0])
        self.vector(r['momento_kn_m'],[360,-480,0])
        r=self.calcular(superficie(),nivel=2,sentido=-1)
        self.vector(r['fuerza_kn'],[0,0,-240]);self.vector(r['momento_kn_m'],[-360,480,0])

    def test_inclinado_parcial_y_poligono_concavo(self):
        g=superficie([(0,0,0),(4,0,0),(4,3,3),(0,3,3)])
        r=self.calcular(g,nivel=1.5)
        self.assertAlmostEqual(r['integral_presion_neta_kn'],45*math.sqrt(2))
        self.vector(r['fuerza_kn'],[0,-45,45]);self.vector(r['centro_presion_m'],[2,.5,.5])
        g=superficie([(0,0,0),(4,0,0),(4,1,0),(1,1,0),(1,3,0),(0,3,0)])
        r=self.calcular(g,nivel=2)
        self.assertAlmostEqual(r['integral_presion_neta_kn'],120)
        self.vector(r['centro_presion_m'],[1.5,1,0])

    def test_unidades_fisicas_equivalentes(self):
        valores=[]
        for unidad in ('m','cm','mm'):
            r=self.calcular(con_hueco(unidad,transformar=lambda x,y:(x,0,y)))
            valores.append((r['fuerza_kn'],r['momento_kn_m']))
        self.assertEqual(valores[0],valores[1]);self.assertEqual(valores[0],valores[2])

    def test_cambio_de_geometria_fuente_o_declaracion_invalida_vinculo(self):
        g,d,f=entradas();v=a.declarar_acciones_liquidos(g,d,f)
        for origen in ('geometria','fuente','declaracion'):
            gg,vv,ff=copy.deepcopy((g,v,f))
            if origen=='geometria':gg['procedencia']['descripcion']='Otra fuente'
            elif origen=='fuente':ff[0]['contenido']['gamma_kn_m3']=11
            else:vv['declaracion']['nivel_libre_z_m']=4
            with self.subTest(origen=origen),self.assertRaises(a.ErrorAccionesLiquidos):
                a.calcular_acciones_liquidos(gg,vv,ff)

    def test_parametros_no_finitos_fuentes_y_revision_invalidos(self):
        for key,value in [('peso_especifico_kn_m3',0),('peso_especifico_kn_m3',True),('nivel_libre_z_m',float('nan'))]:
            g,d,f=entradas();d[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(a.ErrorAccionesLiquidos):a.declarar_acciones_liquidos(g,d,f)
        for mutate in (lambda d:d['revision'].update(estado='pendiente'),
                       lambda d:d['revision'].update(fecha='2026-99-99'),
                       lambda d:d['superficies'][0].update(sentido_normal=True),
                       lambda d:d['superficies'][0].update(fuentes=['INEXISTENTE'])):
            g,d,f=entradas();mutate(d)
            with self.assertRaises(a.ErrorAccionesLiquidos):a.declarar_acciones_liquidos(g,d,f)

    def test_cli_estricta_reproduce_sin_sobrescribir_fuentes(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);paths=[root/n for n in ('geometria.json','declaracion.json','fuentes.json')]
            for p,data in zip(paths,entradas()):p.write_text(json.dumps(data),encoding='utf-8')
            originales=[p.read_bytes() for p in paths];out=root/'derivacion.json'
            args=[x for p,flag in zip(paths,('--geometria','--declaracion','--fuentes')) for x in (flag,str(p))]+['--salida',str(out)]
            with contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(a.main(args),0)
                guardado=out.read_bytes();self.assertEqual(a.main(args),2)
            self.assertEqual(out.read_bytes(),guardado);self.assertEqual([p.read_bytes() for p in paths],originales)
            self.assertEqual(json.loads(guardado)['superficies'][0]['integral_presion_neta_kn'],180)

    def test_cli_json_duplicado_no_publica_salida(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);p=root/'entrada.json';p.write_text('{"id":1,"id":2}')
            out=root/'salida.json'
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(a.main(['--geometria',str(p),'--declaracion',str(p),'--fuentes',str(p),'--salida',str(out)]),2)
            self.assertFalse(out.exists())


if __name__=='__main__':unittest.main()
