"""Registro de extracción preliminar: candidatos con evidencia y revisión trazable.

Registra cotas, etiquetas y elementos propuestos, su origen en la página y las
correcciones declaradas. La versión 0.2.0 distingue además cargas, propiedades,
parámetros, cantidades, textos y resultados impresos (estos nunca son entradas),
admite el símbolo literal, una clasificación propuesta pendiente y la cobertura
declarada por recorte; la 0.1.0 sigue siendo válida tal como se guardó. No realiza OCR, no convierte candidatos en nodos,
muros o niveles y no aprueba datos de ingeniería. Revisar un candidato solo
confirma o corrige lo leído; no equivale a aprobación técnica.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from .coherencia_literal import alertas_cota_literal

CONTRATO_EXTRACCION = "draft2model.extraccion_preliminar"
CONTRATO_EXPORTACION = "draft2model.extraccion_revisada"
VERSION_EXTRACCION = "0.1.0"
VERSION_SEMANTICA = "0.2.0"
VERSIONES_EXTRACCION = (VERSION_EXTRACCION, VERSION_SEMANTICA)
SISTEMA_COORDENADAS = "pagina_visible_normalizada"

TIPOS_CANDIDATO = ("cota", "etiqueta", "elemento")
UNIDADES_COTA = ("m", "cm", "mm", "desconocida")
UNIDAD_NO_APLICA = "no_aplica"
# 0.2.0: magnitudes no geométricas con su unidad literal normalizada; «Kg» impreso de fuerza es kgf.
# Ninguna unidad se convierte aquí y ninguna magnitud se vuelve parámetro de ingeniería por leerse.
UNIDADES_POR_TIPO = {
    "cota": UNIDADES_COTA,
    "carga": ("kgf/m2", "kgf/m", "kgf", "kN/m2", "kN/m", "kN", "tf/m2", "tf/m", "tf", "desconocida"),
    "propiedad": ("kgf/cm2", "kgf/m2", "MPa", "kN/m2", "kgf/m3", "kN/m3", "tf/m3", "desconocida"),
    "parametro": ("adimensional", "s", "desconocida"),
    "cantidad": (UNIDAD_NO_APLICA,),
    "etiqueta": (UNIDAD_NO_APLICA,),
    "elemento": (UNIDAD_NO_APLICA,),
    "texto": (UNIDAD_NO_APLICA,),
}
UNIDADES_POR_TIPO["resultado_impreso"] = tuple(dict.fromkeys(
    u for t in ("cota", "carga", "propiedad", "parametro") for u in UNIDADES_POR_TIPO[t])) + (UNIDAD_NO_APLICA,)
TIPOS_SEMANTICOS = TIPOS_CANDIDATO + ("carga", "propiedad", "parametro", "cantidad", "texto", "resultado_impreso")
TIPOS_NUMERICOS = ("cota", "carga", "propiedad", "parametro")
ESTADOS_COBERTURA = ("completa", "parcial", "sin_lecturas")
METODOS = ("manual", "sintetico", "ocr", "vision", "importado")
TIPOS_PROCEDENCIA = ("sintetico", "expediente")
ESTADOS_REVISION = ("pendiente", "revisado", "rechazado")

PATRON_ID = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}"
PATRON_SHA256 = r"[0-9a-f]{64}"

AVISO = (
    "Extracción preliminar. Revisar un candidato confirma o corrige lo leído en la "
    "evidencia; no aprueba datos de ingeniería ni valida la estructura. Las "
    "coordenadas bbox_normalizada son relativas a la página visible, no metros."
)

_CAMPOS_RAIZ = {
    "obligatorios": (
        "contrato", "version_contrato", "caso", "procedencia", "alcance",
        "sistema_coordenadas", "candidatos",
    ),
    "opcionales": (),
}
_CAMPOS_RAIZ_02 = {"obligatorios": _CAMPOS_RAIZ["obligatorios"], "opcionales": ("cobertura", "cuarentena")}
_CAMPOS_CUARENTENA = {"obligatorios": ("id", "errores", "recortes", "candidato_original"), "opcionales": ()}
_CAMPOS_PROCEDENCIA = {"obligatorios": ("tipo", "descripcion"), "opcionales": ("expediente_sha256",)}
_CAMPOS_CANDIDATO = {
    "obligatorios": ("id", "tipo", "valor_propuesto", "unidad", "metodo", "evidencia"),
    "opcionales": ("texto_fuente", "observaciones", "revision"),
}
_CAMPOS_CANDIDATO_02 = {
    "obligatorios": _CAMPOS_CANDIDATO["obligatorios"],
    "opcionales": _CAMPOS_CANDIDATO["opcionales"] + ("simbolo", "clasificacion_propuesta", "historial_evidencia"),
}
_CAMPOS_REUBICACION = {"obligatorios": ("indice", "bbox_anterior", "bbox_nueva", "motivo", "fecha", "revisor_declarado"),
                       "opcionales": ()}
_CAMPOS_CLASIFICACION = {"obligatorios": ("tipo", "valor", "unidad", "motivo", "origen"), "opcionales": ("simbolo",)}
_CAMPOS_COBERTURA = {"obligatorios": ("recorte_id", "estado", "observacion"), "opcionales": ("efectiva",)}
_CAMPOS_COBERTURA_EFECTIVA = {"obligatorios": ("estado", "candidatos_declarados", "recuperados", "en_cuarentena", "motivo"),
                              "opcionales": ()}
_CAMPOS_METODO = {"obligatorios": ("tipo",), "opcionales": ("herramienta", "version", "confianza", "descripcion")}
_CAMPOS_EVIDENCIA = {
    "obligatorios": ("archivo_id", "pagina", "original_sha256", "bbox_normalizada"),
    "opcionales": ("recorte_id", "imagen_sha256"),
}
_CAMPOS_REVISION = {"obligatorios": ("estado", "historial"), "opcionales": ()}
_CAMPOS_ENTRADA = {
    "obligatorios": ("estado", "motivo", "fecha", "revisor_declarado"),
    "opcionales": ("valor_revisado", "unidad_revisada"),
}
_CAMPOS_ENTRADA_02 = {"obligatorios": _CAMPOS_ENTRADA["obligatorios"],
                      "opcionales": _CAMPOS_ENTRADA["opcionales"] + ("tipo_revisado",)}

_SIN_VALOR = object()


class ErrorExtraccion(ValueError):
    """Operación imposible sobre un registro de extracción."""


@dataclass(frozen=True)
class Hallazgo:
    ruta: str
    codigo: str
    mensaje: str

    def __str__(self) -> str:
        return f"{self.ruta}: {self.mensaje} [{self.codigo}]"


@dataclass
class ResultadoExtraccion:
    errores: list[Hallazgo] = field(default_factory=list)
    advertencias: list[Hallazgo] = field(default_factory=list)
    # candidato_id -> estado de referencia de cada evidencia, en el mismo orden.
    referencias: dict[str, list[str]] = field(default_factory=dict)
    resumen: dict[str, int] = field(default_factory=dict)
    inventario_aportado: bool = False

    @property
    def consistente(self) -> bool:
        return not self.errores

    def a_dict(self) -> dict[str, Any]:
        return {
            "aviso": AVISO,
            "consistente": self.consistente,
            "inventario_aportado": self.inventario_aportado,
            "errores": [vars(h) for h in self.errores],
            "advertencias": [vars(h) for h in self.advertencias],
            "referencias": copy.deepcopy(self.referencias),
            "resumen": dict(self.resumen),
        }


def es_numero(valor: Any) -> bool:
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def huella(data: Any) -> str:
    canonico = json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonico.encode("utf-8")).hexdigest()


# -- inventario de evidencia -------------------------------------------------

def inventario_desde(
    expediente: dict[str, Any],
    revisiones: Iterable[dict[str, Any]] = (),
    recortes: Iterable[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Construye un inventario a partir de expediente.json, revision.json y recorte.json ya cargados.

    Solo resume lo registrado por esos módulos; no vuelve a calcular hashes de archivos.
    Las páginas quedan sin comprobar si ninguna revisión documental las inventarió.
    """
    if not isinstance(expediente, dict) or not isinstance(expediente.get("archivos"), list):
        raise ErrorExtraccion("Expediente inválido para construir el inventario.")
    archivos = {
        a["id"]: {"sha256": a.get("sha256"), "paginas": None}
        for a in expediente["archivos"]
        if isinstance(a, dict) and isinstance(a.get("id"), str)
    }
    for revision in revisiones:
        if revision.get("caso") != expediente.get("id"):
            raise ErrorExtraccion("Una revisión documental pertenece a otro caso.")
        for documento in revision.get("documentos", []):
            paginas = documento.get("paginas_declaradas")
            if documento.get("id") in archivos and not documento.get("error") and es_numero(paginas):
                previo = archivos[documento["id"]]["paginas"]
                if previo is not None and previo != paginas:
                    raise ErrorExtraccion(f"Revisiones con distinto número de páginas para {documento['id']}.")
                archivos[documento["id"]]["paginas"] = paginas
    inventario_recortes = {}
    for recorte in recortes:
        if recorte.get("caso") != expediente.get("id"):
            raise ErrorExtraccion("Un recorte pertenece a otro caso.")
        if not isinstance(recorte.get("id"), str):
            raise ErrorExtraccion("Recorte sin identificador.")
        inventario_recortes[recorte["id"]] = {
            clave: recorte.get(clave)
            for clave in ("archivo_id", "pagina", "origen_sha256", "imagen_sha256", "bbox_normalizada", "sistema_coordenadas")
        }
    return {
        "caso": expediente.get("id"),
        "alcance": copy.deepcopy(expediente.get("alcance")),
        "archivos": archivos,
        "recortes": inventario_recortes,
    }


# -- validación --------------------------------------------------------------

class _Validador:
    def __init__(self, data: Any, inventario: dict[str, Any] | None):
        self.data = data
        self.inv = inventario
        self.r = ResultadoExtraccion(inventario_aportado=inventario is not None)
        self.v02 = isinstance(data, dict) and data.get("version_contrato") == VERSION_SEMANTICA
        self.tipos = TIPOS_SEMANTICOS if self.v02 else TIPOS_CANDIDATO

    def error(self, ruta: str, codigo: str, mensaje: str) -> None:
        self.r.errores.append(Hallazgo(ruta, codigo, mensaje))

    def advertencia(self, ruta: str, codigo: str, mensaje: str) -> None:
        self.r.advertencias.append(Hallazgo(ruta, codigo, mensaje))

    def objeto(self, ruta: str, valor: Any, campos: dict[str, tuple[str, ...]]) -> bool:
        if not isinstance(valor, dict):
            self.error(ruta, "tipo_invalido", f"Se esperaba un objeto; se recibió {_tipo(valor)}.")
            return False
        admitidos = set(campos["obligatorios"]) | set(campos["opcionales"])
        for clave in valor:
            if clave not in admitidos:
                self.error(f"{ruta}.{clave}", "campo_desconocido", "Campo no definido en esta versión del contrato.")
        for clave in campos["obligatorios"]:
            if clave not in valor:
                self.error(f"{ruta}.{clave}", "campo_ausente", "Campo obligatorio ausente.")
        return True

    def texto(self, ruta: str, valor: Any) -> bool:
        if not isinstance(valor, str) or not valor.strip():
            self.error(ruta, "tipo_invalido", f"Se esperaba texto no vacío; se recibió {_tipo(valor)}.")
            return False
        return True

    def patron(self, ruta: str, valor: Any, patron: str, descripcion: str) -> bool:
        if not isinstance(valor, str) or not re.fullmatch(patron, valor):
            self.error(ruta, "formato_invalido", f"Se esperaba {descripcion}; se recibió {valor!r}.")
            return False
        return True

    def fecha(self, ruta: str, valor: Any) -> str | None:
        try:
            if isinstance(valor, str) and len(valor) == 10 and date.fromisoformat(valor):
                return valor
        except ValueError:
            pass
        self.error(ruta, "fecha_invalida", "Use una fecha ISO AAAA-MM-DD.")
        return None

    def valor(self, ruta: str, tipo: Any, valor: Any, *, admite_nulo: bool) -> None:
        if valor is None:
            if not admite_nulo:
                self.error(ruta, "nulo_no_admitido", "Un candidato revisado requiere valor; si es ilegible, recháselo o déjelo pendiente.")
            return
        if tipo in TIPOS_NUMERICOS:
            if not es_numero(valor):
                self.error(ruta, "tipo_invalido", f"Una {tipo} requiere número; se recibió {_tipo(valor)}. Use null si no se lee.")
            elif not math.isfinite(valor):
                self.error(ruta, "no_finito", f"Valor no finito ({valor}).")
        elif tipo == "cantidad":
            if type(valor) is not int or valor < 0:
                self.error(ruta, "tipo_invalido", "Una cantidad es un entero no negativo (p. ej. número de barras), no una longitud.")
        elif tipo == "resultado_impreso":
            if not ((es_numero(valor) and math.isfinite(valor)) or (isinstance(valor, str) and valor.strip())):
                self.error(ruta, "tipo_invalido", "Un resultado impreso es número finito o texto no vacío.")
        elif tipo in ("etiqueta", "elemento", "texto"):
            if not isinstance(valor, str) or not valor.strip():
                self.error(ruta, "tipo_invalido", f"Se esperaba texto no vacío; se recibió {_tipo(valor)}. Use null si no se lee.")

    def unidad(self, ruta: str, tipo: Any, unidad: Any) -> None:
        if self.v02 and tipo in UNIDADES_POR_TIPO and tipo not in ("cota", "etiqueta", "elemento"):
            if not isinstance(unidad, str) or unidad not in UNIDADES_POR_TIPO[tipo]:
                self.error(ruta, "unidad_invalida",
                           f"Unidad {unidad!r} no admitida para '{tipo}'; use {', '.join(UNIDADES_POR_TIPO[tipo])}.")
            return
        if tipo == "cota":
            if not isinstance(unidad, str) or unidad not in UNIDADES_COTA:
                self.error(
                    ruta, "unidad_invalida",
                    f"Unidad {unidad!r} no admitida para una cota; use {', '.join(UNIDADES_COTA)}.",
                )
        elif tipo in ("etiqueta", "elemento") and unidad != UNIDAD_NO_APLICA:
            self.error(ruta, "unidad_invalida", f"Para '{tipo}' la unidad debe ser '{UNIDAD_NO_APLICA}'.")

    # -- secciones ------------------------------------------------------
    def ejecutar(self) -> ResultadoExtraccion:
        data = self.data
        if not self.objeto("$", data, _CAMPOS_RAIZ_02 if self.v02 else _CAMPOS_RAIZ):
            return self.r
        if "contrato" in data and data["contrato"] != CONTRATO_EXTRACCION:
            self.error("$.contrato", "contrato_incorrecto", f"Se esperaba '{CONTRATO_EXTRACCION}'.")
        if "version_contrato" in data and data["version_contrato"] not in VERSIONES_EXTRACCION:
            self.error(
                "$.version_contrato", "version_no_admitida",
                f"Versión {data['version_contrato']!r} no admitida; se aceptan {', '.join(VERSIONES_EXTRACCION)}.",
            )
        if "caso" in data:
            self.patron("$.caso", data["caso"], PATRON_ID, "un identificador de caso")
        if "sistema_coordenadas" in data and data["sistema_coordenadas"] != SISTEMA_COORDENADAS:
            self.error(
                "$.sistema_coordenadas", "sistema_no_admitido",
                f"Solo se admite '{SISTEMA_COORDENADAS}' (docs/RECORTES.md).",
            )
        if "procedencia" in data:
            self.procedencia(data["procedencia"])
        if "alcance" in data:
            self.alcance(data["alcance"])
        if self.inv is not None and "caso" in data and data["caso"] != self.inv.get("caso"):
            self.error("$.caso", "caso_incompatible", "El caso no coincide con el inventario de evidencia.")
        if "candidatos" in data:
            self.candidatos(data["candidatos"])
        if "cobertura" in data:
            self.cobertura(data["cobertura"])
        if "cuarentena" in data:
            self.cuarentena(data["cuarentena"], data.get("cobertura"))
        return self.r

    def cuarentena(self, valor: Any, cobertura: Any) -> None:
        """Candidatos apartados en una recuperación explícita: se conservan íntegros y no son lecturas."""
        if not isinstance(valor, list) or not valor:
            self.error("$.cuarentena", "tipo_invalido", "Se esperaba una lista no vacía.")
            return
        afectados = set()
        for i, item in enumerate(valor):
            ruta = f"$.cuarentena[{i}]"
            if not self.objeto(ruta, item, _CAMPOS_CUARENTENA):
                continue
            errores = item.get("errores")
            if not isinstance(errores, list) or not errores or not all(isinstance(e, str) and e.strip() for e in errores):
                self.error(f"{ruta}.errores", "tipo_invalido", "Se requiere al menos un error en texto.")
            if not isinstance(item.get("recortes"), list):
                self.error(f"{ruta}.recortes", "tipo_invalido", "Se esperaba una lista de recortes.")
            else:
                afectados.update(r for r in item["recortes"] if isinstance(r, str))
        self.advertencia("$.cuarentena", "candidatos_en_cuarentena",
                         f"{len(valor)} candidato(s) apartados sin corregir; revisar contra el original antes de usarlos.")
        if isinstance(cobertura, list):
            for c in cobertura:
                if isinstance(c, dict) and c.get("recorte_id") in afectados and c.get("estado") == "completa":
                    self.advertencia("$.cobertura", "cobertura_con_cuarentena",
                                     f"Recorte {c['recorte_id']}: «completa» es la declaración del lector, pero hay lecturas en cuarentena.")

    def cobertura(self, valor: Any) -> None:
        """Cobertura declarada por recorte: «completa» es una declaración del lector, no una prueba."""
        if not isinstance(valor, list):
            self.error("$.cobertura", "tipo_invalido", "Se esperaba una lista por recorte.")
            return
        vistos = set()
        for i, item in enumerate(valor):
            ruta = f"$.cobertura[{i}]"
            if not self.objeto(ruta, item, _CAMPOS_COBERTURA):
                continue
            if self.patron(f"{ruta}.recorte_id", item.get("recorte_id"), PATRON_ID, "un identificador de recorte"):
                if item["recorte_id"] in vistos:
                    self.error(f"{ruta}.recorte_id", "id_duplicado", "Recorte repetido en la cobertura.")
                vistos.add(item["recorte_id"])
                if self.inv is not None and item["recorte_id"] not in self.inv.get("recortes", {}):
                    self.error(f"{ruta}.recorte_id", "referencia_rota", "Recorte no registrado.")
            if item.get("estado") not in ESTADOS_COBERTURA:
                self.error(f"{ruta}.estado", "estado_invalido", f"Use: {', '.join(ESTADOS_COBERTURA)}.")
            elif item["estado"] != "completa":
                self.advertencia(f"{ruta}.estado", "cobertura_incompleta",
                                 f"Recorte {item.get('recorte_id')}: cobertura {item['estado']}; hay lecturas sin extraer.")
            if not isinstance(item.get("observacion"), str):
                self.error(f"{ruta}.observacion", "tipo_invalido", "Se esperaba texto (puede ser vacío).")
            if "efectiva" in item:
                self.cobertura_efectiva(f"{ruta}.efectiva", item["efectiva"], item.get("estado"))

    def cobertura_efectiva(self, ruta: str, valor: Any, declarada: Any) -> None:
        """Cobertura del lote importado: la declaración del lector se conserva aparte y nunca se eleva."""
        if not self.objeto(ruta, valor, _CAMPOS_COBERTURA_EFECTIVA):
            return
        n = [valor.get(k) for k in ("candidatos_declarados", "recuperados", "en_cuarentena")]
        if not all(type(x) is int and x >= 0 for x in n) or n[0] != n[1] + n[2]:
            self.error(ruta, "conteo_invalido", "candidatos_declarados = recuperados + en_cuarentena (enteros ≥ 0).")
            return
        estado = valor.get("estado")
        if estado not in ESTADOS_COBERTURA:
            self.error(f"{ruta}.estado", "estado_invalido", f"Use: {', '.join(ESTADOS_COBERTURA)}.")
        elif n[2] and estado == "completa":
            self.error(f"{ruta}.estado", "cobertura_elevada", "Con candidatos en cuarentena la cobertura efectiva no es completa.")
        elif declarada != "completa" and estado == "completa":
            self.error(f"{ruta}.estado", "cobertura_elevada", "La cobertura efectiva no puede superar la declarada.")
        elif estado != "completa":
            self.advertencia(f"{ruta}.estado", "cobertura_efectiva_incompleta",
                             f"Lote importado: {n[1]} de {n[0]} lecturas declaradas ({n[2]} en cuarentena).")
        self.texto(f"{ruta}.motivo", valor.get("motivo"))

    def procedencia(self, valor: Any) -> None:
        ruta = "$.procedencia"
        if not self.objeto(ruta, valor, _CAMPOS_PROCEDENCIA):
            return
        if "tipo" in valor and valor["tipo"] not in TIPOS_PROCEDENCIA:
            self.error(f"{ruta}.tipo", "procedencia_invalida", f"Use: {', '.join(TIPOS_PROCEDENCIA)}.")
        if "descripcion" in valor:
            self.texto(f"{ruta}.descripcion", valor["descripcion"])
        if "expediente_sha256" in valor:
            self.patron(f"{ruta}.expediente_sha256", valor["expediente_sha256"], PATRON_SHA256, "SHA256 en minúsculas")
        if valor.get("tipo") == "sintetico":
            self.advertencia(f"{ruta}.tipo", "datos_sinteticos", "Datos sintéticos: solo para probar software.")

    def alcance(self, valor: Any) -> None:
        # Se conserva tal cual lo declaró el expediente; aquí solo se exige que exista.
        if not isinstance(valor, dict) or not isinstance(valor.get("estado"), str) or not valor["estado"].strip():
            self.error("$.alcance", "alcance_invalido", "Se requiere un objeto con 'estado' (copiado del expediente).")
            return
        try:
            json.dumps(valor, allow_nan=False)
        except (TypeError, ValueError):
            self.error("$.alcance", "alcance_invalido", "El alcance debe ser JSON válido, sin valores no finitos.")
            return
        if valor["estado"] == "fuera_mvp_declarado":
            self.advertencia(
                "$.alcance.estado", "fuera_mvp",
                "Caso provisional fuera del MVP: solo para pruebas de procesamiento.",
            )
        if self.inv is not None and self.inv.get("alcance") is not None and valor != self.inv["alcance"]:
            self.error("$.alcance", "alcance_incompatible", "El alcance difiere del declarado en el expediente.")

    def candidatos(self, valor: Any) -> None:
        if not isinstance(valor, list):
            self.error("$.candidatos", "tipo_invalido", f"Se esperaba una lista; se recibió {_tipo(valor)}.")
            return
        vistos: set[str] = set()
        conteo = dict.fromkeys(
            ("candidatos", "pendientes", "revisados", "rechazados", "valores_desconocidos",
             "unidades_desconocidas", "evidencias", "referencias_no_comprobadas", "referencias_comprobadas"),
            0,
        )
        conteo["candidatos"] = len(valor)
        for i, cand in enumerate(valor):
            ruta = f"$.candidatos[{i}]"
            if not self.objeto(ruta, cand, _CAMPOS_CANDIDATO_02 if self.v02 else _CAMPOS_CANDIDATO):
                continue
            ident = cand.get("id")
            if "id" in cand and self.patron(f"{ruta}.id", ident, PATRON_ID, "un identificador"):
                if ident in vistos:
                    self.error(f"{ruta}.id", "id_duplicado", f"Identificador '{ident}' repetido.")
                vistos.add(ident)
            tipo = cand.get("tipo")
            if "tipo" in cand and tipo not in self.tipos:
                self.error(f"{ruta}.tipo", "tipo_candidato_invalido", f"Use: {', '.join(self.tipos)}.")
                tipo = None
            if tipo == "resultado_impreso":
                self.advertencia(f"{ruta}.tipo", "resultado_impreso",
                                 "Resultado previo impreso: se conserva como lectura, nunca como entrada ni calibración.")
            if "valor_propuesto" in cand:
                self.valor(f"{ruta}.valor_propuesto", tipo, cand["valor_propuesto"], admite_nulo=True)
                conteo["valores_desconocidos"] += cand["valor_propuesto"] is None
            if "unidad" in cand:
                self.unidad(f"{ruta}.unidad", tipo, cand["unidad"])
                conteo["unidades_desconocidas"] += cand["unidad"] == "desconocida"
            for clave in ("texto_fuente", "observaciones", "simbolo"):
                if clave in cand:
                    self.texto(f"{ruta}.{clave}", cand[clave])
            for codigo, mensaje in alertas_cota_literal(cand):
                self.advertencia(ruta, codigo, mensaje)
            if "clasificacion_propuesta" in cand:
                self.clasificacion(f"{ruta}.clasificacion_propuesta", cand["clasificacion_propuesta"])
            if "historial_evidencia" in cand:
                self.historial_evidencia(f"{ruta}.historial_evidencia", cand["historial_evidencia"], cand.get("evidencia"))
            if "metodo" in cand:
                self.metodo(f"{ruta}.metodo", cand["metodo"])
            estados_ref: list[str] = []
            if "evidencia" in cand:
                evidencia = cand["evidencia"]
                if not isinstance(evidencia, list) or not evidencia:
                    self.error(f"{ruta}.evidencia", "evidencia_ausente", "Se requiere una lista no vacía de evidencias.")
                else:
                    for j, ev in enumerate(evidencia):
                        estados_ref.append(self.evidencia(f"{ruta}.evidencia[{j}]", ev))
            conteo["evidencias"] += len(estados_ref)
            conteo["referencias_no_comprobadas"] += estados_ref.count("referencia_no_comprobada")
            conteo["referencias_comprobadas"] += estados_ref.count("comprobada")
            if isinstance(ident, str):
                self.r.referencias[ident] = estados_ref
            estado = self.revision(f"{ruta}.revision", tipo, cand.get("revision"))
            if estado is not None:
                conteo[{"pendiente": "pendientes", "revisado": "revisados", "rechazado": "rechazados"}[estado]] += 1
        self.r.resumen = conteo

    def historial_evidencia(self, ruta: str, valor: Any, evidencia: Any) -> None:
        """Reubicaciones declaradas: la última región nueva de cada índice debe ser la evidencia vigente."""
        if not isinstance(valor, list) or not valor:
            self.error(ruta, "tipo_invalido", "Se esperaba una lista no vacía de reubicaciones.")
            return
        ultima, fecha_previa = {}, None
        for k, item in enumerate(valor):
            rk = f"{ruta}[{k}]"
            if not self.objeto(rk, item, _CAMPOS_REUBICACION):
                continue
            i = item.get("indice")
            if type(i) is not int or not isinstance(evidencia, list) or not 0 <= i < len(evidencia):
                self.error(f"{rk}.indice", "indice_invalido", "No corresponde a una evidencia del candidato.")
                continue
            for clave in ("bbox_anterior", "bbox_nueva"):
                self.bbox(f"{rk}.{clave}", item.get(clave))
            if item.get("bbox_anterior") == item.get("bbox_nueva"):
                self.error(f"{rk}.bbox_nueva", "sin_cambio", "La reubicación debe cambiar la región.")
            if i in ultima and ultima[i] != item.get("bbox_anterior"):
                self.error(f"{rk}.bbox_anterior", "historial_incoherente", "No coincide con la región nueva anterior.")
            ultima[i] = item.get("bbox_nueva")
            for clave in ("motivo", "revisor_declarado"):
                self.texto(f"{rk}.{clave}", item.get(clave))
            fecha = self.fecha(f"{rk}.fecha", item.get("fecha"))
            if fecha and fecha_previa and fecha < fecha_previa:
                self.error(f"{rk}.fecha", "historial_desordenado", "Las fechas no pueden retroceder.")
            fecha_previa = fecha or fecha_previa
        for i, bbox in ultima.items():
            if isinstance(evidencia[i], dict) and evidencia[i].get("bbox_normalizada") != bbox:
                self.error(f"{ruta}", "historial_incoherente", f"La evidencia {i} no es la última región reubicada.")

    def clasificacion(self, ruta: str, valor: Any) -> None:
        """Propuesta de tipo/unidad pendiente de revisión; no sustituye a la lectura ni la aprueba."""
        if not self.objeto(ruta, valor, _CAMPOS_CLASIFICACION):
            return
        tipo = valor.get("tipo")
        if tipo not in TIPOS_SEMANTICOS:
            self.error(f"{ruta}.tipo", "tipo_candidato_invalido", f"Use: {', '.join(TIPOS_SEMANTICOS)}.")
            return
        self.valor(f"{ruta}.valor", tipo, valor.get("valor"), admite_nulo=True)
        self.unidad(f"{ruta}.unidad", tipo, valor.get("unidad"))
        for clave in ("motivo", "origen", "simbolo"):
            if clave in valor:
                self.texto(f"{ruta}.{clave}", valor[clave])

    def metodo(self, ruta: str, valor: Any) -> None:
        if not self.objeto(ruta, valor, _CAMPOS_METODO):
            return
        if "tipo" in valor and valor["tipo"] not in METODOS:
            self.error(f"{ruta}.tipo", "metodo_invalido", f"Use: {', '.join(METODOS)}.")
        for clave in ("herramienta", "version", "descripcion"):
            if clave in valor:
                self.texto(f"{ruta}.{clave}", valor[clave])
        if "confianza" in valor:
            conf = valor["confianza"]
            if not es_numero(conf) or not math.isfinite(conf) or not 0 <= conf <= 1:
                self.error(f"{ruta}.confianza", "confianza_invalida", "Debe ser un número finito entre 0 y 1.")

    def evidencia(self, ruta: str, ev: Any) -> str:
        """Valida forma y, con inventario, referencias. Devuelve el estado de referencia."""
        errores_previos = len(self.r.errores)
        if not self.objeto(ruta, ev, _CAMPOS_EVIDENCIA):
            return "invalida"
        if "archivo_id" in ev:
            self.patron(f"{ruta}.archivo_id", ev["archivo_id"], PATRON_ID, "un identificador de archivo")
        pagina = ev.get("pagina")
        if "pagina" in ev and (not isinstance(pagina, int) or isinstance(pagina, bool) or pagina < 1):
            self.error(f"{ruta}.pagina", "pagina_invalida", f"La página es un entero desde 1; se recibió {pagina!r}.")
        if "original_sha256" in ev:
            self.patron(f"{ruta}.original_sha256", ev["original_sha256"], PATRON_SHA256, "SHA256 en minúsculas")
        if "recorte_id" in ev:
            self.patron(f"{ruta}.recorte_id", ev["recorte_id"], PATRON_ID, "un identificador de recorte")
        if "imagen_sha256" in ev:
            self.patron(f"{ruta}.imagen_sha256", ev["imagen_sha256"], PATRON_SHA256, "SHA256 en minúsculas")
            if "recorte_id" not in ev:
                self.error(f"{ruta}.imagen_sha256", "recorte_ausente", "imagen_sha256 requiere recorte_id.")
        if "bbox_normalizada" in ev:
            self.bbox(f"{ruta}.bbox_normalizada", ev["bbox_normalizada"])
        if len(self.r.errores) > errores_previos:
            return "invalida"
        if self.inv is None:
            return "referencia_no_comprobada"
        return self.contrastar(ruta, ev)

    def bbox(self, ruta: str, valor: Any) -> None:
        if not isinstance(valor, list) or len(valor) != 4:
            self.error(ruta, "bbox_invalida", "Se requiere [x0, y0, x1, y1].")
            return
        for k, v in enumerate(valor):
            if not es_numero(v):
                self.error(f"{ruta}[{k}]", "tipo_invalido", f"Se esperaba un número; se recibió {_tipo(v)}.")
                return
            if not math.isfinite(v):
                self.error(f"{ruta}[{k}]", "no_finito", f"Valor no finito ({v}).")
                return
        x0, y0, x1, y1 = valor
        if not (0 <= x0 < x1 <= 1 and 0 <= y0 < y1 <= 1):
            self.error(ruta, "bbox_fuera_de_rango", "Requiere 0 <= x0 < x1 <= 1 y 0 <= y0 < y1 <= 1 (área positiva).")

    def contrastar(self, ruta: str, ev: dict) -> str:
        archivo = self.inv.get("archivos", {}).get(ev["archivo_id"])
        if archivo is None:
            self.error(f"{ruta}.archivo_id", "referencia_rota", f"'{ev['archivo_id']}' no existe en el expediente.")
            return "incompatible"
        estado = "comprobada"
        if archivo.get("sha256") != ev["original_sha256"]:
            self.error(f"{ruta}.original_sha256", "hash_incompatible", "No coincide con el hash registrado del original.")
            estado = "incompatible"
        paginas = archivo.get("paginas")
        if paginas is None:
            self.advertencia(f"{ruta}.pagina", "pagina_no_comprobada", "El inventario no registra el número de páginas.")
            estado = "parcial" if estado == "comprobada" else estado
        elif ev["pagina"] > paginas:
            self.error(f"{ruta}.pagina", "pagina_inexistente", f"El archivo tiene {paginas} página(s).")
            estado = "incompatible"
        if "recorte_id" in ev:
            recorte = self.inv.get("recortes", {}).get(ev["recorte_id"])
            if recorte is None:
                self.error(f"{ruta}.recorte_id", "referencia_rota", f"Recorte '{ev['recorte_id']}' no registrado.")
                return "incompatible"
            for propio, del_recorte in (("archivo_id", "archivo_id"), ("pagina", "pagina"), ("original_sha256", "origen_sha256")):
                if recorte.get(del_recorte) != ev[propio]:
                    self.error(f"{ruta}.{propio}", "recorte_incompatible", "No coincide con el registro del recorte.")
                    estado = "incompatible"
            if "imagen_sha256" in ev and recorte.get("imagen_sha256") != ev["imagen_sha256"]:
                self.error(f"{ruta}.imagen_sha256", "hash_incompatible", "No coincide con el hash del recorte.")
                estado = "incompatible"
            rb = recorte.get("bbox_normalizada")
            b = ev["bbox_normalizada"]
            if isinstance(rb, list) and len(rb) == 4 and not (rb[0] <= b[0] and rb[1] <= b[1] and b[2] <= rb[2] and b[3] <= rb[3]):
                self.advertencia(f"{ruta}.bbox_normalizada", "bbox_fuera_del_recorte", "La región excede la del recorte citado.")
        return estado

    def revision(self, ruta: str, tipo: Any, valor: Any) -> str | None:
        if valor is None:
            return "pendiente"  # sin bloque de revisión: aún no revisado
        if not self.objeto(ruta, valor, _CAMPOS_REVISION):
            return None
        historial = valor.get("historial")
        if "historial" in valor and not isinstance(historial, list):
            self.error(f"{ruta}.historial", "tipo_invalido", "Se esperaba una lista.")
            historial = None
        ultimo_estado = "pendiente"
        fecha_previa = None
        for k, entrada in enumerate(historial or []):
            rk = f"{ruta}.historial[{k}]"
            if not self.objeto(rk, entrada, _CAMPOS_ENTRADA_02 if self.v02 else _CAMPOS_ENTRADA):
                continue
            tipo_entrada = tipo
            if "tipo_revisado" in entrada:
                if entrada.get("estado") != "revisado":
                    self.error(f"{rk}.tipo_revisado", "campo_no_aplicable", "Solo una entrada 'revisado' reclasifica.")
                elif entrada["tipo_revisado"] not in TIPOS_SEMANTICOS:
                    self.error(f"{rk}.tipo_revisado", "tipo_candidato_invalido", f"Use: {', '.join(TIPOS_SEMANTICOS)}.")
                else:
                    tipo_entrada = entrada["tipo_revisado"]
            estado = entrada.get("estado")
            if estado not in ESTADOS_REVISION:
                self.error(f"{rk}.estado", "estado_invalido", f"Use: {', '.join(ESTADOS_REVISION)}.")
            for clave in ("motivo", "revisor_declarado"):
                if clave in entrada:
                    self.texto(f"{rk}.{clave}", entrada[clave])
            fecha = self.fecha(f"{rk}.fecha", entrada.get("fecha"))
            if fecha and fecha_previa and fecha < fecha_previa:
                self.error(f"{rk}.fecha", "historial_desordenado", "Las fechas del historial no pueden retroceder.")
            fecha_previa = fecha or fecha_previa
            if estado == "revisado":
                for clave in ("valor_revisado", "unidad_revisada"):
                    if clave not in entrada:
                        self.error(f"{rk}.{clave}", "campo_ausente", "Un candidato revisado declara valor y unidad explícitos.")
                if "valor_revisado" in entrada:
                    self.valor(f"{rk}.valor_revisado", tipo_entrada, entrada["valor_revisado"], admite_nulo=False)
                if "unidad_revisada" in entrada:
                    self.unidad(f"{rk}.unidad_revisada", tipo_entrada, entrada["unidad_revisada"])
            elif estado in ESTADOS_REVISION:
                for clave in ("valor_revisado", "unidad_revisada"):
                    if clave in entrada:
                        self.error(f"{rk}.{clave}", "campo_no_aplicable", f"No corresponde a una entrada '{estado}'.")
            if estado in ESTADOS_REVISION:
                ultimo_estado = estado
        actual = valor.get("estado")
        if "estado" in valor:
            if actual not in ESTADOS_REVISION:
                self.error(f"{ruta}.estado", "estado_invalido", f"Use: {', '.join(ESTADOS_REVISION)}.")
                return None
            if actual != ultimo_estado:
                self.error(f"{ruta}.estado", "estado_incoherente", f"El historial termina en '{ultimo_estado}'.")
        return actual if actual in ESTADOS_REVISION else None


def validar_extraccion(data: Any, inventario: dict[str, Any] | None = None) -> ResultadoExtraccion:
    """Valida el registro. Sin inventario, las referencias quedan como 'referencia_no_comprobada'."""
    return _Validador(data, inventario).ejecutar()


# -- correcciones y exportación ---------------------------------------------

def corregir(
    data: dict[str, Any],
    candidato_id: str,
    *,
    estado: str,
    motivo: str,
    fecha: str,
    revisor_declarado: str,
    valor_revisado: Any = _SIN_VALOR,
    unidad_revisada: Any = _SIN_VALOR,
    tipo_revisado: Any = _SIN_VALOR,
) -> dict[str, Any]:
    """Devuelve una copia con una nueva entrada de revisión; `data` no se modifica.

    `tipo_revisado` (solo 0.2.0) reclasifica la lectura, p. ej. una «cota 6» que es una cantidad de barras.

    `valor_propuesto` se conserva. Para 'revisado' deben indicarse valor y unidad,
    aunque repitan lo propuesto. `revisor_declarado` es una declaración, no una firma verificada.
    """
    previo = validar_extraccion(data)
    if not previo.consistente:
        raise ErrorExtraccion("El registro de entrada no es consistente: " + "; ".join(map(str, previo.errores)))
    nuevo = copy.deepcopy(data)
    candidatos = [c for c in nuevo["candidatos"] if c["id"] == candidato_id]
    if not candidatos:
        raise ErrorExtraccion(f"Candidato '{candidato_id}' inexistente.")
    candidato = candidatos[0]
    entrada: dict[str, Any] = {"estado": estado, "motivo": motivo, "fecha": fecha, "revisor_declarado": revisor_declarado}
    if valor_revisado is not _SIN_VALOR:
        entrada["valor_revisado"] = copy.deepcopy(valor_revisado)
    if unidad_revisada is not _SIN_VALOR:
        entrada["unidad_revisada"] = unidad_revisada
    if tipo_revisado is not _SIN_VALOR:
        entrada["tipo_revisado"] = tipo_revisado
    revision = candidato.setdefault("revision", {"estado": "pendiente", "historial": []})
    revision["historial"].append(entrada)
    revision["estado"] = estado
    resultado = validar_extraccion(nuevo)
    if not resultado.consistente:
        raise ErrorExtraccion("Corrección rechazada: " + "; ".join(map(str, resultado.errores)))
    return nuevo


def exportar_revisados(data: dict[str, Any], inventario: dict[str, Any] | None = None) -> dict[str, Any]:
    """Exporta solo candidatos 'revisado' con su evidencia, procedencia y alcance.

    No convierte candidatos en geometría ni normaliza unidades; los pendientes y
    rechazados se listan como excluidos. No constituye aprobación de ingeniería.
    """
    resultado = validar_extraccion(data, inventario)
    if not resultado.consistente:
        raise ErrorExtraccion("No se exporta un registro inconsistente: " + "; ".join(map(str, resultado.errores)))
    exportados, pendientes, rechazados, resultados_impresos = [], [], [], []
    for cand in data["candidatos"]:
        revision = cand.get("revision") or {"estado": "pendiente", "historial": []}
        if revision["estado"] == "pendiente":
            pendientes.append(cand["id"])
            continue
        if revision["estado"] == "rechazado":
            rechazados.append(cand["id"])
            continue
        final = revision["historial"][-1]
        tipo_final = final.get("tipo_revisado", cand["tipo"])
        if tipo_final == "resultado_impreso":
            resultados_impresos.append(cand["id"])  # nunca entrada ni calibración
            continue
        evidencia = copy.deepcopy(cand["evidencia"])
        for ev, estado_ref in zip(evidencia, resultado.referencias[cand["id"]]):
            ev["estado_referencia"] = estado_ref
        exportado = {
            "id": cand["id"],
            "tipo": tipo_final,
            "valor_propuesto": copy.deepcopy(cand["valor_propuesto"]),
            "unidad_propuesta": cand["unidad"],
            "valor_revisado": copy.deepcopy(final["valor_revisado"]),
            "unidad_revisada": final["unidad_revisada"],
            "corregido": (final["valor_revisado"], final["unidad_revisada"], tipo_final) != (cand["valor_propuesto"], cand["unidad"], cand["tipo"]),
            "metodo": copy.deepcopy(cand["metodo"]),
            "evidencia": evidencia,
            "revision": copy.deepcopy(revision),
        }
        if tipo_final != cand["tipo"]:
            exportado["tipo_propuesto"] = cand["tipo"]
        if "historial_evidencia" in cand:
            exportado["historial_evidencia"] = copy.deepcopy(cand["historial_evidencia"])
        for clave in ("texto_fuente", "simbolo"):
            if clave in cand:
                exportado[clave] = cand[clave]
        exportados.append(exportado)
    excluidos = {"pendientes": pendientes, "rechazados": rechazados}
    if data["version_contrato"] == VERSION_SEMANTICA:
        excluidos["resultados_impresos"] = resultados_impresos
    return {
        "contrato": CONTRATO_EXPORTACION,
        "version_contrato": data["version_contrato"],
        "aviso": AVISO,
        "caso": data["caso"],
        "procedencia": copy.deepcopy(data["procedencia"]),
        "alcance": copy.deepcopy(data["alcance"]),
        "sistema_coordenadas": data["sistema_coordenadas"],
        "huella_extraccion": huella(data),
        "inventario_aportado": inventario is not None,
        "aprobacion_ingenieria": None,
        "candidatos": exportados,
        "excluidos": excluidos,
    }


# -- lectura -----------------------------------------------------------------

def cargar_extraccion(path: Path) -> Any:
    """Lee JSON rechazando claves repetidas y literales NaN/Infinity."""

    def sin_duplicados(pares: list[tuple[str, Any]]) -> dict[str, Any]:
        resultado: dict[str, Any] = {}
        for clave, valor in pares:
            if clave in resultado:
                raise ErrorExtraccion(f"Clave JSON repetida: '{clave}'.")
            resultado[clave] = valor
        return resultado

    def constante(nombre: str) -> Any:
        raise ErrorExtraccion(f"Valor no finito '{nombre}' no admitido.")

    try:
        return json.loads(
            Path(path).read_text(encoding="utf-8"), object_pairs_hook=sin_duplicados, parse_constant=constante
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ErrorExtraccion(f"No se pudo leer {Path(path).name}: {exc}") from exc


def _tipo(valor: Any) -> str:
    if valor is None:
        return "null"
    if isinstance(valor, bool):
        return "booleano"
    return {int: "entero", float: "número", str: "texto", list: "lista", dict: "objeto"}.get(
        type(valor), type(valor).__name__
    )
