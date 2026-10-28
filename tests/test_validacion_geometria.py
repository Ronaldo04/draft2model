"""Pruebas del contrato de geometría v0.1 con datos sintéticos, no planos reales."""

import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from draft2model.contratos import huella_contenido
from draft2model.validacion_geometria import (
    ErrorLecturaGeometria,
    cargar_geometria,
    validar_archivo,
    validar_geometria,
)

EJEMPLO = Path(__file__).resolve().parents[1] / "examples" / "geometria_sintetica.json"


def sintetico(unidad="m"):
    """Rectángulo sintético 4 x 3 con altura 2.6, expresado en la unidad pedida."""
    f = {"m": 1, "cm": 100, "mm": 1000}[unidad]
    return {
        "contrato": "draft2model.geometria",
        "version_contrato": "0.1.0",
        "id": "sintetico-prueba",
        "unidad_longitud": unidad,
        "procedencia": {"tipo": "sintetico", "descripcion": "Datos sintéticos de prueba."},
        "niveles": [
            {"id": "N0", "cota": 0 * f},
            {"id": "N1", "cota": round(2.6 * f, 6)},
        ],
        "nodos": [
            {"id": "A", "x": 0 * f, "y": 0 * f},
            {"id": "B", "x": 4 * f, "y": 0 * f},
            {"id": "C", "x": 4 * f, "y": 3 * f},
            {"id": "D", "x": 0 * f, "y": 3 * f},
        ],
        "muros": [
            {"id": f"M{i}", "nodo_inicio": a, "nodo_fin": b, "nivel_inferior": "N0",
             "nivel_superior": "N1", "espesor": round(0.15 * f, 6)}
            for i, (a, b) in enumerate((("A", "B"), ("B", "C"), ("C", "D"), ("D", "A")), 1)
        ],
        "faltantes": [],
        "revision": {"estado": "borrador", "aprobacion": None},
    }


def aprobar(data):
    data["revision"] = {
        "estado": "aprobado",
        "aprobacion": {
            "declarada_por": "Revisor sintético de prueba",
            "fecha": "2026-10-13",
            "huella_contenido": huella_contenido(data),
        },
    }
    return data


class GeometriaTests(unittest.TestCase):
    def codigos(self, resultado):
        return {(h.ruta, h.codigo) for h in resultado.errores}

    def assertError(self, data, ruta, codigo):
        resultado = validar_geometria(data)
        self.assertFalse(resultado.consistente)
        self.assertFalse(resultado.disponible_para_modelado)
        self.assertIn((ruta, codigo), self.codigos(resultado), [str(e) for e in resultado.errores])
        self.assertIsNone(resultado.geometria_m)
        return resultado

    def test_caso_sintetico_valido(self):
        resultado = validar_geometria(sintetico())
        self.assertTrue(resultado.consistente, [str(e) for e in resultado.errores])
        self.assertTrue(resultado.datos_sinteticos)
        self.assertIn("datos_sinteticos", {h.codigo for h in resultado.advertencias})
        self.assertEqual(resultado.derivados_m["muros"]["M1"], {"longitud": 4.0, "altura": 2.6})
        self.assertEqual(resultado.derivados_m["muros"]["M2"]["longitud"], 3.0)
        json.dumps(resultado.a_dict(), allow_nan=False)

    def test_ejemplo_versionado_consistente_pero_no_disponible(self):
        resultado = validar_archivo(EJEMPLO)
        self.assertTrue(resultado.consistente, [str(e) for e in resultado.errores])
        self.assertFalse(resultado.disponible_para_modelado)
        self.assertEqual(
            [(f["id"], f["campo"]) for f in resultado.faltantes], [("M4", "espesor")]
        )
        self.assertIsNone(resultado.geometria_m["muros"][3]["espesor"])

    def test_conversion_equivalente_m_cm_mm(self):
        resultados = {u: validar_geometria(sintetico(u)) for u in ("m", "cm", "mm")}
        for unidad, resultado in resultados.items():
            with self.subTest(unidad=unidad):
                self.assertTrue(resultado.consistente, [str(e) for e in resultado.errores])
                self.assertEqual(resultado.geometria_m["unidad_longitud"], "m")
        base = resultados["m"]
        for unidad in ("cm", "mm"):
            with self.subTest(unidad=unidad):
                for clave in ("niveles", "nodos", "muros"):
                    self.assertEqual(resultados[unidad].geometria_m[clave], base.geometria_m[clave])
                self.assertEqual(resultados[unidad].derivados_m, base.derivados_m)
        self.assertEqual(base.geometria_m["muros"][0]["espesor"], 0.15)

    def test_unidad_no_admitida_o_implicita(self):
        for unidad in ("in", "M", "", None, 1):
            with self.subTest(unidad=unidad):
                data = sintetico()
                data["unidad_longitud"] = unidad
                self.assertError(data, "$.unidad_longitud", "unidad_no_admitida")
        data = sintetico()
        del data["unidad_longitud"]
        self.assertError(data, "$.unidad_longitud", "campo_ausente")

    def test_identificadores_duplicados(self):
        data = sintetico()
        data["nodos"][1]["id"] = "A"
        self.assertError(data, "$.nodos[1].id", "id_duplicado")
        data = sintetico()
        data["muros"][2]["id"] = "M1"
        self.assertError(data, "$.muros[2].id", "id_duplicado")

    def test_referencias_rotas(self):
        for campo, valor in (("nodo_fin", "Z"), ("nivel_superior", "N9")):
            with self.subTest(campo=campo):
                data = sintetico()
                data["muros"][0][campo] = valor
                self.assertError(data, f"$.muros[0].{campo}", "referencia_rota")
        data = sintetico()
        data["faltantes"] = [{"coleccion": "muros", "id": "M99", "campo": "espesor", "descripcion": "x"}]
        self.assertError(data, "$.faltantes[0].id", "referencia_rota")

    def test_muro_longitud_cero_y_extremos_iguales(self):
        data = sintetico()
        data["nodos"][1]["x"] = 0
        self.assertError(data, "$.muros[0]", "longitud_nula")
        data = sintetico()
        data["muros"][0]["nodo_fin"] = "A"
        self.assertError(data, "$.muros[0].nodo_fin", "extremos_iguales")

    def test_altura_derivada_no_positiva(self):
        data = sintetico()
        data["niveles"][1]["cota"] = 0
        self.assertError(data, "$.muros[0]", "altura_no_positiva")
        data = sintetico()
        data["muros"][0]["nivel_superior"] = "N0"
        self.assertError(data, "$.muros[0].nivel_superior", "niveles_iguales")

    def test_espesor_negativo_y_cero(self):
        for valor in (-0.15, 0, 0.0):
            with self.subTest(valor=valor):
                data = sintetico()
                data["muros"][0]["espesor"] = valor
                self.assertError(data, "$.muros[0].espesor", "no_positivo")

    def test_ausente_cero_y_null_se_distinguen(self):
        ausente = sintetico()
        del ausente["muros"][0]["espesor"]
        self.assertError(ausente, "$.muros[0].espesor", "campo_ausente")

        cero = sintetico()
        cero["muros"][0]["espesor"] = 0
        self.assertError(cero, "$.muros[0].espesor", "no_positivo")

        nulo_sin_declarar = sintetico()
        nulo_sin_declarar["muros"][0]["espesor"] = None
        self.assertError(nulo_sin_declarar, "$.muros[id=M1].espesor", "nulo_no_declarado")

        nulo = sintetico()
        nulo["muros"][0]["espesor"] = None
        nulo["faltantes"] = [{"coleccion": "muros", "id": "M1", "campo": "espesor", "descripcion": "Sin dato."}]
        resultado = validar_geometria(nulo)
        self.assertTrue(resultado.consistente, [str(e) for e in resultado.errores])
        self.assertFalse(resultado.disponible_para_modelado)
        self.assertIsNone(resultado.geometria_m["muros"][0]["espesor"])

    def test_faltante_contradictorio_y_campo_no_anulable(self):
        data = sintetico()
        data["faltantes"] = [{"coleccion": "muros", "id": "M1", "campo": "espesor", "descripcion": "x"}]
        self.assertError(data, "$.faltantes[0]", "faltante_contradictorio")
        data = sintetico()
        data["nodos"][0]["x"] = None
        self.assertError(data, "$.nodos[0].x", "nulo_no_admitido")

    def test_cota_faltante_deja_altura_sin_determinar(self):
        data = sintetico()
        data["niveles"][1]["cota"] = None
        data["faltantes"] = [{"coleccion": "niveles", "id": "N1", "campo": "cota", "descripcion": "Sin cota."}]
        resultado = validar_geometria(data)
        self.assertTrue(resultado.consistente, [str(e) for e in resultado.errores])
        self.assertIsNone(resultado.derivados_m["muros"]["M1"]["altura"])
        derivados = [f for f in resultado.faltantes if f["origen"] == "derivado"]
        self.assertEqual(len(derivados), 4)
        self.assertFalse(resultado.disponible_para_modelado)

    def test_valores_no_finitos_y_booleanos(self):
        for valor in (math.nan, math.inf, -math.inf):
            with self.subTest(valor=valor):
                data = sintetico()
                data["nodos"][2]["y"] = valor
                self.assertError(data, "$.nodos[2].y", "no_finito")
        for valor in (True, False, "0.15", [0.15]):
            with self.subTest(valor=valor):
                data = sintetico()
                data["muros"][1]["espesor"] = valor
                self.assertError(data, "$.muros[1].espesor", "tipo_invalido")

    def test_tipos_y_campos_desconocidos(self):
        data = sintetico()
        data["muros"][0]["espesr"] = 0.15
        self.assertError(data, "$.muros[0].espesr", "campo_desconocido")
        data = sintetico()
        data["nodos"] = {}
        self.assertError(data, "$.nodos", "tipo_invalido")
        data = sintetico()
        data["version_contrato"] = "99.0.0"
        self.assertError(data, "$.version_contrato", "version_no_admitida")
        resultado = validar_geometria([])
        self.assertIn(("$", "tipo_invalido"), self.codigos(resultado))

    def test_supuesto_requiere_justificacion_y_no_mezcla_sinteticos(self):
        data = sintetico()
        data["procedencia"] = {"tipo": "supuesto", "descripcion": "Hipótesis."}
        self.assertError(data, "$.procedencia.justificacion", "supuesto_sin_justificacion")
        data = sintetico()
        data["muros"][0]["procedencia"] = {"tipo": "plano", "descripcion": "Lámina", "lamina": "L0001"}
        self.assertError(data, "$.muros[0].procedencia.tipo", "procedencia_mixta")

    def test_consistente_pero_pendiente_de_aprobacion(self):
        resultado = validar_geometria(sintetico())
        self.assertTrue(resultado.consistente)
        self.assertEqual(resultado.faltantes, [])
        self.assertFalse(resultado.disponible_para_modelado)
        self.assertTrue(any("aprobación explícita" in b for b in resultado.bloqueos))
        salida = resultado.a_dict()
        self.assertTrue(salida["consistente"])
        self.assertFalse(salida["disponible_para_modelado"])

    def test_aprobacion_registrada_y_vigente(self):
        resultado = validar_geometria(aprobar(sintetico()))
        self.assertTrue(resultado.consistente, [str(e) for e in resultado.errores])
        self.assertEqual(resultado.bloqueos, [])
        self.assertTrue(resultado.disponible_para_modelado)

    def test_cambio_posterior_invalida_aprobacion(self):
        data = aprobar(sintetico())
        data["muros"][0]["espesor"] = 0.25
        resultado = validar_geometria(data)
        self.assertTrue(resultado.consistente)
        self.assertFalse(resultado.disponible_para_modelado)
        self.assertTrue(any("huella distinta" in b for b in resultado.bloqueos))

    def test_aprobacion_con_faltantes_no_habilita_modelado(self):
        data = sintetico()
        data["muros"][0]["espesor"] = None
        data["faltantes"] = [{"coleccion": "muros", "id": "M1", "campo": "espesor", "descripcion": "Sin dato."}]
        resultado = validar_geometria(aprobar(data))
        self.assertTrue(resultado.consistente)
        self.assertFalse(resultado.disponible_para_modelado)

    def test_estado_y_aprobacion_incoherentes(self):
        data = sintetico()
        data["revision"]["estado"] = "aprobado"
        self.assertError(data, "$.revision.aprobacion", "aprobacion_ausente")
        data = aprobar(sintetico())
        data["revision"]["estado"] = "en_revision"
        self.assertError(data, "$.revision.aprobacion", "aprobacion_incoherente")
        data = aprobar(sintetico())
        data["revision"]["aprobacion"]["fecha"] = "13/10/2026"
        self.assertError(data, "$.revision.aprobacion.fecha", "fecha_invalida")

    def test_entrada_no_se_modifica(self):
        casos = [sintetico("cm"), aprobar(sintetico("mm")), sintetico()]
        casos[2]["nodos"][0]["x"] = math.nan
        for data in casos:
            with self.subTest(unidad=data["unidad_longitud"]):
                antes = copy.deepcopy(data)
                resultado = validar_geometria(data)
                self.assertEqual(repr(data), repr(antes))
                if resultado.geometria_m is not None:
                    resultado.geometria_m["muros"][0]["espesor"] = -1
                    self.assertEqual(repr(data), repr(antes))

    def test_lectura_rechaza_claves_repetidas_y_nan(self):
        with tempfile.TemporaryDirectory() as temp:
            ruta = Path(temp) / "geo.json"
            for texto in ('{"id": "a", "id": "b"}', '{"cota": NaN}', '{"cota": Infinity}'):
                with self.subTest(texto=texto):
                    ruta.write_text(texto, encoding="utf-8")
                    with self.assertRaises(ErrorLecturaGeometria):
                        cargar_geometria(ruta)


class RepresentabilidadNumericaTests(unittest.TestCase):
    """Entradas JSON válidas cuyo cálculo en coma flotante no es representable.

    No se aplican tolerancias físicas: solo se exige que cada número y cada
    resultado derivado exista como binary64 finito y conserve lo que la entrada distingue.
    """

    def rechazo(self, data, ruta, codigo):
        resultado = validar_geometria(data)
        self.assertFalse(resultado.consistente)
        self.assertFalse(resultado.disponible_para_modelado)
        self.assertIn((ruta, codigo), {(h.ruta, h.codigo) for h in resultado.errores},
                      [str(e) for e in resultado.errores])
        self.assertIsNone(resultado.geometria_m)
        self.assertIsNone(resultado.derivados_m)
        self.assertIsNone(resultado.huella_contenido)
        self.assertIn("El contrato tiene errores de consistencia.", resultado.bloqueos)
        json.dumps(resultado.a_dict(), allow_nan=False)  # el diagnóstico es JSON estricto
        return resultado

    def test_enteros_enormes_en_coordenadas_cotas_y_espesor(self):
        casos = (
            (("nodos", 0, "x"), 10**1000, "$.nodos[0].x"),
            (("nodos", 2, "y"), -(10**1000), "$.nodos[2].y"),
            (("niveles", 1, "cota"), 10**400, "$.niveles[1].cota"),
            (("muros", 1, "espesor"), 10**400, "$.muros[1].espesor"),
            (("nodos", 1, "x"), 2**1024, "$.nodos[1].x"),  # primer entero que no cabe en binary64
        )
        for (coleccion, indice, campo), valor, ruta in casos:
            with self.subTest(ruta=ruta):
                data = sintetico()
                data[coleccion][indice][campo] = valor
                resultado = self.rechazo(data, ruta, "fuera_de_rango")
                mensaje = next(h.mensaje for h in resultado.errores if h.ruta == ruta)
                self.assertLess(len(mensaje), 200)  # no reproduce los miles de dígitos

    def test_entero_grande_representable_se_acepta_sin_umbral(self):
        data = sintetico()
        data["nodos"][1]["x"] = 10**300  # entero válido y representable: no hay límite físico
        resultado = validar_geometria(data)
        self.assertTrue(resultado.consistente, [str(e) for e in resultado.errores])
        self.assertEqual(resultado.geometria_m["nodos"][1]["x"], 1e300)
        self.assertEqual(resultado.derivados_m["muros"]["M1"]["longitud"], 1e300)
        json.dumps(resultado.a_dict(), allow_nan=False)

    def test_desbordamiento_de_longitud(self):
        data = sintetico()
        data["nodos"][0]["x"] = -1.7e308
        data["nodos"][1]["x"] = 1.7e308
        resultado = self.rechazo(data, "$.muros[0]", "longitud_no_representable")
        # Sin allow_nan=False, json.dumps escribiría Infinity/NaN si quedara alguno: no debe haber ninguno.
        texto = json.dumps(resultado.a_dict())
        self.assertNotIn("Infinity", texto)
        self.assertNotIn("NaN", texto)

    def test_desbordamiento_de_altura(self):
        data = sintetico()
        data["niveles"][0]["cota"] = -1.7e308
        data["niveles"][1]["cota"] = 1.7e308
        resultado = self.rechazo(data, "$.muros[0]", "altura_no_representable")
        self.assertEqual(
            {h.ruta for h in resultado.errores if h.codigo == "altura_no_representable"},
            {"$.muros[0]", "$.muros[1]", "$.muros[2]", "$.muros[3]"},
        )

    def test_subdesbordamiento_a_cero_al_normalizar(self):
        # 1e-323 es positivo en mm, pero 1e-323 / 1000 se redondea a 0.0 en metros.
        self.assertEqual(1e-323 / 1000, 0.0)
        for (coleccion, indice, campo), ruta in (
            (("muros", 0, "espesor"), "$.muros[0].espesor"),
            (("nodos", 0, "y"), "$.nodos[0].y"),
            (("niveles", 0, "cota"), "$.niveles[0].cota"),
        ):
            with self.subTest(ruta=ruta):
                data = sintetico("mm")
                data[coleccion][indice][campo] = 1e-323
                self.rechazo(data, ruta, "normalizacion_a_cero")

    def test_colapso_geometrico_tras_normalizar(self):
        a = 2.0**-1060
        b = math.nextafter(a, 1.0)  # distinto de a en mm
        self.assertNotEqual(a, b)
        self.assertEqual(a / 1000, b / 1000)  # pero igual en metros, y distinto de cero
        self.assertNotEqual(a / 1000, 0.0)

        data = sintetico("mm")
        data["nodos"][0].update(x=a, y=0)
        data["nodos"][1].update(x=b, y=0)
        self.rechazo(data, "$.muros[0]", "longitud_nula_tras_normalizar")

        data = sintetico("mm")
        data["niveles"][0]["cota"] = a
        data["niveles"][1]["cota"] = b
        self.rechazo(data, "$.muros[0]", "altura_nula_tras_normalizar")

    def test_tipos_invalidos_de_unidad(self):
        for unidad in ([], {}, None, True, False, 5, 1.5, ["m"], {"m": 1}):
            with self.subTest(unidad=unidad):
                data = sintetico()
                data["unidad_longitud"] = unidad
                self.rechazo(data, "$.unidad_longitud", "unidad_no_admitida")

    def test_diagnostico_estricto_con_valores_no_finitos_en_texto(self):
        data = sintetico()
        data["faltantes"] = [{"descripcion": math.nan}]
        data["muros"][0]["espesor"] = math.inf
        resultado = self.rechazo(data, "$.faltantes[0].descripcion", "tipo_invalido")
        self.assertIn(("$.muros[0].espesor", "no_finito"), {(h.ruta, h.codigo) for h in resultado.errores})
        self.assertEqual(resultado.faltantes, [{"origen": "declarado", "descripcion": None}])

    def test_mensajes_con_enteros_enormes_no_fallan(self):
        for ruta, cambio in (
            ("$.version_contrato", lambda d: d.update(version_contrato=10**5000)),
            ("$.unidad_longitud", lambda d: d.update(unidad_longitud=10**5000)),
            ("$.procedencia.tipo", lambda d: d["procedencia"].update(tipo=10**5000)),
            ("$.revision.estado", lambda d: d["revision"].update(estado=10**5000)),
        ):
            with self.subTest(ruta=ruta):
                data = sintetico()
                cambio(data)
                resultado = validar_geometria(data)
                self.assertFalse(resultado.consistente)
                hallazgo = next(h for h in resultado.errores if h.ruta == ruta)
                self.assertLess(len(hallazgo.mensaje), 200)
                json.dumps(resultado.a_dict(), allow_nan=False)


if __name__ == "__main__":
    unittest.main()
