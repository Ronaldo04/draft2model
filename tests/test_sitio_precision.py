"""Cribado métrico conservador; capas sintéticas sin cartografía ni red."""

import copy
import json
import math
from pathlib import Path
import tempfile
import unittest

from draft2model.sitio import consultar_sitio, huella_capa


def rectangulo(x0, y0, x1, y1):
    return [[x0,y0],[x1,y0],[x1,y1],[x0,y1],[x0,y0]]


class SitioPrecisionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'capa.json'
        self.data={'contrato':'draft2model.capa_sitio','version':'0.1.0','crs':'EPSG:4326',
                   'fuente':{'titulo':'SINTÉTICO','edicion':'prueba','referencia':'Sin valor territorial'},
                   'fecha':'2026-10-18','precision_m':10,'datos_sinteticos':True,
                   'zonas':[{'id':'Z1','etiqueta':'Fixture','geometria':{'type':'Polygon',
                            'coordinates':[rectangulo(0,0,2,2)]}}], 'aprobacion':None}
        self.write()

    def write(self):
        self.data['aprobacion']={'huella':huella_capa(self.data),'revisor_declarado':'Fixture de software',
                                'fecha':'2026-10-18','alcance':'Prueba, no aprobación de ingeniería'}
        self.path.write_text(json.dumps(self.data),encoding='utf-8')

    def estado(self,x,y):
        antes=self.path.read_bytes()
        respuesta=consultar_sitio(self.path,x,y)
        self.assertEqual(antes,self.path.read_bytes())
        self.assertIsNone(respuesta['parametros_geotecnicos'])
        self.assertIsNone(respuesta['capacidad_portante'])
        return respuesta['estado']

    def test_interior_y_fuera_lejanos_conservan_estado(self):
        self.assertEqual(self.estado(1,1),'dentro')
        self.assertEqual(self.estado(-.01,1),'sin_cobertura')
        self.assertEqual(self.estado(3,3),'sin_cobertura')

    def test_ambos_lados_y_borde_son_inciertos(self):
        # Aproximadamente 1 m en el ecuador, muy inferior a los 10 m declarados.
        for x in (-.00001,0.,.00001):
            with self.subTest(x=x):
                self.assertEqual(self.estado(x,1),'limite')
        cercano=consultar_sitio(self.path,-.00001,1)
        self.assertEqual(cercano['zonas'],[{'id':'Z1','etiqueta':'Fixture','posicion':'limite'}])

    def test_vertices_usan_distancia_radial_no_solo_caja(self):
        self.assertEqual(self.estado(-.00001,-.00001),'limite')
        # Cada eje está a menos de 10 m, pero el vértice está a más de 10 m.
        self.assertEqual(self.estado(-.00007,-.00007),'sin_cobertura')

    def test_precision_cambia_resultado_sin_cambiar_geometria(self):
        # ~5.5 m de separación al borde vertical.
        self.data['precision_m']=1;self.write()
        self.assertEqual(self.estado(.00005,1),'dentro')
        self.assertEqual(self.estado(-.00005,1),'sin_cobertura')
        self.data['precision_m']=10;self.write()
        self.assertEqual(self.estado(.00005,1),'limite')
        self.assertEqual(self.estado(-.00005,1),'limite')

    def test_hueco_borde_y_ambos_lados(self):
        self.data['zonas'][0]['geometria']['coordinates'].append(rectangulo(.5,.5,1.5,1.5))
        self.write()
        self.assertEqual(self.estado(1,1),'sin_cobertura')
        for x in (.5-.00001,.5,.5+.00001):
            with self.subTest(x=x):self.assertEqual(self.estado(x,1),'limite')
        self.assertEqual(self.estado(.49,1),'dentro')

    def test_solape_lejano_ambiguo_y_proximo_limite(self):
        otra=copy.deepcopy(self.data['zonas'][0])
        otra['id']='Z2';otra['geometria']['coordinates']=[rectangulo(1,0,3,2)]
        self.data['zonas'].append(otra);self.write()
        self.assertEqual(self.estado(1.5,1),'ambiguo')
        self.assertEqual(self.estado(1+.00001,1),'limite')
        posiciones={z['id']:z['posicion'] for z in consultar_sitio(self.path,1+.00001,1)['zonas']}
        self.assertEqual(posiciones,{'Z1':'dentro','Z2':'limite'})

    def test_escala_longitud_varia_con_latitud(self):
        # Misma separación angular: ~11 m en ecuador y ~6 m a 58 grados.
        self.data['zonas'][0]['geometria']['coordinates']=[rectangulo(0,-.1,.1,.1)]
        self.write();self.assertEqual(self.estado(.0001,0),'dentro')
        self.data['zonas'][0]['geometria']['coordinates']=[rectangulo(0,57.9,.1,58.1)]
        self.write();self.assertEqual(self.estado(.0001,58),'limite')

    def test_umbral_inclusivo_en_ecuador_y_margen_fuera(self):
        self.data['zonas'][0]['geometria']['coordinates']=[rectangulo(0,-.1,.1,.1)]
        self.write()
        # En el ecuador la longitud de arco elipsoidal es a * delta_lambda.
        # No usa los helpers del algoritmo de cribado para fijar la referencia.
        a_wgs84=6378137.
        for metros,esperado in ((9.999,'limite'),(10.,'limite'),(10.001,'dentro')):
            grados=math.degrees(metros/a_wgs84)
            with self.subTest(metros=metros):
                self.assertEqual(self.estado(grados,0),esperado)
                self.assertEqual(self.estado(-grados,0),'limite' if esperado=='limite' else 'sin_cobertura')

    def test_punto_lejano_para_validar_capa_sigue_admitido(self):
        # El servicio de contexto consulta (0,0) para validar una capa registrada.
        self.data['zonas'][0]['geometria']['coordinates']=[rectangulo(-77.2,-12.2,-77.,-12.)]
        self.write();self.assertEqual(self.estado(0,0),'sin_cobertura')

    def test_dominio_latitudes_y_antimeridiano_rechazados(self):
        for y in (60.001,-60.001):
            with self.subTest(latitud=y),self.assertRaisesRegex(ValueError,'latitudes'):
                consultar_sitio(self.path,0,y)
        self.data['zonas'][0]['geometria']['coordinates']=[rectangulo(0,60.1,.1,60.2)]
        self.write()
        with self.assertRaisesRegex(ValueError,'latitudes'):consultar_sitio(self.path,0,0)
        self.data['zonas'][0]['geometria']['coordinates']=[rectangulo(179,0,-179,1)]
        self.write()
        with self.assertRaises(ValueError):consultar_sitio(self.path,179.5,.5)
        self.data['zonas'][0]['geometria']['coordinates']=[rectangulo(179.8,0,179.9,.1)]
        self.write()
        with self.assertRaisesRegex(ValueError,'antimeridiano'):consultar_sitio(self.path,-179.9,0)

    def test_limites_precision_extension_y_numeros_invalidos(self):
        self.data['precision_m']=50_000;self.write()
        self.assertEqual(self.estado(1,1),'dentro')
        for valor in (50_000.001,0,-1,True,float('nan'),float('inf'),10**1000):
            with self.subTest(valor=str(valor)[:30]):
                self.data['precision_m']=valor
                self.path.write_text(json.dumps(self.data),encoding='utf-8')
                with self.assertRaises(ValueError):consultar_sitio(self.path,1,1)
        self.data['precision_m']=10
        self.data['zonas'][0]['geometria']['coordinates']=[rectangulo(0,0,10,10)]
        self.write();self.assertEqual(self.estado(5,5),'dentro')
        self.data['zonas'][0]['geometria']['coordinates']=[rectangulo(0,0,10.001,10)]
        self.write()
        with self.assertRaisesRegex(ValueError,'capa local'):consultar_sitio(self.path,5,5)

    def test_contrato_estados_y_fuentes_sin_campos_nuevos(self):
        result=consultar_sitio(self.path,.00001,1)
        self.assertEqual(set(result),{'contrato','version','ubicacion','estado','zonas','fuente','fecha_fuente',
            'precision_m','datos_sinteticos','sha256_capa','huella_capa','parametros_geotecnicos','capacidad_portante','aviso'})
        self.assertEqual(result['version'],'0.1.0')
        self.assertEqual(result['estado'],'limite')
        self.assertEqual(result['fuente'],self.data['fuente'])
        self.assertEqual(result['precision_m'],10)
        self.assertEqual(result['huella_capa'],huella_capa(self.data))
        self.assertIn('conservadora',result['aviso'])


if __name__=='__main__':unittest.main()
