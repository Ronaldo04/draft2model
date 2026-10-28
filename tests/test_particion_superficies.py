"""Partición conforme de superficies con huecos: comprobaciones INDEPENDIENTES del algoritmo.

Los verificadores de esta prueba no usan funciones del módulo: áreas de Newell en 3D, base ortonormal
propia del plano, recorte Sutherland–Hodgman para solapes e intersecciones con huecos, incidencias de
aristas, cadenas de contorno y nodos colgantes en coordenadas XYZ. Datos sintéticos; sin ETABS.
"""
import copy
import json
import math
import unittest
from pathlib import Path

from draft2model import particion_superficies as ps

EJEMPLO = Path(__file__).resolve().parents[1] / "examples" / "geometria_sintetica.json"
PROC = {"tipo": "sintetico", "descripcion": "Geometría SINTÉTICA de prueba de partición; no representa una obra."}


def geometria(vertices, host, huecos=(), unidad="m", factor=1.0, procedencia=PROC, extra_superficies=()):
    """Geometría 0.3 en borrador. `vertices` en metros; `factor` los reexpresa en la unidad declarada."""
    data = json.loads(EJEMPLO.read_text(encoding="utf-8"))
    data.update(version_contrato="0.3.0", unidad_longitud=unidad, niveles=[], nodos=[], muros=[], faltantes=[],
                procedencia=copy.deepcopy(procedencia), revision={"estado": "borrador", "aprobacion": None})
    data["vertices"] = [{"id": k, "x": p[0] * factor, "y": p[1] * factor, "z": p[2] * factor, "procedencia": copy.deepcopy(procedencia)}
                        for k, p in vertices.items()]
    data["superficies"] = [{"id": "S1", "vertices": list(host), "papel_geometrico": "host sintético",
                            "procedencia": copy.deepcopy(procedencia)}]
    data["superficies"] += [{"id": sid, "vertices": list(ids), "papel_geometrico": "otra", "procedencia": copy.deepcopy(procedencia)}
                            for sid, ids in extra_superficies]
    data["aberturas"] = [{"id": hid, "superficie": "S1", "vertices": list(ids), "procedencia": copy.deepcopy(procedencia)}
                         for hid, ids in huecos]
    return data


# -- geometría independiente ---------------------------------------------------

def sub(a, b):
    return [x - y for x, y in zip(a, b)]


def cruz(a, b):
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]]


def punto(a, b):
    return math.fsum(x * y for x, y in zip(a, b))


def newell(q):
    n = len(q)
    return [math.fsum((q[i][(k + 1) % 3] - q[(i + 1) % n][(k + 1) % 3]) * (q[i][(k + 2) % 3] + q[(i + 1) % n][(k + 2) % 3])
                      for i in range(n)) for k in range(3)]


def area3(q):
    return math.hypot(*newell(q)) / 2


def unitario(v):
    m = math.hypot(*v)
    return [x / m for x in v]


class Plano:
    """Base ortonormal propia (distinta de la proyección por eje del módulo)."""

    def __init__(self, contorno):
        self.o = contorno[0]
        self.n = unitario(newell(contorno))
        self.e1 = unitario(sub(contorno[1], contorno[0]))
        self.e2 = cruz(self.n, self.e1)

    def a2(self, p):
        d = sub(p, self.o)
        return (punto(d, self.e1), punto(d, self.e2))


def area2(p):
    return math.fsum(p[i][0] * p[(i + 1) % len(p)][1] - p[(i + 1) % len(p)][0] * p[i][1] for i in range(len(p))) / 2


def dentro(p, poligono):
    r = False
    for i in range(len(poligono)):
        a, b = poligono[i], poligono[(i + 1) % len(poligono)]
        if (a[1] > p[1]) != (b[1] > p[1]) and a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1]) > p[0]:
            r = not r
    return r


def recortar(sujeto, recorte):
    """Sutherland–Hodgman: sujeto cualquiera, recorte convexo antihorario."""
    salida = list(sujeto)
    for i in range(len(recorte)):
        a, b = recorte[i], recorte[(i + 1) % len(recorte)]
        lado = lambda p: (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])
        entrada, salida = salida, []
        for j in range(len(entrada)):
            p, q = entrada[j - 1], entrada[j]
            lp, lq = lado(p), lado(q)
            if lq >= 0:
                if lp < 0:
                    t = lp / (lp - lq)
                    salida.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
                salida.append(q)
            elif lp >= 0:
                t = lp / (lp - lq)
                salida.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
        if not salida:
            return []
    return salida


def antihorario(p):
    return p if area2(p) > 0 else list(reversed(p))


class Verificador(unittest.TestCase):
    def comprobar(self, geo, sid="S1"):
        antes = copy.deepcopy(geo)
        r = ps.particionar_superficie(geo, sid)
        self.assertEqual(geo, antes)  # entrada intacta
        self.assertEqual(r, ps.particionar_superficie(copy.deepcopy(geo), sid))  # determinista
        json.dumps(r, allow_nan=False)
        self.assertEqual((r["contrato"], r["ejecutable"], r["aprueba_ingenieria"]), ("draft2model.particion_superficie", False, False))
        div = {"m": 1, "cm": 100, "mm": 1000}[geo["unidad_longitud"]]
        vx = {v["id"]: [v["x"] / div, v["y"] / div, v["z"] / div] for v in geo["vertices"]}
        host = next(s for s in geo["superficies"] if s["id"] == sid)
        huecos = [a for a in geo["aberturas"] if a["superficie"] == sid]
        self.assertEqual([h["id"] for h in r["huecos"]], [a["id"] for a in huecos])
        hq = [vx[v] for v in host["vertices"]]
        plano = Plano(hq)
        nodos = {n["id"]: n["xyz_m"] for n in r["nodos"]}
        self.assertEqual(len(nodos), len(r["nodos"]))
        escala = max(math.dist(a, b) for a in hq for b in hq)
        # Nodos sobre el plano; originales con su XYZ fuente; calculados sobre su arista con t declarado.
        for n in r["nodos"]:
            self.assertLess(abs(punto(sub(n["xyz_m"], plano.o), plano.n)), 1e-9 * escala)
            t = n["traza"]
            if t["tipo"] == "original":
                self.assertEqual(n["id"], t["vertice"])
                for a, b in zip(n["xyz_m"], vx[t["vertice"]]):
                    self.assertAlmostEqual(a, b, delta=1e-12 * max(1, abs(b)))
            else:
                a, b = vx[t["desde"]], vx[t["hasta"]]
                self.assertTrue(0 < t["t_aprox"] < 1)
                esperado = [x + t["t_aprox"] * (y - x) for x, y in zip(a, b)]
                self.assertLess(math.dist(esperado, n["xyz_m"]), 1e-9 * escala)
        # Áreas, orientación y convexidad.
        normal_host = unitario(newell(hq))
        bruta = area3(hq)
        a_huecos = math.fsum(area3([vx[v] for v in a["vertices"]]) for a in huecos)
        celdas2 = []
        for cl in r["celdas"]:
            q = [nodos[i] for i in cl["nodos"]]
            self.assertEqual(len(set(cl["nodos"])), len(cl["nodos"]))
            self.assertGreater(punto(newell(q), normal_host), 0, cl["id"])  # orientación coherente con la normal
            self.assertAlmostEqual(cl["area_m2"], area3(q), delta=1e-9 * bruta)
            p = antihorario([plano.a2(x) for x in q])
            for i in range(len(p)):
                a, b, d = p[i - 1], p[i], p[(i + 1) % len(p)]
                self.assertGreaterEqual((b[0] - a[0]) * (d[1] - a[1]) - (b[1] - a[1]) * (d[0] - a[0]), -1e-9 * bruta)
            celdas2.append(p)
        suma = math.fsum(area2(p) for p in celdas2)
        self.assertAlmostEqual(suma, bruta - a_huecos, delta=1e-9 * bruta)
        self.assertAlmostEqual(r["cobertura"]["area_neta_m2"], bruta - a_huecos, delta=1e-9 * bruta)
        # Celdas dentro del host, fuera de huecos, sin intersección positiva con huecos ni solapes entre sí.
        h2 = [plano.a2(x) for x in hq]
        huecos2 = [antihorario([plano.a2(vx[v]) for v in a["vertices"]]) for a in huecos]
        for p in celdas2:
            cen = (math.fsum(x for x, _ in p) / len(p), math.fsum(y for _, y in p) / len(p))
            self.assertTrue(dentro(cen, h2))
            for h in huecos2:
                self.assertFalse(dentro(cen, h))
                inter = recortar(h, p)
                self.assertLess(abs(area2(inter)) if len(inter) >= 3 else 0, 1e-9 * bruta)
        cajas = [(min(x for x, _ in p), max(x for x, _ in p), min(y for _, y in p), max(y for _, y in p)) for p in celdas2]
        for i in range(len(celdas2)):
            for j in range(i + 1, len(celdas2)):
                a, b = cajas[i], cajas[j]
                if a[0] < b[1] and b[0] < a[1] and a[2] < b[3] and b[2] < a[3]:
                    inter = recortar(celdas2[i], celdas2[j])
                    self.assertLess(abs(area2(inter)) if len(inter) >= 3 else 0, 1e-9 * bruta)
        # Incidencias: interiores dos opuestas; frontera una; frontera = segmentos de las cadenas fuente.
        dirigidas = [(cl["nodos"][i], cl["nodos"][(i + 1) % len(cl["nodos"])]) for cl in r["celdas"] for i in range(len(cl["nodos"]))]
        self.assertEqual(len(dirigidas), len(set(dirigidas)))
        cuenta = {}
        for a, b in dirigidas:
            cuenta.setdefault(frozenset((a, b)), set()).add((a, b))
        self.assertTrue(all(len(v) in (1, 2) for v in cuenta.values()))
        frontera = {k for k, v in cuenta.items() if len(v) == 1}
        segmentos = set()
        contornos = [("superficie:" + sid, host["vertices"])] + [("hueco:" + a["id"], a["vertices"]) for a in huecos]
        esperadas = [(nombre, i, ids[i], ids[(i + 1) % len(ids)]) for nombre, ids in contornos for i in range(len(ids))]
        self.assertEqual([(c_["contorno"], c_["arista"], c_["desde"], c_["hasta"]) for c_ in r["cadenas_contorno"]], esperadas)
        for cad in r["cadenas_contorno"]:
            a, b = vx[cad["desde"]], vx[cad["hasta"]]
            self.assertEqual((cad["nodos"][0], cad["nodos"][-1]), (cad["desde"], cad["hasta"]))
            ts = []
            for nid in cad["nodos"]:
                d = sub(nodos[nid], a)
                ab = sub(b, a)
                t = punto(d, ab) / punto(ab, ab)
                self.assertLess(math.dist(nodos[nid], [x + t * y for x, y in zip(a, ab)]), 1e-9 * escala)
                ts.append(t)
            self.assertEqual(ts, sorted(ts))
            self.assertEqual(len(set(ts)), len(ts))
            for u, w in zip(cad["nodos"], cad["nodos"][1:]):
                segmentos.add(frozenset((u, w)))
        self.assertEqual(frontera, segmentos)
        # Sin nodos colgantes: ningún nodo dentro de una arista de celda.
        for cl in r["celdas"]:
            ids = cl["nodos"]
            for i in range(len(ids)):
                a, b = nodos[ids[i]], nodos[ids[(i + 1) % len(ids)]]
                ab = sub(b, a)
                for nid, p in nodos.items():
                    if nid in (ids[i], ids[(i + 1) % len(ids)]):
                        continue
                    t = punto(sub(p, a), ab) / punto(ab, ab)
                    if 1e-12 < t < 1 - 1e-12:
                        self.assertGreater(math.dist(p, [x + t * y for x, y in zip(a, ab)]), 1e-9 * escala,
                                           f"nodo colgante {nid} en {cl['id']}")
        # Conectividad: el grafo de celdas por aristas interiores es conexo si la región neta lo es.
        return r


RECT = dict(VA=(0, 0, 0), VB=(4, 0, 0), VC=(4, 3, 0), VD=(0, 3, 0))


def plano_xyz(transform, puntos):
    return {k: transform(*p) for k, p in puntos.items()}


ORIENTACIONES = {"horizontal": lambda x, y, z: (x, y, 2.6), "vertical": lambda x, y, z: (0.0, x, y),
                 "inclinado": lambda x, y, z: (x, y, 0.3 * x + 0.2 * y)}


class ParticionTests(Verificador):
    def test_orientaciones_y_reversion(self):
        base = dict(RECT, H1=(1, 1, 0), H2=(2, 1, 0), H3=(2, 2, 0), H4=(1, 2, 0))
        for nombre, f in ORIENTACIONES.items():
            vx = plano_xyz(f, base)
            for host, hueco in ((["VA", "VB", "VC", "VD"], ["H1", "H2", "H3", "H4"]), (["VD", "VC", "VB", "VA"], ["H1", "H4", "H3", "H2"]),
                                (["VA", "VB", "VC", "VD"], ["H4", "H3", "H2", "H1"])):
                with self.subTest(nombre, host=host[0], hueco=hueco[1]):
                    r = self.comprobar(geometria(vx, host, [("A1", hueco)]))
                    self.assertEqual(r["comprobaciones"]["nodos_colgantes"], 0)
                    self.assertGreaterEqual(len(r["celdas"]), 4)

    def test_unidades_equivalentes(self):
        vx = plano_xyz(ORIENTACIONES["inclinado"], dict(RECT, H1=(1, 1, 0), H2=(2.5, 1, 0), H3=(1.5, 2, 0)))
        resultados = []
        for unidad, factor in (("m", 1), ("cm", 100), ("mm", 1000)):
            r = self.comprobar(geometria(vx, ["VA", "VB", "VC", "VD"], [("A1", ["H1", "H2", "H3"])], unidad, factor))
            resultados.append(r)
        ref = resultados[0]
        for r in resultados[1:]:
            self.assertEqual([c_["nodos"] for c_ in r["celdas"]], [c_["nodos"] for c_ in ref["celdas"]])
            for a, b in zip(r["nodos"], ref["nodos"]):
                self.assertEqual(a["id"], b["id"])
                self.assertLess(math.dist(a["xyz_m"], b["xyz_m"]), 1e-12 * 10)
            self.assertNotEqual(r["origen"]["sha256_geometria_canonica"], ref["origen"]["sha256_geometria_canonica"])

    def test_concavos_sin_hueco(self):
        formas = {
            "L": dict(P1=(0, 0, 0), P2=(4, 0, 0), P3=(4, 1, 0), P4=(1, 1, 0), P5=(1, 3, 0), P6=(0, 3, 0)),
            "peine": dict(P1=(0, 0, 0), P2=(5, 0, 0), P3=(5, 3, 0), P4=(4, 3, 0), P5=(4, 1, 0), P6=(3, 1, 0), P7=(3, 3, 0),
                          P8=(2, 3, 0), P9=(2, 1, 0), P10=(1, 1, 0), P11=(1, 3, 0), P12=(0, 3, 0)),
            "estrella": dict(P1=(0, 0, 0), P2=(2, 1, 0), P3=(4, 0, 0), P4=(3, 2, 0), P5=(4, 4, 0), P6=(2, 3, 0), P7=(0, 4, 0), P8=(1, 2, 0)),
        }
        for nombre, puntos in formas.items():
            for orient, f in ORIENTACIONES.items():
                with self.subTest(nombre, orient=orient):
                    vx = plano_xyz(f, puntos)
                    r = self.comprobar(geometria(vx, list(puntos)))
                    self.assertEqual(r["huecos"], [])

    def test_varios_huecos_formas_y_barrido_compartido(self):
        puntos = dict(P1=(0, 0, 0), P2=(10, 0, 0), P3=(10, 6, 0), P4=(6, 6, 0), P5=(6, 4, 0), P6=(4, 4, 0), P7=(4, 6, 0), P8=(0, 6, 0),
                      T1=(1, 1, 0), T2=(3, 1, 0), T3=(2, 3, 0),                            # triángulo
                      R1=(4, 1, 0), R2=(6, 1, 0), R3=(6, 2, 0), R4=(4, 2, 0),             # rectángulo con x compartidas con P5/P6
                      L1=(7, 1, 0), L2=(9, 1, 0), L3=(9, 2, 0), L4=(8, 2, 0), L5=(8, 3, 0), L6=(7, 3, 0),  # hueco cóncavo
                      G1=(1, 4, 0), G2=(2, 3.5, 0), G3=(3, 4, 0), G4=(2.5, 5, 0), G5=(1.5, 5, 0))         # pentágono (x=2 compartida)
        huecos = [("TRI", ["T1", "T2", "T3"]), ("REC", ["R1", "R2", "R3", "R4"]), ("ELE", ["L1", "L2", "L3", "L4", "L5", "L6"]),
                  ("PEN", ["G1", "G2", "G3", "G4", "G5"])]
        for orient, f in ORIENTACIONES.items():
            with self.subTest(orient):
                vx = plano_xyz(f, puntos)
                r = self.comprobar(geometria(vx, ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8"], huecos))
                self.assertEqual(len(r["huecos"]), 4)
                calculados = [n for n in r["nodos"] if n["traza"]["tipo"] == "sobre_arista"]
                self.assertTrue(calculados)

    def test_vertices_colineales_y_otra_superficie_no_vinculada(self):
        puntos = dict(VA=(0, 0, 0), VM=(2, 0, 0), VB=(4, 0, 0), VC=(4, 3, 0), VN=(4, 1.5, 0), VD=(0, 3, 0),
                      H1=(1, 1, 0), H2=(2, 1, 0), H3=(2, 2, 0), H4=(1, 2, 0), O1=(5, 0, 0), O2=(6, 0, 0), O3=(6, 1, 0))
        vx = plano_xyz(ORIENTACIONES["horizontal"], puntos)
        geo = geometria(vx, ["VA", "VM", "VB", "VN", "VC", "VD"], [("A1", ["H1", "H2", "H3", "H4"])], extra_superficies=[("S2", ["O1", "O2", "O3"])])
        r = self.comprobar(geo)
        self.assertTrue(all(not n["id"].startswith("O") for n in r["nodos"]))
        self.assertIn("pendiente", r["compatibilidad_interhost"])
        r2 = self.comprobar(geo, "S2")
        self.assertEqual((r2["huecos"], len(r2["celdas"])), ([], 1))

    def test_traslacion_grande_representable_y_rechazo_inestable(self):
        base = dict(RECT, H1=(1, 1, 0), H2=(2, 1, 0), H3=(2, 2, 0), H4=(1, 2, 0))
        for desplazamiento in (1e5, 1e6):
            with self.subTest(desplazamiento):
                vx = {k: (x + desplazamiento, y - desplazamiento, z + 50) for k, (x, y, z) in base.items()}
                r = self.comprobar(geometria(vx, ["VA", "VB", "VC", "VD"], [("A1", ["H1", "H2", "H3", "H4"])]))
                self.assertAlmostEqual(r["cobertura"]["area_celdas_m2"], 11, delta=1e-6)
        vx = {k: (x * 1e-3 + 1e12, y * 1e-3, z) for k, (x, y, z) in base.items()}
        with self.assertRaises(ps.ErrorParticion):
            ps.particionar_superficie(geometria(vx, ["VA", "VB", "VC", "VD"], [("A1", ["H1", "H2", "H3", "H4"])]), "S1")

    def test_cambio_de_fuente_y_entradas_invalidas(self):
        base = dict(RECT, H1=(1, 1, 0), H2=(2, 1, 0), H3=(2, 2, 0), H4=(1, 2, 0))
        geo = geometria(base, ["VA", "VB", "VC", "VD"], [("A1", ["H1", "H2", "H3", "H4"])])
        r = ps.particionar_superficie(geo, "S1")
        movida = copy.deepcopy(geo)
        movida["vertices"][4]["x"] = 1.25
        procedencia = copy.deepcopy(geo)
        procedencia["aberturas"][0]["procedencia"]["descripcion"] = "Otra fuente sintética"
        for variante in (movida, procedencia):
            r2 = ps.particionar_superficie(variante, "S1")
            self.assertNotEqual(r2["origen"]["sha256_geometria_canonica"], r["origen"]["sha256_geometria_canonica"])
            self.assertNotEqual(r2["origen"]["huella_contenido"], r["origen"]["huella_contenido"])
            self.assertNotEqual(r2["huella_particion"], r["huella_particion"])
        v02 = copy.deepcopy(geo)
        v02["version_contrato"] = "0.2.0"
        exterior = copy.deepcopy(geo)
        exterior["vertices"][4]["x"] = -1.0
        cruzado = geometria(dict(base, H2=(5, 1, 0)), ["VA", "VB", "VC", "VD"], [("A1", ["H1", "H2", "H3", "H4"])])
        no_plano = geometria(dict(base, H3=(2, 2, 0.5)), ["VA", "VB", "VC", "VD"], [("A1", ["H1", "H2", "H3", "H4"])])
        for nombre, (entrada, sid) in {"versión 0.2": (v02, "S1"), "superficie inexistente": (geo, "S9"), "id no texto": (geo, 1),
                                        "hueco exterior": (exterior, "S1"), "hueco cruzando": (cruzado, "S1"),
                                        "hueco no coplanar": (no_plano, "S1"), "no objeto": ([], "S1"), "nulo": (None, "S1")}.items():
            with self.subTest(nombre), self.assertRaises(ps.ErrorParticion):
                ps.particionar_superficie(entrada, sid)

    def test_contrato_y_trazas(self):
        vx = plano_xyz(ORIENTACIONES["inclinado"], dict(RECT, H1=(1, 1, 0), H2=(2, 1, 0), H3=(2, 2, 0), H4=(1, 2, 0)))
        r = self.comprobar(geometria(vx, ["VA", "VB", "VC", "VD"], [("A1", ["H1", "H2", "H3", "H4"])]))
        self.assertEqual(set(r), {"contrato", "version_contrato", "ejecutable", "aprueba_ingenieria", "aviso", "origen", "superficie",
                                  "huecos", "proyeccion", "nodos", "celdas", "cadenas_contorno", "cobertura", "comprobaciones",
                                  "compatibilidad_interhost", "pendientes", "huella_particion"})
        self.assertEqual(r["origen"]["version_geometria"], "0.3.0")
        self.assertEqual(len(r["origen"]["sha256_geometria_canonica"]), 64)
        self.assertTrue(all(c_["pieza_de"] == "S1" for c_ in r["celdas"]))
        self.assertTrue(all(c_["id"].startswith("S1#c") for c_ in r["celdas"]))
        datos = {k: v for k, v in r.items() if k != "huella_particion"}
        import hashlib
        self.assertEqual(r["huella_particion"], hashlib.sha256(json.dumps(datos, sort_keys=True, ensure_ascii=False,
                                                                           separators=(",", ":")).encode()).hexdigest())
        self.assertTrue(r["pendientes"])


class SensibilidadTests(Verificador):
    """Los verificadores detectan salidas defectuosas; el módulo rechaza una construcción no conforme."""

    def setUp(self):
        base = dict(RECT, H1=(1, 1, 0), H2=(2, 1, 0), H3=(2, 2, 0), H4=(1, 2, 0))
        self.geo = geometria(plano_xyz(ORIENTACIONES["inclinado"], base), ["VA", "VB", "VC", "VD"], [("A1", ["H1", "H2", "H3", "H4"])])

    def test_omision_de_nodos_laterales_rechazada_por_el_modulo(self):
        original = ps._nodos_laterales
        ps._nodos_laterales = lambda *a: ([], [])  # el fallo clásico: trapecio que salta el inicio del hueco
        try:
            with self.assertRaises(ps.ErrorParticion) as ctx:
                ps.particionar_superficie(self.geo, "S1")
        finally:
            ps._nodos_laterales = original
        self.assertIn("no verificable", str(ctx.exception))

    def test_verificador_independiente_detecta_salidas_defectuosas(self):
        bueno = ps.particionar_superficie(self.geo, "S1")
        def colgante(r):
            celda = next(c_ for c_ in r["celdas"] if "H1" in c_["nodos"] and len(c_["nodos"]) > 4)
            celda["nodos"] = [n for n in celda["nodos"] if n not in ("H1", "H4")]
        def invertida(r):
            r["celdas"][0]["nodos"].reverse()
        def sin_celda(r):
            r["celdas"].pop()
        def nodo_movido(r):
            n = next(n for n in r["nodos"] if n["traza"]["tipo"] == "sobre_arista")
            n["xyz_m"] = [x + 0.01 for x in n["xyz_m"]]
        for nombre, defecto in {"nodo colgante": colgante, "orientación invertida": invertida, "celda omitida": sin_celda,
                                "nodo fuera de su arista": nodo_movido}.items():
            with self.subTest(nombre):
                malo = copy.deepcopy(bueno)
                defecto(malo)
                original = ps.particionar_superficie
                ps.particionar_superficie = lambda *a, malo=malo: copy.deepcopy(malo)
                try:
                    with self.assertRaises(AssertionError):
                        self.comprobar(self.geo)
                finally:
                    ps.particionar_superficie = original


if __name__ == "__main__":
    unittest.main()
