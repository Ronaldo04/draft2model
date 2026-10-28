"""Config0.3 aprobada declarativamente con versiones reales en disco; sin doble de gestión."""
import copy
import json
import unittest
from draft2model import gestion_geometria as g, modelo_estructural as m
from tests import test_gestion_geometria as disco, test_modelo_superficies as datos


class CasoAberturas(unittest.TestCase):
    def setUp(self):
        self.f = disco.CasoGeometria(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.raiz = self.f.raiz
        self.montar()

    def montar(self, orientacion="horizontal"):
        transform = {"horizontal": lambda x,y:(x,y,2.6), "inclinado": lambda x,y:(x,y,x*.3), "vertical":lambda x,y:(0,x,y*.8)}[orientacion]
        xyz = {v: transform(x,y) for v,(x,y) in dict(VA=(0,0),VB=(4,0),VC=(4,3),VD=(0,3),H1=(1,1),H2=(2,1),H3=(2,2),H4=(1,2)).items()}
        geo = datos.geometria_superficies(vertices=xyz, superficies=[("S1",["VA","VB","VC","VD"],"host sintético")], aprobar=False)
        geo.update(version_contrato="0.3.0", aberturas=[{"id":"HUECO1","superficie":"S1","vertices":["H1","H2","H3","H4"],"procedencia":copy.deepcopy(geo["procedencia"])}])
        imp = g.importar_geometria(self.raiz, disco.CASO, self.f.escribir(geo))
        self.version = self.f.aprobar(imp.identificador, imp.comprobacion.huella_contenido)
        self.geo = g.consultar_version(self.raiz, disco.CASO, self.version.identificador).geometria
        data = datos.configuracion_superficies()
        data.update(version_contrato="0.3.0", frames=[],asignaciones_frames=[],vertices_compartidos=[],diafragmas=[])
        data["puntos"] = [{"id":v,"vertice_geometria":v} for v in xyz]
        data["sin_diafragma"] = [{"punto":v,"motivo":"Exclusión explícita sintética","fuente":datos.F} for v in xyz]
        data["apoyos"] = [{"punto":v,"restricciones":[True]*6,"fuente":datos.F} for v in ("VA","VB")]
        data["asignaciones_superficies"] = [{"objetivo":"S1","seccion":"LOSA20","fuente":datos.F}]
        data["cargas"] = [data["cargas"][1]]
        data["masa"]["gravedad_m_s2"] = 9.80665
        data["geometria_origen"] = {"version_id": self.version.identificador,"sha256_geometria":self.version.comprobacion.sha256_geometria,"huella_contenido":self.version.comprobacion.huella_contenido}
        if orientacion == "vertical":
            next(s for s in data["secciones"] if s["id"]=="LOSA20")["tipo"] = "shell_muro"
        self.data = self.aprobar(data)
        self.archivo = self.f.escribir(self.data,"config03.json")

    def aprobar(self,data):
        data=copy.deepcopy(data)
        data["revision"]={"estado":"aprobado","aprobacion":{"revisor_declarado":"Revisor de software sintético","fecha":"2026-10-19","huella_configuracion":m.huella_configuracion(data),"alcance":"Solo software; no diseño","identidad_revisor":"declarada_no_verificada"}}
        return data


class ModeloAberturasTests(CasoAberturas):
    def test_orientaciones_reales_en_disco_y_bloqueo(self):
        for orientacion in ("horizontal","inclinado","vertical"):
            self.montar(orientacion)
            data=m.cargar_configuracion(self.archivo)
            r=m.comprobar_configuracion(self.raiz,data)
            self.assertTrue(r.consistente,r.errores)
            self.assertTrue(r.geometria_aprobada_por_huella,r.bloqueos)
            self.assertTrue(r.apto_para_plan_desarrollo,r.bloqueos)
            self.assertFalse(r.apto_para_adaptador)
            self.assertIn(m.BLOQUEO_ABERTURAS,r.bloqueos)

    def test_omisiones_fuentes_versiones_y_hash(self):
        for cambiar in (lambda d:d["puntos"].pop(),lambda d:d["secciones"][1].update(fuente="falsa"),lambda d:d["geometria_origen"].update(sha256_geometria="0"*64),lambda d:d.update(version_contrato="0.2.0"),lambda d:d["cargas"][0].update(objetivo="HUECO1")):
            data=copy.deepcopy(self.data); cambiar(data); data=self.aprobar(data)
            r=m.comprobar_configuracion(self.raiz,data)
            self.assertFalse(r.apto_para_plan_desarrollo,r.a_dict())

    def test_cambio_hueco_en_disco_invalida(self):
        ruta=self.version.ruta/g.ARCHIVO_GEOMETRIA; raw=ruta.read_bytes()
        changed=copy.deepcopy(self.geo); changed["vertices"][-1]["y"]-=.01
        ruta.write_text(json.dumps(changed),encoding="utf-8")
        try:
            self.assertFalse(m.comprobar_configuracion(self.raiz,self.data).apto_para_plan_desarrollo)
        finally:ruta.write_bytes(raw)
