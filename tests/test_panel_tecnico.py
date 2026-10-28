import json
from pathlib import Path
import tempfile
import unittest
from draft2model.panel_tecnico import crear_panel

ROOT=Path(__file__).resolve().parents[1]


class PanelTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.output=Path(self.tmp.name)/'panel.html'
        self.results=ROOT/'examples/resultados_estructurales_sinteticos.json'
        self.rules=ROOT/'examples/reglas_estructurales_sinteticas.json'

    def test_panel_fuentes_numeros_y_sin_sobrescritura(self):
        crear_panel(self.results,self.rules,self.output)
        html=self.output.read_text(encoding='utf-8')
        raw=html.split('<script type="application/json" id="datos">')[1].split('</script>')[0]
        data=json.loads(raw)
        self.assertEqual(data['resultados'],json.loads(self.results.read_text(encoding='utf-8')))
        self.assertTrue(data['resultados']['datos_sinteticos'])
        self.assertIsNone(data['numero_muros'])
        self.assertEqual(len(data['evaluacion']['evaluaciones']),3)
        with self.assertRaises(FileExistsError):crear_panel(self.results,self.rules,self.output)

    def test_texto_no_puede_cerrar_script(self):
        data=json.loads(self.results.read_text(encoding='utf-8'));data['advertencias'].append('</script><script>alert(1)</script>')
        source=Path(self.tmp.name)/'malicioso.json';source.write_text(json.dumps(data),encoding='utf-8')
        crear_panel(source,self.rules,self.output)
        html=self.output.read_text(encoding='utf-8')
        self.assertNotIn('</script><script>alert',html)
        self.assertIn('\\u003c/script\\u003e',html)

    def test_geometria_no_relacionada_rechazada(self):
        with self.assertRaises(ValueError):crear_panel(self.results,self.rules,self.output,geometria=ROOT/'examples/geometria_sintetica.json')
        self.assertFalse(self.output.exists())

    def test_sin_reglas_conserva_resultados_y_declara_evaluacion_pendiente(self):
        crear_panel(self.results,None,self.output)
        html=self.output.read_text(encoding='utf-8')
        data=json.loads(html.split('id="datos">')[1].split('</script>')[0])
        self.assertIsNone(data['evaluacion'])
        self.assertEqual(data['resultados'],json.loads(self.results.read_bytes()))
        self.assertIn('Evaluación pendiente',html)
        self.assertIn('No se declara cumplimiento',html)
