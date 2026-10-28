"""Reutilización de validar_geometria (282): resultado idéntico al original, copias independientes, invalidación por contenido."""
import copy
import json
import unittest

from draft2model import validacion_geometria as vgm
from draft2model.cache_validacion_geometria import reutilizar_validacion
from tests.test_validacion_geometria import sintetico

ORIGINAL = vgm.validar_geometria.__wrapped__


def forma(r):
    return json.dumps(r.a_dict(), ensure_ascii=False)          # sin sort_keys: el orden también debe conservarse


class CacheValidacionTests(unittest.TestCase):
    def setUp(self):
        vgm.validar_geometria.cache_clear()

    def test_igual_al_original_frio_y_caliente_y_orden_conservado(self):
        g = sintetico()
        esperado = ORIGINAL(copy.deepcopy(g))
        frio, caliente = vgm.validar_geometria(g), vgm.validar_geometria(g)
        for r in (frio, caliente):
            self.assertEqual(forma(r), forma(esperado))
            self.assertEqual((r.consistente, r.huella_contenido), (esperado.consistente, esperado.huella_contenido))
        self.assertEqual(vgm.validar_geometria.cache_info()["hits"], 1)

    def test_errores_conservados_y_copias_independientes(self):
        g = sintetico(); g["muros"][0]["espesor"] = -1
        a = vgm.validar_geometria(g)
        self.assertFalse(a.consistente)
        a.errores.clear(); a.geometria_m and a.geometria_m.clear()
        b = vgm.validar_geometria(g)
        self.assertFalse(b.consistente)
        self.assertEqual(forma(b), forma(ORIGINAL(g)))

    def test_cualquier_cambio_invalida_incluida_revision(self):
        g = sintetico(); vgm.validar_geometria(g)
        for cambio in (lambda x: x["nodos"][0].update(x=0.001), lambda x: x.update(revision={"estado": "aprobado", "aprobacion": None}),
                       lambda x: x["niveles"][1].update(cota=2.7)):
            h = copy.deepcopy(g); cambio(h)
            with self.subTest(cambio=cambio):
                self.assertEqual(forma(vgm.validar_geometria(h)), forma(ORIGINAL(h)))
        self.assertEqual(vgm.validar_geometria.cache_info()["hits"], 0)

    def test_no_json_no_se_guarda_y_excepciones_originales(self):
        llamadas = []
        @reutilizar_validacion
        def val(d):
            llamadas.append(1)
            if d.get("fallar"):
                raise ValueError("original")
            return vgm.ResultadoValidacion(geometria_m={"t": (1, 2)})   # tupla: no JSON estricto
        val({"a": 1}); val({"a": 1})
        self.assertEqual(len(llamadas), 2)
        self.assertEqual(val.cache_info()["entradas"], 0)
        with self.assertRaisesRegex(ValueError, "original"):
            val({"fallar": True})
        self.assertEqual(vgm.validar_geometria(float("nan")).__class__.__name__, "ResultadoValidacion")   # clave no JSON: original

    def test_orden_cruzado_igual_al_original(self):
        # Revisión Codex 284: primar con una ordenación y consultar otra; forma sin sort_keys idéntica al original.
        g = sintetico()
        h = {k: g[k] for k in reversed(list(g))}
        h["niveles"] = [{k: n[k] for k in reversed(list(n))} for n in h["niveles"]]
        for primero, segundo in ((g, h), (h, g)):
            vgm.validar_geometria.cache_clear()
            vgm.validar_geometria(copy.deepcopy(primero))
            for x in (segundo, primero, segundo):
                self.assertEqual(forma(vgm.validar_geometria(copy.deepcopy(x))), forma(ORIGINAL(copy.deepcopy(x))))


if __name__ == "__main__":
    unittest.main()
