"""Planes geométricos inmutables ligados a una versión comprobada, sin ETABS."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from uuid import uuid4

from . import gestion_geometria as g
from .gestion_extraccion import _publicar, _carpeta_propia, json_desde_bytes, carpeta_caso
from .plan_modelado import preparar_plan_modelado


def _bytes(data):
    return (json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode('utf-8')


def _origen(consulta):
    comp = consulta.comprobacion
    return {'caso': consulta.caso, 'version_id': consulta.identificador,
            'sha256_geometria': comp.sha256_geometria,
            'huella_contenido': comp.huella_contenido,
            'expediente_sha256': comp.expediente_sha256,
            'sha256_metadatos': hashlib.sha256((consulta.ruta / g.ARCHIVO_METADATOS).read_bytes()).hexdigest()}


def _consultar(raiz, caso, version):
    consulta = g.consultar_version(raiz, caso, version)
    if not consulta.comprobacion.correcta:
        raise g.ErrorEvidencia('Geometría de origen no vigente.', consulta.comprobacion.problemas)
    return consulta


def generar_plan_version(raiz: Path, caso: str, version: str) -> Path:
    """Admite borrador/faltantes, los conserva y no concede aprobación al plan."""
    consulta = _consultar(raiz, caso, version)
    origen = _origen(consulta)
    plan = preparar_plan_modelado(consulta.geometria)
    plan['version_geometria'] = origen
    # Detectar cambios durante el cálculo, incluidos metadatos de aprobación.
    if _origen(_consultar(raiz, caso, version)) != origen:
        raise g.ErrorGestion('La versión cambió durante la generación; no se guarda.')
    raw = _bytes(plan)
    registro = {'tipo': 'draft2model.version_plan', 'version_registro': '0.1.0',
                'origen': origen, 'sha256_plan': hashlib.sha256(raw).hexdigest(),
                'aprobacion_plan': None, 'ejecutable_en_etabs': False}
    return _publicar(carpeta_caso(raiz, caso), 'planes', uuid4().hex,
                     {'plan.json': raw, 'version.json': _bytes(registro)})


def comprobar_plan(raiz: Path, caso: str, identificador: str) -> dict:
    """Comprueba fuente vigente, bytes y concordancia completa con el cálculo actual."""
    import re
    if not re.fullmatch(g.PATRON_VERSION, identificador or ''):
        raise g.ErrorGestion('Identificador de plan inválido.')
    folder = _carpeta_propia(carpeta_caso(raiz, caso), 'planes') / identificador
    if folder.resolve() != folder or not folder.is_dir():
        raise g.ErrorGestion('Plan ausente o enlazado.')
    for name in ('plan.json', 'version.json'):
        if (folder / name).resolve() != folder / name:
            raise g.ErrorGestion('Archivo de plan enlazado.')
    raw = (folder / 'plan.json').read_bytes()
    plan = json_desde_bytes(raw, 'plan.json')
    meta = json_desde_bytes((folder / 'version.json').read_bytes(), 'version.json')
    if not isinstance(meta, dict) or not isinstance(meta.get('origen'), dict):
        raise g.ErrorGestion('Registro de plan inválido.')
    origen = meta['origen']
    consulta = _consultar(raiz, caso, origen.get('version_id'))
    esperado = preparar_plan_modelado(consulta.geometria)
    esperado['version_geometria'] = _origen(consulta)
    registro = {'tipo': 'draft2model.version_plan', 'version_registro': '0.1.0',
                'origen': esperado['version_geometria'],
                'sha256_plan': hashlib.sha256(raw).hexdigest(),
                'aprobacion_plan': None, 'ejecutable_en_etabs': False}
    if plan != esperado or meta != registro:
        raise g.ErrorEvidencia('Plan alterado o desactualizado.',
                               ['El plan o su registro no corresponde a la versión geométrica vigente.'])
    return {'correcta': True, 'plan_id': identificador, 'origen': origen,
            'ejecutable_en_etabs': False, 'aprobacion_plan': None}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operacion', choices=('generar', 'comprobar'))
    parser.add_argument('--raiz', type=Path, default=Path('data/private'))
    parser.add_argument('--caso', required=True)
    parser.add_argument('--version', help='Versión geométrica para generar')
    parser.add_argument('--plan', help='Identificador del plan para comprobar')
    args = parser.parse_args(argv)
    try:
        if args.operacion == 'generar':
            if not args.version:
                parser.error('generar requiere --version')
            print(generar_plan_version(args.raiz, args.caso, args.version))
        else:
            if not args.plan:
                parser.error('comprobar requiere --plan')
            print(json.dumps(comprobar_plan(args.raiz, args.caso, args.plan), ensure_ascii=False))
        return 0
    except g.ErrorEvidencia as exc:
        print(str(exc), file=sys.stderr)
        return 2
    except (ValueError, OSError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
