"""Trabajos persistentes sobre modelos reales en disco y lector Python fabricado."""
from dataclasses import replace
import json
import threading
import unittest
from unittest.mock import patch

from draft2model import adaptador_etabs as ad
from draft2model.revision_visual import RevisionLocal
from draft2model.revision_verificacion_modelo import ServicioVerificacionModelo
from tests import test_vinculo_verificacion_modelo as fixtures


class ServicioTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.VinculoTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.app=RevisionLocal(self.f.f.root)
        def factory(work, lock):
            self.f.ver.config=replace(self.f.ver.config,trabajo=work,bloqueo=lock)
            return self.f.ver
        self.service=ServicioVerificacionModelo(self.app,factory)
        self.body={'caso':self.f.f.case,'modelo':self.f.folder.name,'huella_modelo':self.f.state['huella_modelo'],
            'expediente_sha256':self.app.expediente(self.f.f.case)[2],'clave_solicitud':'a'*32,
            'criterios':self.f.criteria,'ejes_locales_area':None}

    def execute(self, prep, **extra):
        return self.service.ejecutar({'caso':prep['caso'],'trabajo':prep['id'],
            'expediente_sha256':prep['expediente_sha256'],'huella_preparacion':prep['huella_preparacion'],
            'confirmacion_explicita':True,**extra})

    def finish(self, prep):
        self.service._threads[prep['id']].join(20)
        self.assertFalse(self.service._threads[prep['id']].is_alive())
        return self.service.consultar(prep['caso'],prep['id'])

    def test_prepara_idempotente_no_motor_clave_y_campos(self):
        with patch('subprocess.Popen',side_effect=AssertionError('No proceso al preparar')):
            a=self.service.preparar(self.body);b=self.service.preparar(self.body)
        self.assertEqual(a['id'],b['id']);self.assertFalse(a['lectura_comprobada'])
        with self.assertRaisesRegex(ValueError,'clave_reutilizada'):
            self.service.preparar({**self.body,'ejes_locales_area':{}})
        with self.assertRaises(ValueError):self.service.preparar({**self.body,'ruta_edb':'externa'})
        with self.assertRaises(ValueError):self.service.preparar({**self.body,'clave_solicitud':'b'*32,'criterios':{}})

    def test_confirmacion_modo_fuente_y_exclusion_compartida(self):
        prep=self.service.preparar(self.body)
        with self.assertRaisesRegex(ValueError,'confirmacion'):self.execute(prep,confirmacion_explicita=False)
        with self.assertRaisesRegex(ValueError,'preparacion_cambio'):self.execute(prep,huella_preparacion='0'*64)
        lease=ad.BloqueoExclusivo(self.app.ejecucion.lease).adquirir()
        try:
            with self.assertRaisesRegex(ValueError,'otra_ejecucion'):self.execute(prep)
        finally:lease.liberar()
        with self.assertRaises(ValueError):ServicioVerificacionModelo(self.app).preparar({**self.body,'clave_solicitud':'b'*32})
        self.f.f.base.original.write_bytes(b'fuente cambiada')
        self.assertFalse(self.service.consultar(prep['caso'],prep['id'])['vigente'])
        with self.assertRaisesRegex(ValueError,'entradas_no_vigentes'):self.execute(prep)
        self.assertNotIn(prep['id'],self.service._threads)

    def test_lectura_comprobada_discrepancia_no_aprueba_y_no_reenvia(self):
        point=next(iter(self.f.obs['puntos']['coordenadas']));self.f.obs['puntos']['coordenadas'][point][0]+=1
        self.f.obsfile.write_bytes(fixtures.v._bytes(self.f.obs))
        prep=self.service.preparar(self.body);self.execute(prep);result=self.finish(prep)
        self.assertEqual(result['estado'],'aceptado');self.assertTrue(result['lectura_comprobada'])
        self.assertEqual(result['resultado']['estado'],'discrepancias')
        self.assertFalse(result['resultado']['verificado']);self.assertFalse(result['aprueba_modelo'] or result['autoriza_analisis'])
        thread=self.service._threads[prep['id']];self.execute(prep);self.assertIs(thread,self.service._threads[prep['id']])
        target=self.f.folder.parent.parent/'verificaciones_modelo'/result['verificacion_id']/'respuesta.json'
        target.write_bytes(b'{}');self.assertFalse(self.service.consultar(prep['caso'],prep['id'])['lectura_comprobada'])

    def test_worker_fallido_y_huerfano_sin_reintento(self):
        prep=self.service.preparar(self.body)
        with patch.object(self.f.ver,'ejecutar_verificacion',side_effect=RuntimeError('fallo fabricado')):
            self.execute(prep);result=self.finish(prep)
        self.assertEqual(result['estado'],'incierto');self.assertTrue(result['requiere_recuperacion'])
        self.assertTrue(self.service.pendiente.exists());self.assertFalse(result['lectura_comprobada'])
        second=self.service.preparar({**self.body,'clave_solicitud':'b'*32})
        with self.assertRaisesRegex(ValueError,'motor_incierto'):self.execute(second)
        record,_=self.service._leer(second['caso'],second['id']);self.service._estado(record,'en_ejecucion')
        restarted=ServicioVerificacionModelo(self.app,self.service._fabrica)
        self.assertEqual(restarted.consultar(second['caso'],second['id'])['estado'],'incierto')

    def test_snapshot_alterado_no_lanza_y_clave_distinta_es_otro_trabajo(self):
        prep=self.service.preparar(self.body)
        other=self.service.preparar({**self.body,'clave_solicitud':'b'*32})
        self.assertNotEqual(prep['id'],other['id'])
        (self.service._carpeta(prep['caso'],prep['id'])/'plan.json').write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError,'entradas_no_vigentes'):self.execute(prep)
        self.assertFalse(self.service.pendiente.exists())
        self.assertFalse(self.service.consultar(prep['caso'],prep['id'])['vigente'])

    def test_worker_vivo_reserva_compartida_y_modo_no_suplantable(self):
        entered=threading.Event();release=threading.Event()
        original=self.f.ver.ejecutar_verificacion
        def waiting(*a,**kw):
            entered.set()
            if not release.wait(10):raise RuntimeError('timeout de prueba')
            return original(*a,**kw)
        prep=self.service.preparar(self.body)
        with patch.object(self.f.ver,'ejecutar_verificacion',side_effect=waiting):
            self.execute(prep)
            try:
                self.assertTrue(entered.wait(10))
                self.assertEqual(self.service.consultar(prep['caso'],prep['id'])['estado'],'en_ejecucion')
                with self.assertRaises(ad.ErrorBloqueo):ad.BloqueoExclusivo(self.app.ejecucion.lease).adquirir()
            finally:release.set();self.finish(prep)
        other=self.service.preparar({**self.body,'clave_solicitud':'b'*32})
        factory=self.service._fabrica
        def wrong(work,lock):
            verifier=factory(work,lock);verifier.config=replace(verifier.config,modo='real');return verifier
        self.service._fabrica=wrong
        with patch.object(self.f.ver,'ejecutar_verificacion',side_effect=AssertionError('Nunca lanzar con modo ajeno')):
            self.execute(other);result=self.finish(other)
        self.assertEqual(result['estado'],'incierto');self.assertFalse(result['lectura_comprobada'])
