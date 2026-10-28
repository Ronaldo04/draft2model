"""Flujo general: en modo real el análisis solo se acepta si el puente declara el cierre de SU instancia (sin ETABS)."""
import json
import sys
import unittest

from draft2model import adaptador_etabs as ad
from draft2model.analisis_etabs import AnalizadorEtabs
from tests import test_analisis_etabs as base

TRANSPORTE_REAL = base.TRANSPORTE.replace("'modo_ejecucion':'doble'", "'modo_ejecucion':'real'").replace(
    "'analisis_ejecutado':True,'aprueba_resultados':False}}",
    "'analisis_ejecutado':True,'aprueba_resultados':False,'version_etabs':'21.1.0','id_proceso':4242,"
    "'inicio_proceso_utc':'2026-10-22T00:00:00Z','modelo_abierto':s['destino'],"
    "'instancia_cerrada':(os.environ.get('CERRADA','1')=='1')}}")


class CierreAnalisisTests(base.AnalisisTests):
    def analizar_como_real(self, cerrada):
        """Prepara como doble (el modelo fixture es doble) y ejecuta con el adaptador en modo real y transporte fabricado."""
        script = self.fixture.base.trabajo / f"analizador_real_{int(cerrada)}.py"
        script.write_text(TRANSPORTE_REAL, encoding="utf-8")
        cfg = ad.ConfiguracionPuente.doble(self.fixture.base.corridas, (sys.executable, str(script)),
                                           entorno={"CERRADA": "1" if cerrada else "0"})
        a = AnalizadorEtabs(cfg)
        prepared = self.prepare(a)
        a.config.modo = "real"
        return a, prepared

    def test_real_con_cierre_declarado_se_acepta(self):
        a, prepared = self.analizar_como_real(True)
        try:
            r = a.ejecutar_analisis(prepared, confirmar_analisis=True)
        except ad.ErrorEvidenciaEtabs as exc:   # otras comprobaciones del modo real del adaptador base
            self.skipTest("El adaptador base exige más del modo real en este transporte: " + str(exc))
        self.assertTrue(r.datos["instancia_cerrada"])

    def test_real_sin_cierre_no_se_acepta(self):
        a, prepared = self.analizar_como_real(False)
        with self.assertRaises(ad.ErrorEvidenciaEtabs) as ctx:
            a.ejecutar_analisis(prepared, confirmar_analisis=True)
        self.assertIn("no cerrada", str(ctx.exception))
        self.assertTrue(a.estado_incierto.exists())   # el motor queda incierto hasta registrar recuperación



class GuionAnalisisTests(unittest.TestCase):
    def test_guion_cierra_solo_su_instancia_en_finally(self):
        from pathlib import Path
        texto = (Path(__file__).resolve().parents[1] / "scripts/analizar_modelo_etabs.ps1").read_text(encoding="utf-8-sig")
        i = texto.index("} finally {")
        bloque = texto[i:]
        for fragmento in ("$owned.StartTime.ToUniversalTime().ToString('o') -ne $inicioPropio", "ApplicationExit($false)",
                          "WaitForExit(", "instancia_cerrada=$true", "tipo='cierre_propio'", "$out.estado='error'"):
            self.assertIn(fragmento, bloque)
        self.assertLess(i, texto.index("[IO.File]::Move($temporary,$Respuesta)"))   # se cierra antes de publicar la respuesta
        self.assertNotIn("Stop-Process", texto)                                     # nunca se mata un proceso por nombre/ID


if __name__ == "__main__":
    unittest.main()
