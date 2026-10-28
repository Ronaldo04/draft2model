"""Conversión de superficies desde lecturas sintéticas comprobadas, sin API ni ETABS."""
import copy
import hashlib
import json
import unittest
from unittest import mock

from draft2model import conversion_geometria as conversion
from draft2model import gestion_extraccion as e
from draft2model.extraccion_preliminar import exportar_revisados
from draft2model.validacion_geometria import validar_geometria
from tests import test_conversion_geometria as legado


def manifiesto_superficie(anterior):
    nuevo = copy.deepcopy(anterior)
    nuevo.update(version_contrato="0.2.0", niveles=[], nodos=[], muros=[])

    def medida(numero):
        return {"valor": numero, "unidad": "m", "justificacion": "Coordenada física sintética declarada para probar conectividad, no medida en píxeles.", "referencias": ["C006"]}

    nuevo["vertices"] = [{"id": f"V{i}", "x": {"candidato": "C006"} if x else medida(0),
                          "y": medida(y), "z": {"candidato": "C001"}}
                         for i, (x, y) in enumerate(((0, 0), (4, 0), (4, 3), (0, 3)))]
    nuevo["superficies"] = [{"id": "S1", "vertices": ["V0", "V1", "V2", "V3"],
                             "papel_geometrico": "piso sintético, sin sección asignada",
                             "referencias": ["C004"]}]
    return nuevo


class ConversionSuperficiesTests(unittest.TestCase):
    def setUp(self):
        self.f = legado.ConversionTests("test_recorrido_comprobado_conversion_importacion_y_traza")
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()
        _, datos, _, comprobacion = e._cargar_comprobada(self.f.raiz, legado.CASO, self.f.version.identificador, "Prueba")
        self.exportacion = exportar_revisados(datos, comprobacion.inventario)
        self.manifiesto = manifiesto_superficie(self.f.manifiesto)

    def test_publicacion_fuente_exacta_medidas_y_conectividad(self):
        original = copy.deepcopy(self.manifiesto)
        resultado = self.f.convertir(self.manifiesto)
        self.assertEqual(self.manifiesto, original)
        g, traza = resultado.geometria, resultado.trazabilidad
        self.assertEqual(g["version_contrato"], "0.2.0")
        self.assertEqual(traza["version_contrato"], "0.2.0")
        self.assertEqual(g["revision"], {"estado": "borrador", "aprobacion": None})
        self.assertIsNone(traza["aprobacion_ingenieria"])
        self.assertEqual(g["vertices"][1]["x"], 4)
        self.assertEqual(g["vertices"][1]["z"], 2.6)
        self.assertEqual(g["vertices"][1]["procedencia"]["referencias"], ["C006", "C001"])
        self.assertEqual(g["superficies"][0]["procedencia"]["referencias"], ["C004"])
        self.assertEqual(len(traza["correspondencias"]), 13)
        self.assertEqual(traza["correspondencias"][-1]["modo"], "conectividad_superficie_declarada")
        self.assertEqual(traza["correspondencias"][-1]["vertices"], ["V0", "V1", "V2", "V3"])
        r = validar_geometria(g)
        self.assertTrue(r.consistente, r.errores)
        self.assertFalse(r.disponible_para_modelado)
        self.assertEqual(r.derivados_m["superficies"]["S1"]["area_m2"], 12)
        self.assertFalse((self.f.caso_dir / "geometrias").exists())
        for archivo, campo in (("exportacion.json", "exportacion_sha256"), ("manifiesto.json", "manifiesto_sha256"), ("geometria.json", "geometria_sha256")):
            self.assertEqual(hashlib.sha256((resultado.ruta/archivo).read_bytes()).hexdigest(), traza[campo])
        conversion.comprobar_reproduccion(json.loads((resultado.ruta/"exportacion.json").read_bytes()),
                                          json.loads((resultado.ruta/"manifiesto.json").read_bytes()), g, traza["correspondencias"])

    def test_equivalencia_de_unidades_y_coexistencia_legada(self):
        esperado, _ = conversion._construir(self.exportacion, self.manifiesto)
        metros = validar_geometria(esperado).geometria_m
        for unidad in ("cm", "mm"):
            nuevo = copy.deepcopy(self.manifiesto)
            nuevo["unidad_longitud"] = unidad
            g, _ = conversion._construir(self.exportacion, nuevo)
            self.assertEqual(validar_geometria(g).geometria_m, metros)
        mixto = copy.deepcopy(self.f.manifiesto)
        mixto.update(version_contrato="0.2.0", vertices=self.manifiesto["vertices"], superficies=self.manifiesto["superficies"])
        g, _ = conversion._construir(self.exportacion, mixto)
        self.assertEqual(g["muros"][0]["id"], "M1")
        self.assertTrue(validar_geometria(g).consistente)

    def test_referencias_medidas_y_contorno_invalidos(self):
        cambios = [lambda m: m["vertices"][0].update(z=2.6),
                   lambda m: m["vertices"][0].update(z={"candidato": "C004"}),
                   lambda m: m["vertices"][0].update(z={"candidato": "C002"}),
                   lambda m: m["vertices"][0].update(z={"candidato": "C003"}),
                   lambda m: m["vertices"][0].update(z={"candidato": "ausente"}),
                   lambda m: m["vertices"][0]["x"].update(unidad="px"),
                   lambda m: m["vertices"][0]["x"].update(referencias=[]),
                   lambda m: m["vertices"][0]["x"].update(valor=True),
                   lambda m: m["vertices"][0].update(procedencia={}),
                   lambda m: m["superficies"][0].update(referencias=[]),
                   lambda m: m["superficies"][0].update(referencias=["C004", "C004"]),
                   lambda m: m["superficies"][0].update(referencias=[{}]),
                   lambda m: m["superficies"][0].update(vertices=["V0", "V1", "V2", "V0"]),
                   lambda m: m["superficies"][0].update(vertices=["V0", "V2", "V1", "V3"]),
                   lambda m: m["superficies"][0].update(vertices=["V0", "V1", "ausente"]),
                   lambda m: m["superficies"][0].update(papel_geometrico=""),
                   lambda m: m.update(vertices=None),
                   lambda m: m.pop("superficies")]
        for cambiar in cambios:
            nuevo = copy.deepcopy(self.manifiesto)
            cambiar(nuevo)
            with self.subTest(cambiar=cambiar), self.assertRaises(e.ErrorEvidencia):
                conversion._construir(self.exportacion, nuevo)

    def test_reproduccion_rechaza_falsificacion_incluso_con_hashes_recalculados(self):
        for manifest in (self.f.manifiesto, self.manifiesto):
            g, correspondencias = conversion._construir(self.exportacion, manifest)
            conversion.comprobar_reproduccion(self.exportacion, manifest, g, correspondencias)
            alterada = copy.deepcopy(g)
            alterada["procedencia"]["descripcion"] += " falsificación"
            with self.assertRaises(e.ErrorEvidencia):
                conversion.comprobar_reproduccion(self.exportacion, manifest, alterada, correspondencias)
            corr = copy.deepcopy(correspondencias)
            corr[0]["valor_geometria"] = 999
            with self.assertRaises(e.ErrorEvidencia):
                conversion.comprobar_reproduccion(self.exportacion, manifest, g, corr)

    def test_compatibilidad_estricta_manifiesto_v01(self):
        nuevo = copy.deepcopy(self.manifiesto)
        nuevo["version_contrato"] = "0.1.0"
        with self.assertRaises(e.ErrorEvidencia):
            conversion._construir(self.exportacion, nuevo)
        anterior = copy.deepcopy(self.f.manifiesto)
        anterior["muros"] = []
        with self.assertRaises(e.ErrorEvidencia):
            conversion._construir(self.exportacion, anterior)

    def test_fuente_alterada_despues_de_exportacion_impide_publicacion(self):
        exportar = e.exportar_version

        def cambiar_fuente(*args):
            resultado = exportar(*args)
            self.f.original.write_bytes(self.f.original.read_bytes()+b"alteracion tardia")
            return resultado

        with mock.patch.object(e, "exportar_version", cambiar_fuente), self.assertRaises(e.ErrorEvidencia):
            self.f.convertir(self.manifiesto)
        self.assertFalse((self.f.caso_dir/conversion.CARPETA).exists())


if __name__ == "__main__":
    unittest.main()
