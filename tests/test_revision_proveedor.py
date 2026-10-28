"""Trabajos web del proveedor visual con transporte Python; ninguna llamada real, clave ni red."""
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from draft2model.revision_proveedor import ErrorProveedorWeb, ServicioProveedor
from draft2model.revision_visual import RevisionLocal
from draft2model.entrada_vision import cargar_paquete
from tests import test_entrada_vision as fixtures

SECRETO = 'sk-prueba-no-real-0123456789'


class Transporte:
    """Transporte sintético: registra llamadas; nunca recibe credenciales."""
    def __init__(self, respuesta=None, error=None, efecto=None):
        self.respuesta, self.error, self.efecto, self.llamadas = respuesta, error, efecto, []

    def __call__(self, payload, timeout):
        self.llamadas.append((payload, timeout))
        if self.efecto:
            self.efecto()
        if self.error:
            raise self.error
        return self.respuesta


class ProveedorWebTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.EntradaVisionTests(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.app = RevisionLocal(self.fixture.case.parent)
        self.packet = self.fixture.pack()
        self.caso = self.fixture.case.name; self.fp = self.app.expediente(self.caso)[2]
        for target in ('draft2model.proveedor_openai._http', 'subprocess.Popen'):
            guard = patch(target, side_effect=AssertionError('Sin red ni procesos'))
            guard.start(); self.addCleanup(guard.stop)
        env = patch.dict('os.environ', {'OPENAI_API_KEY': ''}); env.start(); self.addCleanup(env.stop)

    def service(self, transporte=None):
        return ServicioProveedor(self.app, transporte)

    def body(self, clave='a'*32, **cambios):
        return {'caso': self.caso, 'expediente_sha256': self.fp, 'paquete': self.packet.parent.name,
                'modelo': 'fixture-vision', 'opciones': {'max_tokens': 512, 'detalle': 'low', 'timeout_s': 30},
                'clave_solicitud': clave, **cambios}

    def api(self, **cambios):
        req, sha, _, _ = cargar_paquete(self.fixture.manifest, self.packet)
        parsed = self.fixture.response(self.packet)
        return {'id': 'resp_fixture', 'model': 'fixture-vision-devuelto', 'status': 'completed',
                'output': [{'type': 'message', 'role': 'assistant',
                            'content': [{'type': 'output_text', 'text': json.dumps(parsed)}]}],
                'usage': {'input_tokens': 100, 'output_tokens': 20, 'total_tokens': 120}, **cambios}

    def run_job(self, service, item):
        out = service.ejecutar({'caso': self.caso, 'trabajo': item['id'], 'huella_preparacion': item['huella_preparacion'],
                                'expediente_sha256': item['expediente_sha256'], 'confirmacion_explicita': True})
        thread = service._threads.get(item['id'])
        if thread:
            thread.join(30); self.assertFalse(thread.is_alive())
        return out, service.consultar(self.caso, item['id'])

    def assertSinPrivados(self, data):
        text = json.dumps(data, ensure_ascii=False)
        for forbidden in (str(self.app.raiz), str(self.app.raiz).replace('\\', '\\\\'),
                          'Authorization', 'OPENAI_API_KEY', SECRETO, 'data:image'):
            self.assertNotIn(forbidden, text)

    def code(self, ctx):
        return ctx.exception.codigo

    def test_preparar_sin_clave_red_ni_proceso_idempotente_y_tras_reinicio(self):
        service = self.service()
        item = service.preparar(self.body())
        self.assertEqual(item['estado'], 'preparado'); self.assertTrue(item['vigente'])
        self.assertIsNone(item['modo']); self.assertIsNone(item['costo_estimado'])
        self.assertFalse(item['aprueba_ingenieria'] or item['aprueba_resultados'] or item['llamada_real_acreditada'])
        self.assertSinPrivados(item)
        self.assertEqual(service.preparar(self.body())['id'], item['id'])
        with self.assertRaises(ErrorProveedorWeb) as ctx:
            service.preparar(self.body(modelo='otro-modelo'))
        self.assertEqual(self.code(ctx), 'clave_reutilizada_con_otros_datos')
        for cambios in ({'modelo': ''}, {'opciones': {'max_tokens': 10, 'detalle': 'low', 'timeout_s': 30}},
                        {'opciones': {'max_tokens': 512, 'detalle': 'low', 'timeout_s': 30, 'ruta': 'x'}},
                        {'paquete': '../x'}, {'expediente_sha256': '0'*64}):
            with self.subTest(cambios=cambios), self.assertRaises(ErrorProveedorWeb):
                service.preparar(self.body(clave='b'*32, **cambios))
        reiniciado = self.service()
        self.assertEqual(reiniciado.consultar(self.caso, item['id'])['huella_preparacion'], item['huella_preparacion'])
        self.assertEqual([t['id'] for t in reiniciado.listar(self.caso)['trabajos']], [item['id']])

    def test_confirmacion_huella_y_clave_ausente_sin_envio(self):
        service = self.service()
        item = service.preparar(self.body())
        base = {'caso': self.caso, 'trabajo': item['id'], 'huella_preparacion': item['huella_preparacion'],
                'expediente_sha256': self.fp, 'confirmacion_explicita': True}
        for cambios, codigo in (({'confirmacion_explicita': 'si'}, 'confirmacion_requerida'),
                                ({'huella_preparacion': '0'*64}, 'preparacion_cambio')):
            with self.assertRaises(ErrorProveedorWeb) as ctx:
                service.ejecutar({**base, **cambios})
            self.assertEqual(self.code(ctx), codigo)
        with self.assertRaises(ErrorProveedorWeb) as ctx:
            service.ejecutar(base)  # modo real sin OPENAI_API_KEY
        self.assertEqual(self.code(ctx), 'clave_ausente_sin_envio')
        self.assertEqual(service.consultar(self.caso, item['id'])['estado'], 'preparado')
        self.assertFalse((self.fixture.case/'vision/intentos_openai').exists())

    def test_transporte_python_completado_verificado_sin_reenvio(self):
        transporte = Transporte(self.api())
        service = self.service(transporte)
        item = service.preparar(self.body())
        with patch.dict('os.environ', {'OPENAI_API_KEY': SECRETO}):
            started, done = self.run_job(service, item)
        self.assertEqual(started['estado'], 'en_ejecucion')
        self.assertEqual(done['estado'], 'completado_verificado'); self.assertTrue(done['vigente'])
        self.assertEqual(done['modo'], 'transporte_prueba_python'); self.assertEqual(done['proveedor_declarado'], 'simulado')
        self.assertFalse(done['llamada_real_acreditada'] or done['aprueba_ingenieria'] or done['aprueba_resultados'])
        self.assertEqual(done['modelo_declarado'], 'fixture-vision')
        self.assertEqual(done['observado']['modelo_devuelto'], 'fixture-vision-devuelto')
        self.assertEqual(done['observado']['usage']['total_tokens'], 120)
        self.assertTrue((self.fixture.case/'vision/respuestas'/done['respuesta_visual']['id']/'extraccion.json').is_file())
        self.assertEqual(len(transporte.llamadas), 1); self.assertEqual(transporte.llamadas[0][1], 30)
        self.assertSinPrivados(done)
        again, _ = self.run_job(service, item)
        self.assertEqual(again['estado'], 'completado_verificado'); self.assertEqual(len(transporte.llamadas), 1)
        for path in list(self.app.raiz.rglob('*')):
            if path.is_file() and path.suffix in ('.json', '.sqlite3'):
                self.assertNotIn(SECRETO.encode(), path.read_bytes(), path.name)
        self.assertEqual(self.service().listar(self.caso)['trabajos'][0]['estado'], 'completado_verificado')

    def test_respuesta_invalida_rechazada_sin_bloquear_caso(self):
        transporte = Transporte(self.api(status='incomplete'))
        service = self.service(transporte)
        _, done = self.run_job(service, service.preparar(self.body()))
        self.assertEqual(done['estado'], 'respuesta_rechazada'); self.assertIsNone(done['respuesta_visual'])
        transporte.respuesta = self.api()
        _, second = self.run_job(service, service.preparar(self.body(clave='b'*32)))
        self.assertEqual(second['estado'], 'completado_verificado'); self.assertEqual(len(transporte.llamadas), 2)

    def test_timeout_incierto_sin_relanzar_bloquea_caso_y_recuperacion_explicita(self):
        transporte = Transporte(error=TimeoutError('corte sintético'))
        service = self.service(transporte)
        item = service.preparar(self.body())
        _, done = self.run_job(service, item)
        self.assertEqual(done['estado'], 'incierto'); self.assertTrue(done['requiere_recuperacion'])
        again, _ = self.run_job(self.service(transporte), item)
        self.assertEqual(again['estado'], 'incierto')
        other = service.preparar(self.body(clave='b'*32))
        with self.assertRaises(ErrorProveedorWeb) as ctx:
            self.run_job(service, other)
        self.assertEqual(self.code(ctx), 'incertidumbre_pendiente_en_caso')
        self.assertEqual(len(transporte.llamadas), 1)
        recover = {'caso': self.caso, 'trabajo': item['id'], 'huella_preparacion': item['huella_preparacion'],
                   'confirmacion_explicita': True, 'resolucion': 'cerrar_sin_reintento'}
        with self.assertRaises(ErrorProveedorWeb):
            service.recuperar({**recover, 'confirmacion_explicita': False})
        closed = service.recuperar(recover)
        self.assertEqual(closed['estado'], 'incierto_resuelto')
        self.assertEqual(closed['resolucion'], {'resolucion': 'cerrar_sin_reintento', 'intento_registrado': True,
                                                'evidencia_completa': False})
        self.assertEqual(len(transporte.llamadas), 1)
        transporte.error = None; transporte.respuesta = self.api()
        _, second = self.run_job(service, other)
        self.assertEqual(second['estado'], 'completado_verificado')

    def test_recuperacion_con_evidencia_completa_se_verifica_sin_reenvio(self):
        transporte = Transporte(self.api())
        service = self.service(transporte)
        item = service.preparar(self.body())
        _, done = self.run_job(service, item)
        record, _ = service._leer_trabajo(self.caso, item['id'])
        service._estado({**record, 'salida': None}, 'incierto')  # p. ej. caída tras el resultado del cliente
        closed = service.recuperar({'caso': self.caso, 'trabajo': item['id'], 'huella_preparacion': item['huella_preparacion'],
                                    'confirmacion_explicita': True, 'resolucion': 'cerrar_sin_reintento'})
        self.assertEqual(closed['estado'], 'completado_verificado'); self.assertTrue(closed['resolucion']['evidencia_completa'])
        self.assertEqual(closed['respuesta_visual'], done['respuesta_visual']); self.assertEqual(len(transporte.llamadas), 1)

    def test_reinicio_con_trabajo_en_ejecucion_huerfano_queda_incierto(self):
        transporte = Transporte(self.api())
        service = self.service(transporte)
        item = service.preparar(self.body())
        record, _ = service._leer_trabajo(self.caso, item['id'])
        service._estado({**record, 'modo': 'transporte_prueba_python', 'proveedor_declarado': 'simulado'}, 'en_ejecucion')
        reiniciado = self.service(transporte)
        self.assertEqual(reiniciado.consultar(self.caso, item['id'])['estado'], 'incierto')
        again, _ = self.run_job(reiniciado, item)
        self.assertEqual(again['estado'], 'incierto'); self.assertEqual(transporte.llamadas, [])

    def test_fuentes_alteradas_antes_y_durante_el_envio(self):
        transporte = Transporte(self.api())
        service = self.service(transporte)
        item = service.preparar(self.body())
        plan = next((self.fixture.case/'vision/planes_openai').glob('*/plan.json'))
        original = plan.read_bytes(); plan.write_bytes(original+b' ')
        self.assertFalse(service.consultar(self.caso, item['id'])['vigente'])
        with self.assertRaises(ErrorProveedorWeb) as ctx:
            self.run_job(service, item)
        self.assertEqual(self.code(ctx), 'entradas_no_vigentes')
        self.assertEqual(service.consultar(self.caso, item['id'])['estado'], 'fallido_sin_envio')
        self.assertEqual(transporte.llamadas, [])
        second = service.preparar(self.body(clave='b'*32))
        plan2 = self.fixture.case/'vision/planes_openai'/[p for p in (self.fixture.case/'vision/planes_openai').iterdir()
                                                          if p.name != plan.parent.name][0].name/'plan.json'
        transporte.efecto = lambda: plan2.write_bytes(plan2.read_bytes()+b' ')
        _, done = self.run_job(service, second)
        self.assertEqual(done['estado'], 'respuesta_rechazada'); self.assertEqual(len(transporte.llamadas), 1)

    def test_paquete_alterado_invalida_preparado(self):
        service = self.service()
        item = service.preparar(self.body())
        image = next(p for p in self.packet.parent.rglob('*.png'))
        image.write_bytes(image.read_bytes()+b'X')
        self.assertFalse(service.consultar(self.caso, item['id'])['vigente'])


if __name__ == '__main__':
    unittest.main()
