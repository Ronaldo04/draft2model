import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock
from draft2model.__main__ import main
from draft2model.adaptador_etabs import AdaptadorEtabs,ConfiguracionPuente


class CliEtabsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.work=Path(self.temp.name)/'trabajo'

    def cli(self,*args):
        out,err=io.StringIO(),io.StringIO()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            code=main(['etabs','--trabajo',str(self.work),*args])
        return code,out.getvalue(),err.getvalue()

    def test_preparacion_desde_cli_principal_no_inicia_proceso(self):
        with mock.patch('subprocess.Popen',side_effect=AssertionError('No debe ejecutar')):
            code,out,err=self.cli('diagnosticar')
        self.assertEqual(code,0,err)
        data=json.loads(out);self.assertFalse(data['ejecuto_etabs'])
        source=Path(data['solicitud']);self.assertTrue(source.is_absolute())
        self.assertEqual(json.loads(source.read_bytes())['operacion'],'diagnosticar')

    def test_preparar_copia_conserva_original_y_rechaza_duplicado(self):
        import hashlib
        original=Path(self.temp.name)/'plantilla.edb';original.write_bytes(b'fixture no ETABS')
        destination=Path(self.temp.name)/'copia'
        args=('abrir-copia','--plantilla',str(original),'--sha256',hashlib.sha256(original.read_bytes()).hexdigest(),'--destino',str(destination))
        code,out,err=self.cli(*args);self.assertEqual(code,0,err)
        self.assertEqual(original.read_bytes(),(destination/original.name).read_bytes())
        self.assertEqual(json.loads(out)['modo'],'preparado')
        code,_,_=self.cli(*args);self.assertNotEqual(code,0)

    def test_recuperacion_conserva_evidencia(self):
        self.work.mkdir();adapter=AdaptadorEtabs(ConfiguracionPuente.real(self.work))
        adapter.estado_incierto.write_text('{"estado":"motor_incierto"}',encoding='utf-8')
        code,out,err=self.cli('recuperar','--motor-inactivo','--revisor','Prueba sintética','--motivo','Motor de prueba detenido')
        self.assertEqual(code,0,err);self.assertFalse(adapter.estado_incierto.exists())
        self.assertTrue(Path(json.loads(out)['evidencia_archivada']).is_file())
