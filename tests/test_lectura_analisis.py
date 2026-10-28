"""Lector con transporte Python doble y metadatos SDK; nunca ejecuta ETABS."""
from dataclasses import replace
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from draft2model import adaptador_etabs as ad
from draft2model.lectura_analisis import LectorAnalisis,SCRIPT
from draft2model.normalizacion_etabs import registrar_resultados
from draft2model.resultados_estructurales import huella_declaracion
from draft2model.evidencia_analisis import verificar_evidencia
from tests import test_revision_analisis as fixture_analisis


TRANSPORTE=r'''
from datetime import datetime,timezone
import json,os,sys,time
from pathlib import Path
a=sys.argv[1:];s=json.loads(Path(a[a.index('-Solicitud')+1]).read_bytes());r=Path(a[a.index('-Respuesta')+1])
assert s['operacion']=='leer_tablas' and 'id_proceso' not in s and s['combinaciones']==[]
if os.environ.get('ESPERAR'):time.sleep(5)
if os.environ.get('FALSO_EXITO'):
 r.write_text(json.dumps({'estado':'ok','exitosa':True}));sys.exit(0)
if os.environ.get('ALTERAR'):Path(os.environ['ALTERAR']).write_bytes(b'alterado')
tables=[]
for name in s['tablas']:
 field='Case' if name=='Modal Periods And Frequencies' else 'OutputCase'
 row={field:('AJENO' if os.environ.get('FILA_AJENA') else s['casos'][0]),'Story':'N1','Direction':'X','Drift':'0.0001'}
 if os.environ.get('FILA_MALFORMADA'):row['Extra']=['no texto']
 tables.append({'clave':name,'version_tabla':1,'campos':[field,'Story','Direction','Drift'],'filas':[row]})
out={'contrato':'draft2model.etabs_respuesta','version_contrato':'0.1.0','id_solicitud':s['id'],'operacion':'leer_tablas',
 'modo_ejecucion':'real' if os.environ.get('MODO_AJENO') else 'doble','estado':'ok','avisos':['Transporte sintetico.'],
 'fin_utc':None if os.environ.get('FECHA_INVALIDA') else datetime.now(timezone.utc).isoformat(),'datos':{
 'modelo':s['modelo_esperado']+'otro' if os.environ.get('MODELO_AJENO') else s['modelo_esperado'],
 'version_etabs':'otra' if os.environ.get('VERSION_AJENA') else s['version_etabs_esperada'],
 'unidades':'N_m_C' if os.environ.get('UNIDADES_AJENAS') else s['unidades_esperadas'],
 'casos':s['casos'],'combinaciones':[],'estado_casos':{c:(3 if os.environ.get('ESTADO_INCOMPLETO') else 4) for c in s['casos']},
 'tablas':tables,'instancia':'activa' if os.environ.get('INSTANCIA_AJENA') else 'nueva','id_proceso':1234,
 'inicio_proceso_utc':datetime.now(timezone.utc).isoformat(),'instancia_cerrada':not bool(os.environ.get('NO_CERRADA')),
 'sha256_modelo_verificado':s['sha256_edb'],'corrida_analisis_id':s['corrida_analisis_id'],
 'analisis_ejecutado':False,'aprueba_resultados':False}}
r.write_text(json.dumps(out),encoding='utf-8')
'''


class LecturaAnalisisTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixture_analisis.AnalisisWebTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        prepared=self.fixture.prepare();self.fixture.execute(prepared);result=self.fixture.finish(prepared)
        self.assertEqual(result['estado'],'aceptado')
        self.app=self.fixture.app;self.case=self.fixture.case;self.run=self.case/'analisis_etabs'/result['corrida_id']
        self.work=self.case/'lecturas_etabs';self.work.mkdir()
        script=self.fixture.fixture.base.trabajo/'lector_doble.py';script.write_text(TRANSPORTE,encoding='utf-8')
        self.command=(sys.executable,str(script));self.environment={}
        self.config=ad.ConfiguracionPuente.doble(self.work,self.command,self.app.ejecucion.motor_lock,entorno=self.environment)
        self.reader=LectorAnalisis(self.config)

    def prepare(self,reader=None,**kwargs):
        return (reader or self.reader).preparar_lectura(self.app.raiz,self.fixture.caso,self.run,
            tablas=kwargs.get('tablas',['Story Drifts']),casos=kwargs.get('casos',['EST']))

    def test_preparar_no_lanza_y_lectura_no_copia_edb_ni_recalcula(self):
        before=(self.run/'analizado.edb').read_bytes()
        with patch('subprocess.Popen',side_effect=AssertionError('No proceso en preparar')):
            prepared=self.prepare()
        self.assertEqual(list(prepared.solicitud.carpeta.glob('*.edb')),[])
        with self.assertRaises(ad.ErrorAdaptador):self.reader.ejecutar_lectura(prepared)
        result=self.reader.ejecutar_lectura(prepared,confirmar_lectura=True)
        self.assertEqual(result.operacion,'leer_tablas');self.assertEqual(result.datos['estado_casos'],{'EST':4})
        self.assertTrue(result.datos['instancia_cerrada']);self.assertFalse(result.datos['analisis_ejecutado'])
        self.assertEqual((self.run/'analizado.edb').read_bytes(),before)
        self.assertTrue((prepared.solicitud.carpeta/'aceptacion_lectura.json').exists())
        self.assertFalse(self.reader.estado_incierto.exists())
        with self.assertRaises(ad.ErrorAdaptador):self.reader.ejecutar_lectura(prepared,confirmar_lectura=True)

    def test_compatibilidad_normalizador_y_evidencia_sin_motor(self):
        prepared=self.prepare();response=self.reader.ejecutar_lectura(prepared,confirmar_lectura=True)
        source=self.fixture.model/'configuracion.json';config=json.loads(source.read_bytes())
        mapping={'contrato':'draft2model.mapeo_resultados_etabs','version':'0.1.0','caso':self.fixture.caso,
            'datos_sinteticos':True,'huella_configuracion':prepared.evidencia['configuracion']['huella'],
            'sha256_respuesta':hashlib.sha256(prepared.solicitud.respuesta.read_bytes()).hexdigest(),
            'modelo':{'archivo':(self.run/'analizado.edb').relative_to(self.case).as_posix(),
                      'sha256':prepared.evidencia['sha256_edb_analizado']},
            'unidades_api_esperadas':'kN_m_C','version_etabs_esperada':prepared.evidencia['version_etabs'],
            'selectores':[{'id':'DX','variable':'deriva','caso':'EST','direccion':'X','ubicacion':'N1',
                          'tabla':'Story Drifts','filtros':{'OutputCase':'EST','Story':'N1','Direction':'X'},
                          'campo_valor':'Drift','unidad_origen':'1'}],'revision':None}
        mapping['revision']={'estado':'aprobado','aprobacion':{'revisor_declarado':'Prueba sintetica',
            'fecha':'2026-10-17','motivo':'Solo software','alcance':'Fila fabricada de prueba',
            'huella_contenido':huella_declaracion(mapping)}}
        path=prepared.solicitud.carpeta/'mapeo_prueba.json';path.write_text(json.dumps(mapping),encoding='utf-8')
        with patch('subprocess.Popen',side_effect=AssertionError('Normalizacion offline')):
            target=registrar_resultados(self.app.raiz,source,prepared.solicitud.respuesta,path)
            evidence=verificar_evidencia(self.app.raiz,self.fixture.caso,target.name,self.run)
        self.assertEqual(evidence['analisis']['corrida_id'],self.run.name)
        self.assertFalse(evidence['aprueba_resultados'])
        self.assertEqual(json.loads((target/'resultados.json').read_bytes())['resultados'][0]['valor'],0.0001)

    def test_fuentes_alteradas_antes_de_lanzar_no_crean_proceso(self):
        for path in (self.run/'analizado.edb',self.fixture.approval/'aprobacion.json',self.fixture.model/'modelo.edb',self.fixture.fixture.base.original):
            with self.subTest(path=path.name):
                prepared=self.prepare();raw=path.read_bytes();path.write_bytes(raw+b'alterado')
                with patch('subprocess.Popen',side_effect=AssertionError('Fuente alterada no lanza')):
                    with self.assertRaises(ValueError):self.reader.ejecutar_lectura(prepared,confirmar_lectura=True)
                self.assertFalse(self.reader.estado_incierto.exists());path.write_bytes(raw)

    def test_solicitud_alterada_y_modo_casos_no_admitidos(self):
        for kwargs in ({'casos':['OTRO']},{'casos':[]},{'tablas':['A','A']},{'tablas':[]}):
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.prepare(**kwargs)
        other=LectorAnalisis(replace(self.config,modo='real'))
        with self.assertRaises(ValueError):self.prepare(other)
        prepared=self.prepare();prepared.solicitud.contenido['casos']=['AJENO']
        with patch('subprocess.Popen',side_effect=AssertionError('Solicitud alterada no lanza')):
            with self.assertRaises(ValueError):self.reader.ejecutar_lectura(prepared,confirmar_lectura=True)

    def test_incoherencias_no_se_aceptan_y_conservan_incertidumbre(self):
        flags=['FILA_AJENA','FILA_MALFORMADA','MODO_AJENO','MODELO_AJENO','VERSION_AJENA','UNIDADES_AJENAS',
               'ESTADO_INCOMPLETO','INSTANCIA_AJENA','NO_CERRADA','FALSO_EXITO','FECHA_INVALIDA']
        for index,flag in enumerate(flags):
            with self.subTest(flag=flag):
                config=ad.ConfiguracionPuente.doble(self.work,self.command,self.case/('doble_'+str(index)+'.lock'),entorno={flag:'1'})
                reader=LectorAnalisis(config);prepared=self.prepare(reader)
                with self.assertRaises((ValueError,RuntimeError)):reader.ejecutar_lectura(prepared,confirmar_lectura=True)
                self.assertTrue(reader.estado_incierto.exists())
                self.assertFalse((prepared.solicitud.carpeta/'aceptacion_lectura.json').exists())

    def test_fuente_cambiada_durante_lectura_y_timeout(self):
        self.environment['ALTERAR']=str(self.run/'analizado.edb');prepared=self.prepare()
        raw=(self.run/'analizado.edb').read_bytes()
        with self.assertRaises(ValueError):self.reader.ejecutar_lectura(prepared,confirmar_lectura=True)
        self.assertTrue(self.reader.estado_incierto.exists());(self.run/'analizado.edb').write_bytes(raw)
        reader=LectorAnalisis(ad.ConfiguracionPuente.doble(self.work,self.command,self.case/'timeout.lock',
            timeout_s=0.3,entorno={'ESPERAR':'1'}));prepared=self.prepare(reader)
        with self.assertRaises(ad.ErrorTiempo):reader.ejecutar_lectura(prepared,confirmar_lectura=True)
        self.assertTrue(reader.estado_incierto.exists())

    def test_case_modal_conservado_y_work_externo_rechazado(self):
        prepared=self.prepare(tablas=['Modal Periods And Frequencies'])
        response=self.reader.ejecutar_lectura(prepared,confirmar_lectura=True)
        self.assertIn('Case',response.datos['tablas'][0]['campos'])
        external=LectorAnalisis(replace(self.config,trabajo=self.fixture.fixture.base.trabajo))
        with self.assertRaises(ValueError):self.prepare(external)


class ScriptLectorTests(unittest.TestCase):
    def test_script_sin_recalculo_guardado_copia_ni_instancia_activa(self):
        source=SCRIPT.read_text(encoding='utf-8')
        for forbidden in ('.RunAnalysis(','.Save(','.Copy(','.GetObject(','.GetObjectProcess(', 'SetRunCaseFlag'):
            self.assertNotIn(forbidden,source)
        self.assertIn('CreateObjectProgID',source);self.assertIn('ApplicationExit($false)',source)
        self.assertIn('$owned.Handle',source);self.assertIn('$owned.WaitForExit',source)

    @unittest.skipUnless(os.name=='nt' and ad.POWERSHELL_51.is_file(),'Parser Windows PowerShell5.1')
    def test_sintaxis_ps_y_firmas_sdk_por_metadatos_sin_com(self):
        code="""
$tokens=$null;$errors=$null
$null=[Management.Automation.Language.Parser]::ParseFile($env:D2M_LECTOR_PS,[ref]$tokens,[ref]$errors)
if($errors.Count){$errors | ForEach-Object {$_.Message};exit 1}
if(Test-Path -LiteralPath $env:D2M_LECTOR_DLL){
 $assembly=[Reflection.Assembly]::ReflectionOnlyLoadFrom($env:D2M_LECTOR_DLL)
 $file=$assembly.GetType('ETABSv1.cFile').GetMethod('OpenFile')
 $close=$assembly.GetType('ETABSv1.cOAPI').GetMethod('ApplicationExit')
 $status=$assembly.GetType('ETABSv1.cAnalyze').GetMethod('GetCaseStatus')
 $table=$assembly.GetType('ETABSv1.cDatabaseTables').GetMethod('GetTableForDisplayArray')
 if($file.ReturnType.FullName -ne 'System.Int32' -or $file.GetParameters().Count -ne 1 -or
    $close.GetParameters()[0].ParameterType.FullName -ne 'System.Boolean' -or
    $status.GetParameters().Count -ne 3 -or $table.GetParameters().Count -ne 7){exit 2}
}
'Parser y metadatos correctos'
"""
        result=subprocess.run([str(ad.POWERSHELL_51),'-NoProfile','-NonInteractive','-Command',code],
            env={**os.environ,'D2M_LECTOR_PS':str(SCRIPT),'D2M_LECTOR_DLL':str(ad.DLL_ETABS)},capture_output=True,timeout=20)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__':unittest.main()
