"""Proyecciones web de derivados sin rutas privadas ni publicación por datos obsoletos."""
import copy
import json
import unittest
from unittest.mock import patch

from draft2model import revision_preparacion as preparation
from tests import test_revision_preparacion as fixture_preparacion


class PreparacionDerivadosTests(unittest.TestCase):
    def setUp(self):
        fixture=fixture_preparacion.PreparacionWebTests();fixture.setUp();self.addCleanup(fixture.doCleanups)
        self.fixture=fixture;self.app=fixture.app;self.service=fixture.service
        self.caso=fixture.caso;self.fp=fixture.fp;self.base=fixture.base
        self.body={**self.base,'archivo':'L0001','config':{'rotacion_grados':90,'contraste':1.2,
            'perspectiva':{'esquinas_px':[[0,0],[80,0],[80,60],[0,60]],'dimensiones_salida_px':[60,40]}},
            'revisor_declarado':'Operador SINTÉTICO','motivo':'Preparación de prueba de software.'}

    def publicar(self):return self.service.preprocesar(copy.deepcopy(self.body))
    def consultar(self,version):return self.service.preprocesamiento(self.caso,version,expediente_sha256=self.fp)

    def test_proyecciones_imagen_y_paquete_conservan_original_y_no_filtran_rutas(self):
        info=self.service.original_raster(self.caso,'L0001',expediente_sha256=self.fp)
        self.assertEqual(info['exif_original']['dimensiones_original_px'],[80,60])
        original=self.app.raiz/self.caso/'originales/lamina-0001.png';antes=original.read_bytes()
        first=self.publicar();second=self.publicar()
        self.assertEqual(len(first['id']),64);self.assertNotEqual(first['id'],second['id'])
        self.assertEqual(first,self.consultar(first['id']))
        self.assertNotIn('original',first['transformacion'])
        raw=self.service.imagen_preprocesada(self.caso,first['id'],expediente_sha256=self.fp)
        self.assertTrue(raw.startswith(b'\x89PNG'))
        history=self.service.preprocesamientos(self.caso,'L0001',expediente_sha256=self.fp)
        self.assertEqual(len(history['versiones']),2)
        for value in (info,first,history):
            self.assertNotIn(str(self.app.raiz),json.dumps(value))
            self.assertNotIn('imagen_bytes',value);self.assertNotIn('ruta',value)
        crop=self.fixture.crop(preprocesamiento=first['id'])
        self.assertEqual(crop['preprocesamiento_id'],first['id'])
        self.assertEqual(crop['tipo_fuente'],'raster_preprocesado')
        self.assertEqual(crop['bbox_derivado_normalizada'],[.1,.1,.8,.8])
        self.assertNotEqual(crop['bbox_normalizada'],crop['bbox_derivado_normalizada'])
        self.assertEqual(crop['tipo_transformacion'],'homografia_3x3')
        packet=self.fixture.prepare(crop)
        self.assertFalse(packet['transmision_externa'] or packet['aprueba_ingenieria'])
        self.assertEqual(original.read_bytes(),antes)

    def test_campos_exactos_vigencia_ids_y_tipo_original(self):
        for body in ({**self.body,'ruta':'C:/fuera'}, {**self.body,'expediente_sha256':'0'*64},
                     {**self.body,'archivo':'L0002'}, {**self.body,'revisor_declarado':''},
                     {k:v for k,v in self.body.items() if k!='config'}):
            with self.subTest(body=body),self.assertRaises(ValueError):self.service.preprocesar(body)
        for ident in ('../x','f'*32,None,True):
            with self.assertRaises(ValueError):self.consultar(ident)
            with self.assertRaises(ValueError):self.fixture.crop(preprocesamiento=ident)
        with self.assertRaises(ValueError):self.service.original_raster(self.caso,'L0002',expediente_sha256=self.fp)
        with self.assertRaises(ValueError):self.service.preprocesamientos(self.caso,'L0001',expediente_sha256='0'*64)
        # El recorrido anterior conserva su contrato y no exige selector de derivado.
        self.assertEqual(self.fixture.crop()['tipo_fuente'],'raster')

    def test_fuente_y_matriz_alteradas_no_se_exponen_como_recorte_vigente(self):
        version=self.publicar();crop=self.fixture.crop(preprocesamiento=version['id'])
        path=self.app.raiz/self.caso/'recortes'/crop['id']/'recorte.json'
        raw=path.read_bytes();data=json.loads(raw);data['pixel_a_pagina_visible'][0][0]+=1
        path.write_text(json.dumps(data))
        try:
            with self.assertRaises(ValueError):self.service.recorte(self.caso,crop['id'],expediente_sha256=self.fp)
            with self.assertRaises(ValueError):self.service.imagen(self.caso,crop['id'],expediente_sha256=self.fp)
        finally:path.write_bytes(raw)
        data=json.loads(raw);data['tipo_fuente']='raster';path.write_text(json.dumps(data))
        try:
            with self.assertRaises(ValueError):self.service.recorte(self.caso,crop['id'],expediente_sha256=self.fp)
        finally:path.write_bytes(raw)
        config=self.app.raiz/self.caso/'preprocesamientos'/version['id']/'config.json'
        config.write_bytes(config.read_bytes()+b'\n')
        for read in (lambda:self.consultar(version['id']),
                     lambda:self.service.imagen_preprocesada(self.caso,version['id'],expediente_sha256=self.fp),
                     lambda:self.service.preprocesamientos(self.caso,'L0001',expediente_sha256=self.fp),
                     lambda:self.service.recorte(self.caso,crop['id'],expediente_sha256=self.fp)):
            with self.assertRaises(ValueError):read()

    def test_consulta_revalida_expediente_despues_de_leer_bytes(self):
        version=self.publicar();consultar=preparation.derivadas.consultar_preprocesamiento
        original=self.app.raiz/self.caso/'originales/lamina-0001.png'
        def cambiado(*args):
            consulta=consultar(*args);original.write_bytes(b'alterado durante proyeccion');return consulta
        with patch.object(preparation.derivadas,'consultar_preprocesamiento',cambiado),self.assertRaises(ValueError):
            self.service.imagen_preprocesada(self.caso,version['id'],expediente_sha256=self.fp)
