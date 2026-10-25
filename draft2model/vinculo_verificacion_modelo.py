"""Vincular una relectura al modelo construido inmutable, sin aprobarlo ni analizarlo."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4

from . import revision_modelo as modelos
from . import verificacion_modelo_guardado as lector
from .gestion_extraccion import _publicar, carpeta_caso, json_desde_bytes

ARCHIVOS = ('solicitud.json', 'expectativa.json', 'criterios.json', 'respuesta.json',
            'resultado_verificacion.json')
TIPO = 'draft2model.verificacion_modelo_construido'


def _bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2)+'\n').encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw):
    return json_desde_bytes(raw, 'evidencia de relectura')


def _fuente(raiz, caso, modelo, huella):
    state = modelos.consultar(raiz, caso, modelo)
    if state['huella_modelo'] != huella:
        raise ValueError('El modelo no coincide con la huella seleccionada.')
    plan = _json(modelos._leer(state['ruta']/'plan.json'))
    edb = state['ruta']/'modelo.edb'
    if _sha(modelos._leer(edb)) != state['origen']['sha256_modelo']:
        raise ValueError('El EDB construido ha cambiado.')
    return state, plan, edb


def _comprobar(files, state, plan):
    request, exp, crit, response, result = [_json(files[n]) for n in ARCHIVOS]
    if not all(isinstance(x, dict) for x in (request, exp, crit, response, result)):
        raise ValueError('Evidencia de relectura incompleta.')
    # Regenerar expectativas desde el plan conservado, no desde un resultado declarado.
    expected = lector.expectativa_desde_plan(plan, ejes_locales_area=exp.get('ejes_locales_area'))
    if expected != exp:
        raise ValueError('Expectativa distinta del plan construido.')
    lector.validar_criterios(crit)
    mode = state['origen']['modo']
    query = lector.consulta_desde_expectativa(exp)
    if (request.get('contrato') != 'draft2model.etabs_solicitud'
            or request.get('version_contrato') != '0.1.0'
            or request.get('version_lector') != lector.VERSION_LECTOR
            or not isinstance(request.get('id'), str) or re.fullmatch('[0-9a-f]{32}',request['id']) is None
            or request.get('operacion') != lector.OPERACION
            or request.get('modo_configurado') != mode
            or request.get('sha256_edb') != state['origen']['sha256_modelo']
            or request.get('huella_plan') != plan['huella_plan']
            or request.get('sha256_expectativa') != _sha(files['expectativa.json'])
            or request.get('consulta') != query):
        raise ValueError('Solicitud de lectura ajena al modelo.')
    if (response.get('contrato') != 'draft2model.etabs_respuesta'
            or response.get('version_contrato') != '0.1.0'
            or response.get('estado') != 'ok' or response.get('operacion') != lector.OPERACION
            or response.get('id_solicitud') != request.get('id')
            or response.get('modo_ejecucion') != mode):
        raise ValueError('Respuesta de lectura ajena a la solicitud.')
    data = response.get('datos')
    if (not isinstance(data, dict) or data.get('sha256_antes') != request['sha256_edb']
            or data.get('sha256_despues') != request['sha256_edb']
            or data.get('consulta') != query or data.get('instancia_cerrada') is not True
            or data.get('version_lector') != request['version_lector']
            or data.get('guardado') is not False or data.get('modificaciones') != []
            or type(data.get('firmas_verificadas')) is not int or data['firmas_verificadas'] <= 0):
        raise ValueError('Respuesta sin garantías de lectura comprobables.')
    if mode == 'real':
        if (data.get('instancia') != 'nueva' or type(data.get('id_proceso')) is not int
                or data['id_proceso'] <= 0 or not isinstance(data.get('inicio_proceso_utc'), str)):
            raise ValueError('Instancia propia de lectura no identificada.')
    elif data.get('instancia') != 'doble':
        raise ValueError('Modo de lectura distinto del modelo construido.')
    observed = data.get('lecturas')
    lector.validar_observado(observed, query)
    if (request.get('version_etabs_esperada') is not None
            and observed.get('version_etabs') != request['version_etabs_esperada']):
        raise ValueError('La versión leída no coincide con la solicitada.')
    compared = lector.comparar(exp, observed, crit)
    if (result.get('contrato') != lector.CONTRATO_RESULTADO
            or result.get('version_contrato') != lector.VERSION
            or result.get('id_lectura') != request['id'] or result.get('modo') != mode
            or result.get('sha256_edb') != request['sha256_edb']
            or result.get('origen_plan') != exp['origen_plan']
            or any(result.get('sha256_'+key) != _sha(files[name]) for key, name in
                   [('solicitud','solicitud.json'), ('expectativa','expectativa.json'),
                    ('criterios','criterios.json'), ('respuesta','respuesta.json')])
            or result.get('guardado') is not False or result.get('ejecutable') is not False
            or result.get('instancia_nueva_cerrada') is not True
            or any(result.get(k) != v for k, v in compared.items())):
        raise ValueError('Resultado no reproducible desde las observaciones conservadas.')
    return result


def verificar(raiz, caso, modelo, *, huella_modelo, verificador, criterios,
              confirmar_lectura=False, ejes_locales_area=None, version_etabs_esperada=None):
    """Leer el snapshot del EDB, revalidar y publicar vínculo inmutable, incluso discrepancias.

    El verificador debe compartir el bloqueo ETABS del resto de operaciones. Un
    modelo fabricado solo admite un verificador doble; nunca se abre como real.
    """
    if confirmar_lectura is not True:
        raise ValueError('Confirme explícitamente la lectura del modelo seleccionado.')
    state, plan, edb = _fuente(raiz, caso, modelo, huella_modelo)
    if verificador.config.modo != state['origen']['modo']:
        raise ValueError('El modo del verificador no corresponde al modelo construido.')
    prep = verificador.preparar_verificacion(edb, state['origen']['sha256_modelo'], plan,
        criterios=criterios, ejes_locales_area=ejes_locales_area,
        version_etabs_esperada=version_etabs_esperada)
    verificador.ejecutar_verificacion(prep, confirmar_lectura=True)
    files = {n: modelos._leer(prep.solicitud.carpeta/n) for n in ARCHIVOS}
    fresh, fresh_plan, _ = _fuente(raiz, caso, modelo, huella_modelo)
    result = _comprobar(files, fresh, fresh_plan)
    ident = uuid4().hex
    record = {'tipo': TIPO, 'version': '0.1.0', 'id': ident, 'caso': caso,
              'modelo': modelo, 'huella_modelo': huella_modelo, 'origen': state['origen'],
              'archivos': {n: _sha(raw) for n, raw in files.items()},
              'estado': result['estado'], 'aprueba_modelo': False, 'autoriza_analisis': False}
    files['registro.json'] = _bytes(record)
    _fuente(raiz, caso, modelo, huella_modelo)  # fuentes vigentes al publicar
    return _publicar(carpeta_caso(raiz, caso), 'verificaciones_modelo', ident, files)


def consultar(raiz, caso, version):
    folder = modelos._folder(raiz, caso, 'verificaciones_modelo', version)
    raw = modelos._leer(folder/'registro.json'); record = _json(raw)
    fields = {'tipo','version','id','caso','modelo','huella_modelo','origen','archivos',
              'estado','aprueba_modelo','autoriza_analisis'}
    if (not isinstance(record, dict) or set(record) != fields or record['tipo'] != TIPO
            or record['version'] != '0.1.0' or record['id'] != version or record['caso'] != caso
            or record['aprueba_modelo'] is not False or record['autoriza_analisis'] is not False):
        raise ValueError('Registro de verificación inválido.')
    state, plan, _ = _fuente(raiz, caso, record['modelo'], record['huella_modelo'])
    files = {n: modelos._leer(folder/n) for n in ARCHIVOS}
    if record['archivos'] != {n: _sha(v) for n, v in files.items()} or record['origen'] != state['origen']:
        raise ValueError('Fuentes de verificación alteradas.')
    result = _comprobar(files, state, plan)
    if result['estado'] != record['estado']:
        raise ValueError('Estado de verificación alterado.')
    _fuente(raiz, caso, record['modelo'], record['huella_modelo'])
    return {'id': version, 'sha256_registro': _sha(raw), 'modelo': record['modelo'],
            'huella_modelo': record['huella_modelo'], 'modo': state['origen']['modo'],
            'resultado': result, 'aprueba_modelo': False, 'autoriza_analisis': False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raiz', required=True, type=Path)
    parser.add_argument('--caso', required=True)
    parser.add_argument('--modelo', required=True)
    parser.add_argument('--huella-modelo', required=True)
    parser.add_argument('--criterios', required=True, type=Path)
    parser.add_argument('--ejes-locales-area', type=Path)
    parser.add_argument('--trabajo', required=True, type=Path)
    parser.add_argument('--bloqueo', required=True, type=Path)
    parser.add_argument('--confirmar-lectura', action='store_true')
    args = parser.parse_args(argv)
    try:
        config = lector.configuracion_real(args.trabajo, args.bloqueo)
        path = verificar(args.raiz, args.caso, args.modelo, huella_modelo=args.huella_modelo,
            verificador=lector.VerificadorModeloGuardado(config),
            criterios=_json(modelos._leer(args.criterios)),
            ejes_locales_area=_json(modelos._leer(args.ejes_locales_area)) if args.ejes_locales_area else None,
            confirmar_lectura=args.confirmar_lectura)
        print(json.dumps(consultar(args.raiz,args.caso,path.name), ensure_ascii=False, indent=2))
    except (ValueError, OSError, RuntimeError):
        print('Verificación no completada; consulte la evidencia local del verificador.')
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
