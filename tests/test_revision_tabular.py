"""Contingencia tabular web CSV/XLSX con datos sintéticos; sin red, procesos, API ni ETABS."""
import base64
import csv
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import zipfile
from xml.sax.saxutils import escape

import pymupdf

from draft2model import gestion_geometria as g
from draft2model.ingreso import registrar_expediente
from draft2model.revision_tabular import ErrorTabular, ServicioTabular
from draft2model.revision_visual import RevisionLocal

ROOT = Path(__file__).resolve().parents[1]
EJEMPLO = ROOT/'examples'/'tabular_sintetico'
CASO = 'tabular-sintetico'
NS = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
REL = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def libro(modificar=None):
    """XLSX mínimo con las tres hojas del ejemplo, celdas de texto en línea."""
    files = {'xl/workbook.xml': f'<workbook xmlns="{NS}" xmlns:r="{REL}"><sheets>' + ''.join(
                f'<sheet name="{n}" sheetId="{i}" r:id="r{i}"/>' for i, n in enumerate(('niveles', 'nodos', 'muros'), 1)) + '</sheets></workbook>',
             'xl/_rels/workbook.xml.rels': '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + ''.join(
                f'<Relationship Id="r{i}" Type="{REL}/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, 4)) + '</Relationships>'}
    for i, name in enumerate(('niveles', 'nodos', 'muros'), 1):
        rows = list(csv.reader(io.StringIO((EJEMPLO/f'{name}.csv').read_text(encoding='utf-8'))))
        files[f'xl/worksheets/sheet{i}.xml'] = f'<worksheet xmlns="{NS}"><sheetData>' + ''.join(
            '<row r="'+str(n)+'">' + ''.join(f'<c r="{chr(65+c)}{n}" t="inlineStr"><is><t>{escape(v)}</t></is></c>' for c, v in enumerate(row))
            + '</row>' for n, row in enumerate(rows, 1)) + '</sheetData></worksheet>'
    if modificar:
        modificar(files)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as z:
        for name, text in files.items():
            z.writestr(name, text)
    return buffer.getvalue()


def reemplazar(files, name, old, new):
    assert old in files[name], old
    files[name] = files[name].replace(old, new, 1)


def b64(raw):
    return base64.b64encode(raw).decode()


class TabularWebTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup); root = Path(tmp.name).resolve()
        for caso in (CASO, 'otro-caso'):
            pdf = root/(caso+'.pdf')
            with pymupdf.open() as doc:
                doc.new_page(width=200, height=120).insert_text((40, 50), 'SINTETICO'); doc.save(pdf)
            registrar_expediente(caso, [pdf], root/'casos', uso_autorizado=True, provisional_fuera_alcance=True)
        self.app = RevisionLocal(root/'casos'); self.service = ServicioTabular(self.app)
        self.fp = self.app.expediente(CASO)[2]; self.case = self.app.raiz/CASO
        self.meta = json.loads((EJEMPLO/'metadatos.json').read_text(encoding='utf-8')); self.meta['id'] = CASO
        self.csv = {n+'.csv': (EJEMPLO/f'{n}.csv').read_bytes() for n in ('niveles', 'nodos', 'muros')}
        for target in ('subprocess.Popen', 'urllib.request.urlopen', 'socket.create_connection'):
            guard = patch(target, side_effect=AssertionError('Sin red ni procesos')); guard.start(); self.addCleanup(guard.stop)

    def body_csv(self, meta=None, archivos=None, **cambios):
        files = archivos if archivos is not None else self.csv
        return {'caso': CASO, 'expediente_sha256': self.fp, 'metadatos_json': json.dumps(meta or self.meta), 'formato': 'csv',
                'archivos': [{'nombre': n, 'contenido_base64': b64(r)} for n, r in files.items()], **cambios}

    def body_xlsx(self, raw=None, nombre='planilla.xlsx', meta=None):
        return {'caso': CASO, 'expediente_sha256': self.fp, 'metadatos_json': json.dumps(meta or self.meta), 'formato': 'xlsx',
                'archivos': [{'nombre': nombre, 'contenido_base64': b64(raw if raw is not None else libro())}]}

    def importar(self, item, **cambios):
        return self.service.importar({'caso': CASO, 'expediente_sha256': self.fp, 'version': item['id'],
                                      'huella_tabular': item['huella_tabular'], 'confirmacion_explicita': True, **cambios})

    def versiones_geometria(self):
        base = self.case/'geometrias'
        return sorted(p.name for p in base.iterdir() if len(p.name) == 32) if base.is_dir() else []

    def test_csv_y_xlsx_equivalentes_al_mismo_contrato(self):
        original_xlsx = libro()
        a = self.service.crear(self.body_csv()); b = self.service.crear(self.body_xlsx(raw=original_xlsx))
        self.assertEqual(a['archivos']['geometria.json'], b['archivos']['geometria.json'])
        esperado = json.loads((ROOT/'examples/geometria_sintetica.json').read_text(encoding='utf-8')); esperado['id'] = CASO
        guardada = json.loads((self.case/'tabulares'/a['id']/'geometria.json').read_text(encoding='utf-8'))
        self.assertEqual(guardada, esperado)
        self.assertEqual((a['estado'], a['aprobacion'], a['disponible_para_modelado']), ('borrador', None, False))
        self.assertEqual(b['nombre_original'], 'planilla.xlsx'); self.assertEqual(a['resumen']['faltantes'], 1)
        self.assertEqual((self.case/'tabulares'/b['id']/'libro.xlsx').read_bytes(), original_xlsx)
        text = json.dumps([a, b, self.service.listar(CASO, expediente_sha256=self.fp)])
        self.assertNotIn(str(self.app.raiz), text); self.assertNotIn(json.dumps(str(self.app.raiz))[1:-1], text)
        self.assertLess(len(text), 20000)

    def test_importacion_confirmada_replay_e_historial(self):
        item = self.service.crear(self.body_csv())
        for cambios in ({'confirmacion_explicita': False}, {'huella_tabular': '0'*64}, {'version': '../x'}):
            with self.subTest(cambios=cambios), self.assertRaises(ErrorTabular):
                self.importar(item, **cambios)
        self.assertEqual(self.versiones_geometria(), [])
        first = self.importar(item); again = self.importar(item)
        self.assertEqual(first, again); self.assertEqual(self.versiones_geometria(), [first['geometria']])
        checked = g.consultar_version(self.app.raiz, CASO, first['geometria'])
        self.assertTrue(checked.comprobacion.correcta)
        self.assertEqual(checked.geometria['revision'], {'estado': 'borrador', 'aprobacion': None})
        self.assertFalse(first['aprueba_geometria'] or first['aprueba_ingenieria'] or first['disponible_para_modelado'])
        listado = self.service.listar(CASO, expediente_sha256=self.fp)['versiones']
        self.assertEqual(listado[0]['importacion']['estado'], 'importada')

    def test_importacion_interrumpida_no_se_repite(self):
        item = self.service.crear(self.body_csv())
        real = g.importar_geometria

        def corte(*args, **kwargs):
            real(*args, **kwargs)
            raise OSError('corte simulado tras publicar la geometría')
        with patch('draft2model.revision_tabular.g.importar_geometria', side_effect=corte):
            with self.assertRaises(ErrorTabular):
                self.importar(item)
        self.assertEqual(len(self.versiones_geometria()), 1)
        with self.assertRaises(ErrorTabular) as ctx:
            self.importar(item)
        self.assertIn('interrumpida', str(ctx.exception))
        self.assertEqual(len(self.versiones_geometria()), 1)
        self.assertEqual(self.service.consultar(CASO, item['id'], expediente_sha256=self.fp)['importacion']['estado'], 'interrumpida')

    def test_entradas_invalidas_rechazadas_sin_publicar(self):
        aprobado = dict(self.meta, revision={'estado': 'aprobado', 'aprobacion': {'revisor_declarado': 'x'}})
        sin_unidad = {k: v for k, v in self.meta.items() if k != 'unidad_longitud'}
        malos = [self.body_csv(meta=dict(self.meta, unidad_longitud='ft')), self.body_csv(meta=sin_unidad),
                 self.body_csv(meta=aprobado), self.body_csv(meta=dict(self.meta, id='otro-caso')),
                 self.body_csv(archivos=dict(self.csv, **{'nodos.csv': b'id,x,y,extra\nA,0,0,1\n'})),
                 self.body_csv(archivos={'niveles.csv': self.csv['niveles.csv'], 'nodos.csv': self.csv['nodos.csv']}),
                 self.body_csv(archivos=dict(self.csv, **{'../muros.csv': b'x'})),
                 self.body_csv(metadatos_json='{"id":1,"id":2}'),
                 self.body_csv(formato='xlsx'),
                 {**self.body_csv(), 'ruta': 'C:/x'},
                 {**self.body_csv(), 'archivos': [{'nombre': 'niveles.csv', 'contenido_base64': '***'}]},
                 self.body_xlsx(raw=b'no es zip'), self.body_xlsx(nombre='libro.csv'),
                 self.body_xlsx(raw=libro(lambda f: reemplazar(f, 'xl/worksheets/sheet2.xml',
                     '<c r="B2" t="inlineStr"><is><t>0.0</t></is></c>', '<c r="B2"><f>0+0</f><v>0</v></c>'))),
                 self.body_xlsx(raw=libro(lambda f: reemplazar(f, 'xl/workbook.xml', 'name="muros"', 'name="muros" state="hidden"'))),
                 self.body_xlsx(raw=libro(lambda f: f.update({'xl/externalLinks/externalLink1.xml': '<x/>'}))),
                 {**self.body_csv(), 'expediente_sha256': '0'*64}]
        for i, body in enumerate(malos):
            with self.subTest(i=i), self.assertRaises(ErrorTabular):
                self.service.crear(body)
        base = self.case/'tabulares'
        self.assertEqual([p.name for p in base.iterdir() if not p.name.startswith('.')] if base.is_dir() else [], [])

    def test_formula_no_aceptada_aunque_el_valor_coincida(self):
        def formula(files):
            name = 'xl/worksheets/sheet2.xml'
            files[name] = files[name].replace('<is><t>4.0</t></is></c>', '<is><t>4.0</t></is><f>2+2</f></c>', 1)
            assert '<f>' in files[name]
        with self.assertRaises(ErrorTabular):
            self.service.crear(self.body_xlsx(raw=libro(formula)))

    def test_alteraciones_de_fuente_version_caso_y_expediente(self):
        item = self.service.crear(self.body_csv()); target = self.case/'tabulares'/item['id']
        source = target/'nodos.csv'; original = source.read_bytes()
        source.write_bytes(original.replace(b'4', b'5', 1))
        with self.assertRaises(ErrorTabular):
            self.service.consultar(CASO, item['id'], expediente_sha256=self.fp)
        source.write_bytes(original)
        # Alteración coherente: geometría y hash del registro rehechos; la reconversión lo detecta.
        geo = json.loads((target/'geometria.json').read_text(encoding='utf-8')); geo['nodos'][0]['x'] = 99.0
        raw = (json.dumps(geo, sort_keys=True, ensure_ascii=False, indent=2)+'\n').encode()
        (target/'geometria.json').write_bytes(raw)
        meta = json.loads((target/'version.json').read_text(encoding='utf-8'))
        import hashlib
        meta['archivos']['geometria.json'] = hashlib.sha256(raw).hexdigest()
        (target/'version.json').write_text(json.dumps(meta), encoding='utf-8')
        with self.assertRaises(ErrorTabular):
            self.service.consultar(CASO, item['id'], expediente_sha256=self.fp)
        self.assertFalse(self.service.listar(CASO, expediente_sha256=self.fp)['versiones'][0]['vigente'])
        ok = self.service.crear(self.body_csv())
        otro = self.app.raiz/'otro-caso'/'tabulares'; otro.mkdir()
        shutil.copytree(self.case/'tabulares'/ok['id'], otro/ok['id'])
        with self.assertRaises(ErrorTabular):
            self.service.consultar('otro-caso', ok['id'], expediente_sha256=self.app.expediente('otro-caso')[2])
        pdf = next(self.case.rglob('*.pdf')); pdf.write_bytes(pdf.read_bytes()+b'%alterado')
        with self.assertRaises(ErrorTabular):
            self.service.consultar(CASO, ok['id'], expediente_sha256=self.fp)
        with self.assertRaises(ErrorTabular):
            self.importar(ok)


if __name__ == '__main__':
    unittest.main()
