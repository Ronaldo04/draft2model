"""Contexto local de malla: equivalencia íntegra, reproducción y mutaciones; sin ETABS/red."""
import copy
import unittest
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from draft2model import malla_preparacion as mp
from draft2model import particion_superficies as ps
from draft2model import compatibilidad_particiones as cp
from draft2model import triangulacion_particiones as tp
from draft2model.validacion_geometria import validar_geometria
from tests.test_integracion_malla import escenario, documento_conexiones
from tests.test_modelo_superficies import geometria_superficies


HUELLAS_PREVIAS = {
    'horizontal': 'a297c7ac84fc3ba7eaa8c9ca60fab6e94943258860045ecf43e7c8f1cb509912',
    'vertical': '15bb8aaf9b99486fa77e23076343590ab2939d25f53aacb75a0f65da0b94cd46',
    'inclinado': '843b15871b5fff531e524d4e380fe5e852582c0650c297da5d2562eb748677e1',
    'conectados': '8018073b8bbfac82edea9609d8bd96f210f2b762bc4b0ffe30190b3d520ede82',
    'vertical_corte': '3d9d1b39e352b043ee59939e3634a09d6d61611a9ab717593819f13569d62c50',
    'conectados_corte': 'ed9e3e3e5e5ace6b5a01f6d304d775096e83c36dbf24dac7c31d4a2f71ead421',
}


def fixture(nombre):
    esc = escenario(nombre)
    geo = geometria_superficies(vertices=esc['vertices'],
                               superficies=[(h, v, 'host sintetico') for h, v, _ in esc['hosts']], aprobar=False)
    geo.update(version_contrato='0.3.0', aberturas=[
        {'id': a, 'superficie': s, 'vertices': v, 'procedencia': copy.deepcopy(geo['procedencia'])}
        for a, s, v in esc['huecos']])
    cfg = {'asignaciones_superficies': [{'objetivo': h, 'seccion': s} for h, _, s in esc['hosts']],
           'conexiones_borde': documento_conexiones(geo, esc),
           'cortes_nivel': [{'z_m': z} for z in esc.get('cortes', [])],
           'puntos': [{'id': v, 'vertice_geometria': v} for v in esc['vertices']],
           'vertices_compartidos': [],
           'frames': [{'id': i, 'inicio': a, 'fin': b} for i, a, b, _ in esc['frames']]}
    return geo, cfg


def actualizar_conexiones(geo, cfg):
    doc = cfg['conexiones_borde']
    doc['geometria'] = {'sha256_geometria_canonica': cp._sha(geo),
                        'huella_contenido': validar_geometria(geo).huella_contenido}
    doc['declaracion']['huella_conexiones'] = cp.huella_conexiones(doc)


def muchos_hosts(n=48):
    fuente, cfg = fixture('vertical')
    geo = copy.deepcopy(fuente)
    geo['vertices'], geo['superficies'], geo['aberturas'] = [], [], []
    for i in range(n):
        prefijo = f'B{i}_'
        for original in fuente['vertices']:
            v = copy.deepcopy(original)
            v['id'] = prefijo + v['id']
            v['x'] += i * 3
            geo['vertices'].append(v)
        for clave in ('superficies', 'aberturas'):
            for original in fuente[clave]:
                fila = copy.deepcopy(original)
                fila['id'] = prefijo + fila['id']
                fila['vertices'] = [prefijo + v for v in fila['vertices']]
                if 'superficie' in fila:
                    fila['superficie'] = prefijo + fila['superficie']
                geo[clave].append(fila)
    cfg['puntos'] = [{'id': v['id'], 'vertice_geometria': v['id']} for v in geo['vertices']]
    cfg['asignaciones_superficies'] = [{'objetivo': s['id'], 'seccion': 'MURO'} for s in geo['superficies']]
    actualizar_conexiones(geo, cfg)
    return geo, cfg


@contextmanager
def sin_contexto():
    """Ruta pública anterior: cada etapa reproduce y valida íntegramente sus entradas."""
    particionar, compatibilizar, triangular = ps.particionar_superficie, cp.compatibilizar_particiones, tp.triangular_compatibilidad
    with patch.object(ps, 'particionar_superficie', side_effect=lambda *a, **kw: particionar(*a)), \
         patch.object(cp, 'compatibilizar_particiones', side_effect=lambda *a, **kw: compatibilizar(*a)), \
         patch.object(tp, 'triangular_compatibilidad', side_effect=lambda *a, **kw: triangular(*a)):
        yield


class RendimientoMalla246Tests(unittest.TestCase):
    def setUp(self):
        # Estas pruebas cuentan validaciones internas y mutan entradas DURANTE el cálculo en cada invocación: se fuerza
        # explícitamente el camino frío (función original sin cache, cache_malla_pura 268) sin cambiar ninguna aserción.
        # El comportamiento de la cache se prueba aparte en tests/test_cache_malla_pura_268.py.
        frio = patch.object(mp, 'preparar_malla', mp.preparar_malla.__wrapped__)
        frio.start()
        self.addCleanup(frio.stop)

    def test_igualdad_completa_orientaciones_huecos_conexiones_cortes_y_frames(self):
        for nombre, huella in HUELLAS_PREVIAS.items():
            with self.subTest(nombre=nombre):
                geo, cfg = fixture(nombre)
                antes = copy.deepcopy((geo, cfg))
                with sin_contexto():
                    esperado = mp.preparar_malla(geo, cfg)
                actual = mp.preparar_malla(geo, cfg)
                self.assertEqual(actual, esperado)
                self.assertEqual(actual['huella_preparacion'], huella)
                self.assertEqual((geo, cfg), antes)

    def test_48_hosts_validacion_unica_y_documento_completo_igual(self):
        geo, cfg = muchos_hosts()
        with patch.object(ps, 'validar_geometria', wraps=validar_geometria) as a, \
             patch.object(cp, 'validar_geometria', wraps=validar_geometria) as b:
            actual = mp.preparar_malla(geo, cfg)
            self.assertEqual(a.call_count + b.call_count, 1)
        with sin_contexto(), patch.object(ps, 'validar_geometria', wraps=validar_geometria) as a, \
             patch.object(cp, 'validar_geometria', wraps=validar_geometria) as b:
            esperado = mp.preparar_malla(geo, cfg)
            self.assertEqual(a.call_count + b.call_count, 147)
        self.assertEqual(actual, esperado)
        self.assertEqual(len(actual['triangulos']), 576)
        self.assertEqual(actual['huella_preparacion'], 'fc4ec8d523db1c4539b1117b69e4611808700afde07e600f53e6acd8339181bc')

    def test_geometria_invalida_rechazada_igual(self):
        cambios = (
            lambda g: g['vertices'][0].update(x=float('nan')),
            lambda g: g['vertices'][0].update(x=0.4),
            lambda g: g['superficies'][0]['vertices'].pop(),
            lambda g: g.update(version_contrato='0.2.0'),
        )
        for cambio in cambios:
            geo, cfg = fixture('vertical')
            cambio(geo)
            with self.subTest(cambio=cambio):
                with sin_contexto(), self.assertRaises(mp.ErrorMalla) as previo:
                    mp.preparar_malla(geo, cfg)
                with self.assertRaises(mp.ErrorMalla) as actual:
                    mp.preparar_malla(geo, cfg)
                self.assertEqual(str(actual.exception), str(previo.exception))

    def test_mutacion_durante_particiones_y_tras_triangulacion_se_rechaza(self):
        for modulo, nombre in ((ps, 'particionar_superficie'), (tp, 'triangular_compatibilidad')):
            for referencia in (False, True):
                geo, cfg = fixture('conectados')
                original = getattr(modulo, nombre)
                def mutar(*args, **kwargs):
                    resultado = original(*args, **kwargs)
                    geo['procedencia']['descripcion'] += ' alterada'
                    return resultado
                with self.subTest(etapa=nombre, referencia=referencia):
                    if referencia:
                        with sin_contexto():
                            publico = getattr(modulo, nombre)
                            # La ruta pública también debe ver la mutación entre etapas.
                            with patch.object(modulo, nombre, side_effect=lambda *a, **kw: mutar_publico(publico, geo, *a, **kw)):
                                with self.assertRaises(mp.ErrorMalla):
                                    mp.preparar_malla(geo, cfg)
                    else:
                        with patch.object(modulo, nombre, side_effect=mutar), self.assertRaisesRegex(mp.ErrorMalla, 'cambió'):
                            mp.preparar_malla(geo, cfg)

    def test_particion_y_compatibilidad_manipuladas_con_hash_recalculado(self):
        geo, cfg = fixture('conectados')
        contexto = ps._ContextoGeometria(geo)
        partes = [ps.particionar_superficie(geo, s['id'], _contexto=contexto) for s in geo['superficies']]
        conexiones = cfg['conexiones_borde']
        compat = cp.compatibilizar_particiones(geo, partes, conexiones, _contexto=contexto)
        malas = copy.deepcopy(partes)
        malas[0]['nodos'][0]['xyz_m'][0] += 1
        malas[0]['huella_particion'] = ps._sha({k: v for k, v in malas[0].items() if k != 'huella_particion'})
        alterada = copy.deepcopy(compat)
        alterada['nodos'][0]['xyz_m'][0] += 1
        alterada['huella_compatibilidad'] = cp._sha({k: v for k, v in alterada.items() if k != 'huella_compatibilidad'})
        for extra in ({}, {'_contexto': contexto}):
            with self.subTest(contexto=bool(extra)):
                with self.assertRaises(cp.ErrorCompatibilidad):
                    cp.compatibilizar_particiones(geo, malas, conexiones, **extra)
                with self.assertRaises(tp.ErrorTriangulacion):
                    tp.triangular_compatibilidad(geo, partes, conexiones, alterada, **extra)

    def test_mutacion_no_serializable_tras_triangulacion_no_se_publica(self):
        geo, cfg = fixture('vertical')
        triangular = tp.triangular_compatibilidad
        def mutar(*args, **kwargs):
            resultado = triangular(*args, **kwargs)
            geo['vertices'][0]['x'] = float('nan')
            return resultado
        with patch.object(tp, 'triangular_compatibilidad', side_effect=mutar):
            with self.assertRaisesRegex(mp.ErrorMalla, 'JSON estricto'):
                mp.preparar_malla(geo, cfg)

    def test_invocaciones_sucesivas_y_fuente_mutada_no_reusan_validacion(self):
        geo, cfg = fixture('vertical')
        esperado = mp.preparar_malla(geo, cfg)
        with patch.object(ps, 'validar_geometria', wraps=validar_geometria) as validar:
            a = mp.preparar_malla(geo, cfg)
            a['nodos'][0]['xyz_m'][0] += 8
            self.assertEqual(mp.preparar_malla(geo, cfg), esperado)
            geo['procedencia']['descripcion'] += ' otra fuente'
            with self.assertRaises(mp.ErrorMalla):
                mp.preparar_malla(geo, cfg)
            actualizar_conexiones(geo, cfg)
            nuevo = mp.preparar_malla(geo, cfg)
            self.assertEqual(validar.call_count, 4)
        self.assertNotEqual(nuevo['huella_preparacion'], esperado['huella_preparacion'])
        geo['vertices'][0]['x'] = 0.4
        with self.assertRaises(mp.ErrorMalla):
            mp.preparar_malla(geo, cfg)

    def test_contextos_concurrentes_independientes(self):
        a = fixture('vertical')
        b = fixture('inclinado')
        esperados = [mp.preparar_malla(*datos) for datos in (a, b)]
        with ThreadPoolExecutor(max_workers=2) as executor:
            actuales = list(executor.map(lambda datos: mp.preparar_malla(*datos), (a, b)))
        self.assertEqual(actuales, esperados)


def mutar_publico(publico, geo, *args, **kwargs):
    resultado = publico(*args, **kwargs)
    geo['procedencia']['descripcion'] += ' alterada'
    return resultado


if __name__ == '__main__':
    unittest.main()
