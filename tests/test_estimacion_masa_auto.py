"""El descuento estimado no altera el bruto ni convierte fallos de captura en éxito."""
import copy
import unittest
from unittest.mock import patch
from draft2model import estimacion_masa_auto as e
from draft2model.estimacion_extremos_auto import validar_captura_configuracion
from draft2model.libro_masa import contrastar_masa_nativa

CONFIG = {'unidades':'kN_m_C','version_etabs':'21.1.0','retorno':0,'tolerancia_union_m':'0.001'}
PLAN = {'huella_plan':'f'*64}
LIBRO = {'masa_total_kn_s2_m':10.,'gravedad_m_s2':10.,'contribuciones':{'peso_propio_por_patrones':{'factor_efectivo':1.}}}
PRED = {'estado':'estimacion','problemas_plan':[], 'plan_validado':PLAN,
        'perfil_peso':{'salvedades':[]},'totales':{'vigas':1,'descuento_kN':5.},
        'vigas':[{'viga':'V1','abstencion':[],'offsets':{'I':.1,'J':.1},'descuento_peso':{'kN':5.}}]}


def captura(axes=0):
    row={'point_element':'1','mass_source':'MsSrc1','global_xyz':['0','0','0'],'point_axes_deg':[str(axes),'0','0'],
         'U1':'9.5','U2':'9.5','U3':'0','R1':'0','R2':'0','R3':'0'}
    return {'unidades':'kN_m_C','retorno':0,'numero_resultados':1,'point_elements':['1'],'mass_sources':['MsSrc1'],
            **{k:[row[k]] for k in ('U1','U2','U3','R1','R2','R3')},'observaciones':[row]}


class EstimacionMasa(unittest.TestCase):
    def crear(self,pred=None,cap=None,masa_propia=False):
        with patch.object(e,'estimar_desde_plan',return_value=copy.deepcopy(PRED if pred is None else pred)):
            return e.crear(PLAN,{'masa':{'incluir_masa_propia':masa_propia}},LIBRO,CONFIG,cap or captura(),
                           lectura='a'*32,fuente='MsSrc1',tolerancia=0.001)

    def test_separacion_y_validacion(self):
        antes=copy.deepcopy(LIBRO); out=self.crear()
        bruto=contrastar_masa_nativa(captura(),LIBRO,capture_id='a'*32,fuente_esperada='MsSrc1',tolerancia_relativa=.001)
        self.assertEqual(bruto['estado'],'no_coherente')
        self.assertEqual(out['contraste_estimado']['estado'],'coherente')
        self.assertEqual(out['masa_estimada_kn_s2_m'],9.5)
        self.assertEqual(antes,LIBRO)
        e.validar(out,LIBRO,bruto)
        for key in ('masa_estimada_kn_s2_m','descuento_peso_kn','factor_peso_propio'):
            bad=copy.deepcopy(out);bad[key]+=1
            with self.subTest(key=key),self.assertRaises(ValueError):e.validar(bad,LIBRO,bruto)

    def test_ejes_incorrectos_no_se_convierten_en_exito(self):
        self.assertEqual(self.crear(cap=captura(90))['contraste_estimado']['estado'],'no_coherente')

    def test_abstencion_y_fuente_no_cubierta(self):
        p=copy.deepcopy(PRED);p['totales']=None
        for out in (self.crear(pred=p),self.crear(masa_propia=True)):
            self.assertEqual(out['estado'],'no_estimable');self.assertIsNone(out['masa_estimada_kn_s2_m'])
            self.assertIsNone(out['contraste_estimado']);self.assertTrue(out['motivos'])

    def test_captura_config_tipada(self):
        self.assertEqual(validar_captura_configuracion(CONFIG,'kN_m_C','21.1.0')['tolerancia_union_m'],.001)
        for k,v in [('retorno',True),('retorno',1),('tolerancia_union_m',.001),('tolerancia_union_m','NaN'),
                    ('tolerancia_union_m','1e999'),('tolerancia_union_m','0'),('unidades','N_mm_C'),('version_etabs','22')]:
            bad={**CONFIG,k:v}
            with self.subTest(k=k,v=v),self.assertRaises(ValueError):validar_captura_configuracion(bad,'kN_m_C','21.1.0')
