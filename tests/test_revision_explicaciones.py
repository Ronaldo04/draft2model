"""Explicaciones sustentadas con dobles Python; sin red, procesos, API real ni ETABS."""
import base64
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from draft2model.proveedor_openai import ErrorProveedor
from draft2model.revision_contexto import ServicioContexto
from draft2model.revision_explicaciones import ErrorExplicaciones, ServicioExplicaciones
from draft2model.revision_visual import RevisionLocal
from tests.fixture_etabs import extraer_evidencia
from tests.test_revision_contexto import CASO, RESULTADO, TEXTO, capa, corpus, reglas

SECRETO = 'sk-prueba-no-real-explicaciones-01'
FRAGMENTO = 'Deriva: relación desplazamiento/altura de entrepiso.'


class Transporte:
    def __init__(self, respuesta=None, error=None, efecto=None):
        self.respuesta, self.error, self.efecto, self.llamadas = respuesta, error, efecto, []

    def __call__(self, payload, timeout):
        self.llamadas.append((payload, timeout))
        if self.efecto:
            self.efecto()
        if self.error:
            raise self.error
        return self.respuesta


def declaracion(**cambios):
    base = {'id': 'D1', 'texto': 'El cortante VX en la base es 0.0 kN según el resultado vigente.',
            'indicadores': ['R:VX'], 'cifras': [{'indicador': 'R:VX', 'valor': 0.0, 'unidad': 'kN'}],
            'citas': [{'fragmento_id': 'F1', 'texto': FRAGMENTO}]}
    base.update(cambios)
    return base


def api(declaraciones=None, **cambios):
    parsed = {'contrato': 'draft2model.explicacion_llm', 'version': '0.1.0',
              'declaraciones': [declaracion()] if declaraciones is None else declaraciones,
              'abstenciones': [{'tema': 'normativa', 'motivo': 'No hay normativa en los datos.'}]}
    return {'id': 'resp_fixture', 'model': 'modelo-devuelto-fixture', 'status': 'completed',
            'output': [{'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': json.dumps(parsed)}]}],
            'usage': {'input_tokens': 10, 'output_tokens': 5, 'total_tokens': 15}, **cambios}


class ExplicacionesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.bundle = extraer_evidencia(Path(temp.name).resolve()/'fixture')
        self.app = RevisionLocal(self.bundle/'private')
        self.fp = self.app.expediente(CASO)[2]; self.case = self.app.raiz/CASO
        for target in ('draft2model.proveedor_openai._http', 'subprocess.Popen', 'urllib.request.urlopen',
                       'socket.create_connection'):
            guard = patch(target, side_effect=AssertionError('Sin red ni procesos')); guard.start(); self.addCleanup(guard.stop)
        env = patch.dict('os.environ', {'OPENAI_API_KEY': ''}); env.start(); self.addCleanup(env.stop)
        ctx = ServicioContexto(self.app); base = {'caso': CASO, 'expediente_sha256': self.fp}
        self.huella = self.app.resultados.consultar_resultado(CASO, RESULTADO, expediente_sha256=self.fp)['huella']
        self.corpus = ctx.registrar_corpus({**base, 'manifiesto_json': json.dumps(corpus()),
            'archivos': [{'nombre': 'fuente.txt', 'contenido_base64': base64.b64encode(TEXTO.encode()).decode()}]})
        self.rec = ctx.recuperar({**base, 'corpus': self.corpus['id'], 'consulta': 'deriva', 'limite': 3, 'resultado': RESULTADO})
        self.rules = ctx.registrar_reglas({**base, 'reglas_json': json.dumps(reglas(1.0))})
        self.ev = ctx.evaluar({**base, 'resultado': RESULTADO, 'reglas': self.rules['id'],
                               'huella_resultados': self.huella, 'huella_reglas': self.rules['huella']})
        self.site = ctx.consultar_sitio({**base, 'sitio': ctx.registrar_sitio({**base, 'capa_json': json.dumps(capa())})['id'],
                                         'longitud': 1, 'latitud': 1, 'resultado': None})

    def body(self, clave='a'*32, **cambios):
        return {'caso': CASO, 'expediente_sha256': self.fp, 'resultado': RESULTADO, 'huella_resultados': self.huella,
                'derivados': {'recuperacion': self.rec['id'], 'evaluacion': self.ev['id'], 'sitio': self.site['id']},
                'modelo': 'modelo-declarado-fixture', 'opciones': {'max_tokens': 512, 'timeout_s': 20},
                'clave_solicitud': clave, **cambios}

    def run_job(self, service, item):
        out = service.ejecutar({'caso': CASO, 'trabajo': item['id'], 'huella_preparacion': item['huella_preparacion'],
                                'expediente_sha256': self.fp, 'confirmacion_explicita': True})
        thread = service._threads.get(item['id'])
        if thread:
            thread.join(30); self.assertFalse(thread.is_alive())
        return out, service.consultar(CASO, item['id'])

    def assertSeguro(self, data):
        text = json.dumps(data, ensure_ascii=False)
        for forbidden in (str(self.app.raiz), json.dumps(str(self.app.raiz))[1:-1], 'Authorization',
                          'OPENAI_API_KEY', SECRETO):
            self.assertNotIn(forbidden, text)

    def assertContingencia(self, done, causa):
        self.assertEqual(done['estado'], 'contingencia'); salida = done['salida']
        self.assertEqual((salida['modo'], salida['causa']), ('contingencia_deterministica', causa))
        self.assertFalse(salida['generacion_llm_real']); self.assertIsNone(salida['declaraciones_llm'])
        det = salida['deterministico']
        self.assertEqual(det['indicadores'][0]['ref'], 'R:VX'); self.assertEqual(det['indicadores'][0]['valor'], 0.0)
        self.assertEqual(det['fragmentos'][0]['texto'], FRAGMENTO); self.assertEqual(det['fragmentos'][0]['edicion'], 'prueba')
        self.assertTrue(any('E:R-V:EST:X:base' in line for line in det['tabla']))
        return salida

    def test_preparacion_sin_clave_red_idempotente_y_reinicio(self):
        service = ServicioExplicaciones(self.app)
        item = service.preparar(self.body())
        self.assertEqual(item['estado'], 'preparado'); self.assertTrue(item['vigente']); self.assertIsNone(item['salida'])
        self.assertFalse(item['aprueba_resultados'] or item['aprueba_informe'])
        self.assertSeguro(item)
        self.assertEqual(service.preparar(self.body())['id'], item['id'])
        with self.assertRaises(ErrorExplicaciones) as ctx:
            service.preparar(self.body(modelo='otro'))
        self.assertEqual(ctx.exception.codigo, 'clave_reutilizada_con_otros_datos')
        for cambios in ({'huella_resultados': '0'*64}, {'modelo': ''}, {'derivados': {'recuperacion': None}},
                        {'derivados': {'recuperacion': self.ev['id'], 'evaluacion': None, 'sitio': None}},
                        {'opciones': {'max_tokens': 1, 'timeout_s': 20}}):
            with self.subTest(cambios=cambios), self.assertRaises(ErrorExplicaciones):
                service.preparar(self.body(clave='b'*32, **cambios))
        peticion = (self.app.raiz/'.explicaciones_web/trabajos'/item['id']/'peticion.json').read_text(encoding='utf-8')
        self.assertNotIn('api.openai.com', peticion); self.assertIn('R:VX', peticion)
        self.assertEqual(ServicioExplicaciones(self.app).listar(CASO)['trabajos'][0]['id'], item['id'])

    def test_contingencia_por_clave_ausente_sin_envio(self):
        service = ServicioExplicaciones(self.app)
        _, done = self.run_job(service, service.preparar(self.body()))
        self.assertContingencia(done, 'api_restringida_a_revision_planos')
        self.assertFalse((self.app.raiz/'.explicaciones_web/trabajos'/done['id']/'intento.json').exists())
        self.assertSeguro(done)

    def test_respuesta_valida_sustentada_queda_propuesta_y_sin_reenvio(self):
        transporte = Transporte(api())
        service = ServicioExplicaciones(self.app, transporte)
        item = service.preparar(self.body())
        started, done = self.run_job(service, item)
        self.assertEqual(started['estado'], 'en_ejecucion')
        self.assertEqual(done['estado'], 'completado_llm_verificado'); salida = done['salida']
        self.assertEqual(salida['modo'], 'llm_verificado'); self.assertFalse(salida['generacion_llm_real'])
        self.assertEqual(salida['modo_transporte'], 'transporte_prueba_python')
        self.assertEqual(salida['declaraciones_llm']['declaraciones'][0]['estado'], 'propuesta_pendiente_revision_humana')
        self.assertEqual(salida['observado']['modelo_devuelto'], 'modelo-devuelto-fixture')
        self.assertEqual(salida['modelo_declarado'], 'modelo-declarado-fixture')
        self.assertEqual(salida['conformidad_normativa'], 'no_evaluada')
        self.run_job(service, item); self.assertEqual(len(transporte.llamadas), 1)
        schema = transporte.llamadas[0][0]['text']['format']['schema']
        self.assertEqual(schema['properties']['declaraciones']['items']['properties']['citas']['items']['properties']['fragmento_id']['enum'], ['F1'])

    def test_contenido_no_sustentado_cae_a_contingencia(self):
        casos = {'cita_falsa': declaracion(citas=[{'fragmento_id': 'F1', 'texto': 'Texto inventado.'}]),
                 'cifra_alterada': declaracion(cifras=[{'indicador': 'R:VX', 'valor': 0.5, 'unidad': 'kN'}]),
                 'unidad_alterada': declaracion(cifras=[{'indicador': 'R:VX', 'valor': 0.0, 'unidad': 'N'}]),
                 'numero_sin_respaldo': declaracion(texto='El cortante es 12.5 kN.'),
                 'indicador_inexistente': declaracion(indicadores=['R:INVENTADO'], cifras=[]),
                 'sin_sustento': declaracion(indicadores=[], cifras=[], citas=[], texto='Texto libre.'),
                 'conformidad': declaracion(texto='La estructura cumple la norma con 0.0 kN.')}
        for i, (nombre, decl) in enumerate(casos.items()):
            with self.subTest(nombre):
                service = ServicioExplicaciones(self.app, Transporte(api([decl])))
                _, done = self.run_job(service, service.preparar(self.body(clave=format(i+1, '032x'))))
                salida = self.assertContingencia(done, 'contenido_no_sustentado')
                self.assertTrue(salida['errores_validacion'])

    def test_respuesta_invalida_y_rechazo_definitivo(self):
        service = ServicioExplicaciones(self.app, Transporte(api(status='incomplete')))
        _, done = self.run_job(service, service.preparar(self.body()))
        self.assertContingencia(done, 'respuesta_llm_invalida')
        service = ServicioExplicaciones(self.app, Transporte(error=ErrorProveedor('OpenAI devolvió HTTP 400; no se reintentó.')))
        _, done = self.run_job(service, service.preparar(self.body(clave='b'*32)))
        self.assertContingencia(done, 'rechazo_llm')

    def test_incierto_bloquea_nueva_clave_reinicio_y_recuperacion(self):
        transporte = Transporte(error=TimeoutError('corte sintético'))
        service = ServicioExplicaciones(self.app, transporte)
        item = service.preparar(self.body())
        _, done = self.run_job(service, item)
        self.assertEqual(done['estado'], 'incierto'); self.assertTrue(done['requiere_recuperacion'])
        again, _ = self.run_job(ServicioExplicaciones(self.app, transporte), item)
        self.assertEqual(again['estado'], 'incierto')
        other = service.preparar(self.body(clave='b'*32))
        with self.assertRaises(ErrorExplicaciones) as ctx:
            self.run_job(service, other)
        self.assertEqual(ctx.exception.codigo, 'incertidumbre_pendiente_en_caso')
        self.assertEqual(len(transporte.llamadas), 1)
        recover = {'caso': CASO, 'trabajo': item['id'], 'huella_preparacion': item['huella_preparacion'],
                   'confirmacion_explicita': True, 'resolucion': 'cerrar_sin_reintento'}
        with self.assertRaises(ErrorExplicaciones):
            service.recuperar({**recover, 'resolucion': 'reintentar'})
        closed = service.recuperar(recover)
        self.assertEqual(closed['estado'], 'incierto_resuelto'); self.assertEqual(closed['salida']['causa'], 'envio_incierto_cerrado')
        transporte.error = None; transporte.respuesta = api()
        _, second = self.run_job(service, other)
        self.assertEqual(second['estado'], 'completado_llm_verificado'); self.assertEqual(len(transporte.llamadas), 2)

    def test_huerfano_tras_reinicio_no_reenvia(self):
        transporte = Transporte(api())
        service = ServicioExplicaciones(self.app, transporte)
        item = service.preparar(self.body())
        record, _ = service._trabajo(CASO, item['id'])
        service._estado({**record, 'modo_transporte': 'transporte_prueba_python'}, 'en_ejecucion')
        reiniciado = ServicioExplicaciones(self.app, transporte)
        self.assertEqual(reiniciado.consultar(CASO, item['id'])['estado'], 'incierto')
        self.assertEqual(self.run_job(reiniciado, item)[0]['estado'], 'incierto'); self.assertEqual(transporte.llamadas, [])

    def test_cambios_de_fuentes_invalidan_preparacion_y_explicacion(self):
        transporte = Transporte(api())
        service = ServicioExplicaciones(self.app, transporte)
        done = self.run_job(service, service.preparar(self.body()))[1]
        self.assertTrue(done['vigente'])
        doc = self.case/'contexto/corpus'/self.corpus['id']/'fuente.txt'
        original = doc.read_bytes(); doc.write_bytes(original+b'X')
        stale = service.consultar(CASO, done['id'])
        self.assertFalse(stale['vigente']); self.assertIsNone(stale['salida'])
        doc.write_bytes(original)
        self.assertTrue(service.consultar(CASO, done['id'])['vigente'])
        item = service.preparar(self.body(clave='b'*32))
        rules = self.case/'contexto/reglas'/self.rules['id']/'reglas.json'
        rules.write_bytes(rules.read_bytes()+b' ')
        self.assertFalse(service.consultar(CASO, item['id'])['vigente'])
        with self.assertRaises(ErrorExplicaciones) as ctx:
            self.run_job(service, item)
        self.assertEqual(ctx.exception.codigo, 'entradas_no_vigentes')
        self.assertEqual(len(transporte.llamadas), 1)

    def test_cambio_durante_envio_no_se_acepta(self):
        rules = self.case/'contexto/reglas'/self.rules['id']/'reglas.json'
        transporte = Transporte(api(), efecto=lambda: rules.write_bytes(rules.read_bytes()+b' '))
        service = ServicioExplicaciones(self.app, transporte)
        _, done = self.run_job(service, service.preparar(self.body()))
        self.assertEqual(done['estado'], 'fallido_fuentes_cambiadas'); self.assertIsNone(done['salida'])

    def test_clave_presente_no_autoriza_api_para_explicaciones(self):
        with patch.dict('os.environ', {'OPENAI_API_KEY': SECRETO}), \
                patch('draft2model.proveedor_openai._http', return_value=api()) as http:
            service = ServicioExplicaciones(self.app)
            _, done = self.run_job(service, service.preparar(self.body()))
        http.assert_not_called()
        self.assertContingencia(done, 'api_restringida_a_revision_planos')
        self.assertSeguro(done)
        for path in self.app.raiz.rglob('*'):
            if path.is_file():
                self.assertNotIn(SECRETO.encode(), path.read_bytes(), path.name)


if __name__ == '__main__':
    unittest.main()
