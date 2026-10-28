"""Integración completa sintética sin red, proveedor IA ni motor ETABS."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pymupdf

from examples.flujo_integrado_sintetico import crear_demo, verificar_demo
from draft2model.gestion_geometria import comprobar_version
from draft2model.gestion_planes import comprobar_plan
from draft2model.informe import exportar_informe, validar_informe
from draft2model.modelo_estructural import comprobar_configuracion, huella_configuracion
from draft2model.orquestacion import RegistroCorridas
from draft2model.resultados_estructurales import cargar_json, huella_resultados


class FlujoIntegradoTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.destination = Path(temp.name) / 'demo-nueva'
        with patch('socket.socket', side_effect=AssertionError('La demo no puede usar red.')):
            self.summary = crear_demo(self.destination)
        self.root = self.destination / 'private'
        self.case = self.root / self.summary['caso']
        self.work = self.case / 'demo'

    def test_recorrido_cifras_citas_huellas_pdf_y_sqlite(self):
        self.assertTrue(verificar_demo(self.destination)['correcta'])
        self.assertEqual(len(self.summary['corridas']), 6)
        registry = RegistroCorridas(self.root)
        for ident in self.summary['corridas'].values():
            record = registry.consultar(ident)
            self.assertEqual(record['estado'], 'completada')
            self.assertTrue(record['vigente'])
            self.assertTrue(record['salidas'])
        geometry_path = self.case / 'geometrias' / self.summary['geometria_aprobada'] / 'geometria.json'
        geometry = cargar_json(geometry_path)
        self.assertEqual(geometry['niveles'][1]['cota'], 2.6)
        self.assertEqual(geometry['nodos'][1]['x'], 4.0)
        self.assertEqual(geometry['muros'][0]['espesor'], 0.15)
        self.assertEqual(geometry['revision']['estado'], 'aprobado')
        self.assertIn('SIMULADO', geometry['revision']['aprobacion']['declarada_por'])
        plan = cargar_json(self.case / 'planes' / self.summary['plan_id'] / 'plan.json')
        self.assertFalse(plan['ejecutable_en_etabs'])
        surfaces = plan['superficies']
        self.assertAlmostEqual(surfaces[0]['area_bruta_m2'], 10.4)
        config = cargar_json(self.work / 'configuracion.json')
        results = cargar_json(self.work / 'resultados_simulados.json')
        report = cargar_json(self.work / 'informe_borrador/informe.json')
        self.assertEqual(results['configuracion']['sha256'], huella_configuracion(config))
        self.assertEqual(results['geometria']['sha256'], hashlib.sha256(geometry_path.read_bytes()).hexdigest())
        self.assertEqual(report['huellas']['resultados'], huella_resultados(results))
        self.assertEqual(report['revision'], {'estado': 'borrador', 'aprobacion': None})
        self.assertEqual(report['motor']['tipo'], 'simulacion')
        self.assertTrue(report['datos_sinteticos'])
        self.assertEqual(report['siete_resultados']['geometria_muros']['numero_muros'], 1)
        self.assertEqual(report['siete_resultados']['periodos'][0]['valor'], 0.5)
        self.assertEqual(report['siete_resultados']['derivas'][0]['valor'], 0.002)
        self.assertEqual(report['siete_resultados']['cortante_basal'][0]['valor'], 100.0)
        self.assertEqual(len(report['fuentes']['citas']), 3)
        validar_informe(report)
        with pymupdf.open(self.work / 'informe_borrador/informe.pdf') as pdf:
            text = '\n'.join(page.get_text() for page in pdf)
            self.assertGreater(len(pdf), 0)
            self.assertIn('SIMUL', text.upper())
            self.assertIn('BORRADOR', text.upper())
        self.assertEqual(self.summary['metricas_software']['ejecuciones_etabs'], 0)
        self.assertEqual(self.summary['metricas_software']['llamadas_ia_reales'], 0)
        self.assertIsNone(self.summary['metricas_software']['ahorro_validado'])
        self.assertGreater(self.summary['metricas_software']['tiempo_hasta_exportacion_s'], 0)

    def test_no_sobrescribe_y_repetir_exige_carpeta_nueva(self):
        report_path = self.work / 'informe_borrador/informe.pdf'
        before = report_path.read_bytes()
        with self.assertRaises(FileExistsError):
            crear_demo(self.destination)
        self.assertEqual(report_path.read_bytes(), before)
        other = self.destination.parent / 'otra-demo'
        summary = crear_demo(other, caso='otro-caso-sintetico')
        self.assertNotEqual(summary['geometria_aprobada'], self.summary['geometria_aprobada'])
        self.assertTrue(verificar_demo(other, caso='otro-caso-sintetico')['correcta'])

    def test_original_alterado_invalida_derivados(self):
        original = self.case / 'originales/lamina-0001.pdf'
        original.write_bytes(original.read_bytes()+b'\nALTERACION SINTETICA')
        with self.assertRaises(ValueError):
            verificar_demo(self.destination)
        self.assertFalse(comprobar_version(self.root, self.summary['caso'], self.summary['geometria_aprobada']).correcta)
        self.assertFalse(comprobar_configuracion(self.root, cargar_json(self.work / 'configuracion.json')).apto_para_adaptador)
        with self.assertRaises(ValueError):
            comprobar_plan(self.root, self.summary['caso'], self.summary['plan_id'])
        registry = RegistroCorridas(self.root)
        self.assertTrue(all(not registry.consultar(ident)['vigente'] for ident in self.summary['corridas'].values()))

    def test_fuente_citada_alterada_bloquea_verificacion_y_exportacion(self):
        source = self.work / 'fuentes/fuente_sintetica.pdf'
        source.write_bytes(source.read_bytes()+b'\nALTERACION SINTETICA')
        with self.assertRaises(ValueError):
            verificar_demo(self.destination)
        report = cargar_json(self.work / 'informe_borrador/informe.json')
        geometry = self.case / 'geometrias' / self.summary['geometria_aprobada'] / 'geometria.json'
        with self.assertRaises(ValueError):
            exportar_informe(report, self.work / 'informe-no-publicable', geometria_archivo=geometry,
                             corpus=self.work / 'fuentes/corpus.json')
        self.assertFalse((self.work / 'informe-no-publicable').exists())
        registry = RegistroCorridas(self.root)
        for name in ('modelo', 'analisis', 'evaluacion', 'informe'):
            self.assertFalse(registry.consultar(self.summary['corridas'][name])['vigente'])


if __name__ == '__main__':
    unittest.main()
