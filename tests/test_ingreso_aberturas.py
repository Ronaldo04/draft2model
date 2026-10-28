"""Ingreso supervisado de huecos sintéticos; fuentes/recibos reales, sin API/ETABS."""
import copy
import csv
import hashlib
import io
import json
from pathlib import Path
import unittest

from draft2model import contratos as c
from draft2model import conversion_geometria as conversion
from draft2model import revision_conversion as rc
from draft2model import revision_tabular as rt
from draft2model.importacion_tabular import convertir_tablas, colecciones_tabulares, ErrorImportacionTabular, main
from draft2model.lectura_xlsx import leer_tablas_xlsx
from tests.test_geometria_aberturas import ejemplo
from tests.test_tabular_superficies import tabla, xlsx
from tests import test_revision_tabular as tabular
from tests import test_revision_conversion as web
from tests.test_conversion_superficies import manifiesto_superficie


def fuentes(caso):
    geometria=ejemplo(); geometria['id']=caso
    esquemas=colecciones_tabulares(geometria)
    metadatos={k:v for k,v in geometria.items() if k not in esquemas}
    tablas={}
    for nombre,spec in esquemas.items():
        campos=spec['obligatorios']
        filas=[[json.dumps(item[k],ensure_ascii=False) if isinstance(item[k],(dict,list)) else item[k] for k in campos] for item in geometria[nombre]]
        tablas[nombre]=tabla(campos,filas)
    return geometria,metadatos,tablas


def manifiesto(anterior):
    m=manifiesto_superficie(anterior); m['version_contrato']='0.3.0'
    def medida(v): return {'valor':v,'unidad':'m','justificacion':'Medida física sintética declarada, no píxeles.','referencias':['C006']}
    m['vertices'].extend([{'id':f'H{i}','x':medida(x),'y':medida(y),'z':{'candidato':'C001'}} for i,(x,y) in enumerate(((1,1),(2,1),(2,2),(1,2)))])
    m['aberturas']=[{'id':'A1','superficie':'S1','vertices':['H0','H1','H2','H3'],'referencias':['C004']}]
    return m


class TabularAberturasTests(unittest.TestCase):
    def setUp(self):
        self.f=tabular.TabularWebTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.geometria,self.meta,self.tablas=fuentes(tabular.CASO)

    def body(self,tablas=None):
        return self.f.body_csv(meta=self.meta,archivos={n+'.csv':t.encode() for n,t in (tablas or self.tablas).items()})

    def test_seis_tablas_xlsx_y_cli_conservan_huecos_sin_inferir(self):
        self.assertEqual(convertir_tablas(self.meta,self.tablas),self.geometria)
        raw=xlsx(self.tablas)
        hojas=leer_tablas_xlsx(io.BytesIO(raw),colecciones=tuple(self.tablas))
        self.assertEqual(convertir_tablas(self.meta,hojas),self.geometria)
        with self.assertRaises(ValueError): leer_tablas_xlsx(io.BytesIO(raw))
        carpeta=self.f.case.parent/'csv03'; carpeta.mkdir()
        (carpeta/'metadata.json').write_text(json.dumps(self.meta),encoding='utf-8')
        args=['--metadatos',str(carpeta/'metadata.json'),'--salida',str(carpeta/'resultado.json')]
        for nombre,texto in self.tablas.items():
            path=carpeta/(nombre+'.csv'); path.write_text(texto,encoding='utf-8');args.extend(['--'+nombre,str(path)])
        self.assertEqual(main(args),0)
        self.assertEqual(json.loads((carpeta/'resultado.json').read_text(encoding='utf-8')),self.geometria)

    def test_registro_reproduce_bytes_importa_separado_y_replay(self):
        item=self.f.service.crear(self.body())
        otro=self.f.service.crear(self.f.body_xlsx(raw=xlsx(self.tablas),meta=self.meta))
        self.assertEqual(item['version_contrato'],'0.3.0')
        self.assertEqual(item['archivos']['geometria.json'],otro['archivos']['geometria.json'])
        self.assertEqual(item['resumen']['aberturas'],1)
        self.assertEqual(self.f.versiones_geometria(),[])
        self.assertEqual(self.f.service.consultar(tabular.CASO,item['id'],expediente_sha256=self.f.fp),item)
        imported=self.f.importar(item)
        self.assertEqual(self.f.importar(item),imported)
        geo=self.f.app.geometria(tabular.CASO,imported['geometria'])
        self.assertEqual(geo['datos'],self.geometria)
        self.assertFalse(geo['comprobacion']['validacion']['disponible_para_modelado'])
        self.assertEqual(geo['datos']['revision'],{'estado':'borrador','aprobacion':None})

    def test_colecciones_version_json_estricto_y_formulas_rechazados(self):
        for version in ('0.1.0','0.2.0','99.0.0'):
            with self.subTest(version=version),self.assertRaises(ErrorImportacionTabular):
                convertir_tablas({**self.meta,'version_contrato':version},self.tablas)
        for nombre in self.tablas:
            with self.subTest(nombre=nombre),self.assertRaises(ErrorImportacionTabular):
                convertir_tablas(self.meta,{n:t for n,t in self.tablas.items() if n!=nombre})
        for celda in ('["A1V0",NaN,"A1V2"]','["A1V0","A1V1","ausente"]','["A1V0","A1V0","A1V2"]','["A1V0",{"x":1,"x":2},"A1V2"]'):
            tablas={**self.tablas,'aberturas':tabla(['id','superficie','vertices','procedencia'],[['A1','S1',celda,json.dumps(self.geometria['procedencia'])]])}
            with self.subTest(celda=celda),self.assertRaises(ErrorImportacionTabular): convertir_tablas(self.meta,tablas)
        with self.assertRaises(ValueError): leer_tablas_xlsx(io.BytesIO(xlsx(self.tablas,formula=True)),colecciones=tuple(self.tablas))

    def test_geometria_rehasheada_no_puede_eliminar_hueco(self):
        item=self.f.service.crear(self.body()); carpeta=self.f.case/'tabulares'/item['id']
        path=carpeta/'geometria.json'; geometria=json.loads(path.read_bytes());geometria['aberturas']=[]
        path.write_bytes(rt._bytes(geometria))
        path_meta=carpeta/'version.json'; meta=json.loads(path_meta.read_bytes());meta['archivos']['geometria.json']=hashlib.sha256(path.read_bytes()).hexdigest();path_meta.write_bytes(rt._bytes(meta))
        with self.assertRaises(ValueError): self.f.service.consultar(tabular.CASO,item['id'],expediente_sha256=self.f.fp)
        with self.assertRaises(ValueError): self.f.importar(item)
        self.assertEqual(self.f.versiones_geometria(),[])

    def test_http_seis_tablas_requiere_confirmacion_e_importa_hueco(self):
        from types import SimpleNamespace
        from tests import test_revision_visual as http
        self.f.server=SimpleNamespace(revision=self.f.app,token='prueba',origen='http://127.0.0.1:8766')
        request=lambda *a,**kw:http.HTTPRevisionTests.request(self.f,*a,**kw)
        status,raw,_=request('POST','/api/tabular/crear',self.body())
        self.assertEqual(status,201,raw);item=json.loads(raw)
        self.assertEqual(self.f.versiones_geometria(),[])
        body={'caso':tabular.CASO,'expediente_sha256':self.f.fp,'version':item['id'],'huella_tabular':item['huella_tabular'],'confirmacion_explicita':False}
        self.assertEqual(request('POST','/api/tabular/importar',body)[0],409)
        status,raw,_=request('POST','/api/tabular/importar',{**body,'confirmacion_explicita':True})
        self.assertEqual(status,201,raw);imported=json.loads(raw)
        self.assertEqual(self.f.app.geometria(tabular.CASO,imported['geometria'])['datos']['aberturas'],self.geometria['aberturas'])


class ConversionAberturasTests(unittest.TestCase):
    def setUp(self):
        self.f=web.ConversionWebTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.m=manifiesto(self.f.fixture.manifiesto)

    def crear(self):
        status,raw,_=self.f.request('POST','/api/conversion/crear',{**self.f.body,'manifiesto_json':json.dumps(self.m)})
        self.assertEqual(status,201,raw);return json.loads(raw)

    def test_http_referencias_trazas_areas_e_importacion_separada(self):
        item=self.crear();g=item['geometria'];traza=item['trazabilidad']
        self.assertEqual(g['version_contrato'],'0.3.0')
        self.assertEqual(g['aberturas'][0]['procedencia']['referencias'],['C004'])
        self.assertEqual(traza['correspondencias'][-1]['modo'],'conectividad_abertura_declarada')
        self.assertEqual(traza['correspondencias'][-1]['superficie'],'S1')
        self.assertEqual(self.f.app.geometrias(self.f.caso),[])
        self.assertEqual(self.f.consult(item),item)
        status,raw,_=self.f.request('POST','/api/conversion/importar-geometria',self.f.import_body(item))
        self.assertEqual(status,201,raw)
        imported=json.loads(raw);self.assertFalse(imported['disponible_para_modelado'])
        self.assertEqual(self.f.app.geometria(self.f.caso,imported['geometria'])['datos'],g)

    def test_referencias_medidas_y_versiones_no_omiten_aberturas(self):
        cambios=[lambda m:m['aberturas'][0].update(referencias=[]),
                 lambda m:m['aberturas'][0].update(referencias=['C002']),
                 lambda m:m['aberturas'][0].update(superficie='ausente'),
                 lambda m:m['aberturas'][0].update(referencias=['C004','C004']),
                 lambda m:m['vertices'][-1].update(x={'valor':1,'unidad':'px','justificacion':'sin escala','referencias':['C004']}),
                 lambda m:m.update(version_contrato='0.2.0'),lambda m:m.pop('aberturas')]
        for cambio in cambios:
            m=copy.deepcopy(self.m);cambio(m)
            with self.subTest(cambio=cambio),self.assertRaises(ValueError):self.f.create(manifiesto_json=json.dumps(m))
        self.assertEqual(self.f.app.geometrias(self.f.caso),[])

    def test_hueco_o_traza_rehasheados_exigen_reproduccion_exacta(self):
        item=self.crear();folder=self.f.case/rc.CARPETA/item['id']
        nombres=('geometria.json','trazabilidad.json','web.json'); originales={n:(folder/n).read_bytes() for n in nombres}
        for objetivo in ('geometria','traza'):
            geometry=json.loads(originales['geometria.json']);trace=json.loads(originales['trazabilidad.json']);receipt=json.loads(originales['web.json'])
            if objetivo=='geometria': geometry['aberturas']=[]
            else: trace['correspondencias'][-1]['superficie']='otra'
            raw=rc._bytes(geometry);(folder/'geometria.json').write_bytes(raw)
            trace['geometria_sha256']=hashlib.sha256(raw).hexdigest();trace['huella_contenido']=c.huella_contenido(geometry)
            (folder/'trazabilidad.json').write_bytes(rc._bytes(trace))
            for n in ('geometria.json','trazabilidad.json'):receipt['archivos'][n]=hashlib.sha256((folder/n).read_bytes()).hexdigest()
            (folder/'web.json').write_bytes(rc._bytes(receipt))
            with self.subTest(objetivo=objetivo),self.assertRaises(ValueError):self.f.consult(item)
            with self.assertRaises(ValueError):self.f.service.importar_geometria(self.f.import_body(item))
            for n,raw in originales.items():(folder/n).write_bytes(raw)


if __name__=='__main__':unittest.main()
