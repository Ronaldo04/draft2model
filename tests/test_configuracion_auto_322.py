"""La configuración nativa debe pertenecer a la misma captura solicitada."""
import copy
from types import SimpleNamespace
import unittest
from draft2model import adaptador_etabs as ad
from draft2model.lectura_analisis import LectorAnalisis


class ConfiguracionAutoCaptura(unittest.TestCase):
    def setUp(self):
        self.expected = {'modelo_esperado':'modelo.edb','version_etabs_esperada':'21.1.0',
            'unidades_esperadas':'kN_m_C','casos':['MODAL'],'corrida_analisis_id':'a'*32,
            'sha256_edb':'b'*64,'resultados_api':['ConfiguracionAuto'],'tablas':[]}
        self.data = {'modelo':'modelo.edb','version_etabs':'21.1.0','unidades':'kN_m_C',
            'casos':['MODAL'],'combinaciones':[],'corrida_analisis_id':'a'*32,
            'sha256_modelo_verificado':'b'*64,'instancia':'nueva','id_proceso':123,
            'inicio_proceso_utc':'2026-10-24T12:00:00Z','instancia_cerrada':True,
            'analisis_ejecutado':False,'aprueba_resultados':False,'estado_casos':{'MODAL':4},
            'tablas':[],'resultados_api':{'ConfiguracionAuto':{'unidades':'kN_m_C',
                'version_etabs':'21.1.0','retorno':0,'tolerancia_union_m':'0.001'}}}

    def check(self, data=None, expected=None):
        LectorAnalisis._comprobar_datos(SimpleNamespace(contenido=expected or self.expected), data or self.data)

    def test_captura_correcta_y_compatibilidad_sin_opt_in(self):
        self.check()
        expected=copy.deepcopy(self.expected);expected.pop('resultados_api')
        data=copy.deepcopy(self.data);data.pop('resultados_api')
        self.check(data,expected)

    def test_version_unidades_y_retorno_incompatibles(self):
        for key,value in [('version_etabs','22.0.0'),('unidades','N_mm_C'),('retorno',True),
                          ('retorno',1),('tolerancia_union_m','NaN'),('tolerancia_union_m',.001)]:
            data=copy.deepcopy(self.data);data['resultados_api']['ConfiguracionAuto'][key]=value
            with self.subTest(key=key,value=value),self.assertRaises(ad.ErrorEvidenciaEtabs):self.check(data)

    def test_no_acepta_configuracion_omitida_o_no_solicitada(self):
        data=copy.deepcopy(self.data);data['resultados_api']={}
        with self.assertRaises(ad.ErrorEvidenciaEtabs):self.check(data)
        expected=copy.deepcopy(self.expected);expected.pop('resultados_api')
        with self.assertRaises(ad.ErrorEvidenciaEtabs):self.check(expected=expected)
