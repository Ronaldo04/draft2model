"""Pruebas sintéticas puras de `draft2model.politicas_malla_automatica` (sin ETABS, red ni I/O de expediente).

Cubre:
- Nodos derivados de borde y huecos, superficies conectadas, cortes Z explícitos y barras subdivididas.
- Caso sintético numeroso (>= 60 nodos derivados) resuelto mediante reglas concisas sin enumeración manual.
- Reglas faltantes (pendientes explícitos, cero apoyos o diafragmas inventados, no asume z=0 ni herencia de extremos).
- Reglas contradictorias en restricciones, diafragmas, barras y fuentes (señala conflicto sin elegir la primera).
- Unidades/coordenadas inválidas, coplanaridad de diafragmas y contrato cerrado de reglas.
- Incompatibilidad de geometría/configuración origen y referencias/fuentes inexistentes.
- Preservación de identidad y bandera `datos_sinteticos`, degradación obligatoria a borrador (sin heredar aprobación),
  no maquillaje de otros faltantes (0.5.0 con líquidos pendientes) e inmutabilidad estricta de entradas.
"""
from __future__ import annotations

import copy
import hashlib
import json
import unittest
from uuid import uuid4

from draft2model import compatibilidad_particiones as cp
from draft2model import contratos
from draft2model import malla_preparacion as mp
from draft2model import modelo_estructural as m
from draft2model import politicas_malla_automatica as pma
from draft2model.validacion_geometria import validar_geometria
from tests import test_integracion_malla as tim
from tests import test_modelo_superficies as datos

F = datos.F
F2 = "F-SINTETICA-2"
G = 9.80665
SHA_PLANTILLA = hashlib.sha256(b"plantilla-sintetica-350").hexdigest()
SHA_GEO_FICTICIO = hashlib.sha256(b"bytes-geometria-sintetica-350").hexdigest()


def _canon_sha(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def montar_en_memoria(
    esc: dict,
    *,
    datos_sinteticos: bool = True,
    unidad_geometria: str = "m",
    version_config: str = m.VERSION_MALLA,
    fuente_extra: bool = False,
) -> tuple[dict, dict]:
    """Construye geometría 0.3.0 aprobada y configuración 0.4.0/0.5.0 en memoria (100% sintético, sin disco)."""
    escala = {"m": 1.0, "cm": 100.0, "mm": 1000.0}[unidad_geometria]
    geo = datos.geometria_superficies(
        vertices={
            vid: tuple(round(coord * escala, 9) for coord in xyz)
            for vid, xyz in esc["vertices"].items()
        },
        superficies=[(h, vs, "host sintético") for h, vs, _ in esc["hosts"]],
        aprobar=False,
    )
    geo["unidad_longitud"] = unidad_geometria
    for niv in geo["niveles"]:
        niv["cota"] = round(niv["cota"] * escala, 9)
    for nod in geo["nodos"]:
        nod["x"] = round(nod["x"] * escala, 9)
        nod["y"] = round(nod["y"] * escala, 9)
    if not datos_sinteticos:
        proc_no_sint = {
            "tipo": "plano",
            "descripcion": "Fixture de software para verificar preservación de bandera (no corresponde a proyecto real).",
            "expediente_id": "EXP-PRUEBA-000",
            "lamina": "L-00",
        }
        geo["procedencia"] = copy.deepcopy(proc_no_sint)
        for v in geo["vertices"]:
            v["procedencia"] = copy.deepcopy(proc_no_sint)
        for s in geo["superficies"]:
            s["procedencia"] = copy.deepcopy(proc_no_sint)
    geo.update(
        version_contrato="0.3.0",
        aberturas=[
            {
                "id": aid,
                "superficie": sid,
                "vertices": vs,
                "procedencia": copy.deepcopy(geo["procedencia"]),
            }
            for aid, sid, vs in esc["huecos"]
        ],
    )
    geo["revision"] = {
        "estado": "aprobado",
        "aprobacion": {
            "declarada_por": "Revisor sintético de software",
            "fecha": "2026-10-25",
            "huella_contenido": contratos.huella_contenido(geo),
            "alcance": "Solo pruebas sintéticas de políticas de malla; no ingeniería.",
            "observaciones": "Sin ETABS ni datos reales.",
        },
    }
    vg = validar_geometria(copy.deepcopy(geo))
    assert vg.consistente, vg.errores

    cfg = datos.configuracion_superficies()
    cfg["datos_sinteticos"] = datos_sinteticos
    if fuente_extra:
        cfg["fuentes"].append({
            "id": F2,
            "descripcion": "Segunda fuente sintética de prueba",
            "referencia": "Nota técnica sintética 2",
            "sha256": hashlib.sha256(b"fuente-sintetica-2").hexdigest(),
        })
    secciones = {h[2] for h in esc["hosts"]} | ({"FRAME"} if esc["frames"] else set())
    cfg["secciones"] = [s for s in cfg["secciones"] if s["id"] in secciones]
    if "MURO" in secciones:
        cfg["secciones"].append({
            "id": "MURO",
            "tipo": "shell_muro",
            "material": "MAT1",
            "dimensiones": {"espesor_m": 0.2},
            "fuente": F,
        })
    cfg.update(version_contrato=version_config, vertices_compartidos=[], asignaciones_muros=[])
    cfg["plantilla"]["sha256"] = SHA_PLANTILLA
    cfg["puntos"] = [{"id": v, "vertice_geometria": v} for v in esc["vertices"]]
    cfg["frames"] = [{"id": i, "inicio": a, "fin": b, "tipo": t, "fuente": F} for i, a, b, t in esc["frames"]]
    cfg["asignaciones_frames"] = [{"objetivo": i, "seccion": "FRAME", "fuente": F} for i, *_ in esc["frames"]]
    cfg["asignaciones_superficies"] = [{"objetivo": h, "seccion": s, "fuente": F} for h, _, s in esc["hosts"]]
    unidad_carga = {"superficie": "kN/m2", "frame": "kN/m", "punto": "kN"}
    cfg["cargas"] = [
        {
            "id": i,
            "patron": "L",
            "objetivo_tipo": t,
            "objetivo": obj,
            "componentes": comp,
            "unidad": unidad_carga[t],
            "sistema": "global",
            "fuente": F,
        }
        for i, t, obj, comp in esc["cargas"]
    ]
    cfg["apoyos"] = [{"punto": p, "restricciones": [True] * 6, "fuente": F} for p in esc["apoyos"]]
    z_dia = esc["diafragma_z"]
    piso = [v for v, xyz in esc["vertices"].items() if z_dia is not None and xyz[2] == z_dia]
    cfg["diafragmas"] = [{"id": "DIA1", "tipo": "rigido", "puntos": piso, "fuente": F}] if piso else []
    cfg["sin_diafragma"] = [
        {"punto": v, "motivo": "Fuera del piso sintético", "fuente": F}
        for v in esc["vertices"]
        if v not in piso
    ]
    cfg["masa"]["gravedad_m_s2"] = G
    cfg["geometria_origen"] = {
        "version_id": uuid4().hex,
        "sha256_geometria": SHA_GEO_FICTICIO,
        "huella_contenido": vg.huella_contenido,
    }
    cfg["conexiones_borde"] = tim.documento_conexiones(geo, esc)
    cfg["malla"] = {"estrategia": mp.ESTRATEGIA, "fuente": F}
    cfg["cortes_nivel"] = [
        {"z_m": zc, "fuente": F, "motivo": "Corte Z sintético explícito."}
        for zc in esc.get("cortes", [])
    ]
    cfg["nodos_derivados"] = []
    cfg["subdivision_frames"] = []
    cfg["revision"] = {"estado": "borrador", "aprobacion": None}
    if version_config == m.VERSION_LIQUIDOS:
        cfg["liquidos"] = {
            "aplicabilidad": "ausente_confirmado",
            "fuente": F,
            "motivo": "Escenario sintético seco confirmado.",
            "declaraciones": [],
        }
    return geo, cfg


def reglas_base(
    *,
    reglas_restricciones=None,
    resto_restricciones=None,
    reglas_diafragma=None,
    resto_diafragma=None,
    subdivision_frames=None,
) -> dict:
    doc = pma.plantilla_reglas_vacia()
    doc["reglas_restricciones"] = list(reglas_restricciones or [])
    doc["resto_restricciones"] = copy.deepcopy(resto_restricciones)
    doc["reglas_diafragma"] = list(reglas_diafragma or [])
    doc["resto_diafragma"] = copy.deepcopy(resto_diafragma)
    doc["subdivision_frames"] = copy.deepcopy(subdivision_frames)
    return doc


class PoliticasMallaAutomaticaTests(unittest.TestCase):
    def test_sin_reglas_expone_inventario_y_pendientes_sin_inventar_apoyos_ni_diafragmas(self):
        esc = tim.escenario("conectados_corte")
        geo, cfg = montar_en_memoria(esc)
        sha_geo, sha_cfg = _canon_sha(geo), _canon_sha(cfg)

        prep = mp.preparar_malla(geo, cfg)
        self.assertTrue(any(n.startswith("MN_") for n in prep["nodos_derivados"]))
        self.assertTrue(any(n.startswith("MC_") for n in prep["nodos_derivados"]))
        self.assertEqual([r["frame"] for r in prep["frames_subdivision_requerida"]], ["VIGA1"])

        for argumento_reglas in (None, pma.plantilla_reglas_vacia()):
            with self.subTest(reglas_declaradas=argumento_reglas is not None):
                vista = pma.previsualizar_politicas_malla(geo, cfg, argumento_reglas)
                self.assertEqual(vista["contrato"], pma.CONTRATO_PROPUESTA)
                self.assertFalse(vista["listo_para_aplicar"])
                self.assertFalse(vista["ejecutable"])
                self.assertFalse(vista["aprueba_ingenieria"])
                self.assertTrue(vista["datos_sinteticos"])
                self.assertEqual(vista["errores"], [])
                self.assertEqual(vista["conflictos"], [])
                # Ningún apoyo ni diafragma ni subdivisión inventados.
                self.assertEqual(vista["nodos_derivados_propuestos"], [])
                self.assertEqual(vista["subdivision_frames_propuesta"], [])
                self.assertEqual(
                    [x["nodo"] for x in vista["inventario_nodos_derivados"]],
                    prep["nodos_derivados"],
                )
                self.assertEqual(
                    [x["frame"] for x in vista["inventario_subdivision_frames"]],
                    ["VIGA1"],
                )
                # Dos pendientes por cada nodo derivado (restricciones + diafragma) + 1 por VIGA1.
                self.assertEqual(len(vista["pendientes"]), 2 * len(prep["nodos_derivados"]) + 1)

        with self.assertRaises(pma.ErrorPoliticaMalla) as ctx:
            pma.aplicar_politicas_malla(geo, cfg, None)
        self.assertIsNotNone(ctx.exception.propuesta)
        self.assertFalse(ctx.exception.propuesta["listo_para_aplicar"])

        with self.assertRaises(pma.ErrorPoliticaMalla) as ctx2:
            pma.aplicar_politicas_malla(geo, cfg, pma.plantilla_reglas_vacia())
        self.assertGreater(len(ctx2.exception.propuesta["pendientes"]), 0)

        self.assertEqual(_canon_sha(geo), sha_geo)
        self.assertEqual(_canon_sha(cfg), sha_cfg)

    def test_recorrido_completo_escenarios_borde_hueco_conectados_cortes_y_barra_subdividida(self):
        for nombre in ("horizontal", "vertical", "inclinado", "conectados", "vertical_corte", "conectados_corte"):
            with self.subTest(nombre):
                esc = tim.escenario(nombre)
                geo, cfg = montar_en_memoria(esc)
                sha_geo, sha_cfg = _canon_sha(geo), _canon_sha(cfg)

                rr = []
                if nombre in ("vertical", "vertical_corte", "conectados", "conectados_corte"):
                    rr.append({
                        "id": "APOYO_BORDE_BASE_MURO",
                        "selector": {"tipo": "borde_entre_puntos", "inicio": "W1", "fin": "W2"},
                        "restricciones": [True] * 6,
                        "fuente": F,
                        "motivo": "Borde inferior explícito W1-W2 empotrado en cimentación sintética.",
                    })
                elif nombre == "inclinado":
                    rr.append({
                        "id": "APOYO_BORDE_RAMPA",
                        "selector": {"tipo": "borde_entre_puntos", "inicio": "V1", "fin": "V4"},
                        "restricciones": [True, True, True, False, False, False],
                        "fuente": F,
                        "motivo": "Arranque explícito V1-V4 articulado en rampa sintética.",
                    })

                rd = []
                if esc["diafragma_z"] is not None:
                    rd.append({
                        "id": "DIAFRAGMA_LOSA_NIVEL",
                        "selector": {"tipo": "plano_z", "z_m": esc["diafragma_z"]},
                        "accion": "asignar",
                        "diafragma": "DIA1",
                        "motivo_sin_diafragma": None,
                        "fuente": F,
                    })

                sub = (
                    {
                        "modo": "autorizar_calculadas",
                        "fuente": F,
                        "motivo": "Subdivisión conforme con malla de losa/muro.",
                    }
                    if esc["frames"]
                    else None
                )

                reglas = reglas_base(
                    reglas_restricciones=rr,
                    resto_restricciones={
                        "restricciones": [False] * 6,
                        "fuente": F,
                        "motivo": "Resto de nodos interiores/superiores libres de apoyo externo.",
                    },
                    reglas_diafragma=rd,
                    resto_diafragma={
                        "accion": "excluir",
                        "diafragma": None,
                        "motivo_sin_diafragma": "Nodo fuera del diafragma de entrepiso declarado.",
                        "fuente": F,
                    },
                    subdivision_frames=sub,
                )
                sha_reglas = _canon_sha(reglas)

                vista = pma.previsualizar_politicas_malla(geo, cfg, reglas)
                self.assertTrue(vista["listo_para_aplicar"], vista)
                self.assertEqual(vista["errores"], [])
                self.assertEqual(vista["conflictos"], [])
                self.assertEqual(vista["pendientes"], [])

                if nombre in ("conectados", "conectados_corte"):
                    # Comprobar trazabilidad topológica de borde conectado C1.
                    en_c1 = [x["nodo"] for x in vista["inventario_nodos_derivados"] if "C1" in x["conexiones_borde"]]
                    self.assertTrue(en_c1, "debe identificar nodos derivados sobre la conexión C1")
                if nombre == "conectados_corte":
                    # El corte Z=1.2 m atraviesa el contorno de la ventana HM del muro S2.
                    en_hm = [x["nodo"] for x in vista["inventario_nodos_derivados"] if "HM" in x["aberturas"]]
                    self.assertTrue(en_hm, "el corte Z debe identificar nodos MC_* sobre la abertura HM")

                aplicada = pma.aplicar_politicas_malla(geo, cfg, reglas)
                self.assertIsNot(aplicada, cfg)
                self.assertEqual(aplicada["revision"], {"estado": "borrador", "aprobacion": None})
                self.assertEqual(_canon_sha(geo), sha_geo)
                self.assertEqual(_canon_sha(cfg), sha_cfg)
                self.assertEqual(_canon_sha(reglas), sha_reglas)

                val = m.validar_configuracion(aplicada, geo)
                self.assertTrue(val.consistente, val.a_dict())
                self.assertEqual(val.errores, [])
                self.assertEqual(val.faltantes, [])

    def test_no_asume_z0_ni_continuidad_de_extremos_fijados_sin_regla_explicita(self):
        esc = tim.escenario("vertical_corte")
        geo, cfg = montar_en_memoria(esc)
        # W1=(0,0,0) y W2=(0,5,0) están empotrados en cfg["apoyos"], pero NO hay regla para z=0 ni resto_restricciones.
        reglas_incompletas = reglas_base(
            reglas_restricciones=[
                {
                    "id": "SOLO_CORTE_LIBRE",
                    "selector": {"tipo": "entidades", "nodos_corte": True},
                    "restricciones": [False] * 6,
                    "fuente": F,
                    "motivo": "Nodos de corte Z libres.",
                }
            ],
            resto_restricciones=None,
            reglas_diafragma=[],
            resto_diafragma={
                "accion": "excluir",
                "diafragma": None,
                "motivo_sin_diafragma": "Muro aislado sin diafragma de piso.",
                "fuente": F,
            },
        )
        vista = pma.previsualizar_politicas_malla(geo, cfg, reglas_incompletas)
        self.assertFalse(vista["listo_para_aplicar"])
        nodos_z0 = {x["nodo"] for x in vista["inventario_nodos_derivados"] if x["z_m"] == 0.0}
        self.assertTrue(nodos_z0)
        pendientes_z0 = {
            p["nodo"]
            for p in vista["pendientes"]
            if p["tipo"] == "restricciones_nodo_derivado" and p["nodo"] in nodos_z0
        }
        # Ningún nodo en z=0 entre W1 y W2 hereda el empotramiento de W1/W2 ni se asume libre.
        self.assertEqual(pendientes_z0, nodos_z0)
        self.assertFalse({x["nodo"] for x in vista["nodos_derivados_propuestos"]} & nodos_z0)

        # Y si el ingeniero declara explícitamente z=0 como libre (p. ej. panel colgado), se respeta [False]*6.
        reglas_colgado = reglas_base(
            reglas_restricciones=[
                {
                    "id": "Z0_COLGADO_LIBRE",
                    "selector": {"tipo": "plano_z", "z_m": 0.0},
                    "restricciones": [False] * 6,
                    "fuente": F,
                    "motivo": "Borde z=0 en voladizo/colgado sin apoyo inferior.",
                }
            ],
            resto_restricciones={
                "restricciones": [False] * 6,
                "fuente": F,
                "motivo": "Resto del panel libre.",
            },
            resto_diafragma={
                "accion": "excluir",
                "diafragma": None,
                "motivo_sin_diafragma": "Panel sin diafragma.",
                "fuente": F,
            },
        )
        aplicada = pma.aplicar_politicas_malla(geo, cfg, reglas_colgado)
        por_nodo = {x["nodo"]: x for x in aplicada["nodos_derivados"]}
        for n in nodos_z0:
            self.assertEqual(por_nodo[n]["restricciones"], [False] * 6)

    def test_caso_numeroso_una_regla_evita_declarar_nodos_individualmente(self):
        piso = lambda x, y: (x, y, 3.0)
        muro = lambda y, z: (0.0, y, z)
        vertices = {
            **tim._rect("V", 0.0, 0.0, 12.0, 8.0, piso),
            "W1": (0.0, 0.0, 0.0),
            "W2": (0.0, 8.0, 0.0),
        }
        huecos = []
        # 6 aberturas desfasadas en la losa S1 (para generar nodos MN_* tanto en borde exterior como sobre contornos de hueco)
        # y 4 ventanas en el muro S2 cortadas por niveles Z (nodos MC_*).
        idx = 1
        for ix, x_base in enumerate((1.0, 4.5, 8.0)):
            for iy, y0 in enumerate((1.0, 4.5)):
                x0 = x_base + 0.6 * iy
                pref = f"HL{idx}_"
                vertices.update(tim._rect(pref, x0, y0, x0 + 1.5, y0 + 1.5, piso))
                huecos.append((f"H_LOSA_{idx}", "S1", [f"{pref}{k}" for k in range(1, 5)]))
                idx += 1
        for iw, y0 in enumerate((0.6, 2.4, 4.2, 6.0), 1):
            pref = f"HM{iw}_"
            vertices.update(tim._rect(pref, y0, 0.7, y0 + 1.0, 1.9, muro))
            huecos.append((f"H_MURO_{iw}", "S2", [f"{pref}{k}" for k in range(1, 5)]))

        esc_grande = {
            "vertices": vertices,
            "hosts": [
                ("S1", ["V1", "V2", "V3", "V4"], "LOSA20"),
                ("S2", ["W1", "W2", "V4", "V1"], "MURO"),
            ],
            "huecos": huecos,
            "conexiones": [("C1", ("S1", "V4", "V1"), ("S2", "V4", "V1"))],
            "frames": [("VIGA_BORDE", "V1", "V4", "viga")],
            "apoyos": ["W1", "W2", "V2", "V3"],
            "diafragma_z": 3.0,
            "cortes": [0.5, 1.3, 2.3],
            "cargas": [
                ("Q_LOSA", "superficie", "S1", [0.0, 0.0, -2.5]),
                ("Q_VIGA", "frame", "VIGA_BORDE", [0.0, 0.0, -4.0]),
            ],
        }
        geo, cfg = montar_en_memoria(esc_grande, fuente_extra=True)
        prep = mp.preparar_malla(geo, cfg)
        self.assertGreaterEqual(len(prep["nodos_derivados"]), 60)
        self.assertGreaterEqual(len(prep["frames_subdivision_requerida"][0]["subframes"]), 6)

        reglas = reglas_base(
            reglas_restricciones=[
                {
                    "id": "BASE_MURO_Z0",
                    "selector": {"tipo": "plano_z", "z_m": 0.0, "hosts": ["S2"]},
                    "restricciones": [True] * 6,
                    "fuente": F2,
                    "motivo": "Cimentación corrida bajo muro S2 en z=0 m.",
                }
            ],
            resto_restricciones={
                "restricciones": [False] * 6,
                "fuente": F,
                "motivo": "Resto de nodos derivados sin apoyo externo.",
            },
            reglas_diafragma=[
                {
                    "id": "DIAFRAGMA_TECHO_Z3",
                    "selector": {"tipo": "plano_z", "z_m": 3.0},
                    "accion": "asignar",
                    "diafragma": "DIA1",
                    "motivo_sin_diafragma": None,
                    "fuente": F2,
                }
            ],
            resto_diafragma={
                "accion": "excluir",
                "diafragma": None,
                "motivo_sin_diafragma": "Cotas bajo z=3.0 m fuera del diafragma de techo.",
                "fuente": F,
            },
            subdivision_frames={
                "modo": "por_frame",
                "reglas_frames": [
                    {
                        "id": "SUBDIV_VIGA_BORDE",
                        "frames": ["VIGA_BORDE"],
                        "accion": "autorizar",
                        "fuente": F2,
                        "motivo": "Compatibilidad de viga de borde con malla de losa y muro.",
                    }
                ],
            },
        )

        vista = pma.previsualizar_politicas_malla(geo, cfg, reglas)
        self.assertTrue(vista["listo_para_aplicar"], vista["resumen"])
        self.assertEqual(vista["resumen"]["nodos_derivados_resueltos"], len(prep["nodos_derivados"]))
        aplicada = pma.aplicar_politicas_malla(geo, cfg, reglas)
        self.assertEqual(len(aplicada["nodos_derivados"]), len(prep["nodos_derivados"]))
        self.assertEqual(aplicada["subdivision_frames"][0]["nodos"], prep["frames_subdivision_requerida"][0]["nodos"])

        val = m.validar_configuracion(aplicada, geo)
        self.assertTrue(val.consistente, val.a_dict())
        self.assertEqual(val.errores, [])
        self.assertEqual(val.faltantes, [])

    def test_reglas_contradictorias_senalan_conflicto_sin_elegir_la_primera(self):
        esc = tim.escenario("conectados")
        geo, cfg = montar_en_memoria(esc, fuente_extra=True)

        # 1. Contradicción en restricciones sobre nodos de S2 en z=0, diafragma en S1 y subdivisión en VIGA1.
        reglas_conflicto = reglas_base(
            reglas_restricciones=[
                {
                    "id": "R_EMPOTRADO_Z0",
                    "selector": {"tipo": "plano_z", "z_m": 0.0},
                    "restricciones": [True] * 6,
                    "fuente": F,
                    "motivo": "Regla 1: empotrado.",
                },
                {
                    "id": "R_ARTICULADO_MURO",
                    "selector": {"tipo": "entidades", "hosts": ["S2"]},
                    "restricciones": [True, True, True, False, False, False],
                    "fuente": F,
                    "motivo": "Regla 2: articulado en todo el muro S2.",
                },
            ],
            resto_restricciones={
                "restricciones": [False] * 6,
                "fuente": F,
                "motivo": "Resto libre.",
            },
            reglas_diafragma=[
                {
                    "id": "D_ASIGNAR_PISO",
                    "selector": {"tipo": "plano_z", "z_m": 2.6},
                    "accion": "asignar",
                    "diafragma": "DIA1",
                    "motivo_sin_diafragma": None,
                    "fuente": F,
                },
                {
                    "id": "D_EXCLUIR_CONEXION_C1",
                    "selector": {"tipo": "entidades", "conexiones_borde": ["C1"]},
                    "accion": "excluir",
                    "diafragma": None,
                    "motivo_sin_diafragma": "Borde compartido excluido en contradicción con regla de piso.",
                    "fuente": F,
                },
            ],
            resto_diafragma={
                "accion": "excluir",
                "diafragma": None,
                "motivo_sin_diafragma": "Fuera del piso.",
                "fuente": F,
            },
            subdivision_frames={
                "modo": "por_frame",
                "reglas_frames": [
                    {
                        "id": "F_AUTORIZAR",
                        "frames": ["VIGA1"],
                        "accion": "autorizar",
                        "fuente": F,
                        "motivo": "Subdividir viga.",
                    },
                    {
                        "id": "F_BLOQUEAR",
                        "frames": ["VIGA1"],
                        "accion": "bloquear",
                        "fuente": F,
                        "motivo": "No subdividir viga.",
                    },
                ],
            },
        )

        vista = pma.previsualizar_politicas_malla(geo, cfg, reglas_conflicto)
        self.assertFalse(vista["listo_para_aplicar"])
        tipos_conflicto = {c["tipo"] for c in vista["conflictos"]}
        self.assertIn("contradiccion_restricciones", tipos_conflicto)
        self.assertIn("contradiccion_diafragma", tipos_conflicto)
        self.assertIn("contradiccion_subdivision_frame", tipos_conflicto)
        # Los nodos en conflicto no se publican eligiendo la primera regla.
        nodos_en_conflicto = {c["nodo"] for c in vista["conflictos"] if "nodo" in c}
        self.assertFalse(nodos_en_conflicto & {x["nodo"] for x in vista["nodos_derivados_propuestos"]})

        with self.assertRaises(pma.ErrorPoliticaMalla):
            pma.aplicar_politicas_malla(geo, cfg, reglas_conflicto)

        # 2. Dos reglas específicas (restricciones vs diafragma) con distinta fuente en el mismo nodo producen conflicto de fuente.
        nodo_en_c1 = next(
            x["nodo"] for x in vista["inventario_nodos_derivados"] if "C1" in x["conexiones_borde"]
        )
        reglas_fuentes_opuestas = reglas_base(
            reglas_restricciones=[
                {
                    "id": "R_NODO_C1",
                    "selector": {"tipo": "nodos", "nodos": [nodo_en_c1]},
                    "restricciones": [False] * 6,
                    "fuente": F,
                    "motivo": "Fuente 1 en nodo específico.",
                }
            ],
            resto_restricciones={"restricciones": [False] * 6, "fuente": F, "motivo": "Resto F."},
            reglas_diafragma=[
                {
                    "id": "D_NODO_C1",
                    "selector": {"tipo": "nodos", "nodos": [nodo_en_c1]},
                    "accion": "asignar",
                    "diafragma": "DIA1",
                    "motivo_sin_diafragma": None,
                    "fuente": F2,
                }
            ],
            resto_diafragma={
                "accion": "excluir",
                "diafragma": None,
                "motivo_sin_diafragma": "Resto F.",
                "fuente": F,
            },
            subdivision_frames={"modo": "autorizar_calculadas", "fuente": F, "motivo": "Conforme."},
        )
        vista_fuentes = pma.previsualizar_politicas_malla(geo, cfg, reglas_fuentes_opuestas)
        self.assertFalse(vista_fuentes["listo_para_aplicar"])
        self.assertTrue(any(c["tipo"] == "conflicto_fuentes_nodo_derivado" for c in vista_fuentes["conflictos"]))

    def test_coordenadas_y_unidades_incorrectas_y_contrato_cerrado(self):
        esc = tim.escenario("conectados")
        geo, cfg = montar_en_memoria(esc)

        # 1. Unidad de longitud distinta de 'm' en reglas.
        reglas_cm = pma.plantilla_reglas_vacia()
        reglas_cm["unidad_longitud"] = "cm"
        v_cm = pma.previsualizar_politicas_malla(geo, cfg, reglas_cm)
        self.assertFalse(v_cm["listo_para_aplicar"])
        self.assertTrue(any(e["ruta"] == "$.reglas.unidad_longitud" for e in v_cm["errores"]))

        # 2. Unidades inválidas en la configuración.
        cfg_mal_u = copy.deepcopy(cfg)
        cfg_mal_u["unidades"]["longitud"] = "mm"
        v_cfg_u = pma.previsualizar_politicas_malla(geo, cfg_mal_u, pma.plantilla_reglas_vacia())
        self.assertFalse(v_cfg_u["listo_para_aplicar"])
        self.assertTrue(any(e["ruta"] == "$.configuracion.unidades" for e in v_cfg_u["errores"]))

        # 3. Coordenada no finita (NaN) y campo desconocido o entero en vez de bool.
        reglas_nan = reglas_base(
            reglas_restricciones=[
                {
                    "id": "R_NAN",
                    "selector": {"tipo": "plano_z", "z_m": float("nan")},
                    "restricciones": [True] * 6,
                    "fuente": F,
                    "motivo": "Cota inválida.",
                }
            ]
        )
        v_nan = pma.previsualizar_politicas_malla(geo, cfg, reglas_nan)
        self.assertFalse(v_nan["listo_para_aplicar"])
        self.assertTrue(any(e["ruta"] == "$.reglas" for e in v_nan["errores"]))

        reglas_campo_extra = pma.plantilla_reglas_vacia()
        reglas_campo_extra["tolerancia_fusion_m"] = 0.05
        self.assertTrue(pma.validar_reglas_politica(reglas_campo_extra))

        reglas_int_bool = reglas_base(
            resto_restricciones={"restricciones": [1, 0, 0, 0, 0, 0], "fuente": F, "motivo": "Enteros no son bool."}
        )
        self.assertTrue(pma.validar_reglas_politica(reglas_int_bool))

        # 4. Diafragma DIA1 (cota 2.6 m) asignado a nodo fuera de su plano (z=0.0 m).
        reglas_fuera_cota = reglas_base(
            resto_restricciones={"restricciones": [False] * 6, "fuente": F, "motivo": "Libre."},
            reglas_diafragma=[
                {
                    "id": "DIA_FUERA_PLANO",
                    "selector": {"tipo": "plano_z", "z_m": 0.0},
                    "accion": "asignar",
                    "diafragma": "DIA1",
                    "motivo_sin_diafragma": None,
                    "fuente": F,
                }
            ],
            resto_diafragma={
                "accion": "excluir",
                "diafragma": None,
                "motivo_sin_diafragma": "Resto.",
                "fuente": F,
            },
            subdivision_frames={"modo": "autorizar_calculadas", "fuente": F, "motivo": "Conforme."},
        )
        v_cota = pma.previsualizar_politicas_malla(geo, cfg, reglas_fuera_cota)
        self.assertFalse(v_cota["listo_para_aplicar"])
        self.assertTrue(any("fuera de la cota" in e["mensaje"] for e in v_cota["errores"]))

        # 5. Geometría expresada en centímetros ('cm'): la normalización a metros funciona con reglas en 'm',
        #    mientras que escribir z_m=260 en lugar de 2.6 m deja el piso sin emparejar.
        geo_cm, cfg_cm = montar_en_memoria(tim.escenario("horizontal"), unidad_geometria="cm")
        reglas_equivocadas_260 = reglas_base(
            resto_restricciones={"restricciones": [False] * 6, "fuente": F, "motivo": "Libre."},
            reglas_diafragma=[
                {
                    "id": "DIA_EN_CM_POR_ERROR",
                    "selector": {"tipo": "plano_z", "z_m": 260.0},
                    "accion": "asignar",
                    "diafragma": "DIA1",
                    "motivo_sin_diafragma": None,
                    "fuente": F,
                }
            ],
        )
        v_260 = pma.previsualizar_politicas_malla(geo_cm, cfg_cm, reglas_equivocadas_260)
        self.assertFalse(v_260["listo_para_aplicar"])
        self.assertIn("diafragma:DIA_EN_CM_POR_ERROR", v_260["reglas_sin_coincidencia"])
        self.assertGreater(len(v_260["pendientes"]), 0)

        reglas_correctas_m = reglas_base(
            resto_restricciones={"restricciones": [False] * 6, "fuente": F, "motivo": "Libre."},
            reglas_diafragma=[
                {
                    "id": "DIA_EN_M",
                    "selector": {"tipo": "plano_z", "z_m": 2.6},
                    "accion": "asignar",
                    "diafragma": "DIA1",
                    "motivo_sin_diafragma": None,
                    "fuente": F,
                }
            ],
        )
        aplicada_cm = pma.aplicar_politicas_malla(geo_cm, cfg_cm, reglas_correctas_m)
        self.assertTrue(m.validar_configuracion(aplicada_cm, geo_cm).consistente)

    def test_geometria_o_configuracion_origen_incompatible(self):
        esc = tim.escenario("conectados")
        geo, cfg = montar_en_memoria(esc)

        # Geometría con versión distinta de 0.3.0.
        geo_02 = copy.deepcopy(geo)
        geo_02["version_contrato"] = "0.2.0"
        v1 = pma.previsualizar_politicas_malla(geo_02, cfg, pma.plantilla_reglas_vacia())
        self.assertFalse(v1["listo_para_aplicar"])
        self.assertTrue(any(e["ruta"] == "$.geometria.version_contrato" for e in v1["errores"]))

        # Configuración de otro caso.
        cfg_otro_caso = copy.deepcopy(cfg)
        cfg_otro_caso["caso"] = "OTRO-CASO"
        v2 = pma.previsualizar_politicas_malla(geo, cfg_otro_caso, pma.plantilla_reglas_vacia())
        self.assertFalse(v2["listo_para_aplicar"])
        self.assertTrue(any(e["ruta"] == "$.configuracion.caso" for e in v2["errores"]))

        # Marca datos_sinteticos discordante entre geometría y configuración.
        cfg_no_sint = copy.deepcopy(cfg)
        cfg_no_sint["datos_sinteticos"] = False
        v3 = pma.previsualizar_politicas_malla(geo, cfg_no_sint, pma.plantilla_reglas_vacia())
        self.assertFalse(v3["listo_para_aplicar"])
        self.assertTrue(any(e["ruta"] == "$.configuracion.datos_sinteticos" for e in v3["errores"]))

        # Huella de contenido de otra geometría.
        cfg_otra_huella = copy.deepcopy(cfg)
        cfg_otra_huella["geometria_origen"]["huella_contenido"] = "a" * 64
        v4 = pma.previsualizar_politicas_malla(geo, cfg_otra_huella, pma.plantilla_reglas_vacia())
        self.assertFalse(v4["listo_para_aplicar"])
        self.assertTrue(any(e["ruta"] == "$.configuracion.geometria_origen.huella_contenido" for e in v4["errores"]))

        # Borrador temprano sin conexiones_borde aún generado.
        cfg_sin_cx = copy.deepcopy(cfg)
        cfg_sin_cx["conexiones_borde"] = None
        v5 = pma.previsualizar_politicas_malla(geo, cfg_sin_cx, pma.plantilla_reglas_vacia())
        self.assertFalse(v5["listo_para_aplicar"])
        self.assertTrue(any(e["ruta"] == "$.configuracion.conexiones_borde" for e in v5["errores"]))

    def test_fuentes_y_entidades_inexistentes_rechazadas(self):
        esc = tim.escenario("conectados")
        geo, cfg = montar_en_memoria(esc)
        cfg["frames"].append({"id": "COL_ESQUINA", "inicio": "W1", "fin": "V1", "tipo": "columna", "fuente": F})
        cfg["asignaciones_frames"].append({"objetivo": "COL_ESQUINA", "seccion": "FRAME", "fuente": F})

        reglas_invalidas = reglas_base(
            reglas_restricciones=[
                {
                    "id": "R_FUENTE_INEXISTENTE",
                    "selector": {"tipo": "plano_z", "z_m": 0.0},
                    "restricciones": [True] * 6,
                    "fuente": "FUENTE_FANTASMA",
                    "motivo": "Fuente no registrada.",
                },
                {
                    "id": "R_HOST_INEXISTENTE",
                    "selector": {"tipo": "entidades", "hosts": ["S99"]},
                    "restricciones": [True] * 6,
                    "fuente": F,
                    "motivo": "Host inexistente.",
                },
                {
                    "id": "R_PUNTO_NO_DERIVADO",
                    "selector": {"tipo": "nodos", "nodos": ["V1"]},
                    "restricciones": [True] * 6,
                    "fuente": F,
                    "motivo": "V1 es punto de configuración, no nodo derivado.",
                },
            ],
            resto_restricciones={
                "restricciones": [False] * 6,
                "fuente": "OTRA_FANTASMA",
                "motivo": "Resto con fuente inexistente.",
            },
            reglas_diafragma=[
                {
                    "id": "D_DIAFRAGMA_INEXISTENTE",
                    "selector": {"tipo": "plano_z", "z_m": 2.6},
                    "accion": "asignar",
                    "diafragma": "DIA_NO_EXISTE",
                    "motivo_sin_diafragma": None,
                    "fuente": F,
                }
            ],
            resto_diafragma={
                "accion": "excluir",
                "diafragma": None,
                "motivo_sin_diafragma": "Fuera del piso.",
                "fuente": F,
            },
            subdivision_frames={
                "modo": "por_frame",
                "reglas_frames": [
                    {
                        "id": "SUB_COL_SIN_NODOS_INTERIORES",
                        "frames": ["COL_ESQUINA"],
                        "accion": "autorizar",
                        "fuente": F,
                        "motivo": "COL_ESQUINA no tiene nodos interiores de malla.",
                    }
                ],
            },
        )

        vista = pma.previsualizar_politicas_malla(geo, cfg, reglas_invalidas)
        self.assertFalse(vista["listo_para_aplicar"])
        rutas_error = {e["ruta"] for e in vista["errores"]}
        self.assertIn("$.reglas.reglas_restricciones[0].fuente", rutas_error)
        self.assertIn("$.reglas.reglas_restricciones[1].selector.hosts", rutas_error)
        self.assertIn("$.reglas.reglas_restricciones[2].selector.nodos", rutas_error)
        self.assertIn("$.reglas.resto_restricciones.fuente", rutas_error)
        self.assertIn("$.reglas.reglas_diafragma[0].diafragma", rutas_error)
        self.assertIn("$.reglas.subdivision_frames.reglas_frames[0].frames", rutas_error)
        with self.assertRaises(pma.ErrorPoliticaMalla):
            pma.aplicar_politicas_malla(geo, cfg, reglas_invalidas)

    def test_preserva_identidad_sintetica_no_hereda_aprobacion_ni_maquilla_otros_faltantes(self):
        # 1. Configuración 0.5.0 con datos incompletos ajenos a la malla (líquidos e información de sitio)
        #    y con una aprobación previa simulada en la entrada.
        esc = tim.escenario("conectados_corte")
        geo, cfg = montar_en_memoria(esc, datos_sinteticos=True, version_config=m.VERSION_LIQUIDOS)
        cfg["liquidos"] = {
            "aplicabilidad": "informacion_insuficiente",
            "fuente": F,
            "motivo": "Pendiente revisar lámina hidráulica sintética.",
            "declaraciones": [],
        }
        cfg["sitio"]["ubicacion"] = None
        cfg["faltantes"] = [
            {
                "ruta": "$.sitio.ubicacion",
                "motivo": "Ubicación pendiente de confirmación.",
                "fuente": F,
            }
        ]
        cfg["revision"] = {
            "estado": "aprobado",
            "aprobacion": {
                "revisor_declarado": "Revisor previo",
                "fecha": "2026-10-20",
                "huella_configuracion": "b" * 64,
                "alcance": "Aprobación previa que NO debe heredarse.",
                "identidad_revisor": "declarada_no_verificada",
            },
        }
        sha_geo_antes = _canon_sha(geo)
        sha_cfg_antes = _canon_sha(cfg)

        reglas = reglas_base(
            reglas_restricciones=[
                {
                    "id": "BASE_W1_W2",
                    "selector": {"tipo": "borde_entre_puntos", "inicio": "W1", "fin": "W2"},
                    "restricciones": [True] * 6,
                    "fuente": F,
                    "motivo": "Base empotrada explícita.",
                }
            ],
            resto_restricciones={
                "restricciones": [False] * 6,
                "fuente": F,
                "motivo": "Resto libre.",
            },
            reglas_diafragma=[
                {
                    "id": "DIA_Z26",
                    "selector": {"tipo": "plano_z", "z_m": 2.6},
                    "accion": "asignar",
                    "diafragma": "DIA1",
                    "motivo_sin_diafragma": None,
                    "fuente": F,
                }
            ],
            resto_diafragma={
                "accion": "excluir",
                "diafragma": None,
                "motivo_sin_diafragma": "Fuera de cota 2.6 m.",
                "fuente": F,
            },
            subdivision_frames={"modo": "autorizar_calculadas", "fuente": F, "motivo": "Subdivisión conforme."},
        )
        sha_reglas_antes = _canon_sha(reglas)

        copia = pma.aplicar_politicas_malla(geo, cfg, reglas)

        # Entradas intactas.
        self.assertEqual(_canon_sha(geo), sha_geo_antes)
        self.assertEqual(_canon_sha(cfg), sha_cfg_antes)
        self.assertEqual(_canon_sha(reglas), sha_reglas_antes)
        self.assertEqual(cfg["revision"]["estado"], "aprobado")

        # La copia está en borrador sin aprobación heredada, conserva identidad/estado sintético y NO maquilla líquidos ni sitio.
        self.assertEqual(copia["revision"], {"estado": "borrador", "aprobacion": None})
        self.assertIs(copia["datos_sinteticos"], True)
        self.assertEqual(copia["caso"], cfg["caso"])
        self.assertEqual(copia["id"], cfg["id"])
        self.assertIsNone(copia["sitio"]["ubicacion"])
        self.assertEqual(copia["liquidos"]["aplicabilidad"], "informacion_insuficiente")

        val = m.validar_configuracion(copia, geo)
        self.assertTrue(val.consistente, val.a_dict())
        self.assertEqual(val.errores, [])
        rutas_faltantes = {f["ruta"] for f in val.faltantes}
        # Cero faltantes de malla/subdivisión, pero siguen visibles los faltantes reales de sitio y líquidos.
        self.assertFalse(any(r.startswith("$.nodos_derivados") or r.startswith("$.subdivision_frames") for r in rutas_faltantes))
        self.assertIn("$.sitio.ubicacion", rutas_faltantes)
        self.assertTrue(any("liquidos" in r for r in rutas_faltantes))

        # 2. También preserva datos_sinteticos=False cuando geometría y configuración sintéticas de prueba declaran False.
        geo_f, cfg_f = montar_en_memoria(tim.escenario("horizontal"), datos_sinteticos=False)
        reglas_h = reglas_base(
            resto_restricciones={"restricciones": [False] * 6, "fuente": F, "motivo": "Libre."},
            reglas_diafragma=[
                {
                    "id": "DIA_H",
                    "selector": {"tipo": "plano_z", "z_m": 2.6},
                    "accion": "asignar",
                    "diafragma": "DIA1",
                    "motivo_sin_diafragma": None,
                    "fuente": F,
                }
            ],
        )
        copia_f = pma.aplicar_politicas_malla(geo_f, cfg_f, reglas_h)
        self.assertIs(copia_f["datos_sinteticos"], False)

    def test_selectores_de_abertura_bloqueo_de_frame_y_reproducibilidad_determinista(self):
        # Losa horizontal con dos huecos desfasados en X para que existan nodos derivados MN_* sobre bordes de hueco,
        # conectada a muro con ventana cortada en Z=1.2 m (nodos MC_* sobre HM) y barra VIGA1.
        piso = lambda x, y: (x, y, 2.6)
        muro = lambda y, z: (0.0, y, z)
        esc = {
            "vertices": {
                **tim._rect("V", 0.0, 0.0, 5.0, 4.0, piso),
                **tim._rect("HA", 1.0, 0.6, 3.0, 1.6, piso),
                **tim._rect("HB", 1.8, 2.2, 3.6, 3.2, piso),
                "W1": (0.0, 0.0, 0.0),
                "W2": (0.0, 4.0, 0.0),
                **tim._rect("G", 1.0, 0.8, 2.5, 1.8, muro),
            },
            "hosts": [
                ("S1", ["V1", "V2", "V3", "V4"], "LOSA20"),
                ("S2", ["W1", "W2", "V4", "V1"], "MURO"),
            ],
            "huecos": [
                ("HA", "S1", ["HA1", "HA2", "HA3", "HA4"]),
                ("HB", "S1", ["HB1", "HB2", "HB3", "HB4"]),
                ("HM", "S2", ["G1", "G2", "G3", "G4"]),
            ],
            "conexiones": [("C1", ("S1", "V4", "V1"), ("S2", "V4", "V1"))],
            "frames": [("VIGA1", "V1", "V4", "viga")],
            "apoyos": ["W1", "W2"],
            "diafragma_z": 2.6,
            "cortes": [1.2],
            "cargas": [("Q1", "superficie", "S1", [0.0, 0.0, -2.0])],
        }
        geo, cfg = montar_en_memoria(esc)

        # 1. Bloqueo explícito de subdivisión en VIGA1 impide declarar listo y deja pendiente visible.
        reglas_bloqueo = reglas_base(
            reglas_restricciones=[
                {
                    "id": "APOYO_BORDE_HA",
                    "selector": {"tipo": "entidades", "aberturas": ["HA"]},
                    "restricciones": [False, False, True, False, False, False],
                    "fuente": F,
                    "motivo": "Puntal vertical sintético bajo abertura HA.",
                },
                {
                    "id": "GUIA_CORTE_VENTANA_HM",
                    "selector": {"tipo": "entidades", "aberturas": ["HM"], "nodos_corte": True},
                    "restricciones": [True, False, False, False, False, False],
                    "fuente": F,
                    "motivo": "Restricción X sintética en corte Z sobre jamba de HM.",
                },
            ],
            resto_restricciones={"restricciones": [False] * 6, "fuente": F, "motivo": "Resto libre."},
            reglas_diafragma=[
                {
                    "id": "DIA_S1",
                    "selector": {"tipo": "plano_z", "z_m": 2.6},
                    "accion": "asignar",
                    "diafragma": "DIA1",
                    "motivo_sin_diafragma": None,
                    "fuente": F,
                }
            ],
            resto_diafragma={
                "accion": "excluir",
                "diafragma": None,
                "motivo_sin_diafragma": "Fuera de losa.",
                "fuente": F,
            },
            subdivision_frames={
                "modo": "por_frame",
                "reglas_frames": [
                    {
                        "id": "BLOQUEAR_VIGA1",
                        "frames": ["VIGA1"],
                        "accion": "bloquear",
                        "fuente": F,
                        "motivo": "Revisión pendiente del modelo de conexión viga-losa.",
                    }
                ],
            },
        )
        v_bloq = pma.previsualizar_politicas_malla(geo, cfg, reglas_bloqueo)
        self.assertFalse(v_bloq["listo_para_aplicar"])
        self.assertEqual([p["tipo"] for p in v_bloq["pendientes"]], ["subdivision_frame_bloqueada"])

        # 2. Al autorizar VIGA1, se verifica selección exacta sobre HA y HM y determinismo de huellas.
        reglas_ok = copy.deepcopy(reglas_bloqueo)
        reglas_ok["subdivision_frames"]["reglas_frames"][0]["accion"] = "autorizar"
        v_a = pma.previsualizar_politicas_malla(geo, cfg, reglas_ok)
        v_b = pma.previsualizar_politicas_malla(geo, cfg, reglas_ok)
        self.assertTrue(v_a["listo_para_aplicar"])
        self.assertEqual(v_a["huella_propuesta"], v_b["huella_propuesta"])

        copia_a = pma.aplicar_politicas_malla(geo, cfg, reglas_ok)
        copia_b = pma.aplicar_politicas_malla(geo, cfg, reglas_ok)
        self.assertEqual(m.huella_configuracion(copia_a), m.huella_configuracion(copia_b))
        por_nodo = {x["nodo"]: x for x in copia_a["nodos_derivados"]}
        nodos_ha = [x["nodo"] for x in v_a["inventario_nodos_derivados"] if "HA" in x["aberturas"]]
        nodos_hm_corte = [
            x["nodo"] for x in v_a["inventario_nodos_derivados"] if "HM" in x["aberturas"] and x["es_nodo_corte"]
        ]
        self.assertTrue(nodos_ha)
        self.assertTrue(nodos_hm_corte)
        for n in nodos_ha:
            self.assertEqual(por_nodo[n]["restricciones"], [False, False, True, False, False, False])
        for n in nodos_hm_corte:
            self.assertEqual(por_nodo[n]["restricciones"], [True, False, False, False, False, False])
        self.assertTrue(m.validar_configuracion(copia_a, geo).consistente)


if __name__ == "__main__":
    unittest.main()
