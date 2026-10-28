"""Comprobaciones focales del archivo independiente, sin motor ni red."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import exportar_caso_268 as mod

class ArchiveTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1]/'tmp'
        base.mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.base = Path(self.temp.name)
        self.root = self.base/'private'; self.case = self.root/'caso'
        self.case.mkdir(parents=True)
        (self.case/'expediente.json').write_bytes(b'{"caso":"caso"}')
        (self.case/'analizado.EDB').write_bytes(b'fixture-only-EDB-not-native')
        (self.root/'credenciales.local.md').write_text('secret outside selected case')
        self.out = self.base/'out'

    def tearDown(self): self.temp.cleanup()

    def test_roundtrip_exact_no_other_case_or_keys(self):
        m = mod.create(self.root,'caso',self.out)
        self.assertEqual(mod.verify(self.out)['archivos'],3)
        self.assertFalse(m['relectura_portable_verificada'])
        self.assertFalse(m['aprueba_ingenieria'])
        self.assertEqual(set(m['archivos']),{'caso/expediente.json','caso/analizado.EDB','LEEME_ANEXO.txt'})
        with self.assertRaises(FileExistsError): mod.create(self.root,'caso',self.out)

    def test_changed_zip_rejected(self):
        mod.create(self.root,'caso',self.out)
        with (self.out/'Caso.zip').open('ab') as f: f.write(b'alteration')
        with self.assertRaisesRegex(ValueError,'ZIP alterado'): mod.verify(self.out)

    def test_secret_inside_case_is_rejected_without_content_in_error(self):
        key = b'sk-proj-'+b'A'*35
        (self.case/'notes.md').write_bytes(key)
        with self.assertRaises(ValueError) as caught: mod.create(self.root,'caso',self.out)
        self.assertNotIn(key.decode(),str(caught.exception))
        self.assertTrue((self.out/'FALLO.json').exists())
        self.assertFalse((self.out/'MANIFIESTO.json').exists())

    def test_changed_source_does_not_publish_success(self):
        original = mod.stream
        def mutate(path, sink=None):
            value = original(path,sink)
            if sink is not None and path.name=='analizado.EDB': path.write_bytes(b'changed')
            return value
        with patch.object(mod,'stream',side_effect=mutate):
            with self.assertRaisesRegex(ValueError,'cambió'): mod.create(self.root,'caso',self.out)
        self.assertFalse((self.out/'MANIFIESTO.json').exists())

    def test_output_in_case_and_path_escape_rejected(self):
        with self.assertRaises(ValueError): mod.create(self.root,'../caso',self.out)
        with self.assertRaisesRegex(ValueError,'dentro'): mod.create(self.root,'caso',self.case/'out')

if __name__ == '__main__': unittest.main()
