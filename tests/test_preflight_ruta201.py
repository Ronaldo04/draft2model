"""Etapa 03 (ruta 201): validación previa accionable y proveedores operativos solo Google/OpenAI. Sin ETABS, red ni claves."""
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from draft2model import preflight as pf
from draft2model.revision_visual import RevisionLocal
from tests import test_revision_visual as httpfixtures
from tests import test_modelo_estructural as fixtures


class PreflightTests(unittest.TestCase):
    def setUp(self):
        t = tempfile.TemporaryDirectory(); self.addCleanup(t.cleanup)
        self.dir = Path(t.name)

    def test_dll_ausente_o_version_distinta_son_errores_accionables(self):
        r = pf.comprobar_etabs(self.dir / "no_existe.dll")
        self.assertEqual(r[0]["estado"], "error"); self.assertIn("Instale ETABS", r[0]["accion"])
        dll = self.dir / "ETABSv1.dll"; dll.write_bytes(b"MZ")
        with mock.patch.object(pf, "version_archivo", return_value="1.30.0.0"):
            r = pf.comprobar_etabs(dll)
        self.assertEqual(r[0]["estado"], "error"); self.assertIn("--verificar-firmas", r[0]["accion"])
        with mock.patch.object(pf, "version_archivo", return_value=pf.op.VERSION_DLL_VERIFICADA):
            self.assertEqual(pf.comprobar_etabs(dll)[0]["estado"], "ok")

    def test_rutas_largas_permisos_y_marca_de_incertidumbre(self):
        self.assertEqual(pf.comprobar_raiz(self.dir / "falta")[0]["estado"], "error")
        corta = {c["id"]: c for c in pf.comprobar_raiz(self.dir)}
        self.assertEqual(corta["permisos"]["estado"], "ok")
        larga = self.dir / ("x" * 120) / ("y" * 100)
        larga.mkdir(parents=True)
        r = {c["id"]: c for c in pf.comprobar_raiz(larga)}
        self.assertEqual(r["rutas"]["estado"], "error"); self.assertIn("no use junctions", r["rutas"]["accion"])
        lock = self.dir / "motor.lock"
        self.assertEqual(pf.comprobar_motor(lock)[0]["estado"], "ok")
        Path(str(lock) + ".incierto.json").write_text("{}", encoding="utf-8")
        r = pf.comprobar_motor(lock)[0]
        self.assertEqual(r["estado"], "error"); self.assertIn("confirmar_recuperacion", r["accion"]); self.assertIn("No borre", r["accion"])

    def test_powershell_ausente_o_directiva_restringida(self):
        self.assertEqual(pf.comprobar_powershell(self.dir / "powershell.exe")[0]["estado"], "error")
        ps = self.dir / "powershell.exe"; ps.write_bytes(b"")
        with mock.patch.object(pf.subprocess, "run", return_value=SimpleNamespace(stdout=b"Restricted\r\n")):
            r = pf.comprobar_powershell(ps)[0]
        self.assertEqual(r["estado"], "error"); self.assertIn("no cambia la directiva", r["accion"])

    def test_resultado_global_y_salida_no_imprime_claves(self):
        with mock.patch.object(pf, "version_archivo", return_value=pf.op.VERSION_DLL_VERIFICADA):
            r = pf.ejecutar(self.dir, lock=self.dir / "motor.lock")
        self.assertIn("leer o imprimir claves", r["no_hace"])
        self.assertEqual(r["listo"], r["errores"] == 0)
        self.assertNotIn("API_KEY", json.dumps(r))


class ProveedoresOperativosTests(unittest.TestCase):
    def setUp(self):
        self.base = fixtures.ModeloTests(); self.base.setUp(); self.addCleanup(self.base.doCleanups)
        self.app = RevisionLocal(self.base.raiz)
        self.server = SimpleNamespace(revision=self.app, token="prueba", origen="http://127.0.0.1:8766")

    def test_pagina_solo_ofrece_google_y_openai(self):
        status, raw, _ = httpfixtures.HTTPRevisionTests.request(self, "GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b'<option value="openai"', raw); self.assertIn(b'<option value="gemini"', raw)
        self.assertNotIn(b'value="anthropic"', raw); self.assertNotIn(b'value="openai_compatible"', raw)

    def test_cli_solo_admite_proveedores_autorizados(self):
        from draft2model import proveedor_openai
        with self.assertRaises(SystemExit):
            proveedor_openai.main(["preparar", "--proveedor", "anthropic", "--expediente", "x", "--solicitud", "y", "--modelo", "m"])


if __name__ == "__main__":
    unittest.main()
