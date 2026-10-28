"""Etapa 03 (ruta 201): edificio de referencia SINTÉTICO con todos los componentes por el recorrido normal.

Cuatro niveles; losas aligeradas nervadas (niveles 1–3) y maciza (techo); placas (muros shell) entre niveles con
conexiones declaradas a cada losa; columnas y vigas; escalera (descanso horizontal + tramo inclinado) conectada a la
losa del nivel 1; cisterna (presión hidrostática en la placa inferior, corte Z declarado). Gestión real en disco →
configuración 0.5 → plan 0.5 validado → relectura independiente con dobles. Datos sintéticos: no es la referencia real
ni ingeniería; el piloto con planos reales es la etapa 04.
"""
import copy
import unittest

from draft2model import gestion_geometria as g
from draft2model import malla_preparacion as mp
from draft2model import modelo_estructural as m
from draft2model import operaciones_etabs as o
from draft2model import verificacion_modelo_guardado as v
from tests import test_gestion_geometria as disco
from tests import test_integracion_malla as tim
from tests import test_liquidos_ruta201 as tlr
from tests import test_modelo_superficies as datos
from tests import test_relectura_liquidos_ruta201 as trl
from tests import test_verificacion_modelo_guardado as tvm

F = tim.F
COTAS = [0.0, 2.6, 5.2, 7.8, 10.4]
NERVADA = {"alto_total_m": 0.25, "capa_m": 0.05, "ancho_nervio_superior_m": 0.12, "ancho_nervio_inferior_m": 0.1,
           "separacion_m": 0.4, "direccion_nervios": 1, "angulo_ejes_locales_grados": 0.0}


def edificio():
    v, hosts, conexiones, frames, cargas = {}, [], [], [], []
    for k in range(1, 5):
        z = COTAS[k]
        v.update({f"S{k}A": (0, 0, z), f"S{k}B": (4, 0, z), f"S{k}C": (4, 3, z), f"S{k}D": (0, 3, z)})
        hosts.append((f"LOSA{k}", [f"S{k}A", f"S{k}B", f"S{k}C", f"S{k}D"], "ALIG" if k < 4 else "LOSA20"))
        # Placa en x=0 entre el nivel k-1 y k (la inferior apoya en la base).
        abajo = ("B0A", "B0D") if k == 1 else (f"S{k-1}A", f"S{k-1}D")
        if k == 1:
            v.update({"B0A": (0, 0, 0), "B0D": (0, 3, 0)})
        hosts.append((f"PLACA{k}", [abajo[0], abajo[1], f"S{k}D", f"S{k}A"], "MURO"))
        conexiones.append((f"CS{k}", (f"LOSA{k}", f"S{k}D", f"S{k}A"), (f"PLACA{k}", f"S{k}D", f"S{k}A")))
        if k > 1:
            conexiones.append((f"CI{k}", (f"LOSA{k-1}", f"S{k-1}D", f"S{k-1}A"), (f"PLACA{k}", abajo[0], abajo[1])))
        # Columnas en x=4 y vigas en y=0 (sobre el borde de cada losa).
        for esquina, (x, y) in (("B", (4, 0)), ("C", (4, 3))):
            ini = f"G{esquina}" if k == 1 else f"S{k-1}{esquina}"
            if k == 1:
                v[f"G{esquina}"] = (x, y, 0)
            frames.append((f"COL{esquina}{k}", ini, f"S{k}{esquina}", "columna"))
        frames.append((f"VIGA{k}", f"S{k}A", f"S{k}B", "viga"))
        cargas.append((f"Q{k}", "superficie", f"LOSA{k}", [0, 0, -2]))
    # Escalera: descanso al nivel 1 adosado al borde x=4 de LOSA1 y tramo inclinado hasta el suelo.
    v.update({"DESC2": (5.5, 0, 2.6), "DESC3": (5.5, 1.2, 2.6), "DESC4": (4, 1.2, 2.6),
              "TR1": (8, 0, 0), "TR2": (8, 1.2, 0)})
    hosts.append(("DESCANSO", ["S1B", "DESC2", "DESC3", "DESC4"], "LOSA20"))
    hosts.append(("TRAMO", ["DESC2", "TR1", "TR2", "DESC3"], "LOSA20"))
    conexiones.append(("CE1", ("LOSA1", "S1B", "S1C"), ("DESCANSO", "DESC4", "S1B")))
    conexiones.append(("CE2", ("DESCANSO", "DESC2", "DESC3"), ("TRAMO", "DESC3", "DESC2")))
    cargas.append(("QESC", "superficie", "TRAMO", [0, 0, -3]))
    cargas.append(("WV1", "frame", "VIGA1", [0, 0, -1]))
    return {"vertices": v, "hosts": hosts, "huecos": [], "conexiones": conexiones, "frames": frames,
            "apoyos": ["B0A", "B0D", "GB", "GC", "TR1", "TR2"], "diafragma_z": None, "cargas": cargas}


class CasoReferencia(tlr.CasoLiquidos):
    def montar_referencia(self):
        self.esc = esc = edificio()
        geo = datos.geometria_superficies(vertices=esc["vertices"], superficies=[(h, vs, "componente sintético") for h, vs, _ in esc["hosts"]],
                                          aprobar=False)
        geo["niveles"] = [{"id": f"N{i}", "nombre": f"Nivel {i} sintético", "cota": z} for i, z in enumerate(COTAS)]
        geo.update(version_contrato="0.3.0", aberturas=[])
        imp = g.importar_geometria(self.raiz, disco.CASO, self.f.escribir(geo, "geo_referencia.json"))
        self.version = self.f.aprobar(imp.identificador, imp.comprobacion.huella_contenido)
        self.geo = g.consultar_version(self.raiz, disco.CASO, self.version.identificador).geometria
        data = self.configuracion(esc)
        data["secciones"].append({"id": "ALIG", "tipo": "shell_losa_nervada_v1", "material": "MAT1", "dimensiones": dict(NERVADA), "fuente": F})
        data["secciones"].append({"id": "LOSA20", "tipo": "shell_losa_homogenea", "material": "MAT1", "dimensiones": {"espesor_m": 0.2}, "fuente": F})
        data["secciones"] = list({s["id"]: s for s in data["secciones"]}.values())
        coords = esc["vertices"]
        data["diafragmas"] = [{"id": f"DIA{k}", "tipo": "rigido", "puntos": sorted(p for p, xyz in coords.items() if xyz[2] == COTAS[k] and p.startswith(("S", "DESC"))),
                               "fuente": F} for k in range(1, 5)]
        en_dia = {p for d in data["diafragmas"] for p in d["puntos"]}
        data["sin_diafragma"] = [{"punto": p, "motivo": "Fuera de los pisos sintéticos", "fuente": F} for p in coords if p not in en_dia]
        # Cisterna: presión en la placa inferior hasta Z=1.2 (corte declarado), patrón dedicado.
        d, f = tlr.declaracion("CISTERNA", 1.2, [("PLACA1", 1)])
        data["version_contrato"] = m.VERSION_LIQUIDOS
        data["cortes_nivel"] = [{"z_m": 1.2, "fuente": F, "motivo": "Nivel libre de la cisterna (sintético)."}]
        data["patrones"].append({"id": "HIDRO", "tipo": "otro", "multiplicador_peso_propio": 0, "fuente": F})
        data["liquidos"] = {"aplicabilidad": "presente", "fuente": F, "motivo": "Cisterna sintética declarada.",
                            "declaraciones": [{"declaracion": d, "fuentes": f, "patron": "HIDRO"}]}
        return data

    def completar(self, data, prep=None):
        """Política explícita declarada por la prueba: base empotrada; nodos en cotas de piso al diafragma del piso."""
        data = copy.deepcopy(data)
        prep = prep or mp.preparar_malla(self.geo, data)
        xyz = {n["csi"]: n["xyz_m"] for n in prep["nodos"]}
        data["nodos_derivados"] = []
        for n in prep["nodos_derivados"]:
            z = xyz[n][2]
            dia = f"DIA{COTAS.index(z)}" if z in COTAS[1:] else None
            data["nodos_derivados"].append({"nodo": n, "xyz_m": xyz[n], "restricciones": [z == 0.0] * 6, "diafragma": dia,
                                            "motivo_sin_diafragma": None if dia else "Nodo fuera de un piso (declarado).", "fuente": F})
        data["subdivision_frames"] = [{"frame": r["frame"], "nodos": r["nodos"], "fuente": F} for r in prep["frames_subdivision_requerida"]]
        return data


class ReferenciaSinteticaTests(CasoReferencia):
    def test_edificio_completo_por_el_recorrido_normal(self):
        config = self.aprobar_en_disco(self.montar_referencia())
        r = m.comprobar_configuracion(self.raiz, config)
        self.assertTrue(r.apto_para_adaptador, r.a_dict())
        plan = self.plan(config)
        self.assertEqual(o.validar_plan_por_version(plan), [])
        ops = plan["operaciones"]
        metodos = [x["metodo"] for x in ops]
        hosts = plan["malla"]["hosts"]
        # Todos los componentes presentes: 4 losas, 4 placas, descanso y tramo de escalera; 8 columnas; 4 vigas.
        self.assertEqual(set(hosts), {f"LOSA{k}" for k in range(1, 5)} | {f"PLACA{k}" for k in range(1, 5)} | {"DESCANSO", "TRAMO"})
        frames = {a["UserName"] for x in ops if x["metodo"] == "cFrameObj.AddByPoint" for a in [{y["nombre"]: y["valor"] for y in x["argumentos"]}]}
        self.assertTrue(all(any(f == c or f.startswith(c + "_S") for f in frames) for c in [f"COL{e}{k}" for e in "BC" for k in range(1, 5)] + [f"VIGA{k}" for k in range(1, 5)]))
        pisos = next(x for x in ops if x["metodo"] == "cStory.SetStories_2")
        self.assertEqual({y["nombre"]: y["valor"] for y in pisos["argumentos"]}["NumberStories"], 4)
        # Aligerada conservada (no se sustituye por maciza): capa, tipo nervado y ejes por triángulo.
        self.assertIn("cPropArea.SetSlabRibbed", metodos)
        self.assertTrue(any(x["metodo"] == "cAreaObj.SetLocalAxes" for x in ops))
        # Escalera inclinada conectada: nodos compartidos con el descanso y el descanso con LOSA1.
        conexiones = {c["id"]: c["nodos_compartidos"] for c in plan["malla"]["conexiones"]}
        self.assertTrue(conexiones["CE1"] and conexiones["CE2"])
        # Cisterna: presión en la placa inferior con corte en 1.2 y conservación del contorno neto.
        liq = plan["liquidos"]
        self.assertEqual([h["superficie"] for h in liq["hosts"]], ["PLACA1"])
        self.assertLessEqual(liq["hosts"][0]["error_relativo_max"], 1e-9)
        self.assertEqual(plan["malla"]["cortes_nivel"]["niveles_z_m"], [1.2])
        # Diafragmas por piso y apoyos en la base.
        self.assertEqual({d for x in ops if x["metodo"] == "cDiaphragm.SetDiaphragm" for d in [x["argumentos"][0]["valor"]]}, {f"DIA{k}" for k in range(1, 5)})
        # Relectura independiente con dobles (representaciones ETABS observadas) verificada.
        exp = v.expectativa_desde_plan(plan)
        self.assertEqual([x for x in exp["inventario"] if x["cobertura"] == "sin_lector"], [])
        res = v.comparar(exp, tvm.lecturas(trl.modelo_etabs(exp)), tvm.CRITERIOS)
        self.assertEqual(res["estado"], "verificado", res["discrepancias"][:5] + res["incompletos"][:5])
        self.assertEqual((res["cobertura"]["malla"], res["cobertura"]["cargas_liquidos"]), ("completa", "completa"))


if __name__ == "__main__":
    unittest.main()
