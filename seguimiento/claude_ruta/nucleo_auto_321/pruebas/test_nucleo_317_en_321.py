"""321 (núcleo; copia via 319 de las 8 pruebas de 317, cambios mínimos de importación y mensajes): pruebas propias con mini-planes SINTÉTICOS (dimensiones, orientación, conectividad, longitudes, tolerancia, límites).
Ejecutar: python -m unittest seguimiento/claude_ruta/nucleo_auto_321/pruebas/test_nucleo_317_en_321.py
"""
import math, sys, unittest
from pathlib import Path
AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
sys.path.insert(0, str(AQUI.parent / "fuentes"))
import estimacion_extremos_auto as _E  # noqa: E402
class P:  # adaptador: el núcleo 321 conserva la interfaz de 319
    predecir = staticmethod(_E.nucleo)

CFG = {"etabs_version": "21.1.0", "unidades": "kN_m_C", "tolerancia_union_m": 0.001, "procedencia_tolerancia": "escenario_declarado", "vigas": None}
SEC = {"V": (0.40, 0.20), "C1": (0.50, 0.25), "C2": (0.30, 0.30), "C3": (0.70, 0.35)}


def plan(puntos, frames, sec=SEC, ins=(), ang=None, adv=(), areas=(), extra=()):
    ops = [{"metodo": "cPointObj.AddCartesian", "argumentos": [{"nombre": "X", "valor": x}, {"nombre": "Y", "valor": y}, {"nombre": "Z", "valor": z}, {"nombre": "UserName", "valor": n}]}
           for n, (x, y, z) in puntos.items()]
    ops += [{"metodo": "cPropMaterial.SetWeightAndMass", "argumentos": [{"nombre": "Name", "valor": "M"}, {"nombre": "MyOption", "valor": 1}, {"nombre": "Value", "valor": 25.0}]}]
    ops += [{"metodo": "cPropFrame.SetRectangle", "argumentos": [{"nombre": "Name", "valor": n}, {"nombre": "MatProp", "valor": "M"}, {"nombre": "T3", "valor": t3}, {"nombre": "T2", "valor": t2}]}
            for n, (t3, t2) in sec.items()]
    ops += [{"metodo": "cFrameObj.AddByPoint", "argumentos": [{"nombre": "Point1", "valor": {"ref": "punto:" + a}}, {"nombre": "Point2", "valor": {"ref": "punto:" + b}},
             {"nombre": "PropName", "valor": s}, {"nombre": "UserName", "valor": n}]} for n, (a, b, s) in frames]
    ops += [{"metodo": "cFrameObj.SetInsertionPoint", "argumentos": [{"nombre": "Name", "valor": {"ref": "frame:" + n}}]} for n in ins]
    ops += [{"metodo": "cFrameObj.SetLocalAxes", "argumentos": [{"nombre": "Name", "valor": {"ref": "frame:" + n}}, {"nombre": "Ang", "valor": a}]} for n, a in (ang or {}).items()]
    ops += [{"metodo": "cFrameObj.SetLocalAxesAdvanced", "argumentos": [{"nombre": "Name", "valor": {"ref": "frame:" + n}}]} for n in adv]
    ops += [{"metodo": "cAreaObj.AddByPoint", "argumentos": [{"nombre": "Point", "valor": [{"ref": "punto:" + p} for p in a]}]} for a in areas]
    ops += list(extra)
    return {"operaciones": ops}


def base(L=4.0, dir="X", ci="C1", cj="C1", **kw):
    b = (L, 0, 3) if dir == "X" else (0, L, 3)
    pts = {"a": (0, 0, 3), "b": b, "a0": (0, 0, 0), "b0": (b[0], b[1], 0)}
    fr = [("VIGA", ("a", "b", "V"))]
    if ci: fr.append(("CI", ("a0", "a", ci)))
    if cj: fr.append(("CJ", ("b0", "b", cj)))
    return pts, fr


def run(p, **cfg):
    out = P.predecir(p, {**CFG, **cfg})
    return out, {v["viga"]: v for v in out["vigas"]}


class Regla(unittest.TestCase):
    def test_dimensiones_y_orientacion(self):
        _, v = run(plan(*base(dir="X")))
        self.assertAlmostEqual(v["VIGA"]["offsets"]["I"], 0.25)            # T3/2 a lo largo de X (local 2)
        _, v = run(plan(*base(dir="Y")))
        self.assertAlmostEqual(v["VIGA"]["offsets"]["I"], 0.125)           # T2/2 a lo largo de Y (local 3)
        _, v = run(plan(*base(dir="X"), ang={"CI": 90}))
        self.assertAlmostEqual(v["VIGA"]["offsets"]["I"], 0.125)           # columna girada 90°: T2 en X
        self.assertAlmostEqual(v["VIGA"]["offsets"]["J"], 0.25)
        _, v = run(plan(*base(dir="X", ci="C3", cj="C2")))
        self.assertAlmostEqual(v["VIGA"]["offsets"]["I"], 0.35); self.assertAlmostEqual(v["VIGA"]["offsets"]["J"], 0.15)

    def test_conectividad(self):
        pts, fr = base(cj=None); pts["b6"] = (4, 0, 6); fr.append(("CS", ("b", "b6", "C3")))           # columna superior
        pts["c"] = (4, 3, 3); fr.append(("V2", ("b", "c", "V")))                                    # otra viga
        _, v = run(plan(pts, fr), vigas=["VIGA"])
        self.assertEqual(v["VIGA"]["offsets"]["J"], 0.0); self.assertFalse(v["VIGA"]["abstencion"])
        self.assertIn("documental", " ".join(v["VIGA"]["extremos"][1]["procedencia"]))
        pts, fr = base(cj=None); pts.update({"w1": (4, 1, 3), "w2": (4, 1, 0)})
        _, v = run(plan(pts, fr, areas=[("b", "w1", "w2")]))
        self.assertEqual(v["VIGA"]["offsets"]["J"], 0.0); self.assertTrue(v["VIGA"]["salvedades"])
        self.assertIn("experimental_315", " ".join(v["VIGA"]["extremos"][1]["procedencia"]))

    def test_exceso_un_extremo_con_dos_tolerancias(self):
        for tol in (0.001, 0.005):
            _, v = run(plan(*base(L=0.31, cj=None, ci="C3")), tolerancia_union_m=tol)     # 0.35 >= 0.31
            self.assertAlmostEqual(v["VIGA"]["offsets"]["I"], 0.31 - 2 * tol); self.assertAlmostEqual(v["VIGA"]["offsets"]["Lc"], 2 * tol)
        _, v = run(plan(*base(L=0.31, cj=None, ci="C3")), tolerancia_union_m=0.003)
        self.assertIsNone(v["VIGA"]["offsets"]); self.assertIn("no ensayada", v["VIGA"]["abstencion"][0])

    def test_exceso_ambos_extremos_y_limites(self):
        _, v = run(plan(*base(L=0.45, ci="C1", cj="C1")))                                    # 0.25 + 0.25 >= 0.45; cada uno < L
        self.assertEqual((v["VIGA"]["offsets"]["I"], v["VIGA"]["offsets"]["J"]), (0.0, 0.0))
        _, v = run(plan(*base(L=0.2505, cj=None, ci="C1")))                                   # 0.25 en (L-2tol, L): zona límite
        self.assertIsNone(v["VIGA"]["offsets"]); self.assertIn("zona límite", v["VIGA"]["abstencion"][0])
        _, v = run(plan(*base(L=0.008, cj=None, ci="C1")), tolerancia_union_m=0.005)          # L-2tol <= 0
        self.assertIsNone(v["VIGA"]["offsets"]); self.assertIn("no positivo", v["VIGA"]["abstencion"][0])
        _, v = run(plan(*base(L=0.6, cj=None, ci="C1")))                                      # sin exceso
        self.assertAlmostEqual(v["VIGA"]["offsets"]["I"], 0.25)

    def test_descuento_y_totales_solo_completos(self):
        out, v = run(plan(*base()))
        self.assertAlmostEqual(v["VIGA"]["descuento_peso"]["kN"], 0.5 * 0.40 * 0.20 * 25.0); self.assertIsNotNone(out["totales"])
        pts, fr = base(); pts["z"] = (9, 0, 3); pts["y"] = (9, 0, 3.0); fr.append(("V0", ("z", "y", "V")))   # viga degenerada pedida
        out, v = run(plan(pts, fr), vigas=["VIGA", "V0"])
        self.assertIsNone(out["totales"]); self.assertIn("longitud nula", v["V0"]["abstencion"][0])

    def test_abstenciones_de_entrada(self):
        for cfg in ({"etabs_version": "22.0.0"}, {"unidades": "N_mm_C"}, {"tolerancia_union_m": float("nan")}, {"tolerancia_union_m": None},
                    {"procedencia_tolerancia": None}):
            out, _ = run(plan(*base()), **cfg)
            self.assertEqual(out["estado"], "abstencion_global"); self.assertEqual(out["vigas"], [])
        self.assertEqual(P.predecir(plan(*base()), None)["estado"], "abstencion_global")
        pts, fr = base(); pts["b"] = (float("inf"), 0, 3)
        _, v = run(plan(pts, fr), vigas=["VIGA"]); self.assertIn("no finito", v["VIGA"]["abstencion"][0])
        pts, fr = base(); fr.append(("VIGA", ("a", "b", "V")))
        out, v = run(plan(pts, fr)); self.assertTrue(out["problemas_plan"]); self.assertIn("duplicado", v["VIGA"]["abstencion"][0])

    def test_abstenciones_de_columna(self):
        cases = [dict(ins=("CI",)), dict(adv=("CI",)), dict(ang={"CI": 45}), dict(sec={k: v for k, v in SEC.items() if k != "C1"})]
        for kw in cases:
            _, v = run(plan(*base(), **kw))
            self.assertIsNone(v["VIGA"]["offsets"], kw)
        pts, fr = base(); pts["d"] = (1, 1, 0); fr.append(("DIAG", ("d", "a", "C2")))       # frame inclinado conectado
        _, v = run(plan(pts, fr), vigas=["VIGA"]); self.assertIn("inclinado", " ".join(v["VIGA"]["abstencion"]))
        c, s = math.cos(math.radians(30)), math.sin(math.radians(30))
        pts = {"a": (0, 0, 3), "b": (3 * c, 3 * s, 3), "a0": (0, 0, 0)}
        _, v = run(plan(pts, [("VIGA", ("a", "b", "V")), ("CI", ("a0", "a", "C1"))]))
        self.assertIn("oblicua", v["VIGA"]["abstencion"][0])

    def test_independencia_estatica(self):
        # 321: el módulo incluye la CLI (que sí abre archivos); la independencia se exige al NÚCLEO
        import inspect
        src = "".join(inspect.getsource(f) for f in (_E.nucleo, _E.leer_plan, _E._fila_viga, _E._cara, _E._bloqueos, _E.validar_config))
        for prohibido in ("open(", "lecturas_analisis", "respuesta.json", "OffsetI", "libro_masa", "0.002", "pueblo", "VS-"):
            self.assertNotIn(prohibido, src)


if __name__ == "__main__":
    unittest.main()
