"""Contornos sintéticos: verifican geometría computacional, no estructuras reales."""
import copy
import math
import unittest

from draft2model import contratos as c
from draft2model.geometria_superficies import BLOQUEO_INTEGRACION, migrar_a_superficies
from draft2model.validacion_geometria import validar_geometria
from tests import test_validacion_geometria as legado


def ejemplo(puntos=None, unidad="m"):
    puntos = puntos or [(0, 0, 0), (4, 0, 0), (4, 3, 0), (0, 3, 0)]
    factor = {"m": 1, "cm": 100, "mm": 1000}[unidad]
    data = migrar_a_superficies(legado.sintetico(unidad))
    data["niveles"] = data["nodos"] = data["muros"] = []
    data["vertices"] = [{"id": f"V{i}", **{k: x*factor for k, x in zip(("x", "y", "z"), p)},
                         "procedencia": copy.deepcopy(data["procedencia"])} for i, p in enumerate(puntos)]
    data["superficies"] = [{"id": "S1", "vertices": [v["id"] for v in data["vertices"]],
                             "papel_geometrico": "contorno de prueba sin sección física",
                             "procedencia": copy.deepcopy(data["procedencia"])}]
    return data


class SuperficiesTests(unittest.TestCase):
    def test_unidades_equivalentes_y_fuente_intacta(self):
        resultados = []
        for unidad in ("m", "cm", "mm"):
            data = ejemplo(unidad=unidad)
            original = copy.deepcopy(data)
            r = validar_geometria(data)
            self.assertTrue(r.consistente, r.errores)
            self.assertFalse(r.disponible_para_modelado)
            self.assertIn(BLOQUEO_INTEGRACION, r.bloqueos)
            self.assertEqual(data, original)
            self.assertEqual(r.a_dict()["version_contrato"], "0.2.0")
            resultados.append(r.derivados_m["superficies"]["S1"])
        self.assertEqual(resultados[0], resultados[1])
        self.assertEqual(resultados[0], resultados[2])
        self.assertEqual(resultados[0]["area_m2"], 12)
        self.assertEqual(resultados[0]["normal_unitaria"], [0, 0, 1])

    def test_orientaciones_concavidad_y_vertices_intermedios(self):
        casos = [([(0,0,0), (4,0,0), (4,3,3), (0,3,3)], 12*math.sqrt(2)),
                 ([(0,0,0), (0,4,0), (0,4,3), (0,0,3)], 12),
                 ([(0,0,0), (4,0,0), (2,1,0), (4,3,0), (0,3,0)], 9),
                 ([(0,0,0), (2,0,0), (4,0,0), (4,3,0), (0,3,0)], 12)]
        for puntos, area in casos:
            with self.subTest(puntos=puntos):
                r = validar_geometria(ejemplo(puntos))
                self.assertTrue(r.consistente, r.errores)
                self.assertAlmostEqual(r.derivados_m["superficies"]["S1"]["area_m2"], area)

    def test_inversion_normal_sin_reparar(self):
        data = ejemplo()
        data["superficies"][0]["vertices"].reverse()
        r = validar_geometria(data)
        self.assertEqual(r.derivados_m["superficies"]["S1"]["normal_unitaria"], [0,0,-1])
        self.assertEqual(r.geometria_m["superficies"][0]["vertices"], ["V3","V2","V1","V0"])

    def test_geometrias_invalidas(self):
        casos = [[(0,0,0), (4,3,0), (4,0,0), (0,3,0)],
                 [(0,0,0), (4,0,0), (4,3,.01), (0,3,0)],
                 [(0,0,0), (1,0,0), (2,0,0)],
                 [(0,0,0), (4,0,0), (4,3,0), (0,0,0)],
                 [(0,0,0), (4,0,0), (2,0,0), (2,3,0), (0,3,0)],
                 [(0,0,0), (4,0,0), (4,4,0), (2,0,0), (0,4,0)],
                 [(1e16,1e16,0), (1e16+4,1e16,0), (1e16+4,1e16+4,0)],
                 [(0,0,0), (1e308,0,0), (1e308,1e308,0)],
                 [(0,0,0), (1e-200,0,0), (0,1e-200,0)]]
        for puntos in casos:
            with self.subTest(puntos=puntos):
                r = validar_geometria(ejemplo(puntos))
                self.assertFalse(r.consistente)
                self.assertIsNone(r.geometria_m)
                self.assertIsNone(r.huella_contenido)

    def test_esquema_y_referencias_rechazan_sin_excepciones(self):
        cambios = [lambda d: d["vertices"][0].update(x=True),
                   lambda d: d["vertices"][0].update(x=float("nan")),
                   lambda d: d["vertices"][0].update(z=None),
                   lambda d: d["vertices"][0].update(x=10**1000),
                   lambda d: d["vertices"][0].update(id="V1"),
                   lambda d: d["vertices"][0].pop("procedencia"),
                   lambda d: d["vertices"][0].update(piso="N1"),
                   lambda d: d["vertices"][0]["procedencia"].update(tipo="plano"),
                   lambda d: d["superficies"][0].update(vertices=["V0","V1"]),
                   lambda d: d["superficies"][0].update(vertices=["V0","V1","ausente"]),
                   lambda d: d["superficies"][0].update(vertices=["V0","V1",{}]),
                   lambda d: d["superficies"][0].update(vertices=["V0","V1","V2","V0"]),
                   lambda d: d["superficies"][0].update(papel_geometrico=" "),
                   lambda d: d["superficies"][0].pop("id"),
                   lambda d: d["superficies"][0].update(procedencia=[]),
                   lambda d: d.update(vertices={}),
                   lambda d: d.update(superficies=None),
                   lambda d: d.pop("superficies")]
        for cambiar in cambios:
            data = ejemplo()
            cambiar(data)
            with self.subTest(cambiar=cambiar):
                self.assertFalse(validar_geometria(data).consistente)

    def test_aprobacion_ligada_superficies_y_bloqueo_integracion(self):
        data = legado.aprobar(ejemplo())
        r = validar_geometria(data)
        self.assertEqual(r.huella_contenido, c.huella_contenido(data))
        self.assertEqual(r.bloqueos, [BLOQUEO_INTEGRACION])
        data["vertices"][0]["x"] = -.1
        self.assertTrue(any("huella distinta" in x for x in validar_geometria(data).bloqueos))

    def test_migracion_solo_explicita_sin_aprobacion_heredada(self):
        original = legado.aprobar(legado.sintetico())
        copia = copy.deepcopy(original)
        nueva = migrar_a_superficies(original)
        self.assertEqual(original, copia)
        self.assertEqual(nueva["revision"], {"estado": "borrador", "aprobacion": None})
        self.assertEqual(nueva["muros"], original["muros"])
        self.assertTrue(validar_geometria(nueva).consistente)
        for invalido in (nueva, {}, None):
            with self.assertRaises(ValueError):
                migrar_a_superficies(invalido)
        original["muros"][0]["espesor"] = -1
        with self.assertRaises(ValueError):
            migrar_a_superficies(original)

    def test_v01_no_admite_nuevas_colecciones(self):
        data = legado.sintetico()
        self.assertEqual(c.VERSION_GEOMETRIA, "0.1.0")
        data["vertices"] = []
        self.assertFalse(validar_geometria(data).consistente)

    def test_misma_version_incompleta_no_es_version_desconocida(self):
        data = ejemplo()
        del data["vertices"]
        del data["superficies"]
        errores = validar_geometria(data).errores
        self.assertEqual({e.ruta for e in errores}, {"$.vertices", "$.superficies"})
        self.assertTrue(all(e.codigo == "campo_ausente" for e in errores))

    def test_subflujo_fisico_normalizacion_a_cero(self):
        data = ejemplo(unidad="mm")
        data["vertices"][0]["x"] = 5e-324
        r = validar_geometria(data)
        self.assertFalse(r.consistente)
        self.assertTrue(any(e.codigo == "normalizacion_a_cero" for e in r.errores))


if __name__ == "__main__":
    unittest.main()
