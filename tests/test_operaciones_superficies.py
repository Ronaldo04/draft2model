"""Plan 0.2 de superficies (desarrollo, no ejecutable) desde configuración y geometría 0.2 SINTÉTICAS.

Los dobles (gestión aprobada por huella, ensamblado ETABSv1 falso) prueban transporte y despacho;
no acreditan ETABS, su solver ni la idoneidad estructural. Ninguna prueba inicia ETABS ni usa red.
"""
import base64
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

from draft2model import adaptador_etabs as ad
from draft2model import ejecutor_etabs as ej
from draft2model import modelo_estructural as m
from draft2model import operaciones_etabs as o
from tests import test_ejecutor_etabs as te
from tests.test_modelo_superficies import CasoSuperficies, VERTICES, geometria_superficies

G_PRUEBA = 9.80665
POWERSHELL = ad.POWERSHELL_51.is_file() and os.name == "nt"
NUEVOS = ("cPropArea.SetSlab", "cPropArea.GetSlab", "cPropArea.GetWall", "cAreaObj.GetPoints", "cAreaObj.GetProperty",
          "cPointObj.GetCoordCartesian")
# Firmas tal como las devolvió la reflexión de metadatos de ETABSv1.dll 1.29.0.0 el 19-10-2026 (sin iniciar ETABS).
REFLEJADAS = {
    "cPropArea.SetSlab": "Int32 (String Name, eSlabType SlabType, eShellType ShellType, String MatProp, Double Thickness, Int32 color, String notes, String GUID)",
    "cPropArea.GetSlab": "Int32 (String Name, eSlabType& SlabType, eShellType& ShellType, String& MatProp, Double& Thickness, Int32& color, String& notes, String& GUID)",
    "cPropArea.GetWall": "Int32 (String Name, eWallPropType& WallPropType, eShellType& ShellType, String& MatProp, Double& Thickness, Int32& color, String& notes, String& GUID)",
    "cAreaObj.GetPoints": "Int32 (String Name, Int32& NumberPoints, String[]& Point)",
    "cAreaObj.GetProperty": "Int32 (String Name, String& PropName)",
    "cPointObj.GetCoordCartesian": "Int32 (String Name, Double& X, Double& Y, Double& Z, String CSys)",
    "cAreaObj.AddByPoint": "Int32 (Int32 NumberPoints, String[]& Point, String& Name, String PropName, String UserName)",
    "cAreaObj.SetLoadUniform": "Int32 (String Name, String LoadPat, Double Value, Int32 Dir, Boolean Replace, String CSys, eItemType ItemType)",
}


class PlanSuperficiesBase(CasoSuperficies):
    def setUp(self):
        super().setUp()
        self.data["masa"]["gravedad_m_s2"] = G_PRUEBA
        self.destino = str(self.trabajo / "salida" / "modelo_superficies.edb")

    def montar(self, geometria=None, aprobada=True):
        super().montar(geometria, aprobada)
        self.data["masa"]["gravedad_m_s2"] = G_PRUEBA

    def opciones(self, **cambios):
        base = {"destino_guardado": self.destino, "tipo_shell_losa": "ShellThin", "gravedad_programa_m_s2": G_PRUEBA}
        base.update(cambios)
        return {k: v for k, v in base.items() if v is not None}

    def plan(self, data=None, **cambios):
        return o.generar_plan_superficies(self.raiz, data if data is not None else self.aprobar_config(), **self.opciones(**cambios))

    @staticmethod
    def args(op):
        return {a["nombre"]: a["valor"] for a in op["argumentos"]}

    def ops(self, plan, metodo):
        return [op for op in plan.operaciones if op["metodo"] == metodo]


class PlanSuperficiesTests(PlanSuperficiesBase):
    def test_plan_desarrollo_trazable_y_no_ejecutable(self):
        data = self.aprobar_config()
        antes = copy.deepcopy(data)
        plan = self.plan(data)
        self.assertEqual(data, antes)
        d = plan.datos
        self.assertEqual((d["version_contrato"], d["estado"], d["ejecutable"]), ("0.2.0", "plan_desarrollo_no_ejecutable", False))
        self.assertFalse(d["aprueba_modelo"])
        self.assertFalse(d["comprobacion"]["apto_para_adaptador"])
        self.assertFalse(d["comprobacion"]["ejecutable_en_etabs"])
        self.assertIn(m.BLOQUEO_SUPERFICIES, d["comprobacion"]["bloqueos"])
        self.assertEqual(o.validar_plan_superficies(d), [])
        self.assertEqual(o.validar_plan(d), ["Contrato de plan no admitido."])  # el ejecutor solo acepta 0.1
        self.assertEqual(plan.huella, self.plan(data).huella)
        fases = list(dict.fromkeys(op["fase"] for op in plan.operaciones))
        self.assertEqual(fases, ["verificacion", "unidades", "pisos", "materiales", "secciones", "puntos", "frames",
                                 "superficies", "comprobacion_objetos", "patrones", "cargas", "masa", "apoyos",
                                 "diafragmas", "casos", "combinaciones", "analisis", "guardado"])
        self.assertTrue(d["integracion_pendiente"])
        capacidades = {p["capacidad"] for p in d["pendientes"]}
        self.assertTrue({"aberturas", "aligerado", "tanque_agua", "escalera"} <= capacidades)
        self.assertEqual(d["mapeo_ids"]["superficies"], {"S1": "S1", "S2": "S2"})
        traza = d["trazabilidad_superficies"]["S2"]
        self.assertEqual((traza["vertices_geometria"], traza["puntos"], traza["seccion"]),
                         (["R1", "R2", "R3", "R4"], ["R1", "R2", "R3", "R4"], "LOSA20"))
        self.assertEqual(traza["papel_geometrico"], "panel inclinado sintético")
        self.assertNotIn("cAnalyze.RunAnalysis", [op["metodo"] for op in plan.operaciones])
        json.dumps(d, allow_nan=False)

    def test_contornos_secciones_cargas_y_cota_intermedia(self):
        plan = self.plan()
        areas = {self.args(op)["UserName"]: self.args(op) for op in self.ops(plan, "cAreaObj.AddByPoint")}
        self.assertEqual(areas["S1"]["NumberPoints"], 4)
        self.assertEqual(areas["S1"]["Point"], [{"ref": "punto:" + p} for p in ("A1", "B1", "C1", "D1")])  # compartidos
        self.assertEqual(areas["S2"]["Point"], [{"ref": "punto:" + p} for p in ("R1", "R2", "R3", "R4")])
        self.assertEqual((areas["S1"]["PropName"], areas["S2"]["PropName"]), ("LOSA20", "LOSA20"))
        losa = self.args(self.ops(plan, "cPropArea.SetSlab")[0])
        self.assertEqual((losa["Name"], losa["SlabType"], losa["ShellType"]["nombre"], losa["MatProp"], losa["Thickness"]),
                         ("LOSA20", {"enum": "eSlabType", "nombre": "Slab", "valor": 0}, "ShellThin", "MAT1", 0.2))
        self.assertFalse(self.ops(plan, "cPropArea.SetWall"))
        puntos = {self.args(op)["UserName"]: self.args(op) for op in self.ops(plan, "cPointObj.AddCartesian")}
        self.assertEqual(len(puntos), 12)  # sin duplicar los vértices compartidos
        self.assertEqual((puntos["R3"]["X"], puntos["R3"]["Y"], puntos["R3"]["Z"]), (4, 6, 1.3))
        pisos = self.args(self.ops(plan, "cStory.SetStories_2")[0])
        self.assertEqual((pisos["StoryNames"], pisos["StoryHeights"]), (["N1"], [2.6]))  # 1.3 m no crea piso
        carga = [self.args(op) for op in self.ops(plan, "cAreaObj.SetLoadUniform")]
        self.assertEqual(carga, [{"Name": {"ref": "superficie:S1"}, "LoadPat": "L", "Value": -2, "Dir": 6, "Replace": False,
                                  "CSys": "Global", "ItemType": {"enum": "eItemType", "nombre": "Objects", "valor": 0}}])
        relectura = {(op["metodo"], json.dumps(self.args(op)["Name"])): op for op in plan.operaciones
                     if op["fase"] == "comprobacion_objetos"}
        coord = relectura["cPointObj.GetCoordCartesian", json.dumps({"ref": "punto:R3"})]["verificar_valores"]
        self.assertEqual([(v["parametro"], v["esperado"]) for v in coord], [("X", 4), ("Y", 6), ("Z", 1.3)])
        contorno = relectura["cAreaObj.GetPoints", json.dumps({"ref": "superficie:S1"})]["verificar_valores"]
        self.assertEqual([(v["parametro"], v["esperado"]) for v in contorno],
                         [("NumberPoints", 4), ("Point", ["A1", "B1", "C1", "D1"])])
        slab = relectura["cPropArea.GetSlab", json.dumps("LOSA20")]
        self.assertEqual([(v["parametro"], v["esperado"]) for v in slab["verificar_valores"]], [("MatProp", "MAT1"), ("Thickness", 0.2)])
        libres = [op for op in plan.operaciones if op["metodo"] == "cPropArea.GetNameList"][0]
        self.assertEqual(libres["verificar_ausentes"][0]["nombres"], ["LOSA20"])
        salidas = {s["registra"] for op in plan.operaciones for s in op.get("salidas", [])}
        self.assertTrue({"superficie:S1", "superficie:S2", "punto:R3"} <= salidas)

    def test_entrada_01_no_elude_bloqueo(self):
        data = self.aprobar_config()
        with self.assertRaises(o.ErrorPlanRechazado):
            o.generar_plan(self.raiz, data, destino_guardado=self.destino, tipo_shell_muro="ShellThin",
                           gravedad_programa_m_s2=G_PRUEBA)
        ejecutor = ej.EjecutorPlanEtabs(ej.configuracion_doble(self.trabajo, (sys.executable, "-c", "pass")))
        with self.assertRaises(ad.ErrorEvidenciaEtabs):
            ejecutor.preparar(self.raiz, data, self.plan(data).datos, copia=self.trabajo / "c.edb",
                              modelo_esperado=self.trabajo / "c.edb")
        with self.assertRaises(o.ErrorPlan):  # una 0.1 no entra por la vía de superficies
            o.generar_plan_superficies(self.raiz, dict(data, version_contrato="0.1.0"), **self.opciones())

    def test_configuracion_o_evidencia_no_admitidas(self):
        with self.assertRaises(o.ErrorPlanRechazado):
            self.plan(self.data)  # borrador
        cambiada = self.aprobar_config()
        cambiada["cargas"][1]["componentes"] = [0, 0, -3]
        with self.assertRaises(o.ErrorPlanRechazado):
            self.plan(cambiada)
        data = self.aprobar_config()
        self.problemas_doble = ["Original alterado (simulado)."]
        with self.assertRaises(o.ErrorPlanRechazado):
            self.plan(data)

    def test_opciones_explicitas(self):
        data = self.aprobar_config()
        for nombre, cambios in {"sin tipo de losa": {"tipo_shell_losa": None}, "losa layered": {"tipo_shell_losa": "Layered"},
                                "muro sin muros": {"tipo_shell_muro": "ShellThin"}, "destino relativo": {"destino_guardado": "m.edb"},
                                "desconocida": {"ejecutar": True}}.items():
            with self.subTest(nombre), self.assertRaises(o.ErrorPlan) as ctx:
                self.plan(data, **cambios)
            self.assertEqual(ctx.exception.codigo, 1)

    def test_transporte_rechaza_concavo_y_cota_fuera_de_pisos(self):
        casos = {
            "cóncavo": (dict(VERTICES, VX=(2, 1.5, 2.6)),
                        [("S1", ["VA", "VB", "VX", "VC", "VD"], "piso cóncavo"), ("S2", ["R1", "R2", "R3", "R4"], "panel")],
                        "cóncava"),
            "sobre el tope": (dict(VERTICES, R3=(4, 6, 3.5), R4=(0, 6, 3.5)), None, "fuera de"),
        }
        for nombre, (vertices, superficies, esperado) in casos.items():
            with self.subTest(nombre):
                self.montar(geometria_superficies(vertices, superficies))
                data = copy.deepcopy(self.data)
                if "VX" in vertices:
                    data["puntos"].append({"id": "VX", "vertice_geometria": "VX"})
                    data["diafragmas"][0]["puntos"].append("VX")
                config = self.aprobar_config(data)
                self.assertTrue(m.comprobar_configuracion(self.raiz, config).apto_para_plan_desarrollo,
                                m.comprobar_configuracion(self.raiz, config).errores)
                with self.assertRaises(o.ErrorPlanRechazado) as ctx:
                    self.plan(config)
                self.assertIn(esperado, "\n".join(ctx.exception.motivos))

    def test_validar_plan_superficies_detecta_manipulacion(self):
        plan = self.plan()

        def con_huella(cambio):
            datos = copy.deepcopy(plan.datos)
            cambio(datos)
            datos["huella_plan"] = o.huella_plan(datos)
            return datos
        area = next(i for i, op in enumerate(plan.operaciones) if op["metodo"] == "cAreaObj.AddByPoint")
        casos = {
            "ejecutable": lambda d: d.update(ejecutable=True),
            "estado": lambda d: d.update(estado="plan_no_ejecutado"),
            "método ajeno": lambda d: d["operaciones"][area].update(metodo="cAreaObj.Delete"),
            "referencia inexistente": lambda d: d["operaciones"][area]["argumentos"][1]["valor"].append({"ref": "punto:NO"}),
            "enum de losa": lambda d: next(op for op in d["operaciones"] if op["metodo"] == "cPropArea.SetSlab")
                                      ["argumentos"][1]["valor"].update(valor=3),
            "guardado no final": lambda d: d["operaciones"].reverse(),
        }
        for nombre, cambio in casos.items():
            with self.subTest(nombre):
                self.assertTrue(o.validar_plan_superficies(con_huella(cambio)))
        self.assertIn("huella", " ".join(o.validar_plan_superficies(dict(plan.datos, aviso="otro"))))

    def test_cli_escribe_plan_de_desarrollo(self):
        entrada = self.escribir(self.aprobar_config(), "config02.json")
        salida = self.trabajo / "plan02.json"
        argv = ["--raiz", str(self.raiz), "--entrada", str(entrada), "--salida", str(salida), "--destino-guardado",
                self.destino, "--tipo-shell-losa", "ShellThick", "--gravedad-programa", str(G_PRUEBA)]
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(o.main(argv), 0)
        datos = json.loads(salida.read_text(encoding="utf-8"))
        self.assertEqual(o.validar_plan_superficies(datos), [])
        self.assertEqual(datos["opciones"]["tipo_shell_losa"], "ShellThick")


class ListaBlancaSuperficiesTests(unittest.TestCase):
    def test_firmas_iguales_a_reflexion_registrada_y_lista_powershell(self):
        for metodo, texto in REFLEJADAS.items():
            _, retorno, parametros = o.FIRMAS[metodo]
            self.assertEqual(f"{retorno} (" + ", ".join(f"{t} {n}" for t, n in parametros) + ")", texto)
        script = ej.SCRIPT_EJECUTOR.read_bytes().decode("utf-8-sig")
        bloque = re.search(r"\$MetodosPermitidos = @\((.*?)\n\)", script, re.S).group(1)
        permitidos = set(re.findall(r"'([^']+)'", bloque))
        self.assertEqual(permitidos, set(o.FIRMAS))
        self.assertTrue(set(NUEVOS) <= permitidos)
        self.assertEqual(o.ENUMS["eSlabType"], {"Slab": 0, "Ribbed": 3, "Waffle": 4})
        for metodo in o.FIRMAS:
            for prohibido in ("RunAnalysis", "Delete", "ApplicationExit", "SetModelIsLocked"):
                self.assertNotIn(prohibido, metodo)

    @unittest.skipUnless(o.DLL_ETABS.is_file() and o.POWERSHELL_51.is_file(), "requiere ETABSv1.dll y Windows PowerShell 5.1")
    def test_firmas_contra_dll_instalada(self):
        informe = o.verificar_firmas_dll()  # solo metadatos por reflexión; no inicia ETABS
        self.assertEqual(informe["diferencias"], [])


ESTADO_CS = r"""
public static class Estado {
  public static System.Collections.Generic.Dictionary<string, double[]> Pt = new System.Collections.Generic.Dictionary<string, double[]>();
  public static System.Collections.Generic.Dictionary<string, string[]> Area = new System.Collections.Generic.Dictionary<string, string[]>();
  public static System.Collections.Generic.Dictionary<string, string> Prop = new System.Collections.Generic.Dictionary<string, string>();
  public static System.Collections.Generic.Dictionary<string, string> Mat = new System.Collections.Generic.Dictionary<string, string>();
  public static System.Collections.Generic.Dictionary<string, double> Esp = new System.Collections.Generic.Dictionary<string, double>();
  public static double Desvio() { return Falso.Env("FALSO_DESVIO") == "1" ? 0.5 : 0.0; }
}"""
CUERPOS = {
    "cPointObj.AddCartesian": 'Name = Falso.Nombre(UserName); Estado.Pt[Name] = new double[] { X, Y, Z }; '
                              'return Falso.Retorno("cPointObj.AddCartesian", 0);',
    "cPointObj.GetCoordCartesian": "double[] p = Estado.Pt[Name]; X = p[0] + Estado.Desvio(); Y = p[1]; Z = p[2]; return 0;",
    "cAreaObj.AddByPoint": 'Name = Falso.Nombre(UserName); Estado.Area[Name] = (string[])Point.Clone(); '
                           'Estado.Prop[Name] = PropName; return Falso.Retorno("cAreaObj.AddByPoint", 0);',
    "cAreaObj.GetPoints": "Point = Estado.Area[Name]; NumberPoints = Point.Length; return 0;",
    "cAreaObj.GetProperty": "PropName = Estado.Prop[Name]; return 0;",
    "cPropArea.SetSlab": 'Estado.Mat[Name] = MatProp; Estado.Esp[Name] = Thickness; return Falso.Retorno("cPropArea.SetSlab", 0);',
    "cPropArea.GetSlab": "MatProp = Estado.Mat[Name]; Thickness = Estado.Esp[Name]; return 0;",
}


@unittest.skipUnless(POWERSHELL, "requiere Windows PowerShell 5.1")
class DespachoSuperficiesTests(PlanSuperficiesBase):
    """Script PowerShell REAL en modo doble contra un ETABSv1 falso con estado. No usa la DLL de CSI ni ETABS.

    El ejecutor Python rechaza planes 0.2; aquí la solicitud se arma directamente para probar solo
    lista blanca, conversión tipada, contornos, relecturas y detención ante fallos del script.
    """

    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        carpeta = Path(cls._dir.name)
        cs, dll = carpeta / "ETABSv1_superficies.cs", carpeta / "ETABSv1_superficies.dll"
        cs.write_text(te.generar_cs(CUERPOS, ESTADO_CS), encoding="utf-8")
        script = "Add-Type -TypeDefinition ([IO.File]::ReadAllText($env:D2M_CS)) -OutputAssembly $env:D2M_DLL -OutputType Library"
        proceso = subprocess.run([str(ad.POWERSHELL_51), "-NoProfile", "-NonInteractive", "-EncodedCommand",
                                  base64.b64encode(script.encode("utf-16-le")).decode()],
                                 env=dict(os.environ, D2M_CS=str(cs), D2M_DLL=str(dll)), capture_output=True, timeout=180)
        if proceso.returncode != 0 or not dll.is_file():
            cls._dir.cleanup()
            raise unittest.SkipTest("No se pudo compilar el ensamblado falso: " + proceso.stderr.decode("utf-8", "replace")[-800:])
        cls.dll = dll

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def setUp(self):
        super().setUp()
        self.copia = self.trabajo / "copia.edb"
        self.copia.write_bytes(te.CONTENIDO_COPIA)
        self.data["plantilla"]["sha256"] = hashlib.sha256(te.CONTENIDO_COPIA).hexdigest()
        Path(self.destino).parent.mkdir()
        self.plan_datos = self.plan().datos

    def ejecutar(self, **entorno):
        ident = uuid4().hex
        corrida = self.trabajo / "corridas" / ident
        corrida.mkdir(parents=True)
        log = corrida / "llamadas.jsonl"
        solicitud = {"contrato": ad.CONTRATO_SOLICITUD, "version_contrato": ad.VERSION_CONTRATO, "id": ident,
                     "operacion": "ejecutar_plan", "modo_configurado": "doble", "dll": str(self.dll),
                     "version_dll_esperada": self.plan_datos["api"]["version_archivo_verificada"],
                     "modelo_esperado": str(self.copia), "sha256_copia": hashlib.sha256(te.CONTENIDO_COPIA).hexdigest(),
                     "destino": self.destino, "id_proceso": None, "huella_plan": self.plan_datos["huella_plan"],
                     "origen": self.plan_datos["origen"], "operaciones": self.plan_datos["operaciones"]}
        contenido = json.dumps(solicitud, ensure_ascii=False).encode("utf-8")
        (corrida / "solicitud.json").write_bytes(contenido)
        respuesta = corrida / "respuesta.json"
        proceso = subprocess.run([str(ad.POWERSHELL_51), "-NoProfile", "-NonInteractive", "-File", str(ej.SCRIPT_EJECUTOR),
                                  "-Solicitud", str(corrida / "solicitud.json"), "-Respuesta", str(respuesta),
                                  "-Sha256Solicitud", hashlib.sha256(contenido).hexdigest(), "-Modo", "doble"],
                                 env=dict(os.environ, FALSO_MODELO=str(self.copia), FALSO_LOG=str(log), **entorno),
                                 capture_output=True, timeout=300, stdin=subprocess.DEVNULL)
        llamadas = [json.loads(l) for l in log.read_text(encoding="utf-8").splitlines() if l.strip()] if log.is_file() else []
        datos = json.loads(respuesta.read_text(encoding="utf-8-sig")) if respuesta.is_file() else None
        return proceso.returncode, datos, llamadas

    def test_despacho_completo_contornos_y_relecturas(self):
        codigo, respuesta, llamadas = self.ejecutar()
        self.assertEqual(codigo, 0, respuesta and respuesta.get("error"))
        self.assertEqual(respuesta["estado"], "ok")
        self.assertEqual([l["m"] for l in llamadas], [op["metodo"] for op in self.plan_datos["operaciones"]])
        areas = [l["a"] for l in llamadas if l["m"] == "cAreaObj.AddByPoint"]
        self.assertIn([4, ["A1", "B1", "C1", "D1"], "", "LOSA20", "S1"], areas)
        self.assertIn([4, ["R1", "R2", "R3", "R4"], "", "LOSA20", "S2"], areas)
        self.assertIn(["LOSA20", "eSlabType.Slab=0", "eShellType.ShellThin=1", "MAT1", 0.2, -1, "", ""],
                      [l["a"] for l in llamadas if l["m"] == "cPropArea.SetSlab"])
        self.assertIn([4.0, 6.0, 1.3, "", "R3", "Global", True, 0], [l["a"] for l in llamadas if l["m"] == "cPointObj.AddCartesian"])
        self.assertIn(["S1", "L", -2.0, 6, False, "Global", "eItemType.Objects=0"],
                      [l["a"] for l in llamadas if l["m"] == "cAreaObj.SetLoadUniform"])
        self.assertEqual(respuesta["progreso"]["mapeo_nombres"]["superficie:S2"], "S2")
        self.assertTrue(Path(self.destino).is_file())  # archivo del doble, no un modelo ETABS

    def test_fallo_parcial_id_cambiado_y_relectura_distinta_detienen_sin_guardar(self):
        casos = {"fallo en AddByPoint": ({"FALSO_FALLA": "cAreaObj.AddByPoint"}, "cAreaObj.AddByPoint"),
                 "ID devuelto distinto": ({"FALSO_RENOMBRAR": "S2"}, "cAreaObj.AddByPoint"),
                 "coordenada releída distinta": ({"FALSO_DESVIO": "1"}, "cPointObj.GetCoordCartesian")}
        for nombre, (entorno, metodo) in casos.items():
            with self.subTest(nombre):
                codigo, respuesta, llamadas = self.ejecutar(**entorno)
                self.assertEqual(codigo, 30)
                self.assertEqual(respuesta["error"]["tipo"], "api")
                self.assertEqual(llamadas[-1]["m"], metodo)
                self.assertNotIn("cFile.Save", [l["m"] for l in llamadas])
                self.assertTrue(respuesta["progreso"]["mutaciones_realizadas"])
                self.assertFalse(Path(self.destino).exists())


if __name__ == "__main__":
    unittest.main()
