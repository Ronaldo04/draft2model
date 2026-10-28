"""Cotas auxiliares (tipo "auxiliar") separadas de los pisos: contrato, validador y guarda del plan (ensayo nativo 257)."""
import unittest
from types import SimpleNamespace

from draft2model import operaciones_etabs as op
from draft2model.validacion_geometria import validar_geometria
from tests.test_validacion_geometria import sintetico


def con_auxiliares():
    g = sintetico()
    g["niveles"] += [{"id": "NCF", "cota": -2.5, "tipo": "auxiliar"}, {"id": "NTT", "cota": 14.25, "tipo": "auxiliar"}]
    return g


def codigos(r):
    return {p.codigo for p in r.errores}


class ContratoTests(unittest.TestCase):
    def test_tipo_auxiliar_admitido(self):
        r = validar_geometria(con_auxiliares())
        self.assertTrue(r.consistente, [str(e) for e in r.errores])

    def test_tipo_invalido(self):
        g = sintetico()
        g["niveles"][1]["tipo"] = "sotano"
        self.assertIn("valor_invalido", codigos(validar_geometria(g)))

    def test_muro_no_une_cota_auxiliar(self):
        g = con_auxiliares()
        g["muros"][0]["nivel_superior"] = "NTT"
        self.assertIn("nivel_auxiliar_en_muro", codigos(validar_geometria(g)))


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.vg = SimpleNamespace(geometria_m=con_auxiliares())

    def test_pisos_excluyen_auxiliares(self):
        self.assertEqual([n["id"] for n in op._niveles_piso(self.vg)], ["N0", "N1"])
        self.assertEqual([n["id"] for n in op._niveles_auxiliares(self.vg)], ["NCF", "NTT"])

    def test_guarda_con_envolvente_declarada(self):
        sup = {"coordenadas": {"P1": (0, 0, -2.5), "P2": (0, 0, 14.25), "P3": (0, 0, 14.3)},
               "asignaciones": {}, "contornos": {}, "derivados": {}}
        pisos, aux = op._niveles_piso(self.vg), op._niveles_auxiliares(self.vg)
        motivos = op._motivos_superficies(sup, pisos, aux)
        self.assertEqual(len(motivos), 1)
        self.assertIn("'P3'", motivos[0])
        # Sin cotas auxiliares declaradas se conserva el rechazo original (no se crean pisos ficticios).
        self.assertEqual(len(op._motivos_superficies(sup, pisos)), 3)


if __name__ == "__main__":
    unittest.main()
