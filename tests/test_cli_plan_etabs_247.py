"""BRECHA_CLI_247: plan-etabs dirige 0.5 a malla/líquidos y acepta el mapa R241 por sección desde archivo JSON."""
import contextlib
import io
import json
import unittest
from unittest.mock import patch

from draft2model import operaciones_etabs as op
from draft2model.__main__ import main
from tests import test_liquidos_ruta201 as tl

BASE = ["plan-etabs", "--raiz", ".", "--entrada", "config.json", "--salida", "no-se-escribe.json"]


def despacho(version, extra, archivo=None):
    llamadas, recibido = [], {}

    def legado(*a, **k):
        llamadas.append("generar_plan"); raise op.ErrorPlan("CENTINELA")

    def malla(raiz, config, **k):
        llamadas.append("generar_plan_malla"); recibido.update(k); raise op.ErrorPlan("CENTINELA")

    err = io.StringIO()
    with patch.object(op.me, "cargar_configuracion", return_value={"version_contrato": version}), \
            patch.object(op, "generar_plan", side_effect=legado), patch.object(op, "generar_plan_malla", side_effect=malla), \
            contextlib.redirect_stderr(err):
        try:
            codigo = main(BASE + extra)
        except SystemExit as exc:
            codigo = exc.code
    return codigo, llamadas, recibido, err.getvalue()


class DespachoTests(unittest.TestCase):
    def setUp(self):
        self.dir = tl.tim.disco.CasoGeometria(); self.dir.setUp(); self.addCleanup(self.dir.doCleanups)

    def mapa(self, contenido):
        ruta = self.dir.trabajo / "losas.json"
        ruta.write_bytes(contenido if isinstance(contenido, bytes) else json.dumps(contenido).encode("utf-8"))
        return str(ruta)

    def test_05_va_a_malla_con_global_o_mapa(self):
        self.assertEqual(despacho("0.5.0", ["--tipo-shell-losa", "Membrane"])[1:3], (["generar_plan_malla"], {"tipo_shell_losa": "Membrane"}))
        self.assertEqual(despacho("0.5.0", [])[1], ["generar_plan_malla"])
        m = {"PISO": {"tipo": "Membrane", "funcion": "piso", "justificacion": "revisión"},
             "FONDO": {"tipo": "ShellThick", "funcion": "fondo_deposito", "justificacion": "flexión fuera del plano"}}
        codigo, llamadas, recibido, _ = despacho("0.5.0", ["--tipo-shell-losa-json", self.mapa(m)])
        self.assertEqual((llamadas, recibido["tipo_shell_losa"]), (["generar_plan_malla"], m))
        self.assertEqual(despacho("0.4.0", ["--tipo-shell-losa-json", self.mapa(m)])[2]["tipo_shell_losa"], m)

    def test_rutas_previas_conservadas(self):
        self.assertEqual(despacho("0.4.0", ["--tipo-shell-losa", "Membrane"])[1], ["generar_plan_malla"])
        self.assertEqual(despacho("0.1.0", [])[1], ["generar_plan"])
        codigo, llamadas, _, err = despacho("0.1.0", ["--tipo-shell-losa", "Membrane"])
        self.assertEqual((codigo, llamadas), (1, []))

    def test_conflictos_y_archivos_invalidos(self):
        m = self.mapa({"PISO": {"tipo": "Membrane", "funcion": "piso", "justificacion": "x"}})
        codigo, llamadas, _, err = despacho("0.5.0", ["--tipo-shell-losa", "Membrane", "--tipo-shell-losa-json", m])
        self.assertEqual((codigo, llamadas), (2, []))
        self.assertIn("not allowed with", err)
        for nombre, contenido in (("no objeto", [1, 2]), ("vacío", {}), ("JSON inválido", b"{no json")):
            with self.subTest(nombre):
                codigo, llamadas, _, _ = despacho("0.5.0", ["--tipo-shell-losa-json", self.mapa(contenido)])
                self.assertNotEqual(codigo, 0); self.assertEqual(llamadas, [])
        codigo, llamadas, _, _ = despacho("0.5.0", ["--tipo-shell-losa-json", str(self.dir.trabajo / "no_existe.json")])
        self.assertEqual((codigo, llamadas), (1, []))
        codigo, llamadas, _, err = despacho("0.1.0", ["--tipo-shell-losa-json", m])
        self.assertEqual((codigo, llamadas), (1, [])); self.assertIn("0.4/0.5", err)


class IntegracionCli05Tests(tl.CasoLiquidos):
    def test_plan_real_05_por_seccion_desde_archivo(self):
        config = self.aprobar_en_disco(self.montar_liquidos("conectados", "ausente_confirmado", patrones=()))
        entrada = self.f.escribir(config, "cfg05_cli.json")
        mapa = {"LOSA20": {"tipo": "Membrane", "funcion": "piso", "justificacion": "Piso con diafragma rígido (sintético)."}}
        archivo = self.f.trabajo / "losas.json"
        archivo.write_text(json.dumps(mapa), encoding="utf-8")
        salida = self.f.trabajo / "plan_cli.json"
        opciones = self.opciones(config)
        argv = ["plan-etabs", "--raiz", str(self.raiz), "--entrada", str(entrada), "--salida", str(salida),
                "--destino-guardado", opciones["destino_guardado"], "--tipo-shell-muro", opciones["tipo_shell_muro"],
                "--gravedad-programa", str(opciones["gravedad_programa_m_s2"]), "--tipo-shell-losa-json", str(archivo)]
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(argv), 0)
        plan = json.loads(salida.read_text(encoding="utf-8"))
        self.assertEqual(plan["version_contrato"], "0.5.0")
        self.assertEqual(op.validar_plan_por_version(plan), [])
        self.assertEqual([x["seccion"] for x in plan["idealizacion_losas"]], ["LOSA20"])
        slab = next(x for x in plan["operaciones"] if x["metodo"] == "cPropArea.SetSlab")
        self.assertEqual({a["nombre"]: a["valor"] for a in slab["argumentos"]}["ShellType"]["nombre"], "Membrane")


if __name__ == "__main__":
    unittest.main()
