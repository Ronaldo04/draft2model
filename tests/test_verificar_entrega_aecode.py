"""Integridad de la entrega completa; fixtures de archivo, sin ETABS ni red."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from scripts.verificar_entrega_aecode import verificar


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value), encoding='utf-8')


def archive(path, files):
    with zipfile.ZipFile(path, 'w') as z:
        for name, raw in files.items():
            z.writestr(name, raw)
    return {name: {'sha256': sha(raw), 'bytes': len(raw)} for name, raw in files.items()}


class EntregaCompleta(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / 'fuentes'
        self.extra = self.root / 'complemento'
        self.source.mkdir()
        self.extra.mkdir()
        inv = archive(self.source / 'Draft2Model.zip', {'README.md': b'fuente de prueba'})
        hashes = {name: item['sha256'] for name, item in inv.items()}
        self.fp = sha(json.dumps(hashes, sort_keys=True, separators=(',', ':')).encode())
        write_json(self.source / 'MANIFIESTO.json', {
            'tipo': 'paquete_fuentes', 'zip': 'Draft2Model.zip', 'archivos': hashes,
            'huella_fuentes': self.fp, 'zip_sha256': sha((self.source / 'Draft2Model.zip').read_bytes())})
        case_zip = self.root / 'Caso.zip'
        inv = archive(case_zip, {'caso1/original.pdf': b'original de prueba', 'LEEME_ANEXO.txt': b'archivo',
                               'caso1/analisis_etabs/analisis1/analizado.EDB': b'EDB de prueba'})
        case = {'contrato': 'draft2model.anexo_archivado', 'archivo': 'Caso.zip', 'caso': 'caso1',
                'sha256_zip': sha(case_zip.read_bytes()), 'archivos': inv}
        self.files = {'caso_archivado/Caso.zip': case_zip.read_bytes(),
                      'caso_archivado/MANIFIESTO.json': json.dumps(case).encode(),
                      'resultados/informe/informe.json': json.dumps({'caso_id': 'caso1',
                          'evidencia_analisis': {'caso_id': 'caso1',
                              'resultado': {'id': 'resultado1', 'sha256_edb_leido': sha(b'EDB de prueba')},
                              'analisis': {'corrida_id': 'analisis1', 'sha256_edb_analizado': sha(b'EDB de prueba')},
                              'modelo': {'modelo_id': 'modelo1'}}}).encode(),
                      'resultados/informe/informe.html': b'<html>informe</html>',
                      'resultados/informe/informe.pdf': b'%PDF-prueba',
                      'resultados/panel.html': b'<html>panel</html>'}
        self.publish_extra()

    def publish_extra(self):
        inv = archive(self.extra / 'Complemento.zip', self.files)
        write_json(self.extra / 'MANIFIESTO_COMPLEMENTO.json', {
            'contrato': 'draft2model.complemento_archivado', 'archivo': 'Complemento.zip',
            'ids_declarados': {'caso': 'caso1', 'resultado': 'resultado1',
                              'analisis': 'analisis1', 'modelo': 'modelo1'}, 'archivos': inv,
            'sha256_zip': sha((self.extra / 'Complemento.zip').read_bytes())})

    def test_conjunto_integro_sin_afirmar_aceptacion(self):
        result = verificar(self.source, self.extra, self.fp)
        self.assertEqual(result['caso'], 'caso1')
        self.assertEqual(result['estado'], 'integridad_verificada_no_aceptacion_funcional')
        self.assertFalse(result['aprueba_ingenieria'])

    def test_fuentes_de_otra_version(self):
        with self.assertRaisesRegex(ValueError, 'Huella'):
            verificar(self.source, self.extra, '0' * 64)

    def test_zip_alterado(self):
        with (self.extra / 'Complemento.zip').open('ab') as f:
            f.write(b'alteracion')
        with self.assertRaisesRegex(ValueError, 'Hash del ZIP'):
            verificar(self.source, self.extra, self.fp)

    def test_informe_otro_caso_aunque_hashes_sean_coherentes(self):
        self.files['resultados/informe/informe.json'] = b'{"caso_id":"otro"}'
        self.publish_extra()
        with self.assertRaisesRegex(ValueError, 'Informe de otro'):
            verificar(self.source, self.extra, self.fp)

    def test_salida_omitida_aunque_inventario_sea_coherente(self):
        del self.files['resultados/panel.html']
        self.publish_extra()
        with self.assertRaisesRegex(ValueError, 'salida obligatoria'):
            verificar(self.source, self.extra, self.fp)

    def test_ruta_no_segura_aunque_hashes_sean_coherentes(self):
        self.files['../fuera.txt'] = b'no extraer'
        self.publish_extra()
        with self.assertRaisesRegex(ValueError, 'Ruta no'):
            verificar(self.source, self.extra, self.fp)

    def test_paquete_con_error_registrado(self):
        write_json(self.source / 'ERROR_EMPAQUETADO.json', {'estado': 'fallido'})
        with self.assertRaisesRegex(ValueError, 'fallo registrado'):
            verificar(self.source, self.extra, self.fp)

    def test_resultado_distinto_del_mismo_caso(self):
        report = json.loads(self.files['resultados/informe/informe.json'])
        report['evidencia_analisis']['resultado']['id'] = 'resultado2'
        self.files['resultados/informe/informe.json'] = json.dumps(report).encode()
        self.publish_extra()
        with self.assertRaisesRegex(ValueError, 'versiones distintas'):
            verificar(self.source, self.extra, self.fp)

    def test_edb_del_informe_distinto_del_archivado(self):
        report = json.loads(self.files['resultados/informe/informe.json'])
        report['evidencia_analisis']['analisis']['sha256_edb_analizado'] = '0' * 64
        self.files['resultados/informe/informe.json'] = json.dumps(report).encode()
        self.publish_extra()
        with self.assertRaisesRegex(ValueError, 'EDB archivado distinto'):
            verificar(self.source, self.extra, self.fp)


if __name__ == '__main__':
    unittest.main()
