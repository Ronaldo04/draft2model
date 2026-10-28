"""Evidencia con patrones sintéticos; no mide precisión de un proveedor visual."""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from draft2model.preprocesamiento import (
    preparar_transformacion, transformar_punto, procesar_imagen, main,
)


def config(rotacion=0, contraste=1., perspectiva=None):
    return {"rotacion_grados": rotacion, "contraste": contraste, "perspectiva": perspectiva}


def rectificacion(esquinas, dimensiones):
    return {"esquinas_px": esquinas, "dimensiones_salida_px": dimensiones}


class PreprocesamientoTests(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.raiz = Path(self.temporal.name)
        self.original = self.raiz / "original.png"
        imagen = Image.new("RGB", (12, 8))
        for y in range(8):
            for x in range(12):
                imagen.putpixel((x,y), (x*20, y*30, (x+y)*10))
        imagen.save(self.original)
        self.bytes_original = self.original.read_bytes()

    def procesar(self, configuracion):
        carpeta = self.raiz / "salida"
        registro = procesar_imagen(self.original, configuracion, carpeta)
        datos = json.loads(registro.read_text(encoding="utf-8"))
        with Image.open(carpeta / "imagen.png") as img:
            imagen = img.copy()
        return datos, imagen

    def test_identidad_conserva_pixeles_original_y_hashes(self):
        cfg = config()
        antes = copy.deepcopy(cfg)
        registro, salida = self.procesar(cfg)
        with Image.open(self.original) as imagen:
            self.assertEqual(salida.tobytes(), imagen.tobytes())
        self.assertEqual(self.original.read_bytes(), self.bytes_original)
        for archivo, clave in ((self.original,"original_sha256"),
                               (self.raiz / "salida" / "imagen.png","imagen_sha256"),
                               (self.raiz / "salida" / "config.json","config_sha256")):
            self.assertEqual(registro[clave], hashlib.sha256(archivo.read_bytes()).hexdigest())
        self.assertEqual(cfg, antes)
        self.assertIsNone(registro["escala_metrica"])
        self.assertEqual(registro["mejora_precision_vision"], "no_evaluada")

    def test_rotaciones_horarias_pixeles_y_centros_coherentes(self):
        for grados in (0,90,180,270):
            with self.subTest(grados=grados):
                carpeta = self.raiz / str(grados)
                ruta = procesar_imagen(self.original, config(grados), carpeta)
                registro = json.loads(ruta.read_text(encoding="utf-8"))
                with Image.open(self.original) as origen, Image.open(carpeta/"imagen.png") as salida:
                    self.assertEqual(list(salida.size),registro["dimensiones_salida_px"])
                    for x,y in ((0,0),(11,0),(11,7),(0,7),(5,3)):
                        u,v = transformar_punto(registro["origen_a_salida"],x+.5,y+.5)
                        self.assertEqual(salida.getpixel((int(u),int(v))),origen.getpixel((x,y)))
                        xx,yy = transformar_punto(registro["salida_a_origen"],u,v)
                        self.assertAlmostEqual(xx,x+.5)
                        self.assertAlmostEqual(yy,y+.5)

    def test_rectificacion_identidad_pixeles_sin_desfase(self):
        p = rectificacion([[0,0],[12,0],[12,8],[0,8]], [12,8])
        _,salida = self.procesar(config(perspectiva=p))
        with Image.open(self.original) as imagen:
            self.assertEqual(salida.tobytes(),imagen.tobytes())

    def test_rectificacion_recorte_pixeles_conocidos(self):
        p = rectificacion([[2,1],[10,1],[10,7],[2,7]], [8,6])
        datos,salida = self.procesar(config(perspectiva=p))
        with Image.open(self.original) as imagen:
            esperado = imagen.crop((2,1,10,7))
            self.assertEqual(salida.tobytes(),esperado.tobytes())
        u,v = transformar_punto(datos["origen_a_salida"],2,1)
        self.assertAlmostEqual(u,0.)
        self.assertAlmostEqual(v,0.)

    def test_perspectiva_real_y_rotacion_roundtrip_y_patron(self):
        imagen = Image.new("RGB", (120,80))
        for y in range(80):
            for x in range(120):
                imagen.putpixel((x,y), (255 if x<60 else 0,255 if y<40 else 0,0))
        imagen.save(self.original)
        p = rectificacion([[10,5],[110,10],[100,75],[20,70]], [100,60])
        ruta = procesar_imagen(self.original,config(90,perspectiva=p),self.raiz/"perspectiva")
        datos = json.loads(ruta.read_text(encoding="utf-8"))
        with Image.open(self.raiz/"perspectiva"/"imagen.png") as salida:
            for u,v in ((8.5,8.5),(51.5,8.5),(8.5,91.5),(51.5,91.5)):
                x,y = transformar_punto(datos["salida_a_origen"],u,v)
                self.assertEqual(salida.getpixel((int(u),int(v))),imagen.getpixel((int(x),int(y))))
            for u in (0.,10.5,30.5,60.):
                for v in (0.,20.5,50.5,100.):
                    x,y = transformar_punto(datos["salida_a_origen"],u,v)
                    uu,vv = transformar_punto(datos["origen_a_salida"],x,y)
                    self.assertAlmostEqual(u,uu,places=8)
                    self.assertAlmostEqual(v,vv,places=8)

    def test_contraste_es_explicito_y_no_cambia_coordenadas(self):
        datos,salida = self.procesar(config(contraste=2.))
        with Image.open(self.original) as imagen:
            self.assertNotEqual(salida.tobytes(),imagen.tobytes())
        self.assertEqual(transformar_punto(datos["origen_a_salida"],3,4),(3.,4.))

    def test_esquinas_invalidas_rechazadas_antes_crear_salida(self):
        casos = [
            [[0,0],[12,0],[12,8],[12,8]],
            [[0,0],[12,8],[12,0],[0,8]],
            [[0,0],[0,8],[12,8],[12,0]],
            [[0,0],[12,0],[5,2],[0,8]],
            [[-1,0],[12,0],[12,8],[0,8]],
            [[0,0],[12,0],[12,float("nan")],[0,8]],
            [[0,0],[12,0],[12,0.00000000001],[0,0.00000000001]],
            [[0,0],[12,0],[12,8]],
        ]
        for puntos in casos:
            with self.subTest(puntos=puntos),self.assertRaises(ValueError):
                procesar_imagen(self.original,config(perspectiva=rectificacion(puntos,[12,8])),self.raiz/"invalida")
            self.assertFalse((self.raiz/"invalida").exists())
        self.assertEqual(self.original.read_bytes(),self.bytes_original)

    def test_config_numeros_y_recursos_invalidos(self):
        for cfg in (config(45),config(True),config(90.),config(contraste=0),
                    config(contraste=float("inf")),config(contraste=True),
                    config(contraste=10**1000),dict(config(),extra=1)):
            with self.subTest(config=str(cfg)[:90]),self.assertRaises(ValueError):
                preparar_transformacion([12,8],cfg)
        for dims in ([1,8],[16001,2],[5000,5000],[True,8],[12,float("nan")]):
            with self.subTest(dims=dims),self.assertRaises(ValueError):
                preparar_transformacion(dims,config())
        with self.assertRaises(ValueError):
            preparar_transformacion([12,8],config(perspectiva=rectificacion([[0,0],[12,0],[12,8],[0,8]],[5000,5000])))

    def test_limite_bytes_y_salida_existente(self):
        with patch("draft2model.preprocesamiento.MAX_BYTES",10),self.assertRaises(ValueError):
            procesar_imagen(self.original,config(),self.raiz/"no_creada")
        self.assertFalse((self.raiz/"no_creada").exists())
        carpeta = self.raiz/"existe"
        carpeta.mkdir()
        (carpeta/"conservar.txt").write_bytes(b"intacto")
        with self.assertRaises(ValueError):
            procesar_imagen(self.original,config(),carpeta)
        self.assertEqual((carpeta/"conservar.txt").read_bytes(),b"intacto")

    def test_cli_y_config_duplicada(self):
        archivo = self.raiz/"config.json"
        archivo.write_text(json.dumps(config(90)),encoding="utf-8")
        args = ["--entrada",str(self.original),"--config",str(archivo),"--salida",str(self.raiz/"cli")]
        self.assertEqual(main(args),0)
        self.assertEqual(main(args),1)
        archivo.write_text('{"contraste":1,"contraste":2}',encoding="utf-8")
        args[-1] = str(self.raiz/"duplicada")
        self.assertEqual(main(args),1)
        self.assertFalse((self.raiz/"duplicada").exists())

    def test_formato_no_soportado_y_archivo_danado(self):
        gif = self.raiz/"imagen.gif"
        Image.new("RGB",(12,8)).save(gif)
        danado = self.raiz/"danado.png"
        danado.write_bytes(b"PNG incompleto")
        for origen in (gif,danado):
            with self.subTest(origen=origen),self.assertRaises((ValueError,OSError)):
                procesar_imagen(origen,config(),self.raiz/"no_creada")
            self.assertFalse((self.raiz/"no_creada").exists())

    def test_jpeg_y_exif_no_automatico(self):
        jpeg = self.raiz/"foto.jpg"
        exif = Image.Exif()
        exif[274] = 6
        with Image.open(self.original) as imagen:
            imagen.save(jpeg,exif=exif)
        ruta = procesar_imagen(jpeg,config(),self.raiz/"jpeg")
        registro = json.loads(ruta.read_text(encoding="utf-8"))
        self.assertEqual(registro["exif_orientacion_original"],6)
        self.assertFalse(registro["exif_aplicado_automaticamente"])
        self.assertEqual(registro["dimensiones_salida_px"],[12,8])


if __name__ == "__main__":
    unittest.main()
