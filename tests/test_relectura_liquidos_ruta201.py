"""Relectura independiente del plan 0.5 (presión hidrostática en tabla no uniforme). Dobles: no prueban ETABS."""
import copy
import unittest

from draft2model import operaciones_etabs as o
from draft2model import verificacion_modelo_guardado as v
from tests import test_liquidos_ruta201 as tlr
from tests import test_relectura_malla as trm
from tests import test_verificacion_modelo_guardado as tvm

CRITERIOS = tvm.CRITERIOS
T = o.TABLA_NO_UNIFORME


def plan_liquidos():
    h = tlr.CasoLiquidos("setUp")
    h.setUp()
    try:
        d, f = tlr.declaracion("CISTERNA", 1.5, [("S1", 1)], origen=(0, 2, 1))
        c = h.aprobar_en_disco(h.montar_liquidos("vertical_corte", "presente", [(d, f, "HIDRO")]))
        return h.plan(c)
    finally:
        h.doCleanups()


def modelo_etabs(exp):
    """Representación ETABS: contornos rotados, gravedad Dir10, tabla con Story/Label de solo lectura y una fila ajena."""
    m = trm.modelo_etabs(exp)
    t = m["tablas"][T]
    campos = ["Story", "Label"] + [c for c in t["campos"] if c != "GUID"] + ["GUID"]
    filas = [{"Story": "Story1", "Label": "F" + str(i), **{k: f[k] for k in o.CAMPOS_NO_UNIFORME}, "GUID": ""} for i, f in enumerate(t["filas"])]
    filas.append({"Story": "Story1", "Label": "X", "UniqueName": "OTRO", "LoadPattern": "AJENO", "Dir": "Gravity",
                  "A": "0", "B": "0", "C": "0", "D": "1", "Restriction": "Use All Values", "GUID": ""})
    m["tablas"][T] = {"campos": campos, "filas": filas}
    return m


class RelecturaLiquidosTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = plan_liquidos()
        cls.exp = v.expectativa_desde_plan(cls.plan)

    def leer(self, m, **kw):
        return v.comparar(self.exp, tvm.lecturas(m, **kw), CRITERIOS)

    def test_inventario_y_tabla_verificados_con_resultante_independiente(self):
        self.assertEqual([x for x in self.exp["inventario"] if x["cobertura"] == "sin_lector"], [])
        self.assertIn("cargas_liquidos", {x.get("categoria") for x in self.exp["inventario"]})
        r = self.leer(modelo_etabs(self.exp))
        self.assertEqual(r["estado"], "verificado", r["discrepancias"] + r["incompletos"])
        self.assertEqual(r["cobertura"]["cargas_liquidos"], "completa")
        self.assertIn("cargas_liquidos", r["alcance"])
        self.assertIn("equilibrio_del_solver", r["controles_no_afirmados"])
        self.assertFalse(r["aprueba_modelo"])

    def test_unidades_n_mm_equivalentes(self):
        m = tvm.a_n_mm(modelo_etabs(self.exp))
        for f in m["tablas"][T]["filas"]:
            if f["LoadPattern"] == "HIDRO":
                for k in ("A", "B", "C"):
                    f[k] = repr(float(f[k]) * 1e-6)  # kN/m3 -> N/mm3
                f["D"] = repr(float(f["D"]) * 1e-3)  # kN/m2 -> N/mm2
        r = v.comparar(self.exp, tvm.lecturas(m, unidades="N_mm_C"), CRITERIOS)
        self.assertEqual(r["estado"], "verificado", r["discrepancias"] + r["incompletos"])

    def test_negativos_de_tabla(self):
        m0 = modelo_etabs(self.exp)
        filas = lambda m: m["tablas"][T]["filas"]
        primera = lambda m: next(f for f in filas(m) if f["LoadPattern"] == "HIDRO")
        casos = {
            "fila faltante": lambda m: filas(m).remove(primera(m)),
            "fila extra": lambda m: filas(m).append(dict(primera(m), UniqueName="MA_EXTRA")),
            "fila duplicada": lambda m: filas(m).append(dict(primera(m))),
            "signo": lambda m: primera(m).update(C=repr(-float(primera(m)["C"]))),
            "magnitud": lambda m: primera(m).update(D=repr(float(primera(m)["D"]) * 1.01 + 1)),
            "restricción": lambda m: primera(m).update(Restriction="Use All Values"),
            "proyectada": lambda m: primera(m).update(Dir=primera(m)["Dir"] + " Proj"),
        }
        for nombre, cambio in casos.items():
            with self.subTest(nombre):
                m = copy.deepcopy(m0); cambio(m)
                r = self.leer(m)
                self.assertEqual(r["estado"], "discrepancias", nombre)
                self.assertTrue(any(d["categoria"] == "cargas_liquidos" for d in r["discrepancias"]), r["discrepancias"])

    def test_tabla_no_leida_o_pieza_faltante_es_incompleta(self):
        m = modelo_etabs(self.exp)
        m["tablas"].pop(T)
        r = self.leer(m)
        self.assertNotEqual(r["estado"], "verificado")
        self.assertEqual(r["cobertura"]["cargas_liquidos"], "incompleta")


if __name__ == "__main__":
    unittest.main()
