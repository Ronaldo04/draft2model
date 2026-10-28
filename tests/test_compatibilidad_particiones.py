"""Compatibilidad entre particiones con conexiones de borde explícitas: verificación INDEPENDIENTE.

Los verificadores no usan funciones del módulo: nodos sobre cada segmento compartido en XYZ, ausencia de nodos
colgantes entre superficies, incidencias por superficie, áreas de Newell frente a las particiones originales y a
las áreas netas fuente. Datos sintéticos; sin ETABS.
"""
import copy
import json
import math
import unittest
from pathlib import Path

from draft2model import compatibilidad_particiones as cp
from draft2model import particion_superficies as ps
from draft2model.validacion_geometria import validar_geometria

EJEMPLO = Path(__file__).resolve().parents[1] / "examples" / "geometria_sintetica.json"
PROC = {"tipo": "sintetico", "descripcion": "Geometría SINTÉTICA de compatibilidad; no representa una obra."}


def geometria(vertices, superficies, huecos=(), unidad="m", factor=1.0):
    data = json.loads(EJEMPLO.read_text(encoding="utf-8"))
    data.update(version_contrato="0.3.0", unidad_longitud=unidad, niveles=[], nodos=[], muros=[], faltantes=[],
                procedencia=copy.deepcopy(PROC), revision={"estado": "borrador", "aprobacion": None})
    data["vertices"] = [{"id": k, "x": p[0] * factor, "y": p[1] * factor, "z": p[2] * factor, "procedencia": copy.deepcopy(PROC)}
                        for k, p in vertices.items()]
    data["superficies"] = [{"id": s, "vertices": list(ids), "papel_geometrico": "sintética", "procedencia": copy.deepcopy(PROC)}
                           for s, ids in superficies]
    data["aberturas"] = [{"id": h, "superficie": s, "vertices": list(ids), "procedencia": copy.deepcopy(PROC)} for h, s, ids in huecos]
    return data


def documento(geo, pares, ident="CX1"):
    vg = validar_geometria(copy.deepcopy(geo))
    doc = {"contrato": "draft2model.conexiones_borde", "version_contrato": "0.1.0", "id": ident,
           "geometria": {"sha256_geometria_canonica": cp._sha(geo), "huella_contenido": vg.huella_contenido},
           "conexiones": [{"id": f"C{i}", "a": {"superficie": a[0], "desde": a[1], "hasta": a[2]},
                           "b": {"superficie": b[0], "desde": b[1], "hasta": b[2]}, "fuente": "F1"} for i, (a, b) in enumerate(pares, 1)],
           "fuentes": [{"id": "F1", "descripcion": "Croquis sintético de conexiones", "referencia": "prueba", "sha256": "a" * 64}],
           "declaracion": {"declarado_por": "Revisor sintético", "fecha": "2026-10-20", "identidad": "declarada_no_verificada",
                           "alcance": "Bordes compartidos sintéticos", "huella_conexiones": ""}}
    doc["declaracion"]["huella_conexiones"] = cp.huella_conexiones(doc)
    return doc


def particiones(geo):
    return [ps.particionar_superficie(geo, s["id"]) for s in geo["superficies"]]


# -- verificador independiente ----------------------------------------------------

def sub(a, b):
    return [x - y for x, y in zip(a, b)]


def punto(a, b):
    return math.fsum(x * y for x, y in zip(a, b))


def newell(q):
    n = len(q)
    return [math.fsum((q[i][(k + 1) % 3] - q[(i + 1) % n][(k + 1) % 3]) * (q[i][(k + 2) % 3] + q[(i + 1) % n][(k + 2) % 3])
                      for i in range(n)) for k in range(3)]


def sobre(p, a, b, tol):
    ab = sub(b, a)
    t = punto(sub(p, a), ab) / punto(ab, ab)
    cerca = math.dist(p, [x + t * y for x, y in zip(a, ab)]) <= tol
    return cerca, t


class Verificador(unittest.TestCase):
    def compatibilizar(self, geo, doc):
        partes = particiones(geo)
        antes = (copy.deepcopy(geo), copy.deepcopy(partes), copy.deepcopy(doc))
        r = cp.compatibilizar_particiones(geo, partes, doc)
        self.assertEqual((geo, partes, doc), antes)  # entradas intactas
        self.assertEqual(r, cp.compatibilizar_particiones(copy.deepcopy(geo), copy.deepcopy(partes), copy.deepcopy(doc)))
        json.dumps(r, allow_nan=False)
        self.assertEqual((r["contrato"], r["ejecutable"], r["aprueba_ingenieria"]), ("draft2model.compatibilidad_particiones", False, False))
        self.verificar(geo, partes, r)
        return r, partes

    def verificar(self, geo, partes, r):
        div = {"m": 1, "cm": 100, "mm": 1000}[geo["unidad_longitud"]]
        vx = {v["id"]: [v["x"] / div, v["y"] / div, v["z"] / div] for v in geo["vertices"]}
        nodos = {n["id"]: n["xyz_m"] for n in r["nodos"]}
        self.assertEqual(len(nodos), len(r["nodos"]))
        originales = {p["superficie"]["id"]: p for p in partes}
        escala = max(math.dist(a, b) for a in vx.values() for b in vx.values())
        tol = 1e-9 * escala
        for pieza in r["piezas"]:
            sid = pieza["superficie"]
            orig = originales[sid]
            self.assertEqual([c["id"] for c in pieza["celdas"]], [c["id"] for c in orig["celdas"]])
            normal = orig["superficie"]["normal_unitaria"]
            total = 0.0
            dirigidas = set()
            for cl, oc in zip(pieza["celdas"], orig["celdas"]):
                self.assertEqual(cl["pieza_de"], sid)
                q = [nodos[n] for n in cl["nodos"]]
                area = punto(newell(q), normal) / 2
                self.assertGreater(area, 0)
                xyz_orig = {x["id"]: x["xyz_m"] for x in orig["nodos"]}
                self.assertAlmostEqual(area, punto(newell([xyz_orig[i] for i in oc["nodos"]]), normal) / 2, delta=1e-9 * max(1, area))
                total += area
                for i in range(len(cl["nodos"])):
                    d = (cl["nodos"][i], cl["nodos"][(i + 1) % len(cl["nodos"])])
                    self.assertNotIn(d, dirigidas)
                    dirigidas.add(d)
            host = next(s for s in geo["superficies"] if s["id"] == sid)
            bruta = math.hypot(*newell([vx[v] for v in host["vertices"]])) / 2
            huecos = math.fsum(math.hypot(*newell([vx[v] for v in a["vertices"]])) / 2 for a in geo["aberturas"] if a["superficie"] == sid)
            self.assertAlmostEqual(total, bruta - huecos, delta=1e-9 * bruta)
            frontera = {frozenset(d) for d in dirigidas if (d[1], d[0]) not in dirigidas}
            cadenas = {frozenset((u, w)) for cd in pieza["cadenas_contorno"] for u, w in zip(cd["nodos"], cd["nodos"][1:])}
            self.assertEqual(frontera, cadenas)
        celdas = {p["superficie"]: p["celdas"] for p in r["piezas"]}
        for cx in r["conexiones"]:
            a0, a1 = vx[cx["a"]["desde"]], vx[cx["a"]["hasta"]]
            ini, fin = nodos[cx["solape"]["inicio"]], nodos[cx["solape"]["fin"]]
            self.assertGreater(math.dist(ini, fin), tol)
            for extremo in (ini, fin):
                self.assertTrue(sobre(extremo, a0, a1, tol)[0])
            # Todos los nodos de ambas superficies situados sobre el solape son exactamente los compartidos.
            en_solape = set()
            for sid in (cx["a"]["superficie"], cx["b"]["superficie"]):
                for cl in celdas[sid]:
                    for n in cl["nodos"]:
                        cerca, t = sobre(nodos[n], ini, fin, tol)
                        if cerca and -1e-12 <= t <= 1 + 1e-12:
                            en_solape.add(n)
            self.assertEqual(en_solape, set(cx["nodos_compartidos"]))
            # Ningún nodo compartido dentro de una arista de celda de cualquiera de las dos superficies (sin colgantes).
            for sid in (cx["a"]["superficie"], cx["b"]["superficie"]):
                for cl in celdas[sid]:
                    ns = cl["nodos"]
                    for i in range(len(ns)):
                        u, w = nodos[ns[i]], nodos[ns[(i + 1) % len(ns)]]
                        for n in cx["nodos_compartidos"]:
                            if n in (ns[i], ns[(i + 1) % len(ns)]):
                                continue
                            cerca, t = sobre(nodos[n], u, w, tol)
                            self.assertFalse(cerca and 1e-12 < t < 1 - 1e-12, f"nodo colgante {n} en {cl['id']}")


PISO = dict(VA=(0, 0, 3), VB=(4, 0, 3), VC=(4, 3, 3), VD=(0, 3, 3), H1=(1, 0.5, 3), H2=(2, 0.5, 3), H3=(2, 1.5, 3), H4=(1, 1.5, 3))


class CompatibilidadTests(Verificador):
    def test_coplanares_lado_cortado_y_lado_sin_cortes(self):
        v = dict(PISO, H1=(1, 1.5, 3), H2=(2, 1.5, 3), H3=(2, 2.5, 3), H4=(1, 2.5, 3), VE=(4, 6, 3), VF=(0, 6, 3))
        geo = geometria(v, [("S1", ["VA", "VB", "VC", "VD"]), ("S2", ["VD", "VC", "VE", "VF"])], [("A1", "S1", ["H1", "H2", "H3", "H4"])])
        antes_s2 = ps.particionar_superficie(geo, "S2")
        self.assertEqual(len(antes_s2["celdas"]), 1)
        r, _ = self.compatibilizar(geo, documento(geo, [(("S1", "VC", "VD"), ("S2", "VD", "VC"))]))
        s2 = next(p for p in r["piezas"] if p["superficie"] == "S2")["celdas"][0]
        self.assertGreater(len(s2["nodos"]), 4)  # recibe los cortes del hueco de S1
        self.assertEqual(len(r["conexiones"][0]["nodos_compartidos"]), 4)

    def test_ortogonales_orientacion_inversa_y_solape_parcial(self):
        casos = {
            "completo, b directa": (dict(PISO, WA=(0, 0, 0), WB=(4, 0, 0)), ["WA", "WB", "VB", "VA"], ("S2", "VB", "VA")),
            "completo, b inversa": (dict(PISO, WA=(0, 0, 0), WB=(4, 0, 0)), ["WA", "WB", "VB", "VA"], ("S2", "VA", "VB")),
            "parcial": (dict(PISO, H1=(2.5, 0.5, 3), H2=(3, 0.5, 3), H3=(3, 1, 3), H4=(2.5, 1, 3), WA=(2, 0, 0), WB=(6, 0, 0), WC=(6, 0, 3),
                             WD=(2, 0, 3)), ["WA", "WB", "WC", "WD"], ("S2", "WC", "WD")),
        }
        for nombre, (v, muro, lado_b) in casos.items():
            with self.subTest(nombre):
                geo = geometria(v, [("S1", ["VA", "VB", "VC", "VD"]), ("S2", muro)], [("A1", "S1", ["H1", "H2", "H3", "H4"])])
                r, _ = self.compatibilizar(geo, documento(geo, [(("S1", "VA", "VB"), lado_b)]))
                cx = r["conexiones"][0]
                if nombre == "parcial":
                    self.assertEqual((cx["solape"]["inicio"], cx["solape"]["fin"]), ("WD", "VB"))
                    self.assertAlmostEqual(cx["solape"]["longitud_m"], 2)
                    self.assertTrue(any(i["particion"] == "S1" for n in r["nodos"] if n["id"] == "WD" for i in n["insertado_en"]))
                    libres = {(b["superficie"], b["arista"]) for b in r["bordes_no_conectados"] if b["contorno"].startswith("superficie:")}
                    self.assertIn(("S1", 0), libres)  # tramo 0..2 del borde del piso sin conexión
                self.assertEqual(cx["b"]["orientacion"], "inversa" if nombre == "completo, b inversa" else "directa")
                self.assertEqual(cx["a"]["orientacion"], "directa")

    def test_tres_hosts_propagacion_y_varias_conexiones(self):
        v = dict(PISO, UA=(0, -3, 3), UB=(4, -3, 3), G1=(3, -1, 3), G2=(3.5, -1, 3), G3=(3.5, -0.5, 3), G4=(3, -0.5, 3),
                 WA=(0, 0, 0), WB=(4, 0, 0), XA=(4, 0, 0), XB=(4, 3, 0))
        geo = geometria(v, [("S1", ["VA", "VB", "VC", "VD"]), ("S2", ["WA", "WB", "VB", "VA"]), ("S3", ["UA", "UB", "VB", "VA"]),
                            ("S4", ["WB", "XB", "VC", "VB"])],
                        [("A1", "S1", ["H1", "H2", "H3", "H4"]), ("A3", "S3", ["G1", "G2", "G3", "G4"])])
        doc = documento(geo, [(("S1", "VA", "VB"), ("S2", "VB", "VA")), (("S2", "VA", "VB"), ("S3", "VB", "VA")),
                              (("S1", "VB", "VC"), ("S4", "VC", "VB"))])
        r, _ = self.compatibilizar(geo, doc)
        compartidos = [set(cx["nodos_compartidos"]) for cx in r["conexiones"]]
        self.assertEqual(compartidos[0], compartidos[1])  # S1 y S3 comparten cortes a través de S2 sin conexión directa
        self.assertGreaterEqual(len(compartidos[0]), 6)  # cortes de A1 (S1) y de A3 (S3) en ambos sentidos
        s3 = next(p for p in r["piezas"] if p["superficie"] == "S3")
        s1 = next(p for p in r["piezas"] if p["superficie"] == "S1")
        self.assertTrue(any(n.startswith("S1#") for c in s3["celdas"] for n in c["nodos"]))  # cortes de S1 en S3
        self.assertTrue(any(n.startswith("S3#") for c in s1["celdas"] for n in c["nodos"]))  # y de S3 en S1
        s4 = next(p for p in r["piezas"] if p["superficie"] == "S4")
        self.assertEqual(len(r["conexiones"][2]["nodos_compartidos"]) >= 2, True)
        self.assertTrue(s4["celdas"])

    def test_unidades_y_traslacion_grande(self):
        v = dict(PISO, WA=(0, 0, 0), WB=(4, 0, 0))
        ref = None
        for unidad, factor in (("m", 1), ("cm", 100), ("mm", 1000)):
            geo = geometria(v, [("S1", ["VA", "VB", "VC", "VD"]), ("S2", ["WA", "WB", "VB", "VA"])], [("A1", "S1", ["H1", "H2", "H3", "H4"])], unidad, factor)
            r, _ = self.compatibilizar(geo, documento(geo, [(("S1", "VA", "VB"), ("S2", "VB", "VA"))]))
            firma = ([n["id"] for n in r["nodos"]], [c["nodos"] for p in r["piezas"] for c in p["celdas"]])
            ref = ref or firma
            self.assertEqual(firma, ref)
        lejos = {k: (x + 1e6, y - 1e6, z + 10) for k, (x, y, z) in v.items()}
        geo = geometria(lejos, [("S1", ["VA", "VB", "VC", "VD"]), ("S2", ["WA", "WB", "VB", "VA"])], [("A1", "S1", ["H1", "H2", "H3", "H4"])])
        r, _ = self.compatibilizar(geo, documento(geo, [(("S1", "VA", "VB"), ("S2", "VB", "VA"))]))
        self.assertEqual(len(r["conexiones"][0]["nodos_compartidos"]), 4)

    def test_sin_declaracion_no_hay_union(self):
        v = dict(PISO, WA=(0, 0, 0), WB=(4, 0, 0), WC=(4, 0, 3), WD=(0, 0, 3))  # borde coincidente con IDs distintos
        geo = geometria(v, [("S1", ["VA", "VB", "VC", "VD"]), ("S2", ["WA", "WB", "WC", "WD"])], [("A1", "S1", ["H1", "H2", "H3", "H4"])])
        r, partes = self.compatibilizar(geo, documento(geo, []))
        s2 = next(p for p in r["piezas"] if p["superficie"] == "S2")
        self.assertEqual(s2["celdas"][0]["nodos"], ["WA", "WB", "WC", "WD"])  # ningún corte importado por proximidad
        self.assertEqual(r["comprobaciones"]["nodos_insertados"], 0)
        self.assertIn(("S2", 2), {(b["superficie"], b["arista"]) for b in r["bordes_no_conectados"]})

    def test_rechazos(self):
        v = dict(PISO, WA=(0, 0, 0), WB=(4, 0, 0), WC=(4, 0, 3), WD=(0, 0, 3), PA=(4, 0, 0), PB=(6, 0, 0), PC=(6, 0, 3),
                 OA=(0, 0.01, 0), OB=(4, 0.01, 0), OC=(4, 0.01, 3), OD=(0, 0.01, 3))
        geo = geometria(v, [("S1", ["VA", "VB", "VC", "VD"]), ("S2", ["WA", "WB", "WC", "WD"]), ("S3", ["PA", "PB", "PC", "VB"]),
                            ("S4", ["OA", "OB", "OC", "OD"])], [("A1", "S1", ["H1", "H2", "H3", "H4"])])
        partes = particiones(geo)
        bueno = documento(geo, [(("S1", "VA", "VB"), ("S2", "WC", "WD"))])
        cp.compatibilizar_particiones(geo, partes, bueno)

        def doc_mod(f):
            d = copy.deepcopy(bueno)
            f(d)
            return d

        def redeclarar(d):
            d["declaracion"]["huella_conexiones"] = cp.huella_conexiones(d)
            return d
        alterada = copy.deepcopy(partes)
        alterada[1]["celdas"][0]["nodos"] = list(reversed(alterada[1]["celdas"][0]["nodos"]))
        otra_geo = copy.deepcopy(geo)
        otra_geo["vertices"][4]["x"] = 1.1
        casos = {
            "superficie ajena": (partes, documento(geo, [(("S1", "VA", "VB"), ("S9", "WC", "WD"))])),
            "segmento ajeno": (partes, documento(geo, [(("S1", "VA", "VC"), ("S2", "WC", "WD"))])),
            "cruce puntual": (partes, documento(geo, [(("S1", "VA", "VB"), ("S3", "PB", "PC"))])),
            "contacto en un extremo": (partes, documento(geo, [(("S1", "VA", "VB"), ("S3", "PA", "PB"))])),
            "no coincidentes": (partes, documento(geo, [(("S1", "VA", "VB"), ("S4", "OC", "OD"))])),
            "misma superficie": (partes, documento(geo, [(("S1", "VA", "VB"), ("S1", "VB", "VC"))])),
            "par repetido": (partes, documento(geo, [(("S1", "VA", "VB"), ("S2", "WC", "WD")), (("S1", "VB", "VA"), ("S2", "WD", "WC"))])),
            "declaración alterada": (partes, doc_mod(lambda d: d["conexiones"][0]["b"].update(desde="WD", hasta="WC"))),
            "campo extra": (partes, redeclarar(doc_mod(lambda d: d["conexiones"][0].update(nota="x")))),
            "fuente alterada": (partes, redeclarar(doc_mod(lambda d: d["fuentes"][0].update(sha256="Z" * 64)))),
            "NaN": (partes, doc_mod(lambda d: d["fuentes"][0].update(descripcion=float("nan")))),
            "identidad verificada": (partes, redeclarar(doc_mod(lambda d: d["declaracion"].update(identidad="verificada")))),
            "geometría distinta": (partes, redeclarar(doc_mod(lambda d: d["geometria"].update(huella_contenido="0" * 64)))),
            "partición alterada": (alterada, bueno),
            "partición omitida": ([partes[0], partes[2], partes[3]], bueno),
            "partición duplicada": (partes + [partes[1]], bueno),
            "partición de otra fuente": (partes[:1] + [ps.particionar_superficie(otra_geo, "S2")] + partes[2:], bueno),
            "sin particiones": ([], bueno),
        }
        for nombre, (pp, doc) in casos.items():
            with self.subTest(nombre), self.assertRaises(cp.ErrorCompatibilidad):
                cp.compatibilizar_particiones(geo, pp, doc)

    def test_puntos_ambiguos_rechazados_sin_fusion(self):
        # Dentro del solape: corte del hueco a x=3 y vértice colineal del muro a x=3+2e-12 (distintos, más cerca que el criterio).
        v = dict(PISO, H1=(3, 0.5, 3), H2=(3.5, 0.5, 3), H3=(3.5, 1, 3), H4=(3, 1, 3),
                 WA=(2.5, 0, 0), WB=(6, 0, 0), WC=(6, 0, 3), WM=(3 + 2e-12, 0, 3), WD=(2.5, 0, 3))
        geo = geometria(v, [("S1", ["VA", "VB", "VC", "VD"]), ("S2", ["WA", "WB", "WC", "WM", "WD"])], [("A1", "S1", ["H1", "H2", "H3", "H4"])])
        fuera = dict(v, WM=(5, 0, 3))  # control: mismo caso sin la casi-coincidencia se compatibiliza
        geo_ok = geometria(fuera, [("S1", ["VA", "VB", "VC", "VD"]), ("S2", ["WA", "WB", "WC", "WM", "WD"])], [("A1", "S1", ["H1", "H2", "H3", "H4"])])
        self.compatibilizar(geo_ok, documento(geo_ok, [(("S1", "VA", "VB"), ("S2", "WM", "WD"))]))
        with self.assertRaises(cp.ErrorCompatibilidad) as ctx:
            cp.compatibilizar_particiones(geo, particiones(geo), documento(geo, [(("S1", "VA", "VB"), ("S2", "WM", "WD"))]))
        self.assertIn("ambiguo", str(ctx.exception))

    def test_verificador_detecta_colgante_si_se_omite_la_propagacion(self):
        v = dict(PISO, WA=(0, 0, 0), WB=(4, 0, 0))
        geo = geometria(v, [("S1", ["VA", "VB", "VC", "VD"]), ("S2", ["WA", "WB", "VB", "VA"])], [("A1", "S1", ["H1", "H2", "H3", "H4"])])
        doc = documento(geo, [(("S1", "VA", "VB"), ("S2", "VB", "VA"))])
        partes = particiones(geo)
        r = cp.compatibilizar_particiones(geo, partes, doc)
        malo = copy.deepcopy(r)
        celda = next(p for p in malo["piezas"] if p["superficie"] == "S2")["celdas"][0]
        celda["nodos"] = [n for n in celda["nodos"] if not n.startswith("S1#")]
        with self.assertRaises(AssertionError):
            self.verificar(geo, partes, malo)


if __name__ == "__main__":
    unittest.main()
