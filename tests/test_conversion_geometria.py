"""Conversión explícita con evidencia sintética comprobada e importación geométrica real."""

import copy
import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from draft2model import conversion_geometria as conversion
from draft2model import gestion_extraccion as extracciones
from draft2model import gestion_geometria as geometrias
from draft2model.validacion_geometria import validar_geometria
from tests.test_gestion_extraccion import CasoSintetico, CASO

EJEMPLO = Path(__file__).resolve().parents[1] / "examples" / "conversion_sintetica" / "manifiesto.json"


class ConversionTests(CasoSintetico):
    def setUp(self):
        super().setUp()
        self.manifiesto = json.loads(EJEMPLO.read_bytes())
        for ident, valor in (("C005", 15), ("C006", 400)):
            candidato = copy.deepcopy(self.data["candidatos"][0])
            candidato.update(id=ident, valor_propuesto=valor, unidad="cm")
            self.data["candidatos"].append(candidato)
        for candidato in self.data["candidatos"]:
            candidato["metodo"] = {"tipo": "sintetico"}
        self.entrada = self.escribir(self.data)
        version = self.importar()
        for ident, valor, unidad in (("C001", 260, "cm"), ("C004", "muro", "no_aplica"),
                                     ("C005", 15, "cm"), ("C006", 400, "cm")):
            version = extracciones.corregir_version(
                self.raiz, CASO, version.identificador, ident, estado="revisado",
                motivo="Revisión de lectura sintética de prueba.", fecha="2026-10-16",
                revisor_declarado="Revisor sintético", valor_revisado=valor, unidad_revisada=unidad,
            )
        self.version = extracciones.corregir_version(
            self.raiz, CASO, version.identificador, "C003", estado="rechazado",
            motivo="Etiqueta sintética excluida.", fecha="2026-10-16", revisor_declarado="Revisor sintético",
        )

    def convertir(self, manifiesto=None, version=None):
        ruta = self.escribir(self.manifiesto if manifiesto is None else manifiesto, "manifiesto.json")
        return conversion.convertir_lecturas(self.raiz, CASO, version or self.version.identificador, ruta)

    def test_recorrido_comprobado_conversion_importacion_y_traza(self):
        resultado = self.convertir()
        geometria = resultado.geometria
        self.assertEqual(geometria["revision"], {"estado": "borrador", "aprobacion": None})
        self.assertEqual(geometria["niveles"][1]["cota"], 2.6)
        self.assertEqual(geometria["nodos"][1]["x"], 4)
        self.assertEqual(geometria["muros"][0]["espesor"], 0.15)
        validacion = validar_geometria(geometria)
        self.assertTrue(validacion.consistente)
        self.assertFalse(validacion.disponible_para_modelado)
        self.assertTrue(validacion.datos_sinteticos)
        for nombre, campo in (("exportacion.json", "exportacion_sha256"),
                               ("manifiesto.json", "manifiesto_sha256"), ("geometria.json", "geometria_sha256")):
            self.assertEqual(hashlib.sha256((resultado.ruta / nombre).read_bytes()).hexdigest(), resultado.trazabilidad[campo])
        self.assertEqual(resultado.trazabilidad["alcance"], self.data["alcance"])
        self.assertEqual({c["modo"] for c in resultado.trazabilidad["correspondencias"]},
                         {"declaracion_operador", "candidato_revisado", "conectividad_declarada"})
        imp = geometrias.importar_geometria(self.raiz, CASO, resultado.ruta / "geometria.json")
        self.assertTrue(imp.comprobacion.correcta, imp.comprobacion.problemas)
        self.assertFalse(imp.comprobacion.validacion["disponible_para_modelado"])
        otra = self.convertir()
        self.assertNotEqual(otra.identificador, resultado.identificador)
        self.assertTrue((resultado.ruta / "geometria.json").exists())

    def test_candidato_pendiente_rechazado_o_ausente_no_se_convierte(self):
        for ident in ("C002", "C003", "NO_EXISTE", None):
            manifest = copy.deepcopy(self.manifiesto)
            manifest["niveles"][1]["cota"] = {"candidato": ident}
            with self.subTest(ident=ident), self.assertRaises(extracciones.ErrorEvidencia):
                self.convertir(manifest)
        self.assertFalse((self.caso_dir / conversion.CARPETA).exists())

    def test_unidades_destino_cm_mm_conservan_geometria_m(self):
        original = validar_geometria(self.convertir().geometria).geometria_m
        for unidad in ("cm", "mm"):
            manifest = copy.deepcopy(self.manifiesto)
            manifest["unidad_longitud"] = unidad
            with self.subTest(unidad=unidad):
                resultado = validar_geometria(self.convertir(manifest).geometria)
                self.assertTrue(resultado.consistente)
                self.assertEqual(resultado.geometria_m, original)

    def test_exportacion_alterada_durante_publicacion_se_rechaza(self):
        exportar = extracciones.exportar_version
        def alterada(*args):
            resultado = exportar(*args)
            datos = json.loads(resultado.ruta.read_bytes())
            datos["candidatos"][0]["valor_revisado"] = 999
            resultado.ruta.write_text(json.dumps(datos), encoding="utf-8")
            return resultado
        with mock.patch.object(extracciones, "exportar_version", alterada):
            with self.assertRaises(extracciones.ErrorEvidencia):
                self.convertir()
        self.assertFalse((self.caso_dir / conversion.CARPETA).exists())

    def test_conectividad_ids_y_unidades_explicitos(self):
        alteraciones = [
            lambda m: m["muros"][0].update(nodo_fin="NO_EXISTE"),
            lambda m: m["nodos"][1].update(id="A"),
            lambda m: m["niveles"][0].pop("id"),
            lambda m: m["nodos"][0].update(x=None),
            lambda m: m["nodos"][0]["x"].update(unidad="px"),
            lambda m: m.update(unidad_longitud="desconocida"),
            lambda m: m.update(sistema_coordenadas="pagina_visible_normalizada"),
            lambda m: m["escala"].update(metodo="pixeles_a_metros"),
            lambda m: m["ejes"].pop("direccion_x"),
            lambda m: m["muros"][0].update(referencias=["C002"]),
            lambda m: m["nodos"][0]["x"].update(referencias=[]),
            lambda m: m["nodos"][0]["x"].update(valor=True),
            lambda m: m["nodos"][0]["x"].update(valor=10**1000),
            lambda m: m["nodos"][0]["x"].update(valor=2**53 + 1),
            lambda m: m["nodos"][0]["x"].update(valor=1e-323, unidad="mm"),
            lambda m: m["niveles"][1].update(cota={"candidato": "C004"}),
        ]
        for indice, alterar in enumerate(alteraciones):
            manifest = copy.deepcopy(self.manifiesto)
            alterar(manifest)
            with self.subTest(caso=indice), self.assertRaises(extracciones.ErrorEvidencia):
                self.convertir(manifest)
        self.assertFalse((self.caso_dir / conversion.CARPETA).exists())

    def test_no_convierte_sintetico_a_real_y_rechaza_contradiccion(self):
        for cambios in ({"datos_sinteticos": False},
                        {"datos_sinteticos": False, "procedencia": {"tipo": "plano", "descripcion": "Supuesta realidad"}},
                        {"datos_sinteticos": 1}):
            manifest = copy.deepcopy(self.manifiesto)
            manifest.update(cambios)
            with self.subTest(cambios=cambios), self.assertRaises(extracciones.ErrorEvidencia):
                self.convertir(manifest)

    def test_original_y_recorte_alterados_impiden_conversion(self):
        for ruta in (self.original, self.imagen):
            original = ruta.read_bytes()
            ruta.write_bytes(original + b"alteracion")
            try:
                with self.subTest(archivo=ruta.name), self.assertRaises(extracciones.ErrorEvidencia):
                    self.convertir()
            finally:
                ruta.write_bytes(original)
        self.assertFalse((self.caso_dir / conversion.CARPETA).exists())

    def test_valor_revisado_con_unidad_desconocida_no_se_convierte(self):
        desconocida = extracciones.corregir_version(
            self.raiz, CASO, self.version.identificador, "C005", estado="revisado",
            motivo="Unidad sintética desconocida.", fecha="2026-10-16", revisor_declarado="Revisor sintético",
            valor_revisado=15, unidad_revisada="desconocida",
        )
        with self.assertRaises(extracciones.ErrorEvidencia):
            self.convertir(version=desconocida.identificador)

    def test_json_estricto_caso_y_version_manifiesto(self):
        for campo, valor in (("caso", "otro-caso"), ("version_contrato", "999"), ("contrato", "otro")):
            manifest = copy.deepcopy(self.manifiesto)
            manifest[campo] = valor
            with self.subTest(campo=campo), self.assertRaises(extracciones.ErrorEvidencia):
                self.convertir(manifest)
        ruta = self.trabajo / "mal.json"
        for texto in ('{"caso":"a","caso":"b"}', '{"valor":NaN}'):
            ruta.write_text(texto, encoding="utf-8")
            with self.assertRaises(extracciones.ErrorGestion):
                conversion.convertir_lecturas(self.raiz, CASO, self.version.identificador, ruta)

    def test_cli_modulo_y_codigos(self):
        ruta = self.escribir(self.manifiesto, "manifiesto.json")
        argumentos = ["--raiz", str(self.raiz), "--caso", CASO, "--extraccion", self.version.identificador,
                      "--manifiesto", str(ruta)]
        salida = io.StringIO()
        with redirect_stdout(salida):
            self.assertEqual(conversion.main(argumentos), 0)
        self.assertTrue(json.loads(salida.getvalue())["correcta"])
        ruta.write_text("{}", encoding="utf-8")
        with redirect_stdout(io.StringIO()):
            self.assertEqual(conversion.main(argumentos), 2)
        ruta.unlink()
        with redirect_stdout(io.StringIO()):
            self.assertEqual(conversion.main(argumentos), 1)
