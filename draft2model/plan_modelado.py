"""Plan geométrico previo al adaptador ETABS: superficies 3D trazables desde el contrato de geometría.

`preparar_plan_modelado(geometria)` es una función pura: no modifica la entrada, no
lee ni escribe archivos y no depende de ETABS, red ni estado externo. Las
superficies son propuestas geométricas en metros; no son objetos ETABS, no
definen ejes locales y no incluyen materiales, secciones, cargas ni masa.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path
from typing import Any

from draft2model import contratos as c
from draft2model.validacion_geometria import ErrorLecturaGeometria, cargar_geometria, validar_geometria

CONTRATO_PLAN = "draft2model.plan_modelado"
VERSION_PLAN = "0.1.0"
VERSION_PLAN_SUPERFICIES = "0.2.0"
VERSION_PLAN_ABERTURAS = "0.3.0"

ORDEN_VERTICES = ("inicio_inferior", "fin_inferior", "fin_superior", "inicio_superior")

ESTADO_INCONSISTENTE = "inconsistente"
ESTADO_CON_FALTANTES = "consistente_con_faltantes"
ESTADO_SIN_APROBACION = "consistente_completa_sin_aprobacion_vigente"
ESTADO_APROBACION_VIGENTE = "consistente_completa_con_aprobacion_vigente"

LIMITACIONES = (
    "Las superficies son propuestas geométricas; no equivalen a objetos, secciones ni ejes locales de ETABS.",
    "Faltan representación estructural, materiales, secciones, cargas, masa, condiciones de borde, "
    "diafragmas y la verificación del adaptador ETABS.",
    "El área geométrica bruta es longitud por altura del rectángulo; no descuenta aberturas y no "
    "determina peso, masa ni resistencia.",
    "El contrato de geometría v0.1 no indica si los nodos representan el eje o una cara del muro: la "
    "superficie pasa por los nodos y el espesor se informa sin aplicarse a la posición.",
    "No se infieren tipología, materiales, cargas, parámetros sísmicos ni admisibilidad por número de pisos.",
    "El plan no tiene revisión ni aprobación propias; una aprobación geométrica no se transfiere al plan.",
)

_BLOQUEOS_PERMANENTES = (
    "ejecutable_en_etabs es false: el adaptador ETABS y la representación estructural no están implementados ni verificados.",
    "El plan derivado no tiene revisión ni aprobación propias.",
)


def preparar_plan_modelado(geometria: Any) -> dict[str, Any]:
    """Transforma un contrato de geometría v0.1 en un plan de superficies 3D en metros.

    Reutiliza `validar_geometria` y su copia normalizada `geometria_m`; no duplica la
    validación. El resultado es independiente de la entrada y serializable con JSON
    estricto (sin NaN ni Infinity).
    """
    resultado = validar_geometria(geometria)
    validacion = resultado.a_dict()
    origen = {
        "contrato": c.CONTRATO_GEOMETRIA,
        "version_contrato": geometria.get("version_contrato") if isinstance(geometria, dict) else c.VERSION_GEOMETRIA,
        "huella_contenido": resultado.huella_contenido,
        "validacion": {
            clave: validacion[clave]
            for clave in (
                "consistente", "disponible_para_modelado", "datos_sinteticos",
                "errores", "advertencias", "faltantes", "bloqueos",
            )
        },
        "revision": _revision_origen(geometria, resultado),
    }
    con_aberturas = isinstance(geometria, dict) and geometria.get("version_contrato") == c.VERSION_GEOMETRIA_ABERTURAS
    extendida = isinstance(geometria, dict) and geometria.get("version_contrato") in (c.VERSION_GEOMETRIA_SUPERFICIES, c.VERSION_GEOMETRIA_ABERTURAS)
    plan: dict[str, Any] = {
        "contrato": CONTRATO_PLAN,
        "version_contrato": VERSION_PLAN_ABERTURAS if con_aberturas else (VERSION_PLAN_SUPERFICIES if extendida else VERSION_PLAN),
        "caso": _caso(geometria),
        "ejecutable_en_etabs": False,
        "estado_origen": _estado(resultado),
        "origen": origen,
        "unidades": {
            "longitud": "m",
            "area": "m2",
            "unidad_longitud_origen": _unidad_origen(geometria),
            "coordenadas": "x, y en planta según el contrato de geometría; z = cota del nivel. No son coordenadas de imagen.",
        },
        "procedencia": None,
        "orden_vertices": list(ORDEN_VERTICES),
        "superficies": [],
        "omisiones": [],
        "cobertura": "sin_superficies",
        "bloqueos": [],
        "limitaciones": list(LIMITACIONES),
        "aprobacion_plan": None,
    }

    if extendida:
        plan["orden_vertices_superficies"] = "Contorno ordenado explícito de IDs XYZ; no se reordena ni equivale a ejes locales ETABS."
        if con_aberturas:
            plan["aberturas"] = []
            plan["vertices"] = []
            plan["unidades"]["coordenadas"] = "Vértices XYZ físicos explícitos en metros; los muros heredados usan nodos XY y cotas de nivel. No son coordenadas de imagen."
            plan["limitaciones"][2] = "Los muros conservan su área bruta rectangular; las superficies explícitas conservan área bruta, huecos y área neta, sin determinar peso, masa ni resistencia."
            plan["limitaciones"].append("Aberturas v0.3 explícitas: no hay exportación ETABS, configuración estructural, conversión ni importación tabular v0.3 integradas.")
        else:
            plan["limitaciones"].append("Superficies v0.2: geometría plana explícita, sin sección, huecos, mallado, rigidez, carga, masa ni idealización estructural inferidas.")
    if not resultado.consistente:
        plan["bloqueos"] = [
            "Geometría de origen inconsistente: no se emiten superficies. Corrija los errores del validador.",
            *_BLOQUEOS_PERMANENTES,
        ]
        return _json_estricto(plan)

    geometria_m = resultado.geometria_m
    if con_aberturas:
        plan["vertices"] = copy.deepcopy(geometria_m["vertices"])
    plan["procedencia"] = copy.deepcopy(geometria_m["procedencia"])
    nodos = {n["id"]: n for n in geometria_m["nodos"]}
    niveles = {n["id"]: n for n in geometria_m["niveles"]}

    for muro in geometria_m["muros"]:
        faltantes = _faltantes_muro(muro, niveles)
        if faltantes:
            plan["omisiones"].append({"muro_id": muro["id"], "motivo": "datos_faltantes", "faltantes": faltantes})
            continue
        superficie, invalidos = _superficie(
            muro, nodos, niveles, resultado.derivados_m["muros"], geometria_m["procedencia"]
        )
        if invalidos:
            plan["omisiones"].append({
                "muro_id": muro["id"],
                "motivo": "calculo_derivado_no_valido",
                "valores_no_validos": invalidos,
                "detalle": "Resultado no finito o no positivo en metros (desbordamiento o subdesbordamiento); "
                           "no se sustituye por otro valor.",
            })
            continue
        plan["superficies"].append(superficie)

    if extendida:
        for item in geometria_m["superficies"]:
            derivado = resultado.derivados_m["superficies"][item["id"]]
            plan["superficies"].append({
                "superficie_id": item["id"], "papel_geometrico": item["papel_geometrico"],
                "vertices_ids": list(item["vertices"]),
                "vertices_m": copy.deepcopy(derivado["vertices_m"]),
                "area_geometrica_m2": derivado["area_m2"],
                "normal_unitaria": list(derivado["normal_unitaria"]),
                "procedencia": copy.deepcopy(item["procedencia"]),
                "procedencia_declarada_en": "superficie",
            })
            if con_aberturas:
                plan["superficies"][-1].update({k: copy.deepcopy(derivado[k]) for k in ("area_bruta_m2", "area_aberturas_m2", "area_neta_m2", "aberturas_ids")})
        if con_aberturas:
            for item in geometria_m["aberturas"]:
                derivado = resultado.derivados_m["aberturas"][item["id"]]
                plan["aberturas"].append({
                    "abertura_id": item["id"], "superficie_id": item["superficie"],
                    "vertices_ids": list(item["vertices"]), "vertices_m": copy.deepcopy(derivado["vertices_m"]),
                    "area_geometrica_m2": derivado["area_m2"], "normal_unitaria": list(derivado["normal_unitaria"]),
                    "procedencia": copy.deepcopy(item["procedencia"]), "procedencia_declarada_en": "abertura",
                })
            plan["cobertura_aberturas"] = "completa"
    total = len(geometria_m["muros"]) + (len(geometria_m["superficies"]) if extendida else 0)
    emitidas = len(plan["superficies"])
    plan["cobertura"] = "completa" if emitidas == total else ("parcial" if emitidas else "sin_superficies")

    bloqueos = []
    if plan["omisiones"]:
        bloqueos.append(
            f"{len(plan['omisiones'])} de {total} muro(s) sin superficie; ver 'omisiones'. No se completan datos."
        )
    if plan["estado_origen"] == ESTADO_CON_FALTANTES:
        bloqueos.append("La geometría de origen tiene faltantes declarados.")
    elif plan["estado_origen"] == ESTADO_SIN_APROBACION:
        bloqueos.append("La geometría de origen no tiene una aprobación registrada vigente.")
    if extendida:
        bloqueos.extend(b for b in resultado.bloqueos if b not in bloqueos)
    plan["bloqueos"] = bloqueos + list(_BLOQUEOS_PERMANENTES)
    return _json_estricto(plan)


# -- auxiliares --------------------------------------------------------------

def _estado(resultado) -> str:
    if not resultado.consistente:
        return ESTADO_INCONSISTENTE
    if resultado.faltantes:
        return ESTADO_CON_FALTANTES
    if getattr(resultado, "version_contrato", None) in (c.VERSION_GEOMETRIA_SUPERFICIES, c.VERSION_GEOMETRIA_ABERTURAS):
        return "consistente_completa_con_integracion_pendiente"
    if resultado.disponible_para_modelado:
        return ESTADO_APROBACION_VIGENTE
    return ESTADO_SIN_APROBACION


def _caso(geometria: Any) -> str | None:
    if isinstance(geometria, dict) and isinstance(geometria.get("id"), str):
        return geometria["id"]
    return None


def _unidad_origen(geometria: Any) -> str | None:
    """Unidad declarada si es una de las admitidas; cualquier otro tipo JSON da None, sin excepciones."""
    unidad = geometria.get("unidad_longitud") if isinstance(geometria, dict) else None
    return unidad if isinstance(unidad, str) and unidad in c.DIVISORES_A_METROS else None


def _revision_origen(geometria: Any, resultado) -> dict[str, Any] | None:
    """Resume el estado de revisión de la geometría sin copiar la aprobación al plan."""
    if not resultado.consistente:
        return None
    revision = geometria["revision"]
    aprobacion = revision["aprobacion"]
    return {
        "estado": revision["estado"],
        "aprobacion_registrada": aprobacion is not None,
        "aprobacion_vigente": aprobacion is not None
        and revision["estado"] == "aprobado"
        and aprobacion["huella_contenido"] == resultado.huella_contenido,
        "nota": "Estado de la geometría de origen; no es una aprobación del plan.",
    }


def _faltantes_muro(muro: dict, niveles: dict) -> list[dict[str, str]]:
    faltantes = []
    if muro["espesor"] is None:
        faltantes.append({"coleccion": "muros", "id": muro["id"], "campo": "espesor"})
    for clave in ("nivel_inferior", "nivel_superior"):
        if niveles[muro[clave]]["cota"] is None:
            faltantes.append({"coleccion": "niveles", "id": muro[clave], "campo": "cota"})
    return faltantes


def _valido(valor: float) -> bool:
    return math.isfinite(valor) and valor > 0


def _superficie(
    muro: dict, nodos: dict, niveles: dict, derivados: dict, procedencia_raiz: dict
) -> tuple[dict | None, list[str]]:
    a, b = nodos[muro["nodo_inicio"]], nodos[muro["nodo_fin"]]
    z0 = niveles[muro["nivel_inferior"]]["cota"]
    z1 = niveles[muro["nivel_superior"]]["cota"]
    # Longitud y altura provienen del validador, que ya rechaza valores no representables.
    longitud = derivados[muro["id"]]["longitud"]
    altura = derivados[muro["id"]]["altura"]
    # El área es propia del plan: dos factores finitos pueden dar un producto infinito o cero.
    area = longitud * altura
    espesor = muro["espesor"]
    invalidos = [
        nombre
        for nombre, valor in (("longitud_m", longitud), ("altura_m", altura), ("area_bruta_m2", area), ("espesor_m", espesor))
        if not _valido(valor)
    ]
    if invalidos:
        return None, invalidos
    propia = muro.get("procedencia")
    superficie = {
        "muro_id": muro["id"],
        "naturaleza": "propuesta_geometrica",
        "nodo_inicio": muro["nodo_inicio"],
        "nodo_fin": muro["nodo_fin"],
        "nivel_inferior": muro["nivel_inferior"],
        "nivel_superior": muro["nivel_superior"],
        "espesor_m": espesor,
        "longitud_m": longitud,
        "altura_m": altura,
        "area_bruta_m2": area,
        "vertices_m": [
            [a["x"], a["y"], z0],
            [b["x"], b["y"], z0],
            [b["x"], b["y"], z1],
            [a["x"], a["y"], z1],
        ],
        "procedencia": copy.deepcopy(propia if propia is not None else procedencia_raiz),
        "procedencia_declarada_en": "muro" if propia is not None else "contrato",
    }
    if "observaciones" in muro:
        superficie["observaciones"] = muro["observaciones"]
    return superficie, []


def _json_estricto(plan: dict[str, Any]) -> dict[str, Any]:
    """Copia independiente vía JSON estricto; falla si quedara NaN o Infinity."""
    return json.loads(json.dumps(plan, ensure_ascii=False, allow_nan=False))


def serializar(plan: dict[str, Any]) -> str:
    """Texto JSON determinista del plan, tal como se guarda en el ejemplo versionado."""
    return json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


# -- regeneración del ejemplo (único punto con lectura/escritura) -------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera un plan geométrico a partir de un contrato de geometría.")
    parser.add_argument("geometria", type=Path, help="JSON draft2model.geometria v0.1")
    parser.add_argument("--salida", type=Path, required=True, help="Archivo JSON del plan (UTF-8)")
    parser.add_argument("--sobrescribir", action="store_true", help="Permite reemplazar un archivo de salida existente")
    args = parser.parse_args(argv)
    try:
        geometria = cargar_geometria(args.geometria)
    except ErrorLecturaGeometria as error:
        print(f"Operación no completada: {error}", file=sys.stderr)
        return 1
    if args.salida.exists() and not args.sobrescribir:
        print("Operación no completada: la salida existe; use --sobrescribir para reemplazarla.", file=sys.stderr)
        return 1
    plan = preparar_plan_modelado(geometria)
    args.salida.write_text(serializar(plan), encoding="utf-8", newline="\n")
    print(f"Plan: {args.salida} | estado de origen: {plan['estado_origen']} | cobertura: {plan['cobertura']} | "
          f"superficies: {len(plan['superficies'])} | omisiones: {len(plan['omisiones'])} | ejecutable_en_etabs: false")
    return 2 if plan["estado_origen"] == ESTADO_INCONSISTENTE else 0


if __name__ == "__main__":
    raise SystemExit(main())
