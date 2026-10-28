"""Contexto versionado (corpus, sitio, reglas) sobre copias temporales de la fixture sintética; sin red."""
import base64
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from draft2model.fuentes import huella_corpus
from draft2model.resultados_estructurales import huella_declaracion
from draft2model.revision_contexto import ErrorContexto, ServicioContexto
from draft2model.revision_visual import RevisionLocal
from draft2model.sitio import huella_capa
from tests.fixture_etabs import extraer_evidencia

CASO = 'demo-integrada-sintetica'
RESULTADO = '72c06efb3bfe477bb1fe565809aeddec'
TEXTO = 'Fuente SINTETICA de prueba. Deriva: relación desplazamiento/altura de entrepiso.'


def corpus(sintetico=True, texto=TEXTO):
    data = {'contrato': 'draft2model.corpus', 'version': '0.1.0', 'datos_sinteticos': sintetico,
            'documentos': [{'id': 'D1', 'titulo': 'Fuente sintética', 'edicion': 'prueba', 'archivo': 'fuente.txt',
                            'sha256': hashlib.sha256(texto.encode()).hexdigest()}],
            'fragmentos': [{'id': 'F1', 'documento': 'D1', 'pagina': 1, 'apartado': 'Deriva',
                            'texto': 'Deriva: relación desplazamiento/altura de entrepiso.'}], 'aprobacion': None}
    data['aprobacion'] = {'huella': huella_corpus(data), 'revisor_declarado': 'Prueba sintética de software',
                          'fecha': '2026-10-18', 'alcance': 'Ensayo de software, sin normativa real'}
    return data


def capa():
    data = {'contrato': 'draft2model.capa_sitio', 'version': '0.1.0', 'crs': 'EPSG:4326',
            'fuente': {'titulo': 'Cuadrado SINTÉTICO', 'edicion': 'prueba', 'referencia': 'fixture local'},
            'fecha': '2026-10-18', 'precision_m': 10, 'datos_sinteticos': True,
            'zonas': [{'id': 'Z1', 'etiqueta': 'Zona sintética',
                       'geometria': {'type': 'Polygon', 'coordinates': [[[0, 0], [2, 0], [2, 2], [0, 2], [0, 0]]]}}],
            'aprobacion': None}
    data['aprobacion'] = {'huella': huella_capa(data), 'revisor_declarado': 'Prueba sintética', 'fecha': '2026-10-18',
                          'alcance': 'Solo prueba de cobertura'}
    return data


def reglas(limite, comparador='<=', sintetico=True, aprobar=True):
    data = {'contrato': 'draft2model.reglas_estructurales', 'version_contrato': '0.1.0', 'id': 'reglas-ctx-001',
            'datos_sinteticos': sintetico,
            'reglas': [{'id': 'R-V', 'variable': 'cortante', 'unidad': 'kN',
                        'formula': {'expresion': 'factor * x + desplazamiento', 'factor': 1.0, 'desplazamiento': 0.0},
                        'limite': limite, 'comparador': comparador,
                        'aplicabilidad': {'aplica': True, 'casos': ['EST'], 'direcciones': ['X'], 'ubicaciones': ['base'],
                                          'motivo': 'Selector fabricado para pruebas de software.'},
                        'fuente': {'titulo': 'Fixture SIN valor normativo', 'edicion': 'sintética', 'apartado': 'R-V',
                                   'referencia': 'tests/test_revision_contexto.py'}}],
            'revision': {'estado': 'borrador', 'aprobacion': None}}
    if aprobar:
        data['revision'] = {'estado': 'aprobado', 'aprobacion': {
            'revisor_declarado': 'Fixture automática, identidad no autenticada', 'fecha': '2026-10-18',
            'motivo': 'Aprobación fabricada para pruebas de software.', 'alcance': 'Solo pruebas sintéticas.',
            'huella_contenido': huella_declaracion(data)}}
    return data


class ContextoTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.bundle = extraer_evidencia(Path(temp.name).resolve()/'fixture')
        self.app = RevisionLocal(self.bundle/'private')
        self.service = ServicioContexto(self.app)
        self.fp = self.app.expediente(CASO)[2]
        self.case = self.app.raiz/CASO
        self.huella_resultado = self.app.resultados.consultar_resultado(CASO, RESULTADO, expediente_sha256=self.fp)['huella']
        for target in ('subprocess.Popen', 'urllib.request.urlopen', 'socket.create_connection'):
            guard = patch(target, side_effect=AssertionError('Sin red ni procesos')); guard.start(); self.addCleanup(guard.stop)

    def base(self):
        return {'caso': CASO, 'expediente_sha256': self.fp}

    def reg_corpus(self, data=None, texto=TEXTO, nombre='fuente.txt'):
        return self.service.registrar_corpus({**self.base(), 'manifiesto_json': json.dumps(data or corpus()),
            'archivos': [{'nombre': nombre, 'contenido_base64': base64.b64encode(texto.encode()).decode()}]})

    def reg_sitio(self, data=None):
        return self.service.registrar_sitio({**self.base(), 'capa_json': json.dumps(data or capa())})

    def reg_reglas(self, data):
        return self.service.registrar_reglas({**self.base(), 'reglas_json': json.dumps(data)})

    def evaluar(self, item, **cambios):
        return self.service.evaluar({**self.base(), 'resultado': RESULTADO, 'reglas': item['id'],
                                     'huella_resultados': self.huella_resultado, 'huella_reglas': item['huella'], **cambios})

    def assertSinRutas(self, data):
        text = json.dumps(data, ensure_ascii=False)
        for ruta in (str(self.app.raiz), json.dumps(str(self.app.raiz))[1:-1]):
            self.assertNotIn(ruta, text)

    def test_recorrido_corpus_recuperacion_abstencion_y_reinicio(self):
        item = self.reg_corpus()
        self.assertEqual(item['tipo'], 'corpus'); self.assertTrue(item['datos_sinteticos'] and item['utilizable'])
        self.assertEqual(item['identidad_revisor'], 'declarada_no_verificada')
        self.assertFalse(item['verificacion_profesional'] or item['aprueba_resultados'] or item['aprueba_informe'])
        self.assertEqual(item['aprobacion_declarada']['revisor_declarado'], 'Prueba sintética de software')
        found = self.service.recuperar({**self.base(), 'corpus': item['id'], 'consulta': '¿Cómo se define la deriva?',
                                        'limite': 5, 'resultado': None})
        self.assertFalse(found['salida']['abstencion']); self.assertEqual(found['salida']['fragmentos'][0]['id'], 'F1')
        self.assertEqual(found['fuentes']['corpus'], {'id': item['id'], 'huella': item['huella']})
        none = self.service.recuperar({**self.base(), 'corpus': item['id'], 'consulta': 'capacidad portante geotécnica',
                                       'limite': 5, 'resultado': RESULTADO})
        self.assertTrue(none['salida']['abstencion']); self.assertEqual(none['salida']['fragmentos'], [])
        self.assertEqual(none['fuentes']['resultado'], {'id': RESULTADO, 'huella': self.huella_resultado})
        nuevo = ServicioContexto(RevisionLocal(self.app.raiz))
        listado = nuevo.listar(CASO, expediente_sha256=self.fp)
        self.assertEqual([r['vigente'] for r in listado['corpus']], [True])
        self.assertEqual(sorted(r['id'] for r in listado['derivados']), sorted([found['id'], none['id']]))
        self.assertEqual(nuevo.consultar_derivado(CASO, found['id'], expediente_sha256=self.fp)['salida'], found['salida'])
        self.assertSinRutas([item, found, none, listado])

    def test_documento_alterado_invalida_corpus_y_derivados(self):
        item = self.reg_corpus()
        found = self.service.recuperar({**self.base(), 'corpus': item['id'], 'consulta': 'deriva', 'limite': 1, 'resultado': None})
        target = self.case/'contexto/corpus'/item['id']/'fuente.txt'
        original = target.read_bytes(); target.write_bytes(original+b' ALTERADO')
        with self.assertRaises(ErrorContexto):
            self.service.consultar(CASO, 'corpus', item['id'], expediente_sha256=self.fp)
        with self.assertRaises(ErrorContexto):
            self.service.consultar_derivado(CASO, found['id'], expediente_sha256=self.fp)
        listado = self.service.listar(CASO, expediente_sha256=self.fp)
        self.assertFalse(listado['corpus'][0]['vigente']); self.assertFalse(listado['derivados'][0]['vigente'])
        target.write_bytes(original)
        self.assertTrue(self.service.consultar_derivado(CASO, found['id'], expediente_sha256=self.fp)['vigente'])
        salida = self.case/'contexto/derivados'/found['id']/'salida.json'
        salida.write_bytes(salida.read_bytes().replace(b'F1', b'F9'))
        with self.assertRaises(ErrorContexto):
            self.service.consultar_derivado(CASO, found['id'], expediente_sha256=self.fp)

    def test_registro_rechaza_sin_aprobacion_rutas_tipos_y_limites(self):
        sin = corpus(); sin['aprobacion'] = None
        obsoleta = corpus(); obsoleta['fragmentos'][0]['texto'] = 'Otro texto'
        for data, texto, nombre in ((sin, TEXTO, 'fuente.txt'), (obsoleta, TEXTO, 'fuente.txt'),
                                    (corpus(), TEXTO+'x', 'fuente.txt'), (corpus(), TEXTO, '../fuente.txt'),
                                    (corpus(), TEXTO, 'corpus.json'), (corpus(), TEXTO, 'otro.txt')):
            with self.subTest(nombre=nombre), self.assertRaises(ErrorContexto):
                self.reg_corpus(data, texto, nombre)
        abs_corpus = corpus(); abs_corpus['documentos'][0]['archivo'] = 'C:/x/fuente.txt'
        for body in ({**self.base(), 'manifiesto_json': json.dumps(corpus()), 'archivos': [{'nombre': 'fuente.txt', 'contenido_base64': '***'}]},
                     {**self.base(), 'manifiesto_json': json.dumps(corpus()), 'archivos': 'fuente.txt'},
                     {**self.base(), 'manifiesto_json': json.dumps(corpus()), 'archivos': [], 'ruta': 'x'},
                     {**self.base(), 'manifiesto_json': '{"a":1,"a":2}', 'archivos': []},
                     {**self.base(), 'manifiesto_json': json.dumps(abs_corpus),
                      'archivos': [{'nombre': 'fuente.txt', 'contenido_base64': base64.b64encode(TEXTO.encode()).decode()}]},
                     {**self.base(), 'manifiesto_json': json.dumps(corpus()),
                      'archivos': [{'nombre': 'fuente.txt', 'contenido_base64': 'A'*(6*1024*1024)}]},
                     {'caso': CASO, 'expediente_sha256': '0'*64, 'manifiesto_json': json.dumps(corpus()), 'archivos': []}):
            with self.assertRaises(ErrorContexto):
                self.service.registrar_corpus(body)
        with self.assertRaises(ErrorContexto):
            self.reg_reglas(reglas(1.0, aprobar=False))  # borrador: no utilizable, no se aprueba aquí
        bad = capa(); bad['zonas'][0]['geometria']['coordinates'] = [[[0, 0], [1, 0], [0, 0]]]
        with self.assertRaises(ErrorContexto):
            self.reg_sitio(bad)
        with self.assertRaises(ErrorContexto):
            self.service.registrar_sitio({**self.base(), 'capa_json': 'x'*(1024*1024+1)})
        self.assertFalse((self.case/'contexto/corpus').exists() and any(
            p.name[:1] != '.' for p in (self.case/'contexto/corpus').iterdir()))

    def test_sitio_dentro_limite_sin_cobertura_y_sin_inferencias(self):
        item = self.reg_sitio()
        for punto, estado in (((1, 1), 'dentro'), ((0, 1), 'limite'), ((3, 3), 'sin_cobertura')):
            out = self.service.consultar_sitio({**self.base(), 'sitio': item['id'], 'longitud': punto[0],
                                                'latitud': punto[1], 'resultado': None})
            self.assertEqual(out['salida']['estado'], estado)
            self.assertIsNone(out['salida']['parametros_geotecnicos']); self.assertIsNone(out['salida']['capacidad_portante'])
            self.assertEqual(out['salida']['huella_capa'], item['huella'])
        for lon in (float('nan'), '1', True, 200):
            with self.assertRaises(ErrorContexto):
                self.service.consultar_sitio({**self.base(), 'sitio': item['id'], 'longitud': lon, 'latitud': 1, 'resultado': None})

    def test_reglas_debajo_en_sobre_y_huellas_exactas(self):
        for limite, relacion, satisface in ((1.0, 'debajo', True), (0.0, 'en', True), (-1.0, 'sobre', False)):
            item = self.reg_reglas(reglas(limite))
            out = self.evaluar(item)
            ev = out['salida']['evaluaciones'][0]
            self.assertEqual((ev['relacion_limite'], ev['satisface_regla_configurada']), (relacion, satisface))
            self.assertEqual(ev['valor_entrada'], 0.0); self.assertEqual(out['salida']['huella_reglas'], item['huella'])
            self.assertEqual(out['fuentes']['resultado'], {'id': RESULTADO, 'huella': self.huella_resultado})
            self.assertFalse(out['aprueba_resultados'] or out['aprueba_informe'])
            self.assertEqual(out['conformidad_normativa'], 'no_evaluada')
        with self.assertRaises(ErrorContexto):
            self.evaluar(item, huella_reglas='0'*64)
        with self.assertRaises(ErrorContexto):
            self.evaluar(item, huella_resultados='0'*64)
        target = self.case/'contexto/reglas'/item['id']/'reglas.json'
        target.write_bytes(target.read_bytes().replace(b'-1.0', b'-2.0'))
        with self.assertRaises(ErrorContexto):
            self.evaluar(item)
        listado = self.service.listar(CASO, expediente_sha256=self.fp)
        self.assertEqual([r['vigente'] for r in listado['reglas']].count(False), 1)

    def test_mezcla_sintetico_real(self):
        reales = self.reg_reglas(reglas(1.0, sintetico=False))
        with self.assertRaises(ErrorContexto):
            self.evaluar(reales)  # el núcleo exige igual naturaleza para reglas y resultados
        with self.assertRaises(ErrorContexto):
            ServicioContexto._mezcla(True, {'datos_sinteticos': False})  # contexto sintético sobre resultado real
        ServicioContexto._mezcla(False, {'datos_sinteticos': True})  # permitido, como en informe.py
        real = self.reg_corpus(corpus(sintetico=False))
        out = self.service.recuperar({**self.base(), 'corpus': real['id'], 'consulta': 'deriva', 'limite': 1, 'resultado': RESULTADO})
        self.assertFalse(out['salida']['datos_sinteticos'])

    def test_resultado_alterado_invalida_evaluacion_y_cambio_durante_consulta(self):
        item = self.reg_reglas(reglas(1.0))
        out = self.evaluar(item)
        original = self.service._calcular

        def cambiar(*args, **kwargs):
            value = original(*args, **kwargs)
            target = self.case/'contexto/reglas'/item['id']/'reglas.json'
            target.write_bytes(target.read_bytes()+b' ')  # bytes con huella registrada
            return value
        with patch.object(self.service, '_calcular', side_effect=cambiar):
            with self.assertRaises(ErrorContexto):
                self.evaluar(item)
        path = self.case/'resultados_estructurales'/RESULTADO/'resultados.json'
        path.write_bytes(path.read_bytes()+b'\n')
        with self.assertRaises(ErrorContexto):
            self.service.consultar_derivado(CASO, out['id'], expediente_sha256=self.fp)

    def test_carpeta_enlazada_rechazada(self):
        item = self.reg_sitio()
        group = self.case/'contexto/sitio'
        moved = self.case/'sitio_movido'
        shutil.move(str(group), str(moved))
        try:
            import _winapi
            _winapi.CreateJunction(str(moved), str(group))
        except (ImportError, OSError):
            try:
                os.symlink(moved, group, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest('No se pueden crear enlaces en este sistema.')
        with self.assertRaises(ErrorContexto):
            self.service.consultar(CASO, 'sitio', item['id'], expediente_sha256=self.fp)


if __name__ == '__main__':
    unittest.main()
