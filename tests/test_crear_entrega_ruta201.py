"""R203-02: la entrega inmutable admite solo prefijos y archivos raíz explícitos, y la API crear() rechaza claves
reservadas o ausentes sin crear carpeta. Proyecto aislado en un directorio temporal; no toca entregas/ reales."""
import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

RAIZ = Path(__file__).resolve().parents[1]
_spec = importlib.util.spec_from_file_location("crear_entrega_ruta", RAIZ / "scripts" / "crear_entrega_ruta.py")
cer = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cer)
DATOS = {"pruebas": [], "limitaciones": [], "siguiente_etapa": "02"}


class EntregaRutaTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.raiz = Path(tmp.name).resolve()
        for rel in ("README.md", "requirements.txt", "requirements-win-py310.lock", "requirements-extra.txt",
                    "notas.md", "draft2model/a.py", "tmp/x.log", "data/private/b.json",
                    "draft2model/credenciales_locales.py", "scripts/usar_credenciales_locales.py",
                    "tests/test_credenciales_locales.py", "docs/credenciales.local.md", "scripts/credencial_extra.py",
                    "scripts/cliente.env"):
            (self.raiz / rel).parent.mkdir(parents=True, exist_ok=True)
            (self.raiz / rel).write_bytes(rel.encode())
        p = mock.patch.object(cer, "RAIZ", self.raiz)
        p.start(); self.addCleanup(p.stop)

    def entregas(self):
        d = self.raiz / "entregas"
        return sorted(d.iterdir()) if d.exists() else []

    def test_raiz_explicita_y_prefijos_admitidos(self):
        m = cer.crear("01", "entregado", ["README.md", "requirements.txt", "requirements-win-py310.lock",
                                           "draft2model/a.py"], ["tmp/x.log"], DATOS)
        man = json.loads(m.read_text(encoding="utf-8"))
        self.assertEqual(set(man["archivos"]), {"README.md", "requirements.txt", "requirements-win-py310.lock",
                                                "draft2model/a.py"})
        with zipfile.ZipFile(m.parent / "fuentes.zip") as z:
            self.assertEqual(sorted(z.namelist()), sorted(man["archivos"]))

    def test_archivos_raiz_no_listados_se_rechazan(self):
        for rel in ("requirements-extra.txt", "notas.md", "tmp/x.log", "data/private/b.json", "../fuera.txt"):
            with self.subTest(rel=rel), self.assertRaises(ValueError):
                cer.crear("01", "entregado", [rel], [], DATOS)
        self.assertEqual(self.entregas(), [])

    def test_codigo_de_credenciales_incluido_y_secretos_excluidos(self):  # R223-06
        legit = ["draft2model/credenciales_locales.py", "scripts/usar_credenciales_locales.py", "tests/test_credenciales_locales.py"]
        (self.raiz / legit[2]).write_text("CLAVE = 'sk-prueba-" + "x" * 24 + "'", encoding="utf-8")  # ficticia marcada
        m = cer.crear("06", "entregado", legit, [], DATOS)
        self.assertEqual(set(json.loads(m.read_text(encoding="utf-8"))["archivos"]), set(legit))
        for rel in ("docs/credenciales.local.md", "scripts/credencial_extra.py", "scripts/cliente.env"):
            with self.subTest(rel=rel), self.assertRaises(ValueError):
                cer.crear("06", "entregado", [rel], [], DATOS)
        (self.raiz / legit[0]).write_text("K = 'sk-" + "A1b2" * 8 + "'", encoding="utf-8")  # forma de clave real
        with self.assertRaisesRegex(ValueError, "Posible clave"):
            cer.crear("06", "entregado", [legit[0]], [], DATOS)
        self.assertEqual(len(self.entregas()), 1)

    def test_crear_rechaza_claves_reservadas_o_faltantes_sin_carpeta(self):
        for datos in ({**DATOS, "estado": "finalizado"}, {**DATOS, "snapshot": {}}, {**DATOS, "id": "x"},
                      {"pruebas": [], "limitaciones": []}, [], None):
            with self.subTest(datos=datos), self.assertRaises(ValueError):
                cer.crear("01", "entregado", ["README.md"], [], datos)
        self.assertEqual(self.entregas(), [])

    def test_cli_rechaza_datos_reservados(self):
        f = self.raiz / "d.json"
        f.write_text(json.dumps({**DATOS, "tarea": "otra"}), encoding="utf-8")
        with mock.patch("sys.stderr"):
            self.assertEqual(cer.main(["--etapa", "01", "--estado", "entregado", "--archivos", "README.md",
                                       "--datos", str(f)]), 2)
        self.assertEqual(self.entregas(), [])


if __name__ == "__main__":
    unittest.main()
