"""Una segunda versión no debe atender el puerto de una sesión local existente."""
from pathlib import Path
import tempfile
import unittest
from draft2model.revision_visual import ServidorRevision


class PuertoExclusivoTests(unittest.TestCase):
    def test_rechaza_segundo_servidor_sin_interrumpir_el_primero(self):
        with tempfile.TemporaryDirectory() as folder:
            first=ServidorRevision(Path(folder),0)
            try:
                address=first.server_address
                with self.assertRaises(OSError):ServidorRevision(Path(folder),address[1])
                self.assertEqual(first.socket.getsockname(),address)
            finally:first.server_close()


if __name__=='__main__':unittest.main()
