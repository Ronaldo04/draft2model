import sys
import os
import tempfile
import time
from pathlib import Path
import unittest
from draft2model.adaptador_etabs import AdaptadorEtabs, ConfiguracionPuente


class SalidaHeredadaTests(unittest.TestCase):
    def test_descendiente_con_salida_heredada_no_retiene_al_cliente(self):
        with tempfile.TemporaryDirectory() as temp:
            work=Path(temp);script=work/'puente.py'
            script.write_text('''import sys,subprocess,json
from pathlib import Path
a=sys.argv[1:];s=json.loads(Path(a[a.index('-Solicitud')+1]).read_bytes());r=Path(a[a.index('-Respuesta')+1])
child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(3)'],stdout=sys.stdout,stderr=sys.stderr,close_fds=False)
Path(__file__).with_suffix('.pid').write_text(str(child.pid),encoding='ascii')
r.write_text(json.dumps({'contrato':'draft2model.etabs_respuesta','version_contrato':'0.1.0','id_solicitud':s['id'],'operacion':'diagnosticar','modo_ejecucion':'doble','estado':'ok','datos':{},'avisos':[]}),encoding='utf-8')
''',encoding='utf-8')
            adapter=AdaptadorEtabs(ConfiguracionPuente.doble(work,(sys.executable,str(script)),timeout_s=2))
            start=time.monotonic()
            try:
                response=adapter.diagnosticar()
                self.assertLess(time.monotonic()-start,2)
                self.assertEqual(response.modo_ejecucion,'doble')
            finally:
                # Esperar el proceso exacto: el reloj del padre incluye arranque
                # del puente y no indica cuándo el hijo liberó sus handles.
                pid_file=script.with_suffix('.pid')
                if pid_file.exists() and os.name=='nt':
                    import ctypes
                    from ctypes import wintypes
                    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
                    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
                    kernel.OpenProcess.restype=wintypes.HANDLE
                    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
                    kernel.WaitForSingleObject.restype=wintypes.DWORD
                    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
                    handle=kernel.OpenProcess(0x00100000,False,int(pid_file.read_text()))
                    if handle:
                        try:self.assertEqual(kernel.WaitForSingleObject(handle,10000),0,'El hijo controlado no terminó.')
                        finally:kernel.CloseHandle(handle)
                elif pid_file.exists():
                    time.sleep(4)
