"""Módulo 1: Sistema Aporticado de Concreto Armado (Draft2Model).

Especificación integral de requisitos de datos de entrada, criterios normativos
y reglas de verificación para edificaciones estructuradas con pórticos de concreto
armado resistentes a momentos según el Reglamento Nacional de Edificaciones (RNE):
- Norma Técnica E.030-2026: Diseño Sismorresistente (R0 = 8, CT = 35, Deriva <= 0.007).
- Norma Técnica E.060: Concreto Armado (Inercias agrietadas, zonas rígidas, secciones mínimas).
- Norma Técnica E.020: Cargas (Metrado de cargas gravitacionales y tabiquería aislada).
"""

from __future__ import annotations

import copy
import math
from typing import Any

from .modulos_sistema import MODULO_PORTICADO
from .normativa_e030 import (
    TABLA1_Z,
    TABLA4_S,
    TABLA5_TP,
    TABLA5_TL,
    TABLA7_U,
    TABLA10_R0,
    TABLA14_DERIVA,
    coeficiente_r,
    cortante_basal_estatico,
    deriva_admisible,
    espectro,
    factor_c,
    factor_uso,
    factor_zona,
    parametros_sitio,
    periodo_aproximado
)


# -- Requisitos de Datos de Entrada por Etapa ----------------------------------------------------

REQUISITOS_ETAPA_1_EXPEDIENTE = {
    "etapa": 1,
    "nombre": "Expediente Documental y Planos",
    "descripcion": "Láminas esenciales requeridas para un sistema aporticado de concreto armado.",
    "documentos_requeridos": [
        {
            "codigo": "PLANO_ARQ",
            "descripcion": "Láminas de Arquitectura (Plantas por nivel, elevaciones y cortes con alturas libres de entrepiso y vanos)",
            "obligatorio": True
        },
        {
            "codigo": "PLANO_EST_CIMENTACION",
            "descripcion": "Plano de Cimentación (Zapatas aisladas/conectadas, vigas de cimentación y detalles de empotramiento de columnas)",
            "obligatorio": True
        },
        {
            "codigo": "PLANO_EST_COLUMNAS",
            "descripcion": "Plano y Cuadro de Columnas (Dimensiones b x h, orientación geométrica en planta, refuerzo longitudinal y estribos)",
            "obligatorio": True
        },
        {
            "codigo": "PLANO_EST_VIGAS",
            "descripcion": "Plano de Encofrado de Vigas y Aligerados (Secciones de vigas principales y secundarias, peraltes, luces libres)",
            "obligatorio": True
        },
        {
            "codigo": "PLANO_DET_TABIQUERIA",
            "descripcion": "Detalles de tabiquería no portante con juntas sísmicas de tecnopor (mínimo 2.5 cm) para garantizar aislamiento del pórtico",
            "obligatorio": False,
            "nota": "Si no se aísla, debe evaluarse la interacción de columna corta."
        }
    ]
}

REQUISITOS_ETAPA_2_EXTRACCIONES = {
    "etapa": 2,
    "nombre": "Extracciones de Datos y Parámetros",
    "candidatos_esperados": [
        {"campo": "material_concreto_fc", "unidad": "kgf/cm2", "rango_valido": (210.0, 450.0), "ejemplo": 210.0},
        {"campo": "material_acero_fy", "unidad": "kgf/cm2", "valor_norma": 4200.0},
        {"campo": "espesor_losa_aligerada", "unidad": "m", "valores_tipicos": [0.17, 0.20, 0.25]},
        {"campo": "sobrecarga_uso_piso_tipico", "unidad": "kN/m2", "ejemplo": 2.0},
        {"campo": "sobrecarga_uso_azotea", "unidad": "kN/m2", "ejemplo": 1.0},
        {"campo": "peso_acabados", "unidad": "kN/m2", "ejemplo": 1.0},
        {"campo": "peso_tabiqueria_distribuida", "unidad": "kN/m2", "rango_tipico": (1.0, 1.5)},
        {"campo": "zona_sismica", "rango": [1, 2, 3, 4], "ejemplo": 4},
        {"campo": "perfil_suelo", "valores": ["S0", "S1", "S2", "S3", "S4"], "ejemplo": "S1"},
        {"campo": "categoria_edificacion", "valores": ["A2", "B", "C"], "ejemplo": "C"}
    ]
}

REQUISITOS_ETAPA_3_GEOMETRIA = {
    "etapa": 3,
    "nombre": "Geometría Estructural y Niveles",
    "elementos_geom": {
        "niveles": "Cotas acumuladas Z (m) desde la base hasta la cubierta superior",
        "grilla_ortogonal": "Ejes alfabéticos (X) y numéricos (Y) con cotas entre ejes",
        "nudos": "Intersecciones ortogonales de ejes resistentes",
        "lineas_columnas": "Elementos verticales entre nudos de niveles consecutivos",
        "lineas_vigas": "Elementos horizontales conectando columnas en cada nivel",
        "paneles_losa": "Superficies de entrepiso delimitadas por vigas perimetrales",
        "muros_de_corte": "NO PERMITIDOS en cantidad significativa (los pórticos deben tomar >= 80% del cortante en la base)"
    }
}

REQUISITOS_ETAPA_4_CONFIGURACION = {
    "etapa": 4,
    "nombre": "Configuración Estructural e Hipótesis de Modelado",
    "parametros_normativos": {
        "sistema_resistente": "concreto_porticos",
        "r0": 8.0,
        "ct": 35.0,
        "deriva_limite": 0.007,
        "factor_amplificacion_deriva": "0.75 * R si es regular, 0.85 * R si es irregular",
        "modificadores_inercia": {
            "columnas_I22": 0.70,
            "columnas_I33": 0.70,
            "vigas_I33": 0.35,
            "vigas_I22": 0.35,
            "area_axial": 1.00,
            "area_corte": 1.00
        },
        "zonas_rigidas_nudos": {
            "rigid_zone_factor": 0.50,
            "motivo": "Considera la flexibilidad parcial de la zona de panel nudo viga-columna (E.060 Art. 10.11)"
        },
        "diafragmas": "Rigid diaphragm en cada piso",
        "apoyos": "Empotramiento perfecto en la base (U1=U2=U3=R1=R2=R3=True)"
    }
}

REQUISITOS_ETAPA_5_MODELO = {
    "etapa": 5,
    "nombre": "Construcción de Modelo ETABS",
    "operaciones_clave": [
        "Definición de materiales ISOTROPIC CONCRETE_FC210 / FC280 y REBAR_FY4200.",
        "Definición de secciones FRAME rectangulares para columnas y vigas.",
        "Asignación de Property Modifiers para agrietamiento (0.70 columnas, 0.35 vigas).",
        "Asignación de End Length Offsets automáticos con 50% de zona rígida.",
        "Dibujo de frames de columnas y vigas entre coordenadas de grilla.",
        "Creación de diafragmas rígidos Diaph1, Diaph2, etc.",
        "Asignación de cargas uniformes en losas y cargas lineales de tabiquería en vigas.",
        "Configuración de fuente de masa MsSrc1 (1.00 Dead + 0.25 Live + 1.00 Tabiquería).",
        "Definición de función de respuesta espectral E.030-2026 R=8 y R=1 para derivas."
    ]
}

REQUISITOS_ETAPA_6_ANALISIS = {
    "etapa": 6,
    "nombre": "Análisis y Comprobaciones Post-Solver",
    "controles_obligatorios": [
        {
            "id": "PARTICIPACION_MASA_MODAL",
            "criterio": "Suma de masa modal participativa >= 90% en X y en Y",
            "cita": "Norma E.030-2026 Art. 28",
            "tolerancia": 0.90
        },
        {
            "id": "CONTROL_DERIVA_MAXIMA",
            "criterio": "Deriva inelástica máxima en entrepiso <= 0.007 en X y en Y",
            "cita": "Norma E.030-2026 Tabla N° 14 (Concreto Armado)",
            "limite": 0.007
        },
        {
            "id": "ESCALAMIENTO_CORTANTE_BASAL",
            "criterio": "V_dinámico >= 80% V_estático (regular) u 90% V_estático (irregular)",
            "cita": "Norma E.030-2026 Art. 44.1"
        },
        {
            "id": "ESTABILIDAD_NUMERICA_SOLVER",
            "criterio": "0 autovalores negativos en la matriz de rigidez global y 0 singularidades",
            "cita": "Control de solucionador matricial CSI ETABS"
        },
        {
            "id": "CONTROL_COLUMNA_FUERTE_VIGA_DEBIL",
            "criterio": "Momento resistente de columnas >= 1.2 x momento resistente de vigas concurrentes",
            "cita": "Norma E.060 Art. 21.4.2"
        }
    ]
}

REQUISITOS_ETAPA_7_INFORME = {
    "etapa": 7,
    "nombre": "Informe Técnico y Panel Interactivo",
    "secciones_entregable": [
        "1. Identificación y Alcance del Módulo de Pórticos de Concreto Armado.",
        "2. Criterios de Diseño Sismorresistente según E.030-2026 (Z=0.45, U=1.0, S, R=8, CT=35).",
        "3. Especificación de Materiales y Propiedades de Sección (Inercias agrietadas E.060).",
        "4. Cuadro Resumen de Cargas Gravitacionales y Masa Sísmica.",
        "5. Resultados Modales: Períodos fundamentales T1, T2, T3 y Masa Participativa.",
        "6. Envolvente de Cortante Basal Estático vs Dinámico y Factores de Escala.",
        "7. Distorsiones Inelásticas de Entrepiso y Verificación frente al Límite 0.007.",
        "8. Conclusiones de Aprobación Técnica y Recomendaciones de Detalle de Refuerzo."
    ]
}


# -- Funciones de Validación y Cálculo para Pórticos de Concreto ----------------------------------

def calcular_parametros_porticado(
    *,
    zona: int,
    categoria: str,
    perfil: str,
    altura_total_hn: float,
    irregular_altura: float = 1.0,
    irregular_planta: float = 1.0,
    vs30: float | None = None
) -> dict[str, Any]:
    """Calcula los parámetros sísmicos normativos completos para el Módulo de Sistema Aporticado."""
    # Factor de zona Z
    z_info = factor_zona(zona)
    z = z_info["Z"]

    # Factor de uso U
    u_info = factor_uso(categoria)
    u = u_info["U"]

    # Parámetros de sitio S, TP, TL
    sitio_info = parametros_sitio(zona, perfil, vs30=vs30)
    s = sitio_info["S"]
    tp = sitio_info["TP"]
    tl = sitio_info["TL"]

    # Coeficiente R para pórticos (R0 = 8)
    r_info = coeficiente_r("concreto_porticos", irregular_altura, irregular_planta)
    r = r_info["R"]

    # Período aproximado con CT = 35
    periodo_info = periodo_aproximado(altura_total_hn, "porticos_concreto")
    t_aprox = periodo_info["T_s"]

    # Factor de amplificación sísmica C
    c_info = factor_c(t_aprox, tp, tl)
    c_val = c_info["C"]

    # Deriva admisible
    es_regular = (irregular_altura >= 0.999 and irregular_planta >= 0.999)
    deriva_info = deriva_admisible("concreto_armado", regular=es_regular, R=r)

    # Espectro inelástico (tabla de aceleraciones)
    periodos_espectro = [round(i * 0.05, 2) for i in range(1, 81)]  # 0.05 s a 4.00 s
    espectro_info = espectro(Z=z, U=u, S=s, R=r, TP=tp, TL=tl, periodos=periodos_espectro)

    # Espectro elástico R=1 (para derivas)
    espectro_r1 = espectro(Z=z, U=u, S=s, R=1.0, TP=tp, TL=tl, periodos=periodos_espectro)

    return {
        "modulo": MODULO_PORTICADO["id"],
        "nombre_modulo": MODULO_PORTICADO["nombre"],
        "parametros": {
            "Z": z,
            "U": u,
            "S": s,
            "TP": tp,
            "TL": tl,
            "R0": 8.0,
            "Ia": irregular_altura,
            "Ip": irregular_planta,
            "R": r,
            "CT": 35.0,
            "hn_m": altura_total_hn,
            "T_aprox_s": t_aprox,
            "C_aprox": c_val,
            "es_regular": es_regular,
            "deriva_limite": deriva_info["limite"],
            "factor_deriva_inelastica": deriva_info["factor_desplazamiento"]
        },
        "modificadores_inercia": MODULO_PORTICADO["normativa"]["concreto"]["modificador_inercia_columnas"],
        "factor_zona_rigida": MODULO_PORTICADO["normativa"]["concreto"]["factor_zona_rigida_nudos"],
        "espectro_diseno_r": espectro_info,
        "espectro_elastico_r1": espectro_r1,
        "citas": {
            "zona": z_info["cita"],
            "uso": u_info["cita"],
            "sitio": sitio_info["cita"],
            "r": r_info["cita"],
            "periodo": periodo_info["cita"],
            "deriva": deriva_info["cita"]
        }
    }


def verificar_secciones_porticado(
    secciones: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Verifica si las secciones de columnas y vigas cumplen con los requisitos mínimos de E.060 Cap. 21."""
    reporte = []
    for sec in secciones:
        tipo = sec.get("tipo", "")
        sec_id = sec.get("id", "")
        dims = sec.get("dimensiones", {})
        ancho = dims.get("ancho_m", 0.0)
        alto = dims.get("alto_m", 0.0)

        if "col" in sec_id.lower() or "c" in sec_id.lower():
            # Verificación de columnas (E.060 Art. 21.4.1)
            area = ancho * alto
            menor_dim = min(ancho, alto)
            cumple_dim = menor_dim >= 0.25
            cumple_area = area >= 0.10  # 1000 cm2 = 0.10 m2
            reporte.append({
                "seccion": sec_id,
                "elemento": "columna",
                "ancho_m": ancho,
                "alto_m": alto,
                "area_m2": area,
                "cumple_dimension_minima_25cm": cumple_dim,
                "cumple_area_minima_1000cm2": cumple_area,
                "valido": cumple_dim and cumple_area,
                "observacion": "Conforme con E.060 Art. 21.4.1" if (cumple_dim and cumple_area) else "Dimensiones inferiores al estándar sísmico de columnas"
            })
        elif "vig" in sec_id.lower() or "v" in sec_id.lower():
            # Verificación de vigas (E.060 Art. 21.3.1)
            menor_dim = ancho
            esbeltez = alto / ancho if ancho > 0 else 0
            cumple_ancho = menor_dim >= 0.25
            cumple_esbeltez = esbeltez <= 4.0
            reporte.append({
                "seccion": sec_id,
                "elemento": "viga",
                "ancho_m": ancho,
                "peralte_m": alto,
                "relacion_h_b": round(esbeltez, 2),
                "cumple_ancho_minimo_25cm": cumple_ancho,
                "cumple_relacion_h_b_max_4": cumple_esbeltez,
                "valido": cumple_ancho and cumple_esbeltez,
                "observacion": "Conforme con E.060 Art. 21.3.1" if (cumple_ancho and cumple_esbeltez) else "Ancho o peralte fuera de límites sísmicos de viga"
            })
    return reporte


def validar_derivas_porticado(
    derivas_por_piso: list[dict[str, Any]]
) -> dict[str, Any]:
    """Evalúa si las derivas inelásticas de cada piso cumplen con el límite de 0.007 de E.030."""
    LIMITE = 0.007
    filas = []
    max_deriva = 0.0
    piso_critico = ""
    direccion_critica = ""
    cumple_global = True

    for item in derivas_por_piso:
        nivel = item.get("nivel", "")
        dx = float(item.get("deriva_x", 0.0))
        dy = float(item.get("deriva_y", 0.0))

        cumple_x = dx <= LIMITE
        cumple_y = dy <= LIMITE
        if not (cumple_x and cumple_y):
            cumple_global = False

        if dx > max_deriva:
            max_deriva = dx
            piso_critico = nivel
            direccion_critica = "X"
        if dy > max_deriva:
            max_deriva = dy
            piso_critico = nivel
            direccion_critica = "Y"

        filas.append({
            "nivel": nivel,
            "deriva_x": dx,
            "deriva_y": dy,
            "cumple_x": cumple_x,
            "cumple_y": cumple_y,
            "margen_seguridad_x": round((LIMITE - dx) / LIMITE * 100, 1),
            "margen_seguridad_y": round((LIMITE - dy) / LIMITE * 100, 1)
        })

    return {
        "limite_normativo": LIMITE,
        "norma": "E.030-2026 Tabla N° 14 (Concreto Armado)",
        "cumple_todas_derivas": cumple_global,
        "maxima_deriva": max_deriva,
        "piso_critico": piso_critico,
        "direccion_critica": direccion_critica,
        "niveles": filas
    }


def obtener_especificacion_modulo(modulo_id: str | None = "porticado") -> dict[str, Any]:
    """Retorna la especificación técnica completa del módulo requerido."""
    from .modulos_sistema import obtener_modulo, MODULO_PORTICADO, MODULO_ALBANILERIA
    mod = obtener_modulo(modulo_id)
    es_porticado = mod["id"] == "porticado"
    if es_porticado:
        return {
            "modulo": mod,
            "etapas_requisitos": [
                REQUISITOS_ETAPA_1_EXPEDIENTE,
                REQUISITOS_ETAPA_2_EXTRACCIONES,
                REQUISITOS_ETAPA_3_GEOMETRIA,
                REQUISITOS_ETAPA_4_CONFIGURACION,
                REQUISITOS_ETAPA_5_MODELO,
                REQUISITOS_ETAPA_6_ANALISIS,
                REQUISITOS_ETAPA_7_INFORME,
            ],
            "parametros_referencia": {
                "r0": 8.0,
                "ct": 35.0,
                "deriva_limite": 0.007,
                "modificador_columna": 0.70,
                "modificador_viga": 0.35,
                "offset_zona_rigida": 0.50,
                "peso_sismico": "1.00 CM + 0.25 CV (Cat C)",
                "ancho_minimo_columna_m": 0.25,
                "area_minima_columna_m2": 0.10,
                "ancho_minimo_viga_m": 0.25,
            },
            "estado_preparacion": {
                "listo_para_ingesta_curso": True,
                "archivos_esperados": [
                    "Planos de arquitectura (plantas y cortes)",
                    "Planos de estructuras (cimentación, columnas, vigas, losas)",
                    "Estudio de Mecánica de Suelos (EMS) o tipo de suelo S",
                    "Ubicación geográfica del proyecto (Zona sísmica Z)"
                ]
            }
        }
    else:
        return {
            "modulo": mod,
            "caso_demostracion": "pueblo-libre-v04",
            "parametros_referencia": {
                "r0": 3.0,
                "ct": 60.0,
                "deriva_limite": 0.005,
                "fm_kgf_cm2": 35.0,
                "Em_kgf_cm2": 17500.0,
                "peso_sismico": "1.00 CM + 0.25 CV (Cat C)",
            },
            "estado_preparacion": {
                "listo_para_ingesta_curso": False,
                "nota": "Módulo secundario en fase de desarrollo. Caso de validación activo: pueblo-libre-v04."
            }
        }

