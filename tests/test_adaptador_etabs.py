"""Adaptador ETABS con un proceso doble y con el puente real solo en rutas que fallan antes de la API.

Ninguna prueba carga ETABSv1.dll ni se conecta a ETABS: las pruebas del puente real usan una
DLL inexistente y solicitudes que se rechazan en la validación previa.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from draft2model import adaptador_etabs as a

RAIZ = Path(__file__).resolve().parents[1]
DLL_INEXISTENTE = r"C:\draft2model_no_existe\ETABSv1.dll"
POWERSHELL_DISPONIBLE = os.name == "nt" and a.POWERSHELL_51.is_file()

DOBLE = r'''
import hashlib, json, os, sys, time
args = sys.argv[1:]
sol, resp = args[args.index("-Solicitud") + 1], args[args.index("-Respuesta") + 1]
modo = os.environ.get("DOBLE_ETABS_MODO", "ok")
s = json.load(open(sol, encoding="utf-8"))
op, p = s["operacion"], s["parametros"]
if modo == "lento":
    time.sleep(60)
r = {"contrato": "draft2model.etabs_respuesta", "version_contrato": "0.1.0", "version_puente": "doble",
     "modo_ejecucion": "doble", "id_solicitud": s["id"], "operacion": op, "estado": "ok", "error": None,
     "datos": {}, "avisos": ["Doble de pruebas: no se usó ETABS."]}
codigo = 0
if op == "diagnosticar":
    r["datos"] = {"version": "doble", "unidades": "kN_m_C", "modelo": None}
elif op == "abrir_copia_plantilla":
    r["datos"] = {"modelo_abierto": p["copia"], "sha256_copia_verificado": p["sha256_copia"]}
elif op == "leer_tablas":
    r["datos"] = {"tablas": [{"clave": t, "filas": [{"OutputCase": c} for c in p["casos"]]} for t in p["tablas"]]}
elif op == "guardar_como":
    contenido = b"modelo doble"
    with open(p["destino"], "xb") as f:
        f.write(contenido)
    r["datos"] = {"destino": p["destino"], "sha256": "0" * 64 if modo == "hash_falso" else hashlib.sha256(contenido).hexdigest()}
if modo == "error":
    r.update(estado="error", datos=None, error={"tipo": "api", "mensaje": "File.OpenFile devolvio 1.", "codigo_api": 1})
    codigo = 30
elif modo == "evidencia":
    r.update(estado="error", datos=None, error={"tipo": "evidencia", "mensaje": "copia alterada", "codigo_api": None})
    codigo = 41
elif modo == "salida_sin_respuesta":
    sys.exit(3)
elif modo == "id_ajeno":
    r["id_solicitud"] = "f" * 32
elif modo == "finge_real":
    r["modo_ejecucion"] = "real"
elif modo == "incoherente":
    codigo = 30
if modo != "sin_respuesta":
    with open(resp, "x", encoding="utf-8") as f:
        f.write(json.dumps(r))
sys.exit(codigo)
'''

RETENER_BLOQUEO = (
    "import sys, time; sys.path.insert(0, sys.argv[3]); "
    "from draft2model.adaptador_etabs import BloqueoExclusivo; "
    "b = BloqueoExclusivo(sys.argv[1]).adquirir(); open(sys.argv[2], 'w').write('listo'); time.sleep(60)"
)


def sha(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


class Base(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = Path(temp.name).resolve()
        self.trabajo = self.dir / "corridas"
        self.trabajo.mkdir()
        self.doble = self.dir / "doble_puente.py"
        self.doble.write_text(DOBLE, encoding="utf-8")
        self.plantilla = self.dir / "plantillas" / "plantilla.edb"
        self.plantilla.parent.mkdir()
        self.contenido_plantilla = b"EDB sintetico de plantilla"
        self.plantilla.write_bytes(self.contenido_plantilla)

    def adaptador(self, modo_doble="ok", timeout_s=30.0):
        config = a.ConfiguracionPuente.doble(self.trabajo, (sys.executable, str(self.doble)), timeout_s=timeout_s,
                                             entorno={"DOBLE_ETABS_MODO": modo_doble})
        return a.AdaptadorEtabs(config)

    def corridas(self):
        return sorted(p for p in self.trabajo.iterdir() if p.is_dir())


class PreparacionTests(Base):
    def test_preparado_real_no_ejecuta(self):
        adaptador = a.AdaptadorEtabs(a.ConfiguracionPuente.real(self.trabajo, dll=Path(DLL_INEXISTENTE)))
        preparada = adaptador.diagnosticar(solo_preparar=True)
        self.assertEqual(preparada.modo, "preparado")
        self.assertEqual(Path(preparada.argv[0]), a.POWERSHELL_51)
        self.assertIn("-NoProfile", preparada.argv)
        self.assertEqual(preparada.argv[preparada.argv.index("-File") + 1], str(a.SCRIPT_PUENTE))
        self.assertEqual(preparada.argv[-4:], ["-Solicitud", str(preparada.solicitud), "-Respuesta", str(preparada.respuesta)])
        contenido = json.loads(preparada.solicitud.read_text(encoding="utf-8"))
        self.assertEqual((contenido["contrato"], contenido["operacion"], contenido["id"]),
                         (a.CONTRATO_SOLICITUD, "diagnosticar", preparada.id))
        self.assertEqual(contenido["dll"], DLL_INEXISTENTE)
        self.assertEqual(sorted(p.name for p in preparada.carpeta.iterdir()), ["solicitud.json"])

    def test_operaciones_no_admitidas_o_futuras(self):
        adaptador = self.adaptador()
        for operacion in ("RunAnalysis", "aplicar_modelo_estructural"):
            with self.subTest(operacion), self.assertRaises(a.ErrorAdaptador) as ctx:
                adaptador.preparar(operacion, {})
            self.assertEqual(a.codigo_salida(ctx.exception), 1)
        with self.assertRaises(a.ErrorAdaptador):
            adaptador.preparar("diagnosticar", {"ejecutar_analisis": True})
        self.assertEqual(self.corridas(), [])

    def test_validacion_de_parametros(self):
        adaptador = self.adaptador()
        modelo = str(self.dir / "modelo.edb")
        invalidos = {
            "sin casos": ("leer_tablas", {"modelo_esperado": modelo, "tablas": ["Story Drifts"]}),
            "casos repetidos": ("leer_tablas", {"modelo_esperado": modelo, "tablas": ["T"], "casos": ["SX", "SX"]}),
            "tablas vacías": ("leer_tablas", {"modelo_esperado": modelo, "tablas": [], "casos": ["SX"]}),
            "ruta relativa": ("leer_tablas", {"modelo_esperado": "modelo.edb", "tablas": ["T"], "casos": ["SX"]}),
            "no edb": ("guardar_como", {"modelo_esperado": modelo, "destino": str(self.dir / "x.txt")}),
            "mismo destino": ("guardar_como", {"modelo_esperado": modelo, "destino": modelo}),
            "id proceso": ("diagnosticar", {"id_proceso": True}),
            "activa sin reemplazo": ("abrir_copia_plantilla", {"copia": modelo, "sha256_copia": "0" * 64,
                                                             "instancia": "activa"}),
        }
        for nombre, (operacion, parametros) in invalidos.items():
            with self.subTest(nombre), self.assertRaises(a.ErrorAdaptador):
                adaptador.preparar(operacion, parametros)
        self.assertEqual(self.corridas(), [])


class DobleTests(Base):
    def test_trabajo_relativo_no_rompe_rutas_del_subproceso(self):
        # La carpeta relativa debe estar en la MISMA unidad que el cwd (TEMP puede estar en otra: C: frente a D:, revisión 267).
        base = Path.cwd() / "tmp" if (Path.cwd() / "tmp").is_dir() else Path.cwd()
        local = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(local.cleanup)
        trabajo = Path(local.name).resolve() / "corridas"
        trabajo.mkdir()
        relativo = Path(os.path.relpath(trabajo))
        self.assertFalse(relativo.is_absolute())
        config=a.ConfiguracionPuente.doble(relativo,(sys.executable,str(self.doble)))
        adapter=a.AdaptadorEtabs(config)
        self.assertTrue(adapter.config.trabajo.is_absolute())
        self.assertEqual(adapter.diagnosticar().datos['version'],'doble')

    def test_timeout_mutacion_bloquea_reintento_hasta_recuperacion(self):
        params={'modelo_esperado':str(self.dir/'modelo.edb'), 'destino':str(self.dir/'salida.edb')}
        with self.assertRaises(a.ErrorTiempo):
            self.adaptador('lento',timeout_s=0.5).ejecutar_operacion('guardar_como',params)
        current=self.adaptador()
        self.assertTrue(current.estado_incierto.exists())
        with self.assertRaises(a.ErrorBloqueo):current.ejecutar_operacion('guardar_como',params)
        self.assertEqual(current.diagnosticar().datos['version'],'doble')
        with self.assertRaises(a.ErrorAdaptador):current.confirmar_recuperacion(motor_inactivo_declarado=False,revisor_declarado='Prueba sintética',motivo='Sin verificar')
        evidence=current.confirmar_recuperacion(motor_inactivo_declarado=True,revisor_declarado='Prueba sintética',motivo='Motor doble terminado e inspeccionado')
        self.assertTrue(evidence.is_file());self.assertFalse(current.estado_incierto.exists())

    def test_diagnostico_doble_trazable(self):
        respuesta = self.adaptador().diagnosticar()
        self.assertEqual(respuesta.modo_ejecucion, "doble")
        self.assertEqual(respuesta.datos["version"], "doble")
        self.assertEqual(respuesta.codigo_proceso, 0)
        self.assertEqual(sorted(p.name for p in respuesta.corrida.iterdir()),
                         ["registro.json", "respuesta.json", "salida_puente.txt", "solicitud.json", "stderr_proceso.bin", "stdout_proceso.bin"])
        registro = json.loads((respuesta.corrida / "registro.json").read_text(encoding="utf-8"))
        self.assertEqual((registro["estado"], registro["modo"]), ("ok", "doble"))

    def test_tiempo_agotado(self):
        inicio = time.monotonic()
        with self.assertRaises(a.ErrorTiempo) as ctx:
            self.adaptador("lento", timeout_s=1.5).diagnosticar()
        self.assertLess(time.monotonic() - inicio, 20)
        self.assertEqual(a.codigo_salida(ctx.exception), 4)
        registro = json.loads((ctx.exception.corrida / "registro.json").read_text(encoding="utf-8"))
        self.assertEqual(registro["estado"], "tiempo_agotado")
        self.assertIn("desconocido", str(ctx.exception))
        self.assertEqual(self.adaptador().diagnosticar().datos["version"], "doble")  # el bloqueo se liberó

    def test_salida_no_cero_y_respuestas_invalidas(self):
        with self.assertRaises(a.ErrorPuente) as ctx:
            self.adaptador("error").diagnosticar()
        self.assertEqual((ctx.exception.tipo, ctx.exception.codigo_proceso), ("api", 30))
        self.assertIn("File.OpenFile", str(ctx.exception))
        self.assertEqual(a.codigo_salida(ctx.exception), 3)
        for modo in ("salida_sin_respuesta", "sin_respuesta", "id_ajeno", "finge_real", "incoherente"):
            with self.subTest(modo), self.assertRaises(a.ErrorPuente) as ctx:
                self.adaptador(modo).diagnosticar()
            self.assertNotIsInstance(ctx.exception, a.ErrorTiempo)
        with self.assertRaises(a.ErrorEvidenciaEtabs):
            self.adaptador("evidencia").diagnosticar()

    def test_bloqueo_concurrente(self):
        bloqueo = self.trabajo / "puente_etabs.lock"
        listo = self.dir / "listo.txt"
        retenedor = subprocess.Popen([sys.executable, "-c", RETENER_BLOQUEO, str(bloqueo), str(listo), str(RAIZ)])
        self.addCleanup(lambda: (retenedor.kill(), retenedor.wait()))
        limite = time.monotonic() + 20
        while not listo.exists():
            self.assertIsNone(retenedor.poll(), "el proceso retenedor terminó")
            self.assertLess(time.monotonic(), limite, "el retenedor no adquirió el bloqueo")
            time.sleep(0.05)
        adaptador = self.adaptador()
        with self.assertRaises(a.ErrorBloqueo) as ctx:
            adaptador.diagnosticar()
        self.assertEqual(a.codigo_salida(ctx.exception), 5)
        self.assertFalse(any((c / "respuesta.json").exists() for c in self.corridas()))
        retenedor.kill()
        retenedor.wait()
        self.assertEqual(adaptador.diagnosticar().modo_ejecucion, "doble")  # liberado al morir el proceso

    def test_solicitud_no_se_ejecuta_dos_veces(self):
        adaptador = self.adaptador()
        preparada = adaptador.diagnosticar(solo_preparar=True)
        adaptador.ejecutar(preparada)
        with self.assertRaises(a.ErrorAdaptador):
            adaptador.ejecutar(preparada)


class PlantillaTests(Base):
    def test_copia_verificada_y_original_intacto(self):
        destino = self.dir / "copias" / "corrida1"
        destino.parent.mkdir()
        respuesta = self.adaptador().abrir_copia_plantilla(self.plantilla, sha(self.contenido_plantilla), destino,
                                                           instancia="nueva")
        copia = destino / "plantilla.edb"
        self.assertEqual(copia.read_bytes(), self.contenido_plantilla)
        self.assertEqual(self.plantilla.read_bytes(), self.contenido_plantilla)
        self.assertEqual(respuesta.modo_ejecucion, "doble")
        enviado = json.loads((respuesta.corrida / "solicitud.json").read_text(encoding="utf-8"))["parametros"]
        self.assertEqual(Path(enviado["copia"]), copia)
        self.assertNotIn(str(self.plantilla), json.dumps(enviado))  # el puente nunca recibe el original
        self.assertEqual(respuesta.artefactos["sha256_plantilla"], sha(self.contenido_plantilla))

    def test_plantilla_alterada(self):
        destino = self.dir / "copia_alterada"
        esperado = sha(self.contenido_plantilla)
        self.plantilla.write_bytes(self.contenido_plantilla + b" alterado")
        with self.assertRaises(a.ErrorEvidenciaEtabs) as ctx:
            self.adaptador().abrir_copia_plantilla(self.plantilla, esperado, destino, instancia="nueva")
        self.assertEqual(a.codigo_salida(ctx.exception), 2)
        self.assertFalse(destino.exists())
        self.assertEqual(self.corridas(), [])

    def test_plantilla_cambia_durante_la_copia(self):
        destino = self.dir / "copia_cambiante"
        esperado = sha(self.contenido_plantilla)
        with mock.patch.object(a, "file_hash", side_effect=[esperado, esperado, "1" * 64]):
            with self.assertRaises(a.ErrorEvidenciaEtabs):
                self.adaptador().abrir_copia_plantilla(self.plantilla, esperado, destino, instancia="nueva")
        self.assertFalse(destino.exists())  # la copia descartada no queda visible
        self.assertEqual(self.corridas(), [])

    def test_destinos_existentes(self):
        destino = self.dir / "existente"
        destino.mkdir()
        (destino / "otro.txt").write_text("previo", encoding="utf-8")
        with self.assertRaises(a.ErrorAdaptador) as ctx:
            self.adaptador().abrir_copia_plantilla(self.plantilla, sha(self.contenido_plantilla), destino, instancia="nueva")
        self.assertEqual(a.codigo_salida(ctx.exception), 1)
        self.assertEqual(sorted(p.name for p in destino.iterdir()), ["otro.txt"])

        guardado = self.dir / "guardado.edb"
        guardado.write_bytes(b"previo")
        with self.assertRaises(a.ErrorAdaptador):
            self.adaptador().guardar_como(self.dir / "modelo.edb", guardado)
        self.assertEqual(guardado.read_bytes(), b"previo")
        self.assertEqual(self.corridas(), [])


class GuardarYLeerTests(Base):
    def test_guardar_como_verifica_huella(self):
        destino = self.dir / "resultado.edb"
        respuesta = self.adaptador().guardar_como(self.dir / "modelo.edb", destino)
        self.assertEqual(respuesta.artefactos["guardado"]["sha256"], sha(b"modelo doble"))
        with self.assertRaises(a.ErrorEvidenciaEtabs):
            self.adaptador("hash_falso").guardar_como(self.dir / "modelo.edb", self.dir / "otro.edb")

    def test_leer_tablas_casos_explicitos(self):
        respuesta = self.adaptador().leer_tablas(self.dir / "modelo.edb", ["Story Drifts", "Base Reactions"],
                                                 casos=["SX", "SY"])
        self.assertEqual([t["clave"] for t in respuesta.datos["tablas"]], ["Story Drifts", "Base Reactions"])
        enviado = json.loads((respuesta.corrida / "solicitud.json").read_text(encoding="utf-8"))["parametros"]
        self.assertEqual((enviado["casos"], enviado["combinaciones"]), (["SX", "SY"], []))


class PuenteEstaticoTests(unittest.TestCase):
    def setUp(self):
        self.bytes = a.SCRIPT_PUENTE.read_bytes()
        self.texto = self.bytes.decode("utf-8-sig")

    def test_bom_para_windows_powershell(self):
        self.assertTrue(self.bytes.startswith(b"\xef\xbb\xbf"), "PS 5.1 lee como ANSI un .ps1 UTF-8 sin BOM")

    def test_configuracion_respeta_politica_del_equipo(self):
        command = a.ConfiguracionPuente.real(Path('tmp')).comando
        self.assertNotIn('-ExecutionPolicy', command)
        self.assertNotIn('Bypass', command)

    def test_sin_llamadas_prohibidas(self):
        for prohibido in ("RunAnalysis", "ApplicationExit", "SetPresentUnits", "InitializeNewModel",
                          "SetModelIsLocked", "Remove-Item -Recurse", "-Force -Recurse"):
            with self.subTest(prohibido):
                self.assertNotIn(prohibido, self.texto)

    def test_lista_de_procesos_no_se_desenrolla(self):
        # Con un solo proceso, PS 5.1 devolvía un diccionario y Count contaba sus claves (falso "2 instancias").
        llamadas = [l for l in self.texto.splitlines() if "Get-ProcesosEtabs" in l
                    and not l.lstrip().startswith(("#", "function"))]
        self.assertTrue(llamadas)
        for linea in llamadas:
            self.assertIn("@(Get-ProcesosEtabs", linea)

    def test_operaciones_coinciden(self):
        registradas = re.findall(r"^\s+(\w+)\s+= @\{ validar", self.texto, flags=re.M)
        self.assertEqual(sorted(registradas), sorted(a.OPERACIONES))


@unittest.skipUnless(POWERSHELL_DISPONIBLE, "requiere Windows PowerShell 5.1")
class PuenteRealSinApiTests(Base):
    """Puente PowerShell real; cada caso falla antes de cargar la DLL o con una DLL inexistente."""

    @classmethod
    def setUpClass(cls):
        # Probar ejecución normal con solicitud inexistente: nunca llega a la API.
        with tempfile.TemporaryDirectory() as folder:
            probe = subprocess.run([str(a.POWERSHELL_51), '-NoProfile', '-NonInteractive', '-File',
                                    str(a.SCRIPT_PUENTE), '-Solicitud', str(Path(folder)/'ausente.json'),
                                    '-Respuesta', str(Path(folder)/'respuesta.json')],
                                   capture_output=True, timeout=30)
        diagnostic = probe.stderr.decode('utf-8', errors='replace')
        if 'AuthorizationManager check failed' in diagnostic or 'PSSecurityException' in diagnostic:
            raise unittest.SkipTest('La política del entorno bloquea archivos PowerShell; no se elude. Puente real pendiente en un entorno autorizado.')

    def real(self):
        return a.AdaptadorEtabs(a.ConfiguracionPuente.real(self.trabajo, dll=Path(DLL_INEXISTENTE), timeout_s=90))

    def test_dll_inexistente(self):
        with self.assertRaises(a.ErrorPuente) as ctx:
            self.real().diagnosticar()
        self.assertEqual((ctx.exception.tipo, ctx.exception.codigo_proceso), ("api_no_disponible", 20))
        self.assertEqual(ctx.exception.respuesta["modo_ejecucion"], "real")
        self.assertEqual(ctx.exception.respuesta["entorno"]["edicion"], "Desktop")

    def test_puente_rechaza_operacion_desconocida(self):
        adaptador = self.real()
        preparada = adaptador.diagnosticar(solo_preparar=True)
        contenido = dict(preparada.contenido, operacion="RunAnalysis")
        preparada.solicitud.write_text(json.dumps(contenido), encoding="utf-8")
        with self.assertRaises(a.ErrorPuente) as ctx:
            adaptador.ejecutar(preparada)
        self.assertEqual((ctx.exception.tipo, ctx.exception.codigo_proceso), ("solicitud", 10))

    def test_puente_rechaza_copia_alterada(self):
        copia = self.dir / "copia" / "plantilla.edb"
        copia.parent.mkdir()
        copia.write_bytes(self.contenido_plantilla + b" alterado")
        adaptador = self.real()
        preparada = adaptador.preparar("abrir_copia_plantilla", {
            "copia": str(copia), "sha256_copia": sha(self.contenido_plantilla), "instancia": "nueva"})
        with self.assertRaises(a.ErrorEvidenciaEtabs):
            adaptador.ejecutar(preparada)
        respuesta = json.loads(preparada.respuesta.read_text(encoding="utf-8"))
        self.assertEqual(respuesta["error"]["tipo"], "evidencia")

    def test_puente_rechaza_destino_existente(self):
        adaptador = self.real()
        destino = self.dir / "destino.edb"
        preparada = adaptador.guardar_como(self.dir / "modelo.edb", destino, solo_preparar=True)
        destino.write_bytes(b"previo")  # aparece después de preparar
        with self.assertRaises(a.ErrorPuente) as ctx:
            adaptador.ejecutar(preparada)
        self.assertEqual((ctx.exception.tipo, ctx.exception.codigo_proceso), ("precondicion", 40))
        self.assertEqual(destino.read_bytes(), b"previo")

    def test_puente_no_sobrescribe_respuesta(self):
        preparada = self.real().diagnosticar(solo_preparar=True)
        preparada.respuesta.write_text("previa", encoding="utf-8")
        proceso = subprocess.run(preparada.argv, capture_output=True, timeout=90)
        self.assertEqual(proceso.returncode, 50, proceso.stderr)
        self.assertEqual(preparada.respuesta.read_text(encoding="utf-8"), "previa")
        self.assertEqual(sorted(p.name for p in preparada.carpeta.iterdir()), ["respuesta.json", "solicitud.json"])


if __name__ == "__main__":
    unittest.main()
