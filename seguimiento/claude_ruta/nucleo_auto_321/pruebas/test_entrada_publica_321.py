"""321: entrada pública (plan REAL generado por operaciones_etabs.generar_plan con la fixture existente PlanBase) y CLI.
Ejecutar desde PROYECTO FINAL (sin modificar el paquete público):
  python -m unittest seguimiento/claude_ruta/nucleo_auto_321/pruebas/test_entrada_publica_321.py
"""
import copy, json, sys, tempfile, unittest
from pathlib import Path
AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[3]
sys.path.insert(0, str(RAIZ)); sys.path.insert(0, str(AQUI.parent / "fuentes")); sys.path.insert(0, str(AQUI))
import estimacion_extremos_auto as E  # noqa: E402
from draft2model import operaciones_etabs as oe  # noqa: E402
from tests.test_operaciones_etabs import PlanBase  # noqa: E402  (fixture existente, sin cambios)
from test_nucleo_317_en_321 import plan as mini, base, CFG  # noqa: E402

CFG_REAL = {"etabs_version": "21.1.0", "unidades": "kN_m_C", "tolerancia_union_m": 0.001, "procedencia_tolerancia": "escenario_declarado", "vigas": None}


def op(metodo, salidas=None, **args):
    d = {"metodo": metodo, "argumentos": [{"nombre": k, "valor": v} for k, v in args.items()]}
    if salidas:
        d["salidas"] = salidas
    return d


class EntradaPublica(PlanBase):
    def setUp(self):
        super().setUp()
        self.datos = self.plan().datos
        self.assertEqual(oe.validar_plan_por_version(self.datos), [])

    def test_plan_real_valido_se_analiza(self):
        out = E.estimar_desde_plan(self.datos, CFG_REAL)
        self.assertEqual(out["estado"], "estimacion"); self.assertEqual(out["problemas_plan"], [])
        self.assertEqual(out["plan_validado"]["huella_plan"], self.datos["huella_plan"])
        self.assertTrue(all(v["descuento_peso"] is None or v["descuento_peso"]["kN"] >= 0 for v in out["vigas"]))

    def test_huella_alterada_rechazada_antes_del_nucleo(self):
        d = copy.deepcopy(self.datos)
        punto = next(o for o in d["operaciones"] if o["metodo"] == "cPointObj.AddCartesian")
        next(a for a in punto["argumentos"] if a["nombre"] == "X")["valor"] += 0.5
        out = E.estimar_desde_plan(d, CFG_REAL)
        self.assertEqual(out["estado"], "plan_rechazado"); self.assertIsNone(out["totales"]); self.assertEqual(out["vigas"], [])

    def test_operacion_fuera_de_lista_blanca_rechazada(self):
        d = copy.deepcopy(self.datos)
        d["operaciones"].append(op("cFrameObj.SetEndLengthOffset", Name={"ref": "frame:V1"}, AutoOffset=False, Length1=0.3, Length2=0.0, RZ=0.0))
        self.assertEqual(E.estimar_desde_plan(d, CFG_REAL)["estado"], "plan_rechazado")

    def test_seleccion_inexistente_sin_totales(self):
        out = E.estimar_desde_plan(self.datos, dict(CFG_REAL, vigas=["NO_EXISTE"]))
        self.assertIsNone(out["totales"]); self.assertEqual(out["cobertura"]["pedidas"], 1); self.assertEqual(out["cobertura"]["completas"], 0)

    def test_config_invalida_antes_del_validador(self):
        def no_llamar(_):
            raise AssertionError("el validador no debe ejecutarse con configuración inválida")
        out = E.estimar_desde_plan(self.datos, dict(CFG_REAL, etabs_version="22.0.0"), validador=no_llamar)
        self.assertEqual(out["estado"], "abstencion_global")

    def test_cli_salida_nueva_huellas_y_sin_sobrescritura(self):
        t = Path(tempfile.mkdtemp(prefix="d2m321_"))
        (t / "plan.json").write_text(json.dumps(self.datos), encoding="utf-8"); (t / "cfg.json").write_text(json.dumps(CFG_REAL), encoding="utf-8")
        args = ["--plan", str(t / "plan.json"), "--configuracion", str(t / "cfg.json"), "--salida", str(t / "out.json")]
        self.assertEqual(E.main(args), 0)
        out = json.loads((t / "out.json").read_text(encoding="utf-8")); antes = (t / "out.json").read_bytes()
        self.assertEqual(len(out["entradas"]["plan_sha256"]), 64); self.assertEqual(out["llamadas_remotas"], 0); self.assertFalse(out["lee_solver"])
        self.assertEqual(E.main(args), 2); self.assertEqual((t / "out.json").read_bytes(), antes)
        (t / "cfg_nan.json").write_text('{"etabs_version": "21.1.0", "unidades": "kN_m_C", "tolerancia_union_m": NaN, "procedencia_tolerancia": "escenario_declarado", "vigas": null}', encoding="utf-8")
        self.assertEqual(E.main(["--plan", str(t / "plan.json"), "--configuracion", str(t / "cfg_nan.json"), "--salida", str(t / "o2.json")]), 2)
        (t / "cfg_dup.json").write_text('{"etabs_version": "21.1.0", "etabs_version": "21.1.0", "unidades": "kN_m_C", "tolerancia_union_m": 0.001, "procedencia_tolerancia": "escenario_declarado", "vigas": null}', encoding="utf-8")
        self.assertEqual(E.main(["--plan", str(t / "plan.json"), "--configuracion", str(t / "cfg_dup.json"), "--salida", str(t / "o3.json")]), 2)
        self.assertFalse((t / "o2.json").exists() or (t / "o3.json").exists())
        d = copy.deepcopy(self.datos); d["huella_plan"] = "0" * 64; (t / "malo.json").write_text(json.dumps(d), encoding="utf-8")
        self.assertEqual(E.main(["--plan", str(t / "malo.json"), "--configuracion", str(t / "cfg.json"), "--salida", str(t / "o4.json")]), 3)
        self.assertEqual(json.loads((t / "o4.json").read_text(encoding="utf-8"))["estado"], "plan_rechazado")


class NucleoOperaciones(unittest.TestCase):
    def run_(self, extra, vigas=("VIGA",), areas=(), pts_extra=None):
        pts, fr = base()
        if pts_extra:
            pts.update(pts_extra)
        p = mini(pts, fr, extra=extra, areas=areas)
        return E.nucleo(p, dict(CFG, vigas=list(vigas)))

    def test_grupo_o_seleccion_no_resuelto(self):
        out = self.run_([op("cFrameObj.SetInsertionPoint", Name="GRUPO_X", ItemType={"enum": "eItemType", "nombre": "Group", "valor": 1})])
        self.assertIsNone(out["totales"]); self.assertTrue(any("ItemType" in x for x in out["problemas_plan"]))

    def test_referencia_a_frame_inexistente(self):
        out = self.run_([op("cFrameObj.SetInsertionPoint", Name={"ref": "frame:NO_EXISTE"}, ItemType={"enum": "eItemType", "nombre": "Objects", "valor": 0})])
        self.assertIsNone(out["totales"]); self.assertTrue(any("inexistente" in x for x in out["problemas_plan"]))

    def test_escritura_no_clasificada_no_se_pierde(self):
        out = self.run_([op("cFrameObj.SetReleases", Name={"ref": "frame:VIGA"})])
        self.assertIsNone(out["totales"]); self.assertTrue(out["vigas"][0]["abstencion"]); self.assertTrue(any("no clasificada" in x for x in out["problemas_plan"]))

    def test_unidades_cambiadas_en_el_plan(self):
        out = self.run_([op("cSapModel.SetPresentUnits", Units={"enum": "eUnits", "nombre": "N_mm_C", "valor": 9})])
        self.assertIsNone(out["totales"])

    def test_aberturas_por_nombre_registrado(self):
        pts = {"w1": (4, 1, 3), "w2": (4, 1, 0)}
        area = op("cAreaObj.AddByPoint", salidas=[{"registra": "abertura:A1"}], Point=[{"ref": "punto:b"}, {"ref": "punto:w1"}, {"ref": "punto:w2"}], UserName="A1")
        ok = self.run_([area, op("cAreaObj.SetOpening", Name={"ref": "abertura:A1"}, IsOpening=True, ItemType={"enum": "eItemType", "nombre": "Objects", "valor": 0})], pts_extra=pts)
        self.assertEqual(ok["problemas_plan"], [])
        malo = self.run_([area, op("cAreaObj.SetOpening", Name={"ref": "abertura:NO"}, IsOpening=True, ItemType={"enum": "eItemType", "nombre": "Objects", "valor": 0})], pts_extra=pts)
        self.assertIsNone(malo["totales"])

    def test_multiplicador_peso_propio_y_fuente_de_masa(self):
        out = self.run_([op("cLoadPatterns.Add", Name="D", SelfWTMultiplier=2), op("cLoadPatterns.Add", Name="D2", SelfWTMultiplier=1)])
        self.assertTrue(out["perfil_peso"]["salvedades"])
        out = self.run_([op("cLoadPatterns.Add", Name="D", SelfWTMultiplier=float("nan"))])
        self.assertIsNone(out["totales"])

    def test_clasificacion_completa_de_lista_blanca(self):
        escrituras = {k for k in oe.FIRMAS if not oe.es_lectura(k)}
        self.assertEqual(escrituras - E.INTERPRETADAS - E.NEUTRAS, set())
        self.assertEqual(set(oe.TABLAS_EDITABLES) - E.TABLAS_NEUTRAS, set())


if __name__ == "__main__":
    unittest.main()
