"""Etapa 01 de la ruta 201: resultado de malla en el informe, huella de configuración en la preparación y
consulta de las fuentes permanentes 198 (solo lectura). Sin ETABS, red ni claves."""
import copy
import json
import unittest
from pathlib import Path

from draft2model import gestion_configuracion as gc
from draft2model import revision_modelo as rm
from tests import test_informe_relectura_modelo as tir
from tests import test_integracion_malla as tim

RAIZ = Path(__file__).resolve().parents[1]
N198 = RAIZ / "tmp" / "n198"
MALLA = {"hosts": {"S1": {"area_neta_fuente_m2": 11.0, "area_triangulos_leida_m2": 11.0, "triangulos_leidos": 14}},
         "conexiones": ["C1"], "subdivisiones": ["VIGA1"], "cargas": ["Q1<b>"], "huella_preparacion": "e" * 64}


class InformeMallaTests(unittest.TestCase):
    def setUp(self):
        self.base = tir.InformeRelecturaTests("test_sin_seleccion_no_agrega_evidencia")
        self.base.setUp()
        self.addCleanup(self.base.doCleanups)

    def html(self):
        b = self.base
        item = b.service.crear(b.body(relectura_modelo=b.ref()))
        return b.service.archivo(tir.CASO, item["id"], "html", expediente_sha256=b.fp).decode("utf-8")

    def test_malla_presente_se_muestra_escapada_y_con_limites(self):
        self.base.result["malla"] = copy.deepcopy(MALLA)
        self.base.result["cobertura"] = {"malla": "completa"}
        html = self.html()
        self.assertIn("Malla 0.4 (cobertura completa)", html)
        self.assertIn("Q1&lt;b&gt;", html); self.assertNotIn("Q1<b>", html)
        self.assertIn("No afirma masa propia por elemento", html)

    def test_sin_malla_no_hay_seccion(self):
        self.assertNotIn("Malla 0.4", self.html())


class HuellaPreparacionTests(unittest.TestCase):
    def test_preparacion_expone_huella_de_la_version(self):
        h = tim.CasoMalla("setUp"); h.setUp(); self.addCleanup(h.doCleanups)
        imp, expuesta, _ = h.registrar_aprobada("vertical_corte")
        self.assertEqual(expuesta["huella_configuracion"], imp["metadatos"]["huella_configuracion"])
        self.assertFalse(expuesta["aprueba_ingenieria"])


# Evidencia permanente 198/200 (tmp/): ver scripts/verificar_evidencia_ruta201.py.


if __name__ == "__main__":
    unittest.main()
