"""Modelo construido inmutable y revisión propia antes de autorizar análisis."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from .gestion_extraccion import carpeta_caso, _carpeta_propia, _publicar, json_desde_bytes
from .operaciones_etabs import (VERSION_PLAN_LIQUIDOS, VERSION_PLAN_MALLA, generar_plan, generar_plan_malla, validar_plan,
                                validar_plan_liquidos, validar_plan_malla)

ARCHIVOS = ('configuracion.json', 'plan.json', 'aceptacion_integracion.json',
            'solicitud.json', 'respuesta.json', 'traza.jsonl', 'modelo.edb')
CONTROLES = ('geometria_conectividad', 'materiales_secciones', 'cargas_masa',
             'apoyos_diafragmas', 'casos_combinaciones')


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)+'\n').encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw):
    return json_desde_bytes(raw, 'evidencia del modelo')


def _leer(path):
    path = Path(path).absolute()
    if path.resolve() != path or not path.is_file():
        raise ValueError('Evidencia ausente, enlazada o con ruta no normalizada.')
    return path.read_bytes()


def _validar(raiz, caso, files):
    config, plan, acceptance, request, response = [_json(files[n]) for n in ARCHIVOS[:5]]
    if not all(isinstance(item, dict) for item in (config, plan, acceptance, request, response)):
        raise ValueError('Evidencias JSON deben ser objetos.')
    if not isinstance(config, dict) or config.get('caso') != caso:
        raise ValueError('Configuración de otro caso.')
    if not isinstance(plan, dict) or not isinstance(plan.get('opciones'), dict):
        raise ValueError('Plan inválido.')
    # Regenera por versión: 0.4 (malla) o el recorrido 0.1, que rechaza configuraciones de desarrollo.
    regenerated = (generar_plan_malla if config.get('version_contrato') in ('0.4.0', '0.5.0') else generar_plan)(raiz, config, **plan['opciones']).datos
    # El catálogo informativo de capacidades pendientes puede evolucionar sin
    # cambiar una sola operación ya ejecutada. Conservar y validar su hash
    # histórico, comparando estrictamente todo el contenido operativo.
    def contenido_operativo(value):
        return {k:v for k,v in value.items() if k not in ('huella_plan','pendientes')}
    problemas = {VERSION_PLAN_MALLA: validar_plan_malla, VERSION_PLAN_LIQUIDOS: validar_plan_liquidos}.get(plan.get('version_contrato'), validar_plan)(plan)
    if problemas or contenido_operativo(regenerated) != contenido_operativo(plan):
        raise ValueError('Plan/configuración/geometría no vigentes.')
    mode = acceptance.get('modo')
    if mode not in ('real', 'doble') or (mode == 'doble' and config['datos_sinteticos'] is not True):
        raise ValueError('Solo se admite doble para datos sintéticos.')
    saved = {'ruta': plan['opciones']['destino_guardado'], 'sha256': _sha(files['modelo.edb'])}
    if (acceptance.get('aceptada') is not True or acceptance.get('origen') != plan['origen']
            or acceptance.get('huella_plan') != plan['huella_plan'] or acceptance.get('guardado') != saved
            or acceptance.get('analisis_ejecutado') is not False or acceptance.get('aprueba_modelo') is not False):
        raise ValueError('Falta aceptación integrada coherente del modelo construido.')
    if (request.get('operacion') != 'ejecutar_plan' or request.get('modo_configurado') != mode
            or request.get('origen') != plan['origen'] or request.get('huella_plan') != plan['huella_plan']
            or request.get('operaciones') != plan['operaciones'] or request.get('destino') != saved['ruta']
            or request.get('sha256_copia') != config['plantilla']['sha256']):
        raise ValueError('Solicitud distinta del plan aceptado.')
    names = {s['registra']: s['debe_ser'] for op in plan['operaciones'] for s in op.get('salidas', [])}
    progress = response.get('progreso') or {}
    result = response.get('datos') or {}
    if (response.get('estado') != 'ok' or response.get('operacion') != 'ejecutar_plan'
            or response.get('modo_ejecucion') != mode or response.get('id_solicitud') != request.get('id')
            or result.get('guardado') != saved or result.get('huella_plan') != plan['huella_plan']
            or result.get('analisis_ejecutado') is not False or result.get('aprueba_modelo') is not False
            or progress.get('operaciones_ejecutadas') != len(plan['operaciones'])
            or progress.get('mapeo_nombres') != names):
        raise ValueError('Respuesta no corresponde al modelo construido.')
    trace = [_json(line) for line in files['traza.jsonl'].splitlines() if line.strip()]
    expected = [(op['orden'], op['metodo'], event) for op in plan['operaciones'] for event in ('inicio', 'fin')]
    if [(row.get('orden'), row.get('metodo'), row.get('evento')) for row in trace] != expected:
        raise ValueError('Traza incompleta, reordenada o ajena al plan.')
    for op, row in zip(plan['operaciones'], trace[1::2]):
        if row.get('retorno') != 0 or isinstance(row.get('retorno'), bool):
            raise ValueError('Traza sin retorno API satisfactorio.')
        outputs = {s['registra']: s['debe_ser'] for s in op.get('salidas', [])}
        if row.get('salidas', {}) != outputs:
            raise ValueError('Salidas de traza distintas al plan.')
    return {'caso': caso, 'datos_sinteticos': config['datos_sinteticos'], 'modo': mode,
            'huella_plan': plan['huella_plan'], 'sha256_modelo': saved['sha256'],
            'origen': plan['origen']}


def registrar(raiz, caso, configuracion, plan, corrida):
    """Capturar un EDB aceptado; nunca hereda aprobación de la configuración."""
    folder = Path(corrida).absolute()
    if (folder/'revision_integracion_fallida.json').exists():
        raise ValueError('La corrida tiene una revisión de integración fallida.')
    files = {n: _leer(folder/n) for n in ARCHIVOS[2:6]}
    files['configuracion.json'] = _bytes(configuracion)
    files['plan.json'] = _bytes(plan)
    if _json(_leer(folder/'plan.json')) != plan:
        raise ValueError('El plan de la corrida no coincide.')
    acceptance = _json(files['aceptacion_integracion.json'])
    files['modelo.edb'] = _leer(Path(acceptance['guardado']['ruta']))
    origin = _validar(raiz, caso, files)
    ident = uuid4().hex
    manifest = {'tipo': 'draft2model.modelo_construido', 'version': '0.1.0', 'id': ident,
        'creado_utc': datetime.now(timezone.utc).isoformat(), 'origen': origin,
        'archivos': {n: _sha(raw) for n, raw in files.items()}, 'revision': 'pendiente',
        'productor': 'declarado_no_autenticado', 'analisis_ejecutado': False}
    files['version.json'] = _bytes(manifest)
    # Volver a comprobar originales vinculados justo antes de publicar.
    _validar(raiz, caso, files)
    return _publicar(carpeta_caso(raiz, caso), 'modelos_construidos', ident, files)


def _folder(raiz, caso, group, ident):
    if not isinstance(ident, str) or not re.fullmatch('[0-9a-f]{32}', ident):
        raise ValueError('Identificador inválido.')
    folder = _carpeta_propia(carpeta_caso(raiz, caso), group)/ident
    if folder.resolve() != folder or not folder.is_dir():
        raise ValueError('Registro ausente o enlazado.')
    return folder


def consultar(raiz, caso, modelo):
    folder = _folder(raiz, caso, 'modelos_construidos', modelo)
    raw = _leer(folder/'version.json'); manifest = _json(raw)
    if not isinstance(manifest, dict):
        raise ValueError('Registro de modelo inválido.')
    files = {n: _leer(folder/n) for n in ARCHIVOS}
    origin = _validar(raiz, caso, files)
    if (manifest.get('tipo') != 'draft2model.modelo_construido' or manifest.get('version') != '0.1.0'
            or manifest.get('id') != modelo or manifest.get('origen') != origin
            or manifest.get('archivos') != {n: _sha(v) for n, v in files.items()}
            or manifest.get('revision') != 'pendiente' or manifest.get('analisis_ejecutado') is not False
            or manifest.get('productor') != 'declarado_no_autenticado'):
        raise ValueError('Registro de modelo alterado.')
    return {'modelo_id': modelo, 'huella_modelo': _sha(raw), 'ruta': folder,
            'origen': origin, 'estado': 'pendiente', 'aprobacion': None}


def aprobar(raiz, caso, modelo, *, huella_esperada, revisor, fecha, alcance, controles):
    state = consultar(raiz, caso, modelo)
    if state['huella_modelo'] != huella_esperada:
        raise ValueError('El modelo no coincide con la huella revisada.')
    if not all(isinstance(v, str) and v.strip() for v in (revisor, fecha, alcance)):
        raise ValueError('Revisor, fecha y alcance requeridos.')
    if date.fromisoformat(fecha).isoformat() != fecha:
        raise ValueError('Fecha debe ser AAAA-MM-DD.')
    if not isinstance(controles, dict) or set(controles) != set(CONTROLES) or any(v is not True for v in controles.values()):
        raise ValueError('Todos los controles requieren confirmación explícita.')
    approval = {'tipo': 'draft2model.aprobacion_modelo', 'version': '0.1.0', 'caso': caso,
        'modelo_id': modelo, 'huella_modelo': huella_esperada, 'origen': state['origen'],
        'revisor_declarado': revisor, 'identidad_revisor': 'declarada_no_verificada',
        'fecha': fecha, 'alcance': alcance, 'controles': controles, 'autoriza_analisis': True}
    consultar(raiz, caso, modelo)
    return _publicar(carpeta_caso(raiz, caso), 'aprobaciones_modelo', uuid4().hex,
                     {'aprobacion.json': _bytes(approval)})


def consultar_aprobacion(raiz, caso, aprobacion):
    folder = _folder(raiz, caso, 'aprobaciones_modelo', aprobacion)
    raw = _leer(folder/'aprobacion.json'); record = _json(raw)
    if not isinstance(record, dict) or not isinstance(record.get('modelo_id'), str):
        raise ValueError('Registro de aprobación inválido.')
    state = consultar(raiz, caso, record['modelo_id'])
    required = {'tipo','version','caso','modelo_id','huella_modelo','origen','revisor_declarado',
                'identidad_revisor','fecha','alcance','controles','autoriza_analisis'}
    if (set(record) != required or record['tipo'] != 'draft2model.aprobacion_modelo'
            or record['version'] != '0.1.0' or record['caso'] != caso
            or record['huella_modelo'] != state['huella_modelo'] or record['origen'] != state['origen']
            or record['identidad_revisor'] != 'declarada_no_verificada' or record['autoriza_analisis'] is not True
            or set(record['controles']) != set(CONTROLES) or any(v is not True for v in record['controles'].values())
            or not all(isinstance(record[n], str) and record[n].strip() for n in ('revisor_declarado','alcance','fecha'))
            or date.fromisoformat(record['fecha']).isoformat() != record['fecha']):
        raise ValueError('Aprobación no vigente o inválida.')
    return {**state, 'estado': 'aprobado', 'aprobacion': record,
            'aprobacion_id': aprobacion, 'sha256_aprobacion': _sha(raw)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raiz', type=Path, required=True); parser.add_argument('--caso', required=True)
    commands = parser.add_subparsers(dest='operacion', required=True)
    register = commands.add_parser('registrar')
    for name in ('configuracion','plan','corrida'): register.add_argument('--'+name, type=Path, required=True)
    consult = commands.add_parser('consultar'); consult.add_argument('--modelo', required=True)
    approve = commands.add_parser('aprobar')
    for name in ('modelo','huella-esperada','revisor','fecha','alcance'): approve.add_argument('--'+name, required=True)
    for name in CONTROLES: approve.add_argument('--confirmar-'+name.replace('_','-'), action='store_true')
    gate = commands.add_parser('comprobar-aprobacion'); gate.add_argument('--aprobacion', required=True)
    args = parser.parse_args(argv)
    try:
        if args.operacion == 'registrar':
            output = registrar(args.raiz,args.caso,_json(_leer(args.configuracion)),_json(_leer(args.plan)),args.corrida)
        elif args.operacion == 'consultar': output = consultar(args.raiz,args.caso,args.modelo)
        elif args.operacion == 'comprobar-aprobacion': output = consultar_aprobacion(args.raiz,args.caso,args.aprobacion)
        else:
            output = aprobar(args.raiz,args.caso,args.modelo,huella_esperada=args.huella_esperada,
                revisor=args.revisor,fecha=args.fecha,alcance=args.alcance,
                controles={name:getattr(args,'confirmar_'+name) for name in CONTROLES})
        print(json.dumps(output, ensure_ascii=False, default=str, indent=2)); return 0
    except (ValueError, OSError, KeyError, TypeError, AttributeError) as error:
        import sys
        print('Revisión de modelo rechazada: '+str(error), file=sys.stderr); return 2


if __name__ == '__main__': raise SystemExit(main())
