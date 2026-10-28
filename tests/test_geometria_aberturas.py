"""Casos sintéticos de huecos geométricos; no acreditan ingeniería ni ETABS."""
import copy
import math
import unittest

from draft2model import contratos as c
from draft2model import gestion_geometria as gestion
from draft2model.geometria_aberturas import BLOQUEO_INTEGRACION
from draft2model.plan_modelado import preparar_plan_modelado
from draft2model.validacion_geometria import validar_geometria
from tests.test_geometria_superficies import ejemplo as superficie
from tests import test_gestion_geometria as disco


def ejemplo(unidad="m", transformar=lambda x,y:(x,y,0)):
    data = superficie([transformar(x,y) for x,y in [(0,0),(4,0),(4,3),(0,3)]], unidad)
    data.update(version_contrato=c.VERSION_GEOMETRIA_ABERTURAS, aberturas=[])
    agregar(data, [(1,1),(2,1),(2,2),(1,2)], transformar=transformar)
    return data


def agregar(data, puntos, ident="A1", transformar=lambda x,y:(x,y,0)):
    factor = c.DIVISORES_A_METROS[data["unidad_longitud"]]
    ids=[]
    for i, (x,y) in enumerate(puntos):
        vid=f"{ident}V{i}"; ids.append(vid)
        data["vertices"].append({"id":vid, **{k:v*factor for k,v in zip(("x","y","z"),transformar(x,y))},
                                  "procedencia":copy.deepcopy(data["procedencia"])})
    data["aberturas"].append({"id":ident,"superficie":"S1","vertices":ids,"procedencia":copy.deepcopy(data["procedencia"])})


class AberturasTests(unittest.TestCase):
    def test_orientaciones_unidades_y_areas(self):
        for transformar, area in [(lambda x,y:(x,y,0),1), (lambda x,y:(x,y,y),math.sqrt(2)), (lambda x,y:(0,x,y),1)]:
            derivados=[]
            for unidad in ("m","cm","mm"):
                with self.subTest(unidad=unidad,area=area):
                    data=ejemplo(unidad,transformar); antes=copy.deepcopy(data)
                    r=validar_geometria(data)
                    self.assertTrue(r.consistente,r.errores)
                    self.assertFalse(r.disponible_para_modelado)
                    self.assertIn(BLOQUEO_INTEGRACION,r.bloqueos)
                    self.assertEqual(data,antes)
                    d=r.derivados_m["superficies"]["S1"]
                    self.assertAlmostEqual(d["area_bruta_m2"],12*area)
                    self.assertAlmostEqual(d["area_aberturas_m2"],area)
                    self.assertAlmostEqual(d["area_neta_m2"],11*area)
                    self.assertEqual(d["aberturas_ids"],["A1"])
                    derivados.append(r.derivados_m)
            self.assertEqual(derivados[0],derivados[1]); self.assertEqual(derivados[0],derivados[2])

    def test_plan_conserva_huecos_trazas_orden_y_fuente(self):
        data=ejemplo(); agregar(data,[(2.5,.5),(3.5,.5),(3.5,1.5),(2.5,1.5)],"A2")
        data["aberturas"][0]["vertices"].reverse()
        original=copy.deepcopy(data)
        plan=preparar_plan_modelado(data)
        self.assertEqual(plan["version_contrato"],"0.3.0")
        self.assertEqual(plan["cobertura"],"completa")
        self.assertEqual(plan["cobertura_aberturas"],"completa")
        self.assertFalse(plan["ejecutable_en_etabs"])
        self.assertEqual(plan["superficies"][0]["area_neta_m2"],10)
        self.assertEqual([a["abertura_id"] for a in plan["aberturas"]],["A1","A2"])
        self.assertEqual(plan["aberturas"][0]["vertices_ids"],data["aberturas"][0]["vertices"])
        self.assertEqual(plan["aberturas"][0]["procedencia"],data["aberturas"][0]["procedencia"])
        self.assertEqual(plan["vertices"],data["vertices"])
        self.assertEqual(plan["origen"]["huella_contenido"],c.huella_contenido(data))
        plan["aberturas"][0]["procedencia"]["descripcion"]="cambio externo"
        self.assertEqual(data,original)

    def test_lista_vacia_explicita_y_versiones_anteriores_estrictas(self):
        data=ejemplo(); data["aberturas"]=[]
        r=validar_geometria(data)
        self.assertTrue(r.consistente,r.errores)
        self.assertEqual(r.derivados_m["superficies"]["S1"]["area_neta_m2"],12)
        for version in ("0.1.0","0.2.0"):
            data["version_contrato"]=version
            self.assertFalse(validar_geometria(data).consistente)
        data["version_contrato"]="0.3.0"; del data["aberturas"]
        self.assertFalse(validar_geometria(data).consistente)

    def test_muros_heredados_y_superficie_con_hueco_no_se_confunden(self):
        from tests.test_validacion_geometria import sintetico
        data=ejemplo(); muros=sintetico()
        for clave in ("niveles","nodos","muros"):
            data[clave]=copy.deepcopy(muros[clave])
        plan=preparar_plan_modelado(data)
        self.assertTrue(plan["origen"]["validacion"]["consistente"])
        self.assertEqual(len(plan["superficies"]),len(data["muros"])+1)
        self.assertEqual(plan["cobertura"],"completa")
        self.assertEqual(plan["superficies"][-1]["superficie_id"],"S1")
        self.assertEqual(plan["superficies"][-1]["aberturas_ids"],["A1"])
        self.assertEqual(plan["aberturas"][0]["superficie_id"],"S1")

    def test_exterior_contacto_cruce_no_coplanar_y_autointerseccion(self):
        casos=[[(0,1),(1,1),(1,2),(0,2)], [(-1,1),(1,1),(1,2),(-1,2)],
               [(5,1),(6,1),(6,2),(5,2)], [(1,1),(2,2),(2,1),(1,2)],
               [(1,1),(2,1),(1,1)], [(1,1),(2,1),(3,1)]]
        for puntos in casos:
            with self.subTest(puntos=puntos):
                data=ejemplo(); data["aberturas"]=[]; agregar(data,puntos,"nuevo")
                self.assertTrue(any(e.codigo == "abertura_invalida" for e in validar_geometria(data).errores))
                self.rechazar(data)
        data=ejemplo()
        for vertice in data["vertices"][4:]: vertice["z"] = .001
        self.rechazar(data)

    def test_hueco_concavo_valido_anfitriona_concava_y_cruce_de_entrante(self):
        data=ejemplo(); data["aberturas"]=[]
        agregar(data,[(.5,.5),(2.5,.5),(1.5,1),(2.5,2.5),(.5,2.5)],"nuevo")
        self.assertTrue(validar_geometria(data).consistente)
        data=superficie([(0,0,0),(4,0,0),(4,4,0),(3,4,0),(3,1,0),(1,1,0),(1,4,0),(0,4,0)])
        data.update(version_contrato="0.3.0",aberturas=[])
        agregar(data,[(.2,2),(.8,2),(.8,3),(.2,3)])
        self.assertTrue(validar_geometria(data).consistente)
        data["aberturas"]=[]
        agregar(data,[(.2,2),(3.8,2),(3.8,3),(.2,3)],"cruza")
        self.rechazar(data)

    def test_aberturas_contacto_cruce_y_anidacion_ambas_direcciones(self):
        casos=[[(2,1),(3,1),(3,2),(2,2)], [(1.5,.5),(2.5,.5),(2.5,1.5),(1.5,1.5)],
               [(1.2,1.2),(1.8,1.2),(1.8,1.8),(1.2,1.8)],
               [(.5,.5),(2.5,.5),(2.5,2.5),(.5,2.5)], [(1,1),(2,1),(2,2),(1,2)]]
        for puntos in casos:
            data=ejemplo(); agregar(data,puntos,"A2")
            with self.subTest(puntos=puntos): self.rechazar(data)

    def test_esquema_identidad_referencias_y_numeros(self):
        cambios=[lambda d:d["aberturas"][0].update(superficie="ausente"),
                 lambda d:d["aberturas"][0].update(superficie=[]),
                 lambda d:d["aberturas"][0].update(vertices=["A1V0","A1V1","ausente"]),
                 lambda d:d["aberturas"][0].update(vertices=[{},"A1V1","A1V2"]),
                 lambda d:d["aberturas"][0].update(otro=1),
                 lambda d:d["aberturas"].append(copy.deepcopy(d["aberturas"][0])),
                 lambda d:d["vertices"][4].update(x=float("nan")),
                 lambda d:d["vertices"][4].update(x=True),
                 lambda d:d["vertices"][4].update(x=float("inf")),
                 lambda d:d.update(aberturas=None),
                 lambda d:d["aberturas"].append(None)]
        for cambio in cambios:
            data=ejemplo(); cambio(data)
            with self.subTest(cambio=cambio): self.rechazar(data)

    def test_aprobacion_huella_alteracion_y_plan_no_ejecutable(self):
        data=ejemplo()
        data["revision"]={"estado":"aprobado","aprobacion":{"declarada_por":"Prueba sintética","fecha":"2026-10-19","huella_contenido":c.huella_contenido(data)}}
        r=validar_geometria(data)
        self.assertTrue(r.aprobacion_geometrica_vigente)
        self.assertFalse(r.disponible_para_modelado)
        self.assertFalse(preparar_plan_modelado(data)["ejecutable_en_etabs"])
        data["vertices"][4]["x"]=.9
        r=validar_geometria(data)
        self.assertTrue(r.consistente,r.errores)
        self.assertFalse(r.aprobacion_geometrica_vigente)
        self.assertFalse(r.disponible_para_modelado)

    def test_gestion_importacion_aprobacion_y_alteracion_real_en_disco(self):
        fixture=disco.CasoGeometria(); fixture.setUp(); self.addCleanup(fixture.doCleanups)
        data=ejemplo(); data["id"]=disco.CASO
        base=gestion.importar_geometria(fixture.raiz,disco.CASO,fixture.escribir(data))
        antes=disco.instantanea(base.ruta)
        child=fixture.aprobar(base.identificador,base.comprobacion.huella_contenido)
        self.assertEqual(disco.instantanea(base.ruta),antes)
        consulta=gestion.consultar_version(fixture.raiz,disco.CASO,child.identificador)
        self.assertTrue(consulta.comprobacion.correcta,consulta.comprobacion.problemas)
        self.assertEqual(consulta.metadatos["contrato_geometria"]["version_contrato"],"0.3.0")
        self.assertFalse(consulta.comprobacion.validacion["disponible_para_modelado"])
        self.assertTrue(validar_geometria(consulta.geometria).aprobacion_geometrica_vigente)
        path=child.ruta/gestion.ARCHIVO_GEOMETRIA
        path.write_bytes(path.read_bytes()+b" ")
        self.assertFalse(gestion.consultar_version(fixture.raiz,disco.CASO,child.identificador).comprobacion.correcta)

    def rechazar(self,data):
        r=validar_geometria(data)
        self.assertFalse(r.consistente)
        self.assertIsNone(r.geometria_m); self.assertIsNone(r.derivados_m); self.assertIsNone(r.huella_contenido)
        self.assertFalse(r.disponible_para_modelado)
        plan=preparar_plan_modelado(data)
        self.assertEqual(plan["superficies"],[]); self.assertEqual(plan["aberturas"],[])
        self.assertFalse(plan["ejecutable_en_etabs"])


if __name__ == "__main__": unittest.main()
