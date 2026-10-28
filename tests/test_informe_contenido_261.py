"""Revisión Codex 261: inventario de contenido del informe ligado al modelo analizado; nunca prueba masa nativa por declaración."""
import copy
import unittest

from draft2model import informe

EVIDENCIA = {"modelo": {"modelo_id": "m" * 32}}
RES = {"caso_id": "caso-sintetico"}
BASE = {"caso_id": "caso-sintetico", "modelo_id": "m" * 32, "huella_plan": "a" * 64, "inventario": {
    "estado": "contabilidad_declarada_coherente",
    "escenarios": [{"deposito": "TANQUE", "estado": "lleno", "fuente": "F1", "declaracion": "AGUA", "modo": "patron_presion",
                    "patron_masa": "HIDRO", "volumen_m3": 1.0, "peso_kn": 10.0, "masa_kn_s2_m": 1.0, "factor_contenido": 1,
                    "fz_presion_kn": -10.0}],
    "peso_total_kn": 10.0, "masa_total_kn_s2_m": 1.0, "aprueba_ingenieria": False, "crea_cargas": False, "ejecutable": False,
    "huella_liquidos": "b" * 64, "estados": {"TANQUE": "lleno"}, "masa_nativa_verificada": False, "nota": "sintético"}}


def con(**cambios):
    v = copy.deepcopy(BASE)
    for ruta, valor in cambios.items():
        obj = v
        *pre, ult = ruta.split("__")
        for k in pre:
            obj = obj[int(k)] if isinstance(obj, list) else obj[k]
        obj[ult] = valor
    return v


class InventarioInformeTests(unittest.TestCase):
    def test_valido_ligado_al_modelo(self):
        informe._validar_contenido_masa(copy.deepcopy(BASE), RES, EVIDENCIA)

    def test_rechazos(self):
        casos = {"masa nativa declarada": con(inventario__masa_nativa_verificada=True),
                 "plan no identificado": con(huella_plan="plan-de-otro-modelo"),
                 "otro modelo": con(modelo_id="x" * 32),
                 "otro caso": con(caso_id="otro"),
                 "NaN": con(inventario__peso_total_kn=float("nan")),
                 "infinito en escenario": con(inventario__escenarios__0__volumen_m3=float("inf")),
                 "booleano como número": con(inventario__escenarios__0__peso_kn=True),
                 "factor parcial": con(inventario__escenarios__0__factor_contenido=0.25),
                 "Fz distinto de −γV": con(inventario__escenarios__0__fz_presion_kn=-9.0),
                 "total alterado": con(inventario__peso_total_kn=11.0),
                 "estado distinto": con(inventario__estados={"TANQUE": "vacio"}),
                 "aprueba ingeniería": con(inventario__aprueba_ingenieria=True),
                 "huella líquidos inválida": con(inventario__huella_liquidos="z")}
        for nombre, valor in casos.items():
            with self.subTest(nombre), self.assertRaises(ValueError):
                informe._validar_contenido_masa(valor, RES, EVIDENCIA)

    def test_sin_evidencia_de_analisis(self):
        with self.assertRaises(ValueError):
            informe._validar_contenido_masa(copy.deepcopy(BASE), RES, None)
        with self.assertRaises(ValueError):
            informe._contenido_masa({"raiz": ".", "caso": "caso-sintetico"}, RES, None)

    def test_sin_fuente_no_hay_seccion(self):
        self.assertIsNone(informe._contenido_masa(None, RES, EVIDENCIA))


if __name__ == "__main__":
    unittest.main()
