import copy
import json
import unittest
from draft2model.normalizacion_etabs import previsualizar_resultados
from tests import test_normalizacion_etabs as fixtures


class PrevisualizacionTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.NormalizacionTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.fixture.mapping['revision']={'estado':'borrador','aprobacion':None}
        self.write()

    def write(self):self.fixture.map_path.write_text(json.dumps(self.fixture.mapping),encoding='utf-8')

    def preview(self):
        f=self.fixture
        return previsualizar_resultados(f.raiz,f.config_path,f.raw_path,f.map_path)

    def snapshot(self):
        root=self.fixture.base.trabajo
        return {p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}

    def test_borrador_comprobado_sin_publicar_ni_conceder_aprobacion(self):
        before=self.snapshot();preview=self.preview()
        self.assertFalse(preview['publicado'] or preview['aprueba_resultados'])
        self.assertEqual(preview['revision_mapeo'],'borrador')
        self.assertEqual(preview['resultados']['resultados'][2]['valor'],-1)
        self.assertEqual(preview['correspondencias'][2]['factor'],0.001)
        self.assertEqual(self.snapshot(),before)
        with self.assertRaises(ValueError):self.fixture.run_normalizer()
        self.assertEqual(self.snapshot(),before)

    def test_filtros_ambiguos_integridad_y_revision_invalida_rechazados(self):
        original=copy.deepcopy(self.fixture.mapping)
        self.fixture.mapping['selectores'][1]['filtros']={'OutputCase':'EX'};self.write()
        with self.assertRaisesRegex(ValueError,'ambiguo'):self.preview()
        self.fixture.mapping=copy.deepcopy(original)
        self.fixture.mapping['sha256_respuesta']='0'*64;self.write()
        with self.assertRaises(ValueError):self.preview()
        self.fixture.mapping=copy.deepcopy(original)
        self.fixture.mapping['revision']={'estado':'aprobado','aprobacion':None};self.write()
        with self.assertRaises(ValueError):self.preview()
