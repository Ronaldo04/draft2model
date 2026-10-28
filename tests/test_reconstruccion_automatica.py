import copy
import unittest
from draft2model.reconstruccion_automatica import reconstruir, resolver_eje


def fixture():
    e={'archivo_id':'L1','pagina':1,'original_sha256':'a'*64,'bbox_normalizada':[0,0,1,1],'texto':'Dimensiones en metros'}
    evidence=[e]
    manifest={'id':'demo','archivos':[{'id':'L1','sha256':'a'*64,'paginas':1}]}
    response={'contrato':'draft2model.reconstruccion_planos','version_contrato':'0.1.0','caso':'demo',
        'unidad':'m','evidencia_unidad':evidence,'origen_local':'A',
        'niveles':[{'id':'N1','cota':3,'evidencias':evidence}],
        'puntos':[{'id':p,'nivel':'N1','evidencias':evidence} for p in 'ABCD'],
        'medidas':[{'id':'MX','desde':'A','hasta':'B','eje':'x','valor':4,'evidencias':evidence},
                   {'id':'MY','desde':'A','hasta':'D','eje':'y','valor':3,'evidencias':evidence}],
        'alineaciones':[{'desde':a,'hasta':b,'eje':axis,'evidencias':evidence}
                        for a,b,axis in [('A','D','x'),('B','C','x'),('A','B','y'),('C','D','y')]],
        'elementos':[{'id':'S1','tipo':'losa','puntos':list('ABCD'),'evidencias':evidence}],'faltantes':[]}
    return response,manifest


class ReconstructionTests(unittest.TestCase):
    def test_evidencia_de_unidad_y_elementos_no_acepta_pagina_inexistente(self):
        for group in ('evidencia_unidad','puntos'):
            data,manifest=fixture()
            if group=='evidencia_unidad':
                data[group]=copy.deepcopy(data[group]);data[group][0]['pagina']=2
            else:
                data[group][0]['evidencias']=copy.deepcopy(data[group][0]['evidencias']);data[group][0]['evidencias'][0]['pagina']=2
            with self.subTest(group=group),self.assertRaisesRegex(ValueError,'Evidencia'):reconstruir(data,manifest)

    def test_medidas_a_geometria_sin_coordenadas_manuales_ni_aprobacion(self):
        data,manifest=fixture();before=copy.deepcopy(data)
        result=reconstruir(data,manifest)
        self.assertEqual(result['estado'],'geometria_borrador')
        self.assertEqual(result['coordenadas_resueltas']['x'],{'A':0,'B':4,'D':0,'C':4})
        self.assertEqual(result['coordenadas_resueltas']['y']['C'],3)
        self.assertEqual(result['geometria']['vertices'][0]['z'],3)
        self.assertIsNone(result['geometria']['revision']['aprobacion'])
        self.assertFalse(result['ejecutable_etabs']);self.assertEqual(data,before)

    def test_no_rellena_componentes_desconectados_con_cero(self):
        data,manifest=fixture();data['alineaciones'].pop()
        result=reconstruir(data,manifest)
        self.assertIsNone(result['geometria']);self.assertTrue(result['faltantes'])

    def test_contradiccion_no_se_oculta_ajustando_dimensiones(self):
        data,manifest=fixture();measure=copy.deepcopy(data['medidas'][0]);measure.update(id='CONFLICTO',valor=5);data['medidas'].append(measure)
        result=reconstruir(data,manifest)
        self.assertIsNone(result['geometria']);self.assertTrue(result['conflictos'])

    def test_unidad_ausente_o_no_respaldada_no_genera_geometria(self):
        for unit,literal in [('desconocida','sin unidad'),('m','escala1:50')]:
            data,manifest=fixture();data['unidad']=unit
            for e in data['evidencia_unidad']:e['texto']=literal
            self.assertIsNone(reconstruir(data,manifest)['geometria'])

    def test_fuente_ajena_campos_inyectados_y_no_finitos(self):
        for change in ('source','unknown','nan'):
            data,manifest=fixture()
            if change=='source':manifest['archivos'][0]['sha256']='b'*64
            elif change=='unknown':data['aprobar']=True
            else:data['medidas'][0]['valor']=float('nan')
            with self.assertRaises(ValueError):reconstruir(data,manifest)

    def test_unidades_cm_y_mm(self):
        for unit,k in [('cm',100),('mm',1000)]:
            data,manifest=fixture();data['unidad']=unit
            for e in data['evidencia_unidad']:e['texto']='Unidad '+unit
            for m in data['medidas']:m['valor']*=k
            for n in data['niveles']:n['cota']*=k
            result=reconstruir(data,manifest)
            self.assertEqual(result['estado'],'geometria_borrador')
            self.assertEqual(result['coordenadas_resueltas']['x']['C'],4)

    def test_unifica_puntos_exactos_sin_ajustar_medidas(self):
        data,manifest=fixture();e=data['puntos'][0]['evidencias']
        data['puntos'].append({'id':'E','nivel':'N1','evidencias':e})
        data['alineaciones'] += [{'desde':'C','hasta':'E','eje':axis,'evidencias':e} for axis in ('x','y')]
        data['elementos'][0]['puntos']=['A','B','C','E','D']
        result=reconstruir(data,manifest)
        self.assertEqual(result['estado'],'geometria_borrador')
        self.assertEqual(result['identificadores_unificados'],{'E':'C'})
        self.assertEqual(len(result['geometria']['vertices']),4)
        self.assertEqual(result['geometria']['superficies'][0]['vertices'],list('ABCD'))

    def test_no_crea_frame_de_longitud_cero_tras_unificar(self):
        data,manifest=fixture();e=data['puntos'][0]['evidencias']
        data['puntos'].append({'id':'E','nivel':'N1','evidencias':e})
        data['alineaciones'] += [{'desde':'C','hasta':'E','eje':axis,'evidencias':e} for axis in ('x','y')]
        data['elementos'].append({'id':'F1','tipo':'viga','puntos':['C','E'],'evidencias':e})
        self.assertIsNone(reconstruir(data,manifest)['geometria'])

    def test_elemento_y_medida_incompletos_reportan_faltantes_sin_abortar(self):
        data,manifest=fixture();e=data['puntos'][0]['evidencias']
        data['puntos'] += [{'id':'CIS1','nivel':'N1','evidencias':e},{'id':'CIS2','nivel':'N1','evidencias':e}]
        data['elementos'].append({'id':'CISTERNA','tipo':'otro','puntos':['CIS1','CIS2'],'evidencias':e})
        data['medidas'].append({'id':'M_BUCLE','desde':'A','hasta':'A','eje':'x','valor':0.75,'evidencias':e})
        result=reconstruir(data,manifest)
        self.assertEqual(result['estado'],'faltan_datos_para_geometria')
        self.assertIsNone(result['geometria'])
        self.assertEqual(result['resumen_lectura']['elementos_validos'],1)
        self.assertEqual(len(result['resumen_lectura']['elementos_incompletos']),1)
        self.assertTrue(any('CISTERNA' in f for f in result['faltantes']))
        self.assertTrue(any('M_BUCLE' in f for f in result['faltantes']))
        self.assertTrue(any(c['relacion']=='M_BUCLE' for c in result['conflictos']))

    def test_alineacion_xy_entre_niveles_y_unidad_revisada_trazable(self):
        data,manifest=fixture();e=data['puntos'][0]['evidencias']
        data['unidad']='desconocida';data['evidencia_unidad']=[]
        data['niveles'].append({'id':'N2','cota':6,'evidencias':e})
        for p in 'ABCD':
            data['puntos'].append({'id':p+'2','nivel':'N2','evidencias':e})
            data['alineaciones'].append({'desde':p,'hasta':p+'2','eje':'xy','evidencias':e})
        data['elementos'].append({'id':'S2','tipo':'losa','puntos':['A2','B2','C2','D2','A2'],'evidencias':e})
        sin_unidad=reconstruir(data,manifest)
        self.assertIsNone(sin_unidad['geometria'])
        self.assertFalse(any('sin cadena de medidas' in f for f in sin_unidad['faltantes']))
        con_unidad=reconstruir(data,manifest,unidad_revisada={
            'unidad':'m','revisor':'Ing. Prueba','motivo':'Cotas y NPT expresados en metros en láminas.'})
        self.assertEqual(con_unidad['estado'],'geometria_borrador')
        self.assertEqual(con_unidad['unidad_declarada_ingenieria']['unidad'],'m')
        self.assertIsNone(con_unidad['aprobacion_ingenieria'])
        self.assertEqual(len(con_unidad['geometria']['superficies']),2)

    def test_origen_con_descripcion_y_observaciones_conservadas_en_borrador(self):
        data,manifest=fixture()
        data['origen_local']='A: cruce de ejes A y 1 en N1'
        data['faltantes']=['Cisterna local en corte sin amarre global en planta.']
        result=reconstruir(data,manifest)
        self.assertEqual(result['estado'],'geometria_borrador')
        self.assertEqual(result['resumen_lectura']['origen_local'],'A')
        self.assertEqual(result['resumen_lectura']['bloqueos_coordenadas'],0)
        self.assertEqual(result['geometria']['faltantes'],
                         [{'descripcion':'Cisterna local en corte sin amarre global en planta.'}])
        self.assertFalse(result['validacion']['disponible_para_modelado'])
        self.assertIsNone(result['aprobacion_ingenieria'])


if __name__=='__main__':unittest.main()
