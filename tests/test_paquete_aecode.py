"""Empaquetado sobre proyectos aislados; no ETABS, red ni claves reales."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import zipfile

from scripts import crear_paquete_aecode as pkg

ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = ROOT / 'tmp/pruebas_paquete_aecode'


class PackageTests(unittest.TestCase):
    def setUp(self):
        TEMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.temp = TemporaryDirectory(dir=TEMP_ROOT)
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'proyecto'
        self.root.mkdir()
        for folder in pkg.CARPETAS:
            (self.root / folder).mkdir()
        for name in (*pkg.RAIZ_PUBLICA, *pkg.SEGUIMIENTO):
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text('fixture\n', encoding='utf-8')
        self.code = self.root / 'draft2model/core.py'
        self.code.write_text('VALUE = 1\n', encoding='utf-8')
        self.catalog = self.root / 'seguimiento/hitos.json'
        self.catalog.write_text(json.dumps({'milestones': [{'criteria': [{'check_files': ['draft2model/core.py', 'seguimiento/control.py']}]}]}), encoding='utf-8')

    def tearDown(self):
        assert self.base.is_relative_to(TEMP_ROOT.resolve())
        self.temp.cleanup()

    def test_snapshot_reproducible_full_inventory_no_private_or_cache(self):
        sentinel = b'sk-proj-' + b'A' * 32
        for name in ('data/private/credenciales.local.md', 'draft2model/private/notas.txt',
                     'draft2model/__pycache__/local.pyc', 'scripts/.env', 'tmp/registro.json'):
            p = self.root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(sentinel)
        a = pkg.crear(self.root, self.base / 'salida1')
        b = pkg.crear(self.root, self.base / 'salida2')
        self.assertEqual(a['huella_fuentes'], b['huella_fuentes'])
        self.assertEqual(a['zip_sha256'], b['zip_sha256'])
        self.assertFalse(a['incluye_datos_privados'])
        self.assertIn('requiere_informe', a['validacion_funcional'])
        with zipfile.ZipFile(self.base / 'salida1/Draft2Model.zip') as z:
            self.assertEqual(set(z.namelist()), set(a['archivos']))
            for name, digest in a['archivos'].items():
                self.assertEqual(hashlib.sha256(z.read(name)).hexdigest(), digest)
                self.assertNotIn(sentinel, z.read(name))
        self.assertTrue((self.base / 'salida1/LEEME_AECODE.md').is_file())

    def test_real_looking_key_in_public_source_aborts_before_output(self):
        key = 'sk-proj-' + 'B' * 35
        self.code.write_text('KEY = ' + repr(key))
        out = self.base / 'salida'
        with self.assertRaises(ValueError) as caught:
            pkg.crear(self.root, out)
        self.assertNotIn(key, str(caught.exception))
        self.assertFalse(out.exists())

    def test_missing_catalog_dependency_does_not_create_package(self):
        self.catalog.write_text(json.dumps({'milestones': [{'criteria': [{'check_files': ['tmp/no_publicable.json']}]}]}))
        with self.assertRaisesRegex(ValueError, 'Recurso requerido'):
            pkg.crear(self.root, self.base / 'salida')
        self.assertFalse((self.base / 'salida').exists())

    def test_nested_zip_fixture_checks_credentials_and_paths_without_extracting(self):
        archive = self.root / 'tests/fixtures/nativa/evidencia.zip'
        archive.parent.mkdir(parents=True)
        for name, content in [('receipt.json', b'sk-proj-' + b'C'*35), ('../escape.txt', b'no')]:
            with self.subTest(name=name):
                with zipfile.ZipFile(archive, 'w') as z:
                    z.writestr(name, content)
                with self.assertRaises(ValueError):
                    pkg.crear(self.root, self.base / 'salida')
                self.assertFalse((self.base / 'escape.txt').exists())

    def test_existing_destination_is_preserved(self):
        out = self.base / 'salida'
        out.mkdir()
        (out / 'sentinel.txt').write_text('preservar')
        with self.assertRaises(ValueError):
            pkg.crear(self.root, out)
        self.assertEqual((out / 'sentinel.txt').read_text(), 'preservar')

    def test_offline_wheels_must_match_entire_lock(self):
        wheels = self.base / 'wheels'
        wheels.mkdir()
        raw = b'fixture-wheel-not-a-runtime'
        digest = hashlib.sha256(raw).hexdigest()
        (self.root / 'requirements-win-py310.lock').write_text('fixture==1 --hash=sha256:' + digest)
        with self.assertRaisesRegex(ValueError, 'Faltan wheels'):
            pkg.crear(self.root, self.base / 'sin_dependencia', wheels)
        (wheels / 'fixture.whl').write_bytes(raw)
        result = pkg.crear(self.root, self.base / 'con_dependencia', wheels)
        self.assertEqual(result['dependencias_offline'], ['wheels/fixture.whl'])
        self.assertEqual(result['archivos']['wheels/fixture.whl'], digest)
        (wheels / 'ajeno.whl').write_bytes(b'ajeno')
        with self.assertRaisesRegex(ValueError, 'Wheel ajeno'):
            pkg.crear(self.root, self.base / 'ajena', wheels)

    def test_output_cannot_modify_source_tree(self):
        with self.assertRaises(ValueError):
            pkg.crear(self.root, self.root / 'draft2model/entrega')
        self.assertFalse((self.root / 'draft2model/entrega').exists())

    def test_concurrent_source_edit_leaves_error_not_manifest(self):
        original = zipfile.ZipFile.writestr
        changed = False
        def mutate(z, name, data, *args, **kwargs):
            nonlocal changed
            result = original(z, name, data, *args, **kwargs)
            if not changed:
                self.code.write_text('VALUE = 2\n')
                changed = True
            return result
        out = self.base / 'salida'
        with patch.object(zipfile.ZipFile, 'writestr', mutate):
            with self.assertRaisesRegex(ValueError, 'fuentes cambiaron'):
                pkg.crear(self.root, out)
        self.assertTrue((out / 'ERROR_EMPAQUETADO.json').is_file())
        self.assertFalse((out / 'MANIFIESTO.json').exists())


if __name__ == '__main__':
    unittest.main()
