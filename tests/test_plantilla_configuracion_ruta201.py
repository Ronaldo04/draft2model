"""Etapa 03 (ruta 201): autoría sin programar — conexiones ligadas a la geometría y borrador sin datos inventados."""
import copy
import unittest

from draft2model import modelo_estructural as m
from draft2model import plantilla_configuracion as pc
from tests import test_gestion_geometria as disco
from tests import test_integracion_malla as tim


class PlantillaTests(tim.CasoMalla):
    def test_conexiones_generadas_equivalen_a_las_revisadas_y_validan(self):
        data = self.montar("conectados")
        fuentes = copy.deepcopy(data["conexiones_borde"]["fuentes"])
        conexiones = copy.deepcopy(data["conexiones_borde"]["conexiones"])
        doc = pc.documento_conexiones(self.geo, conexiones, fuentes, {"declarado_por": "Revisor sintético", "fecha": "2026-10-21",
                                                                       "alcance": "Bordes conectados de prueba."})
        self.assertEqual(doc["declaracion"]["identidad"], "declarada_no_verificada")
        data["conexiones_borde"] = doc
        r = m.validar_configuracion(self.aprobar_local(self.completar(data)), self.geo)
        self.assertTrue(r.consistente, r.errores)
        mal = copy.deepcopy(conexiones); mal[0]["b"]["desde"] = "W1"
        with self.assertRaises(pc.ErrorPlantilla):
            pc.documento_conexiones(self.geo, mal, fuentes, {"declarado_por": "x", "fecha": "2026-10-21", "alcance": "y"})

    def test_borrador_sin_datos_inventados_y_errores_accionables(self):
        self.montar("vertical")
        for version in (m.VERSION_MALLA, m.VERSION_LIQUIDOS):
            with self.subTest(version):
                b = pc.borrador(self.raiz, disco.CASO, self.version.identificador, version_contrato=version)
                self.assertEqual(b["revision"], {"estado": "borrador", "aprobacion": None})
                self.assertEqual(sorted(p["id"] for p in b["puntos"]), sorted(v["id"] for v in self.geo["vertices"]))
                self.assertTrue(all(a["seccion"] is None for a in b["asignaciones_superficies"]))
                self.assertEqual((b["materiales"], b["cargas"], b["apoyos"], b["diafragmas"]), ([], [], [], []))
                self.assertIsNone(b["conexiones_borde"])
                if version == m.VERSION_LIQUIDOS:
                    self.assertEqual(b["liquidos"]["aplicabilidad"], "informacion_insuficiente")  # no se asume ausencia
                r = m.validar_configuracion(b, self.geo)
                self.assertFalse(r.consistente)
                self.assertTrue(any("conexiones_borde" in e for e in r.errores) or any("$." in e for e in r.errores))


if __name__ == "__main__":
    unittest.main()
