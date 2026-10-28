"""Consultas locales de paquetes normalizados y modelos; nunca ejecuta ni aprueba."""
from __future__ import annotations

from pathlib import Path
import re
import stat

from . import evidencia_analisis as evidencia
from . import revision_modelo as modelos
from .normalizacion_web import exigir_publicacion


class ErrorResultados(ValueError):
    """Error publicable sin rutas ni contenido privado."""


class ServicioResultados:
    def __init__(self, app):
        self.app = app

    @staticmethod
    def _id(version):
        if not isinstance(version, str) or re.fullmatch(r'[0-9a-f]{32}', version) is None:
            raise ErrorResultados('Identificador de versión inválido.')

    @staticmethod
    def _sin_enlace(path):
        info = path.lstat()
        if (path.resolve() != path or stat.S_ISLNK(info.st_mode)
                or getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
            raise ErrorResultados('Directorio o archivo enlazado no permitido.')

    def _expediente(self, caso, esperada=None):
        folder, _, fingerprint = self.app.expediente(caso)
        root = Path(self.app.raiz)
        folder = Path(folder)
        self._sin_enlace(root)
        self._sin_enlace(folder)
        if folder.parent != root or not folder.is_dir():
            raise ErrorResultados('Expediente inválido o ausente.')
        if esperada is not None and fingerprint != esperada:
            raise ErrorResultados('El expediente cambió; vuelve a consultarlo.')
        return folder, fingerprint

    def _grupo(self, folder, grupo):
        base = folder / grupo
        if base.exists() or base.is_symlink():
            self._sin_enlace(base)
            if not base.is_dir():
                raise ErrorResultados('Directorio de versiones inválido.')
        return base

    def _version(self, folder, grupo, version):
        self._id(version)
        target = self._grupo(folder, grupo) / version
        self._sin_enlace(target)
        if not target.is_dir():
            raise ErrorResultados('Versión inválida o ausente.')
        # La proyección pública nunca debe seguir enlaces de una versión.
        for child in target.iterdir():
            self._sin_enlace(child)
            if not child.is_file():
                raise ErrorResultados('Contenido de versión inválido.')
        return target

    def _resultado(self, folder, caso, version, fingerprint):
        self._version(folder, 'resultados_estructurales', version)
        exigir_publicacion(folder,version)
        checked = evidencia.verificar_resultado_normalizado(self.app.raiz, caso, version)
        data = checked['datos']
        return {'id': version, 'caso': caso, 'expediente_sha256': fingerprint,
                'vigente': True, 'estado': checked['estado'],
                'huella': checked['huella'], 'datos': data,
                'metadatos': {'configuracion_id': data['configuracion']['id'],
                    'huella_configuracion': data['configuracion']['sha256'],
                    'geometria_version_id': data['geometria']['id'],
                    'sha256_geometria': data['geometria']['sha256'],
                    'sha256_edb_leido': checked['sha256_edb'],
                    'corrida_tablas_id': data['corrida_id'],
                    'mapeo_revision_vigente': True},
                'analisis_vinculado': False, 'evidencia_analisis': None,
                'revision_resultados': 'pendiente', 'conformidad_normativa': 'no_evaluada',
                'aprueba_resultados': False}

    def _modelo(self, folder, caso, version, fingerprint):
        self._version(folder, 'modelos_construidos', version)
        checked = modelos.consultar(self.app.raiz, caso, version)
        origin = checked['origen']
        source = origin['origen']
        return {'id': version, 'caso': caso, 'expediente_sha256': fingerprint,
                'vigente': True, 'estado': 'modelo_verificado',
                'huella_modelo': checked['huella_modelo'],
                'origen': {'datos_sinteticos': origin['datos_sinteticos'],
                    'modo': origin['modo'], 'huella_plan': origin['huella_plan'],
                    'sha256_modelo': origin['sha256_modelo'],
                    'configuracion_id': source['configuracion_id'],
                    'huella_configuracion': source['huella_configuracion'],
                    'geometria_version_id': source['geometria']['version_id'],
                    'sha256_geometria': source['geometria']['sha256_geometria']},
                'revision': 'pendiente', 'aprobacion': None,
                'analisis_vinculado': False, 'aprueba_resultados': False}

    def _listar(self, caso, grupo, consultar):
        try:
            with self.app.lock:
                folder, fingerprint = self._expediente(caso)
                base = self._grupo(folder, grupo)
                rows = []
                for path in sorted(base.iterdir()) if base.is_dir() else []:
                    if re.fullmatch(r'[0-9a-f]{32}', path.name) is None:
                        continue
                    try:
                        data = consultar(folder, caso, path.name, fingerprint)
                        if grupo == 'resultados_estructurales':
                            res = data['datos']
                            summary = {'creado_utc': res['creado_utc'], 'motor': res['motor'],
                                       'datos_sinteticos': res['datos_sinteticos'],
                                       'configuracion_id': res['configuracion']['id'],
                                       'corrida_tablas_id': res['corrida_id'],
                                       'estado': data['estado'], 'analisis_vinculado': False,
                                       'aprueba_resultados': False}
                        else:
                            summary = {**data['origen'], 'estado': data['estado'],
                                       'revision': data['revision'], 'aprobacion': None, 'analisis_vinculado': False,
                                       'aprueba_resultados': False}
                        rows.append({'id': path.name, 'vigente': True, 'problemas': [], 'resumen': summary})
                    except (ValueError, OSError, TypeError, KeyError, RuntimeError):
                        rows.append({'id': path.name, 'vigente': False,
                                     'problemas': ['version_no_vigente'], 'resumen': None})
                self._expediente(caso, fingerprint)
                return {'caso': caso, 'expediente_sha256': fingerprint, 'versiones': rows}
        except ErrorResultados:
            raise
        except (ValueError, OSError, TypeError, KeyError, RuntimeError):
            raise ErrorResultados('No se pudo consultar el expediente o sus versiones.') from None

    def _consultar(self, caso, version, expediente_sha256, consultar):
        try:
            with self.app.lock:
                self._id(version)
                if not isinstance(expediente_sha256, str) or re.fullmatch(r'[0-9a-f]{64}', expediente_sha256) is None:
                    raise ErrorResultados('Huella de expediente inválida.')
                folder, fingerprint = self._expediente(caso, expediente_sha256)
                result = consultar(folder, caso, version, fingerprint)
                self._expediente(caso, fingerprint)
                return result
        except ErrorResultados:
            raise
        except (ValueError, OSError, TypeError, KeyError, RuntimeError):
            raise ErrorResultados('Versión inválida, ausente o sin evidencia vigente; vuelve a consultar el expediente.') from None

    def _inventario(self, caso, grupo):
        """Solo IDs de versiones publicadas, SIN comprobarlas (Continuación288): `vigente` es null y `verificacion` «pendiente».

        No lee ni muestra metadatos sin verificar y no habilita uso alguno: abrir una versión (consultar_*) ejecuta la comprobación
        completa de fuentes, huellas y vigencia. El listado completo (modo por omisión) no cambia.
        """
        try:
            with self.app.lock:
                folder, fingerprint = self._expediente(caso)
                base = self._grupo(folder, grupo)
                rows = [{'id': path.name, 'vigente': None, 'verificacion': 'pendiente', 'problemas': [], 'resumen': None}
                        for path in (sorted(base.iterdir()) if base.is_dir() else []) if re.fullmatch(r'[0-9a-f]{32}', path.name)]
                self._expediente(caso, fingerprint)
                return {'caso': caso, 'expediente_sha256': fingerprint, 'versiones': rows, 'modo': 'inventario',
                        'aviso': 'Versiones sin comprobar: la comprobación completa se ejecuta al abrir cada una.'}
        except ErrorResultados:
            raise
        except (ValueError, OSError, TypeError, KeyError, RuntimeError):
            raise ErrorResultados('No se pudo consultar el expediente o sus versiones.') from None

    def listar_resultados(self, caso, *, inventario=False):
        if inventario:
            return self._inventario(caso, 'resultados_estructurales')
        return self._listar(caso, 'resultados_estructurales', self._resultado)

    def consultar_resultado(self, caso, version, *, expediente_sha256):
        return self._consultar(caso, version, expediente_sha256, self._resultado)

    def listar_modelos(self, caso, *, inventario=False):
        if inventario:
            return self._inventario(caso, 'modelos_construidos')
        return self._listar(caso, 'modelos_construidos', self._modelo)

    def consultar_modelo(self, caso, version, *, expediente_sha256):
        return self._consultar(caso, version, expediente_sha256, self._modelo)
