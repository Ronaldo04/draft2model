"""CLI completa en una raíz temporal: ingresar, revisar, recortar y comandos de extracción."""

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

import pymupdf

from draft2model.__main__ import main

CASO = "sintetico-cli"


class CliExtraccionTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.trabajo = Path(temp.name)
        self.raiz = self.trabajo / "private"
        pdf = self.trabajo / "plano_sintetico.pdf"
        with pymupdf.open() as doc:
            doc.new_page(width=400, height=300).draw_rect((50, 50, 350, 250), color=(0, 0, 0))
            doc.save(pdf)
        # Los comandos existentes siguen funcionando con la raíz configurable.
        codigo, salida, _ = self.cli("ingresar", "--caso", CASO, "--archivos", str(pdf),
                                     "--uso-autorizado", "--provisional-fuera-alcance")
        self.assertEqual(codigo, 0, salida)
        self.assertEqual(self.cli("revisar", "--caso", CASO, "--max-lado", "256")[0], 0)
        codigo, salida, _ = self.cli("recortar", "--caso", CASO, "--archivo", "L0001", "--pagina", "1",
                                     "--bbox", "0", "0", "0.5", "0.5", "--dpi", "72")
        self.assertEqual(codigo, 0, salida)
        self.caso_dir = self.raiz / CASO
        expediente = json.loads((self.caso_dir / "expediente.json").read_text(encoding="utf-8"))
        recorte = json.loads(next((self.caso_dir / "recortes").glob("*/recorte.json")).read_text(encoding="utf-8"))
        evidencia = {"archivo_id": "L0001", "pagina": 1, "original_sha256": expediente["archivos"][0]["sha256"],
                     "recorte_id": recorte["id"], "imagen_sha256": recorte["imagen_sha256"],
                     "bbox_normalizada": [0.1, 0.1, 0.2, 0.2]}
        self.entrada = self.trabajo / "extraccion.json"
        self.entrada.write_text(json.dumps({
            "contrato": "draft2model.extraccion_preliminar", "version_contrato": "0.1.0", "caso": CASO,
            "procedencia": {"tipo": "expediente", "descripcion": "Lectura manual sintética."},
            "alcance": expediente["alcance"], "sistema_coordenadas": "pagina_visible_normalizada",
            "candidatos": [
                {"id": "C001", "tipo": "cota", "valor_propuesto": 2.6, "unidad": "m",
                 "metodo": {"tipo": "manual"}, "evidencia": [evidencia]},
                {"id": "C002", "tipo": "etiqueta", "valor_propuesto": "EJE A", "unidad": "no_aplica",
                 "metodo": {"tipo": "manual"}, "evidencia": [evidencia]},
            ],
        }), encoding="utf-8")

    def cli(self, *argv):
        salida, errores = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(errores):
            codigo = main(list(argv), raiz=self.raiz)
        return codigo, salida.getvalue(), errores.getvalue()

    def version_id(self, texto, etiqueta):
        coincidencia = re.search(etiqueta + r": ([0-9a-f]{32})", texto)
        self.assertIsNotNone(coincidencia, texto)
        return coincidencia.group(1)

    def corregir(self, padre, *extra):
        base = ("corregir-extraccion", "--caso", CASO, "--extraccion", padre, "--candidato", "C001",
                "--motivo", "Lectura confirmada.", "--fecha", "2026-10-15", "--revisor", "Revisor sintético")
        return self.cli(*base, *extra)

    def test_flujo_por_linea_de_comandos(self):
        codigo, salida, errores = self.cli("importar-extraccion", "--caso", CASO, "--entrada", str(self.entrada))
        self.assertEqual(codigo, 0, errores)
        self.assertIn("Revisión técnica pendiente", salida)
        self.assertIn("fuera_mvp", salida)
        v0 = self.version_id(salida, "Extracción registrada")

        codigo, salida, _ = self.cli("validar-extraccion", "--caso", CASO, "--extraccion", v0)
        self.assertEqual(codigo, 0, salida)
        self.assertIn("comprobada 2", salida)

        codigo, salida, errores = self.corregir(v0, "--estado", "revisado", "--valor-json", "2.65", "--unidad", "m")
        self.assertEqual(codigo, 0, errores)
        v1 = self.version_id(salida, "Nueva versión")
        self.assertIn("identidad no se verifica", salida)

        codigo, salida, errores = self.cli("exportar-extraccion", "--caso", CASO, "--extraccion", v1)
        self.assertEqual(codigo, 0, errores)
        self.assertIn("Revisados exportados: 1; pendientes excluidos: 1; rechazados excluidos: 0", salida)
        exportacion = next((self.caso_dir / "extracciones_exportadas").glob("*/exportacion.json"))
        datos = json.loads(exportacion.read_text(encoding="utf-8"))
        self.assertEqual(datos["candidatos"][0]["valor_revisado"], 2.65)
        self.assertEqual(datos["alcance"]["estado"], "fuera_mvp_declarado")
        self.assertIsNone(datos["aprobacion_ingenieria"])

    def test_valor_json_no_convierte_texto_ni_booleanos(self):
        v0 = self.version_id(self.cli("importar-extraccion", "--caso", CASO, "--entrada", str(self.entrada))[1],
                             "Extracción registrada")
        # Cadena JSON para una cota: el registro la rechaza (código 2), no la convierte.
        codigo, _, errores = self.corregir(v0, "--estado", "revisado", "--valor-json", '"2.65"', "--unidad", "m")
        self.assertEqual(codigo, 2, errores)
        for valor in ("true", "NaN", "[1]", "2,65", "__import__('os')"):
            with self.subTest(valor=valor):
                codigo, _, errores = self.corregir(v0, "--estado", "revisado", "--valor-json", valor, "--unidad", "m")
                self.assertEqual(codigo, 1, errores)
        codigo, _, _ = self.corregir(v0, "--estado", "revisado", "--unidad", "m")
        self.assertEqual(codigo, 2)
        self.assertEqual(len(list((self.caso_dir / "extracciones").iterdir())), 1)

    def test_codigos_de_retorno(self):
        codigo, _, errores = self.cli("importar-extraccion", "--caso", "../fuera", "--entrada", str(self.entrada))
        self.assertEqual(codigo, 1, errores)
        codigo, _, errores = self.cli("validar-extraccion", "--caso", CASO, "--extraccion", "no-es-un-id")
        self.assertEqual(codigo, 1, errores)
        v0 = self.version_id(self.cli("importar-extraccion", "--caso", CASO, "--entrada", str(self.entrada))[1],
                             "Extracción registrada")
        original = self.caso_dir / "originales" / "lamina-0001.pdf"
        original.write_bytes(original.read_bytes() + b"%cambio\n")
        codigo, salida, _ = self.cli("validar-extraccion", "--caso", CASO, "--extraccion", v0)
        self.assertEqual(codigo, 2)
        self.assertIn("alterado", salida)
        codigo, _, errores = self.cli("exportar-extraccion", "--caso", CASO, "--extraccion", v0)
        self.assertEqual(codigo, 2)
        self.assertIn("no se guardó nada", errores)
        self.assertFalse((self.caso_dir / "extracciones_exportadas").exists())

    def test_revision_malformada_devuelve_rechazo_sin_traceback(self):
        ruta = next((self.caso_dir / "revision_documental").glob("*/revision.json"))
        respaldo = ruta.read_bytes()
        for documentos in ([None], "documentos", [{"id": 5, "archivo": None}]):
            with self.subTest(documentos=documentos):
                meta = json.loads(respaldo)
                meta["documentos"] = documentos
                ruta.write_text(json.dumps(meta), encoding="utf-8")
                codigo, salida, errores = self.cli("importar-extraccion", "--caso", CASO, "--entrada", str(self.entrada))
                self.assertEqual(codigo, 2, salida + errores)
                self.assertNotIn("Traceback", errores)
                self.assertIn(f"Revisión {ruta.parent.name}", errores)
                self.assertIn("no se guardó nada", errores)
        self.assertFalse((self.caso_dir / "extracciones").exists())

    def test_fuente_y_coordenadas_alteradas_devuelven_2(self):
        v0 = self.version_id(self.cli("importar-extraccion", "--caso", CASO, "--entrada", str(self.entrada))[1],
                             "Extracción registrada")
        fuente = self.caso_dir / "extracciones" / v0 / "fuente_importada.json"
        respaldo = fuente.read_bytes()
        fuente.write_text("{}", encoding="utf-8")
        codigo, salida, _ = self.cli("validar-extraccion", "--caso", CASO, "--extraccion", v0)
        self.assertEqual(codigo, 2, salida)
        self.assertIn("fuente", salida.lower())
        fuente.write_bytes(respaldo)
        self.assertEqual(self.cli("validar-extraccion", "--caso", CASO, "--extraccion", v0)[0], 0)
        recorte = next((self.caso_dir / "recortes").glob("*/recorte.json"))
        meta = json.loads(recorte.read_text(encoding="utf-8"))
        meta["sistema_coordenadas"] = "pixeles_sin_rotacion"
        recorte.write_text(json.dumps(meta), encoding="utf-8")
        codigo, salida, _ = self.cli("validar-extraccion", "--caso", CASO, "--extraccion", v0)
        self.assertEqual(codigo, 2, salida)
        self.assertIn("sistema de coordenadas", salida)
        codigo, _, errores = self.cli("exportar-extraccion", "--caso", CASO, "--extraccion", v0)
        self.assertEqual(codigo, 2, errores)
        self.assertFalse((self.caso_dir / "extracciones_exportadas").exists())

    def test_destino_enlazado_fuera_del_caso(self):
        from test_gestion_extraccion import enlazar_carpeta, quitar_enlace

        externo = self.trabajo / "fuera_del_caso"
        externo.mkdir()
        enlace = self.caso_dir / "extracciones"
        if enlazar_carpeta(enlace, externo) is None:
            self.skipTest("El sistema no permite crear junctions ni enlaces simbólicos de carpeta.")
        self.addCleanup(quitar_enlace, enlace)
        codigo, _, errores = self.cli("importar-extraccion", "--caso", CASO, "--entrada", str(self.entrada))
        self.assertEqual(codigo, 1, errores)
        self.assertIn("fuera del caso", errores)
        self.assertEqual(list(externo.iterdir()), [])

    def test_ayuda_de_comandos(self):
        opciones = {
            "importar-extraccion": ("--caso", "--entrada"),
            "validar-extraccion": ("--extraccion",),
            "corregir-extraccion": ("--candidato", "--estado", "--motivo", "--fecha", "--revisor", "--valor-json", "--unidad"),
            "exportar-extraccion": ("--extraccion",),
            "ingresar": ("--uso-autorizado",),
        }
        for comando, esperadas in opciones.items():
            with self.subTest(comando=comando):
                salida = io.StringIO()
                with contextlib.redirect_stdout(salida), self.assertRaises(SystemExit) as ctx:
                    main([comando, "--help"], raiz=self.raiz)
                self.assertEqual(ctx.exception.code, 0)
                for opcion in esperadas:
                    self.assertIn(opcion, salida.getvalue())


if __name__ == "__main__":
    unittest.main()
