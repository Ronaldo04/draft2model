"""Estado económico de entrega: no inspecciona ventanas ni acredita calidad."""
import hashlib
import json
from pathlib import Path
import re


def estado(root):
    registry=root/'seguimiento/ANTIGRAVITY_ESTADO.json'
    if not registry.is_file():return {'estado':'sin_encargo','requiere_revision':False}
    data=json.loads(registry.read_text(encoding='utf-8'))
    if Path(data['raiz']).resolve()!=root.resolve():raise ValueError('Registro de otra carpeta.')
    marker=root/data['marcador']
    if marker.resolve().parent!=registry.parent.resolve():raise ValueError('Marcador fuera del seguimiento.')
    if not marker.is_file():return {'tarea':data['tarea'],'estado':'sin_marcador','requiere_revision':False}
    if marker.is_symlink() or marker.stat().st_size>100000:raise ValueError('Marcador enlazado o excesivo.')
    raw=marker.read_bytes();result=json.loads(raw.decode('utf-8'));digest=hashlib.sha256(raw).hexdigest()
    if result['tarea']!=data['tarea'] or Path(result['raiz']).resolve()!=root.resolve():raise ValueError('Entrega de otro encargo.')
    if result.get('apis_usadas')!=0 or result.get('etabs_usado') is not False:raise ValueError('Entrega declara operaciones fuera del alcance.')
    if result.get('estado')=='bloqueado':return {'tarea':data['tarea'],'estado':'bloqueo_declarado','requiere_revision':True}
    if result.get('estado')!='entregado':raise ValueError('Estado de marcador desconocido.')
    allowed=set(data['archivos_permitidos']);seen=set()
    for row in result['archivos']:
        name=row['ruta'];path=root/name
        if name not in allowed or name in seen or path.is_symlink() or not path.is_file():raise ValueError('Archivo no autorizado o ausente.')
        if not path.resolve().is_relative_to(root.resolve()):raise ValueError('Archivo fuera de la raíz.')
        if not re.fullmatch('[0-9a-f]{64}',row['sha256']) or hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Hash de entrega distinto: '+name)
        seen.add(name)
    required=set(data.get('archivos_necesarios',('draft2model/politicas_malla_automatica.py','tests/test_politicas_malla_automatica.py','docs/POLITICAS_MALLA_AUTOMATICA.md')))
    if not required<=allowed:raise ValueError('Entregables requeridos fuera del alcance registrado.')
    if not required<=seen:raise ValueError('Faltan entregables necesarios.')
    reviewed=data.get('estado')=='revisado' and data.get('sha256_marcador_revisado')==digest
    return {'tarea':data['tarea'],'estado':'revisado' if reviewed else 'entrega_candidata',
            'requiere_revision':not reviewed,'sha256_marcador':digest,'archivos':len(seen)}


if __name__=='__main__':
    try:result=estado(Path(__file__).resolve().parents[1])
    except (OSError,ValueError,KeyError,TypeError) as error:
        result={'estado':'registro_inconsistente','requiere_revision':True,'motivo':str(error)}
    print(json.dumps(result,ensure_ascii=False))
