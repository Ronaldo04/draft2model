"""Conversión explícita y revisable de lecturas comprobadas a geometría borrador.

No interpreta planos, píxeles ni conectividad. El operador declara correspondencias,
ejes y coordenadas físicas. La evidencia se comprueba de nuevo antes de publicar.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from . import contratos as c
from . import gestion_extraccion as e
from .extraccion_preliminar import exportar_revisados
from .validacion_geometria import validar_geometria

CONTRATO = "draft2model.conversion_geometria"
VERSION = "0.1.0"
VERSION_SUPERFICIES = "0.2.0"
VERSION_ABERTURAS = "0.3.0"
CARPETA = "conversiones_geometria"
AVISO = (
    "Correspondencias y coordenadas declaradas por el operador; no se infiere conectividad, "
    "escala de imagen ni seguridad estructural. La geometría queda en borrador sin aprobación."
)


@dataclass
class ResultadoConversion:
    identificador: str
    ruta: Path
    geometria: dict[str, Any]
    trazabilidad: dict[str, Any]


def _rechazar(mensaje: str) -> None:
    raise e.ErrorEvidencia("Conversión rechazada.", [mensaje])


def _objeto(valor: Any, claves: set[str], ruta: str) -> dict:
    if not isinstance(valor, dict) or set(valor) != claves:
        _rechazar(f"{ruta}: se requieren exactamente los campos {', '.join(sorted(claves))}.")
    return valor


def _texto(valor: Any, ruta: str) -> str:
    if not isinstance(valor, str) or not valor.strip():
        _rechazar(f"{ruta}: se requiere texto no vacío.")
    return valor


def _hash(contenido: bytes) -> str:
    return hashlib.sha256(contenido).hexdigest()


def _bytes(valor: Any) -> bytes:
    return (json.dumps(valor, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _canonico(valor: Any) -> str:
    return json.dumps(valor, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _numero(valor: Any, ruta: str) -> float:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)):
        _rechazar(f"{ruta}: se requiere una longitud numérica conocida.")
    try:
        numero = float(valor)
    except (OverflowError, ValueError):
        _rechazar(f"{ruta}: longitud fuera de rango.")
    if not math.isfinite(numero):
        _rechazar(f"{ruta}: longitud no finita.")
    if isinstance(valor, int) and numero != valor:
        _rechazar(f"{ruta}: entero no representable exactamente como longitud binary64.")
    return numero


def _construir(exportacion: dict, manifiesto: Any) -> tuple[dict, list[dict]]:
    aberturas_v03 = isinstance(manifiesto, dict) and manifiesto.get("version_contrato") == VERSION_ABERTURAS
    superficies_v02 = isinstance(manifiesto, dict) and manifiesto.get("version_contrato") in (VERSION_SUPERFICIES, VERSION_ABERTURAS)
    campos_raiz = {
        "contrato", "version_contrato", "caso", "datos_sinteticos", "operador_declarado",
        "procedencia", "unidad_longitud", "sistema_coordenadas", "ejes", "escala",
        "niveles", "nodos", "muros",
    }
    if superficies_v02:
        campos_raiz.update(("vertices", "superficies"))
    if aberturas_v03:
        campos_raiz.add("aberturas")
    _objeto(manifiesto, campos_raiz, "manifiesto")
    if manifiesto["contrato"] != CONTRATO or manifiesto["version_contrato"] not in (VERSION, VERSION_SUPERFICIES, VERSION_ABERTURAS):
        _rechazar("Contrato o versión del manifiesto no admitidos.")
    if manifiesto["caso"] != exportacion["caso"]:
        _rechazar("El manifiesto pertenece a otro caso.")
    _texto(manifiesto["operador_declarado"], "operador_declarado")
    sintetico = manifiesto["datos_sinteticos"]
    if type(sintetico) is not bool:
        _rechazar("datos_sinteticos debe ser booleano explícito.")
    procedencia = _objeto(manifiesto["procedencia"], {"tipo", "descripcion"}, "procedencia")
    _texto(procedencia["descripcion"], "procedencia.descripcion")
    if procedencia["tipo"] != ("sintetico" if sintetico else "plano"):
        _rechazar("La procedencia geométrica no corresponde a la marca sintética declarada.")
    fuente_sintetica = exportacion["procedencia"]["tipo"] == "sintetico" or any(
        candidato["metodo"]["tipo"] == "sintetico" for candidato in exportacion["candidatos"]
    )
    if fuente_sintetica and not sintetico:
        _rechazar("No se convierten lecturas sintéticas en geometría real.")
    unidad = manifiesto["unidad_longitud"]
    if not isinstance(unidad, str) or unidad not in c.DIVISORES_A_METROS:
        _rechazar("unidad_longitud debe ser m, cm o mm.")
    if manifiesto["sistema_coordenadas"] != "cartesiano_ortogonal":
        _rechazar("Se requieren coordenadas físicas cartesianas ortogonales; no píxeles ni bbox.")
    ejes = _objeto(manifiesto["ejes"], {"origen", "direccion_x", "direccion_y"}, "ejes")
    for clave, valor in ejes.items():
        _texto(valor, f"ejes.{clave}")
    escala = _objeto(manifiesto["escala"], {"metodo", "descripcion"}, "escala")
    if escala["metodo"] != "coordenadas_fisicas_declaradas":
        _rechazar("La escala admite solo coordenadas físicas declaradas; no se mide desde imágenes.")
    _texto(escala["descripcion"], "escala.descripcion")
    candidatos = {item["id"]: item for item in exportacion["candidatos"]}
    trazas = []

    def referencia(ident: Any) -> dict:
        if not isinstance(ident, str) or ident not in candidatos:
            _rechazar("Referencia a candidato ausente, pendiente o rechazado.")
        candidato = candidatos[ident]
        if candidato["revision"]["estado"] != "revisado" or not candidato["evidencia"] or any(
            ev.get("estado_referencia") != "comprobada" for ev in candidato["evidencia"]
        ):
            _rechazar(f"Candidato {ident}: revisión o evidencia no comprobadas completamente.")
        return candidato

    def medida(valor: Any, ruta: str) -> float:
        if isinstance(valor, dict) and set(valor) == {"candidato"}:
            cand = referencia(valor["candidato"])
            if cand["tipo"] != "cota":
                _rechazar(f"{ruta}: una medida desde candidato requiere tipo cota.")
            numero, unidad_origen = cand["valor_revisado"], cand["unidad_revisada"]
            refs = [cand["id"]]
            modo = "candidato_revisado"
        else:
            dato = _objeto(valor, {"valor", "unidad", "justificacion", "referencias"}, ruta)
            _texto(dato["justificacion"], ruta + ".justificacion")
            refs = dato["referencias"]
            if not isinstance(refs, list) or not refs:
                _rechazar(f"{ruta}: una declaración del operador requiere referencias revisadas explícitas.")
            for ident in refs:
                referencia(ident)
            if len(set(refs)) != len(refs):
                _rechazar(f"{ruta}: referencias repetidas.")
            numero, unidad_origen = dato["valor"], dato["unidad"]
            modo = "declaracion_operador"
        if not isinstance(unidad_origen, str) or unidad_origen not in c.DIVISORES_A_METROS:
            _rechazar(f"{ruta}: unidad desconocida o no física.")
        original = _numero(numero, ruta)
        divisor = c.DIVISORES_A_METROS[unidad_origen]
        factor_destino = c.DIVISORES_A_METROS[unidad]
        # Una sola operación: entre unidades admitidas la razón es una potencia de diez.
        convertido = original / (divisor // factor_destino) if divisor >= factor_destino else original * (factor_destino // divisor)
        if not math.isfinite(convertido) or (original != 0 and convertido == 0):
            _rechazar(f"{ruta}: conversión numérica no representable.")
        trazas.append({"ruta": ruta, "modo": modo, "referencias": list(refs),
                       "valor_origen": numero, "unidad_origen": unidad_origen,
                       "valor_geometria": convertido, "unidad_geometria": unidad})
        return convertido

    geometria = {
        "contrato": c.CONTRATO_GEOMETRIA,
        "version_contrato": c.VERSION_GEOMETRIA_ABERTURAS if aberturas_v03 else (c.VERSION_GEOMETRIA_SUPERFICIES if superficies_v02 else c.VERSION_GEOMETRIA),
        "id": manifiesto["caso"], "unidad_longitud": unidad,
        "procedencia": copy.deepcopy(procedencia), "niveles": [], "nodos": [], "muros": [],
        "faltantes": [], "revision": {"estado": "borrador", "aprobacion": None},
    }
    for coleccion, longitudes, campos in (
        ("niveles", ("cota",), {"id", "cota"}),
        ("nodos", ("x", "y"), {"id", "x", "y"}),
        ("muros", ("espesor",), {"id", "nodo_inicio", "nodo_fin", "nivel_inferior", "nivel_superior", "espesor", "referencias"}),
    ):
        elementos = manifiesto[coleccion]
        if not isinstance(elementos, list) or (not elementos and not superficies_v02):
            _rechazar(f"{coleccion}: se requiere una lista" + (" explícita." if superficies_v02 else " no vacía."))
        for indice, elemento in enumerate(elementos):
            ruta = f"{coleccion}[{indice}]"
            _objeto(elemento, campos, ruta)
            nuevo = {clave: copy.deepcopy(valor) for clave, valor in elemento.items() if clave != "referencias"}
            if coleccion == "muros":
                refs = elemento["referencias"]
                if not isinstance(refs, list) or not refs:
                    _rechazar(f"{ruta}: declare referencias revisadas para el muro y su conectividad.")
                for ident in refs:
                    referencia(ident)
                trazas.append({"ruta": ruta, "modo": "conectividad_declarada", "referencias": refs,
                               "nodo_inicio": nuevo["nodo_inicio"], "nodo_fin": nuevo["nodo_fin"],
                               "nivel_inferior": nuevo["nivel_inferior"], "nivel_superior": nuevo["nivel_superior"]})
            for clave in longitudes:
                nuevo[clave] = medida(elemento[clave], f"{ruta}.{clave}")
            geometria[coleccion].append(nuevo)
    if superficies_v02:
        geometria.update(vertices=[], superficies=[])
        for coleccion in ("vertices", "superficies"):
            elementos = manifiesto[coleccion]
            if not isinstance(elementos, list):
                _rechazar(f"{coleccion}: se requiere una lista explícita.")
            for indice, elemento in enumerate(elementos):
                ruta = f"{coleccion}[{indice}]"
                campos = {"id", "x", "y", "z"} if coleccion == "vertices" else {"id", "vertices", "papel_geometrico", "referencias"}
                _objeto(elemento, campos, ruta)
                nuevo = {"id": copy.deepcopy(elemento["id"])}
                if coleccion == "vertices":
                    comienzo = len(trazas)
                    for clave in ("x", "y", "z"):
                        nuevo[clave] = medida(elemento[clave], f"{ruta}.{clave}")
                    refs = list(dict.fromkeys(ident for traza in trazas[comienzo:] for ident in traza["referencias"]))
                else:
                    refs = elemento["referencias"]
                    if not isinstance(refs, list) or not refs:
                        _rechazar(f"{ruta}: declare referencias revisadas explícitas para la superficie y su conectividad.")
                    for ident in refs:
                        referencia(ident)
                    if len(set(refs)) != len(refs):
                        _rechazar(f"{ruta}: referencias repetidas.")
                    nuevo.update(vertices=copy.deepcopy(elemento["vertices"]),
                                 papel_geometrico=copy.deepcopy(elemento["papel_geometrico"]))
                    trazas.append({"ruta": ruta, "modo": "conectividad_superficie_declarada",
                                   "referencias": copy.deepcopy(refs),
                                   "vertices": copy.deepcopy(elemento["vertices"]),
                                   "papel_geometrico": copy.deepcopy(elemento["papel_geometrico"])})
                nuevo["procedencia"] = {**copy.deepcopy(procedencia), "referencias": copy.deepcopy(refs)}
                geometria[coleccion].append(nuevo)
    if aberturas_v03:
        geometria["aberturas"] = []
        if not isinstance(manifiesto["aberturas"], list):
            _rechazar("aberturas: se requiere una lista explícita.")
        for indice, elemento in enumerate(manifiesto["aberturas"]):
            ruta = f"aberturas[{indice}]"
            _objeto(elemento, {"id", "superficie", "vertices", "referencias"}, ruta)
            refs = elemento["referencias"]
            if not isinstance(refs, list) or not refs:
                _rechazar(f"{ruta}: declare referencias revisadas explícitas para el hueco y su anfitriona/conectividad.")
            for ident in refs:
                referencia(ident)
            if len(set(refs)) != len(refs):
                _rechazar(f"{ruta}: referencias repetidas.")
            nuevo = {k: copy.deepcopy(elemento[k]) for k in ("id", "superficie", "vertices")}
            nuevo["procedencia"] = {**copy.deepcopy(procedencia), "referencias": copy.deepcopy(refs)}
            geometria["aberturas"].append(nuevo)
            trazas.append({"ruta": ruta, "modo": "conectividad_abertura_declarada", "referencias": copy.deepcopy(refs),
                           "superficie": nuevo["superficie"], "vertices": copy.deepcopy(nuevo["vertices"])})
    validacion = validar_geometria(geometria)
    if not validacion.consistente or validacion.faltantes:
        _rechazar("Geometría declarada inconsistente o incompleta: " + "; ".join(map(str, validacion.errores)))
    return geometria, trazas


def comprobar_reproduccion(exportacion: dict, manifiesto: Any, geometria: Any, correspondencias: Any) -> None:
    """Reproduce cada formato desde su fuente exacta; no sustituye comprobación de evidencia vigente."""
    esperada, trazas = _construir(exportacion, manifiesto)
    try:
        coincide = _canonico(geometria) == _canonico(esperada) and _canonico(correspondencias) == _canonico(trazas)
    except (TypeError, ValueError, OverflowError):
        coincide = False
    if not coincide:
        _rechazar("La geometría o sus correspondencias no reproducen la exportación revisada y el manifiesto exactos.")


def convertir_lecturas(raiz: Path, caso: str, extraccion_id: str, manifiesto: Path) -> ResultadoConversion:
    """Publica geometría borrador y trazabilidad, comprobando la versión de extracción vigente.

    El manifiesto es un archivo JSON estricto; nunca se aceptan exportaciones sueltas
    como evidencia suficiente. No importa ni aprueba la geometría automáticamente.
    """
    try:
        contenido = Path(manifiesto).read_bytes()
    except OSError as exc:
        raise e.ErrorGestion(f"No se pudo leer el manifiesto: {exc}") from exc
    manifest = e.json_desde_bytes(contenido, "manifiesto.json")
    caso_dir, datos, _, comp = e._cargar_comprobada(raiz, caso, extraccion_id, "Conversión rechazada")
    prevista = exportar_revisados(datos, comp.inventario)
    geometria, correspondencias = _construir(prevista, manifest)
    # La exportación pública vuelve a comprobar evidencia y guarda sus bytes exactos.
    exportada = e.exportar_version(raiz, caso, extraccion_id)
    sin_origen = {clave: valor for clave, valor in exportada.datos.items() if clave != "origen"}
    if _canonico(sin_origen) != _canonico(prevista):
        _rechazar("La extracción cambió durante la conversión; vuelva a revisar el manifiesto.")
    export_bytes = exportada.ruta.read_bytes()
    if _canonico(e.json_desde_bytes(export_bytes, "exportacion.json")) != _canonico(exportada.datos):
        _rechazar("La exportación persistida cambió durante la conversión.")
    geo_bytes = _bytes(geometria)
    identificador = uuid4().hex
    trazabilidad = {
        "contrato": "draft2model.trazabilidad_conversion", "version_contrato": manifest["version_contrato"],
        "id": identificador, "caso": caso, "extraccion_id": extraccion_id,
        "exportacion_id": exportada.identificador,
        "exportacion_sha256": _hash(export_bytes), "manifiesto_sha256": _hash(contenido),
        "geometria_sha256": _hash(geo_bytes), "huella_contenido": c.huella_contenido(geometria),
        "expediente_sha256": exportada.comprobacion.expediente_sha256,
        "datos_sinteticos": manifest["datos_sinteticos"],
        "procedencia_extraccion": copy.deepcopy(prevista["procedencia"]),
        "alcance": copy.deepcopy(prevista["alcance"]),
        "operador_declarado": manifest["operador_declarado"],
        "identidad_operador": "declarada_no_verificada", "aprobacion_ingenieria": None,
        "sistema_coordenadas": manifest["sistema_coordenadas"], "ejes": manifest["ejes"],
        "escala": manifest["escala"], "correspondencias": correspondencias, "aviso": AVISO,
    }
    # Revalida la fuente tras construir y exportar: ningún derivado sustituye el expediente vigente.
    _, actual, _, comprobacion_actual = e._cargar_comprobada(raiz, caso, extraccion_id, "Conversión rechazada")
    if _canonico(exportar_revisados(actual, comprobacion_actual.inventario)) != _canonico(prevista):
        _rechazar("La extracción cambió antes de publicar la conversión.")
    if exportada.ruta.read_bytes() != export_bytes:
        _rechazar("La exportación cambió antes de publicar la conversión.")
    ruta = e._publicar(caso_dir, CARPETA, identificador, {
        "geometria.json": geo_bytes, "trazabilidad.json": _bytes(trazabilidad),
        "manifiesto.json": contenido, "exportacion.json": export_bytes,
    })
    return ResultadoConversion(identificador, ruta, geometria, trazabilidad)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=e.RAIZ_PRIVADA)
    parser.add_argument("--caso", required=True)
    parser.add_argument("--extraccion", required=True)
    parser.add_argument("--manifiesto", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        resultado = convertir_lecturas(args.raiz, args.caso, args.extraccion, args.manifiesto)
    except e.ErrorEvidencia as exc:
        print(json.dumps({"correcta": False, "problemas": exc.problemas}, ensure_ascii=False))
        return 2
    except (e.ErrorGestion, OSError) as exc:
        print(json.dumps({"correcta": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps({"correcta": True, "conversion": resultado.identificador,
                      "ruta": str(resultado.ruta), "geometria": str(resultado.ruta / "geometria.json"),
                      "aprobacion_ingenieria": None}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
