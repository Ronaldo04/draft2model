"""Operaciones web locales sobre versiones de configuración; sin ejecutar ETABS."""
import re
import tempfile
from pathlib import Path
from . import gestion_configuracion as configs
from .gestion_extraccion import json_desde_bytes,_carpeta_propia


class ServicioConfiguracion:
    def __init__(self,revision):self.revision=revision

    def listar(self,caso):
        folder,_,_=self.revision.expediente(caso)
        base=_carpeta_propia(folder,'configuraciones_estructurales')
        return sorted(p.name for p in base.iterdir() if re.fullmatch(r'[0-9a-f]{32}',p.name) and p.is_dir()) if base.is_dir() else []

    def consultar(self,caso,version):
        _,_,fingerprint=self.revision.expediente(caso)
        result=configs.consultar(self.revision.raiz,caso,version)
        return {'id':result['id'],'datos':result['configuracion'],'metadatos':result['metadatos'],
                'comprobacion':result['comprobacion'],'cadena':result['cadena'],
                'huella':result['metadatos']['huella_configuracion'],
                'sha256_configuracion':result['metadatos']['sha256_configuracion'],'expediente_sha256':fingerprint}

    def malla(self,caso,version):
        """Preparación de malla 0.4 (nodos derivados, triángulos, faltantes) antes de aprobar; solo lectura."""
        _,_,fingerprint=self.revision.expediente(caso)
        result=configs.preparar_malla_version(self.revision.raiz,caso,version)
        return {**result,'expediente_sha256':fingerprint}

    def actuar(self,operacion,body):
        if not isinstance(body,dict):raise ValueError('Objeto requerido.')
        with self.revision.lock:
            caso=body.get('caso');folder,_,fingerprint=self.revision.expediente(caso)
            if body.get('expediente_sha256')!=fingerprint:raise ValueError('Expediente cambió.')
            base={'caso','expediente_sha256'}
            if operacion=='importar':
                if set(body)!=base|{'configuracion_json'} or not isinstance(body['configuracion_json'],str):raise ValueError('Importación inválida.')
                raw=body['configuracion_json'].encode();json_desde_bytes(raw,'configuración')
                with tempfile.TemporaryDirectory(prefix='.config-',dir=folder) as tmp:
                    path=Path(tmp)/'entrada.json';path.write_bytes(raw)
                    result=configs.importar(self.revision.raiz,caso,path)
            else:
                base|={'version','huella','sha256_configuracion','revisor_declarado','fecha','motivo'}
                extra={'configuracion_json'} if operacion=='revisar' else {'alcance','confirmacion_explicita'}
                if operacion not in ('revisar','aprobar') or set(body)!=base|extra:raise ValueError('Operación inválida.')
                current=self.consultar(caso,body['version'])
                if current['huella']!=body['huella'] or current['sha256_configuracion']!=body['sha256_configuracion']:
                    raise ValueError('Configuración cambió; recargar antes de registrar.')
                actor={'revisor':body['revisor_declarado'],'fecha':body['fecha'],'motivo':body['motivo']}
                if operacion=='revisar':
                    if not isinstance(body['configuracion_json'],str):raise ValueError('JSON completo requerido.')
                    data=json_desde_bytes(body['configuracion_json'].encode(),'configuración')
                    result=configs.revisar(self.revision.raiz,caso,body['version'],data,**actor)
                else:
                    if body['confirmacion_explicita'] is not True:raise ValueError('Confirmación explícita requerida.')
                    result=configs.aprobar(self.revision.raiz,caso,body['version'],huella_esperada=body['huella'],alcance=body['alcance'],**actor)
            return {'id':result['id'],'operacion':operacion,'ruta_relativa':result['ruta'].relative_to(folder).as_posix()}
