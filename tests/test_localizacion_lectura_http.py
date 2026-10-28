import hashlib
import json
from types import SimpleNamespace
from urllib.parse import urlencode

import pymupdf
from draft2model.ingreso import registrar_expediente
from draft2model.revision_documental import revisar_expediente
from tests import test_revision_visual as visual


class LocalizacionHTTPTests(visual.CasoVisual):
    request = visual.HTTPRevisionTests.request

    def setUp(self):
        super().setUp()
        source = self.work / 'literal.pdf'
        with pymupdf.open() as doc:
            page = doc.new_page()
            page.insert_text((50, 50), 'C-1')
            page.insert_text((150, 150), 'C-1')
            doc.save(source)
        self.manifest = registrar_expediente('busqueda', [source], self.root, uso_autorizado=True,
                                             provisional_fuera_alcance=True)
        revisar_expediente(self.manifest, max_lado=256)
        manifest = json.loads(self.manifest.read_text(encoding='utf-8'))
        self.extraction['caso'] = 'busqueda'
        c = self.extraction['candidatos'][0]
        c.update(tipo='elemento', valor_propuesto='C-1', unidad='no_aplica', texto_fuente='C-1')
        c['evidencia'][0]['original_sha256'] = manifest['archivos'][0]['sha256']
        self.base = {'caso': 'busqueda', 'expediente_sha256': hashlib.sha256(self.manifest.read_bytes()).hexdigest()}
        self.server = SimpleNamespace(revision=self.app, token='token-local-de-prueba',
                                      origen='http://127.0.0.1:8766')

    def query(self, **changes):
        version = self.imported()
        record = self.app.version('busqueda', version)
        q = {**self.base, 'version': version, 'huella': record['huella'], 'candidato': 'C1', **changes}
        return '/api/localizar-lectura?' + urlencode(q), version

    def test_http_proposes_all_regions_without_changing_version(self):
        url, version = self.query()
        path = self.manifest.parent / 'extracciones' / version / 'extraccion.json'
        before = path.read_bytes()
        status, raw, _ = self.request('GET', url)
        self.assertEqual(status, 200, raw)
        data = json.loads(raw)
        self.assertFalse(data['modifica_datos'])
        self.assertEqual(data['fuentes'][0]['estado'], 'ambigua')
        self.assertEqual(len(data['fuentes'][0]['regiones']), 2)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.app.documentos('busqueda')['versiones'], [version])

    def test_legacy_without_literal_abstains(self):
        del self.extraction['candidatos'][0]['texto_fuente']
        url, _ = self.query()
        status, raw, _ = self.request('GET', url)
        self.assertEqual(status, 200, raw)
        self.assertEqual(json.loads(raw)['estado'], 'sin_texto_literal')
        self.assertEqual(json.loads(raw)['fuentes'], [])

    def test_stale_hash_and_unknown_candidate_rejected(self):
        for change in ({'huella': '0'*64}, {'expediente_sha256': '0'*64}, {'candidato': 'OTRO'}):
            url, _ = self.query(**change)
            self.assertEqual(self.request('GET', url)[0], 409)

    def test_extra_and_duplicate_params_rejected(self):
        url, _ = self.query()
        for suffix in ('&archivo=C:/otro.pdf', '&candidato=C1'):
            self.assertEqual(self.request('GET', url + suffix)[0], 409)

    def test_original_tampering_rejected(self):
        url, _ = self.query()
        (self.manifest.parent / 'originales/lamina-0001.pdf').write_bytes(b'alterado')
        self.assertEqual(self.request('GET', url)[0], 409)

    def test_same_origin_session_required(self):
        url, _ = self.query()
        self.assertEqual(self.request('GET', url, headers={'X-Revision-Session': 'incorrecto'})[0], 403)
