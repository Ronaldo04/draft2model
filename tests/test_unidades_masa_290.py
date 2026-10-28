"""Revisión Codex 290: unidad de salida de la fórmula (Vdin/Vest adimensional) y texto de captura de masa del informe."""
import copy
import unittest
from pathlib import Path

from draft2model import informe
from draft2model.evaluacion_estructural import validar_reglas
from draft2model.resultados_estructurales import huella_declaracion
from tests import test_evaluacion_estructural as te

RAIZ = Path(__file__).resolve().parents[1]


class UnidadResultadoTests(te.EvaluacionTests):
    SIN_CLAVE = object()

    def regla_cociente(self, unidad_resultado="1"):
        r = copy.deepcopy(next(x for x in self.rules["reglas"] if x["variable"] == "cortante"))
        r.update(id="VMIN-PRUEBA", formula={"expresion": "factor * x + desplazamiento", "factor": 1 / 100.0, "desplazamiento": 0.0},
                 limite=0.8, comparador=">=")
        r["aplicabilidad"].update(casos=["SX"], direcciones=["X"], ubicaciones=["base"])
        if unidad_resultado is not self.SIN_CLAVE:   # None explícito SÍ incluye la clave (revisión Codex 293)
            r["unidad_resultado"] = unidad_resultado
        return r

    def test_cociente_adimensional_entrada_en_kN(self):
        self.rules["reglas"].append(self.regla_cociente()); te.approve(self.rules)
        ev = next(e for e in self.evaluate()["evaluaciones"] if e["regla_id"] == "VMIN-PRUEBA")
        self.assertEqual((ev["unidad"], ev["unidad_resultado"]), ("kN", "1"))

    def test_sin_clave_conserva_forma_anterior(self):
        res = self.evaluate()
        self.assertTrue(all("unidad_resultado" not in e for e in res["evaluaciones"]))

    def test_unidad_resultado_invalida_rechazada(self):
        # Control: con aprobación fresca una regla válida se acepta; así el rechazo siguiente prueba la UNIDAD, no la aprobación.
        valida = copy.deepcopy(self.rules)
        valida["reglas"].append(self.regla_cociente("1")); te.approve(valida)
        self.assertTrue(validar_reglas(valida)["correcta"], validar_reglas(valida)["errores"])
        for valor in ("kN·m", 1, None, "s"):
            with self.subTest(valor=valor):
                reglas = copy.deepcopy(self.rules)
                regla = self.regla_cociente(valor)
                self.assertIn("unidad_resultado", regla)
                reglas["reglas"].append(regla); te.approve(reglas)
                check = validar_reglas(reglas)
                self.assertFalse(check["correcta"])
                self.assertTrue(any("unidad_resultado" in e for e in check["errores"]), check["errores"])
                self.assertFalse(any("Aprobación" in e for e in check["errores"]), check["errores"])

    def test_renderizadores_usan_unidad_de_salida(self):
        texto = (RAIZ / "draft2model/informe.py").read_text(encoding="utf-8")
        self.assertIn('ures = regla.get("unidad_resultado", regla["unidad"])', texto)
        self.assertIn("ev.unidad_resultado||ev.unidad", (RAIZ / "draft2model/panel_tecnico.py").read_text(encoding="utf-8"))
        self.assertIn("ev.get('unidad_resultado', ev['unidad'])", (RAIZ / "draft2model/revision_explicaciones.py").read_text(encoding="utf-8"))


class CapturaMasaTextoTests(unittest.TestCase):
    """El banner de contenido refleja si hay sección de masa nativa y su estado, sin elevarlo ni borrarlo."""

    def html(self, masa_nativa):
        cm = {"modelo_id": "m" * 32, "huella_plan": "a" * 64,
              "inventario": {"masa_nativa_verificada": False, "estados": {"T": "lleno"}, "escenarios": [], "peso_total_kn": 0.0,
                             "masa_total_kn_s2_m": 0.0, "nota": "n"}}
        inf = {"contenido_masa": cm}
        if masa_nativa is not None:
            inf["masa_nativa"] = {"contraste": {"estado": masa_nativa}}
        texto = (RAIZ / "draft2model/informe.py").read_text(encoding="utf-8")
        i = texto.index('    if "contenido_masa" in informe:\n        cm = informe["contenido_masa"]')
        j = texto.index("cuerpo += _lista(", i)
        codigo = texto[i:j].replace("    if ", "if ", 1)
        ns = {"informe": inf, "cuerpo": "", "_p": lambda t, c="": t}
        exec(compile("\n".join(l[4:] if l.startswith("    ") else l for l in codigo.split("\n")), "banner", "exec"), ns)
        return ns["cuerpo"]

    def test_tres_casos(self):
        self.assertIn("NO verificada (sin captura nativa", self.html(None))
        self.assertIn("contraste COHERENTE", self.html("coherente"))
        sin = self.html("no_coherente")
        self.assertIn("contraste NO COHERENTE", sin)
        self.assertNotIn("sin captura nativa", sin)


if __name__ == "__main__":
    unittest.main()
