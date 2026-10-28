"""Conversión web explícita y verificada; importación independiente como borrador."""
from functools import wraps
import hashlib
import json
from pathlib import Path
import re
import tempfile

from . import gestion_extraccion as e
from . import gestion_geometria as g
from .adaptador_etabs import BloqueoExclusivo
from .contratos import huella_contenido
from .conversion_geometria import convertir_lecturas, comprobar_reproduccion, CARPETA, AVISO
from .extraccion_preliminar import exportar_revisados
from .validacion_geometria import validar_geometria


def _bytes(value):
    return (json.dumps(value,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n').encode('utf-8')


def _sha(raw):return hashlib.sha256(raw).hexdigest()


def _id(value):
    if not isinstance(value,str) or not re.fullmatch('[0-9a-f]{32}',value):raise ValueError('Identificador inválido.')
    return value


def _safe(path, *, missing=False):
    if path.resolve()!=path:raise ValueError('Ruta enlazada o ajena.')
    if not missing and not path.exists():raise ValueError('Fuente ausente.')
    return path


def _read(path):return _safe(path).read_bytes()


def _new(path,raw):
    _safe(path,missing=True)
    with path.open('xb') as stream:stream.write(raw)


def _public(method):
    @wraps(method)
    def run(*args,**kwargs):
        try:return method(*args,**kwargs)
        except (ValueError,OSError,RuntimeError,KeyError,TypeError,AttributeError,IndexError,OverflowError):
            raise ValueError('Conversión inválida, alterada o sin fuentes vigentes; revisa la selección y sus huellas.') from None
    return run


class ServicioConversion:
    def __init__(self,app):self.app=app

    def _case(self,caso,fp):
        folder,_,actual=self.app.expediente(caso)
        if not isinstance(fp,str) or not re.fullmatch('[0-9a-f]{64}',fp) or fp!=actual:
            raise ValueError('Expediente sin vigencia.')
        _safe(Path(self.app.raiz));_safe(folder)
        if folder.parent!=Path(self.app.raiz):raise ValueError('Caso ajeno.')
        return folder

    def _source(self,caso,extraccion,fp):
        folder=self._case(caso,fp);ident=_id(extraccion)
        data,meta,problems=e.cargar_version(folder,caso,ident)
        check=e.validar_version(self.app.raiz,caso,ident)
        if problems or not check.correcta:raise ValueError('Extracción no comprobada.')
        base=_safe(_safe(folder/'extracciones')/ident)
        raw={name:_read(base/name) for name in ('extraccion.json','version.json')}
        if (e.json_desde_bytes(raw['extraccion.json'],'extracción')!=data
                or e.json_desde_bytes(raw['version.json'],'versión')!=meta):
            raise ValueError('Extracción cambiada durante consulta.')
        export=exportar_revisados(data,check.inventario)
        self._case(caso,fp)
        return export,{name:_sha(value) for name,value in raw.items()}

    @staticmethod
    def _fields(body,extra):
        if not isinstance(body,dict) or set(body)!={'caso','expediente_sha256'}|set(extra):
            raise ValueError('Campos de conversión inválidos.')

    @_public
    def crear(self,body):
        self._fields(body,('extraccion','manifiesto_json'))
        if not isinstance(body['manifiesto_json'],str) or len(body['manifiesto_json'].encode('utf-8'))>1500*1024:
            raise ValueError('Manifiesto JSON inválido o demasiado grande.')
        with self.app.lock:
            caso,fp,source=body['caso'],body['expediente_sha256'],_id(body['extraccion'])
            folder=self._case(caso,fp);_,signatures=self._source(caso,source,fp)
            raw=body['manifiesto_json'].encode('utf-8');e.json_desde_bytes(raw,'manifiesto')
            with tempfile.TemporaryDirectory(prefix='.conversion-',dir=folder) as temp:
                path=Path(temp)/'manifiesto.json';_new(path,raw)
                converted=convertir_lecturas(self.app.raiz,caso,source,path)
            if self._source(caso,source,fp)[1]!=signatures:raise ValueError('Extracción cambiada durante conversión.')
            target=_safe(_safe(folder/CARPETA)/_id(converted.identificador))
            artifacts={name:_sha(_read(target/name)) for name in ('manifiesto.json','geometria.json','trazabilidad.json','exportacion.json')}
            if artifacts['manifiesto.json']!=_sha(raw):raise ValueError('Manifiesto cambiado.')
            receipt={'id':converted.identificador,'caso':caso,'extraccion':source,'expediente_sha256':fp,
                'fuentes':signatures,'archivos':artifacts}
            _new(target/'web.json',_bytes(receipt))
            return self.consultar(caso,converted.identificador,expediente_sha256=fp)

    def _load(self,caso,version,fp):
        folder=self._case(caso,fp);target=_safe(_safe(folder/CARPETA)/_id(version))
        names=('manifiesto.json','geometria.json','trazabilidad.json','exportacion.json','web.json')
        raw={name:_read(target/name) for name in names}
        manifest,geometry,trace,export,receipt=(e.json_desde_bytes(raw[name],name) for name in names)
        if (not all(isinstance(v,dict) for v in (manifest,geometry,trace,export,receipt))
                or set(receipt)!={'id','caso','extraccion','expediente_sha256','fuentes','archivos'}
                or receipt.get('id')!=version or receipt.get('caso')!=caso or receipt.get('expediente_sha256')!=fp
                or not isinstance(receipt.get('archivos'),dict) or set(receipt['archivos'])!=set(names)-{'web.json'}
                or any(receipt['archivos'][name]!=_sha(raw[name]) for name in names if name!='web.json')):
            raise ValueError('Registro de conversión alterado.')
        expected,signatures=self._source(caso,receipt['extraccion'],fp)
        if (receipt['fuentes']!=signatures or _bytes({k:v for k,v in export.items() if k!='origen'})!=_bytes(expected)
                or not isinstance(export.get('origen'),dict) or export['origen'].get('extraccion_id')!=receipt['extraccion']
                or export['origen'].get('expediente_sha256')!=fp):raise ValueError('Exportación de otras fuentes.')
        export_path=_safe(_safe(folder/'extracciones_exportadas')/_id(trace['exportacion_id']))/'exportacion.json'
        if _read(export_path)!=raw['exportacion.json']:raise ValueError('Exportación conservada alterada.')
        if (trace.get('contrato')!='draft2model.trazabilidad_conversion' or manifest.get('version_contrato') not in ('0.1.0','0.2.0','0.3.0')
                or trace.get('version_contrato')!=manifest.get('version_contrato')
                or geometry.get('version_contrato')!=manifest.get('version_contrato')
                or trace.get('id')!=version or trace.get('caso')!=caso or trace.get('extraccion_id')!=receipt['extraccion']
                or trace.get('expediente_sha256')!=fp or trace.get('exportacion_sha256')!=_sha(raw['exportacion.json'])
                or trace.get('manifiesto_sha256')!=_sha(raw['manifiesto.json'])
                or trace.get('geometria_sha256')!=_sha(raw['geometria.json'])
                or trace.get('huella_contenido')!=huella_contenido(geometry)
                or trace.get('aprobacion_ingenieria') is not None or trace.get('datos_sinteticos') is not manifest.get('datos_sinteticos')
                or geometry.get('id')!=caso or geometry.get('revision')!={'estado':'borrador','aprobacion':None}
                or manifest.get('caso')!=caso or trace.get('alcance')!=expected['alcance']
                or trace.get('procedencia_extraccion')!=expected['procedencia']
                or trace.get('identidad_operador')!='declarada_no_verificada'
                or any(trace.get(k)!=manifest.get(k) for k in ('operador_declarado','ejes','escala','sistema_coordenadas'))
                or geometry.get('unidad_longitud')!=manifest.get('unidad_longitud')
                or geometry.get('procedencia')!=manifest.get('procedencia')):
            raise ValueError('Geometría o trazabilidad ajenas.')
        comprobar_reproduccion(export,manifest,geometry,trace.get('correspondencias'))
        validation=validar_geometria(geometry)
        if (not validation.consistente or validation.faltantes or validation.disponible_para_modelado
                or validation.datos_sinteticos is not manifest['datos_sinteticos']):
            raise ValueError('Geometría no es un borrador íntegro.')
        self._case(caso,fp)
        if self._source(caso,receipt['extraccion'],fp)[1]!=signatures or _read(export_path)!=raw['exportacion.json']:
            raise ValueError('Fuentes cambiadas durante consulta.')
        if any(_read(target/name)!=value for name,value in raw.items()):raise ValueError('Conversión cambiada durante consulta.')
        return target,raw,receipt,manifest,geometry,trace

    @_public
    def consultar(self,caso,version,*,expediente_sha256):
        with self.app.lock:
            _,raw,receipt,manifest,geometry,trace=self._load(caso,version,expediente_sha256)
            fields=('extraccion_id','exportacion_id','datos_sinteticos','operador_declarado','identidad_operador',
                'alcance','ejes','escala','correspondencias','aprobacion_ingenieria')
            return {'id':version,'caso':caso,'extraccion':receipt['extraccion'],'expediente_sha256':expediente_sha256,
                'huella_conversion':_sha(_bytes(receipt)),'sha256_geometria':_sha(raw['geometria.json']),
                'manifiesto':manifest,'geometria':geometry,'trazabilidad':{k:trace[k] for k in fields},
                'vigente':True,'estado':'borrador','aprobacion':None,'disponible_para_modelado':False,'aviso':AVISO}

    @_public
    def listar(self,caso,*,expediente_sha256):
        with self.app.lock:
            folder=self._case(caso,expediente_sha256);base=_safe(folder/CARPETA,missing=True);rows=[]
            for path in sorted(base.iterdir()) if base.is_dir() else []:
                if not re.fullmatch('[0-9a-f]{32}',path.name):continue
                # Solo versiones registradas por este servicio; la CLI mantiene sus artefactos propios.
                if not (path/'web.json').exists():continue
                try:
                    data=self.consultar(caso,path.name,expediente_sha256=expediente_sha256)
                    rows.append({'id':path.name,'extraccion':data['extraccion'],'vigente':True,'estado':'borrador'})
                except ValueError:rows.append({'id':path.name,'vigente':False,'problemas':['conversion_no_vigente']})
            self._case(caso,expediente_sha256)
            return {'caso':caso,'expediente_sha256':expediente_sha256,'versiones':rows}

    @_public
    def importar_geometria(self,body):
        self._fields(body,('version','huella_conversion','confirmacion_explicita'))
        if body['confirmacion_explicita'] is not True:raise ValueError('Confirma importar el borrador.')
        with self.app.lock:
            caso,fp=body['caso'],body['expediente_sha256'];folder=self._case(caso,fp)
            lock=_safe(folder/'conversion_web.lock',missing=True)
            with BloqueoExclusivo(lock):
                target,raw,receipt,_,geometry,_=self._load(caso,body['version'],fp)
                if body['huella_conversion']!=_sha(_bytes(receipt)):raise ValueError('Huella de conversión distinta.')
                accepted=target/'importacion_web.json';marker=target/'importacion_pendiente.json'
                if accepted.exists():
                    saved=e.json_desde_bytes(_read(accepted),'importación')
                    ident=_id(saved['geometria']);checked=g.consultar_version(self.app.raiz,caso,ident)
                    if (not checked.comprobacion.correcta or checked.geometria!=geometry
                            or saved!={'conversion':body['version'],'geometria':ident,'huella_conversion':body['huella_conversion']}):
                        raise ValueError('Importación anterior no vigente.')
                else:
                    if marker.exists():raise ValueError('Importación interrumpida; requiere revisión externa.')
                    _new(marker,_bytes({'conversion':body['version'],'huella_conversion':body['huella_conversion']}))
                    imported=g.importar_geometria(self.app.raiz,caso,target/'geometria.json');ident=imported.identificador
                    checked=g.consultar_version(self.app.raiz,caso,ident)
                    self._load(caso,body['version'],fp)
                    if not checked.comprobacion.correcta or checked.geometria!=geometry:raise ValueError('Importación no comprobada.')
                    _new(accepted,_bytes({'conversion':body['version'],'geometria':ident,'huella_conversion':body['huella_conversion']}))
                self._load(caso,body['version'],fp)
                return {'caso':caso,'conversion':body['version'],'geometria':ident,'expediente_sha256':fp,
                    'estado':'borrador','aprobacion':None,'disponible_para_modelado':False}
