"""Paquete visual de perspectiva/contraste con evidencia en el ORIGINAL EXIF."""
import copy
import hashlib
import json
from unittest.mock import patch
from tests.respuesta_vision_semantica import respuesta as respuesta_vision

from draft2model import entrada_vision as v
from draft2model import recortes as r
from draft2model import revision_preprocesamiento as servicio
from draft2model.preprocesamiento import transformar_punto
from draft2model.extraccion_preliminar import validar_extraccion
from tests.test_revision_preprocesamiento import CasoPreprocesado


class RecortesPreprocesadosTests(CasoPreprocesado):
    def recorte(self):
        registro = self.publicar()
        crop = r.generar_recorte(self.manifest,'L0001',1,[.12,.15,.88,.82],
                                 preprocesamiento_id=registro.parent.name)
        return registro,crop

    def paquete(self):
        registro,crop = self.recorte()
        return registro,crop,v.preparar_paquete(self.manifest,self.revision,[crop])

    def test_recorte_y_homografia_compuesta_ida_vuelta(self):
        registro,crop = self.recorte(); meta = json.loads(crop.read_bytes())
        self.assertEqual(meta['tipo_fuente'],'raster_preprocesado')
        self.assertEqual(meta['preprocesamiento_id'],registro.parent.name)
        self.assertEqual(meta['pagina_visible_px'],[129,201])
        self.assertEqual(meta['dimensiones_derivado_px'],[100,160])
        self.assertNotEqual(meta['bbox_normalizada'],meta['bbox_derivado_normalizada'])
        consulta = servicio.consultar_preprocesamiento(self.manifest,registro.parent.name)
        a,b,c,d,e,f = consulta['registro']['exif_original']['original_a_pagina_visible_px']
        for x,y in ((0,0),tuple(meta['dimensiones_px']),(15.25,22.75)):
            px,py = r.punto_a_pagina(meta,x,y)
            volver = transformar_punto(meta['pagina_visible_a_pixel'],px,py)
            self.assertAlmostEqual(volver[0],x,places=8); self.assertAlmostEqual(volver[1],y,places=8)
            aa,bb,cc,dd,ee,ff = meta['pixel_a_derivado_px']
            rawx,rawy = transformar_punto(consulta['transformacion']['salida_a_origen'],aa*x+cc*y+ee,bb*x+dd*y+ff)
            self.assertAlmostEqual(px,a*rawx+c*rawy+e,places=8)
            self.assertAlmostEqual(py,b*rawx+d*rawy+f,places=8)
        self.assertEqual(self.original.read_bytes(),self.original_bytes)

    def test_paquete_y_respuesta_mapean_cuatro_esquinas_al_original(self):
        registro,crop,path = self.paquete()
        req,sha,_,_ = v.cargar_paquete(self.manifest,path)
        imagen = next(i for i in req['imagenes'] if i['rol']=='recorte')
        self.assertEqual(imagen['tipo_fuente'],'raster_preprocesado')
        self.assertEqual(imagen['preprocesamiento_id'],registro.parent.name)
        for nombre in servicio.ARCHIVOS:
            ruta = (registro.parent/nombre).relative_to(self.case).as_posix()
            self.assertTrue(any(f['ruta']==ruta for f in req['fuentes']))
        response = respuesta_vision(req, sha, [{'id':'C001','tipo':'cota',
            'valor_propuesto':None,'unidad':'desconocida','evidencia':[{'imagen_id':imagen['id'],
            'bbox_imagen_normalizada':[.1,.2,.7,.8]}]}])
        salida = v.adaptar_respuesta(self.manifest,path,response,proveedor='local',modelo='sintetico',modo_prueba=True)
        candidate = salida['candidatos'][0]
        self.assertEqual(candidate['revision'],{'estado':'pendiente','historial':[]})
        self.assertTrue(validar_extraccion(salida).consistente)
        w,h = imagen['dimensiones_px']; pw,ph = imagen['pagina_visible_px']
        puntos = [r.punto_a_pagina(imagen,x*w,y*h) for x,y in ((.1,.2),(.7,.2),(.7,.8),(.1,.8))]
        expected = [min(x for x,y in puntos)/pw,min(y for x,y in puntos)/ph,
                    max(x for x,y in puntos)/pw,max(y for x,y in puntos)/ph]
        self.assertEqual(candidate['evidencia'][0]['bbox_normalizada'],expected)
        self.assertEqual(candidate['evidencia'][0]['original_sha256'],hashlib.sha256(self.original_bytes).hexdigest())

    def test_derivado_transformacion_o_crop_alterados_rechazados(self):
        registro,crop,path = self.paquete()
        for archivo in (registro.parent/'config.json',registro.parent/'imagen.png',
                        registro.parent/'transformacion.json',crop.parent/'recorte.png'):
            raw = archivo.read_bytes(); archivo.write_bytes(raw+b'\n')
            try:
                with self.subTest(archivo=archivo.name),self.assertRaises((ValueError,OSError)):
                    v.cargar_paquete(self.manifest,path)
            finally:archivo.write_bytes(raw)
        meta = json.loads(crop.read_bytes()); meta['pixel_a_pagina_visible'][0][0] += 1
        crop.write_bytes(v._json(meta))
        with self.assertRaises(ValueError):v.preparar_paquete(self.manifest,self.revision,[crop])

    def test_solicitud_coherentemente_rehashada_no_sustituye_transformacion_publicada(self):
        _,_,path = self.paquete()
        req = json.loads(path.read_bytes())
        req['imagenes'][1]['pixel_a_pagina_visible'][0][0] += 1
        path.write_bytes(v._json(req))
        integridad = json.loads((path.parent/'integridad.json').read_bytes())
        integridad['solicitud_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
        (path.parent/'integridad.json').write_bytes(v._json(integridad))
        with self.assertRaises(ValueError):v.cargar_paquete(self.manifest,path)

    def test_cambios_de_fuente_al_preparar_o_cargar_no_se_aceptan(self):
        registro,crop = self.recorte()
        verificar = v._verificar_render
        def cambiado(*args,**kwargs):
            result = verificar(*args,**kwargs)
            if kwargs.get('recorte'):
                archivo = registro.parent/'config.json'
                archivo.write_bytes(archivo.read_bytes()+b'\n')
            return result
        with patch.object(v,'_verificar_render',cambiado),self.assertRaises(ValueError):
            v.preparar_paquete(self.manifest,self.revision,[crop])

    def test_cambio_durante_recorte_se_detecta_antes_de_devolverlo(self):
        registro = self.publicar()
        renderizar = r._renderizar_imagen_raster
        def cambiado(*args,**kwargs):
            resultado = renderizar(*args,**kwargs)
            archivo = registro.parent/'config.json'
            archivo.write_bytes(archivo.read_bytes()+b'\n')
            return resultado
        with patch.object(r,'_renderizar_imagen_raster',cambiado),self.assertRaises(ValueError):
            r.generar_recorte(self.manifest,'L0001',1,[.1,.1,.7,.8],preprocesamiento_id=registro.parent.name)

    def test_cambio_durante_publicacion_paquete_no_se_presenta_como_exito(self):
        registro,crop = self.recorte()
        publicar = v._publish
        def cambiado(*args,**kwargs):
            resultado = publicar(*args,**kwargs)
            archivo = registro.parent/'config.json'
            archivo.write_bytes(archivo.read_bytes()+b'\n')
            return resultado
        with patch.object(v,'_publish',cambiado),self.assertRaises(ValueError):
            v.preparar_paquete(self.manifest,self.revision,[crop])

    def test_recortes_original_y_derivado_pueden_compartir_contexto(self):
        _,crop = self.recorte()
        original_crop = r.generar_recorte(self.manifest,'L0001',1,[.1,.1,.5,.5])
        path = v.preparar_paquete(self.manifest,self.revision,[original_crop,crop])
        req,_,_,_ = v.cargar_paquete(self.manifest,path)
        self.assertEqual([i['rol'] for i in req['imagenes']],['contexto','recorte','recorte'])
        self.assertEqual(req['imagenes'][1]['tipo_fuente'],'raster')
        self.assertEqual(req['imagenes'][2]['tipo_fuente'],'raster_preprocesado')
