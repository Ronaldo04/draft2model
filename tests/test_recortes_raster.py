"""Originales raster sintéticos: EXIF, recortes verificables y adaptación pendiente sin red."""
import copy
from io import BytesIO
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tests.respuesta_vision_semantica import respuesta as respuesta_vision

from PIL import Image, ImageDraw, ImageOps

from draft2model import recortes as r
from draft2model import entrada_vision as v
from draft2model.ingreso import registrar_expediente, file_hash
from draft2model.revision_documental import revisar_expediente
from draft2model.extraccion_preliminar import validar_extraccion


class RecortesRasterTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def case(self, orientation=6, fmt='PNG', name=None):
        source = self.root/(name or f'raster-{fmt}-{orientation}')
        source = source.with_suffix('.png' if fmt == 'PNG' else '.jpg')
        image = Image.new('RGB',(201,129),'white'); draw = ImageDraw.Draw(image)
        draw.rectangle((0,0,100,64),fill='red'); draw.rectangle((101,0,200,64),fill='green')
        draw.rectangle((0,65,100,128),fill='blue'); draw.rectangle((101,65,200,128),fill='yellow')
        exif = Image.Exif(); exif[274] = orientation
        image.save(source,format=fmt,exif=exif,dpi=(300,300)); image.close()
        manifest = registrar_expediente(source.stem,[source],self.root/'casos',uso_autorizado=True,
            provisional_fuera_alcance=True)
        revision = revisar_expediente(manifest,max_lado=128)
        crop = r.generar_recorte(manifest,'L0001',1,[.173,.217,.811,.783])
        return source, manifest, revision, crop

    def package(self, data):
        return v.preparar_paquete(data[1],data[2],[data[3]])

    def response(self, manifest, request):
        req, sha, _, _ = v.cargar_paquete(manifest,request)
        return respuesta_vision(req, sha, [{'id':'C001','tipo':'cota',
            'valor_propuesto':None,'unidad':'desconocida','evidencia':[{'imagen_id':'REC0001',
                'bbox_imagen_normalizada':[.1,.2,.6,.8]}]}])

    def rewrite_request(self, path, request):
        path.write_bytes(v._json(request))
        integrity = json.loads((path.parent/'integridad.json').read_bytes())
        integrity['solicitud_sha256'] = file_hash(path)
        (path.parent/'integridad.json').write_bytes(v._json(integrity))

    def test_png_jpeg_ocho_orientaciones_coinciden_con_vista_y_matrices_reversibles(self):
        for fmt in ('PNG','JPEG'):
            for orientation in range(1,9):
                with self.subTest(fmt=fmt,orientation=orientation):
                    data = self.case(orientation,fmt); source, manifest, _, crop = data
                    digest = file_hash(source); meta = json.loads(crop.read_bytes())
                    with Image.open(source) as raw:
                        visible = ImageOps.exif_transpose(raw).convert('RGB')
                    box = meta['bbox_pagina_visible_px']
                    with Image.open(crop.parent/'recorte.png') as actual:
                        expected = visible.crop(box)
                        self.assertEqual(actual.size,expected.size); self.assertEqual(actual.tobytes(),expected.tobytes())
                        expected.close()
                    self.assertEqual(meta['pagina_visible_px'],list(visible.size)); visible.close()
                    self.assertNotIn('pagina_visible_pt',meta); self.assertNotIn('dpi_render_aproximado',meta)
                    self.assertEqual(meta['espacio_pagina_visible'],r.ESPACIO_RASTER)
                    self.assertIsNone(meta['escala_geometrica'])
                    forward, backward = meta['original_a_pagina_visible_px'],meta['pagina_visible_a_original_px']
                    def point(matrix,x,y):
                        a,b,c,d,e,f = matrix; return a*x+c*y+e,b*x+d*y+f
                    for x,y in ((0,0),(201,129),(33.25,77.75)):
                        final = point(backward,*point(forward,x,y))
                        self.assertAlmostEqual(final[0],x); self.assertAlmostEqual(final[1],y)
                    with Image.open(source) as raw:
                        pixels = raw.convert('RGB'); shown = ImageOps.exif_transpose(raw).convert('RGB')
                        for x,y in ((20,20),(160,20),(20,100),(160,100)):
                            vx,vy = point(forward,x+.5,y+.5)
                            self.assertEqual(shown.getpixel((math.floor(vx),math.floor(vy))),pixels.getpixel((x,y)))
                        pixels.close(); shown.close()
                    request = self.package(data); req,_,_,_ = v.cargar_paquete(manifest,request)
                    self.assertEqual(req['sistema_coordenadas_salida'],v.COORDENADAS)
                    self.assertEqual(req['imagenes'][1]['pagina_visible_px'],meta['pagina_visible_px'])
                    self.assertEqual(file_hash(source),digest)

    def test_respuesta_pendiente_mapea_bordes_reales_no_interpolacion_del_bbox(self):
        data = self.case(); request = self.package(data); meta = json.loads(data[3].read_bytes())
        response = self.response(data[1],request)
        adapted = v.adaptar_respuesta(data[1],request,response,proveedor='doble-local',modelo='sintetico',modo_prueba=True)
        candidate = adapted['candidatos'][0]; actual = candidate['evidencia'][0]['bbox_normalizada']
        width,height = meta['dimensiones_px']; page_w,page_h = meta['pagina_visible_px']
        left,top = r.punto_a_pagina(meta,.1*width,.2*height)
        right,bottom = r.punto_a_pagina(meta,.6*width,.8*height)
        self.assertEqual(actual,[left/page_w,top/page_h,right/page_w,bottom/page_h])
        self.assertNotAlmostEqual(actual[0],.173+.1*(.811-.173),places=6)
        self.assertEqual(candidate['revision'],{'estado':'pendiente','historial':[]})
        self.assertIsNone(candidate['valor_propuesto']); self.assertEqual(candidate['unidad'],'desconocida')
        self.assertTrue(validar_extraccion(adapted).consistente)
        raw = self.root/'respuesta.json'; raw.write_bytes(v._json(response))
        stored = v.registrar_respuesta(data[1],request,raw,proveedor='doble-local',modelo='sintetico',modo_prueba=True)
        self.assertEqual(json.loads(stored.read_bytes()),adapted)
        self.assertEqual((stored.parent/'respuesta_original.json').read_bytes(),raw.read_bytes())
        self.assertIsNone(json.loads((stored.parent/'registro.json').read_bytes())['aprobacion_ingenieria'])

    def test_contexto_con_dimensiones_redondeadas_y_sin_exif(self):
        data = self.case(1); report = json.loads(data[2].read_bytes())
        page = report['documentos'][0]['paginas'][0]
        self.assertEqual([page['ancho_preview_px'],page['alto_preview_px']],[128,82])
        self.package(data)

    def test_metadatos_exif_matriz_puntos_pdf_o_dimensiones_mezclados_rechazados(self):
        data = self.case(); original = json.loads(data[3].read_bytes())
        changes = [lambda m:m.update(orientacion_exif=1),
            lambda m:m['pixel_a_pagina_visible'].__setitem__(4,0),
            lambda m:m['original_a_pagina_visible_px'].__setitem__(0,9),
            lambda m:m['original_a_pagina_visible_px'].__setitem__(0,False),
            lambda m:m['pagina_visible_a_original_px'].__setitem__(4,1),
            lambda m:m.update(pagina_visible_pt=m['pagina_visible_px']),
            lambda m:m.update(pagina_visible_px=[201,129]),
            lambda m:m.update(tipo_fuente='pdf'),
            lambda m:m.update(espacio_pagina_visible='pdf_pt'),
            lambda m:m.update(dimensiones_original_px=[129,201])]
        for change in changes:
            changed = copy.deepcopy(original); change(changed); data[3].write_bytes(v._json(changed))
            with self.subTest(meta=changed),self.assertRaises((v.ErrorVision,ValueError)):self.package(data)
        self.assertFalse((data[1].parent/'vision').exists())

    def test_preview_imagen_y_original_alterados_se_rechazan(self):
        data = self.case(); request = self.package(data)
        report = json.loads(data[2].read_bytes()); preview = data[1].parent/report['documentos'][0]['paginas'][0]['vista_previa']
        for target in (preview,data[3].parent/'recorte.png',data[1].parent/'originales/lamina-0001.png'):
            original = target.read_bytes(); target.write_bytes(original+b'ALTERADO')
            with self.subTest(path=target.name),self.assertRaises((ValueError,OSError)):v.cargar_paquete(data[1],request)
            target.write_bytes(original)
        with Image.open(preview) as image:Image.new('RGB',image.size,'white').save(preview)
        with self.assertRaises(v.ErrorVision):self.package(data)

    def test_registro_documental_exif_o_dpi_mezclado_rechazado(self):
        data = self.case(); original = json.loads(data[2].read_bytes())
        for extra in ({'orientacion_exif':1},{'dimensiones_original_px':[129,201]},
                {'dpi_declarado':[72,72]},{'ancho_puntos':129}):
            changed = copy.deepcopy(original); changed['documentos'][0]['paginas'][0].update(extra)
            data[2].write_bytes(v._json(changed))
            with self.subTest(extra=extra),self.assertRaises(v.ErrorVision):self.package(data)

    def test_solicitud_transformacion_alterada_rehashada_rechazada_al_cargar(self):
        data = self.case(); request = self.package(data); original = json.loads(request.read_bytes())
        for update in (lambda req:req['imagenes'][1]['pixel_a_pagina_visible'].__setitem__(4,0),
                lambda req:req['imagenes'][1].update(pagina_visible_pt=[129,201]),
                lambda req:req['recortes'][0].update(orientacion_exif=1),
                lambda req:req['revision_documental']['documentos'][0]['paginas'][0].update(orientacion_exif=1)):
            changed = copy.deepcopy(original); update(changed); self.rewrite_request(request,changed)
            with self.subTest(update=update),self.assertRaises(v.ErrorVision):v.cargar_paquete(data[1],request)

    def test_pagina_unica_limites_exif_invalido_y_sin_sobrescribir(self):
        data = self.case(); manifest = data[1]; previous = {p:p.read_bytes() for p in data[3].parent.iterdir()}
        for page in (0,2,True):
            with self.subTest(page=page),self.assertRaises(ValueError):r.generar_recorte(manifest,'L0001',page,[0,0,1,1])
        for bbox in ([0,0,0,1],[0,0,math.inf,1],[-.1,0,1,1],[0,False,1,1]):
            with self.subTest(bbox=bbox),self.assertRaises(ValueError):r.generar_recorte(manifest,'L0001',1,bbox)
        second = r.generar_recorte(manifest,'L0001',1,[.173,.217,.811,.783],dpi=72)
        self.assertNotEqual(second,data[3]); self.assertEqual(previous,{p:p.read_bytes() for p in data[3].parent.iterdir()})
        with patch.object(r,'MAX_BYTES_RASTER',16),self.assertRaises(ValueError):r.cargar_raster_orientado(data[0])
        with patch.object(r,'MAX_PIXELES_RASTER',100),self.assertRaises(ValueError):r.cargar_raster_orientado(data[0])
        with patch.object(r,'MAX_PIXELES_RECORTE',1000):
            raw,meta = r.renderizar_recorte_raster(data[0],[0,0,1,1])
            with Image.open(BytesIO(raw)) as image:self.assertLessEqual(image.width*image.height,1000)
            self.assertGreater(meta['pixel_a_pagina_visible'][0],1)

    def test_exif_invalido_y_png_animado_no_crean_recorte(self):
        for animated in (False,True):
            source = self.root/('animado.png' if animated else 'exif-invalido.jpg')
            image = Image.new('RGB',(20,10),'red')
            if animated:image.save(source,save_all=True,append_images=[Image.new('RGB',(20,10),'blue')],duration=100)
            else:
                exif = Image.Exif(); exif[274] = 9; image.save(source,exif=exif)
            manifest = registrar_expediente(source.stem,[source],self.root/'casos',uso_autorizado=True)
            with self.subTest(animated=animated),self.assertRaises(ValueError):r.generar_recorte(manifest,'L0001',1,[0,0,1,1])
            self.assertFalse((manifest.parent/'recortes').exists())

    def test_mezclar_otra_fuente_de_igual_tamano_no_se_acepta(self):
        one = self.case(6,name='uno'); other = self.case(8,name='otro')
        # Poner PNG + metadatos de otro original no convierte el hash ajeno en evidencia del primero.
        original = json.loads(one[3].read_bytes()); foreign = json.loads(other[3].read_bytes())
        for key in ('orientacion_exif','original_a_pagina_visible_px','pagina_visible_a_original_px','imagen_sha256'):
            original[key] = foreign[key]
        (one[3].parent/'recorte.png').write_bytes((other[3].parent/'recorte.png').read_bytes())
        one[3].write_bytes(v._json(original))
        with self.assertRaises(v.ErrorVision):self.package(one)

    def test_presupuesto_reduccion_en_imagen_muy_estrecha(self):
        source = self.root/'estrecha.png'; Image.new('RGB',(1,1001),'white').save(source)
        with patch.object(r,'MAX_PIXELES_RECORTE',100):
            raw,meta = r.renderizar_recorte_raster(source,[0,0,1,1])
        self.assertEqual(meta['dimensiones_px'],[1,100])
        with Image.open(BytesIO(raw)) as image:self.assertEqual(image.size,(1,100))

    def test_cambios_durante_preparacion_y_carga_rechazados(self):
        data = self.case(); real = v._verificar_render; changed = []
        def alter_metadata(*args,**kwargs):
            result = real(*args,**kwargs)
            if not changed:
                changed.append(1); data[3].write_bytes(data[3].read_bytes()+b' ')
            return result
        with patch.object(v,'_verificar_render',side_effect=alter_metadata):
            with self.assertRaises(v.ErrorVision):self.package(data)
        self.assertFalse((data[1].parent/'vision').exists())
        # Restaurar bytes canónicos y crear un paquete nuevo para cada artefacto.
        crop = json.loads(data[3].read_bytes()); data[3].write_bytes(v._json(crop))
        for artifact in ('integridad.json','prompt.txt','imagen'):
            request = self.package(data); req = json.loads(request.read_bytes())
            target = request.parent/req['imagenes'][1]['ruta'] if artifact == 'imagen' else request.parent/artifact
            real_validate = v._verificar_geometria_paquete
            def alter_copy(*args):
                result = real_validate(*args); target.write_bytes(target.read_bytes()+b' '); return result
            with self.subTest(artifact=artifact),patch.object(v,'_verificar_geometria_paquete',side_effect=alter_copy):
                with self.assertRaises(v.ErrorVision):v.cargar_paquete(data[1],request)


if __name__ == '__main__':unittest.main()
