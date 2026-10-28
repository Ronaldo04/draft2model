"""Versionado real en disco de configuración0.3; nunca autoriza ETABS."""
import copy
from draft2model import gestion_configuracion as cfg, gestion_geometria as geo, operaciones_etabs as ops
from tests.test_modelo_aberturas import CasoAberturas


class GestionAberturasTests(CasoAberturas):
    def importar(self):
        data=copy.deepcopy(self.data);data['revision']={'estado':'borrador','aprobacion':None}
        return cfg.importar(self.raiz,data['caso'],self.f.escribir(data,'borrador03.json'))

    def aprobar(self,item,huella=None):
        # CasoAberturas.montar usa aprobar(data) para su fixture; no alterar ese protocolo.
        if 'metadatos' not in item:return super().aprobar(item)
        return cfg.aprobar(self.raiz,self.data['caso'],item['id'],
            huella_esperada=huella or item['metadatos']['huella_configuracion'],
            revisor='Prueba',fecha='2026-10-20',motivo='Solo software',alcance='Plan de desarrollo; no ingeniería')

    def test_aprobar_crea_hija_y_permite_plan_no_ejecutable(self):
        parent=self.importar();before=copy.deepcopy(parent)
        approved=self.aprobar(parent)
        self.assertEqual(cfg.consultar(self.raiz,self.data['caso'],parent['id']),before)
        self.assertTrue(approved['comprobacion']['aprobacion_configuracion_vigente'])
        self.assertTrue(approved['comprobacion']['apto_para_plan_desarrollo'])
        self.assertFalse(approved['comprobacion']['apto_para_adaptador'])
        plan=ops.generar_plan_aberturas(self.raiz,approved['configuracion'],destino_guardado=str(self.f.trabajo/'nuevo.edb'),tipo_shell_losa='ShellThin',gravedad_programa_m_s2=9.80665)
        self.assertEqual(ops.validar_plan_aberturas(plan.datos),[]);self.assertFalse(plan.datos['ejecutable'])

    def test_huella_ajena_no_publica_aprobacion(self):
        parent=self.importar()
        with self.assertRaises(ValueError):self.aprobar(parent,'0'*64)
        self.assertEqual(cfg.consultar(self.raiz,self.data['caso'],parent['id'])['configuracion']['revision']['estado'],'borrador')

    def test_cambio_hueco_invalida_hija(self):
        approved=self.aprobar(self.importar());path=self.version.ruta/geo.ARCHIVO_GEOMETRIA
        raw=path.read_bytes()
        try:
            changed=copy.deepcopy(self.geo);changed['vertices'][-1]['y']-=.05
            path.write_bytes(self.f.escribir(changed,'alteracion03.json').read_bytes())
            with self.assertRaises(ValueError):cfg.consultar(self.raiz,self.data['caso'],approved['id'])
        finally:path.write_bytes(raw)
