"""Lectura supervisada de tablas XLSX según contrato explícito, sin fórmulas ni conversiones implícitas."""
import csv
import io
from pathlib import PurePosixPath
import re
import zipfile
from xml.etree import ElementTree as ET

NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
    'r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
REL='http://schemas.openxmlformats.org/package/2006/relationships'
MAX_XML=8*1024*1024


def _leer_tablas_xlsx(entrada, *, colecciones=('niveles', 'nodos', 'muros')):
    """Devuelve CSV equivalente, conservando blancos; rechaza funciones no soportadas."""
    colecciones = tuple(colecciones)
    if colecciones not in (('niveles', 'nodos', 'muros'), ('niveles', 'nodos', 'muros', 'vertices', 'superficies'), ('niveles', 'nodos', 'muros', 'vertices', 'superficies', 'aberturas')):
        raise ValueError('Colecciones XLSX no admitidas.')
    with zipfile.ZipFile(entrada) as archive:
        entries=archive.infolist();names=[i.filename for i in entries]
        if len(entries)>500 or len(set(names))!=len(names) or sum(i.file_size for i in entries)>32*1024*1024:
            raise ValueError('XLSX demasiado grande o con archivos duplicados.')
        if any(i.flag_bits&1 or 'vbaProject' in i.filename or i.filename.startswith('xl/externalLinks/') for i in entries):
            raise ValueError('XLSX cifrado, con macros o vínculos externos no admitido.')
        def xml(name):
            with archive.open(name) as stream:raw=stream.read(MAX_XML+1)
            if len(raw)>MAX_XML or b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
                raise ValueError('XML excede límites o contiene declaraciones no permitidas.')
            return ET.fromstring(raw)
        # Rechazar referencias externas incluso si no se utilizan en las tablas.
        for name in names:
            if name.endswith('.rels') and any(e.attrib.get('TargetMode')=='External' for e in xml(name)):
                raise ValueError('Vínculos externos no admitidos.')
        workbook=xml('xl/workbook.xml');relationships={}
        for rel in xml('xl/_rels/workbook.xml.rels'):
            if rel.attrib.get('Id') in relationships:raise ValueError('Relación de libro duplicada.')
            relationships[rel.attrib.get('Id')]=rel.attrib
        shared=[]
        if 'xl/sharedStrings.xml' in names:
            shared=[''.join(t.text or '' for t in list(si.findall('m:t',NS))+list(si.findall('m:r/m:t',NS))) for si in xml('xl/sharedStrings.xml')]
        formats=[]
        if 'xl/styles.xml' in names:
            root=xml('xl/styles.xml');xfs=root.find('m:cellXfs',NS)
            formats=[int(x.attrib.get('numFmtId','0')) for x in xfs] if xfs is not None else []
        sheets=workbook.find('m:sheets',NS)
        if sheets is None or len(sheets)!=len(colecciones) or {s.attrib.get('name') for s in sheets}!=set(colecciones):
            raise ValueError('Se requieren exactamente las hojas: ' + ', '.join(colecciones) + '.')
        result={}
        for sheet in sheets:
            if sheet.attrib.get('state','visible')!='visible':raise ValueError('Hojas ocultas no admitidas.')
            rel=relationships.get(sheet.attrib.get('{'+NS['r']+'}id'))
            if not rel or rel.get('Type')!=NS['r']+'/worksheet':raise ValueError('Relación de hoja inválida.')
            target=rel.get('Target','');path=PurePosixPath(target)
            if '..' in path.parts or '\\' in target:raise ValueError('Ruta de hoja inválida.')
            source=target.lstrip('/') if target.startswith('/') else 'xl/'+target
            if not source.startswith('xl/worksheets/') or not source.endswith('.xml'):raise ValueError('Ruta de hoja fuera de tablas.')
            root=xml(source)
            if any(e.tag.rsplit('}',1)[-1] in ('f','mergeCell','extLst') for e in root.iter()):
                raise ValueError('No se admiten fórmulas, celdas combinadas ni extensiones de hoja.')
            rows={};count=0
            for cell in root.findall('.//m:sheetData/m:row/m:c',NS):
                count+=1
                if count>100000:raise ValueError('Demasiadas celdas.')
                match=re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]{0,4})',cell.attrib.get('r',''))
                if not match:raise ValueError('Referencia de celda inválida.')
                col=0
                for letter in match[1]:col=26*col+ord(letter)-64
                row=int(match[2])
                if col>128 or row>10000:raise ValueError('Tabla supera 128 columnas o 10000 filas.')
                cells=rows.setdefault(row,{})
                if col in cells:raise ValueError('Celda repetida.')
                kind=cell.attrib.get('t','n');value=cell.find('m:v',NS)
                text=value.text if value is not None and value.text is not None else ''
                if kind=='inlineStr':text=''.join(t.text or '' for t in cell.findall('.//m:t',NS))
                elif kind=='s':
                    if not re.fullmatch(r'\d+',text) or int(text)>=len(shared):raise ValueError('Texto compartido inválido.')
                    text=shared[int(text)]
                elif kind=='n':
                    style=int(cell.attrib.get('s','0'))
                    if style<0 or (formats and (style>=len(formats) or formats[style] not in (0,1,2,3,4,11))) or (not formats and style!=0):
                        raise ValueError('Formato numérico/fecha no soportado; usar General o texto.')
                else:raise ValueError('Solo texto o números explícitos; booleanos, errores y fechas no admitidos.')
                cells[col]=text
            if 1 not in rows or not rows[1]:raise ValueError('Cabecera de tabla ausente.')
            width=max(rows[1]);out=io.StringIO(newline='');writer=csv.writer(out)
            for index in sorted(rows):
                if max(rows[index])>width:raise ValueError('Fila excede la cabecera.')
                writer.writerow([rows[index].get(c,'') for c in range(1,width+1)])
            result[sheet.attrib['name']]=out.getvalue()
        return result


def leer_tablas_xlsx(entrada, *, colecciones=('niveles', 'nodos', 'muros')):
    try:return _leer_tablas_xlsx(entrada, colecciones=colecciones)
    except (zipfile.BadZipFile,KeyError,ET.ParseError,UnicodeError,IndexError) as exc:
        raise ValueError('XLSX incompleto o XML inválido; revisar formato del libro.') from exc
