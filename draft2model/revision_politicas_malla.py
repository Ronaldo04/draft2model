"""Servicio de políticas explícitas de malla sobre preparaciones inmutables.

Conserva reglas y declaración en un hijo borrador; nunca aprueba ni ejecuta ETABS.
"""
from __future__ import annotations

import copy
import hashlib
import json
from datetime import date
from pathlib import Path

from . import gestion_geometria as gg
from . import modelo_estructural as modelo
from . import politicas_malla_automatica as motor
from .validacion_geometria import validar_geometria

SENTINEL = 'DECISION-FORMULARIO'
CAMPOS = {'caso', 'expediente_sha256', 'version', 'sha256_configuracion', 'reglas', 'declaracion'}


def _bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _codigo():
    nombres = ('revision_politicas_malla.py', 'politicas_malla_automatica.py', 'malla_preparacion.py',
               'particion_superficies.py', 'compatibilidad_particiones.py', 'triangulacion_particiones.py',
               'validacion_geometria.py', 'geometria_aberturas.py', 'geometria_superficies.py', 'modelo_estructural.py')
    return {n: _sha(Path(__file__).with_name(n).read_bytes()) for n in nombres}


CODIGO_CARGADO = _codigo()


def _declaracion(valor):
    if (not isinstance(valor, dict) or set(valor) != {'declarado_por', 'fecha', 'alcance'} or
            any(not isinstance(v, str) or not v.strip() or len(v) > 2000 for v in valor.values())):
        raise ValueError('Completa declarante, fecha y alcance de la decisión de malla.')
    try:
        if len(valor['fecha']) != 10:
            raise ValueError()
        date.fromisoformat(valor['fecha'])
    except ValueError:
        raise ValueError('Fecha de declaración inválida.') from None
    return copy.deepcopy(valor)


def _sustituir(valor, nueva):
    if isinstance(valor, list):
        return [_sustituir(v, nueva) for v in valor]
    if isinstance(valor, dict):
        return {k: nueva if k == 'fuente' and v == SENTINEL else _sustituir(v, nueva) for k, v in valor.items()}
    return valor


def _usa_formulario(valor):
    if isinstance(valor, list):
        return any(_usa_formulario(v) for v in valor)
    if isinstance(valor, dict):
        return any(k == 'fuente' and v == SENTINEL or _usa_formulario(v) for k, v in valor.items())
    return False


class ServicioPoliticasMalla:
    def __init__(self, app):
        self.app = app
        self._codigo_cargado = copy.deepcopy(CODIGO_CARGADO)

    def _exigir_codigo(self):
        if _codigo() != self._codigo_cargado:
            raise ValueError('El código de políticas de malla cambió; actualiza el servidor antes de continuar.')

    def _calcular(self, body):
        self._exigir_codigo()
        servicio = self.app.preparacion_configuracion
        caso, fp = body['caso'], body['expediente_sha256']
        data, meta, meta_sha = servicio._cargar(caso, fp, body['version'])
        if meta['sha256_configuracion'] != body['sha256_configuracion']:
            raise ValueError('La configuración preparada cambió; vuelve a abrirla.')
        consulta = gg.consultar_version(self.app.raiz, caso, data['geometria_origen']['version_id'])
        geo, comp = consulta.geometria, consulta.comprobacion
        if (not comp.correcta or comp.sha256_geometria != data['geometria_origen']['sha256_geometria'] or
                comp.huella_contenido != data['geometria_origen']['huella_contenido']):
            raise ValueError('La geometría de la preparación perdió vigencia.')
        comprobacion = validar_geometria(geo)
        if not comprobacion.consistente or comprobacion.datos_sinteticos != data['datos_sinteticos']:
            raise ValueError('La naturaleza o geometría de la preparación no corresponde.')
        decision = {'caso': caso, 'expediente_sha256': fp, 'preparacion': body['version'],
                    'sha256_configuracion': meta['sha256_configuracion'],
                    'reglas_formulario': copy.deepcopy(body['reglas']),
                    'declaracion': copy.deepcopy(body['declaracion']), 'identidad': 'declarada_no_verificada'}
        temporal, reglas = copy.deepcopy(data), copy.deepcopy(body['reglas'])
        fuente_decision = None
        if _usa_formulario(reglas):
            decision['declaracion'] = _declaracion(body['declaracion'])
            decision_sha = _sha(_bytes(decision))
            fuente_decision = {'id': 'DECISION-MALLA-' + decision_sha[:24],
                              'descripcion': 'Reglas de ingeniería declaradas en formulario; identidad declarada, no verificada. ' + _bytes(decision['declaracion']).decode('utf-8'),
                              'referencia': 'registro.json#origen.decision;sha256=' + decision_sha + ';version_creadora_en_cadena_de_padres',
                              'sha256': decision_sha}
            if any(f.get('id') == fuente_decision['id'] for f in temporal['fuentes']):
                raise ValueError('ID de fuente de decisión ya existente; no se sobrescribe.')
            temporal['fuentes'].append(fuente_decision)
            reglas = _sustituir(reglas, fuente_decision['id'])
        propuesta = motor.previsualizar_politicas_malla(geo, temporal, reglas)
        candidato = motor.aplicar_politicas_malla(geo, temporal, reglas) if propuesta['listo_para_aplicar'] else temporal
        validacion = modelo.validar_configuracion(candidato, geo).a_dict()
        enlace = {'entrada': copy.deepcopy(body), 'sha256_registro_padre': meta_sha,
                  'sha256_geometria_canonica': _sha(_bytes(geo)), 'codigo': self._codigo_cargado,
                  'decision': decision, 'fuente_decision': fuente_decision, 'reglas_calculo': reglas,
                  'propuesta': propuesta}
        huella = _sha(_bytes(enlace))
        self._exigir_codigo()
        vista = {'caso': caso, 'expediente_sha256': fp, 'version': body['version'],
                 'sha256_configuracion': meta['sha256_configuracion'], 'huella_propuesta': huella,
                 'sha256_algoritmo': self._codigo_cargado['politicas_malla_automatica.py'],
                 'codigo': copy.deepcopy(self._codigo_cargado), 'propuesta': propuesta,
                 'malla_calculable': propuesta['huella_preparacion'] is not None,
                 'politicas_completas': propuesta['listo_para_aplicar'],
                 'configuracion_completa': False, 'validacion': validacion,
                 'otros_faltantes_tecnicos': [f for f in validacion.get('faltantes', [])
                      if not f.get('ruta', '').startswith(('$.nodos_derivados.', '$.subdivision_frames.'))],
                 'fuente_decision': fuente_decision, 'aprueba_ingenieria': False, 'ejecutable_etabs': False}
        return vista, candidato, meta, meta_sha, enlace

    def previsualizar(self, body):
        if not isinstance(body, dict) or set(body) != CAMPOS:
            raise ValueError('Campos de vista previa de malla inválidos.')
        with self.app.lock:
            return self._calcular(body)[0]

    def aplicar(self, body):
        campos = CAMPOS | {'confirmacion_explicita', 'huella_propuesta', 'sha256_algoritmo'}
        if not isinstance(body, dict) or set(body) != campos or body['confirmacion_explicita'] is not True:
            raise ValueError('Confirma explícitamente las políticas de malla previsualizadas.')
        _declaracion(body['declaracion'])
        with self.app.lock:
            entrada = {k: copy.deepcopy(body[k]) for k in CAMPOS}
            vista, candidato, meta, meta_sha, enlace = self._calcular(entrada)
            if body['huella_propuesta'] != vista['huella_propuesta'] or body['sha256_algoritmo'] != vista['sha256_algoritmo']:
                raise ValueError('La propuesta, sus reglas, fuentes o código cambiaron; vuelve a previsualizar.')
            if not vista['politicas_completas']:
                raise ValueError('Las políticas mantienen errores, conflictos o pendientes; no se aplican parcialmente.')
            padre = {'id': body['version'], 'sha256_registro': meta_sha, 'sha256_configuracion': meta['sha256_configuracion']}
            self._exigir_codigo()
            saved = self.app.preparacion_configuracion._guardar(body['caso'], body['expediente_sha256'], candidato,
                padre=padre, origen={'tipo': 'politicas_malla_en_formulario', 'decision': enlace['decision'],
                                    'reglas_calculo': enlace['reglas_calculo'], 'huella_propuesta': vista['huella_propuesta'],
                                    'huella_malla': vista['propuesta']['huella_preparacion'],
                                    'codigo': enlace['codigo'], 'confirmacion_explicita': True})
            return {**saved, 'politicas_malla': vista, 'aprueba_ingenieria': False, 'ejecutable_etabs': False}
