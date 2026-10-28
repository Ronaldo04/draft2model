"""Plan geométrico previo a ETABS con datos sintéticos, no planos reales."""

import contextlib
import copy
import hashlib
import io
import json
import math
import tempfile
import unittest
from pathlib import Path

from draft2model.contratos import huella_contenido
from draft2model.plan_modelado import (
    ESTADO_APROBACION_VIGENTE,
    ESTADO_CON_FALTANTES,
    ESTADO_INCONSISTENTE,
    ESTADO_SIN_APROBACION,
    main,
    preparar_plan_modelado,
    serializar,
)
from draft2model.validacion_geometria import cargar_geometria, validar_geometria

RAIZ = Path(__file__).resolve().parents[1]
GEOMETRIA_EJEMPLO = RAIZ / "examples" / "geometria_sintetica.json"
PLAN_EJEMPLO = RAIZ / "examples" / "plan_modelado_sintetico.json"


def geometria(unidad="m"):
    """Valores diádicos (exactos en binario) para comparar coordenadas sin tolerancias.

    Cota inferior negativa válida, un muro ortogonal y uno oblicuo 3-4-5.
    """
    f = {"m": 1, "cm": 100, "mm": 1000}[unidad]
    return {
        "contrato": "draft2model.geometria",
        "version_contrato": "0.1.0",
        "id": "sintetico-plan",
        "unidad_longitud": unidad,
        "procedencia": {"tipo": "sintetico", "descripcion": "Datos sintéticos de prueba."},
        "niveles": [{"id": "N0", "cota": -0.5 * f}, {"id": "N1", "cota": 2.5 * f}],
        "nodos": [
            {"id": "A", "x": 0 * f, "y": 0 * f},
            {"id": "B", "x": 4 * f, "y": 0 * f},
            {"id": "D", "x": 1 * f, "y": 1 * f},
            {"id": "E", "x": 4 * f, "y": 5 * f},
        ],
        "muros": [
            {"id": "M1", "nodo_inicio": "A", "nodo_fin": "B", "nivel_inferior": "N0",
             "nivel_superior": "N1", "espesor": 0.25 * f},
            {"id": "M2", "nodo_inicio": "D", "nodo_fin": "E", "nivel_inferior": "N0",
             "nivel_superior": "N1", "espesor": 0.125 * f,
             "procedencia": {"tipo": "sintetico", "descripcion": "Muro oblicuo sintético."}},
        ],
        "faltantes": [],
        "revision": {"estado": "borrador", "aprobacion": None},
    }


def aprobar(data):
    data["revision"] = {
        "estado": "aprobado",
        "aprobacion": {"declarada_por": "Revisor sintético", "fecha": "2026-10-15",
                       "huella_contenido": huella_contenido(data)},
    }
    return data


def faltante(coleccion, ident, campo):
    return {"coleccion": coleccion, "id": ident, "campo": campo, "descripcion": "Dato desconocido."}


class PlanModeladoTests(unittest.TestCase):
    def superficie(self, plan, muro_id):
        return next(s for s in plan["superficies"] if s["muro_id"] == muro_id)

    # -- coordenadas -------------------------------------------------------
    def test_vertices_y_orden_explicitos(self):
        plan = preparar_plan_modelado(geometria())
        self.assertEqual(plan["orden_vertices"], ["inicio_inferior", "fin_inferior", "fin_superior", "inicio_superior"])
        m1 = self.superficie(plan, "M1")
        self.assertEqual(m1["vertices_m"], [[0.0, 0.0, -0.5], [4.0, 0.0, -0.5], [4.0, 0.0, 2.5], [0.0, 0.0, 2.5]])
        self.assertEqual((m1["longitud_m"], m1["altura_m"], m1["area_bruta_m2"], m1["espesor_m"]), (4.0, 3.0, 12.0, 0.25))
        self.assertEqual((m1["nodo_inicio"], m1["nodo_fin"], m1["nivel_inferior"], m1["nivel_superior"]),
                         ("A", "B", "N0", "N1"))
        self.assertEqual(m1["naturaleza"], "propuesta_geometrica")

    def test_muro_oblicuo_y_cota_negativa(self):
        m2 = self.superficie(preparar_plan_modelado(geometria()), "M2")
        self.assertEqual(m2["vertices_m"], [[1.0, 1.0, -0.5], [4.0, 5.0, -0.5], [4.0, 5.0, 2.5], [1.0, 1.0, 2.5]])
        self.assertEqual((m2["longitud_m"], m2["altura_m"], m2["area_bruta_m2"], m2["espesor_m"]), (5.0, 3.0, 15.0, 0.125))
        self.assertEqual(m2["procedencia"], {"tipo": "sintetico", "descripcion": "Muro oblicuo sintético."})
        self.assertEqual(m2["procedencia_declarada_en"], "muro")
        self.assertEqual(self.superficie(preparar_plan_modelado(geometria()), "M1")["procedencia_declarada_en"], "contrato")

    def test_equivalencia_m_cm_mm(self):
        planes = {u: preparar_plan_modelado(geometria(u)) for u in ("m", "cm", "mm")}
        for unidad in ("cm", "mm"):
            with self.subTest(unidad=unidad):
                self.assertEqual(planes[unidad]["superficies"], planes["m"]["superficies"])
                self.assertEqual(planes[unidad]["unidades"]["unidad_longitud_origen"], unidad)
                self.assertEqual(planes[unidad]["unidades"]["longitud"], "m")

    # -- entradas inconsistentes ------------------------------------------
    def assertDiagnostico(self, data, codigo):
        plan = preparar_plan_modelado(data)
        self.assertEqual(plan["estado_origen"], ESTADO_INCONSISTENTE)
        self.assertEqual((plan["superficies"], plan["omisiones"], plan["cobertura"]), ([], [], "sin_superficies"))
        self.assertIsNone(plan["origen"]["huella_contenido"])
        self.assertIsNone(plan["procedencia"])
        self.assertFalse(plan["ejecutable_en_etabs"])
        self.assertIn(codigo, {e["codigo"] for e in plan["origen"]["validacion"]["errores"]})
        self.assertTrue(any("inconsistente" in b for b in plan["bloqueos"]))
        json.dumps(plan, allow_nan=False)
        return plan

    def test_referencias_invalidas_longitud_nula_y_altura_no_positiva(self):
        data = geometria()
        data["muros"][0]["nodo_fin"] = "Z"
        self.assertDiagnostico(data, "referencia_rota")
        data = geometria()
        data["nodos"][1]["x"] = 0
        self.assertDiagnostico(data, "longitud_nula")
        data = geometria()
        data["niveles"][1]["cota"] = -0.5
        self.assertDiagnostico(data, "altura_no_positiva")
        data = geometria()
        data["niveles"][1]["cota"] = -1.0
        self.assertDiagnostico(data, "altura_no_positiva")

    def test_entradas_no_objeto(self):
        for data in (None, [], "geometria", 5):
            with self.subTest(data=data):
                plan = self.assertDiagnostico(data, "tipo_invalido")
                self.assertIsNone(plan["caso"])

    # -- faltantes y propuestas parciales ---------------------------------
    def test_espesor_faltante_produce_propuesta_parcial(self):
        data = geometria()
        data["muros"][1]["espesor"] = None
        data["faltantes"] = [faltante("muros", "M2", "espesor")]
        plan = preparar_plan_modelado(data)
        self.assertEqual(plan["estado_origen"], ESTADO_CON_FALTANTES)
        self.assertEqual([s["muro_id"] for s in plan["superficies"]], ["M1"])
        self.assertEqual(plan["omisiones"], [{"muro_id": "M2", "motivo": "datos_faltantes",
                                              "faltantes": [{"coleccion": "muros", "id": "M2", "campo": "espesor"}]}])
        self.assertEqual(plan["cobertura"], "parcial")
        self.assertTrue(any("1 de 2" in b for b in plan["bloqueos"]))

    def test_cota_faltante_omite_todos_los_muros_que_la_usan(self):
        data = geometria()
        data["niveles"][1]["cota"] = None
        data["muros"][1]["espesor"] = None
        data["faltantes"] = [faltante("niveles", "N1", "cota"), faltante("muros", "M2", "espesor")]
        plan = preparar_plan_modelado(data)
        self.assertEqual(plan["superficies"], [])
        self.assertEqual(plan["cobertura"], "sin_superficies")
        self.assertEqual(plan["omisiones"], [
            {"muro_id": "M1", "motivo": "datos_faltantes",
             "faltantes": [{"coleccion": "niveles", "id": "N1", "campo": "cota"}]},
            {"muro_id": "M2", "motivo": "datos_faltantes",
             "faltantes": [{"coleccion": "muros", "id": "M2", "campo": "espesor"},
                           {"coleccion": "niveles", "id": "N1", "campo": "cota"}]},
        ])
        self.assertNotIn("2.5", json.dumps(plan["omisiones"]))  # no se inventa una cota

    def test_faltante_general_mantiene_estado_con_faltantes(self):
        data = geometria()
        data["faltantes"] = [{"descripcion": "Láminas de cortes no disponibles."}]
        plan = preparar_plan_modelado(data)
        self.assertEqual((plan["estado_origen"], plan["cobertura"]), (ESTADO_CON_FALTANTES, "completa"))
        self.assertEqual(plan["omisiones"], [])

    # -- aprobación ---------------------------------------------------------
    def test_aprobacion_ausente_vigente_y_desactualizada(self):
        sin = preparar_plan_modelado(geometria())
        self.assertEqual(sin["estado_origen"], ESTADO_SIN_APROBACION)
        self.assertFalse(sin["origen"]["revision"]["aprobacion_registrada"])

        vigente = preparar_plan_modelado(aprobar(geometria()))
        self.assertEqual(vigente["estado_origen"], ESTADO_APROBACION_VIGENTE)
        self.assertTrue(vigente["origen"]["revision"]["aprobacion_vigente"])
        self.assertTrue(vigente["origen"]["validacion"]["disponible_para_modelado"])

        data = aprobar(geometria())
        data["muros"][0]["espesor"] = 0.5
        vieja = preparar_plan_modelado(data)
        self.assertEqual(vieja["estado_origen"], ESTADO_SIN_APROBACION)
        self.assertEqual((vieja["origen"]["revision"]["aprobacion_registrada"],
                          vieja["origen"]["revision"]["aprobacion_vigente"]), (True, False))
        self.assertTrue(any("huella distinta" in b for b in vieja["origen"]["validacion"]["bloqueos"]))

        for plan in (sin, vigente, vieja):
            with self.subTest(estado=plan["estado_origen"]):
                self.assertIsNone(plan["aprobacion_plan"])
                self.assertFalse(plan["ejecutable_en_etabs"])
                self.assertNotIn("declarada_por", json.dumps(plan))  # la aprobación no se copia al plan
                self.assertTrue(any("ejecutable_en_etabs es false" in b for b in plan["bloqueos"]))
                self.assertTrue(any("no tiene revisión ni aprobación propias" in b for b in plan["bloqueos"]))

    # -- pureza e independencia ---------------------------------------------
    def test_entrada_intacta_y_sin_referencias_compartidas(self):
        for data in (geometria("cm"), aprobar(geometria()), {"id": "x", "nodos": [{"x": math.nan}]}):
            with self.subTest(caso=data.get("id")):
                antes = copy.deepcopy(data)
                plan = preparar_plan_modelado(data)
                self.assertEqual(repr(data), repr(antes))
                if plan["superficies"]:
                    self.assertIsNot(plan["procedencia"], data["procedencia"])
                    self.assertIsNot(self.superficie(plan, "M2")["procedencia"], data["muros"][1]["procedencia"])
                    plan["procedencia"]["tipo"] = "alterado"
                    self.superficie(plan, "M2")["procedencia"]["descripcion"] = "alterado"
                    plan["superficies"][0]["vertices_m"][0][0] = 99.0
                    self.assertEqual(repr(data), repr(antes))

    def test_determinista_y_json_estricto(self):
        def sin_constantes(nombre):
            raise ValueError(nombre)

        for data in (geometria(), geometria("mm"), aprobar(geometria()), {"id": "roto"}):
            with self.subTest(caso=data.get("unidad_longitud")):
                a, b = preparar_plan_modelado(data), preparar_plan_modelado(copy.deepcopy(data))
                self.assertEqual(a, b)
                self.assertEqual(serializar(a), serializar(b))
                self.assertEqual(json.loads(serializar(a), parse_constant=sin_constantes), a)
                self.assertFalse(a["ejecutable_en_etabs"])

    # -- representabilidad numérica ------------------------------------------
    # Longitud, altura y normalización no representables los rechaza el validador:
    # el plan queda inconsistente y sin superficies. El área es el único derivado
    # propio del plan y se omite explícitamente si no es representable.
    def con(self, cambios_niveles=None, nodos_extra=(), muro_extra=None, unidad="m"):
        data = geometria(unidad)
        for ident, cota in (cambios_niveles or {}).items():
            next(n for n in data["niveles"] if n["id"] == ident)["cota"] = cota
        data["nodos"].extend(nodos_extra)
        if muro_extra:
            data["muros"].append(muro_extra)
        return data

    def muro_extra(self, inicio="X", fin="Y", espesor=0.25):
        return {"id": "M9", "nodo_inicio": inicio, "nodo_fin": fin, "nivel_inferior": "N0",
                "nivel_superior": "N1", "espesor": espesor}

    def test_desbordamiento_de_longitud_es_origen_inconsistente(self):
        data = self.con(nodos_extra=({"id": "X", "x": 1.7e308, "y": 0}, {"id": "Y", "x": -1.7e308, "y": 0}),
                        muro_extra=self.muro_extra())
        plan = self.assertDiagnostico(data, "longitud_no_representable")
        self.assertIn("$.muros[2]", {e["ruta"] for e in plan["origen"]["validacion"]["errores"]})

    def test_desbordamiento_de_altura_es_origen_inconsistente(self):
        self.assertDiagnostico(self.con(cambios_niveles={"N0": -1.7e308, "N1": 1.7e308}), "altura_no_representable")

    def test_area_no_representable_con_longitud_y_altura_finitas(self):
        detalle = ("Resultado no finito o no positivo en metros (desbordamiento o subdesbordamiento); "
                   "no se sustituye por otro valor.")
        # 1e200 × 1e200 desborda; el validador acepta ambos factores porque son finitos.
        data = self.con(cambios_niveles={"N0": 0, "N1": 1e200},
                        nodos_extra=({"id": "X", "x": 0, "y": 0}, {"id": "Y", "x": 1e200, "y": 0}),
                        muro_extra=self.muro_extra())
        self.assertTrue(validar_geometria(data).consistente)
        plan = preparar_plan_modelado(data)
        omision = next(o for o in plan["omisiones"] if o["muro_id"] == "M9")
        self.assertEqual(omision, {"muro_id": "M9", "motivo": "calculo_derivado_no_valido",
                                   "valores_no_validos": ["area_bruta_m2"], "detalle": detalle})
        self.assertNotIn("M9", [s["muro_id"] for s in plan["superficies"]])
        json.dumps(plan, allow_nan=False)

        # 1e-200 × 1e-200 se redondea a 0.0: tampoco se presenta como área válida.
        data = self.con(cambios_niveles={"N0": 0, "N1": 1e-200},
                        nodos_extra=({"id": "X", "x": 0, "y": 0}, {"id": "Y", "x": 1e-200, "y": 0}),
                        muro_extra=self.muro_extra())
        self.assertTrue(validar_geometria(data).consistente)
        self.assertEqual(1e-200 * 1e-200, 0.0)
        plan = preparar_plan_modelado(data)
        # M1 (4 × 1e-200) y M2 (5 × 1e-200) siguen siendo representables; solo M9 se omite.
        self.assertEqual([(s["muro_id"], s["area_bruta_m2"]) for s in plan["superficies"]],
                         [("M1", 4e-200), ("M2", 5e-200)])
        self.assertEqual(plan["omisiones"], [{"muro_id": "M9", "motivo": "calculo_derivado_no_valido",
                                              "valores_no_validos": ["area_bruta_m2"], "detalle": detalle}])
        self.assertEqual(plan["cobertura"], "parcial")
        json.dumps(plan, allow_nan=False)

    def test_subdesbordamiento_al_normalizar_es_origen_inconsistente(self):
        # 1e-323 mm es positivo en la entrada, pero al pasar a metros se redondea a 0.0.
        data = self.con(unidad="mm", muro_extra=self.muro_extra("A", "E", espesor=1e-323))
        plan = self.assertDiagnostico(data, "normalizacion_a_cero")
        self.assertIn("$.muros[2].espesor", {e["ruta"] for e in plan["origen"]["validacion"]["errores"]})

    def test_colapso_tras_normalizar_es_origen_inconsistente(self):
        a = 2.0**-1060
        b = math.nextafter(a, 1.0)
        data = self.con(unidad="mm", nodos_extra=({"id": "X", "x": a, "y": 0}, {"id": "Y", "x": b, "y": 0}),
                        muro_extra=self.muro_extra())
        self.assertDiagnostico(data, "longitud_nula_tras_normalizar")

    def test_enteros_enormes_no_lanzan_excepciones(self):
        for cambio, codigo in (
            (lambda d: d["nodos"][0].update(x=10**1000), "fuera_de_rango"),
            (lambda d: d["niveles"][1].update(cota=-(10**1000)), "fuera_de_rango"),
            (lambda d: d["muros"][0].update(espesor=10**400), "fuera_de_rango"),
        ):
            with self.subTest(codigo=codigo):
                data = geometria()
                cambio(data)
                self.assertDiagnostico(data, codigo)

    def test_unidad_con_tipos_json_invalidos(self):
        for unidad in ([], {}, None, True, False, 5, 2.5, ["m"], {"m": 1}, "M", ""):
            with self.subTest(unidad=unidad):
                data = geometria()
                data["unidad_longitud"] = unidad
                plan = self.assertDiagnostico(data, "unidad_no_admitida")
                self.assertIsNone(plan["unidades"]["unidad_longitud_origen"])
                self.assertEqual(plan["unidades"]["longitud"], "m")
        data = geometria()
        del data["unidad_longitud"]
        self.assertIsNone(self.assertDiagnostico(data, "campo_ausente")["unidades"]["unidad_longitud_origen"])

    # -- ejemplo versionado --------------------------------------------------
    def test_ejemplo_reproducible_desde_geometria_sintetica(self):
        hash_entrada = hashlib.sha256(GEOMETRIA_EJEMPLO.read_bytes()).hexdigest()
        plan = preparar_plan_modelado(cargar_geometria(GEOMETRIA_EJEMPLO))
        self.assertEqual(PLAN_EJEMPLO.read_bytes().decode("utf-8"), serializar(plan))
        self.assertEqual(hashlib.sha256(GEOMETRIA_EJEMPLO.read_bytes()).hexdigest(), hash_entrada)
        self.assertEqual(plan["estado_origen"], ESTADO_CON_FALTANTES)
        self.assertEqual([s["muro_id"] for s in plan["superficies"]], ["M1", "M2", "M3"])
        self.assertEqual(plan["omisiones"], [{"muro_id": "M4", "motivo": "datos_faltantes",
                                              "faltantes": [{"coleccion": "muros", "id": "M4", "campo": "espesor"}]}])
        self.assertTrue(plan["origen"]["validacion"]["datos_sinteticos"])
        self.assertEqual(plan["procedencia"]["tipo"], "sintetico")

    def test_comando_de_regeneracion(self):
        with tempfile.TemporaryDirectory() as temp:
            salida = Path(temp) / "plan.json"
            silencio = io.StringIO()
            with contextlib.redirect_stdout(silencio), contextlib.redirect_stderr(silencio):
                self.assertEqual(main([str(GEOMETRIA_EJEMPLO), "--salida", str(salida)]), 0)
                self.assertEqual(salida.read_bytes(), PLAN_EJEMPLO.read_bytes())
                previo = salida.read_bytes()
                self.assertEqual(main([str(GEOMETRIA_EJEMPLO), "--salida", str(salida)]), 1)  # no sobrescribe
                self.assertEqual(salida.read_bytes(), previo)
                inconsistente = Path(temp) / "rota.json"
                data = geometria()
                data["muros"][0]["nodo_fin"] = "Z"
                inconsistente.write_text(json.dumps(data), encoding="utf-8")
                self.assertEqual(main([str(inconsistente), "--salida", str(Path(temp) / "diag.json")]), 2)
                ilegible = Path(temp) / "ilegible.json"
                ilegible.write_text('{"id": NaN}', encoding="utf-8")
                self.assertEqual(main([str(ilegible), "--salida", str(Path(temp) / "x.json")]), 1)
                self.assertFalse((Path(temp) / "x.json").exists())


if __name__ == "__main__":
    unittest.main()
