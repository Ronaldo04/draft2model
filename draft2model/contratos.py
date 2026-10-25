"""Contrato de geometría v0.1: propuesta inicial, no especificación aprobada.

Define nombres, versiones, unidades y campos admitidos. No contiene umbrales
normativos, criterios sísmicos ni tolerancias estructurales.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

CONTRATO_GEOMETRIA = "draft2model.geometria"
VERSION_GEOMETRIA = "0.1.0"
VERSION_GEOMETRIA_SUPERFICIES = "0.2.0"
VERSION_GEOMETRIA_ABERTURAS = "0.3.0"

# Divisores enteros exactos hacia metros: dividir por 100 o 1000 redondea una
# sola vez, por lo que 260 cm, 2600 mm y 2.6 m producen el mismo float.
DIVISORES_A_METROS = {"m": 1, "cm": 100, "mm": 1000}

ESTADOS_REVISION = ("borrador", "en_revision", "observado", "aprobado")
TIPOS_PROCEDENCIA = ("sintetico", "plano", "levantamiento", "supuesto")

PATRON_ID = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}"

CAMPOS_RAIZ = (
    "contrato",
    "version_contrato",
    "id",
    "unidad_longitud",
    "procedencia",
    "niveles",
    "nodos",
    "muros",
    "faltantes",
    "revision",
)
CAMPOS_PROCEDENCIA = {
    "obligatorios": ("tipo", "descripcion"),
    "opcionales": ("expediente_id", "lamina", "referencias", "justificacion"),
}
CAMPOS_FALTANTE = {
    "obligatorios": ("descripcion",),
    "opcionales": ("coleccion", "id", "campo"),
}
CAMPOS_REVISION = {"obligatorios": ("estado", "aprobacion"), "opcionales": ()}
CAMPOS_APROBACION = {
    "obligatorios": ("declarada_por", "fecha", "huella_contenido"),
    "opcionales": ("alcance", "observaciones"),
}

# "anulables": el valor null representa un dato faltante y debe declararse en
# "faltantes". "longitudes": campos que se normalizan a metros.
COLECCIONES: dict[str, dict[str, tuple[str, ...]]] = {
    "niveles": {
        "obligatorios": ("id", "cota"),
        "opcionales": ("nombre", "procedencia", "tipo"),  # tipo: "piso" (por omisión) | "auxiliar" (ensayo257)
        "anulables": ("cota",),
        "longitudes": ("cota",),
    },
    "nodos": {
        "obligatorios": ("id", "x", "y"),
        "opcionales": ("procedencia",),
        "anulables": (),
        "longitudes": ("x", "y"),
    },
    "muros": {
        "obligatorios": (
            "id",
            "nodo_inicio",
            "nodo_fin",
            "nivel_inferior",
            "nivel_superior",
            "espesor",
        ),
        "opcionales": ("procedencia", "observaciones"),
        "anulables": ("espesor",),
        "longitudes": ("espesor",),
    },
}


CAMPOS_RAIZ_SUPERFICIES = CAMPOS_RAIZ + ("vertices", "superficies")
CAMPOS_VERTICE = {"obligatorios": ("id", "x", "y", "z", "procedencia"), "opcionales": ()}
CAMPOS_SUPERFICIE = {"obligatorios": ("id", "vertices", "papel_geometrico", "procedencia"), "opcionales": ()}
CAMPOS_RAIZ_ABERTURAS = CAMPOS_RAIZ_SUPERFICIES + ("aberturas",)
CAMPOS_ABERTURA = {"obligatorios": ("id", "superficie", "vertices", "procedencia"), "opcionales": ()}


def huella_contenido(data: dict[str, Any]) -> str:
    """SHA256 del contenido canónico sin el bloque "revision".

    Una aprobación registrada declara esta huella; si la geometría cambia,
    la huella deja de coincidir y la aprobación no se aplica al nuevo contenido.
    """
    contenido = {clave: valor for clave, valor in data.items() if clave != "revision"}
    canonico = json.dumps(
        contenido, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False
    )
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()
