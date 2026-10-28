"""Modal Eigen y espectro de respuesta: plan, rechazos y despacho con un ETABSv1 .NET falso con estado.

El doble reproduce los esquemas de tabla OBSERVADOS en ETABS 21.1 (operaciones_etabs.ESQUEMAS_OBSERVADOS:
campos, importabilidad y unidades leídos de una instancia real) y el retorno -96 observado para una tabla
inexistente. Las descripciones de campo y los textos de celda del doble NO están observados: se marcan
como "DOBLE" y solo sirven para ejercitar el mecanismo de comprobación.

Cobertura con dobles: traducción, orden, tipos, transporte y detección de efectos no aplicados.
No es validación física: ninguna prueba contacta ETABS ni ejecuta análisis.
"""

import base64
import copy
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from draft2model import adaptador_etabs as ad
from draft2model import ejecutor_etabs as ej
from draft2model import operaciones_etabs as o
from tests.test_ejecutor_etabs import CONTENIDO_COPIA, POWERSHELL, generar_cs
from tests.test_operaciones_etabs import EJEMPLO, G_PRUEBA, PlanBase, instantanea

FASES_DINAMICAS = ["verificacion", "unidades", "pisos", "materiales", "secciones", "puntos", "frames", "muros",
                   "patrones", "cargas", "masa", "apoyos", "diafragmas", "casos", "casos_modales",
                   "funciones_espectrales", "casos_espectrales", "comprobacion_dinamica", "combinaciones",
                   "analisis", "guardado"]
EIGEN = {"frecuencia_desplazamiento_hz": 0.0, "frecuencia_corte_hz": 0.0, "tolerancia": 1e-9,
         "desplazamiento_automatico": True}
OPCIONES_DINAMICAS = {"parametros_modales": {"MOD": EIGEN}, "amortiguamiento_funciones": {"ESP-PRUEBA": 0.05},
                      "excentricidad_espectral": {"EX": 0.0}, "respuesta_rigida_espectral": {"EX": False}}
CLAVE_INVENTADA_FALLIDA = "Load Cases - Response Spectrum"  # clave de la entrega anterior; ETABS devolvió -96


class DinamicaBase(PlanBase):
    """Ejemplo completo del contrato (EST, MOD, EX y COMB1 = EST + EX) ligado a geometría sintética aprobada."""

    def setUp(self):
        super().setUp()
        ejemplo = json.loads(EJEMPLO.read_bytes())
        for clave in ("casos", "espectros", "combinaciones", "analisis"):
            self.data[clave] = ejemplo[clave]

    def opciones(self, **cambios):
        base = {"destino_guardado": self.destino, "tipo_shell_muro": "ShellThin", "gravedad_programa_m_s2": G_PRUEBA,
                **copy.deepcopy(OPCIONES_DINAMICAS)}
        base.update(cambios)
        return {k: v for k, v in base.items() if v is not None}


class PlanDinamicoTests(DinamicaBase):
    def test_archivado_canonico_no_depende_del_orden_de_claves_json(self):
        plan=self.plan(self.aprobar_config()).datos
        archivado=json.loads(json.dumps(plan,sort_keys=True))
        self.assertEqual(o.validar_plan(archivado),[])

    def test_plan_dinamico_completo(self):
        data = self.aprobar_config()
        antes_config, antes_raiz = copy.deepcopy(data), instantanea(self.raiz)
        plan = self.plan(data)
        self.assertEqual(data, antes_config)
        self.assertEqual(instantanea(self.raiz), antes_raiz)
        self.assertEqual(o.validar_plan(plan.datos), [])
        self.assertEqual(plan.huella, self.plan(data).huella)
        self.assertEqual(list(dict.fromkeys(op["fase"] for op in plan.operaciones)), FASES_DINAMICAS)
        metodos = [op["metodo"] for op in plan.operaciones]
        self.assertNotIn("cAnalyze.RunAnalysis", metodos)
        self.assertLess(metodos.index("cCaseModalEigen.SetCase"), metodos.index("cCaseResponseSpectrum.SetModalCase"))
        self.assertLess(metodos.index("edicion_tabla"), metodos.index("cCaseResponseSpectrum.SetLoads"))
        self.assertLess(metodos.index("cCaseResponseSpectrum.GetModalComb_1"), metodos.index("cCombo.Add"))

        ops = {}
        for op in plan.operaciones:
            ops.setdefault(op["metodo"], []).append(op)
        self.assertEqual(self.args(ops["cCaseModalEigen.SetNumberModes"][0]), {"Name": "MOD", "MaxModes": 3, "MinModes": 3})
        self.assertEqual(self.args(ops["cCaseModalEigen.SetParameters"][0]),
                         {"Name": "MOD", "EigenShiftFreq": 0.0, "EigenCutOff": 0.0, "EigenTol": 1e-9, "AllowAutoFreqShift": 1})
        funcion, caso_rs, amortiguamiento = ops["edicion_tabla"]
        self.assertEqual((funcion["tabla"], funcion["modo"]), (o.TABLA_FUNCION_RS, "agregar"))
        self.assertEqual(funcion["registros"], [
            {"Name": "ESP-PRUEBA", "Period": "0.0", "Value": "0.1", "DampRatio": "0.05"},
            {"Name": "ESP-PRUEBA", "Period": "1.0", "Value": "0.1", "DampRatio": "0.05"},
            {"Name": "ESP-PRUEBA", "Period": "2.0", "Value": "0.05", "DampRatio": "0.05"}])
        # Caso y amortiguamiento separados, en las tablas reales.
        self.assertEqual((caso_rs["tabla"], caso_rs["modo"]), ("Load Case Definitions - Response Spectrum", "modificar"))
        self.assertEqual(caso_rs["registros"], [{"Name": "EX", "ModalCombo": "CQC", "RigidResp": "No"}])
        self.assertEqual((amortiguamiento["tabla"], amortiguamiento["modo"]), ("Load Case Definitions - Damping - Modal", "modificar"))
        self.assertEqual(amortiguamiento["registros"], [{"Name": "EX", "ConstDamp": "0.05"}])
        self.assertEqual(self.args(ops["cCaseResponseSpectrum.SetModalCase"][0]), {"Name": "EX", "ModalCase": "MOD"})
        self.assertEqual(self.args(ops["cCaseResponseSpectrum.SetLoads"][0]), {"Name": "EX", "NumberLoads": 1,
                         "LoadName": ["U1"], "Func": ["ESP-PRUEBA"], "SF": [1], "CSys": ["Global"], "Ang": [0.0]})

        relecturas = {op["metodo"]: {v["parametro"]: v["esperado"] for v in op["verificar_valores"]}
                      for op in plan.operaciones if op.get("verificar_valores")}
        self.assertEqual(relecturas["cFunction.GetValues"], {"NumberItems": 3, "MyTime": [0, 1, 2], "Value": [0.1, 0.1, 0.05]})
        self.assertEqual(relecturas["cCaseResponseSpectrum.GetDampConstant"], {"Damp": 0.05})
        self.assertEqual(relecturas["cCaseResponseSpectrum.GetModalComb_1"], {"MyType": 1})
        self.assertEqual(ops["cCaseResponseSpectrum.GetDampType"][0]["registrar_valores"], ["DampType"])
        self.assertNotIn("verificar_valores", ops["cCaseResponseSpectrum.GetDampType"][0])  # código no observado

        verificaciones = ops["cDatabaseTables.GetAllFieldsInTable"]
        self.assertEqual([self.args(v)["TableKey"] for v in verificaciones],
                         [o.TABLA_FUNCION_RS, o.TABLA_CASO_RS, o.TABLA_AMORTIGUAMIENTO_MODAL])
        for v in verificaciones:
            campos = sorted(o.TABLAS_EDITABLES[self.args(v)["TableKey"]]["campos"])
            self.assertEqual((v["verificar_presentes"][0]["nombres"], v["verificar_importables"]), (campos, campos))
            self.assertEqual(v["fase"], "verificacion")
        self.assertEqual(verificaciones[1]["verificar_textos"],
                         [{"campo": "ModalCombo", "valores": ["CQC"]}, {"campo": "RigidResp", "valores": ["No"]}])
        self.assertNotIn("verificar_textos", verificaciones[2])
        marcados = [self.args(op)["Name"] for op in ops["cAnalyze.SetRunCaseFlag"][1:]]
        self.assertEqual(marcados, ["EST", "MOD", "EX"])
        # 57 estáticas + 4 verificaciones (GetNameList de funciones y 3 tablas) + 3 modales + 1 edición de función
        # + 4 espectrales + 2 ediciones (caso y damping) + 10 relecturas + 1 SetCaseList (EX en COMB1) + 2 marcas.
        self.assertEqual(len(plan.operaciones), 84)

    def test_direcciones_y_combinacion_modal(self):
        for direccion, carga in (("UY", "U2"), ("UZ", "U3")):
            with self.subTest(direccion):
                data = copy.deepcopy(self.data)
                data["casos"][2]["parametros"].update(direccion=direccion, combinacion_modal="SRSS")
                plan = self.plan(self.aprobar_config(data))
                cargas = next(op for op in plan.operaciones if op["metodo"] == "cCaseResponseSpectrum.SetLoads")
                self.assertEqual(self.args(cargas)["LoadName"], [carga])
                tabla = [op for op in plan.operaciones if op["metodo"] == "edicion_tabla"][1]
                self.assertEqual(tabla["registros"][0]["ModalCombo"], "SRSS")
                textos = next(op for op in plan.operaciones if op.get("verificar_textos"))["verificar_textos"]
                self.assertEqual(textos[0], {"campo": "ModalCombo", "valores": ["SRSS"]})
                comb = next(op for op in plan.operaciones if op["metodo"] == "cCaseResponseSpectrum.GetModalComb_1")
                self.assertEqual(comb["verificar_valores"][0]["esperado"], 2)

    def test_opciones_obligatorias_y_validas(self):
        data = self.aprobar_config()
        casos = {
            "sin parametros_modales": {"parametros_modales": None},
            "sin amortiguamiento_funciones": {"amortiguamiento_funciones": None},
            "sin excentricidad_espectral": {"excentricidad_espectral": None},
            "sin respuesta_rigida_espectral": {"respuesta_rigida_espectral": None},
            "eigen incompleto": {"parametros_modales": {"MOD": {k: v for k, v in EIGEN.items() if k != "tolerancia"}}},
            "tolerancia nula": {"parametros_modales": {"MOD": dict(EIGEN, tolerancia=0)}},
            "frecuencia negativa": {"parametros_modales": {"MOD": dict(EIGEN, frecuencia_corte_hz=-1)}},
            "automático no booleano": {"parametros_modales": {"MOD": dict(EIGEN, desplazamiento_automatico=1)}},
            "amortiguamiento 1": {"amortiguamiento_funciones": {"ESP-PRUEBA": 1.0}},
            "amortiguamiento booleano": {"amortiguamiento_funciones": {"ESP-PRUEBA": True}},
            "excentricidad negativa": {"excentricidad_espectral": {"EX": -0.05}},
            "rígida como texto": {"respuesta_rigida_espectral": {"EX": "no"}},
            "caso inexistente": {"excentricidad_espectral": {"EX": 0.0, "OTRO": 0.0}},
            "espectro faltante": {"amortiguamiento_funciones": {}},
        }
        for nombre, cambios in casos.items():
            with self.subTest(nombre), self.assertRaises(o.ErrorPlan) as ctx:
                self.plan(data, **cambios)
            self.assertEqual(ctx.exception.codigo, 1, str(ctx.exception))
            self.assertNotIsInstance(ctx.exception, o.ErrorPlanRechazado)

    def test_respuesta_rigida_y_masa_explicita_rechazan_plan_completo(self):
        with self.assertRaises(o.ErrorPlanRechazado) as ctx:
            self.plan(self.aprobar_config(), respuesta_rigida_espectral={"EX": True})
        self.assertIn("respuesta rígida", "\n".join(ctx.exception.motivos))
        explicita = copy.deepcopy(self.data)
        explicita["masa"].update(metodo="explicita", factores_patrones=[], masas_puntos=[{"punto": "B1", "masa_kN_s2_m": 1}])
        with self.assertRaises(o.ErrorPlanRechazado):
            self.plan(self.aprobar_config(explicita))

    def test_validar_plan_rechaza_ediciones_manipuladas(self):
        plan = self.plan()

        def con_huella(cambio):
            datos = copy.deepcopy(plan.datos)
            cambio(datos)
            datos["huella_plan"] = o.huella_plan(datos)
            return datos

        def edicion(datos, indice=0):
            return [op for op in datos["operaciones"] if op["metodo"] == "edicion_tabla"][indice]

        def verificacion(datos, indice=0):
            return [op for op in datos["operaciones"] if op["metodo"] == "cDatabaseTables.GetAllFieldsInTable"][indice]

        casos = {
            "tabla inventada anterior": lambda d: edicion(d, 1).update(tabla=CLAVE_INVENTADA_FALLIDA),
            "ConstDamp en el caso": lambda d: edicion(d, 1).update(campos=["Name", "ModalCombo", "RigidResp", "ConstDamp"]),
            "campo extra": lambda d: edicion(d)["registros"][0].update(GUID="x"),
            "valor vacío": lambda d: edicion(d)["registros"][0].update(Value=""),
            "modo cambiado": lambda d: edicion(d, 2).update(modo="agregar"),
            "método de tabla suelto": lambda d: verificacion(d).update(metodo="cDatabaseTables.ApplyEditedTables"),
            "mutación en verificación": lambda d: d["operaciones"][0].update(metodo="cCaseModalEigen.SetCase"),
            "tolerancia excesiva": lambda d: next(op for op in d["operaciones"] if op.get("verificar_valores"))
                                             ["verificar_valores"][0].update(tolerancia_relativa=0.5),
            "presentes sobre entrada": lambda d: verificacion(d)["verificar_presentes"][0].update(parametro="TableKey"),
            "textos vacíos": lambda d: verificacion(d, 1)["verificar_textos"][0].update(valores=[]),
            "registrar entrada": lambda d: next(op for op in d["operaciones"] if op.get("registrar_valores"))
                                           .update(registrar_valores=["Name"]),
            "importables en otro método": lambda d: d["operaciones"][3].update(verificar_importables=["Name"]),
        }
        for nombre, cambio in casos.items():
            with self.subTest(nombre):
                self.assertTrue(o.validar_plan(con_huella(cambio)))


class RegresionEstaticaTests(PlanBase):
    def test_plan_estatico_sin_fases_ni_constantes_dinamicas(self):
        plan = self.plan()
        self.assertEqual(len(plan.operaciones), 57)
        fases = set(op["fase"] for op in plan.operaciones)
        self.assertFalse(fases & {"casos_modales", "funciones_espectrales", "casos_espectrales", "comprobacion_dinamica"})
        self.assertEqual(plan.datos["constantes_adaptador"], o.CONSTANTES_ADAPTADOR)
        self.assertNotIn("funciones", plan.datos["mapeo_ids"])
        with self.assertRaises(o.ErrorPlan):  # una opción dinámica sin casos que la usen no se ignora
            self.plan(parametros_modales={"MOD": EIGEN})

    @unittest.skipUnless(o.DLL_ETABS.is_file() and o.POWERSHELL_51.is_file(), "requiere ETABSv1.dll y Windows PowerShell 5.1")
    def test_firmas_dinamicas_contra_dll(self):
        informe = o.verificar_firmas_dll()  # solo metadatos por reflexión; no inicia ETABS
        self.assertEqual(informe["diferencias"], [])
        self.assertEqual(informe["metodos"], len(o.FIRMAS))
        self.assertTrue({"cCaseModalEigen.SetNumberModes", "cCaseResponseSpectrum.SetLoads", "cCaseResponseSpectrum.GetDampType",
                         "cDatabaseTables.ApplyEditedTables"} <= set(o.FIRMAS))


# -- ensamblado falso con estado y esquemas observados ------------------------------

def _cs_lista(valores, tipo):
    if tipo == "bool":
        return "new bool[] { " + ", ".join("true" if v else "false" for v in valores) + " }"
    return "new string[] { " + ", ".join('"' + v + '"' for v in valores) + " }"


def apoyo_cs() -> str:
    """C# del estado del doble; los esquemas salen de ESQUEMAS_OBSERVADOS (evidencia real), no se escriben a mano."""
    ramas_campos, ramas_importables = [], []
    for tabla, esquema in o.ESQUEMAS_OBSERVADOS.items():
        ramas_campos.append(f'if (tabla == "{tabla}") return {_cs_lista(esquema["campos"], "string")};')
        ramas_importables.append(f'if (tabla == "{tabla}") return {_cs_lista(esquema["importables"], "bool")};')
    return r"""
public static class Dinamico {
  public static System.Collections.Generic.Dictionary<string, int[]> Modos = new System.Collections.Generic.Dictionary<string, int[]>();
  public static System.Collections.Generic.Dictionary<string, double[]> Eigen = new System.Collections.Generic.Dictionary<string, double[]>();
  public static System.Collections.Generic.Dictionary<string, System.Collections.Generic.List<string[]>> Funciones = new System.Collections.Generic.Dictionary<string, System.Collections.Generic.List<string[]>>();
  public static System.Collections.Generic.Dictionary<string, string> Modal = new System.Collections.Generic.Dictionary<string, string>();
  public static System.Collections.Generic.Dictionary<string, object[]> Cargas = new System.Collections.Generic.Dictionary<string, object[]>();
  public static System.Collections.Generic.Dictionary<string, double> Ecc = new System.Collections.Generic.Dictionary<string, double>();
  public static System.Collections.Generic.Dictionary<string, string> Comb = new System.Collections.Generic.Dictionary<string, string>();
  public static System.Collections.Generic.Dictionary<string, string> Rigida = new System.Collections.Generic.Dictionary<string, string>();
  public static System.Collections.Generic.Dictionary<string, string> Amort = new System.Collections.Generic.Dictionary<string, string>();
  public static System.Collections.Generic.Dictionary<string, string> TipoAmort = new System.Collections.Generic.Dictionary<string, string>();
  public static string PendTabla; public static string[] PendCampos; public static string[] PendDatos;
  public const string TF = "Functions - Response Spectrum - User Defined";
  public const string TC = "Load Case Definitions - Response Spectrum";
  public const string TD = "Load Case Definitions - Damping - Modal";
  public const string PREDETERMINADO = "<predeterminado del doble>";
  static Dinamico() {
    string previa = Falso.Env("FALSO_FUNCION_PREVIA");
    if (previa != null) {
      Funciones[previa] = new System.Collections.Generic.List<string[]>();
      Funciones[previa].Add(new string[] { "0", "1", "0.05" }); Funciones[previa].Add(new string[] { "1", "1", "0.05" });
    }
  }
  public static bool Ignorar(string m) { return Falso.Env("FALSO_IGNORAR") == m; }
  public static double Num(string s) { return double.Parse(s, CultureInfo.InvariantCulture); }
  public static string Txt(double d) { return d.ToString("R", CultureInfo.InvariantCulture); }
  static string[] CamposObservados(string tabla) { """ + " ".join(ramas_campos) + r""" return null; }
  static bool[] ImportablesObservados(string tabla) { """ + " ".join(ramas_importables) + r""" return null; }
  public static string[] Campos(string tabla) {
    string[] c = CamposObservados(tabla);
    string sin = Falso.Env("FALSO_SIN_CAMPO");
    return (c == null || sin == null) ? c : Array.FindAll(c, x => x != sin);
  }
  public static bool[] Importables(string tabla) {
    string[] todos = CamposObservados(tabla); bool[] imp = ImportablesObservados(tabla);
    if (todos == null) return null;
    var salida = new System.Collections.Generic.List<bool>();
    for (int i = 0; i < todos.Length; i++) {
      if (todos[i] == Falso.Env("FALSO_SIN_CAMPO")) continue;
      salida.Add(todos[i] == Falso.Env("FALSO_NO_IMPORTABLE") ? false : imp[i]);
    }
    return salida.ToArray();
  }
  public static string Descripcion(string campo) {
    if (Falso.Env("FALSO_DESCRIPCION_VACIA") == campo) return "";
    if (campo == "ModalCombo") return "DOBLE, texto no observado: CQC, SRSS";
    if (campo == "RigidResp") return "DOBLE, texto no observado: Yes, No";
    return "DOBLE";
  }
  static System.Collections.Generic.Dictionary<string, string> FilaVacia(string tabla) {
    var d = new System.Collections.Generic.Dictionary<string, string>();
    foreach (string k in CamposObservados(tabla)) d[k] = "";
    return d;
  }
  public static System.Collections.Generic.List<System.Collections.Generic.Dictionary<string, string>> Filas(string tabla) {
    var filas = new System.Collections.Generic.List<System.Collections.Generic.Dictionary<string, string>>();
    if (tabla == TF) {
      foreach (var f in Funciones) foreach (var p in f.Value) {
        var d = FilaVacia(TF); d["Name"] = f.Key; d["Period"] = p[0]; d["Value"] = p[1]; d["DampRatio"] = p == f.Value[0] ? p[2] : ""; filas.Add(d);
      }
    } else if (tabla == TC) {
      foreach (var c in Cargas) {
        string[] ln = (string[])c.Value[0]; string[] fn = (string[])c.Value[1]; double[] sf = (double[])c.Value[2];
        var d = FilaVacia(TC);
        d["Name"] = c.Key; d["LoadName"] = ln.Length > 0 ? ln[0] : ""; d["Function"] = fn.Length > 0 ? fn[0] : "";
        d["TransAccSF"] = sf.Length > 0 ? Txt(sf[0]) : ""; d["Angle"] = "0"; d["ModalCase"] = Modal[c.Key];
        d["ModalCombo"] = Comb[c.Key]; d["RigidResp"] = Rigida[c.Key]; d["EccenRatio"] = Txt(Ecc[c.Key]);
        filas.Add(d);
      }
    } else if (tabla == TD) {
      foreach (var c in Cargas) {
        var d = FilaVacia(TD); d["Name"] = c.Key; d["DampType"] = TipoAmort[c.Key]; d["ConstDamp"] = Amort[c.Key]; filas.Add(d);
      }
    }
    return filas;
  }
  public static void Aplicar() {
    if (PendTabla == null || Ignorar("cDatabaseTables.ApplyEditedTables")) return;
    int n = PendCampos.Length;
    if (PendTabla == TF) Funciones.Clear();
    for (int r = 0; r * n < PendDatos.Length; r++) {
      var d = new System.Collections.Generic.Dictionary<string, string>();
      for (int i = 0; i < n; i++) d[PendCampos[i]] = PendDatos[r * n + i];
      string k = d["Name"];
      if (PendTabla == TF) {
        if (!Funciones.ContainsKey(k)) Funciones[k] = new System.Collections.Generic.List<string[]>();
        Funciones[k].Add(new string[] { d["Period"], d["Value"], d.ContainsKey("DampRatio") ? d["DampRatio"] : "0.05" });
      } else if (PendTabla == TC) {
        if (d.ContainsKey("ModalCombo")) Comb[k] = d["ModalCombo"];
        if (d.ContainsKey("RigidResp")) Rigida[k] = d["RigidResp"];
      } else if (PendTabla == TD) {
        if (d.ContainsKey("ConstDamp")) Amort[k] = d["ConstDamp"];
      }
    }
    PendTabla = null;
  }
}
"""


CUERPOS_CS = {
    "cCaseModalEigen.SetCase": 'Dinamico.Modos[Name] = new int[] { 12, 1 }; Dinamico.Eigen[Name] = new double[] { 0, 0, 1e-9, 1 }; '
                               'return Falso.Retorno("cCaseModalEigen.SetCase", 0);',
    "cCaseModalEigen.SetNumberModes": 'if (!Dinamico.Ignorar("cCaseModalEigen.SetNumberModes")) Dinamico.Modos[Name] = new int[] { MaxModes, MinModes }; '
                                      'return Falso.Retorno("cCaseModalEigen.SetNumberModes", 0);',
    "cCaseModalEigen.SetParameters": 'if (!Dinamico.Ignorar("cCaseModalEigen.SetParameters")) Dinamico.Eigen[Name] = new double[] { EigenShiftFreq, EigenCutOff, EigenTol, AllowAutoFreqShift }; '
                                     'return Falso.Retorno("cCaseModalEigen.SetParameters", 0);',
    "cCaseModalEigen.GetNumberModes": "int[] m = Dinamico.Modos[Name]; MaxModes = m[0]; MinModes = m[1]; return 0;",
    "cCaseModalEigen.GetParameters": "double[] e = Dinamico.Eigen[Name]; EigenShiftFreq = e[0]; EigenCutOff = e[1]; EigenTol = e[2]; "
                                     "AllowAutoFreqShift = (int)e[3]; return 0;",
    "cCaseModalEigen.GetLoads": "NumberLoads = 0; LoadType = new string[0]; LoadName = new string[0]; TargetPar = new double[0]; "
                                "StaticCorrect = new bool[0]; return 0;",
    "cCaseResponseSpectrum.SetCase": 'Dinamico.Modal[Name] = ""; Dinamico.Cargas[Name] = new object[] { new string[0], new string[0], new double[0], new string[0], new double[0] }; '
                                     'Dinamico.Ecc[Name] = 0.25; Dinamico.Comb[Name] = Dinamico.PREDETERMINADO; Dinamico.Rigida[Name] = Dinamico.PREDETERMINADO; '
                                     'Dinamico.Amort[Name] = "0"; Dinamico.TipoAmort[Name] = Dinamico.PREDETERMINADO; '
                                     'return Falso.Retorno("cCaseResponseSpectrum.SetCase", 0);',
    "cCaseResponseSpectrum.SetModalCase": 'Dinamico.Modal[Name] = ModalCase; return Falso.Retorno("cCaseResponseSpectrum.SetModalCase", 0);',
    "cCaseResponseSpectrum.SetLoads": "Dinamico.Cargas[Name] = new object[] { (string[])LoadName.Clone(), (string[])Func.Clone(), (double[])SF.Clone(), "
                                      '(string[])CSys.Clone(), (double[])Ang.Clone() }; return Falso.Retorno("cCaseResponseSpectrum.SetLoads", 0);',
    "cCaseResponseSpectrum.SetEccentricity": 'if (!Dinamico.Ignorar("cCaseResponseSpectrum.SetEccentricity")) Dinamico.Ecc[Name] = Eccen; '
                                             'return Falso.Retorno("cCaseResponseSpectrum.SetEccentricity", 0);',
    "cCaseResponseSpectrum.GetModalCase": "ModalCase = Dinamico.Modal[Name]; return 0;",
    "cCaseResponseSpectrum.GetLoads": "object[] c = Dinamico.Cargas[Name]; LoadName = (string[])c[0]; Func = (string[])c[1]; SF = (double[])c[2]; "
                                      "CSys = (string[])c[3]; Ang = (double[])c[4]; NumberLoads = LoadName.Length; return 0;",
    "cCaseResponseSpectrum.GetEccentricity": "Eccen = Dinamico.Ecc[Name]; return 0;",
    "cCaseResponseSpectrum.GetDampConstant": "Damp = Dinamico.Num(Dinamico.Amort[Name]); return 0;",
    "cCaseResponseSpectrum.GetDampType": "DampType = 0; return 0;",
    "cCaseResponseSpectrum.GetModalComb_1": 'MyType = Dinamico.Comb[Name] == "CQC" ? 1 : (Dinamico.Comb[Name] == "SRSS" ? 2 : 0); F1 = 0; F2 = 0; '
                                            "PeriodicRigidCombType = 1; Td = 0; return 0;",
    "cFunction.GetNameList": "var l = new System.Collections.Generic.List<string>(Falso.Nombres(\"cFunction\")); l.AddRange(Dinamico.Funciones.Keys); "
                             "MyName = l.ToArray(); NumberNames = MyName.Length; return 0;",
    "cFunction.GetValues": "if (!Dinamico.Funciones.ContainsKey(Name)) { NumberItems = 0; MyTime = new double[0]; Value = new double[0]; return 1; } "
                           "var p = Dinamico.Funciones[Name]; NumberItems = p.Count; MyTime = new double[p.Count+1]; Value = new double[p.Count+1]; "
                           "for (int i = 0; i < p.Count; i++) { MyTime[i+1] = Dinamico.Num(p[i][0]); Value[i+1] = Dinamico.Num(p[i][1]); } return 0;",
    # Retorno -96 observado en ETABS 21.1 para una clave de tabla inexistente.
    "cDatabaseTables.GetAllFieldsInTable": f"string[] c = Dinamico.Campos(TableKey); if (c == null) return {o.RETORNO_TABLA_INEXISTENTE_OBSERVADO}; "
                                           "TableVersion = 1; NumberFields = c.Length; FieldKey = c; FieldName = c; "
                                           "Description = new string[c.Length]; UnitsString = new string[c.Length]; IsImportable = Dinamico.Importables(TableKey); "
                                           "for (int i = 0; i < c.Length; i++) { Description[i] = Dinamico.Descripcion(c[i]); UnitsString[i] = \"\"; } "
                                           'return Falso.Retorno("cDatabaseTables.GetAllFieldsInTable", 0);',
    "cDatabaseTables.GetTableForEditingArray": f"string[] c = Dinamico.Campos(TableKey); if (c == null) return {o.RETORNO_TABLA_INEXISTENTE_OBSERVADO}; "
                                               "var filas = Dinamico.Filas(TableKey); TableVersion = 1; "
                                               "FieldsKeysIncluded = filas.Count == 0 ? new string[0] : c; NumberRecords = filas.Count; "
                                               "var datos = new System.Collections.Generic.List<string>(); "
                                               "foreach (var f in filas) foreach (string k in c) datos.Add(f.ContainsKey(k) ? f[k] : \"\"); "
                                               "TableData = datos.ToArray(); return 0;",
    "cDatabaseTables.SetTableForEditingArray": "Dinamico.PendTabla = TableKey; Dinamico.PendCampos = FieldsKeysIncluded; Dinamico.PendDatos = TableData; "
                                               'return Falso.Retorno("cDatabaseTables.SetTableForEditingArray", 0);',
    "cDatabaseTables.ApplyEditedTables": 'NumFatalErrors = 0; NumErrorMsgs = 0; NumWarnMsgs = Falso.Env("FALSO_ADVERTENCIA") == "1" ? 1 : 0; NumInfoMsgs = 1; '
                                         'ImportLog = NumWarnMsgs > 0 ? "Advertencia simulada: valor por defecto asumido" : "Importacion simulada"; '
                                         'Dinamico.Aplicar(); return Falso.Retorno("cDatabaseTables.ApplyEditedTables", 0);',
}

EXPANSION_TABLA = ["cDatabaseTables.GetAllFieldsInTable", "cDatabaseTables.GetTableForEditingArray",
                   "cDatabaseTables.SetTableForEditingArray", "cDatabaseTables.ApplyEditedTables",
                   "cDatabaseTables.GetTableForEditingArray"]


def compilar_doble(carpeta: Path) -> Path:
    cs, dll = carpeta / "ETABSv1_dinamico.cs", carpeta / "ETABSv1_dinamico.dll"
    cs.write_text(generar_cs(CUERPOS_CS, apoyo_cs()), encoding="utf-8")
    script = "Add-Type -TypeDefinition ([IO.File]::ReadAllText($env:D2M_CS)) -OutputAssembly $env:D2M_DLL -OutputType Library"
    proceso = subprocess.run([str(ad.POWERSHELL_51), "-NoProfile", "-NonInteractive", "-EncodedCommand",
                              base64.b64encode(script.encode("utf-16-le")).decode()],
                             env=dict(os.environ, D2M_CS=str(cs), D2M_DLL=str(dll)), capture_output=True, timeout=180)
    if proceso.returncode != 0 or not dll.is_file():
        raise unittest.SkipTest("No se compiló el ensamblado falso: " + proceso.stderr.decode("utf-8", "replace")[-1500:])
    return dll


@unittest.skipUnless(POWERSHELL, "requiere Windows PowerShell 5.1")
class DespachoDinamicoTests(DinamicaBase):
    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        try:
            cls.dll = compilar_doble(Path(cls._dir.name))
        except unittest.SkipTest:
            cls._dir.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

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

    def ejecutar(self, **entorno):
        self.log = self.trabajo / f"llamadas_{len(list(self.trabajo.glob('llamadas_*')))}.jsonl"
        variables = {"FALSO_MODELO": str(self.copia), "FALSO_LOG": str(self.log), **entorno}
        ejecutor = ej.EjecutorPlanEtabs(ej.configuracion_doble_powershell(self.corridas, self.dll, entorno=variables))
        preparada = ejecutor.preparar(self.raiz, self.config, self.plan_datos, copia=self.copia, modelo_esperado=self.copia)
        return ejecutor, preparada

    def llamadas(self):
        if not self.log.is_file():
            return []
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines() if l.strip()]

    def esperado(self):
        salida = []
        for op in self.plan_datos["operaciones"]:
            salida += EXPANSION_TABLA if op["metodo"] == "edicion_tabla" else [op["metodo"]]
        return salida

    def fallo(self, ejecutor_preparada=None, **entorno):
        ejecutor, preparada = ejecutor_preparada or self.ejecutar(**entorno)
        with self.assertRaises((ad.ErrorPuente, ad.ErrorEvidenciaEtabs)) as ctx:
            ejecutor.ejecutar(preparada)
        return ejecutor, ctx.exception

    def sin_mutaciones(self):
        return all(o.es_lectura(l["m"]) for l in self.llamadas())

    def test_despacho_dinamico_completo_y_fusion_de_tablas(self):
        ejecutor, preparada = self.ejecutar(FALSO_FUNCION_PREVIA="UnifRS")
        resultado = ejecutor.ejecutar(preparada)
        llamadas = self.llamadas()
        self.assertEqual([l["m"] for l in llamadas], self.esperado())
        por_metodo = {}
        for l in llamadas:
            por_metodo.setdefault(l["m"], []).append(l["a"])
        self.assertEqual(por_metodo["cCaseModalEigen.SetNumberModes"], [["MOD", 3, 3]])
        self.assertEqual(por_metodo["cCaseResponseSpectrum.SetLoads"], [["EX", 1, ["U1"], ["ESP-PRUEBA"], [1], ["Global"], [0]]])
        funcion, caso, amort = por_metodo["cDatabaseTables.SetTableForEditingArray"]
        self.assertEqual((funcion[0], caso[0], amort[0]), (o.TABLA_FUNCION_RS, o.TABLA_CASO_RS, o.TABLA_AMORTIGUAMIENTO_MODAL))
        self.assertEqual(funcion[2], list(o.ESQUEMAS_OBSERVADOS[o.TABLA_FUNCION_RS]["campos"]))
        self.assertEqual((funcion[4].count("UnifRS"), funcion[4].count("ESP-PRUEBA")), (2, 3))  # función previa conservada
        # Solo columnas importables: MassSource y CoordSys (no importables en ETABS 21.1) no se escriben.
        esquema = o.ESQUEMAS_OBSERVADOS[o.TABLA_CASO_RS]
        self.assertEqual(caso[2], [c for c, i in zip(esquema["campos"], esquema["importables"]) if i])
        self.assertNotIn("MassSource", caso[2])
        self.assertNotIn("CoordSys", caso[2])
        fila_caso = dict(zip(caso[2], caso[4]))
        self.assertEqual((fila_caso["Name"], fila_caso["ModalCombo"], fila_caso["RigidResp"]), ("EX", "CQC", "No"))
        self.assertEqual(fila_caso["Function"], "ESP-PRUEBA")  # campos ajenos se conservan
        fila_amort = dict(zip(amort[2], amort[4]))
        self.assertEqual((fila_amort["Name"], fila_amort["ConstDamp"], fila_amort["DampType"]),
                         ("EX", "0.05", "<predeterminado del doble>"))  # DampType no se modifica
        self.assertNotIn("cAnalyze.RunAnalysis", por_metodo)
        fines = [l for l in resultado.traza if l.get("evento") == "fin"]
        self.assertEqual(len(fines), len(self.plan_datos["operaciones"]))
        self.assertEqual(next(l for l in fines if l["metodo"] == "cCaseResponseSpectrum.GetDampConstant")["releidos"], {"Damp": 0.05})
        self.assertEqual(next(l for l in fines if l["metodo"] == "cCaseResponseSpectrum.GetDampType")["releidos"], {"DampType": 0})
        tablas = [l["tabla"] for l in fines if l["metodo"] == "edicion_tabla"]
        self.assertEqual([(t["tabla"], t["registros_declarados"], t["registros_totales"]) for t in tablas],
                         [(o.TABLA_FUNCION_RS, 3, 5), (o.TABLA_CASO_RS, 1, 1), (o.TABLA_AMORTIGUAMIENTO_MODAL, 1, 1)])
        self.assertFalse(resultado.aprueba_modelo)
        self.assertFalse(ejecutor.estado_incierto.exists())

    def test_regresion_clave_inventada_detiene_antes_de_mutar(self):
        """Reproduce la corrida real b8b0a4e5…: GetAllFieldsInTable('Load Cases - Response Spectrum') = -96."""
        ejecutor, preparada = self.ejecutar()
        contenido = json.loads(preparada.solicitud.solicitud.read_text(encoding="utf-8"))
        op = next(x for x in contenido["operaciones"] if x["metodo"] == "cDatabaseTables.GetAllFieldsInTable"
                  and x["argumentos"][0]["valor"] == o.TABLA_CASO_RS)
        op["argumentos"][0]["valor"] = CLAVE_INVENTADA_FALLIDA
        nuevo = json.dumps(contenido).encode("utf-8")
        preparada.solicitud.solicitud.write_bytes(nuevo)
        argv = preparada.solicitud.argv
        argv[argv.index("-Sha256Solicitud") + 1] = hashlib.sha256(nuevo).hexdigest()
        _, error = self.fallo((ejecutor, preparada))
        self.assertEqual((error.tipo, error.respuesta["error"]["codigo_api"]), ("precondicion", -96))
        self.assertIn("no existe", str(error))
        self.assertEqual(error.progreso["orden_fallida"], op["orden"])
        self.assertTrue(self.sin_mutaciones())
        self.assertFalse(error.incierto)

    def test_verificaciones_previas_sin_mutar(self):
        casos = {"campo ausente": ({"FALSO_SIN_CAMPO": "DampRatio"}, "DampRatio"),
                 "ConstDamp no importable": ({"FALSO_NO_IMPORTABLE": "ConstDamp"}, "importable"),
                 "texto no nombrado": ({"FALSO_DESCRIPCION_VACIA": "RigidResp"}, "no nombra 'No'"),
                 "función existente": ({"FALSO_NOMBRES_cFunction": "ESP-PRUEBA"}, "ESP-PRUEBA")}
        for nombre, (entorno, texto) in casos.items():
            with self.subTest(nombre):
                ejecutor, error = self.fallo(**entorno)
                self.assertEqual(error.tipo, "precondicion")
                self.assertIn(texto, str(error))
                self.assertTrue(self.sin_mutaciones())
                self.assertFalse(error.incierto)

    def test_advertencia_de_importacion_detiene_sin_llamadas_posteriores(self):
        ejecutor, error = self.fallo(FALSO_ADVERTENCIA="1")
        self.assertEqual(error.tipo, "api")
        self.assertIn("advertencias 1", str(error))
        metodos = [l["m"] for l in self.llamadas()]
        self.assertEqual(metodos[-1], "cDatabaseTables.ApplyEditedTables")
        self.assertNotIn("cCaseResponseSpectrum.SetCase", metodos)
        self.assertTrue(error.incierto)
        ejecutor.adaptador.confirmar_recuperacion(motor_inactivo_declarado=True, revisor_declarado="R", motivo="prueba")

    def test_efectos_no_aplicados_detectados_por_relectura(self):
        for metodo, lectura in (("cCaseResponseSpectrum.SetEccentricity", "cCaseResponseSpectrum.GetEccentricity"),
                                ("cCaseModalEigen.SetNumberModes", "cCaseModalEigen.GetNumberModes"),
                                ("cDatabaseTables.ApplyEditedTables", "cDatabaseTables.GetTableForEditingArray")):
            with self.subTest(metodo):
                ejecutor, error = self.fallo(FALSO_IGNORAR=metodo)
                self.assertEqual(error.tipo, "api")
                self.assertEqual(self.llamadas()[-1]["m"], lectura)
                self.assertTrue(error.incierto)
                ejecutor.adaptador.confirmar_recuperacion(motor_inactivo_declarado=True, revisor_declarado="R", motivo="prueba")


if __name__ == "__main__":
    unittest.main()
