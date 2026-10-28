"""Contornos sintéticos en página con anclas declaradas; sin ingeniería ni ETABS."""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from draft2model import gestion_geometria as geo
from draft2model.revision_superposicion import ErrorSuperposicion, aplicar
from tests import test_geometria_superficies as formas
from tests import test_revision_superposicion as legado


class SuperposicionSuperficiesTests(unittest.TestCase):
    def setUp(self):
        self.f = legado.SuperposicionTests('test_transformacion_conocida_proyeccion_e_historial')
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()
        self.datos = formas.ejemplo([(0,0,2.6), (4,0,2.6), (4,3,2.6), (0,3,2.6)])
        self.datos['id'] = legado.CASO
        self.ident = self.importar(self.datos)

    def importar(self, data):
        path = self.f.root/'superficies.json'
        path.write_text(json.dumps(data), encoding='utf-8')
        return geo.importar_geometria(self.f.app.raiz, legado.CASO, path).identificador

    def cuerpo(self, ident=None):
        ident = ident or self.ident
        actual = self.f.app.geometria(legado.CASO, ident)
        return {'caso': legado.CASO, 'expediente_sha256': self.f.fp, 'geometria': ident,
                'huella_geometria': actual['huella'], 'sha256_geometria': actual['sha256_geometria'],
                'archivo': self.f.archivo, 'pagina': 1, 'version_contrato': '0.2.0',
                'plano': {'tipo': 'horizontal', 'cota_m': 2.6}, 'superficies': ['S1'],
                'anclas': [{'vertice': f'V{i}', 'punto': list(aplicar(legado.matriz(), *p[:2]))}
                           for i, p in enumerate(((0,0), (4,0), (4,3)))],
                'revisor_declarado': 'Operador sintético declarado', 'fecha': '2026-10-19',
                'motivo': 'Anclas sintéticas de prueba; no detección.', 'confirmacion_explicita': True}

    def test_contorno_guardado_consultado_y_proyectado_con_area_procedencia(self):
        esquema = self.f.service.esquema(legado.CASO, self.ident, expediente_sha256=self.f.fp)
        self.assertEqual(esquema['niveles'], [])
        self.assertEqual(esquema['nodos'], [])
        self.assertEqual(esquema['version_geometria'], '0.2.0')
        self.assertEqual(esquema['superficies'][0]['area_m2'], 12)
        item = self.f.service.crear(self.cuerpo())
        consulta = self.f.service.consultar(legado.CASO, item['id'], expediente_sha256=self.f.fp)
        self.assertEqual(item, consulta)
        self.assertIsNone(item['nivel'])
        self.assertEqual(item['plano'], {'tipo':'horizontal', 'cota_m':2.6})
        self.assertEqual(item['transformacion']['de'], 'plano_horizontal_xy_m')
        superficie = item['superficies'][0]
        self.assertEqual(superficie['area_m2'], 12)
        self.assertEqual(superficie['procedencia'], self.datos['superficies'][0]['procedencia'])
        self.assertEqual(superficie['vertices_m'][0], [0,0,2.6])
        for punto, origen in zip(superficie['proyeccion'], superficie['vertices_m']):
            u, v = aplicar(legado.matriz(), *origen[:2])
            self.assertAlmostEqual(punto['u'], u)
            self.assertAlmostEqual(punto['v'], v)
            self.assertIn('vertice', punto)
            self.assertNotIn('nodo', punto)
        self.assertFalse(item['aprueba_geometria'] or item['aprueba_ingenieria'] or item['disponible_para_modelado'])
        registro = self.f.service.listar(legado.CASO, expediente_sha256=self.f.fp)['versiones'][0]
        self.assertEqual(registro['plano'], item['plano'])
        self.assertEqual(registro['superficies'], ['S1'])

    def test_unidades_fisicas_metros_sin_story_ni_ancla_legacy(self):
        data = copy.deepcopy(self.datos)
        data['unidad_longitud'] = 'cm'
        for vertice in data['vertices']:
            for clave in ('x','y','z'):
                vertice[clave] *= 100
        item = self.f.service.crear(self.cuerpo(self.importar(data)))
        self.assertEqual(item['geometria']['unidad_longitud'], 'cm')
        self.assertEqual(item['superficies'][0]['area_m2'], 12)
        self.assertEqual(item['superficies'][0]['vertices_m'][2], [4,3,2.6])
        cuerpo = self.cuerpo()
        cuerpo['anclas'][0] = {'nodo': 'V0', 'punto': [.3,.6]}
        with self.assertRaises(ErrorSuperposicion):
            self.f.service.crear(cuerpo)

    def test_cotas_planos_selecciones_y_anclas_invalidos(self):
        cambios = [lambda b: b.update(plano={'tipo':'inclinado','cota_m':2.6}),
                   lambda b: b.update(plano={'tipo':'horizontal','cota_m':0}),
                   lambda b: b.update(plano={'tipo':'horizontal','cota_m':True}),
                   lambda b: b.update(plano={'tipo':'horizontal','cota_m':float('nan')}),
                   lambda b: b['plano'].update(nivel='N0'),
                   lambda b: b.update(superficies=[]),
                   lambda b: b.update(superficies=['S1','S1']),
                   lambda b: b.update(superficies=['ausente']),
                   lambda b: b.update(nivel='N0'),
                   lambda b: b.update(version_contrato='99.0.0'),
                   lambda b: b['anclas'][0].update(vertice='A'),
                   lambda b: b['anclas'][0].update(vertice='V1'),
                   lambda b: b['anclas'][0].update(punto=[2,.5])]
        for cambio in cambios:
            cuerpo = self.cuerpo()
            cambio(cuerpo)
            with self.subTest(cambio=cambio), self.assertRaises(ErrorSuperposicion):
                self.f.service.crear(cuerpo)
        data = copy.deepcopy(self.datos)
        for i in (2,3):
            data['vertices'][i]['z'] += 1
        ident = self.importar(data)
        with self.assertRaises(ErrorSuperposicion):
            self.f.service.crear(self.cuerpo(ident))

    def test_fuera_de_pagina_se_conserva_sin_recortar(self):
        b = self.cuerpo()
        b['anclas'] = [{'vertice': v, 'punto': p} for v,p in [('V0',[.6,.9]),('V2',[.9,.6]),('V3',[.2,.3])]]
        item = self.f.service.crear(b)
        self.assertEqual(item['fuera_imagen'][0]['vertice'], 'V1')
        self.assertAlmostEqual(item['fuera_imagen'][0]['u'], 1.3)
        self.assertAlmostEqual(item['fuera_imagen'][0]['v'], 1.2)

    def test_registro_manipulado_no_se_acepta_por_recalcular_hash(self):
        item = self.f.service.crear(self.cuerpo())
        folder = self.f.case/'superposiciones'/item['id']
        original = {n:(folder/n).read_bytes() for n in ('version.json','correspondencia.json')}
        cambios = [lambda r:r.update(plano={'tipo':'horizontal','cota_m':0}),
                   lambda r:r['anclas'][0].update(punto=[.4,.4]),
                   lambda r:r.update(superficies=['ausente']),
                   lambda r:r.update(aprueba_geometria=True),
                   lambda r:r.update(extra=True)]
        for cambio in cambios:
            reg = json.loads(original['correspondencia.json'])
            cambio(reg)
            raw = json.dumps(reg).encode()
            meta = json.loads(original['version.json'])
            meta['sha256_correspondencia'] = hashlib.sha256(raw).hexdigest()
            (folder/'correspondencia.json').write_bytes(raw)
            (folder/'version.json').write_text(json.dumps(meta), encoding='utf-8')
            with self.subTest(cambio=cambio), self.assertRaises(ErrorSuperposicion):
                self.f.service.consultar(legado.CASO, item['id'], expediente_sha256=self.f.fp)
        for nombre, raw in original.items():
            (folder/nombre).write_bytes(raw)
        self.assertTrue(self.f.service.consultar(legado.CASO, item['id'], expediente_sha256=self.f.fp)['vigente'])

    def test_mutacion_geometria_postrender_y_original_invalida(self):
        item = self.f.service.crear(self.cuerpo())
        path = self.f.case/'geometrias'/self.ident/'geometria.json'
        raw = path.read_bytes()
        pagina = self.f.app.pagina

        def mutar(*args, **kwargs):
            valor = pagina(*args, **kwargs)
            path.write_bytes(raw+b' ')
            return valor

        try:
            with patch.object(self.f.app, 'pagina', side_effect=mutar), self.assertRaises(ErrorSuperposicion):
                self.f.service.consultar(legado.CASO, item['id'], expediente_sha256=self.f.fp)
        finally:
            path.write_bytes(raw)
        pdf = next(self.f.case.rglob('*.pdf'))
        pdf.write_bytes(pdf.read_bytes()+b'%cambio')
        with self.assertRaises(ErrorSuperposicion):
            self.f.service.consultar(legado.CASO, item['id'], expediente_sha256=self.f.fp)


if __name__ == '__main__':
    unittest.main()
