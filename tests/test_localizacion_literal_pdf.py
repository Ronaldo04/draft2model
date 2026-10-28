import unittest
import pymupdf

from draft2model.localizacion_literal_pdf import localizar_literal_pdf


def pdf(texts, rotation=0, crop=False):
    with pymupdf.open() as doc:
        page = doc.new_page(width=400, height=300)
        for index, text in enumerate(texts):
            page.insert_text((50, 65 + index * 20), text)
        if crop:
            page.set_cropbox(pymupdf.Rect(20, 15, 380, 280))
        page.set_rotation(rotation)
        return doc.tobytes()


class LocalizacionLiteralTests(unittest.TestCase):
    def test_exact_words_and_no_numeric_conversion(self):
        raw = pdf(['C-10 260 cm', 'C-1 2.60 m'])
        self.assertEqual(localizar_literal_pdf(raw, 1, 'C-1')['total'], 1)
        self.assertEqual(localizar_literal_pdf(raw, 1, 'C-')['total'], 0)
        self.assertEqual(localizar_literal_pdf(raw, 1, '2.6 m')['total'], 0)
        self.assertEqual(localizar_literal_pdf(raw, 1, '2.60 m')['estado'], 'unica')

    def test_duplicates_are_not_resolved_by_guessing(self):
        result = localizar_literal_pdf(pdf(['C-1', 'C-1']), 1, 'C-1')
        self.assertEqual(result['estado'], 'ambigua')
        self.assertEqual(len(result['regiones']), 2)

    def test_all_rotations_and_crop_are_visible_coordinates(self):
        for rotation in (0, 90, 180, 270):
            for cropped in (False, True):
                with self.subTest(rotation=rotation, cropped=cropped):
                    raw = pdf(['C-1'], rotation, cropped)
                    result = localizar_literal_pdf(raw, 1, 'C-1')
                    self.assertEqual(result['estado'], 'unica')
                    box = result['regiones'][0]['bbox_normalizada']
                    self.assertTrue(0 <= box[0] < box[2] <= 1 and 0 <= box[1] < box[3] <= 1)
                    with pymupdf.open(stream=raw, filetype='pdf') as doc:
                        page = doc[0]
                        rect = pymupdf.Rect(box[0]*page.rect.width, box[1]*page.rect.height,
                                            box[2]*page.rect.width, box[3]*page.rect.height)
                        unrotated = rect * page.derotation_matrix
                        self.assertEqual(page.get_textbox(unrotated).strip(), 'C-1')

    def test_scanned_or_empty_page_abstains(self):
        self.assertEqual(localizar_literal_pdf(pdf([]), 1, 'C-1')['estado'], 'sin_texto_vectorial')

    def test_no_matches_across_unrelated_lines(self):
        self.assertEqual(localizar_literal_pdf(pdf(['C-1', '2.60 m']), 1, 'C-1 2.60 m')['total'], 0)

    def test_page_and_literal_validation(self):
        for page, text in [(True, 'C-1'), (0, 'C-1'), (2, 'C-1'), (1, ''), (1, 'a'*501)]:
            with self.subTest(page=page):
                with self.assertRaises(ValueError):
                    localizar_literal_pdf(pdf(['C-1']), page, text)

    def test_many_matches_does_not_misreport_uniqueness(self):
        with pymupdf.open() as doc:
            page = doc.new_page(width=400, height=300)
            for index in range(60):
                page.insert_text((20 + 60*(index % 6), 20 + 25*(index // 6)), 'C-1')
            raw = doc.tobytes()
        result = localizar_literal_pdf(raw, 1, 'C-1')
        self.assertEqual(result, {'estado': 'demasiadas_coincidencias', 'total': 60, 'regiones': []})

    def test_read_only_case_insensitive_and_whitespace(self):
        raw = pdf(['CORTE C-1'])
        before = bytes(raw)
        self.assertEqual(localizar_literal_pdf(raw, 1, ' corte   c-1 ')['estado'], 'unica')
        self.assertEqual(raw, before)


if __name__ == '__main__':
    unittest.main()
