"""Controles postsolver persistidos: lectura aceptada exacta + criterios declarados, recalculados al consultar.

Usa la lectura aceptada de ServicioLecturas (bytes de respuesta y vínculos verificados), el análisis
aceptado (modelo/EDB) y el núcleo controles_analisis. No ejecuta ETABS, no reescribe el estado del motor
ni resultados nativos y no certifica normativa ni seguridad. Una fuente solver solo declarada queda
marcada como tal y no basta para proyectar "controlado".
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from uuid import uuid4

from . import controles_analisis as nucleo
from . import evidencia_analisis as evidencia
from .gestion_extraccion import json_desde_bytes

CARPETA = 'controles_analisis'
CONTRATO_WEB = 'draft2model.controles_analisis_web'
CAMPOS_CREAR = {'caso', 'expediente_sha256', 'lectura', 'sha256_respuesta', 'avisos_solver_json', 'revisor_declarado',
                'fecha', 'alcance', 'controles', 'confirmacion_explicita'}
MAX_AVISOS = 1024*1024
ERRORES = (ValueError, OSError, TypeError, KeyError, RuntimeError, UnicodeError, OverflowError, RecursionError, IndexError)


class ErrorControles(ValueError):
    """Mensaje público, sin rutas ni contenido privado."""


def _bytes(data):
    return (json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)+'\n').encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _uuid(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{32}', value) is None:
        raise ErrorControles('Identificador inválido; se esperan 32 hexadecimales en minúsculas.')
    return value


def _hex64(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ErrorControles('Huella inválida; se esperan 64 hexadecimales en minúsculas.')
    return value


def _sin_enlace(path, *, falta=False):
    path = Path(path)
    if falta and not os.path.lexists(path):
        return path
    info = os.lstat(path)
    if (path.resolve() != path or stat.S_ISLNK(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
        raise ErrorControles('Directorio o archivo enlazado no permitido.')
    return path


def _leer(path):
    path = _sin_enlace(path)
    if not path.is_file():
        raise ErrorControles('Archivo ausente.')
    return path.read_bytes()


def proyeccion_publica(doc):
    """Contrato del núcleo sin bytes embebidos; conserva SHA, criterios, valores y trazas."""
    out = {k: v for k, v in doc.items() if k != 'fuentes'}
    out['fuentes'] = {k: (None if v is None else {'sha256': v['sha256']}) for k, v in doc['fuentes'].items()}
    return out


class ServicioControles:
    def __init__(self, app):
        self.app = app

    def _caso(self, caso, fp):
        _hex64(fp)
        folder, _, actual = self.app.expediente(caso)
        folder = Path(folder)
        if actual != fp:
            raise ErrorControles('El expediente cambió; vuelve a consultarlo.')
        _sin_enlace(Path(self.app.raiz)); _sin_enlace(folder)
        if folder.parent != Path(self.app.raiz):
            raise ErrorControles('Expediente inválido.')
        return folder

    def _base(self, folder, crear=False):
        base = _sin_enlace(folder/CARPETA, falta=True)
        if os.path.lexists(base):
            if not base.is_dir():
                raise ErrorControles('Directorio de controles inválido.')
        elif crear:
            base.mkdir()
        return base

    def _publico(self, operacion, mensaje):
        try:
            with self.app.lock:
                return operacion()
        except ErrorControles:
            raise
        except ERRORES:
            raise ErrorControles(mensaje) from None

    def _fuentes(self, caso, fp, lectura, sha_respuesta):
        """Lectura aceptada y vigente, sus bytes exactos y el análisis aceptado que vincula modelo/EDB."""
        folder = self._caso(caso, fp)
        job = self.app.lecturas.consultar(caso, _uuid(lectura))
        if (job['estado'] != 'aceptado' or job['vigente'] is not True or job['lectura_verificada'] is not True
                or job['expediente_sha256'] != fp or job['sha256_respuesta'] != _hex64(sha_respuesta)):
            raise ErrorControles('La lectura no está aceptada, vigente o corresponde a otro SHA o expediente.')
        raw = self.app.lecturas.respuesta_bytes(caso, lectura, expediente_sha256=fp)
        if _sha(raw) != sha_respuesta:
            raise ErrorControles('Bytes de respuesta distintos del SHA aceptado.')
        run = _sin_enlace(folder/'analisis_etabs'/_uuid(job['analisis']))
        proof = evidencia.verificar_analisis_aceptado(self.app.raiz, caso, run)
        if proof['sha256_edb_analizado'] != job['sha256_edb'] or proof['datos_sinteticos'] is not job['datos_sinteticos']:
            raise ErrorControles('El análisis aceptado no coincide con la lectura.')
        vinculo = {'lectura_trabajo': lectura, 'lectura_id': job['lectura_id'], 'corrida_analisis': job['analisis'],
                   'modelo': {'id': proof['modelo_id'], 'sha256_edb': proof['sha256_edb_analizado']},
                   'casos': list(job['casos']), 'datos_sinteticos': proof['datos_sinteticos'],
                   'sha256_respuesta': sha_respuesta, 'sha256_aceptacion_analisis': proof['sha256_aceptacion']}
        return raw, vinculo

    # -- registro ------------------------------------------------------------------------
    def crear(self, body):
        def operacion():
            if not isinstance(body, dict) or set(body) != CAMPOS_CREAR:
                raise ErrorControles('Campos exactos requeridos: '+', '.join(sorted(CAMPOS_CREAR))+'.')
            if body['confirmacion_explicita'] is not True:
                raise ErrorControles('Confirma explícitamente la declaración de criterios y aplicabilidad.')
            caso, fp = body['caso'], body['expediente_sha256']
            avisos = body['avisos_solver_json']
            if avisos is not None and (not isinstance(avisos, str) or not avisos.strip() or len(avisos.encode('utf-8')) > MAX_AVISOS):
                raise ErrorControles('avisos_solver_json debe ser null o texto JSON de hasta 1 MiB.')
            avisos_raw = None if avisos is None else avisos.encode('utf-8')
            raw, vinculo = self._fuentes(caso, fp, body['lectura'], body['sha256_respuesta'])
            declaracion = {'caso': caso, 'expediente_sha256': fp, 'corrida_analisis': vinculo['corrida_analisis'],
                           'lectura': vinculo['lectura_id'], 'modelo': vinculo['modelo'], 'datos_sinteticos': vinculo['datos_sinteticos'],
                           'casos': vinculo['casos'], 'sha256_respuesta': vinculo['sha256_respuesta'],
                           'sha256_avisos_solver': None if avisos_raw is None else _sha(avisos_raw),
                           'revisor_declarado': body['revisor_declarado'], 'fecha': body['fecha'], 'alcance': body['alcance'],
                           'controles': body['controles']}
            try:
                doc = nucleo.crear_controles(declaracion, raw, avisos_solver_bytes=avisos_raw)
            except ErrorControles:
                raise
            except ERRORES as error:
                # Mensajes del núcleo: fijos, sin rutas; se exponen para corregir la declaración.
                raise ErrorControles('Declaración o fuentes rechazadas: '+str(error)[:300]) from None
            doc_raw = _bytes(doc)
            folder = self._caso(caso, fp); base = self._base(folder, crear=True); ident = uuid4().hex
            meta = {'contrato': CONTRATO_WEB, 'id': ident, 'caso': caso, 'expediente_sha256': fp,
                    'vinculo': vinculo, 'sha256_controles': _sha(doc_raw), 'creado_utc': datetime.now(timezone.utc).isoformat()}
            with tempfile.TemporaryDirectory(prefix='.ctl-', dir=base) as temporal:
                etapa = Path(temporal).resolve()
                if etapa.parent != base:
                    raise ErrorControles('Temporal fuera del caso.')
                paquete = etapa/'paquete'; paquete.mkdir()
                for name, data in (('controles.json', doc_raw), ('version.json', _bytes(meta))):
                    with (paquete/name).open('xb') as stream:
                        stream.write(data)
                self._cargar(caso, ident, fp, ruta=paquete)
                destino = base/ident
                if os.path.lexists(destino):
                    raise ErrorControles('Destino existente; no se sobrescribe.')
                paquete.rename(destino)
            return self.consultar(caso, ident, expediente_sha256=fp)
        return self._publico(operacion, 'No se registraron los controles: lectura, análisis o declaración sin vigencia.')

    # -- consulta revalidada -------------------------------------------------------------
    def _cargar(self, caso, ident, fp, *, ruta=None):
        folder = self._caso(caso, fp)
        target = _sin_enlace(ruta if ruta is not None else self._base(folder)/_uuid(ident))
        if not target.is_dir() or sorted(p.name for p in target.iterdir()) != ['controles.json', 'version.json']:
            raise ErrorControles('Versión de controles ausente o con contenido inválido.')
        meta_raw, doc_raw = _leer(target/'version.json'), _leer(target/'controles.json')
        meta = json_desde_bytes(meta_raw, 'version.json')
        if (not isinstance(meta, dict) or set(meta) != {'contrato', 'id', 'caso', 'expediente_sha256', 'vinculo', 'sha256_controles', 'creado_utc'}
                or meta['contrato'] != CONTRATO_WEB or meta['id'] != ident or meta['caso'] != caso
                or meta['expediente_sha256'] != fp or meta['sha256_controles'] != _sha(doc_raw)):
            raise ErrorControles('Registro de controles alterado o de otro caso.')
        doc = json_desde_bytes(doc_raw, 'controles.json')
        vinculo = meta['vinculo']
        raw, actual = self._fuentes(caso, fp, vinculo['lectura_trabajo'], vinculo['sha256_respuesta'])
        if actual != vinculo:
            raise ErrorControles('La lectura, el análisis o el modelo cambiaron; los controles no se heredan.')
        d = doc.get('declaracion') if isinstance(doc, dict) else None
        if (not isinstance(d, dict) or d.get('caso') != caso or d.get('expediente_sha256') != fp
                or d.get('lectura') != vinculo['lectura_id'] or d.get('corrida_analisis') != vinculo['corrida_analisis']
                or d.get('modelo') != vinculo['modelo'] or d.get('casos') != vinculo['casos']):
            raise ErrorControles('Declaración de controles ajena al vínculo registrado.')
        solver = doc['fuentes'].get('avisos_solver')
        import base64
        solver_raw = None if solver is None else base64.b64decode(solver['bytes_base64'], validate=True)
        try:
            nucleo.validar_controles(doc, respuesta_bytes=raw, avisos_solver_bytes=solver_raw)
        except ValueError:
            raise ErrorControles('Los controles no se reproducen desde sus fuentes y criterios.') from None
        # La fuente también debe seguir vigente después del recálculo.
        # Releer solo el registro no detecta una lectura/EDB alterados en ese intervalo.
        raw_final, vinculo_final = self._fuentes(caso, fp, vinculo['lectura_trabajo'], vinculo['sha256_respuesta'])
        if raw_final != raw or vinculo_final != vinculo:
            raise ErrorControles('Las fuentes cambiaron durante la validación de controles.')
        if _leer(target/'version.json') != meta_raw or _leer(target/'controles.json') != doc_raw:
            raise ErrorControles('El registro cambió durante la consulta.')
        return meta, doc

    def consultar(self, caso, version, *, expediente_sha256):
        def operacion():
            meta, doc = self._cargar(caso, _uuid(version), expediente_sha256)
            v = meta['vinculo']
            return {'id': meta['id'], 'caso': caso, 'expediente_sha256': expediente_sha256, 'creado_utc': meta['creado_utc'],
                    'sha256_controles': meta['sha256_controles'], 'lectura': v['lectura_trabajo'], 'analisis': v['corrida_analisis'],
                    'modelo': v['modelo'], 'casos': v['casos'], 'datos_sinteticos': v['datos_sinteticos'], 'vigente': True,
                    'contenido': proyeccion_publica(doc),
                    'estado_motor': 'csi_4_terminado_no_equivale_a_controlado', 'seleccion_automatica': False,
                    'aprueba_resultados': False, 'conformidad_normativa': 'no_evaluada', 'verificacion_profesional': False}
        return self._publico(operacion, 'Controles sin vigencia: lectura, análisis, registro o criterios cambiaron.')

    def listar(self, caso, *, expediente_sha256):
        def operacion():
            base = self._base(self._caso(caso, expediente_sha256))
            rows = []
            for path in sorted(base.iterdir()) if base.is_dir() else []:
                if re.fullmatch('[0-9a-f]{32}', path.name) is None:
                    continue
                try:
                    item = self.consultar(caso, path.name, expediente_sha256=expediente_sha256)
                    c = item['contenido']
                    rows.append({'id': path.name, 'vigente': True, 'analisis': item['analisis'], 'lectura': item['lectura'],
                                 'estado_global': c['estado_global'], 'apto_proyeccion_controlado': c['apto_proyeccion_controlado'],
                                 'sha256_controles': item['sha256_controles']})
                except ERRORES:
                    rows.append({'id': path.name, 'vigente': False, 'problemas': ['controles_no_vigentes']})
            self._caso(caso, expediente_sha256)
            return {'caso': caso, 'expediente_sha256': expediente_sha256, 'versiones': rows, 'seleccion_automatica': False}
        return self._publico(operacion, 'No se pudieron listar los controles.')
