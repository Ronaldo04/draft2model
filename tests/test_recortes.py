import json
import tempfile
import unittest
from pathlib import Path

import pymupdf
from PIL import Image

from draft2model.ingreso import registrar_expediente, file_hash
from draft2model.recortes import generar_recorte, punto_a_pagina


class RecorteTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def case(self, rotation):
        source = self.root / f"fuente-{rotation}.pdf"
        with pymupdf.open() as doc:
            page = doc.new_page(width=400, height=300)
            page.draw_rect((0, 0, 200, 150), fill=(1, 0, 0), color=None)
            page.draw_rect((200, 0, 400, 150), fill=(0, 1, 0), color=None)
            page.draw_rect((0, 150, 200, 300), fill=(0, 0, 1), color=None)
            page.draw_rect((200, 150, 400, 300), fill=(1, 1, 0), color=None)
            page.set_rotation(rotation)
            doc.save(source)
        return source, registrar_expediente(f"caso-{rotation}", [source], self.root / "casos", uso_autorizado=True, provisional_fuera_alcance=True)

    def test_region_y_transformacion_con_todas_las_rotaciones(self):
        for rotation in (0, 90, 180, 270):
            with self.subTest(rotation=rotation):
                source, manifest = self.case(rotation)
                original_hash = file_hash(source)
                output = generar_recorte(manifest, "L0001", 1, [0, 0, 0.5, 0.5], dpi=72)
                meta = json.loads(output.read_text(encoding="utf-8"))
                with Image.open(output.parent / "recorte.png") as crop:
                    observed = crop.getpixel((crop.width // 2, crop.height // 2))
                    with pymupdf.open(source) as doc:
                        full = doc[0].get_pixmap(alpha=False)
                        expected = full.pixel(full.width // 4, full.height // 4)
                    self.assertEqual(observed, expected)
                    self.assertEqual(punto_a_pagina(meta, 0, 0), (0, 0))
                self.assertEqual(meta["rotacion_pdf_grados"], rotation)
                self.assertEqual(meta["alcance"]["estado"], "fuera_mvp_declarado")
                self.assertIsNone(meta["escala_geometrica"])
                self.assertEqual(file_hash(source), original_hash)

    def test_region_desplazada_mapea_pixel_a_pagina(self):
        _, manifest = self.case(0)
        output = generar_recorte(manifest, "L0001", 1, [0.5, 0.5, 1, 1], dpi=144)
        meta = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(punto_a_pagina(meta, 0, 0), (200, 150))
        self.assertEqual(punto_a_pagina(meta, 20, 20), (210, 160))

    def test_rechazos_no_crean_recortes(self):
        _, manifest = self.case(0)
        for bbox in ([0, 0, 0, 1], [-0.1, 0, 1, 1], [0, 0, 1.1, 1], [0, 0, float("nan"), 1], [True, 0, 1, 1]):
            with self.subTest(bbox=bbox), self.assertRaises(ValueError):
                generar_recorte(manifest, "L0001", 1, bbox)
        for archivo, page in (("no-existe", 1), ("L0001", 2), ("L0001", 0)):
            with self.subTest(archivo=archivo, page=page), self.assertRaises(ValueError):
                generar_recorte(manifest, archivo, page, [0, 0, 1, 1])
        self.assertFalse((manifest.parent / "recortes").exists())

    def test_fuente_alterada_se_rechaza(self):
        _, manifest = self.case(0)
        (manifest.parent / "originales/lamina-0001.pdf").write_bytes(b"alterado")
        with self.assertRaises(ValueError):
            generar_recorte(manifest, "L0001", 1, [0, 0, 1, 1])

    def test_render_grande_reduce_resolucion_y_preserva_presupuesto(self):
        source = self.root / "grande.pdf"
        with pymupdf.open() as doc:
            doc.new_page(width=4000, height=3000)
            doc.save(source)
        manifest = registrar_expediente("grande", [source], self.root / "casos", uso_autorizado=True)
        output = generar_recorte(manifest, "L0001", 1, [0, 0, 1, 1], dpi=300)
        meta = json.loads(output.read_text(encoding="utf-8"))
        self.assertLess(meta["dpi_render_aproximado"], 300)
        self.assertLessEqual(meta["dimensiones_px"][0] * meta["dimensiones_px"][1], 8_000_000)


if __name__ == "__main__":
    unittest.main()
