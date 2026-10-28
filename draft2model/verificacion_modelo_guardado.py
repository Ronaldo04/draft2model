"""Relectura independiente de un EDB guardado, en instancia ETABS NUEVA y propia de solo lectura.

Tres capas separadas:
1. Expectativa pura (`expectativa_desde_plan`): se deriva de un plan 0.1 (`validar_plan`) o 0.2 de
   desarrollo (`validar_plan_superficies`) ya validado. El plan es solo FUENTE de expectativas; no
   autoriza construir ni ejecutar nada. Sin valores por defecto de ingeniería.
2. Comparación pura (`comparar`): observado frente a expectativa con igualdad discreta y criterios
   numéricos de LECTURA explícitos (umbral de ida y vuelta, no tolerancia de ingeniería).
3. Transporte y política (`VerificadorModeloGuardado`): copia privada del EDB con SHA256, script
   `scripts/verificar_modelo_guardado.ps1` (Windows PowerShell 5.1) que abre esa copia en una instancia
   nueva propia, refleja firmas, solo llama lectores y la cierra sin guardar; revalidación de huellas
   antes y después; resultado publicado sin sobrescribir.

Versión 0.2.0: además de geometría, propiedades, cargas y masa, relee apoyos, diafragmas, patrones,
casos (estático, modal Eigen, espectral), combinaciones, funciones espectrales, campos de tablas de
definición (por tabla de VISUALIZACIÓN, de solo lectura) y marcas de ejecución, e inventaría cada
operación del plan: comprobada, excluida con motivo trazable o sin lector (resultado incompleto).

Versión 0.3.0: además relee las propiedades nervadas (SetSlabRibbed) y casetonadas (SetSlabWaffle) con
sus parámetros de API exactos y la orientación local declarada por el plan (SetLocalAxes). Una orientación
del plan es obligatoria y el solicitante no la puede sustituir; la normal geométrica no se toma como eje.

Versión 0.4.0: (a) normalización dimensional EXPLÍCITA de lo leído hacia las unidades del plan (kN_m_C)
cuando ETABS reabre en otro sistema admitido ((N|kN)_(mm|cm|m)_C), con factores racionales exactos y
evidencia; una unidad no admitida o una magnitud sin conversión comprobada deja el resultado incompleto;
(b) aberturas del plan 0.3: GetOpening distingue hosts (False) de huecos (True) y el contorno/propiedad del
hueco se comparan como cualquier área; marcar Opening NO demuestra corte de rigidez ni mallado;
(c) diagnóstico del puente sin respuesta (p. ej. directiva de ejecución que impide `-File`).

Estados: `verificado` solo si no hay discrepancias ni lecturas incompletas en el alcance declarado.
Ejes locales de área sin criterio explícito quedan `sin_criterio` y nunca se afirman. Nada aprueba el
modelo ni certifica seguridad estructural.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import os
import re
import stat
from dataclasses import dataclass, replace
from fractions import Fraction
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import adaptador_etabs as ad
from . import operaciones_etabs as op
from .gestion_extraccion import json_desde_bytes

CONTRATO_RESULTADO = "draft2model.verificacion_modelo_guardado"
CONTRATO_EXPECTATIVA = "draft2model.expectativa_modelo_guardado"
VERSION = "0.4.0"
VERSION_LECTOR = "0.4.0"  # script y Python deben coincidir; una mezcla con lectores anteriores se rechaza
VERSIONES_RESULTADO_LEGIBLES = ("0.1.0", "0.2.0", "0.3.0", "0.4.0")
# Unidades: factores exactos de la unidad leída a la del plan (kN, m). Temperatura C, tiempo s y grados son
# idénticos en todos los sistemas admitidos. Cualquier otro sistema queda sin conversión comprobada.
FACTOR_FUERZA = {"N": Fraction(1, 1000), "kN": Fraction(1)}
FACTOR_LONGITUD = {"mm": Fraction(1, 1000), "cm": Fraction(1, 100), "m": Fraction(1)}
PATRON_UNIDADES = re.compile(r"(N|kN)_(mm|cm|m)_C")
# Exponentes (fuerza, longitud) de cada magnitud con dimensión; las demás son invariantes en los sistemas admitidos.
DIMENSIONES = {"longitud_m": (0, 1), "modulo_kN_m2": (1, -2), "peso_kN_m3": (1, -3), "presion_kN_m2": (1, -2),
               "fuerza_kN": (1, 0), "momento_kN_m": (1, 1), "fuerza_lineal_kN_m": (1, -1), "aceleracion_m_s2": (0, 1)}
# SF espectral [L/s²]: documentación CSI Response Spectrum y ensayo real180 de ETABS21.1,
# plan 1 m/s² -> GetLoads 1000 mm/s² (EDB reabierto N_mm_C); evidencia REAL_RELECTURA_180.
# Esta tabla conserva el rechazo por magnitud para futuras lecturas sin conversión demostrada.
SIN_CONVERSION_COMPROBADA = {}
# Parámetros de API de losas aligeradas (firmas reflejadas en ETABSv1 1.29.0.0). Se comparan con estos nombres.
PARAMETROS_ALIGERADO = {
    "nervada": {"OverallDepth": "longitud_m", "SlabThickness": "longitud_m", "StemWidthTop": "longitud_m",
                "StemWidthBot": "longitud_m", "RibSpacing": "longitud_m", "RibsParallelTo": None},
    "casetonada": {"OverallDepth": "longitud_m", "SlabThickness": "longitud_m", "StemWidthTop": "longitud_m",
                   "StemWidthBot": "longitud_m", "RibSpacingDir1": "longitud_m", "RibSpacingDir2": "longitud_m"},
}
SUBTIPO_ALIGERADO = {"Ribbed": "nervada", "Waffle": "casetonada"}
OPERACION = "verificar_modelo_guardado"
SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "verificar_modelo_guardado.ps1"
UNIDADES = "kN_m_C"
SHA = re.compile(r"[0-9a-f]{64}")
# Magnitudes de lectura: cada una exige un umbral absoluto explícito del solicitante (sin defaults).
MAGNITUDES = ("longitud_m", "modulo_kN_m2", "adimensional", "coeficiente_termico_1_C", "peso_kN_m3",
              "presion_kN_m2", "fuerza_kN", "momento_kN_m", "fuerza_lineal_kN_m", "angulo_deg",
              "frecuencia_hz", "tiempo_s", "aceleracion_m_s2")
MAX_UMBRAL_LECTURA = 1e-6  # por encima ya sería una tolerancia física/de ingeniería: se rechaza
CATEGORIAS = ("unidades", "pisos", "puntos", "frames", "areas", "propiedades_area", "propiedades_frame", "materiales",
              "cargas_area", "cargas_punto", "cargas_frame", "fuente_masa", "apoyos", "diafragmas", "patrones", "casos",
              "combinaciones", "funciones_espectrales", "tablas_dinamicas", "marcas_de_ejecucion", "aberturas")
# Leído y registrado, nunca afirmado: no hay expectativa en el plan ni representación verificada de «ninguno».
FUERA_DE_ALCANCE = ("diafragma_de_area", "subtipo_de_caso", "tipo_de_amortiguamiento_espectral", "combinacion_modal_oapi",
                    "abertura_sin_operacion_en_plan")
# Plan 0.4: lo que la relectura de malla NO afirma (sin getter o fuera del alcance de una relectura).
NO_AFIRMADOS_MALLA = ("masa_propia_por_elemento", "calidad_y_rigidez_de_malla", "efecto_estructural_del_diafragma")
DIRECCION_EJE = {4: 0, 5: 1, 6: 2}  # cargas globales completas X/Y/Z; 7-9 proyectadas y 10/11 gravedad no se suman como completas
EFECTO_ABERTURAS = "efecto_estructural_de_aberturas"  # persistencia del hueco ≠ corte de rigidez, malla o cargas netas
# Inventario de operaciones modificadoras: método -> categoría comprobada. Lo no listado queda «sin_lector».
INVENTARIO = {
    "cSapModel.SetPresentUnits": "unidades", "cStory.SetStories_2": "pisos",
    "cPropMaterial.SetMaterial": "materiales", "cPropMaterial.SetMPIsotropic": "materiales",
    "cPropMaterial.SetWeightAndMass": "materiales", "cPropArea.SetWall": "propiedades_area",
    "cPropArea.SetSlab": "propiedades_area", "cPropFrame.SetRectangle": "propiedades_frame",
    "cPropFrame.SetConcreteL": "propiedades_frame", "cFrameObj.SetInsertionPoint": "frames",
    "cPropArea.SetSlabRibbed": "propiedades_area", "cPropArea.SetSlabWaffle": "propiedades_area",
    "cAreaObj.SetLocalAxes": "areas", "cAreaObj.SetOpening": "aberturas",
    "cPointObj.AddCartesian": "puntos", "cFrameObj.AddByPoint": "frames", "cAreaObj.AddByPoint": "areas",
    "cLoadPatterns.Add": "patrones", "cPointObj.SetLoadForce": "cargas_punto",
    "cFrameObj.SetLoadDistributed": "cargas_frame", "cAreaObj.SetLoadUniform": "cargas_area",
    "cPropMaterial.SetMassSource_1": "fuente_masa", "cPointObj.SetRestraint": "apoyos",
    "cDiaphragm.SetDiaphragm": "diafragmas", "cPointObj.SetDiaphragm": "diafragmas",
    "cCaseStaticLinear.SetCase": "casos", "cCaseStaticLinear.SetLoads": "casos",
    "cCaseModalEigen.SetCase": "casos", "cCaseModalEigen.SetNumberModes": "casos", "cCaseModalEigen.SetParameters": "casos",
    "cCaseResponseSpectrum.SetCase": "casos", "cCaseResponseSpectrum.SetModalCase": "casos",
    "cCaseResponseSpectrum.SetLoads": "casos", "cCaseResponseSpectrum.SetEccentricity": "casos",
    "cCombo.Add": "combinaciones", "cCombo.SetCaseList": "combinaciones",
    "cAnalyze.SetRunCaseFlag": "marcas_de_ejecucion",
    "edicion_tabla:" + op.TABLA_FUNCION_RS: "funciones_espectrales",
    "edicion_tabla:" + op.TABLA_CASO_RS: "tablas_dinamicas",
    "edicion_tabla:" + op.TABLA_AMORTIGUAMIENTO_MODAL: "tablas_dinamicas",
    "edicion_tabla:" + op.TABLA_NO_UNIFORME: "cargas_liquidos",
}
EXCLUSIONES = {"cFile.Save": "El guardado se acredita por el SHA256 del EDB leído; leerlo no requiere otra relectura."}
# Campos de tabla comparados por tabla de VISUALIZACIÓN (magnitud o None = texto exacto). Period/Value de la función
# se comparan con cFunction.GetValues; Name es la clave de fila.
CAMPOS_TABLA = {op.TABLA_FUNCION_RS: {"DampRatio": "adimensional"},
                op.TABLA_CASO_RS: {"ModalCombo": None, "RigidResp": None},
                op.TABLA_AMORTIGUAMIENTO_MODAL: {"ConstDamp": "adimensional"},
                op.TABLA_NO_UNIFORME: {}}  # plan 0.5: comparación propia por clave compuesta (tabla_liquidos)
DIR_LIQUIDO = {"Global-X": (0, 1), "Global-Y": (1, 1), "Gravity": (2, -1)}  # componentes completas; Proj/Local no se reinterpretan
TIPO_CASO = {"cCaseStaticLinear.SetCase": "LinearStatic", "cCaseModalEigen.SetCase": "Modal",
             "cCaseResponseSpectrum.SetCase": "ResponseSpectrum"}


class ErrorVerificacion(ValueError):
    """Solicitud, expectativa o criterios inválidos; no se lee nada."""


# -- utilidades ------------------------------------------------------------------

def _bytes(data: Any) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2) + "\n").encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _finito(valor: Any) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _nuevo(ruta: Path, raw: bytes) -> None:
    with open(ruta, "xb") as archivo:
        archivo.write(raw)


def _regular(ruta: Path) -> Path:
    info = ruta.lstat()
    if (stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
        raise ad.ErrorEvidenciaEtabs("Archivo enlazado o no regular.")
    return ruta


def contorno_orientado_igual(esperado, observado):
    """Mismo ciclo orientado, incluso con distinto inicio; rechaza nodos repetidos."""
    if (not isinstance(esperado, list) or not isinstance(observado, list)
            or len(esperado) < 3 or len(esperado) != len(observado)
            or any(type(x) is not str for x in esperado + observado)
            or len(set(esperado)) != len(esperado) or len(set(observado)) != len(observado)):
        return False
    return any(observado[k:] + observado[:k] == esperado for k in range(len(observado)))


def carga_vertical_global(carga, categoria):
    """Dir10/11 es -Z real/proyectada (CSI incidente9398); conserva carga cruda."""
    result = dict(carga)
    if (result.get('csys') == 'Global' and result.get('dir') in (10, 11)
            and (categoria == 'cargas_area' or categoria == 'cargas_frame' and result.get('tipo') == 1)):
        result['dir'] = 6 if result['dir'] == 10 else 9
        for campo in (('valor',) if categoria == 'cargas_area' else ('val1', 'val2')):
            result[campo] = -result[campo]
    return result


# -- 1. expectativa pura ---------------------------------------------------------

def expectativa_desde_plan(plan: Any, *, ejes_locales_area: Any = None) -> dict:
    """Expectativa exacta desde un plan validado. `ejes_locales_area` = {area: {"angulo_deg", "avanzado"}} opcional."""
    if not isinstance(plan, dict):
        raise ErrorVerificacion("El plan debe ser un objeto JSON.")
    version = plan.get("version_contrato")
    if version == op.VERSION_PLAN:
        problemas = op.validar_plan(plan)
    elif version == op.VERSION_PLAN_SUPERFICIES:
        problemas = op.validar_plan_superficies(plan)
    elif version == getattr(op, "VERSION_PLAN_ABERTURAS", None) and hasattr(op, "validar_plan_aberturas"):
        problemas = op.validar_plan_aberturas(plan)
    elif version == getattr(op, "VERSION_PLAN_MALLA", None) and hasattr(op, "validar_plan_malla"):
        problemas = op.validar_plan_malla(plan)
    elif version == getattr(op, "VERSION_PLAN_LIQUIDOS", None) and hasattr(op, "validar_plan_liquidos"):
        problemas = op.validar_plan_liquidos(plan)
    else:
        problemas = ["Versión de plan no admitida; no se reinterpreta."]
    if problemas:
        raise ErrorVerificacion("Plan no válido como fuente de expectativas: " + "; ".join(problemas))
    nombres = {s["registra"]: s["debe_ser"] for o in plan["operaciones"] for s in o.get("salidas", [])}

    def val(v):
        if isinstance(v, dict) and set(v) == {"ref"}:
            return nombres[v["ref"]]
        if isinstance(v, list):
            return [val(x) for x in v]
        return v
    e = {"unidades": None, "pisos": None, "puntos": {}, "frames": {}, "areas": {}, "clase_area": {},
         "propiedades_area": {}, "propiedades_frame": {}, "materiales": {}, "cargas_area": [], "cargas_punto": [],
         "cargas_frame": [], "fuente_masa": None, "apoyos": {}, "diafragmas": {}, "diafragmas_puntos": {}, "patrones": {},
         "casos": {}, "combinaciones": {}, "funciones": {}, "tablas": {},
         "ejecucion": {"todos_desmarcados": False, "ejecutar": []}, "inventario": [], "ejes_plan": {}, "aberturas": {}}
    for o in plan["operaciones"]:
        m = o["metodo"] if o.get("metodo") != "edicion_tabla" else "edicion_tabla:" + o["tabla"]
        entrada = {"orden": o["orden"], "metodo": m, "fase": o["fase"], "origen": o["origen"]}
        if m in INVENTARIO:
            entrada.update(cobertura="comprobada", categoria=INVENTARIO[m])
        elif m in EXCLUSIONES:
            entrada.update(cobertura="excluida", motivo=EXCLUSIONES[m])
        elif not m.startswith("edicion_tabla:") and op.es_lectura(m):
            entrada.update(cobertura="excluida", motivo="Lectura del propio plan durante la construcción; no modifica el modelo.")
        else:
            entrada.update(cobertura="sin_lector", motivo="Operación modificadora sin lector ni exclusión trazable.")
        e["inventario"].append(entrada)
        if m.startswith("edicion_tabla:"):
            e["tablas"][o["tabla"]] = {"clave": o["clave"], "campos": list(o["campos"]), "registros": copy.deepcopy(o["registros"])}
            continue
        a = {x["nombre"]: val(x["valor"]) for x in o["argumentos"]}
        if m == "cSapModel.SetPresentUnits":
            e["unidades"] = a["Units"]["nombre"]
        elif m == "cStory.SetStories_2":
            e["pisos"] = {"base": a["BaseElevation"], "nombres": list(a["StoryNames"]), "alturas": list(a["StoryHeights"])}
        elif m == "cPropMaterial.SetMaterial":
            e["materiales"].setdefault(a["Name"], {})["tipo"] = {"nombre": a["MatType"]["nombre"], "valor": a["MatType"]["valor"]}
        elif m == "cPropMaterial.SetMPIsotropic":
            e["materiales"].setdefault(a["Name"], {}).update(E=a["E"], U=a["U"], A=a["A"])
        elif m == "cPropMaterial.SetWeightAndMass":
            if a["MyOption"] != 1:
                raise ErrorVerificacion("SetWeightAndMass con opción distinta de peso; sin expectativa definida.")
            e["materiales"].setdefault(a["Name"], {})["W"] = a["Value"]
        elif m in ("cPropArea.SetWall", "cPropArea.SetSlab"):
            losa = m.endswith("SetSlab")
            tipo = a["SlabType"] if losa else a["WallPropType"]
            e["propiedades_area"][a["Name"]] = {
                "clase": "losa" if losa else "muro", "subtipo": {"nombre": tipo["nombre"], "valor": tipo["valor"]},
                "shell": {"nombre": a["ShellType"]["nombre"], "valor": a["ShellType"]["valor"]},
                "material": a["MatProp"], "espesor": a["Thickness"]}
        elif m == "cPropFrame.SetRectangle":
            e["propiedades_frame"][a["Name"]] = {"material": a["MatProp"], "t3": a["T3"], "t2": a["T2"]}
        elif m == "cPropFrame.SetConcreteL":
            e["propiedades_frame"][a["Name"]] = {"material": a["MatProp"], "l": {
                "t3": a["T3"], "t2": a["T2"], "tf": a["Tf"], "twc": a["TwC"], "twt": a["TwT"],
                "espejo2": a["MirrorAbout2"], "espejo3": a["MirrorAbout3"]}}
        elif m == "cFrameObj.SetInsertionPoint":
            if a["CSys"] != "Global" or a["ItemType"]["nombre"] != "Objects" or a["Name"] not in e["frames"]:
                raise ErrorVerificacion("SetInsertionPoint no global, sobre grupo o sin frame previo; sin expectativa definida.")
            e["frames"][a["Name"]]["insercion"] = {"cardinal": a["CardinalPoint"], "mirror2": a["Mirror2"],
                                                   "stiff_transform": a["StiffTransform"], "offset1": list(a["Offset1"]),
                                                   "offset2": list(a["Offset2"]), "csys": a["CSys"]}
        elif m == "cPointObj.AddCartesian":
            if a["CSys"] != "Global":
                raise ErrorVerificacion("Punto en sistema no global; sin expectativa definida.")
            e["puntos"][a["UserName"]] = [a["X"], a["Y"], a["Z"]]
        elif m == "cFrameObj.AddByPoint":
            e["frames"][a["UserName"]] = {"puntos": [a["Point1"], a["Point2"]], "seccion": a["PropName"]}
        elif m == "cAreaObj.AddByPoint":
            e["areas"][a["UserName"]] = {"puntos": list(a["Point"]), "propiedad": a["PropName"]}
            e["clase_area"][a["UserName"]] = o["salidas"][0]["registra"].split(":", 1)[0]
        elif m == "cAreaObj.SetLoadUniform":
            e["cargas_area"].append({"objeto": a["Name"], "patron": a["LoadPat"], "csys": a["CSys"], "dir": a["Dir"],
                                     "valor": a["Value"], "origen": o["origen"]})
        elif m == "cPointObj.SetLoadForce":
            e["cargas_punto"].append({"objeto": a["Name"], "patron": a["LoadPat"], "csys": a["CSys"],
                                      "valores": list(a["Value"]), "origen": o["origen"]})
        elif m == "cFrameObj.SetLoadDistributed":
            if a["RelDist"] is not True:
                raise ErrorVerificacion("Carga distribuida con distancias absolutas; sin expectativa definida.")
            e["cargas_frame"].append({"objeto": a["Name"], "patron": a["LoadPat"], "tipo": a["MyType"], "csys": a["CSys"],
                                      "dir": a["Dir"], "rd1": a["Dist1"], "rd2": a["Dist2"], "val1": a["Val1"],
                                      "val2": a["Val2"], "origen": o["origen"]})
        elif m in ("cPropArea.SetSlabRibbed", "cPropArea.SetSlabWaffle"):
            tipo = "nervada" if m.endswith("Ribbed") else "casetonada"
            prop = e["propiedades_area"].get(a["Name"])
            if prop is None or prop["clase"] != "losa" or SUBTIPO_ALIGERADO.get(prop["subtipo"]["nombre"]) != tipo:
                raise ErrorVerificacion(f"{m} sin SetSlab previo del subtipo correspondiente; sin expectativa coherente.")
            if set(a) != {"Name", *PARAMETROS_ALIGERADO[tipo]}:
                raise ErrorVerificacion(f"{m} con parámetros no reconocidos.")
            prop["aligerado"] = {"tipo": tipo, "parametros": {k: a[k] for k in PARAMETROS_ALIGERADO[tipo]}}
            # ETABS21.1: el setter específico reemplaza GetSlab.Thickness por SlabThickness,
            # incluso si un plan anterior inició SetSlab con OverallDepth. Ensayo real181.
            prop["espesor"] = a["SlabThickness"]
        elif m == "cAreaObj.SetOpening":
            if a["ItemType"]["nombre"] != "Objects" or type(a["IsOpening"]) is not bool:
                raise ErrorVerificacion("SetOpening sobre grupo o con valor no booleano; sin expectativa definida.")
            if e["aberturas"].get(a["Name"], a["IsOpening"]) != a["IsOpening"]:
                raise ErrorVerificacion("SetOpening contradictorio para el mismo objeto; sin expectativa definida.")
            e["aberturas"][a["Name"]] = a["IsOpening"]
        elif m == "cAreaObj.SetLocalAxes":
            if a["ItemType"]["nombre"] != "Objects":
                raise ErrorVerificacion("SetLocalAxes sobre grupo o selección; sin expectativa definida.")
            e["ejes_plan"][a["Name"]] = {"angulo_deg": a["Ang"], "avanzado": None}
        elif m == "cAreaObj.GetLocalAxes" and o["fase"] != "verificacion":
            for v_ in o.get("verificar_valores", []):  # el plan declara explícitamente Advanced esperado
                if v_["parametro"] == "Advanced" and a["Name"] in e["ejes_plan"]:
                    e["ejes_plan"][a["Name"]]["avanzado"] = v_["esperado"]
        elif m == "cPointObj.SetRestraint":
            e["apoyos"][a["Name"]] = list(a["Value"])
        elif m == "cDiaphragm.SetDiaphragm":
            e["diafragmas"][a["Name"]] = a["SemiRigid"]
        elif m == "cPointObj.SetDiaphragm":
            e["diafragmas_puntos"][a["Name"]] = {"opcion": {"nombre": a["DiaphragmOption"]["nombre"], "valor": a["DiaphragmOption"]["valor"]},
                                                 "diafragma": a["DiaphragmName"]}
        elif m == "cLoadPatterns.Add":
            e["patrones"][a["Name"]] = {"tipo": {"nombre": a["MyType"]["nombre"], "valor": a["MyType"]["valor"]},
                                        "multiplicador": a["SelfWTMultiplier"]}
        elif m in TIPO_CASO:
            e["casos"][a["Name"]] = {"tipo": TIPO_CASO[m]}
        elif m == "cCaseStaticLinear.SetLoads":
            e["casos"][a["Name"]]["cargas"] = [{"tipo_carga": x, "nombre": n, "factor": f}
                                               for x, n, f in zip(a["LoadType"], a["LoadName"], a["SF"])]
        elif m == "cCaseModalEigen.SetNumberModes":
            e["casos"][a["Name"]]["modos"] = [a["MaxModes"], a["MinModes"]]
        elif m == "cCaseModalEigen.SetParameters":
            e["casos"][a["Name"]]["parametros"] = {"desplazamiento": a["EigenShiftFreq"], "corte": a["EigenCutOff"],
                                                   "tolerancia": a["EigenTol"], "automatico": a["AllowAutoFreqShift"]}
        elif m == "cCaseModalEigen.GetLoads" and o["fase"] != "verificacion":
            for v_ in o.get("verificar_valores", []):  # el plan declara explícitamente sus cargas iniciales esperadas
                if v_["parametro"] == "NumberLoads":
                    e["casos"][a["Name"]]["numero_cargas"] = v_["esperado"]
        elif m == "cCaseResponseSpectrum.SetModalCase":
            e["casos"][a["Name"]]["modal"] = a["ModalCase"]
        elif m == "cCaseResponseSpectrum.SetLoads":
            e["casos"][a["Name"]]["cargas"] = [{"nombre": n, "funcion": f, "factor": s, "csys": c, "angulo": g}
                                               for n, f, s, c, g in zip(a["LoadName"], a["Func"], a["SF"], a["CSys"], a["Ang"])]
        elif m == "cCaseResponseSpectrum.SetEccentricity":
            e["casos"][a["Name"]]["excentricidad"] = a["Eccen"]
        elif m == "cCombo.Add":
            e["combinaciones"][a["Name"]] = {"tipo": a["ComboType"], "casos": []}
        elif m == "cCombo.SetCaseList":
            e["combinaciones"][a["Name"]]["casos"].append({"tipo": {"nombre": a["CNameType"]["nombre"], "valor": a["CNameType"]["valor"]},
                                                           "nombre": a["CName"], "factor": a["SF"]})
        elif m == "cAnalyze.SetRunCaseFlag":
            if a["All"] is True:
                if a["Name"] != "" or a["Run"] is not False or e["ejecucion"]["ejecutar"]:
                    raise ErrorVerificacion("Marca global de ejecución no reconocida; sin expectativa definida.")
                e["ejecucion"]["todos_desmarcados"] = True
            elif a["Run"] is True:
                e["ejecucion"]["ejecutar"].append(a["Name"])
            else:
                raise ErrorVerificacion("Desmarcado individual no reconocido; sin expectativa definida.")
        elif m == "cPropMaterial.SetMassSource_1":
            e["fuente_masa"] = {"incluir_elementos": a["IncludeElements"], "incluir_masa_adicional": a["IncludeAddedMass"],
                                "incluir_cargas": a["IncludeLoads"], "factores": dict(zip(a["LoadPat"], a["sf"]))}
            if len(e["fuente_masa"]["factores"]) != len(a["LoadPat"]):
                raise ErrorVerificacion("Fuente de masa con patrones repetidos.")
    if e["unidades"] != UNIDADES or e["pisos"] is None or e["fuente_masa"] is None:
        raise ErrorVerificacion("El plan no fija unidades kN_m_C, pisos o fuente de masa explícitos.")
    for nombre, mat in e["materiales"].items():
        if set(mat) != {"tipo", "E", "U", "A", "W"}:
            raise ErrorVerificacion(f"Material {nombre} sin todas sus asignaciones; expectativa incompleta.")
    _expectativa_tablas(e)
    for nombre, prop in e["propiedades_area"].items():
        if prop["clase"] == "losa" and prop["subtipo"]["nombre"] in SUBTIPO_ALIGERADO and "aligerado" not in prop:
            raise ErrorVerificacion(f"Losa {nombre} {prop['subtipo']['nombre']} sin parámetros de aligerado en el plan.")
    solicitados = _validar_ejes(ejes_locales_area, e["areas"]) or {}
    for area, plan_ejes in e["ejes_plan"].items():
        pedido = solicitados.get(area)
        if pedido is not None and (pedido["angulo_deg"] != plan_ejes["angulo_deg"]
                                   or (plan_ejes["avanzado"] is not None and pedido["avanzado"] != plan_ejes["avanzado"])):
            raise ErrorVerificacion(f"ejes_locales_area de {area} contradice la orientación declarada por el plan; no se sustituye.")
    combinados = {**solicitados, **copy.deepcopy(e["ejes_plan"])}
    e["ejes_locales_area"] = combinados or None
    e["ejes_origen"] = {a_: ("plan" if a_ in e["ejes_plan"] else "solicitante") for a_ in combinados}
    e["origen_plan"] = {"version_contrato": plan["version_contrato"], "huella_plan": plan["huella_plan"],
                        "origen": copy.deepcopy(plan["origen"]), "destino_guardado": plan["opciones"]["destino_guardado"]}
    if version in (getattr(op, "VERSION_PLAN_MALLA", None), getattr(op, "VERSION_PLAN_LIQUIDOS", None)):
        e["malla"] = _expectativa_malla(plan, e)  # solo 0.4/0.5: las expectativas 0.1-0.3 no cambian de forma
    if version == getattr(op, "VERSION_PLAN_LIQUIDOS", None):
        liq = plan["liquidos"]
        e["liquidos"] = {"aplicabilidad": liq["aplicabilidad"], "patrones": list(liq["patrones"]),
                         "hosts": [{k: copy.deepcopy(h[k]) for k in ("declaracion", "patron", "superficie", "triangulos", "origen_momentos_m",
                                                                     "fuerza_fuente_kn", "momento_fuente_kn_m")} for h in liq["hosts"]],
                         "filas": copy.deepcopy(liq["filas"])}
    return {"contrato": CONTRATO_EXPECTATIVA, "version_contrato": VERSION, **e}


def _expectativa_malla(plan: dict, e: dict) -> dict:
    """Expectativa de malla 0.4 desde la sección `malla`/`conservacion` del plan validado; rechaza incoherencias.

    Solo nombres, normales, áreas netas FUENTE y resultantes esperadas: la comprobación posterior usa coordenadas,
    contornos, longitudes y cargas LEÍDAS del EDB reabierto, no las áreas de triángulos del plan.
    """
    malla, cons = plan.get("malla"), plan.get("conservacion")
    if not isinstance(malla, dict) or not isinstance(cons, dict):
        raise ErrorVerificacion("Plan 0.4 sin secciones malla/conservacion; expectativa de malla incompleta.")
    superficies = {n for n, c in e["clase_area"].items() if c == "superficie"}
    hosts = {}
    for h, info in sorted(malla["hosts"].items()):
        tris = list(info["triangulos"])
        if not tris or not set(tris) <= superficies:
            raise ErrorVerificacion(f"Host {h}: triángulos de la malla sin AddByPoint en el plan; expectativa incoherente.")
        hosts[h] = {"triangulos": tris, "normal": list(info["normal_unitaria"]), "area_neta_m2": info["area_neta_m2"],
                    "aberturas": list(info.get("aberturas", []))}
    asignados = [t for x in hosts.values() for t in x["triangulos"]]
    if len(set(asignados)) != len(asignados) or set(asignados) != superficies:
        raise ErrorVerificacion("Cobertura de triángulos por host incoherente con las áreas creadas por el plan.")
    malla_a_csi = {}
    for csi, d in malla["nodos_derivados"].items():
        for ident in [d["nodo_malla"], *d.get("alias", [])]:
            malla_a_csi[ident] = csi
    conexiones = []
    for c in malla.get("conexiones", []):
        resueltos, sin_resolver = [], []
        for n in c["nodos_compartidos"]:
            csi = malla_a_csi.get(n, n if n in e["puntos"] else None)
            (resueltos if csi is not None else sin_resolver).append(csi or n)
        conexiones.append({"id": c["id"], "nodos": resueltos, "sin_resolver": sin_resolver})
    subframes = []
    for r in malla.get("frames_subdivididos", []):
        if len(r["subframes"]) != len(r["nodos"]) - 1 or not set(r["subframes"]) <= set(e["frames"]) or r["frame"] in e["frames"]:
            raise ErrorVerificacion(f"Subdivisión de {r['frame']} incoherente con los frames creados por el plan.")
        for k, s in enumerate(r["subframes"]):
            if e["frames"][s]["puntos"] != [r["nodos"][k], r["nodos"][k + 1]]:
                raise ErrorVerificacion(f"Subframe {s} con extremos distintos de la subdivisión declarada.")
        subframes.append({"frame": r["frame"], "nodos": list(r["nodos"]), "subframes": list(r["subframes"])})
    cargas = []
    for c in cons.get("cargas", []):
        cat = "cargas_area" if c["objetivo_tipo"] == "superficie" else "cargas_frame"
        prefijo = f"$.cargas.{c['carga']}@"  # una operación por parte (operaciones_etabs 0.4)
        partes = [x for x in e[cat] if x["origen"].startswith(prefijo)]
        if not partes or {x["objeto"] for x in partes} != set(c["partes"]) or len({x["patron"] for x in partes}) != 1:
            raise ErrorVerificacion(f"Carga {c['carga']}: partes declaradas en conservación distintas de las operaciones del plan.")
        cargas.append({"carga": c["carga"], "categoria": cat, "objetivo": c["objetivo"], "patron": partes[0]["patron"],
                       "partes": sorted(c["partes"]), "fuerza_kN": list(c["fuerza_esperada_kN"]),
                       "momento_kNm": list(c["momento_esperado_kNm"])})
    return {"hosts": hosts, "conexiones": conexiones, "subframes": subframes, "cargas": cargas,
            "cortes_nivel": copy.deepcopy(malla.get("cortes_nivel")), "huella_preparacion": malla["huella_preparacion"]}


def _expectativa_tablas(e: dict) -> None:
    """Funciones y amortiguamientos desde las filas que el plan escribe; sin valores supuestos."""
    # Una tabla sin campos de relectura definidos queda «sin_lector» en el inventario (resultado incompleto).
    funcion = e["tablas"].get(op.TABLA_FUNCION_RS)
    for fila in (funcion or {}).get("registros", []):
        f = e["funciones"].setdefault(fila["Name"], {"periodos": [], "valores": [], "amortiguamientos": set()})
        f["periodos"].append(float(fila["Period"]))
        f["valores"].append(float(fila["Value"]))
        f["amortiguamientos"].add(float(fila["DampRatio"]))
    for nombre, f in e["funciones"].items():
        if len(f["amortiguamientos"]) != 1:
            raise ErrorVerificacion(f"Función {nombre} con amortiguamientos distintos por fila; sin expectativa única.")
        f["amortiguamiento"] = f.pop("amortiguamientos").pop()
    damping = e["tablas"].get(op.TABLA_AMORTIGUAMIENTO_MODAL)
    for fila in (damping or {}).get("registros", []):
        if fila["Name"] not in e["casos"] or e["casos"][fila["Name"]]["tipo"] != "ResponseSpectrum":
            raise ErrorVerificacion("Amortiguamiento de un caso espectral inexistente en el plan.")
        e["casos"][fila["Name"]]["amortiguamiento"] = float(fila["ConstDamp"])


def _validar_ejes(ejes: Any, areas: dict) -> dict | None:
    if ejes is None:
        return None
    if not isinstance(ejes, dict) or not ejes or not set(ejes) <= set(areas):
        raise ErrorVerificacion("ejes_locales_area debe referirse solo a áreas del plan.")
    for nombre, item in ejes.items():
        if (not isinstance(item, dict) or set(item) != {"angulo_deg", "avanzado"} or not _finito(item["angulo_deg"])
                or type(item["avanzado"]) is not bool):
            raise ErrorVerificacion(f"Criterio de ejes de {nombre}: se requieren angulo_deg finito y avanzado booleano.")
    return copy.deepcopy(ejes)


def validar_criterios(criterios: Any) -> dict:
    """Umbrales de LECTURA explícitos: {"relativo": r, "absolutos": {magnitud: a}}; todas las magnitudes, sin defaults."""
    if not isinstance(criterios, dict) or set(criterios) != {"relativo", "absolutos"}:
        raise ErrorVerificacion("criterios requiere exactamente 'relativo' y 'absolutos'; no hay valores por defecto.")
    r, absolutos = criterios["relativo"], criterios["absolutos"]
    if not _finito(r) or not 0 <= r <= MAX_UMBRAL_LECTURA:
        raise ErrorVerificacion(f"'relativo' debe estar en [0, {MAX_UMBRAL_LECTURA}]; es un umbral de lectura, no de ingeniería.")
    if not isinstance(absolutos, dict) or set(absolutos) != set(MAGNITUDES):
        raise ErrorVerificacion("'absolutos' debe declarar exactamente: " + ", ".join(MAGNITUDES))
    for magnitud, valor in absolutos.items():
        if not _finito(valor) or not 0 <= valor <= MAX_UMBRAL_LECTURA:
            raise ErrorVerificacion(f"Umbral absoluto de {magnitud} fuera de [0, {MAX_UMBRAL_LECTURA}] (lectura, no ingeniería).")
    return {"relativo": r, "absolutos": dict(absolutos)}


def consulta_desde_expectativa(exp: dict) -> dict:
    """Solo NOMBRES de propiedades a consultar; ningún valor esperado viaja al lector."""
    pa = exp["propiedades_area"]
    casos = exp["casos"]
    return {"losas": sorted(n for n, p in pa.items() if p["clase"] == "losa"),
            "losas_nervadas": sorted(n for n, p in pa.items() if p.get("aligerado", {}).get("tipo") == "nervada"),
            "losas_casetonadas": sorted(n for n, p in pa.items() if p.get("aligerado", {}).get("tipo") == "casetonada"),
            "muros": sorted(n for n, p in pa.items() if p["clase"] == "muro"),
            "rectangulos": sorted(n for n, p in exp["propiedades_frame"].items() if "l" not in p), "materiales": sorted(exp["materiales"]),
            "diafragmas": sorted(exp["diafragmas"]), "patrones": sorted(exp["patrones"]),
            "casos_estaticos": sorted(n for n, c in casos.items() if c["tipo"] == "LinearStatic"),
            "casos_modales": sorted(n for n, c in casos.items() if c["tipo"] == "Modal"),
            "casos_espectrales": sorted(n for n, c in casos.items() if c["tipo"] == "ResponseSpectrum"),
            "combinaciones": sorted(exp["combinaciones"]), "funciones": sorted(exp["funciones"]),
            "tablas": sorted(t for t in exp["tablas"] if t in CAMPOS_TABLA),
            # Claves opcionales (configuración 0.5): solo si el plan crea secciones L o inserciones.
            **({"secciones_l": sorted(n for n, p in exp["propiedades_frame"].items() if "l" in p)}
               if any("l" in p for p in exp["propiedades_frame"].values()) else {}),
            **({"insercion_frames": sorted(n for n, f in exp["frames"].items() if "insercion" in f)}
               if any("insercion" in f for f in exp["frames"].values()) else {})}


# -- 2. comparación pura ----------------------------------------------------------

def validar_observado(obs: Any, consulta: dict) -> None:
    """Esquema estricto de lo leído; cualquier forma inesperada se trata como respuesta manipulada o truncada."""
    def falla(motivo):
        raise ad.ErrorEvidenciaEtabs("Lectura observada inválida: " + motivo)

    def nombres(v, ruta):
        if not isinstance(v, list) or not all(isinstance(x, str) and x for x in v) or len(set(v)) != len(v):
            falla(ruta + " requiere lista de nombres únicos")
        return v

    def nums(v, n, ruta):
        if not isinstance(v, list) or (n is not None and len(v) != n) or not all(_finito(x) for x in v):
            falla(ruta + " requiere números finitos")

    def enum(v, ruta):
        if not isinstance(v, dict) or set(v) != {"nombre", "valor"} or not isinstance(v["nombre"], str) or type(v["valor"]) is not int:
            falla(ruta + " requiere enumerado {nombre, valor}")
    claves = {"unidades", "version_etabs", "pisos", "puntos", "frames", "areas", "cargas_area", "cargas_punto",
              "cargas_frame", "materiales", "propiedades_area", "propiedades_frame", "fuente_masa", "retornos_no_cero",
              "apoyos", "diafragmas_puntos", "diafragmas_areas", "diafragmas", "patrones", "casos", "combinaciones",
              "funciones", "tablas", "ejecucion"}
    if not isinstance(obs, dict) or set(obs) != claves:
        falla("claves raíz")
    if (not isinstance(obs["unidades"], str) or not re.fullmatch(r"[A-Za-z]+_[A-Za-z]+_[A-Za-z]+", obs["unidades"])
            or not isinstance(obs["version_etabs"], str)):
        falla("unidades o versión")
    p = obs["pisos"]
    if not isinstance(p, dict) or set(p) != {"base", "nombres", "elevaciones", "alturas"} or not _finito(p["base"]):
        falla("pisos")
    nombres(p["nombres"], "pisos.nombres")
    nums(p["elevaciones"], len(p["nombres"]), "pisos.elevaciones")
    nums(p["alturas"], len(p["nombres"]), "pisos.alturas")
    pts = obs["puntos"]
    if not isinstance(pts, dict) or set(pts) != {"nombres", "coordenadas"}:
        falla("puntos")
    if not isinstance(pts["coordenadas"], dict) or set(pts["coordenadas"]) - set(nombres(pts["nombres"], "puntos.nombres")):
        falla("puntos.coordenadas fuera de la lista")
    for n, c in pts["coordenadas"].items():
        nums(c, 3, "puntos.coordenadas." + n)
    fr = obs["frames"]
    if not isinstance(fr, dict) or set(fr) != {"nombres", "puntos", "secciones"} | ({"insercion"} if "insercion_frames" in consulta else set()):
        falla("frames")
    if "insercion_frames" in consulta:
        if not isinstance(fr["insercion"], dict) or set(fr["insercion"]) - set(consulta["insercion_frames"]):
            falla("frames.insercion fuera de la consulta")
        for n, d in fr["insercion"].items():
            if (not isinstance(d, dict) or set(d) != {"cardinal", "mirror2", "stiff_transform", "offset1", "offset2", "csys"}
                    or type(d["cardinal"]) is not int or type(d["mirror2"]) is not bool or type(d["stiff_transform"]) is not bool
                    or not isinstance(d["csys"], str)):
                falla("frames.insercion." + n)
            nums(d["offset1"], 3, "insercion.offset1")
            nums(d["offset2"], 3, "insercion.offset2")
    lista = set(nombres(fr["nombres"], "frames.nombres"))
    for clave in ("puntos", "secciones"):
        if not isinstance(fr[clave], dict) or set(fr[clave]) - lista:
            falla("frames." + clave)
    for n, v in fr["puntos"].items():
        if not isinstance(v, list) or len(v) != 2 or not all(isinstance(x, str) for x in v):
            falla("frames.puntos." + n)
    if not all(isinstance(v, str) for v in fr["secciones"].values()):
        falla("frames.secciones")
    ar = obs["areas"]
    if not isinstance(ar, dict) or set(ar) != {"nombres", "puntos", "propiedades", "ejes", "aberturas"}:
        falla("areas")
    lista = set(nombres(ar["nombres"], "areas.nombres"))
    if not all(type(x) is bool for x in ar["aberturas"].values()) if isinstance(ar["aberturas"], dict) else True:
        falla("areas.aberturas")
    for clave in ("puntos", "propiedades", "ejes", "aberturas"):
        if not isinstance(ar[clave], dict) or set(ar[clave]) - lista:
            falla("areas." + clave)
    for n, v in ar["puntos"].items():
        if not isinstance(v, list) or not v or not all(isinstance(x, str) for x in v):
            falla("areas.puntos." + n)
    for n, v in ar["ejes"].items():
        if not isinstance(v, dict) or set(v) != {"angulo_deg", "avanzado"} or not _finito(v["angulo_deg"]) or type(v["avanzado"]) is not bool:
            falla("areas.ejes." + n)
    if not all(isinstance(v, str) for v in ar["propiedades"].values()):
        falla("areas.propiedades")
    for cat, campos in (("cargas_area", {"objeto", "patron", "csys", "dir", "valor"}),
                        ("cargas_punto", {"objeto", "patron", "csys", "valores"}),
                        ("cargas_frame", {"objeto", "patron", "tipo", "csys", "dir", "rd1", "rd2", "val1", "val2"})):
        tabla = obs[cat]
        objetos = {"cargas_area": ar["nombres"], "cargas_punto": pts["nombres"], "cargas_frame": fr["nombres"]}[cat]
        if not isinstance(tabla, dict) or set(tabla) - set(objetos):
            falla(cat + " sobre objetos no listados")
        for n, items in tabla.items():
            if not isinstance(items, list):
                falla(cat + "." + n)
            for it in items:
                if not isinstance(it, dict) or set(it) != campos or not all(isinstance(it[k], str) for k in ("objeto", "patron", "csys")):
                    falla(cat + "." + n + " campos")
                if cat == "cargas_punto":
                    nums(it["valores"], 6, cat)
                else:
                    for k in campos - {"objeto", "patron", "csys", "dir", "tipo"}:
                        nums([it[k]], 1, cat + "." + k)
                    for k in campos & {"dir", "tipo"}:
                        if type(it[k]) is not int:
                            falla(cat + "." + k)
    mat = obs["materiales"]
    if not isinstance(mat, dict) or set(mat) != {"nombres", "detalle"} or not isinstance(mat["detalle"], dict):
        falla("materiales")
    nombres(mat["nombres"], "materiales.nombres")
    if set(mat["detalle"]) - set(consulta["materiales"]):
        falla("materiales.detalle fuera de la consulta")
    for n, d in mat["detalle"].items():
        if not isinstance(d, dict) or set(d) != {"tipo", "E", "U", "A", "G", "W", "M"}:
            falla("materiales.detalle." + n)
        enum(d["tipo"], "materiales.tipo")
        nums([d[k] for k in ("E", "U", "A", "G", "W", "M")], 6, "materiales." + n)
    pa = obs["propiedades_area"]
    if not isinstance(pa, dict) or set(pa) != {"nombres", "losas", "muros", "nervadas", "casetonadas"}:
        falla("propiedades_area")
    for clase, tipo in (("nervadas", "nervada"), ("casetonadas", "casetonada")):
        if not isinstance(pa[clase], dict) or set(pa[clase]) - set(consulta["losas_" + clase]):
            falla("propiedades_area." + clase + " fuera de la consulta")
        for n, d in pa[clase].items():
            if not isinstance(d, dict) or set(d) != set(PARAMETROS_ALIGERADO[tipo]):
                falla("propiedades_area." + clase + "." + n)
            for k, magnitud in PARAMETROS_ALIGERADO[tipo].items():
                if magnitud is None:
                    if type(d[k]) is not int:
                        falla("propiedades_area." + n + "." + k)
                else:
                    nums([d[k]], 1, "propiedades_area." + n + "." + k)
    nombres(pa["nombres"], "propiedades_area.nombres")
    for clase in ("losas", "muros"):
        if not isinstance(pa[clase], dict) or set(pa[clase]) - set(consulta[clase]):
            falla("propiedades_area." + clase + " fuera de la consulta")
        for n, d in pa[clase].items():
            if not isinstance(d, dict) or set(d) != {"subtipo", "shell", "material", "espesor"} or not isinstance(d["material"], str):
                falla("propiedades_area." + n)
            enum(d["subtipo"], "subtipo")
            enum(d["shell"], "shell")
            nums([d["espesor"]], 1, "espesor")
    pf = obs["propiedades_frame"]
    if (not isinstance(pf, dict) or set(pf) != {"nombres", "rectangulos"} | ({"secciones_l"} if "secciones_l" in consulta else set())
            or not isinstance(pf["rectangulos"], dict)):
        falla("propiedades_frame")
    if "secciones_l" in consulta:
        if not isinstance(pf["secciones_l"], dict) or set(pf["secciones_l"]) - set(consulta["secciones_l"]):
            falla("propiedades_frame.secciones_l fuera de la consulta")
        for n, d in pf["secciones_l"].items():
            if (not isinstance(d, dict) or set(d) != {"material", "t3", "t2", "tf", "twc", "twt", "espejo2", "espejo3"}
                    or not isinstance(d["material"], str) or type(d["espejo2"]) is not bool or type(d["espejo3"]) is not bool):
                falla("propiedades_frame.secciones_l." + n)
            nums([d[k] for k in ("t3", "t2", "tf", "twc", "twt")], 5, "seccion_l")
    nombres(pf["nombres"], "propiedades_frame.nombres")
    if set(pf["rectangulos"]) - set(consulta["rectangulos"]):
        falla("propiedades_frame fuera de la consulta")
    for n, d in pf["rectangulos"].items():
        if not isinstance(d, dict) or set(d) != {"material", "t3", "t2"} or not isinstance(d["material"], str):
            falla("propiedades_frame." + n)
        nums([d["t3"], d["t2"]], 2, "rectangulo")
    fm = obs["fuente_masa"]
    if (not isinstance(fm, dict) or set(fm) != {"incluir_elementos", "incluir_masa_adicional", "incluir_cargas", "patrones", "factores"}
            or not all(type(fm[k]) is bool for k in ("incluir_elementos", "incluir_masa_adicional", "incluir_cargas"))
            or not isinstance(fm["patrones"], list) or not all(isinstance(x, str) for x in fm["patrones"])):
        falla("fuente_masa")
    nums(fm["factores"], len(fm["patrones"]), "fuente_masa.factores")
    _validar_observado_configuracion(obs, consulta, falla, nombres, nums, enum)
    rn = obs["retornos_no_cero"]
    if not isinstance(rn, list) or not all(isinstance(x, dict) and set(x) == {"metodo", "objeto", "codigo"}
                                           and isinstance(x["metodo"], str) and isinstance(x["objeto"], str)
                                           and type(x["codigo"]) is int and x["codigo"] != 0 for x in rn):
        falla("retornos_no_cero")


def _validar_observado_configuracion(obs, consulta, falla, nombres, nums, enum):
    def mapa(v, ruta, permitidos):
        if not isinstance(v, dict) or set(v) - set(permitidos):
            falla(ruta + " con nombres fuera de la lista o consulta")
        return v
    puntos, areas = obs["puntos"]["nombres"], obs["areas"]["nombres"]
    for n, r in mapa(obs["apoyos"], "apoyos", puntos).items():
        if not isinstance(r, list) or len(r) != 6 or not all(type(x) is bool for x in r):
            falla("apoyos." + n)
    for n, d in mapa(obs["diafragmas_puntos"], "diafragmas_puntos", puntos).items():
        if not isinstance(d, dict) or set(d) != {"opcion", "diafragma"} or not isinstance(d["diafragma"], str):
            falla("diafragmas_puntos." + n)
        enum(d["opcion"], "diafragmas_puntos.opcion")
    if not all(isinstance(x, str) for x in mapa(obs["diafragmas_areas"], "diafragmas_areas", areas).values()):
        falla("diafragmas_areas")
    d = obs["diafragmas"]
    if not isinstance(d, dict) or set(d) != {"nombres", "semirrigido"}:
        falla("diafragmas")
    nombres(d["nombres"], "diafragmas.nombres")
    if not all(type(x) is bool for x in mapa(d["semirrigido"], "diafragmas.semirrigido", consulta["diafragmas"]).values()):
        falla("diafragmas.semirrigido")
    p = obs["patrones"]
    if not isinstance(p, dict) or set(p) != {"nombres", "detalle"}:
        falla("patrones")
    nombres(p["nombres"], "patrones.nombres")
    for n, x in mapa(p["detalle"], "patrones.detalle", consulta["patrones"]).items():
        if not isinstance(x, dict) or set(x) != {"tipo", "multiplicador"}:
            falla("patrones." + n)
        enum(x["tipo"], "patrones.tipo")
        nums([x["multiplicador"]], 1, "patrones.multiplicador")
    c = obs["casos"]
    if not isinstance(c, dict) or set(c) != {"nombres", "tipos", "estaticos", "modales", "espectrales"}:
        falla("casos")
    lista = nombres(c["nombres"], "casos.nombres")
    for n, x in mapa(c["tipos"], "casos.tipos", lista).items():
        if not isinstance(x, dict) or set(x) != {"tipo", "subtipo"} or type(x["subtipo"]) is not int:
            falla("casos.tipos." + n)
        enum(x["tipo"], "casos.tipo")
    for n, cargas in mapa(c["estaticos"], "casos.estaticos", consulta["casos_estaticos"]).items():
        if not isinstance(cargas, list) or not all(isinstance(y, dict) and set(y) == {"tipo_carga", "nombre", "factor"}
                                                   and isinstance(y["tipo_carga"], str) and isinstance(y["nombre"], str)
                                                   and _finito(y["factor"]) for y in cargas):
            falla("casos.estaticos." + n)
    for n, x in mapa(c["modales"], "casos.modales", consulta["casos_modales"]).items():
        if (not isinstance(x, dict) or set(x) != {"modos", "desplazamiento", "corte", "tolerancia", "automatico", "numero_cargas"}
                or not isinstance(x["modos"], list) or len(x["modos"]) != 2 or not all(type(y) is int for y in x["modos"])
                or type(x["automatico"]) is not int or type(x["numero_cargas"]) is not int):
            falla("casos.modales." + n)
        nums([x["desplazamiento"], x["corte"], x["tolerancia"]], 3, "casos.modales")
    for n, x in mapa(c["espectrales"], "casos.espectrales", consulta["casos_espectrales"]).items():
        if (not isinstance(x, dict) or set(x) != {"modal", "cargas", "excentricidad", "amortiguamiento", "tipo_amortiguamiento",
                                                   "comb_modal"} or not isinstance(x["modal"], str)
                or type(x["tipo_amortiguamiento"]) is not int or not isinstance(x["cargas"], list)):
            falla("casos.espectrales." + n)
        for y in x["cargas"]:
            if (not isinstance(y, dict) or set(y) != {"nombre", "funcion", "factor", "csys", "angulo"}
                    or not all(isinstance(y[k], str) for k in ("nombre", "funcion", "csys"))):
                falla("casos.espectrales.cargas")
            nums([y["factor"], y["angulo"]], 2, "casos.espectrales.cargas")
        nums([x["excentricidad"], x["amortiguamiento"]], 2, "casos.espectrales")
        cm = x["comb_modal"]
        if not isinstance(cm, dict) or set(cm) != {"tipo", "f1", "f2", "periodica_rigida", "td"} \
                or type(cm["tipo"]) is not int or type(cm["periodica_rigida"]) is not int:
            falla("casos.espectrales.comb_modal")
        nums([cm["f1"], cm["f2"], cm["td"]], 3, "comb_modal")
    k = obs["combinaciones"]
    if not isinstance(k, dict) or set(k) != {"nombres", "detalle"}:
        falla("combinaciones")
    nombres(k["nombres"], "combinaciones.nombres")
    for n, x in mapa(k["detalle"], "combinaciones.detalle", consulta["combinaciones"]).items():
        if not isinstance(x, dict) or set(x) != {"tipo", "casos"} or type(x["tipo"]) is not int or not isinstance(x["casos"], list):
            falla("combinaciones." + n)
        for y in x["casos"]:
            if not isinstance(y, dict) or set(y) != {"tipo", "nombre", "factor"} or not isinstance(y["nombre"], str):
                falla("combinaciones.casos")
            enum(y["tipo"], "combinaciones.tipo")
            nums([y["factor"]], 1, "combinaciones.factor")
    f = obs["funciones"]
    if not isinstance(f, dict) or set(f) != {"nombres", "valores"}:
        falla("funciones")
    nombres(f["nombres"], "funciones.nombres")
    for n, x in mapa(f["valores"], "funciones.valores", consulta["funciones"]).items():
        if not isinstance(x, dict) or set(x) != {"numero", "tiempos", "valores"} or type(x["numero"]) is not int:
            falla("funciones." + n)
        nums(x["tiempos"], None, "funciones.tiempos")
        nums(x["valores"], len(x["tiempos"]), "funciones.valores")
    for n, x in mapa(obs["tablas"], "tablas", consulta["tablas"]).items():
        if not isinstance(x, dict) or set(x) != {"campos", "filas"}:
            falla("tablas." + n)
        campos = nombres(x["campos"], "tablas.campos")
        if not isinstance(x["filas"], list) or not all(isinstance(fila, dict) and set(fila) == set(campos)
                                                       and all(isinstance(z, str) for z in fila.values()) for fila in x["filas"]):
            falla("tablas.filas")
    ej = obs["ejecucion"]
    if (not isinstance(ej, dict) or set(ej) != {"casos", "ejecutar"} or not isinstance(ej["casos"], list)
            or not isinstance(ej["ejecutar"], list) or len(ej["casos"]) != len(ej["ejecutar"])
            or not all(isinstance(x, str) for x in ej["casos"]) or not all(type(x) is bool for x in ej["ejecutar"])):
        falla("ejecucion")


def factores_unidades(plan: str, leidas: str) -> dict:
    """Factores exactos lectura→plan por magnitud; sin conversión comprobada → magnitud no comparable."""
    evidencia = {"plan": plan, "leidas": leidas, "normalizacion": "identidad", "factores": {}, "factores_exactos": {},
                 "no_comparables": {}, "valores_normalizados": 0}
    if leidas == plan:
        return evidencia
    m_plan, m_leidas = PATRON_UNIDADES.fullmatch(plan), PATRON_UNIDADES.fullmatch(leidas)
    if m_plan is None or m_leidas is None:
        evidencia["normalizacion"] = "no_admitida"
        for magnitud in DIMENSIONES:
            evidencia["no_comparables"][magnitud] = f"unidades {leidas} sin conversión comprobada a {plan}"
        return evidencia
    evidencia["normalizacion"] = "dimensional"
    f_fuerza = FACTOR_FUERZA[m_leidas[1]] / FACTOR_FUERZA[m_plan[1]]
    f_longitud = FACTOR_LONGITUD[m_leidas[2]] / FACTOR_LONGITUD[m_plan[2]]
    for magnitud, (a, b) in DIMENSIONES.items():
        if magnitud in SIN_CONVERSION_COMPROBADA:
            evidencia["no_comparables"][magnitud] = SIN_CONVERSION_COMPROBADA[magnitud]
            continue
        factor = f_fuerza ** a * f_longitud ** b
        evidencia["factores_exactos"][magnitud] = factor
        evidencia["factores"][magnitud] = f"{factor.numerator}/{factor.denominator}"
    return evidencia


class _Comparador:
    def __init__(self, exp, obs, crit):
        self.exp, self.obs, self.crit = exp, obs, crit
        self.discrepancias, self.incompletos, self.comprobaciones = [], [], 0
        self.fallidos = set()
        self.unidades = factores_unidades(exp["unidades"], obs["unidades"])
        self.cobertura = {c: "completa" for c in CATEGORIAS}
        self.resumen_malla = None
        self.filas_liquidos = None
        if exp.get("malla"):
            self.cobertura["malla"] = "completa"
        if exp.get("liquidos"):
            self.cobertura["cargas_liquidos"] = "completa"

    def disc(self, cat, objeto, campo, esperado, observado, motivo):
        self.discrepancias.append({"categoria": cat, "objeto": objeto, "campo": campo, "esperado": esperado,
                                   "observado": observado, "motivo": motivo})

    def inc(self, cat, objeto, motivo):
        self.incompletos.append({"categoria": cat, "objeto": objeto, "motivo": motivo})
        self.cobertura[cat] = "incompleta"

    def igual(self, cat, objeto, campo, e, o):
        self.comprobaciones += 1
        if e != o or type(e) is bool and type(o) is not bool:
            self.disc(cat, objeto, campo, e, o, "valor discreto distinto")

    def num(self, cat, objeto, campo, e, o, magnitud):
        motivo = self.unidades["no_comparables"].get(magnitud)
        if motivo is not None:
            self.inc(cat, objeto, f"{campo}: {motivo}")
            return
        factor = self.unidades["factores_exactos"].get(magnitud)
        if factor is not None and factor != 1 and _finito(o):
            o = float(Fraction(o) * factor)  # un solo redondeo desde el racional exacto
            self.unidades["valores_normalizados"] += 1
        self.comprobaciones += 1
        umbral = max(self.crit["absolutos"][magnitud], self.crit["relativo"] * max(abs(e), abs(o)))
        if not (_finito(o) and abs(o - e) <= umbral):
            self.disc(cat, objeto, campo, e, o, f"diferencia mayor que el umbral de lectura ({magnitud})")

    def nombres(self, cat, esperado, observado, exacto=True, metodo=None):
        if metodo in self.fallidos:  # lista no legible: ya consta como incompleta; no se juzgan ausencias
            return sorted(esperado), []
        faltan, sobran = sorted(set(esperado) - set(observado)), sorted(set(observado) - set(esperado))
        self.comprobaciones += 1
        for n in faltan:
            self.disc(cat, n, "existencia", True, False, "nombre esperado ausente")
        if exacto:
            for n in sobran:
                self.disc(cat, n, "existencia", False, True, "objeto fuera de cobertura de la expectativa")
        return sorted(set(esperado) & set(observado)), sobran

    def ejecutar(self):
        e, o = self.exp, self.obs
        fallidos = {}
        self.fallidos = {r["metodo"] for r in o["retornos_no_cero"]}
        for r in o["retornos_no_cero"]:
            fallidos.setdefault(r["metodo"], set()).add(r["objeto"])
        mapa_cat = {"cPointObj": "puntos", "cFrameObj": "frames", "cAreaObj": "areas", "cPropArea": "propiedades_area",
                    "cPropFrame": "propiedades_frame", "cPropMaterial": "materiales", "cStory": "pisos",
                    "cDiaphragm": "diafragmas", "cLoadPatterns": "patrones", "cLoadCases": "casos",
                    "cCaseStaticLinear": "casos", "cCaseModalEigen": "casos", "cCaseResponseSpectrum": "casos",
                    "cCombo": "combinaciones", "cFunction": "funciones_espectrales", "cDatabaseTables": "tablas_dinamicas",
                    "cAnalyze": "marcas_de_ejecucion"}
        for metodo, objetos in sorted(fallidos.items()):
            cat = {"cAreaObj.GetLoadUniform": "cargas_area", "cPointObj.GetLoadForce": "cargas_punto",
                   "cFrameObj.GetLoadDistributed": "cargas_frame", "cPropMaterial.GetMassSource_1": "fuente_masa",
                   "cPointObj.GetRestraint": "apoyos", "cPointObj.GetDiaphragm": "diafragmas",
                   "cAreaObj.GetDiaphragm": "diafragmas", "cAreaObj.GetOpening": "aberturas"}.get(
                metodo, mapa_cat.get(metodo.split(".")[0], "unidades"))
            for objeto in sorted(objetos):
                self.inc(cat, objeto, f"{metodo} devolvió un código distinto de 0; lectura no disponible")
        if self.unidades["normalizacion"] == "no_admitida":
            self.inc("unidades", "modelo", f"unidades leídas {o['unidades']} sin conversión comprobada a {e['unidades']}")
        else:
            self.comprobaciones += 1
        p = e["pisos"]
        self.igual("pisos", "modelo", "nombres", p["nombres"], o["pisos"]["nombres"])
        self.num("pisos", "modelo", "base", p["base"], o["pisos"]["base"], "longitud_m")
        if p["nombres"] == o["pisos"]["nombres"]:
            for n, he, ho in zip(p["nombres"], p["alturas"], o["pisos"]["alturas"]):
                self.num("pisos", n, "altura", he, ho, "longitud_m")
        comunes, _ = self.nombres("puntos", e["puntos"], o["puntos"]["nombres"])
        for n in comunes:
            if n not in o["puntos"]["coordenadas"]:
                self.inc("puntos", n, "coordenadas no leídas")
                continue
            for i, eje in enumerate("XYZ"):
                self.num("puntos", n, eje, e["puntos"][n][i], o["puntos"]["coordenadas"][n][i], "longitud_m")
        comunes, _ = self.nombres("frames", e["frames"], o["frames"]["nombres"])
        for n in comunes:
            for campo, fuente in (("puntos", "puntos"), ("seccion", "secciones")):
                if n not in o["frames"][fuente]:
                    self.inc("frames", n, campo + " no leído")
                else:
                    self.igual("frames", n, campo, e["frames"][n][campo], o["frames"][fuente][n])
            ins = e["frames"][n].get("insercion")
            if ins is not None:
                d = o["frames"].get("insercion", {}).get(n)
                if d is None:
                    self.inc("frames", n, "inserción no leída")
                    continue
                for k in ("cardinal", "mirror2", "stiff_transform", "csys"):
                    self.igual("frames", n, "insercion." + k, ins[k], d[k])
                for k in ("offset1", "offset2"):
                    if len(d[k]) != 3:
                        self.inc("frames", n, f"insercion.{k} sin tres componentes")
                        continue
                    for i, eje in enumerate("XYZ"):
                        self.num("frames", n, f"insercion.{k}.{eje}", ins[k][i], d[k][i], "longitud_m")
        comunes, _ = self.nombres("areas", e["areas"], o["areas"]["nombres"])
        for n in comunes:
            if n not in o["areas"]["puntos"] or n not in o["areas"]["propiedades"]:
                self.inc("areas", n, "contorno o propiedad no leídos")
                continue
            esperado = e["areas"][n]["puntos"]
            observado = o["areas"]["puntos"][n]
            # ETABS21.1/ensayo191 cambia el primer punto del ciclo. Conservar
            # secuencia y sentido; no aceptar ordenación ni inversión. Los bytes
            # observados permanecen intactos en la evidencia de lectura.
            equivalente = contorno_orientado_igual(esperado, observado)
            self.igual("areas", n, "contorno_ordenado", esperado, esperado if equivalente else observado)
            self.igual("areas", n, "propiedad", e["areas"][n]["propiedad"], o["areas"]["propiedades"][n])
        self.propiedades()
        self.cargas()
        self.masa()
        self.apoyos()
        self.diafragmas()
        self.patrones()
        self.casos()
        self.combinaciones()
        self.funciones()
        self.tablas()
        self.ejecucion()
        self.aberturas()
        if self.exp.get("malla"):
            self.malla()
        return self.ejes()

    def aberturas(self):
        """Estado Opening persistido: host False, hueco True. No prueba vaciado, malla ni cargas netas."""
        for n, esperado in sorted(self.exp["aberturas"].items()):
            if n not in self.obs["areas"]["nombres"]:
                continue  # ausencia ya consta como discrepancia de existencia
            leido = self.obs["areas"]["aberturas"].get(n)
            if leido is None:
                self.inc("aberturas", n, "GetOpening no legible")
            else:
                self.igual("aberturas", n, "IsOpening", esperado, leido)

    def multiconjunto(self, cat, objeto, esperados, observados, llave, numericos):
        """Igualdad por clave exacta; duplicados no se emparejan por orden: quedan incompletos."""
        ee, oo = {}, {}
        for x in esperados:
            ee.setdefault(tuple(json.dumps(x[k], sort_keys=True) for k in llave), []).append(x)
        for x in observados:
            oo.setdefault(tuple(json.dumps(x[k], sort_keys=True) for k in llave), []).append(x)
        for clave in sorted(set(ee) | set(oo)):
            a, b = ee.get(clave, []), oo.get(clave, [])
            self.comprobaciones += 1
            if len(a) != len(b):
                self.disc(cat, objeto, "cantidad:" + "/".join(clave), len(a), len(b),
                          "entrada faltante" if len(a) > len(b) else "entrada extra no esperada")
            elif len(a) > 1:
                self.inc(cat, objeto, "entradas repetidas con la misma clave; no se emparejan por orden")
            else:
                for campo, magnitud in numericos:
                    self.num(cat, objeto, "/".join(clave) + "." + campo, a[0][campo], b[0][campo], magnitud)

    def apoyos(self):
        # La configuración declara todos los apoyos; un punto sin SetRestraint está libre por configuración.
        for n in sorted(set(self.exp["puntos"]) & set(self.obs["puntos"]["nombres"])):
            leido = self.obs["apoyos"].get(n)
            if leido is None:
                self.inc("apoyos", n, "restricciones no leídas")
            else:
                self.igual("apoyos", n, "restricciones", self.exp["apoyos"].get(n, [False] * 6), leido)

    def diafragmas(self):
        e, o = self.exp, self.obs
        self.nombres("diafragmas", e["diafragmas"], o["diafragmas"]["nombres"], exacto=False, metodo="cDiaphragm.GetNameList")
        for n, semi in sorted(e["diafragmas"].items()):
            if n not in o["diafragmas"]["semirrigido"]:
                self.inc("diafragmas", n, "definición no leída")
            else:
                self.igual("diafragmas", n, "semirrigido", semi, o["diafragmas"]["semirrigido"][n])
        for n in sorted(set(e["puntos"]) & set(o["puntos"]["nombres"])):
            esperado, leido = e["diafragmas_puntos"].get(n), o["diafragmas_puntos"].get(n)
            if esperado is None:
                self.inc("diafragmas", n, "el plan no asigna diafragma ni exclusión a este punto")
            elif leido is None:
                self.inc("diafragmas", n, "asignación de diafragma no leída")
            else:
                self.igual("diafragmas", n, "opcion", esperado["opcion"], leido["opcion"])
                self.igual("diafragmas", n, "diafragma", esperado["diafragma"], leido["diafragma"])

    def patrones(self):
        e, o = self.exp["patrones"], self.obs["patrones"]
        self.nombres("patrones", e, o["nombres"], exacto=False, metodo="cLoadPatterns.GetNameList")
        for n, x in sorted(e.items()):
            d = o["detalle"].get(n)
            if d is None:
                self.inc("patrones", n, "tipo o multiplicador no leídos")
                continue
            self.igual("patrones", n, "tipo", x["tipo"], d["tipo"])
            self.num("patrones", n, "multiplicador", x["multiplicador"], d["multiplicador"], "adimensional")

    def casos(self):
        e, o = self.exp["casos"], self.obs["casos"]
        self.nombres("casos", e, o["nombres"], exacto=False, metodo="cLoadCases.GetNameList")
        for n, x in sorted(e.items()):
            if n not in o["nombres"] and "cLoadCases.GetNameList" not in self.fallidos:
                continue
            tipo = o["tipos"].get(n)
            if tipo is None:
                self.inc("casos", n, "tipo de caso no leído")
            else:
                self.igual("casos", n, "tipo", x["tipo"], tipo["tipo"]["nombre"])
            if x["tipo"] == "LinearStatic":
                leido = o["estaticos"].get(n)
                if leido is None:
                    self.inc("casos", n, "cargas del caso estático no leídas")
                else:
                    self.multiconjunto("casos", n, x.get("cargas", []), leido, ("tipo_carga", "nombre"), (("factor", "adimensional"),))
            elif x["tipo"] == "Modal":
                leido = o["modales"].get(n)
                if leido is None:
                    self.inc("casos", n, "parámetros modales no leídos")
                    continue
                self.igual("casos", n, "modos", x["modos"], leido["modos"])
                p = x["parametros"]
                self.num("casos", n, "desplazamiento", p["desplazamiento"], leido["desplazamiento"], "frecuencia_hz")
                self.num("casos", n, "corte", p["corte"], leido["corte"], "frecuencia_hz")
                self.num("casos", n, "tolerancia", p["tolerancia"], leido["tolerancia"], "adimensional")
                self.igual("casos", n, "automatico", p["automatico"], leido["automatico"])
                if "numero_cargas" in x:
                    self.igual("casos", n, "numero_cargas", x["numero_cargas"], leido["numero_cargas"])
                else:
                    self.inc("casos", n, "el plan no declara cargas iniciales modales esperadas")
            else:
                leido = o["espectrales"].get(n)
                if leido is None:
                    self.inc("casos", n, "parámetros espectrales no leídos")
                    continue
                self.igual("casos", n, "modal", x["modal"], leido["modal"])
                self.multiconjunto("casos", n, x["cargas"], leido["cargas"], ("nombre", "funcion", "csys"),
                                   (("factor", "aceleracion_m_s2"), ("angulo", "angulo_deg")))
                self.num("casos", n, "excentricidad", x["excentricidad"], leido["excentricidad"], "adimensional")
                if "amortiguamiento" in x:
                    self.num("casos", n, "amortiguamiento", x["amortiguamiento"], leido["amortiguamiento"], "adimensional")
                else:
                    self.inc("casos", n, "el plan no declara amortiguamiento del caso espectral")

    def combinaciones(self):
        e, o = self.exp["combinaciones"], self.obs["combinaciones"]
        self.nombres("combinaciones", e, o["nombres"], exacto=False, metodo="cCombo.GetNameList")
        for n, x in sorted(e.items()):
            d = o["detalle"].get(n)
            if d is None:
                self.inc("combinaciones", n, "tipo o lista de casos no leídos")
                continue
            self.igual("combinaciones", n, "tipo", x["tipo"], d["tipo"])
            self.multiconjunto("combinaciones", n, x["casos"], d["casos"], ("tipo", "nombre"), (("factor", "adimensional"),))

    def funciones(self):
        e, o = self.exp["funciones"], self.obs["funciones"]
        self.nombres("funciones_espectrales", e, o["nombres"], exacto=False, metodo="cFunction.GetNameList")
        for n, x in sorted(e.items()):
            d = o["valores"].get(n)
            if d is None:
                self.inc("funciones_espectrales", n, "valores no leídos")
                continue
            tiempos, valores = d["tiempos"], d["valores"]
            if len(tiempos) == d["numero"] + 1 and d["numero"] > 0 and tiempos[0] == 0 and valores[0] == 0:
                tiempos, valores = tiempos[1:], valores[1:]  # centinela (0,0) observado en ETABS 21.1, como el ejecutor
            elif len(tiempos) != d["numero"]:
                self.inc("funciones_espectrales", n, "GetValues devolvió un recuento no reconocido")
                continue
            self.igual("funciones_espectrales", n, "numero", len(x["periodos"]), len(tiempos))
            if len(x["periodos"]) == len(tiempos):
                for i, (te, ve, to, vo) in enumerate(zip(x["periodos"], x["valores"], tiempos, valores)):
                    self.num("funciones_espectrales", n, f"periodo[{i}]", te, to, "tiempo_s")
                    self.num("funciones_espectrales", n, f"valor[{i}]", ve, vo, "adimensional")

    def tablas(self):
        for tabla, esperada in sorted(self.exp["tablas"].items()):
            if tabla not in CAMPOS_TABLA:
                continue  # ya consta como sin_lector en la cobertura del plan
            leida = self.obs["tablas"].get(tabla)
            if tabla == op.TABLA_NO_UNIFORME:
                if leida is None:
                    self.inc("cargas_liquidos", tabla, "tabla no uniforme no leída")
                else:
                    self.tabla_liquidos(esperada, leida)
                continue
            if leida is None:
                self.inc("tablas_dinamicas", tabla, "tabla de visualización no leída")
                continue
            clave, comparados = esperada["clave"], CAMPOS_TABLA[tabla]
            faltan = [c for c in [clave, *comparados] if c not in leida["campos"]]
            if faltan:
                self.inc("tablas_dinamicas", tabla, "campos ausentes en la tabla leída: " + ", ".join(faltan))
                continue
            por_nombre = {}
            for fila in esperada["registros"]:
                por_nombre.setdefault(fila[clave], []).append(fila)
            for nombre, filas in sorted(por_nombre.items()):
                leidas = [f for f in leida["filas"] if f[clave] == nombre]
                if not leidas:
                    self.disc("tablas_dinamicas", f"{tabla}:{nombre}", "registro", True, False, "registro ausente en la tabla")
                    continue
                for campo, magnitud in comparados.items():
                    esperados = {f[campo] for f in filas}
                    observados = [f[campo] for f in leidas if f[campo] != ""]
                    if len(esperados) != 1 or not observados:
                        self.inc("tablas_dinamicas", f"{tabla}:{nombre}", f"{campo}: sin valor único esperado u observado")
                        continue
                    esperado = esperados.pop()
                    for valor in observados:
                        if magnitud is None:
                            self.igual("tablas_dinamicas", f"{tabla}:{nombre}", campo, esperado, valor)
                        else:
                            try:
                                numero = float(valor)
                            except ValueError:
                                self.disc("tablas_dinamicas", f"{tabla}:{nombre}", campo, esperado, valor, "texto no numérico")
                                continue
                            self.num("tablas_dinamicas", f"{tabla}:{nombre}", campo, float(esperado), numero, magnitud)

    def tabla_liquidos(self, esperada, leida):
        """Filas por clave compuesta objeto/patrón/dirección, solo de los patrones de líquido del plan; las ajenas se cuentan."""
        cat, campos = "cargas_liquidos", list(op.CAMPOS_NO_UNIFORME)
        faltan = [c for c in campos if c not in leida["campos"]]
        if faltan:
            self.inc(cat, op.TABLA_NO_UNIFORME, "campos ausentes en la tabla leída: " + ", ".join(faltan))
            return
        patrones = set(self.exp["liquidos"]["patrones"])
        clave = lambda f: (f["UniqueName"], f["LoadPattern"], f["Dir"])
        esperadas = {clave(f): f for f in esperada["registros"]}
        observadas, ajenas = {}, 0
        for f in leida["filas"]:
            if f["LoadPattern"] not in patrones:
                ajenas += 1
                continue
            if clave(f) in observadas:
                self.disc(cat, "/".join(clave(f)), "registro", 1, 2, "fila duplicada objeto/patrón/dirección: no se suma ni se oculta")
                continue
            observadas[clave(f)] = f
        normalizadas = {}
        for k in sorted(set(esperadas) | set(observadas)):
            self.comprobaciones += 1
            if k not in observadas:
                self.disc(cat, "/".join(k), "registro", True, False, "fila de presión esperada ausente")
                continue
            if k not in esperadas:
                self.disc(cat, "/".join(k), "registro", False, True, "fila de presión extra en un patrón de líquido")
                continue
            e, o = esperadas[k], observadas[k]
            self.igual(cat, "/".join(k), "Restriction", e["Restriction"], o["Restriction"])
            fila = {"Dir": o["Dir"], "Restriction": o["Restriction"]}
            for campo, magnitud in (("A", "peso_kN_m3"), ("B", "peso_kN_m3"), ("C", "peso_kN_m3"), ("D", "presion_kN_m2")):
                try:
                    valor = float(o[campo])
                except (TypeError, ValueError):
                    self.disc(cat, "/".join(k), campo, e[campo], o[campo], "texto no numérico")
                    fila = None
                    break
                self.num(cat, "/".join(k), campo, float(e[campo]), valor, magnitud)
                fila[campo] = self._valor_malla(valor, magnitud)
            if fila is not None:
                normalizadas[k] = fila
        self.filas_liquidos = {"filas": normalizadas, "ajenas": ajenas}

    def _resultante_liquidos(self, geo, xyz, eps):
        """Fuerza/momento integrados con filas, coordenadas y contornos LEÍDOS frente al contorno neto fuente."""
        from .cargas_liquidos_etabs import evaluar_componente
        from .vinculo_presion_malla import _integrar
        leidas = (self.filas_liquidos or {}).get("filas")
        if leidas is None:
            self.inc("cargas_liquidos", "resultante", "tabla no leída o no comparable; la resultante no se afirma")
            return
        for h in self.exp["liquidos"]["hosts"]:
            objeto = h["declaracion"] + "/" + h["superficie"]
            F, M, margen, completo = [0.0] * 3, [0.0] * 3, 0.0, True
            for t in h["triangulos"]:
                comps = [dict(f) for (n, p, _), f in sorted(leidas.items()) if n == t and p == h["patron"]]
                if t not in geo or not comps:
                    self.inc("cargas_liquidos", objeto, f"{t}: geometría o filas no leídas; la resultante no se afirma")
                    completo = False
                    break
                if any(c["Dir"] not in DIR_LIQUIDO for c in comps):
                    self.inc("cargas_liquidos", objeto, f"{t}: dirección proyectada o local; no se reinterpreta como componente completa")
                    completo = False
                    break
                if any(c["Restriction"] not in ("Zero Negative Values", "Zero Positive Values") for c in comps):
                    self.inc("cargas_liquidos", objeto, f"{t}: restricción de signo no hidrostática; la resultante no se afirma")
                    completo = False
                    break
                puntos = [xyz[n] for n in geo[t]["anillo"]]
                try:
                    _, fuerza, momento = _integrar(puntos, comps, h["origen_momentos_m"])
                except ValueError as exc:  # ErrorCargaLiquido: componente leída no evaluable
                    self.inc("cargas_liquidos", objeto, f"{t}: componente leída no evaluable ({exc})")
                    completo = False
                    break
                F = [F[k] + fuerza[k] for k in range(3)]
                M = [M[k] + momento[k] for k in range(3)]
                pmax = max(abs(evaluar_componente(c, q)) for c in comps for q in puntos)
                margen += pmax * eps * sum(math.dist(puntos[i], puntos[(i + 1) % 3]) for i in range(3))
            if not completo:
                continue
            brazo = max((abs(x) for q in xyz.values() for x in q), default=0.0) + max(abs(x) for x in h["origen_momentos_m"])
            for k, eje in enumerate("XYZ"):
                self._cerca("cargas_liquidos", objeto, "F" + eje, h["fuerza_fuente_kn"][k], F[k], "fuerza_kN", margen)
                self._cerca("cargas_liquidos", objeto, "M" + eje, h["momento_fuente_kn_m"][k], M[k], "momento_kN_m", 2 * margen * brazo)

    def ejecucion(self):
        e, o = self.exp["ejecucion"], self.obs["ejecucion"]
        if "cAnalyze.GetRunCaseFlag" in self.fallidos:
            return  # ya incompleto: sin lectura de marcas no se juzga ninguna
        if len(set(o["casos"])) != len(o["casos"]):
            self.disc("marcas_de_ejecucion", "modelo", "casos", "sin repetir", o["casos"], "casos repetidos en GetRunCaseFlag")
            return
        leidas = dict(zip(o["casos"], o["ejecutar"]))
        for n in e["ejecutar"]:
            if n not in leidas:
                self.disc("marcas_de_ejecucion", n, "existencia", True, False, "caso a ejecutar ausente")
        if not e["todos_desmarcados"]:
            self.inc("marcas_de_ejecucion", "modelo", "el plan no desmarca todos los casos; las demás marcas no tienen expectativa")
        for n, run in sorted(leidas.items()):
            if n in e["ejecutar"] or e["todos_desmarcados"]:
                self.igual("marcas_de_ejecucion", n, "ejecutar", n in e["ejecutar"], run)

    def propiedades(self):
        e, o = self.exp, self.obs
        self.nombres("propiedades_area", e["propiedades_area"], o["propiedades_area"]["nombres"], exacto=False, metodo="cPropArea.GetNameList")
        for n, p in sorted(e["propiedades_area"].items()):
            clase = "losas" if p["clase"] == "losa" else "muros"
            d = o["propiedades_area"][clase].get(n)
            if d is None:
                self.inc("propiedades_area", n, f"no legible como {p['clase']}")
                continue
            self.igual("propiedades_area", n, "subtipo", p["subtipo"], d["subtipo"])
            self.igual("propiedades_area", n, "shell", p["shell"], d["shell"])
            self.igual("propiedades_area", n, "material", p["material"], d["material"])
            self.num("propiedades_area", n, "espesor", p["espesor"], d["espesor"], "longitud_m")
        for n, p in sorted(e["propiedades_area"].items()):
            if "aligerado" not in p:
                continue
            tipo = p["aligerado"]["tipo"]
            d = o["propiedades_area"][tipo + "s"].get(n)
            if d is None:
                self.inc("propiedades_area", n, f"parámetros de losa {tipo} no legibles")
                continue
            for k, magnitud in PARAMETROS_ALIGERADO[tipo].items():
                if magnitud is None:
                    self.igual("propiedades_area", n, k, p["aligerado"]["parametros"][k], d[k])
                else:
                    self.num("propiedades_area", n, k, p["aligerado"]["parametros"][k], d[k], magnitud)
        self.nombres("propiedades_frame", e["propiedades_frame"], o["propiedades_frame"]["nombres"], exacto=False, metodo="cPropFrame.GetNameList")
        for n, p in sorted(e["propiedades_frame"].items()):
            if "l" in p:
                d = o["propiedades_frame"].get("secciones_l", {}).get(n)
                if d is None:
                    self.inc("propiedades_frame", n, "no legible como sección L")
                    continue
                self.igual("propiedades_frame", n, "material", p["material"], d["material"])
                for k in ("t3", "t2", "tf", "twc", "twt"):
                    self.num("propiedades_frame", n, k, p["l"][k], d[k], "longitud_m")
                for k in ("espejo2", "espejo3"):
                    self.igual("propiedades_frame", n, k, p["l"][k], d[k])
                continue
            d = o["propiedades_frame"]["rectangulos"].get(n)
            if d is None:
                self.inc("propiedades_frame", n, "no legible como rectángulo")
                continue
            self.igual("propiedades_frame", n, "material", p["material"], d["material"])
            self.num("propiedades_frame", n, "t3", p["t3"], d["t3"], "longitud_m")
            self.num("propiedades_frame", n, "t2", p["t2"], d["t2"], "longitud_m")
        self.nombres("materiales", e["materiales"], o["materiales"]["nombres"], exacto=False, metodo="cPropMaterial.GetNameList")
        for n, p in sorted(e["materiales"].items()):
            d = o["materiales"]["detalle"].get(n)
            if d is None:
                self.inc("materiales", n, "propiedades no leídas")
                continue
            self.igual("materiales", n, "tipo", p["tipo"], d["tipo"])
            for campo, magnitud in (("E", "modulo_kN_m2"), ("U", "adimensional"), ("A", "coeficiente_termico_1_C"),
                                    ("W", "peso_kN_m3")):
                self.num("materiales", n, campo, p[campo], d[campo], magnitud)

    def cargas(self):
        definiciones = {
            "cargas_area": (("objeto", "patron", "csys", "dir"), (("valor", "presion_kN_m2"),), "areas"),
            "cargas_punto": (("objeto", "patron", "csys"), None, "puntos"),
            "cargas_frame": (("objeto", "patron", "csys", "dir", "tipo"),
                             (("rd1", "adimensional"), ("rd2", "adimensional"), ("val1", "fuerza_lineal_kN_m"),
                              ("val2", "fuerza_lineal_kN_m")), "frames"),
        }
        for cat, (llave, valores, objetos) in definiciones.items():
            esperadas, observadas = {}, {}
            for c in self.exp[cat]:
                c = carga_vertical_global(c, cat)
                esperadas.setdefault(tuple(c[k] for k in llave), []).append(c)
            leidos = set(self.obs[cat])
            for nombre in self.obs[objetos]["nombres"]:
                if nombre not in leidos:
                    self.inc(cat, nombre, "cargas del objeto no leídas")
            for nombre, items in self.obs[cat].items():
                for c in items:
                    c = carga_vertical_global(c, cat)
                    if c["objeto"] != nombre:
                        self.disc(cat, nombre, "objeto", nombre, c["objeto"], "la API devolvió una carga de otro objeto")
                    observadas.setdefault(tuple(c[k] for k in llave), []).append(c)
            for clave in sorted(set(esperadas) | set(observadas), key=str):
                if clave[0] not in leidos:
                    continue  # objeto sin lectura de cargas: ya consta como incompleto, no como faltante
                ee, oo = esperadas.get(clave, []), observadas.get(clave, [])
                self.comprobaciones += 1
                if len(ee) != len(oo):
                    self.disc(cat, clave[0], "cantidad", len(ee), len(oo),
                              "carga faltante" if len(ee) > len(oo) else "carga extra no esperada")
                    continue
                if len(ee) > 1:
                    self.inc(cat, clave[0], "varias cargas con la misma clave; no se emparejan por orden ni aproximación")
                    continue
                if cat == "cargas_punto":
                    for i, nombre in enumerate(("F1", "F2", "F3", "M1", "M2", "M3")):
                        self.num(cat, clave[0], f"{clave[1]}.{nombre}", ee[0]["valores"][i], oo[0]["valores"][i],
                                 "fuerza_kN" if i < 3 else "momento_kN_m")
                else:
                    for campo, magnitud in valores:
                        self.num(cat, clave[0], f"{clave[1]}.{campo}", ee[0][campo], oo[0][campo], magnitud)

    def masa(self):
        e, o = self.exp["fuente_masa"], self.obs["fuente_masa"]
        for campo in ("incluir_elementos", "incluir_masa_adicional", "incluir_cargas"):
            self.igual("fuente_masa", "modelo", campo, e[campo], o[campo])
        if len(set(o["patrones"])) != len(o["patrones"]):
            self.disc("fuente_masa", "modelo", "patrones", sorted(e["factores"]), o["patrones"], "patrones repetidos en la lectura")
            return
        observados = dict(zip(o["patrones"], o["factores"]))
        self.igual("fuente_masa", "modelo", "patrones", sorted(e["factores"]), sorted(observados))
        for patron in sorted(set(e["factores"]) & set(observados)):
            self.num("fuente_masa", patron, "factor", e["factores"][patron], observados[patron], "adimensional")

    # -- malla 0.4: comprobación geométrica INDEPENDIENTE desde lo leído -------------------------------------
    def _cerca(self, cat, objeto, campo, e, o, magnitud, extra=0.0):
        """Como num(), con un margen adicional derivado de la tolerancia de lectura de coordenadas (no de ingeniería)."""
        self.comprobaciones += 1
        umbral = max(self.crit["absolutos"][magnitud], self.crit["relativo"] * max(abs(e), abs(o)), extra)
        if not (_finito(o) and abs(o - e) <= umbral):
            self.disc(cat, objeto, campo, e, o, f"diferencia mayor que el umbral de lectura ({magnitud})")

    def malla(self):
        m, o = self.exp["malla"], self.obs
        necesarias = ('longitud_m', 'presion_kN_m2', 'fuerza_lineal_kN_m')
        if (self.unidades["normalizacion"] == "no_admitida"
                or any(x in self.unidades['no_comparables'] for x in necesarias)):
            self.inc("malla", "modelo", "unidades leídas sin conversión dimensional comprobada para geometría/cargas de malla")
            return
        # Solo copia de cálculo: preservar coordenadas/cargas observadas y EDB.
        xyz = {n: [self._valor_malla(x, 'longitud_m') for x in p]
               for n, p in o["puntos"]["coordenadas"].items()}
        contornos = o["areas"]["puntos"]
        eps = self.crit["absolutos"]["longitud_m"]
        geo, host_de, resumen, parciales = {}, {}, {}, set()
        for h, info in m["hosts"].items():
            area = perimetro = 0.0
            completo = True
            for t in info["triangulos"]:
                anillo = contornos.get(t)
                if t not in o["areas"]["nombres"]:
                    completo = False  # ausencia ya consta como discrepancia de existencia
                    continue
                if anillo is None or any(n not in xyz for n in anillo):
                    self.inc("malla", t, "contorno o coordenadas no leídos; el área del host no se afirma")
                    completo = False
                    continue
                if len(anillo) != 3:
                    self.disc("malla", t, "numero_nodos", 3, len(anillo), "pieza leída no triangular")
                    completo = False
                    continue
                p = [xyz[n] for n in anillo]
                u = [p[1][k] - p[0][k] for k in range(3)]
                w = [p[2][k] - p[0][k] for k in range(3)]
                cruz = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
                a = math.fsum(c * n for c, n in zip(cruz, info["normal"])) / 2
                self.comprobaciones += 1
                if not a > 0:
                    self.disc("malla", t, "orientacion", "normal del host " + h, "invertida o degenerada",
                              "triángulo leído con orientación opuesta a la normal del host")
                geo[t] = {"area": a, "centroide": [math.fsum(q[k] for q in p) / 3 for k in range(3)], "anillo": list(anillo)}
                host_de[t] = h
                area += a
                perimetro += sum(math.dist(p[i], p[(i + 1) % 3]) for i in range(3))
            resumen[h] = {"area_neta_fuente_m2": info["area_neta_m2"], "area_triangulos_leida_m2": area if completo else None,
                          "triangulos_leidos": sum(1 for t in info["triangulos"] if t in geo)}
            if completo:
                # Cota de primer orden del error de área por coordenadas leídas: eps_longitud × perímetro total.
                self._cerca("malla", h, "area_neta_m2", info["area_neta_m2"], area, "longitud_m", eps * perimetro)
            else:
                parciales.add(h)
                self.inc("malla", h, "área neta no comprobable: faltan triángulos o contornos leídos")
        self._conformidad(geo, host_de, xyz, eps)
        for c in m["conexiones"]:
            for n in c["sin_resolver"]:
                self.inc("malla", c["id"], f"nodo compartido {n} sin nombre CSI resoluble en el plan")
            for n in c["nodos"]:
                usos = {host_de[t] for t, g in geo.items() if n in g["anillo"]}
                if len(usos) < 2 and parciales:  # sin lectura completa no se juzga una ausencia
                    self.inc("malla", c["id"], f"nodo compartido {n}: hosts {sorted(parciales)} sin lectura completa")
                    continue
                self.comprobaciones += 1
                if len(usos) < 2:
                    self.disc("malla", c["id"], "nodo_compartido:" + n, "≥2 hosts", sorted(usos),
                              "nodo del borde conectado no compartido por los triángulos de ambos hosts")
        for r in m["subframes"]:
            self._subframes(r, xyz, eps)
        for c in m["cargas"]:
            self._conservacion(c, geo, xyz, eps)
        if self.exp.get("liquidos") and self.exp["liquidos"]["hosts"]:
            self._resultante_liquidos(geo, xyz, eps)
        self.resumen_malla = {"hosts": resumen, "conexiones": [c["id"] for c in m["conexiones"]],
                              "subdivisiones": [r["frame"] for r in m["subframes"]], "cargas": [c["carga"] for c in m["cargas"]],
                              "huella_preparacion": m["huella_preparacion"]}

    def _conformidad(self, geo, host_de, xyz, eps):
        """Aristas dirigidas únicas por host y ningún nodo de la malla dentro de una arista ajena (nodo colgante)."""
        dirigidas = {}
        for t, g in geo.items():
            a = g["anillo"]
            for i in range(3):
                dirigidas.setdefault((host_de[t], a[i], a[(i + 1) % 3]), []).append(t)
        for (h, p, q), ts in sorted(dirigidas.items()):
            if len(ts) > 1:
                self.disc("malla", h, f"arista {p}->{q}", 1, len(ts), "arista repetida en el mismo sentido: orientación o malla incoherente")
        nodos = sorted({n for g in geo.values() for n in g["anillo"]})
        aristas = sorted({tuple(sorted((g["anillo"][i], g["anillo"][(i + 1) % 3]))) for g in geo.values() for i in range(3)})
        self.comprobaciones += 1
        for a, b in aristas:
            pa, pb = xyz[a], xyz[b]
            d = [pb[k] - pa[k] for k in range(3)]
            dd = math.fsum(x * x for x in d)
            for n in nodos:
                if n in (a, b):
                    continue
                v = [xyz[n][k] - pa[k] for k in range(3)]
                t = math.fsum(x * y for x, y in zip(v, d)) / dd
                if not 0 < t < 1:
                    continue
                dist = math.dist(xyz[n], [pa[k] + t * d[k] for k in range(3)])
                if dist <= eps + self.crit["relativo"] * math.sqrt(dd):
                    self.disc("malla", n, f"arista {a}-{b}", "nodo compartido por ambos lados", "nodo colgante",
                              "nodo de la malla dentro de una arista leída: malla no conforme o nodo compartido roto")

    def _subframes(self, r, xyz, eps):
        o = self.obs["frames"]
        if any(s not in o["puntos"] for s in r["subframes"]) or any(n not in xyz for n in r["nodos"]):
            self.inc("malla", r["frame"], "subframes o nodos no leídos; la subdivisión no se afirma")
            return
        cadena = [o["puntos"][s] for s in r["subframes"]]
        self.comprobaciones += 1
        if any(cadena[k][1] != cadena[k + 1][0] for k in range(len(cadena) - 1)) or cadena[0][0] != r["nodos"][0] or cadena[-1][1] != r["nodos"][-1]:
            self.disc("malla", r["frame"], "conectividad", r["nodos"], [x for par in cadena for x in par],
                      "subframes leídos no forman la cadena continua del frame original")
            return
        p0, p1 = xyz[r["nodos"][0]], xyz[r["nodos"][-1]]
        d = [p1[k] - p0[k] for k in range(3)]
        largo = math.dist(p0, p1)
        anterior = 0.0
        for n in [x[1] for x in cadena[:-1]]:
            v = [xyz[n][k] - p0[k] for k in range(3)]
            t = math.fsum(x * y for x, y in zip(v, d)) / (largo * largo)
            fuera = math.dist(xyz[n], [p0[k] + t * d[k] for k in range(3)])
            self.comprobaciones += 1
            if fuera > eps + self.crit["relativo"] * largo or not anterior < t < 1:
                self.disc("malla", r["frame"], "colinealidad:" + n, "interior y ordenado sobre el frame", t,
                          "nodo intermedio leído fuera del eje del frame o fuera de orden")
            anterior = t
        suma = math.fsum(math.dist(xyz[a], xyz[b]) for a, b in cadena)
        self._cerca("malla", r["frame"], "longitud_total", largo, suma, "longitud_m", eps * len(cadena))

    def _valor_malla(self, valor, magnitud):
        factor = self.unidades['factores_exactos'].get(magnitud, Fraction(1))
        if factor != 1:
            self.unidades['valores_normalizados'] += 1
        return float(Fraction(valor) * factor)

    def _conservacion(self, c, geo, xyz, eps):
        """Fuerza y momento desde cargas LEÍDAS × áreas/longitudes LEÍDAS frente a la resultante fuente del plan."""
        cat = c["categoria"]
        F, M, margen = [0.0] * 3, [0.0] * 3, 0.0
        for parte in c["partes"]:
            leidas = self.obs[cat].get(parte)
            if leidas is None or (cat == "cargas_area" and parte not in geo):
                self.inc("malla", c["carga"], f"{parte}: carga o geometría no leída; la resultante no se afirma")
                return
            for x in leidas:
                x = carga_vertical_global(x, cat)
                if x["patron"] != c["patron"]:
                    continue
                if x["csys"] != "Global" or x["dir"] not in DIRECCION_EJE or (cat == "cargas_frame" and (
                        x["tipo"] != 1 or x["rd1"] != 0 or x["rd2"] != 1 or x["val1"] != x["val2"])):
                    self.inc("malla", c["carga"], f"{parte}: dirección proyectada/local o carga no uniforme; no se reinterpreta como carga completa")
                    return
                if cat == "cargas_area":
                    medida, centro = geo[parte]["area"], geo[parte]["centroide"]
                    valor = self._valor_malla(x['valor'], 'presion_kN_m2')
                    a = geo[parte]["anillo"]
                    margen += abs(valor) * eps * sum(math.dist(xyz[a[i]], xyz[a[(i + 1) % 3]]) for i in range(3))
                else:
                    p, q = (xyz[n] for n in self.obs["frames"]["puntos"][parte])
                    medida, centro = math.dist(p, q), [(p[k] + q[k]) / 2 for k in range(3)]
                    valor = self._valor_malla(x['val1'], 'fuerza_lineal_kN_m')
                    margen += abs(valor) * 2 * eps
                f = [0.0] * 3
                f[DIRECCION_EJE[x["dir"]]] = valor * medida
                F = [F[k] + f[k] for k in range(3)]
                mk = [centro[1] * f[2] - centro[2] * f[1], centro[2] * f[0] - centro[0] * f[2], centro[0] * f[1] - centro[1] * f[0]]
                M = [M[k] + mk[k] for k in range(3)]
        brazo = max((abs(x) for p in xyz.values() for x in p), default=0.0)
        for k, eje in enumerate("XYZ"):
            self._cerca("malla", c["carga"], "F" + eje, c["fuerza_kN"][k], F[k], "fuerza_kN", margen)
            self._cerca("malla", c["carga"], "M" + eje, c["momento_kNm"][k], M[k], "momento_kN_m", margen * brazo * 2)

    def ejes(self):
        criterio = self.exp.get("ejes_locales_area")
        sin_criterio = sorted(n for n in self.exp["areas"] if not criterio or n not in criterio)
        for n, c in sorted((criterio or {}).items()):
            leido = self.obs["areas"]["ejes"].get(n)
            if leido is None:
                self.inc("areas", n, "ejes locales no leídos")
                continue
            self.num("areas", n, "eje_local_angulo", c["angulo_deg"], leido["angulo_deg"], "angulo_deg")
            if c["avanzado"] is not None:  # el plan no siempre declara Advanced: entonces no se afirma
                self.igual("areas", n, "eje_local_avanzado", c["avanzado"], leido["avanzado"])
        return sin_criterio


def comparar(expectativa: dict, observado: dict, criterios: dict) -> dict:
    """Comparación pura. Estado: discrepancias > incompleto > verificado; nunca éxito por datos faltantes."""
    crit = validar_criterios(criterios)
    validar_observado(observado, consulta_desde_expectativa(expectativa))
    comp = _Comparador(expectativa, observado, crit)
    sin_criterio = comp.ejecutar()
    inventario = expectativa["inventario"]
    sin_lector = [x for x in inventario if x["cobertura"] == "sin_lector"]
    for x in sin_lector:
        comp.incompletos.append({"categoria": "cobertura_plan", "objeto": f"{x['orden']}:{x['metodo']}", "motivo": x["motivo"]})
    estado = "discrepancias" if comp.discrepancias else "incompleto" if comp.incompletos else "verificado"
    cobertura_plan = {
        "operaciones": len(inventario),
        "comprobadas": sum(1 for x in inventario if x["cobertura"] == "comprobada"),
        "excluidas": [{k: x[k] for k in ("orden", "metodo", "motivo")} for x in inventario if x["cobertura"] == "excluida"],
        "sin_lector": [{k: x[k] for k in ("orden", "metodo", "motivo")} for x in sin_lector],
        "por_metodo": {m: sum(1 for x in inventario if x["metodo"] == m) for m in sorted({x["metodo"] for x in inventario})},
    }
    return {
        "estado": estado, "verificado": estado == "verificado",
        "verificacion_global_del_plan": estado == "verificado" and not sin_lector,
        "cobertura_plan": cobertura_plan,
        "alcance": list(CATEGORIAS) + (["malla"] if expectativa.get("malla") else [])
                   + (["cargas_liquidos"] if expectativa.get("liquidos") else []), "fuera_de_alcance": list(FUERA_DE_ALCANCE),
        "cobertura": dict(comp.cobertura, ejes_locales_area="sin_criterio" if sin_criterio else "completa"),
        "comprobaciones": comp.comprobaciones, "discrepancias": comp.discrepancias, "incompletos": comp.incompletos,
        "ejes_sin_criterio": sin_criterio, "ejes_origen": copy.deepcopy(expectativa.get("ejes_origen", {})),
        "controles_no_afirmados": (["ejes_locales_area"] if sin_criterio else []) + list(FUERA_DE_ALCANCE)
                                  + ([EFECTO_ABERTURAS] if any(expectativa.get("aberturas", {}).values()) else [])
                                  + (list(NO_AFIRMADOS_MALLA) if expectativa.get("malla") else [])
                                  + (["hidrodinamica", "geotecnia", "flotacion", "equilibrio_del_solver"] if expectativa.get("liquidos") else []),
        **({"malla": comp.resumen_malla} if expectativa.get("malla") else {}),
        "unidades": {k: (dict(v) if isinstance(v, dict) else v) for k, v in comp.unidades.items() if k != "factores_exactos"},
        "aprueba_modelo": False, "certifica_seguridad_estructural": False,
    }


# -- 3. transporte y política ------------------------------------------------------

def configuracion_real(trabajo: Path, bloqueo: Path | None = None, *, timeout_s: float = 600.0,
                       dll: Path | None = None) -> ad.ConfiguracionPuente:
    return ad.ConfiguracionPuente.real(trabajo, bloqueo, timeout_s=timeout_s, dll=dll, script=SCRIPT)


def configuracion_doble_powershell(trabajo: Path, dll_prueba: Path, bloqueo: Path | None = None, *,
                                   timeout_s: float = 180.0, entorno: dict[str, str] | None = None) -> ad.ConfiguracionPuente:
    """Script real contra un ensamblado de PRUEBA; el script rechaza la DLL de CSI en modo doble."""
    comando = (str(ad.POWERSHELL_51), "-NoProfile", "-NonInteractive", "-File", str(SCRIPT))
    config = ad.ConfiguracionPuente.doble(trabajo, comando, bloqueo, timeout_s=timeout_s, entorno=entorno)
    return replace(config, dll=Path(dll_prueba))


@dataclass
class PreparacionVerificacion:
    solicitud: ad.SolicitudPreparada
    edb: Path
    sha256_edb: str
    expectativa: dict
    criterios: dict
    bytes_solicitud: bytes
    argv: tuple


@dataclass
class ResultadoVerificacion:
    id: str
    estado: str
    verificado: bool
    resultado: dict
    corrida: Path


class VerificadorModeloGuardado(ad.AdaptadorEtabs):
    """Lectura deliberada; reutiliza bloqueo, tiempo límite y estado incierto de AdaptadorEtabs."""

    def __init__(self, configuracion: ad.ConfiguracionPuente):
        super().__init__(configuracion)
        self._preparaciones: dict[str, PreparacionVerificacion] = {}

    def preparar_verificacion(self, edb: Path, sha256_edb: str, plan: dict, *, criterios: dict,
                              ejes_locales_area: dict | None = None,
                              version_etabs_esperada: str | None = None) -> PreparacionVerificacion:
        expectativa = expectativa_desde_plan(plan, ejes_locales_area=ejes_locales_area)
        crit = validar_criterios(criterios)
        if not isinstance(sha256_edb, str) or not SHA.fullmatch(sha256_edb):
            raise ErrorVerificacion("sha256_edb debe ser SHA256 hexadecimal en minúsculas.")
        if version_etabs_esperada is not None and (not isinstance(version_etabs_esperada, str) or not version_etabs_esperada.strip()):
            raise ErrorVerificacion("version_etabs_esperada debe ser texto o null.")
        edb = ad._ruta_edb(edb, "edb")
        if not edb.is_file():
            raise ErrorVerificacion("El EDB indicado no existe.")
        if self.config.modo == "doble" and expectativa["origen_plan"]["origen"].get("datos_sinteticos") is not True:
            raise ad.ErrorEvidenciaEtabs("Solo datos sintéticos admiten transporte doble.")
        raw_edb = _regular(edb).read_bytes()
        if _sha(raw_edb) != sha256_edb:
            raise ad.ErrorEvidenciaEtabs("El EDB no coincide con el SHA256 declarado.")
        trabajo = Path(self.config.trabajo)
        if not trabajo.is_dir():
            raise ErrorVerificacion("No existe la carpeta de trabajo.")
        ident = uuid4().hex
        carpeta = trabajo / ident
        carpeta.mkdir()
        copia = carpeta / "modelo_lectura.edb"  # copia privada: la instancia nunca abre el original
        _nuevo(copia, raw_edb)
        consulta = consulta_desde_expectativa(expectativa)
        raw_exp, raw_crit = _bytes(expectativa), _bytes(crit)
        _nuevo(carpeta / "expectativa.json", raw_exp)
        _nuevo(carpeta / "criterios.json", raw_crit)
        contenido = {"contrato": ad.CONTRATO_SOLICITUD, "version_contrato": ad.VERSION_CONTRATO, "id": ident,
                     "operacion": OPERACION, "modo_configurado": self.config.modo, "modelo_lectura": str(copia),
                     "sha256_edb": sha256_edb, "unidades_esperadas": UNIDADES,
                     "version_etabs_esperada": version_etabs_esperada,
                     "dll": str(self.config.dll or ad.DLL_ETABS), "consulta": consulta,
                     "sha256_expectativa": _sha(raw_exp), "huella_plan": expectativa["origen_plan"]["huella_plan"],
                     "version_lector": VERSION_LECTOR}
        raw = _bytes(contenido)
        ruta = carpeta / "solicitud.json"
        _nuevo(ruta, raw)
        argv = [*self.config.comando, "-Solicitud", str(ruta), "-Respuesta", str(carpeta / "respuesta.json"),
                "-Sha256Solicitud", _sha(raw), "-Modo", self.config.modo]
        prep = PreparacionVerificacion(ad.SolicitudPreparada(ident, OPERACION, carpeta, ruta, carpeta / "respuesta.json",
                                                              argv, contenido),
                                       edb, sha256_edb, expectativa, crit, raw, tuple(argv))
        self._preparaciones[ident] = prep
        return prep

    def _revalidar(self, prep: PreparacionVerificacion) -> None:
        s = prep.solicitud
        if (tuple(s.argv) != prep.argv or _regular(s.solicitud).read_bytes() != prep.bytes_solicitud
                or _sha(_regular(s.carpeta / "expectativa.json").read_bytes()) != s.contenido["sha256_expectativa"]
                or _regular(s.carpeta / "criterios.json").read_bytes() != _bytes(prep.criterios)):
            raise ad.ErrorEvidenciaEtabs("Solicitud, expectativa o criterios alterados.")
        if _sha(_regular(prep.edb).read_bytes()) != prep.sha256_edb:
            raise ad.ErrorEvidenciaEtabs("El EDB original cambió.")
        if _sha(_regular(s.carpeta / "modelo_lectura.edb").read_bytes()) != prep.sha256_edb:
            raise ad.ErrorEvidenciaEtabs("La copia de lectura cambió.")

    def ejecutar_verificacion(self, prep: PreparacionVerificacion, *, confirmar_lectura: bool = False) -> ResultadoVerificacion:
        if confirmar_lectura is not True:
            raise ad.ErrorAdaptador("Confirmación explícita de lectura requerida.")
        if self._preparaciones.get(prep.solicitud.id) is not prep:
            raise ad.ErrorAdaptador("Preparación ajena al verificador.")
        return self.ejecutar(prep.solicitud)

    def ejecutar(self, preparada):  # type: ignore[override]
        if preparada.id not in self._preparaciones:
            raise ad.ErrorAdaptador("Use preparar_verificacion/ejecutar_verificacion.")
        return super().ejecutar(preparada)

    @staticmethod
    def _comprobar_datos(prep: PreparacionVerificacion, datos: Any) -> dict:
        s = prep.solicitud.contenido
        claves = {"sha256_antes", "sha256_despues", "instancia", "id_proceso", "inicio_proceso_utc", "instancia_cerrada",
                  "firmas_verificadas", "version_dll", "consulta", "lecturas", "guardado", "modificaciones", "version_lector"}
        if (not isinstance(datos, dict) or set(datos) != claves or datos["sha256_antes"] != s["sha256_edb"]
                or datos["sha256_despues"] != s["sha256_edb"] or datos["instancia_cerrada"] is not True
                or datos["guardado"] is not False or datos["modificaciones"] != []
                or datos["consulta"] != s["consulta"] or datos["version_lector"] != VERSION_LECTOR
                or type(datos["firmas_verificadas"]) is not int
                or datos["firmas_verificadas"] <= 0 or not isinstance(datos["version_dll"], str)):
            raise ad.ErrorEvidenciaEtabs("Respuesta sin huellas, cierre o consulta verificables; no se acepta.")
        if s["modo_configurado"] == "real":
            if datos["instancia"] != "nueva" or type(datos["id_proceso"]) is not int or datos["id_proceso"] <= 0 \
                    or not isinstance(datos["inicio_proceso_utc"], str):
                raise ad.ErrorEvidenciaEtabs("Instancia propia no identificada.")
        elif datos["instancia"] != "doble":
            raise ad.ErrorEvidenciaEtabs("Modo doble con instancia no declarada como doble.")
        if s["version_etabs_esperada"] is not None and datos["lecturas"].get("version_etabs") != s["version_etabs_esperada"]:
            raise ad.ErrorEvidenciaEtabs("Versión de ETABS distinta de la esperada.")
        validar_observado(datos["lecturas"], s["consulta"])
        return datos["lecturas"]

    def _lanzar(self, request):
        prep = self._preparaciones[request.id]
        self._revalidar(prep)
        _nuevo(self.estado_incierto, _bytes({"corrida": request.id, "operacion": OPERACION,
                                             "estado": "lectura_no_confirmada", "fecha_utc": datetime.now(timezone.utc).isoformat()}))
        try:
            respuesta = super()._lanzar(request)
            observado = self._comprobar_datos(prep, respuesta.datos)
            self._revalidar(prep)  # huellas después de leer, antes de publicar
            comparacion = comparar(prep.expectativa, observado, prep.criterios)
            raw_respuesta = _regular(request.respuesta).read_bytes()
            resultado = {"contrato": CONTRATO_RESULTADO, "version_contrato": VERSION, "id_lectura": request.id,
                         "modo": self.config.modo, "sha256_edb": prep.sha256_edb,
                         "origen_plan": copy.deepcopy(prep.expectativa["origen_plan"]),
                         "sha256_solicitud": _sha(prep.bytes_solicitud),
                         "sha256_expectativa": request.contenido["sha256_expectativa"],
                         "sha256_criterios": _sha(_bytes(prep.criterios)), "sha256_respuesta": _sha(raw_respuesta),
                         "instancia_nueva_cerrada": True, "guardado": False, "ejecutable": False, **comparacion}
            _nuevo(request.carpeta / "resultado_verificacion.json", _bytes(resultado))
            _nuevo(request.carpeta / "estado_motor_resuelto.json", self.estado_incierto.read_bytes())
            self.estado_incierto.unlink()
            return ResultadoVerificacion(request.id, resultado["estado"], resultado["verificado"], resultado, request.carpeta)
        except Exception as error:
            if not self.estado_incierto.exists():
                _nuevo(self.estado_incierto, _bytes({"corrida": request.id, "estado": "lectura_no_confirmada"}))
            diagnostico = diagnosticar_puente(request.carpeta) if not request.respuesta.exists() else None
            try:
                _nuevo(request.carpeta / "verificacion_no_completada.json",
                       _bytes({"verificado": False, "estado": "no_completada", "tipo": type(error).__name__,
                               "mensaje": str(error)[:2000], "motor_incierto": True, "diagnostico_puente": diagnostico}))
            except FileExistsError:
                pass
            if diagnostico is not None and isinstance(error, ad.ErrorPuente) and not isinstance(error, ad.ErrorTiempo):
                raise ad.ErrorPuente(f"{error} Causa observada: {diagnostico['causa']}: {diagnostico['detalle']}",
                                     tipo=diagnostico["tipo"], corrida=request.carpeta,
                                     codigo_proceso=error.codigo_proceso) from error
            raise


_DIRECTIVA = re.compile(r"running scripts is disabled|cannot be loaded because|UnauthorizedAccess|"
                        r"no se puede cargar|deshabilitad[ao] la ejecuci|execution polic|directiva de ejecuci", re.I)


def diagnosticar_puente(carpeta: Path) -> dict:
    """Causa concreta de un puente sin respuesta, desde su stderr conservado; rutas absolutas ocultas."""
    try:
        texto = (Path(carpeta) / "salida_puente.txt").read_bytes().decode("utf-8", "replace")
    except OSError:
        return {"tipo": "puente", "causa": "sin_salida_conservada", "detalle": "No hay salida_puente.txt."}
    errores = texto.split("--- stderr ---", 1)[-1].strip()
    plano = " ".join(errores.split())
    plano = re.sub(r"[A-Za-z]:\\[^\r\n]*?\.(?:ps1|edb|json|dll|txt)\b", "<ruta>", plano)  # rutas con espacios hasta su extensión
    detalle = re.sub(r"[A-Za-z]:\\\S*", "<ruta>", plano)[:600] or "stderr vacío"
    if _DIRECTIVA.search(errores):
        return {"tipo": "entorno", "causa": "directiva_de_ejecucion_impide_file", "detalle": detalle}
    return {"tipo": "puente", "causa": "sin_respuesta", "detalle": detalle}


def cargar_resultado(ruta: Path) -> dict:
    """Lee un resultado publicado (JSON estricto)."""
    datos = json_desde_bytes(_regular(Path(ruta)).read_bytes(), "resultado_verificacion.json")
    if (not isinstance(datos, dict) or datos.get("contrato") != CONTRATO_RESULTADO
            or datos.get("version_contrato") not in VERSIONES_RESULTADO_LEGIBLES):
        raise ErrorVerificacion("Resultado de verificación no admitido.")
    return datos
