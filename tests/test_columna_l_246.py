"""C-1 en L nativa (Codex 246): contrato 0.5, plan, relectura del modelo guardado y convención ensayada en ETABS propio."""
import copy
import json
import math
import unittest
from pathlib import Path

from draft2model import modelo_estructural as m
from draft2model import operaciones_etabs as o
from draft2model import verificacion_modelo_guardado as vmg
from tests import test_integracion_malla as tim
from tests import test_liquidos_ruta201 as tl

F = tim.F
FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "columna_l_etabs21_246.json").read_text(encoding="utf-8"))
L40 = {"id": "L40", "tipo": "frame_l_concreto", "material": "MAT1", "fuente": F,
       "dimensiones": {"alto_m": 0.40, "ancho_m": 0.40, "espesor_ala_m": 0.15, "espesor_alma_m": 0.15,
                       "espejo_eje_2": True, "espejo_eje_3": False}}
INSERCION = {"frame": "VIGA1", "punto_cardinal": 10, "desplazamiento_global_m": [0.07, 0.05, 0.0], "transformar_rigidez": True, "fuente": F}
NUEVOS = {"cPropFrame.SetConcreteL", "cPropFrame.GetConcreteL", "cFrameObj.SetInsertionPoint", "cFrameObj.GetInsertionPoint"}


def con_l(data, insercion=True):
    data = copy.deepcopy(data)
    data["secciones"].append(copy.deepcopy(L40))
    data["asignaciones_frames"] = [{**a, "seccion": "L40"} for a in data["asignaciones_frames"]]
    if insercion:
        data["insercion_frames"] = [copy.deepcopy(INSERCION)]
    return data


class ContratoLTests(tl.CasoLiquidos):
    def base(self):
        return self.montar_liquidos("conectados", "ausente_confirmado", patrones=())

    def test_l_e_insercion_validas_y_clave_opcional(self):
        r = m.validar_configuracion(self.aprobar_local(self.completar(con_l(self.base()))), self.geo)
        self.assertTrue(r.consistente, r.errores)
        sin = m.validar_configuracion(self.aprobar_local(self.completar(con_l(self.base(), insercion=False))), self.geo)
        self.assertTrue(sin.consistente, sin.errores)

    def test_rechazos(self):
        casos = {
            "espejo no booleano": lambda d: d["secciones"][-1]["dimensiones"].update(espejo_eje_2=1),
            "alma >= ancho": lambda d: d["secciones"][-1]["dimensiones"].update(espesor_alma_m=0.40),
            "ala >= alto": lambda d: d["secciones"][-1]["dimensiones"].update(espesor_ala_m=0.5),
            "campo extra": lambda d: d["secciones"][-1]["dimensiones"].update(radio_m=0.01),
            "cardinal 11 no ensayado": lambda d: d["insercion_frames"][0].update(punto_cardinal=11),
            "sin transformación": lambda d: d["insercion_frames"][0].update(transformar_rigidez=False),
            "frame inexistente": lambda d: d["insercion_frames"][0].update(frame="NADA"),
            "vector incompleto": lambda d: d["insercion_frames"][0].update(desplazamiento_global_m=[0.1, 0.0]),
            "lista vacía": lambda d: d.update(insercion_frames=[]),
        }
        for nombre, mutar in casos.items():
            with self.subTest(nombre):
                data = con_l(self.base())
                mutar(data)
                r = m.validar_configuracion(self.completar(data) if nombre != "lista vacía" else data, self.geo)
                self.assertFalse(r.consistente, nombre)

    def test_l_no_admitida_en_04(self):
        data = con_l(self.montar("conectados"), insercion=False)
        r = m.validar_configuracion(data, self.geo)
        self.assertTrue(any("seccion.tipo" in e for e in r.errores), r.errores)


class PlanLTests(tl.CasoLiquidos):
    def test_plan_crea_y_relee_l_e_insercion_por_subframe(self):
        base = self.montar_liquidos("conectados", "ausente_confirmado", patrones=())
        p0 = self.plan(self.aprobar_en_disco(base))
        self.assertFalse(NUEVOS & {x["metodo"] for x in p0["operaciones"]}, "sin L el plan no cambia")
        p = self.plan(self.aprobar_en_disco(con_l(base)))
        self.assertEqual(o.validar_plan_por_version(p), [])
        ops = p["operaciones"]
        set_l = [x for x in ops if x["metodo"] == "cPropFrame.SetConcreteL"]
        args = {a["nombre"]: a["valor"] for a in set_l[0]["argumentos"]}
        self.assertEqual((args["T3"], args["T2"], args["Tf"], args["TwC"], args["TwT"], args["MirrorAbout2"], args["MirrorAbout3"]),
                         (0.40, 0.40, 0.15, 0.15, 0.15, True, False))
        ins = [x for x in ops if x["metodo"] == "cFrameObj.SetInsertionPoint"]
        subframes = sorted(f["id"] for f in p["malla"]["frames"]) if "frames" in p.get("malla", {}) else None
        self.assertGreaterEqual(len(ins), 2)  # VIGA1 se subdivide: la inserción sigue a cada subframe
        self.assertTrue(all(x["argumentos"][0]["valor"]["ref"].startswith("frame:VIGA1_S") for x in ins), subframes)
        relect = [x for x in ops if x["metodo"] == "cFrameObj.GetInsertionPoint"]
        self.assertEqual(len(relect), len(ins))
        esperado = {v["parametro"]: v["esperado"] for v in relect[0]["verificar_valores"]}
        self.assertEqual((esperado["CardinalPoint"], esperado["Offset1"], esperado["CSys"]), (10, [0.07, 0.05, 0.0], "Global"))
        self.assertTrue(any(x["metodo"] == "cPropFrame.GetConcreteL" for x in ops))
        # Mutación antes del guardado: getters después de sus setters.
        orden = {x["metodo"]: x["orden"] for x in ops}
        self.assertLess(orden["cPropFrame.SetConcreteL"], orden["cPropFrame.GetConcreteL"])
        self.assertLess(orden["cFrameObj.GetInsertionPoint"], orden["cFile.Save"])

        exp = vmg.expectativa_desde_plan(p)
        self.assertIn("l", exp["propiedades_frame"]["L40"])
        consulta = vmg.consulta_desde_expectativa(exp)
        self.assertEqual(consulta["secciones_l"], ["L40"])
        self.assertNotIn("L40", consulta["rectangulos"])
        self.assertTrue(consulta["insercion_frames"])
        self.assertNotIn("secciones_l", vmg.consulta_desde_expectativa(vmg.expectativa_desde_plan(p0)))


class ConvencionNativaTests(unittest.TestCase):
    """Fixture del ensayo propio: la carga axial en el punto cardinal 1 revela el vector joint→centroide."""

    def test_propiedades_iguales_a_la_l_acotada(self):
        b, t = 0.40, 0.15
        area = 2 * b * t - t * t
        xc = (b * t * b / 2 + b * t * t / 2 - t * t * t / 2) / area
        ix = (t * b ** 3 / 3 + b * t ** 3 / 3 - t ** 4 / 3) - area * xc ** 2
        # La reapertura devuelve las unidades de la base de datos (N_mm_C), como en el ensayo 181 de aligerados.
        escala = {"kN_m_C": 1.0, "N_mm_C": 1000.0}
        for fase, clave in (("secciones_construccion", "construccion"), ("secciones_reapertura", "reapertura")):
            k = escala[FIXTURE["unidades"][clave]]
            for nombre, s in FIXTURE[fase].items():
                with self.subTest(fase=fase, seccion=nombre):
                    self.assertTrue(math.isclose(s["T3"] / k, 0.40, rel_tol=1e-12) and math.isclose(s["Tf"] / k, 0.15, rel_tol=1e-12))
                    self.assertTrue(math.isclose(s["props"]["Area"] / k ** 2, area, rel_tol=1e-9))
                    self.assertTrue(math.isclose(s["props"]["I22"] / k ** 4, ix, rel_tol=1e-9))
                    self.assertTrue(math.isclose(s["props"]["I33"] / k ** 4, ix, rel_tol=1e-9))

    def test_espejos_definen_brazos_y_no_hay_acople_de_producto_de_inercia(self):
        c = FIXTURE["carga"]
        rig = 2 * c["E_kN_m2"] * FIXTURE["secciones_construccion"]["L_M20_M30"]["props"]["I22"] / (abs(c["PZ_kN"]) * c["H_m"] ** 2)
        brazos = {}
        for nombre, r in FIXTURE["resultados_tope"].items():
            ped = FIXTURE["pedidos"][nombre]
            if ped["variante"] == "C10":
                self.assertEqual(r["FX"][1], 0.0, "ETABS no acopla Ixy: uy nulo bajo FX en el centroide")
            if ped["variante"] != "C1":
                continue
            dx, dy = -r["PZ"][0] * rig, -r["PZ"][1] * rig   # centroide − nudo en la esquina mínima de la envolvente
            brazo_x = "+X" if dx < 0.2 else "-X"           # centroide cerca del borde mínimo: el brazo en Y está en x mínimo
            brazo_y = "+Y" if dy < 0.2 else "-Y"
            brazos[ped["seccion"]] = (brazo_x, brazo_y)
            for d in (dx, dy):
                self.assertTrue(min(abs(d - 0.151923), abs(d - 0.248077)) < 2e-3, d)
        self.assertEqual(brazos, {"L_M20_M30": ("+X", "-Y"), "L_M21_M30": ("+X", "+Y"),
                                  "L_M20_M31": ("-X", "-Y"), "L_M21_M31": ("-X", "+Y")})

    def test_insercion_global_releida_y_cierres(self):
        for nombre, f in FIXTURE["insercion_reapertura"].items():
            if nombre.endswith("_C10G"):
                self.assertEqual(FIXTURE["unidades"]["reapertura"], "N_mm_C")
                self.assertEqual((f["cardinal"], f["offset_i"], f["csys"], f["stiff_transform"]), (10, [100, 50, 0], "Global", True))
        self.assertTrue(all(c["confirmado"] for c in FIXTURE["cierres"]))


if __name__ == "__main__":
    unittest.main()
