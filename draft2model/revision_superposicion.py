"""Contraste espacial explícito entre geometría versionada y página original.

Esquema por nivel desde el contrato geométrico vigente (XY y unidad del propio contrato) y
correspondencia declarada con tres anclas no colineales nodo→punto normalizado de la página
original renderizada por la revisión local. La transformación afín se calcula solo con esas
anclas: no se infiere escala, unidad ni correspondencia desde bboxes. No aprueba ingeniería,
no edita geometría y una superposición no prueba que un elemento esté documentado en el plano.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
import struct
import tempfile
from uuid import uuid4

from .gestion_extraccion import json_desde_bytes

CONTRATO = 'draft2model.superposicion_geometria'
VERSION = '0.1.0'
VERSION_SUPERFICIES = '0.2.0'
VERSION_PLANO3D = '0.3.0'
VERSION_ABERTURAS = '0.4.0'
VERSION_GEOMETRIA_ABERTURAS = '0.3.0'
EPS_BASE3D = 1e-12  # consistencia computacional; nunca tolerancia de ingeniería
CARPETA = 'superposiciones'
CAMPOS_CREAR = {'caso', 'expediente_sha256', 'geometria', 'huella_geometria', 'sha256_geometria', 'archivo', 'pagina',
                'nivel', 'anclas', 'revisor_declarado', 'fecha', 'motivo', 'confirmacion_explicita'}
CAMPOS_CREAR_SUPERFICIES = (CAMPOS_CREAR - {'nivel'}) | {'version_contrato', 'plano', 'superficies'}
MIN_FORMA = 1e-3   # área del triángulo / (lado mayor)^2: rechaza anclas casi colineales
TOL = 1e-9
AVISO = ('Correspondencia declarada con tres anclas; transformación afín exacta en esas anclas. No infiere escala ni '
         'unidades desde el dibujo, no prueba que un elemento esté documentado y no aprueba ingeniería ni habilita modelado.')
ERRORES = (ValueError, OSError, TypeError, KeyError, RuntimeError, UnicodeError, OverflowError, ZeroDivisionError, IndexError)


class ErrorSuperposicion(ValueError):
    """Mensaje público, sin rutas ni contenido privado."""


def _bytes(data):
    return (json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)+'\n').encode('utf-8')


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _uuid(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{32}', value) is None:
        raise ErrorSuperposicion('Identificador inválido; se esperan 32 hexadecimales en minúsculas.')
    return value


def _hex64(value):
    if not isinstance(value, str) or re.fullmatch('[0-9a-f]{64}', value) is None:
        raise ErrorSuperposicion('Huella inválida; se esperan 64 hexadecimales en minúsculas.')
    return value


def _num(value):
    return type(value) in (int, float) and math.isfinite(value)


def _sin_enlace(path, *, falta=False):
    path = Path(path)
    if falta and not os.path.lexists(path):
        return path
    info = os.lstat(path)
    if (path.resolve() != path or stat.S_ISLNK(info.st_mode)
            or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0)):
        raise ErrorSuperposicion('Directorio o archivo enlazado no permitido.')
    return path


def _leer(path):
    path = _sin_enlace(path)
    if not path.is_file():
        raise ErrorSuperposicion('Archivo ausente.')
    return path.read_bytes()


def _png_dimensiones(raw):
    if raw[:8] != b'\x89PNG\r\n\x1a\n' or raw[12:16] != b'IHDR':
        raise ErrorSuperposicion('La vista previa no es PNG válido.')
    width, height = struct.unpack('>II', raw[16:24])
    if not width or not height:
        raise ErrorSuperposicion('Vista previa vacía.')
    return [width, height]


def _forma(p):
    """Medida adimensional de no colinealidad de tres puntos (0 colineal; ~0.43 equilátero)."""
    (x1, y1), (x2, y2), (x3, y3) = p
    area2 = abs((x2-x1)*(y3-y1)-(x3-x1)*(y2-y1))
    lado = max(math.dist(p[0], p[1]), math.dist(p[1], p[2]), math.dist(p[0], p[2]))
    return 0.0 if lado == 0 else area2/(2*lado*lado)


def transformacion(modelo, imagen):
    """Afín exacta modelo XY → página normalizada desde tres pares; matriz [[a,b,c],[d,e,f]]."""
    if _forma(modelo) < MIN_FORMA or _forma(imagen) < MIN_FORMA:
        raise ErrorSuperposicion('Anclas colineales, repetidas o numéricamente inestables; elige tres puntos bien separados.')
    (x1, y1), (x2, y2), (x3, y3) = modelo
    det = x1*(y2-y3)-y1*(x2-x3)+(x2*y3-x3*y2)
    if det == 0:
        raise ErrorSuperposicion('Anclas del modelo colineales.')
    inv = [[(y2-y3)/det, (y3-y1)/det, (y1-y2)/det],
           [(x3-x2)/det, (x1-x3)/det, (x2-x1)/det],
           [(x2*y3-x3*y2)/det, (x3*y1-x1*y3)/det, (x1*y2-x2*y1)/det]]
    filas = []
    for k in (0, 1):
        t = [imagen[0][k], imagen[1][k], imagen[2][k]]
        filas.append([sum(inv[r][c]*t[c] for c in range(3)) for r in range(3)])
    for (x, y), (u, v) in zip(modelo, imagen):
        pu, pv = aplicar(filas, x, y)
        if abs(pu-u) > TOL or abs(pv-v) > TOL:
            raise ErrorSuperposicion('Transformación numéricamente inestable.')
    if not all(_num(v) for fila in filas for v in fila):
        raise ErrorSuperposicion('Transformación no finita.')
    return filas


def aplicar(m, x, y):
    return m[0][0]*x+m[0][1]*y+m[0][2], m[1][0]*x+m[1][1]*y+m[1][2]


class ServicioSuperposicion:
    def __init__(self, app):
        self.app = app

    # -- fuentes vigentes (APIs públicas existentes) ------------------------------------
    def _geometria(self, caso, version, fp):
        _uuid(version); _hex64(fp)
        current = self.app.geometria(caso, version)  # gestion_geometria valida evidencia y contrato
        if current['expediente_sha256'] != fp:
            raise ErrorSuperposicion('El expediente cambió; vuelve a consultarlo.')
        datos = current['datos']
        if datos.get('id') != caso:
            raise ErrorSuperposicion('La geometría pertenece a otro caso.')
        return current

    def _fuente(self, caso, archivo, pagina, fp):
        if not isinstance(archivo, str) or not archivo or type(pagina) is not int or pagina < 1:
            raise ErrorSuperposicion('Selecciona archivo original y página válidos.')
        raw, _, current = self.app._original(caso, archivo)
        if current != fp:
            raise ErrorSuperposicion('El expediente cambió; vuelve a consultarlo.')
        preview = self.app.pagina(caso, archivo, pagina, fp)  # misma página visible que /api/pagina
        return {'archivo': archivo, 'sha256_original': _sha(raw), 'pagina': pagina,
                'sha256_preview': _sha(preview), 'preview_px': _png_dimensiones(preview),
                'sistema': 'pagina_visible_normalizada_0_1'}

    @staticmethod
    def _esquema(current, version):
        datos = current['datos']
        nodos = {n['id']: n for n in datos['nodos']}
        niveles = []
        for nivel in datos['niveles']:
            muros = []
            for m in datos['muros']:
                if m['nivel_inferior'] != nivel['id']:
                    continue  # planta del nivel: muros que nacen en él
                a, b = nodos[m['nodo_inicio']], nodos[m['nodo_fin']]
                muros.append({'id': m['id'], 'nivel_inferior': m['nivel_inferior'], 'nivel_superior': m['nivel_superior'],
                              'inicio': {'id': a['id'], 'x': a['x'], 'y': a['y']}, 'fin': {'id': b['id'], 'x': b['x'], 'y': b['y']},
                              'longitud': math.hypot(b['x']-a['x'], b['y']-a['y']), 'espesor': m['espesor']})
            niveles.append({'id': nivel['id'], 'nombre': nivel.get('nombre'), 'cota': nivel['cota'], 'muros': muros})
        xs = [n['x'] for n in datos['nodos']]; ys = [n['y'] for n in datos['nodos']]
        validacion = current['comprobacion'].get('validacion') or {}
        resultado = {'geometria': version, 'caso': datos['id'], 'huella_geometria': current['huella'],
                'sha256_geometria': current['sha256_geometria'], 'unidad_longitud': datos['unidad_longitud'],
                'estado_revision': datos['revision']['estado'], 'procedencia': datos['procedencia'].get('tipo'),
                'disponible_para_modelado': bool(validacion.get('disponible_para_modelado')) and datos['revision']['estado'] == 'aprobado',
                'nodos': [{'id': n['id'], 'x': n['x'], 'y': n['y']} for n in datos['nodos']], 'niveles': niveles,
                'extension': {'x': [min(xs), max(xs)] if xs else [0, 0], 'y': [min(ys), max(ys)] if ys else [0, 0]},
                'aviso': 'Esquema métrico del contrato geométrico; sin correspondencia no se alinea con ningún plano.'}
        if datos.get('version_contrato') in (VERSION_SUPERFICIES, VERSION_GEOMETRIA_ABERTURAS):
            from .validacion_geometria import validar_geometria
            comprobada = validar_geometria(datos)
            if not comprobada.consistente:
                raise ErrorSuperposicion('Superficies geométricas inconsistentes.')
            normalizada = comprobada.geometria_m
            resultado.update(version_geometria=datos['version_contrato'],
                             vertices_m=normalizada['vertices'], superficies=[])
            for superficie in normalizada['superficies']:
                derivado = comprobada.derivados_m['superficies'][superficie['id']]
                item = {**superficie, **derivado}
                if datos['version_contrato'] == VERSION_GEOMETRIA_ABERTURAS:
                    item['aberturas'] = [{**a, **comprobada.derivados_m['aberturas'][a['id']]} for a in normalizada['aberturas'] if a['superficie'] == superficie['id']]
                resultado['superficies'].append(item)
        return resultado

    def esquema(self, caso, version, *, expediente_sha256):
        def operacion():
            current = self._geometria(caso, version, expediente_sha256)
            return self._esquema(current, version)
        return self._publico(operacion, 'Geometría sin vigencia, de otro caso o expediente cambiado.')

    def _publico(self, operacion, mensaje):
        try:
            with self.app.lock:
                return operacion()
        except ErrorSuperposicion:
            raise
        except ERRORES:
            raise ErrorSuperposicion(mensaje) from None

    def _caso(self, caso, fp):
        _hex64(fp)
        folder, _, actual = self.app.expediente(caso)
        folder = Path(folder)
        if actual != fp:
            raise ErrorSuperposicion('El expediente cambió; vuelve a consultarlo.')
        _sin_enlace(Path(self.app.raiz)); _sin_enlace(folder)
        if folder.parent != Path(self.app.raiz):
            raise ErrorSuperposicion('Expediente inválido.')
        return folder

    def _base(self, folder, crear=False):
        base = _sin_enlace(folder/CARPETA, falta=True)
        if os.path.lexists(base):
            if not base.is_dir():
                raise ErrorSuperposicion('Directorio de superposiciones inválido.')
        elif crear:
            base.mkdir()
        return base

    # -- registro ------------------------------------------------------------------------
    @staticmethod
    def _plano_superficies(esquema, plano, seleccion, *, version_geometria=VERSION_SUPERFICIES):
        if (esquema.get('version_geometria') != version_geometria or not isinstance(plano, dict)
                or set(plano) != {'tipo', 'cota_m'} or plano['tipo'] != 'horizontal' or not _num(plano['cota_m'])):
            raise ErrorSuperposicion('Declara plano horizontal y cota física Z finita en metros para geometría v0.2.')
        if (not isinstance(seleccion, list) or not seleccion or not all(isinstance(v, str) for v in seleccion)
                or len(set(seleccion)) != len(seleccion)):
            raise ErrorSuperposicion('Selecciona superficies explícitas, distintas y existentes.')
        tabla = {s['id']: s for s in esquema['superficies']}
        superficies = []
        for ident in seleccion:
            if ident not in tabla:
                raise ErrorSuperposicion('Superficie seleccionada inexistente.')
            superficie = tabla[ident]
            if any(p[2] != plano['cota_m'] for p in superficie['vertices_m']):
                raise ErrorSuperposicion('Superficie fuera de la cota horizontal declarada o inclinada; esta vista no la proyecta como piso.')
            superficies.append(superficie)
        return {'id': None, 'muros': [], 'superficies': superficies}

    @staticmethod
    def _plano3d_superficies(esquema, plano, seleccion, *, version_geometria=VERSION_SUPERFICIES):
        campos = {'tipo', 'origen_m', 'eje_u', 'eje_v'}
        if (esquema.get('version_geometria') != version_geometria or not isinstance(plano, dict)
                or set(plano) != campos or plano['tipo'] != 'base_ortonormal_3d'
                or any(not isinstance(plano[k], list) or len(plano[k]) != 3 or not all(_num(x) for x in plano[k])
                       for k in ('origen_m', 'eje_u', 'eje_v'))):
            raise ErrorSuperposicion('Declara origen XYZ físico en metros y dos ejes 3D unitarios y ortogonales.')
        origen, u, v = (plano[k] for k in ('origen_m', 'eje_u', 'eje_v'))
        producto = lambda a, b: math.fsum(x*y for x, y in zip(a, b))
        if (abs(math.hypot(*u)-1) > EPS_BASE3D or abs(math.hypot(*v)-1) > EPS_BASE3D
                or abs(producto(u, v)) > EPS_BASE3D):
            raise ErrorSuperposicion('Los ejes declarados no son unitarios/ortogonales; no se normalizan ni reparan.')
        normal = [u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0]]
        if (not isinstance(seleccion, list) or not seleccion or not all(isinstance(s, str) for s in seleccion)
                or len(set(seleccion)) != len(seleccion)):
            raise ErrorSuperposicion('Selecciona superficies 3D explícitas y distintas.')
        tabla = {s['id']: s for s in esquema['superficies']}
        superficies, coordenadas, criterios = [], {}, {}
        for ident in seleccion:
            if ident not in tabla:
                raise ErrorSuperposicion('Superficie seleccionada inexistente.')
            s = tabla[ident]
            puntos = s['vertices_m']
            escala = max(abs(p[k]-puntos[0][k]) for p in puntos for k in range(3))
            magnitud = max(abs(x) for p in puntos+[origen] for x in p)
            tolerancia = max(EPS_BASE3D*escala, 64*math.ulp(magnitud))
            if not _num(tolerancia) or escala <= 0 or tolerancia/escala > 1e-6:
                raise ErrorSuperposicion('Origen/coordenadas del plano numéricamente inestables respecto del contorno.')
            uv = []
            for nombre, p in zip(s['vertices'], puntos):
                delta = [p[k]-origen[k] for k in range(3)]
                if not all(_num(x) for x in delta) or abs(producto(delta, normal)) > tolerancia:
                    raise ErrorSuperposicion('Superficie fuera del plano 3D declarado; no se aplana automáticamente.')
                par = [producto(delta, u), producto(delta, v)]
                if not all(_num(x) for x in par):
                    raise ErrorSuperposicion('Coordenadas del plano no representables.')
                coordenadas[nombre] = {'id': nombre, 'x': par[0], 'y': par[1]}
                uv.append(par)
            superficies.append({**s, 'vertices_plano_m': uv})
            criterios[ident] = {'escala_contorno_m': escala, 'tolerancia_computacional_m': tolerancia}
        return {'id': None, 'muros': [], 'superficies': superficies, 'coordenadas_plano': coordenadas,
                'base_vista': {'normal_u_cruz_v': normal, 'epsilon_ortonormalidad': EPS_BASE3D,
                              'criterios_coplanaridad': criterios}, 'huella_plano': _sha(_bytes(plano))}

    @staticmethod
    def _ids_aberturas(vista):
        return {s['id']: [a['id'] for a in s['aberturas']] for s in vista['superficies']}

    @classmethod
    def _vista_aberturas(cls, esquema, plano, seleccion):
        if not isinstance(plano, dict) or plano.get('tipo') not in ('horizontal', 'base_ortonormal_3d'):
            raise ErrorSuperposicion('Superposición0.4 exige plano horizontal o base ortonormal3D explícitos.')
        tridimensional = plano['tipo'] == 'base_ortonormal_3d'
        metodo = cls._plano3d_superficies if tridimensional else cls._plano_superficies
        vista = metodo(esquema, plano, seleccion, version_geometria=VERSION_GEOMETRIA_ABERTURAS)
        for superficie in vista['superficies']:
            huecos = []
            for hueco in superficie['aberturas']:
                if not tridimensional:
                    if any(p[2] != plano['cota_m'] for p in hueco['vertices_m']):
                        raise ErrorSuperposicion('Abertura fuera del plano horizontal exacto declarado.')
                    huecos.append(hueco)
                    continue
                puntos = hueco['vertices_m']
                escala = max(abs(p[k]-puntos[0][k]) for p in puntos for k in range(3))
                magnitud = max(abs(x) for p in puntos+[plano['origen_m']] for x in p)
                tolerancia = max(EPS_BASE3D*escala, 64*math.ulp(magnitud))
                if not _num(tolerancia) or escala <= 0 or tolerancia/escala > 1e-6:
                    raise ErrorSuperposicion('Abertura numéricamente inestable respecto de la base3D declarada.')
                uv = []
                for punto in puntos:
                    delta = [punto[k]-plano['origen_m'][k] for k in range(3)]
                    if not all(_num(x) for x in delta) or abs(math.fsum(x*y for x,y in zip(delta,vista['base_vista']['normal_u_cruz_v']))) > tolerancia:
                        raise ErrorSuperposicion('Abertura fuera del plano3D declarado; no se aplana.')
                    par = [math.fsum(x*y for x,y in zip(delta,plano[eje])) for eje in ('eje_u','eje_v')]
                    if not all(_num(x) for x in par):
                        raise ErrorSuperposicion('Proyección de abertura no representable.')
                    uv.append(par)
                huecos.append({**hueco, 'vertices_plano_m': uv})
                vista['base_vista'].setdefault('criterios_coplanaridad_aberturas', {}).setdefault(superficie['id'], {})[hueco['id']] = {'escala_contorno_m': escala, 'tolerancia_computacional_m': tolerancia}
            superficie['aberturas'] = huecos
        return vista

    @classmethod
    def _anclas_vertices(cls, anclas, esquema, vista):
        if (not isinstance(anclas, list) or len(anclas) != 3
                or any(not isinstance(a, dict) or set(a) != {'vertice', 'punto'} for a in anclas)):
            raise ErrorSuperposicion('Declara tres anclas de vértice 3D; no nodos del contrato histórico.')
        vertices = vista.get('coordenadas_plano') or {v['id']: v for v in esquema['vertices_m']}
        presentes = {ident for s in vista['superficies'] for ident in s['vertices']}
        return cls._anclas([{'nodo': a['vertice'], 'punto': a['punto']} for a in anclas], vertices, presentes)

    @staticmethod
    def _anclas(anclas, nodos, nivel_muros):
        if not isinstance(anclas, list) or len(anclas) != 3:
            raise ErrorSuperposicion('Declara exactamente tres anclas.')
        modelo, imagen, ids = [], [], []
        for a in anclas:
            if (not isinstance(a, dict) or set(a) != {'nodo', 'punto'} or not isinstance(a['nodo'], str)
                    or not isinstance(a['punto'], list) or len(a['punto']) != 2 or not all(_num(v) for v in a['punto'])
                    or not all(0 <= v <= 1 for v in a['punto'])):
                raise ErrorSuperposicion('Cada ancla requiere nodo y punto normalizado [u, v] entre 0 y 1.')
            if a['nodo'] not in nodos:
                raise ErrorSuperposicion('Ancla con nodo inexistente en la geometría.')
            if a['nodo'] not in nivel_muros:
                raise ErrorSuperposicion('Ancla con nodo que no pertenece a muros del nivel seleccionado.')
            ids.append(a['nodo']); modelo.append((nodos[a['nodo']]['x'], nodos[a['nodo']]['y']))
            imagen.append((float(a['punto'][0]), float(a['punto'][1])))
        if len(set(ids)) != 3 or len(set(imagen)) != 3:
            raise ErrorSuperposicion('Anclas duplicadas: usa tres nodos y tres puntos distintos.')
        return modelo, imagen

    def crear(self, body):
        def operacion():
            nueva = isinstance(body, dict) and body.get('version_contrato') in (VERSION_SUPERFICIES, VERSION_PLANO3D, VERSION_ABERTURAS)
            con_aberturas = nueva and body['version_contrato'] == VERSION_ABERTURAS
            plano3d = nueva and (body['version_contrato'] == VERSION_PLANO3D or (con_aberturas and isinstance(body.get('plano'), dict) and body['plano'].get('tipo') == 'base_ortonormal_3d'))
            campos = CAMPOS_CREAR_SUPERFICIES if nueva else CAMPOS_CREAR
            if not isinstance(body, dict) or set(body) != campos:
                raise ErrorSuperposicion('Campos exactos requeridos: '+', '.join(sorted(CAMPOS_CREAR))+'.')
            if body['confirmacion_explicita'] is not True:
                raise ErrorSuperposicion('Confirma explícitamente la declaración de correspondencia.')
            for key, limit in (('revisor_declarado', 150), ('motivo', 2000)):
                if not isinstance(body[key], str) or not body[key].strip() or len(body[key]) > limit:
                    raise ErrorSuperposicion('Declara revisor (hasta 150) y motivo (hasta 2000) no vacíos.')
            try:
                if not isinstance(body['fecha'], str) or date.fromisoformat(body['fecha']).isoformat() != body['fecha']:
                    raise ValueError
            except ValueError:
                raise ErrorSuperposicion('Fecha ISO AAAA-MM-DD inválida.') from None
            caso, fp, version = body['caso'], body['expediente_sha256'], _uuid(body['geometria'])
            folder = self._caso(caso, fp)
            current = self._geometria(caso, version, fp)
            if current['huella'] != _hex64(body['huella_geometria']) or current['sha256_geometria'] != _hex64(body['sha256_geometria']):
                raise ErrorSuperposicion('La geometría abierta cambió; vuelve a cargar su esquema.')
            esquema = self._esquema(current, version)
            if esquema.get('version_geometria') == VERSION_GEOMETRIA_ABERTURAS and not con_aberturas:
                raise ErrorSuperposicion('Geometría con aberturas exige superposición0.4; no se omiten huecos en un formato anterior.')
            if nueva:
                nivel = self._vista_aberturas(esquema, body['plano'], body['superficies']) if con_aberturas else (self._plano3d_superficies if plano3d else self._plano_superficies)(esquema, body['plano'], body['superficies'])
                modelo, imagen = self._anclas_vertices(body['anclas'], esquema, nivel)
            else:
                nivel = next((n for n in esquema['niveles'] if n['id'] == body['nivel']), None)
                if nivel is None or not nivel['muros']:
                    raise ErrorSuperposicion('Nivel inexistente o sin muros en esta geometría.')
                nodos = {n['id']: n for n in esquema['nodos']}
                del_nivel = {m[k]['id'] for m in nivel['muros'] for k in ('inicio', 'fin')}
                modelo, imagen = self._anclas(body['anclas'], nodos, del_nivel)
            matriz = transformacion(modelo, imagen)
            fuente = self._fuente(caso, body['archivo'], body['pagina'], fp)
            registro = {'contrato': CONTRATO, 'version': body['version_contrato'] if nueva else VERSION, 'caso': caso, 'expediente_sha256': fp,
                        'geometria': {'id': version, 'huella': current['huella'], 'sha256': current['sha256_geometria'],
                                      'unidad_longitud': esquema['unidad_longitud'], 'estado_revision': esquema['estado_revision']},
                        'fuente': fuente,
                        'anclas': [{('vertice' if nueva else 'nodo'): a['vertice' if nueva else 'nodo'], 'punto': [float(a['punto'][0]), float(a['punto'][1])]} for a in body['anclas']],
                        'transformacion': {'tipo': 'afin_exacta_tres_anclas', 'de': 'modelo_xy_'+esquema['unidad_longitud'],
                                           'a': fuente['sistema'], 'matriz': matriz},
                        'declaracion': {'revisor_declarado': body['revisor_declarado'], 'fecha': body['fecha'], 'motivo': body['motivo']},
                        'identidad_revisor': 'declarada_no_verificada', 'aprueba_ingenieria': False, 'aprueba_geometria': False}
            if nueva:
                registro.update(plano=body['plano'], superficies=body['superficies'])
                registro['geometria']['version_contrato'] = VERSION_GEOMETRIA_ABERTURAS if con_aberturas else VERSION_SUPERFICIES
                if con_aberturas:
                    registro['aberturas'] = self._ids_aberturas(nivel)
                registro['transformacion']['de'] = 'plano_horizontal_xy_m'
                if plano3d:
                    registro.update(huella_plano=nivel['huella_plano'], base_vista=nivel['base_vista'])
                    registro['transformacion']['de'] = 'plano3d_uv_m'
            else:
                registro['nivel'] = body['nivel']
            raw = _bytes(registro)
            base = self._base(folder, crear=True)
            ident = uuid4().hex
            meta = {'contrato': CONTRATO, 'id': ident, 'caso': caso, 'sha256_correspondencia': _sha(raw),
                    'creado_utc': datetime.now(timezone.utc).isoformat()}
            with tempfile.TemporaryDirectory(prefix='.sup-', dir=base) as temporal:
                etapa = Path(temporal).resolve()
                if etapa.parent != base:
                    raise ErrorSuperposicion('Temporal fuera del caso.')
                paquete = etapa/'paquete'; paquete.mkdir()
                for name, data in (('correspondencia.json', raw), ('version.json', _bytes(meta))):
                    with (paquete/name).open('xb') as stream:
                        stream.write(data)
                self._cargar(caso, ident, fp, ruta=paquete)
                destino = base/ident
                if os.path.lexists(destino):
                    raise ErrorSuperposicion('Destino existente; no se sobrescribe.')
                paquete.rename(destino)
            return self.consultar(caso, ident, expediente_sha256=fp)
        return self._publico(operacion, 'No se registró la correspondencia: fuentes, geometría o anclas sin vigencia.')

    # -- consulta revalidada -----------------------------------------------------------
    def _cargar(self, caso, ident, fp, *, ruta=None):
        folder = self._caso(caso, fp)
        target = _sin_enlace(ruta if ruta is not None else self._base(folder)/_uuid(ident))
        if not target.is_dir() or sorted(p.name for p in target.iterdir()) != ['correspondencia.json', 'version.json']:
            raise ErrorSuperposicion('Versión de superposición ausente o con contenido inválido.')
        meta_raw, raw = _leer(target/'version.json'), _leer(target/'correspondencia.json')
        meta = json_desde_bytes(meta_raw, 'version.json')
        if (not isinstance(meta, dict) or set(meta) != {'contrato', 'id', 'caso', 'sha256_correspondencia', 'creado_utc'}
                or meta['contrato'] != CONTRATO or meta['id'] != ident or meta['caso'] != caso
                or meta['sha256_correspondencia'] != _sha(raw)):
            raise ErrorSuperposicion('Registro de superposición alterado o de otro caso.')
        reg = json_desde_bytes(raw, 'correspondencia.json')
        if not isinstance(reg, dict) or reg.get('contrato') != CONTRATO or reg.get('caso') != caso or reg.get('expediente_sha256') != fp:
            raise ErrorSuperposicion('Correspondencia de otro caso o expediente.')
        geo = reg['geometria']
        current = self._geometria(caso, geo['id'], fp)
        if current['huella'] != geo['huella'] or current['sha256_geometria'] != geo['sha256']:
            raise ErrorSuperposicion('La geometría cambió: la correspondencia no se hereda; registra una nueva.')
        esquema = self._esquema(current, geo['id'])
        if esquema['unidad_longitud'] != geo['unidad_longitud']:
            raise ErrorSuperposicion('Unidad de la geometría distinta de la registrada.')
        if reg.get('version') in (VERSION_SUPERFICIES, VERSION_PLANO3D, VERSION_ABERTURAS):
            con_aberturas = reg['version'] == VERSION_ABERTURAS
            plano3d = reg['version'] == VERSION_PLANO3D or (con_aberturas and isinstance(reg.get('plano'), dict) and reg['plano'].get('tipo') == 'base_ortonormal_3d')
            campos = {'contrato', 'version', 'caso', 'expediente_sha256', 'geometria', 'fuente', 'anclas', 'transformacion',
                      'declaracion', 'identidad_revisor', 'aprueba_ingenieria', 'aprueba_geometria', 'plano', 'superficies'}
            if plano3d:
                campos.update(('huella_plano', 'base_vista'))
            if con_aberturas:
                campos.add('aberturas')
            if (set(reg) != campos or geo.get('version_contrato') != (VERSION_GEOMETRIA_ABERTURAS if con_aberturas else VERSION_SUPERFICIES)
                    or set(geo) != {'id', 'huella', 'sha256', 'unidad_longitud', 'estado_revision', 'version_contrato'}
                    or set(reg['transformacion']) != {'tipo', 'de', 'a', 'matriz'}
                    or reg['aprueba_geometria'] is not False or reg['aprueba_ingenieria'] is not False
                    or reg['identidad_revisor'] != 'declarada_no_verificada'
                    or reg['transformacion'].get('de') != ('plano3d_uv_m' if plano3d else 'plano_horizontal_xy_m')
                    or reg['transformacion'].get('tipo') != 'afin_exacta_tres_anclas'
                    or reg['transformacion'].get('a') != reg['fuente'].get('sistema')):
                raise ErrorSuperposicion('Contrato de superposición de superficies alterado.')
            declaracion = reg['declaracion']
            if (not isinstance(declaracion, dict) or set(declaracion) != {'revisor_declarado', 'fecha', 'motivo'}
                    or any(not isinstance(declaracion[k], str) or not declaracion[k].strip() or len(declaracion[k]) > limite
                           for k, limite in (('revisor_declarado', 150), ('motivo', 2000)))
                    or not isinstance(declaracion['fecha'], str)
                    or date.fromisoformat(declaracion['fecha']).isoformat() != declaracion['fecha']):
                raise ErrorSuperposicion('Declaración de correspondencia inválida.')
            nivel = self._vista_aberturas(esquema, reg['plano'], reg['superficies']) if con_aberturas else (self._plano3d_superficies if plano3d else self._plano_superficies)(esquema, reg['plano'], reg['superficies'])
            if con_aberturas and reg['aberturas'] != self._ids_aberturas(nivel):
                raise ErrorSuperposicion('El registro debe conservar todas las aberturas de las superficies seleccionadas.')
            if plano3d and (reg['huella_plano'] != nivel['huella_plano'] or reg['base_vista'] != nivel['base_vista']):
                raise ErrorSuperposicion('Huella/base de vista 3D no corresponden al plano geométrico exacto.')
            modelo, imagen = self._anclas_vertices(reg['anclas'], esquema, nivel)
        elif reg.get('version') == VERSION:
            if esquema.get('version_geometria') == VERSION_GEOMETRIA_ABERTURAS:
                raise ErrorSuperposicion('Contrato antiguo incompatible con geometría con aberturas.')
            nivel = next((n for n in esquema['niveles'] if n['id'] == reg['nivel']), None)
            if nivel is None:
                raise ErrorSuperposicion('Nivel registrado inexistente.')
            nodos = {n['id']: n for n in esquema['nodos']}
            modelo, imagen = self._anclas(reg['anclas'], nodos, {m[k]['id'] for m in nivel['muros'] for k in ('inicio', 'fin')})
        else:
            raise ErrorSuperposicion('Versión de superposición no admitida.')
        if transformacion(modelo, imagen) != reg['transformacion']['matriz']:
            raise ErrorSuperposicion('La transformación registrada no corresponde a sus anclas.')
        fuente = reg['fuente']
        if self._fuente(caso, fuente['archivo'], fuente['pagina'], fp) != fuente:
            raise ErrorSuperposicion('El original o su vista previa cambiaron; la calibración no se ajusta automáticamente.')
        # La geometría debe seguir vigente después de renderizar la vista previa (no solo al inicio).
        final = self._geometria(caso, geo['id'], fp)
        if final['huella'] != geo['huella'] or final['sha256_geometria'] != geo['sha256']:
            raise ErrorSuperposicion('La geometría cambió durante la consulta.')
        if _leer(target/'version.json') != meta_raw or _leer(target/'correspondencia.json') != raw:
            raise ErrorSuperposicion('El registro cambió durante la consulta.')
        return meta, reg, esquema, nivel

    def consultar(self, caso, version, *, expediente_sha256):
        def operacion():
            meta, reg, esquema, nivel = self._cargar(caso, _uuid(version), expediente_sha256)
            m = reg['transformacion']['matriz']
            fuera, muros = [], []
            for muro in nivel['muros']:
                extremos = []
                for k in ('inicio', 'fin'):
                    u, v = aplicar(m, muro[k]['x'], muro[k]['y'])
                    dentro = 0 <= u <= 1 and 0 <= v <= 1
                    extremos.append({'nodo': muro[k]['id'], 'u': u, 'v': v, 'dentro_imagen': dentro})
                    if not dentro:
                        fuera.append({'muro': muro['id'], 'nodo': muro[k]['id'], 'u': u, 'v': v})
                muros.append({**muro, 'proyeccion': extremos})
            resultado = {'id': meta['id'], 'caso': caso, 'expediente_sha256': expediente_sha256, 'creado_utc': meta['creado_utc'],
                    'sha256_correspondencia': meta['sha256_correspondencia'], 'geometria': reg['geometria'],
                    'fuente': reg['fuente'], 'nivel': reg.get('nivel'), 'anclas': reg['anclas'], 'transformacion': reg['transformacion'],
                    'declaracion': reg['declaracion'], 'muros': muros, 'fuera_imagen': fuera, 'vigente': True,
                    'naturaleza': 'correspondencia_declarada_no_deteccion', 'identidad_revisor': 'declarada_no_verificada',
                    'aprueba_ingenieria': False, 'aprueba_geometria': False, 'disponible_para_modelado': esquema['disponible_para_modelado'],
                    'aviso': AVISO}
            if reg['version'] in (VERSION_SUPERFICIES, VERSION_PLANO3D, VERSION_ABERTURAS):
                superficies = []
                for superficie in nivel['superficies']:
                    proyeccion = []
                    coordenadas = superficie.get('vertices_plano_m', superficie['vertices_m'])
                    for ident, punto in zip(superficie['vertices'], coordenadas):
                        x, y = punto[:2]
                        u, v = aplicar(m, x, y)
                        if not _num(u) or not _num(v):
                            raise ErrorSuperposicion('Proyección no representable.')
                        dentro = 0 <= u <= 1 and 0 <= v <= 1
                        proyeccion.append({'vertice': ident, 'u': u, 'v': v, 'dentro_imagen': dentro})
                        if not dentro:
                            fuera.append({'superficie': superficie['id'], 'vertice': ident, 'u': u, 'v': v})
                    superficies.append({**superficie, 'proyeccion': proyeccion})
                    if reg['version'] == VERSION_ABERTURAS:
                        huecos = []
                        for abertura in superficie['aberturas']:
                            proyeccion_hueco = []
                            for ident, punto in zip(abertura['vertices'], abertura.get('vertices_plano_m', abertura['vertices_m'])):
                                u, v = aplicar(m, *punto[:2])
                                if not _num(u) or not _num(v):
                                    raise ErrorSuperposicion('Proyección de abertura no representable.')
                                dentro = 0 <= u <= 1 and 0 <= v <= 1
                                proyeccion_hueco.append({'vertice': ident, 'u': u, 'v': v, 'dentro_imagen': dentro})
                                if not dentro:
                                    fuera.append({'superficie': superficie['id'], 'abertura': abertura['id'], 'vertice': ident, 'u': u, 'v': v})
                            huecos.append({**abertura, 'proyeccion': proyeccion_hueco})
                        superficies[-1]['aberturas'] = huecos
                resultado.update(version_contrato=reg['version'], plano=reg['plano'], superficies=superficies,
                                 aviso=AVISO+' Vista horizontal declarada: solo contornos coplanares a la cota física indicada; no prueba malla, sección o conectividad estructural.')
                if reg['version'] == VERSION_ABERTURAS:
                    resultado['aviso'] += ' Incluye todas las aberturas de las superficies seleccionadas; áreas bruta/huecos/neta geométricas, sin aprobación estructural.'
                if reg['version'] == VERSION_PLANO3D or (reg['version'] == VERSION_ABERTURAS and reg['plano']['tipo'] == 'base_ortonormal_3d'):
                    resultado.update(huella_plano=reg['huella_plano'], base_vista=reg['base_vista'],
                                     aviso=AVISO+' Base 3D y sentido U×V declarados: proyección UV de superficies coplanares. No son ejes locales de ETABS ni una asignación física.')
            return resultado
        return self._publico(operacion, 'Superposición sin vigencia: geometría, original, vista previa o registro cambiaron.')

    def listar(self, caso, *, expediente_sha256):
        def operacion():
            base = self._base(self._caso(caso, expediente_sha256))
            rows = []
            for path in sorted(base.iterdir()) if base.is_dir() else []:
                if re.fullmatch('[0-9a-f]{32}', path.name) is None:
                    continue
                try:
                    item = self.consultar(caso, path.name, expediente_sha256=expediente_sha256)
                    row = {'id': path.name, 'vigente': True, 'geometria': item['geometria']['id'], 'nivel': item['nivel'],
                           'archivo': item['fuente']['archivo'], 'pagina': item['fuente']['pagina']}
                    if item.get('version_contrato') in (VERSION_SUPERFICIES, VERSION_PLANO3D, VERSION_ABERTURAS):
                        row.update(version_contrato=item['version_contrato'], plano=item['plano'], superficies=[s['id'] for s in item['superficies']])
                    rows.append(row)
                except ERRORES:
                    rows.append({'id': path.name, 'vigente': False, 'problemas': ['superposicion_no_vigente']})
            self._caso(caso, expediente_sha256)
            return {'caso': caso, 'expediente_sha256': expediente_sha256, 'versiones': rows, 'seleccion_automatica': False}
        return self._publico(operacion, 'No se pudieron listar las superposiciones.')
