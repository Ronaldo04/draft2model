"""Vínculo presión/malla desde versiones reales en disco, sin ETABS ni API."""
import copy
from pathlib import Path
import unittest

from draft2model import vinculo_presion_malla as v
from draft2model import gestion_configuracion as gc, modelo_estructural as me, operaciones_etabs as op
from draft2model.acciones_liquidos import declarar_acciones_liquidos
from draft2model.cargas_liquidos_etabs import ErrorCargaLiquido
from tests.test_integracion_malla import CasoMalla, REVISOR, F
from tests.test_acciones_liquidos import entradas
from tests import test_gestion_geometria as disco


class VinculoPresionTests(CasoMalla):
    def preparar(self,nombre='vertical_corte',nivel=1.5,origen=None):
        data=self.montar(nombre)
        data['patrones'].append({'id':'HIDRO','tipo':'otro','multiplicador_peso_propio':0,'fuente':F})
        data=self.completar(data)
        imp=gc.importar(self.raiz,disco.CASO,self.f.escribir(data,'hidro.json'))
        rev=gc.revisar(self.raiz,disco.CASO,imp['id'],data,**REVISOR)
        config=gc.aprobar(self.raiz,disco.CASO,rev['id'],
                          huella_esperada=me.huella_configuracion(rev['configuracion']),
                          alcance='Prueba software de patrón dedicado.',**REVISOR)['configuracion']
        plan=op.generar_plan_por_version(self.raiz,config,**self.opciones(config)).datos
        geo,d,fuentes=entradas(copy.deepcopy(self.geo),nivel=nivel)
        if origen is not None:d['origen_momentos_m']=origen
        d['superficies']=[{'superficie':h,'sentido_normal':1,'fuentes':['F1']} for h in plan['malla']['hosts']]
        declarada=declarar_acciones_liquidos(geo,d,fuentes)
        return config,plan,declarada,fuentes

    def vincular(self,values,patron='HIDRO'):
        return v.preparar_tabla_liquidos(self.raiz,*values,patron=patron)

    def test_hole_partial_pressure_and_nonzero_origin_conserve_force_and_moment(self):
        for origen in ([0,0,0],[2,3,4]):
            with self.subTest(origen=origen):
                values=self.preparar(origen=origen)
                before=copy.deepcopy(values)
                result=self.vincular(values)
                host=result['hosts'][0]
                self.assertAlmostEqual(host['fuerza_kn'][0],53.8,places=9)
                self.assertEqual(host['aberturas_ids'],['PUERTA'])
                for a,b in zip(host['momento_kn_m'],host['momento_fuente_kn_m']):self.assertAlmostEqual(a,b,places=9)
                self.assertEqual({r['UniqueName'] for r in result['filas']},set(host['triangulos']))
                self.assertTrue(all(r['LoadPattern']=='HIDRO' for r in result['filas']))
                self.assertFalse(result['aplicado']);self.assertFalse(result['ejecutable'])
                self.assertEqual(values,before)
                self.assertEqual(result,self.vincular(values))

    def test_connected_hosts_keep_all_dry_floor_material_and_distinct_components(self):
        values=self.preparar('conectados_corte',nivel=1.2)
        result=self.vincular(values)
        hosts={h['superficie']:h for h in result['hosts']}
        self.assertEqual(set(hosts),{'S1','S2'})
        self.assertAlmostEqual(hosts['S1']['area_material_m2'],11)
        self.assertEqual(hosts['S1']['fuerza_kn'],[0,0,0])
        self.assertEqual(len(result['filas']),sum(len(h['triangulos']) for h in hosts.values()))
        piso=[r for r in result['filas'] if r['UniqueName'] in hosts['S1']['triangulos']]
        self.assertTrue(all(r['Dir']=='Gravity' for r in piso))
        self.assertGreater(hosts['S2']['fuerza_kn'][0],0)

    def test_missing_cut_rejected_even_when_import_coefficients_would_succeed(self):
        values=self.preparar('vertical',nivel=1.5)
        with self.assertRaisesRegex(ErrorCargaLiquido,'corte explícito'):self.vincular(values)

    def test_inclined_fully_wet_components_and_entirely_dry_wall_need_no_cut(self):
        for nombre,nivel in (('inclinado',1.5),('vertical',-1)):
            with self.subTest(nombre=nombre):
                result=self.vincular(self.preparar(nombre,nivel=nivel,origen=[-2,4,1]))
                host=result['hosts'][0]
                for a,b in zip(host['fuerza_kn']+host['momento_kn_m'],host['fuerza_fuente_kn']+host['momento_fuente_kn_m']):
                    self.assertAlmostEqual(a,b,places=8)
                if nombre=='inclinado':
                    self.assertEqual({r['Dir'] for r in result['filas']},{'Global-X','Gravity'})
                    self.assertEqual(len(result['filas']),2*len(host['triangulos']))
                else:
                    self.assertEqual(host['fuerza_kn'],[0,0,0])
                    self.assertEqual(len(result['filas']),len(host['triangulos']))

    def test_rehashed_plan_or_changed_source_not_accepted(self):
        config,plan,d,f=self.preparar()
        changed=copy.deepcopy(plan)
        changed['malla']['hosts']['S1']['triangulos'].pop()
        changed['huella_plan']=op.huella_plan(changed)
        with self.assertRaisesRegex(ErrorCargaLiquido,'regeneración'):self.vincular((config,changed,d,f))
        f[0]['contenido']['gamma_kn_m3']=11
        with self.assertRaises(ErrorCargaLiquido):self.vincular((config,plan,d,f))

    def test_no_reuse_loaded_or_selfweight_pattern_and_no_approval_transfer(self):
        values=self.preparar()
        for p in ('L','D','AUSENTE'):
            with self.subTest(patron=p):
                with self.assertRaises(ErrorCargaLiquido):self.vincular(values,patron=p)
        config,plan,d,f=copy.deepcopy(values)
        config['patrones'][-1]['multiplicador_peso_propio']=1
        # Approval/configuration source changed: a newly hashed plan does not bless it.
        with self.assertRaises(ErrorCargaLiquido):self.vincular((config,plan,d,f))


if __name__=='__main__':unittest.main()
