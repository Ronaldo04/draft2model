"""Correspondencia0.4 conserva huecos y áreas sobre fuentes sintéticas exactas."""
import copy
import hashlib
import json
import unittest
from unittest.mock import patch

from draft2model import gestion_geometria as geo
from draft2model import revision_superposicion as sup
from tests.test_geometria_aberturas import ejemplo
from tests import test_revision_superposicion as base


class SuperposicionAberturasTests(unittest.TestCase):
    def setUp(self):
        self.f=base.SuperposicionTests();self.f.setUp();self.addCleanup(self.f.doCleanups)

    def preparar(self,transformar=lambda x,y:(x,y,2.6),plano=None,unidad='m'):
        datos=ejemplo(unidad,transformar);datos['id']=base.CASO
        ident=self.importar(datos)
        actual=self.f.app.geometria(base.CASO,ident)
        body={'caso':base.CASO,'expediente_sha256':self.f.fp,'geometria':ident,'huella_geometria':actual['huella'],
              'sha256_geometria':actual['sha256_geometria'],'archivo':self.f.archivo,'pagina':1,'version_contrato':'0.4.0',
              'plano':plano or {'tipo':'horizontal','cota_m':2.6},'superficies':['S1'],
              'anclas':[{'vertice':f'V{i}','punto':[.2+.1*x,.2+.1*y]} for i,(x,y) in enumerate(((0,0),(4,0),(4,3)))],
              'revisor_declarado':'Operador sintético','fecha':'2026-10-19','motivo':'Correspondencia declarada de software, sin ingeniería.','confirmacion_explicita':True}
        return body,ident

    def importar(self,datos):
        path=self.f.root/'aberturas.json';path.write_text(json.dumps(datos),encoding='utf-8')
        return geo.importar_geometria(self.f.app.raiz,base.CASO,path).identificador

    def consultar(self,item):return self.f.service.consultar(base.CASO,item['id'],expediente_sha256=self.f.fp)

    def test_horizontal_todos_huecos_areas_y_fuentes_regeneradas(self):
        body,ident=self.preparar(unidad='cm')
        esquema=self.f.service.esquema(base.CASO,ident,expediente_sha256=self.f.fp)
        self.assertEqual(esquema['version_geometria'],'0.3.0')
        self.assertEqual(esquema['superficies'][0]['aberturas'][0]['vertices_m'][0],[1,1,2.6])
        status,raw,_=self.f.request('POST','/api/superposicion/crear',body)
        self.assertEqual(status,201,raw);item=json.loads(raw)
        self.assertEqual(self.consultar(item),item)
        self.assertEqual(item['version_contrato'],'0.4.0')
        self.assertEqual(item['geometria']['version_contrato'],'0.3.0')
        s=item['superficies'][0];h=s['aberturas'][0]
        self.assertEqual((s['area_bruta_m2'],s['area_aberturas_m2'],s['area_neta_m2']),(12,1,11))
        self.assertEqual(h['id'],'A1');self.assertEqual(h['superficie'],'S1')
        self.assertEqual(len(h['proyeccion']),4)
        self.assertAlmostEqual(h['proyeccion'][0]['u'],.3);self.assertAlmostEqual(h['proyeccion'][0]['v'],.3)
        self.assertFalse(item['aprueba_geometria'] or item['aprueba_ingenieria'] or item['disponible_para_modelado'])
        registro=json.loads((self.f.case/'superposiciones'/item['id']/'correspondencia.json').read_bytes())
        self.assertEqual(registro['aberturas'],{'S1':['A1']})
        self.assertEqual(self.f.service.listar(base.CASO,expediente_sha256=self.f.fp)['versiones'][0]['version_contrato'],'0.4.0')

    def test_inclinado_y_vertical_con_huecos_en_base3d(self):
        import math
        casos=[(lambda x,y:(10+x,20+y,2+y),{'tipo':'base_ortonormal_3d','origen_m':[10,20,2],'eje_u':[1,0,0],'eje_v':[0,1/math.sqrt(2),1/math.sqrt(2)]},math.sqrt(2)),
               (lambda x,y:(2,x,y),{'tipo':'base_ortonormal_3d','origen_m':[2,0,0],'eje_u':[0,1,0],'eje_v':[0,0,1]},1)]
        for transformar,plano,factor in casos:
            body,_=self.preparar(transformar,plano)
            body['anclas'][2]['punto'][1]=.2+.3*factor
            item=self.f.service.crear(body);s=item['superficies'][0];h=s['aberturas'][0]
            self.assertAlmostEqual(s['area_neta_m2'],11*factor)
            self.assertAlmostEqual(h['vertices_plano_m'][0][0],1)
            self.assertAlmostEqual(h['vertices_plano_m'][0][1],factor)
            self.assertAlmostEqual(h['proyeccion'][0]['v'],.2+.1*factor)
            self.assertIn('A1',item['base_vista']['criterios_coplanaridad_aberturas']['S1'])
            self.assertEqual(self.consultar(item),item)

    def test_formatos_anteriores_y_anclas_de_hueco_no_pueden_omitirlo(self):
        body,_=self.preparar()
        for version in ('0.1.0','0.2.0','0.3.0'):
            with self.subTest(version=version),self.assertRaises(sup.ErrorSuperposicion):
                self.f.service.crear({**body,'version_contrato':version})
        for cambio in (lambda b:b['anclas'][0].update(vertice='A1V0'),lambda b:b.update(superficies=[]),
                       lambda b:b.update(sha256_geometria='0'*64),lambda b:b.update(aberturas=[]),
                       lambda b:b['plano'].update(cota_m=0),lambda b:b['plano'].update(tipo='inferencia')):
            b=copy.deepcopy(body);cambio(b)
            with self.subTest(cambio=cambio),self.assertRaises(sup.ErrorSuperposicion):self.f.service.crear(b)

    def test_registro_rehasheado_sin_hueco_o_anfitriona_alterada_no_es_vigente(self):
        body,_=self.preparar();item=self.f.service.crear(body)
        carpeta=self.f.case/'superposiciones'/item['id'];regpath=carpeta/'correspondencia.json';metapath=carpeta/'version.json'
        originales=(regpath.read_bytes(),metapath.read_bytes())
        for cambio in (lambda r:r.update(aberturas={'S1':[]}),lambda r:r['geometria'].update(version_contrato='0.2.0'),lambda r:r['plano'].update(cota_m=0)):
            registro=json.loads(originales[0]);meta=json.loads(originales[1]);cambio(registro)
            regpath.write_bytes(sup._bytes(registro));meta['sha256_correspondencia']=hashlib.sha256(regpath.read_bytes()).hexdigest();metapath.write_bytes(sup._bytes(meta))
            with self.subTest(cambio=cambio),self.assertRaises(sup.ErrorSuperposicion):self.consultar(item)
            regpath.write_bytes(originales[0]);metapath.write_bytes(originales[1])

    def test_cambio_geometrico_durante_render_se_detecta(self):
        body,ident=self.preparar();item=self.f.service.crear(body)
        path=self.f.case/'geometrias'/ident/'geometria.json';original=path.read_bytes();real=self.f.app.pagina
        def cambiar(*args,**kwargs):
            raw=real(*args,**kwargs);path.write_bytes(original+b' ');return raw
        try:
            with patch.object(self.f.app,'pagina',side_effect=cambiar),self.assertRaises(sup.ErrorSuperposicion):self.consultar(item)
        finally:path.write_bytes(original)
        self.assertEqual(self.consultar(item),item)

    def test_anclas_otra_superficie_y_geometria02_con_formato04_rechazadas(self):
        body,ident=self.preparar()
        datos=self.f.app.geometria(base.CASO,ident)['datos']
        datos['vertices'].extend([{'id':'W'+str(i),**{k:v for k,v in punto.items() if k!='id'}} for i,punto in enumerate(copy.deepcopy(datos['vertices'][:4]))])
        datos['superficies'].append({**copy.deepcopy(datos['superficies'][0]),'id':'S2','vertices':['W0','W1','W2','W3']})
        nuevo=self.importar(datos);actual=self.f.app.geometria(base.CASO,nuevo)
        body.update(geometria=nuevo,huella_geometria=actual['huella'],sha256_geometria=actual['sha256_geometria'])
        body['anclas'][0]['vertice']='W0'
        with self.assertRaises(sup.ErrorSuperposicion):self.f.service.crear(body)
        datos['version_contrato']='0.2.0';datos.pop('aberturas');nuevo=self.importar(datos);actual=self.f.app.geometria(base.CASO,nuevo)
        body.update(geometria=nuevo,huella_geometria=actual['huella'],sha256_geometria=actual['sha256_geometria']);body['anclas'][0]['vertice']='V0'
        with self.assertRaises(sup.ErrorSuperposicion):self.f.service.crear(body)


if __name__=='__main__':unittest.main()
