"""Integración con modelo construido real en disco y transporte Python fabricado; sin ETABS."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from draft2model import adaptador_etabs as ad
from draft2model import revision_modelo as rm
from draft2model import verificacion_modelo_guardado as lector
from draft2model import vinculo_verificacion_modelo as v
from tests import test_revision_modelo as modelos_fixture
from tests import test_verificacion_modelo_guardado as datos_lector

WORKER = r'''
import json,sys
from pathlib import Path
args=sys.argv
s=json.loads(Path(args[args.index('-Solicitud')+1]).read_bytes())
obs=json.loads(Path(args[1]).read_bytes())
d={'sha256_antes':s['sha256_edb'],'sha256_despues':s['sha256_edb'],'instancia':'doble',
   'id_proceso':None,'inicio_proceso_utc':None,'instancia_cerrada':True,
   'firmas_verificadas':31,'version_dll':'DOBLE_NO_CSI','consulta':s['consulta'],
   'lecturas':obs,'guardado':False,'modificaciones':[],'version_lector':s['version_lector']}
r={'contrato':'draft2model.etabs_respuesta','version_contrato':'0.1.0','id_solicitud':s['id'],
   'operacion':s['operacion'],'modo_ejecucion':'doble','estado':'ok','datos':d,'avisos':[]}
Path(args[args.index('-Respuesta')+1]).write_text(json.dumps(r),encoding='utf-8')
'''


class VinculoTests(unittest.TestCase):
    def setUp(self):
        self.f = modelos_fixture.RevisionModeloTests('test_borrador_no_hereda_aprobacion_y_aprobacion_propia')
        self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.folder = self.f.register()
        self.state = rm.consultar(self.f.root,self.f.case,self.folder.name)
        exp = lector.expectativa_desde_plan(self.f.plan)
        self.obs = datos_lector.lecturas(datos_lector.modelo_desde_expectativa(exp))
        self.criteria = copy.deepcopy(datos_lector.CRITERIOS)
        self.worker = self.f.base.trabajo/'lector_vinculado_falso.py'
        self.worker.write_text(WORKER,encoding='utf-8')
        self.obsfile = self.worker.with_suffix('.json')
        self.obsfile.write_bytes(v._bytes(self.obs))
        self.work = self.worker.parent/'corridas_vinculadas';self.work.mkdir()
        self.ver = lector.VerificadorModeloGuardado(ad.ConfiguracionPuente.doble(
            self.work,(sys.executable,str(self.worker),str(self.obsfile))))

    def run_read(self, **options):
        return v.verificar(self.f.root,self.f.case,self.folder.name,
            huella_modelo=self.state['huella_modelo'],verificador=self.ver,
            criterios=self.criteria,confirmar_lectura=True,**options)

    def test_lee_snapshot_publica_y_reproduce_sin_aprobar(self):
        before={p.name:p.read_bytes() for p in self.folder.iterdir()}
        target=self.run_read()
        record=v.consultar(self.f.root,self.f.case,target.name)
        self.assertEqual(record['modelo'],self.folder.name)
        self.assertEqual(record['modo'],'doble')
        self.assertFalse(record['aprueba_modelo'] or record['autoriza_analisis'])
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.folder.iterdir()})
        self.assertEqual(record['resultado']['sha256_edb'],self.state['origen']['sha256_modelo'])

    def test_discrepancias_se_conservan_sin_convertirlas_en_aprobacion(self):
        nombre=next(iter(self.obs['puntos']['coordenadas']))
        self.obs['puntos']['coordenadas'][nombre][0]+=1
        self.obsfile.write_bytes(v._bytes(self.obs))
        target=self.run_read();r=v.consultar(self.f.root,self.f.case,target.name)
        self.assertEqual(r['resultado']['estado'],'discrepancias')
        self.assertFalse(r['resultado']['verificado'])

    def test_confirmacion_huella_y_modo_antes_de_lanzar(self):
        with self.assertRaises(ValueError):
            v.verificar(self.f.root,self.f.case,self.folder.name,huella_modelo=self.state['huella_modelo'],
                verificador=self.ver,criterios=self.criteria)
        with self.assertRaises(ValueError):
            v.verificar(self.f.root,self.f.case,self.folder.name,huella_modelo='0'*64,
                verificador=self.ver,criterios=self.criteria,confirmar_lectura=True)
        from dataclasses import replace
        self.ver.config=replace(self.ver.config,modo='real')
        with self.assertRaises(ValueError):self.run_read()
        self.assertEqual(list(self.work.iterdir()),[])

    def test_modelo_cambia_tras_lectura_no_publica_vinculo(self):
        original=self.ver.ejecutar_verificacion
        def cambiar(*a,**kw):
            result=original(*a,**kw)
            (self.folder/'modelo.edb').write_bytes(b'alterado tras leer')
            return result
        with patch.object(self.ver,'ejecutar_verificacion',side_effect=cambiar):
            with self.assertRaises(ValueError):self.run_read()
        self.assertFalse((self.folder.parent.parent/'verificaciones_modelo').exists())

    def test_respuesta_reescrita_con_hashes_rehechos_se_recalcula(self):
        target=self.run_read()
        response=json.loads((target/'respuesta.json').read_bytes())
        nombre=next(iter(response['datos']['lecturas']['puntos']['coordenadas']))
        response['datos']['lecturas']['puntos']['coordenadas'][nombre][0]+=1
        (target/'respuesta.json').write_bytes(v._bytes(response))
        result=json.loads((target/'resultado_verificacion.json').read_bytes())
        result['sha256_respuesta']=v._sha((target/'respuesta.json').read_bytes())
        (target/'resultado_verificacion.json').write_bytes(v._bytes(result))
        record=json.loads((target/'registro.json').read_bytes())
        record['archivos']={n:v._sha((target/n).read_bytes()) for n in v.ARCHIVOS}
        (target/'registro.json').write_bytes(v._bytes(record))
        with self.assertRaises(ValueError):v.consultar(self.f.root,self.f.case,target.name)

    def test_geometria_fuente_alterada_invalida_consulta(self):
        target=self.run_read();self.f.base.original.write_bytes(b'original distinto')
        with self.assertRaises(ValueError):v.consultar(self.f.root,self.f.case,target.name)
