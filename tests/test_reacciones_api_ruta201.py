"""R207/R208 (ruta 201): BaseReact tipado validado estrictamente y aceptación del ensayo solo con equilibrio estricto.

Pruebas puras: sin ETABS, red ni procesos.
"""
import copy
import importlib.util
import unittest
from pathlib import Path
from types import SimpleNamespace

from draft2model import adaptador_etabs as ad
from draft2model import lectura_analisis as la

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("ensayar_plan_liquidos", RAIZ / "scripts" / "ensayar_plan_liquidos.py")
epl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(epl)

ESPERADO = {"modelo_esperado": "C:/x/analisis_etabs/" + "a" * 32 + "/analizado.edb", "version_etabs_esperada": "21.1.0",
            "unidades_esperadas": "kN_m_C", "casos": ["CHIDRO"], "corrida_analisis_id": "a" * 32, "sha256_edb": "b" * 64,
            "tablas": ["Base Reactions"]}
FILA_TABLA = {"OutputCase": "CHIDRO", "FX": "-53.8"}
BR = {"unidades": "kN_m_C", "punto_reaccion": ["0", "0", "0"], "casos_seleccionados": ["CHIDRO"],
      "filas": [{"LoadCase": "CHIDRO", "StepType": "", "StepNum": "0", "FX": "-53.799999999999535", "FY": "0", "FZ": "0",
                 "MX": "0", "MY": "-25.593333333332723", "MZ": "135.7249999999993"}]}


def datos(api=True):
    d = {"modelo": ESPERADO["modelo_esperado"], "version_etabs": "21.1.0", "unidades": "kN_m_C", "casos": ["CHIDRO"],
         "combinaciones": [], "corrida_analisis_id": "a" * 32, "sha256_modelo_verificado": "b" * 64, "instancia": "nueva",
         "id_proceso": 123, "inicio_proceso_utc": "2026-10-21T08:00:00.0000000Z", "instancia_cerrada": True,
         "analisis_ejecutado": False, "aprueba_resultados": False, "estado_casos": {"CHIDRO": 4},
         "tablas": [{"clave": "Base Reactions", "campos": ["OutputCase", "FX"], "filas": [dict(FILA_TABLA)]}]}
    if api:
        d["resultados_api"] = {"BaseReact": copy.deepcopy(BR)}
    return d


class ValidacionBaseReactTests(unittest.TestCase):
    def comprobar(self, data, pedido=True):
        contenido = dict(ESPERADO, **({"resultados_api": ["BaseReact"]} if pedido else {}))
        la.LectorAnalisis._comprobar_datos(SimpleNamespace(contenido=contenido), data)

    def test_valido_pedido_y_legado_sin_pedido(self):
        self.comprobar(datos(True), pedido=True)
        self.comprobar(datos(False), pedido=False)

    def test_rechazos(self):
        def otro_caso(d): d["resultados_api"]["BaseReact"]["filas"][0]["LoadCase"] = "EST"
        def no_finito(d): d["resultados_api"]["BaseReact"]["filas"][0]["MY"] = "NaN"
        def numero_no_texto(d): d["resultados_api"]["BaseReact"]["filas"][0]["FX"] = -53.8
        def unidades(d): d["resultados_api"]["BaseReact"]["unidades"] = "N_mm_C"
        def campo_extra(d): d["resultados_api"]["BaseReact"]["filas"][0]["X"] = "0"
        casos = {"falta cuando se pide": (lambda d: d.pop("resultados_api"), True),
                 "presente sin pedirse": (lambda d: None, False),
                 "otro caso": (otro_caso, True), "no finito": (no_finito, True), "número no textual": (numero_no_texto, True),
                 "otras unidades": (unidades, True), "campo extra": (campo_extra, True)}
        for nombre, (cambio, pedido) in casos.items():
            with self.subTest(nombre):
                d = datos(True)
                cambio(d)
                with self.assertRaises(ad.ErrorEvidenciaEtabs):
                    self.comprobar(d, pedido=pedido)

    def test_solo_basereact_admitido(self):
        lector = la.LectorAnalisis.__new__(la.LectorAnalisis)
        with self.assertRaises(ad.ErrorAdaptador):
            la.LectorAnalisis.preparar_lectura(lector, RAIZ, "x", RAIZ, tablas=["Base Reactions"], casos=["CHIDRO"], resultados_api=["JointReact"])


class AceptacionEnsayoTests(unittest.TestCase):
    F, M = [53.8, 0.0, 0.0], [0.0, 25.593333333333334, -135.725]

    def test_equilibrio_estricto_con_dobles_y_tabla_redondeada_por_separado(self):
        d = datos(True)
        api = epl.equilibrio_api(d, self.F, self.M)
        self.assertEqual(api["estado"], "equilibrio_estricto")
        tabla = epl.equilibrio({"tablas": [{"filas": [{"OutputCase": "CHIDRO", "FX": "-53.8", "FY": "0", "FZ": "0", "MX": "0",
                                                       "MY": "-25.5933", "MZ": "135.725"}]}]}, self.F, self.M)
        self.assertEqual(tabla["estado"], "residuo_excede")  # el texto redondeado NO acredita el criterio estricto
        self.assertEqual(tabla["estado_precision_mostrada"], "equilibrio_a_precision_de_tabla")
        d["resultados_api"]["BaseReact"]["filas"][0]["MY"] = "-25.5933"
        self.assertEqual(epl.equilibrio_api(d, self.F, self.M)["estado"], "residuo_excede")
        d["resultados_api"]["BaseReact"]["punto_reaccion"] = ["1", "0", "0"]
        self.assertEqual(epl.equilibrio_api(d, self.F, self.M)["estado"], "no_comparable")
        self.assertEqual(epl.equilibrio_api(datos(False), self.F, self.M)["estado"], "no_disponible")

    def test_resultado_global_no_cero_si_falta_una_fase_o_el_equilibrio(self):
        base = {"construccion": {"estado": "ok", "cierre_confirmado": True}, "relectura": {"estado": "verificado"},
                "analisis_controlado": {"estado": "ok"}, "lectura_resultados_api": {"estado": "ok"},
                "equilibrio_api_api": {"estado": "equilibrio_estricto"}}
        r = {"fases": copy.deepcopy(base)}
        self.assertEqual(epl.resultado_global(r), 0)
        self.assertTrue(r["resultado_global"]["aceptado"])
        for fase, valor in (("equilibrio_api_api", {"estado": "residuo_excede"}), ("relectura", {"estado": "incompleto"}),
                            ("construccion", {"estado": "ok", "cierre_confirmado": False}), ("analisis_controlado", {"estado": "error"})):
            with self.subTest(fase):
                r = {"fases": dict(copy.deepcopy(base), **{fase: valor})}
                self.assertEqual(epl.resultado_global(r), 2)
                self.assertFalse(r["resultado_global"]["aceptado"])


if __name__ == "__main__":
    unittest.main()
