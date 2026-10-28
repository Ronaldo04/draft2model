"""Ejecutor del plan ETABS sin tocar ETABS real.

- Despacho: el script PowerShell REAL se ejecuta en modo doble contra un ensamblado .NET falso
  `ETABSv1`, generado desde operaciones_etabs.FIRMAS y compilado con Add-Type, que registra cada
  llamada con sus argumentos (enums, arreglos, refs y salidas).
- Transporte: un proceso doble en Python simula tiempo agotado, fallos y respuestas ausentes.
Ninguna prueba carga la DLL de CSI salvo para rechazarla por token antes de conectar.
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
import time
import unittest
from dataclasses import replace
from pathlib import Path

from draft2model import adaptador_etabs as ad
from draft2model import ejecutor_etabs as ej
from draft2model import operaciones_etabs as o
from tests.test_operaciones_etabs import PlanBase

RAIZ = Path(__file__).resolve().parents[1]
POWERSHELL = ad.POWERSHELL_51.is_file() and os.name == "nt"
CONTENIDO_COPIA = b"EDB SINTETICO: copia de plantilla para pruebas del ejecutor"

TIPOS_CS = {"Double": "double", "Int32": "int", "String": "string", "Boolean": "bool"}


def _tipo_cs(tipo: str) -> str:
    ref = tipo.endswith("&")
    base = tipo.rstrip("&")
    arreglo = base.endswith("[]")
    base = base[:-2] if arreglo else base
    cs = TIPOS_CS.get(base, base) + ("[]" if arreglo else "")
    return ("ref " if ref else "") + cs


def generar_cs(cuerpos: dict | None = None, extra: str = "") -> str:
    """Ensamblado falso con exactamente las interfaces, firmas y enumeraciones de la lista blanca.

    `cuerpos` reemplaza el cuerpo C# de métodos concretos (con estado); `extra` añade tipos de apoyo.
    """
    cuerpos = cuerpos or {}
    enums = {e: dict(v) for e, v in o.ENUMS.items()}
    enums["eUnits"]["lb_in_F"] = 1
    enums.setdefault("eFramePropType", {"I": 1})
    enums.setdefault("eLoadCaseType", {"LinearStatic": 1})
    rutas = {ruta: clave.split(".")[0] for clave, (ruta, _, _) in o.FIRMAS.items()}
    propiedades: dict[str, list[tuple[str, str]]] = {"cOAPI": [("SapModel", "cSapModel")]}
    for ruta, iface in rutas.items():
        if "." in ruta:
            padre, prop = ruta.rsplit(".", 1)
            propiedades.setdefault(rutas[padre], []).append((prop, iface))
    metodos: dict[str, list[str]] = {}
    implementaciones: dict[str, list[str]] = {}
    for clave, (_, retorno, parametros) in o.FIRMAS.items():
        iface, nombre = clave.split(".")
        firma = ", ".join(f"{_tipo_cs(t)} {n}" for t, n in parametros)
        metodos.setdefault(iface, []).append(f"int {nombre}({firma});")
        nombres = [n for _, n in parametros]
        cuerpo = [f'Falso.Registrar("{clave}", new object[] {{ {", ".join(nombres)} }});']
        normal = "0"
        if nombre == "Count":
            normal = f'Falso.Cuenta("{iface}")'
        elif nombre == "GetNameList":
            cuerpo += [f'MyName = Falso.Nombres("{iface}");', "NumberNames = MyName.Length;"]
        elif nombre in ("AddCartesian", "AddByPoint"):
            cuerpo.append("Name = Falso.Nombre(UserName);")
        elif clave == "cFile.Save":
            cuerpo.append("Falso.Guardar(FileName);")
        elif clave == "cSapModel.SetPresentUnits":
            cuerpo.append("Falso.Unidades = Units;")
        cuerpo.append(f'return Falso.Retorno("{clave}", {normal});')
        if clave in cuerpos:
            cuerpo = [cuerpo[0], cuerpos[clave]]
        implementaciones.setdefault(iface, []).append(f"public int {nombre}({firma}) {{ {' '.join(cuerpo)} }}")
    metodos["cSapModel"] += ["string GetModelFilename(bool IncludePath);", "eUnits GetPresentUnits();"]
    implementaciones["cSapModel"] += ["public string GetModelFilename(bool IncludePath) { return Falso.Modelo(); }",
                                      "public eUnits GetPresentUnits() { return Falso.Unidades; }"]
    interfaces = sorted(set(metodos) | set(propiedades))
    partes = ["using System; using System.IO; using System.Text; using System.Globalization;",
              '[assembly: System.Reflection.AssemblyVersion("1.0.0.0")]',
              f'[assembly: System.Reflection.AssemblyFileVersion("{o.VERSION_DLL_VERIFICADA}")]',
              "namespace ETABSv1 {"]
    for enum, valores in enums.items():
        partes.append(f"public enum {enum} {{ " + ", ".join(f"{n} = {v}" for n, v in valores.items()) + " }")
    for iface in interfaces:
        miembros = [f"{tipo} {prop} {{ get; }}" for prop, tipo in propiedades.get(iface, [])] + metodos.get(iface, [])
        partes.append(f"public interface {iface} {{ {' '.join(miembros)} }}")
        impl = [f"public {tipo} {prop} {{ get {{ return new {tipo}_Falso(); }} }}" for prop, tipo in propiedades.get(iface, [])]
        partes.append(f"public class {iface}_Falso : {iface} {{ {' '.join(impl + implementaciones.get(iface, []))} }}")
    partes.append(extra)
    partes.append(r"""
public class Helper {
  public cOAPI GetObject(string typeName) { return Falso.Env("FALSO_SIN_INSTANCIA") == "1" ? null : new cOAPI_Falso(); }
  public cOAPI GetObjectProcess(string typeName, int pid) { return GetObject(typeName); }
}
public static class Falso {
  public static eUnits Unidades = eUnits.lb_in_F;
  public static string Env(string n) { return Environment.GetEnvironmentVariable(n); }
  public static string Modelo() { return Env("FALSO_MODELO"); }
  public static int Cuenta(string i) { string v = Env("FALSO_CUENTA_" + i); return v == null ? 0 : int.Parse(v); }
  public static string[] Nombres(string i) { string v = Env("FALSO_NOMBRES_" + i); return string.IsNullOrEmpty(v) ? new string[0] : v.Split(';'); }
  public static string Nombre(string u) { return Env("FALSO_RENOMBRAR") == u ? u + "_1" : u; }
  public static void Guardar(string f) { if (Env("FALSO_SAVE_SIN_ARCHIVO") != "1") File.WriteAllText(f, "EDB falso"); }
  public static int Retorno(string m, int normal) {
    if (Env("FALSO_EXCEPCION") == m) throw new InvalidOperationException("Excepcion simulada en " + m);
    if (Env("FALSO_FALLA") == m) return 3;
    return normal;
  }
  public static void Registrar(string m, object[] a) {
    string log = Env("FALSO_LOG"); if (log == null) return;
    StringBuilder sb = new StringBuilder(); sb.Append("{\"m\":\"").Append(m).Append("\",\"a\":[");
    for (int i = 0; i < a.Length; i++) { if (i > 0) sb.Append(','); Json(sb, a[i]); }
    sb.Append("]}\n"); File.AppendAllText(log, sb.ToString());
  }
  static void Json(StringBuilder sb, object v) {
    if (v == null) { sb.Append("null"); return; }
    if (v is string) { sb.Append('"').Append(((string)v).Replace("\\", "\\\\").Replace("\"", "\\\"")).Append('"'); return; }
    if (v is bool) { sb.Append((bool)v ? "true" : "false"); return; }
    if (v is Enum) { sb.Append("\"").Append(v.GetType().Name).Append('.').Append(v.ToString()).Append('=').Append(Convert.ToInt32(v)).Append('"'); return; }
    if (v is double) { sb.Append(((double)v).ToString("R", CultureInfo.InvariantCulture)); return; }
    if (v is int) { sb.Append(((int)v).ToString(CultureInfo.InvariantCulture)); return; }
    if (v is Array) { sb.Append('['); int i = 0; foreach (object x in (Array)v) { if (i++ > 0) sb.Append(','); Json(sb, x); } sb.Append(']'); return; }
    sb.Append("\"?\"");
  }
}
}""")
    return "\n".join(partes)


DOBLE = r'''
import json, os, sys, time
args = sys.argv[1:]
sol, resp = args[args.index("-Solicitud") + 1], args[args.index("-Respuesta") + 1]
s = json.load(open(sol, encoding="utf-8"))
modo = os.environ.get("DOBLE_MODO", "ok")
traza = os.path.join(os.path.dirname(resp), "traza.jsonl")
def linea(d):
    with open(traza, "a", encoding="utf-8") as f: f.write(json.dumps(d) + "\n")
ops = s["operaciones"]
lectura = lambda m: m.endswith(".Count") or m.endswith(".GetNameList")
r = {"contrato": "draft2model.etabs_respuesta", "version_contrato": "0.1.0", "version_puente": "doble",
     "modo_ejecucion": "doble", "id_solicitud": s["id"], "operacion": "ejecutar_plan", "estado": "error",
     "error": None, "datos": None, "avisos": [], "progreso": {"operaciones_totales": len(ops),
     "operaciones_ejecutadas": 0, "mutaciones_realizadas": False, "orden_fallida": None, "mapeo_nombres": {}}}
if modo == "lento":
    linea({"orden": 1, "metodo": ops[0]["metodo"], "evento": "inicio", "lectura": True}); time.sleep(60)
if modo == "previo":
    r["error"] = {"tipo": "precondicion", "mensaje": "modelo distinto", "codigo_api": None}
    open(resp, "x").write(json.dumps(r)); sys.exit(40)
corte = next(i for i, op in enumerate(ops) if not lectura(op["metodo"])) + 2
for op in ops[:corte]:
    linea({"orden": op["orden"], "metodo": op["metodo"], "evento": "inicio", "lectura": lectura(op["metodo"])})
    if not lectura(op["metodo"]): r["progreso"]["mutaciones_realizadas"] = True
    if modo == "sin_respuesta" and not lectura(op["metodo"]): sys.exit(1)
    linea({"orden": op["orden"], "metodo": op["metodo"], "evento": "fin"})
r["progreso"]["orden_fallida"] = ops[corte]["orden"]
r["error"] = {"tipo": "api", "mensaje": "retorno 1", "codigo_api": 1}
open(resp, "x").write(json.dumps(r)); sys.exit(30)
'''

RETENER = ("import sys, time; sys.path.insert(0, sys.argv[3]); from draft2model.adaptador_etabs import BloqueoExclusivo; "
           "b = BloqueoExclusivo(sys.argv[1]).adquirir(); open(sys.argv[2], 'w').write('listo'); time.sleep(60)")


class EjecutorBase(PlanBase):
    def setUp(self):
        super().setUp()
        self.copia = self.trabajo / "copia" / "plantilla.edb"
        self.copia.parent.mkdir()
        self.copia.write_bytes(CONTENIDO_COPIA)
        self.data["plantilla"]["sha256"] = hashlib.sha256(CONTENIDO_COPIA).hexdigest()
        Path(self.destino).parent.mkdir()
        self.config = self.aprobar_config()
        self.plan_datos = self.plan(self.config).datos
        self.corridas = self.trabajo / "corridas"
        self.corridas.mkdir()

    def preparar(self, ejecutor, plan=None, **extra):
        argumentos = dict(copia=self.copia, modelo_esperado=self.copia)
        argumentos.update(extra)
        return ejecutor.preparar(self.raiz, self.config, plan if plan is not None else self.plan_datos, **argumentos)


@unittest.skipUnless(POWERSHELL, "requiere Windows PowerShell 5.1")
class DespachoNetFalsoTests(EjecutorBase):
    """Script real + ensamblado ETABSv1 falso: verifica despacho tipado sin ETABS."""

    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        carpeta = Path(cls._dir.name)
        cs, dll = carpeta / "ETABSv1_falso.cs", carpeta / "ETABSv1_falso.dll"
        cs.write_text(generar_cs(), encoding="utf-8")
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

    def ejecutor(self, real=False, **entorno):
        self.log = self.trabajo / f"llamadas_{len(list(self.trabajo.glob('llamadas_*')))}.jsonl"
        variables = {"FALSO_MODELO": str(self.copia), "FALSO_LOG": str(self.log), **entorno}
        if real:
            config = replace(ej.configuracion_real(self.corridas, timeout_s=120, dll=self.dll), entorno=variables)
        else:
            config = ej.configuracion_doble_powershell(self.corridas, self.dll, entorno=variables)
        return ej.EjecutorPlanEtabs(config)

    def llamadas(self):
        if not self.log.is_file():
            return []
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines() if l.strip()]

    def test_plan_completo_despachado_en_orden(self):
        ejecutor = self.ejecutor()
        preparada = self.preparar(ejecutor)
        self.assertEqual(preparada.modo, "preparado")
        self.assertFalse(self.log.exists())  # preparar no ejecuta nada
        resultado = ejecutor.ejecutar(preparada)
        self.assertEqual(resultado.modo_ejecucion, "doble")
        llamadas = self.llamadas()
        self.assertEqual([l["m"] for l in llamadas], [op["metodo"] for op in self.plan_datos["operaciones"]])
        por_metodo = {}
        for l in llamadas:
            por_metodo.setdefault(l["m"], []).append(l["a"])
        self.assertEqual(por_metodo["cSapModel.SetPresentUnits"], [["eUnits.kN_m_C=6"]])  # enum
        pisos = por_metodo["cStory.SetStories_2"][0]
        self.assertEqual((pisos[0], pisos[1], pisos[2], pisos[3], pisos[8]), (0.0, 1, ["N1"], [2.6], [0]))  # arreglos
        self.assertIn([4.0, 0.0, 2.6, "", "B1", "Global", True, 0], por_metodo["cPointObj.AddCartesian"])  # ref de entrada ""
        self.assertIn(["A0", "A1", "", "FRAME", "COL1"], por_metodo["cFrameObj.AddByPoint"])  # refs resueltas
        self.assertIn([4, ["A0", "B0", "B1", "A1"], "", "SHELL15", "M1"], por_metodo["cAreaObj.AddByPoint"])
        self.assertIn(["COMB1", "eCNameType.LoadCase=0", "EST", 1.2], por_metodo["cCombo.SetCaseList"])  # enum por ref
        self.assertEqual(por_metodo["cPropMaterial.GetNameList"][0], [0, [], "eMatType.0=0"])  # 0 = todos
        self.assertNotIn("cAnalyze.RunAnalysis", por_metodo)

        self.assertEqual(Path(resultado.guardado["ruta"]).read_text(), "EDB falso")
        self.assertEqual(resultado.mapeo_nombres["punto:B1"], "B1")
        self.assertEqual(resultado.operaciones_ejecutadas, len(self.plan_datos["operaciones"]))
        self.assertEqual(len(resultado.traza), 2 * len(self.plan_datos["operaciones"]))
        self.assertFalse(resultado.aprueba_modelo)
        self.assertEqual(resultado.datos["unidades"], "kN_m_C")
        self.assertEqual(self.copia.read_bytes(), CONTENIDO_COPIA)  # la copia no se modifica en disco
        self.assertTrue((resultado.corrida / "resultado_ejecucion.json").is_file())
        self.assertFalse(ejecutor.estado_incierto.exists())

    def _fallo(self, **entorno):
        ejecutor = self.ejecutor(**entorno)
        preparada = self.preparar(ejecutor)
        with self.assertRaises((ad.ErrorPuente, ad.ErrorEvidenciaEtabs)) as ctx:
            ejecutor.ejecutar(preparada)
        return ejecutor, preparada, ctx.exception

    def test_fallo_intermedio_detiene_y_conserva_traza(self):
        ejecutor, preparada, error = self._fallo(FALSO_FALLA="cFrameObj.AddByPoint")
        self.assertEqual((error.tipo, error.codigo_proceso, error.codigo), ("api", 30, 3))
        metodos = [l["m"] for l in self.llamadas()]
        self.assertEqual(metodos[-1], "cFrameObj.AddByPoint")
        self.assertEqual(metodos.count("cFrameObj.AddByPoint"), 1)  # ninguna llamada posterior
        orden = next(op["orden"] for op in self.plan_datos["operaciones"] if op["metodo"] == "cFrameObj.AddByPoint")
        self.assertEqual(error.progreso["orden_fallida"], orden)
        self.assertEqual(error.traza[-1], {**error.traza[-1], "orden": orden, "evento": "error"})
        self.assertTrue(error.progreso["mutaciones_realizadas"])
        self.assertTrue(error.incierto)
        self.assertTrue(ejecutor.estado_incierto.is_file())
        self.assertFalse(Path(self.destino).exists())
        # La incertidumbre persiste: otra corrida se bloquea hasta registrar recuperación.
        with self.assertRaises(ad.ErrorBloqueo):
            ejecutor.ejecutar(self.preparar(ejecutor))
        ejecutor.adaptador.confirmar_recuperacion(motor_inactivo_declarado=True, revisor_declarado="Revisor sintético",
                                                  motivo="Prueba: copia descartada.")
        self.assertFalse(ejecutor.estado_incierto.exists())

    def test_excepcion_y_nombre_reasignado(self):
        for entorno, metodo in (({"FALSO_EXCEPCION": "cPropMaterial.SetMPIsotropic"}, "cPropMaterial.SetMPIsotropic"),
                                ({"FALSO_RENOMBRAR": "B1"}, "cPointObj.AddCartesian")):
            with self.subTest(entorno):
                ejecutor, _, error = self._fallo(**entorno)
                self.assertEqual(error.tipo, "api")
                self.assertEqual(self.llamadas()[-1]["m"], metodo)
                self.assertTrue(error.incierto)
                ejecutor.adaptador.confirmar_recuperacion(motor_inactivo_declarado=True, revisor_declarado="R", motivo="m")

    def test_precondiciones_antes_de_mutar(self):
        casos = {"puntos existentes": ({"FALSO_CUENTA_cPointObj": "2"}, "api"),
                 "nombre ocupado": ({"FALSO_NOMBRES_cDiaphragm": "D1;DIA1"}, "precondicion"),
                 "modelo equivocado": ({"FALSO_MODELO": str(self.trabajo / "otro.edb")}, "precondicion"),
                 "sin instancia": ({"FALSO_SIN_INSTANCIA": "1"}, "api_no_disponible")}
        for nombre, (entorno, tipo) in casos.items():
            with self.subTest(nombre):
                ejecutor, _, error = self._fallo(**entorno)
                self.assertEqual(error.tipo, tipo)
                self.assertFalse(any(not (l["m"].endswith(".Count") or l["m"].endswith(".GetNameList"))
                                     for l in self.llamadas()))
                self.assertFalse(error.incierto)
                self.assertFalse(ejecutor.estado_incierto.exists())

    def test_solicitud_manipulada_y_firma(self):
        ejecutor = self.ejecutor()
        preparada = self.preparar(ejecutor)
        contenido = json.loads(preparada.solicitud.solicitud.read_text(encoding="utf-8"))
        contenido["operaciones"][-2]["argumentos"][1]["valor"] = False
        preparada.solicitud.solicitud.write_text(json.dumps(contenido), encoding="utf-8")
        with self.assertRaises(ad.ErrorEvidenciaEtabs):  # huella de la solicitud
            ejecutor.ejecutar(preparada)
        self.assertEqual(self.llamadas(), [])
        # Con la huella rehecha, el script aún rechaza una firma distinta de la DLL antes de mutar.
        preparada = self.preparar(ejecutor)
        contenido = json.loads(preparada.solicitud.solicitud.read_text(encoding="utf-8"))
        contenido["operaciones"][-1]["argumentos"][0]["tipo"] = "String&"
        nuevo = json.dumps(contenido).encode("utf-8")
        preparada.solicitud.solicitud.write_bytes(nuevo)
        argv = preparada.solicitud.argv
        argv[argv.index("-Sha256Solicitud") + 1] = hashlib.sha256(nuevo).hexdigest()
        with self.assertRaises(ad.ErrorPuente) as ctx:
            ejecutor.ejecutar(preparada)
        self.assertEqual((ctx.exception.tipo, ctx.exception.codigo_proceso), ("firma", 42))
        self.assertEqual(self.llamadas(), [])

    def test_guardado_existente_y_save_sin_archivo(self):
        ejecutor = self.ejecutor()
        preparada = self.preparar(ejecutor)
        Path(self.destino).write_bytes(b"previo")
        with self.assertRaises(ad.ErrorAdaptador):  # comprobación de Python antes de lanzar
            ejecutor.ejecutar(preparada)
        with self.assertRaises(ad.ErrorAdaptador):
            self.preparar(ejecutor)
        self.assertEqual(Path(self.destino).read_bytes(), b"previo")
        Path(self.destino).unlink()
        ejecutor, _, error = self._fallo(FALSO_SAVE_SIN_ARCHIVO="1")
        self.assertIn("destino no existe", str(error))
        self.assertTrue(error.incierto)

    def test_modo_real_exige_confirmacion_y_dll_de_csi(self):
        ejecutor = self.ejecutor(real=True)
        preparada = self.preparar(ejecutor)
        with self.assertRaises(ad.ErrorAdaptador):
            ejecutor.ejecutar(preparada)  # sin confirmar_mutacion
        with self.assertRaises(ad.ErrorPuente) as ctx:
            ejecutor.ejecutar(preparada, confirmar_mutacion=True)
        self.assertEqual(ctx.exception.tipo, "precondicion")
        self.assertIn("firmada por CSI", str(ctx.exception))
        self.assertEqual(self.llamadas(), [])

    @unittest.skipUnless(o.DLL_ETABS.is_file(), "requiere ETABSv1.dll instalada")
    def test_modo_doble_rechaza_dll_de_csi(self):
        # Solo carga metadatos para leer el token y se detiene antes de crear Helper o conectar.
        config = ej.configuracion_doble_powershell(self.corridas, o.DLL_ETABS)
        ejecutor = ej.EjecutorPlanEtabs(config)
        with self.assertRaises(ad.ErrorPuente) as ctx:
            ejecutor.ejecutar(self.preparar(ejecutor))
        self.assertIn("no puede cargar la DLL real", str(ctx.exception))


class PreparacionTests(EjecutorBase):
    def ejecutor(self, modo="ok", timeout_s=30.0):
        doble = self.trabajo / "doble.py"
        doble.write_text(DOBLE, encoding="utf-8")
        return ej.EjecutorPlanEtabs(ej.configuracion_doble(self.corridas, (sys.executable, str(doble)),
                                                           timeout_s=timeout_s, entorno={"DOBLE_MODO": modo}))

    def test_plan_alterado_con_huella_rehecha_no_basta(self):
        plan = copy.deepcopy(self.plan_datos)
        next(op for op in plan["operaciones"] if op["metodo"] == "cPropMaterial.SetMPIsotropic")["argumentos"][1]["valor"] = 2e6
        plan["huella_plan"] = o.huella_plan(plan)
        self.assertEqual(o.validar_plan(plan), [])
        with self.assertRaises(ad.ErrorEvidenciaEtabs) as ctx:
            self.preparar(self.ejecutor(), plan)
        self.assertIn("idéntico", str(ctx.exception))
        self.assertEqual(list(self.corridas.iterdir()), [])

    def test_configuracion_o_evidencia_no_vigentes(self):
        cambiada = copy.deepcopy(self.config)
        cambiada["materiales"][0]["E_kN_m2"] = 2e6
        with self.assertRaises(ad.ErrorEvidenciaEtabs):
            self.ejecutor().preparar(self.raiz, cambiada, self.plan_datos, copia=self.copia, modelo_esperado=self.copia)
        self.original.write_bytes(self.original.read_bytes() + b"alterado")
        with self.assertRaises(ad.ErrorEvidenciaEtabs):
            self.preparar(self.ejecutor())

    def test_copia_y_modelo_esperado(self):
        with self.assertRaises(ad.ErrorAdaptador):
            self.preparar(self.ejecutor(), modelo_esperado=self.trabajo / "otro.edb")
        self.copia.write_bytes(CONTENIDO_COPIA + b"x")
        with self.assertRaises(ad.ErrorEvidenciaEtabs):
            self.preparar(self.ejecutor())

    def test_tiempo_agotado_deja_incertidumbre(self):
        ejecutor = self.ejecutor("lento", timeout_s=2)
        inicio = time.monotonic()
        with self.assertRaises(ad.ErrorTiempo) as ctx:
            ejecutor.ejecutar(self.preparar(ejecutor))
        self.assertLess(time.monotonic() - inicio, 30)
        self.assertEqual(ctx.exception.codigo, 4)
        self.assertTrue(ctx.exception.incierto)
        self.assertEqual(ctx.exception.traza[0]["evento"], "inicio")
        self.assertTrue(ejecutor.estado_incierto.is_file())
        with self.assertRaises(ad.ErrorBloqueo):
            ejecutor.ejecutar(self.preparar(ejecutor))

    def test_fallo_parcial_y_sin_respuesta_tras_mutar(self):
        for modo in ("parcial", "sin_respuesta"):
            with self.subTest(modo):
                ejecutor = self.ejecutor(modo)
                with self.assertRaises(ad.ErrorPuente) as ctx:
                    ejecutor.ejecutar(self.preparar(ejecutor))
                self.assertTrue(ctx.exception.incierto)
                self.assertTrue(ejecutor.estado_incierto.is_file())
                self.assertTrue(ctx.exception.traza)
                ejecutor.adaptador.confirmar_recuperacion(motor_inactivo_declarado=True, revisor_declarado="R", motivo="m")

    def test_fallo_previo_sin_incertidumbre(self):
        ejecutor = self.ejecutor("previo")
        with self.assertRaises(ad.ErrorPuente) as ctx:
            ejecutor.ejecutar(self.preparar(ejecutor))
        self.assertEqual(ctx.exception.tipo, "precondicion")
        self.assertFalse(ctx.exception.incierto)
        self.assertFalse(ejecutor.estado_incierto.exists())

    def test_bloqueo_compartido(self):
        ejecutor = self.ejecutor()
        listo = self.trabajo / "listo"
        retenedor = subprocess.Popen([sys.executable, "-c", RETENER, str(ejecutor.config.bloqueo), str(listo), str(RAIZ)])
        self.addCleanup(lambda: (retenedor.kill(), retenedor.wait()))
        limite = time.monotonic() + 20
        while not listo.exists():
            self.assertLess(time.monotonic(), limite)
            time.sleep(0.05)
        preparada = self.preparar(ejecutor)
        with self.assertRaises(ad.ErrorBloqueo):
            ejecutor.ejecutar(preparada)
        self.assertFalse(preparada.solicitud.respuesta.exists())
        # El adaptador comparte el mismo archivo de bloqueo por defecto.
        self.assertEqual(ejecutor.config.bloqueo, ad.AdaptadorEtabs(ad.ConfiguracionPuente.real(self.corridas)).config.bloqueo)


class ScriptEstaticoTests(unittest.TestCase):
    def setUp(self):
        self.bytes = ej.SCRIPT_EJECUTOR.read_bytes()
        self.texto = self.bytes.decode("utf-8-sig")

    def test_bom_y_sin_evaluacion_ni_elusion(self):
        self.assertTrue(self.bytes.startswith(b"\xef\xbb\xbf"))
        for prohibido in ("Invoke-Expression", "iex ", "RunAnalysis", "ApplicationExit", "ExecutionPolicy",
                          "SetPresentUnits(", "Remove-Item -Recurse", "Add-Type -TypeDefinition"):
            self.assertNotIn(prohibido, self.texto)

    def test_lista_blanca_igual_a_firmas(self):
        bloque = re.search(r"\$MetodosPermitidos = @\((.*?)\n\)", self.texto, re.S).group(1)
        self.assertEqual(sorted(re.findall(r"'([^']+)'", bloque)), sorted(o.FIRMAS))

    def test_configuracion_real_sin_bypass(self):
        config = ej.configuracion_real(Path(tempfile.gettempdir()))
        self.assertNotIn("Bypass", config.comando)
        self.assertEqual(config.comando[-1], str(ej.SCRIPT_EJECUTOR))


if __name__ == "__main__":
    unittest.main()
