import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from draft2model.fuentes import cargar_corpus, huella_corpus, recuperar, verificar_citas


class FuentesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name)
        self.source = self.folder / 'fuente.txt'
        self.source.write_text('Fuente SINTETICA. Deriva: relación desplazamiento/altura.', encoding='utf-8')
        self.data = {'contrato':'draft2model.corpus', 'version':'0.1.0', 'datos_sinteticos':True,
                     'documentos':[{'id':'D1','titulo':'Fuente sintética','edicion':'prueba','archivo':'fuente.txt',
                                    'sha256':hashlib.sha256(self.source.read_bytes()).hexdigest()}],
                     'fragmentos':[{'id':'F1','documento':'D1','pagina':1,'apartado':'Deriva',
                                    'texto':'Deriva: relación desplazamiento/altura.'}], 'aprobacion':None}
        self.path = self.folder / 'corpus.json'
        self.write()

    def write(self):
        self.data['aprobacion'] = {'huella':huella_corpus(self.data), 'revisor_declarado':'Prueba sintética',
                                  'fecha':'2026-10-16','alcance':'Ensayo software, sin normativa real'}
        self.path.write_text(json.dumps(self.data), encoding='utf-8')

    def test_recuperacion_cita_y_abstencion(self):
        result = recuperar(self.path, 'Cómo se calcula la deriva')
        self.assertFalse(result['abstencion'])
        self.assertTrue(result['datos_sinteticos'])
        self.assertEqual(result['fragmentos'][0]['id'], 'F1')
        self.assertTrue(verificar_citas(self.path,[{'fragmento_id':'F1','texto':self.data['fragmentos'][0]['texto']}],result['huella_corpus']))
        self.assertTrue(recuperar(self.path, 'capacidad geotécnica')['abstencion'])

    def test_fuente_y_aprobacion_alteradas(self):
        self.source.write_bytes(b'alterada')
        with self.assertRaises(ValueError): cargar_corpus(self.path)

    def test_corpus_cambiado_invalida_aprobacion(self):
        data = copy.deepcopy(self.data)
        data['fragmentos'][0]['texto'] = 'Otra conclusión'
        self.path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ValueError): cargar_corpus(self.path)

    def test_cita_inventada_y_version_distinta(self):
        for citation, fingerprint in (({'fragmento_id':'NO','texto':'x'},huella_corpus(self.data)),
                                      ({'fragmento_id':'F1','texto':'alterado'},huella_corpus(self.data)),
                                      ({'fragmento_id':'F1','texto':self.data['fragmentos'][0]['texto']},'0'*64)):
            with self.subTest(citation=citation), self.assertRaises(ValueError):
                verificar_citas(self.path,[citation],fingerprint)

    def test_referencias_duplicadas_y_rutas(self):
        for change in ('ruta', 'documento', 'pagina', 'duplicado'):
            original = copy.deepcopy(self.data)
            if change == 'ruta': self.data['documentos'][0]['archivo']='../fuera.txt'
            if change == 'documento': self.data['fragmentos'][0]['documento']='NO'
            if change == 'pagina': self.data['fragmentos'][0]['pagina']=True
            if change == 'duplicado': self.data['fragmentos'].append(copy.deepcopy(self.data['fragmentos'][0]))
            self.write()
            with self.subTest(change=change), self.assertRaises(ValueError): cargar_corpus(self.path)
            self.data = original
