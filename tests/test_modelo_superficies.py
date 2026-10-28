"""Configuración 0.2 de superficies con geometría 0.2 SINTÉTICA versionada; no representa una obra ni usa ETABS.

Caso válido: piso homogéneo sintético (losa S1 sobre cuatro columnas, vértices compartidos con los
puntos de columna) y panel inclinado S2 con cota intermedia (1.3 m entre N0 = 0 y N1 = 2.6), apoyado
en su borde inferior. Huecos y aligerados NO están implementados y no se prueban como válidos.
"""
import copy
import hashlib
import json
from pathlib import Path
from unittest import mock
from uuid import uuid4

from draft2model import contratos
from draft2model import gestion_geometria as g
from draft2model import modelo_estructural as m
from draft2model.geometria_superficies import BLOQUEO_INTEGRACION
from draft2model.gestion_extraccion import ErrorGestion
from tests.test_gestion_geometria import CasoGeometria, CASO

RAIZ = Path(__file__).resolve().parents[1]
EJEMPLO_GEO = RAIZ / "examples" / "geometria_sintetica.json"
EJEMPLO_CONFIG = RAIZ / "examples" / "modelo_estructural_sintetico.json"
F = "F-SINTETICA"
VERTICES = {"VA": (0, 0, 2.6), "VB": (4, 0, 2.6), "VC": (4, 3, 2.6), "VD": (0, 3, 2.6),
            "R1": (0, 4, 0), "R2": (4, 4, 0), "R3": (4, 6, 1.3), "R4": (0, 6, 1.3)}


def geometria_superficies(vertices=None, superficies=None, aprobar=True):
    data = json.loads(EJEMPLO_GEO.read_text(encoding="utf-8"))
    procedencia = copy.deepcopy(data["procedencia"])
    data.update(version_contrato=contratos.VERSION_GEOMETRIA_SUPERFICIES, muros=[], faltantes=[])
    data["vertices"] = [{"id": k, "x": x, "y": y, "z": z, "procedencia": copy.deepcopy(procedencia)}
                        for k, (x, y, z) in (vertices or VERTICES).items()]
    data["superficies"] = [{"id": sid, "vertices": ids, "papel_geometrico": papel, "procedencia": copy.deepcopy(procedencia)}
                           for sid, ids, papel in (superficies or [("S1", ["VA", "VB", "VC", "VD"], "piso sintético"),
                                                                    ("S2", ["R1", "R2", "R3", "R4"], "panel inclinado sintético")])]
    data["revision"] = {"estado": "borrador", "aprobacion": None}
    if aprobar:
        data["revision"] = {"estado": "aprobado", "aprobacion": {
            "declarada_por": "Revisor sintético", "fecha": "2026-10-19", "huella_contenido": contratos.huella_contenido(data),
            "alcance": "Superficies sintéticas de software.", "observaciones": "Solo pruebas."}}
    return data


def configuracion_superficies():
    data = json.loads(EJEMPLO_CONFIG.read_bytes())
    data["version_contrato"] = m.VERSION_SUPERFICIES
    data["secciones"] = [{"id": "FRAME", "tipo": "frame_rectangular", "material": "MAT1",
                          "dimensiones": {"ancho_m": 0.2, "alto_m": 0.3}, "fuente": F},
                         {"id": "LOSA20", "tipo": "shell_losa_homogenea", "material": "MAT1",
                          "dimensiones": {"espesor_m": 0.2}, "fuente": F}]
    nodos = [{"id": f"{n}{k}", "nodo_geometria": n, "nivel_geometria": f"N{k}"} for k in (0, 1) for n in "ABCD"]
    data["puntos"] = nodos + [{"id": r, "vertice_geometria": r} for r in ("R1", "R2", "R3", "R4")]
    data["vertices_compartidos"] = [{"vertice_geometria": "V" + n, "punto": n + "1", "fuente": F} for n in "ABCD"]
    data["frames"] = [{"id": "COL" + n, "inicio": n + "0", "fin": n + "1", "tipo": "columna", "fuente": F} for n in "ABCD"]
    data["asignaciones_muros"] = []
    data["asignaciones_frames"] = [{"objetivo": "COL" + n, "seccion": "FRAME", "fuente": F} for n in "ABCD"]
    data["asignaciones_superficies"] = [{"objetivo": s, "seccion": "LOSA20", "fuente": F} for s in ("S1", "S2")]
    data["cargas"] = [{"id": "P1", "patron": "L", "objetivo_tipo": "punto", "objetivo": "B1", "componentes": [0, 0, -1],
                       "unidad": "kN", "sistema": "global", "fuente": F},
                      {"id": "Q1", "patron": "L", "objetivo_tipo": "superficie", "objetivo": "S1", "componentes": [0, 0, -2],
                       "unidad": "kN/m2", "sistema": "global", "fuente": F}]
    data["apoyos"] = [{"punto": p, "restricciones": [True] * 6, "fuente": F} for p in ("A0", "B0", "C0", "D0", "R1", "R2")]
    data["diafragmas"] = [{"id": "DIA1", "tipo": "rigido", "puntos": ["A1", "B1", "C1", "D1"], "fuente": F}]
    data["sin_diafragma"] = [{"punto": p, "motivo": "Fuera del piso sintético", "fuente": F}
                             for p in ("A0", "B0", "C0", "D0", "R1", "R2", "R3", "R4")]
    data["espectros"] = []
    data["casos"] = [data["casos"][0]]
    data["combinaciones"] = [{"id": "COMB1", "tipo": "lineal", "casos": [{"caso": "EST", "factor": 1.2}], "fuente": F}]
    data["analisis"] = {"casos_ejecutar": ["EST"], "combinaciones_resultados": ["COMB1"], "fuente": F}
    return data


class CasoSuperficies(CasoGeometria):
    """Expediente sintético con geometría 0.2 y configuración 0.2 en borrador.

    DOBLE DE GESTIÓN: la gestión vigente no puede registrar una aprobación 0.2 (`importar_geometria`
    rechaza aprobaciones y `aprobar_geometria` exige `disponible_para_modelado`, falso en 0.2 por
    BLOQUEO_INTEGRACION). Para el caso aprobado se sustituye `consultar_version` por un doble que
    devuelve la geometría aprobada por huella con su comprobación; integrarlo corresponde a Codex.
    El caso en borrador usa la gestión real (importación y comprobación de evidencia).
    """

    def setUp(self):
        super().setUp()
        self._parche = None
        self.addCleanup(self._retirar_doble)
        self.montar()

    def _retirar_doble(self):
        if self._parche is not None:
            self._parche.stop()
            self._parche = None

    def montar(self, geometria=None, aprobada=True):
        self._retirar_doble()
        if aprobada:
            geo = geometria if geometria is not None else geometria_superficies()
            version_id = uuid4().hex
            self.problemas_doble = []
            comprobacion = g.ComprobacionGeometria(
                CASO, version_id, sha256_geometria=hashlib.sha256(json.dumps(geo, sort_keys=True).encode()).hexdigest(),
                huella_contenido=contratos.huella_contenido(geo), cadena=[version_id])

            def consultar(raiz, caso, vid):
                if caso != CASO or vid != version_id:
                    raise ErrorGestion("Versión inexistente en el doble de gestión.")
                comp = copy.deepcopy(comprobacion)
                comp.problemas = list(self.problemas_doble)
                return g.ConsultaGeometria(caso, vid, Path(raiz) / "doble", copy.deepcopy(geo), {"doble": True}, comp)
            self._parche = mock.patch.object(g, "consultar_version", consultar)
            self._parche.start()
            origen = {"version_id": version_id, "sha256_geometria": comprobacion.sha256_geometria,
                      "huella_contenido": comprobacion.huella_contenido}
        else:
            geo = geometria if geometria is not None else geometria_superficies(aprobar=False)
            imp = g.importar_geometria(self.raiz, CASO, self.escribir(geo, "geo02.json"))
            origen = {"version_id": imp.identificador, "sha256_geometria": imp.comprobacion.sha256_geometria,
                      "huella_contenido": imp.comprobacion.huella_contenido}
        self.geometria = g.consultar_version(self.raiz, CASO, origen["version_id"]).geometria
        self.data = configuracion_superficies()
        self.data["geometria_origen"] = origen

    def aprobar_config(self, data=None):
        data = copy.deepcopy(self.data if data is None else data)
        data["revision"] = {"estado": "aprobado", "aprobacion": {
            "revisor_declarado": "Revisor SINTÉTICO de software", "fecha": "2026-10-19",
            "huella_configuracion": m.huella_configuracion(data),
            "alcance": "Superficies sintéticas para probar el transporte.", "identidad_revisor": "declarada_no_verificada"}}
        return data


class ConfiguracionSuperficiesTests(CasoSuperficies):
    def test_valida_consistente_pero_nunca_apta_para_adaptador(self):
        antes = copy.deepcopy(self.data)
        r = m.validar_configuracion(self.data, self.geometria)
        self.assertTrue(r.consistente, r.errores)
        self.assertEqual(self.data, antes)
        self.assertFalse(r.apto_para_adaptador)
        d = r.a_dict()
        self.assertEqual(d["version_contrato"], "0.2.0")
        self.assertFalse(d["ejecutable_en_etabs"])
        self.assertIn(BLOQUEO_INTEGRACION, r.bloqueos)
        self.assertIn(m.BLOQUEO_SUPERFICIES, r.bloqueos)
        self.assertTrue(r.geometria_aprobada_por_huella)
        json.dumps(d, allow_nan=False)

    def test_comprobada_admite_solo_plan_de_desarrollo(self):
        r = m.comprobar_configuracion(self.raiz, self.aprobar_config())
        self.assertTrue(r.consistente, r.errores)
        self.assertTrue(r.geometria_comprobada)
        self.assertTrue(r.aprobacion_configuracion_vigente)
        self.assertTrue(r.apto_para_plan_desarrollo, r.bloqueos)
        self.assertFalse(r.apto_para_adaptador)  # el bloqueo de integración no se elude
        self.assertEqual(set(r.bloqueos), {BLOQUEO_INTEGRACION, m.BLOQUEO_SUPERFICIES})
        self.assertFalse(m.comprobar_configuracion(self.raiz, self.data).apto_para_plan_desarrollo)  # borrador
        cambiada = self.aprobar_config()
        cambiada["secciones"][1]["dimensiones"]["espesor_m"] = 0.25  # tras aprobar
        self.assertFalse(m.comprobar_configuracion(self.raiz, cambiada).apto_para_plan_desarrollo)

    def test_evidencia_alterada_impide_plan_de_desarrollo(self):
        self.problemas_doble = ["Original alterado (simulado en el doble)."]
        r = m.comprobar_configuracion(self.raiz, self.aprobar_config())
        self.assertFalse(r.geometria_comprobada)
        self.assertFalse(r.apto_para_plan_desarrollo)

    def test_geometria_borrador_gestion_real_no_aprobada_por_huella(self):
        self.montar(aprobada=False)  # importación y comprobación reales, sin doble
        r = m.comprobar_configuracion(self.raiz, self.aprobar_config())
        self.assertTrue(r.geometria_comprobada, r.errores)
        self.assertTrue(r.consistente, r.errores)
        self.assertFalse(r.geometria_aprobada_por_huella)
        self.assertFalse(r.apto_para_plan_desarrollo)
        self.assertIn("Geometría sin aprobación vigente o con faltantes.", r.bloqueos)

    def test_version_01_sin_campos_nuevos_y_sin_reinterpretacion(self):
        d01 = m.validar_configuracion(json.loads(EJEMPLO_CONFIG.read_bytes())).a_dict()
        self.assertNotIn("version_contrato", d01)
        self.assertNotIn("apto_para_plan_desarrollo", d01)
        etiquetada = copy.deepcopy(self.data)
        etiquetada["version_contrato"] = m.VERSION  # 0.2 reetiquetada como 0.1
        self.assertFalse(m.validar_configuracion(etiquetada, self.geometria).consistente)
        geo01 = json.loads(EJEMPLO_GEO.read_text(encoding="utf-8"))
        r = m.validar_configuracion(self.data, geo01)
        self.assertIn("exige una geometría 0.2.0", " ".join(r.errores))

    def test_invalidos(self):
        def mod(f):
            d = copy.deepcopy(self.data)
            f(d)
            return d

        def quitar(lista, **campos):
            return [x for x in lista if not all(x.get(k) == v for k, v in campos.items())]
        casos = {
            "superficie sin sección": (lambda d: d.update(asignaciones_superficies=d["asignaciones_superficies"][:1]),
                                       "cobertura de superficies"),
            "sección incompatible": (lambda d: d["asignaciones_superficies"][0].update(seccion="FRAME"), "sección incompatible"),
            "punto huérfano": (lambda d: (d.update(frames=quitar(d["frames"], id="COLA"),
                                                   asignaciones_frames=quitar(d["asignaciones_frames"], objetivo="COLA"))),
                               "punto sin conexión"),
            "vértice sin punto": (lambda d: (d.update(puntos=quitar(d["puntos"], id="R4"),
                                                      sin_diafragma=quitar(d["sin_diafragma"], punto="R4"))),
                                  "sin punto ni vértice compartido"),
            "compartido con otra cota": (lambda d: d["vertices_compartidos"][0].update(punto="A0"), "difieren"),
            "punto coincidente duplicado": (lambda d: (d["vertices_compartidos"].pop(0),
                                                       d["puntos"].append({"id": "VAP", "vertice_geometria": "VA"}),
                                                       d["sin_diafragma"].append({"punto": "VAP", "motivo": "x", "fuente": F})),
                                            "coincidentes"),
            "conexión ausente": (lambda d: d.update(apoyos=quitar(quitar(d["apoyos"], punto="R1"), punto="R2")),
                                 "conexión ausente"),
            "diafragma no coplanar": (lambda d: (d["diafragmas"][0]["puntos"].append("R3"),
                                                 d.update(sin_diafragma=quitar(d["sin_diafragma"], punto="R3"))), "coplanares"),
            "diafragma de un punto": (lambda d: (d["diafragmas"].append({"id": "DIA2", "tipo": "rigido", "puntos": ["R4"],
                                                                         "fuente": F}),
                                                 d.update(sin_diafragma=quitar(d["sin_diafragma"], punto="R4"))),
                                      "al menos dos puntos"),
            "material incompatible": (lambda d: d["materiales"][0].update(tipo="ortotropo"), "material incompatible"),
            "masa explícita": (lambda d: d["masa"].update(metodo="explicita", factores_patrones=[],
                                                          masas_puntos=[{"punto": "B1", "masa_kN_s2_m": 1}]), "masa puntual"),
            "unidad de carga de superficie": (lambda d: d["cargas"][1].update(unidad="kN/m"), "unidad o sistema"),
            "carga a superficie inexistente": (lambda d: d["cargas"][1].update(objetivo="S9"), "referencia inexistente"),
            "punto con campos mezclados": (lambda d: d["puntos"][-1].update(nivel_geometria="N0"), "alternativa"),
            "compartido de punto vértice": (lambda d: d["vertices_compartidos"][0].update(punto="R1"), "solo un punto nodo+nivel"),
            "doble peso propio": (lambda d: d["masa"].update(incluir_masa_propia=True), "duplican"),
            "huella geométrica": (lambda d: d["geometria_origen"].update(huella_contenido="0" * 64), "huella de contenido"),
        }
        for nombre, (cambio, esperado) in casos.items():
            with self.subTest(nombre):
                r = m.validar_configuracion(mod(cambio), self.geometria)
                self.assertFalse(r.consistente, nombre)
                self.assertIn(esperado, " ".join(r.errores))

    def test_superficie_vertical_con_losa_rechazada(self):
        vertical = dict(VERTICES, R3=(4, 4, 1.3), R4=(0, 4, 1.3))
        geo = geometria_superficies(vertical)
        data = copy.deepcopy(self.data)
        r = m.validar_configuracion(data, geo)
        self.assertIn("vertical", " ".join(r.errores))

    def test_cota_intermedia_sin_nivel_ficticio(self):
        r = m.validar_configuracion(self.data, self.geometria)
        self.assertTrue(r.consistente, r.errores)
        self.assertEqual([n["id"] for n in self.geometria["niveles"]], ["N0", "N1"])  # 1.3 m no crea nivel
