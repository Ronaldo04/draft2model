"""Análisis mediante transporte fabricado; no conecta con ETABS."""
import json
import sys
import unittest
from unittest import mock
from draft2model import adaptador_etabs as ad
from draft2model.analisis_etabs import AnalizadorEtabs
from tests import test_revision_modelo as fixture_modelo

TRANSPORTE = r'''
import sys,json,hashlib,os
from pathlib import Path
a=sys.argv[1:];s=json.loads(Path(a[a.index('-Solicitud')+1]).read_bytes());r=Path(a[a.index('-Respuesta')+1])
if os.environ.get('ABRUPTO'):sys.exit(1)
p=Path(s['destino']);p.write_bytes(b'ANALIZADO FABRICADO, NO ETABS')
if os.environ.get('ALTERAR'):Path(os.environ['ALTERAR']).write_bytes(b'cambiado')
out={'contrato':'draft2model.etabs_respuesta','version_contrato':'0.1.0','id_solicitud':s['id'],
'operacion':'analizar_modelo','modo_ejecucion':'doble','estado':'ok','avisos':[],
'datos':{'guardado':{'ruta':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()},
'casos_ejecutados':s['casos'],'estados_casos':{n:(3 if os.environ.get('INCOMPLETO') else 4) for n in s['casos']},
'sha256_entrada':s['sha256_entrada'],'analisis_ejecutado':True,'aprueba_resultados':False}}
r.write_text(json.dumps(out),encoding='utf-8')
'''


class AnalisisTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_modelo.RevisionModeloTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.model=self.fixture.register();self.approval=self.fixture.approve(self.model)
        script=self.fixture.base.trabajo/'analizador_doble.py';script.write_text(TRANSPORTE,encoding='utf-8')
        self.config=ad.ConfiguracionPuente.doble(self.fixture.base.corridas,(sys.executable,str(script)))

    def prepare(self, analyzer):
        return analyzer.preparar_analisis(self.fixture.root,self.fixture.case,self.approval.name)

    def test_preparar_no_lanza_y_exito_no_aprueba_resultados(self):
        analyzer=AnalizadorEtabs(self.config)
        with mock.patch('subprocess.Popen',side_effect=AssertionError('No lanzar')): prepared=self.prepare(analyzer)
        raw=(self.model/'modelo.edb').read_bytes()
        result=analyzer.ejecutar_analisis(prepared)
        self.assertTrue(result.datos['analisis_ejecutado']);self.assertFalse(result.datos['aprueba_resultados'])
        self.assertFalse(analyzer.estado_incierto.exists())
        self.assertTrue((prepared.solicitud.carpeta/'aceptacion_analisis.json').exists())
        self.assertEqual(raw,(self.model/'modelo.edb').read_bytes())
        with self.assertRaises(ValueError):analyzer.ejecutar_analisis(prepared)

    def test_origen_cambiado_antes_de_lanzar_impide_proceso(self):
        analyzer=AnalizadorEtabs(self.config);prepared=self.prepare(analyzer)
        self.fixture.base.original.write_bytes(b'cambiado')
        with mock.patch('subprocess.Popen',side_effect=AssertionError('No lanzar')):
            with self.assertRaises(ValueError):analyzer.ejecutar_analisis(prepared)
        self.assertFalse(analyzer.estado_incierto.exists())

    def test_caso_incompleto_y_salida_abrupta_persisten_incertidumbre(self):
        for flag in ('INCOMPLETO','ABRUPTO'):
            with self.subTest(flag=flag):
                config=ad.ConfiguracionPuente.doble(self.fixture.base.corridas,self.config.comando,
                    bloqueo=self.fixture.base.trabajo/(flag+'.lock'),entorno={flag:'1'})
                analyzer=AnalizadorEtabs(config);prepared=self.prepare(analyzer)
                with self.assertRaises((ValueError,RuntimeError)):analyzer.ejecutar_analisis(prepared)
                self.assertTrue(analyzer.estado_incierto.exists())
                self.assertFalse((prepared.solicitud.carpeta/'aceptacion_analisis.json').exists())

    def test_origen_cambiado_durante_proceso_no_acepta(self):
        self.config.entorno={'ALTERAR':str(self.fixture.base.original)}
        analyzer=AnalizadorEtabs(self.config);prepared=self.prepare(analyzer)
        with self.assertRaises(ValueError):analyzer.ejecutar_analisis(prepared)
        self.assertTrue(analyzer.estado_incierto.exists())

    def test_solicitud_en_memoria_alterada_rechazada(self):
        analyzer=AnalizadorEtabs(self.config);prepared=self.prepare(analyzer)
        prepared.solicitud.contenido['casos']=['AJENO']
        with self.assertRaises(ValueError):analyzer.ejecutar_analisis(prepared)


if __name__=='__main__':unittest.main()
