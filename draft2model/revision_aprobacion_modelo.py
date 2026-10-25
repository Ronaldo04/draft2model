"""Revisión propia de modelos construidos; nunca calcula ni aprueba resultados."""
from pathlib import Path
import re
import stat

from . import revision_modelo as rm


class ErrorRevisionModelo(ValueError):
    def __init__(self, codigo):
        self.codigo = codigo
        super().__init__(codigo)


def _uuid(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{32}', value) is None:
        raise ErrorRevisionModelo('identificador_invalido')


def _seguro(path):
    info = path.lstat()
    if (path.resolve() != path or stat.S_ISLNK(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        raise ErrorRevisionModelo('ruta_no_permitida')
    return path


class ServicioRevisionModelo:
    def __init__(self, app):
        self.app = app

    def _expediente(self, caso, fingerprint):
        if not isinstance(fingerprint, str) or re.fullmatch('[0-9a-f]{64}', fingerprint) is None:
            raise ErrorRevisionModelo('huella_expediente_invalida')
        folder, _, current = self.app.expediente(caso)
        if current != fingerprint:
            raise ErrorRevisionModelo('expediente_cambio')
        folder = _seguro(Path(folder))
        if folder.parent != Path(self.app.raiz):
            raise ErrorRevisionModelo('caso_invalido')
        return folder

    def _modelo(self, caso, modelo, fingerprint):
        _uuid(modelo)
        self._expediente(caso, fingerprint)
        projected = self.app.resultados.consultar_modelo(caso, modelo, expediente_sha256=fingerprint)
        checked = rm.consultar(self.app.raiz, caso, modelo)
        if checked['huella_modelo'] != projected['huella_modelo']:
            raise ErrorRevisionModelo('modelo_cambio')
        self._expediente(caso, fingerprint)
        return projected

    @staticmethod
    def _aprobar_proyeccion(checked):
        approval = checked['aprobacion']
        return {'id': checked['aprobacion_id'], 'sha256_aprobacion': checked['sha256_aprobacion'],
                'huella_modelo': checked['huella_modelo'],
                'revisor_declarado': approval['revisor_declarado'],
                'identidad_revisor': 'declarada_no_verificada', 'fecha': approval['fecha'],
                'alcance': approval['alcance'], 'controles': dict(approval['controles']),
                'autoriza_analisis': True}

    def _consultar(self, caso, modelo, fingerprint):
        snapshot = self._modelo(caso, modelo, fingerprint)
        folder = self._expediente(caso, fingerprint)
        base = folder/'aprobaciones_modelo'
        try:
            _seguro(base)
        except FileNotFoundError:
            paths = []
        else:
            if not base.is_dir():
                raise ErrorRevisionModelo('directorio_aprobaciones_invalido')
            paths = sorted(base.iterdir())
        approvals = []; invalid = False
        for path in paths:
            if re.fullmatch('[0-9a-f]{32}', path.name) is None:
                continue
            try:
                _seguro(path)
                _seguro(path/'aprobacion.json')
                checked = rm.consultar_aprobacion(self.app.raiz, caso, path.name)
                if checked['modelo_id'] == modelo and checked['huella_modelo'] == snapshot['huella_modelo']:
                    approvals.append(self._aprobar_proyeccion(checked))
            except (ValueError, OSError, RuntimeError, KeyError, TypeError, AttributeError):
                invalid = True
        if self._modelo(caso, modelo, fingerprint) != snapshot:
            raise ErrorRevisionModelo('modelo_cambio')
        # Las aprobaciones tienen identidad propia: no escoger la última carpeta.
        for approval in approvals:
            checked = rm.consultar_aprobacion(self.app.raiz, caso, approval['id'])
            if self._aprobar_proyeccion(checked) != approval:
                raise ErrorRevisionModelo('aprobacion_cambio')
        self._expediente(caso, fingerprint)
        return {'caso': caso, 'modelo': modelo, 'expediente_sha256': fingerprint,
                'huella_modelo': snapshot['huella_modelo'], 'origen': snapshot['origen'],
                'estado': 'aprobado' if approvals else 'pendiente', 'aprobaciones': approvals,
                'controles_requeridos': list(rm.CONTROLES),
                'advertencias': ['aprobaciones_no_verificables_en_caso'] if invalid else [],
                'identidad_revisor': 'declarada_no_verificada',
                'analisis_ejecutado': False, 'aprueba_resultados': False}

    def consultar(self, caso, modelo, *, expediente_sha256):
        try:
            with self.app.lock:
                return self._consultar(caso, modelo, expediente_sha256)
        except ErrorRevisionModelo:
            raise
        except (ValueError, OSError, RuntimeError, KeyError, TypeError, AttributeError):
            raise ErrorRevisionModelo('revision_modelo_no_vigente') from None

    def aprobar(self, body):
        try:
            with self.app.lock:
                fields = {'caso','modelo','expediente_sha256','huella_modelo','revisor','fecha','alcance','controles','confirmacion_explicita'}
                if not isinstance(body, dict) or set(body) != fields:
                    raise ErrorRevisionModelo('campos_invalidos')
                if body['confirmacion_explicita'] is not True:
                    raise ErrorRevisionModelo('confirmacion_requerida')
                controls = body['controles']
                if not isinstance(controls, dict) or set(controls) != set(rm.CONTROLES) or any(value is not True for value in controls.values()):
                    raise ErrorRevisionModelo('controles_explicitos_requeridos')
                if not all(isinstance(body[k], str) and body[k].strip() for k in ('revisor','fecha','alcance')):
                    raise ErrorRevisionModelo('declaracion_incompleta')
                snapshot = self._modelo(body['caso'], body['modelo'], body['expediente_sha256'])
                if body['huella_modelo'] != snapshot['huella_modelo']:
                    raise ErrorRevisionModelo('modelo_cambio')
                # Cada publicación es una declaración nueva, nunca aprobación heredada.
                target = rm.aprobar(self.app.raiz, body['caso'], body['modelo'],
                    huella_esperada=body['huella_modelo'], revisor=body['revisor'],
                    fecha=body['fecha'], alcance=body['alcance'], controles=dict(controls))
                checked = rm.consultar_aprobacion(self.app.raiz, body['caso'], target.name)
                if checked['modelo_id'] != body['modelo'] or checked['huella_modelo'] != body['huella_modelo']:
                    raise ErrorRevisionModelo('aprobacion_cambio')
                result = self._consultar(body['caso'], body['modelo'], body['expediente_sha256'])
                if target.name not in {item['id'] for item in result['aprobaciones']}:
                    raise ErrorRevisionModelo('aprobacion_cambio')
                return {**result, 'aprobacion_registrada': target.name}
        except ErrorRevisionModelo:
            raise
        except (ValueError, OSError, RuntimeError, KeyError, TypeError, AttributeError):
            raise ErrorRevisionModelo('aprobacion_rechazada') from None
