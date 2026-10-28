import copy
import hashlib
import json
import unittest
from tests import test_modelo_estructural as fixture
from draft2model.normalizacion_etabs import registrar_resultados
from draft2model.resultados_estructurales import huella_declaracion,exigir_resultados


class NormalizacionTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.ModeloTests();self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.raiz=self.base.raiz;self.case=self.base.caso_dir
        self.config=self.base.aprobar_config();self.config_path=self.base.escribir(self.config,'config-modelo.json')
        self.model=self.case/'modelos'/'prueba.edb';self.model.parent.mkdir();self.model.write_bytes(b'EDB SINTETICO, NO ES ETABS')
        self.raw={'contrato':'draft2model.etabs_respuesta','version_contrato':'0.1.0','id_solicitud':'a'*32,
                  'operacion':'leer_tablas','modo_ejecucion':'doble','estado':'ok','fin_utc':'2026-10-17T13:00:00Z','avisos':['Prueba sintética'],
                  'datos':{'modelo':str(self.model),'version_etabs':'21.1.0','unidades':'N_m_C','casos':['MOD','EX'],
                           'estado_casos':{'MOD':4,'EX':4},'tablas':[
                               {'clave':'Indicadores-fabricados','campos':['OutputCase','Indicador','Valor'],
                                'filas':[{'OutputCase':'MOD','Indicador':'P','Valor':'0.5'},
                                         {'OutputCase':'EX','Indicador':'D','Valor':'0.002'},
                                         {'OutputCase':'EX','Indicador':'V','Valor':'-1000'}]}]}}
        self.mapping={'contrato':'draft2model.mapeo_resultados_etabs','version':'0.1.0','caso':self.config['caso'],
                      'datos_sinteticos':True,'huella_configuracion':fixture.m.huella_configuracion(self.config),
                      'sha256_respuesta':'0'*64,'modelo':{'archivo':'modelos/prueba.edb','sha256':hashlib.sha256(self.model.read_bytes()).hexdigest()},
                      'unidades_api_esperadas':'N_m_C','version_etabs_esperada':'21.1.0','selectores':[], 'revision':None}
        for var,case,indicator,location,unit in (('periodo','MOD','P','modo-1','s'),('deriva','EX','D','N1','1'),('cortante','EX','V','base','N')):
            self.mapping['selectores'].append({'id':indicator,'variable':var,'caso':case,'direccion':'X','ubicacion':location,
                'tabla':'Indicadores-fabricados','filtros':{'OutputCase':case,'Indicador':indicator},'campo_valor':'Valor','unidad_origen':unit})
        self.raw_path=self.base.trabajo/'respuesta.json';self.map_path=self.base.trabajo/'mapeo.json';self.write()

    def write(self):
        self.raw_path.write_text(json.dumps(self.raw),encoding='utf-8')
        self.mapping['sha256_respuesta']=hashlib.sha256(self.raw_path.read_bytes()).hexdigest()
        self.mapping['revision']={'estado':'aprobado','aprobacion':{'revisor_declarado':'Prueba sintética','fecha':'2026-10-17',
            'motivo':'Solo software','alcance':'Selectores fabricados','huella_contenido':huella_declaracion(self.mapping)}}
        self.map_path.write_text(json.dumps(self.mapping),encoding='utf-8')

    def run_normalizer(self):return registrar_resultados(self.raiz,self.config_path,self.raw_path,self.map_path)

    def test_recorrido_conversion_unidades_traza_y_originales(self):
        raw_before=self.raw_path.read_bytes();model_before=self.model.read_bytes()
        folder=self.run_normalizer();data=json.loads((folder/'resultados.json').read_bytes())
        self.assertTrue(exigir_resultados(data)['correcta']);self.assertEqual(data['motor']['tipo'],'simulacion')
        self.assertTrue(data['datos_sinteticos']);self.assertEqual(data['resultados'][2]['valor'],-1)
        trace=json.loads((folder/'trazabilidad.json').read_bytes())
        self.assertEqual(trace['correspondencias'][2]['fila_indice'],2)
        self.assertEqual(trace['correspondencias'][2]['factor'],0.001)
        self.assertEqual(self.raw_path.read_bytes(),raw_before);self.assertEqual(self.model.read_bytes(),model_before)
        self.assertNotEqual(folder,self.run_normalizer())

    def test_ausencia_explicita_y_ambiguedad_rechazada(self):
        self.raw['datos']['tablas'][0]['filas'].pop();self.write()
        data=json.loads((self.run_normalizer()/'resultados.json').read_bytes())
        self.assertIsNone(data['resultados'][2]['valor']);self.assertTrue(data['omisiones'])
        self.raw['datos']['tablas'][0]['filas'].append(copy.deepcopy(self.raw['datos']['tablas'][0]['filas'][0]));self.write()
        with self.assertRaises(ValueError):self.run_normalizer()

    def test_motor_en_ruta_distinta_exige_copia_exacta_y_declaracion(self):
        motor=self.base.trabajo/'motor.edb';motor.write_bytes(self.model.read_bytes())
        self.raw['datos']['modelo']=str(motor);self.write()
        with self.assertRaises(ValueError):self.run_normalizer()
        self.mapping['modelo']['archivo_motor']=str(motor);self.write()
        folder=self.run_normalizer()
        self.assertTrue((folder/'resultados.json').is_file())
        motor.write_bytes(b'otro modelo')
        with self.assertRaises(ValueError):self.run_normalizer()

    def test_fecha_dotnet_siete_decimales_en_python310(self):
        self.raw['fin_utc']='2026-10-17T13:00:00.1234567Z';self.write()
        raw_before=self.raw_path.read_bytes()
        folder=self.run_normalizer();data=json.loads((folder/'resultados.json').read_bytes())
        self.assertEqual(data['creado_utc'],'2026-10-17T13:00:00.123456+00:00')
        self.assertEqual(raw_before,(folder/'respuesta_puente.json').read_bytes())

    def test_periodo_modal_campo_case_csi_explicito_y_sin_alias_libres(self):
        table={'clave':'Modal Periods And Frequencies','campos':['Case','Mode','Period'],
               'filas':[{'Case':'MOD','Mode':'1','Period':'0.442'}]}
        self.raw['datos']['tablas'].append(table)
        selector=self.mapping['selectores'][0]
        selector.update(tabla=table['clave'],filtros={'Case':'MOD','Mode':'1'},campo_valor='Period')
        self.write();folder=self.run_normalizer()
        result=json.loads((folder/'resultados.json').read_bytes())
        self.assertEqual(result['resultados'][0]['valor'],0.442)
        selector['filtros']['Case']='OTRO';self.write()
        with self.assertRaises(ValueError):self.run_normalizer()
        selector['filtros']['Case']='MOD';selector['tabla']='Tabla-inventada';table['clave']='Tabla-inventada';self.write()
        with self.assertRaises(ValueError):self.run_normalizer()

    def test_semantica_unidades_estado_campos_y_numeros(self):
        base_raw,base_map=copy.deepcopy(self.raw),copy.deepcopy(self.mapping)
        for change in ('unidad','estado','campo','locale','infinito','subdesborde','otro_modelo','version','caso_omitido'):
            self.raw,self.mapping=copy.deepcopy(base_raw),copy.deepcopy(base_map)
            if change=='unidad':self.mapping['selectores'][2]['unidad_origen']='kN'
            if change=='estado':self.raw['datos']['estado_casos']['MOD']=3
            if change=='campo':self.mapping['selectores'][0]['campo_valor']='NO'
            if change=='locale':self.raw['datos']['tablas'][0]['filas'][0]['Valor']='1,25'
            if change=='infinito':self.raw['datos']['tablas'][0]['filas'][0]['Valor']='1e999'
            if change=='subdesborde':self.raw['datos']['tablas'][0]['filas'][2]['Valor']='1e-323'
            if change=='otro_modelo':self.raw['datos']['modelo']=str(self.case/'otro.edb')
            if change=='version':self.raw['datos']['version_etabs']='22'
            if change=='caso_omitido':del self.mapping['selectores'][0]['filtros']['OutputCase']
            self.write()
            with self.subTest(change=change),self.assertRaises(ValueError):self.run_normalizer()

    def test_modelo_fuente_y_aprobaciones_alterados(self):
        self.raw_path.write_bytes(self.raw_path.read_bytes()+b' ')
        with self.assertRaises(ValueError):self.run_normalizer()
        self.write();self.mapping['selectores'][0]['direccion']='Y'
        self.map_path.write_text(json.dumps(self.mapping),encoding='utf-8')
        with self.assertRaises(ValueError):self.run_normalizer()
        self.write();self.model.write_bytes(b'cambio')
        with self.assertRaises(ValueError):self.run_normalizer()
