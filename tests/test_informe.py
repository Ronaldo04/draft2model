"""Informe sintético: datos exactos, citas, aprobación y PDF paginado."""

import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import unicodedata

import pymupdf

from draft2model.informe import (
    crear_informe, validar_informe, aprobar_informe, renderizar_html, exportar_informe, main,
)
from draft2model.evaluacion_estructural import evaluar_resultados
from draft2model.fuentes import huella_corpus
from draft2model.resultados_estructurales import huella_resultados, huella_declaracion

EJEMPLOS = Path(__file__).resolve().parents[1] / "examples"


class InformeTests(unittest.TestCase):
    def test_tablas_con_omisiones_no_desaparecen_tras_salto(self):
        self.contexto['hipotesis']=['Hipótesis de software explícita con datos fabricados y origen revisado. '*2]*5
        self.contexto['faltantes']=['Falta revisión del proyecto real, fuentes normativas, sitio y comparación manual.']*5
        self.resultados['resultados']=[r for r in self.resultados['resultados'] if r['variable']!='periodo']
        self.resultados['resultados'].append({'id':'DY','variable':'deriva','caso':'SX','direccion':'Y',
            'ubicacion':'N1','valor':None,'unidad':'1','motivo_omision':'No existe fila para el selector revisado.'})
        self.resultados['omisiones'].append('DY: No existe fila para el selector revisado.')
        informe=crear_informe(self.resultados,None,self.contexto)
        carpeta=exportar_informe(informe,self.raiz/'omision_salto')
        with pymupdf.open(carpeta/'informe.pdf') as doc:
            text=unicodedata.normalize('NFKC','\n'.join(p.get_text() for p in doc))
        for expected in ('4. Derivas','5. Cortante','6. Advertencias','7. Condición','DY / SX','No existe fila','100.0','Trazabilidad'):
            self.assertIn(expected,text)

    def test_sin_reglas_exporta_pendiente_sin_cumplimiento(self):
        informe=crear_informe(self.resultados,None,self.contexto)
        self.assertTrue(validar_informe(informe))
        self.assertIsNone(informe['reglas'])
        self.assertEqual(informe['evaluacion']['estado'],'pendiente')
        self.assertEqual(informe['evaluacion']['evaluaciones'],[])
        text=renderizar_html(informe)
        self.assertIn('No se declara cumplimiento',text)
        altered=copy.deepcopy(informe);altered['evaluacion']['estado']='evaluado'
        with self.assertRaises(ValueError):validar_informe(altered)

    def setUp(self):
        self.resultados = json.loads((EJEMPLOS/"resultados_estructurales_sinteticos.json").read_text(encoding="utf-8"))
        self.reglas = json.loads((EJEMPLOS/"reglas_estructurales_sinteticas.json").read_text(encoding="utf-8"))
        self.contexto = {"titulo":"Evaluación sísmica sintética: albañilería y precisión",
                         "hipotesis":["Datos fabricados para probar software; sin análisis estructural."],
                         "faltantes":["Modelo manual real no disponible."],"sitio":None}
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raiz = Path(self.tmp.name)

    def crear(self, **kwargs):
        return crear_informe(self.resultados,self.reglas,self.contexto,**kwargs)

    def corpus(self):
        archivo = self.raiz/"fuente.txt"
        texto = "Fuente sintética: los datos fabricados no validan una vivienda."
        archivo.write_text(texto,encoding="utf-8")
        corpus = {"contrato":"draft2model.corpus","version":"0.1.0","datos_sinteticos":True,
                  "documentos":[{"id":"D1","titulo":"Documento de prueba sintético","edicion":"0.1 fabricada",
                                 "archivo":"fuente.txt","sha256":hashlib.sha256(archivo.read_bytes()).hexdigest()}],
                  "fragmentos":[{"id":"F1","documento":"D1","pagina":1,"apartado":"Advertencia","texto":texto}],
                  "aprobacion":None}
        corpus["aprobacion"] = {"huella":huella_corpus(corpus),"revisor_declarado":"Fixture sintética",
                                "fecha":"2026-10-16","alcance":"Solo pruebas; sin valor normativo."}
        manifiesto = self.raiz/"corpus.json"
        manifiesto.write_text(json.dumps(corpus,ensure_ascii=False),encoding="utf-8")
        return manifiesto,[{"fragmento_id":"F1","texto":texto}]

    def test_borrador_independiente_y_cifras_exactas_sin_mutar(self):
        antes = copy.deepcopy([self.resultados,self.reglas,self.contexto])
        informe = self.crear()
        self.assertTrue(validar_informe(informe))
        self.assertEqual(informe["revision"],{"estado":"borrador","aprobacion":None})
        self.assertEqual(informe["siete_resultados"]["periodos"][0]["valor"],.5)
        self.assertEqual(informe["siete_resultados"]["derivas"][0]["valor"],.002)
        self.assertEqual(informe["siete_resultados"]["cortante_basal"][0]["valor"],100.)
        self.assertEqual([self.resultados,self.reglas,self.contexto],antes)
        self.assertEqual(len(informe["siete_resultados"]),7)
        self.assertIsNone(informe["siete_resultados"]["geometria_muros"]["numero_muros"])
        self.assertEqual(informe["siete_resultados"]["estado_modelo_analisis"]["analisis"],"no_disponible")

    def test_evaluacion_ajena_alterada_rechazada(self):
        evaluacion = evaluar_resultados(self.resultados,self.reglas,
            huella_resultados_esperada=huella_resultados(self.resultados),
            huella_reglas_esperada=huella_declaracion(self.reglas))
        self.assertTrue(validar_informe(self.crear(evaluacion=evaluacion)))
        evaluacion["evaluaciones"][0]["valor_evaluado"] = 999
        with self.assertRaises(ValueError):
            self.crear(evaluacion=evaluacion)

    def test_json_y_evaluacion_figurados_no_se_aceptan(self):
        informe = self.crear()
        informe["siete_resultados"]["derivas"][0]["valor"] = 123
        with self.assertRaises(ValueError):
            validar_informe(informe)
        informe = self.crear()
        informe["evaluacion"]["evaluaciones"][0]["valor_evaluado"] = 123
        with self.assertRaises(ValueError):
            exportar_informe(informe,self.raiz/"incorrecto")
        self.assertFalse((self.raiz/"incorrecto").exists())

    def test_aprobacion_propia_y_cambios_invalidan(self):
        borrador = self.crear()
        aprobado = aprobar_informe(borrador,revisor_declarado="Revisor sintético",fecha="2026-10-16",motivo="Prueba documental.")
        self.assertEqual(borrador["revision"]["estado"],"borrador")
        self.assertTrue(validar_informe(aprobado))
        aprobado["contexto"]["titulo"] += " alterado"
        with self.assertRaises(ValueError):
            validar_informe(aprobado)

    def test_fuentes_citas_y_alteracion_actual(self):
        manifiesto,citas = self.corpus()
        informe = self.crear(corpus=manifiesto,citas=citas)
        texto = renderizar_html(informe)
        self.assertIn("Página: 1",texto)
        self.assertIn("0.1 fabricada",texto)
        self.assertIn("Documento de prueba sintético",texto)
        exportar_informe(informe,self.raiz/"con_fuente",corpus=manifiesto)
        (self.raiz/"fuente.txt").write_text("alterada",encoding="utf-8")
        with self.assertRaises(ValueError):
            exportar_informe(informe,self.raiz/"obsoleta",corpus=manifiesto)

    def test_citas_inexistentes_o_sin_corpus_rechazadas(self):
        manifiesto,citas = self.corpus()
        with self.assertRaises(ValueError):
            self.crear(citas=citas)
        with self.assertRaises(ValueError):
            self.crear(corpus=manifiesto,citas=[{"fragmento_id":"fantasma","texto":"falso"}])
        informe = self.crear(corpus=manifiesto,citas=citas)
        informe["fuentes"]["fragmentos"][0]["texto"] += " cifra falsa"
        with self.assertRaises(ValueError):
            validar_informe(informe)

    def test_geometria_hash_real_y_faltantes(self):
        geo = EJEMPLOS/"geometria_sintetica.json"
        self.resultados["geometria"]["sha256"] = hashlib.sha256(geo.read_bytes()).hexdigest()
        informe = self.crear(geometria_archivo=geo)
        self.assertEqual(informe["siete_resultados"]["geometria_muros"]["numero_muros"],4)
        self.assertIn("Espesor no disponible",renderizar_html(informe))
        exportar_informe(informe,self.raiz/"geometria",geometria_archivo=geo)
        with self.assertRaises(ValueError):
            exportar_informe(informe,self.raiz/"sin_archivo")
        self.resultados["geometria"]["sha256"] = "0"*64
        with self.assertRaises(ValueError):
            self.crear(geometria_archivo=geo)

    def test_html_escapado_y_faltante_no_convertido_a_cero(self):
        self.contexto["titulo"] = '<script>alert("x")</script> & prueba'
        self.contexto["hipotesis"] = ['<img src="https://no.example/a" onerror="x">']
        fila = self.resultados["resultados"][1]
        fila.update(valor=None,motivo_omision="No disponible por prueba.")
        informe = self.crear()
        texto = renderizar_html(informe)
        self.assertNotIn("<script>",texto)
        self.assertNotIn("<img ",texto)
        self.assertIn("&lt;script&gt;",texto)
        self.assertIn("No disponible por prueba.",texto)
        self.assertIsNone(informe["siete_resultados"]["derivas"][0]["valor"])
        self.assertEqual(informe["evaluacion"]["evaluaciones"][1]["estado"],"faltante")

    def test_solo_base_es_cortante_basal(self):
        self.resultados["resultados"][2]["ubicacion"] = "N1"
        informe = self.crear()
        self.assertEqual(informe["siete_resultados"]["cortante_basal"],[])
        self.assertEqual(informe["resultados"]["resultados"][2]["valor"],100.)

    def test_pdf_unicode_cifras_paginacion_y_raster(self):
        informe = self.crear()
        carpeta = exportar_informe(informe,self.raiz/"paquete")
        self.assertEqual(json.loads((carpeta/"informe.json").read_text(encoding="utf-8")),informe)
        with pymupdf.open(carpeta/"informe.pdf") as doc:
            texto = "\n".join(p.get_text() for p in doc)
            for esperado in ("Evaluación sísmica","albañilería","SIMULACIÓN","0.5","0.002","100.0","kN",
                             "1. Estado", "2. Geometría", "3. Periodos", "4. Derivas", "5. Cortante", "6. Advertencias", "7. Condición"):
                self.assertIn(esperado,texto)
            for i,pagina in enumerate(doc):
                self.assertIn(f"{i+1} / {len(doc)}",pagina.get_text())
                pix = pagina.get_pixmap(matrix=pymupdf.Matrix(.5,.5))
                self.assertGreater(pix.width,200)
                self.assertGreater(len(pix.samples),100_000)
                for bloque in pagina.get_text("blocks"):
                    self.assertGreaterEqual(bloque[0],0)
                    self.assertLessEqual(bloque[2],pagina.rect.width+1)
                    self.assertLessEqual(bloque[3],pagina.rect.height+1)

    def test_paginas_adicionales_conservan_ultimo_parrafo(self):
        self.contexto["hipotesis"] = [f"Hipótesis sintética {i}: revisión explícita y parámetros pendientes de ingeniería." for i in range(120)]
        carpeta = exportar_informe(self.crear(),self.raiz/"largo")
        with pymupdf.open(carpeta/"informe.pdf") as doc:
            self.assertGreater(len(doc),3)
            texto = "\n".join(p.get_text() for p in doc)
            self.assertIn("Hipótesis sintética 119",texto)
            self.assertIn("Trazabilidad y revisión",texto)

    def test_no_sobrescribe_y_cli(self):
        for nombre,datos in (("resultados",self.resultados),("reglas",self.reglas),("contexto",self.contexto)):
            (self.raiz/f"{nombre}.json").write_text(json.dumps(datos),encoding="utf-8")
        args = []
        for nombre in ("resultados","reglas","contexto"):
            args += ["--"+nombre,str(self.raiz/f"{nombre}.json")]
        salida = self.raiz/"cli"
        args += ["--salida",str(salida)]
        self.assertEqual(main(args),0)
        bytes_pdf = (salida/"informe.pdf").read_bytes()
        self.assertEqual(main(args),1)
        self.assertEqual((salida/"informe.pdf").read_bytes(),bytes_pdf)


if __name__ == "__main__":
    unittest.main()
