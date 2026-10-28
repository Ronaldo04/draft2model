"""Candidato Codex 262 (reuso de la preparación de malla), adaptado a tests/ sin tmp. Igualdad completa de planes y aislamiento de instantáneas; sin ETABS ni red."""
from copy import deepcopy
import dataclasses
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from draft2model import reuso_preparacion as reuse
from draft2model import malla_preparacion as mp
from tests.test_liquidos_ruta201 import CasoLiquidos
from tests import test_contenido_liquidos_258 as contenido_fixture



class SnapshotTests(unittest.TestCase):
    def snapshot(self):
        geometry={'vertices':[1,2]}; config={'revision':{'estado':'borrador'},'masa':1}
        body={'nodos':[{'id':'N1'}]}
        body['huella_preparacion']=hashlib.sha256(reuse._canon(body)).hexdigest()
        snapshot=reuse.sellar(geometry,config,body,reuse.huellas(geometry,config))
        return geometry,config,body,snapshot

    def test_copias_aisladas_y_original_no_mutado(self):
        g,c,p,s=self.snapshot()
        first=reuse.obtener(s,g,c)
        self.assertEqual(first,p)
        first['nodos'][0]['id']='ALTERADO'
        p['nodos'][0]['id']='OTRA_MUTACION'
        self.assertEqual(reuse.obtener(s,g,c)['nodos'][0]['id'],'N1')

    def test_cualquier_cambio_de_entrada_invalida_incluso_revision(self):
        g,c,p,s=self.snapshot()
        for a,b in [({'vertices':[1,3]},c),(g,dict(c,masa=2)),(g,dict(c,revision={'estado':'aprobado'}))]:
            self.assertIsNone(reuse.obtener(s,a,b))

    def test_alteracion_interna_no_se_reutiliza(self):
        g,c,p,s=self.snapshot()
        self.assertIsNone(reuse.obtener(dataclasses.replace(s,contenido=b'{}'),g,c))
        self.assertIsNone(reuse.obtener({},g,c))
        self.assertIsNone(reuse.obtener(s,g,{'masa':float('nan')}))

    def test_mutacion_durante_calculo_y_preparacion_incoherente_rechazadas(self):
        g,c,p,s=self.snapshot()
        with self.assertRaises(ValueError):reuse.sellar(g,dict(c,masa=3),p,s.entradas)
        with self.assertRaises(ValueError):reuse.sellar(g,c,dict(p,huella_preparacion='a'*64),s.entradas)

    def test_planes_completos_iguales_una_preparacion_en_lugar_de_dos(self):
        records=[]
        for scenario in ('horizontal','inclinado','vertical','conectados'):
            with self.subTest(escenario=scenario):
                case=CasoLiquidos()
                try:
                    case.setUp()
                    config=case.aprobar_en_disco(case.montar_liquidos(scenario,'ausente_confirmado',patrones=()))
                    original=mp.preparar_malla
                    with patch.object(reuse,'obtener',return_value=None),patch.object(mp,'preparar_malla',wraps=original) as calls:
                        baseline=case.plan(config)
                        before=calls.call_count
                    with patch.object(mp,'preparar_malla',wraps=original) as calls:
                        after_plan=case.plan(config)
                        after=calls.call_count
                    self.assertEqual(baseline,after_plan)
                    self.assertEqual(before,2)
                    self.assertEqual(after,1)
                    records.append({'escenario':scenario,'preparaciones_antes':before,'despues':after,
                                    'plan_sha256':hashlib.sha256(reuse._canon(after_plan)).hexdigest()})
                finally:
                    case.doCleanups()
        self.assertEqual(len(records),len({r['plan_sha256'] for r in records}))   # comparación en memoria; sin artefactos

    def test_plan_con_contenido_y_liquidos_identico(self):
        case=contenido_fixture.ContenidoTests()
        try:
            case.setUp()
            config=case.montar_contenido()
            config['revision']={'estado':'borrador','aprobacion':None}
            config=case.aprobar_en_disco(config)
            original=mp.preparar_malla
            with patch.object(reuse,'obtener',return_value=None),patch.object(mp,'preparar_malla',wraps=original) as calls:
                baseline=case.plan(config)
                self.assertEqual(calls.call_count,2)
            with patch.object(mp,'preparar_malla',wraps=original) as calls:
                actual=case.plan(config)
                self.assertEqual(calls.call_count,1)
            self.assertEqual(actual,baseline)
            self.assertAlmostEqual(actual['contenido_masa']['peso_total_kn'],220.)
        finally:
            case.doCleanups()


if __name__=='__main__':unittest.main()
