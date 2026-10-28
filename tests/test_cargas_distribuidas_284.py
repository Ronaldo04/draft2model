"""Equivalencia exacta de _cargas_distribuidas con la comprensión cuadrática anterior (medición 282: ≈ 27 s en 09d1)."""
import random
import unittest

from draft2model import operaciones_etabs as op


def anterior(cargas_config, exp):
    return {c["id"]: [x["id"] for x in exp if x["id"].startswith(c["id"] + "@")]
            for c in cargas_config if any(x["id"].startswith(c["id"] + "@") for x in exp)}


class CargasDistribuidasTests(unittest.TestCase):
    def test_equivalencia_casos_limite(self):
        cfg = [{"id": i} for i in ("Q1", "Q1@A", "Q", "Q10", "SOLO", "VACIA@")]
        exp = [{"id": i} for i in ("Q1@T1", "Q1@A@T2", "Q10@T3", "Q@x", "Q1@", "SOLO", "VACIA@@T", "OTRA@T", "Q1@A@T2@b")]
        r = op._cargas_distribuidas(cfg, exp)
        self.assertEqual(r, anterior(cfg, exp))
        self.assertEqual(list(r), list(anterior(cfg, exp)))           # mismo orden de claves
        for k in r:
            self.assertEqual(r[k], anterior(cfg, exp)[k])              # mismo orden de valores

    def test_equivalencia_aleatoria(self):
        rnd = random.Random(284)
        for _ in range(200):
            cfg = [{"id": "".join(rnd.choice("AB@") for _ in range(rnd.randint(1, 3)))} for _ in range(rnd.randint(0, 6))]
            exp = [{"id": "".join(rnd.choice("AB@1") for _ in range(rnd.randint(1, 6)))} for _ in range(rnd.randint(0, 12))]
            r, a = op._cargas_distribuidas(cfg, exp), anterior(cfg, exp)
            self.assertEqual(r, a)
            self.assertEqual(list(r), list(a))


if __name__ == "__main__":
    unittest.main()


class ProblemasMallaHostsTests(unittest.TestCase):
    def test_cobertura_por_host_igual_que_antes(self):
        base = {"estado": "plan_no_ejecutado", "ejecutable": True, "aprueba_ingenieria": False, "operaciones": [],
                "malla": {"hosts": {"H1": {"triangulos": ["T2", "T1"]}, "H2": {"triangulos": ["T3"]}, "H3": {"triangulos": []}},
                          "triangulos": {"T1": {"host": "H1"}, "T2": {"host": "H1"}, "T3": {"host": "H2"}, "T4": {"host": 7}, "T5": "x"}}}
        problemas = [p for p in op._problemas_malla(base) if "cobertura" in p]
        self.assertEqual(problemas, [])
        malo = {**base, "malla": {**base["malla"], "hosts": {**base["malla"]["hosts"], "H2": {"triangulos": []}}}}
        self.assertEqual([p for p in op._problemas_malla(malo) if "cobertura" in p], ["Plan 0.4: host H2 con cobertura de triángulos inconsistente."])
