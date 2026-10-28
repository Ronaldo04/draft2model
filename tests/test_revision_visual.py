"""Pruebas de revisión sobre originales sintéticos y parser HTTP con transporte en memoria."""
import hashlib
import http.client
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace

import pymupdf
from PIL import Image

from draft2model import gestion_extraccion as g
from draft2model.ingreso import registrar_expediente
from draft2model.revision_documental import revisar_expediente
from draft2model.revision_visual import ErrorRevision, RevisionLocal, ManejadorRevision


class CasoVisual(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.work = Path(tmp.name)
        self.root = self.work / 'private'
        source = self.work / 'synthetic.pdf'
        with pymupdf.open() as doc:
            for rotation in (0, 90, 180, 270):
                page = doc.new_page(width=400, height=300)
                page.draw_rect((40, 30, 120, 90), color=(1, 0, 0), fill=(1, 0, 0))
                page.set_rotation(rotation)
            doc.save(source)
        self.manifest = registrar_expediente('demo', [source], self.root, uso_autorizado=True,
                                             provisional_fuera_alcance=True)
        revisar_expediente(self.manifest, max_lado=256)
        data = json.loads(self.manifest.read_text(encoding='utf-8'))
        self.extraction = {
            'contrato': 'draft2model.extraccion_preliminar', 'version_contrato': '0.1.0',
            'caso': 'demo', 'procedencia': {'tipo': 'expediente', 'descripcion': 'PDF sintético de pruebas.'},
            'alcance': data['alcance'], 'sistema_coordenadas': 'pagina_visible_normalizada',
            'candidatos': [{'id': 'C1', 'tipo': 'cota', 'valor_propuesto': 2.6, 'unidad': 'm',
                            'metodo': {'tipo': 'manual'}, 'evidencia': [
                                {'archivo_id': 'L0001', 'pagina': 1, 'original_sha256': data['archivos'][0]['sha256'],
                                 'bbox_normalizada': [0.1, 0.1, 0.3, 0.3]}]}]}
        self.app = RevisionLocal(self.root)
        self.base = {'caso': 'demo', 'expediente_sha256': hashlib.sha256(self.manifest.read_bytes()).hexdigest()}

    def imported(self):
        return self.app.actuar('importar', {**self.base, 'extraccion_json': json.dumps(self.extraction)})['id']

    def correction(self, version):
        record = self.app.version('demo', version)
        return {**self.base, 'version': version, 'huella': record['huella'], 'candidato': 'C1',
                'estado': 'revisado', 'valor_revisado': 2.65, 'unidad_revisada': 'm',
                'motivo': 'Lectura sintética contrastada.', 'fecha': '2026-10-15',
                'revisor_declarado': 'Pruebas sintéticas'}


class RevisionVisualTests(CasoVisual):
    def test_consultar_sin_inventar_lecturas(self):
        docs = self.app.documentos('demo')
        self.assertEqual(docs['versiones'], [])
        self.assertEqual(docs['alcance']['estado'], 'fuera_mvp_declarado')
        self.assertEqual(docs['documentos'][0]['paginas'], 4)
        self.assertEqual(self.app.casos()[0]['id'], 'demo')

    def test_importar_corregir_exportar_sin_sobrescribir(self):
        version = self.imported()
        before = (self.manifest.parent / 'extracciones' / version / 'extraccion.json').read_bytes()
        corrected = self.app.actuar('corregir', self.correction(version))['id']
        record = self.app.version('demo', corrected)
        self.assertEqual(record['datos']['candidatos'][0]['revision']['historial'][-1]['valor_revisado'], 2.65)
        self.assertEqual(record['metadatos']['padre']['id'], version)
        self.assertIsNone(record['metadatos']['aprobacion_ingenieria'])
        exported = self.app.actuar('exportar', {**self.base, 'version': corrected, 'huella': record['huella']})
        export = json.loads((self.manifest.parent / exported['ruta_relativa']).read_text(encoding='utf-8'))
        self.assertEqual(export['alcance']['estado'], 'fuera_mvp_declarado')
        self.assertIsNone(export['aprobacion_ingenieria'])
        self.assertEqual((self.manifest.parent / 'extracciones' / version / 'extraccion.json').read_bytes(), before)

    def test_rechazo_y_pendiente_no_se_exportan(self):
        original = self.imported()
        for state in ('rechazado', 'pendiente'):
            body = self.correction(original)
            body.update(estado=state)
            body.pop('valor_revisado'); body.pop('unidad_revisada')
            version = self.app.actuar('corregir', body)['id']
            record = self.app.version('demo', version)
            self.assertEqual(record['datos']['candidatos'][0]['revision']['estado'], state)
            result = g.exportar_version(self.root, 'demo', version)
            self.assertEqual(len(result.datos['candidatos']), 0)

    def test_huella_cliente_obsoleta_no_guarda(self):
        version = self.imported()
        body = self.correction(version)
        body['huella'] = '0' * 64
        with self.assertRaises(ErrorRevision):
            self.app.actuar('corregir', body)
        self.assertEqual(self.app.documentos('demo')['versiones'], [version])

    def test_original_alterado_bloquea_pagina_y_correccion(self):
        version = self.imported()
        body = self.correction(version)
        (self.manifest.parent / 'originales/lamina-0001.pdf').write_bytes(b'alterado')
        with self.assertRaises(ErrorRevision):
            self.app.pagina('demo', 'L0001', 1, self.base['expediente_sha256'])
        with self.assertRaises(ErrorRevision):
            self.app.actuar('corregir', body)
        self.assertTrue(self.app.documentos('demo')['documentos'][0]['error'])

    def test_expediente_cambiado_no_guarda_ni_renderiza(self):
        version = self.imported()
        body = self.correction(version)
        self.manifest.write_bytes(self.manifest.read_bytes() + b'\n')
        with self.assertRaises(ErrorRevision):
            self.app.actuar('corregir', body)
        with self.assertRaises(ErrorRevision):
            self.app.pagina('demo', 'L0001', 1, self.base['expediente_sha256'])

    def test_json_duplicado_no_importa(self):
        with self.assertRaises(g.ErrorGestion):
            self.app.actuar('importar', {**self.base, 'extraccion_json': '{"caso":"demo","caso":"otro"}'})
        self.assertFalse((self.manifest.parent / 'extracciones').exists())
        self.assertFalse(list(self.manifest.parent.glob('.revision-*')))

    def test_valor_y_unidad_invalidos_no_guardan(self):
        version = self.imported()
        for overrides in ({'valor_revisado': True}, {'unidad_revisada': 'pies'}, {'valor_revisado': '2.6'}):
            body = {**self.correction(version), **overrides}
            with self.assertRaises(g.ErrorEvidencia):
                self.app.actuar('corregir', body)
        self.assertEqual(len(self.app.documentos('demo')['versiones']), 1)

    def test_paginas_rotadas_coinciden_con_pagina_visible(self):
        # Centro del rectángulo rojo tras rotaciones PDF, coordenadas esperadas independientes.
        centers = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
        for page, (x, y) in enumerate(centers, 1):
            raw = self.app.pagina('demo', 'L0001', page, self.base['expediente_sha256'])
            with Image.open(BytesIO(raw)) as image:
                expected_size = (800, 600) if page in (1, 3) else (600, 800)
                self.assertEqual(image.size, expected_size)
                rgb = image.getpixel((round(x * image.width), round(y * image.height)))
                self.assertGreater(rgb[0], 240)
                self.assertLess(rgb[1], 20)

    def test_imagen_exif_se_presenta_en_orientacion_visible(self):
        source = self.work / 'image.jpg'
        image = Image.new('RGB', (90, 50), 'red')
        exif = image.getexif(); exif[274] = 6
        image.save(source, exif=exif)
        manifest = registrar_expediente('imagen', [source], self.root, uso_autorizado=True)
        sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
        with Image.open(BytesIO(self.app.pagina('imagen', 'L0001', 1, sha))) as shown:
            self.assertEqual(shown.size, (50, 90))

    def test_rutas_paginas_y_fuentes_no_autorizadas(self):
        for case in ('../demo', 'C:/Windows', ''):
            with self.assertRaises(g.ErrorGestion):
                self.app.documentos(case)
        for page in (0, -1, 5, True):
            with self.assertRaises(ErrorRevision):
                self.app.pagina('demo', 'L0001', page, self.base['expediente_sha256'])
        data = json.loads(self.manifest.read_text(encoding='utf-8'))
        data['uso_autorizado_declarado'] = False
        self.manifest.write_text(json.dumps(data), encoding='utf-8')
        self.assertEqual(self.app.casos(), [])
        with self.assertRaises(ErrorRevision):
            self.app.documentos('demo')

    def test_version_alterada_no_abre(self):
        version = self.imported()
        path = self.manifest.parent / 'extracciones' / version / 'extraccion.json'
        data = json.loads(path.read_text(encoding='utf-8'))
        data['candidatos'][0]['valor_propuesto'] = 99
        path.write_text(json.dumps(data), encoding='utf-8')
        with self.assertRaises(ErrorRevision):
            self.app.version('demo', version)


class ConexionMemoria:
    """Transporte binario para probar el parser HTTP real sin permisos de sockets."""
    def __init__(self, raw):
        self.input = BytesIO(raw)
        self.output = bytearray()

    def makefile(self, *args, **kwargs):
        return self.input

    def sendall(self, raw):
        self.output.extend(raw)

    def settimeout(self, value):
        pass


class HTTPRevisionTests(CasoVisual):
    def setUp(self):
        super().setUp()
        self.server = SimpleNamespace(revision=self.app, token='token-local-de-prueba',
                                      origen='http://127.0.0.1:8766')

    def request(self, method, path, body=None, headers=None):
        h = {'X-Revision-Session': self.server.token, 'Origin': self.server.origen, 'Host': '127.0.0.1:8766'}
        if headers is not None:
            h.update(headers)
        raw = json.dumps(body).encode() if body is not None else None
        if raw:
            h['Content-Type'] = 'application/json'
            h['Content-Length'] = str(len(raw))
        wire = (method+' '+path+' HTTP/1.0\r\n'+''.join(k+': '+v+'\r\n' for k,v in h.items())+'\r\n').encode()+ (raw or b'')
        conn = ConexionMemoria(wire)
        ManejadorRevision(conn, ('127.0.0.1', 12345), self.server)
        response = http.client.HTTPResponse(ConexionMemoria(bytes(conn.output)))
        response.begin()
        result = response.status, response.read(), dict(response.headers)
        return result

    def test_http_flujo_real(self):
        status, raw, headers = self.request('GET', '/')
        self.assertEqual(status, 200)
        self.assertIn(self.server.token.encode(), raw)
        self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        self.assertEqual(headers['Cache-Control'], 'no-store')
        status, raw, _ = self.request('GET', '/api/casos')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)['casos'][0]['id'], 'demo')
        status, raw, _ = self.request('POST', '/api/importar', {**self.base, 'extraccion_json': json.dumps(self.extraction)})
        self.assertEqual(status, 201, raw)
        version = json.loads(raw)['id']
        status, raw, _ = self.request('POST', '/api/corregir', self.correction(version))
        self.assertEqual(status, 201, raw)
        child = json.loads(raw)['id']
        record = self.app.version('demo', child)
        status, raw, _ = self.request('POST', '/api/exportar', {**self.base, 'version': child, 'huella': record['huella']})
        self.assertEqual(status, 201, raw)

    def test_http_origen_host_token_y_fetch_site_rechazados(self):
        for h in ({'Origin': 'https://example.com'}, {'Host': 'evil.test'},
                  {'X-Revision-Session': 'incorrecto'}, {'X-Revision-Session': 'inválido'}, {'Sec-Fetch-Site': 'cross-site'}):
            status, _, _ = self.request('GET', '/api/casos', headers=h)
            self.assertEqual(status, 403, h)
            status, _, _ = self.request('POST', '/api/importar', self.base, headers=h)
            self.assertEqual(status, 403, h)
        status, _, _ = self.request('POST', '/api/importar', self.base, headers={'Origin': ''})
        self.assertEqual(status, 403)

    def test_http_no_sirve_archivos_arbitrarios(self):
        for path in ('/expediente.json', '/../../.env', '/data/private/demo/expediente.json'):
            self.assertEqual(self.request('GET', path)[0], 404)
        status, raw, _ = self.request('GET', '/api/documentos?caso=..%2Fdemo')
        self.assertEqual(status, 409)
        self.assertNotIn(str(self.root).encode(), raw)

    def test_http_pagina_png_y_parametros_repetidos(self):
        status, raw, headers = self.request('GET', '/api/pagina?caso=demo&archivo=L0001&pagina=2&expediente_sha256='+self.base['expediente_sha256'])
        self.assertEqual(status, 200)
        self.assertEqual(headers['Content-Type'], 'image/png')
        self.assertTrue(raw.startswith(b'\x89PNG'))
        self.assertEqual(self.request('GET', '/api/documentos?caso=demo&caso=otro')[0], 409)


class GeometriaVisualTests(HTTPRevisionTests):
    def geometry(self, completa=False):
        data = json.loads((Path(__file__).resolve().parents[1] / 'examples/geometria_sintetica.json').read_text(encoding='utf-8'))
        data['id'] = 'demo'
        if completa:
            data['muros'][3]['espesor'] = 0.15
            data['faltantes'] = []
        return data

    def geo_import(self):
        status, raw, _ = self.request('POST', '/api/geometria/importar',
            {**self.base, 'geometria_json': json.dumps(self.geometry())})
        self.assertEqual(status, 201, raw)
        return json.loads(raw)['id']

    def geo_body(self, version):
        record = self.app.geometria('demo', version)
        return {**self.base, 'version': version, 'huella': record['huella'],
                'sha256_geometria': record['sha256_geometria'], 'motivo': 'Comprobación sintética.',
                'fecha': '2026-10-16', 'revisor_declarado': 'Prueba sintética'}

    def test_http_geometria_importar_revisar_aprobar(self):
        version = self.geo_import()
        original = (self.manifest.parent / 'geometrias' / version / 'geometria.json').read_bytes()
        status, raw, _ = self.request('GET', '/api/geometrias?caso=demo')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)['versiones'], [version])
        status, raw, _ = self.request('GET', '/api/geometria?caso=demo&version='+version)
        self.assertEqual(status, 200)
        self.assertTrue(json.loads(raw)['comprobacion']['correcta'])
        self.assertIsNone(json.loads(raw)['datos']['revision']['aprobacion'])
        status, raw, _ = self.request('POST', '/api/geometria/revisar',
            {**self.geo_body(version), 'geometria_json': json.dumps(self.geometry(True))})
        self.assertEqual(status, 201, raw)
        child = json.loads(raw)['id']
        record = self.app.geometria('demo', child)
        self.assertEqual(record['datos']['revision']['estado'], 'borrador')
        self.assertIsNone(record['datos']['revision']['aprobacion'])
        status, raw, _ = self.request('POST', '/api/geometria/aprobar',
            {**self.geo_body(child), 'alcance_revision': 'Geometría sintética completa.', 'confirmacion_explicita': True})
        self.assertEqual(status, 201, raw)
        approved = self.app.geometria('demo', json.loads(raw)['id'])
        self.assertEqual(approved['datos']['revision']['estado'], 'aprobado')
        self.assertTrue(approved['comprobacion']['validacion']['datos_sinteticos'])
        self.assertEqual(approved['huella'], record['huella'])
        self.assertEqual(approved['metadatos']['alcance'], self.extraction['alcance'])
        self.assertEqual((self.manifest.parent / 'geometrias' / version / 'geometria.json').read_bytes(), original)
        self.assertEqual(self.app.documentos('demo')['versiones'], [])

    def test_geometria_faltantes_huella_confirmacion_y_campos_rechazados(self):
        version = self.geo_import()
        good = {**self.geo_body(version), 'alcance_revision': 'Geometría sintética.', 'confirmacion_explicita': True}
        for overrides in ({}, {'huella': '0'*64}, {'confirmacion_explicita': False},
                          {'confirmacion_explicita': 'true'}, {'ruta': 'C:/secret'}, {'alcance_revision': ''}):
            status, _, _ = self.request('POST', '/api/geometria/aprobar', {**good, **overrides})
            self.assertEqual(status, 409, overrides)
        self.assertEqual(self.app.geometrias('demo'), [version])
        body = {**self.geo_body(version), 'geometria_json': json.dumps(self.geometry(True))}
        self.assertEqual(self.request('POST', '/api/geometria/revisar', {**body, 'sha256_geometria': '0'*64})[0], 409)
        approved = self.geometry(True); approved['revision']['estado'] = 'aprobado'
        self.assertEqual(self.request('POST', '/api/geometria/revisar', {**body, 'geometria_json': json.dumps(approved)})[0], 409)

    def test_geometria_evidencia_alterada_bloquea_consulta_y_escritura(self):
        version = self.geo_import()
        body = {**self.geo_body(version), 'geometria_json': json.dumps(self.geometry(True))}
        (self.manifest.parent / 'originales/lamina-0001.pdf').write_bytes(b'alterado')
        self.assertEqual(self.request('GET', '/api/geometria?caso=demo&version='+version)[0], 409)
        self.assertEqual(self.request('POST', '/api/geometria/revisar', body)[0], 409)
        self.assertEqual(self.app.geometrias('demo'), [version])

    def test_geometria_importacion_no_acepta_rutas_ni_json_duplicado(self):
        for body in ({**self.base, 'geometria_json': '{"id":"demo","id":"otro"}'},
                     {**self.base, 'geometria_json': '{}', 'ruta': '../geometria.json'}):
            self.assertEqual(self.request('POST', '/api/geometria/importar', body)[0], 409)
        self.assertEqual(self.app.geometrias('demo'), [])


if __name__ == '__main__':
    unittest.main()
