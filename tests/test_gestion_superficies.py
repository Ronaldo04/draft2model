"""Aprobaciones declaradas reales en disco0.2; no dobles de gestión ni ETABS."""
import copy
import unittest
from pathlib import Path
from draft2model import gestion_geometria as g
from draft2model import gestion_configuracion as cfg
from draft2model import modelo_estructural as model
from draft2model import operaciones_etabs as ops
from tests import test_gestion_geometria as fixture
from tests import test_modelo_superficies as datos
from tests import test_operaciones_superficies as transporte


class GestionSuperficiesTests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.CasoGeometria(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.raiz=self.f.raiz
        self.geo=g.importar_geometria(self.raiz,fixture.CASO,self.f.escribir(datos.geometria_superficies(aprobar=False)))

    def aprobar_geo(self):
        return self.f.aprobar(self.geo.identificador,self.geo.comprobacion.huella_contenido)

    def importar_cfg(self,geo):
        data=datos.configuracion_superficies()
        data['revision']={'estado':'borrador','aprobacion':None}
        data['masa']['gravedad_m_s2']=transporte.G_PRUEBA
        data['geometria_origen']={'version_id':geo.identificador,'sha256_geometria':geo.comprobacion.sha256_geometria,
                                 'huella_contenido':geo.comprobacion.huella_contenido}
        path=self.f.escribir(data,'config02.json')
        return cfg.importar(self.raiz,fixture.CASO,path)

    def aprobar_cfg(self,data,huella=None):
        return cfg.aprobar(self.raiz,fixture.CASO,data['id'],
            huella_esperada=huella or data['metadatos']['huella_configuracion'],
            revisor='Revisor sintético declarado',fecha='2026-10-19',motivo='Prueba de flujo de software',
            alcance='Configuración sintética; no ingeniería ni permiso ETABS')

    def test_aprobacion_geometrica_no_habilita_adaptador_y_preserva_padre(self):
        before=fixture.instantanea(self.geo.ruta)
        approved=self.aprobar_geo()
        self.assertEqual(fixture.instantanea(self.geo.ruta),before)
        consulted=g.consultar_version(self.raiz,fixture.CASO,approved.identificador)
        self.assertTrue(consulted.comprobacion.correcta,consulted.comprobacion.problemas)
        self.assertEqual(consulted.geometria['revision']['estado'],'aprobado')
        self.assertFalse(consulted.comprobacion.validacion['disponible_para_modelado'])
        self.assertEqual(consulted.metadatos['padre']['id'],self.geo.identificador)

    def test_config_aprobada_permite_plan_desarrollo_pero_no_ejecucion(self):
        source=self.importar_cfg(self.aprobar_geo()); before=source['configuracion']
        approved=self.aprobar_cfg(source)
        self.assertEqual(cfg.consultar(self.raiz,fixture.CASO,source['id'])['configuracion'],before)
        check=approved['comprobacion']
        self.assertTrue(check['aprobacion_configuracion_vigente'])
        self.assertTrue(check['geometria_aprobada_por_huella'])
        self.assertTrue(check['apto_para_plan_desarrollo'])
        self.assertFalse(check['apto_para_adaptador'])
        plan=ops.generar_plan_superficies(self.raiz,approved['configuracion'],
            destino_guardado=str(self.f.trabajo/'nuevo.edb'),tipo_shell_losa='ShellThin',gravedad_programa_m_s2=transporte.G_PRUEBA)
        self.assertEqual(ops.validar_plan_superficies(plan.datos),[])
        self.assertTrue(ops.validar_plan(plan.datos))
        self.assertFalse(plan.datos['ejecutable'])

    def test_sin_aprobacion_geometrica_o_huella_distinta_no_publica_aprobacion(self):
        source=self.importar_cfg(self.geo)
        with self.assertRaises(ValueError): self.aprobar_cfg(source)
        source=self.importar_cfg(self.aprobar_geo())
        with self.assertRaises(ValueError): self.aprobar_cfg(source,'0'*64)

    def test_geometria_alterada_invalida_configuracion_aprobada(self):
        geo=self.aprobar_geo(); approved=self.aprobar_cfg(self.importar_cfg(geo))
        path=geo.ruta/g.ARCHIVO_GEOMETRIA; raw=path.read_bytes()
        changed=copy.deepcopy(g.consultar_version(self.raiz,fixture.CASO,geo.identificador).geometria)
        changed['vertices'][0]['x']+=.1
        self.f.escribir(changed,'alterada.json'); path.write_bytes((self.f.trabajo/'alterada.json').read_bytes())
        try:
            with self.assertRaises(ValueError): cfg.consultar(self.raiz,fixture.CASO,approved['id'])
        finally: path.write_bytes(raw)
        self.assertTrue(cfg.consultar(self.raiz,fixture.CASO,approved['id'])['comprobacion']['apto_para_plan_desarrollo'])
