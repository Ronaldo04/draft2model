"""Validación del contrato de geometría v0.1.

Comprueba consistencia interna y disponibilidad declarada para modelado. No
completa datos, no aprueba, no aplica criterios normativos ni tolerancias
estructurales y no certifica la identidad de quien registra una aprobación.
"""

from __future__ import annotations

import copy
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from draft2model import contratos as c

ALCANCE = (
    "Consistencia interna del contrato de geometría v0.1 (propuesta inicial). "
    "No es validación estructural ni normativa; la aprobación registrada es un "
    "dato de entrada y no se verifica la identidad o competencia de quien la declara."
)

_INVALIDO = object()


class ErrorLecturaGeometria(ValueError):
    """Archivo que no puede leerse como JSON del contrato."""


@dataclass(frozen=True)
class Hallazgo:
    ruta: str
    codigo: str
    mensaje: str

    def __str__(self) -> str:
        return f"{self.ruta}: {self.mensaje} [{self.codigo}]"


@dataclass
class ResultadoValidacion:
    errores: list[Hallazgo] = field(default_factory=list)
    advertencias: list[Hallazgo] = field(default_factory=list)
    faltantes: list[dict[str, Any]] = field(default_factory=list)
    bloqueos: list[str] = field(default_factory=list)
    datos_sinteticos: bool | None = None
    huella_contenido: str | None = None
    geometria_m: dict[str, Any] | None = None
    derivados_m: dict[str, Any] | None = None

    @property
    def consistente(self) -> bool:
        return not self.errores

    @property
    def disponible_para_modelado(self) -> bool:
        return self.consistente and not self.bloqueos

    def a_dict(self) -> dict[str, Any]:
        return {
            "alcance": ALCANCE,
            "contrato": c.CONTRATO_GEOMETRIA,
            "version_contrato": c.VERSION_GEOMETRIA,
            "consistente": self.consistente,
            "disponible_para_modelado": self.disponible_para_modelado,
            "datos_sinteticos": self.datos_sinteticos,
            "errores": [vars(h) for h in self.errores],
            "advertencias": [vars(h) for h in self.advertencias],
            "faltantes": copy.deepcopy(self.faltantes),
            "bloqueos": list(self.bloqueos),
            "huella_contenido": self.huella_contenido,
            "geometria_m": copy.deepcopy(self.geometria_m),
            "derivados_m": copy.deepcopy(self.derivados_m),
        }


def es_numero(valor: Any) -> bool:
    """int o float, excluyendo bool (True no se acepta como 1)."""
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


class _Validador:
    def __init__(self, data: Any):
        self.data = data
        self.r = ResultadoValidacion()
        self.ids: dict[str, dict[str, dict[str, Any]]] = {nombre: {} for nombre in c.COLECCIONES}
        self.nulos: set[tuple[str, str, str]] = set()
        self.sintetico: bool | None = None

    # -- registro --------------------------------------------------------
    def error(self, ruta: str, codigo: str, mensaje: str) -> None:
        self.r.errores.append(Hallazgo(ruta, codigo, mensaje))

    def advertencia(self, ruta: str, codigo: str, mensaje: str) -> None:
        self.r.advertencias.append(Hallazgo(ruta, codigo, mensaje))

    # -- utilidades de tipo ---------------------------------------------
    def objeto(self, ruta: str, valor: Any, campos: dict[str, tuple[str, ...]]) -> bool:
        if not isinstance(valor, dict):
            self.error(ruta, "tipo_invalido", f"Se esperaba un objeto; se recibió {_tipo(valor)}.")
            return False
        admitidos = set(campos["obligatorios"]) | set(campos["opcionales"])
        for clave in valor:
            if clave not in admitidos:
                self.error(f"{ruta}.{clave}", "campo_desconocido", "Campo no definido en el contrato v0.1.")
        for clave in campos["obligatorios"]:
            if clave not in valor:
                self.error(f"{ruta}.{clave}", "campo_ausente", "Campo obligatorio ausente.")
        return True

    def texto(self, ruta: str, valor: Any) -> str | None:
        if not isinstance(valor, str) or not valor.strip():
            self.error(ruta, "tipo_invalido", f"Se esperaba texto no vacío; se recibió {_tipo(valor)}.")
            return None
        return valor

    def identificador(self, ruta: str, valor: Any) -> str | None:
        if not isinstance(valor, str):
            self.error(ruta, "tipo_invalido", f"El identificador debe ser texto; se recibió {_tipo(valor)}.")
            return None
        if not re.fullmatch(c.PATRON_ID, valor):
            self.error(
                ruta,
                "identificador_invalido",
                f"Identificador '{valor}' inválido; use hasta 64 letras, números, '.', '_' o '-'.",
            )
            return None
        return valor

    def longitud(self, ruta: str, obj: dict, campo: str, *, anulable: bool, positivo: bool) -> Any:
        """Devuelve el número, None (dato faltante declarado como null) o _INVALIDO."""
        if campo not in obj:
            return _INVALIDO  # ya informado como campo_ausente
        valor = obj[campo]
        if valor is None:
            if anulable:
                return None
            self.error(ruta, "nulo_no_admitido", "Este campo no admite null; se requiere un número.")
            return _INVALIDO
        if not es_numero(valor):
            self.error(ruta, "tipo_invalido", f"Se esperaba un número; se recibió {_tipo(valor)}.")
            return _INVALIDO
        if not math.isfinite(valor):
            self.error(ruta, "no_finito", f"Valor no finito ({valor}); se requiere un número finito.")
            return _INVALIDO
        if positivo and valor <= 0:
            detalle = "cero" if valor == 0 else f"negativo ({valor})"
            self.error(
                ruta,
                "no_positivo",
                f"Debe ser mayor que cero; se recibió {detalle}. "
                "Si el dato se desconoce, registre null y declárelo en 'faltantes'.",
            )
            return _INVALIDO
        return valor

    # -- secciones -------------------------------------------------------
    def ejecutar(self) -> ResultadoValidacion:
        data = self.data
        if not self.objeto("$", data, {"obligatorios": c.CAMPOS_RAIZ, "opcionales": ()}):
            self.cerrar()
            return self.r

        if "contrato" in data and data["contrato"] != c.CONTRATO_GEOMETRIA:
            self.error("$.contrato", "contrato_incorrecto", f"Se esperaba '{c.CONTRATO_GEOMETRIA}'.")
        if "version_contrato" in data and data["version_contrato"] != c.VERSION_GEOMETRIA:
            self.error(
                "$.version_contrato",
                "version_no_admitida",
                f"Versión {data['version_contrato']!r} no admitida; este validador acepta '{c.VERSION_GEOMETRIA}'.",
            )
        if "id" in data:
            self.identificador("$.id", data["id"])
        if "unidad_longitud" in data:
            unidad = data["unidad_longitud"]
            if not isinstance(unidad, str) or unidad not in c.DIVISORES_A_METROS:
                admitidas = ", ".join(c.DIVISORES_A_METROS)
                self.error(
                    "$.unidad_longitud",
                    "unidad_no_admitida",
                    f"Unidad {unidad!r} no admitida; use explícitamente una de: {admitidas}.",
                )
        if "procedencia" in data:
            self.procedencia("$.procedencia", data["procedencia"], raiz=True)

        for nombre in c.COLECCIONES:
            if nombre in data:
                self.coleccion(nombre, data[nombre])
        self.referencias_muros()
        if "faltantes" in data:
            self.faltantes(data["faltantes"])
        if "revision" in data:
            self.revision(data["revision"])
        self.cerrar()
        return self.r

    def procedencia(self, ruta: str, valor: Any, *, raiz: bool = False) -> None:
        if not self.objeto(ruta, valor, c.CAMPOS_PROCEDENCIA):
            return
        tipo = valor.get("tipo")
        if "tipo" in valor and tipo not in c.TIPOS_PROCEDENCIA:
            self.error(
                f"{ruta}.tipo",
                "procedencia_invalida",
                f"Tipo {tipo!r} no admitido; use: {', '.join(c.TIPOS_PROCEDENCIA)}.",
            )
            tipo = None
        if "descripcion" in valor:
            self.texto(f"{ruta}.descripcion", valor["descripcion"])
        for clave in ("expediente_id", "lamina", "justificacion"):
            if clave in valor:
                self.texto(f"{ruta}.{clave}", valor[clave])
        if "referencias" in valor:
            refs = valor["referencias"]
            if not isinstance(refs, list):
                self.error(f"{ruta}.referencias", "tipo_invalido", "Se esperaba una lista de textos.")
            else:
                for i, ref in enumerate(refs):
                    self.texto(f"{ruta}.referencias[{i}]", ref)
        if tipo == "supuesto" and "justificacion" not in valor:
            self.error(
                f"{ruta}.justificacion",
                "supuesto_sin_justificacion",
                "Un dato supuesto requiere justificación explícita.",
            )
        if tipo is None:
            return
        if raiz:
            self.sintetico = tipo == "sintetico"
        elif self.sintetico is not None and (tipo == "sintetico") != self.sintetico:
            self.error(
                f"{ruta}.tipo",
                "procedencia_mixta",
                "No se mezclan datos sintéticos con datos de expediente en un mismo contrato.",
            )

    def coleccion(self, nombre: str, elementos: Any) -> None:
        spec = c.COLECCIONES[nombre]
        ruta_col = f"$.{nombre}"
        if not isinstance(elementos, list):
            self.error(ruta_col, "tipo_invalido", f"Se esperaba una lista; se recibió {_tipo(elementos)}.")
            return
        if not elementos:
            self.error(ruta_col, "coleccion_vacia", "La lista no puede estar vacía.")
            return
        for i, elem in enumerate(elementos):
            ruta = f"{ruta_col}[{i}]"
            if not self.objeto(ruta, elem, spec):
                continue
            ident = self.identificador(f"{ruta}.id", elem["id"]) if "id" in elem else None
            if ident is not None:
                if ident in self.ids[nombre]:
                    self.error(f"{ruta}.id", "id_duplicado", f"Identificador '{ident}' repetido en {nombre}.")
                    ident = None
                else:
                    self.ids[nombre][ident] = elem
            for campo in spec["longitudes"]:
                positivo = campo == "espesor"
                valor = self.longitud(
                    f"{ruta}.{campo}", elem, campo, anulable=campo in spec["anulables"], positivo=positivo
                )
                if valor is None and ident is not None:
                    self.nulos.add((nombre, ident, campo))
            if "nombre" in elem:
                self.texto(f"{ruta}.nombre", elem["nombre"])
            if "observaciones" in elem:
                self.texto(f"{ruta}.observaciones", elem["observaciones"])
            if "procedencia" in elem:
                self.procedencia(f"{ruta}.procedencia", elem["procedencia"])

    def referencias_muros(self) -> None:
        muros = self.data.get("muros")
        if not isinstance(muros, list):
            return
        for i, muro in enumerate(muros):
            if not isinstance(muro, dict):
                continue
            ruta = f"$.muros[{i}]"
            refs = {}
            for campo, coleccion in (
                ("nodo_inicio", "nodos"),
                ("nodo_fin", "nodos"),
                ("nivel_inferior", "niveles"),
                ("nivel_superior", "niveles"),
            ):
                if campo not in muro:
                    continue
                ident = self.identificador(f"{ruta}.{campo}", muro[campo])
                if ident is None:
                    continue
                if ident not in self.ids[coleccion]:
                    self.error(
                        f"{ruta}.{campo}",
                        "referencia_rota",
                        f"'{ident}' no existe en {coleccion}.",
                    )
                    continue
                refs[campo] = ident
            ini, fin = refs.get("nodo_inicio"), refs.get("nodo_fin")
            if ini is not None and ini == fin:
                self.error(f"{ruta}.nodo_fin", "extremos_iguales", f"Inicio y fin usan el mismo nodo '{ini}'.")
            elif ini is not None and fin is not None:
                a, b = self.ids["nodos"][ini], self.ids["nodos"][fin]
                if _coords(a) is not None and _coords(a) == _coords(b):
                    self.error(
                        ruta,
                        "longitud_nula",
                        f"Los nodos '{ini}' y '{fin}' tienen las mismas coordenadas; longitud cero.",
                    )
            inf, sup = refs.get("nivel_inferior"), refs.get("nivel_superior")
            if inf is not None and inf == sup:
                self.error(
                    f"{ruta}.nivel_superior", "niveles_iguales", f"Nivel inferior y superior son '{inf}'."
                )
            elif inf is not None and sup is not None:
                ci, cs = _cota(self.ids["niveles"][inf]), _cota(self.ids["niveles"][sup])
                if ci is not None and cs is not None and cs <= ci:
                    self.error(
                        ruta,
                        "altura_no_positiva",
                        f"La cota de '{sup}' debe ser mayor que la de '{inf}'; la altura derivada no es positiva.",
                    )

    def faltantes(self, valor: Any) -> None:
        if not isinstance(valor, list):
            self.error("$.faltantes", "tipo_invalido", f"Se esperaba una lista; se recibió {_tipo(valor)}.")
            return
        declarados: set[tuple[str, str, str]] = set()
        for i, item in enumerate(valor):
            ruta = f"$.faltantes[{i}]"
            if not self.objeto(ruta, item, c.CAMPOS_FALTANTE):
                continue
            if "descripcion" in item:
                self.texto(f"{ruta}.descripcion", item["descripcion"])
            claves = [k for k in ("coleccion", "id", "campo") if k in item]
            if not claves:
                continue  # faltante general, sin campo asociado
            if len(claves) != 3:
                self.error(ruta, "faltante_incompleto", "Indique 'coleccion', 'id' y 'campo' juntos, o ninguno.")
                continue
            coleccion, ident, campo = item["coleccion"], item["id"], item["campo"]
            if not isinstance(coleccion, str) or coleccion not in c.COLECCIONES:
                self.error(f"{ruta}.coleccion", "referencia_rota", f"Colección {coleccion!r} inexistente.")
                continue
            if campo not in c.COLECCIONES[coleccion]["anulables"]:
                self.error(
                    f"{ruta}.campo",
                    "campo_no_anulable",
                    f"{campo!r} no puede declararse faltante en {coleccion}.",
                )
                continue
            if not isinstance(ident, str) or ident not in self.ids[coleccion]:
                self.error(f"{ruta}.id", "referencia_rota", f"{ident!r} no existe en {coleccion}.")
                continue
            clave = (coleccion, ident, campo)
            if clave in declarados:
                self.error(ruta, "faltante_duplicado", "Faltante declarado más de una vez.")
            elif clave not in self.nulos:
                self.error(
                    ruta,
                    "faltante_contradictorio",
                    f"{coleccion}/{ident}.{campo} tiene valor pero está declarado como faltante.",
                )
            declarados.add(clave)
        for coleccion, ident, campo in sorted(self.nulos - declarados):
            self.error(
                f"$.{coleccion}[id={ident}].{campo}",
                "nulo_no_declarado",
                "Valor null sin declaración en 'faltantes'; la ausencia debe ser explícita.",
            )

    def revision(self, valor: Any) -> None:
        if not self.objeto("$.revision", valor, c.CAMPOS_REVISION):
            return
        estado = valor.get("estado")
        if "estado" in valor and estado not in c.ESTADOS_REVISION:
            self.error(
                "$.revision.estado",
                "estado_invalido",
                f"Estado {estado!r} no admitido; use: {', '.join(c.ESTADOS_REVISION)}.",
            )
        if "aprobacion" not in valor:
            return
        aprobacion = valor["aprobacion"]
        if aprobacion is None:
            if estado == "aprobado":
                self.error(
                    "$.revision.aprobacion",
                    "aprobacion_ausente",
                    "El estado 'aprobado' requiere un registro de aprobación.",
                )
            return
        if estado in c.ESTADOS_REVISION and estado != "aprobado":
            self.error(
                "$.revision.aprobacion",
                "aprobacion_incoherente",
                f"Hay aprobación registrada pero el estado es '{estado}'.",
            )
        ruta = "$.revision.aprobacion"
        if not self.objeto(ruta, aprobacion, c.CAMPOS_APROBACION):
            return
        if "declarada_por" in aprobacion:
            self.texto(f"{ruta}.declarada_por", aprobacion["declarada_por"])
        for clave in ("alcance", "observaciones"):
            if clave in aprobacion:
                self.texto(f"{ruta}.{clave}", aprobacion[clave])
        if "fecha" in aprobacion:
            fecha = aprobacion["fecha"]
            try:
                valida = isinstance(fecha, str) and len(fecha) == 10 and date.fromisoformat(fecha)
            except ValueError:
                valida = False
            if not valida:
                self.error(f"{ruta}.fecha", "fecha_invalida", "Use una fecha ISO AAAA-MM-DD.")
        if "huella_contenido" in aprobacion:
            huella = aprobacion["huella_contenido"]
            if not isinstance(huella, str) or not re.fullmatch(r"[0-9a-f]{64}", huella):
                self.error(f"{ruta}.huella_contenido", "huella_invalida", "Se esperaba SHA256 hexadecimal en minúsculas.")

    # -- cierre ----------------------------------------------------------
    def cerrar(self) -> None:
        r = self.r
        r.datos_sinteticos = self.sintetico
        for coleccion, ident, campo in sorted(self.nulos):
            descripcion = _descripcion_declarada(self.data, coleccion, ident, campo)
            r.faltantes.append(
                {"origen": "declarado", "coleccion": coleccion, "id": ident, "campo": campo, "descripcion": descripcion}
            )
        if isinstance(self.data, dict) and isinstance(self.data.get("faltantes"), list):
            for item in self.data["faltantes"]:
                if isinstance(item, dict) and not any(k in item for k in ("coleccion", "id", "campo")):
                    r.faltantes.append({"origen": "declarado", "descripcion": item.get("descripcion")})

        if r.errores:
            r.bloqueos.append("El contrato tiene errores de consistencia.")
            return

        self.normalizar()
        if self.sintetico:
            self.advertencia(
                "$.procedencia.tipo",
                "datos_sinteticos",
                "Datos sintéticos: solo sirven para probar software, no representan una vivienda.",
            )
        if r.faltantes:
            r.bloqueos.append(f"Hay {len(r.faltantes)} dato(s) faltante(s); no se completan automáticamente.")
        revision = self.data["revision"]
        if revision["estado"] != "aprobado":
            r.bloqueos.append(f"Revisión en estado '{revision['estado']}'; se requiere aprobación explícita.")
        elif revision["aprobacion"]["huella_contenido"] != r.huella_contenido:
            r.bloqueos.append(
                "La aprobación registrada no corresponde al contenido actual (huella distinta); se requiere nueva aprobación."
            )

    def normalizar(self) -> None:
        r = self.r
        data = self.data
        r.huella_contenido = c.huella_contenido(data)
        divisor = c.DIVISORES_A_METROS[data["unidad_longitud"]]
        geometria = copy.deepcopy(data)
        geometria["unidad_longitud"] = "m"
        for nombre, spec in c.COLECCIONES.items():
            for elem in geometria[nombre]:
                for campo in spec["longitudes"]:
                    if elem[campo] is not None:
                        elem[campo] = elem[campo] / divisor
        r.geometria_m = geometria

        nodos = {n["id"]: n for n in geometria["nodos"]}
        niveles = {n["id"]: n for n in geometria["niveles"]}
        derivados: dict[str, dict[str, Any]] = {}
        usados: set[str] = set()
        vistos: dict[tuple, str] = {}
        for muro in geometria["muros"]:
            a, b = nodos[muro["nodo_inicio"]], nodos[muro["nodo_fin"]]
            usados.update((a["id"], b["id"]))
            ci, cs = niveles[muro["nivel_inferior"]]["cota"], niveles[muro["nivel_superior"]]["cota"]
            altura = None if ci is None or cs is None else cs - ci
            derivados[muro["id"]] = {"longitud": math.hypot(b["x"] - a["x"], b["y"] - a["y"]), "altura": altura}
            if altura is None:
                faltante = next(n for n in (muro["nivel_inferior"], muro["nivel_superior"]) if niveles[n]["cota"] is None)
                r.faltantes.append({
                    "origen": "derivado",
                    "coleccion": "muros",
                    "id": muro["id"],
                    "campo": "altura",
                    "descripcion": f"No determinable: falta la cota del nivel '{faltante}'.",
                })
            clave = (
                frozenset((muro["nodo_inicio"], muro["nodo_fin"])),
                muro["nivel_inferior"],
                muro["nivel_superior"],
            )
            if clave in vistos:
                self.advertencia(
                    f"$.muros[id={muro['id']}]",
                    "muro_repetido",
                    f"Mismos nodos y niveles que '{vistos[clave]}'.",
                )
            else:
                vistos[clave] = muro["id"]
        r.derivados_m = {"muros": derivados}

        posiciones: dict[tuple, str] = {}
        for nodo in geometria["nodos"]:
            if nodo["id"] not in usados:
                self.advertencia(f"$.nodos[id={nodo['id']}]", "nodo_sin_uso", "Nodo no referenciado por ningún muro.")
            pos = (nodo["x"], nodo["y"])
            if pos in posiciones:
                self.advertencia(
                    f"$.nodos[id={nodo['id']}]",
                    "nodos_coincidentes",
                    f"Mismas coordenadas que '{posiciones[pos]}'.",
                )
            else:
                posiciones[pos] = nodo["id"]


def validar_geometria(data: Any) -> ResultadoValidacion:
    """Valida un contrato ya cargado. No modifica `data`."""
    return _Validador(data).ejecutar()


def cargar_geometria(path: Path) -> Any:
    """Lee JSON rechazando claves repetidas y literales NaN/Infinity."""

    def sin_duplicados(pares: list[tuple[str, Any]]) -> dict[str, Any]:
        resultado: dict[str, Any] = {}
        for clave, valor in pares:
            if clave in resultado:
                raise ErrorLecturaGeometria(f"Clave JSON repetida: '{clave}'.")
            resultado[clave] = valor
        return resultado

    def constante(nombre: str) -> Any:
        raise ErrorLecturaGeometria(f"Valor no finito '{nombre}' no admitido.")

    try:
        texto = Path(path).read_text(encoding="utf-8")
        return json.loads(texto, object_pairs_hook=sin_duplicados, parse_constant=constante)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErrorLecturaGeometria(f"No se pudo leer {Path(path).name}: {exc}") from exc


def validar_archivo(path: Path) -> ResultadoValidacion:
    return validar_geometria(cargar_geometria(path))


def _tipo(valor: Any) -> str:
    if valor is None:
        return "null"
    if isinstance(valor, bool):
        return "booleano"
    return {int: "entero", float: "número", str: "texto", list: "lista", dict: "objeto"}.get(
        type(valor), type(valor).__name__
    )


def _valido(valor: Any) -> bool:
    return es_numero(valor) and math.isfinite(valor)


def _coords(nodo: dict) -> tuple | None:
    x, y = nodo.get("x"), nodo.get("y")
    return (x, y) if _valido(x) and _valido(y) else None


def _cota(nivel: dict) -> Any:
    cota = nivel.get("cota")
    return cota if _valido(cota) else None


def _descripcion_declarada(data: Any, coleccion: str, ident: str, campo: str) -> str | None:
    if not isinstance(data, dict) or not isinstance(data.get("faltantes"), list):
        return None
    for item in data["faltantes"]:
        if isinstance(item, dict) and (item.get("coleccion"), item.get("id"), item.get("campo")) == (
            coleccion,
            ident,
            campo,
        ):
            return item.get("descripcion")
    return None
