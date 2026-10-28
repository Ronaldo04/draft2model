import csv
import io
import json
import re
from pathlib import Path
import tempfile
import unittest
import zipfile
from xml.sax.saxutils import escape
from draft2model.lectura_xlsx import leer_tablas_xlsx
from draft2model.importacion_tabular import convertir_tablas,main

ROOT=Path(__file__).resolve().parents[1]


class XlsxTests(unittest.TestCase):
    def test_texto_compartido_numero_real_y_libro_corrupto(self):
        ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
        self.files['xl/sharedStrings.xml']=f'<sst xmlns="{ns}">\n<si>\n<t>id</t>\n</si>\n</sst>'
        name='xl/worksheets/sheet1.xml'
        self.files[name]=re.sub(r'<c r="A1".*?</c>','<c r="A1" t="s"><v>0</v></c>',self.files[name],count=1)
        self.files[name]=re.sub(r'<c r="C2".*?</c>','<c r="C2"><v>0</v></c>',self.files[name],count=1)
        self.write()
        self.assertTrue(convertir_tablas(self.meta,leer_tablas_xlsx(self.path)))
        self.path.write_bytes(b'no ZIP')
        with self.assertRaises(ValueError):leer_tablas_xlsx(self.path)

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'tablas.xlsx'
        self.meta=json.loads((ROOT/'examples/tabular_sintetico/metadatos.json').read_bytes())
        self.files={};ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';rel='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
        self.files['xl/workbook.xml']=f'<workbook xmlns="{ns}" xmlns:r="{rel}"><sheets>'+''.join(f'<sheet name="{name}" sheetId="{i}" r:id="r{i}"/>' for i,name in enumerate(('niveles','nodos','muros'),1))+'</sheets></workbook>'
        self.files['xl/_rels/workbook.xml.rels']='<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(f'<Relationship Id="r{i}" Type="{rel}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1,4))+'</Relationships>'
        for i,name in enumerate(('niveles','nodos','muros'),1):
            rows=list(csv.reader(io.StringIO((ROOT/f'examples/tabular_sintetico/{name}.csv').read_text(encoding='utf-8'))))
            self.files[f'xl/worksheets/sheet{i}.xml']=f'<worksheet xmlns="{ns}"><sheetData>'+''.join('<row r="'+str(n)+'">'+''.join(f'<c r="{chr(65+c)}{n}" t="inlineStr"><is><t>{escape(value)}</t></is></c>' for c,value in enumerate(row))+'</row>' for n,row in enumerate(rows,1))+'</sheetData></worksheet>'
        self.write()

    def write(self):
        with zipfile.ZipFile(self.path,'w',zipfile.ZIP_DEFLATED) as z:
            for name,text in self.files.items():z.writestr(name,text)

    def test_mismo_contrato_y_cli_sin_sobrescritura(self):
        expected=json.loads((ROOT/'examples/geometria_sintetica.json').read_bytes())
        self.assertEqual(convertir_tablas(self.meta,leer_tablas_xlsx(self.path)),expected)
        output=Path(self.tmp.name)/'salida.json'
        args=['--metadatos',str(ROOT/'examples/tabular_sintetico/metadatos.json'),'--xlsx',str(self.path),'--salida',str(output)]
        self.assertEqual(main(args),0);self.assertEqual(json.loads(output.read_bytes()),expected)
        self.assertEqual(main(args),1)

    def test_formula_hoja_oculta_y_vinculo_externo_rechazados(self):
        original=dict(self.files)
        for change in ('formula','oculta','externa','combinada'):
            self.files=dict(original)
            if change=='formula':self.files['xl/worksheets/sheet1.xml']=self.files['xl/worksheets/sheet1.xml'].replace('<is>','<f>1+1</f><is>',1)
            if change=='oculta':self.files['xl/workbook.xml']=self.files['xl/workbook.xml'].replace('name="niveles"','state="hidden" name="niveles"')
            if change=='externa':self.files['xl/_rels/workbook.xml.rels']=self.files['xl/_rels/workbook.xml.rels'].replace('Id="r1"','TargetMode="External" Id="r1"')
            if change=='combinada':self.files['xl/worksheets/sheet1.xml']=self.files['xl/worksheets/sheet1.xml'].replace('</worksheet>','<mergeCells><mergeCell ref="A1:B1"/></mergeCells></worksheet>')
            self.write()
            with self.subTest(change=change),self.assertRaises(ValueError):leer_tablas_xlsx(self.path)

    def test_hojas_extra_xml_inseguro_y_filas_excedidas(self):
        original=dict(self.files)
        for change in ('hoja','entity','referencia'):
            self.files=dict(original)
            if change=='hoja':self.files['xl/workbook.xml']=self.files['xl/workbook.xml'].replace('name="muros"','name="extra"')
            if change=='entity':self.files['xl/worksheets/sheet1.xml']='<!DOCTYPE x [<!ENTITY x "test">]>'+self.files['xl/worksheets/sheet1.xml']
            if change=='referencia':self.files['xl/worksheets/sheet1.xml']=self.files['xl/worksheets/sheet1.xml'].replace('r="A1"','r="AAA10001"')
            self.write()
            with self.subTest(change=change),self.assertRaises(ValueError):leer_tablas_xlsx(self.path)
