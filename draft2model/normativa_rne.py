"""Criterios de materiales y cargas del RNE vigente con cita verificable (E.060, E.070, E.020).

Ediciones (auditoría de Codex, seguimiento/NORMATIVA_OFICIAL_229.md): E.060 DS 010-2009-VIVIENDA; E.070 y E.020
DS 011-2006-VIVIENDA con fe de erratas de 21/06/2006. Solo se implementan relaciones unívocas del texto; la elección
del material, f'c/f'm de diseño, el uso de cada ambiente y el metrado de acabados/tabiquería son ENTRADAS con fuente.

Unidades: esfuerzos en MPa internamente; 1 kgf/cm² = 0,0980665 MPa (definición de kgf). Las fórmulas de E.060 8.5
están en MPa y no admiten f'c en kgf/cm² directamente.
"""
from __future__ import annotations

import math

KGF_CM2_A_MPA = 0.0980665
E060 = {"codigo": "E.060", "dispositivo": "DS 010-2009-VIVIENDA", "texto_registrado": "seguimiento/normativa_229/E060_DS010_2009.txt"}
E070 = {"codigo": "E.070", "dispositivo": "DS 011-2006-VIVIENDA (fe de erratas 21/06/2006)",
        "texto_registrado": "seguimiento/normativa_229/E070_DS011_2006.txt"}
E020 = {"codigo": "E.020", "dispositivo": "DS 011-2006-VIVIENDA (fe de erratas 21/06/2006)",
        "texto_registrado": "seguimiento/normativa_229/E020_DS011_2006.txt"}
EM_POR_UNIDAD = {"arcilla": 500, "silico_calcarea": 600, "concreto_vibrado": 700}  # E.070 24.7
PESOS_KN_M3 = {"concreto_armado": 24.0, "concreto_simple_grava": 23.0, "agua_dulce": 10.0,
               "albanileria_cocida_solida": 18.0, "albanileria_cocida_hueca": 13.5}  # E.020 anexo 1
# E.020 anexo 1: aligerado en una dirección, vigueta 0,10 m a 0,40 m entre ejes, losa superior 0,05 m (peso propio, kPa).
PESO_ALIGERADO_KPA = {0.17: 2.8, 0.20: 3.0, 0.25: 3.5, 0.30: 4.2}
CARGA_VIVA_KPA = {"vivienda": 2.0, "vivienda_corredores_escaleras": 2.0, "techo_pendiente_hasta_3": 1.0}  # E.020 6.1, 7.1.a


def _cita(norma, articulo, **extra):
    return {**norma, "articulo": articulo, **extra}


def _positivo(v, nombre):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
        raise ValueError(f"{nombre}: número finito positivo requerido.")
    return float(v)


def a_mpa(valor: float, unidad: str) -> float:
    if unidad == "MPa":
        return _positivo(valor, "esfuerzo")
    if unidad == "kgf/cm2":
        return _positivo(valor, "esfuerzo") * KGF_CM2_A_MPA
    raise ValueError("Unidad de esfuerzo admitida: MPa o kgf/cm2.")


def modulo_concreto(fc: float, unidad: str) -> dict:
    """E.060 8.5.2 (concreto de peso normal, wc ≈ 2300 kg/m³): Ec = 4700·√f'c [MPa]; G = Ec/2,3 (8.5.4)."""
    fc_mpa = a_mpa(fc, unidad)
    ec = 4700 * math.sqrt(fc_mpa)
    return {"fc_MPa": fc_mpa, "Ec_MPa": ec, "Ec_kN_m2": ec * 1000, "G_MPa": ec / 2.3,
            "nu_derivado_isotropia": ec / (2 * ec / 2.3) - 1,
            "cita": [_cita(E060, "8.5.2", formula="Ec = 4700 √f'c (MPa)"), _cita(E060, "8.5.4", formula="G = Ec/2,3")],
            "nota": "ν = 0,15 es algebraico (isotropía con G = Ec/2,3), no un valor tabulado por la norma."}


def modulo_albanileria(fm: float, unidad: str, tipo_unidad: str) -> dict:
    """E.070 24.7: Em = 500/600/700·f'm según la unidad; Gm = 0,4·Em (fórmula verificada visualmente, p. 21)."""
    if tipo_unidad not in EM_POR_UNIDAD:
        raise ValueError(f"Tipo de unidad: {sorted(EM_POR_UNIDAD)} (no se infiere del plano).")
    fm_mpa = a_mpa(fm, unidad)
    em = EM_POR_UNIDAD[tipo_unidad] * fm_mpa
    return {"fm_MPa": fm_mpa, "Em_MPa": em, "Em_kN_m2": em * 1000, "Gm_MPa": 0.4 * em, "nu_derivado_isotropia": 0.25,
            "cita": [_cita(E070, "24.7", formula=f"Em = {EM_POR_UNIDAD[tipo_unidad]} f'm; Gm = 0,4 Em", pagina_pdf=21)]}


def peso_especifico(material: str) -> dict:
    if material not in PESOS_KN_M3:
        raise ValueError(f"Material del anexo 1 implementado: {sorted(PESOS_KN_M3)}.")
    return {"peso_kN_m3": PESOS_KN_M3[material], "cita": _cita(E020, "Anexo 1")}


def peso_aligerado(espesor_m: float) -> dict:
    """Peso propio tabulado del aligerado unidireccional (sin acabados ni tabiquería); solo espesores de la tabla."""
    if espesor_m not in PESO_ALIGERADO_KPA:
        raise ValueError(f"Espesor de aligerado tabulado en E.020 anexo 1: {sorted(PESO_ALIGERADO_KPA)}.")
    return {"peso_kPa": PESO_ALIGERADO_KPA[espesor_m], "cita": _cita(E020, "Anexo 1",
            nota="Vigueta 0,10 m, 0,40 m entre ejes, losa superior 0,05 m.")}


def carga_viva(uso: str) -> dict:
    if uso not in CARGA_VIVA_KPA:
        raise ValueError(f"Uso implementado: {sorted(CARGA_VIVA_KPA)}; otros usos requieren su fila de la Tabla 1.")
    return {"kPa": CARGA_VIVA_KPA[uso], "kN_m2": CARGA_VIVA_KPA[uso],
            "cita": _cita(E020, "7.1.a" if uso.startswith("techo") else "6.1", tabla="Tabla 1" if not uso.startswith("techo") else None),
            "nota": "Mínimo según uso efectivo; no incluye acabados ni tabiquería (se metran aparte)."}
