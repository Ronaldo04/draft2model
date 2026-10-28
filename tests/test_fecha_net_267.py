"""Timestamps .NET (1–7 decimales) en el lector general y en el servicio web de lecturas (hallazgo real 09d1)."""
import unittest

from draft2model import adaptador_etabs as ad
from draft2model import lectura_analisis as la
from draft2model.revision_lecturas import ErrorLecturas, ServicioLecturas


class FechaNetTests(unittest.TestCase):
    def test_validas(self):
        for v in ("2026-10-23T01:54:36.1741663+00:00", "2026-10-23T01:54:36.1741663Z", "2026-10-23T01:54:36.17+00:00",
                  "2026-10-23T01:54:36Z", "2026-10-23T01:54:36.123456+00:00"):
            with self.subTest(v=v):
                la._utc(v)
                ServicioLecturas._utc(v)

    def test_invalidas(self):
        for v in ("2026-10-23T01:54:36.12345678+00:00", "2026-13-23T01:54:36Z", "2026-10-23 01:54:36Z", 7, None):
            with self.subTest(v=v):
                with self.assertRaises(ad.ErrorEvidenciaEtabs):
                    la._utc(v)
                with self.assertRaises(ErrorLecturas):
                    ServicioLecturas._utc(v)


if __name__ == "__main__":
    unittest.main()
