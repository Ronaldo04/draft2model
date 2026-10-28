"""Integración normativa en la configuración: puertas separadas, sin valores por defecto ni doble escala."""
import copy
import math
import unittest

from draft2model import configuracion_normativa as cn

BASE = {"fuentes": [{"id": "F-PLANO", "descripcion": "Especificaciones L0001", "referencia": "L0001", "sha256": "a" * 64},
                    {"id": "F-USUARIO", "descripcion": "Decisión del usuario", "referencia": "chat", "sha256": "b" * 64}],
        "hipotesis": [], "materiales": [], "espectros": [], "faltantes": []}
MAT = [{"id": "C210", "clase": "concreto", "resistencia": 210, "unidad": "kgf/cm2", "fuente": "F-PLANO"},
       {"id": "ALB", "clase": "albanileria", "resistencia": 35, "unidad": "kgf/cm2", "fuente": "F-PLANO"}]
D = lambda v, e="declarada_usuario", f="F-USUARIO": {"valor": v, "estado": e, "fuente": f}


class ConfiguracionNormativaTests(unittest.TestCase):
    def test_sin_sitio_materiales_si_espectro_no(self):
        original = copy.deepcopy(BASE)
        nuevo, inf = cn.aplicar(BASE, {"materiales": MAT, "zona": D(4), "categoria": D("C")})
        self.assertEqual(BASE, original)  # entrada intacta
        c210 = next(m for m in nuevo["materiales"] if m["id"] == "C210")
        self.assertTrue(math.isclose(c210["E_kN_m2"], 4700 * math.sqrt(210 * 0.0980665) * 1000, rel_tol=1e-12))
        self.assertEqual(c210["peso_kN_m3"], 24.0)
        self.assertEqual(nuevo["espectros"], [])
        rutas = {f["ruta"] for f in nuevo["faltantes"]}
        self.assertTrue({"sitio.perfil", "sitio.sistema", "sitio.Ia", "sitio.Ip", "materiales.ALB"} <= rutas)  # unidad no declarada
        self.assertIn("no generado", inf["espectro"])
        fuentes = {f["id"]: f for f in nuevo["fuentes"]}
        self.assertEqual(fuentes["RNE-E060-DS010-2009"]["sha256"], cn.FUENTES_OFICIALES["RNE-E060-DS010-2009"][2])

    def test_con_puertas_espectro_trazable_y_escala_unica(self):
        dec = {"materiales": MAT[:1], "zona": D(4), "categoria": D("C"), "perfil": D("S2", "hipotesis_piloto"),
               "vs30": D(450, "hipotesis_piloto"), "sistema": D("albanileria_armada_o_confinada", "hipotesis_piloto"),
               "Ia": D(1.0, "hipotesis_piloto"), "Ip": D(1.0, "hipotesis_piloto")}
        nuevo, inf = cn.aplicar(BASE, dec)
        esp = nuevo["espectros"][0]
        sa = dict((t, a) for t, a in esp["puntos"])
        # Z=0,45; U=1; S=1,05 (Vs30=450); R=3; TP=0,5 → meseta Sa = 0,45·2,5·1,05/3·g
        self.assertTrue(math.isclose(sa[0.3], 0.45 * 2.5 * 1.05 / 3 * 9.80665, rel_tol=1e-12))
        self.assertTrue(math.isclose(sa[0.0], 0.45 * 1.0 * 1.05 / 3 * 9.80665, rel_tol=1e-12))  # C(0)=1 en la norma vigente
        self.assertIn("H-NORMA-ESCALA", {h["id"] for h in nuevo["hipotesis"]})
        self.assertTrue(any("hipotesis_piloto" in h["descripcion"] for h in nuevo["hipotesis"]))
        self.assertIsNone(inf["aprobacion_ingenieria"])
        self.assertIn("Derivas", " ".join(inf["no_evaluado"]))

    def test_decisiones_mal_formadas(self):
        for dec in ({"zona": {"valor": 4}}, {"zona": D(4, "supuesta")}, {"zona": D(4, f="F-INEXISTENTE")},
                    {"materiales": [{**MAT[0], "fuente": "X"}]}, {"materiales": [{**MAT[0], "clase": "acero"}]}):
            with self.subTest(dec=dec), self.assertRaises(cn.ErrorNormativa):
                cn.aplicar(BASE, dec)


if __name__ == "__main__":
    unittest.main()
