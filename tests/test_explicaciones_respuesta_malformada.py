"""Referencias malformadas en respuesta no equivalen a incertidumbre de envío."""
import unittest
from draft2model.revision_explicaciones import ServicioExplicaciones
from tests import test_revision_explicaciones as fixture


class RespuestaMalformadaTests(unittest.TestCase):
    def test_referencias_no_hashables_producen_contingencia_sin_bloquear_caso(self):
        base=fixture.ExplicacionesTests();base.setUp();self.addCleanup(base.doCleanups)
        changes=({'indicadores':[{}]},
                 {'cifras':[{'indicador':[],'valor':0.0,'unidad':'kN'}]},
                 {'citas':[{'fragmento_id':{},'texto':'sin origen válido'}]})
        for i,change in enumerate(changes):
            with self.subTest(change=change):
                transport=fixture.Transporte(fixture.api([fixture.declaracion(**change)]))
                service=ServicioExplicaciones(base.app,transport)
                job=service.preparar(base.body(clave=f'{i+10:032x}'))
                _,done=base.run_job(service,job)
                self.assertEqual(done['estado'],'contingencia')
                self.assertEqual(done['salida']['causa'],'contenido_no_sustentado')
                self.assertFalse(done['requiere_recuperacion'])
                self.assertEqual(len(transport.llamadas),1)
