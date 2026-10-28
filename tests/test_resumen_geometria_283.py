"""Hallazgo Codex 283: el resumen geométrico de informe/panel no presenta «Muros 0» en geometrías por superficies."""
import copy
import unittest
from pathlib import Path

from draft2model import informe
from draft2model.resumen_geometria import resumen_geometria, texto_resumen
from tests.test_validacion_geometria import sintetico

GEO03 = {"version_contrato": "0.3.0", "unidad_longitud": "m", "muros": [],
         "niveles": [{"id": "NCF", "cota": -2.5, "tipo": "auxiliar"}, {"id": "N0", "cota": 0.0, "tipo": "piso"},
                     {"id": "N1", "cota": 2.6, "tipo": "piso"}, {"id": "N2", "cota": 5.2}, {"id": "NTT", "cota": 14.25, "tipo": "auxiliar"}],
         "superficies": [{"id": "W1", "papel_geometrico": "muro de albañilería"}, {"id": "W2", "papel_geometrico": "muro de albañilería"},
                         {"id": "P1", "papel_geometrico": "placa de concreto"}, {"id": "S1", "papel_geometrico": "losa de piso"}]}


class ResumenGeometriaTests(unittest.TestCase):
    def test_superficies_por_papel_y_niveles_separados(self):
        r = resumen_geometria(GEO03)
        self.assertEqual(r["superficies"], 4)
        self.assertEqual(r["superficies_por_papel"], {"losa de piso": 1, "muro de albañilería": 2, "placa de concreto": 1})
        self.assertEqual((r["niveles_piso"], r["base"], r["pisos_sobre_base"]), (["N0", "N1", "N2"], "N0", 2))
        self.assertEqual(r["niveles_auxiliares"], ["NCF", "NTT"])
        texto = texto_resumen(r)
        self.assertNotIn("Muros: 0", texto)
        self.assertIn("no un recuento de muros físicos", texto)

    def test_contrato_01_conserva_forma_anterior(self):
        self.assertIsNone(resumen_geometria(sintetico()))
        self.assertIsNone(resumen_geometria(None))

    def test_siete_y_html_del_informe(self):
        res = {"geometria": {"id": "g", "sha256": "0" * 64}, "resultados": [], "advertencias": [], "omisiones": []}
        ctx = {"sitio": None}
        ev = {"evaluaciones": []}
        s03 = informe._siete(res, ev, {"datos": copy.deepcopy(GEO03)}, ctx)
        self.assertIn("resumen_superficies", s03["geometria_muros"])
        self.assertEqual(s03["geometria_muros"]["numero_muros"], 0)               # valor histórico conservado, no mostrado como ausencia
        s01 = informe._siete(res, ev, {"datos": sintetico()}, ctx)
        self.assertNotIn("resumen_superficies", s01["geometria_muros"])

    def test_panel_usa_el_resumen(self):
        texto = (Path(__file__).resolve().parents[1] / "draft2model/panel_tecnico.py").read_text(encoding="utf-8")
        self.assertIn("d.resumen_geometria?", texto)
        self.assertIn("data['resumen_geometria']=resumen", texto)


if __name__ == "__main__":
    unittest.main()
