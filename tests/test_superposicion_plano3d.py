"""Bases físicas 3D declaradas para contraste visual de paneles sintéticos."""
import copy
import hashlib
import json
import math
import unittest
from unittest.mock import patch

from draft2model.revision_superposicion import ErrorSuperposicion, ServicioSuperposicion
from tests import test_geometria_superficies as formas
from tests import test_superposicion_superficies as horizontal
from tests import test_revision_superposicion as legado


def inclinado():
    q = math.sqrt(.5)
    return ([(10,20,2),(14,20,2),(14,23,5),(10,23,5)],
            {'tipo':'base_ortonormal_3d','origen_m':[10,20,2],'eje_u':[1,0,0],'eje_v':[0,q,q]})


class Plano3dTests(unittest.TestCase):
    def setUp(self):
        self.f = horizontal.SuperposicionSuperficiesTests('test_contorno_guardado_consultado_y_proyectado_con_area_procedencia')
        self.addCleanup(self.f.doCleanups)
        self.f.setUp()
        self.servicio = self.f.f.service
        self.fp = self.f.f.fp

    def preparar(self, puntos=None, plano=None):
        if puntos is None:
            puntos, plano = inclinado()
        datos = formas.ejemplo(puntos)
        datos['id'] = legado.CASO
        ident = self.f.importar(datos)
        return self.body(ident, puntos, plano), ident

    def body(self, ident, puntos, plano):
        body = self.f.cuerpo(ident)
        body.update(version_contrato='0.3.0', plano=copy.deepcopy(plano))
        anclas = []
        for i, p in enumerate(puntos[:3]):
            delta = [p[k]-plano['origen_m'][k] for k in range(3)]
            uv = [math.fsum(delta[k]*plano[eje][k] for k in range(3)) for eje in ('eje_u','eje_v')]
            anclas.append({'vertice':f'V{i}','punto':[.2+.1*uv[0], .2+.1*uv[1]]})
        body['anclas'] = anclas
        return body

    def test_inclinado_regenerado_desde_archivos_exactos(self):
        body, ident = self.preparar()
        item = self.servicio.crear(body)
        self.assertEqual(item['version_contrato'],'0.3.0')
        self.assertEqual(item['geometria']['version_contrato'],'0.2.0')
        self.assertEqual(item['plano'],body['plano'])
        self.assertEqual(item['transformacion']['de'],'plano3d_uv_m')
        self.assertEqual(item['base_vista']['epsilon_ortonormalidad'],1e-12)
        self.assertEqual(len(item['huella_plano']),64)
        s = item['superficies'][0]
        self.assertAlmostEqual(s['area_m2'],12*math.sqrt(2))
        self.assertEqual(s['vertices_m'][2],[14,23,5])
        self.assertAlmostEqual(s['vertices_plano_m'][2][1],3*math.sqrt(2))
        self.assertAlmostEqual(s['proyeccion'][2]['u'],.6)
        self.assertAlmostEqual(s['proyeccion'][2]['v'],.2+.3*math.sqrt(2))
        self.assertFalse(item['aprueba_geometria'] or item['aprueba_ingenieria'] or item['disponible_para_modelado'])
        nuevo_servicio = ServicioSuperposicion(self.f.f.app)
        self.assertEqual(nuevo_servicio.consultar(legado.CASO,item['id'],expediente_sha256=self.fp),item)
        guardado = json.loads((self.f.f.case/'superposiciones'/item['id']/'correspondencia.json').read_bytes())
        raw_plano=(json.dumps(guardado['plano'],sort_keys=True,ensure_ascii=False,allow_nan=False,indent=2)+'\n').encode()
        self.assertEqual(hashlib.sha256(raw_plano).hexdigest(),item['huella_plano'])
        self.assertEqual(nuevo_servicio.listar(legado.CASO,expediente_sha256=self.fp)['versiones'][0]['version_contrato'],'0.3.0')

    def test_vertical_y_sentido_u_cruz_v_declarados(self):
        puntos=[(2,0,0),(2,4,0),(2,4,3),(2,0,3)]
        plano={'tipo':'base_ortonormal_3d','origen_m':[2,0,0],'eje_u':[0,1,0],'eje_v':[0,0,1]}
        b,_=self.preparar(puntos,plano)
        item=self.servicio.crear(b)
        self.assertEqual(item['base_vista']['normal_u_cruz_v'],[1,0,0])
        self.assertEqual(item['superficies'][0]['vertices_plano_m'],[[0,0],[4,0],[4,3],[0,3]])
        self.assertEqual(item['superficies'][0]['area_m2'],12)
        self.assertAlmostEqual(item['superficies'][0]['proyeccion'][3]['v'],.5)

    def test_base_y_miembros_invalidos_no_se_reparan(self):
        body,_=self.preparar()
        cambios=[lambda b:b['plano'].update(eje_u=[2,0,0]),
                 lambda b:b['plano'].update(eje_u=[0,0,0]),
                 lambda b:b['plano'].update(eje_v=[1,0,0]),
                 lambda b:b['plano'].update(eje_v=[.1,math.sqrt(.99),0]),
                 lambda b:b['plano'].update(origen_m=[10,20,3]),
                 lambda b:b['plano'].update(origen_m=[0,0]),
                 lambda b:b['plano'].update(origen_m=[True,20,2]),
                 lambda b:b['plano'].update(eje_v=[0,float('inf'),0]),
                 lambda b:b['plano'].update(tolerancia_ingenieria=1),
                 lambda b:b.update(version_contrato='0.2.0'),
                 lambda b:b.update(superficies=['ausente']),
                 lambda b:b['anclas'][0].update(vertice='no_seleccionado')]
        for cambiar in cambios:
            b=copy.deepcopy(body);cambiar(b)
            with self.subTest(cambiar=cambiar),self.assertRaises(ErrorSuperposicion):
                self.servicio.crear(b)

    def test_otra_superficie_coplanar_no_aporta_anclas_sin_seleccion(self):
        puntos,plano=inclinado()
        datos=formas.ejemplo(puntos);datos['id']=legado.CASO
        datos['vertices'].extend([{'id':f'W{i}','x':x+20,'y':y,'z':z,'procedencia':copy.deepcopy(datos['procedencia'])}
                                 for i,(x,y,z) in enumerate(puntos)])
        datos['superficies'].append({**copy.deepcopy(datos['superficies'][0]),'id':'S2','vertices':[f'W{i}' for i in range(4)]})
        ident=self.f.importar(datos)
        b=self.body(ident,puntos,plano)
        b['anclas'][0]['vertice']='W0'
        with self.assertRaises(ErrorSuperposicion):
            self.servicio.crear(b)

    def test_registro_manipulado_con_hash_recalculado(self):
        body,_=self.preparar();item=self.servicio.crear(body)
        carpeta=self.f.f.case/'superposiciones'/item['id']
        raw=(carpeta/'correspondencia.json').read_bytes();meta_raw=(carpeta/'version.json').read_bytes()
        cambios=[lambda r:r.update(huella_plano='0'*64),
                 lambda r:r['base_vista'].update(epsilon_ortonormalidad=.1),
                 lambda r:r['base_vista']['normal_u_cruz_v'].__setitem__(0,1),
                 lambda r:r['plano'].update(origen_m=[10,20,3]),
                 lambda r:r['transformacion']['matriz'][0].__setitem__(2,.9),
                 lambda r:r.update(aprueba_ingenieria=True)]
        for cambio in cambios:
            reg=json.loads(raw);cambio(reg);modificado=json.dumps(reg).encode()
            meta=json.loads(meta_raw);meta['sha256_correspondencia']=hashlib.sha256(modificado).hexdigest()
            (carpeta/'correspondencia.json').write_bytes(modificado)
            (carpeta/'version.json').write_text(json.dumps(meta),encoding='utf-8')
            with self.subTest(cambio=cambio),self.assertRaises(ErrorSuperposicion):
                self.servicio.consultar(legado.CASO,item['id'],expediente_sha256=self.fp)
        (carpeta/'correspondencia.json').write_bytes(raw);(carpeta/'version.json').write_bytes(meta_raw)
        self.assertTrue(self.servicio.consultar(legado.CASO,item['id'],expediente_sha256=self.fp)['vigente'])

    def test_cambio_fuente_despues_del_render_invalida(self):
        body,ident=self.preparar();item=self.servicio.crear(body)
        archivo=self.f.f.case/'geometrias'/ident/'geometria.json'
        original=archivo.read_bytes();pagina=self.f.f.app.pagina
        def mutar(*args,**kwargs):
            salida=pagina(*args,**kwargs);archivo.write_bytes(original+b' ');return salida
        try:
            with patch.object(self.f.f.app,'pagina',side_effect=mutar),self.assertRaises(ErrorSuperposicion):
                self.servicio.consultar(legado.CASO,item['id'],expediente_sha256=self.fp)
        finally:
            archivo.write_bytes(original)
        self.assertTrue(self.servicio.consultar(legado.CASO,item['id'],expediente_sha256=self.fp)['vigente'])


if __name__=='__main__':
    unittest.main()
