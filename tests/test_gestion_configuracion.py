import copy
import json
import unittest
from tests import test_modelo_estructural as fixture
from draft2model import gestion_configuracion as g


class ConfiguracionVersionadaTests(unittest.TestCase):
    def setUp(self):
        self.base=fixture.ModeloTests();self.base.setUp();self.addCleanup(self.base.doCleanups)
        self.raiz,self.caso=self.base.raiz,self.base.data['caso']
        self.entrada=self.base.escribir(self.base.data,'config-borrador.json')
        self.actor={'revisor':'Prueba SINTETICA','fecha':'2026-10-17','motivo':'Ensayo de software'}

    def test_versiones_aprobacion_y_revision_sin_herencia(self):
        imported=g.importar(self.raiz,self.caso,self.entrada)
        original=(imported['ruta']/'configuracion.json').read_bytes()
        self.assertFalse(imported['comprobacion']['apto_para_adaptador'])
        approved=g.aprobar(self.raiz,self.caso,imported['id'],huella_esperada=fixture.m.huella_configuracion(self.base.data),alcance='Ensayo configuración',**self.actor)
        self.assertTrue(approved['comprobacion']['apto_para_adaptador'])
        proposal=copy.deepcopy(approved['configuracion']);proposal['revision']={'estado':'borrador','aprobacion':None};proposal['materiales'][0]['E_kN_m2']*=1.2
        revised=g.revisar(self.raiz,self.caso,approved['id'],proposal,**self.actor)
        self.assertFalse(revised['comprobacion']['apto_para_adaptador'])
        self.assertEqual(revised['cadena'],[revised['id'],approved['id'],imported['id']])
        self.assertEqual(original,(imported['ruta']/'configuracion.json').read_bytes())
        self.assertTrue(g.consultar(self.raiz,self.caso,approved['id'])['comprobacion']['apto_para_adaptador'])

    def test_aprobacion_importada_huella_distinta_y_faltantes_rechazados(self):
        with self.assertRaises(ValueError):g.importar(self.raiz,self.caso,self.base.escribir(self.base.aprobar_config()))
        imported=g.importar(self.raiz,self.caso,self.entrada)
        with self.assertRaises(ValueError):g.aprobar(self.raiz,self.caso,imported['id'],huella_esperada='0'*64,alcance='Prueba',**self.actor)
        proposal=copy.deepcopy(self.base.data);proposal['materiales'][0]['E_kN_m2']=None
        proposal['faltantes']=[{'ruta':'$.materiales.MAT1.E_kN_m2','motivo':'Pendiente','fuente':'F-SINTETICA'}]
        revision=g.revisar(self.raiz,self.caso,imported['id'],proposal,**self.actor)
        with self.assertRaises(ValueError):g.aprobar(self.raiz,self.caso,revision['id'],huella_esperada=fixture.m.huella_configuracion(proposal),alcance='Prueba',**self.actor)

    def test_metadatos_y_padres_alterados(self):
        imported=g.importar(self.raiz,self.caso,self.entrada)
        revision=g.revisar(self.raiz,self.caso,imported['id'],self.base.data,**self.actor)
        source=imported['ruta']/'version.json';envelope=json.loads(source.read_bytes())
        envelope['contenido']['registro']={'falso':True}
        source.write_text(json.dumps(envelope),encoding='utf-8')
        for version in (imported['id'],revision['id']):
            with self.subTest(version=version),self.assertRaises(ValueError):g.consultar(self.raiz,self.caso,version)

    def test_evidencia_cambiada_invalida_configuracion(self):
        imported=g.importar(self.raiz,self.caso,self.entrada)
        self.base.original.write_bytes(b'alterado')
        with self.assertRaises(ValueError):g.consultar(self.raiz,self.caso,imported['id'])

    def test_conservar_naturaleza_y_no_heredar_aprobaciones(self):
        imported=g.importar(self.raiz,self.caso,self.entrada)
        for field,value in (('id','otra-config'),('datos_sinteticos',False),('revision',{'estado':'aprobado','aprobacion':self.base.aprobar_config()['revision']['aprobacion']})):
            proposal=copy.deepcopy(self.base.data);proposal[field]=value
            with self.subTest(field=field),self.assertRaises(ValueError):g.revisar(self.raiz,self.caso,imported['id'],proposal,**self.actor)
