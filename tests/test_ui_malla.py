"""HTTP de solo lectura de la preparación de malla 0.4 con versiones REALES en disco (sin ETABS ni red externa)."""
import json
import unittest
from types import SimpleNamespace
from urllib.parse import urlencode

from draft2model import gestion_configuracion as gc
from draft2model.revision_visual import RevisionLocal
from tests import test_integracion_malla as malla
from tests import test_gestion_geometria as disco
from tests import test_revision_visual as httpfixtures


def instantanea(carpeta):
    return {str(p.relative_to(carpeta)): p.read_bytes() for p in sorted(carpeta.rglob("*")) if p.is_file()}


class MallaHTTPTests(malla.CasoMalla):
    def setUp(self):
        super().setUp()
        self.imp, self.expuesta, self.aprobada = self.registrar_aprobada("conectados_corte")
        self.app = RevisionLocal(self.raiz)
        self.server = SimpleNamespace(revision=self.app, token="prueba", origen="http://127.0.0.1:8766")
        self.request = lambda *a, **kw: httpfixtures.HTTPRevisionTests.request(self, *a, **kw)
        self.versiones = self.app.configuraciones.listar(disco.CASO)
        self.id_aprobada = next(v for v in self.versiones if gc.consultar(self.raiz, disco.CASO, v)["configuracion"]["revision"]["estado"] == "aprobado")
        self.carpeta = self.app.expediente(disco.CASO)[0]

    def get(self, **query):
        return self.request("GET", "/api/configuracion/malla?" + urlencode(query, doseq=True))

    def test_borrador_y_aprobada_reproducen_la_preparacion(self):
        status, raw, headers = self.get(caso=disco.CASO, version=self.imp["id"])
        self.assertEqual(status, 200, raw)
        self.assertIn("no-store", headers["Cache-Control"])
        data = json.loads(raw)
        self.assertEqual(data["id"], self.imp["id"])
        self.assertEqual(data["expediente_sha256"], self.app.expediente(disco.CASO)[2])
        self.assertFalse(data["apto_para_adaptador"]); self.assertFalse(data["aprueba_ingenieria"])
        self.assertTrue(data["faltantes"])
        self.assertTrue(any(f["ruta"].startswith("$.nodos_derivados.MC_") for f in data["faltantes"]))  # nodos del corte Z
        self.assertEqual(data["preparacion"]["huella_preparacion"], self.expuesta["preparacion"]["huella_preparacion"])
        self.assertEqual(data["preparacion"]["cortes_nivel"]["niveles_z_m"], [1.2])
        self.assertTrue(all(n["restricciones"] is None for n in data["preparacion"]["plantilla_nodos_derivados"]))
        status, raw, _ = self.get(caso=disco.CASO, version=self.id_aprobada)
        self.assertEqual(status, 200, raw)
        aprobada = json.loads(raw)
        self.assertEqual(aprobada["faltantes"], []); self.assertTrue(aprobada["apto_para_adaptador"])
        self.assertFalse(aprobada["aprueba_ingenieria"])

    def test_caso_version_y_parametros_invalidos(self):
        for query in ({"caso": "otro-caso", "version": self.imp["id"]}, {"caso": disco.CASO, "version": "0" * 32},
                      {"caso": disco.CASO, "version": "../" + self.imp["id"]}, {"caso": disco.CASO},
                      {"caso": disco.CASO, "version": [self.imp["id"], self.id_aprobada]}):
            with self.subTest(query=query):
                status, raw, _ = self.get(**query)
                self.assertEqual(status, 409, raw)
                self.assertNotIn(str(self.raiz).encode(), raw)  # sin rutas privadas en errores
        self.assertEqual(self.request("GET", "/api/configuracion/malla?" + urlencode({"caso": disco.CASO, "version": self.imp["id"]}),
                                      headers={"X-Revision-Session": "incorrecto"})[0], 403)

    def test_no_admite_edicion_ni_mutacion_por_consulta(self):
        antes = instantanea(self.carpeta)
        politica = json.dumps([{"nodo": "MN_S1_1", "restricciones": [True] * 6}])
        for extra in ({"nodos_derivados": politica}, {"cortes_nivel": "[2.0]"}, {"revision": "aprobado"}, {"expediente_sha256": "0" * 64}):
            with self.subTest(extra=list(extra)):
                status, raw, _ = self.get(caso=disco.CASO, version=self.imp["id"], **extra)
                self.assertEqual(status, 409, raw)
        status, _, _ = self.request("POST", "/api/configuracion/malla", {"caso": disco.CASO, "version": self.imp["id"],
                                                                         "nodos_derivados": politica})
        self.assertEqual(status, 404)
        self.assertEqual(self.app.configuraciones.listar(disco.CASO), self.versiones)
        self.assertEqual(instantanea(self.carpeta), antes)

    def test_version_alterada_en_disco_no_se_prepara(self):
        ruta = gc._carpeta(self.raiz, disco.CASO, self.id_aprobada) / "configuracion.json"
        raw = ruta.read_bytes()
        ruta.write_bytes(raw.replace(b'"z_m": 1.2', b'"z_m": 1.3'))
        try:
            self.assertEqual(self.get(caso=disco.CASO, version=self.id_aprobada)[0], 409)
        finally:
            ruta.write_bytes(raw)

    def test_pagina_y_cliente_sin_html_inyectado(self):
        status, raw, _ = self.request("GET", "/")
        self.assertEqual(status, 200)
        for ident in (b'id="mallaPanel"', b'id="mallaConsultar"', b'id="mallaExportar"', b'id="mallaFaltantes"', b'id="mallaCortes"'):
            self.assertIn(ident, raw)
        status, raw, _ = self.request("GET", "/configuracion.js")
        self.assertEqual(status, 200)
        self.assertNotIn(b"innerHTML", raw); self.assertNotIn(b"insertAdjacentHTML", raw)
        self.assertIn(b"/api/configuracion/malla?", raw)


if __name__ == "__main__":
    unittest.main()
