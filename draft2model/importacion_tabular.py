"""Contingencia CSV supervisada hacia geometría v0.1/v0.2/v0.3, sin aprobar ni modelar.

La función convertir_tablas es pura: recibe metadatos y textos CSV de la versión declarada y devuelve
el mismo contrato validado que una entrada JSON, conservando su unidad declarada.
"""

from __future__ import annotations

import argparse
import copy
import csv
import io
import json
import math
import sys
from pathlib import Path
from typing import Any, Mapping

from . import contratos
from .validacion_geometria import validar_geometria


class ErrorImportacionTabular(ValueError):
    """Entrada tabular ambigua, inválida o incompatible con el contrato."""


def _objeto_sin_duplicados(pares):
    resultado = {}
    for clave, valor in pares:
        if clave in resultado:
            raise ErrorImportacionTabular(f"Clave JSON duplicada: {clave}.")
        resultado[clave] = valor
    return resultado


def _no_finito(valor):
    raise ErrorImportacionTabular(f"Número JSON no finito: {valor}.")


def _json(texto: str):
    try:
        return json.loads(texto, object_pairs_hook=_objeto_sin_duplicados,
                          parse_constant=_no_finito)
    except (ValueError, RecursionError) as error:
        raise ErrorImportacionTabular(f"JSON inválido: {error}") from error


MAX_CSV = 4 * 1024 * 1024
MAX_FILAS = 10000
COLECCIONES_SUPERFICIES = {
    **contratos.COLECCIONES,
    "vertices": {**contratos.CAMPOS_VERTICE, "anulables": (), "longitudes": ("x", "y", "z")},
    "superficies": {**contratos.CAMPOS_SUPERFICIE, "anulables": (), "longitudes": ()},
}

COLECCIONES_ABERTURAS = {**COLECCIONES_SUPERFICIES, "aberturas": {**contratos.CAMPOS_ABERTURA, "anulables": (), "longitudes": ()}}


def colecciones_tabulares(metadatos):
    """Seleccionar el esquema exclusivamente desde la versión explícita."""
    version = metadatos.get("version_contrato") if isinstance(metadatos, dict) else None
    if version == contratos.VERSION_GEOMETRIA:
        return contratos.COLECCIONES
    if version == contratos.VERSION_GEOMETRIA_SUPERFICIES:
        return COLECCIONES_SUPERFICIES
    if version == contratos.VERSION_GEOMETRIA_ABERTURAS:
        return COLECCIONES_ABERTURAS
    raise ErrorImportacionTabular("version_contrato debe declarar 0.1.0, 0.2.0 o 0.3.0.")


def _tabla(nombre: str, texto: str, esquemas=None) -> list[dict[str, Any]]:
    if not isinstance(texto, str):
        raise ErrorImportacionTabular(f"{nombre}: se requiere texto CSV UTF-8.")
    if len(texto.encode("utf-8")) > MAX_CSV:
        raise ErrorImportacionTabular(f"{nombre}: CSV supera 4 MiB.")
    esquema = (esquemas or contratos.COLECCIONES)[nombre]
    permitidas = set(esquema["obligatorios"]) | set(esquema["opcionales"])
    try:
        lector = csv.reader(io.StringIO(texto.removeprefix("\ufeff"), newline=""), strict=True)
        columnas = next(lector, None)
        if not columnas or len(columnas) != len(set(columnas)):
            raise ErrorImportacionTabular(f"{nombre}: cabecera vacía o columnas duplicadas.")
        extras = set(columnas) - permitidas
        ausentes = set(esquema["obligatorios"]) - set(columnas)
        if extras or ausentes:
            raise ErrorImportacionTabular(
                f"{nombre}: columnas desconocidas {sorted(extras)}; obligatorias ausentes {sorted(ausentes)}."
            )
        filas = []
        for valores in lector:
            if lector.line_num > MAX_FILAS:
                raise ErrorImportacionTabular(f"{nombre}: CSV supera 10000 líneas.")
            if not valores:  # Línea completamente vacía, como permite CSV.
                continue
            if len(valores) != len(columnas):
                raise ErrorImportacionTabular(f"{nombre}, línea {lector.line_num}: número de celdas incorrecto.")
            fila = {}
            for campo, celda in zip(columnas, valores):
                celda = celda.strip()
                if celda.startswith("="):
                    raise ErrorImportacionTabular(f"{nombre}: fórmulas no admitidas.")
                if campo in esquema["longitudes"]:
                    if not celda and campo in esquema["anulables"]:
                        fila[campo] = None
                    else:
                        try:
                            numero = float(celda)
                        except (ValueError, OverflowError) as error:
                            raise ErrorImportacionTabular(
                                f"{nombre}, línea {lector.line_num}, {campo}: número decimal inválido."
                            ) from error
                        if not math.isfinite(numero):
                            raise ErrorImportacionTabular(
                                f"{nombre}, línea {lector.line_num}, {campo}: número no finito."
                            )
                        fila[campo] = numero
                elif campo in ("procedencia", "vertices"):
                    if celda:
                        fila[campo] = _json(celda)
                elif celda or campo in esquema["obligatorios"]:
                    fila[campo] = celda
            filas.append(fila)
        return filas
    except csv.Error as error:
        raise ErrorImportacionTabular(f"{nombre}: CSV inválido: {error}") from error


def convertir_tablas(metadatos: dict[str, Any], tablas: Mapping[str, str]) -> dict[str, Any]:
    """Construir geometría desde niveles/nodos/muros sin E/S ni efectos laterales.

    metadatos contiene todos los campos raíz del contrato excepto las tres
    colecciones. No se completan faltantes, unidades, procedencia o revisión.
    Celdas numéricas vacías solo se aceptan para los campos anulables del contrato;
    sus ausencias deben estar ya declaradas en metadatos.faltantes.
    """
    esquemas = colecciones_tabulares(metadatos)
    raiz = contratos.CAMPOS_RAIZ_ABERTURAS if "aberturas" in esquemas else (contratos.CAMPOS_RAIZ_SUPERFICIES if "superficies" in esquemas else contratos.CAMPOS_RAIZ)
    esperados = set(raiz) - set(esquemas)
    if not isinstance(metadatos, dict) or set(metadatos) != esperados:
        raise ErrorImportacionTabular(
            "Los metadatos requieren exactamente: " + ", ".join(sorted(esperados)) + "."
        )
    if not isinstance(tablas, Mapping) or set(tablas) != set(esquemas):
        raise ErrorImportacionTabular("Se requieren exactamente las tablas: " + ", ".join(esquemas) + ".")
    if metadatos["unidad_longitud"] not in ("m", "cm", "mm"):
        raise ErrorImportacionTabular("unidad_longitud debe declarar m, cm o mm; no se infiere escala.")
    if metadatos["revision"] != {"estado": "borrador", "aprobacion": None}:
        raise ErrorImportacionTabular("La importación solo admite revisión borrador y aprobación null.")
    datos = copy.deepcopy(metadatos)
    for nombre in esquemas:
        datos[nombre] = _tabla(nombre, tablas[nombre], esquemas)
    comprobacion = validar_geometria(datos)
    if not comprobacion.consistente:
        raise ErrorImportacionTabular(
            "Geometría inconsistente: " + "; ".join(str(error) for error in comprobacion.errores)
        )
    return datos


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadatos", required=True, type=Path, help="JSON sin las colecciones geométricas")
    for nombre in COLECCIONES_ABERTURAS:
        parser.add_argument("--" + nombre, type=Path, help=f"CSV UTF-8 de {nombre}")
    parser.add_argument('--xlsx',type=Path,help='Libro con las tres, cinco o seis hojas de la versión declarada, sin fórmulas')
    parser.add_argument("--salida", required=True, type=Path, help="JSON nuevo; no se sobrescribe")
    args = parser.parse_args(argv)
    try:
        metadatos = _json(args.metadatos.read_text(encoding="utf-8-sig"))
        esquemas = colecciones_tabulares(metadatos)
        paths=[getattr(args,nombre) for nombre in COLECCIONES_ABERTURAS]
        if args.xlsx:
            if any(paths):raise ErrorImportacionTabular('No mezclar XLSX y CSV.')
            from .lectura_xlsx import leer_tablas_xlsx
            tablas=leer_tablas_xlsx(args.xlsx, colecciones=tuple(esquemas))
        else:
            if any(bool(getattr(args, n)) != (n in esquemas) for n in COLECCIONES_ABERTURAS):
                raise ErrorImportacionTabular('Proporcionar --xlsx o exactamente los CSV de la versión declarada.')
            tablas = {nombre: getattr(args, nombre).read_text(encoding="utf-8-sig") for nombre in esquemas}
        datos = convertir_tablas(metadatos, tablas)
        contenido = json.dumps(datos, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        # Creación exclusiva también rechaza salida igual a cualquiera de las entradas.
        with args.salida.open("x", encoding="utf-8", newline="\n") as archivo:
            archivo.write(contenido)
    except (OSError, ValueError, TypeError, OverflowError, RecursionError) as error:
        print(f"Importación no completada: {error}", file=sys.stderr)
        return 1
    print(f"Geometría en borrador: {args.salida}")
    print("Ingreso tabular supervisado; sin aprobación de ingeniería, modelo ETABS ni análisis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
