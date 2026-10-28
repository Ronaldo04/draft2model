"""Regresión del esquema CSI real (ETABS 21.1) y de la ejecución dinámica que se detuvo con -96.

Evidencia de Codex, solo lectura sobre una copia real (17-10-2026):
- tmp/d1/tablas_dinamicas_reales.json y tmp/d1/tablas_damping_reales.json (esquemas de tabla);
- tmp/d1/construccion/b8b0a4e515d64767aeceaae1001e9fc6 (plan de 66 operaciones detenido en la operación 13,
  GetAllFieldsInTable('Load Cases - Response Spectrum') = -96, sin mutaciones).
La evidencia está conservada en tests/fixtures/etabs21_sintetico; no requiere tmp de la sesión.
"""

import json
import re
import tempfile
import unittest
from pathlib import Path

from draft2model import operaciones_etabs as o
from tests.fixture_etabs import extraer_evidencia

RAIZ = Path(__file__).resolve().parents[1]
SCRIPT_LECTURA = RAIZ / "scripts" / "leer_vocabulario_dinamico_etabs.ps1"
CLAVE_INVENTADA = "Load Cases - Response Spectrum"


def _leer(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8-sig"))


class EsquemaEmbebidoTests(unittest.TestCase):
    def test_tablas_editables_son_subconjunto_importable_de_lo_observado(self):
        for tabla, definicion in o.TABLAS_EDITABLES.items():
            with self.subTest(tabla):
                self.assertIn(tabla, o.ESQUEMAS_OBSERVADOS)
                esquema = o.ESQUEMAS_OBSERVADOS[tabla]
                importables = dict(zip(esquema["campos"], esquema["importables"]))
                for campo in definicion["campos"]:
                    self.assertIn(campo, importables)
                    self.assertTrue(importables[campo], f"{tabla}.{campo} no es importable")
                self.assertIn(definicion["clave"], definicion["campos"])

    def test_correcciones_del_esquema_real(self):
        self.assertNotIn(CLAVE_INVENTADA, o.TABLAS_EDITABLES)
        self.assertNotIn(CLAVE_INVENTADA, o.ESQUEMAS_OBSERVADOS)
        self.assertEqual(o.TABLA_CASO_RS, "Load Case Definitions - Response Spectrum")
        self.assertNotIn("ConstDamp", o.ESQUEMAS_OBSERVADOS[o.TABLA_CASO_RS]["campos"])
        self.assertNotIn("ConstDamp", o.TABLAS_EDITABLES[o.TABLA_CASO_RS]["campos"])
        self.assertEqual(o.TABLAS_EDITABLES[o.TABLA_AMORTIGUAMIENTO_MODAL]["campos"], ("Name", "ConstDamp"))
        caso = dict(zip(o.ESQUEMAS_OBSERVADOS[o.TABLA_CASO_RS]["campos"], o.ESQUEMAS_OBSERVADOS[o.TABLA_CASO_RS]["importables"]))
        self.assertEqual([c for c, i in caso.items() if not i], ["MassSource", "CoordSys"])

    def test_esquemas_coherentes(self):
        for tabla, esquema in o.ESQUEMAS_OBSERVADOS.items():
            with self.subTest(tabla):
                self.assertEqual(len(esquema["campos"]), len(esquema["importables"]))
                self.assertEqual(len(esquema["campos"]), len(esquema["unidades"]))
                self.assertEqual(len(set(esquema["campos"])), len(esquema["campos"]))


class EvidenciaRealTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.evidencia=extraer_evidencia(Path(temp.name)/'fixture')/'esquema'

    def test_esquemas_embebidos_iguales_a_la_lectura_real(self):
        vistos = set()
        for nombre in ("tablas_dinamicas_reales.json", "tablas_damping_reales.json"):
            evidencia = _leer(self.evidencia / nombre)
            self.assertIs(evidencia["solo_lectura"], True)
            for tabla in evidencia["tablas"]:
                if tabla["tabla"] not in o.ESQUEMAS_OBSERVADOS:
                    continue
                vistos.add(tabla["tabla"])
                esquema = o.ESQUEMAS_OBSERVADOS[tabla["tabla"]]
                with self.subTest(nombre=nombre, tabla=tabla["tabla"]):
                    self.assertEqual(tabla["retorno_campos"], 0)
                    self.assertEqual(tuple(tabla["campos"]), esquema["campos"])
                    self.assertEqual(tuple(tabla["importables"]), esquema["importables"])
                    self.assertEqual(tuple(tabla["unidades"]), esquema["unidades"])
                    self.assertEqual((tabla["version"], tabla["tipo_importacion"]), (esquema["version"], esquema["tipo_importacion"]))
        # Tabla no uniforme (plan 0.5): evidencia real 185 distribuible en tests/fixtures (GetAllFieldsInTable, ETABS 21.1).
        real = _leer(Path(__file__).resolve().parent / "fixtures" / "tabla_no_uniforme_etabs21_185.json")["tabla"]
        esquema = o.ESQUEMAS_OBSERVADOS[real["clave"]]
        with self.subTest(tabla=real["clave"]):
            self.assertEqual(tuple(real["campos"]), esquema["campos"])
            self.assertEqual(tuple(real["importables"]), esquema["importables"])
            self.assertEqual((real["version"], real["tipo_importacion"]), (esquema["version"], esquema["tipo_importacion"]))
        vistos.add(real["clave"])
        self.assertEqual(vistos, set(o.ESQUEMAS_OBSERVADOS))

    def test_la_clave_inventada_no_figura_en_la_lectura_real(self):
        for nombre in ("tablas_dinamicas_reales.json", "tablas_damping_reales.json"):
            claves = {t["tabla"] for t in _leer(self.evidencia / nombre)["tablas"]}
            self.assertNotIn(CLAVE_INVENTADA, claves)


class CorridaRealFallidaTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        self.corrida=extraer_evidencia(Path(temp.name)/'fixture')/'esquema/construccion/b8b0a4e515d64767aeceaae1001e9fc6'

    def test_fallo_observado_y_su_correccion(self):
        respuesta = _leer(self.corrida / "respuesta.json")
        self.assertEqual((respuesta["error"]["codigo_api"], respuesta["progreso"]["orden_fallida"]), (o.RETORNO_TABLA_INEXISTENTE_OBSERVADO, 13))
        self.assertIs(respuesta["progreso"]["mutaciones_realizadas"], False)
        plan = _leer(self.corrida / "plan.json")
        op13 = plan["operaciones"][12]
        self.assertEqual((op13["metodo"], op13["argumentos"][0]["valor"]), ("cDatabaseTables.GetAllFieldsInTable", CLAVE_INVENTADA))
        # El plan antiguo ya no supera validar_plan: el ejecutor lo rechazaría antes de lanzar ETABS.
        problemas = o.validar_plan(plan)
        self.assertTrue(any("tabla no admitida" in p for p in problemas), problemas)
        # Y la clave que falló no se usa en ninguna verificación ni edición del generador actual.
        self.assertNotIn(CLAVE_INVENTADA, json.dumps(o.TABLAS_EDITABLES))


class ScriptLecturaTests(unittest.TestCase):
    def setUp(self):
        self.bytes = SCRIPT_LECTURA.read_bytes()
        self.texto = self.bytes.decode("utf-8-sig")

    def test_solo_lectura(self):
        self.assertTrue(self.bytes.startswith(b"\xef\xbb\xbf"))
        mutaciones = re.findall(r"\.(Set\w*|Apply\w*|Add\w*|Delete\w*|Save|OpenFile|RunAnalysis|ApplicationExit|"
                                r"ApplicationStart|InitializeNewModel|CancelTableEditing)\s*\(", self.texto)
        self.assertEqual(mutaciones, [])
        llamadas = set(re.findall(r"\$(?:db|rs|me|lc|sap|helper)\.(\w+)\(", self.texto))
        self.assertTrue(llamadas)
        self.assertTrue(all(n.startswith("Get") for n in llamadas), llamadas)
        for prohibido in ("ExecutionPolicy", "Invoke-Expression", "Remove-Item", "Set-Content", "Out-File"):
            self.assertNotIn(prohibido, self.texto)
        self.assertIn("CreateNew", self.texto)  # la salida nunca se sobrescribe
        for tabla in o.TABLAS_EDITABLES:
            self.assertIn(tabla, self.texto)


if __name__ == "__main__":
    unittest.main()
