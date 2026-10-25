"""Revisión declarada e inmutable del resultado y análisis explícitos; sin mutar resultados."""
from __future__ import annotations

import copy
from datetime import date, datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from uuid import uuid4

from . import evidencia_analisis as evidencia
from .gestion_extraccion import json_desde_bytes

CONTROLES=('unidades','casos','filtros','omisiones','consistencia_modelo','revision_tecnica')
CAMPOS={'caso','resultado','analisis','expediente_sha256','huella_resultados','huella_evidencia',
        'revisor_declarado','fecha','alcance','motivo','controles','faltantes_criticos','observaciones','confirmacion_explicita'}
CONTRATO='draft2model.revision_resultados_declarada'
VERSION='0.1.0'
GRUPO='revisiones_resultados'
ERRORES=(ValueError,OSError,RuntimeError,KeyError,TypeError,AttributeError,OverflowError,RecursionError)
AVISO=('Identidad y competencia del revisor declaradas, no autenticadas. La revisión no prueba completitud física '
       'ni certifica seguridad estructural; no aprueba informe ni evalúa conformidad normativa.')


class ErrorRevisionResultados(ValueError):
    def __init__(self,codigo):
        self.codigo=codigo
        super().__init__(codigo)


def _bytes(value):
    return (json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)+'\n').encode('utf-8')


def _sha(raw):return hashlib.sha256(raw).hexdigest()


def _id(value):
    if not isinstance(value,str) or re.fullmatch('[0-9a-f]{32}',value) is None:
        raise ErrorRevisionResultados('identificador_invalido')


def _hex(value):
    if not isinstance(value,str) or re.fullmatch('[0-9a-f]{64}',value) is None:
        raise ErrorRevisionResultados('huella_invalida')


def _seguro(path):
    info=path.lstat()
    if (path.resolve()!=path or stat.S_ISLNK(info.st_mode)
            or getattr(info,'st_file_attributes',0)&getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0)):
        raise ErrorRevisionResultados('ruta_no_permitida')
    return path


def _leer(path):
    _seguro(path)
    if not path.is_file() or path.stat().st_size>4*1024*1024:
        raise ErrorRevisionResultados('registro_invalido')
    return path.read_bytes()


def _declaracion(body):
    if not isinstance(body,dict) or set(body)!=CAMPOS:
        raise ErrorRevisionResultados('campos_invalidos')
    if body['confirmacion_explicita'] is not True:
        raise ErrorRevisionResultados('confirmacion_requerida')
    for key in ('resultado','analisis'):_id(body[key])
    for key in ('expediente_sha256','huella_resultados','huella_evidencia'):_hex(body[key])
    controls=body['controles']
    if not isinstance(controls,dict) or set(controls)!=set(CONTROLES) or any(v is not True for v in controls.values()):
        raise ErrorRevisionResultados('controles_explicitos_requeridos')
    for key,limit in (('revisor_declarado',150),('fecha',10),('alcance',4000),('motivo',4000)):
        if not isinstance(body[key],str) or not body[key].strip() or len(body[key])>limit:
            raise ErrorRevisionResultados('declaracion_incompleta')
    if re.fullmatch(r'\d{4}-\d{2}-\d{2}',body['fecha']) is None:
        raise ErrorRevisionResultados('fecha_invalida')
    try:date.fromisoformat(body['fecha'])
    except ValueError:raise ErrorRevisionResultados('fecha_invalida') from None
    for key in ('faltantes_criticos','observaciones'):
        values=body[key]
        if not isinstance(values,list) or len(values)>100 or any(not isinstance(v,str) or not v.strip() or len(v)>2000 for v in values):
            raise ErrorRevisionResultados('observaciones_invalidas')
    if body['faltantes_criticos']:
        raise ErrorRevisionResultados('faltantes_criticos_declarados')
    return copy.deepcopy(body)


class ServicioRevisionResultados:
    def __init__(self,app):self.app=app

    def _caso(self,caso,fp):
        _hex(fp)
        folder,_,actual=self.app.expediente(caso)
        root=_seguro(Path(self.app.raiz));folder=_seguro(Path(folder))
        if actual!=fp:raise ErrorRevisionResultados('expediente_cambio')
        if folder.parent!=root or not folder.is_dir():raise ErrorRevisionResultados('caso_invalido')
        return folder

    def _grupo(self,folder,crear=False):
        base=folder/GRUPO
        if crear and not os.path.lexists(base):base.mkdir()
        if os.path.lexists(base):
            _seguro(base)
            if not base.is_dir():raise ErrorRevisionResultados('directorio_invalido')
        return base

    @staticmethod
    def _inventario(folder):
        _seguro(folder);out={}
        for path in sorted(folder.iterdir()):
            _seguro(path)
            if not path.is_file():raise ErrorRevisionResultados('contenido_resultado_invalido')
            digest=hashlib.sha256()
            with path.open('rb') as stream:
                for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
            out[path.name]=digest.hexdigest()
        return out

    def _fuentes(self,caso,resultado,analisis,fp):
        _id(resultado);_id(analisis);folder=self._caso(caso,fp)
        checked=self.app.resultados.consultar_resultado(caso,resultado,expediente_sha256=fp)
        group=_seguro(folder/'resultados_estructurales');target=_seguro(group/resultado)
        inventory=self._inventario(target)
        run=folder/'analisis_etabs'/analisis
        accepted=evidencia.verificar_analisis_aceptado(self.app.raiz,caso,run)
        proof=evidencia.verificar_evidencia(self.app.raiz,caso,resultado,run)
        data=checked['datos'];rows=data['resultados']
        if not rows:raise ErrorRevisionResultados('resultados_sin_indicadores')
        if (checked['vigente'] is not True or checked['huella']!=proof['resultado']['huella_resultados']
                or accepted['corrida_id']!=analisis or proof['analisis']['corrida_id']!=analisis
                or accepted['sha256_edb_analizado']!=proof['resultado']['sha256_edb_leido']
                or accepted['modelo_id']!=proof['modelo']['modelo_id']
                or accepted['huella_modelo']!=proof['modelo']['huella_modelo']):
            raise ErrorRevisionResultados('fuentes_incompatibles')
        if self._inventario(target)!=inventory:raise ErrorRevisionResultados('resultado_cambio')
        self._caso(caso,fp)
        return {'resultado':resultado,'analisis':analisis,'expediente_sha256':fp,'huella_resultados':checked['huella'],
            'huella_evidencia':evidencia.huella_evidencia(proof),'archivos_resultado':inventory,
            'analisis_aceptado':accepted,'evidencia':proof,'datos_sinteticos':data['datos_sinteticos'],
            'unidades':copy.deepcopy(data['unidades']),'casos':copy.deepcopy(data['casos']),
            'advertencias':copy.deepcopy(data['advertencias']),'omisiones':copy.deepcopy(data['omisiones']),
            'indicadores':[copy.deepcopy(row) for row in rows],
            'filas_omitidas':[copy.deepcopy(row) for row in rows if row['valor'] is None]}

    def consultar_fuentes(self,caso,resultado,analisis,*,expediente_sha256):
        try:
            with self.app.lock:
                snapshot=self._fuentes(caso,resultado,analisis,expediente_sha256)
                if self._fuentes(caso,resultado,analisis,expediente_sha256)!=snapshot:
                    raise ErrorRevisionResultados('fuentes_cambiaron')
                return {'caso':caso,**snapshot,'controles_requeridos':list(CONTROLES),
                    'revision_resultados':'pendiente','identidad_revisor':'declarada_no_verificada',
                    'conformidad_normativa':'no_evaluada','aprueba_resultados':False,'aprueba_informe':False,'aviso':AVISO}
        except ErrorRevisionResultados:raise
        except ERRORES:raise ErrorRevisionResultados('fuentes_no_vigentes') from None

    @staticmethod
    def _proyeccion(record,raw):
        body=record['declaracion'];source=record['fuentes']
        return {'id':record['id'],'caso':body['caso'],'resultado':body['resultado'],'analisis':body['analisis'],
            'expediente_sha256':body['expediente_sha256'],'huella_resultados':body['huella_resultados'],
            'huella_evidencia':body['huella_evidencia'],'sha256_revision':_sha(raw),'creado_utc':record['creado_utc'],
            'vigente':True,'estado':'revision_declarada_vigente','revision_resultados':'revisados_declarados',
            'declaracion':{k:copy.deepcopy(body[k]) for k in ('revisor_declarado','fecha','alcance','motivo','controles','faltantes_criticos','observaciones')},
            'fuentes':copy.deepcopy(source),'identidad_revisor':'declarada_no_verificada',
            'competencia_revisor':'declarada_no_verificada','verificacion_profesional':False,
            'aprueba_resultados':False,'aprueba_informe':False,'aprueba_ingenieria':False,
            'conformidad_normativa':'no_evaluada','seguridad_estructural':'no_certificada','aviso':AVISO}

    def _consultar(self,caso,revision,fp,ruta=None):
        _id(revision);folder=self._caso(caso,fp);base=self._grupo(folder)
        target=_seguro(ruta if ruta is not None else base/revision)
        if not target.is_dir() or {p.name for p in target.iterdir()}!={'revision.json','version.json'}:
            raise ErrorRevisionResultados('registro_invalido')
        raw=_leer(target/'revision.json');meta_raw=_leer(target/'version.json')
        record=json_desde_bytes(raw,'revision');meta=json_desde_bytes(meta_raw,'version')
        fields={'contrato','version','id','creado_utc','declaracion','fuentes'}
        if not isinstance(record,dict) or set(record)!=fields or record['contrato']!=CONTRATO or record['version']!=VERSION or record['id']!=revision:
            raise ErrorRevisionResultados('registro_invalido')
        body=_declaracion(record['declaracion'])
        if body['caso']!=caso or body['expediente_sha256']!=fp:
            raise ErrorRevisionResultados('registro_de_otro_caso')
        stamp=datetime.fromisoformat(record['creado_utc'])
        if stamp.utcoffset() is None or stamp.utcoffset().total_seconds()!=0:raise ErrorRevisionResultados('fecha_registro_invalida')
        expected={'contrato':CONTRATO,'version':VERSION,'id':revision,'caso':caso,'resultado':body['resultado'],
                  'analisis':body['analisis'],'expediente_sha256':fp,'sha256_revision':_sha(raw)}
        if meta!=expected:raise ErrorRevisionResultados('registro_alterado')
        snapshot=self._fuentes(caso,body['resultado'],body['analisis'],fp)
        if snapshot!=record['fuentes'] or body['huella_resultados']!=snapshot['huella_resultados'] or body['huella_evidencia']!=snapshot['huella_evidencia']:
            raise ErrorRevisionResultados('revision_no_vigente')
        if self._fuentes(caso,body['resultado'],body['analisis'],fp)!=snapshot:
            raise ErrorRevisionResultados('fuentes_cambiaron')
        self._caso(caso,fp)
        if _leer(target/'revision.json')!=raw or _leer(target/'version.json')!=meta_raw:
            raise ErrorRevisionResultados('registro_cambio')
        return self._proyeccion(record,raw)

    def consultar(self,caso,revision,*,expediente_sha256):
        try:
            with self.app.lock:return self._consultar(caso,revision,expediente_sha256)
        except ErrorRevisionResultados:raise
        except ERRORES:raise ErrorRevisionResultados('revision_no_vigente') from None

    def registrar(self,body):
        try:
            with self.app.lock:
                body=_declaracion(body);caso=body['caso'];fp=body['expediente_sha256'];folder=self._caso(caso,fp)
                before=self._fuentes(caso,body['resultado'],body['analisis'],fp)
                if body['huella_resultados']!=before['huella_resultados'] or body['huella_evidencia']!=before['huella_evidencia']:
                    raise ErrorRevisionResultados('huellas_no_coinciden')
                ident=uuid4().hex;record={'contrato':CONTRATO,'version':VERSION,'id':ident,
                    'creado_utc':datetime.now(timezone.utc).isoformat(),'declaracion':body,'fuentes':before}
                raw=_bytes(record);meta={'contrato':CONTRATO,'version':VERSION,'id':ident,'caso':caso,
                    'resultado':body['resultado'],'analisis':body['analisis'],'expediente_sha256':fp,'sha256_revision':_sha(raw)}
                base=self._grupo(folder,crear=True);target=base/ident
                with tempfile.TemporaryDirectory(prefix='.rev-',dir=base) as temp:
                    stage=Path(temp).resolve()/'registro';stage.mkdir()
                    for name,value in (('revision.json',raw),('version.json',_bytes(meta))):
                        with (stage/name).open('xb') as stream:stream.write(value)
                    self._consultar(caso,ident,fp,ruta=stage)
                    if self._fuentes(caso,body['resultado'],body['analisis'],fp)!=before:
                        raise ErrorRevisionResultados('fuentes_cambiaron')
                    self._caso(caso,fp)
                    _seguro(base);_seguro(stage.parent);_seguro(stage)
                    if os.path.lexists(target):raise ErrorRevisionResultados('destino_existente')
                    stage.rename(target)
                return self._consultar(caso,ident,fp)
        except ErrorRevisionResultados:raise
        except ERRORES:raise ErrorRevisionResultados('registro_rechazado') from None

    def listar(self,caso,resultado,*,expediente_sha256):
        try:
            with self.app.lock:
                _id(resultado);folder=self._caso(caso,expediente_sha256);base=self._grupo(folder);rows=[]
                for path in sorted(base.iterdir()) if base.is_dir() else []:
                    if re.fullmatch('[0-9a-f]{32}',path.name) is None:continue
                    try:
                        _seguro(path);raw=_leer(path/'revision.json');record=json_desde_bytes(raw,'revision')
                        metadata=json_desde_bytes(_leer(path/'version.json'),'version')
                        if (isinstance(metadata,dict) and metadata.get('resultado')!=resultado
                                and isinstance(record,dict) and isinstance(record.get('declaracion'),dict)
                                and record['declaracion'].get('resultado')==metadata.get('resultado')):continue
                        value=self._consultar(caso,path.name,expediente_sha256)
                        rows.append({'id':path.name,'vigente':True,'problemas':[],
                            'resumen':{k:copy.deepcopy(value[k]) for k in ('analisis','huella_resultados','huella_evidencia','sha256_revision','revision_resultados','declaracion')}})
                    except ERRORES:
                        rows.append({'id':path.name,'vigente':False,'problemas':['revision_no_vigente'],'resumen':None})
                for row in rows:
                    if not row['vigente']:continue
                    try:
                        current=self._consultar(caso,row['id'],expediente_sha256)
                        if any(current[k]!=row['resumen'][k] for k in row['resumen']):
                            raise ErrorRevisionResultados('revision_cambio')
                    except ERRORES:
                        row.update(vigente=False,problemas=['revision_no_vigente'],resumen=None)
                self._caso(caso,expediente_sha256)
                return {'caso':caso,'resultado':resultado,'expediente_sha256':expediente_sha256,'versiones':rows,
                    'seleccion_automatica':False,'conformidad_normativa':'no_evaluada'}
        except ErrorRevisionResultados:raise
        except ERRORES:raise ErrorRevisionResultados('consulta_rechazada') from None
