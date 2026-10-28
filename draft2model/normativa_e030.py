"""Criterios de la Norma Técnica E.030 vigente (RM 183-2026-VIVIENDA, El Peruano, 3 de mayo de 2026) con cita verificable.

Cada función devuelve el valor y la cita (artículo/tabla) del texto oficial registrado por Codex en
`seguimiento/normativa_229/E030_RM183_2026.txt`. Solo se implementa lo que el texto fija de forma unívoca:
factor Z (Tabla 1 y anexo de zonificación), S/TP/TL (Tablas 4 y 5, con interpolación por Vs30 o la regla sin Vs30),
C (Tabla 6, art. 18), espectro inelástico (art. 41), R = R0·Ia·Ip (arts. 22 y 26, Tabla 10), desplazamientos
(art. 50), distorsión admisible (art. 51, Tabla 14), cortante mínimo (art. 44) y excentricidad accidental (art. 45).

No decide por el usuario: el perfil de suelo (requiere EMS, art. 16), la categoría de uso, el sistema estructural y
los factores de irregularidad Ia/Ip (requieren evaluación del modelo) son ENTRADAS declaradas con su fuente. No
evalúa cumplimiento de artículos no implementados aquí; esos quedan como «no evaluado».
"""
from __future__ import annotations

import json
import math
from pathlib import Path

NORMA = {"codigo": "E.030", "titulo": "Diseño Sismorresistente", "dispositivo": "RM 183-2026-VIVIENDA",
         "publicacion": "El Peruano, 2026-05-03", "texto_registrado": "seguimiento/normativa_229/E030_RM183_2026.txt"}
TABLA1_Z = {4: 0.45, 3: 0.35, 2: 0.25, 1: 0.10}
# Tabla 4: S por zona y perfil; S2/S3 son intervalos (interpolación por Vs30, Tabla 3) y S4 exige estudio de sitio.
TABLA4_S = {4: {"S0": 0.80, "S1": 1.00, "S2": (1.00, 1.10), "S3": (1.10, 1.20)},
            3: {"S0": 0.80, "S1": 1.00, "S2": (1.00, 1.15), "S3": (1.15, 1.20), "S4": 1.30},
            2: {"S0": 0.80, "S1": 1.00, "S2": (1.00, 1.30), "S3": (1.30, 1.40), "S4": 1.70},
            1: {"S0": 0.80, "S1": 1.00, "S2": (1.00, 1.30), "S3": (1.30, 1.60), "S4": 2.40}}
TABLA5_TP = {"S0": 0.3, "S1": 0.4, "S2": (0.4, 0.6), "S3": (0.6, 0.9), "S4": 1.2}
TABLA5_TL = {"S0": 3.0, "S1": 2.5, "S2": (2.5, 2.0), "S3": (2.0, 1.6), "S4": 1.6}
# Sin Vs30 (nota de Tablas 4/5): mayor S del intervalo; TP/TL fijados por la nota.
SIN_VS30 = {"S2": (0.6, 2.0), "S3": (0.9, 1.6)}
# Tabla 3: intervalo de Vs30 (m/s) de cada perfil interpolable [mín, máx). El extremo rígido (máx) corresponde al
# primer valor de los intervalos de las Tablas 4/5 (continuidad con el perfil más rígido adyacente).
VS30_INTERVALO = {"S2": (350.0, 550.0), "S3": (200.0, 350.0)}
TABLA10_R0 = {"concreto_porticos": 8, "concreto_dual": 7, "concreto_muros_estructurales": 6,
              "muros_ductilidad_limitada": 3.5, "albanileria_armada_o_confinada": 3}
TABLA14_DERIVA = {"concreto_armado": 0.007, "acero": 0.010, "albanileria": 0.005, "madera": 0.010,
                  "muros_ductilidad_limitada": 0.004}


def _cita(articulo, tabla=None, nota=None):
    c = {**NORMA, "articulo": articulo}
    if tabla:
        c["tabla"] = tabla
    if nota:
        c["nota"] = nota
    return c


def _num(valor, nombre, minimo=None):
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor):
        raise ValueError(f"{nombre}: número finito requerido.")
    if minimo is not None and valor < minimo:
        raise ValueError(f"{nombre}: debe ser ≥ {minimo}.")
    return float(valor)


def _positivo(valor, nombre):
    v = _num(valor, nombre)
    if v <= 0:
        raise ValueError(f"{nombre}: debe ser > 0.")
    return v


def _periodos_sitio(TP, TL):
    TP, TL = _num(TP, "TP", 0), _num(TL, "TL", 0)
    if not 0 < TP < TL:
        raise ValueError("Se requiere 0 < TP < TL (Tabla N° 5).")
    return TP, TL


def factor_zona(zona: int) -> dict:
    if zona not in TABLA1_Z:
        raise ValueError("Zona sísmica 1 a 4 (anexo de zonificación de la norma).")
    return {"Z": TABLA1_Z[zona], "cita": _cita("11", "Tabla N° 1")}


TABLA7_U = {"A2": 1.5, "B": 1.3, "C": 1.0}  # A1: ver nota de la Tabla N° 7 (aislamiento); no se tabula aquí


def factor_uso(categoria: str) -> dict:
    """Tabla N° 7 (art. 19.1). «C»: edificaciones comunes, p. ej. viviendas."""
    if categoria not in TABLA7_U:
        raise ValueError("Categoría A2, B o C; A1 depende de la nota de la Tabla N° 7.")
    return {"U": TABLA7_U[categoria], "cita": _cita("19.1", "Tabla N° 7")}


def parametros_sitio(zona: int, perfil: str, *, vs30: float | None = None) -> dict:
    """S, TP y TL. S2/S3 con Vs30 interpolan; sin Vs30 se aplica la nota de las Tablas 4 y 5."""
    if zona not in TABLA4_S or perfil not in TABLA5_TP:
        raise ValueError("Zona 1–4 y perfil S0–S4.")
    s = TABLA4_S[zona].get(perfil)
    if s is None:
        raise ValueError(f"Perfil {perfil} en zona {zona}: la norma exige análisis de respuesta de sitio.")
    tp, tl = TABLA5_TP[perfil], TABLA5_TL[perfil]
    if not isinstance(s, tuple):
        return {"S": s, "TP": tp, "TL": tl, "metodo": "valor_tabulado", "cita": _cita("17", "Tablas N° 4 y N° 5")}
    if vs30 is None:
        tp, tl = SIN_VS30[perfil]
        return {"S": max(s), "TP": tp, "TL": tl, "metodo": "sin_vs30_nota_tablas_4_5",
                "cita": _cita("17", "Tablas N° 4 y N° 5", "Sin Vs30: mayor S del intervalo y TP/TL de la nota.")}
    vs = _num(vs30, "Vs30", 0)
    lo, hi = VS30_INTERVALO[perfil]
    if not lo <= vs < hi:
        raise ValueError(f"Vs30 = {vs} m/s fuera del intervalo del perfil {perfil} [{lo}, {hi}) de la Tabla N° 3; "
                         "no se extrapola: revise el perfil declarado.")
    t = (hi - vs) / (hi - lo)   # 0 en el extremo rígido, → 1 hacia el blando
    interp = lambda par: par[0] + t * (par[1] - par[0])
    return {"S": interp(s), "TP": interp(tp), "TL": interp(tl), "metodo": "interpolacion_vs30", "vs30_m_s": vs, "t": t,
            "cita": [_cita("17", "Tablas N° 4 y N° 5", "Interpolación lineal en función de Vs30 (nota de las tablas)."),
                     _cita("14.7", "Tabla N° 3")]}


def factor_c(T: float, TP: float, TL: float) -> dict:
    """Tabla N° 6 (art. 18.1). Para el cortante estático, art. 18.3: C = 2,5 en 0 ≤ T ≤ TP."""
    T = _num(T, "T", 0)
    TP, TL = _periodos_sitio(TP, TL)
    if T < 0.2 * TP:
        c, tramo = 1 + 7.5 * (T / TP), "T < 0,2TP"
    elif T <= TP:
        c, tramo = 2.5, "0,2TP ≤ T ≤ TP"
    elif T < TL:
        c, tramo = 2.5 * (TP / T), "TP < T < TL"
    else:
        c, tramo = 2.5 * (TP * TL / T ** 2), "T ≥ TL"
    return {"C": c, "tramo": tramo, "cita": _cita("18.1", "Tabla N° 6")}


def coeficiente_r(sistema: str, Ia: float, Ip: float) -> dict:
    if sistema not in TABLA10_R0:
        raise ValueError(f"Sistema no tabulado aquí; use uno de {sorted(TABLA10_R0)}.")
    for nombre, v in (("Ia", Ia), ("Ip", Ip)):
        if not 0 < _num(v, nombre) <= 1:
            raise ValueError(f"{nombre} debe estar en (0, 1] (Tablas N° 11 y N° 12).")
    r0 = TABLA10_R0[sistema]
    return {"R0": r0, "Ia": Ia, "Ip": Ip, "R": r0 * Ia * Ip, "cita": [_cita("22.1", "Tabla N° 10"), _cita("26")]}


def espectro(*, Z: float, U: float, S: float, R: float, TP: float, TL: float, periodos: list[float],
             g: float = 9.80665) -> dict:
    """Art. 41.1: Sa = Z·U·C·S/R · g. Devuelve la tabla periodo–aceleración (m/s²) para la configuración."""
    for nombre, v in (("Z", Z), ("U", U), ("S", S), ("R", R), ("g", g)):
        _positivo(v, nombre)
    _periodos_sitio(TP, TL)
    if not periodos or sorted(periodos) != list(periodos) or len(set(periodos)) != len(periodos):
        raise ValueError("R > 0 y periodos crecientes sin repetir.")
    filas = []
    for T in periodos:
        c = factor_c(T, TP, TL)["C"]
        filas.append({"T_s": T, "C": c, "Sa_m_s2": Z * U * c * S / R * g})
    return {"filas": filas, "parametros": {"Z": Z, "U": U, "S": S, "R": R, "TP": TP, "TL": TL, "g": g},
            "cita": [_cita("41.1"), _cita("18.1", "Tabla N° 6")]}


def deriva_admisible(material: str, *, regular: bool, R: float) -> dict:
    """Arts. 50–51: desplazamiento inelástico = 0,75R (regular) u 0,85R (irregular) × elástico; límite de Tabla N° 14."""
    if material not in TABLA14_DERIVA:
        raise ValueError(f"Material de la Tabla N° 14: {sorted(TABLA14_DERIVA)}.")
    _num(R, "R", 0)
    return {"limite": TABLA14_DERIVA[material], "factor_desplazamiento": (0.75 if regular else 0.85) * R,
            "cita": [_cita("50.1" if regular else "50.2"), _cita("51", "Tabla N° 14")]}


def cortante_minimo(*, regular: bool) -> dict:
    return {"fraccion_del_estatico": 0.80 if regular else 0.90, "cita": _cita("44.1")}


def excentricidad_accidental(dimension_perpendicular_m: float) -> dict:
    return {"e_m": 0.05 * _num(dimension_perpendicular_m, "dimensión", 0), "cita": _cita("45")}


# -- análisis estático (arts. 31, 34–36) --------------------------------------------------------------------------
FRACCION_CV = {"A": 0.50, "B": 0.50, "C": 0.25, "azotea": 0.25, "deposito": 0.80, "tanque": 1.00}
CT = {"porticos_concreto": 35, "porticos_con_muros_en_cajas": 45, "albanileria_o_muros": 60}


def fraccion_carga_viva(caso: str) -> dict:
    """Art. 31: fracción de la carga viva (o del contenido) que integra el peso sísmico P."""
    if caso not in FRACCION_CV:
        raise ValueError(f"Caso del art. 31: {sorted(FRACCION_CV)}.")
    return {"fraccion": FRACCION_CV[caso], "cita": _cita("31")}


def periodo_aproximado(hn_m: float, sistema: str) -> dict:
    """Art. 36.1: T = hn/CT, CT = 35, 45 o 60 según los elementos resistentes en la dirección."""
    if sistema not in CT:
        raise ValueError(f"Sistema del art. 36.1: {sorted(CT)}.")
    return {"T_s": _num(hn_m, "hn", 0) / CT[sistema], "CT": CT[sistema], "cita": _cita("36.1")}


def cortante_basal_estatico(*, Z, U, S, R, T, TP, TL, P_kN) -> dict:
    """Art. 34: V = Z·U·C·S/R·P con C = 2,5 si T ≤ TP (34.1, 18.3) y C/R ≥ 0,11 (34.2).

    Devuelve por separado el coeficiente bruto (C/R calculado) y el aplicado, max(C/R, 0,11): `V_kN` es el
    cortante utilizable con el mínimo del art. 34.2; `V_bruto_kN` se conserva solo como información.
    """
    for nombre, v in (("Z", Z), ("U", U), ("S", S), ("R", R), ("P", P_kN)):
        _positivo(v, nombre)
    T = _num(T, "T", 0)
    TP, TL = _periodos_sitio(TP, TL)
    c = 2.5 if T <= TP else factor_c(T, TP, TL)["C"]
    c_r = c / R
    aplicado = max(c_r, 0.11)
    return {"C": c, "C_R": c_r, "C_R_aplicado": aplicado, "cumple_C_R_minimo": c_r >= 0.11,
            "minimo_aplicado": c_r < 0.11, "V_bruto_kN": Z * U * c * S / R * P_kN, "V_kN": Z * U * S * aplicado * P_kN,
            "cita": [_cita("34.1"), _cita("34.2"), _cita("18.3")]}


def distribucion_altura(V_kN: float, pesos_kN: list[float], alturas_m: list[float], T: float) -> dict:
    """Art. 35: Fi = αi·V; αi = Pi·hi^k / Σ Pj·hj^k; k = 1 si T ≤ 0,5 s, k = 0,75 + 0,5T ≤ 2 si T > 0,5 s."""
    if len(pesos_kN) != len(alturas_m) or not pesos_kN:
        raise ValueError("Un peso por nivel con su altura sobre la base.")
    k = 1.0 if _num(T, "T", 0) <= 0.5 else min(0.75 + 0.5 * T, 2.0)
    w = [_num(p, "P", 0) * _num(h, "h", 0) ** k for p, h in zip(pesos_kN, alturas_m)]
    total = sum(w)
    if total <= 0:
        raise ValueError("Σ Pi·hi^k debe ser positiva.")
    return {"k": k, "F_kN": [V_kN * x / total for x in w], "cita": _cita("35")}

# -- Anexo II: Zonificación Sísmica Nacional (RM 183-2026-VIVIENDA) -----------------------------
_ANEXO_II_CACHE = None

def cargar_anexo_ii() -> dict:
    global _ANEXO_II_CACHE
    if _ANEXO_II_CACHE is None:
        p = Path(__file__).parent / "datos" / "anexo_ii_e030_2026.json"
        if not p.is_file():
            raise FileNotFoundError(f"Archivo de zonificación {p} no encontrado.")
        _ANEXO_II_CACHE = json.loads(p.read_text(encoding="utf-8"))
    return _ANEXO_II_CACHE


def listar_departamentos() -> list[str]:
    datos = cargar_anexo_ii()
    return sorted(list(datos.keys()))


def listar_provincias(departamento: str) -> list[str]:
    datos = cargar_anexo_ii()
    dep = departamento.strip().upper()
    if dep not in datos:
        raise ValueError(f"Departamento '{departamento}' no registrado en Anexo II.")
    return sorted(list(datos[dep].keys()))


def listar_distritos(departamento: str, provincia: str) -> list[dict]:
    datos = cargar_anexo_ii()
    dep = departamento.strip().upper()
    prov = provincia.strip().upper()
    if dep not in datos or prov not in datos[dep]:
        raise ValueError(f"Provincia '{provincia}' en '{departamento}' no registrada en Anexo II.")
    dist_map = datos[dep][prov]
    return [{"distrito": d, "zona": dist_map[d], "Z": TABLA1_Z[dist_map[d]]} for d in sorted(dist_map.keys())]


def consultar_zona_distrito(departamento: str, provincia: str, distrito: str) -> dict:
    datos = cargar_anexo_ii()
    dep = departamento.strip().upper()
    prov = provincia.strip().upper()
    dist = distrito.strip().upper()
    if dep not in datos or prov not in datos[dep] or dist not in datos[dep][prov]:
        raise ValueError(f"Distrito '{distrito}' ({provincia}, {departamento}) no hallado en Anexo II.")
    zona = datos[dep][prov][dist]
    return {
        "departamento": dep,
        "provincia": prov,
        "distrito": dist,
        "zona": zona,
        "Z": TABLA1_Z[zona],
        "cita": _cita("10.3", "Anexo II", f"Distrito {dist} asignado a Zona {zona} (Z = {TABLA1_Z[zona]}).")
    }


def generar_curva_espectro(*, Z: float, U: float, S: float, R: float, TP: float, TL: float,
                           T_max: float = 4.0, dT: float = 0.05, tipo: str = "C",
                           g: float = 9.80665) -> list[dict]:
    """Genera la curva espectral discretizada según el Art. 41.1 para importación en ETABS.

    tipo='C': factor de amplificación sísmica C(T).
    tipo='Sa': aceleración espectral Sa(T) en m/s2.
    """
    for nombre, v in (("Z", Z), ("U", U), ("S", S), ("R", R), ("g", g), ("T_max", T_max), ("dT", dT)):
        _positivo(v, nombre)
    _periodos_sitio(TP, TL)
    if tipo not in {"C", "Sa"}:
        raise ValueError("tipo debe ser 'C' (amplificación) o 'Sa' (aceleración).")

    puntos = []
    T = 0.0
    while T <= T_max + 1e-9:
        c = factor_c(T, TP, TL)["C"]
        sa = (Z * U * c * S / R) * g
        val = c if tipo == "C" else sa
        puntos.append({"T": round(T, 4), "C": round(c, 5), "Sa": round(sa, 5), "valor": round(val, 5)})
        T += dT
    return puntos


def exportar_archivo_espectro_etabs(ruta_txt=None, *, Z: float, U: float, S: float, R: float,
                                    TP: float, TL: float, T_max: float = 4.0, dT: float = 0.05,
                                    tipo: str = "C", g: float = 9.80665) -> str:
    """Genera el contenido del archivo .txt en formato de pares (Period, Value) para ETABS."""
    puntos = generar_curva_espectro(Z=Z, U=U, S=S, R=R, TP=TP, TL=TL, T_max=T_max, dT=dT, tipo=tipo, g=g)
    lineas = [
        f"; Espectro de Respuesta segun Norma E.030-2026 (RM 183-2026-VIVIENDA)",
        f"; Parametros: Z={Z:.2f}, U={U:.2f}, S={S:.2f}, R={R:.2f}, TP={TP:.2f} s, TL={TL:.2f} s",
        f"; Formato: Periodo(s)\t{tipo}",
    ]
    for p in puntos:
        lineas.append(f"{p['T']:8.4f}\t{p['valor']:10.5f}")
    contenido = "\n".join(lineas) + "\n"

    if ruta_txt is not None:
        p = Path(ruta_txt)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(contenido, encoding="utf-8")
    return contenido


def verificar_escala_cortante_dinamico(*, V_estatico: float, V_dinamico: float, regular: bool = True) -> dict:
    """Art. 44: Verificación de cortante basal mínimo dinámico vs. estático.

    Para estructuras regulares: V_din >= 80% V_est.
    Para estructuras irregulares: V_din >= 90% V_est.
    Si V_din < V_min, se debe escalar por factor_escala = V_min / V_din.
    """
    _positivo(V_estatico, "V_estatico")
    _positivo(V_dinamico, "V_dinamico")
    fraccion = 0.80 if regular else 0.90
    V_min = fraccion * V_estatico
    cumple = V_dinamico >= V_min - 1e-6
    factor_escala = 1.0 if cumple else (V_min / V_dinamico)
    return {
        "V_estatico": V_estatico,
        "V_dinamico": V_dinamico,
        "regular": regular,
        "fraccion": fraccion,
        "V_min": V_min,
        "cumple": cumple,
        "factor_escala": factor_escala,
        "cita": _cita("44.1", nota=f"Cortante dinámico mínimo = {int(fraccion*100)}% del cortante estático.")
    }

