"""Consultas portables de evidencia capturada; sin ETABS, red ni tmp histórico."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from draft2model.revision_visual import RevisionLocal
from draft2model.revision_resultados import ErrorResultados, ServicioResultados
from tests.fixture_etabs import extraer_evidencia

CASO = 'demo-integrada-sintetica'
RESULTADO = '72c06efb3bfe477bb1fe565809aeddec'
MODELO = '225f8c4a9a0744fbb702a9f0b9affdc0'


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


class ServicioResultadosTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = extraer_evidencia(Path(temp.name).resolve()/'evidencia')
        self.app = RevisionLocal(self.root/'private')
        self.service = ServicioResultados(self.app)
        self.case = self.app.raiz/CASO
        self.fingerprint = self.app.expediente(CASO)[2]
        self.result = self.case/'resultados_estructurales'/RESULTADO

    def consultar(self, modelo=False, caso=CASO, version=None, fingerprint=None):
        fn = self.service.consultar_modelo if modelo else self.service.consultar_resultado
        return fn(caso, version or (MODELO if modelo else RESULTADO),
                  expediente_sha256=fingerprint or self.fingerprint)

    def test_listar_consultar_sin_aprobacion_heredada_ni_escrituras(self):
        before = snapshot(self.root)
        results = self.service.listar_resultados(CASO)
        models = self.service.listar_modelos(CASO)
        self.assertEqual(results['expediente_sha256'], self.fingerprint)
        self.assertTrue(all(row['vigente'] for row in results['versiones']))
        self.assertTrue(all(row['vigente'] for row in models['versiones']))
        res, model = self.consultar(), self.consultar(modelo=True)
        self.assertEqual(res['id'], RESULTADO)
        self.assertEqual(res['estado'], 'paquete_verificado')
        self.assertEqual(model['revision'], 'pendiente')
        self.assertIsNone(model['aprobacion'])
        self.assertFalse(res['analisis_vinculado'] or res['aprueba_resultados'])
        self.assertIsNone(res['evidencia_analisis'])
        self.assertEqual(res['revision_resultados'], 'pendiente')
        self.assertEqual(res['metadatos']['configuracion_id'], model['origen']['configuracion_id'])
        self.assertEqual(res['metadatos']['sha256_geometria'], model['origen']['sha256_geometria'])
        self.assertTrue(res['datos']['datos_sinteticos'])
        text = json.dumps([results, models, res, model], ensure_ascii=False)
        for value in (str(self.root), ':\\', 'archivo_motor', 'destino_guardado', '"ruta"'):
            self.assertNotIn(value, text)
        self.assertEqual(snapshot(self.root), before)

    def test_alteraciones_resultado_no_se_muestran_como_validas(self):
        for name in ('resultados.json', 'respuesta_puente.json', 'mapeo.json', 'configuracion.json', 'trazabilidad.json'):
            with self.subTest(name=name):
                path = self.result/name
                original = path.read_bytes()
                path.write_bytes(b'{}')
                self.assertEqual(next(row for row in self.service.listar_resultados(CASO)['versiones']
                                      if row['id'] == RESULTADO),
                                 {'id': RESULTADO, 'vigente': False,
                                  'problemas': ['version_no_vigente'], 'resumen': None})
                with self.assertRaises(ErrorResultados) as error:
                    self.consultar()
                self.assertNotIn(str(self.root), str(error.exception))
                path.write_bytes(original)

    def test_edb_modelo_y_original_invalidados(self):
        model = self.case/'modelos_construidos'/MODELO/'modelo.edb'
        original = model.read_bytes()
        model.write_bytes(original+b'alterado')
        with self.assertRaises(ErrorResultados):
            self.consultar(modelo=True)
        self.assertFalse(next(row for row in self.service.listar_modelos(CASO)['versiones'] if row['id'] == MODELO)['vigente'])
        model.write_bytes(original)
        manifest = json.loads((self.case/'expediente.json').read_bytes())
        source = self.case/manifest['archivos'][0]['archivo']
        source.write_bytes(source.read_bytes()+b'alterado')
        with self.assertRaises(ErrorResultados):
            self.consultar()
        with self.assertRaises(ErrorResultados):
            self.consultar(modelo=True)

    def test_caso_ajeno_ids_y_huella_obsoleta(self):
        other = self.app.raiz/'otro-caso'
        other.mkdir()
        data = json.loads((self.case/'expediente.json').read_bytes())
        data['id'] = 'otro-caso'
        (other/'expediente.json').write_text(json.dumps(data), encoding='utf-8')
        (other/'resultados_estructurales').mkdir()
        shutil.copytree(self.result, other/'resultados_estructurales'/RESULTADO)
        other_fingerprint = self.app.expediente('otro-caso')[2]
        with self.assertRaises(ErrorResultados):
            self.consultar(caso='otro-caso', fingerprint=other_fingerprint)
        for version in ('../'+RESULTADO, 'C:/privado', 'A'*32, None, 123, ''):
            for fn in (self.service.consultar_resultado, self.service.consultar_modelo):
                with self.subTest(version=version, fn=fn.__name__), self.assertRaises(ErrorResultados):
                    fn(CASO, version, expediente_sha256=self.fingerprint)
        with self.assertRaises(ErrorResultados):
            self.consultar(fingerprint='0'*64)
        with self.assertRaises(ErrorResultados):
            self.service.listar_resultados('../otro')

    def test_expediente_cambia_durante_verificacion(self):
        from draft2model import evidencia_analisis as ea
        real = ea.verificar_resultado_normalizado
        def cambiar(*args):
            result = real(*args)
            path = self.case/'expediente.json'
            path.write_bytes(path.read_bytes()+b'\n')
            return result
        with patch.object(ea, 'verificar_resultado_normalizado', side_effect=cambiar):
            with self.assertRaisesRegex(ErrorResultados, 'expediente cambió'):
                self.consultar()

    def test_directorio_alterado_y_fila_invalida(self):
        bad = self.result.parent/('a'*32)
        bad.write_text('no es directorio')
        rows = self.service.listar_resultados(CASO)['versiones']
        self.assertFalse(next(r for r in rows if r['id'] == bad.name)['vigente'])
        with self.assertRaises(ErrorResultados):
            self.consultar(version=bad.name)
        bad.unlink()
        group = self.result.parent
        saved = group.with_name('respaldo')
        group.rename(saved)
        group.write_text('grupo alterado')
        with self.assertRaises(ErrorResultados):
            self.service.listar_resultados(CASO)

    def test_rechazo_de_enlace_sin_seguirlo(self):
        # Prueba la detección de reparse Windows sin necesitar permiso symlink.
        import stat
        from types import SimpleNamespace
        path = self.result
        actual = Path.lstat
        def linked(p):
            if p == path:
                return SimpleNamespace(st_mode=stat.S_IFDIR,
                                       st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT)
            return actual(p)
        with patch.object(Path, 'lstat', linked):
            with self.assertRaises(ErrorResultados):
                self.consultar()

    def test_listas_vacias_y_errores_sin_rutas_internas(self):
        for group, fn in (('resultados_estructurales', self.service.listar_resultados),
                          ('modelos_construidos', self.service.listar_modelos)):
            shutil.rmtree(self.case/group)
            self.assertEqual(fn(CASO)['versiones'], [])
        with patch.object(self.app, 'expediente', side_effect=ValueError('C:/privado/secreto')):
            for fn in (self.service.listar_modelos, self.service.listar_resultados):
                with self.assertRaises(ErrorResultados) as err:
                    fn(CASO)
                self.assertNotIn('privado', str(err.exception))


if __name__ == '__main__':
    unittest.main()
