"""Contrato de comandos: archivos completos, no reemplazo y diagnósticos explícitos."""
import contextlib
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from draft2model.__main__ import main
from draft2model import archivo_plan as a

ROOT = Path(__file__).resolve().parents[1]


class CliPlanTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.input = self.work / 'geometria.json'
        self.input.write_bytes((ROOT/'examples/geometria_sintetica.json').read_bytes())
        self.output = self.work / 'plan.json'

    def cli(self, *args):
        stdout, stderr = StringIO(), StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(['plan-modelado', '--entrada', str(self.input), '--salida', str(self.output), *args])
        return code, stdout.getvalue(), stderr.getvalue()

    def test_plan_reproduce_ejemplo_y_conserva_entrada(self):
        original = self.input.read_bytes()
        code, out, err = self.cli()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.output.read_bytes(), (ROOT/'examples/plan_modelado_sintetico.json').read_bytes())
        self.assertEqual(self.input.read_bytes(), original)
        self.assertIn('cobertura: parcial', out)
        self.assertIn('ejecutable_en_etabs: false', out)
        self.assertFalse(list(self.work.glob('.plan-*')))

    def test_salida_existente_no_se_reemplaza(self):
        self.output.write_bytes(b'contenido anterior')
        code, _, _ = self.cli()
        self.assertEqual(code, 1)
        self.assertEqual(self.output.read_bytes(), b'contenido anterior')

    def test_entrada_como_salida_se_rechaza(self):
        original = self.input.read_bytes()
        self.output = self.input
        self.assertEqual(self.cli()[0], 1)
        self.assertEqual(self.input.read_bytes(), original)

    def test_inconsistencia_es_diagnostico_con_codigo_dos(self):
        data = json.loads(self.input.read_text(encoding='utf-8'))
        data['muros'][0]['nodo_fin'] = 'ausente'
        self.input.write_text(json.dumps(data), encoding='utf-8')
        self.assertEqual(self.cli()[0], 2)
        output = json.loads(self.output.read_text(encoding='utf-8'))
        self.assertEqual(output['estado_origen'], 'inconsistente')
        self.assertEqual(output['superficies'], [])
        self.assertFalse(output['ejecutable_en_etabs'])

    def test_no_admite_lecturas_como_geometria(self):
        self.input.write_bytes((ROOT/'examples/extraccion_sintetica.json').read_bytes())
        self.assertEqual(self.cli()[0], 2)
        self.assertEqual(json.loads(self.output.read_text(encoding='utf-8'))['superficies'], [])

    def test_json_ilegible_no_deja_salida(self):
        for raw in ('{"id":"x","id":"y"}', '{"x":NaN}', 'no JSON'):
            self.input.write_text(raw, encoding='utf-8')
            self.assertEqual(self.cli()[0], 1)
            self.assertFalse(self.output.exists())

    def test_fallo_publicacion_no_deja_temporal_ni_salida(self):
        with patch.object(a, '_publicar_nuevo', side_effect=OSError('Fallo simulado del sistema de archivos')):
            code, _, _ = self.cli()
        self.assertEqual(code, 1)
        self.assertFalse(self.output.exists())
        self.assertFalse(list(self.work.glob('.plan-*')))

    def test_destino_que_aparece_durante_calculo_se_conserva(self):
        original_publish = a._publicar_nuevo

        def concurrent(source, target):
            self.output.write_bytes(b'otro proceso')
            return original_publish(source, target)

        with patch.object(a, '_publicar_nuevo', side_effect=concurrent):
            self.assertEqual(self.cli()[0], 1)
        self.assertEqual(self.output.read_bytes(), b'otro proceso')
        self.assertFalse(list(self.work.glob('.plan-*')))

    def test_cambio_entrada_durante_calculo_no_publica(self):
        original = a.preparar_plan_modelado

        def changed(data):
            self.input.write_bytes(self.input.read_bytes()+b'\n')
            return original(data)

        with patch.object(a, 'preparar_plan_modelado', side_effect=changed):
            self.assertEqual(self.cli()[0], 1)
        self.assertFalse(self.output.exists())

    def test_error_calculo_controlado_no_deja_salida(self):
        with patch.object(a, 'preparar_plan_modelado', side_effect=OverflowError('fuera de rango')):
            code, _, err = self.cli()
        self.assertEqual(code, 1)
        self.assertIn('fuera de rango', err)
        self.assertFalse(self.output.exists())

    def test_directorio_salida_ausente_no_se_crea(self):
        self.output = self.work/'ausente'/'plan.json'
        self.assertEqual(self.cli()[0], 1)
        self.assertFalse(self.output.parent.exists())

    def test_ayuda_general_incluye_comando(self):
        out = StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as captured:
            main(['--help'])
        self.assertEqual(captured.exception.code, 0)
        self.assertIn('plan-modelado', out.getvalue())


if __name__ == '__main__':
    unittest.main()
