"""Sección masa_nativa del informe: ligada al análisis/EDB de la evidencia; contraste recalculado, nunca declarado."""
import copy
import unittest

from draft2model import informe

EVID = {"analisis": {"corrida_id": "c" * 32, "sha256_edb_analizado": "e" * 64}, "modelo": {"modelo_id": "m" * 32}}
RES = {"caso_id": "caso-sintetico"}
BASE = {"caso_id": "caso-sintetico", "lectura_id": "a" * 32, "sha256_respuesta": "b" * 64, "corrida_analisis_id": "c" * 32,
        "sha256_edb": "e" * 64,
        "libro": {"masa_total_kn_s2_m": 30.0, "contribuciones_kn_s2_m": {"peso_propio_por_patrones": 20.0, "liquido_AGUA": 10.0}},
        "contraste": {"estado": "coherente", "aprueba_ingenieria": False, "capture_id": "a" * 32, "fuente_esperada": "MsSrc1",
                      "tolerancia_relativa": 1e-3, "masa_libro_kn_s2_m": 30.0, "masa_observada_U1": 30.01, "masa_observada_U2": 30.01}}


def con(**cambios):
    v = copy.deepcopy(BASE)
    for ruta, valor in cambios.items():
        obj = v
        *pre, ult = ruta.split("__")
        for k in pre:
            obj = obj[k]
        obj[ult] = valor
    return v


class MasaNativaInformeTests(unittest.TestCase):
    def test_valida(self):
        informe._validar_masa_nativa(copy.deepcopy(BASE), RES, EVID)
        informe._validar_masa_nativa(con(contraste__estado="no_coherente"), RES, EVID)   # un fallo se informa, no se oculta

    def test_rechazos(self):
        casos = {"sin evidencia": (copy.deepcopy(BASE), None),
                 "otra corrida": (con(corrida_analisis_id="d" * 32), EVID),
                 "otro EDB": (con(sha256_edb="f" * 64), EVID),
                 "estado aprobado": (con(contraste__estado="aprobado"), EVID),
                 "aprueba ingeniería": (con(contraste__aprueba_ingenieria=True), EVID),
                 "otra captura": (con(contraste__capture_id="9" * 32), EVID),
                 "otra fuente": (con(contraste__fuente_esperada="MsSrc2"), EVID),
                 "tolerancia relajada": (con(contraste__tolerancia_relativa=0.05), EVID),
                 "total del libro alterado": (con(libro__masa_total_kn_s2_m=31.0), EVID),
                 "NaN observado": (con(contraste__masa_observada_U1=float("nan")), EVID),
                 "lectura sin identidad": (con(lectura_id="x"), EVID)}
        for nombre, (valor, evid) in casos.items():
            with self.subTest(nombre), self.assertRaises(ValueError):
                informe._validar_masa_nativa(valor, RES, evid)

    def test_sin_fuente_no_hay_seccion(self):
        self.assertIsNone(informe._masa_nativa(None, RES, EVID))
        with self.assertRaises(ValueError):
            informe._masa_nativa({"raiz": ".", "caso": "caso-sintetico", "lectura_id": "a" * 32}, RES, None)


if __name__ == "__main__":
    unittest.main()
