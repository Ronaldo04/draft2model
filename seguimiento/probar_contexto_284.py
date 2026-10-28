"""Candidato282 aislado: mutaciones, equivalencia de planes y medición de comparación completa."""
from pathlib import Path
import copy
import hashlib
import importlib.util
import json
import os
import sys
import time
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'tmp/runtime_qa_276'
os.environ['TEMP']=os.environ['TMP']=str(ROOT/'tmp/t267root')
sys.path.insert(0,str(RUNTIME))
from draft2model import particion_superficies as ps, malla_preparacion as mp
from tests.test_particion_superficies import geometria
from tests.test_liquidos_ruta201 import CasoLiquidos
from tests.test_contenido_liquidos_258 import ContenidoTests

CANDIDATE=ROOT/'tmp/candidato_contexto_282/particion_superficies.py'
spec=importlib.util.spec_from_file_location('draft2model._candidato_contexto282',CANDIDATE)
cand=importlib.util.module_from_spec(spec)
spec.loader.exec_module(cand)
source_before=CANDIDATE.read_bytes()
plan_hashes=[]

def fixture():
    return geometria({'a':(0.,0.,0.),'b':(1.,0.,0.),'c':(1.,1.,0.),'d':(0.,1.,0.)},('a','b','c','d'))

class ContextoTests(unittest.TestCase):
    def test_misma_fuente_y_particion_completa(self):
        g=fixture(); ctx=cand._ContextoGeometria(g)
        self.assertEqual(ctx.verificar(g)[0],ps._sha(g))
        self.assertEqual(cand.particionar_superficie(g,'S1',_contexto=ctx),ps.particionar_superficie(g,'S1'))

    def test_cambios_numericos_y_de_tipo_se_rechazan(self):
        g=fixture(); ctx=cand._ContextoGeometria(g)
        for value in (True,1,1.1,float('nan')):
            changed=copy.deepcopy(g); changed['vertices'][1]['x']=value
            with self.subTest(value=str(value)),self.assertRaises(cand.ErrorParticion):ctx.verificar(changed)

    def test_metadatos_y_ciclos_se_rechazan(self):
        g=fixture(); ctx=cand._ContextoGeometria(g)
        changed=copy.deepcopy(g); changed['procedencia']['descripcion']='Otra fuente'
        with self.assertRaises(cand.ErrorParticion):ctx.verificar(changed)
        changed=copy.deepcopy(g);changed['revision']['ciclo']=changed
        with self.assertRaises(cand.ErrorParticion):ctx.verificar(changed)

    def test_orden_distinto_equivalente_y_fallback_completo(self):
        g=fixture();ctx=cand._ContextoGeometria(g)
        reordered=dict(reversed(list(g.items())))
        self.assertNotEqual(cand._binario_local(g),cand._binario_local(reordered))
        self.assertEqual(ctx.verificar(reordered)[0],ps._sha(g))
        with patch.object(cand,'_binario_local',return_value=None):
            fallback=cand._ContextoGeometria(g)
            self.assertEqual(fallback.verificar(g)[0],ps._sha(g))
            changed=copy.deepcopy(g);changed['vertices'][1]['x']=2.
            with self.assertRaises(cand.ErrorParticion):fallback.verificar(changed)

    def test_fuente_no_mutada(self):
        g=fixture();before=copy.deepcopy(g);ctx=cand._ContextoGeometria(g)
        for _ in range(3):ctx.verificar(g)
        self.assertEqual(g,before)

    def compare_plan(self,case,config):
        mp.preparar_malla.cache_clear()
        baseline=case.plan(config)
        mp.preparar_malla.cache_clear()
        with patch.object(ps,'_ContextoGeometria',cand._ContextoGeometria),patch.object(cand,'_binario_local',wraps=cand._binario_local) as calls:
            actual=case.plan(config)
            self.assertGreater(calls.call_count,1,'La cache no debe ocultar la ejecución del candidato.')
        self.assertEqual(actual,baseline)
        plan_hashes.append(hashlib.sha256(json.dumps(actual,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest())

    def test_cuatro_planes_completos_con_liquidos(self):
        for scenario in ('horizontal','vertical','inclinado','conectados'):
            with self.subTest(scenario=scenario):
                case=CasoLiquidos()
                try:
                    case.setUp()
                    config=case.aprobar_en_disco(case.montar_liquidos(scenario,'ausente_confirmado',patrones=()))
                    self.compare_plan(case,config)
                finally:case.doCleanups()

    def test_plan_completo_con_contenido(self):
        case=ContenidoTests()
        try:
            case.setUp();config=case.montar_contenido();config['revision']={'estado':'borrador','aprobacion':None}
            self.compare_plan(case,case.aprobar_en_disco(config))
        finally:case.doCleanups()

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContextoTests))
    assert CANDIDATE.read_bytes()==source_before
    report={'tests':result.testsRun,'errores':len(result.errors),'fallos':len(result.failures),'omitidas':len(result.skipped),
            'planes_completos_sha256':plan_hashes,'sha256_candidato':hashlib.sha256(source_before).hexdigest(),
            'base':str(RUNTIME.relative_to(ROOT)),'producto_sin_modificar':True,'api_remota':False,'etabs_ejecutado':False,
            'limites':'Comparación de planes sintéticos y mutaciones; no piloto completo ni aprobación de ingeniería. Candidato NO integrado.',
            'goal_completo':False}
    if result.wasSuccessful():
        path=ROOT/'data/private/pueblo-libre-002/geometrias/25ef94672fac4e53863701b55e32f97d/geometria.json'
        raw=path.read_bytes();g=json.loads(raw);timing={}
        for label,cls in [('base',ps._ContextoGeometria),('candidato',cand._ContextoGeometria)]:
            ctx=cls(g);start=time.perf_counter()
            for _ in range(30):
                self_sha,_=ctx.verificar(g)
            timing[label]={'verificaciones':30,'segundos':time.perf_counter()-start,'sha_fuente':self_sha}
        assert timing['base']['sha_fuente']==timing['candidato']['sha_fuente']
        assert raw==path.read_bytes()
        report['medicion_comparacion_completa']=timing
        report['nota_tiempos']='Solo comparación de contexto, no tiempo global de malla o verificación de evidencia.'
    (ROOT/'seguimiento/REVISION_CONTEXTO_284.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=True))
    raise SystemExit(0 if result.wasSuccessful() else 1)
