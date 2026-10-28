"""Tablas sintéticas v0.2 integradas al ingreso histórico; sin red/ETABS."""
import copy
import csv
import io
import json
from pathlib import Path
import unittest
import zipfile
from xml.sax.saxutils import escape

from draft2model.importacion_tabular import convertir_tablas, ErrorImportacionTabular, main
from draft2model.lectura_xlsx import leer_tablas_xlsx
from draft2model.revision_tabular import ErrorTabular
from draft2model.validacion_geometria import validar_geometria
from tests import test_revision_tabular as soporte
from tests.test_revision_tabular import CASO, NS, REL

NOMBRES = ('niveles', 'nodos', 'muros', 'vertices', 'superficies')
PROCEDENCIA = {'tipo': 'sintetico', 'descripcion': 'Contorno sintético tabular'}


def tabla(headers, rows=()):
    out = io.StringIO(newline=''); writer = csv.writer(out)
    writer.writerow(headers); writer.writerows(rows)
    return out.getvalue()


def fuentes(meta):
    meta = copy.deepcopy(meta)
    meta.update(version_contrato='0.2.0', faltantes=[], procedencia=PROCEDENCIA)
    pro = json.dumps(PROCEDENCIA)
    tablas = {
        'niveles': 'id,cota\n', 'nodos': 'id,x,y\n',
        'muros': 'id,nodo_inicio,nodo_fin,nivel_inferior,nivel_superior,espesor\n',
        'vertices': tabla(['id', 'x', 'y', 'z', 'procedencia'],
                          [('A', 0, 0, 2, pro), ('B', 4, 0, 2, pro), ('C', 4, 3, 2, pro), ('D', 0, 3, 2, pro)]),
        'superficies': tabla(['id', 'vertices', 'papel_geometrico', 'procedencia'],
                             [('S', '["A","B","C","D"]', 'contorno declarado', pro)]),
    }
    return meta, tablas


def xlsx(tablas, formula=False):
    files = {'xl/workbook.xml': f'<workbook xmlns="{NS}" xmlns:r="{REL}"><sheets>' + ''.join(
        f'<sheet name="{n}" sheetId="{i}" r:id="r{i}"/>' for i, n in enumerate(tablas, 1)) + '</sheets></workbook>',
        'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + ''.join(
        f'<Relationship Id="r{i}" Type="{REL}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(tablas)+1)) + '</Relationships>'}
    for i, (name, text) in enumerate(tablas.items(), 1):
        rows = csv.reader(io.StringIO(text))
        files[f'xl/worksheets/sheet{i}.xml'] = f'<worksheet xmlns="{NS}"><sheetData>' + ''.join(
            '<row>' + ''.join(f'<c r="{chr(65+c)}{r}" t="inlineStr"><is><t>{escape(v)}</t></is>' +
            ('<f>1+1</f>' if formula and name == 'vertices' and r == 2 and c == 1 else '') + '</c>'
            for c, v in enumerate(row)) + '</row>' for r, row in enumerate(rows, 1)) + '</sheetData></worksheet>'
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, text in files.items(): z.writestr(name, text)
    return out.getvalue()


class TabularSuperficiesTests(unittest.TestCase):
    setUp = soporte.TabularWebTests.setUp
    body_csv = soporte.TabularWebTests.body_csv
    body_xlsx = soporte.TabularWebTests.body_xlsx
    importar = soporte.TabularWebTests.importar
    versiones_geometria = soporte.TabularWebTests.versiones_geometria

    def datos(self):
        return fuentes(self.meta)

    def registrar(self, meta, tablas):
        return self.service.crear(self.body_csv(meta=meta, archivos={n+'.csv': t.encode() for n, t in tablas.items()}))

    def test_csv_puro_xyz_contorno_sin_fabricar_legacy(self):
        meta, tablas = self.datos(); antes = copy.deepcopy((meta, tablas))
        geometria = convertir_tablas(meta, tablas)
        self.assertEqual((meta, tablas), antes)
        self.assertEqual([geometria[n] for n in NOMBRES[:3]], [[], [], []])
        self.assertEqual(geometria['superficies'][0]['vertices'], ['A', 'B', 'C', 'D'])
        resultado = validar_geometria(geometria)
        self.assertTrue(resultado.consistente)
        self.assertEqual(resultado.derivados_m['superficies']['S']['area_m2'], 12)
        self.assertFalse(resultado.disponible_para_modelado)

    def test_version_explicita_colecciones_exactas(self):
        meta, tablas = self.datos()
        for version in (None, '0.1.0', '0.3.0'):
            m = {**meta, 'version_contrato': version}
            with self.subTest(version=version), self.assertRaises(ErrorImportacionTabular): convertir_tablas(m, tablas)
        for name in NOMBRES:
            with self.subTest(name=name), self.assertRaises(ErrorImportacionTabular):
                convertir_tablas(meta, {n:t for n,t in tablas.items() if n != name})

    def test_anidados_json_estricto_y_contorno_valido(self):
        meta, tablas = self.datos()
        casos = [
            ('superficies', '["A","B","C","D"]', '["A","C","B","D"]'),
            ('superficies', '["A","B","C","D"]', '["A","B","D","D"]'),
            ('superficies', '["A","B","C","D"]', '["A","B","no-existe"]'),
            ('superficies', '["A","B","C","D"]', "['A','B','C']"),
            ('superficies', '["A","B","C","D"]', '["A",NaN,"C"]'),
            ('vertices', json.dumps(PROCEDENCIA), '{"tipo":"sintetico","tipo":"plano","descripcion":"x"}'),
            ('vertices', json.dumps(PROCEDENCIA), '{"tipo":"sintetico","descripcion":Infinity}'),
        ]
        for name, old, new in casos:
            rows = list(csv.reader(io.StringIO(tablas[name])))
            campo = 1 if name == 'superficies' else 4
            rows[1][campo] = new
            with self.subTest(new=new), self.assertRaises(ErrorImportacionTabular):
                convertir_tablas(meta, {**tablas, name: tabla(rows[0], rows[1:])})

    def test_numeros_ids_columnas_formula_y_limite(self):
        meta, tablas = self.datos()
        rows = list(csv.reader(io.StringIO(tablas['vertices'])))
        for valor in ('nan', 'inf', '1e309', '=1+1', 'true'):
            corruptas = copy.deepcopy(rows); corruptas[1][1] = valor
            with self.subTest(valor=valor), self.assertRaises(ErrorImportacionTabular):
                convertir_tablas(meta, {**tablas, 'vertices': tabla(corruptas[0], corruptas[1:])})
        for corruptas in ([rows[0], *rows[1:], rows[1]], [['id','x','y','z','procedencia','extra'], *rows[1:]]):
            with self.assertRaises(ErrorImportacionTabular):
                convertir_tablas(meta, {**tablas, 'vertices': tabla(corruptas[0], corruptas[1:])})
        with self.assertRaises(ErrorImportacionTabular):
            convertir_tablas(meta, {**tablas, 'vertices': 'x'*(4*1024*1024+1)})
        with self.assertRaises(ErrorImportacionTabular):
            convertir_tablas(meta, {**tablas, 'niveles': 'id,cota\n' + '\n'*10000})

    def test_xlsx_cinco_hojas_equivalencia_y_guardas(self):
        meta, tablas = self.datos(); raw = xlsx(tablas)
        self.assertEqual(convertir_tablas(meta, leer_tablas_xlsx(io.BytesIO(raw), colecciones=NOMBRES)), convertir_tablas(meta, tablas))
        with self.assertRaises(ValueError): leer_tablas_xlsx(io.BytesIO(raw))
        for fuente in (xlsx({**tablas, 'extra':'id\n'}), xlsx(tablas, formula=True)):
            with self.assertRaises(ValueError): leer_tablas_xlsx(io.BytesIO(fuente), colecciones=NOMBRES)

    def test_web_bytes_huellas_replay_importacion_separada(self):
        meta, tablas = self.datos()
        a = self.registrar(meta, tablas); raw = xlsx(tablas)
        b = self.service.crear(self.body_xlsx(raw=raw, meta=meta))
        self.assertEqual(a['archivos']['geometria.json'], b['archivos']['geometria.json'])
        self.assertEqual(a['version_contrato'], '0.2.0')
        self.assertEqual((a['resumen']['vertices'], a['resumen']['superficies']), (4, 1))
        self.assertEqual(self.versiones_geometria(), [])
        folder = self.case/'tabulares'/a['id']
        self.assertEqual((folder/'vertices.csv').read_bytes(), tablas['vertices'].encode())
        self.assertEqual((self.case/'tabulares'/b['id']/'libro.xlsx').read_bytes(), raw)
        with self.assertRaises(ErrorTabular): self.importar(a, confirmacion_explicita=False)
        imported = self.importar(a)
        self.assertEqual(imported, self.importar(a))
        self.assertFalse(imported['disponible_para_modelado'])
        self.assertIsNone(imported['aprobacion'])
        # Fuente manipulada aun con checksum de versión coherentemente rehecho.
        stored = json.loads((folder/'version.json').read_text())
        source = (folder/'vertices.csv').read_bytes().replace(b'B,4,0,2', b'B,5,0,2')
        (folder/'vertices.csv').write_bytes(source)
        import hashlib
        stored['archivos']['vertices.csv'] = hashlib.sha256(source).hexdigest()
        (folder/'version.json').write_text(json.dumps(stored))
        with self.assertRaises(ErrorTabular): self.service.consultar(CASO, a['id'], expediente_sha256=self.fp)

    def test_cli_cinco_csv_y_xlsx_misma_salida(self):
        meta, tablas = self.datos(); root = self.case.parent/'entradas'; root.mkdir()
        m = root/'meta.json'; m.write_text(json.dumps(meta), encoding='utf-8')
        args = ['--metadatos', str(m)]
        for n, text in tablas.items():
            p = root/(n+'.csv'); p.write_text(text, encoding='utf-8'); args += ['--'+n, str(p)]
        a=root/'a.json'; b=root/'b.json'; book=root/'tabla.xlsx'; book.write_bytes(xlsx(tablas))
        self.assertEqual(main([*args, '--salida', str(a)]), 0)
        self.assertEqual(main(['--metadatos', str(m), '--xlsx', str(book), '--salida', str(b)]), 0)
        self.assertEqual(a.read_bytes(), b.read_bytes())
        self.assertEqual(main([*args, '--salida', str(a)]), 1)


if __name__ == '__main__': unittest.main()
