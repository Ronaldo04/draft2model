"""Cache pura de preparar_malla (candidato Codex 267/268 portado): pruebas sintéticas y planes completos iguales."""
import math
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from draft2model.cache_malla_pura import MAX_ENTRADAS, reutilizar_malla_pura

class CachePuraTests(unittest.TestCase):
    def test_hit_canonico_y_consumidor_aislado(self):
        calls=[]
        @reutilizar_malla_pura
        def prepare(g,c):
            calls.append(1);return {'puntos':[g['x'],c['revision']['id']]}
        first=prepare({'x':1,'y':2},{'revision':{'id':'a'}})
        first['puntos'][0]=999
        # Revisión 284: otro ORDEN de claves es otra clave (la salida puede depender del orden); no comparte entrada.
        reordenado=prepare({'y':2,'x':1},{'revision':{'id':'a'}})
        self.assertEqual(reordenado,{'puntos':[1,'a']});self.assertEqual(len(calls),2)
        second=prepare({'x':1,'y':2},{'revision':{'id':'a'}})
        third=prepare({'x':1,'y':2},{'revision':{'id':'a'}})
        self.assertEqual(second,{'puntos':[1,'a']})
        self.assertIsNot(second,third);self.assertIsNot(second['puntos'],third['puntos'])
        self.assertEqual(prepare.cache_info()['hits'],2)

    def test_cambios_input_revision_cold(self):
        calls=[]
        @reutilizar_malla_pura
        def prepare(g,c):calls.append(1);return [g['x'],c['revision']]
        g={'x':1};c={'revision':'a'}
        prepare(g,c);g['x']=2;prepare(g,c);c['revision']='b';prepare(g,c)
        self.assertEqual(len(calls),3)

    def test_errores_originales_nunca_cacheados(self):
        calls=[];error=ValueError('original')
        @reutilizar_malla_pura
        def prepare(g,c):calls.append(1);raise error
        for _ in range(2):
            with self.assertRaises(ValueError) as caught:prepare({}, {})
            self.assertIs(caught.exception,error)
        self.assertEqual(len(calls),2);self.assertEqual(prepare.cache_info()['entradas'],0)

    def test_no_json_nan_ciclos_y_subtipos_fallback(self):
        class CustomDict(dict):pass
        cycle=[];cycle.append(cycle)
        for value in ((1,2), {'x':math.nan},{'x':math.inf},{1:'clave'},CustomDict(),cycle,{1,2}):
            calls=[]
            @reutilizar_malla_pura
            def prepare(g,c):calls.append(1);return ('tipo_original',)
            a=prepare(value,{});b=prepare(value,{})
            self.assertIs(type(a),tuple);self.assertEqual(a,b)
            self.assertEqual(len(calls),2);self.assertEqual(prepare.cache_info()['entradas'],0)

    def test_salida_no_json_no_se_convierte(self):
        for output in ((1,2),{'x':math.nan},object()):
            calls=[]
            @reutilizar_malla_pura
            def prepare(g,c):calls.append(1);return output
            self.assertIs(prepare({},{}),output);self.assertIs(prepare({},{}),output)
            self.assertEqual(len(calls),2);self.assertEqual(prepare.cache_info()['entradas'],0)

    def test_mutacion_durante_calculo_no_se_guarda(self):
        @reutilizar_malla_pura
        def prepare(g,c):g['x']+=1;return {'x':g['x']}
        g={'x':0};prepare(g,{});self.assertEqual(prepare.cache_info()['entradas'],0)
        prepare(g,{});self.assertEqual(g['x'],2);self.assertEqual(prepare.cache_info()['entradas'],0)

    def test_lru_dos_entradas_y_limite_bytes(self):
        calls=[]
        @reutilizar_malla_pura(max_entradas=2)   # LRU de 2 explícito (el producto admite hasta MAX_ENTRADAS)
        def prepare(g,c):calls.append(g);return {'value':g}
        prepare(1,{});prepare(2,{});prepare(1,{});prepare(3,{});prepare(2,{})
        self.assertEqual(calls,[1,2,3,2]);self.assertEqual(prepare.cache_info()['entradas'],2)
        @reutilizar_malla_pura(max_bytes=100)
        def large(g,c):return 'a'*200
        large({},{});self.assertEqual(large.cache_info()['entradas'],0)
        @reutilizar_malla_pura(max_bytes=100)
        def small(g,c):return g
        for number in range(10):small(number,{})
        self.assertLessEqual(small.cache_info()['bytes'],100)
        self.assertLessEqual(small.cache_info()['entradas'],2)
        small.cache_clear();self.assertEqual(small.cache_info()['entradas'],0)

    def test_concurrencia_basica_sin_lock_durante_calculo(self):
        # Con single-flight (279) la MISMA clave ya no calcula en paralelo (ver SingleFlightTests). La garantía de esta prueba —
        # ningún lock global durante el cálculo— se comprueba con CUATRO claves distintas que deben coincidir en la barrera.
        started=threading.Barrier(4)
        @reutilizar_malla_pura
        def prepare(g,c):started.wait(timeout=3);return {'x':[g]}
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(lambda g:prepare(g,{}),range(4)))
        self.assertEqual(results,[{'x':[g]} for g in range(4)])
        self.assertEqual(prepare.cache_info()['entradas'],4)
        hit=prepare(1,{});hit['x'].append(9)
        self.assertEqual(prepare(1,{}),{'x':[1]})
        self.assertLessEqual(prepare.cache_info()['bytes'],prepare.cache_info()['max_bytes'])

    def test_limites_y_extension_firma(self):
        for kwargs in ({'max_entradas':MAX_ENTRADAS+1},{'max_bytes':64*1024*1024+1},{'max_entradas':True},{'max_bytes':0}):
            with self.assertRaises(ValueError):reutilizar_malla_pura(**kwargs)
        calls=[]
        @reutilizar_malla_pura
        def prepare(g,c,**kwargs):calls.append(1);return kwargs
        prepare({}, {}, extra=1);prepare({}, {}, extra=1)
        self.assertEqual(len(calls),2);self.assertEqual(prepare.cache_info()['entradas'],0)

class ExpulsionCuatroEntradasTests(unittest.TestCase):
    def test_tres_modelos_no_se_expulsan_entre_si_y_el_quinto_expulsa_el_mas_antiguo(self):
        calls = []
        @reutilizar_malla_pura
        def prepare(g, c):
            calls.append((g, c)); return {"g": g, "c": c}
        for g in (1, 2, 3, 1, 2, 3):      # listado repetido de 3 modelos: solo 3 cálculos
            prepare({"g": g}, {"revision": "a"})
        self.assertEqual(len(calls), 3)
        prepare({"g": 4}, {"revision": "a"}); prepare({"g": 5}, {"revision": "a"})   # 5 > 4: sale el menos usado
        prepare({"g": 1}, {"revision": "a"})
        self.assertEqual(len(calls), 6)
        self.assertLessEqual(prepare.cache_info()["entradas"], MAX_ENTRADAS)


class PlanesConCacheDelProductoTests(unittest.TestCase):
    """El plan con la cache del producto (frío y caliente) es idéntico al del original sin cache."""
    def comprobar(self, case, config):
        from unittest.mock import patch
        from draft2model import malla_preparacion as mp
        with patch.object(mp, "preparar_malla", mp.preparar_malla.__wrapped__):
            baseline = case.plan(config)
        mp.preparar_malla.cache_clear()
        cold = case.plan(config)
        warm = case.plan(config)
        self.assertEqual(baseline, cold)
        self.assertEqual(baseline, warm)
        self.assertGreaterEqual(mp.preparar_malla.cache_info()["hits"], 1)

    def test_planes_geometrias_y_huecos_completos_iguales(self):
        from tests.test_liquidos_ruta201 import CasoLiquidos
        for scenario in ("horizontal", "inclinado", "vertical", "conectados"):
            with self.subTest(scenario=scenario):
                case = CasoLiquidos()
                try:
                    case.setUp()
                    config = case.aprobar_en_disco(case.montar_liquidos(scenario, "ausente_confirmado", patrones=()))
                    self.comprobar(case, config)
                finally:
                    case.doCleanups()

    def test_plan_con_liquidos_y_contenido_igual(self):
        from tests import test_contenido_liquidos_258 as cf
        case = cf.ContenidoTests()
        try:
            case.setUp()
            config = case.montar_contenido()
            config["revision"] = {"estado": "borrador", "aprobacion": None}
            config = case.aprobar_en_disco(config)
            self.comprobar(case, config)
        finally:
            case.doCleanups()

class OrdenExactoTests(unittest.TestCase):
    """Revisión Codex 284: primar con un orden y consultar otro devuelve EXACTAMENTE lo que daría el original (sin sort_keys)."""

    def test_salida_depende_del_orden_de_entrada_como_el_original(self):
        import json
        def original(g, c):
            return {k: g[k] for k in g} | {"c": dict(c)}          # la salida conserva el orden de la entrada
        cached = reutilizar_malla_pura(original)
        a, b = ({"x": 1, "y": 2}, {"r": 1, "s": 2}), ({"y": 2, "x": 1}, {"s": 2, "r": 1})
        for primero, segundo in ((a, b), (b, a)):
            cached.cache_clear()
            cached(*primero)
            for args in (segundo, primero, segundo):
                self.assertEqual(json.dumps(cached(*args)), json.dumps(original(*args)))

    def test_salida_sellada_conserva_orden_de_insercion(self):
        import json
        @reutilizar_malla_pura
        def prepare(g, c):
            return {"z": 1, "a": {"y": 2, "b": 3}}
        frio = prepare({"k": 1}, {})
        caliente = prepare({"k": 1}, {})
        self.assertEqual(json.dumps(caliente), json.dumps(frio))
        self.assertEqual(json.dumps(caliente), '{"z": 1, "a": {"y": 2, "b": 3}}')


if __name__ == '__main__':
    unittest.main()
