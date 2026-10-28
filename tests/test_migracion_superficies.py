"""Migración explícita local, parentesco y huellas; sin red/motor."""
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import json
from types import SimpleNamespace
import unittest
from draft2model import gestion_geometria as g
from draft2model.__main__ import main
from draft2model.revision_visual import RevisionLocal
from tests import test_gestion_geometria as fixture
from tests import test_revision_visual as http


class MigracionTests(unittest.TestCase):
    request = http.HTTPRevisionTests.request

    def setUp(self):
        self.fixture = fixture.CasoGeometria(); self.fixture.setUp(); self.addCleanup(self.fixture.doCleanups)
        self.raiz = self.fixture.raiz
        self.origen = self.fixture.importar(self.fixture.escribir(self.fixture.completa()))
        self.options = dict(huella_esperada=self.origen.comprobacion.huella_contenido,
                            motivo='Extensión geométrica explícita', fecha='2026-10-19', revisor_declarado='Operador sintético')
        self.app = RevisionLocal(self.raiz)
        self.server = SimpleNamespace(revision=self.app, token='prueba', origen='http://127.0.0.1:8766')

    def test_hija_conserva_padre_y_no_hereda_aprobacion(self):
        parent = self.fixture.aprobar(self.origen.identificador, self.options['huella_esperada'])
        before = fixture.instantanea(parent.ruta)
        child = g.migrar_geometria_superficies(self.raiz, fixture.CASO, parent.identificador, **self.options)
        self.assertEqual(fixture.instantanea(parent.ruta), before)
        data = g.consultar_version(self.raiz, fixture.CASO, child.identificador)
        self.assertTrue(data.comprobacion.correcta)
        self.assertEqual(data.geometria['version_contrato'], '0.2.0')
        self.assertEqual(data.geometria['revision'], {'estado':'borrador','aprobacion':None})
        self.assertEqual(data.metadatos['padre']['id'], parent.identificador)
        self.assertFalse(data.comprobacion.validacion['disponible_para_modelado'])
        with self.assertRaises(ValueError):
            g.migrar_geometria_superficies(self.raiz, fixture.CASO, child.identificador,
                **{**self.options,'huella_esperada': child.comprobacion.huella_contenido})

    def body(self):
        source = self.app.geometria(fixture.CASO, self.origen.identificador)
        return {'caso':fixture.CASO,'version':self.origen.identificador,'huella':source['huella'],
                'sha256_geometria':source['sha256_geometria'],'expediente_sha256':source['expediente_sha256'],
                'motivo':self.options['motivo'],'fecha':self.options['fecha'],
                'revisor_declarado':self.options['revisor_declarado']}

    def test_http_huellas_y_campos_invalidos_no_crean_version(self):
        body = self.body(); initial = self.fixture.versiones()
        for changes in ({'huella':'0'*64},{'sha256_geometria':'0'*64},{'expediente_sha256':'0'*64},{'extra':True}):
            self.assertEqual(self.request('POST','/api/geometria/migrar-superficies',{**body,**changes})[0],409)
            self.assertEqual(self.fixture.versiones(), initial)
        status, raw, _ = self.request('POST','/api/geometria/migrar-superficies',body)
        self.assertEqual(status,201,raw)
        child = g.consultar_version(self.raiz, fixture.CASO, json.loads(raw)['id'])
        self.assertEqual(child.metadatos['padre']['id'], self.origen.identificador)
        self.assertEqual(child.geometria['revision']['estado'],'borrador')

    def test_cli_crea_hija_y_rechaza_huella_ajena(self):
        args = ['migrar-geometria-superficies','--caso',fixture.CASO,'--geometria',self.origen.identificador,
                '--huella-esperada',self.options['huella_esperada'],'--motivo','Migración sintética',
                '--fecha','2026-10-19','--revisor','Operador sintético']
        with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
            self.assertEqual(main(args,raiz=self.raiz),0)
            args[args.index('--huella-esperada')+1] = '0'*64
            self.assertEqual(main(args,raiz=self.raiz),2)
        self.assertEqual(len(self.fixture.versiones()),2)
