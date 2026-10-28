"""R241: piso y fondo de depósito simultáneos con formulaciones distintas, transportadas al plan y a la relectura.

Sintético (dobles): prueba argumentos nativos generados y expectativas de relectura; no inicia ETABS.
"""
import copy
import unittest

from draft2model import operaciones_etabs as o
from tests.test_operaciones_superficies import PlanSuperficiesBase

POR_SECCION = {
    "LOSA20": {"tipo": "Membrane", "funcion": "piso",
               "justificacion": "E.030 art. 30.8: se excluye la rigidez fuera del plano de la losa de piso en el modelo sísmico."},
    "FONDO25": {"tipo": "ShellThick", "funcion": "fondo_deposito",
                "justificacion": "Recibe presión hidrostática normal; requiere flexión fuera del plano."},
}


class IdealizacionPorSeccionTests(PlanSuperficiesBase):
    def config(self):
        fondo = copy.deepcopy(next(s for s in self.data["secciones"] if s["id"] == "LOSA20"))
        fondo["id"] = "FONDO25"
        self.data["secciones"].append(fondo)
        for a in self.data["asignaciones_superficies"]:
            if a["objetivo"] == "S2":
                a["seccion"] = "FONDO25"
        return self.aprobar_config()

    def test_piso_y_fondo_simultaneos_en_plan_y_relectura(self):
        plan = self.plan(self.config(), tipo_shell_losa=copy.deepcopy(POR_SECCION))
        enum = {"Membrane": 3, "ShellThick": 2}
        nombre = lambda v: v["nombre"] if isinstance(v, dict) else v
        crear = {self.args(op)["Name"]: self.args(op)["ShellType"] for op in self.ops(plan, "cPropArea.SetSlab")}
        self.assertEqual({k: nombre(v) for k, v in crear.items()}, {"LOSA20": "Membrane", "FONDO25": "ShellThick"})
        for op in self.ops(plan, "cPropArea.GetSlab"):  # la relectura compara el tipo de cada sección
            sid = self.args(op)["Name"]
            esperado = next(v["esperado"] for v in op["verificar_valores"] if v["parametro"] == "ShellType")
            self.assertEqual(nombre(esperado), POR_SECCION[sid]["tipo"], sid)
        ideal = {i["seccion"]: i for i in plan.datos["idealizacion_losas"]}
        self.assertEqual((ideal["LOSA20"]["funcion"], ideal["FONDO25"]["funcion"]), ("piso", "fondo_deposito"))
        self.assertNotIn("aviso", ideal["LOSA20"])  # piso Membrane: sin aviso 30.8
        self.assertTrue(all(enum[POR_SECCION[s]["tipo"]] for s in crear))

    def test_relectura_del_modelo_guardado_espera_y_detecta_cada_formulacion(self):
        from draft2model import verificacion_modelo_guardado as vmg
        plan = self.plan(self.config(), tipo_shell_losa=copy.deepcopy(POR_SECCION))
        e = vmg.expectativa_desde_plan(plan.datos)
        self.assertEqual({k: v["shell"]["nombre"] for k, v in e["propiedades_area"].items()},
                         {"LOSA20": "Membrane", "FONDO25": "ShellThick"})
        # Comparador real: un modelo guardado con el fondo cambiado a Membrane se informa como discrepancia.
        from tests.test_verificacion_modelo_guardado import CRITERIOS, lecturas, modelo_desde_expectativa
        self.assertEqual(vmg.comparar(e, lecturas(modelo_desde_expectativa(e)), CRITERIOS)["discrepancias"], [])
        obs = modelo_desde_expectativa(e)
        obs["propiedades_area"]["losas"]["FONDO25"]["shell"] = {"nombre": "Membrane", "valor": 3}
        r = vmg.comparar(e, lecturas(obs), CRITERIOS)
        self.assertEqual([(d["objeto"], d["campo"]) for d in r["discrepancias"]], [("FONDO25", "shell")])

    def test_rechazos(self):
        config = self.config()
        casos = {
            "membrana en fondo": {**POR_SECCION, "FONDO25": {**POR_SECCION["FONDO25"], "tipo": "Membrane"}},
            "falta una sección": {"LOSA20": POR_SECCION["LOSA20"]},
            "sección desconocida": {**POR_SECCION, "OTRA": POR_SECCION["LOSA20"]},
            "función desconocida": {**POR_SECCION, "LOSA20": {**POR_SECCION["LOSA20"], "funcion": "techo"}},
            "sin justificación": {**POR_SECCION, "LOSA20": {**POR_SECCION["LOSA20"], "justificacion": " "}},
            "campo extra": {**POR_SECCION, "LOSA20": {**POR_SECCION["LOSA20"], "modificador": 0.1}},
        }
        for nombre, valor in casos.items():
            with self.subTest(nombre), self.assertRaises(o.ErrorPlan):
                self.plan(copy.deepcopy(config), tipo_shell_losa=copy.deepcopy(valor))

    def test_global_conserva_el_plan_historico(self):
        config = self.config()
        plan = self.plan(config, tipo_shell_losa="ShellThin")
        self.assertNotIn("idealizacion_losas", plan.datos)  # los planes globales históricos siguen regenerándose idénticos
        avisos = [i.get("aviso", "") for i in o.idealizacion_losas(config, plan.datos["opciones"])]
        self.assertTrue(all("no distingue pisos" in a for a in avisos) and len(avisos) == 2)  # el aviso queda disponible

    def test_piso_no_membrana_avisa_30_8(self):
        valor = {**POR_SECCION, "LOSA20": {**POR_SECCION["LOSA20"], "tipo": "ShellThin", "justificacion": "Análisis de cargas de gravedad."}}
        ideal = {i["seccion"]: i for i in self.plan(self.config(), tipo_shell_losa=valor).datos["idealizacion_losas"]}
        self.assertIn("30.8", ideal["LOSA20"]["aviso"])


if __name__ == "__main__":
    unittest.main()
