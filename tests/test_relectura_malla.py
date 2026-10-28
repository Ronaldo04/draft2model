"""Relectura independiente del plan 0.4 (malla) guardado y reabierto, con DOBLES; nunca ETABS real, red ni claves.

- Plan 0.4 GENERADO desde configuración y geometría reales en disco (dos hosts conectados, huecos, viga conforme y
  corte Z), más el plan real del ensayo 194 como dato de solo lectura (inventario y expectativa).
- Lo «leído» usa las representaciones observadas en ETABS 21.1 (inicio cíclico rotado en GetPoints, ensayo 191;
  GetLoadUniform Dir6/-2 releído Dir10/+2, ensayo 192 / CSI 9398). La comprobación de malla recalcula áreas,
  orientación, conformidad, subframes y resultantes desde coordenadas, contornos y cargas LEÍDOS.
- Puente: script PowerShell REAL en modo doble contra un ETABSv1 FALSO que reabre un «EDB» JSON persistido.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from draft2model import operaciones_etabs as o
from draft2model import verificacion_modelo_guardado as v
from tests import test_integracion_malla as tim
from tests import test_verificacion_modelo_guardado as tvm

CRITERIOS = tvm.CRITERIOS
RAIZ = Path(__file__).resolve().parents[1]
PLAN_194 = RAIZ / "tmp" / "n194" / "plan.json"


def plan_malla():
    """Plan 0.4 del recorrido normal desde configuración aprobada en disco (gestión real, sin ETABS)."""
    h = tim.CasoMalla("setUp")
    h.setUp()
    try:
        _, _, aprobada = h.registrar_aprobada("conectados_corte")
        return o.generar_plan_por_version(h.raiz, aprobada, **h.opciones(aprobada)).datos
    finally:
        h.doCleanups()


def modelo_etabs(exp):
    """«EDB» con las representaciones observadas de ETABS 21.1, no una copia literal de la expectativa."""
    m = tvm.modelo_desde_expectativa(exp)
    for n, anillo in m["areas"]["puntos"].items():
        m["areas"]["puntos"][n] = anillo[1:] + anillo[:1]  # ensayo 191: otro inicio, mismo sentido
    for cargas in m["cargas_area"].values():
        for c in cargas:
            if c["csys"] == "Global" and c["dir"] == 6:
                c.update(dir=10, valor=-c["valor"])  # ensayo 192 / CSI 9398: gravedad con signo invertido
    for cargas in m["cargas_frame"].values():
        for c in cargas:
            if c["csys"] == "Global" and c["dir"] == 6 and c["tipo"] == 1:
                c.update(dir=10, val1=-c["val1"], val2=-c["val2"])
    return m


class Base:
    @classmethod
    def setUpClass(cls):
        cls.plan = plan_malla()
        cls.exp = v.expectativa_desde_plan(cls.plan)

    def leer(self, modelo, **kw):
        return v.comparar(self.exp, tvm.lecturas(modelo, **kw), CRITERIOS)

    def modelo(self):
        return modelo_etabs(self.exp)

    def motivos(self, r, cat="malla"):
        return [d["motivo"] for d in r["discrepancias"] if d["categoria"] == cat]


class ExpectativaMallaTests(Base, unittest.TestCase):
    def test_inventario_completo_sin_lectores_confundidos_con_mutaciones(self):
        inv = self.exp["inventario"]
        self.assertEqual([x for x in inv if x["cobertura"] == "sin_lector"], [])
        nuevos = {"cPointObj.GetRestraint", "cAreaObj.GetLoadUniform", "cPropMaterial.GetMassSource_1", "cFrameObj.GetPoints"}
        for x in inv:
            if x["metodo"] in nuevos:
                self.assertEqual(x["cobertura"], "excluida", x)  # lectura del plan, no mutación
        mutadores = {x["metodo"] for x in inv if x["cobertura"] == "comprobada"}
        self.assertTrue({"cAreaObj.AddByPoint", "cFrameObj.AddByPoint", "cPointObj.SetRestraint", "cPointObj.SetDiaphragm",
                         "cAreaObj.SetLoadUniform", "cFrameObj.SetLoadDistributed", "cPropMaterial.SetMassSource_1"} <= mutadores)
        self.assertNotIn("cAreaObj.SetOpening", {x["metodo"] for x in inv})
        m = self.exp["malla"]
        self.assertEqual(set(m["hosts"]), {"S1", "S2"})
        self.assertEqual(sorted(t for h in m["hosts"].values() for t in h["triangulos"]),
                         sorted(n for n, c in self.exp["clase_area"].items() if c == "superficie"))
        self.assertTrue(m["conexiones"][0]["nodos"]); self.assertEqual(m["conexiones"][0]["sin_resolver"], [])
        self.assertEqual(m["subframes"][0]["frame"], "VIGA1")
        self.assertEqual({c["carga"] for c in m["cargas"]}, {"Q1", "WV"})
        self.assertEqual(self.exp["origen_plan"]["huella_plan"], self.plan["huella_plan"])

    # La comprobación del plan real 194 (evidencia de tmp/) está en scripts/verificar_evidencia_ruta201.py.

    def test_expectativas_incoherentes_o_plan_alterado_no_son_fuente(self):
        cambios = {
            "huella": lambda p: p.update(huella_plan="0" * 64),
            "partes de conservación": lambda p: p["conservacion"]["cargas"][0]["partes"].pop(),
            "subframe con extremos distintos": lambda p: p["malla"]["frames_subdivididos"][0]["nodos"].reverse(),
            "sin sección malla": lambda p: p.pop("malla"),
        }
        for nombre, cambio in cambios.items():
            with self.subTest(nombre):
                p = copy.deepcopy(self.plan); cambio(p)
                if nombre != "huella":
                    p["huella_plan"] = o.huella_plan(p)
                with self.assertRaises(v.ErrorVerificacion):
                    v.expectativa_desde_plan(p)

    def test_legado_sin_seccion_malla(self):
        plan = tvm.Planes().plan_aberturas()
        exp = v.expectativa_desde_plan(plan)
        self.assertNotIn("malla", exp)
        r = v.comparar(exp, tvm.lecturas(tvm.modelo_desde_expectativa(exp)), CRITERIOS)
        self.assertEqual(r["estado"], "verificado")
        self.assertNotIn("malla", r); self.assertNotIn("malla", r["alcance"])


class ComparacionMallaTests(Base, unittest.TestCase):
    def test_representaciones_etabs_verificadas_sin_afirmar_ingenieria(self):
        r = self.leer(self.modelo())
        self.assertEqual(r["estado"], "verificado", r["discrepancias"] + r["incompletos"])
        self.assertTrue(r["verificacion_global_del_plan"])
        self.assertIn("malla", r["alcance"]); self.assertEqual(r["cobertura"]["malla"], "completa")
        for h, x in r["malla"]["hosts"].items():
            self.assertAlmostEqual(x["area_triangulos_leida_m2"], x["area_neta_fuente_m2"], places=10)
        self.assertFalse(r["aprueba_modelo"]); self.assertFalse(r["certifica_seguridad_estructural"])
        self.assertTrue(set(v.NO_AFIRMADOS_MALLA) <= set(r["controles_no_afirmados"]))

    def test_negativos_geometricos(self):
        m0 = self.modelo()
        tri_s1 = self.exp["malla"]["hosts"]["S1"]["triangulos"]
        nodos = self.exp["malla"]["conexiones"][0]["nodos"]
        compartido = next(n for n in nodos if n.startswith("M"))

        def invertir(m):
            t = tri_s1[0]; m["areas"]["puntos"][t] = m["areas"]["puntos"][t][::-1]

        def faltante(m):
            t = tri_s1[0]
            m["areas"]["nombres"].remove(t)
            for k in ("puntos", "propiedades", "ejes", "aberturas"):
                m["areas"][k].pop(t)
            m["cargas_area"].pop(t); m["diafragmas_areas"].pop(t)

        def extra(m):  # material sobre un hueco: pieza adicional no esperada
            m["areas"]["nombres"].append("EXTRA"); m["areas"]["puntos"]["EXTRA"] = ["H1", "H2", "H3"]
            for k, val in (("propiedades", "LOSA20"), ("ejes", {"angulo_deg": 0.0, "avanzado": False}), ("aberturas", False)):
                m["areas"][k]["EXTRA"] = val
            m["cargas_area"]["EXTRA"] = []; m["diafragmas_areas"]["EXTRA"] = ""

        def roto(m):  # el muro usa un nodo duplicado en la misma posición: el borde deja de estar compartido
            m["puntos"]["nombres"].append(compartido + "b")
            m["puntos"]["coordenadas"][compartido + "b"] = list(m["puntos"]["coordenadas"][compartido])
            for t in self.exp["malla"]["hosts"]["S2"]["triangulos"]:
                m["areas"]["puntos"][t] = [compartido + "b" if x == compartido else x for x in m["areas"]["puntos"][t]]

        def colgante(m):  # un triángulo del piso salta el nodo compartido: queda dentro de su arista
            a, b = nodos[0], nodos[1]
            for t in tri_s1:
                anillo = m["areas"]["puntos"][t]
                if b in anillo and a in anillo:
                    m["areas"]["puntos"][t] = [nodos[2] if x == b else x for x in anillo]
                    return
            raise AssertionError("sin triángulo en el borde")
        casos = {"orientación invertida": (invertir, "orientación opuesta"), "pieza faltante": (faltante, None),
                 "pieza extra sobre hueco": (extra, None), "nodo compartido roto": (roto, "no compartido"),
                 "nodo colgante": (colgante, "dentro de una arista leída")}
        for nombre, (cambio, motivo) in casos.items():
            with self.subTest(nombre):
                m = copy.deepcopy(m0); cambio(m)
                r = self.leer(m)
                self.assertEqual(r["estado"], "discrepancias", nombre)
                self.assertFalse(r["verificado"])
                if motivo:
                    self.assertTrue(any(motivo in x for x in self.motivos(r)), self.motivos(r))

    def test_subframes(self):
        m0 = self.modelo()
        sub = self.exp["malla"]["subframes"][0]["subframes"]
        for nombre in ("ausente", "conectividad"):
            with self.subTest(nombre):
                m = copy.deepcopy(m0)
                if nombre == "ausente":
                    s = sub[1]; m["frames"]["nombres"].remove(s)
                    for k in ("puntos", "secciones"):
                        m["frames"][k].pop(s)
                    m["cargas_frame"].pop(s)
                else:
                    m["frames"]["puntos"][sub[1]] = m["frames"]["puntos"][sub[1]][::-1]
                r = self.leer(m)
                self.assertEqual(r["estado"], "discrepancias")
                if nombre == "conectividad":
                    self.assertIn("subframes leídos no forman la cadena continua del frame original", self.motivos(r))

    def test_cargas_magnitud_signo_y_proyeccion(self):
        m0 = self.modelo()
        t = self.exp["malla"]["hosts"]["S1"]["triangulos"][0]
        s = self.exp["malla"]["subframes"][0]["subframes"][0]
        casos = {"magnitud": lambda m: m["cargas_area"][t][0].update(valor=m["cargas_area"][t][0]["valor"] * 1.1),
                 "signo": lambda m: m["cargas_area"][t][0].update(valor=-m["cargas_area"][t][0]["valor"]),
                 "magnitud frame": lambda m: m["cargas_frame"][s][0].update(val1=m["cargas_frame"][s][0]["val1"] * 2,
                                                                            val2=m["cargas_frame"][s][0]["val2"] * 2)}
        for nombre, cambio in casos.items():
            with self.subTest(nombre):
                m = copy.deepcopy(m0); cambio(m)
                r = self.leer(m)
                self.assertEqual(r["estado"], "discrepancias")
                self.assertTrue(any(d["categoria"] == "malla" and d["campo"].startswith(("F", "M")) for d in r["discrepancias"]), r["discrepancias"])
        # Proyectada (Dir11 → 9): no se reinterpreta como carga completa; queda discrepancia de clave e incompleto de malla.
        m = copy.deepcopy(m0); m["cargas_area"][t][0]["dir"] = 11
        r = self.leer(m)
        self.assertEqual(r["estado"], "discrepancias")
        self.assertTrue(any("proyectada" in x["motivo"] for x in r["incompletos"] if x["categoria"] == "malla"))

    def test_apoyo_masa_propiedad_y_diafragma(self):
        m0 = self.modelo()
        derivado = next(n for n in self.exp["puntos"] if n.startswith(("MN_", "MC_")))
        t = self.exp["malla"]["hosts"]["S2"]["triangulos"][0]
        casos = {"apoyos": lambda m: m["apoyos"].__setitem__(derivado, [not x for x in m["apoyos"][derivado]]),
                 "fuente_masa": lambda m: m["fuente_masa"].update(incluir_elementos=not m["fuente_masa"]["incluir_elementos"]),
                 "propiedades_area": lambda m: m["propiedades_area"]["losas"]["LOSA20"].update(espesor=0.25),
                 "areas": lambda m: m["areas"]["propiedades"].__setitem__(t, "LOSA20"),
                 "diafragmas": lambda m: m["diafragmas_puntos"][derivado].update(diafragma="OTRO")}
        for cat, cambio in casos.items():
            with self.subTest(cat):
                m = copy.deepcopy(m0); cambio(m)
                r = self.leer(m)
                self.assertEqual(r["estado"], "discrepancias")
                self.assertTrue(any(d["categoria"] == cat for d in r["discrepancias"]), r["discrepancias"])

    def test_lectura_parcial_y_unidades_no_afirman_malla(self):
        m = self.modelo()
        t = self.exp["malla"]["hosts"]["S1"]["triangulos"][0]
        m["areas"]["puntos"].pop(t)  # GetPoints devolvió código distinto de 0
        r = self.leer(m, retornos=[{"metodo": "cAreaObj.GetPoints", "objeto": t, "codigo": 1}])
        self.assertEqual(r["estado"], "incompleto")
        self.assertEqual(r["cobertura"]["malla"], "incompleta")
        r = v.comparar(self.exp, tvm.lecturas(tvm.a_n_mm(self.modelo()), unidades="N_mm_C"), CRITERIOS)
        self.assertEqual(r["estado"], "verificado", r['discrepancias']+r['incompletos'])
        self.assertEqual(r['cobertura']['malla'], 'completa')
        r = v.comparar(self.exp, tvm.lecturas(self.modelo(), unidades="kip_ft_F"), CRITERIOS)
        self.assertNotEqual(r["estado"], "verificado")
        self.assertTrue(any("conversión dimensional" in x["motivo"] for x in r["incompletos"] if x["categoria"] == "malla"))

    def test_operacion_modificadora_sin_lector_impide_global(self):
        with mock.patch.dict(v.INVENTARIO, {}, clear=False):
            del v.INVENTARIO["cPointObj.SetDiaphragm"]
            exp = v.expectativa_desde_plan(self.plan)
        r = v.comparar(exp, tvm.lecturas(modelo_etabs(exp)), CRITERIOS)
        self.assertEqual(r["estado"], "incompleto")
        self.assertFalse(r["verificacion_global_del_plan"])
        self.assertTrue(r["cobertura_plan"]["sin_lector"])
        self.assertIn("cPointObj.SetDiaphragm", v.INVENTARIO)  # el parche se retira


@unittest.skipUnless(tvm.POWERSHELL, "requiere Windows PowerShell 5.1")
class PuenteMallaTests(Base, unittest.TestCase):
    """Script PowerShell REAL contra ETABSv1 FALSO que reabre un EDB JSON persistido; no es ETABS."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._dir = tempfile.TemporaryDirectory()
        carpeta = Path(cls._dir.name)
        causa = tvm.directiva_impide_file(carpeta)
        if causa:
            cls._dir.cleanup()
            raise unittest.SkipTest("Entorno: la directiva de ejecución efectiva impide '-File': " + causa)
        try:
            cls.dll = tvm.compilar(tvm.CS_FALSO.replace("ITEMTYPE", "eItemType"), carpeta / "ETABSv1_malla.dll")
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

    def verificar(self, modelo):
        self.edb.write_bytes(json.dumps(modelo).encode("utf-8"))
        trabajo = self.dir / ("t" + str(len(list(self.dir.glob("t*")))))
        trabajo.mkdir()
        config = v.configuracion_doble_powershell(trabajo, self.dll, timeout_s=240, entorno={"FALSO_LOG": str(self.log)})
        ver = v.VerificadorModeloGuardado(config)
        prep = ver.preparar_verificacion(self.edb, v._sha(self.edb.read_bytes()), self.plan, criterios=CRITERIOS)
        return ver.ejecutar_verificacion(prep, confirmar_lectura=True)

    def test_reabierto_verificado_y_alterado_con_discrepancias(self):
        r = self.verificar(self.modelo())
        self.assertEqual(r.estado, "verificado", r.resultado["discrepancias"] + r.resultado["incompletos"])
        self.assertEqual(r.resultado["cobertura"]["malla"], "completa")
        llamadas = self.log.read_text(encoding="utf-8").split()
        self.assertNotIn("Set", " ".join(llamadas).replace("SetPresent", ""))  # ningún setter durante la relectura
        m = self.modelo()
        t = self.exp["malla"]["hosts"]["S1"]["triangulos"][0]
        m["areas"]["puntos"][t] = m["areas"]["puntos"][t][::-1]
        r = self.verificar(m)
        self.assertEqual(r.estado, "discrepancias")
        self.assertTrue(any(d["categoria"] == "malla" for d in r.resultado["discrepancias"]))


if __name__ == "__main__":
    unittest.main()
