"""Aritmética y trazabilidad sintéticas, sin ETABS, red ni umbrales normativos."""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from draft2model.controles_analisis import crear_controles, recalcular_controles, validar_controles


def encoded(value):return json.dumps(value,ensure_ascii=False).encode('utf-8')
def sha(raw):return hashlib.sha256(raw).hexdigest()


def fixture():
    # Column names modal/base observed locally; the external-actions table below is ONLY a test double.
    modal={'clave':'Modal Participating Mass Ratios','version_tabla':1,
           'campos':['Case','Mode','UX','SumUX'],
           'filas':[{'Case':'MOD','Mode':'1','UX':'0.7','SumUX':'0.7'},
                    {'Case':'MOD','Mode':'2','UX':'0.25','SumUX':'0.95'}]}
    reactions={'clave':'Base Reactions','version_tabla':1,'campos':['OutputCase','StepType','FX'],
               'filas':[{'OutputCase':'EST','StepType':'Step','FX':'-10'}]}
    loads={'clave':'Cargas_SOLO_DOBLE_NO_TABLA_CSI','version_tabla':1,'campos':['OutputCase','FX'],
           'filas':[{'OutputCase':'EST','FX':'10'}]}
    response={'contrato':'draft2model.etabs_respuesta','version_contrato':'0.1.0','operacion':'leer_tablas',
              'estado':'ok','modo_ejecucion':'doble','id_solicitud':'2'*32,
              'avisos':['Aviso del lector: no acredita log solver.'],
              'datos':{'corrida_analisis_id':'1'*32,'sha256_modelo_verificado':'b'*64,'unidades':'kN_m_C',
                       'casos':['EST','MOD'],'combinaciones':[],'estado_casos':{'EST':4,'MOD':4},
                       'tablas':[modal,reactions,loads]}}
    solver={'contrato':'draft2model.avisos_solver_declarados','version':'0.1.0',
            'corrida_analisis':'1'*32,'modelo_id':'3'*32,'sha256_edb':'b'*64,'casos':['EST','MOD'],
            'origen_declarado':'Fuente SOLO SINTÉTICA de software, no captura real del solver.','advertencias':[]}
    def select(table,field,filters,unit,casefield='OutputCase'):
        return {'tabla':table,'campo_caso':casefield,'campo':field,'filtros':filters,'unidad':unit}
    controls=[{'id':'MOD-X','tipo':'participacion_modal','caso':'MOD','aplica':True,'critico':True,
               'motivo':'Comparación aritmética sintética en modo 2, sin afirmar suficiencia modal física.',
               'fuente_criterio':'Criterio inventado EXCLUSIVAMENTE para prueba de software.',
               'parametros':{'selector':select(modal['clave'],'SumUX',{'Case':'MOD','Mode':'2'},'1','Case'),
                             'direccion':'UX','minimo_acumulado':0.9}},
              {'id':'EST-X','tipo':'equilibrio','caso':'EST','aplica':True,'critico':True,
               'motivo':'Balance estático escalar sintético, componentes y signos declarados.',
               'fuente_criterio':'SOLO prueba unitaria: no tolerancia de ingeniería.',
               'parametros':{'cargas':[{'selector':select(loads['clave'],'FX',{'OutputCase':'EST'},'kN'),'factor':1}],
                             'reacciones':[{'selector':select(reactions['clave'],'FX',{'OutputCase':'EST','StepType':'Step'},'kN'),'factor':1}],
                             'unidad':'kN','tolerancia_absoluta':0.01,'tolerancia_relativa':0.001,'escala_referencia':10}},
              {'id':'SOLVER','tipo':'advertencias_solver','caso':None,'aplica':True,'critico':True,
               'motivo':'Revisar todos los avisos de la fuente declarada de prueba.',
               'fuente_criterio':'SOLO prueba: ningún código admitido.',
               'parametros':{'codigos_admitidos':[]}}]
    raw=encoded(response);warnings=encoded(solver)
    declaration={'caso':'prueba-sintetica','expediente_sha256':'a'*64,'corrida_analisis':'1'*32,'lectura':'2'*32,
                 'modelo':{'id':'3'*32,'sha256_edb':'b'*64},'datos_sinteticos':True,'casos':['EST','MOD'],
                 'sha256_respuesta':sha(raw),'sha256_avisos_solver':sha(warnings),
                 'revisor_declarado':'Identidad declarada de prueba, sin competencia acreditada.',
                 'fecha':'2026-10-18','alcance':'Únicamente aritmética y contrato de software sintético.',
                 'controles':controls}
    return declaration,response,solver


class ControlesAnalisisTests(unittest.TestCase):
    def setUp(self):
        self.d,self.r,self.s=fixture()
        for target in ('subprocess.Popen','urllib.request.urlopen','socket.create_connection'):
            guard=patch(target,side_effect=AssertionError('Sin procesos/red'));guard.start();self.addCleanup(guard.stop)

    def create(self,solver=True):
        raw=encoded(self.r);warnings=encoded(self.s) if solver else None
        self.d['sha256_respuesta']=sha(raw);self.d['sha256_avisos_solver']=sha(warnings) if solver else None
        return crear_controles(self.d,raw,avisos_solver_bytes=warnings)

    def test_satisfactorio_recalculo_json_formulas_fuentes_y_no_mutacion(self):
        before=copy.deepcopy((self.d,self.r,self.s));doc=self.create()
        self.assertEqual((self.d,self.r,self.s),before)
        self.assertEqual(doc['estado_global'],'satisfactorio');self.assertTrue(doc['apto_proyeccion_controlado'])
        self.assertEqual(doc['controles'][0]['valores']['acumulado'],0.95)
        self.assertEqual(doc['controles'][1]['valores']['residuo_firmado'],0)
        self.assertEqual(doc['controles'][1]['valores']['limite'],0.01)
        self.assertEqual(doc['controles'][0]['trazas'][0]['valor_crudo'],'0.95')
        self.assertEqual(len(doc['huellas_tablas']),3);self.assertEqual(doc['avisos_lector'],self.r['avisos'])
        self.assertEqual(recalcular_controles(json.loads(encoded(doc))),doc)
        self.assertTrue(validar_controles(doc,respuesta_bytes=encoded(self.r),avisos_solver_bytes=encoded(self.s)))
        self.assertFalse(doc['revision_profesional_verificada'] or doc['aprueba_resultados'])
        self.assertEqual(doc['estado_analisis'],'no_evaluado_por_este_nucleo')

    def test_discrepancias_modal_y_equilibrio_incluyen_valores(self):
        self.r['datos']['tablas'][0]['filas'][1]['SumUX']='0.89'
        self.r['datos']['tablas'][1]['filas'][0]['FX']='-9.9'
        doc=self.create()
        self.assertEqual([r['estado'] for r in doc['controles']],['discrepante','discrepante','satisfactorio'])
        self.assertFalse(doc['apto_proyeccion_controlado']);self.assertAlmostEqual(doc['controles'][1]['valores']['error_relativo'],0.01)

    def test_limites_inclusivos_sin_redondear(self):
        self.r['datos']['tablas'][0]['filas'][1]['SumUX']='0.9'
        self.d['controles'][1]['parametros'].update(tolerancia_absoluta=1,tolerancia_relativa=0)
        self.r['datos']['tablas'][1]['filas'][0]['FX']='-9'
        self.assertTrue(self.create()['apto_proyeccion_controlado'])

    def test_sin_datos_criticos_no_csi4_igual_controlado(self):
        self.r['datos']['tablas'][0]['filas'][1]['SumUX']=None
        self.r['datos']['tablas'][1]['filas']=[]
        doc=self.create(solver=False)
        self.assertEqual(doc['estado_casos_declarado'],{'EST':4,'MOD':4})
        self.assertEqual([r['estado'] for r in doc['controles']],['sin_datos']*3)
        self.assertEqual(doc['faltantes_criticos'],['MOD-X','EST-X','SOLVER'])
        self.assertIsNone(doc['advertencias_solver']);self.assertFalse(doc['apto_proyeccion_controlado'])

    def test_no_aplicable_solo_declarado_no_oculta_avisos(self):
        self.s['advertencias']=[{'caso':None,'codigo':'AVISO','texto':'Aviso sintético conservado incluso con NA.'}]
        for c in self.d['controles']:c.update(aplica=False,motivo='No aplica EXPLÍCITO solo para este escenario de software.',parametros={})
        doc=self.create();self.assertEqual(doc['estado_global'],'no_aplicable')
        self.assertFalse(doc['apto_proyeccion_controlado']);self.assertEqual(doc['advertencias_solver'],self.s['advertencias'])
        self.d['controles'][0]['aplica']=None
        with self.assertRaises(ValueError):self.create()

    def test_declaracion_externa_sola_no_proyecta_controlado(self):
        # Solo la fuente solver declarada aplica (lista vacía): su control queda satisfactorio pero NO controlado.
        for c in self.d['controles'][:2]:c.update(aplica=False,motivo='No aplica EXPLÍCITO en este escenario de software.',parametros={})
        doc=self.create();self.assertEqual(doc['controles'][2]['estado'],'satisfactorio')
        self.assertEqual(doc['controles'][2]['verificacion'],'declarada_no_verificada')
        self.assertEqual(doc['controles_solo_declarados'],['SOLVER']);self.assertEqual(doc['criticos_no_aplicables'],['MOD-X','EST-X'])
        self.assertFalse(doc['apto_proyeccion_controlado'])

    def test_advertencias_admitidas_y_discrepantes_siempre_visibles(self):
        self.s['advertencias']=[{'caso':'MOD','codigo':'W1','texto':'Aviso sintético no ocultable.'}]
        doc=self.create();self.assertEqual(doc['controles'][2]['estado'],'discrepante')
        self.assertFalse(doc['apto_proyeccion_controlado'])
        self.d['controles'][2]['parametros']['codigos_admitidos']=['W1']
        doc=self.create();self.assertTrue(doc['apto_proyeccion_controlado'])
        self.assertEqual(doc['advertencias_solver'],self.s['advertencias'])
        self.assertEqual(doc['controles'][2]['valores']['advertencias'],self.s['advertencias'])

    def test_unidades_casos_vinculos_y_naturaleza_rechazados(self):
        for field,value in (('unidades','N_m_C'),('corrida_analisis_id','f'*32),
                            ('sha256_modelo_verificado','f'*64),('casos',['EST']),('estado_casos',{'EST':True,'MOD':4})):
            with self.subTest(field=field):
                d,r,s=fixture();self.d,self.r,self.s=d,r,s;self.r['datos'][field]=value
                with self.assertRaises(ValueError):self.create()
        self.d,self.r,self.s=fixture();self.d['datos_sinteticos']=False
        with self.assertRaises(ValueError):self.create()
        self.d,self.r,self.s=fixture();self.s['modelo_id']='f'*32
        with self.assertRaises(ValueError):self.create()

    def test_selectores_ambiguos_unidad_porcentaje_y_numeros_invalidos(self):
        for change in ('duplicado','caso','unidad','direccion','no_acumulado','porcentaje','nan','coma','signo','cancelacion'):
            self.d,self.r,self.s=fixture();p=self.d['controles'][0]['parametros']
            if change=='duplicado':self.r['datos']['tablas'][0]['filas'].append(copy.deepcopy(self.r['datos']['tablas'][0]['filas'][1]))
            elif change=='caso':p['selector']['filtros']['Case']='EST'
            elif change=='unidad':p['selector']['unidad']='%'
            elif change=='direccion':p['direccion']='UY'
            elif change=='no_acumulado':p['selector']['campo']='UX'
            elif change in ('porcentaje','nan','coma'):self.r['datos']['tablas'][0]['filas'][1]['SumUX']={'porcentaje':'95','nan':'NaN','coma':'0,95'}[change]
            elif change=='signo':self.d['controles'][1]['parametros']['cargas'][0]['factor']=False
            else:self.d['controles'][1]['parametros']['reacciones']=copy.deepcopy(self.d['controles'][1]['parametros']['cargas'])
            with self.subTest(change=change),self.assertRaises(ValueError):self.create()

    def test_tabla_ausente_y_cero_filas_se_conservan_sin_inferir(self):
        self.r['datos']['tablas']=self.r['datos']['tablas'][1:]
        doc=self.create();row=doc['controles'][0]
        self.assertEqual(row['estado'],'sin_datos');self.assertIsNone(row['valores']['acumulado'])
        self.assertIsNone(row['trazas'][0]['sha256_tabla']);self.assertIn('Tabla requerida ausente',row['motivos'][0])

    def test_alteraciones_resultados_criterios_fuentes_y_bytes_actuales(self):
        doc=self.create()
        for key,value in (('estado_global','no_aplicable'),('apto_proyeccion_controlado',False),('extra',True)):
            bad=copy.deepcopy(doc);bad[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validar_controles(bad)
        bad=copy.deepcopy(doc);bad['controles'][0]['valores']['acumulado']=1
        with self.assertRaises(ValueError):validar_controles(bad)
        bad=copy.deepcopy(doc);bad['declaracion']['controles'][0]['parametros']['minimo_acumulado']=0.99
        with self.assertRaises(ValueError):validar_controles(bad)
        with self.assertRaises(ValueError):validar_controles(doc,respuesta_bytes=encoded(self.r)+b'\n')
        with self.assertRaises(ValueError):validar_controles(doc,avisos_solver_bytes=encoded(self.s)+b'\n')
        bad=copy.deepcopy(doc);bad['fuentes']['respuesta']['sha256']='0'*64
        with self.assertRaises(ValueError):validar_controles(bad)

    def test_contrato_exacto_revisor_tolerancias_y_aplicabilidad(self):
        for change in ('campo','fecha','sin_familia','aplica','critico','minimo','escala','tolerancia'):
            self.d,self.r,self.s=fixture()
            if change=='campo':self.d['extra']=True
            elif change=='fecha':self.d['fecha']='2026-02-30'
            elif change=='sin_familia':self.d['controles'].pop()
            elif change=='aplica':self.d['controles'][0]['aplica']=1
            elif change=='critico':self.d['controles'][0]['critico']=None
            elif change=='minimo':self.d['controles'][0]['parametros']['minimo_acumulado']=float('inf')
            elif change=='escala':self.d['controles'][1]['parametros']['escala_referencia']=0
            else:self.d['controles'][1]['parametros']['tolerancia_absoluta']=-1
            with self.subTest(change=change),self.assertRaises(ValueError):self.create()


if __name__=='__main__':unittest.main()
