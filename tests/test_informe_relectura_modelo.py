"""Informe real sobre fixture; las fuentes de relectura son dobles explícitos, sin ETABS ni red."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from draft2model.evidencia_analisis import verificar_evidencia
from draft2model.revision_entregables import ServicioEntregables
from draft2model.revision_visual import RevisionLocal
from tests.fixture_etabs import extraer_evidencia

CASO='demo-integrada-sintetica'
RESULTADO='72c06efb3bfe477bb1fe565809aeddec'
ANALISIS='adf97fbc232141e8ae687872c0d71232'
J='5'*32; V='6'*32; S='c'*64; P='d'*64


class InformeRelecturaTests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        bundle=extraer_evidencia(Path(tmp.name).resolve()/'fixture')
        self.app=RevisionLocal(bundle/'private');self.service=ServicioEntregables(self.app)
        run=self.app.raiz/CASO/'analisis_etabs'/ANALISIS
        shutil.copytree(bundle/'analisis'/ANALISIS,run)
        self.fp=self.app.expediente(CASO)[2]
        ev=verificar_evidencia(self.app.raiz,CASO,RESULTADO,run)
        self.assertNotEqual(ev['analisis']['sha256_entrada'],ev['analisis']['sha256_edb_analizado'])
        self.result={'estado':'incompleto','verificado':False,'verificacion_global_del_plan':False,
                     'sha256_edb':ev['analisis']['sha256_entrada'],'origen_plan':{'huella_plan':P},
                     'modo':ev['analisis']['modo'],'ejecutable':False,
                     'cobertura_plan':{'sin_lector':['Operación sintética no cubierta']},
                     'unidades':{'leidas':'N_mm_C','plan':'kN_m_C'},
                     'controles_no_afirmados':['efecto_estructural_de_aberturas'],
                     'incompletos':['Falta comprobación sintética.']}
        self.job={'estado':'aceptado','vigente':True,'lectura_comprobada':True,'verificacion_id':V,
                  'expediente_sha256':self.fp,'resultado':self.result}
        self.proof={'sha256_registro':S,'resultado':self.result,'modelo':ev['modelo']['modelo_id'],
                    'huella_modelo':ev['modelo']['huella_modelo'],'modo':ev['analisis']['modo']}
        self.state={'origen':{'sha256_modelo':ev['analisis']['sha256_entrada'],'datos_sinteticos':True}}
        for target in ('subprocess.Popen','urllib.request.urlopen','socket.create_connection'):
            guard=patch(target,side_effect=AssertionError('Sin red ni procesos'))
            guard.start();self.addCleanup(guard.stop)
        self.guards=[patch.object(self.app.verificacion_modelo,'consultar',side_effect=lambda *a:copy.deepcopy(self.job)),
                     patch('draft2model.vinculo_verificacion_modelo.consultar',side_effect=lambda *a:copy.deepcopy(self.proof)),
                     patch('draft2model.vinculo_verificacion_modelo._fuente',side_effect=lambda *a:(copy.deepcopy(self.state),{'huella_plan':P},None))]
        for guard in self.guards:guard.start();self.addCleanup(guard.stop)

    def body(self,**extra):
        return {'caso':CASO,'resultado':RESULTADO,'expediente_sha256':self.fp,'analisis':ANALISIS,
                'contexto':{'titulo':'Relectura sintética incompleta','hipotesis':['Solo software.'],
                            'faltantes':['Ensayo real pendiente.'],'sitio':None},**extra}

    def ref(self):return {'trabajo':J,'id':V,'sha256_registro':S}

    def approve(self,item):
        return {'caso':CASO,'version':item['id'],'expediente_sha256':self.fp,
                'sha256_informe':item['archivos']['informe.json'],'revisor_declarado':'Prueba',
                'fecha':'2026-10-20','motivo':'Revisión documental sintética.','confirmacion_explicita':True}

    def test_incompleto_con_entrada_edb_exacta_se_conserva_sin_aprobar_modelo(self):
        item=self.service.crear(self.body(relectura_modelo=self.ref()))
        self.assertEqual(item['relectura_modelo_seleccionada'],self.ref())
        raw=self.service.archivo(CASO,item['id'],'json',expediente_sha256=self.fp)
        report=json.loads(raw);vm=report['relectura_modelo']
        self.assertEqual(vm['resultado']['estado'],'incompleto')
        self.assertFalse(vm['aprueba_modelo']);self.assertFalse(vm['autoriza_analisis'])
        self.assertFalse(vm['aprueba_resultados']);self.assertEqual(vm['sha256_edb'],self.result['sha256_edb'])
        html=self.service.archivo(CASO,item['id'],'html',expediente_sha256=self.fp).decode('utf-8')
        self.assertIn('N_mm_C',html);self.assertIn('efecto_estructural_de_aberturas',html)
        child=self.service.aprobar(self.approve(item))
        self.assertEqual(child['relectura_modelo_seleccionada'],self.ref())
        self.assertFalse(child['aprueba_resultados'])

    def test_fuente_cambiada_impide_consulta_descarga_y_aprobacion(self):
        item=self.service.crear(self.body(relectura_modelo=self.ref()))
        self.job['vigente']=False
        for op in (lambda:self.service.consultar(CASO,item['id'],expediente_sha256=self.fp),
                   lambda:self.service.archivo(CASO,item['id'],'pdf',expediente_sha256=self.fp),
                   lambda:self.service.aprobar(self.approve(item))):
            with self.assertRaises(ValueError):op()

    def test_rechaza_sha_nulo_y_edb_posterior_al_analisis(self):
        for ref in (None,{**self.ref(),'sha256_registro':'0'*64},{**self.ref(),'extra':1}):
            with self.subTest(ref=ref),self.assertRaises(ValueError):
                self.service.crear(self.body(relectura_modelo=ref))
        self.state['origen']['sha256_modelo']='0'*64
        with self.assertRaises(ValueError):self.service.crear(self.body(relectura_modelo=self.ref()))

    def test_sin_seleccion_no_agrega_evidencia(self):
        item=self.service.crear(self.body())
        self.assertNotIn('relectura_modelo_seleccionada',item)
        report=json.loads(self.service.archivo(CASO,item['id'],'json',expediente_sha256=self.fp))
        self.assertNotIn('relectura_modelo',report)


if __name__=='__main__':unittest.main()
