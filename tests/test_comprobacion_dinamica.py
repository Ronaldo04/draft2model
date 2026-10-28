import copy
import unittest
from draft2model.comprobacion_dinamica import comprobar
from tests import test_modelo_estructural as fixture


class ComprobacionDinamicaTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.ModeloTests();self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.config=self.base.aprobar_config()
        self.options={'parametros_modales':{'MOD':{'frecuencia_desplazamiento_hz':0.0,'frecuencia_corte_hz':0.0,
                         'tolerancia':1e-9,'desplazamiento_automatico':True}},
                      'excentricidad_espectral':{'EX':0.0},'amortiguamiento_funciones':{'ESP-PRUEBA':0.05}}
        self.read={'solo_lectura':True,'unidades':'kN_m_C','lecturas':[],'tablas':[]}
        self.model=self.base.trabajo/'modelo.edb';self.model.write_bytes(b'MODELO FABRICADO, NO ETABS')
        self.read['modelo']=str(self.model)
        def add(interface,method,name,values):
            self.read['lecturas'].append({'interfaz':interface,'metodo':method,'nombre':name,'valores':values,'retorno':0})
        add('cCaseModalEigen','GetNumberModes','MOD',{'MinModes':3,'MaxModes':3})
        add('cCaseModalEigen','GetParameters','MOD',{'EigenShiftFreq':0.0,'EigenCutOff':0.0,'EigenTol':1e-9,'AllowAutoFreqShift':1})
        add('cCaseModalEigen','GetLoads','MOD',{'NumberLoads':0})
        add('cCaseResponseSpectrum','GetModalCase','EX',{'ModalCase':'MOD'})
        add('cCaseResponseSpectrum','GetLoads','EX',{'NumberLoads':1,'LoadName':['U1'],'Func':['ESP-PRUEBA'],
                                                    'SF':[1.0],'CSys':['Global'],'Ang':[0.0]})
        add('cCaseResponseSpectrum','GetEccentricity','EX',{'Eccen':0.0})
        add('cCaseResponseSpectrum','GetDampConstant','EX',{'Damp':0.05})
        add('cCaseResponseSpectrum','GetDampOverrides','EX',{'NumberItems':0,'Mode':[],'Damp':[]})
        add('cFunction','GetValues','ESP-PRUEBA',{'NumberItems':3,'MyTime':[0.0,1.0,2.0],'Value':[0.1,0.1,0.05]})
        self.read['tablas']=[
            {'tabla':'Load Case Definitions - Response Spectrum','filas':[{'Name':'EX','ModalCombo':'CQC','RigidResp':'No'}]},
            {'tabla':'Load Case Definitions - Damping - Modal','filas':[{'Name':'EX','DampType':'Constant','ConstDamp':'0.05'}]},
            {'tabla':'Functions - Response Spectrum - User Defined','filas':[{'Name':'ESP-PRUEBA','DampRatio':'0.05'}]}]

    def check(self):return comprobar(self.base.raiz,self.config,self.options,self.read,modelo_esperado=self.model)

    def test_coincidencia_sin_aprobacion_y_sin_mutar(self):
        before=copy.deepcopy([self.config,self.options,self.read])
        result=self.check();self.assertTrue(result['correcta']);self.assertFalse(result['aprueba_modelo'])
        self.assertEqual(before,[self.config,self.options,self.read])

    def test_modos_escala_y_damping_distintos_no_se_aceptan(self):
        original=copy.deepcopy(self.read)
        for change in ('modos','escala','damping','combo'):
            self.read=copy.deepcopy(original)
            if change=='modos':self.read['lecturas'][0]['valores']['MaxModes']=2
            if change=='escala':self.read['lecturas'][4]['valores']['SF']=[9.81]
            if change=='damping':self.read['tablas'][1]['filas'][0]['DampType']='Interpolated'
            if change=='combo':self.read['tablas'][0]['filas'][0]['ModalCombo']='SRSS'
            with self.subTest(change=change):self.assertFalse(self.check()['correcta'])

    def test_lectura_o_fila_ausente_no_se_infiere(self):
        self.read['lecturas'].pop();self.assertFalse(self.check()['correcta'])
        self.read['tablas'][1]['filas']=[]
        result=self.check();self.assertFalse(result['correcta']);self.assertTrue(result['faltantes'])

    def test_damping_en_primera_fila_csi_y_ausencia_total(self):
        rows=self.read['tablas'][2]['filas']
        rows.extend([{'Name':'ESP-PRUEBA','DampRatio':None},{'Name':'ESP-PRUEBA','DampRatio':''}])
        self.assertTrue(self.check()['correcta'])
        rows[0]['DampRatio']=None
        self.assertFalse(self.check()['correcta'])

    def test_centinela_getvalues_observado_sin_truncar_otros_datos(self):
        function=self.read['lecturas'][-1]['valores']
        function['MyTime'].insert(0,0.0);function['Value'].insert(0,0.0)
        self.assertTrue(self.check()['correcta'])
        function['Value'][0]=0.5
        self.assertFalse(self.check()['correcta'])

    def test_override_modal_no_se_oculta_por_damping_constante(self):
        override=self.read['lecturas'][-2]['valores']
        override.update(NumberItems=1,Mode=[1],Damp=[0.10])
        self.assertFalse(self.check()['correcta'])

    def test_duplicados_contradictorios_y_origen_alterado_rechazados(self):
        duplicate=copy.deepcopy(self.read['lecturas'][0]);duplicate['valores']['MaxModes']=99
        self.read['lecturas'].append(duplicate)
        with self.assertRaises(ValueError):self.check()
        self.read['lecturas'].pop();self.base.original.write_bytes(b'alterado')
        with self.assertRaises(ValueError):self.check()

    def test_modelo_ajeno_no_pasa_por_tener_los_mismos_valores(self):
        self.read['modelo']=str(self.base.trabajo/'otro.edb')
        with self.assertRaises(ValueError):self.check()


if __name__=='__main__':unittest.main()
