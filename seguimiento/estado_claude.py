"""Sonda local compacta de entrega: no abre ventanas ni ejecuta tareas/pruebas."""
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent.parent
RAIZ_PRODUCTO = {'README.md', 'requirements.txt', 'requirements-win-py310.lock',
                 'Abrir revision de planos.cmd', 'Abrir control de avance.cmd'}


def leer(path):
    if path.resolve() != path or path.stat().st_size > 65536:
        raise ValueError('registro ajeno o demasiado grande')
    return json.loads(path.read_text(encoding='utf-8'))


def ruta(nombre):
    if not isinstance(nombre, str):
        raise ValueError('ruta inválida')
    path = ROOT / nombre
    if path.resolve() != path or not path.is_relative_to(ROOT):
        raise ValueError('ruta fuera del proyecto o enlazada')
    return path


def orden_entrega(par):
    """Dependencias por etapa; dentro de ella, fecha real antes que UUID aleatorio.

    Entregas históricas sin fecha conservan orden estable anterior. Las fechas
    presentes deben tener zona explícita para no depender del reloj local.
    """
    marker, item = par
    fecha = item.get('creado_utc')
    if fecha is None:
        cronologia = (0, datetime.min.replace(tzinfo=timezone.utc))
    else:
        if not isinstance(fecha, str):
            raise ValueError('fecha de entrega inválida')
        try:
            instante = datetime.fromisoformat(fecha.replace('Z', '+00:00'))
        except ValueError as exc:
            raise ValueError('fecha de entrega inválida') from exc
        if instante.tzinfo is None:
            raise ValueError('fecha de entrega sin zona horaria')
        cronologia = (1, instante.astimezone(timezone.utc))
    return (item['etapa'], cronologia, marker.as_posix())


def actividad_auditoria(control, numero):
    """Metadatos de archivos directos, sin leer entregables ni acreditar ejecución."""
    prefixes = control.get('prefijos_autorizados')
    if not isinstance(prefixes, list) or not prefixes:
        raise ValueError('perímetro de auditoría inválido')
    expected = f'seguimiento/claude_ruta/diagnostico_pdf_{numero}/'
    for prefix in prefixes:
        ok = (isinstance(prefix, str) and re.fullmatch(
            r'seguimiento/claude_ruta/[a-z0-9_]+_'+numero+r'/', prefix)) if control.get('modo') == 'auditoria_aislada' else prefix == expected
        if not ok:
            raise ValueError('perímetro de auditoría inválido')
    seen, latest, limited = set(), None, False
    for prefix in prefixes:
        folder = ruta(prefix.rstrip('/'))
        if not folder.exists():
            continue
        for index, child in enumerate(folder.iterdir()):
            if index >= 1000:
                limited = True
                break
            child = ruta(child.relative_to(ROOT).as_posix())
            try:
                if child.is_file():
                    seen.add(child)
                    modified = child.stat().st_mtime
                    latest = modified if latest is None else max(latest, modified)
            except FileNotFoundError:
                continue  # Un archivo temporal puede desaparecer durante la observación.
    return {'archivos_presentes': len(seen), 'alcance_conteo': 'archivos directos de carpetas autorizadas',
            'conteo_truncado': limited,
            'ultima_modificacion_utc': datetime.fromtimestamp(latest, timezone.utc).isoformat() if latest is not None else None,
            'actividad_no_prueba_ejecucion': True}


def estado():
    control = leer(ROOT / 'seguimiento/CLAUDE_ESTADO.json')
    task = control['tarea']
    auditoria_pdf = control.get('modo') in ('auditoria_pdf', 'auditoria_pdf_309', 'auditoria_aislada')
    numero_auditoria = str(task).rsplit('_', 1)[-1] if auditoria_pdf else None
    if auditoria_pdf and (len(numero_auditoria) != 3 or not numero_auditoria.isdigit()):
        raise ValueError('identificador de auditoría inválido')
    if control.get('modo') == 'ruta_autonoma':
        return estado_ruta(control)
    if control['estado'] in ('revisado', 'cerrado'):
        return {'tarea': task, 'estado': control['estado'], 'requiere_revision': False}
    paths = {name: ruta(name) for name in control['archivos']}
    marker = ruta(control['marcador'])
    if not marker.exists():
        return {'tarea': task, 'estado': 'sin_marcador',
                **(actividad_auditoria(control, numero_auditoria) if auditoria_pdf else
                   {'archivos_presentes': sum(p.is_file() for p in paths.values())}),
                'requiere_revision': False}
    data = leer(marker)
    etiqueta = str(data.get('tarea', '')).lower().replace('_', '').replace('-', '').replace(' ', '')
    tarea_correcta = etiqueta in tuple(p + numero_auditoria for p in ('', 'pdf', 'diagnosticopdf', 'encargo')) if auditoria_pdf else data.get('tarea') == task
    if control.get('modo') == 'auditoria_aislada':
        tarea_correcta = data.get('tarea') == task
    estados = ('entregado', 'bloqueado', 'entrega_candidata', 'bloqueo_declarado') if auditoria_pdf else ('entregado', 'bloqueado')
    if not tarea_correcta or data.get('estado') not in estados:
        raise ValueError('marcador no corresponde al encargo vigente')
    if data['estado'] in ('bloqueado', 'bloqueo_declarado'):
        return {'tarea': task, 'estado': 'bloqueo_declarado', 'requiere_revision': True}
    entries = data.get('archivos', data.get('archivos_finales'))
    if auditoria_pdf:
        entries = data.get('archivos_permitidos_sha256', entries)
    # Se aceptan mapa ruta:sha256 o lista de {ruta,sha256}; el marcador no aprueba nada.
    if isinstance(entries, list):
        entries = {item['ruta']: item['sha256'] for item in entries}
    if not isinstance(entries, dict) or not entries:
        raise ValueError('inventario de entrega vacío o inválido')
    # Entrega ampliada: conserva hash previo/final; solo el final acredita los bytes.
    entries = {name: value['final'] if isinstance(value, dict) else value
               for name, value in entries.items()}
    if any(not isinstance(value, str) or len(value) != 64
           or any(c not in '0123456789abcdef' for c in value) for value in entries.values()):
        raise ValueError('hash final inválido')
    prefixes = control.get('prefijos_autorizados')
    if prefixes is not None:
        permitidos = (f'seguimiento/claude_ruta/diagnostico_pdf_{numero_auditoria}/',) if auditoria_pdf else ('draft2model/', 'tests/', 'scripts/', 'docs/')
        if control.get('modo') == 'auditoria_aislada':
            if not isinstance(prefixes,list):
                raise ValueError('perímetro de auditoría inválido')
            permitidos = tuple(p for p in prefixes if isinstance(p,str) and re.fullmatch(
                r'seguimiento/claude_ruta/[a-z0-9_]+_'+numero_auditoria+r'/',p))
        extras = control.get('archivos_adicionales_autorizados', [])
        if auditoria_pdf and extras:
            raise ValueError('la auditoría no admite archivos fuera de su carpeta')
        if not isinstance(extras, list) or any(not isinstance(name, str) for name in extras):
            raise ValueError('archivos adicionales inválidos')
        if (not isinstance(prefixes, list) or not prefixes
                or any(prefix not in permitidos for prefix in prefixes)
                or any(not isinstance(name, str) or not (name in extras or any(name.startswith(prefix) for prefix in prefixes)) for name in entries)
                or not set(paths) <= set(entries)):
            raise ValueError('archivo fuera del alcance consolidado')
        paths = {name: ruta(name) for name in entries}
    elif set(entries) != set(paths):
        raise ValueError('inventario de entrega diferente al autorizado')
    for name, path in paths.items():
        if not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('archivo ausente o demasiado grande')
        if hashlib.sha256(path.read_bytes()).hexdigest() != entries[name]:
            raise ValueError('hash de entrega no coincide; puede seguir en edición')
    return {'tarea': task, 'estado': 'entrega_candidata', 'requiere_revision': True,
            'marcador_sha256': hashlib.sha256(marker.read_bytes()).hexdigest()}


def estado_ruta(control):
    """Revisa snapshots inmutables: el árbol vivo puede pertenecer a la etapa siguiente."""
    task = control['tarea']
    path = ruta(control['estado_ruta'])
    if not path.exists():
        return {'tarea': task, 'estado': 'sin_marcador', 'requiere_revision': False}
    data = leer(path)
    if data['tarea'] != task or data['estado'] not in ('trabajando', 'bloqueado', 'finalizado'):
        raise ValueError('estado de ruta inválido')
    marker_name = data.get('ultima_entrega')
    revisiones_path = ruta(control['revisiones_ruta'])
    revisadas = leer(revisiones_path)['revisadas'] if revisiones_path.exists() else []
    if not marker_name:
        return {'tarea': task, 'estado': 'bloqueo_declarado' if data['estado']=='bloqueado' else 'sin_marcador',
                'etapa': data.get('etapa_actual'), 'requiere_revision': data['estado']=='bloqueado'}
    if not isinstance(marker_name, str) or not marker_name.startswith(('seguimiento/claude_ruta/entregas/', 'entregas/')):
        raise ValueError('entrega fuera de ruta')
    marker = ruta(marker_name)
    entrega = leer(marker)
    if (entrega['tarea'] != task or entrega['estado'] not in ('entregado', 'bloqueado')
            or entrega['etapa'] not in ('01','02','03','04','05','06')):
        raise ValueError('entrega no corresponde a ruta')
    # La ruta puede avanzar varias etapas entre sondeos. ultima_entrega no es
    # una cola: conservar las anteriores sin exigir que Claude espere revisión.
    pendientes = {}
    for base in ('entregas', 'seguimiento/claude_ruta/entregas'):
        carpeta = ruta(base)
        if not carpeta.exists():
            continue
        for candidato in carpeta.glob('*/manifiesto.json'):
            relativo = candidato.relative_to(ROOT).as_posix()
            candidato = ruta(relativo)
            item = leer(candidato)
            if item.get('tarea') != task:
                continue
            if (item.get('estado') not in ('entregado', 'bloqueado')
                    or item.get('etapa') not in ('01','02','03','04','05','06')
                    or not isinstance(item.get('id'), str) or not item['id']):
                raise ValueError('entrega histórica incoherente')
            if item['id'] not in revisadas:
                if item['id'] in pendientes:
                    raise ValueError('id de entrega duplicado')
                pendientes[item['id']] = (candidato, item)
    if entrega['id'] not in revisadas and entrega['id'] not in pendientes:
        pendientes[entrega['id']] = (marker, entrega)
    if not pendientes:
        return {'tarea': task, 'estado': 'sin_marcador', 'etapa': data.get('etapa_actual'),
                'estado_ruta': data['estado'], 'requiere_revision': False}
    marker, entrega = min(pendientes.values(), key=orden_entrega)
    marker_name = marker.relative_to(ROOT).as_posix()
    entries = entrega['archivos']
    if not isinstance(entries, dict) or not entries:
        raise ValueError('snapshot sin inventario')
    for name in entries:
        if (not isinstance(name, str) or '\\' in name or ':' in name or '..' in name.split('/')
                or not (name in RAIZ_PRODUCTO or any(name.startswith(p) for p in ('draft2model/','scripts/','tests/','examples/','docs/')))):
            raise ValueError('archivo ajeno al alcance de implementación')
    snapshot = ruta(entrega['snapshot']['ruta'])
    if snapshot.parent != marker.parent or snapshot.stat().st_size > 64*1024*1024:
        raise ValueError('snapshot ajeno o demasiado grande')
    if hashlib.sha256(snapshot.read_bytes()).hexdigest() != entrega['snapshot']['sha256']:
        raise ValueError('hash de snapshot diferente')
    with zipfile.ZipFile(snapshot) as z:
        archivos = [i for i in z.infolist() if not i.is_dir()]
        if (len(archivos) != len(entries) or {i.filename for i in archivos} != set(entries)
                or sum(i.file_size for i in archivos) > 64*1024*1024):
            raise ValueError('inventario ZIP incoherente')
        for info in archivos:
            if hashlib.sha256(z.read(info)).hexdigest() != entries[info.filename]:
                raise ValueError('bytes de archivo distintos del manifiesto')
    return {'tarea': task, 'estado': 'entrega_candidata', 'requiere_revision': True,
            'etapa': entrega['etapa'], 'entrega_id': entrega['id'], 'manifiesto': marker_name,
            'fuente_revision': 'snapshot_inmutable', 'marcador_sha256': hashlib.sha256(marker.read_bytes()).hexdigest()}


if __name__ == '__main__':
    try:
        result = estado()
    except (ValueError, OSError, KeyError, TypeError, zipfile.BadZipFile):
        result = {'estado': 'registro_inconsistente', 'requiere_revision': True}
    print(json.dumps(result, ensure_ascii=False, separators=(',', ':')))
