"""Pruebas del registro de extracción preliminar con datos sintéticos, no planos reales."""

import copy
import json
import math
import tempfile
import unittest
from pathlib import Path

from draft2model.extraccion_preliminar import (
    ErrorExtraccion,
    cargar_extraccion,
    corregir,
    exportar_revisados,
    inventario_desde,
    validar_extraccion,
)

EJEMPLO = Path(__file__).resolve().parents[1] / "examples" / "extraccion_sintetica.json"
HASH_L1 = "d330d1850c8e5c1bd8f6edcea62b045dfe38e96f48a2b52f828f44d0b1ba458b"
HASH_R1 = "810bd544fe445e93081943fe04c565412a9f246bc37d5335a04637ed4ad6ba65"
ALCANCE = {"estado": "pendiente_verificar", "uso": "pendiente", "motivos": []}


def ejemplo():
    return cargar_extraccion(EJEMPLO)


def inventario(paginas=True, alcance=ALCANCE):
    """Inventario sintético equivalente a expediente.json, revision.json y recorte.json."""
    expediente = {
        "id": "sintetico-ext-001",
        "alcance": copy.deepcopy(alcance),
        "archivos": [{"id": "L0001", "sha256": HASH_L1}],
    }
    revisiones = [{
        "caso": "sintetico-ext-001",
        "documentos": [{"id": "L0001", "error": None, "paginas_declaradas": 2}],
    }] if paginas else []
    recortes = [{
        "id": "R0001", "caso": "sintetico-ext-001", "archivo_id": "L0001", "pagina": 1,
        "origen_sha256": HASH_L1, "imagen_sha256": HASH_R1,
        "bbox_normalizada": [0.1, 0.2, 0.5, 0.5], "sistema_coordenadas": "pagina_visible_normalizada",
    }]
    return inventario_desde(expediente, revisiones, recortes)


def revisar(data, cid="C001", **extra):
    argumentos = dict(estado="revisado", motivo="Confirmado en la evidencia.", fecha="2026-10-14",
                      revisor_declarado="Revisor sintético", valor_revisado=2.6, unidad_revisada="m")
    argumentos.update(extra)
    return corregir(data, cid, **argumentos)


class ExtraccionTests(unittest.TestCase):
    def codigos(self, resultado):
        return {(h.ruta, h.codigo) for h in resultado.errores}

    def assertError(self, data, ruta, codigo, inv=None):
        resultado = validar_extraccion(data, inv)
        self.assertFalse(resultado.consistente)
        self.assertIn((ruta, codigo), self.codigos(resultado), [str(e) for e in resultado.errores])
        return resultado

    def test_caso_sintetico_valido(self):
        resultado = validar_extraccion(ejemplo())
        self.assertTrue(resultado.consistente, [str(e) for e in resultado.errores])
        self.assertEqual(resultado.resumen["candidatos"], 5)
        self.assertEqual(
            (resultado.resumen["pendientes"], resultado.resumen["revisados"], resultado.resumen["rechazados"]), (3, 1, 1)
        )
        self.assertIn("datos_sinteticos", {h.codigo for h in resultado.advertencias})
        json.dumps(resultado.a_dict(), allow_nan=False)

    def test_datos_desconocidos_se_conservan(self):
        data = ejemplo()
        resultado = validar_extraccion(data)
        self.assertEqual(resultado.resumen["valores_desconocidos"], 1)
        self.assertEqual(resultado.resumen["unidades_desconocidas"], 2)
        # Un valor desconocido no puede marcarse como revisado sin un valor explícito.
        with self.assertRaises(ErrorExtraccion):
            revisar(data, "C002", valor_revisado=None, unidad_revisada="desconocida")
        with self.assertRaises(ErrorExtraccion):
            corregir(data, "C002", estado="revisado", motivo="m", fecha="2026-10-14", revisor_declarado="r")
        # Unidad desconocida tampoco se reemplaza automáticamente.
        exportado = exportar_revisados(revisar(data, "C001"))
        c003 = next(c for c in exportado["candidatos"] if c["id"] == "C003")
        self.assertEqual((c003["unidad_propuesta"], c003["unidad_revisada"]), ("desconocida", "cm"))

    def test_unidad_explicita_y_valor_por_tipo(self):
        data = ejemplo()
        del data["candidatos"][0]["unidad"]
        self.assertError(data, "$.candidatos[0].unidad", "campo_ausente")
        for unidad in ("in", None, "", "M"):
            with self.subTest(unidad=unidad):
                data = ejemplo()
                data["candidatos"][0]["unidad"] = unidad
                self.assertError(data, "$.candidatos[0].unidad", "unidad_invalida")
        data = ejemplo()
        data["candidatos"][3]["unidad"] = "m"
        self.assertError(data, "$.candidatos[3].unidad", "unidad_invalida")
        data = ejemplo()
        data["candidatos"][0]["valor_propuesto"] = "2.60"
        self.assertError(data, "$.candidatos[0].valor_propuesto", "tipo_invalido")
        data = ejemplo()
        data["candidatos"][0]["valor_propuesto"] = math.nan
        self.assertError(data, "$.candidatos[0].valor_propuesto", "no_finito")

    def test_referencias_no_comprobadas_sin_inventario(self):
        resultado = validar_extraccion(ejemplo())
        self.assertFalse(resultado.inventario_aportado)
        self.assertEqual(set(sum(resultado.referencias.values(), [])), {"referencia_no_comprobada"})
        self.assertEqual(resultado.resumen["referencias_comprobadas"], 0)
        exportado = exportar_revisados(ejemplo())
        self.assertEqual(exportado["candidatos"][0]["evidencia"][0]["estado_referencia"], "referencia_no_comprobada")
        self.assertFalse(exportado["inventario_aportado"])

    def test_referencias_comprobadas_y_parciales(self):
        resultado = validar_extraccion(ejemplo(), inventario())
        self.assertTrue(resultado.consistente, [str(e) for e in resultado.errores])
        self.assertEqual(set(sum(resultado.referencias.values(), [])), {"comprobada"})
        resultado = validar_extraccion(ejemplo(), inventario(paginas=False))
        self.assertTrue(resultado.consistente)
        self.assertEqual(set(sum(resultado.referencias.values(), [])), {"parcial"})
        self.assertIn("pagina_no_comprobada", {h.codigo for h in resultado.advertencias})

    def test_referencias_rotas(self):
        inv = inventario()
        data = ejemplo()
        data["candidatos"][1]["evidencia"][0]["archivo_id"] = "L0009"
        self.assertError(data, "$.candidatos[1].evidencia[0].archivo_id", "referencia_rota", inv)
        data = ejemplo()
        data["candidatos"][0]["evidencia"][0]["recorte_id"] = "R0009"
        self.assertError(data, "$.candidatos[0].evidencia[0].recorte_id", "referencia_rota", inv)
        data = ejemplo()
        data["candidatos"][1]["evidencia"][0]["original_sha256"] = "0" * 64
        self.assertError(data, "$.candidatos[1].evidencia[0].original_sha256", "hash_incompatible", inv)
        data = ejemplo()
        data["candidatos"][0]["evidencia"][0]["imagen_sha256"] = "1" * 64
        self.assertError(data, "$.candidatos[0].evidencia[0].imagen_sha256", "hash_incompatible", inv)
        data = ejemplo()
        data["candidatos"][0]["evidencia"][0]["pagina"] = 2
        self.assertError(data, "$.candidatos[0].evidencia[0].pagina", "recorte_incompatible", inv)
        data = ejemplo()
        data["caso"] = "otro-caso"
        self.assertError(data, "$.caso", "caso_incompatible", inv)
        # Una evidencia incompleta se informa como error y no se contrasta con el inventario.
        data = ejemplo()
        del data["candidatos"][1]["evidencia"][0]["archivo_id"]
        resultado = self.assertError(data, "$.candidatos[1].evidencia[0].archivo_id", "campo_ausente", inv)
        self.assertEqual(resultado.referencias["C002"], ["invalida"])

    def test_paginas_invalidas(self):
        for pagina in (0, -1, 1.0, True, "1", None):
            with self.subTest(pagina=pagina):
                data = ejemplo()
                data["candidatos"][1]["evidencia"][0]["pagina"] = pagina
                self.assertError(data, "$.candidatos[1].evidencia[0].pagina", "pagina_invalida")
        data = ejemplo()
        data["candidatos"][1]["evidencia"][0]["pagina"] = 3
        self.assertTrue(validar_extraccion(data).consistente)  # sin inventario no se puede saber
        self.assertError(data, "$.candidatos[1].evidencia[0].pagina", "pagina_inexistente", inventario())

    def test_bbox_incorrecta_nan_y_booleanos(self):
        ruta = "$.candidatos[1].evidencia[0].bbox_normalizada"
        casos = [
            ([0.1, 0.2, 0.3], ruta, "bbox_invalida"),
            ("0,0,1,1", ruta, "bbox_invalida"),
            ([0.5, 0.2, 0.4, 0.3], ruta, "bbox_fuera_de_rango"),
            ([0.1, 0.2, 0.1, 0.3], ruta, "bbox_fuera_de_rango"),
            ([0.1, 0.2, 1.2, 0.3], ruta, "bbox_fuera_de_rango"),
            ([-0.1, 0.2, 0.3, 0.4], ruta, "bbox_fuera_de_rango"),
            ([0.1, math.nan, 0.3, 0.4], f"{ruta}[1]", "no_finito"),
            ([0.1, 0.2, math.inf, 0.4], f"{ruta}[2]", "no_finito"),
            ([False, 0.2, True, 0.4], f"{ruta}[0]", "tipo_invalido"),
            ([0.1, "0.2", 0.3, 0.4], f"{ruta}[1]", "tipo_invalido"),
        ]
        for bbox, ruta_error, codigo in casos:
            with self.subTest(bbox=bbox):
                data = ejemplo()
                data["candidatos"][1]["evidencia"][0]["bbox_normalizada"] = bbox
                self.assertError(data, ruta_error, codigo)

    def test_bbox_fuera_del_recorte_es_advertencia(self):
        data = ejemplo()
        data["candidatos"][0]["evidencia"][0]["bbox_normalizada"] = [0.6, 0.6, 0.7, 0.7]
        resultado = validar_extraccion(data, inventario())
        self.assertTrue(resultado.consistente)
        self.assertIn("bbox_fuera_del_recorte", {h.codigo for h in resultado.advertencias})

    def test_ids_duplicados_y_campos_desconocidos(self):
        data = ejemplo()
        data["candidatos"][2]["id"] = "C001"
        self.assertError(data, "$.candidatos[2].id", "id_duplicado")
        data = ejemplo()
        data["candidatos"][0]["evidencia"][0]["pagna"] = 1
        self.assertError(data, "$.candidatos[0].evidencia[0].pagna", "campo_desconocido")
        data = ejemplo()
        data["candidatos"][0]["evidencia"] = []
        self.assertError(data, "$.candidatos[0].evidencia", "evidencia_ausente")
        data = ejemplo()
        data["sistema_coordenadas"] = "metros"
        self.assertError(data, "$.sistema_coordenadas", "sistema_no_admitido")

    def test_correccion_con_historial(self):
        original = ejemplo()
        v1 = revisar(original, "C001", valor_revisado=2.65, motivo="Se lee 2.65 en el recorte ampliado.")
        v2 = corregir(v1, "C001", estado="pendiente", motivo="Reabierto para segunda lectura.",
                      fecha="2026-10-15", revisor_declarado="Otro revisor sintético")
        v3 = revisar(v2, "C001", valor_revisado=2.6, fecha="2026-10-16")
        candidato = v3["candidatos"][0]
        self.assertEqual(candidato["valor_propuesto"], 2.6)
        self.assertEqual([e["estado"] for e in candidato["revision"]["historial"]], ["revisado", "pendiente", "revisado"])
        self.assertEqual(candidato["revision"]["estado"], "revisado")
        self.assertEqual(candidato["revision"]["historial"][0]["valor_revisado"], 2.65)
        self.assertTrue(validar_extraccion(v3).consistente)
        # Fechas que retroceden, estado incoherente y campos impropios se rechazan.
        with self.assertRaises(ErrorExtraccion):
            revisar(v3, "C001", fecha="2026-10-01")
        with self.assertRaises(ErrorExtraccion):
            corregir(v3, "C001", estado="rechazado", motivo="x", fecha="2026-10-16",
                     revisor_declarado="r", valor_revisado=1.0)
        with self.assertRaises(ErrorExtraccion):
            revisar(v3, "C001", fecha="16/10/2026")
        with self.assertRaises(ErrorExtraccion):
            revisar(v3, "C001", motivo="")
        with self.assertRaises(ErrorExtraccion):
            revisar(v3, "C999")
        incoherente = copy.deepcopy(v3)
        incoherente["candidatos"][0]["revision"]["estado"] = "rechazado"
        self.assertError(incoherente, "$.candidatos[0].revision.estado", "estado_incoherente")

    def test_exporta_revisados_y_excluye_rechazados(self):
        data = revisar(ejemplo(), "C001", valor_revisado=2.65)
        exportado = exportar_revisados(data, inventario())
        self.assertEqual([c["id"] for c in exportado["candidatos"]], ["C001", "C003"])
        self.assertEqual(exportado["excluidos"], {"pendientes": ["C002", "C004"], "rechazados": ["C005"]})
        c001 = exportado["candidatos"][0]
        self.assertEqual((c001["valor_propuesto"], c001["valor_revisado"], c001["corregido"]), (2.6, 2.65, True))
        self.assertEqual(c001["evidencia"][0]["recorte_id"], "R0001")
        self.assertEqual(c001["evidencia"][0]["estado_referencia"], "comprobada")
        self.assertIsNone(exportado["aprobacion_ingenieria"])
        self.assertIn("no aprueba datos de ingeniería", exportado["aviso"])
        for clave in ("nodos", "muros", "niveles"):
            self.assertNotIn(clave, exportado)
        json.dumps(exportado, allow_nan=False)

    def test_no_exporta_inconsistente(self):
        data = ejemplo()
        data["candidatos"][2]["id"] = "C001"
        with self.assertRaises(ErrorExtraccion):
            exportar_revisados(data)

    def test_entrada_inmutable(self):
        data = ejemplo()
        antes = copy.deepcopy(data)
        inv = inventario()
        inv_antes = copy.deepcopy(inv)
        validar_extraccion(data, inv)
        nuevo = revisar(data, "C001")
        exportado = exportar_revisados(nuevo, inv)
        exportado["candidatos"][0]["evidencia"][0]["pagina"] = 99
        exportado["alcance"]["estado"] = "alterado"
        self.assertEqual(data, antes)
        self.assertEqual(inv, inv_antes)
        self.assertNotIn("revision", data["candidatos"][0])
        self.assertEqual(nuevo["candidatos"][0]["evidencia"][0]["pagina"], 1)
        self.assertEqual(nuevo["alcance"], ALCANCE)

    def test_conserva_alcance_y_procedencia(self):
        fuera = {"estado": "fuera_mvp_declarado", "uso": "pruebas_procesamiento",
                 "motivos": ["Sistema constructivo y cantidad de pisos fuera del MVP, según declaración."]}
        data = ejemplo()
        data["alcance"] = copy.deepcopy(fuera)
        resultado = validar_extraccion(data, inventario(alcance=fuera))
        self.assertTrue(resultado.consistente, [str(e) for e in resultado.errores])
        self.assertIn("fuera_mvp", {h.codigo for h in resultado.advertencias})
        exportado = exportar_revisados(data, inventario(alcance=fuera))
        self.assertEqual(exportado["alcance"], fuera)
        self.assertEqual(exportado["procedencia"]["tipo"], "sintetico")
        # Perder la marca respecto del expediente es un error, no una simplificación.
        data["alcance"] = copy.deepcopy(ALCANCE)
        self.assertError(data, "$.alcance", "alcance_incompatible", inventario(alcance=fuera))
        del data["alcance"]
        self.assertError(data, "$.alcance", "campo_ausente")

    def test_lectura_rechaza_claves_repetidas_y_nan(self):
        with tempfile.TemporaryDirectory() as temp:
            ruta = Path(temp) / "ext.json"
            for texto in ('{"caso": "a", "caso": "b"}', '{"v": NaN}'):
                with self.subTest(texto=texto):
                    ruta.write_text(texto, encoding="utf-8")
                    with self.assertRaises(ErrorExtraccion):
                        cargar_extraccion(ruta)


if __name__ == "__main__":
    unittest.main()
