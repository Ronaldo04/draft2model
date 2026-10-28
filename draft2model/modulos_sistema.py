"""Arquitectura de Módulos Estructurales de Draft2Model.

Define la modularidad del sistema según la tipología constructiva:
- Módulo 1: Sistema Aporticado de Concreto Armado (RNE E.030-2026, E.060, E.020) [Módulo Principal / Producción].
- Módulo 2: Sistema de Albañilería Confinada (RNE E.070, E.030-2026, E.060, E.020) [En Fase de Desarrollo / Demostración].
"""

from __future__ import annotations

from typing import Any

MODULO_PORTICADO = {
    "id": "porticado",
    "numero": 1,
    "nombre": "Sistema Aporticado de Concreto Armado",
    "titulo": "Módulo 1: Sistema Aporticado (Pórticos de Concreto Armado)",
    "estado": "produccion_activo",
    "etiqueta_ui": "Módulo Principal · Producción Activa",
    "descripcion": (
        "Edificaciones cuyo sistema sismorresistente lateral está conformado por pórticos rígidos "
        "de vigas y columnas de concreto armado resistentes a momento, según E.030-2026 y E.060."
    ),
    "normativa": {
        "sismo": {
            "codigo": "E.030-2026",
            "titulo": "Diseño Sismorresistente",
            "r0": 8.0,
            "sistema_tabla10": "concreto_porticos",
            "ct_art36": 35.0,
            "deriva_max_tabla14": 0.007,
            "fraccion_cortante_minimo_regular": 0.80,
            "fraccion_cortante_minimo_irregular": 0.90,
            "formula_periodo": "T = hn / 35"
        },
        "concreto": {
            "codigo": "E.060",
            "titulo": "Concreto Armado",
            "modificador_inercia_columnas": 0.70,
            "modificador_inercia_vigas": 0.35,
            "modificador_inercia_vigas_derivas": 0.50,
            "factor_zona_rigida_nudos": 0.50,
            "dimension_minima_columna_m": 0.25,
            "area_minima_columna_m2": 0.10,
            "ancho_minimo_viga_m": 0.25,
            "relacion_esbeltez_viga_max": 4.0,
            "criterio_fuerte_columna_debil_viga": True
        },
        "cargas": {
            "codigo": "E.020",
            "titulo": "Cargas",
            "peso_concreto_armado_kN_m3": 24.0,
            "sobrecarga_vivienda_kN_m2": 2.0,
            "sobrecarga_azotea_kN_m2": 1.0,
            "peso_acabados_kN_m2": 1.0
        }
    },
    "hipotesis_modelado": [
        "Pórticos espaciales 3D con conexiones rígidas viga-columna (frame elements tridimensionales).",
        "Base fija empotrada en nudos de cimentación (Z = 0.00 m).",
        "Diafragmas rígidos horizontales en cada nivel de entrepiso.",
        "Modificadores de inercia agrietada según E.060: 0.70 Ig en columnas y 0.35 Ig en vigas.",
        "Zonas rígidas en nudos de 50% para representar la dimensión física de la conexión viga-columna.",
        "Tabiquería no portante debidamente aislada con juntas sísmicas (e >= 2.5 cm); modelada solo como carga muerta gravitacional.",
        "Masa sísmica según E.030 Art. 31: 100% Carga Muerta + 25% Carga Viva (categoría C)."
    ],
    "elementos_requeridos": {
        "columnas": True,
        "vigas": True,
        "losas": True,
        "muros_de_corte": False,
        "placas": False,
        "panos_albanileria": False
    }
}

MODULO_ALBANILERIA = {
    "id": "albanileria",
    "numero": 2,
    "nombre": "Albañilería Confinada",
    "titulo": "Módulo 2: Sistema de Albañilería Confinada (Muros Portantes)",
    "estado": "fase_desarrollo",
    "etiqueta_ui": "Módulo Secundario · En Fase de Desarrollo",
    "descripcion": (
        "Edificaciones cuyos muros portantes de ladrillo de arcilla cocida confinados por columnas y vigas "
        "resisten las fuerzas de gravedad y sismo, según E.070 y E.030-2026."
    ),
    "normativa": {
        "sismo": {
            "codigo": "E.030-2026",
            "titulo": "Diseño Sismorresistente",
            "r0": 3.0,
            "sistema_tabla10": "albanileria_armada_o_confinada",
            "ct_art36": 60.0,
            "deriva_max_tabla14": 0.005,
            "fraccion_cortante_minimo_regular": 0.80,
            "fraccion_cortante_minimo_irregular": 0.90,
            "formula_periodo": "T = hn / 60"
        },
        "albanileria": {
            "codigo": "E.070",
            "titulo": "Albañilería",
            "resistencia_prisma_fm_kgf_cm2": 35.0,
            "modulo_elasticidad_Em_kgf_cm2": 17500.0,
            "modulo_corte_Gm_kgf_cm2": 7000.0,
            "espesor_efectivo_minimo_soga_m": 0.13,
            "densidad_minima_muros_por_eje": True
        },
        "concreto": {
            "codigo": "E.060",
            "titulo": "Concreto Armado de Confinamiento",
            "resistencia_fc_kgf_cm2": 210.0,
            "acero_fy_kgf_cm2": 4200.0
        }
    },
    "hipotesis_modelado": [
        "Muros portantes modelados como elementos de área shell thin o columna ancha.",
        "Columnas y vigas de confinamiento solidarias con el muro.",
        "Diafragma rígido horizontal en cada piso.",
        "Deriva máxima restringida a 0.005 según Tabla 14 E.030.",
        "Caso de referencia validado y conservado: pueblo-libre-v04."
    ],
    "elementos_requeridos": {
        "columnas": True,
        "vigas": True,
        "losas": True,
        "muros_de_corte": True,
        "placas": True,
        "panos_albanileria": True
    },
    "caso_demostracion": "pueblo-libre-v04"
}

MODULOS_SISTEMA: dict[str, dict[str, Any]] = {
    "porticado": MODULO_PORTICADO,
    "albanileria": MODULO_ALBANILERIA
}


def listar_modulos() -> list[dict[str, Any]]:
    """Devuelve la lista ordenada de módulos disponibles."""
    return [MODULO_PORTICADO, MODULO_ALBANILERIA]


def obtener_modulo(modulo_id: str | None) -> dict[str, Any]:
    """Obtiene la definición de un módulo por su clave (por defecto 'porticado')."""
    if not modulo_id:
        return MODULO_PORTICADO
    key = str(modulo_id).strip().lower()
    if key in ("porticado", "porticados", "portico", "concreto_porticos", "1", "modulo_1"):
        return MODULO_PORTICADO
    if key in ("albanileria", "albanileria_confinada", "muros", "2", "modulo_2"):
        return MODULO_ALBANILERIA
    raise ValueError(f"Módulo no reconocido: '{modulo_id}'. Opciones disponibles: 'porticado', 'albanileria'.")
