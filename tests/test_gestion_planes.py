"""Integridad del derivado y su versión fuente; solo expedientes sintéticos."""
import json
import unittest
from tests.test_gestion_geometria import CasoGeometria
from draft2model import gestion_planes as p
from draft2model import gestion_geometria as g


class PlanesTests(CasoGeometria):
    def test_generacion_repetida_inmutable_y_trazable(self):
        source = self.importar()
        before = (source.ruta / 'geometria.json').read_bytes()
        plan = p.generar_plan_version(self.raiz, self.caso_dir.name, source.identificador)
        otro = p.generar_plan_version(self.raiz, self.caso_dir.name, source.identificador)
        self.assertNotEqual(plan, otro)
        self.assertEqual((plan / 'plan.json').read_bytes(), (otro / 'plan.json').read_bytes())
        self.assertEqual(before, (source.ruta / 'geometria.json').read_bytes())
        result = p.comprobar_plan(self.raiz, self.caso_dir.name, plan.name)
        self.assertTrue(result['correcta'])
        data = json.loads((plan / 'plan.json').read_bytes())
        self.assertEqual(data['version_geometria']['version_id'], source.identificador)
        self.assertFalse(data['ejecutable_en_etabs'])
        self.assertIsNone(data['aprobacion_plan'])
        self.assertTrue(data['omisiones'])

    def test_alteracion_plan_aun_rehaciendo_hash(self):
        import hashlib
        source = self.importar()
        folder = p.generar_plan_version(self.raiz, self.caso_dir.name, source.identificador)
        data = json.loads((folder / 'plan.json').read_bytes())
        data['ejecutable_en_etabs'] = True
        raw = json.dumps(data).encode()
        (folder / 'plan.json').write_bytes(raw)
        meta = json.loads((folder / 'version.json').read_bytes())
        meta['sha256_plan'] = hashlib.sha256(raw).hexdigest()
        (folder / 'version.json').write_text(json.dumps(meta), encoding='utf-8')
        with self.assertRaises(g.ErrorEvidencia):
            p.comprobar_plan(self.raiz, self.caso_dir.name, folder.name)

    def test_origen_alterado_impide_consulta_y_nuevo_plan(self):
        source = self.importar()
        folder = p.generar_plan_version(self.raiz, self.caso_dir.name, source.identificador)
        self.original.write_bytes(b'alterado')
        with self.assertRaises(g.ErrorEvidencia):
            p.comprobar_plan(self.raiz, self.caso_dir.name, folder.name)
        with self.assertRaises(g.ErrorEvidencia):
            p.generar_plan_version(self.raiz, self.caso_dir.name, source.identificador)

    def test_revision_no_reescribe_plan_anterior(self):
        source = self.importar()
        folder = p.generar_plan_version(self.raiz, self.caso_dir.name, source.identificador)
        before = (folder / 'plan.json').read_bytes()
        revision = self.revisar(source.identificador)
        nuevo = p.generar_plan_version(self.raiz, self.caso_dir.name, revision.identificador)
        self.assertTrue(p.comprobar_plan(self.raiz, self.caso_dir.name, folder.name)['correcta'])
        self.assertEqual(before, (folder / 'plan.json').read_bytes())
        self.assertEqual(json.loads((nuevo / 'plan.json').read_bytes())['omisiones'], [])


if __name__ == '__main__':
    unittest.main()
