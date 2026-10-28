"""Derivados registrados sintéticos; ninguna prueba usa red, proveedor o ETABS."""
import copy
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from draft2model import revision_preprocesamiento as servicio
from draft2model import preprocesamiento as core
from draft2model.ingreso import registrar_expediente
from draft2model.revision_documental import revisar_expediente


class CasoPreprocesado(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.source = self.root / 'foto.png'
        with Image.new('RGB', (201,129)) as image:
            for y in range(129):
                for x in range(201):
                    image.putpixel((x,y),(x % 256,(2*y) % 256,(x+y) % 256))
            exif = Image.Exif(); exif[274] = 6
            image.save(self.source, exif=exif)
        self.manifest = registrar_expediente('foto-sintetica',[self.source],self.root/'casos',
                                             uso_autorizado=True, provisional_fuera_alcance=True)
        self.case = self.manifest.parent
        self.original = self.case / 'originales/lamina-0001.png'
        self.original_bytes = self.original.read_bytes()
        self.revision = revisar_expediente(self.manifest,max_lado=128)
        self.config = {'rotacion_grados':90,'contraste':1.2,'perspectiva':{
            'esquinas_px':[[15,10],[185,8],[188,115],[10,120]],'dimensiones_salida_px':[160,100]}}

    def publicar(self, config=None):
        return servicio.registrar_preprocesamiento(self.manifest,'L0001',self.config if config is None else config,
            revisor_declarado='Operador SINTÉTICO',motivo='Transformación explícita de prueba de software.')


class RevisionPreprocesamientoTests(CasoPreprocesado):
    def test_publicar_consultar_historial_conserva_original_y_exif_sin_duplicar(self):
        antes = copy.deepcopy(self.config)
        ruta = self.publicar()
        consulta = servicio.consultar_preprocesamiento(self.manifest,ruta.parent.name)
        self.assertEqual(ruta.parent.name,hashlib.sha256(ruta.read_bytes()).hexdigest())
        self.assertEqual(self.config,antes)
        self.assertEqual(consulta['registro']['original_sha256'],hashlib.sha256(self.original_bytes).hexdigest())
        self.assertEqual(consulta['registro']['exif_original']['orientacion_exif'],6)
        self.assertEqual(consulta['registro']['alcance']['estado'],'fuera_mvp_declarado')
        self.assertIsNone(consulta['registro']['escala_metrica'])
        self.assertEqual(consulta['registro']['mejora_precision_vision'],'no_evaluada')
        with Image.open(BytesIO(consulta['imagen_bytes'])) as image:
            self.assertEqual(image.size,(100,160))
            self.assertEqual(image.getexif().get(274,1),1)
        transformacion = consulta['transformacion']
        self.assertFalse(transformacion['exif_aplicado_automaticamente'])
        for punto in ((15,10),(185,8),(188,115),(10,120),(55.5,62.25)):
            salida = core.transformar_punto(transformacion['origen_a_salida'],*punto)
            regreso = core.transformar_punto(transformacion['salida_a_origen'],*salida)
            for a,b in zip(punto,regreso):self.assertAlmostEqual(a,b,places=8)
        otra = self.publicar()
        self.assertNotEqual(ruta,otra)
        self.assertEqual(len(servicio.historial_preprocesamientos(self.manifest,'L0001')),2)
        self.assertEqual(servicio.historial_preprocesamientos(self.manifest,'NO_EXISTE'),[])
        self.assertEqual(self.original.read_bytes(),self.original_bytes)

    def test_rechaza_cada_archivo_modificado_sin_ocultar_historial(self):
        ruta = self.publicar()
        for nombre in servicio.ARCHIVOS:
            archivo = ruta.parent/nombre
            antes = archivo.read_bytes()
            archivo.write_bytes(antes+b'\n')
            try:
                with self.subTest(nombre=nombre),self.assertRaises(ValueError):
                    servicio.consultar_preprocesamiento(self.manifest,ruta.parent.name)
                with self.assertRaises(ValueError):servicio.historial_preprocesamientos(self.manifest)
            finally:archivo.write_bytes(antes)

    def test_reescritura_coherente_config_render_y_hashes_no_reusa_id_publicado(self):
        ruta = self.publicar()
        changed = copy.deepcopy(self.config); changed['contraste'] = 1.8
        rendered = servicio._render(self.original,changed,self.case)
        registro = json.loads(ruta.read_bytes())
        for nombre,campo in (('imagen.png','imagen_sha256'),('config.json','config_sha256'),
                              ('transformacion.json','transformacion_sha256')):
            (ruta.parent/nombre).write_bytes(rendered[nombre])
            registro[campo] = hashlib.sha256(rendered[nombre]).hexdigest()
        ruta.write_bytes(servicio._json(registro))
        with self.assertRaisesRegex(ValueError,'ID de contenido'):
            servicio.consultar_preprocesamiento(self.manifest,ruta.parent.name)

    def test_original_y_expediente_alterados_invalidan_derivado(self):
        ruta = self.publicar()
        for path in (self.original,self.manifest):
            raw = path.read_bytes(); path.write_bytes(raw+b'\n')
            try:
                with self.subTest(path=path.name),self.assertRaises(ValueError):
                    servicio.consultar_preprocesamiento(self.manifest,ruta.parent.name)
            finally:path.write_bytes(raw)

    def test_rechaza_config_tipos_y_caso_sin_publicacion(self):
        for config in ({},[],None,{**self.config,'rotacion_grados':True},
                       {**self.config,'contraste':float('nan')},{**self.config,'extra':1}):
            with self.subTest(config=config),self.assertRaises((ValueError,TypeError)):
                self.publicar(config=config) if config is not None else servicio.registrar_preprocesamiento(
                    self.manifest,'L0001',None,revisor_declarado='R',motivo='M')
        with self.assertRaises(ValueError):
            servicio.registrar_preprocesamiento(self.manifest,'L0002',self.config,revisor_declarado='R',motivo='M')
        with self.assertRaises(ValueError):
            servicio.registrar_preprocesamiento(self.manifest,'L0001',self.config,revisor_declarado='',motivo='M')
        self.assertFalse((self.case/servicio.CARPETA).exists())
        for ident in ('../x',None,True,'0'*32):
            with self.assertRaises(ValueError):servicio.consultar_preprocesamiento(self.manifest,ident)

    def test_cambio_durante_render_se_detecta_antes_publicar(self):
        render = servicio._render
        def cambiado(*args):
            resultado = render(*args)
            self.original.write_bytes(self.original_bytes+b'cambio')
            return resultado
        with patch.object(servicio,'_render',cambiado),self.assertRaises(ValueError):self.publicar()
        self.assertFalse((self.case/servicio.CARPETA).exists())

    def test_directorio_o_enlace_no_se_lee_como_derivado(self):
        ruta = self.publicar(); archivo = ruta.parent/'config.json'
        raw = archivo.read_bytes(); archivo.unlink(); archivo.mkdir()
        try:
            with self.assertRaises(ValueError):servicio.consultar_preprocesamiento(self.manifest,ruta.parent.name)
        finally:archivo.rmdir(); archivo.write_bytes(raw)
        # No depende de privilegios de symlink: también se rechaza explícitamente el bit reparse.
        real = Path.lstat
        def marcado(path,*args,**kwargs):
            info = real(path,*args,**kwargs)
            if path == archivo:
                class Reparse:
                    st_mode = info.st_mode
                    st_file_attributes = 1024
                return Reparse()
            return info
        with patch.object(Path,'lstat',marcado),self.assertRaises(ValueError):
            servicio.consultar_preprocesamiento(self.manifest,ruta.parent.name)
