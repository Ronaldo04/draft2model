"""El verificador no acredita omisiones, fuentes cambiadas ni timeouts."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from scripts import verificar_proyecto as verifier


class VerificadorTests(unittest.TestCase):
    def check_run(self,*,skip=False,change=False,timeout=False,policy=False,missing_marker=False,start_failure=False,
                  frontend=None):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp).resolve();(root/'draft2model').mkdir();probe=root/'draft2model/probe.py';probe.write_text('original')
            if frontend is not None:
                (root/'tests').mkdir()
                (root/'tests/probe_frontend.cjs').write_text('throw Error("debe ejecutarse");')
            def run(command,**kwargs):
                if '--test-reporter=tap' in command:
                    self.assertIn('--test',command)
                    self.assertTrue(any(str(x).endswith('probe_frontend.cjs') for x in command))
                    if frontend=='missing':raise OSError('Node no disponible')
                    return subprocess.CompletedProcess(command,1 if frontend=='fail' else 0,
                        '# skipped 1\n' if frontend=='skip' else 'ok 1 - prueba # TODO pendiente\n' if frontend=='todo' else '# skipped 0\n# todo 0\n','')
                elif any('sonda_powershell.ps1' in str(x) for x in command):
                    self.assertNotIn('-ExecutionPolicy', command)
                    self.assertNotIn('-EncodedCommand', command)
                    if start_failure: raise OSError('No se pudo iniciar el host.')
                    if policy:return subprocess.CompletedProcess(command,1,'','PSSecurityException: Requested registry access is not allowed.')
                    output='' if missing_marker else 'DRAFT2MODEL_SONDA_PS51_FILE_OK\n'
                elif 'unittest' in command:
                    if timeout:raise subprocess.TimeoutExpired(command,kwargs['timeout'],stderr='prueba en curso')
                    if change:probe.write_text('cambiado')
                    output="test_a ... skipped 'No se permite enlace'\nOK (skipped=1)\n" if skip else 'test_a ... ok\nOK\n'
                else:output='OK\n'
                return subprocess.CompletedProcess(command,0,output,'')
            with patch.object(verifier,'__file__',str(root/'scripts/verificar_proyecto.py')),patch('sys.argv',['verificar','--salida','tmp/informe.json']),patch.object(verifier.subprocess,'run',side_effect=run),contextlib.redirect_stdout(io.StringIO()):
                code=verifier.main()
            return code,json.loads((root/'tmp/informe.json').read_bytes())

    def test_cero_sin_omisiones_y_fuentes_estables(self):
        code,report=self.check_run();self.assertEqual(code,0);self.assertTrue(report['validacion_local_completa'])

    def test_cero_del_runner_con_omision_no_acredita_verificacion(self):
        code,report=self.check_run(skip=True);self.assertEqual(code,1);self.assertFalse(report['validacion_local_completa'])
        self.assertTrue(next(x for x in report['comprobaciones'] if x['nombre']=='suite')['omisiones'])

    def test_fuentes_modificadas_no_acreditan_verificacion(self):
        code,report=self.check_run(change=True);self.assertEqual(code,1);self.assertFalse(report['archivos_estables_durante_ejecucion'])

    def test_timeout_conserva_fallo_y_no_acredita(self):
        code,report=self.check_run(timeout=True);self.assertEqual(code,1);self.assertEqual(next(x for x in report['comprobaciones'] if x['nombre']=='suite')['codigo'],124)

    def test_interfaz_se_ejecuta_y_fallo_no_acredita(self):
        for state in ('ok','fail','missing'):
            with self.subTest(state=state):
                code,report=self.check_run(frontend=state)
                check=next(x for x in report['comprobaciones'] if x['nombre']=='interfaz')
                self.assertEqual(check['codigo'],{'ok':0,'fail':1,'missing':127}[state])
                self.assertEqual(code,0 if state=='ok' else 1)
                self.assertEqual(report['validacion_local_completa'],state=='ok')

    def test_interfaz_omisiones_y_todo_no_acreditan(self):
        for state in ('skip','todo'):
            with self.subTest(state=state):
                code,report=self.check_run(frontend=state)
                self.assertEqual(code,1)
                self.assertTrue(next(x for x in report['comprobaciones'] if x['nombre']=='interfaz')['omisiones'])

    @unittest.skipUnless(os.name=='nt', 'Sonda Windows PowerShell solo en Windows.')
    def test_politica_bloqueada_no_se_omite_ni_acredita(self):
        code,report=self.check_run(policy=True)
        self.assertEqual(code,1);self.assertFalse(report['validacion_local_completa'])
        self.assertEqual(report['bloqueos_entorno'][0]['comprobacion'],'powershell_scripts')
        self.assertEqual(report['bloqueos_entorno'][0]['codigo'],1)
        self.assertEqual(len(report['comprobaciones']),4)
        self.assertEqual(next(x for x in report['comprobaciones'] if x['nombre']=='suite')['codigo'],0)

    @unittest.skipUnless(os.name=='nt', 'Sonda Windows PowerShell solo en Windows.')
    def test_sonda_sin_marca_no_es_exito(self):
        code,report=self.check_run(missing_marker=True)
        self.assertEqual(code,1);self.assertEqual(report['bloqueos_entorno'][0]['codigo'],126)

    @unittest.skipUnless(os.name=='nt', 'Sonda Windows PowerShell solo en Windows.')
    def test_host_que_no_arranca_conserva_informe(self):
        code,report=self.check_run(start_failure=True)
        self.assertEqual(code,1);self.assertEqual(report['bloqueos_entorno'][0]['codigo'],127)
