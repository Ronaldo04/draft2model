"""Etapa 02 (ruta 201): cargas hidrostáticas OPCIONALES de extremo a extremo con configuración 0.5 real en disco.

Gestión real (geometría 0.3 aprobada, configuración importada/revisada/aprobada) → plan 0.5 regenerado entero →
ejecutor verificado con el script PowerShell REAL contra un ETABSv1 FALSO con estado de la tabla no uniforme
(campos, importables y descripciones de los metadatos reales 185) → registro. Los dobles NO prueban ETABS.
"""
import base64
import copy
import json
import math
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from draft2model import adaptador_etabs as ad
from draft2model import ejecutor_etabs as ej
from draft2model import gestion_configuracion as gc
from draft2model import liquidos_malla as lm
from draft2model import modelo_estructural as m
from draft2model import operaciones_etabs as o
from draft2model import revision_modelo as rm
from draft2model.ejecucion_modelo import EjecutorVerificado
from tests import test_acciones_liquidos as tal
from tests import test_ejecutor_etabs as te
from tests import test_gestion_geometria as disco
from tests import test_integracion_malla as tim

F = tim.F
REVISION = {"estado": "revisado", "declarada_por": "Prueba sintética", "fecha": "2026-10-21", "motivo": "Solo software."}


def declaracion(ident, nivel, hosts, gamma=10.0, origen=(0, 0, 0)):
    _, d, fuentes = tal.entradas(nivel=nivel)
    d.update(id=ident, peso_especifico_kn_m3=gamma, origen_momentos_m=list(origen),
             superficies=[{"superficie": h, "sentido_normal": s, "fuentes": ["F1"]} for h, s in hosts])
    return d, fuentes


class CasoLiquidos(tim.CasoMalla):
    def montar_liquidos(self, escenario, aplicabilidad, declaraciones=(), cortes=None, patrones=("HIDRO",)):
        data = self.montar(escenario)
        data["version_contrato"] = m.VERSION_LIQUIDOS
        if cortes is not None:
            data["cortes_nivel"] = [{"z_m": z, "fuente": F, "motivo": "Nivel libre declarado (sintético)."} for z in cortes]
        for p in patrones:
            data["patrones"].append({"id": p, "tipo": "otro", "multiplicador_peso_propio": 0, "fuente": F})
        data["liquidos"] = {"aplicabilidad": aplicabilidad, "fuente": F, "motivo": "Declaración sintética de recipientes.",
                            "declaraciones": [{"declaracion": d, "fuentes": f, "patron": p} for d, f, p in declaraciones]}
        return data

    def aprobar_en_disco(self, data):
        data = self.completar(data)
        imp = gc.importar(self.raiz, disco.CASO, self.f.escribir(data, "cfg05.json"))
        rev = gc.revisar(self.raiz, disco.CASO, imp["id"], data, **tim.REVISOR)
        return gc.aprobar(self.raiz, disco.CASO, rev["id"], huella_esperada=m.huella_configuracion(rev["configuracion"]),
                          alcance="Líquidos sintéticos de software; no ingeniería.", **tim.REVISOR)["configuracion"]

    def plan(self, config):
        return o.generar_plan_por_version(self.raiz, config, **self.opciones(config)).datos


class ConfiguracionYPlanLiquidosTests(CasoLiquidos):
    def test_sin_liquidos_funciona_sin_cargas_de_agua(self):
        # 0.4 sin módulo de agua sigue intacta; 0.5 con ausencia confirmada no crea filas ni patrones ficticios.
        _, _, c04 = self.registrar_aprobada("horizontal")
        p04 = self.plan(c04)
        self.assertEqual(p04["version_contrato"], "0.4.0"); self.assertNotIn("liquidos", p04)
        c05 = self.aprobar_en_disco(self.montar_liquidos("horizontal", "ausente_confirmado", patrones=()))
        p05 = self.plan(c05)
        self.assertEqual((p05["version_contrato"], p05["liquidos"]["aplicabilidad"], p05["liquidos"]["filas"]), ("0.5.0", "ausente_confirmado", []))
        self.assertNotIn("edicion_tabla", [x["metodo"] for x in p05["operaciones"]])
        self.assertEqual(o.validar_plan_por_version(p05), [])

    def test_informacion_insuficiente_no_es_ausencia(self):
        data = self.completar(self.montar_liquidos("horizontal", "informacion_insuficiente", patrones=()))
        r = m.validar_configuracion(self.aprobar_local(data), self.geo)
        self.assertTrue(r.consistente, r.errores)
        self.assertIn("$.liquidos.aplicabilidad", {f["ruta"] for f in r.faltantes})
        self.assertFalse(r.apto_para_adaptador)

    def test_muro_con_puerta_parcialmente_sumergido_conserva_fuerza_y_momento(self):
        d, f = declaracion("CISTERNA", 1.5, [("S1", 1)], origen=(0, 2, 1))
        c = self.aprobar_en_disco(self.montar_liquidos("vertical_corte", "presente", [(d, f, "HIDRO")]))
        p = self.plan(c)
        self.assertEqual(o.validar_plan_por_version(p), [])
        liq = p["liquidos"]
        self.assertEqual(liq["aplicabilidad"], "presente")
        host = liq["hosts"][0]
        self.assertEqual(host["aberturas_ids"], ["PUERTA"])
        self.assertLessEqual(host["error_relativo_max"], 1e-9)
        self.assertGreater(abs(host["fuerza_kn"][0]), 0)
        # Pieza seca conservada: triángulos por encima del nivel siguen en la malla y en la tabla (presión cero por restricción).
        self.assertEqual({r["UniqueName"] for r in liq["filas"]}, set(p["malla"]["hosts"]["S1"]["triangulos"]))
        ops = p["operaciones"]
        previa = next(i for i, x in enumerate(ops) if x["metodo"] == "cDatabaseTables.GetAllFieldsInTable")
        tabla = next(i for i, x in enumerate(ops) if x["metodo"] == "edicion_tabla")
        mutaciones = [i for i, x in enumerate(ops) if x["fase"] != "verificacion"]
        self.assertLess(previa, min(mutaciones)); self.assertLess(tabla, len(ops) - 1)
        self.assertEqual(ops[tabla]["tabla"], o.TABLA_NO_UNIFORME); self.assertEqual(ops[tabla]["modo"], "agregar")
        self.assertNotIn("Story", ops[tabla]["campos"]); self.assertNotIn("Label", ops[tabla]["campos"])
        self.assertNotIn("cStory.SetStories_2", [x["metodo"] for x in ops if x["fase"] not in ("pisos",)])

    def test_fondo_inclinado_y_dos_recipientes_sin_duplicar_patrones(self):
        casos = {
            "fondo": ("horizontal", [declaracion("FONDO", 3.6, [("S1", -1)])], None, ("HIDRO",)),
            "inclinado (componentes X y Z)": ("inclinado", [declaracion("RAMPA", 0.6, [("S1", 1)])], [0.6], ("HIDRO",)),
            "dos recipientes": ("conectados_corte", [declaracion("TANQUE", 3.0, [("S1", -1)]), declaracion("CISTERNA", 1.2, [("S2", 1)])], None, ("H1", "H2")),
        }
        for nombre, (esc, decls, cortes, patrones) in casos.items():
            with self.subTest(nombre):
                c = self.aprobar_en_disco(self.montar_liquidos(esc, "presente", [(d, f, p) for (d, f), p in zip(decls, patrones)], cortes, patrones))
                p = self.plan(c)
                self.assertEqual(o.validar_plan_por_version(p), [])
                filas = p["liquidos"]["filas"]
                self.assertEqual(sorted(p["liquidos"]["patrones"]), sorted(patrones))
                claves = [(r["UniqueName"], r["LoadPattern"], r["Dir"]) for r in filas]
                self.assertEqual(len(claves), len(set(claves)))
                if nombre.startswith("inclinado"):
                    self.assertEqual({r["Dir"] for r in filas}, {"Global-X", "Gravity"})
                for h in p["liquidos"]["hosts"]:
                    self.assertLessEqual(h["error_relativo_max"], 1e-9)

    def test_negativos_de_configuracion(self):
        d15, f15 = declaracion("CISTERNA", 1.5, [("S1", 1)])
        d10, f10 = declaracion("OTRA", 1.0, [("S1", 1)])
        casos = {
            "corte faltante": self.montar_liquidos("vertical_corte", "presente", [(d10, f10, "HIDRO")]),
            "patrón duplicado": self.montar_liquidos("vertical_corte", "presente", [(d15, f15, "HIDRO"), (d15, f15, "HIDRO")]),
            "superficie en dos declaraciones": self.montar_liquidos("vertical_corte", "presente", [(d15, f15, "H1"), (d15, f15, "H2")], patrones=("H1", "H2")),
            "ausente con declaraciones": self.montar_liquidos("vertical_corte", "ausente_confirmado", [(d15, f15, "HIDRO")]),
            "presente sin declaraciones": self.montar_liquidos("vertical_corte", "presente", []),
            "aplicabilidad desconocida": self.montar_liquidos("vertical_corte", "quizas", []),
        }
        con_peso = self.montar_liquidos("vertical_corte", "presente", [(d15, f15, "HIDRO")])
        next(x for x in con_peso["patrones"] if x["id"] == "HIDRO")["multiplicador_peso_propio"] = 1
        casos["patrón con peso propio"] = con_peso
        no_dedicado = self.montar_liquidos("vertical_corte", "presente", [(d15, f15, "HIDRO")])
        no_dedicado["cargas"][0]["patron"] = "HIDRO"
        casos["patrón no dedicado"] = no_dedicado
        fuente_mal = self.montar_liquidos("vertical_corte", "presente", [(d15, copy.deepcopy(f15), "HIDRO")])
        fuente_mal["liquidos"]["declaraciones"][0]["fuentes"][0]["revision"]["estado"] = "borrador"
        casos["fuente sin revisar"] = fuente_mal
        for nombre, data in casos.items():
            with self.subTest(nombre):
                r = m.validar_configuracion(self.aprobar_local(self.completar(data)), self.geo)
                self.assertFalse(r.consistente, nombre)
                self.assertFalse(r.apto_para_adaptador)

    def test_cambio_de_fuente_o_aprobacion_y_plan_rehecho_rechazados(self):
        d, f = declaracion("CISTERNA", 1.5, [("S1", 1)])
        c = self.aprobar_en_disco(self.montar_liquidos("vertical_corte", "presente", [(d, f, "HIDRO")]))
        p = self.plan(c)
        alterada = copy.deepcopy(c)
        alterada["liquidos"]["declaraciones"][0]["fuentes"][0]["contenido"]["gamma_kn_m3"] = 9.81
        self.assertFalse(m.comprobar_configuracion(self.raiz, alterada).apto_para_adaptador)  # huella aprobada no vigente
        with self.assertRaises(o.ErrorPlanRechazado):
            self.plan(alterada)
        manipulaciones = {
            "fila cambiada": lambda q: next(x for x in q["operaciones"] if x["metodo"] == "edicion_tabla")["registros"][0].update(D="0.0"),
            "fila extra": lambda q: next(x for x in q["operaciones"] if x["metodo"] == "edicion_tabla")["registros"].append(dict(q["liquidos"]["filas"][0], LoadPattern="OTRO")),
            "sin verificación previa": lambda q: q["operaciones"].remove(next(x for x in q["operaciones"] if x["metodo"] == "cDatabaseTables.GetAllFieldsInTable")),
            "conservación": lambda q: q["liquidos"]["hosts"][0].update(error_relativo_max=1e-3),
        }
        for nombre, cambio in manipulaciones.items():
            with self.subTest(nombre):
                q = copy.deepcopy(p); cambio(q)
                for i, x in enumerate(q["operaciones"], 1):
                    x["orden"] = i
                q["huella_plan"] = o.huella_plan(q)  # una huella rehecha no valida el plan
                self.assertTrue(o.validar_plan_por_version(q))

    def test_preparacion_pura_coincide_con_el_plan(self):
        d, f = declaracion("CISTERNA", 1.5, [("S1", 1)])
        c = self.aprobar_en_disco(self.montar_liquidos("vertical_corte", "presente", [(d, f, "HIDRO")]))
        p = self.plan(c)
        from draft2model import malla_preparacion as mp
        prep = mp.preparar_malla(self.geo, c)
        self.assertEqual(lm.preparar_liquidos(self.geo, c, prep), p["liquidos"])
        # Ningún triángulo cargado cruza el nivel libre.
        xyz = {n["csi"]: n["xyz_m"] for n in prep["nodos"]}
        for t in prep["triangulos"]:
            zs = [xyz[n][2] for n in t["nodos"]]
            self.assertFalse(min(zs) < 1.5 < max(zs))


LIQUIDO_CS = r"""
public static class Liquido {
  public const string T = "Area Load Assignments - Non-uniform";
  public static string[] C = new string[] { "Story", "Label", "UniqueName", "LoadPattern", "Dir", "A", "B", "C", "D", "Restriction", "GUID" };
  public static bool[] I = new bool[] { false, false, true, true, true, true, true, true, true, true, true };
  public static System.Collections.Generic.List<System.Collections.Generic.Dictionary<string, string>> Filas = Inicial();
  public static string[] PC; public static string[] PD;
  static System.Collections.Generic.List<System.Collections.Generic.Dictionary<string, string>> Inicial() {
    var l = new System.Collections.Generic.List<System.Collections.Generic.Dictionary<string, string>>();
    if (Falso.Env("FALSO_FILA_AJENA") != null) l.Add(Fila(Falso.Env("FALSO_FILA_AJENA"), "AJENO"));
    if (Falso.Env("FALSO_COLISION") != null) l.Add(Fila(Falso.Env("FALSO_COLISION"), "AJENO"));
    return l;
  }
  static System.Collections.Generic.Dictionary<string, string> Fila(string n, string p) {
    var f = new System.Collections.Generic.Dictionary<string, string>();
    foreach (string k in C) f[k] = "";
    f["Story"] = "Story1"; f["Label"] = "F1"; f["UniqueName"] = n; f["LoadPattern"] = p; f["Dir"] = "Gravity";
    f["A"] = "0"; f["B"] = "0"; f["C"] = "0"; f["D"] = "1"; f["Restriction"] = "Use All Values"; return f;
  }
  public static string Desc(string k) {
    if (k == "Dir") return "This is one of the following load directions: Local-1, Local-2, Local-3, Global-X, Global-Y, Gravity, Global-X Proj, Global-Y Proj, Gravity Proj.";
    if (k == "Restriction") return "This is one of the following load restrictions: Use All Values, Zero Negative Values, Zero Positive Values.";
    return "DOBLE";
  }
  public static void Aplicar() {
    if (PC == null) return;
    var nuevas = new System.Collections.Generic.List<System.Collections.Generic.Dictionary<string, string>>();
    int n = PC.Length; bool alterada = false;
    for (int r = 0; r * n < PD.Length; r++) {
      var f = new System.Collections.Generic.Dictionary<string, string>();
      foreach (string k in C) f[k] = "";
      for (int i = 0; i < n; i++) f[PC[i]] = PD[r * n + i];
      if (Falso.Env("FALSO_TABLA_MAL") == "1" && !alterada && f["LoadPattern"] != "AJENO") { f["D"] = "999"; alterada = true; }
      nuevas.Add(f);
    }
    Filas = nuevas; PC = null;
  }
}"""
CUERPOS_LIQUIDO = dict(tim.CUERPOS_MALLA)
CUERPOS_LIQUIDO.update({
    "cDatabaseTables.GetAllFieldsInTable": f"if (TableKey != Liquido.T) return {o.RETORNO_TABLA_INEXISTENTE_OBSERVADO}; "
                                           "TableVersion = 1; NumberFields = Liquido.C.Length; FieldKey = Liquido.C; FieldName = Liquido.C; "
                                           "Description = new string[Liquido.C.Length]; UnitsString = new string[Liquido.C.Length]; IsImportable = Liquido.I; "
                                           "for (int i = 0; i < Liquido.C.Length; i++) { Description[i] = Liquido.Desc(Liquido.C[i]); UnitsString[i] = \"\"; } "
                                           'return Falso.Retorno("cDatabaseTables.GetAllFieldsInTable", 0);',
    "cDatabaseTables.GetTableForEditingArray": f"if (TableKey != Liquido.T) return {o.RETORNO_TABLA_INEXISTENTE_OBSERVADO}; "
                                               "TableVersion = 1; FieldsKeysIncluded = Liquido.Filas.Count == 0 ? new string[0] : Liquido.C; "
                                               "NumberRecords = Liquido.Filas.Count; var datos = new System.Collections.Generic.List<string>(); "
                                               "foreach (var f in Liquido.Filas) foreach (string k in Liquido.C) datos.Add(f[k]); TableData = datos.ToArray(); return 0;",
    "cDatabaseTables.SetTableForEditingArray": "Liquido.PC = FieldsKeysIncluded; Liquido.PD = TableData; "
                                               'return Falso.Retorno("cDatabaseTables.SetTableForEditingArray", 0);',
    "cDatabaseTables.ApplyEditedTables": 'NumFatalErrors = 0; NumErrorMsgs = Falso.Env("FALSO_IMPORT_ERROR") == "1" ? 1 : 0; NumWarnMsgs = 0; NumInfoMsgs = 1; '
                                         'ImportLog = NumErrorMsgs > 0 ? "Error de importación simulado" : "Importación simulada"; '
                                         'if (NumErrorMsgs == 0) Liquido.Aplicar(); return Falso.Retorno("cDatabaseTables.ApplyEditedTables", 0);',
})


@unittest.skipUnless(tim.POWERSHELL, "requiere Windows PowerShell 5.1")
class EjecucionLiquidosDobleTests(CasoLiquidos):
    """Ejecutor verificado + script PowerShell REAL + ETABSv1 FALSO con estado de tabla. No es ETABS."""

    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory(dir=os.environ.get("TEMP"))
        carpeta = Path(cls._dir.name)
        cs, dll = carpeta / "ETABSv1_liquidos.cs", carpeta / "ETABSv1_liquidos.dll"
        cs.write_text(te.generar_cs(CUERPOS_LIQUIDO, tim.ESTADO_MALLA + LIQUIDO_CS), encoding="utf-8")
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
        self.copia = self.f.trabajo / "copia" / "plantilla.edb"
        self.copia.parent.mkdir()
        self.copia.write_bytes(te.CONTENIDO_COPIA)
        Path(self.destino).parent.mkdir()
        self.corridas = self.f.trabajo / "corridas"
        self.corridas.mkdir()
        d, f = declaracion("CISTERNA", 1.5, [("S1", 1)])
        self.config = self.aprobar_en_disco(self.montar_liquidos("vertical_corte", "presente", [(d, f, "HIDRO")]))
        self.datos_plan = self.plan(self.config)

    def ejecutor(self, **entorno):
        self.log = self.f.trabajo / f"llamadas_{len(list(self.f.trabajo.glob('llamadas_*')))}.jsonl"
        variables = {"FALSO_MODELO": str(self.copia), "FALSO_LOG": str(self.log), **entorno}
        return EjecutorVerificado(ej.configuracion_doble_powershell(self.corridas, self.dll, timeout_s=300, entorno=variables))

    def llamadas(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines() if l.strip()] if self.log.is_file() else []

    def test_recorrido_normal_guarda_y_registra_con_filas_ajenas_conservadas(self):
        ejecutor = self.ejecutor(FALSO_FILA_AJENA="OTRO_OBJETO")
        preparada = ejecutor.preparar(self.raiz, self.config, self.datos_plan, copia=self.copia, modelo_esperado=self.copia)
        ejecutor.ejecutar(preparada)
        metodos = [l["m"] for l in self.llamadas()]
        self.assertEqual(metodos[-1], "cFile.Save")
        escritura = next(l["a"] for l in self.llamadas() if l["m"] == "cDatabaseTables.SetTableForEditingArray")
        campos, filas = escritura[2], escritura[3]
        self.assertNotIn("Story", campos); self.assertNotIn("Label", campos)  # de solo lectura: no se reenvían
        self.assertEqual(filas, len(self.datos_plan["liquidos"]["filas"]) + 1)  # fila ajena conservada
        self.assertIn("OTRO_OBJETO", escritura[4])
        registro = rm.registrar(self.raiz, disco.CASO, self.config, self.datos_plan, preparada.carpeta)
        self.assertEqual(rm.consultar(self.raiz, disco.CASO, registro.name)["estado"], "pendiente")

    def test_colision_importacion_y_relectura_distinta_impiden_guardar(self):
        primero = self.datos_plan["liquidos"]["filas"][0]["UniqueName"]
        casos = {"colisión con carga ajena": {"FALSO_COLISION": primero}, "error de importación": {"FALSO_IMPORT_ERROR": "1"},
                 "tabla releída distinta": {"FALSO_TABLA_MAL": "1"}}
        for nombre, entorno in casos.items():
            with self.subTest(nombre):
                plan = self.datos_plan
                ejecutor = self.ejecutor(**entorno)
                preparada = ejecutor.preparar(self.raiz, self.config, plan, copia=self.copia, modelo_esperado=self.copia)
                try:
                    with self.assertRaises(ad.ErrorPuente):
                        ejecutor.ejecutar(preparada)
                finally:
                    if ejecutor.estado_incierto.exists():
                        ejecutor.estado_incierto.unlink()  # marca del doble
                metodos = [l["m"] for l in self.llamadas()]
                self.assertNotIn("cFile.Save", metodos)
                self.assertFalse(Path(self.destino).exists())


if __name__ == "__main__":
    unittest.main()
