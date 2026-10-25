"""Control de publicación web: una operación incompleta requiere recuperación."""
import json
import hashlib
from pathlib import Path
import re


def leer(path):
    if path.resolve()!=path or not path.is_file():raise ValueError('Control de normalización ausente o enlazado.')
    raw=path.read_bytes()
    return raw,json.loads(raw)


def pendientes(caso_dir):
    base=Path(caso_dir)/'normalizaciones_resultados'
    if base.resolve()!=base:raise ValueError('Control enlazado.')
    rows=[]
    for path in sorted(base.iterdir()) if base.is_dir() else []:
        if not re.fullmatch('[0-9a-f]{32}',path.name):continue
        if path.resolve()!=path:raise ValueError('Operación enlazada.')
        request_raw,request=leer(path/'solicitud.json')
        if (not isinstance(request,dict) or request.get('caso')!=caso_dir.name
                or request.get('clave_solicitud')!=path.name):raise ValueError('Solicitud de normalización inválida.')
        done=False
        if (path/'aceptacion.json').exists():
            try:
                receipt_raw,receipt=leer(path/'aceptacion.json')
                done=(isinstance(receipt,dict) and set(receipt)=={'resultado','mapeo_version','huella_mapeo','evidencia_analisis','aprueba_resultados','conformidad_normativa'}
                      and isinstance(receipt.get('resultado'),str) and re.fullmatch('[0-9a-f]{32}',receipt['resultado'])
                      and receipt['mapeo_version']==request.get('version') and receipt['huella_mapeo']==request.get('huella_mapeo')
                      and receipt['aprueba_resultados'] is False and receipt['conformidad_normativa']=='no_evaluada')
                if done:
                    from .evidencia_analisis import verificar_evidencia
                    version=request.get('version')
                    if not isinstance(version,str) or not re.fullmatch('[0-9a-f]{32}',version):raise ValueError('Versión inválida.')
                    mapping=caso_dir/'mapeos_resultados'/version
                    _,meta=leer(mapping/'version.json')
                    analysis=meta.get('analisis') if isinstance(meta,dict) else None
                    if not isinstance(analysis,str) or not re.fullmatch('[0-9a-f]{32}',analysis):raise ValueError('Análisis inválido.')
                    if leer(mapping/'mapeo.json')[0]!=leer(caso_dir/'resultados_estructurales'/receipt['resultado']/'mapeo.json')[0]:
                        raise ValueError('Resultado de otro mapeo.')
                    done=(verificar_evidencia(caso_dir.parent,caso_dir.name,receipt['resultado'],caso_dir/'analisis_etabs'/analysis)==receipt['evidencia_analisis']
                          and leer(path/'aceptacion.json')[0]==receipt_raw and leer(path/'solicitud.json')[0]==request_raw)
            except (ValueError,OSError,KeyError,TypeError):pass
        if (path/'cancelacion.json').exists():
            _,cancel=leer(path/'cancelacion.json')
            done=done or cancel=={'clave_solicitud':path.name,'cancelada_sin_resultado':True}
        if not done:rows.append((path,request))
    return rows


def anteriores(operation):
    path=operation/'preparacion.json'
    if not path.exists():return None  # operación antigua: no inventar el inventario previo
    _,data=leer(path)
    values=data.get('resultados_previos') if isinstance(data,dict) else None
    if not isinstance(values,list) or not all(isinstance(v,str) and re.fullmatch('[0-9a-f]{32}',v) for v in values):
        raise ValueError('Inventario previo inválido.')
    return set(values)


def candidatos(caso_dir,operation,request):
    version=request.get('version')
    if not isinstance(version,str) or not re.fullmatch('[0-9a-f]{32}',version):raise ValueError('Mapeo inválido.')
    mapping=caso_dir/'mapeos_resultados'/version
    preparation=operation/'preparacion.json'
    metadata=leer(preparation)[1] if preparation.exists() else {}
    hashes=metadata.get('archivos') if isinstance(metadata,dict) else None
    names=('mapeo.json','configuracion.json','respuesta.json')
    if hashes is not None:
        if not isinstance(hashes,dict) or set(hashes)!=set(names):raise ValueError('Snapshot de operación inválido.')
        files={name:leer(operation/name)[0] for name in names}
        if any(hashlib.sha256(raw).hexdigest()!=hashes[name] for name,raw in files.items()):raise ValueError('Snapshot de operación alterado.')
    else:files={name:leer(mapping/name)[0] for name in names}  # formato anterior, sin inventario de snapshots
    previous=anteriores(operation);base=caso_dir/'resultados_estructurales'
    if base.resolve()!=base:raise ValueError('Resultados enlazados.')
    found=[]
    for result in sorted(base.iterdir()) if base.is_dir() else []:
        if not re.fullmatch('[0-9a-f]{32}',result.name) or previous is not None and result.name in previous:continue
        try:
            if all(leer(result/target)[0]==files[source] for source,target in
                   (('mapeo.json','mapeo.json'),('configuracion.json','configuracion.json'),('respuesta.json','respuesta_puente.json'))):found.append(result.name)
        except (ValueError,OSError):pass
    return found


def exigir_publicacion(caso_dir,resultado):
    for operation,request in pendientes(caso_dir):
        previous=anteriores(operation)
        if previous is not None and resultado in previous:continue
        if resultado in candidatos(caso_dir,operation,request):
            raise ValueError('Normalización pendiente de recuperación; resultado todavía no aceptado por la operación web.')
