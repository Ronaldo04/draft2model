"""Relectura independiente del EDB guardado con DOBLES; nunca abre ETABS real, no usa red ni instala.

- Comparación pura: expectativas desde planes sintéticos 0.1 y 0.2 aceptados por sus validadores.
- Transporte: un proceso Python doble publica respuestas válidas, truncadas o manipuladas.
- Script real: `verificar_modelo_guardado.ps1` en modo doble contra un ETABSv1 FALSO compilado aquí, que
  carga un «EDB» sintético persistido (JSON) al abrirlo: lo leído proviene del archivo reabierto, no de la
  memoria de construcción. Los dobles no acreditan ETABS ni su solver.
"""
import base64
import copy
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from draft2model import adaptador_etabs as ad
from draft2model import operaciones_etabs as o
from draft2model import verificacion_modelo_guardado as v
from tests import test_losas_aligeradas as tla
from tests import test_modelo_aberturas as tma
from tests import test_operaciones_dinamicas as tod
from tests import test_operaciones_etabs as toe
from tests import test_operaciones_superficies as tos

POWERSHELL = ad.POWERSHELL_51.is_file() and os.name == "nt"
CRITERIOS = {"relativo": 1e-12, "absolutos": {m: 1e-12 for m in v.MAGNITUDES}}
FIRMAS_LECTOR = 61
CODIGO_CASO = {"LinearStatic": 1, "Modal": 3, "ResponseSpectrum": 4}
G_SINTETICA = 9.80665


def modelo_desde_expectativa(exp):
    """«EDB» sintético persistido con exactamente lo esperado y extras de plantilla no referenciados."""
    p = exp["pisos"]
    elevaciones, z = [], p["base"]
    for h in p["alturas"]:
        z += h
        elevaciones.append(z)
    areas, frames, puntos = exp["areas"], exp["frames"], exp["puntos"]
    pa = exp["propiedades_area"]
    return {
        "version": "21.1.0",
        "pisos": {"base": p["base"], "nombres": list(p["nombres"]), "elevaciones": elevaciones, "alturas": list(p["alturas"])},
        "puntos": {"nombres": list(puntos), "coordenadas": copy.deepcopy(puntos)},
        "frames": {"nombres": list(frames), "puntos": {n: f["puntos"] for n, f in frames.items()},
                   "secciones": {n: f["seccion"] for n, f in frames.items()}},
        "areas": {"nombres": list(areas), "puntos": {n: a["puntos"] for n, a in areas.items()},
                  "propiedades": {n: a["propiedad"] for n, a in areas.items()},
                  "ejes": {n: {"angulo_deg": exp["ejes_plan"].get(n, {}).get("angulo_deg", 0.0), "avanzado": False} for n in areas},
                  "aberturas": {n: exp["aberturas"].get(n, False) for n in areas}},
        "cargas_area": {n: [{k: c[k] for k in ("objeto", "patron", "csys", "dir", "valor")} for c in exp["cargas_area"] if c["objeto"] == n]
                        for n in areas},
        "cargas_punto": {n: [{k: c[k] for k in ("objeto", "patron", "csys", "valores")} for c in exp["cargas_punto"] if c["objeto"] == n]
                         for n in puntos},
        "cargas_frame": {n: [{k: c[k] for k in ("objeto", "patron", "tipo", "csys", "dir", "rd1", "rd2", "val1", "val2")}
                             for c in exp["cargas_frame"] if c["objeto"] == n] for n in frames},
        "materiales": {"nombres": list(exp["materiales"]) + ["4000Psi"],
                       "detalle": {n: {"tipo": m["tipo"], "E": m["E"], "U": m["U"], "A": m["A"], "G": m["E"] / (2 * (1 + m["U"])),
                                       "W": m["W"], "M": m["W"] / G_SINTETICA} for n, m in exp["materiales"].items()}},
        "propiedades_area": {"nombres": list(pa) + ["Slab1"],
                             "losas": {n: {k: x[k] for k in ("subtipo", "shell", "material", "espesor")} for n, x in pa.items() if x["clase"] == "losa"},
                             "muros": {n: {k: x[k] for k in ("subtipo", "shell", "material", "espesor")} for n, x in pa.items() if x["clase"] == "muro"},
                             "nervadas": {n: dict(x["aligerado"]["parametros"]) for n, x in pa.items()
                                          if x.get("aligerado", {}).get("tipo") == "nervada"},
                             "casetonadas": {n: dict(x["aligerado"]["parametros"]) for n, x in pa.items()
                                             if x.get("aligerado", {}).get("tipo") == "casetonada"}},
        "propiedades_frame": {"nombres": list(exp["propiedades_frame"]) + ["FSEC1"],
                              "rectangulos": copy.deepcopy(exp["propiedades_frame"])},
        "fuente_masa": {"incluir_elementos": exp["fuente_masa"]["incluir_elementos"],
                        "incluir_masa_adicional": exp["fuente_masa"]["incluir_masa_adicional"],
                        "incluir_cargas": exp["fuente_masa"]["incluir_cargas"],
                        "patrones": list(exp["fuente_masa"]["factores"]), "factores": list(exp["fuente_masa"]["factores"].values())},
        **configuracion_desde_expectativa(exp),
    }


def configuracion_desde_expectativa(exp):
    """Apoyos, diafragmas, patrones, casos, combinaciones, funciones, tablas y marcas; con extras de plantilla."""
    casos = exp["casos"]
    tablas = {}
    for tabla, t_ in exp["tablas"].items():
        filas, vistos = [], set()
        for r in t_["registros"]:
            fila = {k: r[k] for k in t_["campos"]}
            if tabla == "Functions - Response Spectrum - User Defined":
                fila["DampRatio"] = r["DampRatio"] if r["Name"] not in vistos else ""  # agrupado como en ETABS 21.1
                vistos.add(r["Name"])
            filas.append(dict(fila, GUID=""))
        tablas[tabla] = {"campos": list(t_["campos"]) + ["GUID"], "filas": filas}
    return {
        "apoyos": {n: list(exp["apoyos"].get(n, [False] * 6)) for n in exp["puntos"]},
        "diafragmas_puntos": copy.deepcopy(exp["diafragmas_puntos"]),
        "diafragmas_areas": {n: "" for n in exp["areas"]},
        "diafragmas": {"nombres": list(exp["diafragmas"]) + ["D1"], "semirrigido": dict(exp["diafragmas"])},
        "patrones": {"nombres": list(exp["patrones"]) + ["Dead"], "detalle": copy.deepcopy(exp["patrones"])},
        "casos": {"nombres": list(casos) + ["Modal"],
                  "tipos": {**{n: {"tipo": {"nombre": c["tipo"], "valor": CODIGO_CASO[c["tipo"]]}, "subtipo": 0} for n, c in casos.items()},
                            "Modal": {"tipo": {"nombre": "Modal", "valor": 3}, "subtipo": 0}},
                  "estaticos": {n: copy.deepcopy(c["cargas"]) for n, c in casos.items() if c["tipo"] == "LinearStatic"},
                  "modales": {n: {"modos": list(c["modos"]), "desplazamiento": c["parametros"]["desplazamiento"],
                                  "corte": c["parametros"]["corte"], "tolerancia": c["parametros"]["tolerancia"],
                                  "automatico": c["parametros"]["automatico"], "numero_cargas": c["numero_cargas"]}
                              for n, c in casos.items() if c["tipo"] == "Modal"},
                  "espectrales": {n: {"modal": c["modal"], "cargas": copy.deepcopy(c["cargas"]), "excentricidad": c["excentricidad"],
                                      "amortiguamiento": c["amortiguamiento"], "tipo_amortiguamiento": 1,
                                      "comb_modal": {"tipo": 1, "f1": 1.0, "f2": 0.0, "periodica_rigida": 1, "td": 60.0}}
                                  for n, c in casos.items() if c["tipo"] == "ResponseSpectrum"}},
        "combinaciones": {"nombres": list(exp["combinaciones"]), "detalle": copy.deepcopy(exp["combinaciones"])},
        "funciones": {"nombres": list(exp["funciones"]) + ["UNIFTH"],
                      "valores": {n: {"numero": len(f["periodos"]), "tiempos": [0.0] + f["periodos"], "valores": [0.0] + f["valores"]}
                                  for n, f in exp["funciones"].items()}},  # centinela (0,0) observado en ETABS 21.1
        "tablas": tablas,
        "ejecucion": {"casos": list(casos) + ["Modal"], "ejecutar": [n in exp["ejecucion"]["ejecutar"] for n in casos] + [False]},
    }


def lecturas(modelo, retornos=(), unidades="kN_m_C"):
    d = {k: copy.deepcopy(modelo[k]) for k in modelo if k != "version"}
    d.update(unidades=unidades, version_etabs=modelo["version"], retornos_no_cero=list(retornos))
    return d


def a_n_mm(modelo, f_longitud=1000):
    """Reexpresa el EDB sintético kN_m_C en N_mm_C con factores escritos AQUÍ, independientes del módulo.

    1 m = 1000 mm; 1 kN = 1000 N; kN/m2 = 1e-3 N/mm2; kN/m3 = 1e-6 N/mm3; kN/m = 1 N/mm; kN·m = 1e6 N·mm.
    `f_longitud` distinto de 1000 simula un factor erróneo (p. ej. valores en cm declarados como mm).
    """
    m = copy.deepcopy(modelo)
    L, F = f_longitud, 1000
    m["pisos"]["base"] *= L
    m["pisos"]["elevaciones"] = [x * L for x in m["pisos"]["elevaciones"]]
    m["pisos"]["alturas"] = [x * L for x in m["pisos"]["alturas"]]
    m["puntos"]["coordenadas"] = {n: [x * L for x in c] for n, c in m["puntos"]["coordenadas"].items()}
    for items in m["cargas_area"].values():
        for c in items:
            c["valor"] *= F / L ** 2
    for items in m["cargas_punto"].values():
        for c in items:
            c["valores"] = [x * F for x in c["valores"][:3]] + [x * F * L for x in c["valores"][3:]]
    for items in m["cargas_frame"].values():
        for c in items:
            c["val1"] *= F / L
            c["val2"] *= F / L
    for d in m["materiales"]["detalle"].values():
        d["E"] *= F / L ** 2
        d["G"] *= F / L ** 2
        d["W"] *= F / L ** 3
        d["M"] *= F / L ** 4
    for clase in ("losas", "muros"):
        for d in m["propiedades_area"][clase].values():
            d["espesor"] *= L
    for clase in ("nervadas", "casetonadas"):
        for d in m["propiedades_area"][clase].values():
            for k in d:
                if k != "RibsParallelTo":
                    d[k] *= L
    for d in m["propiedades_frame"]["rectangulos"].values():
        d["t3"] *= L
        d["t2"] *= L
    for d in m["casos"]["espectrales"].values():
        for c in d["cargas"]:
            c["factor"] *= L  # aceleración m/s2 -> mm/s2, confirmada por ensayo real180 y dimensión CSI
    return m


class Planes:
    """Planes sintéticos aceptados: 0.1 estático (muros/frames) y 0.2 de desarrollo (superficies)."""

    def plan01(self):
        h = toe.PlanBase("setUp")
        h.setUp()
        try:
            return h.plan().datos  # el plan es solo dato; expediente temporal y dobles se liberan enseguida
        finally:
            h.doCleanups()

    def plan_dinamico(self):
        h = tod.DinamicaBase("setUp")
        h.setUp()
        try:
            return h.plan(h.aprobar_config()).datos
        finally:
            h.doCleanups()

    def plan_aligerado(self, tipo):
        """Plan 0.2 del compilador losas_aligeradas: LOSA20 nervada/casetonada (30°), S2 maciza."""
        h = tos.PlanSuperficiesBase("setUp")
        h.setUp()
        try:
            data = copy.deepcopy(h.data)
            tla.configurar(data, tipo)
            return h.plan(h.aprobar_config(data)).datos
        finally:
            h.doCleanups()

    def plan_aberturas(self, orientacion="horizontal"):
        """Plan 0.3 del compilador en revisión (solo lectura de su API): host S1 y HUECO1 con propiedad None."""
        h = tma.CasoAberturas("setUp")
        h.setUp()
        try:
            h.montar(orientacion)
            return o.generar_plan_aberturas(h.raiz, h.data, destino_guardado=str(h.f.trabajo / "salida" / "modelo.edb"),
                                            gravedad_programa_m_s2=9.80665,
                                            **({"tipo_shell_muro": "ShellThin"} if orientacion == "vertical" else {"tipo_shell_losa": "ShellThin"})).datos
        finally:
            h.doCleanups()

    def plan02(self):
        h = tos.PlanSuperficiesBase("setUp")
        h.setUp()
        try:
            return h.plan().datos  # el plan es solo dato; expediente temporal y dobles se liberan enseguida
        finally:
            h.doCleanups()


class ComparacionPuraTests(Planes, unittest.TestCase):
    def test_expectativas_de_ambos_planes_y_verificado_exacto(self):
        for nombre, plan in (("0.1", self.plan01()), ("0.2", self.plan02())):
            with self.subTest(nombre):
                antes = copy.deepcopy(plan)
                exp = v.expectativa_desde_plan(plan)
                self.assertEqual(plan, antes)
                self.assertEqual(exp["origen_plan"]["huella_plan"], plan["huella_plan"])
                r = v.comparar(exp, lecturas(modelo_desde_expectativa(exp)), CRITERIOS)
                self.assertEqual(r["estado"], "verificado", r["discrepancias"] + r["incompletos"])
                self.assertEqual(r["cobertura"]["ejes_locales_area"], "sin_criterio")
                self.assertIn("ejes_locales_area", r["controles_no_afirmados"])
                self.assertFalse(r["aprueba_modelo"])
        exp = v.expectativa_desde_plan(self.plan02())
        self.assertEqual(exp["areas"]["S1"]["puntos"], ["A1", "B1", "C1", "D1"])
        self.assertEqual(exp["cargas_area"][0]["valor"], -2)
        self.assertEqual(exp["propiedades_area"]["LOSA20"]["subtipo"], {"nombre": "Slab", "valor": 0})

    def test_plan_no_validado_o_reetiquetado_no_es_fuente(self):
        plan = self.plan01()
        for cambio in (lambda d: d.update(version_contrato="0.2.0"), lambda d: d.update(version_contrato="9"),
                       lambda d: d["operaciones"][3].update(fase="x")):
            datos = copy.deepcopy(plan)
            cambio(datos)
            with self.assertRaises(v.ErrorVerificacion):
                v.expectativa_desde_plan(datos)

    def test_criterios_explicitos_de_lectura(self):
        for malo in (None, {}, {"relativo": 1e-12}, {"relativo": 1e-3, "absolutos": CRITERIOS["absolutos"]},
                     {"relativo": 0, "absolutos": {"longitud_m": 0}},
                     {"relativo": 0, "absolutos": dict(CRITERIOS["absolutos"], longitud_m=0.01)}):
            with self.subTest(malo=malo), self.assertRaises(v.ErrorVerificacion):
                v.validar_criterios(malo)

    def test_discrepancias_incompletos_y_ejes(self):
        exp = v.expectativa_desde_plan(self.plan02())
        base = modelo_desde_expectativa(exp)

        def con(cambio, retornos=()):
            m = copy.deepcopy(base)
            cambio(m)
            return v.comparar(exp, lecturas(m, retornos), CRITERIOS)
        casos = {
            "coordenada": (lambda m: m["puntos"]["coordenadas"]["R3"].__setitem__(2, 1.3000001), "discrepancias", "Z"),
            "contorno invertido": (lambda m: m["areas"]["puntos"].__setitem__("S1", ["A1", "D1", "C1", "B1"]), "discrepancias", "contorno_ordenado"),
            "propiedad de área": (lambda m: m["areas"]["propiedades"].__setitem__("S2", "Slab1"), "discrepancias", "propiedad"),
            "espesor": (lambda m: m["propiedades_area"]["losas"]["LOSA20"].__setitem__("espesor", 0.25), "discrepancias", "espesor"),
            "shell": (lambda m: m["propiedades_area"]["losas"]["LOSA20"].__setitem__("shell", {"nombre": "ShellThick", "valor": 2}),
                      "discrepancias", "shell"),
            "carga valor": (lambda m: m["cargas_area"]["S1"][0].__setitem__("valor", -2.5), "discrepancias", "valor"),
            "carga extra": (lambda m: m["cargas_area"]["S2"].append({"objeto": "S2", "patron": "L", "csys": "Global", "dir": 6, "valor": -1}),
                            "discrepancias", "cantidad"),
            "carga faltante": (lambda m: m["cargas_area"].__setitem__("S1", []), "discrepancias", "cantidad"),
            "carga de otro objeto": (lambda m: m["cargas_area"]["S1"][0].__setitem__("objeto", "S2"), "discrepancias", "objeto"),
            "masa factor": (lambda m: m["fuente_masa"]["factores"].__setitem__(1, 0.3), "discrepancias", "factor"),
            "masa propia": (lambda m: m["fuente_masa"].__setitem__("incluir_elementos", True), "discrepancias", "incluir_elementos"),
            "objeto extra": (lambda m: (m["puntos"]["nombres"].append("X9"), m["puntos"]["coordenadas"].__setitem__("X9", [9, 9, 0]),
                                        m["cargas_punto"].__setitem__("X9", [])), "discrepancias", "existencia"),
            "objeto ausente": (lambda m: (m["areas"]["nombres"].remove("S2"), [m["areas"][k].pop("S2") for k in ("puntos", "propiedades", "ejes", "aberturas")],
                                          m["cargas_area"].pop("S2"), m["diafragmas_areas"].pop("S2")), "discrepancias", "existencia"),
            "material": (lambda m: m["materiales"]["detalle"]["MAT1"].__setitem__("E", 1000001), "discrepancias", "E"),
            "cargas duplicadas": (lambda m: m["cargas_area"]["S1"].append(dict(m["cargas_area"]["S1"][0])), "discrepancias", "cantidad"),
        }
        for nombre, (cambio, estado, campo) in casos.items():
            with self.subTest(nombre):
                r = con(cambio)
                self.assertEqual(r["estado"], estado)
                self.assertFalse(r["verificado"])
                self.assertIn(campo, [d["campo"].split(".")[-1] for d in r["discrepancias"]])
        r = con(lambda m: (m["cargas_area"].pop("S2")), [{"metodo": "cAreaObj.GetLoadUniform", "objeto": "S2", "codigo": 5}])
        self.assertEqual((r["estado"], r["cobertura"]["cargas_area"]), ("incompleto", "incompleta"))
        r = con(lambda m: m["propiedades_area"]["losas"].pop("LOSA20"),
                [{"metodo": "cPropArea.GetSlab", "objeto": "LOSA20", "codigo": 1}])
        self.assertEqual(r["estado"], "incompleto")
        # Ejes: con criterio explícito se comparan; sin él nunca se afirman.
        exp_ejes = v.expectativa_desde_plan(self.plan02(), ejes_locales_area={"S1": {"angulo_deg": 0.0, "avanzado": False}})
        r = v.comparar(exp_ejes, lecturas(base), CRITERIOS)
        self.assertEqual((r["estado"], r["ejes_sin_criterio"]), ("verificado", ["S2"]))
        m = copy.deepcopy(base)
        m["areas"]["ejes"]["S1"]["angulo_deg"] = 90.0
        self.assertEqual(v.comparar(exp_ejes, lecturas(m), CRITERIOS)["estado"], "discrepancias")
        with self.assertRaises(v.ErrorVerificacion):
            v.expectativa_desde_plan(self.plan02(), ejes_locales_area={"NOEXISTE": {"angulo_deg": 0, "avanzado": False}})

    def test_lectura_mal_formada_rechazada(self):
        exp = v.expectativa_desde_plan(self.plan02())
        base = lecturas(modelo_desde_expectativa(exp))
        for cambio in (lambda d: d.pop("fuente_masa"), lambda d: d["puntos"]["coordenadas"].__setitem__("R1", [0, 0]),
                       lambda d: d.__setitem__("unidades", "kN-m"), lambda d: d["cargas_area"].__setitem__("NO", []),
                       lambda d: d["retornos_no_cero"].append({"metodo": "x", "objeto": "y", "codigo": 0}),
                       lambda d: d["propiedades_area"]["losas"].__setitem__("OTRA", d["propiedades_area"]["losas"]["LOSA20"])):
            d = copy.deepcopy(base)
            cambio(d)
            with self.assertRaises(ad.ErrorEvidenciaEtabs):
                v.comparar(exp, d, CRITERIOS)


def _fila(tabla, nombre, campo):
    return lambda m: next(f for f in m["tablas"][tabla]["filas"] if f["Name"] == nombre and f[campo] != "").__setitem__


class CoberturaConfiguracionTests(Planes, unittest.TestCase):
    """Geometría idéntica y cada asignación o definición alterada: nunca verificado."""

    def setUp(self):
        self.plan = self.plan_dinamico()
        self.exp = v.expectativa_desde_plan(self.plan)
        self.base = modelo_desde_expectativa(self.exp)

    def comparar(self, cambio=None, retornos=()):
        m = copy.deepcopy(self.base)
        if cambio:
            cambio(m)
        return v.comparar(self.exp, lecturas(m, retornos), CRITERIOS)

    def test_plan_dinamico_verificado_con_inventario_completo(self):
        r = self.comparar()
        self.assertEqual(r["estado"], "verificado", r["discrepancias"] + r["incompletos"])
        self.assertTrue(r["verificacion_global_del_plan"])
        cp = r["cobertura_plan"]
        self.assertEqual(cp["sin_lector"], [])
        self.assertEqual(cp["operaciones"], len(self.plan["operaciones"]))
        self.assertEqual({x["metodo"] for x in cp["excluidas"]} - {"cFile.Save"},
                         {op["metodo"] for op in self.plan["operaciones"] if o.es_lectura(op["metodo"])})
        self.assertEqual(cp["comprobadas"] + len(cp["excluidas"]), cp["operaciones"])
        for categoria in ("apoyos", "diafragmas", "patrones", "casos", "combinaciones", "funciones_espectrales",
                          "tablas_dinamicas", "marcas_de_ejecucion"):
            self.assertEqual(r["cobertura"][categoria], "completa", categoria)
        self.assertIn("diafragma_de_area", r["controles_no_afirmados"])
        consulta = v.consulta_desde_expectativa(self.exp)
        self.assertNotIn("0.05", json.dumps(consulta))  # solo nombres, ningún valor esperado

    def test_cada_asignacion_alterada_es_discrepancia(self):
        tf, tc, td = o.TABLA_FUNCION_RS, o.TABLA_CASO_RS, o.TABLA_AMORTIGUAMIENTO_MODAL
        ex = lambda m: m["casos"]["espectrales"]["EX"]
        casos = {
            "apoyo liberado": (lambda m: m["apoyos"]["A0"].__setitem__(0, False), "restricciones"),
            "apoyo añadido": (lambda m: m["apoyos"].__setitem__("B1", [True] * 6), "restricciones"),
            "diafragma de punto": (lambda m: m["diafragmas_puntos"].__setitem__("A1", {"opcion": {"nombre": "Disconnect", "valor": 1},
                                                                                    "diafragma": ""}), "opcion"),
            "diafragma semirrígido": (lambda m: m["diafragmas"]["semirrigido"].__setitem__("DIA1", True), "semirrigido"),
            "diafragma ausente": (lambda m: (m["diafragmas"]["nombres"].remove("DIA1"), m["diafragmas"]["semirrigido"].pop("DIA1")),
                                  "existencia"),
            "tipo de patrón": (lambda m: m["patrones"]["detalle"]["L"].__setitem__("tipo", {"nombre": "Other", "valor": 8}), "tipo"),
            "peso propio": (lambda m: m["patrones"]["detalle"]["D"].__setitem__("multiplicador", 0), "multiplicador"),
            "tipo de caso": (lambda m: m["casos"]["tipos"]["EST"].__setitem__("tipo", {"nombre": "Modal", "valor": 3}), "tipo"),
            "factor estático": (lambda m: m["casos"]["estaticos"]["EST"][0].__setitem__("factor", 2), "factor"),
            "carga estática extra": (lambda m: m["casos"]["estaticos"]["EST"].append({"tipo_carga": "Load", "nombre": "Dead", "factor": 1}),
                                     "cantidad"),
            "modos": (lambda m: m["casos"]["modales"]["MOD"].__setitem__("modos", [4, 4]), "modos"),
            "tolerancia modal": (lambda m: m["casos"]["modales"]["MOD"].__setitem__("tolerancia", 1e-5), "tolerancia"),
            "factor espectral": (lambda m: ex(m)["cargas"][0].__setitem__("factor", 2), "factor"),
            "función espectral": (lambda m: ex(m)["cargas"][0].__setitem__("funcion", "UNIFTH"), "cantidad"),
            "caso modal del espectral": (lambda m: ex(m).__setitem__("modal", "Modal"), "modal"),
            "excentricidad": (lambda m: ex(m).__setitem__("excentricidad", 0.05), "excentricidad"),
            "amortiguamiento OAPI": (lambda m: ex(m).__setitem__("amortiguamiento", 0.02), "amortiguamiento"),
            "tipo de combinación": (lambda m: m["combinaciones"]["detalle"]["COMB1"].__setitem__("tipo", 1), "tipo"),
            "factor de combinación": (lambda m: m["combinaciones"]["detalle"]["COMB1"]["casos"][0].__setitem__("factor", 1.5), "factor"),
            "caso extra en combinación": (lambda m: m["combinaciones"]["detalle"]["COMB1"]["casos"].append(
                {"tipo": {"nombre": "LoadCase", "valor": 0}, "nombre": "MOD", "factor": 1}), "cantidad"),
            "valor de función": (lambda m: m["funciones"]["valores"]["ESP-PRUEBA"]["valores"].__setitem__(2, 0.2), "valor["),
            "periodo de función": (lambda m: m["funciones"]["valores"]["ESP-PRUEBA"]["tiempos"].__setitem__(3, 2.5), "periodo["),
            "combinación modal (tabla)": (lambda m: _fila(tc, "EX", "ModalCombo")(m)("ModalCombo", "SRSS"), "ModalCombo"),
            "respuesta rígida (tabla)": (lambda m: _fila(tc, "EX", "RigidResp")(m)("RigidResp", "Yes"), "RigidResp"),
            "amortiguamiento de función (tabla)": (lambda m: _fila(tf, "ESP-PRUEBA", "DampRatio")(m)("DampRatio", "0.07"), "DampRatio"),
            "amortiguamiento modal (tabla)": (lambda m: _fila(td, "EX", "ConstDamp")(m)("ConstDamp", "0.1"), "ConstDamp"),
            "caso no marcado": (lambda m: m["ejecucion"]["ejecutar"].__setitem__(m["ejecucion"]["casos"].index("MOD"), False), "ejecutar"),
            "plantilla marcada": (lambda m: m["ejecucion"]["ejecutar"].__setitem__(m["ejecucion"]["casos"].index("Modal"), True), "ejecutar"),
        }
        for nombre, (cambio, campo) in casos.items():
            with self.subTest(nombre):
                r = self.comparar(cambio)
                self.assertEqual(r["estado"], "discrepancias")
                self.assertFalse(r["verificado"] or r["verificacion_global_del_plan"])
                campos = [d["campo"] for d in r["discrepancias"]]
                self.assertTrue(any(c == campo or c.startswith(campo) or c.endswith("." + campo) for c in campos), campos)

    def test_lecturas_fallidas_o_repetidas_son_incompletas(self):
        tc = o.TABLA_CASO_RS
        casos = {
            "lista de casos de combinación": (lambda m: m["combinaciones"]["detalle"].pop("COMB1"), "cCombo.GetCaseList", "COMB1", "combinaciones"),
            "tabla de visualización": (lambda m: m["tablas"].pop(tc), "cDatabaseTables.GetTableForDisplayArray", tc, "tablas_dinamicas"),
            "marcas de ejecución": (lambda m: m.__setitem__("ejecucion", {"casos": [], "ejecutar": []}), "cAnalyze.GetRunCaseFlag", "*",
                                    "marcas_de_ejecucion"),
            "lista de patrones": (lambda m: m.__setitem__("patrones", {"nombres": [], "detalle": m["patrones"]["detalle"]}),
                                  "cLoadPatterns.GetNameList", "*", "patrones"),
            "restricciones": (lambda m: m["apoyos"].pop("A0"), "cPointObj.GetRestraint", "A0", "apoyos"),
            "parámetros modales": (lambda m: m["casos"]["modales"].pop("MOD"), "cCaseModalEigen.GetParameters", "MOD", "casos"),
        }
        for nombre, (cambio, metodo, objeto, categoria) in casos.items():
            with self.subTest(nombre):
                r = self.comparar(cambio, [{"metodo": metodo, "objeto": objeto, "codigo": 5}])
                self.assertEqual(r["estado"], "incompleto", r["discrepancias"])
                self.assertEqual(r["cobertura"][categoria], "incompleta")
        r = self.comparar(lambda m: m["combinaciones"]["detalle"]["COMB1"]["casos"].append(
            copy.deepcopy(m["combinaciones"]["detalle"]["COMB1"]["casos"][0])))
        self.assertEqual(r["estado"], "discrepancias")  # recuentos distintos con la misma clave
        exp2 = copy.deepcopy(self.exp)
        exp2["combinaciones"]["COMB1"]["casos"].append(copy.deepcopy(exp2["combinaciones"]["COMB1"]["casos"][0]))
        m = copy.deepcopy(self.base)
        m["combinaciones"]["detalle"]["COMB1"]["casos"] = copy.deepcopy(exp2["combinaciones"]["COMB1"]["casos"])
        r = v.comparar(exp2, lecturas(m), CRITERIOS)
        self.assertEqual(r["estado"], "incompleto")  # duplicados emparejables solo por orden: no se eligen filas

    def test_metodo_sin_lector_impide_verificacion_global(self):
        inventario = dict(v.INVENTARIO)
        del inventario["cCombo.SetCaseList"]
        original = v.INVENTARIO
        v.INVENTARIO = inventario
        try:
            exp = v.expectativa_desde_plan(self.plan)
        finally:
            v.INVENTARIO = original
        r = v.comparar(exp, lecturas(self.base), CRITERIOS)
        self.assertEqual(r["estado"], "incompleto")
        self.assertFalse(r["verificacion_global_del_plan"])
        self.assertEqual({x["metodo"] for x in r["cobertura_plan"]["sin_lector"]}, {"cCombo.SetCaseList"})


class AligeradosTests(Planes, unittest.TestCase):
    """Propiedades nervadas/casetonadas y orientación del plan; sin equivalencia maciza."""

    def setUp(self):
        self.planes = {"nervada": self.plan_aligerado("shell_losa_nervada_v1"),
                       "casetonada": self.plan_aligerado("shell_losa_casetonada_v1")}

    def test_espesor_capa_contra_getters_reales_etabs21(self):
        # Lectura NATIVA181 guardada: el doble que derivaba todo de la expectativa ocultaba el error.
        native=json.loads((Path(__file__).parent/'fixtures'/'aligerados_etabs21_181.json').read_bytes())
        for tipo,nombre,clase in (('nervada','Ribbed','nervadas'),('casetonada','Waffle','casetonadas')):
            exp=v.expectativa_desde_plan(self.planes[tipo]);modelo=modelo_desde_expectativa(exp)
            self.assertEqual(exp['propiedades_area']['LOSA20']['espesor'],.05)
            values=native['reapertura'][nombre]
            modelo['propiedades_area']['losas']['LOSA20']['espesor']=values['slab']['Thickness']/1000
            modelo['propiedades_area'][clase]['LOSA20']={k:(x if k=='RibsParallelTo' else x/1000) for k,x in values['parametros'].items()}
            r=v.comparar(exp,lecturas(modelo),CRITERIOS)
            self.assertEqual(r['estado'],'verificado',r['discrepancias']+r['incompletos'])
            modelo['propiedades_area']['losas']['LOSA20']['espesor']=.25
            self.assertEqual(v.comparar(exp,lecturas(modelo),CRITERIOS)['estado'],'discrepancias')

    def caso(self, tipo, cambio=None, retornos=(), **kw):
        exp = v.expectativa_desde_plan(self.planes[tipo], **kw)
        m = modelo_desde_expectativa(exp)
        if cambio:
            cambio(m)
        return exp, v.comparar(exp, lecturas(m, retornos), CRITERIOS)

    def test_aligerados_verificados_con_orientacion_obligatoria_del_plan(self):
        for tipo, subtipo in (("nervada", {"nombre": "Ribbed", "valor": 3}), ("casetonada", {"nombre": "Waffle", "valor": 4})):
            with self.subTest(tipo):
                exp, r = self.caso(tipo)
                self.assertEqual(r["estado"], "verificado", r["discrepancias"] + r["incompletos"])
                self.assertTrue(r["verificacion_global_del_plan"])
                losa = exp["propiedades_area"]["LOSA20"]
                self.assertEqual((losa["subtipo"], losa["aligerado"]["tipo"]), (subtipo, tipo))
                self.assertEqual(losa["espesor"], 0.05)  # GetSlab devuelve capa; OverallDepth se compara por separado
                self.assertEqual(exp["ejes_plan"], {"S1": {"angulo_deg": 30, "avanzado": False}})
                self.assertEqual(r["ejes_origen"], {"S1": "plan"})
                self.assertEqual(r["ejes_sin_criterio"], ["S2"])  # S2 maciza: la normal no es eje declarado
                self.assertEqual(r["cobertura"]["ejes_locales_area"], "sin_criterio")
                self.assertEqual(exp["propiedades_area"]["MACIZA"]["subtipo"]["nombre"], "Slab")
                metodos = {x["metodo"] for x in exp["inventario"] if x["cobertura"] == "comprobada"}
                self.assertTrue({"cPropArea.SetSlab" + ("Ribbed" if tipo == "nervada" else "Waffle"), "cAreaObj.SetLocalAxes"} <= metodos)
                self.assertEqual(v.INVENTARIO["cAreaObj.SetOpening"], "aberturas")  # lector 0.4.0: GetOpening real (ver AberturasTests)

    def test_cada_parametro_tipo_material_y_eje_alterado(self):
        for tipo in ("nervada", "casetonada"):
            parametros = list(v.PARAMETROS_ALIGERADO[tipo])
            clase = tipo + "s"
            casos = {k: (lambda m, k=k: m["propiedades_area"][clase]["LOSA20"].__setitem__(
                k, 2 if k == "RibsParallelTo" else m["propiedades_area"][clase]["LOSA20"][k] + 0.01), k) for k in parametros}
            casos.update({
                "subtipo macizo": (lambda m: m["propiedades_area"]["losas"]["LOSA20"].__setitem__("subtipo", {"nombre": "Slab", "valor": 0}), "subtipo"),
                "espesor": (lambda m: m["propiedades_area"]["losas"]["LOSA20"].__setitem__("espesor", 0.2), "espesor"),
                "material": (lambda m: m["propiedades_area"]["losas"]["LOSA20"].__setitem__("material", "4000Psi"), "material"),
                "ángulo local": (lambda m: m["areas"]["ejes"]["S1"].__setitem__("angulo_deg", 0.0), "eje_local_angulo"),
                "ángulo 30-360": (lambda m: m["areas"]["ejes"]["S1"].__setitem__("angulo_deg", -330.0), "eje_local_angulo"),
                "ejes avanzados": (lambda m: m["areas"]["ejes"]["S1"].__setitem__("avanzado", True), "eje_local_avanzado"),
                "propiedad maciza en el área": (lambda m: m["areas"]["propiedades"].__setitem__("S1", "MACIZA"), "propiedad"),
            })
            for nombre, (cambio, campo) in casos.items():
                with self.subTest(tipo=tipo, caso=nombre):
                    _, r = self.caso(tipo, cambio)
                    self.assertEqual(r["estado"], "discrepancias")
                    self.assertIn(campo, [d["campo"] for d in r["discrepancias"]])

    def test_lectura_fallida_parametro_faltante_y_criterio_contrario(self):
        _, r = self.caso("casetonada", lambda m: m["propiedades_area"]["casetonadas"].pop("LOSA20"),
                         [{"metodo": "cPropArea.GetSlabWaffle", "objeto": "LOSA20", "codigo": 1}])
        self.assertEqual((r["estado"], r["cobertura"]["propiedades_area"]), ("incompleto", "incompleta"))
        _, r = self.caso("nervada", lambda m: m["areas"]["ejes"].pop("S1"), [{"metodo": "cAreaObj.GetLocalAxes", "objeto": "S1", "codigo": 1}])
        self.assertEqual(r["estado"], "incompleto")
        with self.assertRaises(ad.ErrorEvidenciaEtabs):  # lectura sin un parámetro: esquema inválido
            self.caso("nervada", lambda m: m["propiedades_area"]["nervadas"]["LOSA20"].pop("RibSpacing"))
        with self.assertRaises(v.ErrorVerificacion):  # el solicitante no sustituye la orientación del plan
            v.expectativa_desde_plan(self.planes["nervada"], ejes_locales_area={"S1": {"angulo_deg": 0.0, "avanzado": False}})
        exp = v.expectativa_desde_plan(self.planes["nervada"], ejes_locales_area={"S1": {"angulo_deg": 30, "avanzado": False},
                                                                                  "S2": {"angulo_deg": 0.0, "avanzado": False}})
        self.assertEqual(exp["ejes_origen"], {"S1": "plan", "S2": "solicitante"})
        r = v.comparar(exp, lecturas(modelo_desde_expectativa(exp)), CRITERIOS)
        self.assertEqual((r["estado"], r["ejes_sin_criterio"], r["cobertura"]["ejes_locales_area"]), ("verificado", [], "completa"))

    def test_plan_aligerado_incoherente_o_sin_lector(self):
        plan = copy.deepcopy(self.planes["nervada"])
        indice = next(i for i, x in enumerate(plan["operaciones"]) if x["metodo"] == "cPropArea.SetSlabRibbed")
        del plan["operaciones"][indice]
        for i, x in enumerate(plan["operaciones"], 1):
            x["orden"] = i
        plan["huella_plan"] = o.huella_plan(plan)
        with self.assertRaises(v.ErrorVerificacion):  # Ribbed sin parámetros: no se supone losa maciza
            v.expectativa_desde_plan(plan)
        inventario = dict(v.INVENTARIO)
        del inventario["cPropArea.SetSlabRibbed"]
        original, v.INVENTARIO = v.INVENTARIO, inventario
        try:
            exp = v.expectativa_desde_plan(self.planes["nervada"])
        finally:
            v.INVENTARIO = original
        r = v.comparar(exp, lecturas(modelo_desde_expectativa(exp)), CRITERIOS)
        self.assertEqual(r["estado"], "incompleto")
        self.assertFalse(r["verificacion_global_del_plan"])


class UnidadesTests(Planes, unittest.TestCase):
    """EDB reabierto en N_mm_C (bloqueo real observado en tmp/d4): normalización dimensional explícita."""

    def setUp(self):
        self.exp02 = v.expectativa_desde_plan(self.plan02())
        self.base02 = modelo_desde_expectativa(self.exp02)

    def test_equivalencia_fisica_n_mm_c(self):
        r = v.comparar(self.exp02, lecturas(a_n_mm(self.base02), unidades="N_mm_C"), CRITERIOS)
        self.assertEqual(r["estado"], "verificado", r["discrepancias"] + r["incompletos"])
        u = r["unidades"]
        self.assertEqual((u["leidas"], u["plan"], u["normalizacion"]), ("N_mm_C", "kN_m_C", "dimensional"))
        self.assertEqual(u["factores"]["longitud_m"], "1/1000")
        self.assertEqual(u["factores"]["presion_kN_m2"], "1000/1")
        self.assertEqual(u["factores"]["peso_kN_m3"], "1000000/1")
        self.assertEqual(u["factores"]["fuerza_lineal_kN_m"], "1/1")
        self.assertGreater(u["valores_normalizados"], 20)
        self.assertNotIn("aceleracion_m_s2", u["no_comparables"])
        self.assertEqual(u["factores"]["aceleracion_m_s2"], "1/1000")
        for unidades, factor in (("kN_mm_C", None), ("N_m_C", None), ("kN_cm_C", None)):
            with self.subTest(unidades):
                self.assertEqual(v.factores_unidades("kN_m_C", unidades)["normalizacion"], "dimensional")

    def test_factor_erroneo_unidad_no_admitida_y_lectura_parcial(self):
        r = v.comparar(self.exp02, lecturas(a_n_mm(self.base02, f_longitud=100), unidades="N_mm_C"), CRITERIOS)
        self.assertEqual(r["estado"], "discrepancias")  # valores en cm declarados como mm
        self.assertIn("Z", {d["campo"] for d in r["discrepancias"]})
        r = v.comparar(self.exp02, lecturas(self.base02, unidades="N_mm_C"), CRITERIOS)
        self.assertEqual(r["estado"], "discrepancias")  # valores kN_m_C sin reexpresar pero declarados N_mm_C
        r = v.comparar(self.exp02, lecturas(self.base02, unidades="kip_in_F"), CRITERIOS)
        self.assertEqual((r["estado"], r["unidades"]["normalizacion"], r["cobertura"]["unidades"]), ("incompleto", "no_admitida", "incompleta"))
        self.assertEqual(r["cobertura"]["puntos"], "incompleta")  # ninguna magnitud dimensional se certifica
        self.assertFalse(r["verificacion_global_del_plan"])
        r = v.comparar(self.exp02, lecturas(a_n_mm(self.base02), [{"metodo": "cAreaObj.GetLoadUniform", "objeto": "S1", "codigo": 3}],
                                          unidades="N_mm_C"), CRITERIOS)
        self.assertEqual((r["estado"], r["cobertura"]["cargas_area"]), ("incompleto", "incompleta"))

    def test_aceleracion_espectral_conversion_dimensional_y_factor_incorrecto(self):
        exp = v.expectativa_desde_plan(self.plan_dinamico())
        r = v.comparar(exp, lecturas(a_n_mm(modelo_desde_expectativa(exp)), unidades="N_mm_C"), CRITERIOS)
        self.assertEqual(r["estado"], "verificado", r["discrepancias"]+r["incompletos"])
        mal=a_n_mm(modelo_desde_expectativa(exp))
        next(iter(mal['casos']['espectrales'].values()))['cargas'][0]['factor']/=1000
        r=v.comparar(exp,lecturas(mal,unidades='N_mm_C'),CRITERIOS)
        self.assertEqual(r['estado'],'discrepancias')
        self.assertEqual(v.comparar(exp, lecturas(modelo_desde_expectativa(exp)), CRITERIOS)["estado"], "verificado")


class AberturasTests(Planes, unittest.TestCase):
    """Plan 0.3: host (Opening False) y hueco (Opening True, propiedad None). Persistencia ≠ efecto físico."""

    def setUp(self):
        self.plan = self.plan_aberturas()
        self.exp = v.expectativa_desde_plan(self.plan)
        self.base = modelo_desde_expectativa(self.exp)

    def comparar(self, cambio=None, retornos=()):
        m = copy.deepcopy(self.base)
        if cambio:
            cambio(m)
        return v.comparar(self.exp, lecturas(m, retornos), CRITERIOS)

    def test_plan_03_verificado_sin_afirmar_efecto_estructural(self):
        self.assertEqual(self.exp["aberturas"], {"S1": False, "ABERTURA.HUECO1": True})
        self.assertEqual(self.exp["areas"]["ABERTURA.HUECO1"]["propiedad"], "None")
        r = self.comparar()
        self.assertEqual(r["estado"], "verificado", r["discrepancias"] + r["incompletos"])
        self.assertTrue(r["verificacion_global_del_plan"])
        self.assertIn(v.EFECTO_ABERTURAS, r["controles_no_afirmados"])
        self.assertIn("cAreaObj.SetOpening", {x["metodo"] for x in self.exp["inventario"] if x["cobertura"] == "comprobada"})
        self.assertEqual(r["cobertura"]["aberturas"], "completa")
        self.assertEqual([c["objeto"] for c in self.exp["cargas_area"]], ["S1"])  # ninguna carga inventada al hueco
        self.assertEqual(self.plan_aberturas("inclinado")["version_contrato"], "0.3.0")

    def test_alteraciones_de_hueco_y_host(self):
        h = "ABERTURA.HUECO1"
        casos = {
            "host marcado como hueco": (lambda m: m["areas"]["aberturas"].__setitem__("S1", True), "IsOpening"),
            "hueco no marcado": (lambda m: m["areas"]["aberturas"].__setitem__(h, False), "IsOpening"),
            "contorno del hueco": (lambda m: m["areas"]["puntos"][h].reverse(), "contorno_ordenado"),
            "sección inventada al hueco": (lambda m: m["areas"]["propiedades"].__setitem__(h, "LOSA20"), "propiedad"),
            "carga al hueco": (lambda m: m["cargas_area"][h].append({"objeto": h, "patron": "L", "csys": "Global", "dir": 6, "valor": -2}),
                               "cantidad"),
            "hueco ausente": (lambda m: (m["areas"]["nombres"].remove(h), [m["areas"][k].pop(h) for k in ("puntos", "propiedades", "ejes", "aberturas")],
                                         m["cargas_area"].pop(h), m["diafragmas_areas"].pop(h)), "existencia"),
        }
        for nombre, (cambio, campo) in casos.items():
            with self.subTest(nombre):
                r = self.comparar(cambio)
                self.assertEqual(r["estado"], "discrepancias")
                self.assertIn(campo, {d["campo"] for d in r["discrepancias"]})
        r = self.comparar(lambda m: m["areas"]["aberturas"].pop(h), [{"metodo": "cAreaObj.GetOpening", "objeto": h, "codigo": 1}])
        self.assertEqual((r["estado"], r["cobertura"]["aberturas"]), ("incompleto", "incompleta"))

    def test_setopening_sin_lector_impide_verificacion_global(self):
        inventario = dict(v.INVENTARIO)
        del inventario["cAreaObj.SetOpening"]
        original, v.INVENTARIO = v.INVENTARIO, inventario
        try:
            exp = v.expectativa_desde_plan(self.plan)
        finally:
            v.INVENTARIO = original
        r = v.comparar(exp, lecturas(self.base), CRITERIOS)
        self.assertEqual(r["estado"], "incompleto")
        self.assertFalse(r["verificacion_global_del_plan"])


@unittest.skipUnless(POWERSHELL, "requiere Windows PowerShell 5.1")
class DiagnosticoEntornoTests(Planes, unittest.TestCase):
    """Reproduce el fallo de la revisión 176 sin cambiar políticas: '-ExecutionPolicy Restricted' solo en el proceso hijo."""

    def test_directiva_restringida_diagnosticada_sin_respuesta(self):
        with tempfile.TemporaryDirectory() as d:
            d = Path(d)
            plan = self.plan02()
            edb = d / "modelo.edb"
            edb.write_bytes(json.dumps(modelo_desde_expectativa(v.expectativa_desde_plan(plan))).encode())
            (d / "trabajo").mkdir()
            comando = (str(ad.POWERSHELL_51), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Restricted", "-File", str(v.SCRIPT))
            config = ad.ConfiguracionPuente.doble(d / "trabajo", comando, timeout_s=120)
            ver = v.VerificadorModeloGuardado(config)
            prep = ver.preparar_verificacion(edb, v._sha(edb.read_bytes()), plan, criterios=CRITERIOS)
            with self.assertRaises(ad.ErrorPuente) as ctx:
                ver.ejecutar_verificacion(prep, confirmar_lectura=True)
            self.assertEqual((ctx.exception.tipo, ctx.exception.codigo_proceso), ("entorno", 1))
            self.assertIn("directiva_de_ejecucion_impide_file", str(ctx.exception))
            self.assertNotRegex(str(ctx.exception), r"[A-Za-z]:\\[^ ]*PROYECTO")  # sin rutas absolutas del proyecto
            evidencia = json.loads((prep.solicitud.carpeta / "verificacion_no_completada.json").read_text(encoding="utf-8"))
            self.assertEqual(evidencia["diagnostico_puente"]["causa"], "directiva_de_ejecucion_impide_file")
            self.assertFalse(prep.solicitud.respuesta.exists())
            self.assertTrue(ver.estado_incierto.exists())  # la marca de incertidumbre no se borra


DOBLE_PY = textwrap.dedent(r'''
    import json, os, sys
    a = sys.argv
    respuesta = a[a.index("-Respuesta") + 1]
    carpeta = os.path.dirname(respuesta)
    s = json.load(open(a[a.index("-Solicitud") + 1], encoding="utf-8"))
    modo = os.environ["DOBLE_MODO"]
    if modo == "truncada":
        open(respuesta, "w", encoding="utf-8").write('{"contrato": "draft2model.etabs_respuesta", "datos": {')
        sys.exit(0)
    lec = json.load(open(os.environ["DOBLE_LECTURAS"], encoding="utf-8"))
    datos = {"sha256_antes": s["sha256_edb"], "sha256_despues": s["sha256_edb"], "instancia": "doble", "id_proceso": None,
             "inicio_proceso_utc": None, "instancia_cerrada": True, "firmas_verificadas": 61, "version_dll": "1.29.0.0",
             "consulta": s["consulta"], "lecturas": lec, "guardado": False, "modificaciones": [], "version_lector": "0.4.0"}
    if modo == "lector_03": datos["version_lector"] = "0.3.0"
    if modo == "sha": datos["sha256_despues"] = "0" * 64
    if modo == "abierta": datos["instancia_cerrada"] = False
    if modo == "guardado": datos["guardado"] = True
    if modo == "consulta": datos["consulta"] = dict(s["consulta"], losas=[])
    if modo == "edb_cambia": open(os.environ["DOBLE_EDB"], "ab").write(b"x")
    r = {"contrato": "draft2model.etabs_respuesta", "version_contrato": "0.1.0", "id_solicitud": s["id"] if modo != "otro_id" else "f" * 32,
         "operacion": "verificar_modelo_guardado", "modo_ejecucion": "doble", "estado": "ok", "datos": datos, "avisos": ["doble"],
         "error": None}
    open(respuesta, "w", encoding="utf-8").write(json.dumps(r))
''')


class TransporteDobleTests(Planes, unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.plan = self.plan02()
        self.exp = v.expectativa_desde_plan(self.plan)
        self.edb = self.dir / "guardado" / "modelo.edb"
        self.edb.parent.mkdir()
        self.edb.write_bytes(json.dumps(modelo_desde_expectativa(self.exp)).encode())
        self.sha = v._sha(self.edb.read_bytes())
        (self.dir / "doble.py").write_text(DOBLE_PY, encoding="utf-8")
        self.lec = self.dir / "lecturas.json"
        self.lec.write_text(json.dumps(lecturas(modelo_desde_expectativa(self.exp))), encoding="utf-8")

    def verificador(self, modo):
        trabajo = self.dir / f"trabajo_{modo}"
        trabajo.mkdir()
        config = ad.ConfiguracionPuente.doble(trabajo, (sys.executable, str(self.dir / "doble.py")), timeout_s=60,
                                              entorno={"DOBLE_MODO": modo, "DOBLE_LECTURAS": str(self.lec), "DOBLE_EDB": str(self.edb)})
        return v.VerificadorModeloGuardado(config)

    def test_respuesta_valida_publica_resultado_ligado(self):
        ver = self.verificador("ok")
        prep = ver.preparar_verificacion(self.edb, self.sha, self.plan, criterios=CRITERIOS)
        self.assertNotIn("valor", json.dumps(prep.solicitud.contenido["consulta"]))  # sin valores esperados
        with self.assertRaises(ad.ErrorAdaptador):
            ver.ejecutar_verificacion(prep)  # confirmación explícita
        r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
        self.assertEqual((r.estado, r.verificado), ("verificado", True))
        publicado = v.cargar_resultado(r.corrida / "resultado_verificacion.json")
        self.assertEqual((publicado["sha256_edb"], publicado["origen_plan"]["huella_plan"]), (self.sha, self.plan["huella_plan"]))
        self.assertFalse(ver.estado_incierto.exists())
        self.assertEqual((prep.solicitud.carpeta / "modelo_lectura.edb").read_bytes(), self.edb.read_bytes())

    def test_respuestas_manipuladas_o_truncadas_no_verifican(self):
        for modo in ("truncada", "sha", "abierta", "guardado", "consulta", "otro_id", "edb_cambia", "lector_03"):
            with self.subTest(modo):
                ver = self.verificador(modo)
                prep = ver.preparar_verificacion(self.edb, self.sha, self.plan, criterios=CRITERIOS)
                with self.assertRaises((ad.ErrorPuente, ad.ErrorEvidenciaEtabs)):
                    ver.ejecutar_verificacion(prep, confirmar_lectura=True)
                self.assertFalse((prep.solicitud.carpeta / "resultado_verificacion.json").exists())
                self.assertTrue((prep.solicitud.carpeta / "verificacion_no_completada.json").is_file())
                self.assertTrue(ver.estado_incierto.exists())
                if modo == "edb_cambia":
                    self.edb.write_bytes(self.edb.read_bytes()[:-1])

    def test_preparacion_rechaza_huella_plan_y_edb_alterado(self):
        ver = self.verificador("ok")
        with self.assertRaises(ad.ErrorEvidenciaEtabs):
            ver.preparar_verificacion(self.edb, "0" * 64, self.plan, criterios=CRITERIOS)
        with self.assertRaises(v.ErrorVerificacion):
            ver.preparar_verificacion(self.edb, self.sha, self.plan, criterios=None)
        prep = ver.preparar_verificacion(self.edb, self.sha, self.plan, criterios=CRITERIOS)
        self.edb.write_bytes(self.edb.read_bytes() + b" ")
        with self.assertRaises(ad.ErrorEvidenciaEtabs):
            ver.ejecutar_verificacion(prep, confirmar_lectura=True)


CS_FALSO = r'''
using System; using System.IO; using System.Collections.Generic; using System.Globalization;
using System.Web.Script.Serialization;
[assembly: System.Reflection.AssemblyVersion("1.0.0.0")]
[assembly: System.Reflection.AssemblyFileVersion("1.29.0.0")]
namespace ETABSv1 {
public enum eUnits { lb_in_F = 1, kip_in_F = 3, kN_mm_C = 5, kN_m_C = 6, N_mm_C = 9, N_m_C = 10, kN_cm_C = 13 }  // valores reflejados
public enum eItemType { Objects = 0, Group = 1 }
public enum eSlabType { Slab = 0, Drop = 1, Ribbed = 3, Waffle = 4 }  // valores reflejados de ETABSv1 1.29.0.0
public enum eShellType { ShellThin = 1, ShellThick = 2, Membrane = 3 }
public enum eWallPropType { Specified = 1 }
public enum eMatType { Steel = 1, Concrete = 2, NoDesign = 3 }
public enum eFramePropType { I = 1, Rectangular = 8 }
public enum eDiaphragmOption { Disconnect = 1, FromShellObject = 2, DefinedDiaphragm = 3 }
public enum eLoadPatternType { Dead = 1, Live = 3, Quake = 5, Other = 8 }
public enum eLoadCaseType { LinearStatic = 1, Modal = 3, ResponseSpectrum = 4 }
public enum eCNameType { LoadCase = 0, LoadCombo = 1 }
public static class M {
  public static Dictionary<string, object> D; public static string Ruta;
  public static string Env(string n) { return Environment.GetEnvironmentVariable(n); }
  public static void Log(string m) { string l = Env("FALSO_LOG"); if (l != null) File.AppendAllText(l, m + "\n"); }
  public static int Ret(string m) {
    Log(m);
    if (Env("FALSO_EXCEPCION") == m) throw new InvalidOperationException("Excepcion simulada en " + m);
    if (Env("FALSO_MUTAR") == m && Ruta != null) File.AppendAllText(Ruta, " ");
    return Env("FALSO_RETORNO") == m ? 5 : 0;
  }
  public static void Cargar(string r) { Ruta = r; var s = new JavaScriptSerializer(); s.MaxJsonLength = int.MaxValue;
    D = (Dictionary<string, object>)s.DeserializeObject(File.ReadAllText(r)); }
  public static Dictionary<string, object> O(object o, string k) { var d = (Dictionary<string, object>)o; return d.ContainsKey(k) ? (Dictionary<string, object>)d[k] : null; }
  public static object G(object o, string k) { var d = (Dictionary<string, object>)o; return d != null && d.ContainsKey(k) ? d[k] : null; }
  public static string[] SA(object o) { var a = (object[])(o ?? new object[0]); var r = new string[a.Length]; for (int i = 0; i < a.Length; i++) r[i] = (string)a[i]; return r; }
  public static double Dbl(object o) { return Convert.ToDouble(o, CultureInfo.InvariantCulture); }
  public static double[] DA(object o) { var a = (object[])(o ?? new object[0]); var r = new double[a.Length]; for (int i = 0; i < a.Length; i++) r[i] = Dbl(a[i]); return r; }
  public static object[] L(object o) { return (object[])(o ?? new object[0]); }
  public static string[] Nombres(string seccion) { return SA(G(D[seccion], "nombres")); }
}
public interface cHelper { cOAPI CreateObjectProgID(string progID); }
public class Helper : cHelper { public cOAPI CreateObjectProgID(string progID) { M.Log("CreateObjectProgID"); return new OAPI(); } }
public interface cOAPI { cSapModel SapModel { get; } int ApplicationStart(); int Hide(); int ApplicationExit(bool FileSave); }
public class OAPI : cOAPI { Sap s = new Sap(); public cSapModel SapModel { get { return s; } }
  public int ApplicationStart() { return M.Ret("cOAPI.ApplicationStart"); } public int Hide() { return M.Ret("cOAPI.Hide"); }
  public int ApplicationExit(bool FileSave) { M.Log("ApplicationExit:" + FileSave); return M.Env("FALSO_CIERRE") == "1" ? 3 : 0; } }
public interface cFile { int OpenFile(string FileName); }
public class Fil : cFile { public int OpenFile(string FileName) { int r = M.Ret("cFile.OpenFile"); if (r == 0) M.Cargar(FileName); return r; } }
public interface cSapModel { cFile File { get; } cStory Story { get; } cPointObj PointObj { get; } cFrameObj FrameObj { get; } cAreaObj AreaObj { get; }
  cPropArea PropArea { get; } cPropFrame PropFrame { get; } cPropMaterial PropMaterial { get; }
  cDiaphragm Diaphragm { get; } cLoadPatterns LoadPatterns { get; } cLoadCases LoadCases { get; } cFunction Func { get; }
  cCombo RespCombo { get; } cAnalyze Analyze { get; } cDatabaseTables DatabaseTables { get; }
  string GetModelFilename(bool IncludePath); int GetVersion(ref string Version, ref double MyVersionNumber); eUnits GetPresentUnits(); }
public class Sap : cSapModel {
  public cFile File { get { return new Fil(); } } public cStory Story { get { return new Sto(); } } public cPointObj PointObj { get { return new Pto(); } }
  public cFrameObj FrameObj { get { return new Fra(); } } public cAreaObj AreaObj { get { return new Are(); } } public cPropArea PropArea { get { return new PA(); } }
  public cPropFrame PropFrame { get { return new PF(); } } public cPropMaterial PropMaterial { get { return new PM(); } }
  public cDiaphragm Diaphragm { get { return new Dia(); } } public cLoadPatterns LoadPatterns { get { return new Pat(); } }
  public cLoadCases LoadCases { get { return new LC(); } } public cFunction Func { get { return new Fun(); } }
  public cCombo RespCombo { get { return new Com(); } } public cAnalyze Analyze { get { return new Ana(); } }
  public cDatabaseTables DatabaseTables { get { return new DB(); } }
  public string GetModelFilename(bool IncludePath) { return M.Ruta; }
  public int GetVersion(ref string Version, ref double MyVersionNumber) { int r = M.Ret("cSapModel.GetVersion"); Version = (string)M.D["version"]; MyVersionNumber = 21.1; return r; }
  public eUnits GetPresentUnits() { string u = M.Env("FALSO_UNIDADES"); return string.IsNullOrEmpty(u) ? eUnits.kN_m_C : (eUnits)Enum.Parse(typeof(eUnits), u); } }
public interface cStory { int GetStories_2(ref double BaseElevation, ref int NumberStories, ref string[] StoryNames, ref double[] StoryElevations, ref double[] StoryHeights, ref bool[] IsMasterStory, ref string[] SimilarToStory, ref bool[] SpliceAbove, ref double[] SpliceHeight, ref int[] color); }
public class Sto : cStory { public int GetStories_2(ref double BaseElevation, ref int NumberStories, ref string[] StoryNames, ref double[] StoryElevations, ref double[] StoryHeights, ref bool[] IsMasterStory, ref string[] SimilarToStory, ref bool[] SpliceAbove, ref double[] SpliceHeight, ref int[] color) {
  int r = M.Ret("cStory.GetStories_2"); if (r != 0) return r; var p = M.D["pisos"]; BaseElevation = M.Dbl(M.G(p, "base")); StoryNames = M.SA(M.G(p, "nombres")); NumberStories = StoryNames.Length;
  StoryElevations = M.DA(M.G(p, "elevaciones")); StoryHeights = M.DA(M.G(p, "alturas")); return 0; } }
public interface cPointObj { int GetNameList(ref int NumberNames, ref string[] MyName); int GetCoordCartesian(string Name, ref double X, ref double Y, ref double Z, string CSys);
  int GetLoadForce(string Name, ref int NumberItems, ref string[] PointName, ref string[] LoadPat, ref int[] LcStep, ref string[] CSys, ref double[] F1, ref double[] F2, ref double[] F3, ref double[] M1, ref double[] M2, ref double[] M3, eItemType ItemType);
  int GetRestraint(string Name, ref bool[] Value); int GetDiaphragm(string Name, ref eDiaphragmOption DiaphragmOption, ref string DiaphragmName); }
public class Pto : cPointObj {
  public int GetRestraint(string Name, ref bool[] Value) { int r = M.Ret("cPointObj.GetRestraint"); var v = M.G(M.D["apoyos"], Name); if (r != 0 || v == null) return r != 0 ? r : 1;
    var a = M.L(v); Value = new bool[a.Length]; for (int i = 0; i < a.Length; i++) Value[i] = (bool)a[i]; return 0; }
  public int GetDiaphragm(string Name, ref eDiaphragmOption DiaphragmOption, ref string DiaphragmName) { int r = M.Ret("cPointObj.GetDiaphragm"); var d = M.G(M.D["diafragmas_puntos"], Name);
    if (r != 0 || d == null) return r != 0 ? r : 1; DiaphragmOption = (eDiaphragmOption)Convert.ToInt32(M.G(M.G(d, "opcion"), "valor")); DiaphragmName = (string)M.G(d, "diafragma"); return 0; }
  public int GetNameList(ref int NumberNames, ref string[] MyName) { int r = M.Ret("cPointObj.GetNameList"); MyName = M.Nombres("puntos"); NumberNames = MyName.Length; return r; }
  public int GetCoordCartesian(string Name, ref double X, ref double Y, ref double Z, string CSys) { int r = M.Ret("cPointObj.GetCoordCartesian"); var c = M.G(M.G(M.D["puntos"], "coordenadas"), Name);
    if (r != 0 || c == null || CSys != "Global") return r != 0 ? r : 1; var a = M.DA(c); X = a[0]; Y = a[1]; Z = a[2]; return 0; }
  public int GetLoadForce(string Name, ref int NumberItems, ref string[] PointName, ref string[] LoadPat, ref int[] LcStep, ref string[] CSys, ref double[] F1, ref double[] F2, ref double[] F3, ref double[] M1, ref double[] M2, ref double[] M3, eItemType ItemType) {
    int r = M.Ret("cPointObj.GetLoadForce"); if (r != 0) return r; var it = M.L(M.G(M.D["cargas_punto"], Name)); int n = it.Length; NumberItems = n;
    PointName = new string[n]; LoadPat = new string[n]; LcStep = new int[n]; CSys = new string[n]; F1 = new double[n]; F2 = new double[n]; F3 = new double[n]; M1 = new double[n]; M2 = new double[n]; M3 = new double[n];
    for (int i = 0; i < n; i++) { var c = it[i]; PointName[i] = (string)M.G(c, "objeto"); LoadPat[i] = (string)M.G(c, "patron"); CSys[i] = (string)M.G(c, "csys"); var v = M.DA(M.G(c, "valores"));
      F1[i] = v[0]; F2[i] = v[1]; F3[i] = v[2]; M1[i] = v[3]; M2[i] = v[4]; M3[i] = v[5]; } return 0; } }
public interface cFrameObj { int GetNameList(ref int NumberNames, ref string[] MyName); int GetPoints(string Name, ref string Point1, ref string Point2); int GetSection(string Name, ref string PropName, ref string SAuto);
  int GetLoadDistributed(string Name, ref int NumberItems, ref string[] FrameName, ref string[] LoadPat, ref int[] MyType, ref string[] CSys, ref int[] Dir, ref double[] RD1, ref double[] RD2, ref double[] Dist1, ref double[] Dist2, ref double[] Val1, ref double[] Val2, eItemType ItemType); }
public class Fra : cFrameObj {
  public int GetNameList(ref int NumberNames, ref string[] MyName) { int r = M.Ret("cFrameObj.GetNameList"); MyName = M.Nombres("frames"); NumberNames = MyName.Length; return r; }
  public int GetPoints(string Name, ref string Point1, ref string Point2) { int r = M.Ret("cFrameObj.GetPoints"); var p = M.SA(M.G(M.G(M.D["frames"], "puntos"), Name)); if (r != 0 || p.Length != 2) return r != 0 ? r : 1; Point1 = p[0]; Point2 = p[1]; return 0; }
  public int GetSection(string Name, ref string PropName, ref string SAuto) { int r = M.Ret("cFrameObj.GetSection"); var s = M.G(M.G(M.D["frames"], "secciones"), Name); if (r != 0 || s == null) return r != 0 ? r : 1; PropName = (string)s; SAuto = ""; return 0; }
  public int GetLoadDistributed(string Name, ref int NumberItems, ref string[] FrameName, ref string[] LoadPat, ref int[] MyType, ref string[] CSys, ref int[] Dir, ref double[] RD1, ref double[] RD2, ref double[] Dist1, ref double[] Dist2, ref double[] Val1, ref double[] Val2, eItemType ItemType) {
    int r = M.Ret("cFrameObj.GetLoadDistributed"); if (r != 0) return r; var it = M.L(M.G(M.D["cargas_frame"], Name)); int n = it.Length; NumberItems = n;
    FrameName = new string[n]; LoadPat = new string[n]; MyType = new int[n]; CSys = new string[n]; Dir = new int[n]; RD1 = new double[n]; RD2 = new double[n]; Dist1 = new double[n]; Dist2 = new double[n]; Val1 = new double[n]; Val2 = new double[n];
    for (int i = 0; i < n; i++) { var c = it[i]; FrameName[i] = (string)M.G(c, "objeto"); LoadPat[i] = (string)M.G(c, "patron"); MyType[i] = Convert.ToInt32(M.G(c, "tipo")); CSys[i] = (string)M.G(c, "csys");
      Dir[i] = Convert.ToInt32(M.G(c, "dir")); RD1[i] = M.Dbl(M.G(c, "rd1")); RD2[i] = M.Dbl(M.G(c, "rd2")); Val1[i] = M.Dbl(M.G(c, "val1")); Val2[i] = M.Dbl(M.G(c, "val2")); } return 0; } }
public interface cAreaObj { int GetNameList(ref int NumberNames, ref string[] MyName); int GetPoints(string Name, ref int NumberPoints, ref string[] Point); int GetProperty(string Name, ref string PropName);
  int GetLocalAxes(string Name, ref double Ang, ref bool Advanced); int GetDiaphragm(string Name, ref string DiaphragmName);
  int GetOpening(string Name, ref bool IsOpening); int GetLoadUniform(string Name, ref int NumberItems, ref string[] AreaName, ref string[] LoadPat, ref string[] CSys, ref int[] Dir, ref double[] Value, ITEMTYPE ItemType); }
public class Are : cAreaObj {
  public int GetOpening(string Name, ref bool IsOpening) { int r = M.Ret("cAreaObj.GetOpening"); var h = M.G(M.G(M.D["areas"], "aberturas"), Name); if (r != 0 || h == null) return r != 0 ? r : 1; IsOpening = (bool)h; return 0; }
  public int GetDiaphragm(string Name, ref string DiaphragmName) { int r = M.Ret("cAreaObj.GetDiaphragm"); var d = M.G(M.D["diafragmas_areas"], Name); if (r != 0 || d == null) return r != 0 ? r : 1; DiaphragmName = (string)d; return 0; }
  public int GetNameList(ref int NumberNames, ref string[] MyName) { int r = M.Ret("cAreaObj.GetNameList"); MyName = M.Nombres("areas"); NumberNames = MyName.Length; return r; }
  public int GetPoints(string Name, ref int NumberPoints, ref string[] Point) { int r = M.Ret("cAreaObj.GetPoints"); var p = M.G(M.G(M.D["areas"], "puntos"), Name); if (r != 0 || p == null) return r != 0 ? r : 1; Point = M.SA(p); NumberPoints = Point.Length; return 0; }
  public int GetProperty(string Name, ref string PropName) { int r = M.Ret("cAreaObj.GetProperty"); var p = M.G(M.G(M.D["areas"], "propiedades"), Name); if (r != 0 || p == null) return r != 0 ? r : 1; PropName = (string)p; return 0; }
  public int GetLocalAxes(string Name, ref double Ang, ref bool Advanced) { int r = M.Ret("cAreaObj.GetLocalAxes"); var e = M.G(M.G(M.D["areas"], "ejes"), Name); if (r != 0 || e == null) return r != 0 ? r : 1; Ang = M.Dbl(M.G(e, "angulo_deg")); Advanced = (bool)M.G(e, "avanzado"); return 0; }
  public int GetLoadUniform(string Name, ref int NumberItems, ref string[] AreaName, ref string[] LoadPat, ref string[] CSys, ref int[] Dir, ref double[] Value, ITEMTYPE ItemType) {
    int r = M.Ret("cAreaObj.GetLoadUniform"); if (r != 0) return r; var it = M.L(M.G(M.D["cargas_area"], Name)); int n = it.Length; NumberItems = n;
    AreaName = new string[n]; LoadPat = new string[n]; CSys = new string[n]; Dir = new int[n]; Value = new double[n];
    for (int i = 0; i < n; i++) { var c = it[i]; AreaName[i] = (string)M.G(c, "objeto"); LoadPat[i] = (string)M.G(c, "patron"); CSys[i] = (string)M.G(c, "csys"); Dir[i] = Convert.ToInt32(M.G(c, "dir")); Value[i] = M.Dbl(M.G(c, "valor")); } return 0; } }
public interface cPropArea { int GetNameList(ref int NumberNames, ref string[] MyName, int PropType);
  int GetSlab(string Name, ref eSlabType SlabType, ref eShellType ShellType, ref string MatProp, ref double Thickness, ref int color, ref string notes, ref string GUID);
  int GetWall(string Name, ref eWallPropType WallPropType, ref eShellType ShellType, ref string MatProp, ref double Thickness, ref int color, ref string notes, ref string GUID);
  int GetSlabRibbed(string Name, ref double OverallDepth, ref double SlabThickness, ref double StemWidthTop, ref double StemWidthBot, ref double RibSpacing, ref int RibsParallelTo);
  int GetSlabWaffle(string Name, ref double OverallDepth, ref double SlabThickness, ref double StemWidthTop, ref double StemWidthBot, ref double RibSpacingDir1, ref double RibSpacingDir2); }
public class PA : cPropArea {
  public int GetSlabRibbed(string Name, ref double OverallDepth, ref double SlabThickness, ref double StemWidthTop, ref double StemWidthBot, ref double RibSpacing, ref int RibsParallelTo) {
    int r = M.Ret("cPropArea.GetSlabRibbed"); var d = M.G(M.G(M.D["propiedades_area"], "nervadas"), Name); if (r != 0 || d == null) return r != 0 ? r : 1;
    OverallDepth = M.Dbl(M.G(d, "OverallDepth")); SlabThickness = M.Dbl(M.G(d, "SlabThickness")); StemWidthTop = M.Dbl(M.G(d, "StemWidthTop")); StemWidthBot = M.Dbl(M.G(d, "StemWidthBot"));
    RibSpacing = M.Dbl(M.G(d, "RibSpacing")); RibsParallelTo = Convert.ToInt32(M.G(d, "RibsParallelTo")); return 0; }
  public int GetSlabWaffle(string Name, ref double OverallDepth, ref double SlabThickness, ref double StemWidthTop, ref double StemWidthBot, ref double RibSpacingDir1, ref double RibSpacingDir2) {
    int r = M.Ret("cPropArea.GetSlabWaffle"); var d = M.G(M.G(M.D["propiedades_area"], "casetonadas"), Name); if (r != 0 || d == null) return r != 0 ? r : 1;
    OverallDepth = M.Dbl(M.G(d, "OverallDepth")); SlabThickness = M.Dbl(M.G(d, "SlabThickness")); StemWidthTop = M.Dbl(M.G(d, "StemWidthTop")); StemWidthBot = M.Dbl(M.G(d, "StemWidthBot"));
    RibSpacingDir1 = M.Dbl(M.G(d, "RibSpacingDir1")); RibSpacingDir2 = M.Dbl(M.G(d, "RibSpacingDir2")); return 0; }
  public int GetNameList(ref int NumberNames, ref string[] MyName, int PropType) { int r = M.Ret("cPropArea.GetNameList"); MyName = M.Nombres("propiedades_area"); NumberNames = MyName.Length; return r; }
  public int GetSlab(string Name, ref eSlabType SlabType, ref eShellType ShellType, ref string MatProp, ref double Thickness, ref int color, ref string notes, ref string GUID) {
    int r = M.Ret("cPropArea.GetSlab"); var d = M.G(M.G(M.D["propiedades_area"], "losas"), Name); if (r != 0 || d == null) return r != 0 ? r : 1;
    SlabType = (eSlabType)Convert.ToInt32(M.G(M.G(d, "subtipo"), "valor")); ShellType = (eShellType)Convert.ToInt32(M.G(M.G(d, "shell"), "valor")); MatProp = (string)M.G(d, "material"); Thickness = M.Dbl(M.G(d, "espesor")); return 0; }
  public int GetWall(string Name, ref eWallPropType WallPropType, ref eShellType ShellType, ref string MatProp, ref double Thickness, ref int color, ref string notes, ref string GUID) {
    int r = M.Ret("cPropArea.GetWall"); var d = M.G(M.G(M.D["propiedades_area"], "muros"), Name); if (r != 0 || d == null) return r != 0 ? r : 1;
    WallPropType = (eWallPropType)Convert.ToInt32(M.G(M.G(d, "subtipo"), "valor")); ShellType = (eShellType)Convert.ToInt32(M.G(M.G(d, "shell"), "valor")); MatProp = (string)M.G(d, "material"); Thickness = M.Dbl(M.G(d, "espesor")); return 0; } }
public interface cPropFrame { int GetNameList(ref int NumberNames, ref string[] MyName, eFramePropType PropType);
  int GetRectangle(string Name, ref string FileName, ref string MatProp, ref double T3, ref double T2, ref int Color, ref string Notes, ref string GUID); }
public class PF : cPropFrame {
  public int GetNameList(ref int NumberNames, ref string[] MyName, eFramePropType PropType) { int r = M.Ret("cPropFrame.GetNameList"); MyName = M.Nombres("propiedades_frame"); NumberNames = MyName.Length; return r; }
  public int GetRectangle(string Name, ref string FileName, ref string MatProp, ref double T3, ref double T2, ref int Color, ref string Notes, ref string GUID) {
    int r = M.Ret("cPropFrame.GetRectangle"); var d = M.G(M.G(M.D["propiedades_frame"], "rectangulos"), Name); if (r != 0 || d == null) return r != 0 ? r : 1;
    MatProp = (string)M.G(d, "material"); T3 = M.Dbl(M.G(d, "t3")); T2 = M.Dbl(M.G(d, "t2")); return 0; } }
public interface cPropMaterial { int GetNameList(ref int NumberNames, ref string[] MyName, eMatType MatType); int GetMaterial(string Name, ref eMatType MatType, ref int Color, ref string Notes, ref string GUID);
  int GetMPIsotropic(string Name, ref double E, ref double U, ref double A, ref double G, double Temp); int GetWeightAndMass(string Name, ref double W, ref double M, double Temp);
  int GetMassSource_1(ref bool IncludeElements, ref bool IncludeAddedMass, ref bool IncludeLoads, ref int NumberLoads, ref string[] LoadPat, ref double[] sf); }
public class PM : cPropMaterial {
  public int GetNameList(ref int NumberNames, ref string[] MyName, eMatType MatType) { int r = M.Ret("cPropMaterial.GetNameList"); MyName = M.Nombres("materiales"); NumberNames = MyName.Length; return r; }
  static object Det(string n) { return M.G(M.G(M.D["materiales"], "detalle"), n); }
  public int GetMaterial(string Name, ref eMatType MatType, ref int Color, ref string Notes, ref string GUID) { int r = M.Ret("cPropMaterial.GetMaterial"); var d = Det(Name); if (r != 0 || d == null) return r != 0 ? r : 1; MatType = (eMatType)Convert.ToInt32(M.G(M.G(d, "tipo"), "valor")); return 0; }
  public int GetMPIsotropic(string Name, ref double E, ref double U, ref double A, ref double G, double Temp) { int r = M.Ret("cPropMaterial.GetMPIsotropic"); var d = Det(Name); if (r != 0 || d == null) return r != 0 ? r : 1;
    E = M.Dbl(M.G(d, "E")); U = M.Dbl(M.G(d, "U")); A = M.Dbl(M.G(d, "A")); G = M.Dbl(M.G(d, "G")); return 0; }
  public int GetWeightAndMass(string Name, ref double W, ref double M_, double Temp) { return 0; }
  public int GetMassSource_1(ref bool IncludeElements, ref bool IncludeAddedMass, ref bool IncludeLoads, ref int NumberLoads, ref string[] LoadPat, ref double[] sf) {
    int r = M.Ret("cPropMaterial.GetMassSource_1"); if (r != 0) return r; var f = M.D["fuente_masa"]; IncludeElements = (bool)M.G(f, "incluir_elementos"); IncludeAddedMass = (bool)M.G(f, "incluir_masa_adicional");
    IncludeLoads = (bool)M.G(f, "incluir_cargas"); LoadPat = M.SA(M.G(f, "patrones")); sf = M.DA(M.G(f, "factores")); NumberLoads = LoadPat.Length; return 0; } }
public interface cDiaphragm { int GetNameList(ref int NumberNames, ref string[] MyName); int GetDiaphragm(string Name, ref bool SemiRigid); }
public class Dia : cDiaphragm {
  public int GetNameList(ref int NumberNames, ref string[] MyName) { int r = M.Ret("cDiaphragm.GetNameList"); MyName = M.Nombres("diafragmas"); NumberNames = MyName.Length; return r; }
  public int GetDiaphragm(string Name, ref bool SemiRigid) { int r = M.Ret("cDiaphragm.GetDiaphragm"); var s = M.G(M.G(M.D["diafragmas"], "semirrigido"), Name); if (r != 0 || s == null) return r != 0 ? r : 1; SemiRigid = (bool)s; return 0; } }
public interface cLoadPatterns { int GetNameList(ref int NumberNames, ref string[] MyName); int GetLoadType(string Name, ref eLoadPatternType MyType); int GetSelfWTMultiplier(string Name, ref double SelfWTMultiplier); }
public class Pat : cLoadPatterns {
  public int GetNameList(ref int NumberNames, ref string[] MyName) { int r = M.Ret("cLoadPatterns.GetNameList"); MyName = M.Nombres("patrones"); NumberNames = MyName.Length; return r; }
  static object Det(string n) { return M.G(M.G(M.D["patrones"], "detalle"), n); }
  public int GetLoadType(string Name, ref eLoadPatternType MyType) { int r = M.Ret("cLoadPatterns.GetLoadType"); var d = Det(Name); if (r != 0 || d == null) return r != 0 ? r : 1; MyType = (eLoadPatternType)Convert.ToInt32(M.G(M.G(d, "tipo"), "valor")); return 0; }
  public int GetSelfWTMultiplier(string Name, ref double SelfWTMultiplier) { int r = M.Ret("cLoadPatterns.GetSelfWTMultiplier"); var d = Det(Name); if (r != 0 || d == null) return r != 0 ? r : 1; SelfWTMultiplier = M.Dbl(M.G(d, "multiplicador")); return 0; } }
public interface cLoadCases { cCaseStaticLinear StaticLinear { get; } cCaseModalEigen ModalEigen { get; } cCaseResponseSpectrum ResponseSpectrum { get; }
  int GetNameList(ref int NumberNames, ref string[] MyName, eLoadCaseType CaseType); int GetTypeOAPI(string Name, ref eLoadCaseType CaseType, ref int SubType); }
public class LC : cLoadCases {
  public cCaseStaticLinear StaticLinear { get { return new SL(); } } public cCaseModalEigen ModalEigen { get { return new ME(); } } public cCaseResponseSpectrum ResponseSpectrum { get { return new RS(); } }
  public int GetNameList(ref int NumberNames, ref string[] MyName, eLoadCaseType CaseType) { int r = M.Ret("cLoadCases.GetNameList"); MyName = M.Nombres("casos"); NumberNames = MyName.Length; return r; }
  public int GetTypeOAPI(string Name, ref eLoadCaseType CaseType, ref int SubType) { int r = M.Ret("cLoadCases.GetTypeOAPI"); var d = M.G(M.G(M.D["casos"], "tipos"), Name); if (r != 0 || d == null) return r != 0 ? r : 1;
    CaseType = (eLoadCaseType)Convert.ToInt32(M.G(M.G(d, "tipo"), "valor")); SubType = Convert.ToInt32(M.G(d, "subtipo")); return 0; } }
public interface cCaseStaticLinear { int GetLoads(string Name, ref int NumberLoads, ref string[] LoadType, ref string[] LoadName, ref double[] SF); }
public class SL : cCaseStaticLinear { public int GetLoads(string Name, ref int NumberLoads, ref string[] LoadType, ref string[] LoadName, ref double[] SF) {
  int r = M.Ret("cCaseStaticLinear.GetLoads"); var it = M.G(M.G(M.D["casos"], "estaticos"), Name); if (r != 0 || it == null) return r != 0 ? r : 1; var a = M.L(it); int n = a.Length; NumberLoads = n;
  LoadType = new string[n]; LoadName = new string[n]; SF = new double[n]; for (int i = 0; i < n; i++) { LoadType[i] = (string)M.G(a[i], "tipo_carga"); LoadName[i] = (string)M.G(a[i], "nombre"); SF[i] = M.Dbl(M.G(a[i], "factor")); } return 0; } }
public interface cCaseModalEigen { int GetNumberModes(string Name, ref int MaxModes, ref int MinModes); int GetParameters(string Name, ref double EigenShiftFreq, ref double EigenCutOff, ref double EigenTol, ref int AllowAutoFreqShift);
  int GetLoads(string Name, ref int NumberLoads, ref string[] LoadType, ref string[] LoadName, ref double[] TargetPar, ref bool[] StaticCorrect); }
public class ME : cCaseModalEigen {
  static object Det(string n) { return M.G(M.G(M.D["casos"], "modales"), n); }
  public int GetNumberModes(string Name, ref int MaxModes, ref int MinModes) { int r = M.Ret("cCaseModalEigen.GetNumberModes"); var d = Det(Name); if (r != 0 || d == null) return r != 0 ? r : 1; var m = M.L(M.G(d, "modos")); MaxModes = Convert.ToInt32(m[0]); MinModes = Convert.ToInt32(m[1]); return 0; }
  public int GetParameters(string Name, ref double EigenShiftFreq, ref double EigenCutOff, ref double EigenTol, ref int AllowAutoFreqShift) { int r = M.Ret("cCaseModalEigen.GetParameters"); var d = Det(Name); if (r != 0 || d == null) return r != 0 ? r : 1;
    EigenShiftFreq = M.Dbl(M.G(d, "desplazamiento")); EigenCutOff = M.Dbl(M.G(d, "corte")); EigenTol = M.Dbl(M.G(d, "tolerancia")); AllowAutoFreqShift = Convert.ToInt32(M.G(d, "automatico")); return 0; }
  public int GetLoads(string Name, ref int NumberLoads, ref string[] LoadType, ref string[] LoadName, ref double[] TargetPar, ref bool[] StaticCorrect) { int r = M.Ret("cCaseModalEigen.GetLoads"); var d = Det(Name); if (r != 0 || d == null) return r != 0 ? r : 1;
    NumberLoads = Convert.ToInt32(M.G(d, "numero_cargas")); LoadType = new string[NumberLoads]; LoadName = new string[NumberLoads]; TargetPar = new double[NumberLoads]; StaticCorrect = new bool[NumberLoads]; return 0; } }
public interface cCaseResponseSpectrum { int GetModalCase(string Name, ref string ModalCase); int GetLoads(string Name, ref int NumberLoads, ref string[] LoadName, ref string[] Func, ref double[] SF, ref string[] CSys, ref double[] Ang);
  int GetEccentricity(string Name, ref double Eccen); int GetDampConstant(string Name, ref double Damp); int GetDampType(string Name, ref int DampType);
  int GetModalComb_1(string Name, ref int MyType, ref double F1, ref double F2, ref int PeriodicRigidCombType, ref double Td); }
public class RS : cCaseResponseSpectrum {
  static object Det(string n) { return M.G(M.G(M.D["casos"], "espectrales"), n); }
  public int GetModalCase(string Name, ref string ModalCase) { int r = M.Ret("cCaseResponseSpectrum.GetModalCase"); var d = Det(Name); if (r != 0 || d == null) return r != 0 ? r : 1; ModalCase = (string)M.G(d, "modal"); return 0; }
  public int GetLoads(string Name, ref int NumberLoads, ref string[] LoadName, ref string[] Func, ref double[] SF, ref string[] CSys, ref double[] Ang) { int r = M.Ret("cCaseResponseSpectrum.GetLoads"); var d = Det(Name); if (r != 0 || d == null) return r != 0 ? r : 1;
    var a = M.L(M.G(d, "cargas")); int n = a.Length; NumberLoads = n; LoadName = new string[n]; Func = new string[n]; SF = new double[n]; CSys = new string[n]; Ang = new double[n];
    for (int i = 0; i < n; i++) { LoadName[i] = (string)M.G(a[i], "nombre"); Func[i] = (string)M.G(a[i], "funcion"); SF[i] = M.Dbl(M.G(a[i], "factor")); CSys[i] = (string)M.G(a[i], "csys"); Ang[i] = M.Dbl(M.G(a[i], "angulo")); } return 0; }
  public int GetEccentricity(string Name, ref double Eccen) { int r = M.Ret("cCaseResponseSpectrum.GetEccentricity"); var d = Det(Name); if (r != 0 || d == null) return r != 0 ? r : 1; Eccen = M.Dbl(M.G(d, "excentricidad")); return 0; }
  public int GetDampConstant(string Name, ref double Damp) { int r = M.Ret("cCaseResponseSpectrum.GetDampConstant"); var d = Det(Name); if (r != 0 || d == null) return r != 0 ? r : 1; Damp = M.Dbl(M.G(d, "amortiguamiento")); return 0; }
  public int GetDampType(string Name, ref int DampType) { int r = M.Ret("cCaseResponseSpectrum.GetDampType"); var d = Det(Name); if (r != 0 || d == null) return r != 0 ? r : 1; DampType = Convert.ToInt32(M.G(d, "tipo_amortiguamiento")); return 0; }
  public int GetModalComb_1(string Name, ref int MyType, ref double F1, ref double F2, ref int PeriodicRigidCombType, ref double Td) { int r = M.Ret("cCaseResponseSpectrum.GetModalComb_1"); var d = Det(Name); if (r != 0 || d == null) return r != 0 ? r : 1;
    var c = M.G(d, "comb_modal"); MyType = Convert.ToInt32(M.G(c, "tipo")); F1 = M.Dbl(M.G(c, "f1")); F2 = M.Dbl(M.G(c, "f2")); PeriodicRigidCombType = Convert.ToInt32(M.G(c, "periodica_rigida")); Td = M.Dbl(M.G(c, "td")); return 0; } }
public interface cFunction { int GetNameList(ref int NumberNames, ref string[] MyName, int FuncType); int GetValues(string Name, ref int NumberItems, ref double[] MyTime, ref double[] Value); }
public class Fun : cFunction {
  public int GetNameList(ref int NumberNames, ref string[] MyName, int FuncType) { int r = M.Ret("cFunction.GetNameList"); MyName = M.Nombres("funciones"); NumberNames = MyName.Length; return r; }
  public int GetValues(string Name, ref int NumberItems, ref double[] MyTime, ref double[] Value) { int r = M.Ret("cFunction.GetValues"); var d = M.G(M.G(M.D["funciones"], "valores"), Name); if (r != 0 || d == null) return r != 0 ? r : 1;
    NumberItems = Convert.ToInt32(M.G(d, "numero")); MyTime = M.DA(M.G(d, "tiempos")); Value = M.DA(M.G(d, "valores")); return 0; } }
public interface cCombo { int GetNameList(ref int NumberNames, ref string[] MyName); int GetTypeOAPI(string name, ref int ComboType); int GetCaseList(string Name, ref int NumberItems, ref eCNameType[] CNameType, ref string[] CName, ref double[] SF); }
public class Com : cCombo {
  static object Det(string n) { return M.G(M.G(M.D["combinaciones"], "detalle"), n); }
  public int GetNameList(ref int NumberNames, ref string[] MyName) { int r = M.Ret("cCombo.GetNameList"); MyName = M.Nombres("combinaciones"); NumberNames = MyName.Length; return r; }
  public int GetTypeOAPI(string name, ref int ComboType) { int r = M.Ret("cCombo.GetTypeOAPI"); var d = Det(name); if (r != 0 || d == null) return r != 0 ? r : 1; ComboType = Convert.ToInt32(M.G(d, "tipo")); return 0; }
  public int GetCaseList(string Name, ref int NumberItems, ref eCNameType[] CNameType, ref string[] CName, ref double[] SF) { int r = M.Ret("cCombo.GetCaseList"); var d = Det(Name); if (r != 0 || d == null) return r != 0 ? r : 1;
    var a = M.L(M.G(d, "casos")); int n = a.Length; NumberItems = n; CNameType = new eCNameType[n]; CName = new string[n]; SF = new double[n];
    for (int i = 0; i < n; i++) { CNameType[i] = (eCNameType)Convert.ToInt32(M.G(M.G(a[i], "tipo"), "valor")); CName[i] = (string)M.G(a[i], "nombre"); SF[i] = M.Dbl(M.G(a[i], "factor")); } return 0; } }
public interface cAnalyze { int GetRunCaseFlag(ref int NumberItems, ref string[] CaseName, ref bool[] Run); }
public class Ana : cAnalyze { public int GetRunCaseFlag(ref int NumberItems, ref string[] CaseName, ref bool[] Run) { int r = M.Ret("cAnalyze.GetRunCaseFlag"); if (r != 0) return r;
  var e = M.D["ejecucion"]; CaseName = M.SA(M.G(e, "casos")); var a = M.L(M.G(e, "ejecutar")); Run = new bool[a.Length]; for (int i = 0; i < a.Length; i++) Run[i] = (bool)a[i]; NumberItems = CaseName.Length; return 0; } }
public interface cDatabaseTables { int GetTableForDisplayArray(string TableKey, ref string[] FieldKeyList, string GroupName, ref int TableVersion, ref string[] FieldsKeysIncluded, ref int NumberRecords, ref string[] TableData); }
public class DB : cDatabaseTables { public int GetTableForDisplayArray(string TableKey, ref string[] FieldKeyList, string GroupName, ref int TableVersion, ref string[] FieldsKeysIncluded, ref int NumberRecords, ref string[] TableData) {
  int r = M.Ret("cDatabaseTables.GetTableForDisplayArray"); var t = M.G(M.D["tablas"], TableKey); if (r != 0 || t == null) return r != 0 ? r : 1;
  FieldsKeysIncluded = M.SA(M.G(t, "campos")); var filas = M.L(M.G(t, "filas")); NumberRecords = filas.Length; TableVersion = 1;
  var datos = new List<string>(); foreach (var f in filas) foreach (var c in FieldsKeysIncluded) datos.Add((string)M.G(f, c)); TableData = datos.ToArray(); return 0; } }
}
'''
# GetWeightAndMass usa el nombre de parámetro exacto 'M' de la firma real; se sustituye aquí para evitar el choque con la clase M.
CS_FALSO = CS_FALSO.replace(
    "public int GetWeightAndMass(string Name, ref double W, ref double M_, double Temp) { return 0; }",
    "public int GetWeightAndMass(string Name, ref double W, ref double M, double Temp) { int r = ETABSv1.M.Ret(\"cPropMaterial.GetWeightAndMass\"); "
    "var d = Det(Name); if (r != 0 || d == null) return r != 0 ? r : 1; W = ETABSv1.M.Dbl(ETABSv1.M.G(d, \"W\")); M = ETABSv1.M.Dbl(ETABSv1.M.G(d, \"M\")); return 0; }")


def directiva_impide_file(carpeta: Path) -> str | None:
    """Ejecuta un .ps1 mínimo con -File (sin -ExecutionPolicy). Devuelve stderr si la directiva lo bloquea."""
    sonda = Path(carpeta) / "sonda_directiva.ps1"
    sonda.write_text("[Console]::Out.Write('ok')", encoding="utf-8")
    proceso = subprocess.run([str(ad.POWERSHELL_51), "-NoProfile", "-NonInteractive", "-File", str(sonda)],
                             capture_output=True, timeout=120, stdin=subprocess.DEVNULL)
    errores = proceso.stderr.decode("utf-8", "replace")
    if proceso.returncode != 0 and v._DIRECTIVA.search(errores):
        return " ".join(errores.split())[:400]
    return None


def compilar(cs: str, destino: Path) -> Path | None:
    fuente = destino.with_suffix(".cs")
    fuente.write_text(cs, encoding="utf-8")
    script = ("Add-Type -TypeDefinition ([IO.File]::ReadAllText($env:D2M_CS)) -ReferencedAssemblies System.Web.Extensions "
              "-OutputAssembly $env:D2M_DLL -OutputType Library")
    proceso = subprocess.run([str(ad.POWERSHELL_51), "-NoProfile", "-NonInteractive", "-EncodedCommand",
                              base64.b64encode(script.encode("utf-16-le")).decode()],
                             env=dict(os.environ, D2M_CS=str(fuente), D2M_DLL=str(destino)), capture_output=True, timeout=180)
    if proceso.returncode != 0 or not destino.is_file():
        raise unittest.SkipTest("No se pudo compilar el ensamblado falso: " + proceso.stderr.decode("utf-8", "replace")[-800:])
    return destino


@unittest.skipUnless(POWERSHELL, "requiere Windows PowerShell 5.1")
class ScriptRealContraFalsoTests(Planes, unittest.TestCase):
    """Script PowerShell REAL, modo doble, ETABSv1 falso que reabre un EDB sintético persistido."""

    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory()
        carpeta = Path(cls._dir.name)
        causa = directiva_impide_file(carpeta)
        if causa:  # entorno, no regresión: se omite con la causa observada (ver DiagnosticoEntornoTests)
            cls._dir.cleanup()
            raise unittest.SkipTest("Entorno: la directiva de ejecución efectiva impide '-File': " + causa)
        try:
            cls.dll = compilar(CS_FALSO.replace("ITEMTYPE", "eItemType"), carpeta / "ETABSv1_lectura.dll")
            (carpeta / "variante").mkdir()
            cls.dll_firma = compilar(CS_FALSO.replace("ITEMTYPE", "int"), carpeta / "variante" / "ETABSv1.dll")
        except unittest.SkipTest:
            cls._dir.cleanup()
            raise

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name)
        self.edb = self.dir / "guardado" / "modelo.edb"
        self.edb.parent.mkdir()
        self.log = self.dir / "llamadas.log"

    def preparar(self, plan, modelo, dll=None, **entorno):
        self.edb.write_bytes(json.dumps(modelo).encode("utf-8"))
        trabajo = self.dir / ("t" + str(len(list(self.dir.glob("t*")))))
        trabajo.mkdir()
        config = v.configuracion_doble_powershell(trabajo, dll or self.dll, timeout_s=240,
                                                  entorno={"FALSO_LOG": str(self.log), **entorno})
        ver = v.VerificadorModeloGuardado(config)
        prep = ver.preparar_verificacion(self.edb, v._sha(self.edb.read_bytes()), plan, criterios=CRITERIOS)
        return ver, prep

    def llamadas(self):
        return self.log.read_text(encoding="utf-8").split() if self.log.is_file() else []

    def test_reapertura_persistida_verifica_planes_01_02_y_dinamico(self):
        for nombre, plan in (("0.1", self.plan01()), ("0.2", self.plan02()), ("dinámico", self.plan_dinamico())):
            with self.subTest(nombre):
                exp = v.expectativa_desde_plan(plan)
                ver, prep = self.preparar(plan, modelo_desde_expectativa(exp))
                r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
                self.assertEqual(r.estado, "verificado", r.resultado["discrepancias"] + r.resultado["incompletos"])
                respuesta = json.loads((prep.solicitud.carpeta / "respuesta.json").read_text(encoding="utf-8-sig"))
                self.assertEqual(respuesta["datos"]["firmas_verificadas"], FIRMAS_LECTOR)
                self.assertEqual(respuesta["datos"]["instancia"], "doble")
                self.assertTrue(self.llamadas()[-1].startswith("ApplicationExit:False"))
                self.assertNotIn("Set", " ".join(self.llamadas()).replace("SetPresent", ""))  # ningún setter
                self.log.unlink()

    def test_archivo_reabierto_distinto_produce_discrepancias(self):
        plan = self.plan02()
        exp = v.expectativa_desde_plan(plan)
        modelo = modelo_desde_expectativa(exp)
        modelo["puntos"]["coordenadas"]["R3"][2] = 1.25
        modelo["cargas_area"]["S1"][0]["valor"] = -3
        modelo["cargas_area"]["S2"].append({"objeto": "S2", "patron": "D", "csys": "Global", "dir": 6, "valor": -1})
        modelo["propiedades_area"]["losas"]["LOSA20"]["espesor"] = 0.18
        modelo["fuente_masa"]["factores"][0] = 0.9
        ver, prep = self.preparar(plan, modelo)
        r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
        self.assertEqual(r.estado, "discrepancias")
        campos = {d["campo"].split(".")[-1] for d in r.resultado["discrepancias"]}
        self.assertTrue({"Z", "valor", "cantidad", "espesor", "factor"} <= campos)

    def test_configuracion_persistida_alterada_con_geometria_igual(self):
        plan = self.plan_dinamico()
        exp = v.expectativa_desde_plan(plan)
        modelo = modelo_desde_expectativa(exp)
        modelo["apoyos"]["A0"][5] = False
        modelo["diafragmas_puntos"]["B1"]["opcion"] = {"nombre": "Disconnect", "valor": 1}
        modelo["patrones"]["detalle"]["L"]["multiplicador"] = 1
        modelo["casos"]["espectrales"]["EX"]["excentricidad"] = 0.1
        modelo["combinaciones"]["detalle"]["COMB1"]["casos"][0]["factor"] = 3
        next(f for f in modelo["tablas"][o.TABLA_CASO_RS]["filas"] if f["Name"] == "EX")["RigidResp"] = "Yes"
        modelo["ejecucion"]["ejecutar"][modelo["ejecucion"]["casos"].index("Modal")] = True
        ver, prep = self.preparar(plan, modelo)
        r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
        self.assertEqual(r.estado, "discrepancias")
        categorias = {d["categoria"] for d in r.resultado["discrepancias"]}
        self.assertEqual(categorias, {"apoyos", "diafragmas", "patrones", "casos", "combinaciones", "tablas_dinamicas",
                                      "marcas_de_ejecucion"})
        self.assertNotIn("puntos", categorias)  # la geometría coincide

    def test_aligerados_persistidos_verificados_y_alterados(self):
        for tipo, metodo in (("shell_losa_nervada_v1", "Ribbed"), ("shell_losa_casetonada_v1", "Waffle")):
            with self.subTest(tipo):
                plan = self.plan_aligerado(tipo)
                exp = v.expectativa_desde_plan(plan)
                ver, prep = self.preparar(plan, modelo_desde_expectativa(exp))
                r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
                self.assertEqual(r.estado, "verificado", r.resultado["discrepancias"] + r.resultado["incompletos"])
                self.assertIn("cPropArea.GetSlab" + metodo, self.llamadas())
                self.log.unlink()
                modelo = modelo_desde_expectativa(exp)
                clase = "nervadas" if metodo == "Ribbed" else "casetonadas"
                modelo["propiedades_area"][clase]["LOSA20"]["StemWidthBot"] = 0.11
                modelo["areas"]["ejes"]["S1"]["angulo_deg"] = 0.0
                modelo["cargas_area"]["S1"][0]["valor"] = -2.5
                ver, prep = self.preparar(plan, modelo)
                r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
                self.assertEqual(r.estado, "discrepancias")
                self.assertTrue({"StemWidthBot", "eje_local_angulo", "L.valor"} <= {d["campo"] for d in r.resultado["discrepancias"]},
                                r.resultado["discrepancias"])
                self.log.unlink()
        plan = self.plan_aligerado("shell_losa_casetonada_v1")
        ver, prep = self.preparar(plan, modelo_desde_expectativa(v.expectativa_desde_plan(plan)), FALSO_RETORNO="cPropArea.GetSlabWaffle")
        r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
        self.assertEqual((r.estado, r.resultado["cobertura"]["propiedades_area"]), ("incompleto", "incompleta"))

    def test_unidades_y_aberturas_persistidas(self):
        plan = self.plan02()
        exp = v.expectativa_desde_plan(plan)
        ver, prep = self.preparar(plan, a_n_mm(modelo_desde_expectativa(exp)), FALSO_UNIDADES="N_mm_C")
        r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
        self.assertEqual(r.estado, "verificado", r.resultado["discrepancias"] + r.resultado["incompletos"])
        self.assertEqual(r.resultado["unidades"]["normalizacion"], "dimensional")
        respuesta = json.loads((prep.solicitud.carpeta / "respuesta.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(respuesta["datos"]["lecturas"]["unidades"], "N_mm_C")  # unidades originales conservadas
        self.assertEqual(respuesta["datos"]["lecturas"]["puntos"]["coordenadas"]["R3"][2], 1300)  # valor bruto sin convertir
        self.assertNotIn("SetPresentUnits", " ".join(self.llamadas()))
        self.log.unlink()
        ver, prep = self.preparar(plan, modelo_desde_expectativa(exp), FALSO_UNIDADES="lb_in_F")
        r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
        self.assertEqual((r.estado, r.resultado["unidades"]["normalizacion"]), ("incompleto", "no_admitida"))
        self.log.unlink()
        plan = self.plan_aberturas()
        exp = v.expectativa_desde_plan(plan)
        ver, prep = self.preparar(plan, modelo_desde_expectativa(exp))
        r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
        self.assertEqual(r.estado, "verificado", r.resultado["discrepancias"] + r.resultado["incompletos"])
        self.assertIn("cAreaObj.GetOpening", self.llamadas())
        self.log.unlink()
        modelo = modelo_desde_expectativa(exp)
        modelo["areas"]["aberturas"]["ABERTURA.HUECO1"] = False
        ver, prep = self.preparar(plan, modelo)
        r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
        self.assertEqual(r.estado, "discrepancias")
        self.assertEqual({d["categoria"] for d in r.resultado["discrepancias"]}, {"aberturas"})

    def test_retorno_no_cero_en_lector_nuevo_es_incompleto(self):
        plan = self.plan_dinamico()
        ver, prep = self.preparar(plan, modelo_desde_expectativa(v.expectativa_desde_plan(plan)), FALSO_RETORNO="cCombo.GetCaseList")
        r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
        self.assertEqual((r.estado, r.resultado["cobertura"]["combinaciones"]), ("incompleto", "incompleta"))
        self.assertFalse(r.resultado["verificacion_global_del_plan"])

    def test_retorno_no_cero_es_incompleto(self):
        plan = self.plan02()
        ver, prep = self.preparar(plan, modelo_desde_expectativa(v.expectativa_desde_plan(plan)), FALSO_RETORNO="cAreaObj.GetLoadUniform")
        r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
        self.assertEqual((r.estado, r.resultado["cobertura"]["cargas_area"]), ("incompleto", "incompleta"))

    def test_errores_cierran_la_instancia_propia_y_no_verifican(self):
        plan = self.plan02()
        modelo = modelo_desde_expectativa(v.expectativa_desde_plan(plan))
        casos = {"excepción de la API": ({"FALSO_EXCEPCION": "cPointObj.GetCoordCartesian"}, "api"),
                 "EDB cambia durante la lectura": ({"FALSO_MUTAR": "cAreaObj.GetLoadUniform"}, "evidencia")}
        for nombre, (entorno, tipo) in casos.items():
            with self.subTest(nombre):
                ver, prep = self.preparar(plan, modelo, **entorno)
                with self.assertRaises((ad.ErrorPuente, ad.ErrorEvidenciaEtabs)):
                    ver.ejecutar_verificacion(prep, confirmar_lectura=True)
                respuesta = json.loads((prep.solicitud.carpeta / "respuesta.json").read_text(encoding="utf-8-sig"))
                self.assertEqual(respuesta["error"]["tipo"], tipo)
                self.assertTrue(respuesta["datos"]["instancia_cerrada"])
                self.assertIn("ApplicationExit:False", self.llamadas())
                self.assertNotRegex(respuesta["error"]["mensaje"], r"[A-Za-z]:\\")  # sin rutas absolutas
                self.assertFalse((prep.solicitud.carpeta / "resultado_verificacion.json").exists())
                self.log.unlink()
                ver.confirmar_recuperacion(motor_inactivo_declarado=True, revisor_declarado="Prueba", motivo="Doble")

    def test_cierre_no_confirmado_es_error(self):
        plan = self.plan02()
        ver, prep = self.preparar(plan, modelo_desde_expectativa(v.expectativa_desde_plan(plan)), FALSO_CIERRE="1")
        with self.assertRaises(ad.ErrorPuente):
            ver.ejecutar_verificacion(prep, confirmar_lectura=True)
        respuesta = json.loads((prep.solicitud.carpeta / "respuesta.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(respuesta["error"]["tipo"], "cierre_propio")

    def test_firma_distinta_detiene_antes_de_crear_instancia(self):
        plan = self.plan02()
        ver, prep = self.preparar(plan, modelo_desde_expectativa(v.expectativa_desde_plan(plan)), dll=self.dll_firma)
        with self.assertRaises(ad.ErrorPuente) as ctx:
            ver.ejecutar_verificacion(prep, confirmar_lectura=True)
        self.assertEqual(ctx.exception.codigo_proceso, 42)
        self.assertNotIn("CreateObjectProgID", self.llamadas())


class FirmasTests(unittest.TestCase):
    def firmas_script(self):
        texto = v.SCRIPT.read_bytes().decode("utf-8-sig")
        bloque = re.search(r"\$Firmas = \[ordered\]@\{(.*?)\n\}", texto, re.S).group(1)
        return dict(re.findall(r"'([^']+)'\s*=\s*'([^']+)'", bloque))

    def test_lista_blanca_solo_lectores_y_ciclo_de_vida(self):
        firmas = self.firmas_script()
        self.assertEqual(len(firmas), FIRMAS_LECTOR)
        ciclo = {"cHelper.CreateObjectProgID", "cOAPI.ApplicationStart", "cOAPI.Hide", "cOAPI.ApplicationExit", "cFile.OpenFile",
                 "cSapModel.GetModelFilename", "cSapModel.GetPresentUnits"}
        for clave in set(firmas) - ciclo:
            self.assertTrue(clave.split(".")[1].startswith("Get"), clave)
        texto = v.SCRIPT.read_bytes().decode("utf-8-sig")
        for prohibido in ("RunAnalysis", ".Save", "SetPresentUnits(", "GetObject(", "Invoke-Expression", "ExecutionPolicy"):
            self.assertNotIn(prohibido, texto)
        self.assertIn("ApplicationExit' $app @($false)", texto)
        self.assertEqual(firmas["cAreaObj.GetLoadUniform"], "Int32 (String Name, Int32& NumberItems, String[]& AreaName, "
                         "String[]& LoadPat, String[]& CSys, Int32[]& Dir, Double[]& Value, eItemType ItemType)")

    @unittest.skipUnless(ad.DLL_ETABS.is_file() and ad.POWERSHELL_51.is_file(), "requiere ETABSv1.dll y Windows PowerShell 5.1")
    def test_firmas_iguales_a_la_dll_instalada(self):
        # Solo metadatos por reflexión; no inicia ETABS.
        firmas = self.firmas_script()
        entorno = dict(os.environ, D2M_DLL=str(ad.DLL_ETABS), D2M_METODOS=";".join(firmas), D2M_ENUMS="eUnits")
        proceso = subprocess.run([str(ad.POWERSHELL_51), "-NoProfile", "-NonInteractive", "-EncodedCommand",
                                  base64.b64encode(o._SCRIPT_REFLEXION.encode("utf-16-le")).decode()],
                                 capture_output=True, env=entorno, timeout=180, stdin=subprocess.DEVNULL)
        self.assertEqual(proceso.returncode, 0, proceso.stderr[-500:])
        reflejado = json.loads(proceso.stdout.decode("utf-8-sig"))["metodos"]
        for clave, firma in firmas.items():
            encontradas = reflejado.get(clave) or []
            if len(encontradas) == 2 and isinstance(encontradas[0], str):
                encontradas = [encontradas]
            textos = [f"{r} (" + ", ".join(p if isinstance(p, list) else ([p] if p else [])) + ")" for r, p in encontradas]
            self.assertIn(firma, textos, clave)


if __name__ == "__main__":
    unittest.main()
