"""Recuperación explícita del motor web (operacion_pendiente.json) sin borrar evidencia; sin ETABS."""
import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from draft2model import adaptador_etabs as ad
from draft2model.revision_ejecucion import ErrorEjecucion, ServicioEjecucion

BODY = {"motor_inactivo_declarado": True, "revisor_declarado": "Revisor de prueba", "motivo": "Proceso del worker terminado; sin ETABS propio.",
        "confirmacion_explicita": True}


class RecuperacionMotorWebTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.app = SimpleNamespace(raiz=Path(self.tmp.name).resolve(), lock=threading.RLock())
        self.s = ServicioEjecucion(self.app)

    def test_archiva_sin_borrar_y_libera(self):
        self.s.pendiente.write_text(json.dumps({"id": "x", "estado": "interrupcion_no_confirmada"}), encoding="utf-8")
        r = self.s.confirmar_recuperacion(dict(BODY))
        self.assertFalse(self.s.pendiente.exists())
        self.assertTrue((self.s.base / r["archivados"][0]).exists())
        reg = json.loads((self.s.base / f"recuperacion_{r['id']}.json").read_text(encoding="utf-8"))
        self.assertEqual(reg["identidad_revisor"], "declarada_no_verificada")

    def test_rechazos(self):
        with self.assertRaises(ErrorEjecucion):
            self.s.confirmar_recuperacion(dict(BODY))                       # sin incertidumbre
        self.s.pendiente.write_text("{}", encoding="utf-8")
        for cambio in ({"confirmacion_explicita": False}, {"motor_inactivo_declarado": False}, {"motivo": " "}, {"extra": 1}):
            with self.subTest(cambio=cambio), self.assertRaises(ErrorEjecucion):
                self.s.confirmar_recuperacion({**BODY, **cambio})
        self.assertTrue(self.s.pendiente.exists())

    def test_no_recupera_con_lease_tomado_ni_trabajo_vivo(self):
        self.s.pendiente.write_text("{}", encoding="utf-8")
        lease = ad.BloqueoExclusivo(self.s.lease).adquirir()
        try:
            with self.assertRaises(ErrorEjecucion):
                self.s.confirmar_recuperacion(dict(BODY))
        finally:
            lease.liberar()
        with self.s._conexion() as db:
            db.execute("INSERT INTO trabajos VALUES ('a','c','k','p','en_ejecucion','{}')")
        with self.assertRaises(ErrorEjecucion):
            self.s.confirmar_recuperacion(dict(BODY))
        self.assertTrue(self.s.pendiente.exists())


if __name__ == "__main__":
    unittest.main()
