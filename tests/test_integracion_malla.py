"""Integración de la malla 0.4 en el recorrido normal, con gestión REAL en disco y sin ETABS.

Geometría 0.3 importada y aprobada → configuración 0.4 importada en borrador (faltantes calculados de política)
→ preparación expuesta → revisión y aprobación → plan 0.4 → ejecutor verificado con el script PowerShell REAL en
modo doble contra un ensamblado ETABSv1 falso con estado → registro del modelo construido.

DOBLES: el ensamblado .NET falso y su estado (no prueban ETABS real; Codex hace el ensayo nativo).
"""
import base64
import copy
import hashlib
import json
import math
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from draft2model import adaptador_etabs as ad
from draft2model import ejecutor_etabs as ej
from draft2model import gestion_configuracion as gc
from draft2model import gestion_geometria as g
from draft2model import malla_preparacion as mp
from draft2model import modelo_estructural as m
from draft2model import operaciones_etabs as o
from draft2model import revision_modelo as rm
from draft2model import compatibilidad_particiones as cp
from draft2model.ejecucion_modelo import EjecutorVerificado
from draft2model.validacion_geometria import validar_geometria
from tests import test_ejecutor_etabs as te
from tests import test_gestion_geometria as disco
from tests import test_modelo_superficies as datos
from tests.test_operaciones_superficies import CUERPOS, ESTADO_CS

F = datos.F
POWERSHELL = ad.POWERSHELL_51.is_file() and os.name == "nt"
G = 9.80665
REVISOR = dict(revisor="Revisor SINTÉTICO de software", fecha="2026-10-20", motivo="Política explícita de nodos derivados.")


def _rect(prefijo, x0, y0, x1, y1, f):
    return {f"{prefijo}{i + 1}": f(x, y) for i, (x, y) in enumerate(((x0, y0), (x1, y0), (x1, y1), (x0, y1)))}


def escenario(nombre):
    """Vértices, hosts (id, vértices, sección), huecos (id, host, vértices), conexiones, frames y cargas."""
    if nombre == "horizontal":
        piso = lambda x, y: (x, y, 2.6)
        v = {**_rect("V", 0, 0, 6, 4, piso), **_rect("HA", 1, 1, 2, 2, piso), **_rect("HB", 3.5, 2, 4.5, 3, piso)}
        return {"vertices": v, "hosts": [("S1", ["V1", "V2", "V3", "V4"], "LOSA20")],
                "huecos": [("HUECO_A", "S1", ["HA1", "HA2", "HA3", "HA4"]), ("HUECO_B", "S1", ["HB1", "HB2", "HB3", "HB4"])],
                "conexiones": [], "frames": [], "apoyos": ["V1", "V2"], "diafragma_z": 2.6,
                "cargas": [("Q1", "superficie", "S1", [0.3, 0, -2])]}
    if nombre == "vertical":
        muro = lambda y, z: (0, y, z)
        v = {**_rect("W", 0, 0, 5, 2.6, muro), **_rect("G", 1.5, 0.8, 2.5, 2.0, muro)}
        return {"vertices": v, "hosts": [("S1", ["W1", "W2", "W3", "W4"], "MURO")],
                "huecos": [("PUERTA", "S1", ["G1", "G2", "G3", "G4"])], "conexiones": [], "frames": [],
                "apoyos": ["W1", "W2"], "diafragma_z": None, "cargas": [("Q1", "superficie", "S1", [-1.5, 0, 0])]}
    if nombre == "vertical_corte":
        return {**escenario("vertical"), "cortes": [1.5]}
    if nombre == "conectados_corte":
        return {**escenario("conectados"), "cortes": [1.2]}
    if nombre == "inclinado":
        rampa = lambda x, y: (x, y, round(0.3 * x, 12))
        v = {**_rect("V", 0, 0, 4, 3, rampa), **_rect("H", 1, 1, 2, 2, rampa)}
        return {"vertices": v, "hosts": [("S1", ["V1", "V2", "V3", "V4"], "LOSA20")],
                "huecos": [("HUECO", "S1", ["H1", "H2", "H3", "H4"])], "conexiones": [], "frames": [],
                "apoyos": ["V1", "V4"], "diafragma_z": None, "cargas": [("Q1", "superficie", "S1", [0, 0, -2])]}
    if nombre == "conectados":
        piso = lambda x, y: (x, y, 2.6)
        muro = lambda y, z: (0, y, z)
        v = {**_rect("V", 0, 0, 4, 3, piso), **_rect("H", 1.5, 1, 2.5, 2, piso), "W1": (0, 0, 0), "W2": (0, 3, 0),
             **_rect("G", 1, 0.8, 2, 1.8, muro)}
        return {"vertices": v, "hosts": [("S1", ["V1", "V2", "V3", "V4"], "LOSA20"), ("S2", ["W1", "W2", "V4", "V1"], "MURO")],
                "huecos": [("HP", "S1", ["H1", "H2", "H3", "H4"]), ("HM", "S2", ["G1", "G2", "G3", "G4"])],
                "conexiones": [("C1", ("S1", "V4", "V1"), ("S2", "V4", "V1"))],
                "frames": [("VIGA1", "V1", "V4", "viga")], "apoyos": ["W1", "W2"], "diafragma_z": 2.6,
                "cargas": [("Q1", "superficie", "S1", [0, 0, -2]), ("WV", "frame", "VIGA1", [0, 0, -3])]}
    raise KeyError(nombre)


def documento_conexiones(geometria, esc):
    vg = validar_geometria(copy.deepcopy(geometria))
    doc = {"contrato": cp.CONTRATO_CONEXIONES if hasattr(cp, "CONTRATO_CONEXIONES") else "draft2model.conexiones_borde",
           "version_contrato": "0.1.0", "id": "CX1",
           "geometria": {"sha256_geometria_canonica": cp._sha(geometria), "huella_contenido": vg.huella_contenido},
           "conexiones": [{"id": cid, "a": {"superficie": a[0], "desde": a[1], "hasta": a[2]},
                           "b": {"superficie": b[0], "desde": b[1], "hasta": b[2]}, "fuente": "FX1"} for cid, a, b in esc["conexiones"]],
           "fuentes": [{"id": "FX1", "descripcion": "Declaración sintética de bordes conectados", "referencia": "Solo pruebas",
                        "sha256": hashlib.sha256(b"conexiones sinteticas").hexdigest()}],
           "declaracion": {"declarado_por": "Revisor sintético", "fecha": "2026-10-20", "identidad": "declarada_no_verificada",
                           "alcance": "Bordes conectados para pruebas de software."}}
    doc["declaracion"]["huella_conexiones"] = cp.huella_conexiones(doc)
    return doc


def politica_explicita(nodo, xyz, esc):
    """Política declarada por la prueba (no inferida por el código): base empotrada, piso en diafragma."""
    base = xyz[2] == 0
    if esc["diafragma_z"] is not None and xyz[2] == esc["diafragma_z"]:
        return [False] * 6, "DIA1", None
    return [base] * 6, None, "Nodo de malla fuera del piso: sin diafragma (declarado)."


class CasoMalla(unittest.TestCase):
    def setUp(self):
        self.f = disco.CasoGeometria(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.raiz = self.f.raiz
        self.destino = str(self.f.trabajo / "salida" / "modelo_malla.edb")

    def montar(self, nombre):
        self.esc = esc = escenario(nombre)
        geo = datos.geometria_superficies(vertices=esc["vertices"], superficies=[(h, vs, "host sintético") for h, vs, _ in esc["hosts"]],
                                          aprobar=False)
        geo.update(version_contrato="0.3.0", aberturas=[{"id": a, "superficie": s, "vertices": vs, "procedencia": copy.deepcopy(geo["procedencia"])}
                                                        for a, s, vs in esc["huecos"]])
        imp = g.importar_geometria(self.raiz, disco.CASO, self.f.escribir(geo, f"geo_{nombre}.json"))
        self.version = self.f.aprobar(imp.identificador, imp.comprobacion.huella_contenido)
        self.geo = g.consultar_version(self.raiz, disco.CASO, self.version.identificador).geometria
        self.borrador = self.configuracion(esc)
        return self.borrador

    def configuracion(self, esc):
        data = datos.configuracion_superficies()
        secciones = {h[2] for h in esc["hosts"]} | ({"FRAME"} if esc["frames"] else set())
        data["secciones"] = [s for s in data["secciones"] if s["id"] in secciones]
        if "MURO" in secciones:
            data["secciones"].append({"id": "MURO", "tipo": "shell_muro", "material": "MAT1", "dimensiones": {"espesor_m": 0.2}, "fuente": F})
        data.update(version_contrato=m.VERSION_MALLA, vertices_compartidos=[], asignaciones_muros=[])
        data["plantilla"]["sha256"] = hashlib.sha256(te.CONTENIDO_COPIA).hexdigest()
        data["puntos"] = [{"id": v, "vertice_geometria": v} for v in esc["vertices"]]
        data["frames"] = [{"id": i, "inicio": a, "fin": b, "tipo": t, "fuente": F} for i, a, b, t in esc["frames"]]
        data["asignaciones_frames"] = [{"objetivo": i, "seccion": "FRAME", "fuente": F} for i, *_ in esc["frames"]]
        data["asignaciones_superficies"] = [{"objetivo": h, "seccion": s, "fuente": F} for h, _, s in esc["hosts"]]
        unidad = {"superficie": "kN/m2", "frame": "kN/m", "punto": "kN"}
        data["cargas"] = [{"id": i, "patron": "L", "objetivo_tipo": t, "objetivo": obj, "componentes": comp, "unidad": unidad[t],
                           "sistema": "global", "fuente": F} for i, t, obj, comp in esc["cargas"]]
        data["apoyos"] = [{"punto": p, "restricciones": [True] * 6, "fuente": F} for p in esc["apoyos"]]
        z = esc["diafragma_z"]
        piso = [v for v, xyz in esc["vertices"].items() if z is not None and xyz[2] == z]
        data["diafragmas"] = [{"id": "DIA1", "tipo": "rigido", "puntos": piso, "fuente": F}] if piso else []
        data["sin_diafragma"] = [{"punto": v, "motivo": "Fuera del piso sintético", "fuente": F} for v in esc["vertices"] if v not in piso]
        data["masa"]["gravedad_m_s2"] = G
        data["geometria_origen"] = {"version_id": self.version.identificador, "sha256_geometria": self.version.comprobacion.sha256_geometria,
                                    "huella_contenido": self.version.comprobacion.huella_contenido}
        data["conexiones_borde"] = documento_conexiones(self.geo, esc)
        data["malla"] = {"estrategia": mp.ESTRATEGIA, "fuente": F}
        data["cortes_nivel"] = [{"z_m": z, "fuente": F, "motivo": "Nivel libre de líquido declarado (sintético)."} for z in esc.get("cortes", [])]
        data["nodos_derivados"], data["subdivision_frames"] = [], []
        data["revision"] = {"estado": "borrador", "aprobacion": None}
        return data

    def completar(self, data, prep=None):
        data = copy.deepcopy(data)
        prep = prep or mp.preparar_malla(self.geo, data)
        xyz = {n["csi"]: n["xyz_m"] for n in prep["nodos"]}
        data["nodos_derivados"] = []
        for n in prep["nodos_derivados"]:
            restr, dia, motivo = politica_explicita(n, xyz[n], self.esc)
            data["nodos_derivados"].append({"nodo": n, "xyz_m": xyz[n], "restricciones": restr, "diafragma": dia, "motivo_sin_diafragma": motivo, "fuente": F})
        data["subdivision_frames"] = [{"frame": r["frame"], "nodos": r["nodos"], "fuente": F} for r in prep["frames_subdivision_requerida"]]
        return data

    def aprobar_local(self, data):
        data = copy.deepcopy(data)
        data["revision"] = {"estado": "aprobado", "aprobacion": {"revisor_declarado": "Revisor SINTÉTICO", "fecha": "2026-10-20",
                            "huella_configuracion": m.huella_configuracion(data), "alcance": "Solo software; no ingeniería",
                            "identidad_revisor": "declarada_no_verificada"}}
        return data

    def registrar_aprobada(self, nombre):
        """Recorrido de gestión real: importar borrador, consultar malla, revisar con política y aprobar."""
        borrador = self.montar(nombre)
        imp = gc.importar(self.raiz, disco.CASO, self.f.escribir(borrador, f"cfg_{nombre}.json"))
        expuesta = gc.preparar_malla_version(self.raiz, disco.CASO, imp["id"])
        revisada = gc.revisar(self.raiz, disco.CASO, imp["id"], self.completar(borrador, expuesta["preparacion"]), **REVISOR)
        aprobada = gc.aprobar(self.raiz, disco.CASO, revisada["id"], huella_esperada=m.huella_configuracion(revisada["configuracion"]),
                              alcance="Transporte de malla sintética; no ingeniería.", **REVISOR)
        return imp, expuesta, aprobada["configuracion"]

    def opciones(self, data):
        tipos = {s["tipo"] for s in data["secciones"]}
        op = {"destino_guardado": self.destino, "gravedad_programa_m_s2": G}
        if "shell_muro" in tipos:
            op["tipo_shell_muro"] = "ShellThin"
        if tipos & {"shell_losa_homogenea", *o.TIPOS_ALIGERADOS}:
            op["tipo_shell_losa"] = "ShellThin"
        return op


class ConfiguracionYPlanMallaTests(CasoMalla):
    def test_orientaciones_varios_huecos_recorrido_de_gestion_real(self):
        for nombre in ("horizontal", "vertical", "inclinado", "conectados", "vertical_corte", "conectados_corte"):
            with self.subTest(nombre):
                imp, expuesta, aprobada = self.registrar_aprobada(nombre)
                # Borrador importable con faltantes calculados; nunca apto.
                self.assertFalse(imp["comprobacion"]["apto_para_adaptador"])
                rutas = {f["ruta"] for f in imp["comprobacion"]["faltantes"]}
                prep = expuesta["preparacion"]
                self.assertTrue(prep["nodos_derivados"], "la partición con huecos debe derivar nodos")
                self.assertEqual(rutas, {f"$.nodos_derivados.{n}" for n in prep["nodos_derivados"]}
                                 | {f"$.subdivision_frames.{r['frame']}" for r in prep["frames_subdivision_requerida"]})
                self.assertEqual(expuesta["faltantes"], imp["comprobacion"]["faltantes"])
                r = m.comprobar_configuracion(self.raiz, aprobada)
                self.assertTrue(r.apto_para_adaptador, r.a_dict())
                self.assertEqual(set(r.bloqueos), {m.BLOQUEO_GEOMETRIA_ABERTURAS})
                self.assertEqual(r.a_dict()["preparacion_malla"]["huella_preparacion"], prep["huella_preparacion"])
                plan = o.generar_plan_por_version(self.raiz, aprobada, **self.opciones(aprobada)).datos
                self.assertEqual(o.validar_plan_por_version(plan), [])
                self.assertEqual(plan["version_contrato"], "0.4.0")
                self.assertTrue(plan["ejecutable"]); self.assertFalse(plan["aprueba_ingenieria"])
                self.verificar_plan(plan, prep, aprobada)

    def verificar_plan(self, plan, prep, config):
        ops = plan["operaciones"]
        args = lambda op: {a["nombre"]: a["valor"] for a in op["argumentos"]}
        areas = [args(op) for op in ops if op["metodo"] == "cAreaObj.AddByPoint"]
        hosts = set(prep["hosts"])
        # Sin host completo ni Opening; un triángulo por celda triangulada, con contorno de 3 nodos de la malla.
        self.assertFalse(hosts & {a["UserName"] for a in areas})
        self.assertNotIn("cAreaObj.SetOpening", [op["metodo"] for op in ops])
        self.assertEqual(sorted(a["UserName"] for a in areas), sorted(t["csi"] for t in prep["triangulos"]))
        self.assertTrue(all(a["NumberPoints"] == 3 for a in areas))
        # Área neta exacta: ningún triángulo sobre huecos y la suma coincide con el área neta fuente.
        for h, info in plan["conservacion"]["hosts"].items():
            self.assertLessEqual(info["error_relativo_area"], 1e-12, h)
            self.assertAlmostEqual(info["area_neta_poligono_m2"], info["area_neta_fuente_m2"], places=12)
        xyz = {n["csi"]: n["xyz_m"] for n in prep["nodos"]}
        huecos = {a["id"]: a for a in self.geo["aberturas"]}
        vg = validar_geometria(copy.deepcopy(self.geo))
        for t in prep["triangulos"]:
            c = t["centroide_m"]
            for a in huecos.values():
                if a["superficie"] != t["host"]:
                    continue
                q = [xyz_v for xyz_v in ([vv["x"], vv["y"], vv["z"]] for vv in vg.geometria_m["vertices"] if vv["id"] in a["vertices"])]
                lo = [min(p[k] for p in q) for k in range(3)]; hi = [max(p[k] for p in q) for k in range(3)]
                self.assertFalse(all(lo[k] - 1e-12 <= c[k] <= hi[k] + 1e-12 for k in range(3)), f"{t['csi']} cubre {a['id']}")
        # Puntos: nodos de la malla con nombre único; derivados con coordenadas de la malla.
        creados = {args(op)["UserName"]: (args(op)["X"], args(op)["Y"], args(op)["Z"]) for op in ops if op["metodo"] == "cPointObj.AddCartesian"}
        self.assertEqual(len(creados), len(set(creados)))
        for n in prep["nodos_derivados"]:
            self.assertEqual(list(creados[n]), xyz[n])
        # Orientación: cada triángulo conserva la normal del host.
        for t in prep["triangulos"]:
            p = [xyz[n] for n in t["nodos"]]
            u = [p[1][k] - p[0][k] for k in range(3)]; w = [p[2][k] - p[0][k] for k in range(3)]
            cruz = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
            normal = vg.derivados_m["superficies"][t["host"]]["normal_unitaria"]
            self.assertGreater(sum(a * b for a, b in zip(cruz, normal)), 0)
        # Cargas de área: la misma intensidad en cada triángulo del host, nunca en huecos; fuerza y momento conservados.
        uniformes = [args(op) for op in ops if op["metodo"] == "cAreaObj.SetLoadUniform"]
        for carga in config["cargas"]:
            if carga["objetivo_tipo"] != "superficie":
                continue
            tri_host = sorted(plan["mapeo_ids"]["hosts_malla"][carga["objetivo"]])
            for i, valor in enumerate(carga["componentes"]):
                if valor:
                    destino = sorted(a["Name"]["ref"].split(":", 1)[1] for a in uniformes if a["Dir"] == o.DIRECCION_GLOBAL[i] and a["Value"] == valor)
                    self.assertEqual(destino, tri_host)
        for c in plan["conservacion"]["cargas"]:
            self.assertLessEqual(c["error_relativo_max"], 1e-9, c)
            self.assertNotEqual(c["fuerza_esperada_kN"], [0, 0, 0])

    def test_dos_hosts_conectados_un_nombre_por_nodo_y_frame_conforme(self):
        borrador = self.montar("conectados")
        prep = mp.preparar_malla(self.geo, borrador)
        compartidos = [n for c in prep["conexiones"] for n in c["nodos_compartidos"]]
        self.assertTrue(compartidos)
        # Nodos del borde compartido: un único nombre CSI usado por triángulos de ambos hosts.
        csi = {n["nodo_malla"]: n["csi"] for n in prep["nodos"] if n["tipo"] == "derivado"}
        por_nodo = {}
        for t in prep["triangulos"]:
            for n in t["nodos"]:
                por_nodo.setdefault(n, set()).add(t["host"])
        borde = [csi.get(n, n) for n in compartidos]
        interiores = [n for n in borde if n.startswith("MN_")]
        self.assertTrue(interiores, "el hueco debe insertar nodos en el borde compartido")
        for n in interiores:
            self.assertEqual(por_nodo[n], {"S1", "S2"})
        # Frame en el borde compartido: subdivisión conforme declarada en los mismos nodos, sección y origen.
        req = prep["frames_subdivision_requerida"]
        self.assertEqual([r["frame"] for r in req], ["VIGA1"])
        self.assertEqual(req[0]["nodos"][0], "V1"); self.assertEqual(req[0]["nodos"][-1], "V4")
        self.assertEqual(set(req[0]["nodos"][1:-1]), set(interiores))
        data = self.aprobar_local(self.completar(borrador, prep))
        r = m.validar_configuracion(data, self.geo)
        self.assertTrue(r.consistente, r.errores)
        exp, sup, _ = o._expandir_malla(data, prep, validar_geometria(copy.deepcopy(self.geo)))
        subs = [f for f in exp["frames"] if f["id"].startswith("VIGA1_S")]
        self.assertEqual([f["inicio"] for f in subs] + [subs[-1]["fin"]], req[0]["nodos"])
        self.assertTrue(all(a["seccion"] == "FRAME" for a in exp["asignaciones_frames"] if a["objetivo"].startswith("VIGA1_S")))
        self.assertNotIn("VIGA1", {f["id"] for f in exp["frames"]})
        partes = [c for c in exp["cargas"] if c["id"].startswith("WV@")]
        self.assertEqual(sorted(c["objetivo"] for c in partes), sorted(f["id"] for f in subs))
        self.assertTrue(all(c["componentes"] == [0, 0, -3] for c in partes))  # misma intensidad kN/m, sin duplicar
        # Sin declaración no hay unión: sin la conexión, los nodos del borde quedan separados (faltan políticas distintas).
        sin = copy.deepcopy(borrador); sin["conexiones_borde"] = documento_conexiones(self.geo, {**self.esc, "conexiones": []})
        prep_sin = mp.preparar_malla(self.geo, sin)
        self.assertEqual(prep_sin["conexiones"], [])
        self.assertNotEqual(prep_sin["huella_preparacion"], prep["huella_preparacion"])

    def test_politica_de_nodos_ausente_conflictiva_o_ajena(self):
        borrador = self.montar("conectados")
        prep = mp.preparar_malla(self.geo, borrador)
        completo = self.completar(borrador, prep)
        r = m.validar_configuracion(self.aprobar_local(completo), self.geo)
        self.assertTrue(r.consistente, r.errores); self.assertEqual(r.faltantes, [])
        n0 = completo["nodos_derivados"][0]["nodo"]
        casos = {
            "ausente": (lambda d: d["nodos_derivados"].pop(0), "faltante"),
            "sin subdivisión": (lambda d: d["subdivision_frames"].clear(), "faltante"),
            "diafragma y motivo": (lambda d: d["nodos_derivados"][0].update(diafragma="DIA1", motivo_sin_diafragma="x"), "error"),
            "ni diafragma ni motivo": (lambda d: d["nodos_derivados"][0].update(diafragma=None, motivo_sin_diafragma=None), "error"),
            "nodo ajeno": (lambda d: d["nodos_derivados"].append({**d["nodos_derivados"][0], "nodo": "MN_S9_1"}), "error"),
            "restricciones incompletas": (lambda d: d["nodos_derivados"][0].update(restricciones=[True] * 5), "error"),
            "fuente inexistente": (lambda d: d["nodos_derivados"][0].update(fuente="NADIE"), "error"),
            "subdivisión distinta": (lambda d: d["subdivision_frames"][0]["nodos"].reverse(), "error"),
            "subdivisión de frame sin nodos": (lambda d: d["subdivision_frames"].append({"frame": "VIGA2", "nodos": [], "fuente": F}), "error"),
            "diafragma fuera de cota": (lambda d: next(x for x in d["nodos_derivados"] if prep_xyz[x["nodo"]][2] != 2.6).update(diafragma="DIA1", motivo_sin_diafragma=None), "error"),
            "muros 0.1": (lambda d: d["asignaciones_muros"].append({"objetivo": "M1", "seccion": "MURO", "fuente": F}), "error"),
            "estrategia": (lambda d: d["malla"].update(estrategia="abanico"), "error"),
            "posición distinta": (lambda d: d["nodos_derivados"][0].update(xyz_m=[9.0, 9.0, 9.0]), "error"),
        }
        prep_xyz = {n["csi"]: n["xyz_m"] for n in prep["nodos"]}
        for nombre, (cambio, tipo) in casos.items():
            with self.subTest(nombre):
                d = copy.deepcopy(completo); cambio(d)
                r = m.validar_configuracion(self.aprobar_local(d), self.geo)
                self.assertFalse(r.apto_para_adaptador)
                if tipo == "faltante":
                    self.assertTrue(r.consistente, r.errores)
                    self.assertTrue(r.faltantes)
                else:
                    self.assertFalse(r.consistente, nombre)
        self.assertTrue(n0.startswith("MN_"))

    def test_aligerado_conserva_tipo_capa_y_ejes_por_triangulo(self):
        borrador = self.montar("horizontal")
        borrador["secciones"] = [s for s in borrador["secciones"] if s["id"] != "LOSA20"] + [{
            "id": "LOSA20", "tipo": "shell_losa_nervada_v1", "material": "MAT1", "fuente": F,
            "dimensiones": {"alto_total_m": 0.25, "capa_m": 0.05, "ancho_nervio_superior_m": 0.12, "ancho_nervio_inferior_m": 0.1,
                            "separacion_m": 0.5, "direccion_nervios": 1, "angulo_ejes_locales_grados": 30.0}}]
        data = self.aprobar_local(self.completar(borrador))
        r = m.validar_configuracion(data, self.geo)
        self.assertTrue(r.consistente, r.errores)
        prep = mp.preparar_malla(self.geo, data)
        vg = validar_geometria(copy.deepcopy(self.geo))
        plan_ops = self._ops_compiladas(data, prep, vg)
        args = lambda op: {a["nombre"]: a["valor"] for a in op["argumentos"]}
        slab = [args(op) for op in plan_ops if op["metodo"] == "cPropArea.SetSlab"]
        self.assertEqual(slab[0]["Thickness"], 0.05)  # GetSlab.Thickness es la CAPA (corrección 181), no el alto total
        self.assertEqual(slab[0]["SlabType"]["nombre"], "Ribbed")
        self.assertIn("cPropArea.SetSlabRibbed", [op["metodo"] for op in plan_ops])
        ejes = [args(op) for op in plan_ops if op["metodo"] == "cAreaObj.SetLocalAxes"]
        self.assertEqual(sorted(a["Name"]["ref"].split(":")[1] for a in ejes), sorted(t["csi"] for t in prep["triangulos"]))
        self.assertTrue(all(a["Ang"] == 30.0 for a in ejes))

    def _ops_compiladas(self, data, prep, vg):
        exp, sup, _ = o._expandir_malla(data, prep, vg)
        niveles = sorted(vg.geometria_m["niveles"], key=lambda n: n["cota"])
        resultado = m.validar_configuracion(data, self.geo)
        return o._compilar(exp, resultado, vg, niveles, self.opciones(data), sup).datos["operaciones"]

    def test_cambio_de_geometria_invalida_la_cadena(self):
        _, _, aprobada = self.registrar_aprobada("inclinado")
        plan = o.generar_plan_por_version(self.raiz, aprobada, **self.opciones(aprobada)).datos
        ruta = self.version.ruta / g.ARCHIVO_GEOMETRIA
        raw = ruta.read_bytes()
        cambiada = copy.deepcopy(self.geo); next(v for v in cambiada["vertices"] if v["id"] == "H2")["x"] += 0.01
        ruta.write_text(json.dumps(cambiada), encoding="utf-8")
        try:
            self.assertFalse(m.comprobar_configuracion(self.raiz, aprobada).apto_para_adaptador)
            with self.assertRaises(o.ErrorPlanRechazado):
                o.generar_plan_por_version(self.raiz, aprobada, **self.opciones(aprobada))
        finally:
            ruta.write_bytes(raw)
        # Conexiones o política alteradas tras aprobar: huella de configuración no vigente.
        alterada = copy.deepcopy(aprobada); alterada["nodos_derivados"][0]["restricciones"] = [True] * 6
        self.assertFalse(m.comprobar_configuracion(self.raiz, alterada).apto_para_adaptador)
        self.assertEqual(o.validar_plan_por_version(plan), [])

    def test_plan_alterado_o_de_desarrollo_rechazado(self):
        _, _, aprobada = self.registrar_aprobada("horizontal")
        plan = o.generar_plan_por_version(self.raiz, aprobada, **self.opciones(aprobada)).datos
        manipulaciones = {
            "host completo": lambda p: p["operaciones"].insert(0, copy.deepcopy(next(op for op in p["operaciones"] if op["metodo"] == "cAreaObj.AddByPoint"))),
            "triángulo omitido": lambda p: p["malla"]["triangulos"].pop(next(iter(p["malla"]["triangulos"]))),
            "conservación": lambda p: p["conservacion"]["cargas"][0].update(error_relativo_max=1e-3),
            "ejecutable falso": lambda p: p.update(ejecutable=False),
            "aprueba ingeniería": lambda p: p.update(aprueba_ingenieria=True),
        }
        for nombre, cambio in manipulaciones.items():
            with self.subTest(nombre):
                p = copy.deepcopy(plan); cambio(p); p["huella_plan"] = o.huella_plan(p)
                self.assertTrue(o.validar_plan_por_version(p))
        for version in ("0.2.0", "0.3.0"):
            self.assertTrue(o.validar_plan_por_version({**plan, "version_contrato": version}))
        with self.assertRaises(o.ErrorPlanRechazado):
            o.generar_plan_por_version(self.raiz, {**aprobada, "version_contrato": "0.3.0"}, **self.opciones(aprobada))

    def test_cortes_z_explicitos_conservan_ambos_lados_y_exigen_politica(self):
        for nombre, z in (("vertical_corte", 1.5), ("conectados_corte", 1.2)):
            with self.subTest(nombre):
                imp, expuesta, aprobada = self.registrar_aprobada(nombre)
                prep = expuesta["preparacion"]
                self.assertEqual(prep["cortes_nivel"]["niveles_z_m"], [z])
                self.assertTrue(prep["cortes_nivel"]["no_crea_pisos"])
                nodos_corte = prep["cortes_nivel"]["nodos_corte"]
                self.assertTrue(nodos_corte)
                xyz = {n["csi"]: n["xyz_m"] for n in prep["nodos"]}
                self.assertTrue(all(xyz[n][2] == z for n in nodos_corte))
                # Los nodos del corte necesitan política explícita: faltan en el borrador importado.
                faltantes = {f["ruta"] for f in imp["comprobacion"]["faltantes"]}
                self.assertTrue({f"$.nodos_derivados.{n}" for n in nodos_corte} <= faltantes)
                # Ningún triángulo atraviesa el nivel; ambos lados (incluida la pieza seca) se conservan.
                usos = {}
                arriba = abajo = 0.0
                for t in prep["triangulos"]:
                    zs = [xyz[n][2] for n in t["nodos"]]
                    self.assertFalse(min(zs) < z < max(zs), t["csi"])
                    for n in t["nodos"]:
                        usos[n] = usos.get(n, 0) + 1
                    if min(zs) >= z:
                        arriba += t["area_m2"]
                    else:
                        abajo += t["area_m2"]
                self.assertGreater(arriba, 0); self.assertGreater(abajo, 0)
                self.assertTrue(all(usos[n] >= 2 for n in nodos_corte))  # nodos compartidos por aristas, sin colgantes
                for h, info in prep["hosts"].items():
                    total = math.fsum(t["area_m2"] for t in prep["triangulos"] if t["host"] == h)
                    self.assertAlmostEqual(total, info["area_neta_m2"], places=10)
                plan = o.generar_plan_por_version(self.raiz, aprobada, **self.opciones(aprobada)).datos
                self.assertEqual(o.validar_plan_por_version(plan), [])
                self.assertEqual(plan["malla"]["cortes_nivel"]["niveles_z_m"], [z])
                self.assertNotIn("cStory.SetStories_2", [op["metodo"] for op in plan["operaciones"] if op["fase"] != "pisos"])
                pisos = next(op for op in plan["operaciones"] if op["metodo"] == "cStory.SetStories_2")
                self.assertNotIn(z, [a["valor"] for a in pisos["argumentos"] if a["nombre"] == "StoryHeights"][0])
        # Declaraciones inválidas del corte y cambio de nivel tras aprobar.
        borrador = self.montar("vertical_corte")
        for cambio in (lambda d: d["cortes_nivel"].append(dict(d["cortes_nivel"][0])),
                       lambda d: d["cortes_nivel"][0].update(fuente="NADIE"),
                       lambda d: d["cortes_nivel"][0].update(motivo=""),
                       lambda d: d["cortes_nivel"][0].update(z_m=float("inf"))):
            d = copy.deepcopy(borrador); cambio(d)
            self.assertFalse(m.validar_configuracion(d, self.geo).consistente)
        completo = self.aprobar_local(self.completar(borrador))
        movido = copy.deepcopy(completo); movido["cortes_nivel"][0]["z_m"] = 1.6
        r = m.validar_configuracion(self.aprobar_local(movido), self.geo)
        self.assertFalse(r.consistente, "las políticas de los nodos del corte anterior ya no corresponden")

    def test_contratos_previos_intactos(self):
        # 0.3 sigue en desarrollo (bloqueo propio, sin apto); 0.4 no altera la salida de 0.1 (sin claves nuevas).
        r01 = m.validar_configuracion(json.loads(datos.EJEMPLO_CONFIG.read_bytes()))
        self.assertNotIn("preparacion_malla", r01.a_dict()); self.assertNotIn("version_contrato", r01.a_dict())
        self.assertEqual(m._validador({"version_contrato": "0.3.0"}).bloqueo_configuracion, m.BLOQUEO_ABERTURAS)
        self.assertIsNone(m._validador({"version_contrato": "0.4.0"}).bloqueo_configuracion)
        self.assertEqual(o.validar_plan_por_version({"contrato": o.CONTRATO_PLAN, "version_contrato": "0.3.0"}),
                         ["Plan 0.3.0 de desarrollo: no ejecutable."])


ESTADO_MALLA = ESTADO_CS + r"""
public static class Malla {
  public static System.Collections.Generic.Dictionary<string, bool[]> Restr = new System.Collections.Generic.Dictionary<string, bool[]>();
  public static System.Collections.Generic.Dictionary<string, System.Collections.Generic.List<object[]>> Cargas = new System.Collections.Generic.Dictionary<string, System.Collections.Generic.List<object[]>>();
  public static System.Collections.Generic.Dictionary<string, string[]> Fr = new System.Collections.Generic.Dictionary<string, string[]>();
  public static object[] Masa = null;
}"""
CUERPOS_MALLA = dict(CUERPOS)
CUERPOS_MALLA.update({
    "cPropArea.SetWall": 'Estado.Mat[Name] = MatProp; Estado.Esp[Name] = Thickness; return Falso.Retorno("cPropArea.SetWall", 0);',
    "cPropArea.GetWall": "MatProp = Estado.Mat[Name]; Thickness = Estado.Esp[Name]; return 0;",
    "cPointObj.SetRestraint": 'Malla.Restr[Name] = (bool[])Value.Clone(); return Falso.Retorno("cPointObj.SetRestraint", 0);',
    "cPointObj.GetRestraint": 'Value = (bool[])Malla.Restr[Name].Clone(); if (Falso.Env("FALSO_RESTR_MAL") == "1") Value[0] = !Value[0]; return 0;',
    "cAreaObj.SetLoadUniform": 'if (!Malla.Cargas.ContainsKey(Name)) Malla.Cargas[Name] = new System.Collections.Generic.List<object[]>(); '
                               'Malla.Cargas[Name].Add(new object[] { LoadPat, CSys, Dir, Value }); return Falso.Retorno("cAreaObj.SetLoadUniform", 0);',
    "cAreaObj.GetLoadUniform": 'System.Collections.Generic.List<object[]> l = Malla.Cargas.ContainsKey(Name) ? Malla.Cargas[Name] : new System.Collections.Generic.List<object[]>(); '
                               'int n = l.Count; NumberItems = n; AreaName = new string[n]; LoadPat = new string[n]; CSys = new string[n]; Dir = new int[n]; Value = new double[n]; '
                               'for (int i = 0; i < n; i++) { AreaName[i] = Name; LoadPat[i] = (string)l[i][0]; CSys[i] = (string)l[i][1]; Dir[i] = (int)l[i][2]; '
                               'Value[i] = (double)l[i][3] * (Falso.Env("FALSO_CARGA_MAL") == "1" ? 2.0 : 1.0); } return 0;',
    "cPropMaterial.SetMassSource_1": 'Malla.Masa = new object[] { IncludeElements, IncludeAddedMass, IncludeLoads, NumberLoads, LoadPat.Clone(), sf.Clone() }; '
                                     'return Falso.Retorno("cPropMaterial.SetMassSource_1", 0);',
    "cPropMaterial.GetMassSource_1": 'IncludeElements = (bool)Malla.Masa[0]; IncludeAddedMass = (bool)Malla.Masa[1]; IncludeLoads = (bool)Malla.Masa[2]; '
                                     'NumberLoads = (int)Malla.Masa[3]; LoadPat = (string[])Malla.Masa[4]; sf = (double[])Malla.Masa[5]; return 0;',
    "cFrameObj.AddByPoint": 'Name = Falso.Nombre(UserName); Malla.Fr[Name] = new string[] { Point1, Point2 }; return Falso.Retorno("cFrameObj.AddByPoint", 0);',
    "cFrameObj.GetPoints": "Point1 = Malla.Fr[Name][0]; Point2 = Malla.Fr[Name][1]; return 0;",
})


@unittest.skipUnless(POWERSHELL, "requiere Windows PowerShell 5.1")
class EjecucionMallaDobleTests(CasoMalla):
    """Ejecutor verificado + script PowerShell REAL en modo doble + ETABSv1 falso con estado. No es ETABS."""

    @classmethod
    def setUpClass(cls):
        cls._dir = tempfile.TemporaryDirectory(dir=os.environ.get("TEMP"))
        carpeta = Path(cls._dir.name)
        cs, dll = carpeta / "ETABSv1_malla.cs", carpeta / "ETABSv1_malla.dll"
        cs.write_text(te.generar_cs(CUERPOS_MALLA, ESTADO_MALLA), encoding="utf-8")
        script = "Add-Type -TypeDefinition ([IO.File]::ReadAllText($env:D2M_CS)) -OutputAssembly $env:D2M_DLL -OutputType Library"
        proceso = subprocess.run([str(ad.POWERSHELL_51), "-NoProfile", "-NonInteractive", "-EncodedCommand",
                                  base64.b64encode(script.encode("utf-16-le")).decode()],
                                 env=dict(os.environ, D2M_CS=str(cs), D2M_DLL=str(dll)), capture_output=True, timeout=180)
        if proceso.returncode != 0 or not dll.is_file():
            cls._dir.cleanup()
            raise unittest.SkipTest("No se pudo compilar el ensamblado falso: " + proceso.stderr.decode("utf-8", "replace")[-800:])
        cls.dll = dll

    @classmethod
    def tearDownClass(cls):
        cls._dir.cleanup()

    def setUp(self):
        super().setUp()
        self.copia = self.f.trabajo / "copia" / "plantilla.edb"
        self.copia.parent.mkdir()
        self.copia.write_bytes(te.CONTENIDO_COPIA)
        Path(self.destino).parent.mkdir()
        self.corridas = self.f.trabajo / "corridas"
        self.corridas.mkdir()
        _, _, self.config = self.registrar_aprobada("conectados_corte")  # dos hosts, viga conforme y corte Z
        self.plan = o.generar_plan_por_version(self.raiz, self.config, **self.opciones(self.config)).datos

    def ejecutor(self, **entorno):
        self.log = self.f.trabajo / f"llamadas_{len(list(self.f.trabajo.glob('llamadas_*')))}.jsonl"
        variables = {"FALSO_MODELO": str(self.copia), "FALSO_LOG": str(self.log), **entorno}
        return EjecutorVerificado(ej.configuracion_doble_powershell(self.corridas, self.dll, timeout_s=300, entorno=variables))

    def llamadas(self):
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines() if l.strip()] if self.log.is_file() else []

    def test_recorrido_normal_guarda_y_registra(self):
        ejecutor = self.ejecutor()
        preparada = ejecutor.preparar(self.raiz, self.config, self.plan, copia=self.copia, modelo_esperado=self.copia)
        resultado = ejecutor.ejecutar(preparada)
        llamadas = self.llamadas()
        self.assertEqual([l["m"] for l in llamadas], [op["metodo"] for op in self.plan["operaciones"]])
        self.assertEqual(llamadas[-1]["m"], "cFile.Save")
        for metodo in ("cPointObj.GetRestraint", "cAreaObj.GetLoadUniform", "cPropMaterial.GetMassSource_1", "cFrameObj.GetPoints"):
            self.assertIn(metodo, [l["m"] for l in llamadas])
        self.assertTrue(Path(self.destino).is_file())  # archivo del doble, no un modelo ETABS
        self.assertEqual(resultado.operaciones_ejecutadas, len(self.plan["operaciones"]))
        registro = rm.registrar(self.raiz, disco.CASO, self.config, self.plan, preparada.carpeta)
        estado = rm.consultar(self.raiz, disco.CASO, registro.name)
        self.assertEqual(estado["estado"], "pendiente")
        self.assertEqual(estado["origen"]["huella_plan"], self.plan["huella_plan"])

    def test_discrepancias_de_relectura_y_fallos_parciales_impiden_guardar(self):
        casos = {"apoyo releído distinto": ({"FALSO_RESTR_MAL": "1"}, "cPointObj.GetRestraint"),
                 "carga releída distinta": ({"FALSO_CARGA_MAL": "1"}, "cAreaObj.GetLoadUniform"),
                 "coordenada releída distinta": ({"FALSO_DESVIO": "1"}, "cPointObj.GetCoordCartesian"),
                 "fallo en triángulo": ({"FALSO_FALLA": "cAreaObj.AddByPoint"}, "cAreaObj.AddByPoint"),
                 "nombre de triángulo cambiado": ({"FALSO_RENOMBRAR": next(iter(self.plan["malla"]["triangulos"]))}, "cAreaObj.AddByPoint")}
        for nombre, (entorno, metodo) in casos.items():
            with self.subTest(nombre):
                ejecutor = self.ejecutor(**entorno)
                preparada = ejecutor.preparar(self.raiz, self.config, self.plan, copia=self.copia, modelo_esperado=self.copia)
                try:
                    with self.assertRaises(ad.ErrorPuente) as ctx:
                        ejecutor.ejecutar(preparada)
                    if "releída" in nombre:
                        self.assertIn(metodo, str(ctx.exception))
                    self.assertTrue(ctx.exception.incierto)  # mutación iniciada: el motor queda marcado incierto
                    self.assertTrue(ejecutor.estado_incierto.is_file())
                finally:
                    if ejecutor.estado_incierto.exists():
                        ejecutor.estado_incierto.unlink()  # marca del doble; se retira para el siguiente subcaso
                llamadas = self.llamadas()
                self.assertEqual(llamadas[-1]["m"], metodo)
                self.assertNotIn("cFile.Save", [l["m"] for l in llamadas])
                self.assertFalse(Path(self.destino).exists())
                self.assertTrue((preparada.carpeta / "revision_integracion_fallida.json").is_file())
                with self.assertRaises((ValueError, OSError)):
                    rm.registrar(self.raiz, disco.CASO, self.config, self.plan, preparada.carpeta)

    def test_plan_no_regenerable_no_se_prepara(self):
        ejecutor = self.ejecutor()
        alterado = copy.deepcopy(self.plan)
        alterado["malla"]["origen"]["huella_triangulacion"] = "0" * 64
        alterado["huella_plan"] = o.huella_plan(alterado)
        with self.assertRaises(ad.ErrorEvidenciaEtabs):
            ejecutor.preparar(self.raiz, self.config, alterado, copia=self.copia, modelo_esperado=self.copia)


if __name__ == "__main__":
    unittest.main()
