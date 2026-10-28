"""Contingencia tabular: equivalencia, rechazos y conservación de entradas."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from draft2model.importacion_tabular import convertir_tablas, main, ErrorImportacionTabular
from draft2model.validacion_geometria import validar_geometria

RAIZ = Path(__file__).resolve().parents[1]
EJEMPLO = RAIZ / "examples" / "tabular_sintetico"


class ImportacionTabularTests(unittest.TestCase):
    def setUp(self):
        self.meta = json.loads((EJEMPLO / "metadatos.json").read_text(encoding="utf-8"))
        self.tablas = {nombre: (EJEMPLO / f"{nombre}.csv").read_text(encoding="utf-8")
                       for nombre in ("niveles", "nodos", "muros")}

    def test_equivalencia_exacta_json_y_conservacion_entradas(self):
        antes_meta, antes_tablas = copy.deepcopy(self.meta), copy.deepcopy(self.tablas)
        esperado = json.loads((RAIZ / "examples" / "geometria_sintetica.json").read_text(encoding="utf-8"))
        salida = convertir_tablas(self.meta, self.tablas)
        self.assertEqual(salida, esperado)
        self.assertEqual(self.meta, antes_meta)
        self.assertEqual(self.tablas, antes_tablas)
        salida["procedencia"]["descripcion"] = "Cambio local"
        self.assertEqual(self.meta, antes_meta)

    def test_faltante_se_conserva_y_no_habilita_modelado(self):
        salida = convertir_tablas(self.meta, self.tablas)
        self.assertIsNone(salida["muros"][3]["espesor"])
        self.assertEqual(salida["faltantes"], self.meta["faltantes"])
        self.assertEqual(salida["procedencia"]["tipo"], "sintetico")
        self.assertFalse(validar_geometria(salida).disponible_para_modelado)

    def test_faltante_no_declarado_rechazado(self):
        self.meta["faltantes"] = []
        with self.assertRaises(ErrorImportacionTabular):
            convertir_tablas(self.meta, self.tablas)

    def test_celdas_numericas_no_finitas_y_no_numeros_rechazados(self):
        for valor in ("NaN", "inf", "-Infinity", "1e9999", "", "true", "4,2"):
            with self.subTest(valor=valor):
                tablas = dict(self.tablas, nodos=f'id,x,y\nA,"{valor}",0\nB,4,0\nC,4,3\nD,0,3\n')
                with self.assertRaises(ErrorImportacionTabular):
                    convertir_tablas(self.meta, tablas)

    def test_cabeceras_extra_duplicadas_ausentes_rechazadas(self):
        for texto in ("id,x,y,extra\nA,0,0,x\n", "id,x,y,x\nA,0,0,0\n",
                      "id,x\nA,0\n", "id, x,y\nA,0,0\n", "", "\n"):
            with self.subTest(csv=texto), self.assertRaises(ErrorImportacionTabular):
                convertir_tablas(self.meta, dict(self.tablas, nodos=texto))

    def test_filas_truncadas_o_excedidas_rechazadas(self):
        for fila in ("A,0", "A,0,0,sobra", 'A,"0,0'):
            with self.subTest(fila=fila), self.assertRaises(ErrorImportacionTabular):
                convertir_tablas(self.meta, dict(self.tablas, nodos="id,x,y\n" + fila))

    def test_referencias_rotas_y_ids_duplicados(self):
        for texto in (self.tablas["nodos"].replace("B,4.0", "ZZ,4.0"),
                      self.tablas["nodos"] + "A,0,0\n"):
            with self.subTest(csv=texto), self.assertRaises(ErrorImportacionTabular):
                convertir_tablas(self.meta, dict(self.tablas, nodos=texto))

    def test_unidad_explicita_sin_inferencia(self):
        for valor in (None, "", "px", "metros"):
            with self.subTest(unidad=valor), self.assertRaises(ErrorImportacionTabular):
                convertir_tablas(dict(self.meta, unidad_longitud=valor), self.tablas)
        centimetros = convertir_tablas(dict(self.meta, unidad_longitud="cm"), self.tablas)
        self.assertEqual(centimetros["nodos"][1]["x"], 4)
        self.assertEqual(validar_geometria(centimetros).geometria_m["nodos"][1]["x"], .04)

    def test_no_importa_aprobaciones(self):
        for revision in ({"estado": "aprobado", "aprobacion": {}},
                         {"estado": "borrador", "aprobacion": {"persona": "x"}}):
            with self.subTest(revision=revision), self.assertRaises(ErrorImportacionTabular):
                convertir_tablas(dict(self.meta, revision=revision), self.tablas)

    def test_metadatos_y_tablas_exactos(self):
        for meta in (dict(self.meta, nodos=[]), dict(self.meta, extra="x"),
                     {k: v for k, v in self.meta.items() if k != "procedencia"}):
            with self.subTest(meta=meta), self.assertRaises(ErrorImportacionTabular):
                convertir_tablas(meta, self.tablas)
        with self.assertRaises(ErrorImportacionTabular):
            convertir_tablas(self.meta, dict(self.tablas, cargas="id,carga\n"))

    def test_bom_csv_aceptado(self):
        self.assertEqual(convertir_tablas(self.meta, self.tablas),
                         convertir_tablas(self.meta, {k: "\ufeff" + v for k, v in self.tablas.items()}))

    def test_procedencia_por_elemento_json_conservada(self):
        import csv
        import io
        salida_csv = io.StringIO(newline="")
        writer = csv.writer(salida_csv)
        writer.writerow(["id", "x", "y", "procedencia"])
        origen = {"tipo": "sintetico", "descripcion": "Nodo manual sintético"}
        for nodo in ("A,0,0", "B,4,0", "C,4,3", "D,0,3"):
            writer.writerow(nodo.split(",") + [json.dumps(origen)])
        salida = convertir_tablas(self.meta, dict(self.tablas, nodos=salida_csv.getvalue()))
        self.assertEqual(salida["nodos"][0]["procedencia"], origen)

    def _argumentos(self, salida, metadatos=None):
        args = ["--metadatos", str(metadatos or EJEMPLO / "metadatos.json")]
        for nombre in self.tablas:
            args += ["--" + nombre, str(EJEMPLO / f"{nombre}.csv")]
        return args + ["--salida", str(salida)]

    def test_cli_salida_nueva_y_rechazo_sobrescritura(self):
        with tempfile.TemporaryDirectory() as carpeta:
            destino = Path(carpeta) / "geometria.json"
            self.assertEqual(main(self._argumentos(destino)), 0)
            inicial = destino.read_bytes()
            self.assertEqual(main(self._argumentos(destino)), 1)
            self.assertEqual(destino.read_bytes(), inicial)
            self.assertEqual(json.loads(inicial), convertir_tablas(self.meta, self.tablas))

    def test_cli_entrada_como_salida_no_modifica_original(self):
        with tempfile.TemporaryDirectory() as carpeta:
            meta = Path(carpeta) / "meta.json"
            inicial = json.dumps(self.meta).encode()
            meta.write_bytes(inicial)
            self.assertEqual(main(self._argumentos(meta, meta)), 1)
            self.assertEqual(meta.read_bytes(), inicial)

    def test_cli_metadatos_duplicados_no_crean_salida(self):
        with tempfile.TemporaryDirectory() as carpeta:
            meta = Path(carpeta) / "meta.json"
            destino = Path(carpeta) / "salida.json"
            meta.write_text('{"id":"a","id":"b"}', encoding="utf-8")
            self.assertEqual(main(self._argumentos(destino, meta)), 1)
            self.assertFalse(destino.exists())


if __name__ == "__main__":
    unittest.main()
