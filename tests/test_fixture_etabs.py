import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tests import fixture_etabs as f


class FixturePortableTests(unittest.TestCase):
    def test_paquete_alterado_se_rechaza_antes_de_extraer(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);copy=root/'paquete';shutil.copytree(f.PAQUETE,copy)
            z=copy/'evidencia.zip';raw=z.read_bytes();z.write_bytes(b'X'+raw[1:])
            with patch.object(f,'PAQUETE',copy),self.assertRaises(ValueError):f.extraer_evidencia(root/'salida')
            self.assertFalse((root/'salida').exists())
