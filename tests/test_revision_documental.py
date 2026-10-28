import json
import tempfile
import unittest
from pathlib import Path

import pymupdf
from PIL import Image

from draft2model.ingreso import file_hash, registrar_expediente
from draft2model.revision_documental import revisar_expediente


class RevisionDocumentalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def pdf(self, name="prueba.pdf", encrypted=False):
        path = self.root / name
        with pymupdf.open() as doc:
            doc.new_page(width=800, height=400).insert_text((30, 40), "LAMINA SINTETICA")
            second = doc.new_page(width=600, height=400)
            second.set_rotation(90)
            if encrypted:
                doc.save(path, encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="fixture", owner_pw="fixture-owner")
            else:
                doc.save(path)
        return path

    def review(self, source, **kwargs):
        manifest = registrar_expediente("prueba", [source], self.root / "casos", uso_autorizado=True, provisional_fuera_alcance=True)
        path = revisar_expediente(manifest, **kwargs)
        return manifest, path, json.loads(path.read_text(encoding="utf-8"))

    def test_pdf_paginas_rotacion_limite_y_originales(self):
        source = self.pdf()
        previous = file_hash(source)
        manifest, output, report = self.review(source, max_lado=512)
        self.assertEqual(report["resumen"]["paginas_renderizadas"], 2)
        self.assertEqual(report["resumen"]["archivos_con_error"], 0)
        self.assertEqual(report["alcance"]["estado"], "fuera_mvp_declarado")
        pages = report["documentos"][0]["paginas"]
        self.assertEqual(pages[1]["rotacion_pdf_grados"], 90)
        for page in pages:
            self.assertLessEqual(max(page["ancho_preview_px"], page["alto_preview_px"]), 512)
            self.assertTrue((manifest.parent / page["vista_previa"]).is_file())
            self.assertEqual(page["legibilidad"], "pendiente_revision_humana")
        self.assertEqual(file_hash(source), previous)
        second_output = revisar_expediente(manifest, 512)
        self.assertNotEqual(output, second_output)
        self.assertTrue(output.is_file())

    def test_imagen_abre_y_registra_dimensiones(self):
        source = self.root / "imagen.png"
        Image.new("RGB", (800, 200), "white").save(source)
        _, _, report = self.review(source, max_lado=256)
        page = report["documentos"][0]["paginas"][0]
        self.assertEqual(page["dimensiones_original_px"], [800, 200])
        self.assertEqual(page["ancho_preview_px"], 256)

    def test_hash_modificado_impide_procesamiento(self):
        source = self.pdf()
        manifest = registrar_expediente("prueba", [source], self.root / "casos", uso_autorizado=True)
        (manifest.parent / "originales/lamina-0001.pdf").write_bytes(b"alterado")
        report = json.loads(revisar_expediente(manifest).read_text(encoding="utf-8"))
        self.assertEqual(report["resumen"]["archivos_con_error"], 1)
        self.assertEqual(report["resumen"]["paginas_renderizadas"], 0)

    def test_pdf_danado_se_registra_como_error(self):
        source = self.root / "danado.pdf"
        source.write_bytes(b"%PDF-1.4\nsolo firma")
        _, _, report = self.review(source)
        self.assertEqual(report["resumen"]["archivos_con_error"], 1)

    def test_pdf_protegido_no_se_desbloquea(self):
        _, _, report = self.review(self.pdf(encrypted=True))
        self.assertEqual(report["resumen"]["archivos_con_error"], 1)
        self.assertIn("protegido", report["documentos"][0]["error"])

    def test_rechaza_referencia_fuera_del_expediente_y_limites(self):
        source = self.pdf()
        manifest = registrar_expediente("prueba", [source], self.root / "casos", uso_autorizado=True)
        data = json.loads(manifest.read_text(encoding="utf-8"))
        data["archivos"][0]["archivo"] = str(source)
        manifest.write_text(json.dumps(data), encoding="utf-8")
        report = json.loads(revisar_expediente(manifest).read_text(encoding="utf-8"))
        self.assertEqual(report["resumen"]["archivos_con_error"], 1)
        for limit in (0, 10000, True, 200.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                revisar_expediente(manifest, limit)


if __name__ == "__main__":
    unittest.main()
