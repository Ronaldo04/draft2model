"""Plan de operaciones ETABS desde configuración y geometría sintéticas aprobadas; nunca contacta ETABS."""

import contextlib
import copy
import io
import json
import unittest
from pathlib import Path

from draft2model import modelo_estructural as m
from draft2model import operaciones_etabs as o
from tests.test_gestion_geometria import CasoGeometria, CASO

EJEMPLO = Path(__file__).resolve().parents[1] / "examples" / "modelo_estructural_sintetico.json"
G_PRUEBA = 9.80665  # gravedad sintética declarada igual en configuración y opción

FASES = ["verificacion", "unidades", "pisos", "materiales", "secciones", "puntos", "frames", "muros", "patrones",
         "cargas", "masa", "apoyos", "diafragmas", "casos", "combinaciones", "analisis", "guardado"]


def instantanea(raiz: Path) -> dict:
    return {p.relative_to(raiz).as_posix(): p.read_bytes() for p in sorted(raiz.rglob("*")) if p.is_file()}


class PlanBase(CasoGeometria):
    def setUp(self):
        super().setUp()
        imp = self.importar(self.escribir(self.completa()))
        self.aprobada = self.aprobar(imp.identificador, imp.comprobacion.huella_contenido)
        data = json.loads(EJEMPLO.read_bytes())
        data["geometria_origen"] = {"version_id": self.aprobada.identificador,
                                    "sha256_geometria": self.aprobada.comprobacion.sha256_geometria,
                                    "huella_contenido": self.aprobada.comprobacion.huella_contenido}
        # Subconjunto estático: sin modal ni espectro; cargas en punto, frame y muro.
        data["casos"] = [data["casos"][0]]
        data["espectros"] = []
        data["combinaciones"] = [{"id": "COMB1", "tipo": "lineal", "casos": [{"caso": "EST", "factor": 1.2}],
                                  "fuente": "F-SINTETICA"}]
        data["analisis"] = {"casos_ejecutar": ["EST"], "combinaciones_resultados": ["COMB1"], "fuente": "F-SINTETICA"}
        data["masa"]["gravedad_m_s2"] = G_PRUEBA
        data["cargas"] += [
            {"id": "Q1", "patron": "L", "objetivo_tipo": "frame", "objetivo": "V1", "componentes": [0, 0, -2],
             "unidad": "kN/m", "sistema": "global", "fuente": "F-SINTETICA"},
            {"id": "W1", "patron": "L", "objetivo_tipo": "muro", "objetivo": "M1", "componentes": [0.5, 0, 0],
             "unidad": "kN/m2", "sistema": "global", "fuente": "F-SINTETICA"},
            {"id": "Z1", "patron": "D", "objetivo_tipo": "punto", "objetivo": "C1", "componentes": [0, 0, 0],
             "unidad": "kN", "sistema": "global", "fuente": "F-SINTETICA"},
        ]
        self.data = data
        self.destino = str(self.trabajo / "salida" / "modelo_plan.edb")

    def aprobar_config(self, data=None):
        data = copy.deepcopy(self.data if data is None else data)
        data["revision"] = {"estado": "aprobado", "aprobacion": {
            "revisor_declarado": "Revisor SINTÉTICO de software", "fecha": "2026-10-17",
            "huella_configuracion": m.huella_configuracion(data),
            "alcance": "Configuración sintética para probar el plan de operaciones.",
            "identidad_revisor": "declarada_no_verificada"}}
        return data

    def opciones(self, **cambios):
        base = {"destino_guardado": self.destino, "tipo_shell_muro": "ShellThin", "gravedad_programa_m_s2": G_PRUEBA}
        base.update(cambios)
        return {k: v for k, v in base.items() if v is not None}

    def plan(self, data=None, **cambios):
        return o.generar_plan(self.raiz, data if data is not None else self.aprobar_config(), **self.opciones(**cambios))

    def ops(self, plan, metodo):
        return [op for op in plan.operaciones if op["metodo"] == metodo]

    @staticmethod
    def args(op):
        return {a["nombre"]: a["valor"] for a in op["argumentos"]}


class PlanTests(PlanBase):
    def test_plan_ordenado_y_ligado_a_origen(self):
        data = self.aprobar_config()
        antes_config, antes_raiz = copy.deepcopy(data), instantanea(self.raiz)
        plan = self.plan(data)
        self.assertEqual(data, antes_config)  # entradas intactas
        self.assertEqual(instantanea(self.raiz), antes_raiz)  # nada escrito en el expediente
        self.assertEqual(o.validar_plan(plan.datos), [])
        self.assertEqual(plan.huella, self.plan(data).huella)  # determinista

        fases = list(dict.fromkeys(op["fase"] for op in plan.operaciones))
        self.assertEqual(fases, FASES)
        self.assertEqual([op["orden"] for op in plan.operaciones], list(range(1, len(plan.operaciones) + 1)))
        metodos = [op["metodo"] for op in plan.operaciones]
        self.assertEqual(metodos[-1], "cFile.Save")
        self.assertNotIn("cAnalyze.RunAnalysis", metodos)
        self.assertLess(metodos.index("cStory.SetStories_2"), metodos.index("cPointObj.AddCartesian"))
        self.assertLess(max(i for i, x in enumerate(metodos) if x == "cPointObj.AddCartesian"),
                        metodos.index("cFrameObj.AddByPoint"))

        origen = plan.datos["origen"]
        self.assertEqual(origen["huella_configuracion"], m.huella_configuracion(data))
        self.assertEqual(origen["geometria"], data["geometria_origen"])
        self.assertEqual(origen["plantilla"]["sha256"], data["plantilla"]["sha256"])
        self.assertTrue(origen["datos_sinteticos"])
        self.assertFalse(plan.datos["ejecutado"])
        self.assertFalse(plan.datos["aprueba_modelo"])
        self.assertFalse(plan.datos["comprobacion"]["ejecutable_en_etabs"])
        self.assertEqual(plan.datos["mapeo_ids"]["niveles"], {"N0": "Base", "N1": "N1"})
        self.assertEqual(plan.datos["no_aplicados_por_api"]["cargas_sin_efecto"], ["Z1"])
        json.dumps(plan.datos, allow_nan=False)

    def test_unidades_valores_y_referencias(self):
        plan = self.plan()
        unidades = self.args(self.ops(plan, "cSapModel.SetPresentUnits")[0])["Units"]
        self.assertEqual(unidades, {"enum": "eUnits", "nombre": "kN_m_C", "valor": 6})
        self.assertEqual(plan.datos["unidades_etabs"], "kN_m_C")
        pisos = self.args(self.ops(plan, "cStory.SetStories_2")[0])
        self.assertEqual((pisos["BaseElevation"], pisos["StoryNames"], pisos["StoryHeights"]), (0.0, ["N1"], [2.6]))
        material = self.args(self.ops(plan, "cPropMaterial.SetMPIsotropic")[0])
        self.assertEqual((material["E"], material["U"], material["A"]), (1000000, 0.2, 0.0))
        self.assertEqual(self.args(self.ops(plan, "cPropMaterial.SetWeightAndMass")[0])["Value"], 10)
        muro = self.args(self.ops(plan, "cPropArea.SetWall")[0])
        self.assertEqual((muro["Thickness"], muro["ShellType"]["nombre"]), (0.15, "ShellThin"))
        frame = self.args(self.ops(plan, "cPropFrame.SetRectangle")[0])
        self.assertEqual((frame["T3"], frame["T2"]), (0.3, 0.2))

        puntos = {self.args(op)["UserName"]: op for op in self.ops(plan, "cPointObj.AddCartesian")}
        b1 = self.args(puntos["B1"])
        self.assertEqual((b1["X"], b1["Y"], b1["Z"], b1["MergeOff"]), (4.0, 0.0, 2.6, True))
        self.assertEqual(puntos["B1"]["salidas"], [{"parametro": "Name", "registra": "punto:B1", "debe_ser": "B1"}])
        m1 = next(op for op in self.ops(plan, "cAreaObj.AddByPoint") if self.args(op)["UserName"] == "M1")
        self.assertEqual(self.args(m1)["Point"], [{"ref": "punto:A0"}, {"ref": "punto:B0"}, {"ref": "punto:B1"}, {"ref": "punto:A1"}])
        self.assertEqual(len(self.ops(plan, "cAreaObj.AddByPoint")), 4)

        fuerza = self.args(self.ops(plan, "cPointObj.SetLoadForce")[0])
        self.assertEqual((fuerza["Name"], fuerza["LoadPat"], fuerza["Value"]), ({"ref": "punto:B1"}, "L", [0, 0, -1, 0.0, 0.0, 0.0]))
        distribuida = self.args(self.ops(plan, "cFrameObj.SetLoadDistributed")[0])
        self.assertEqual((distribuida["Dir"], distribuida["Val1"], distribuida["RelDist"]), (6, -2, True))
        uniforme = self.args(self.ops(plan, "cAreaObj.SetLoadUniform")[0])
        self.assertEqual((uniforme["Name"], uniforme["Dir"], uniforme["Value"]), ({"ref": "muro:M1"}, 4, 0.5))
        masa = self.args(self.ops(plan, "cPropMaterial.SetMassSource_1")[0])
        self.assertEqual((masa["IncludeElements"], masa["LoadPat"], masa["sf"]), (False, ["D", "L"], [1, 0.25]))
        self.assertEqual(len(self.ops(plan, "cPointObj.SetRestraint")), 4)
        diafragmas = self.ops(plan, "cPointObj.SetDiaphragm")
        self.assertEqual(sorted(self.args(op)["DiaphragmOption"]["nombre"] for op in diafragmas),
                         ["DefinedDiaphragm"] * 4 + ["Disconnect"] * 4)
        cargas = self.args(self.ops(plan, "cCaseStaticLinear.SetLoads")[0])
        self.assertEqual((cargas["LoadType"], cargas["LoadName"], cargas["SF"]), (["Load", "Load"], ["D", "L"], [1, 1]))
        self.assertEqual(self.args(self.ops(plan, "cCombo.SetCaseList")[0])["SF"], 1.2)
        self.assertEqual(self.args(self.ops(plan, "cFile.Save")[0])["FileName"], self.destino)
        verificaciones = [op for op in plan.operaciones if op.get("verificar_ausentes")]
        self.assertIn(["DIA1"], [v["verificar_ausentes"][0]["nombres"] for v in verificaciones])

    def test_configuracion_no_apta_rechazada(self):
        with self.assertRaises(o.ErrorPlanRechazado) as ctx:
            self.plan(self.data)  # borrador
        self.assertEqual(ctx.exception.codigo, 2)
        aprobada = self.aprobar_config()
        aprobada["materiales"][0]["E_kN_m2"] = 2e6  # cambio posterior a la aprobación
        with self.assertRaises(o.ErrorPlanRechazado):
            self.plan(aprobada)
        data = self.aprobar_config()
        self.original.write_bytes(self.original.read_bytes() + b"alterado")
        with self.assertRaises(o.ErrorPlanRechazado):
            self.plan(data)

    def test_caracteristicas_no_soportadas_rechazan_plan_completo(self):
        ejemplo = json.loads(EJEMPLO.read_bytes())
        con_modal = copy.deepcopy(self.data)
        for clave in ("casos", "espectros", "combinaciones", "analisis"):
            con_modal[clave] = ejemplo[clave]
        explicita = copy.deepcopy(self.data)
        explicita["masa"].update(metodo="explicita", factores_patrones=[], masas_puntos=[{"punto": "B1", "masa_kN_s2_m": 1}])
        repetida = copy.deepcopy(self.data)
        repetida["cargas"].append(dict(repetida["cargas"][0], id="P2"))
        mismo_nombre = copy.deepcopy(self.data)
        mismo_nombre["combinaciones"][0]["id"] = "EST"
        mismo_nombre["analisis"]["combinaciones_resultados"] = ["EST"]
        casos = {
            # Modal y espectro se planifican; la respuesta rígida declarada sigue pendiente y rechaza el plan.
            "respuesta rígida": (con_modal, {
                "parametros_modales": {"MOD": {"frecuencia_desplazamiento_hz": 0, "frecuencia_corte_hz": 0,
                                               "tolerancia": 1e-9, "desplazamiento_automatico": True}},
                "amortiguamiento_funciones": {"ESP-PRUEBA": 0.05}, "excentricidad_espectral": {"EX": 0.0},
                "respuesta_rigida_espectral": {"EX": True}}, ["respuesta rígida"]),
            "masa explícita": (explicita, {}, ["explicita"]),
            "gravedad no declarada": (self.data, {"gravedad_programa_m_s2": None}, ["gravedad interna"]),
            "gravedad distinta": (self.data, {"gravedad_programa_m_s2": 9.81}, ["difiere"]),
            "cargas acumuladas": (repetida, {}, ["acumulación"]),
            "combinación con nombre de caso": (mismo_nombre, {}, ["nombres distintos"]),
        }
        for nombre, (data, cambios, esperados) in casos.items():
            with self.subTest(nombre):
                config = self.aprobar_config(data)
                self.assertTrue(m.comprobar_configuracion(self.raiz, config).apto_para_adaptador, nombre)
                with self.assertRaises(o.ErrorPlanRechazado) as ctx:
                    self.plan(config, **cambios)
                texto = "\n".join(ctx.exception.motivos)
                for esperado in esperados:
                    self.assertIn(esperado, texto)

    def test_opciones_invalidas(self):
        data = self.aprobar_config()
        for nombre, cambios in {"sin destino": {"destino_guardado": None}, "destino relativo": {"destino_guardado": "m.edb"},
                                "no edb": {"destino_guardado": str(self.trabajo / "m.txt")},
                                "sin shell": {"tipo_shell_muro": None}, "shell layered": {"tipo_shell_muro": "Layered"},
                                "gravedad negativa": {"gravedad_programa_m_s2": -1}}.items():
            with self.subTest(nombre), self.assertRaises(o.ErrorPlan) as ctx:
                self.plan(data, **cambios)
            self.assertEqual(ctx.exception.codigo, 1)
        with self.assertRaises(o.ErrorPlan):
            o.generar_plan(self.raiz, data, **self.opciones(ejecutar_analisis=True))

    def test_validar_plan_detecta_manipulacion(self):
        plan = self.plan()
        def alterado(cambio):
            datos = copy.deepcopy(plan.datos)
            cambio(datos)
            return datos
        def con_huella(cambio):
            datos = alterado(cambio)
            datos["huella_plan"] = o.huella_plan(datos)
            return datos
        self.assertIn("huella", " ".join(o.validar_plan(alterado(lambda d: d["operaciones"][0].update(fase="x")))))
        casos = {
            "método fuera de lista": lambda d: d["operaciones"][5].update(metodo="cAnalyze.RunAnalysis"),
            "tipo de argumento": lambda d: d["operaciones"][-1]["argumentos"][0].update(valor=1),
            "orden": lambda d: d["operaciones"].pop(3),
            "referencia futura": lambda d: next(op for op in d["operaciones"] if op["metodo"] == "cFrameObj.AddByPoint")
                                          ["argumentos"][0].update(valor={"ref": "punto:NO"}),
            "enum": lambda d: next(op for op in d["operaciones"] if op["metodo"] == "cSapModel.SetPresentUnits")
                             ["argumentos"][0]["valor"].update(valor=1),
            "ejecutado": lambda d: d.update(ejecutado=True),
            "guardado no final": lambda d: d["operaciones"].reverse(),
        }
        for nombre, cambio in casos.items():
            with self.subTest(nombre):
                self.assertTrue(o.validar_plan(con_huella(cambio)))

    def test_cli_salida_nueva(self):
        entrada = self.escribir(self.aprobar_config(), "config.json")
        salida = self.trabajo / "plan.json"
        argv = ["--raiz", str(self.raiz), "--entrada", str(entrada), "--salida", str(salida),
                "--destino-guardado", self.destino, "--tipo-shell-muro", "ShellThick", "--gravedad-programa", str(G_PRUEBA)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(o.main(argv), 0)
        datos = json.loads(salida.read_text(encoding="utf-8"))
        self.assertEqual(o.validar_plan(datos), [])
        antes = salida.read_bytes()
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(o.main(argv), 1)  # no sobrescribe
        self.assertEqual(salida.read_bytes(), antes)


class ListaBlancaTests(unittest.TestCase):
    def test_sin_metodos_de_analisis_cierre_o_borrado(self):
        for metodo in o.FIRMAS:
            for prohibido in ("RunAnalysis", "ApplicationExit", "Delete", "InitializeNewModel", "NewBlank", "SetModelIsLocked"):
                self.assertNotIn(prohibido, metodo)

    def test_comparar_firmas_detecta_diferencias(self):
        reflejado = {"metodos": {k: [[r, [f"{t} {n}" for t, n in p]]] for k, (_, r, p) in o.FIRMAS.items()},
                     "enums": {e: dict(v) for e, v in o.ENUMS.items()}}
        self.assertEqual(o.comparar_firmas(reflejado), [])
        reflejado["metodos"]["cPointObj.AddCartesian"][0][1][0] = "Single X"
        reflejado["enums"]["eUnits"]["kN_m_C"] = 5
        self.assertEqual(len(o.comparar_firmas(reflejado)), 2)

    @unittest.skipUnless(o.DLL_ETABS.is_file() and o.POWERSHELL_51.is_file(), "requiere ETABSv1.dll y Windows PowerShell 5.1")
    def test_firmas_contra_dll_instalada(self):
        # Solo carga metadatos de la DLL por reflexión; no inicia ni contacta ETABS.
        informe = o.verificar_firmas_dll()
        self.assertEqual(informe["diferencias"], [])
        self.assertEqual(informe["version_archivo"], o.VERSION_DLL_VERIFICADA)


if __name__ == "__main__":
    unittest.main()
