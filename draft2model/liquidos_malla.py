"""Cargas hidrostáticas revisadas → filas de la tabla CSI no uniforme sobre los triángulos de la malla 0.5.

Puro y determinista (sin ETABS). Para cada declaración `presente` de la configuración 0.5:
declaración revisada → coeficientes globales p = γ·max(0, h − z) (`cargas_liquidos_etabs`) → filas por triángulo de
cada superficie cargada, en el patrón DEDICADO de la declaración → integral de fuerza y momento sobre los triángulos
contrastada con la integral independiente del contorno fuente menos huecos (`acciones_liquidos`).

Exige corte por el nivel libre en toda superficie que lo atraviese: ninguna pieza puede cruzar el nivel (ensayo 185).
No sustituye la presión por cargas puntuales ni uniformes, no rellena huecos y no crea pisos.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math

from .acciones_liquidos import calcular_acciones_liquidos, declarar_acciones_liquidos, ErrorAccionesLiquidos
from .cargas_liquidos_etabs import CAMPOS, TABLA, ErrorCargaLiquido, preparar_cargas_no_uniformes
from .vinculo_presion_malla import _integrar

CONTRATO = "draft2model.liquidos_malla"
VERSION = "0.1.0"
TOLERANCIA = 1e-9  # computacional (conservación de la integral); no es tolerancia de ingeniería


def _canon(x) -> bytes:
    return json.dumps(x, sort_keys=True, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def texto_numero(valor: float) -> str:
    """Texto de celda de tabla editable: decimal de ida y vuelta, con punto."""
    return repr(float(valor))


def preparar_liquidos(geometria: dict, configuracion: dict, prep: dict) -> dict:
    """Filas y conservación para la configuración 0.5 vigente; ErrorCargaLiquido si algo no es reproducible."""
    liq = configuracion.get("liquidos")
    if not isinstance(liq, dict) or liq.get("aplicabilidad") not in ("ausente_confirmado", "presente", "informacion_insuficiente"):
        raise ErrorCargaLiquido("Configuración sin aplicabilidad de líquidos explícita.")
    base = {"contrato": CONTRATO, "version_contrato": VERSION, "aplicabilidad": liq["aplicabilidad"],
            "fuente_aplicabilidad": liq["fuente"], "tabla": TABLA, "version_tabla": 1, "campos": list(CAMPOS),
            "unidades": "kN_m_C", "unidad_ABC": "kN/m3", "unidad_D": "kN/m2", "aprueba_ingenieria": False}
    if liq["aplicabilidad"] == "informacion_insuficiente":
        raise ErrorCargaLiquido("Existencia de líquidos con información insuficiente: no se prepara un plan.")
    if liq["aplicabilidad"] == "ausente_confirmado":
        out = {**base, "declaraciones": [], "patrones": [], "filas": [], "hosts": [],
               "nota": "Ausencia de cisterna/tanque confirmada: sin cargas de líquido ni filas cero ficticias."}
        out["huella_liquidos"] = hashlib.sha256(_canon(out)).hexdigest()
        return out
    niveles = set((prep.get("cortes_nivel") or {}).get("niveles_z_m", []))
    nodos = {n["csi"]: n["xyz_m"] for n in prep["nodos"]}
    triangulos = {t["csi"]: t for t in prep["triangulos"]}
    filas, hosts, declaraciones, piezas_cargadas = [], [], [], {}
    try:
        for item in liq["declaraciones"]:
            patron = item["patron"]
            declarada = declarar_acciones_liquidos(geometria, item["declaracion"], item["fuentes"])
            presion = preparar_cargas_no_uniformes(geometria, declarada, item["fuentes"])
            integral = calcular_acciones_liquidos(geometria, declarada, item["fuentes"])
            esperadas = {s["superficie"]: s for s in integral["superficies"]}
            origen = integral["origen_momentos_m"]
            h = declarada["declaracion"]["nivel_libre_z_m"]
            for host in presion["superficies"]:
                nombre = host["superficie"]
                h = host.get("nivel_efectivo_z_m", declarada["declaracion"]["nivel_libre_z_m"])   # cara física (R253)
                if nombre not in prep["hosts"]:
                    raise ErrorCargaLiquido(f"Superficie {nombre} sin malla asignada.")
                faltan = [z for z in host["cortes_obligatorios_z_m"] if z not in niveles]
                if faltan:
                    raise ErrorCargaLiquido(f"Falta corte explícito en Z={faltan} m para {nombre}.")
                piezas = prep["hosts"][nombre]["triangulos"]
                if not piezas or set(piezas) != {t for t, x in triangulos.items() if x["host"] == nombre}:
                    raise ErrorCargaLiquido(f"Cobertura de piezas incompleta en {nombre}.")
                medidas, fuerzas, momentos = [], [], []
                for pieza in piezas:
                    clave_pieza = (pieza, patron)
                    if clave_pieza in piezas_cargadas:
                        raise ErrorCargaLiquido(f"Pieza {pieza} cargada dos veces en el patrón {patron}.")
                    piezas_cargadas[clave_pieza] = declarada["declaracion"]["id"]
                    xyz = [nodos[n] for n in triangulos[pieza]["nodos"]]
                    zs = [p[2] for p in xyz]
                    if min(zs) < h < max(zs):
                        raise ErrorCargaLiquido(f"La pieza {pieza} cruza el nivel libre Z={h}; no se aproxima la presión.")
                    area, fuerza, momento = _integrar(xyz, host["componentes"], origen)
                    medidas.append(area); fuerzas.append(fuerza); momentos.append(momento)
                    for comp in host["componentes"]:
                        filas.append({"UniqueName": pieza, "LoadPattern": patron, "Dir": comp["Dir"],
                                      "A": texto_numero(comp["A"]), "B": texto_numero(comp["B"]),
                                      "C": texto_numero(comp["C"]), "D": texto_numero(comp["D"]),
                                      "Restriction": comp["Restriction"]})
                f = [math.fsum(v[k] for v in fuerzas) for k in range(3)]
                m = [math.fsum(v[k] for v in momentos) for k in range(3)]
                esperado = esperadas[nombre]
                errores = [abs(a - b) / max(1.0, abs(a), abs(b)) for a, b in zip(f + m, esperado["fuerza_kn"] + esperado["momento_kn_m"])]
                if not all(math.isfinite(e) and e <= TOLERANCIA for e in errores):
                    raise ErrorCargaLiquido(f"La presión sobre las piezas de {nombre} no conserva fuerza y momento del contorno neto.")
                hosts.append({"declaracion": declarada["declaracion"]["id"], "patron": patron, "superficie": nombre,
                              "triangulos": list(piezas), "componentes": copy.deepcopy(host["componentes"]),
                              "nivel_libre_z_m": declarada["declaracion"]["nivel_libre_z_m"],
                              **({"nivel_efectivo_z_m": h, "desplazamiento_cara_m": host["desplazamiento_cara_m"]} if "nivel_efectivo_z_m" in host else {}),
                              "peso_especifico_kn_m3": declarada["declaracion"]["peso_especifico_kn_m3"],
                              "origen_momentos_m": list(origen), "area_material_m2": math.fsum(medidas),
                              "fuerza_kn": f, "momento_kn_m": m, "fuerza_fuente_kn": list(esperado["fuerza_kn"]),
                              "momento_fuente_kn_m": list(esperado["momento_kn_m"]), "error_relativo_max": max(errores),
                              "aberturas_ids": list(host["aberturas_ids"]), "cortes_z_m": list(host["cortes_obligatorios_z_m"])})
            declaraciones.append({"id": declarada["declaracion"]["id"], "patron": patron,
                                  "huella_declaracion": declarada["huella_declaracion"],
                                  "superficies": [s["superficie"] for s in presion["superficies"]]})
    except (ErrorAccionesLiquidos, KeyError, TypeError, ValueError) as exc:
        if isinstance(exc, ErrorCargaLiquido):
            raise
        raise ErrorCargaLiquido("Líquidos no reproducibles con la configuración y malla vigentes: " + str(exc)) from None
    filas.sort(key=lambda r: (r["UniqueName"], r["LoadPattern"], r["Dir"]))
    claves = [(r["UniqueName"], r["LoadPattern"], r["Dir"]) for r in filas]
    if len(set(claves)) != len(claves):
        raise ErrorCargaLiquido("Filas duplicadas objeto/patrón/dirección; no se suman ni se ocultan.")
    out = {**base, "declaraciones": declaraciones, "patrones": sorted({d["patron"] for d in declaraciones}),
           "filas": filas, "hosts": hosts, "criterio_conservacion": f"|a-b| <= {TOLERANCIA}·max(1,|a|,|b|), computacional",
           "no_afirma": ["hidrodinamica", "geotecnia", "flotacion", "masa_del_liquido"]}
    out["huella_liquidos"] = hashlib.sha256(_canon(out)).hexdigest()
    return out
