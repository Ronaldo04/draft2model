import copy
import json
from pathlib import Path
import tempfile
import unittest
from draft2model.sitio import consultar_sitio,huella_capa


class SitioTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'capa.json'
        self.data={'contrato':'draft2model.capa_sitio','version':'0.1.0','crs':'EPSG:4326',
                   'fuente':{'titulo':'Cuadrado SINTÉTICO','edicion':'prueba','referencia':'fixture local'},
                   'fecha':'2026-10-16','precision_m':10,'datos_sinteticos':True,
                   'zonas':[{'id':'Z1','etiqueta':'Zona sintética','geometria':{'type':'Polygon','coordinates':[[[0,0],[2,0],[2,2],[0,2],[0,0]]]}}], 'aprobacion':None}
        self.write()

    def write(self):
        self.data['aprobacion']={'huella':huella_capa(self.data),'revisor_declarado':'Prueba sintética','fecha':'2026-10-16','alcance':'Solo prueba de cobertura'}
        self.path.write_text(json.dumps(self.data),encoding='utf-8')

    def test_dentro_fuera_limite_sin_inferencias(self):
        for point,state in (([1,1],'dentro'),([3,3],'sin_cobertura'),([0,1],'limite'),([0,0],'limite')):
            result=consultar_sitio(self.path,*point)
            self.assertEqual(result['estado'],state)
            self.assertIsNone(result['capacidad_portante']);self.assertIsNone(result['parametros_geotecnicos'])

    def test_huecos_y_solapamiento(self):
        self.data['zonas'][0]['geometria']['coordinates'].append([[0.5,0.5],[1.5,0.5],[1.5,1.5],[0.5,1.5],[0.5,0.5]])
        self.write()
        self.assertEqual(consultar_sitio(self.path,1,1)['estado'],'sin_cobertura')
        self.assertEqual(consultar_sitio(self.path,0.5,1)['estado'],'limite')
        zone=copy.deepcopy(self.data['zonas'][0]);zone['id']='Z2';self.data['zonas'].append(zone);self.write()
        self.assertEqual(consultar_sitio(self.path,0.2,0.2)['estado'],'ambiguo')

    def test_invalidos_y_aprobacion_desactualizada(self):
        self.data['precision_m']=20
        self.path.write_text(json.dumps(self.data),encoding='utf-8')
        with self.assertRaises(ValueError): consultar_sitio(self.path,1,1)
        self.data['crs']='EPSG:3857';self.write()
        with self.assertRaises(ValueError): consultar_sitio(self.path,1,1)

    def test_coordenadas_y_anillos_invalidos(self):
        for coords in ((True,0),(float('nan'),0),(181,0),(0,91)):
            with self.assertRaises(ValueError): consultar_sitio(self.path,*coords)
        self.data['zonas'][0]['geometria']['coordinates'][0].pop(); self.write()
        with self.assertRaises(ValueError): consultar_sitio(self.path,1,1)
