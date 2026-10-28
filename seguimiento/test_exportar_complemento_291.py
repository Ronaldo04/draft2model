"""Integridad y fronteras del complemento; fixtures no acreditan el piloto."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from seguimiento import exportar_complemento_291 as exp


class ComplementoTests(unittest.TestCase):
    def setUp(self):
        self.base = Path(__file__).resolve().parents[1] / 'tmp'
        self.base.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(prefix='complemento291_', dir=self.base)
        self.root = Path(self.tmp.name)
        assert self.root.resolve().is_relative_to(self.base.resolve())
        self.private = self.root / 'private'
        case = self.private / 'piloto'
        case.mkdir(parents=True)
        (case / 'expediente.json').write_text('{}', encoding='utf-8')
        (case / 'original.pdf').write_bytes(b'%PDF-fixture-no-piloto')
        other = self.private / 'otro_caso'
        other.mkdir()
        (other / 'NO_COPIAR.txt').write_bytes(b'privado')
        self.work = self.root / 'work'
        self.report = self.work / 'resultados/informe'
        self.report.mkdir(parents=True)
        report = {'caso_id': 'piloto', 'evidencia_analisis': {
            'resultado': {'id': 'a' * 32}, 'analisis': {'corrida_id': 'b' * 32},
            'modelo': {'modelo_id': 'c' * 32}}}
        (self.report / 'informe.json').write_text(json.dumps(report), encoding='utf-8')
        (self.report / 'informe.html').write_bytes(b'<h1>Fixture</h1>')
        (self.report / 'informe.pdf').write_bytes(b'%PDF-fixture')
        self.panel = self.work / 'resultados/panel.html'
        self.panel.write_bytes(b'<h1>Panel fixture</h1>')
        self.context = self.work / 'resultados/contexto.json'
        self.context.write_text('{}', encoding='utf-8')
        self.registry = {'caso': 'piloto', 'resultados': {'id': 'a' * 32},
            'informe': {'carpeta': str(self.report), **{n: exp.caso_export.stream(self.report / n)['sha256']
                for n in ('informe.json', 'informe.html', 'informe.pdf')}},
            'panel': {'archivo': str(self.panel), 'sha256': exp.caso_export.stream(self.panel)['sha256']}}
        self.registry_path = self.work / 'registro_resultados.json'
        self.save_registry()
        self.output = self.root / 'salida'

    def save_registry(self):
        self.registry_path.write_text(json.dumps(self.registry), encoding='utf-8')

    def tearDown(self):
        assert self.root.resolve().is_relative_to(self.base.resolve())
        self.tmp.cleanup()

    def create(self, output=None):
        return exp.create(self.private, 'piloto', self.work, output or self.output)

    def test_conserva_informe_panel_registro_y_solo_un_caso(self):
        m = self.create()
        self.assertEqual(exp.verify(self.output)['estado'], 'integridad_verificada_no_aceptacion')
        self.assertFalse(m['aprueba_ingenieria'])
        self.assertIn('resultados/informe/informe.pdf', m['archivos'])
        with zipfile.ZipFile(self.output / 'caso_archivado/Caso.zip') as z:
            self.assertIn('piloto/original.pdf', z.namelist())
            self.assertFalse(any('otro_caso' in name for name in z.namelist()))
        for name in ('informe.json', 'informe.html', 'informe.pdf'):
            self.assertEqual((self.report / name).read_bytes(),
                             (self.output / 'resultados/informe' / name).read_bytes())

    def test_rechaza_informe_distinto_de_su_registro(self):
        (self.report / 'informe.html').write_bytes(b'alterado')
        with self.assertRaisesRegex(ValueError, 'Informe distinto'):
            self.create()
        self.assertFalse(self.output.exists())

    def test_rechaza_fuente_externa_al_trabajo(self):
        external = self.root / 'externo.html'
        external.write_bytes(self.panel.read_bytes())
        self.registry['panel']['archivo'] = str(external)
        self.save_registry()
        with self.assertRaises(ValueError):
            self.create()
        self.assertFalse(self.output.exists())

    def test_rechaza_patron_de_credencial_sin_publicarlo(self):
        self.context.write_text(json.dumps({'token': 'sk-' + 'A' * 48}), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'Posible credencial'):
            self.create()
        self.assertFalse(self.output.exists())

    def test_rechaza_zip_alterado(self):
        self.create()
        with (self.output / 'Complemento.zip').open('ab') as f:
            f.write(b'ALTERADO')
        with self.assertRaisesRegex(ValueError, 'ZIP alterado'):
            exp.verify(self.output)

    def test_cambio_concurrente_no_publica_exito(self):
        original = exp.caso_export.create

        def snapshot_then_change(*args):
            m = original(*args)
            (self.report / 'informe.html').write_bytes(b'cambio-concurrente')
            return m

        with patch.object(exp.caso_export, 'create', side_effect=snapshot_then_change):
            with self.assertRaisesRegex(ValueError, 'modificada'):
                self.create()
        self.assertTrue((self.output / 'FALLO.json').is_file())
        self.assertFalse((self.output / 'MANIFIESTO_COMPLEMENTO.json').exists())
        with self.assertRaisesRegex(ValueError, 'fallo registrado'):
            exp.verify(self.output)

    def test_no_sobrescribe_entrega_existente(self):
        self.create()
        before = (self.output / 'MANIFIESTO_COMPLEMENTO.json').read_bytes()
        with self.assertRaises(FileExistsError):
            self.create()
        self.assertEqual(before, (self.output / 'MANIFIESTO_COMPLEMENTO.json').read_bytes())
        exp.verify(self.output)

    def test_rechaza_destino_dentro_del_trabajo(self):
        with self.assertRaisesRegex(ValueError, 'Destino dentro'):
            self.create(self.work / 'salida')

    def public_corpus(self):
        folder = self.root / 'normativa_fixture'
        folder.mkdir()
        pdf = folder / 'norma.pdf'
        pdf.write_bytes(b'%PDF-norma-fixture')
        (folder / 'norma.txt').write_bytes(b'Fuente sintetica; no norma real')
        (folder / 'fuentes_manifest.json').write_text(json.dumps({'fuentes': [
            {'archivo': pdf.name, **exp.caso_export.stream(pdf)}]}), encoding='utf-8')
        return folder

    def test_corpus_explicito_conserva_bytes_y_ruta(self):
        corpus = self.public_corpus()
        m = exp.create(self.private, 'piloto', self.work, self.output, referencias_publicas=corpus)
        self.assertEqual(len(m['referencias_publicas_incluidas']), 3)
        self.assertEqual((corpus / 'norma.txt').read_bytes(),
                         (self.output / 'seguimiento/normativa_fixture/norma.txt').read_bytes())
        exp.verify(self.output)

    def test_corpus_alterado_no_se_publica(self):
        corpus = self.public_corpus()
        (corpus / 'norma.pdf').write_bytes(b'alterado')
        with self.assertRaisesRegex(ValueError, 'Referencia pública distinta'):
            exp.create(self.private, 'piloto', self.work, self.output, referencias_publicas=corpus)
        self.assertFalse(self.output.exists())


if __name__ == '__main__':
    unittest.main()
