"""Integración visual de CLI con PDF sintético; ningún transporte real permitido."""
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tests.respuesta_vision_semantica import respuesta as respuesta_vision

import pymupdf

from draft2model.__main__ import main
from draft2model.ingreso import registrar_expediente
from draft2model.revision_documental import revisar_expediente
from draft2model.recortes import generar_recorte
from draft2model.entrada_vision import cargar_paquete
from draft2model import cli_vision
from draft2model.gestion_extraccion import validar_version


class CliVisionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.work = Path(temp.name)
        self.root = self.work / 'casos'
        pdf = self.work / 'sintetico.pdf'
        with pymupdf.open() as doc:
            page = doc.new_page(width=200, height=120)
            page.insert_text((45, 55), 'SINTETICO 2.60')
            doc.save(pdf)
        self.manifest = registrar_expediente('demo', [pdf], self.root, uso_autorizado=True,
                                            provisional_fuera_alcance=True)
        self.folder = self.manifest.parent
        self.revision = revisar_expediente(self.manifest, max_lado=256)
        self.crop = generar_recorte(self.manifest, 'L0001', 1, [.2,.15,.8,.75], dpi=72)
        guard = patch.object(cli_vision.openai, '_http', side_effect=AssertionError('Red no permitida'))
        guard.start(); self.addCleanup(guard.stop)

    def cli(self, command, *args):
        out, err = StringIO(), StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = main([command, '--caso', 'demo', *args], raiz=self.root)
        return code, out.getvalue(), err.getvalue()

    def package(self):
        code, _, err = self.cli('preparar-vision', '--revision', self.revision.parent.name,
                                '--recortes', self.crop.parent.name)
        self.assertEqual(code, 0, err)
        return next((self.folder/'vision/solicitudes').glob('*/solicitud.json'))

    def response(self, request):
        data, sha, _, _ = cargar_paquete(self.manifest, request)
        path = self.work/'respuesta.json'
        path.write_text(json.dumps(respuesta_vision(data, sha, [{'id':'C1','tipo':'cota','valor_propuesto':2.6,'unidad':'m',
                                                   'evidencia':[{'imagen_id':'REC0001','bbox_imagen_normalizada':[.25,.25,.75,.75]}]}])), encoding='utf-8')
        return path

    def register(self, package, *extra):
        return self.cli('registrar-respuesta-vision', '--solicitud', package.parent.name,
                        '--respuesta', str(self.response(package)), '--proveedor', 'fixture-declarado',
                        '--modelo', 'fixture-local', *extra)

    def test_paquete_y_plan_sin_clave_ni_envio(self):
        package = self.package()
        with patch.dict('os.environ', {}, clear=True):
            code, out, err = self.cli('preparar-openai','--solicitud',package.parent.name,'--modelo','modelo-de-prueba')
        self.assertEqual(code, 0, err)
        self.assertIn('sin envío', out)
        plan = json.loads(next((self.folder/'vision/planes_openai').glob('*/plan.json')).read_text(encoding='utf-8'))
        self.assertEqual(plan['estado'], 'preparado_sin_envio')
        self.assertEqual(plan['configuracion']['modelo'], 'modelo-de-prueba')
        self.assertIsNone(plan['configuracion']['costo_estimado'])
        self.assertFalse(list(self.folder.rglob('intento.json')))

    def test_cli_prepara_proveedores_registrados_sin_claves_ni_envio(self):
        from draft2model.proveedores import CATALOGO
        package = self.package()
        with patch.dict('os.environ', {'D2M_COMPATIBLE_ENDPOINT': 'https://ia.example.org/v1/chat/completions'}, clear=True):
            from draft2model.politica_uso_ia import PROVEEDORES_AUTORIZADOS
            for provider, spec in CATALOGO.items():
                if provider not in PROVEEDORES_AUTORIZADOS:  # ruta 201 (R202-03): solo Google/OpenAI preparan planes
                    with self.subTest(proveedor=provider), self.assertRaises(SystemExit):
                        self.cli('preparar-proveedor', '--proveedor', provider, '--solicitud', package.parent.name, '--modelo', 'modelo-de-prueba')
                    continue
                with self.subTest(proveedor=provider), patch.object(spec.api(), '_http', side_effect=AssertionError('No enviar')) as http:
                    code, out, err = self.cli('preparar-proveedor', '--proveedor', provider,
                                             '--solicitud', package.parent.name, '--modelo', 'modelo-de-prueba')
                    self.assertEqual(code, 0, err)
                    self.assertIn('sin envío', out)
                    path = next((self.folder / ('vision/planes_' + provider)).glob('*/plan.json'))
                    plan = json.loads(path.read_text(encoding='utf-8'))
                    self.assertEqual(plan['configuracion']['proveedor'], provider)
                    self.assertEqual(plan['configuracion']['detalle'], 'auto' if spec.detalle_auto else 'high')
                    http.assert_not_called()
        self.assertFalse(list(self.folder.rglob('intento.json')))

    def test_registro_e_importacion_conservan_pendientes_y_alcance(self):
        package = self.package()
        code, out, err = self.register(package, '--importar')
        self.assertEqual(code, 0, err)
        self.assertIn('Origen declarado', out)
        version = next((self.folder/'extracciones').iterdir())
        self.assertTrue(validar_version(self.root, 'demo', version.name).correcta)
        data = json.loads((version/'extraccion.json').read_text(encoding='utf-8'))
        self.assertEqual(data['alcance']['estado'], 'fuera_mvp_declarado')
        self.assertEqual(data['candidatos'][0]['revision'], {'estado':'pendiente','historial':[]})
        self.assertFalse(list(self.folder.rglob('intento.json')))

    def test_simulacion_se_registra_sin_importarse(self):
        package = self.package()
        self.assertEqual(self.register(package, '--modo-prueba')[0], 0)
        data = json.loads(next((self.folder/'vision/respuestas').glob('*/extraccion.json')).read_text(encoding='utf-8'))
        self.assertEqual(data['procedencia']['tipo'], 'sintetico')
        self.assertEqual(data['candidatos'][0]['metodo']['tipo'], 'sintetico')
        self.assertFalse((self.folder/'extracciones').exists())

    def test_registro_no_importa_por_defecto(self):
        package = self.package()
        self.assertEqual(self.register(package)[0], 0)
        self.assertTrue(list((self.folder/'vision/respuestas').glob('*/extraccion.json')))
        self.assertFalse((self.folder/'extracciones').exists())

    def test_simulacion_no_admite_importacion(self):
        package = self.package()
        self.assertEqual(self.register(package, '--modo-prueba', '--importar')[0], 1)
        self.assertFalse((self.folder/'vision/respuestas').exists())
        self.assertFalse((self.folder/'extracciones').exists())

    def test_fallo_importacion_conserva_adaptacion_y_no_repite(self):
        package = self.package()
        with patch.object(cli_vision.gestion, 'importar_extraccion', side_effect=ValueError('fallo local simulado')) as importer:
            code, out, err = self.register(package, '--importar')
        self.assertEqual(code, 2)
        self.assertIn('no se importó', err)
        self.assertEqual(importer.call_count, 1)
        self.assertEqual(len(list((self.folder/'vision/respuestas').glob('*/extraccion.json'))), 1)
        self.assertFalse((self.folder/'extracciones').exists())

    def test_rutas_en_lugar_de_ids_y_recortes_repetidos(self):
        for args in (['--revision','../otro','--recortes',self.crop.parent.name],
                     ['--revision',self.revision.parent.name,'--recortes','../../archivo'],
                     ['--revision',self.revision.parent.name,'--recortes',self.crop.parent.name,self.crop.parent.name]):
            self.assertEqual(self.cli('preparar-vision', *args)[0], 1)
        self.assertFalse((self.folder/'vision/solicitudes').exists())

    def test_no_se_adivina_modelo_y_rechaza_limites_invalidos(self):
        package = self.package()
        with redirect_stderr(StringIO()), self.assertRaises(SystemExit) as captured:
            main(['preparar-openai','--caso','demo','--solicitud',package.parent.name], raiz=self.root)
        self.assertEqual(captured.exception.code, 2)
        self.assertEqual(self.cli('preparar-openai','--solicitud',package.parent.name,'--modelo','fixture','--max-tokens','1')[0], 1)
        self.assertFalse((self.folder/'vision/planes_openai').exists())

    def test_original_alterado_no_crea_plan(self):
        package = self.package()
        (self.folder/'originales/lamina-0001.pdf').write_bytes(b'alterado')
        self.assertEqual(self.cli('preparar-openai','--solicitud',package.parent.name,'--modelo','fixture')[0], 1)
        self.assertFalse((self.folder/'vision/planes_openai').exists())

    def test_respuesta_ajena_no_se_registra(self):
        package = self.package()
        response = self.response(package)
        data = json.loads(response.read_text(encoding='utf-8'));data['solicitud_id']='0'*32
        response.write_text(json.dumps(data),encoding='utf-8')
        code, _, _ = self.cli('registrar-respuesta-vision','--solicitud',package.parent.name,
                              '--respuesta',str(response),'--proveedor','fixture','--modelo','fixture')
        self.assertEqual(code, 1)
        self.assertFalse((self.folder/'vision/respuestas').exists())

    def test_error_de_imagen_se_informa_sin_traceback(self):
        with patch.object(cli_vision.vision, 'preparar_paquete', side_effect=cli_vision.Image.DecompressionBombError('Imagen excedida')):
            code, _, err = self.cli('preparar-vision','--revision',self.revision.parent.name,
                                    '--recortes',self.crop.parent.name)
        self.assertEqual(code, 1)
        self.assertIn('Imagen excedida', err)
        self.assertFalse((self.folder/'vision/solicitudes').exists())


if __name__ == '__main__':
    unittest.main()
