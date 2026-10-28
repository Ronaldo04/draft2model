"""Libro completo de contribuciones de la fuente de masa (configuración 0.5 + geometría + malla) y contraste con la masa
ENSAMBLADA nativa leída de ETABS (masa_ensamblada).

Contribuciones, todas en kN·s²/m con la g de la fuente de masa:
- peso propio de shells (área de la malla × espesor × γ) y frames (longitud entre nudos × área × γ), solo a través de los
  patrones con multiplicador de peso propio y factor en la fuente (método «patrones»); si la fuente incluye masa de
  elementos (incluir_masa_propia), se suma una vez como «masa_elementos»;
- cargas declaradas de superficie (q·área de malla del host), frame (w·longitud) y punto: componente gravitatoria (−Z)
  por el factor del patrón;
- líquidos: Fz de las presiones conservadas por host (liquidos_malla), por patrón y factor.

Convenciones explícitas, no ajustadas a la respuesta: el libro NO descuenta solapes nudo-elemento (longitud completa entre nudos).
ETABS sí puede descontarlos: en 09d1, con SelfWtOpt=Auto, excluyó el peso de los tramos extremos de las VIGAS y no el de las
columnas (HALLAZGO_DESFASE_CM_09D1); esa diferencia se concilia aparte y de forma explícita (conciliar_extremos_vigas), nunca
dentro del libro independiente. Las cargas hacia arriba restan; no hay masa vertical ni rotacional. Sin E/S ni ETABS.
"""
from __future__ import annotations

import math
import re

from . import malla_preparacion as mp
from .masa_ensamblada import MassValidationError, validate_assembled_joint_mass


class ErrorLibroMasa(ValueError):
    pass


def _area_triangulo(a, b, c):
    u = [b[i] - a[i] for i in range(3)]
    v = [c[i] - a[i] for i in range(3)]
    w = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0]]
    return 0.5 * math.sqrt(sum(x * x for x in w))


def _area_seccion(sec):
    d = sec["dimensiones"]
    if sec["tipo"] == "frame_rectangular":
        return d["ancho_m"] * d["alto_m"]
    if sec["tipo"] == "frame_l_concreto":   # SetConcreteL: T2·Tf + (T3 − Tf)·Tw
        return d["ancho_m"] * d["espesor_ala_m"] + (d["alto_m"] - d["espesor_ala_m"]) * d["espesor_alma_m"]
    raise ErrorLibroMasa("Sección de frame sin área definida en el libro: " + sec["tipo"])


def libro_masa(configuracion: dict, vg, prep: dict, liquidos: dict | None = None) -> dict:
    """vg: validar_geometria(...) de la versión vigente; prep: preparar_malla; liquidos: preparar_liquidos (0.5)."""
    c = configuracion
    masa = c["masa"]
    if masa["metodo"] != "patrones" or masa["masas_puntos"]:
        raise ErrorLibroMasa("El libro cubre la fuente por patrones sin masas puntuales.")
    g = masa["gravedad_m_s2"]
    factores = {f["patron"]: f["factor"] for f in masa["factores_patrones"]}
    patrones = {p["id"]: p for p in c["patrones"]}
    materiales = {m["id"]: m for m in c["materiales"]}
    secciones = {s["id"]: s for s in c["secciones"]}
    nodos = {n["csi"]: n["xyz_m"] for n in prep["nodos"]}

    area_host = {}
    for t in prep["triangulos"]:
        area_host[t["host"]] = area_host.get(t["host"], 0.0) + _area_triangulo(*(nodos[n] for n in t["nodos"]))
    asign = {a["objetivo"]: a["seccion"] for a in c["asignaciones_superficies"]}
    asign.update({a["objetivo"]: a["seccion"] for a in c.get("asignaciones_muros", [])})
    peso_shells = math.fsum(area_host[h] * secciones[s]["dimensiones"]["espesor_m"] * materiales[secciones[s]["material"]]["peso_kN_m3"]
                            for h, s in asign.items() if h in area_host)
    sin_malla = sorted(set(asign) - set(area_host))
    if sin_malla:
        raise ErrorLibroMasa("Superficies asignadas sin piezas de malla: " + ", ".join(sin_malla[:5]))

    xyz = mp.coordenadas_puntos(c, vg)
    long_frame = {f["id"]: math.dist(xyz[f["inicio"]], xyz[f["fin"]]) for f in c["frames"]}
    asign_f = {a["objetivo"]: a["seccion"] for a in c["asignaciones_frames"]}
    peso_frames = math.fsum(long_frame[f] * _area_seccion(secciones[s]) * materiales[secciones[s]["material"]]["peso_kN_m3"]
                            for f, s in asign_f.items())
    peso_propio = peso_shells + peso_frames

    contribuciones = {}
    f_pp = math.fsum(factores.get(p, 0.0) * patrones[p]["multiplicador_peso_propio"] for p in patrones)
    contribuciones["peso_propio_por_patrones"] = {"peso_kn": peso_propio, "factor_efectivo": f_pp,
                                                  "masa_kn_s2_m": f_pp * peso_propio / g,
                                                  "detalle": {"shells_kn": peso_shells, "frames_kn": peso_frames}}
    if masa["incluir_masa_propia"]:
        contribuciones["masa_elementos"] = {"peso_kn": peso_propio, "factor_efectivo": 1.0, "masa_kn_s2_m": peso_propio / g}

    cargas = {}
    for q in c["cargas"]:
        if q["sistema"] != "global":
            raise ErrorLibroMasa("Carga en sistema local: el libro no la proyecta implícitamente (" + q["id"] + ").")
        fz = q["componentes"][2]
        if q["objetivo_tipo"] == "superficie":
            if q["objetivo"] not in area_host:
                raise ErrorLibroMasa("Carga sobre superficie sin malla: " + q["objetivo"])
            w = -fz * area_host[q["objetivo"]]
        elif q["objetivo_tipo"] == "frame":
            w = -fz * long_frame[q["objetivo"]]
        else:
            w = -fz
        cargas[q["patron"]] = cargas.get(q["patron"], 0.0) + w
    for patron, w in sorted(cargas.items()):
        f = factores.get(patron, 0.0)
        contribuciones["cargas_" + patron] = {"peso_kn": w, "factor_efectivo": f, "masa_kn_s2_m": f * w / g}
    if liquidos is not None:
        por_patron = {}
        for h in liquidos["hosts"]:
            por_patron[h["patron"]] = por_patron.get(h["patron"], 0.0) - h["fuerza_kn"][2]
        for patron, w in sorted(por_patron.items()):
            f = factores.get(patron, 0.0)
            contribuciones["liquido_" + patron] = {"peso_kn": w, "factor_efectivo": f, "masa_kn_s2_m": f * w / g,
                                                   "huella_liquidos": liquidos["huella_liquidos"]}
    total = math.fsum(v["masa_kn_s2_m"] for v in contribuciones.values())
    if not math.isfinite(total) or total < 0:
        raise ErrorLibroMasa("Total de masa no finito o negativo.")
    return {"contrato": "draft2model.libro_masa", "version": "0.1.0", "gravedad_m_s2": g, "factores": factores,
            "contribuciones": contribuciones, "masa_total_kn_s2_m": total, "peso_equivalente_kn": total * g,
            "convenciones": ["sin descuento de solapes", "solo componente gravitatoria", "sin masa vertical ni rotacional"],
            "aprueba_ingenieria": False}


DECIMAL = re.compile(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?")


def _numero(v, campo, *, admite_none=False):
    """Texto decimal 'R' del lector (o número no booleano de un extracto); bool, None indebido u otros tipos se rechazan."""
    if v is None and admite_none:
        return None   # posible cola de asignación: su neutralidad la decide masa_ensamblada
    if type(v) is str and DECIMAL.fullmatch(v):
        x = float(v)
    elif type(v) in (int, float):   # type() exacto: bool no es int aquí
        x = float(v)
    else:
        raise ErrorLibroMasa(f"{campo}: valor no numérico o booleano en la captura ({type(v).__name__}).")
    if not math.isfinite(x):
        raise ErrorLibroMasa(f"{campo}: valor no finito en la captura.")
    return x


def _ident(v, campo, *, admite_none=False):
    if (v is None and admite_none) or type(v) is str:
        return v
    raise ErrorLibroMasa(f"{campo}: identificador no textual en la captura ({type(v).__name__}).")


def _triple(v, campo):
    if not isinstance(v, list) or len(v) != 3:
        raise ErrorLibroMasa(campo + ": se requieren tres valores.")
    return [_numero(x, campo) for x in v]


def contrastar_masa_nativa(captura: dict, libro: dict, *, capture_id: str, fuente_esperada: str, tolerancia_relativa: float) -> dict:
    """Captura AssembledJointMass_1 del lector (textos 'R') → masa_ensamblada contra el total del libro.

    La tolerancia es un criterio explícito del llamador (relativa al total del libro), no se ajusta a la respuesta. Un fallo se
    devuelve con su código; nunca se convierte en éxito.
    """
    if not (isinstance(tolerancia_relativa, float) and 0 < tolerancia_relativa < 0.05):
        raise ErrorLibroMasa("Tolerancia relativa explícita en (0, 0.05) requerida.")
    for k in ("retorno", "numero_resultados"):
        if type(captura[k]) is not int:
            raise ErrorLibroMasa(k + ": entero exacto requerido (no booleano).")
    raw = {"capture_id": capture_id, "units": captura["unidades"], "return_code": captura["retorno"],
           "number_results": captura["numero_resultados"],
           "point_elements": [_ident(v, "point_elements", admite_none=True) for v in captura["point_elements"]],
           "mass_sources": [_ident(v, "mass_sources", admite_none=True) for v in captura["mass_sources"]]}
    for k in ("U1", "U2", "U3", "R1", "R2", "R3"):
        raw[k] = [_numero(v, k, admite_none=True) for v in captura[k]]
    filas = []
    for o in captura["observaciones"]:
        if not isinstance(o, dict):
            raise ErrorLibroMasa("Observación de masa no es un objeto.")
        filas.append({"point_element": _ident(o["point_element"], "observacion.point_element"),
                      "mass_source": _ident(o["mass_source"], "observacion.mass_source"),
                      "global_xyz": _triple(o["global_xyz"], "observacion.global_xyz"),
                      "point_axes_deg": _triple(o["point_axes_deg"], "observacion.point_axes_deg"),
                      **{k: _numero(o[k], "observacion." + k) for k in ("U1", "U2", "U3", "R1", "R2", "R3")}})
    obs = {"capture_id": capture_id, "units": captura["unidades"], "rows": filas}
    esperado = libro["masa_total_kn_s2_m"]
    tol = tolerancia_relativa * esperado
    base = {"contrato": "draft2model.contraste_masa_nativa", "version": "0.1.0", "capture_id": capture_id,
            "fuente_esperada": fuente_esperada, "masa_libro_kn_s2_m": esperado, "tolerancia_absoluta": tol,
            "tolerancia_relativa": tolerancia_relativa, "aprueba_ingenieria": False}
    try:
        r = validate_assembled_joint_mass(raw, obs, units="kN_m_C", expected_source=fuente_esperada, expected_mass=esperado,
                                          absolute_mass_tolerance=tol, axes_tolerance_deg=1e-9)
    except MassValidationError as exc:
        u1 = math.fsum(v for v in raw["U1"][:raw["number_results"]] if isinstance(v, float))
        u2 = math.fsum(v for v in raw["U2"][:raw["number_results"]] if isinstance(v, float))
        return {**base, "estado": "no_coherente", "codigo": getattr(exc, "code", type(exc).__name__), "detalle": str(exc),
                "masa_observada_U1": u1, "masa_observada_U2": u2,
                "diferencia_relativa_U1": (u1 - esperado) / esperado if esperado else None}
    u1, u2, u3 = r.totals_U1_U2_U3
    return {**base, "estado": "coherente", "fuente_observada": r.source, "masa_observada_U1": u1, "masa_observada_U2": u2,
            "masa_observada_U3": u3, "centroide_U1": list(r.centroid_U1) if r.centroid_U1 else None,
            "centroide_U2": list(r.centroid_U2) if r.centroid_U2 else None, "numero_puntos": len(r.rows),
            "campos_con_cola": list(r.padded_fields), "diferencia_relativa_U1": (u1 - esperado) / esperado if esperado else None,
            "alcance": "captura nativa del EDB analizado (lector con instancia nueva y huellas) contra libro independiente; "
                       "no acredita distribución hidrodinámica ni aprueba ingeniería"}


def conciliar_extremos_vigas(libro: dict, configuracion: dict, filas_extremos: list, *, fuente: str) -> dict:
    """Conciliación EXPLÍCITA (no independiente) con la tabla nativa «Frame Assignments - End Length Offsets».

    Observado en 09d1 (HALLAZGO_DESFASE_CM_09D1): con SelfWtOpt = Auto, ETABS excluyó el peso propio de los tramos extremos de las
    VIGAS (Σ offsets × w = 6,86124 kN frente a 6,86126 kN de su lista de materiales) y NO el de las columnas, que también tienen
    offsets. Solo se aplica a frames de tipo «viga» con SelfWtOpt «Auto» y RigidFact 0, con los offsets leídos; nada se infiere.
    Devuelve un libro conciliado separado; el libro independiente y su contraste no cambian.
    """
    masa = configuracion["masa"]
    g = masa["gravedad_m_s2"]
    secciones = {s["id"]: s for s in configuracion["secciones"]}
    materiales = {m["id"]: m for m in configuracion["materiales"]}
    tipo = {f["id"]: f["tipo"] for f in configuracion["frames"]}
    asign = {a["objetivo"]: a["seccion"] for a in configuracion["asignaciones_frames"]}
    f_pp = libro["contribuciones"]["peso_propio_por_patrones"]["factor_efectivo"]
    excluido, filas, vistos = 0.0, [], set()
    if not isinstance(filas_extremos, list) or not filas_extremos:
        raise ErrorLibroMasa("Tabla de extremos vacía o no es una lista.")
    for f in filas_extremos:
        if not isinstance(f, dict) or not {"UniqueName", "OffsetI", "OffsetJ", "RigidFact", "SelfWtOpt"} <= set(f):
            raise ErrorLibroMasa("Fila de extremos incompleta.")
        u = f["UniqueName"]
        if type(u) is not str or u not in asign:
            raise ErrorLibroMasa("Frame de la tabla de extremos ausente de la configuración: " + str(u))
        if u in vistos:   # revisión Codex 279: una fila duplicada contaría dos veces el mismo tramo
            raise ErrorLibroMasa("Frame repetido en la tabla de extremos: " + u)
        vistos.add(u)
        if _numero(f["OffsetI"], "OffsetI") < 0 or _numero(f["OffsetJ"], "OffsetJ") < 0:   # un offset negativo sumaría masa
            raise ErrorLibroMasa("Offset de extremo negativo en " + u + ".")
        if tipo[u] != "viga" or f["SelfWtOpt"] != "Auto" or _numero(f["RigidFact"], "RigidFact") != 0:
            continue
        s = secciones[asign[u]]
        w = _area_seccion(s) * materiales[s["material"]]["peso_kN_m3"]
        largo = _numero(f["OffsetI"], "OffsetI") + _numero(f["OffsetJ"], "OffsetJ")
        excluido += largo * w
        filas.append({"frame": u, "offsets_m": largo, "peso_excluido_kn": largo * w})
    conciliado = libro["masa_total_kn_s2_m"] - f_pp * excluido / g
    return {"contrato": "draft2model.libro_masa_conciliado", "version": "0.1.0", "independiente": False, "fuente_extremos": fuente,
            "regla": "vigas con SelfWtOpt Auto y RigidFact 0: se excluye el peso de OffsetI + OffsetJ (observado 09d1)",
            "peso_excluido_kn": excluido, "masa_total_kn_s2_m": conciliado, "filas": filas,
            "masa_libro_independiente_kn_s2_m": libro["masa_total_kn_s2_m"], "aprueba_ingenieria": False}
