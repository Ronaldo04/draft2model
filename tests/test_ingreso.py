"""Pruebas de límites y conservación usando archivos sintéticos, no planos reales."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from draft2model.ingreso import ErrorIngreso, registrar_expediente


class IngresoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / "casos"
        self.pdf = self.root / "sintetico.pdf"
        self.pdf.write_bytes(b"%PDF-1.4\ncontenido sintetico para prueba de firma\n")

    def ingest(self, case="piloto", sources=None, authorized=True):
        return registrar_expediente(case, sources or [self.pdf], self.store, uso_autorizado=authorized)

    def test_preserva_original_hash_y_borrador(self):
        manifest_path = self.ingest()
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        copied = manifest_path.parent / manifest["archivos"][0]["archivo"]
        self.assertEqual(self.pdf.read_bytes(), copied.read_bytes())
        self.assertEqual(manifest["archivos"][0]["sha256"], hashlib.sha256(self.pdf.read_bytes()).hexdigest())
        self.assertEqual(manifest["estado"], "borrador")
        self.assertIsNone(manifest["datos_ingenieria"])
        self.assertIsNone(manifest["aprobacion_tecnica"])

    def test_sin_autorizacion_no_escribe(self):
        with self.assertRaises(ErrorIngreso):
            self.ingest(authorized=False)
        self.assertFalse(self.store.exists())

    def test_identificador_no_escapa_directorio(self):
        for case in ("../escape", "CON", "", "nombre/otro", "a" * 65):
            with self.subTest(case=case), self.assertRaises(ErrorIngreso):
                self.ingest(case=case)
        self.assertFalse(self.store.exists())

    def test_no_sobrescribe_expediente(self):
        path = self.ingest()
        previous = path.read_bytes()
        with self.assertRaises(ErrorIngreso):
            self.ingest()
        self.assertEqual(path.read_bytes(), previous)

    def test_rechaza_duplicados_por_contenido(self):
        duplicate = self.root / "otra_lamina.pdf"
        duplicate.write_bytes(self.pdf.read_bytes())
        with self.assertRaises(ErrorIngreso):
            self.ingest(sources=[self.pdf, duplicate])
        self.assertFalse(self.store.exists())

    def test_rechaza_extension_firma_y_archivo_ausente(self):
        for name, content in (("vacio.pdf", b""), ("falso.png", b"%PDF-1.4"), ("datos.txt", b"%PDF-1.4")):
            source = self.root / name
            source.write_bytes(content)
            with self.subTest(name=name), self.assertRaises(ErrorIngreso):
                self.ingest(sources=[source])
        with self.assertRaises(ErrorIngreso):
            self.ingest(sources=[self.root / "ausente.pdf"])
        self.assertFalse(self.store.exists())

    def test_nombres_iguales_no_pierden_laminas(self):
        directory = self.root / "otra"
        directory.mkdir()
        second = directory / self.pdf.name
        second.write_bytes(b"%PDF-1.4\nsegunda prueba sintetica\n")
        path = self.ingest(sources=[self.pdf, second])
        manifest = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(len(manifest["archivos"]), 2)
        self.assertNotEqual(manifest["archivos"][0]["archivo"], manifest["archivos"][1]["archivo"])


if __name__ == "__main__":
    unittest.main()
