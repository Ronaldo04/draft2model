"""Comandos de versiones geométricas en una raíz temporal con datos sintéticos."""

import contextlib
import io
import json
import re
import tempfile
import unittest
from pathlib import Path

from draft2model.__main__ import main

EJEMPLO = Path(__file__).resolve().parents[1] / "examples" / "geometria_sintetica.json"
CASO = "sintetico-001"  # coincide con el id de examples/geometria_sintetica.json
HUELLA_AJENA = "0" * 64


def instantanea(carpeta: Path) -> dict:
    return {p.relative_to(carpeta).as_posix(): p.read_bytes() for p in sorted(carpeta.rglob("*")) if p.is_file()}


class CliGeometriaTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.trabajo = Path(temp.name)
        self.raiz = self.trabajo / "private"
        pdf = self.trabajo / "plano_sintetico.pdf"
        pdf.write_bytes(b"%PDF-1.4\ncontenido sintetico para pruebas de la CLI de geometria\n")
        # El comando de ingreso existente sigue funcionando junto a los nuevos.
        codigo, salida, errores = self.cli("ingresar", "--caso", CASO, "--archivos", str(pdf),
                                           "--uso-autorizado", "--provisional-fuera-alcance")
        self.assertEqual(codigo, 0, errores)
        self.caso_dir = self.raiz / CASO
        self.geometrias = self.caso_dir / "geometrias"
        self.original = self.caso_dir / "originales" / "lamina-0001.pdf"
        self.entrada = self.trabajo / "geometria.json"
        self.entrada.write_bytes(EJEMPLO.read_bytes())  # incluye un espesor faltante declarado (M4)

    # -- utilidades -----------------------------------------------------------
    def cli(self, *argv):
        salida, errores = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(salida), contextlib.redirect_stderr(errores):
            codigo = main([str(a) for a in argv], raiz=self.raiz)
        return codigo, salida.getvalue(), errores.getvalue()

    def id_de(self, texto, etiqueta):
        coincidencia = re.search(etiqueta + r": ([0-9a-f]{32})", texto)
        self.assertIsNotNone(coincidencia, texto)
        return coincidencia.group(1)

    def escribir(self, data, nombre="propuesta.json"):
        ruta = self.trabajo / nombre
        ruta.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        return ruta

    def completa(self):
        data = json.loads(EJEMPLO.read_text(encoding="utf-8"))
        data["muros"][3]["espesor"] = 0.15
        data["faltantes"] = []
        return data

    def importar(self):
        codigo, salida, errores = self.cli("importar-geometria", "--caso", CASO, "--entrada", self.entrada)
        self.assertEqual(codigo, 0, errores)
        return self.id_de(salida, "Geometría registrada")

    def consultar(self, version):
        codigo, salida, errores = self.cli("consultar-geometria", "--caso", CASO, "--geometria", version, "--json")
        self.assertEqual(codigo, 0, errores)
        return json.loads(salida)

    def revisar(self, padre, propuesta=None, *extra):
        ruta = propuesta or self.escribir(self.completa())
        base = ("revisar-geometria", "--caso", CASO, "--geometria", padre, "--propuesta", ruta)
        resto = {"--motivo": "Se completa el espesor de M4.", "--fecha": "2026-10-16", "--revisor": "Revisor sintético"}
        return self.cli(*base, *self.argumentos(resto, extra))

    def aprobar(self, version, huella, *extra):
        base = ("aprobar-geometria", "--caso", CASO, "--geometria", version)
        resto = {"--huella-esperada": huella, "--revisor": "Revisor sintético", "--fecha": "2026-10-16",
                 "--motivo": "Geometría sintética completa revisada.", "--alcance": "Niveles, nodos y muros sintéticos."}
        return self.cli(*base, *self.argumentos(resto, extra))

    @staticmethod
    def argumentos(base, extra):
        """Combina argumentos por defecto con reemplazos; un valor None omite la opción."""
        valores = dict(base)
        valores.update(dict(zip(extra[::2], extra[1::2])))
        return [x for clave, valor in valores.items() if valor is not None for x in (clave, valor)]

    def versiones(self):
        return sorted(p.name for p in self.geometrias.iterdir()) if self.geometrias.exists() else []

    # -- flujo completo -------------------------------------------------------
    def test_importacion_consulta_revision_aprobacion(self):
        v0 = self.importar()
        datos = self.consultar(v0)
        self.assertEqual(datos["geometria"], json.loads(EJEMPLO.read_text(encoding="utf-8")))
        self.assertEqual(datos["metadatos"]["operacion"], "importacion")
        self.assertTrue(datos["comprobacion"]["correcta"])
        self.assertEqual([f["id"] for f in datos["comprobacion"]["validacion"]["faltantes"]], ["M4"])
        huella_v0 = datos["comprobacion"]["huella_contenido"]

        codigo, salida, _ = self.cli("comprobar-geometria", "--caso", CASO, "--geometria", v0)
        self.assertEqual(codigo, 0, salida)
        self.assertIn("SHA256 comprobado: original L0001", salida)
        self.assertIn("identidad y competencia no se verifican", salida)

        # Con faltantes no se aprueba, aunque la huella sea la correcta.
        codigo, _, errores = self.aprobar(v0, huella_v0)
        self.assertEqual(codigo, 2, errores)
        self.assertIn("faltante", errores)
        self.assertEqual(self.versiones(), [v0])

        antes = instantanea(self.geometrias / v0)
        codigo, salida, errores = self.revisar(v0)
        self.assertEqual(codigo, 0, errores)
        v1 = self.id_de(salida, "Nueva versión geométrica")
        self.assertEqual(instantanea(self.geometrias / v0), antes)
        revision = self.consultar(v1)
        self.assertEqual(revision["metadatos"]["revision"]["revisor_declarado"], "Revisor sintético")
        self.assertEqual(revision["geometria"]["revision"], {"estado": "borrador", "aprobacion": None})
        self.assertEqual(revision["comprobacion"]["cadena"], [v1, v0])
        huella_v1 = revision["comprobacion"]["huella_contenido"]

        antes = instantanea(self.geometrias)
        codigo, salida, errores = self.aprobar(v1, huella_v1)
        self.assertEqual(codigo, 0, errores)
        v2 = self.id_de(salida, "Aprobación registrada")
        self.assertIn("no certifica seguridad estructural", salida)
        for ruta, contenido in antes.items():  # nada anterior se sobrescribe
            self.assertEqual((self.geometrias / ruta).read_bytes(), contenido)

        aprobada = self.consultar(v2)
        registro = aprobada["metadatos"]["aprobacion"]
        self.assertEqual(registro["huella_esperada"], huella_v1)
        self.assertEqual(registro["alcance_revision"], "Niveles, nodos y muros sintéticos.")
        self.assertEqual(registro["identidad_revisor"], "declarada_no_verificada")
        self.assertFalse(registro["certifica_seguridad_estructural"])
        self.assertFalse(registro["aprueba_artefactos_derivados"])
        self.assertTrue(aprobada["metadatos"]["datos_sinteticos"])
        self.assertEqual(aprobada["metadatos"]["alcance"]["estado"], "fuera_mvp_declarado")
        self.assertEqual(aprobada["comprobacion"]["cadena"], [v2, v1, v0])
        self.assertEqual(sorted(self.versiones()), sorted([v0, v1, v2]))

        # Una versión aprobada no se vuelve a aprobar.
        codigo, _, errores = self.aprobar(v2, huella_v1)
        self.assertEqual(codigo, 2, errores)
        self.assertEqual(len(self.versiones()), 3)

    # -- huella y evidencia ---------------------------------------------------
    def test_huella_erronea_no_aprueba(self):
        v0 = self.importar()
        codigo, salida, _ = self.revisar(v0)
        v1 = self.id_de(salida, "Nueva versión geométrica")
        codigo, _, errores = self.aprobar(v1, HUELLA_AJENA)
        self.assertEqual(codigo, 2, errores)
        self.assertIn("huella esperada no coincide", errores)
        # Formato inválido o huella ausente: solicitud rechazada.
        for huella in ("abc", "A" * 64, None):
            with self.subTest(huella=huella):
                self.assertEqual(self.aprobar(v1, huella)[0], 1)
        self.assertEqual(len(self.versiones()), 2)

    def test_evidencia_alterada(self):
        v0 = self.importar()
        codigo, salida, _ = self.revisar(v0)
        v1 = self.id_de(salida, "Nueva versión geométrica")
        huella = self.consultar(v1)["comprobacion"]["huella_contenido"]

        self.original.write_bytes(self.original.read_bytes() + b"%alterado\n")
        for comando in ("comprobar-geometria", "consultar-geometria"):
            with self.subTest(comando=comando):
                codigo, salida, errores = self.cli(comando, "--caso", CASO, "--geometria", v1)
                self.assertEqual(codigo, 2, salida)
                self.assertIn("alterado", salida)
                self.assertIn("no supera la comprobación", errores)
        self.assertEqual(self.aprobar(v1, huella)[0], 2)
        self.assertEqual(self.revisar(v1)[0], 2)
        self.assertEqual(len(self.versiones()), 2)

    def test_geometria_guardada_alterada(self):
        v0 = self.importar()
        archivo = self.geometrias / v0 / "geometria.json"
        archivo.write_bytes(archivo.read_bytes().replace(b"2.6", b"2.7", 1))
        codigo, salida, _ = self.cli("comprobar-geometria", "--caso", CASO, "--geometria", v0, "--json")
        self.assertEqual(codigo, 2)
        self.assertFalse(json.loads(salida)["correcta"])
        self.assertEqual(self.revisar(v0)[0], 2)
        self.assertEqual(self.versiones(), [v0])

    # -- solicitudes y propuestas rechazadas -----------------------------------
    def test_solicitudes_invalidas_codigo_1(self):
        v0 = self.importar()
        casos = {
            "caso fuera": ("comprobar-geometria", "--caso", "../fuera", "--geometria", v0),
            "caso inexistente": ("comprobar-geometria", "--caso", "otro", "--geometria", v0),
            "id inválido": ("consultar-geometria", "--caso", CASO, "--geometria", "no-es-un-id"),
            "id inexistente": ("comprobar-geometria", "--caso", CASO, "--geometria", "f" * 32),
            "entrada ausente": ("importar-geometria", "--caso", CASO, "--entrada", self.trabajo / "nada.json"),
        }
        for nombre, argv in casos.items():
            with self.subTest(nombre):
                self.assertEqual(self.cli(*argv)[0], 1)
        for nombre, extra in {"sin propuesta": ("--propuesta", None), "sin motivo": ("--motivo", None),
                              "sin revisor": ("--revisor", None), "revisor vacío": ("--revisor", "  "),
                              "fecha inválida": ("--fecha", "16/10/2026"),
                              "propuesta ausente": ("--propuesta", self.trabajo / "nada.json")}.items():
            with self.subTest(nombre):
                if extra[0] == "--propuesta":
                    base = ("revisar-geometria", "--caso", CASO, "--geometria", v0, "--motivo", "m",
                            "--fecha", "2026-10-16", "--revisor", "R")
                    argv = base + (("--propuesta", extra[1]) if extra[1] is not None else ())
                    codigo, _, errores = self.cli(*argv)
                else:
                    codigo, _, errores = self.revisar(v0, None, *extra)
                self.assertEqual(codigo, 1, errores)
        for nombre, extra in {"sin alcance": ("--alcance", None), "sin fecha": ("--fecha", None)}.items():
            with self.subTest(nombre):
                self.assertEqual(self.aprobar(v0, HUELLA_AJENA, *extra)[0], 1)
        self.assertEqual(self.versiones(), [v0])

    def test_propuestas_rechazadas(self):
        v0 = self.importar()
        repetida = self.trabajo / "repetida.json"
        repetida.write_text(EJEMPLO.read_text(encoding="utf-8").replace('"id": "sintetico-001",',
                            '"id": "sintetico-001", "id": "sintetico-001",', 1), encoding="utf-8")
        no_finita = self.trabajo / "no_finita.json"
        no_finita.write_text(EJEMPLO.read_text(encoding="utf-8").replace('"cota": 2.6', '"cota": NaN', 1),
                             encoding="utf-8")
        self.assertEqual(self.revisar(v0, repetida)[0], 1)
        self.assertEqual(self.revisar(v0, no_finita)[0], 1)

        aprobada = self.completa()
        aprobada["revision"] = {"estado": "aprobado", "aprobacion": {
            "declarada_por": "X", "fecha": "2026-10-16", "huella_contenido": HUELLA_AJENA, "alcance": "a",
            "observaciones": "o"}}
        otro_caso = self.completa()
        otro_caso["id"] = "otro-caso"
        real = self.completa()
        real["procedencia"] = {"tipo": "expediente", "descripcion": "Procedencia no sintética."}
        for nombre, data in {"aprobación heredada": aprobada, "otro caso": otro_caso,
                             "sintético a real": real}.items():
            with self.subTest(nombre):
                codigo, _, errores = self.revisar(v0, self.escribir(data, nombre.replace(" ", "_") + ".json"))
                self.assertEqual(codigo, 2, errores)
        # Importar una geometría con aprobación declarada también se rechaza.
        codigo, _, errores = self.cli("importar-geometria", "--caso", CASO, "--entrada", self.escribir(aprobada, "ap.json"))
        self.assertEqual(codigo, 2, errores)
        self.assertEqual(self.versiones(), [v0])

    # -- salida sin sobrescritura ---------------------------------------------
    def test_salida_de_consulta_no_sobrescribe(self):
        v0 = self.importar()
        destino = self.trabajo / "consulta.json"
        codigo, salida, errores = self.cli("consultar-geometria", "--caso", CASO, "--geometria", v0, "--salida", destino)
        self.assertEqual(codigo, 0, errores)
        self.assertIn("Resultado guardado en", salida)
        datos = json.loads(destino.read_text(encoding="utf-8"))
        self.assertEqual(datos["version_id"], v0)
        self.assertTrue(datos["comprobacion"]["correcta"])

        destino.write_text("previo", encoding="utf-8")
        codigo, _, errores = self.cli("consultar-geometria", "--caso", CASO, "--geometria", v0, "--salida", destino)
        self.assertEqual(codigo, 1, errores)
        self.assertIn("no se sobrescribe", errores)
        self.assertEqual(destino.read_text(encoding="utf-8"), "previo")
        codigo, _, _ = self.cli("consultar-geometria", "--caso", CASO, "--geometria", v0,
                                "--salida", self.trabajo / "no_existe" / "c.json")
        self.assertEqual(codigo, 1)


if __name__ == "__main__":
    unittest.main()
