"""Contrato explícito de configuración estructural para un adaptador por plantilla.

Valida datos y trazabilidad; no calcula estructuras ni ejecuta ETABS. No impone
número de pisos ni atribuye a una representación equivalencia con albañilería.

Versiones: 0.1.0 (muros y frames sobre nodo+nivel) se valida sin cambios. 0.2.0
(despacho explícito) añade puntos ligados a vértices XYZ de la geometría 0.2,
asignaciones de superficies con la sección de prueba `shell_losa_homogenea` y cargas
uniformes de superficie. La 0.2 nunca queda apta para el adaptador: conserva el
bloqueo de integración geométrico y el propio, y solo informa si puede compilarse un
plan de desarrollo no ejecutable.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from . import gestion_geometria as gg
from .contratos import VERSION_GEOMETRIA_SUPERFICIES, VERSION_GEOMETRIA_ABERTURAS
from .geometria_aberturas import BLOQUEO_INTEGRACION as BLOQUEO_GEOMETRIA_ABERTURAS
from .geometria_superficies import BLOQUEO_INTEGRACION
from .gestion_extraccion import ErrorGestion, json_desde_bytes
from .validacion_geometria import validar_geometria
from . import malla_preparacion as mp

CONTRATO = "draft2model.modelo_estructural"
VERSION = "0.1.0"
VERSION_SUPERFICIES = "0.2.0"
VERSION_ABERTURAS = "0.3.0"
VERSION_MALLA = "0.4.0"
VERSION_LIQUIDOS = "0.5.0"  # 0.4 + aplicabilidad explícita de líquidos (cisterna/tanque)
APLICABILIDAD_LIQUIDOS = ("ausente_confirmado", "presente", "informacion_insuficiente")
# Estado de llenado por depósito (liquidos.contenido, opcional, R249-02). "lleno" = nivel libre declarado en su escenario.
ESTADOS_CONTENIDO = ("lleno", "vacio", "desconocido", "ausente_confirmado")
CAMPOS_CONTENIDO = "deposito estado fuente motivo declaracion modo patron_masa_exclusivo peso_vertical_referencia_kn volumen_m3"
BLOQUEO_ABERTURAS = "Configuración v0.3: plan de desarrollo no ejecutable; efecto físico de huecos y mallado/reapertura pendientes de verificación."
PATRON_ID = r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}"
SHA = r"[0-9a-f]{64}"
BLOQUEO_SUPERFICIES = ("Configuración v0.2 de superficies: solo admite un plan de desarrollo no ejecutable; "
                       "la ejecución ETABS no está autorizada hasta revisar el recorrido completo "
                       "(gestión, plan geométrico, ejecutor, lectura e interfaz).")
TIPOS_ALIGERADOS = ("shell_losa_nervada_v1", "shell_losa_casetonada_v1")
DIM_ALIGERADOS = {
    TIPOS_ALIGERADOS[0]: "alto_total_m capa_m ancho_nervio_superior_m ancho_nervio_inferior_m separacion_m direccion_nervios angulo_ejes_locales_grados",
    TIPOS_ALIGERADOS[1]: "alto_total_m capa_m ancho_nervio_superior_m ancho_nervio_inferior_m separacion_1_m separacion_2_m angulo_ejes_locales_grados",
}
# 0.5: sección L nativa de concreto (cPropFrame.SetConcreteL). Convención de espejos e inserción ensayada en instancias
# propias (scripts/ensayar_columna_l_etabs.ps1): sin espejos los brazos van a +local2/−local3. En ese montaje (voladizo, ETABS 21.1)
# la respuesta no mostró acople por producto de inercia (I22 e I33 sobre ejes paralelos a los brazos); no se generaliza. Solo se admite inserción en el centroide (punto cardinal 10)
# con desplazamiento global y transformación de rigidez, la combinación ensayada.
SECCION_L = "frame_l_concreto"
DIM_L = "alto_m ancho_m espesor_ala_m espesor_alma_m espejo_eje_2 espejo_eje_3"
TIPOS_FRAME = ("frame_rectangular", SECCION_L)
CARDINALES_INSERCION = (10,)
CAMPOS_PUNTO_NODO = frozenset(("id", "nodo_geometria", "nivel_geometria"))
CAMPOS_PUNTO_VERTICE = frozenset(("id", "vertice_geometria"))


def _finitos_dimensiones(q):
    try:
        return all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in q.values())
    except (OverflowError, ValueError):
        return False


def huella_configuracion(data: dict) -> str:
    """Huella del JSON canónico completo excepto su bloque de revisión."""
    contenido = {clave: valor for clave, valor in data.items() if clave != "revision"}
    return hashlib.sha256(json.dumps(contenido, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


@dataclass
class ResultadoModelo:
    errores: list[str] = field(default_factory=list)
    faltantes: list[dict] = field(default_factory=list)
    bloqueos: list[str] = field(default_factory=list)
    huella_contenido: str | None = None
    aprobacion_configuracion_vigente: bool = False
    geometria_comprobada: bool = False
    apto_para_adaptador: bool = False
    comprobacion_geometria: dict | None = None
    version_contrato: str = VERSION
    geometria_aprobada_por_huella: bool = False
    apto_para_plan_desarrollo: bool = False
    preparacion_malla: dict | None = None
    contenido_masa: dict | None = None   # inventario masa_contenido calculado con la malla vigente (solo 0.5 con contenido)

    @property
    def consistente(self):
        return not self.errores

    def a_dict(self):
        salida = {"consistente": self.consistente, "errores": list(self.errores),
                  "faltantes": copy.deepcopy(self.faltantes), "bloqueos": list(self.bloqueos),
                  "huella_contenido": self.huella_contenido,
                  "aprobacion_configuracion_vigente": self.aprobacion_configuracion_vigente,
                  "geometria_comprobada": self.geometria_comprobada,
                  "apto_para_adaptador": self.apto_para_adaptador,
                  "ejecutable_en_etabs": False, "comprobacion_geometria": self.comprobacion_geometria}
        if self.version_contrato in (VERSION_SUPERFICIES, VERSION_ABERTURAS):  # 0.1 conserva su salida exacta
            salida.update(version_contrato=self.version_contrato,
                          geometria_aprobada_por_huella=self.geometria_aprobada_por_huella,
                          apto_para_plan_desarrollo=self.apto_para_plan_desarrollo)
        if self.version_contrato in (VERSION_MALLA, VERSION_LIQUIDOS):
            salida.update(version_contrato=self.version_contrato,
                          geometria_aprobada_por_huella=self.geometria_aprobada_por_huella,
                          preparacion_malla=copy.deepcopy(self.preparacion_malla))
            if self.contenido_masa is not None:   # sin la clave liquidos.contenido la salida no cambia
                salida["contenido_masa"] = copy.deepcopy(self.contenido_masa)
        return salida


def cargar_configuracion(ruta: Path) -> Any:
    try:
        contenido = Path(ruta).read_bytes()
    except OSError as exc:
        raise ErrorGestion(f"Configuración ilegible: {exc}") from exc
    return json_desde_bytes(contenido, "modelo_estructural.json")


class _Validador:
    version = VERSION
    claves_raiz = ("contrato version_contrato id caso datos_sinteticos unidades geometria_origen plantilla fuentes "
                   "hipotesis sitio materiales secciones puntos frames asignaciones_muros asignaciones_frames "
                   "patrones cargas masa apoyos diafragmas sin_diafragma espectros casos combinaciones analisis faltantes revision")
    tipos_seccion = ("shell_muro", "frame_rectangular")
    tipos_espesor = ("shell_muro",)
    objetivos_carga = ("punto", "frame", "muro")
    objetivos_geometricos = ("muro",)
    unidades_carga = {"punto": "kN", "frame": "kN/m", "muro": "kN/m2"}

    def __init__(self, data):
        self.data = data
        self.r = ResultadoModelo()
        self.declarados = {}
        self.nulos = set()

    def error(self, ruta, mensaje):
        self.r.errores.append(f"{ruta}: {mensaje}")

    def objeto(self, valor, claves, ruta):
        if not isinstance(valor, dict) or set(valor) != set(claves.split()):
            self.error(ruta, "campos requeridos exactos: " + claves)
            return False
        return True

    def lista(self, valor, ruta):
        if not isinstance(valor, list):
            self.error(ruta, "se requiere lista explícita")
            return []
        return valor

    def texto(self, valor, ruta):
        if not isinstance(valor, str) or not valor.strip():
            self.error(ruta, "se requiere texto no vacío")
            return False
        return True

    def patron(self, valor, patron, ruta):
        if not isinstance(valor, str) or not re.fullmatch(patron, valor):
            self.error(ruta, "identificador o huella inválidos")
            return False
        return True

    def opcion(self, valor, opciones, ruta):
        if not isinstance(valor, str) or valor not in opciones:
            self.error(ruta, "valor no admitido: " + ", ".join(opciones))
            return False
        return True

    def numero(self, valor, ruta, minimo=None, maximo=None, estricto=False):
        if valor is None:
            self.nulos.add(ruta)
            if ruta not in self.declarados:
                self.error(ruta, "null requiere declaración en faltantes")
            return False
        try:
            valido = isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)
        except (OverflowError, ValueError):
            valido = False
        if not valido:
            self.error(ruta, "número finito representable obligatorio")
            return False
        if minimo is not None and (valor <= minimo if estricto else valor < minimo):
            self.error(ruta, "número menor que el mínimo admitido")
        if maximo is not None and valor >= maximo:
            self.error(ruta, "número mayor o igual que el máximo admitido")
        return True

    def registros(self, valor, claves, ruta, llave="id"):
        salida = {}
        for indice, item in enumerate(self.lista(valor, ruta)):
            pos = f"{ruta}[{indice}]"
            if not self.objeto(item, claves, pos):
                continue
            ident = item[llave]
            if not self.patron(ident, PATRON_ID, pos + "." + llave):
                continue
            if ident in salida:
                self.error(pos, "identificador repetido")
            salida[ident] = item
        return salida

    def referencia(self, ident, tabla, ruta):
        if not isinstance(ident, str) or ident not in tabla:
            self.error(ruta, "referencia inexistente")
            return False
        return True

    def referencias(self, ids, tabla, ruta, no_vacia=False):
        lista = self.lista(ids, ruta)
        if no_vacia and not lista:
            self.error(ruta, "se requiere al menos una referencia")
        vistos = set()
        for ident in lista:
            if self.referencia(ident, tabla, ruta):
                if ident in vistos:
                    self.error(ruta, "referencia repetida")
                vistos.add(ident)
        return vistos

    def validar(self, geometria):
        d, r = self.data, self.r
        if not self.objeto(d, self.claves_raiz, "$"):
            return r
        if d["contrato"] != CONTRATO or d["version_contrato"] != self.version:
            self.error("$", "contrato o versión no admitidos")
        self.patron(d["caso"], PATRON_ID, "$.caso")
        self.patron(d["id"], PATRON_ID, "$.id")
        if type(d["datos_sinteticos"]) is not bool:
            self.error("$.datos_sinteticos", "debe ser booleano")
        unidades = {"longitud": "m", "fuerza": "kN", "tiempo": "s", "temperatura": "C"}
        if d["unidades"] != unidades:
            self.error("$.unidades", "se requieren unidades explícitas m, kN, s, C")
        fuentes = self.registros(d["fuentes"], "id descripcion referencia sha256", "$.fuentes")
        if not fuentes:
            self.error("$.fuentes", "se requiere al menos una fuente")
        for ident, fuente in fuentes.items():
            self.texto(fuente["descripcion"], f"fuentes.{ident}.descripcion")
            self.texto(fuente["referencia"], f"fuentes.{ident}.referencia")
            self.patron(fuente["sha256"], SHA, f"fuentes.{ident}.sha256")
        for indice, item in enumerate(self.lista(d["faltantes"], "$.faltantes")):
            if self.objeto(item, "ruta motivo fuente", f"$.faltantes[{indice}]"):
                if self.texto(item["ruta"], "faltante.ruta"):
                    if item["ruta"] in self.declarados:
                        self.error("$.faltantes", "ruta repetida")
                    self.declarados[item["ruta"]] = item
                self.texto(item["motivo"], "faltante.motivo")
                self.referencia(item["fuente"], fuentes, "faltante.fuente")
        r.faltantes = [{clave: valor if isinstance(valor, str) else None for clave, valor in item.items()}
                       for item in self.declarados.values()]
        origen = d["geometria_origen"]
        if self.objeto(origen, "version_id sha256_geometria huella_contenido", "$.geometria_origen"):
            self.patron(origen["version_id"], r"[0-9a-f]{32}", "geometria_origen.version_id")
            for clave in ("sha256_geometria", "huella_contenido"):
                self.patron(origen[clave], SHA, "geometria_origen." + clave)
        plantilla = d["plantilla"]
        if self.objeto(plantilla, "id version sha256 representacion limitaciones fuente", "$.plantilla"):
            for clave in ("id", "version", "representacion"):
                self.texto(plantilla[clave], "plantilla." + clave)
            self.patron(plantilla["sha256"], SHA, "plantilla.sha256")
            self.referencia(plantilla["fuente"], fuentes, "plantilla.fuente")
            if not self.lista(plantilla["limitaciones"], "plantilla.limitaciones"):
                self.error("plantilla.limitaciones", "declarar alcance y limitaciones de la representación")
            for texto in self.lista(plantilla["limitaciones"], "plantilla.limitaciones"):
                self.texto(texto, "plantilla.limitaciones")
        hipotesis = self.registros(d["hipotesis"], "id descripcion fuente", "$.hipotesis")
        if not hipotesis:
            self.error("$.hipotesis", "declare las hipótesis de representación")
        for item in hipotesis.values():
            self.texto(item["descripcion"], "hipotesis.descripcion")
            self.referencia(item["fuente"], fuentes, "hipotesis.fuente")
        sitio = d["sitio"]
        if self.objeto(sitio, "descripcion ubicacion sistema_resistente parametros fuente", "$.sitio"):
            for clave in ("descripcion", "ubicacion", "sistema_resistente"):
                if sitio[clave] is None:
                    self.nulos.add("$.sitio." + clave)
                    if "$.sitio." + clave not in self.declarados:
                        self.error("$.sitio." + clave, "null requiere declaración de faltante")
                else:
                    self.texto(sitio[clave], "$.sitio." + clave)
            self.referencia(sitio["fuente"], fuentes, "sitio.fuente")
            parametros = self.registros(sitio["parametros"], "id valor unidad fuente", "$.sitio.parametros")
            for ident, item in parametros.items():
                self.numero(item["valor"], f"$.sitio.parametros.{ident}.valor")
                self.opcion(item["unidad"], ("1", "m", "s", "m/s2", "kN/m2"), "parametro.unidad")
                self.referencia(item["fuente"], fuentes, "parametro.fuente")
        materiales = self.registros(d["materiales"], "id tipo E_kN_m2 poisson peso_kN_m3 fuente", "$.materiales")
        for ident, item in materiales.items():
            self.opcion(item["tipo"], ("isotropo_lineal",), "material.tipo")
            self.numero(item["E_kN_m2"], f"$.materiales.{ident}.E_kN_m2", 0, estricto=True)
            self.numero(item["poisson"], f"$.materiales.{ident}.poisson", -1, .5, estricto=True)
            self.numero(item["peso_kN_m3"], f"$.materiales.{ident}.peso_kN_m3", 0)
            self.referencia(item["fuente"], fuentes, "material.fuente")
        secciones = self.registros(d["secciones"], "id tipo material dimensiones fuente", "$.secciones")
        for ident, item in secciones.items():
            self.opcion(item["tipo"], self.tipos_seccion, "seccion.tipo")
            self.referencia(item["material"], materiales, "seccion.material")
            self.referencia(item["fuente"], fuentes, "seccion.fuente")
            dims = DIM_L if item["tipo"] == SECCION_L else DIM_ALIGERADOS[item["tipo"]] if self.version in (VERSION_SUPERFICIES, VERSION_ABERTURAS, VERSION_MALLA, VERSION_LIQUIDOS) and isinstance(item["tipo"], str) and item["tipo"] in DIM_ALIGERADOS else ("espesor_m" if item["tipo"] in self.tipos_espesor else "ancho_m alto_m")
            if self.objeto(item["dimensiones"], dims, "seccion.dimensiones"):
                for clave, valor in item["dimensiones"].items():
                    if item["tipo"] == SECCION_L and clave.startswith("espejo_eje_"):
                        if type(valor) is not bool:
                            self.error(f"$.secciones.{ident}.dimensiones.{clave}", "espejo: booleano explícito")
                    elif self.version in (VERSION_SUPERFICIES, VERSION_ABERTURAS, VERSION_MALLA, VERSION_LIQUIDOS) and item["tipo"] in TIPOS_ALIGERADOS and clave == "angulo_ejes_locales_grados":
                        self.numero(valor, f"$.secciones.{ident}.dimensiones.{clave}", -180, 180)
                    else:
                        self.numero(valor, f"$.secciones.{ident}.dimensiones.{clave}", 0, estricto=True)
        self.secciones_extra(secciones, materiales)
        ctx = self.objetos(geometria, fuentes, secciones)
        puntos, frames = ctx["puntos"], ctx["frames"]
        patrones = self.registros(d["patrones"], "id tipo multiplicador_peso_propio fuente", "$.patrones")
        for ident, item in patrones.items():
            self.opcion(item["tipo"], ("muerta", "viva", "sismo", "otro"), "patron.tipo")
            self.numero(item["multiplicador_peso_propio"], f"$.patrones.{ident}.multiplicador_peso_propio", 0)
            self.referencia(item["fuente"], fuentes, "patron.fuente")
        for item in self.registros(d["cargas"], "id patron objetivo_tipo objetivo componentes unidad sistema fuente", "$.cargas").values():
            self.referencia(item["patron"], patrones, "carga.patron")
            self.opcion(item["objetivo_tipo"], self.objetivos_carga, "carga.objetivo_tipo")
            tabla = self.tabla_carga(ctx, item["objetivo_tipo"])
            if item["objetivo_tipo"] not in self.objetivos_geometricos or geometria is not None:
                self.referencia(item["objetivo"], tabla, "carga.objetivo")
            unidad = self.unidades_carga.get(item["objetivo_tipo"]) if isinstance(item["objetivo_tipo"], str) else None
            if item["unidad"] != unidad or item["sistema"] != "global":
                self.error("$.cargas", "unidad o sistema incompatible con objetivo")
            vector = self.lista(item["componentes"], "carga.componentes")
            if len(vector) != 3:
                self.error("$.cargas", "se requieren tres fuerzas traslacionales globales X,Y,Z")
            for j, valor in enumerate(vector):
                self.numero(valor, f"$.cargas.{item['id']}.componentes[{j}]")
            self.referencia(item["fuente"], fuentes, "carga.fuente")
        masa = d["masa"]
        if self.objeto(masa, "metodo gravedad_m_s2 incluir_masa_propia factores_patrones masas_puntos fuente", "$.masa"):
            self.opcion(masa["metodo"], ("patrones", "explicita"), "masa.metodo")
            self.numero(masa["gravedad_m_s2"], "$.masa.gravedad_m_s2", 0, estricto=True)
            if type(masa["incluir_masa_propia"]) is not bool:
                self.error("$.masa.incluir_masa_propia", "debe ser booleano")
            factores = self.factores(masa["factores_patrones"], patrones, "patron", "$.masa.factores_patrones", positivos=True)
            masas = self.registros(masa["masas_puntos"], "punto masa_kN_s2_m", "$.masa.masas_puntos", "punto")
            for ident, item in masas.items():
                self.referencia(ident, puntos, "masa.punto")
                self.numero(item["masa_kN_s2_m"], f"$.masa.masas_puntos.{ident}.masa_kN_s2_m", 0)
            if (masa["metodo"] == "patrones" and (not factores or masas)) or (masa["metodo"] == "explicita" and (not masas or factores)):
                self.error("$.masa", "seleccione una única fuente explícita y no vacía de masa")
            valores_masa = [item["factor"] for item in factores.values()] if masa["metodo"] == "patrones" else [item["masa_kN_s2_m"] for item in masas.values()]
            if masa["incluir_masa_propia"] is False and valores_masa and all(isinstance(x, (int, float)) and not isinstance(x, bool) and x == 0 for x in valores_masa):
                self.error("$.masa", "fuente de masa nula: declare una contribución positiva o un faltante")
            if masa["incluir_masa_propia"] is True:
                for ident, item in factores.items():
                    multiplicador = patrones.get(ident, {}).get("multiplicador_peso_propio")
                    if isinstance(multiplicador, (int, float)) and not isinstance(multiplicador, bool) and multiplicador > 0 and item["factor"] != 0:
                        self.error("$.masa", "masa propia y patrón con peso propio duplican la misma contribución")
            self.referencia(masa["fuente"], fuentes, "masa.fuente")
            self.masa_extra(masa)
        apoyos = self.registros(d["apoyos"], "punto restricciones fuente", "$.apoyos", "punto")
        if not apoyos:
            self.error("$.apoyos", "declare apoyos; no se infieren")
        for ident, apoyo in apoyos.items():
            self.referencia(ident, puntos, "apoyo.punto")
            restr = apoyo["restricciones"]
            if not isinstance(restr, list) or len(restr) != 6 or any(type(x) is not bool for x in restr) or not any(restr):
                self.error("$.apoyos", "se requieren seis booleanos Ux,Uy,Uz,Rx,Ry,Rz y alguna restricción")
            self.referencia(apoyo["fuente"], fuentes, "apoyo.fuente")
        self.conectividad(ctx, apoyos)
        cobertura = set()
        for diafragma in self.registros(d["diafragmas"], "id tipo puntos fuente", "$.diafragmas").values():
            self.opcion(diafragma["tipo"], ("rigido", "semirigido"), "diafragma.tipo")
            miembros = self.referencias(diafragma["puntos"], puntos, "diafragma.puntos", True)
            self.coplanaridad(ctx, miembros, geometria)
            if cobertura & miembros:
                self.error("$.diafragmas", "punto asignado más de una vez")
            cobertura |= miembros
            self.referencia(diafragma["fuente"], fuentes, "diafragma.fuente")
        for ident, item in self.registros(d["sin_diafragma"], "punto motivo fuente", "$.sin_diafragma", "punto").items():
            self.referencia(ident, puntos, "sin_diafragma.punto")
            if ident in cobertura:
                self.error("$.sin_diafragma", "punto también asignado a diafragma")
            cobertura.add(ident)
            self.texto(item["motivo"], "sin_diafragma.motivo")
            self.referencia(item["fuente"], fuentes, "sin_diafragma.fuente")
        if cobertura != set(puntos):
            self.error("$.diafragmas", "cada punto requiere diafragma o exclusión justificada")
        espectros = self.registros(d["espectros"], "id unidad_aceleracion puntos fuente", "$.espectros")
        for item in espectros.values():
            if item["unidad_aceleracion"] != "m/s2":
                self.error("$.espectros", "aceleración debe expresarse en m/s2")
            anterior = -1
            muestras = self.lista(item["puntos"], "espectro.puntos")
            if len(muestras) < 2:
                self.error("$.espectros", "requiere al menos dos pares periodo_s,aceleracion_m_s2")
            for j, par in enumerate(muestras):
                if not isinstance(par, list) or len(par) != 2:
                    self.error("$.espectros", "par de periodo y aceleración inválido")
                    continue
                if self.numero(par[0], f"$.espectros.{item['id']}.puntos[{j}][0]", 0):
                    if par[0] <= anterior:
                        self.error("$.espectros", "periodos deben ser estrictamente crecientes")
                    anterior = par[0]
                self.numero(par[1], f"$.espectros.{item['id']}.puntos[{j}][1]", 0)
            self.referencia(item["fuente"], fuentes, "espectro.fuente")
        casos = self.registros(d["casos"], "id tipo parametros fuente", "$.casos")
        if not casos:
            self.error("$.casos", "declare al menos un caso de análisis")
        for ident, item in casos.items():
            self.opcion(item["tipo"], ("estatico_lineal", "modal_eigen", "espectro_respuesta"), "caso.tipo")
            self.referencia(item["fuente"], fuentes, "caso.fuente")
            params = item["parametros"]
            if item["tipo"] == "estatico_lineal" and self.objeto(params, "patrones", "caso.parametros"):
                if not self.factores(params["patrones"], patrones, "patron", "caso.patrones"):
                    self.error("$.casos", "caso estático sin patrones")
            elif item["tipo"] == "modal_eigen" and self.objeto(params, "numero_modos", "caso.parametros"):
                numero = params["numero_modos"]
                if numero is None:
                    self.numero(numero, f"$.casos.{ident}.parametros.numero_modos")
                elif type(numero) is not int or not 1 <= numero <= 2**31 - 1:
                    self.error("$.casos", "numero_modos requiere entero positivo")
            elif item["tipo"] == "espectro_respuesta" and self.objeto(params, "modal espectro direccion factor amortiguamiento combinacion_modal", "caso.parametros"):
                if self.referencia(params["modal"], casos, "caso.modal") and casos[params["modal"]]["tipo"] != "modal_eigen":
                    self.error("$.casos", "referencia modal no corresponde a caso modal")
                self.referencia(params["espectro"], espectros, "caso.espectro")
                self.opcion(params["direccion"], ("UX", "UY", "UZ"), "caso.direccion")
                self.numero(params["factor"], f"$.casos.{ident}.parametros.factor", 0, estricto=True)
                self.numero(params["amortiguamiento"], f"$.casos.{ident}.parametros.amortiguamiento", 0, 1, estricto=True)
                self.opcion(params["combinacion_modal"], ("CQC", "SRSS"), "caso.combinacion_modal")
        combinaciones = self.registros(d["combinaciones"], "id tipo casos fuente", "$.combinaciones")
        for item in combinaciones.values():
            self.opcion(item["tipo"], ("lineal", "envolvente"), "combinacion.tipo")
            if not self.factores(item["casos"], casos, "caso", "combinacion.casos"):
                self.error("$.combinaciones", "combinación sin casos")
            self.referencia(item["fuente"], fuentes, "combinacion.fuente")
        analisis = d["analisis"]
        if self.objeto(analisis, "casos_ejecutar combinaciones_resultados fuente", "$.analisis"):
            ejecutar = self.referencias(analisis["casos_ejecutar"], casos, "analisis.casos_ejecutar", True)
            combos = self.referencias(analisis["combinaciones_resultados"], combinaciones, "analisis.combinaciones_resultados")
            for ident in ejecutar:
                item = casos[ident]
                if item["tipo"] == "espectro_respuesta" and isinstance(item["parametros"], dict) and (not isinstance(item["parametros"].get("modal"), str) or item["parametros"].get("modal") not in ejecutar):
                    self.error("$.analisis", "caso espectral requiere ejecutar su caso modal")
            for ident in combos:
                for factor in self.lista(combinaciones[ident]["casos"], "combinacion.casos"):
                    if isinstance(factor, dict) and (not isinstance(factor.get("caso"), str) or factor.get("caso") not in ejecutar):
                        self.error("$.analisis", "combinación seleccionada usa un caso que no se ejecuta")
            self.referencia(analisis["fuente"], fuentes, "analisis.fuente")
        self.revision(d["revision"])
        if r.errores:
            r.bloqueos.append("Configuración inconsistente.")
        if r.faltantes:
            r.bloqueos.append("Configuración con faltantes declarados.")
        if not r.aprobacion_configuracion_vigente:
            r.bloqueos.append("Configuración sin aprobación declarada vigente.")
        return r

    # -- puntos de extensión (0.1: comportamiento histórico exacto) ------------

    def secciones_extra(self, secciones, materiales):
        pass

    def masa_extra(self, masa):
        pass

    def conectividad(self, ctx, apoyos):
        pass

    def tabla_carga(self, ctx, tipo):
        return ctx["puntos"] if tipo == "punto" else ctx["frames"] if tipo == "frame" else ctx["muros_geo"]

    def coplanaridad(self, ctx, miembros, geometria):
        niveles, puntos = ctx["niveles"], ctx["puntos"]
        if geometria is not None and niveles:
            cotas = {niveles.get(puntos[ident]["nivel_geometria"]) for ident in miembros
                     if isinstance(puntos[ident]["nivel_geometria"], str)}
            if len(cotas) > 1:
                self.error("$.diafragmas", "los puntos de un diafragma deben ser coplanares en cota")

    def objetos(self, geometria, fuentes, secciones):
        d, r = self.data, self.r
        puntos = self.registros(d["puntos"], "id nodo_geometria nivel_geometria", "$.puntos")
        pares = {}
        for ident, punto in puntos.items():
            nodo, nivel = punto["nodo_geometria"], punto["nivel_geometria"]
            if self.patron(nodo, PATRON_ID, "punto.nodo") and self.patron(nivel, PATRON_ID, "punto.nivel"):
                if (nodo, nivel) in pares:
                    self.error("$.puntos", "dos puntos modelan el mismo nodo/nivel")
                pares[nodo, nivel] = ident
        frames = self.registros(d["frames"], "id inicio fin tipo fuente", "$.frames")
        usados = set()
        conexiones_frame = set()
        for item in frames.values():
            for clave in ("inicio", "fin"):
                if self.referencia(item[clave], puntos, "frame." + clave):
                    usados.add(item[clave])
            if item["inicio"] == item["fin"]:
                self.error("$.frames", "extremos del frame deben ser distintos")
            if isinstance(item["inicio"], str) and isinstance(item["fin"], str):
                conexion = tuple(sorted((item["inicio"], item["fin"])))
                if conexion in conexiones_frame:
                    self.error("$.frames", "dos frames repiten la misma conexión")
                conexiones_frame.add(conexion)
            self.opcion(item["tipo"], ("viga", "columna", "otro"), "frame.tipo")
            self.referencia(item["fuente"], fuentes, "frame.fuente")
        muros_geo = {}
        niveles = {}
        if geometria is not None:
            vg = validar_geometria(geometria)
            if not vg.consistente:
                self.error("geometria", "contrato geométrico inconsistente")
            else:
                origen = d["geometria_origen"]
                if geometria["id"] != d["caso"] or vg.datos_sinteticos is not d["datos_sinteticos"]:
                    self.error("geometria", "caso o marca sintética no corresponden")
                if isinstance(origen, dict) and origen.get("huella_contenido") != vg.huella_contenido:
                    self.error("geometria", "huella de contenido no corresponde")
                niveles = {x["id"]: x["cota"] for x in vg.geometria_m["niveles"]}
                nodos = {x["id"]: x for x in vg.geometria_m["nodos"]}
                muros_geo = {x["id"]: x for x in vg.geometria_m["muros"]}
                for nodo, nivel in pares:
                    self.referencia(nodo, nodos, "punto.nodo_geometria")
                    self.referencia(nivel, niveles, "punto.nivel_geometria")
                for muro in muros_geo.values():
                    for nodo in (muro["nodo_inicio"], muro["nodo_fin"]):
                        for nivel in (muro["nivel_inferior"], muro["nivel_superior"]):
                            if (nodo, nivel) not in pares:
                                self.error("$.puntos", "falta esquina de muro: " + nodo + "/" + nivel)
                            else:
                                usados.add(pares[nodo, nivel])
                for frame in frames.values():
                    a = puntos.get(frame["inicio"]) if isinstance(frame["inicio"], str) else None
                    b = puntos.get(frame["fin"]) if isinstance(frame["fin"], str) else None
                    if a and b and all(isinstance(p["nodo_geometria"], str) and isinstance(p["nivel_geometria"], str)
                                       and p["nodo_geometria"] in nodos and p["nivel_geometria"] in niveles for p in (a, b)):
                        pa = (nodos[a["nodo_geometria"]]["x"], nodos[a["nodo_geometria"]]["y"], niveles[a["nivel_geometria"]])
                        pb = (nodos[b["nodo_geometria"]]["x"], nodos[b["nodo_geometria"]]["y"], niveles[b["nivel_geometria"]])
                        self.frame_fisico(frame, pa, pb)
                for ident in puntos.keys() - usados:
                    self.error("$.puntos", "punto sin conexión a muro o frame: " + ident)
                if not vg.disponible_para_modelado:
                    r.bloqueos.append("Geometría sin aprobación vigente o con faltantes.")
        else:
            r.bloqueos.append("Falta comprobar la geometría versionada y su cobertura.")
        self.asignaciones_muros_frames(geometria, secciones, fuentes, muros_geo, frames)
        return {"puntos": puntos, "frames": frames, "muros_geo": muros_geo, "niveles": niveles}

    def frame_fisico(self, frame, pa, pb):
        if pa == pb:
            self.error("$.frames", "frame de longitud física nula")
        if frame["tipo"] == "columna" and pa[:2] != pb[:2]:
            self.error("$.frames", "columna declarada requiere extremos verticalmente alineados")
        if frame["tipo"] == "viga" and pa[2] != pb[2]:
            self.error("$.frames", "viga declarada requiere extremos en la misma cota; use otro para inclinadas")

    def asignaciones_muros_frames(self, geometria, secciones, fuentes, muros_geo, frames):
        d = self.data
        asignados_murosshell = self.asignaciones(d["asignaciones_muros"], secciones, muros_geo if geometria is not None else None, "shell_muro", fuentes)
        asignados_frames = self.asignaciones(d["asignaciones_frames"], secciones, frames, "frame_rectangular", fuentes)
        if geometria is not None and asignados_murosshell != set(muros_geo):
            self.error("$.asignaciones_muros", "cobertura de muros incompleta")
        if asignados_frames != set(frames):
            self.error("$.asignaciones_frames", "cobertura de frames incompleta")
        if geometria is not None:
            for item in self.lista(d["asignaciones_muros"], "$.asignaciones_muros"):
                if isinstance(item, dict) and isinstance(item.get("objetivo"), str) and isinstance(item.get("seccion"), str):
                    muro, seccion = muros_geo.get(item["objetivo"]), secciones.get(item["seccion"])
                    if muro and seccion and isinstance(seccion["dimensiones"], dict):
                        espesor = seccion["dimensiones"].get("espesor_m")
                        if espesor is not None and espesor != muro["espesor"]:
                            self.error("$.asignaciones_muros", "espesor de sección difiere de geometría")

    def asignaciones(self, items, secciones, objetivos, tipo, fuentes):
        tabla = self.registros(items, "objetivo seccion fuente", "asignaciones." + tipo, "objetivo")
        for ident, item in tabla.items():
            if objetivos is not None:
                self.referencia(ident, objetivos, "asignacion.objetivo")
            if self.referencia(item["seccion"], secciones, "asignacion.seccion") and secciones[item["seccion"]]["tipo"] != tipo:
                self.error("asignaciones", "tipo de sección incompatible")
            self.referencia(item["fuente"], fuentes, "asignacion.fuente")
        return set(tabla)

    def factores(self, items, tabla, llave, ruta, positivos=False):
        registros = self.registros(items, llave + " factor", ruta, llave)
        for ident, item in registros.items():
            self.referencia(ident, tabla, ruta + "." + llave)
            self.numero(item["factor"], f"{ruta}.{ident}.factor", 0 if positivos else None)
        return registros

    def revision(self, valor):
        if not self.objeto(valor, "estado aprobacion", "$.revision"):
            return
        if not self.opcion(valor["estado"], ("borrador", "aprobado"), "revision.estado"):
            return
        try:
            self.r.huella_contenido = huella_configuracion(self.data)
        except (ValueError, TypeError, OverflowError, UnicodeError, RecursionError):
            self.error("$", "configuración no serializable como JSON estricto")
        aprobacion = valor["aprobacion"]
        if valor["estado"] == "borrador":
            if aprobacion is not None:
                self.error("$.revision", "borrador debe tener aprobación null")
            return
        if not self.objeto(aprobacion, "revisor_declarado fecha huella_configuracion alcance identidad_revisor", "$.revision.aprobacion"):
            return
        antes = len(self.r.errores)
        for clave in ("revisor_declarado", "alcance"):
            self.texto(aprobacion[clave], "aprobacion." + clave)
        try:
            if not isinstance(aprobacion["fecha"], str) or len(aprobacion["fecha"]) != 10:
                raise ValueError()
            date.fromisoformat(aprobacion["fecha"])
        except (TypeError, ValueError):
            self.error("$.revision.aprobacion.fecha", "fecha ISO inválida")
        if aprobacion["identidad_revisor"] != "declarada_no_verificada":
            self.error("$.revision.aprobacion", "identidad debe ser declarada_no_verificada")
        if self.r.huella_contenido is None or aprobacion["huella_configuracion"] != self.r.huella_contenido:
            self.error("$.revision.aprobacion", "huella de configuración no vigente")
        self.r.aprobacion_configuracion_vigente = len(self.r.errores) == antes


class _ValidadorSuperficies(_Validador):
    """Configuración 0.2: superficies planas XYZ sobre geometría 0.2. Nunca apta para el adaptador."""

    version = VERSION_SUPERFICIES
    version_geometria = VERSION_GEOMETRIA_SUPERFICIES
    bloqueo_geometria = BLOQUEO_INTEGRACION
    bloqueo_configuracion = BLOQUEO_SUPERFICIES
    claves_raiz = _Validador.claves_raiz + " asignaciones_superficies vertices_compartidos"
    tipos_seccion = ("shell_muro", "frame_rectangular", "shell_losa_homogenea") + TIPOS_ALIGERADOS
    tipos_espesor = ("shell_muro", "shell_losa_homogenea")
    objetivos_carga = ("punto", "frame", "muro", "superficie")
    objetivos_geometricos = ("muro", "superficie")
    unidades_carga = {"punto": "kN", "frame": "kN/m", "muro": "kN/m2", "superficie": "kN/m2"}

    def __init__(self, data):
        super().__init__(data)
        self.r.version_contrato = self.version

    def secciones_extra(self, secciones, materiales):
        # La sección de prueba es una placa homogénea isótropa lineal; no equivale a una losa aligerada.
        for ident, item in secciones.items():
            if item["tipo"] == "shell_losa_homogenea" and isinstance(item["material"], str) and item["material"] in materiales:
                if materiales[item["material"]]["tipo"] != "isotropo_lineal":
                    self.error(f"$.secciones.{ident}.material", "material incompatible con shell_losa_homogenea")

            if item["tipo"] in TIPOS_ALIGERADOS and isinstance(item["dimensiones"], dict):
                q = item["dimensiones"]
                if set(q) != set(DIM_ALIGERADOS[item["tipo"]].split()):
                    continue
                if not _finitos_dimensiones(q):
                    continue
                if q["capa_m"] >= q["alto_total_m"]:
                    self.error("seccion.dimensiones", "la capa debe ser menor que el alto total")
                separaciones = [q[k] for k in q if k.startswith("separacion")]
                if any(max(q["ancho_nervio_superior_m"], q["ancho_nervio_inferior_m"]) >= e for e in separaciones):
                    self.error("seccion.dimensiones", "el nervio debe ser menor que cada separación")
                if "direccion_nervios" in q and (type(q["direccion_nervios"]) is not int or q["direccion_nervios"] not in (1, 2)):
                    self.error("seccion.dimensiones", "dirección de nervios: entero 1 o 2")

    def asignaciones(self, items, secciones, objetivos, tipo, fuentes):
        if tipo != "shell_losa_homogenea":
            return super().asignaciones(items, secciones, objetivos, tipo, fuentes)
        tabla = self.registros(items, "objetivo seccion fuente", "asignaciones.superficies", "objetivo")
        for ident, item in tabla.items():
            if objetivos is not None:
                self.referencia(ident, objetivos, "asignacion.objetivo")
            if self.referencia(item["seccion"], secciones, "asignacion.seccion"):
                if secciones[item["seccion"]]["tipo"] not in ("shell_losa_homogenea",) + TIPOS_ALIGERADOS:
                    self.error("asignaciones", "tipo de sección incompatible")
            self.referencia(item["fuente"], fuentes, "asignacion.fuente")
        return set(tabla)

    def incorporar_aberturas(self, vg, punto_de_vertice, usados, ctx):
        pass

    def masa_extra(self, masa):
        if masa["metodo"] == "explicita":
            self.error("$.masa.metodo", "masa puntual escalar no habilitada: el contrato no declara sus grados de libertad")

    def tabla_carga(self, ctx, tipo):
        tablas = {"punto": ctx["puntos"], "frame": ctx["frames"], "muro": ctx["muros_geo"], "superficie": ctx["superficies"]}
        return tablas.get(tipo, {}) if isinstance(tipo, str) else {}

    def coplanaridad(self, ctx, miembros, geometria):
        if len(miembros) < 2:
            self.error("$.diafragmas", "un diafragma requiere al menos dos puntos; uno solo no restringe nada")
        if geometria is not None and ctx["coordenadas"]:
            cotas = {ctx["coordenadas"][ident][2] for ident in miembros if ident in ctx["coordenadas"]}
            if len(cotas) > 1:
                self.error("$.diafragmas", "los puntos de un diafragma deben ser coplanares en cota")

    def conectividad(self, ctx, apoyos):
        """Cada grupo de puntos unidos por frames, muros o superficies debe llegar a un apoyo declarado."""
        if not ctx["grupos"]:
            return
        padre = {p: p for p in ctx["puntos"]}

        def raiz(p):
            while padre[p] != p:
                padre[p] = padre[padre[p]]
                p = padre[p]
            return p
        for grupo in ctx["grupos"]:
            miembros = [p for p in grupo if p in padre]
            for p in miembros[1:]:
                padre[raiz(p)] = raiz(miembros[0])
        componentes = {}
        for p in padre:
            componentes.setdefault(raiz(p), []).append(p)
        for miembros in componentes.values():
            if not set(miembros) & set(apoyos):
                self.error("$.apoyos", "conexión ausente: grupo sin apoyo declarado: " + ", ".join(sorted(miembros)[:6]))

    def objetos(self, geometria, fuentes, secciones):
        d, r = self.data, self.r
        ctx = {"puntos": {}, "frames": {}, "muros_geo": {}, "superficies": {}, "niveles": {}, "coordenadas": {}, "grupos": []}
        puntos, pares, por_vertice = ctx["puntos"], {}, {}
        for indice, item in enumerate(self.lista(d["puntos"], "$.puntos")):
            pos = f"$.puntos[{indice}]"
            if not isinstance(item, dict) or set(item) not in (CAMPOS_PUNTO_NODO, CAMPOS_PUNTO_VERTICE):
                self.error(pos, "campos exactos de una alternativa: id nodo_geometria nivel_geometria | id vertice_geometria")
                continue
            if not self.patron(item["id"], PATRON_ID, pos + ".id"):
                continue
            if item["id"] in puntos:
                self.error(pos, "identificador repetido")
            puntos[item["id"]] = item
            if "vertice_geometria" in item:
                if self.patron(item["vertice_geometria"], PATRON_ID, "punto.vertice"):
                    if item["vertice_geometria"] in por_vertice:
                        self.error("$.puntos", "dos puntos modelan el mismo vértice")
                    por_vertice[item["vertice_geometria"]] = item["id"]
            elif self.patron(item["nodo_geometria"], PATRON_ID, "punto.nodo") and self.patron(item["nivel_geometria"], PATRON_ID, "punto.nivel"):
                if (item["nodo_geometria"], item["nivel_geometria"]) in pares:
                    self.error("$.puntos", "dos puntos modelan el mismo nodo/nivel")
                pares[item["nodo_geometria"], item["nivel_geometria"]] = item["id"]
        compartidos = self.registros(d["vertices_compartidos"], "vertice_geometria punto fuente", "$.vertices_compartidos",
                                     "vertice_geometria")
        for vertice, item in compartidos.items():
            if self.referencia(item["punto"], puntos, "vertice_compartido.punto") and "vertice_geometria" in puntos[item["punto"]]:
                self.error("$.vertices_compartidos", "solo un punto nodo+nivel puede representar otro vértice")
            if vertice in por_vertice:
                self.error("$.vertices_compartidos", "el vértice ya tiene un punto propio: " + vertice)
            self.referencia(item["fuente"], fuentes, "vertice_compartido.fuente")
        frames = ctx["frames"] = self.registros(d["frames"], "id inicio fin tipo fuente", "$.frames")
        usados = set()
        conexiones_frame = set()
        for item in frames.values():
            for clave in ("inicio", "fin"):
                if self.referencia(item[clave], puntos, "frame." + clave):
                    usados.add(item[clave])
            if item["inicio"] == item["fin"]:
                self.error("$.frames", "extremos del frame deben ser distintos")
            if isinstance(item["inicio"], str) and isinstance(item["fin"], str):
                conexion = tuple(sorted((item["inicio"], item["fin"])))
                if conexion in conexiones_frame:
                    self.error("$.frames", "dos frames repiten la misma conexión")
                conexiones_frame.add(conexion)
                ctx["grupos"].append([item["inicio"], item["fin"]])
            self.opcion(item["tipo"], ("viga", "columna", "otro"), "frame.tipo")
            self.referencia(item["fuente"], fuentes, "frame.fuente")
        superficies_geo, derivados = {}, {}
        if geometria is not None:
            if not isinstance(geometria, dict) or geometria.get("version_contrato") != self.version_geometria:
                self.error("geometria", f"la configuración {self.version[:3]} exige una geometría {self.version_geometria}; no se reinterpreta otra versión")
                vg = None
            else:
                vg = validar_geometria(geometria)
                if not vg.consistente:
                    self.error("geometria", "contrato geométrico inconsistente")
                    vg = None
            if vg is not None:
                origen = d["geometria_origen"]
                if geometria["id"] != d["caso"] or vg.datos_sinteticos is not d["datos_sinteticos"]:
                    self.error("geometria", "caso o marca sintética no corresponden")
                if isinstance(origen, dict) and origen.get("huella_contenido") != vg.huella_contenido:
                    self.error("geometria", "huella de contenido no corresponde")
                niveles = ctx["niveles"] = {x["id"]: x["cota"] for x in vg.geometria_m["niveles"]}
                nodos = {x["id"]: x for x in vg.geometria_m["nodos"]}
                muros_geo = ctx["muros_geo"] = {x["id"]: x for x in vg.geometria_m["muros"]}
                vertices = {x["id"]: x for x in vg.geometria_m["vertices"]}
                superficies_geo = ctx["superficies"] = {x["id"]: x for x in vg.geometria_m["superficies"]}
                derivados = vg.derivados_m["superficies"]
                coords = ctx["coordenadas"]
                for ident, punto in puntos.items():
                    if "vertice_geometria" in punto:
                        if self.referencia(punto["vertice_geometria"], vertices, "punto.vertice_geometria"):
                            v = vertices[punto["vertice_geometria"]]
                            coords[ident] = (v["x"], v["y"], v["z"])  # metros desde geometria_m, nunca píxeles
                    else:
                        ok_nodo = self.referencia(punto["nodo_geometria"], nodos, "punto.nodo_geometria")
                        ok_nivel = self.referencia(punto["nivel_geometria"], niveles, "punto.nivel_geometria")
                        if ok_nodo and ok_nivel:
                            n = nodos[punto["nodo_geometria"]]
                            coords[ident] = (n["x"], n["y"], niveles[punto["nivel_geometria"]])
                punto_de_vertice = dict(por_vertice)
                for vertice, item in compartidos.items():
                    if (self.referencia(vertice, vertices, "vertice_compartido.vertice") and isinstance(item["punto"], str)
                            and item["punto"] in coords):
                        v = vertices[vertice]
                        if (v["x"], v["y"], v["z"]) != coords[item["punto"]]:
                            self.error("$.vertices_compartidos", "coordenadas del vértice " + vertice
                                       + " difieren del punto " + item["punto"] + "; no se fusionan por proximidad")
                        else:
                            punto_de_vertice[vertice] = item["punto"]
                for muro in muros_geo.values():
                    esquinas = []
                    for nodo in (muro["nodo_inicio"], muro["nodo_fin"]):
                        for nivel in (muro["nivel_inferior"], muro["nivel_superior"]):
                            if (nodo, nivel) not in pares:
                                self.error("$.puntos", "falta esquina de muro: " + nodo + "/" + nivel)
                            else:
                                usados.add(pares[nodo, nivel])
                                esquinas.append(pares[nodo, nivel])
                    ctx["grupos"].append(esquinas)
                for sid, superficie in superficies_geo.items():
                    contorno = []
                    for vertice in superficie["vertices"]:
                        pid = punto_de_vertice.get(vertice)
                        if pid is None:
                            self.error("$.puntos", f"superficie {sid}: vértice {vertice} sin punto ni vértice compartido")
                        else:
                            usados.add(pid)
                            contorno.append(pid)
                    ctx["grupos"].append(contorno)
                self.incorporar_aberturas(vg, punto_de_vertice, usados, ctx)
                for frame in frames.values():
                    a, b = frame["inicio"], frame["fin"]
                    if isinstance(a, str) and isinstance(b, str) and a in coords and b in coords:
                        self.frame_fisico(frame, coords[a], coords[b])
                for ident in sorted(puntos.keys() - usados):
                    self.error("$.puntos", "punto sin conexión a muro, frame o superficie: " + ident)
                vistos = {}
                for ident in sorted(coords):
                    if coords[ident] in vistos:
                        self.error("$.puntos", f"puntos coincidentes {vistos[coords[ident]]} y {ident}: no se fusionan "
                                               "en silencio; declare un único punto y vertices_compartidos")
                    vistos.setdefault(coords[ident], ident)
                # Aprobación geométrica por huella, distinta de la disponibilidad bloqueada para el adaptador.
                r.geometria_aprobada_por_huella = vg.aprobacion_geometrica_vigente and set(vg.bloqueos) == {self.bloqueo_geometria}
                if not r.geometria_aprobada_por_huella:
                    r.bloqueos.append("Geometría sin aprobación vigente o con faltantes.")
                r.bloqueos.extend(b for b in vg.bloqueos if b == self.bloqueo_geometria)
        else:
            r.bloqueos.append("Falta comprobar la geometría versionada y su cobertura.")
        self.asignaciones_muros_frames(geometria, secciones, fuentes, ctx["muros_geo"], frames)
        asignadas = self.asignaciones(d["asignaciones_superficies"], secciones, superficies_geo if geometria is not None else None,
                                      "shell_losa_homogenea", fuentes)
        if geometria is not None and asignadas != set(superficies_geo):
            self.error("$.asignaciones_superficies", "cobertura de superficies incompleta: cada superficie requiere sección")
        for sid in sorted(asignadas & set(derivados)):
            derivado = derivados[sid]
            if self.version == VERSION_SUPERFICIES and abs(derivado["normal_unitaria"][2]) <= derivado["epsilon_relativo_computacional"]:
                self.error("$.asignaciones_superficies", f"superficie {sid} vertical: shell_losa_homogenea no se aplica a "
                                                         "planos verticales; use muros o un incremento revisado")
        for asignacion in d["asignaciones_superficies"]:
            if not isinstance(asignacion, dict):
                continue
            if not isinstance(asignacion.get("seccion"), str) or not isinstance(asignacion.get("objetivo"), str):
                continue
            sec = secciones.get(asignacion["seccion"])
            derivado = derivados.get(asignacion["objetivo"])
            if not sec or not derivado or sec["tipo"] not in TIPOS_ALIGERADOS:
                continue
            q = sec["dimensiones"]
            if not isinstance(q, dict) or set(q) != set(DIM_ALIGERADOS[sec["tipo"]].split()):
                continue
            if not _finitos_dimensiones(q):
                continue
            if abs(abs(derivado["normal_unitaria"][2]) - 1) > derivado["epsilon_relativo_computacional"]:
                self.error("asignaciones.superficies", "aligerado v1 requiere contorno horizontal; inclinados necesitan representación revisada")
            if derivado["normal_unitaria"][2] < 0:
                self.error("asignaciones.superficies", "aligerado v1 requiere normal +Z explícita; no invierte el contorno automáticamente")
            theta = math.radians(q["angulo_ejes_locales_grados"])
            xy = derivado["vertices_m"]
            proyecciones = [[v[0] * math.cos(theta) + v[1] * math.sin(theta) for v in xy],
                            [-v[0] * math.sin(theta) + v[1] * math.cos(theta) for v in xy]]
            luces = [max(a) - min(a) for a in proyecciones]
            pasos = [(2 - q["direccion_nervios"], q["separacion_m"])] if sec["tipo"] == TIPOS_ALIGERADOS[0] and q["direccion_nervios"] in (1, 2) else [(0, q.get("separacion_1_m", 0)), (1, q.get("separacion_2_m", 0))]
            if any(paso > luces[eje] for eje, paso in pasos) or q["alto_total_m"] >= min(luces):
                self.error("asignaciones.superficies", "dimensiones de aligerado incompatibles con extensión del contorno")
        if self.bloqueo_configuracion:  # 0.4 completa no añade bloqueo propio
            r.bloqueos.append(self.bloqueo_configuracion)
        return ctx


class _ValidadorAberturas(_ValidadorSuperficies):
    version = VERSION_ABERTURAS
    version_geometria = VERSION_GEOMETRIA_ABERTURAS
    bloqueo_geometria = BLOQUEO_GEOMETRIA_ABERTURAS
    bloqueo_configuracion = BLOQUEO_ABERTURAS

    def incorporar_aberturas(self, vg, punto_de_vertice, usados, ctx):
        superficies = {s["id"]: s for s in vg.geometria_m["superficies"]}
        ctx["aberturas"] = {a["id"]: a for a in vg.geometria_m["aberturas"]}
        for ident, abertura in ctx["aberturas"].items():
            contorno = []
            for vertice in abertura["vertices"]:
                pid = punto_de_vertice.get(vertice)
                if pid is None:
                    self.error("$.puntos", f"abertura {ident}: vértice {vertice} sin punto explícito")
                else:
                    usados.add(pid)
                    contorno.append(pid)
            # Enlace lógico de pertenencia a host, nunca barra/constraint inferido.
            ctx["grupos"].append(contorno + [punto_de_vertice[v] for v in superficies[abertura["superficie"]]["vertices"] if v in punto_de_vertice])

    def asignaciones(self, items, secciones, objetivos, tipo, fuentes):
        if tipo != "shell_losa_homogenea":
            return super().asignaciones(items, secciones, objetivos, tipo, fuentes)
        tabla = self.registros(items, "objetivo seccion fuente", "asignaciones.superficies", "objetivo")
        for ident, item in tabla.items():
            if objetivos is not None:
                self.referencia(ident, objetivos, "asignacion.objetivo")
            if self.referencia(item["seccion"], secciones, "asignacion.seccion") and secciones[item["seccion"]]["tipo"] not in ("shell_muro", "shell_losa_homogenea") + TIPOS_ALIGERADOS:
                self.error("asignaciones", "tipo de sección incompatible")
            self.referencia(item["fuente"], fuentes, "asignacion.fuente")
        return set(tabla)

    def objetos(self, geometria, fuentes, secciones):
        ctx = super().objetos(geometria, fuentes, secciones)
        if isinstance(geometria, dict) and geometria.get("version_contrato") == VERSION_GEOMETRIA_ABERTURAS:
            vg = validar_geometria(geometria)
            if vg.consistente:
                for a in self.data["asignaciones_superficies"]:
                    if not isinstance(a, dict) or not isinstance(a.get("seccion"), str) or not isinstance(a.get("objetivo"), str):
                        continue
                    sec = secciones.get(a["seccion"]); derivado = vg.derivados_m["superficies"].get(a["objetivo"])
                    if sec and derivado:
                        vertical = abs(derivado["normal_unitaria"][2]) <= derivado["epsilon_relativo_computacional"]
                        if vertical != (sec["tipo"] == "shell_muro"):
                            self.error("asignaciones.superficies", "host vertical requiere shell_muro; los otros hosts requieren sección de losa explícita")
        return ctx


class _ValidadorMalla(_ValidadorAberturas):
    """Configuración 0.4: hosts 0.3 completos (con huecos) mallados por partición+compatibilidad+triangulación.

    La malla se REPRODUCE desde la geometría y `conexiones_borde`; la configuración solo declara la política de los
    nodos derivados y la subdivisión de frames. Lo no declarado es faltante calculado (borrador importable,
    aprobación bloqueada); lo declarado que no corresponde es error. Nunca crea el host completo ni Opening.
    """

    version = VERSION_MALLA
    bloqueo_configuracion = None
    claves_raiz = _ValidadorAberturas.claves_raiz + " conexiones_borde malla cortes_nivel nodos_derivados subdivision_frames"
    objetivos_carga = ("punto", "frame", "superficie")
    objetivos_geometricos = ("superficie",)

    def objetos(self, geometria, fuentes, secciones):
        ctx = super().objetos(geometria, fuentes, secciones)
        d = self.data
        self.ctx, self.preparacion = ctx, None
        if self.lista(d["asignaciones_muros"], "$.asignaciones_muros") or ctx["muros_geo"]:
            self.error("$.asignaciones_muros", "la configuración 0.4 representa los muros como superficies verticales; muros 0.1 no admitidos")
        malla = d["malla"]
        if self.objeto(malla, "estrategia fuente", "$.malla"):
            self.opcion(malla["estrategia"], (mp.ESTRATEGIA,), "malla.estrategia")
            self.referencia(malla["fuente"], fuentes, "malla.fuente")
        # Cortes Z explícitos (adenda 186): declaración revisada con fuente y motivo; no son pisos ni se infieren.
        vistos_z = set()
        for i, corte in enumerate(self.lista(d["cortes_nivel"], "$.cortes_nivel")):
            if self.objeto(corte, "z_m fuente motivo", f"$.cortes_nivel[{i}]"):
                if self.numero(corte["z_m"], f"$.cortes_nivel[{i}].z_m"):
                    if corte["z_m"] in vistos_z:
                        self.error("$.cortes_nivel", "nivel de corte repetido")
                    vistos_z.add(corte["z_m"])
                self.referencia(corte["fuente"], fuentes, "corte_nivel.fuente")
                self.texto(corte["motivo"], "corte_nivel.motivo")
        if not isinstance(d["conexiones_borde"], dict):
            self.error("$.conexiones_borde", "se requiere el documento draft2model.conexiones_borde embebido")
        if geometria is None:
            return ctx
        if self.r.errores:
            self.error("$.malla", "malla no preparada: corrija antes los errores de la configuración")
            return ctx
        try:
            from . import reuso_preparacion as rp
            try:
                entradas_preparacion = rp.huellas(geometria, d)
                self.preparacion = mp.preparar_malla(geometria, d)
                self.r._preparacion_malla_reutilizable = rp.sellar(geometria, d, self.preparacion, entradas_preparacion)
            except (ValueError, TypeError) as error:
                raise mp.ErrorMalla(str(error)) from error
        except mp.ErrorMalla as exc:
            self.error("$.malla", str(exc))
        return ctx

    def validar(self, geometria):
        r = super().validar(geometria)
        if not isinstance(self.data, dict) or set(self.data) != set(self.claves_raiz.split()):
            return r
        antes_err, antes_falt = len(r.errores), len(r.faltantes)
        self.politica_malla(getattr(self, "ctx", None), getattr(self, "preparacion", None))
        if len(r.errores) > antes_err and "Configuración inconsistente." not in r.bloqueos:
            r.bloqueos.insert(0, "Configuración inconsistente.")
        if len(r.faltantes) > antes_falt:
            r.bloqueos.append("Malla con política de nodos derivados o subdivisión de frames pendiente.")
        return r

    def politica_malla(self, ctx, prep):
        d = self.data
        fuentes = {f["id"] for f in d["fuentes"] if isinstance(f, dict) and isinstance(f.get("id"), str)} if isinstance(d["fuentes"], list) else set()
        diafragmas = {x["id"]: x for x in d["diafragmas"] if isinstance(x, dict) and isinstance(x.get("id"), str)} if isinstance(d["diafragmas"], list) else {}
        nodos = self.registros(d["nodos_derivados"], "nodo xyz_m restricciones diafragma motivo_sin_diafragma fuente", "$.nodos_derivados", "nodo")
        subdiv = self.registros(d["subdivision_frames"], "frame nodos fuente", "$.subdivision_frames", "frame")
        for ident, item in nodos.items():
            restr = item["restricciones"]
            if not isinstance(restr, list) or len(restr) != 6 or any(type(x) is not bool for x in restr):
                self.error(f"$.nodos_derivados.{ident}", "restricciones: seis booleanos Ux,Uy,Uz,Rx,Ry,Rz explícitos")
            if (item["diafragma"] is None) == (item["motivo_sin_diafragma"] is None):
                self.error(f"$.nodos_derivados.{ident}", "declare exactamente un diafragma o un motivo sin diafragma (conflicto u omisión)")
            elif item["diafragma"] is not None:
                self.referencia(item["diafragma"], diafragmas, "nodo_derivado.diafragma")
            else:
                self.texto(item["motivo_sin_diafragma"], "nodo_derivado.motivo_sin_diafragma")
            self.referencia(item["fuente"], fuentes, "nodo_derivado.fuente")
        for ident, item in subdiv.items():
            self.referencia(item["fuente"], fuentes, "subdivision_frame.fuente")
        if prep is None:
            return
        derivados = set(prep["nodos_derivados"])
        for ident in sorted(nodos.keys() - derivados):
            self.error("$.nodos_derivados", f"{ident} no es un nodo derivado de la malla reproducida")
        for ident in sorted(derivados - nodos.keys()):
            self.r.faltantes.append({"ruta": f"$.nodos_derivados.{ident}", "motivo": "política de apoyo y diafragma del nodo derivado sin declarar", "fuente": None})
        xyz = {n["csi"]: n["xyz_m"] for n in prep["nodos"]}
        for ident in sorted(nodos.keys() & derivados):
            # La política se liga a la posición reproducida: un nombre reutilizado en otra posición no la hereda.
            if nodos[ident]["xyz_m"] != xyz[ident]:
                self.error(f"$.nodos_derivados.{ident}", f"xyz_m declarado distinto del reproducido {xyz[ident]}; revise la política")
        coords = ctx["coordenadas"] if ctx else {}
        for did, diafragma in diafragmas.items():
            cotas = {coords[p][2] for p in diafragma.get("puntos", []) if isinstance(p, str) and p in coords}
            cotas |= {xyz[i][2] for i, item in nodos.items() if item["diafragma"] == did and i in xyz}
            if len(cotas) > 1:
                self.error("$.diafragmas", f"diafragma {did}: nodos derivados fuera de la cota de sus puntos")
        requeridas = {x["frame"]: x for x in prep["frames_subdivision_requerida"]}
        for ident in sorted(subdiv.keys() - requeridas.keys()):
            self.error("$.subdivision_frames", f"frame {ident} sin nodos de malla interiores: subdivisión no admitida")
        for ident in sorted(requeridas.keys() - subdiv.keys()):
            self.r.faltantes.append({"ruta": f"$.subdivision_frames.{ident}", "motivo": "frame atraviesa nodos de malla: subdivisión conforme sin declarar", "fuente": None})
        for ident in sorted(subdiv.keys() & requeridas.keys()):
            if subdiv[ident]["nodos"] != requeridas[ident]["nodos"]:
                self.error("$.subdivision_frames", f"frame {ident}: nodos declarados distintos de los reproducidos {requeridas[ident]['nodos']}")
        self.r.preparacion_malla = {"huella_preparacion": prep["huella_preparacion"], "nodos_derivados": len(derivados),
                                    "triangulos": len(prep["triangulos"]), "frames_subdivididos": len(requeridas),
                                    "huella_triangulacion": prep["origen"]["huella_triangulacion"]}


class _ValidadorLiquidos(_ValidadorMalla):
    """Configuración 0.5: malla 0.4 + `liquidos` con aplicabilidad EXPLÍCITA.

    - ausente_confirmado: sin declaraciones; el proyecto funciona sin módulo de agua ni cargas cero ficticias.
    - informacion_insuficiente: faltante calculado (la falta de documentación no equivale a ausencia).
    - presente: declaraciones `acciones_liquidos` revisadas, cada una con patrón dedicado sin peso propio ni otras
      cargas, sin compartir patrón ni superficie con otra declaración, y con corte explícito en cada nivel libre
      interior a una superficie cargada (ensayos 185/186).
    """

    version = VERSION_LIQUIDOS
    claves_raiz = _ValidadorMalla.claves_raiz + " liquidos"
    tipos_seccion = _ValidadorMalla.tipos_seccion + (SECCION_L,)

    def __init__(self, data):
        super().__init__(data)
        # `insercion_frames` es opcional: sin la clave, las configuraciones 0.5 existentes no cambian (ni su huella).
        if isinstance(data, dict) and "insercion_frames" in data:
            self.claves_raiz = type(self).claves_raiz + " insercion_frames"

    def secciones_extra(self, secciones, materiales):
        super().secciones_extra(secciones, materiales)
        for ident, item in secciones.items():
            q = item["dimensiones"]
            if item["tipo"] != SECCION_L or not isinstance(q, dict) or set(q) != set(DIM_L.split()):
                continue
            longitudes = {k: q[k] for k in ("alto_m", "ancho_m", "espesor_ala_m", "espesor_alma_m")}
            if not _finitos_dimensiones(longitudes):
                continue
            if q["espesor_ala_m"] >= q["alto_m"] or q["espesor_alma_m"] >= q["ancho_m"]:
                self.error(f"$.secciones.{ident}.dimensiones", "L: cada espesor debe ser menor que la dimensión exterior que lo contiene")

    def asignaciones(self, items, secciones, objetivos, tipo, fuentes):
        if tipo != "frame_rectangular":
            return super().asignaciones(items, secciones, objetivos, tipo, fuentes)
        tabla = self.registros(items, "objetivo seccion fuente", "asignaciones." + tipo, "objetivo")
        for ident, item in tabla.items():
            if objetivos is not None:
                self.referencia(ident, objetivos, "asignacion.objetivo")
            if self.referencia(item["seccion"], secciones, "asignacion.seccion") and secciones[item["seccion"]]["tipo"] not in TIPOS_FRAME:
                self.error("asignaciones", "tipo de sección incompatible")
            self.referencia(item["fuente"], fuentes, "asignacion.fuente")
        return set(tabla)

    def insercion_frames(self, ctx, fuentes):
        d = self.data
        if not isinstance(d, dict) or "insercion_frames" not in d:
            return
        registros = self.registros(d["insercion_frames"], "frame punto_cardinal desplazamiento_global_m transformar_rigidez fuente",
                                   "$.insercion_frames", "frame")
        if not registros:
            self.error("$.insercion_frames", "lista vacía: omita la clave si no hay inserciones")
        for ident, item in registros.items():
            ruta = f"$.insercion_frames.{ident}"
            self.referencia(ident, ctx["frames"], ruta + ".frame")
            if type(item["punto_cardinal"]) is not int or item["punto_cardinal"] not in CARDINALES_INSERCION:
                self.error(ruta + ".punto_cardinal", "solo 10 (centroide), la combinación ensayada en ETABS")
            vector = self.lista(item["desplazamiento_global_m"], ruta + ".desplazamiento_global_m")
            if len(vector) != 3:
                self.error(ruta + ".desplazamiento_global_m", "se requieren tres componentes globales X, Y, Z")
            for j, valor in enumerate(vector):
                self.numero(valor, f"{ruta}.desplazamiento_global_m[{j}]")
            if item["transformar_rigidez"] is not True:
                self.error(ruta + ".transformar_rigidez", "solo true (desplazamiento rígido transformado a los nudos), lo ensayado")
            self.referencia(item["fuente"], fuentes, ruta + ".fuente")

    def objetos(self, geometria, fuentes, secciones):
        self.geometria_liquidos = geometria
        ctx = super().objetos(geometria, fuentes, secciones)
        self.insercion_frames(ctx, fuentes)
        return ctx

    def politica_malla(self, ctx, prep):
        super().politica_malla(ctx, prep)
        self.liquidos(prep)

    def contenido(self, liq, prep):
        """liquidos.contenido (opcional): un estado de llenado explícito por depósito y una sola representación de su masa.

        lleno/vacio: ligado a una declaración de líquido; con malla, masa_contenido exige Fz = −γV de los hosts regenerados,
        patrón sin peso propio y factor exactamente 1 en la fuente de masa. desconocido: faltante que bloquea (no se asume
        vacío ni lleno). ausente_confirmado: sin declaración ni masa. No crea cargas ni aprueba ingeniería.
        """
        d = self.data
        fuentes = {f["id"] for f in d["fuentes"] if isinstance(f, dict) and isinstance(f.get("id"), str)} if isinstance(d["fuentes"], list) else set()
        items = self.lista(liq["contenido"], "$.liquidos.contenido")
        if not items:
            self.error("$.liquidos.contenido", "lista vacía: omita la clave si no declara contenido")
        decl_ids = {}
        for item in liq["declaraciones"] if isinstance(liq["declaraciones"], list) else []:
            if isinstance(item, dict) and isinstance(item.get("declaracion"), dict) and isinstance(item["declaracion"].get("id"), str):
                decl_ids[item["declaracion"]["id"]] = item
        depositos, cubiertas, escenarios, estados = set(), set(), [], {}
        errores_previos = len(self.r.errores)
        for i, it in enumerate(items):
            ruta = f"$.liquidos.contenido[{i}]"
            if not self.objeto(it, CAMPOS_CONTENIDO, ruta):
                continue
            if not self.texto(it["deposito"], ruta + ".deposito"):
                continue   # tipo inválido (lista, objeto, número...): error controlado antes de usarlo como clave
            if it["deposito"] in depositos:
                self.error(ruta + ".deposito", "depósito repetido: un único estado por depósito y evaluación")
            depositos.add(it["deposito"])
            self.referencia(it["fuente"], fuentes, ruta + ".fuente")
            self.texto(it["motivo"], ruta + ".motivo")
            if not self.opcion(it["estado"], ESTADOS_CONTENIDO, ruta + ".estado"):
                continue
            estados[it["deposito"]] = it["estado"]
            if it["estado"] in ("desconocido", "ausente_confirmado"):
                if any(it[k] is not None for k in ("declaracion", "modo", "patron_masa_exclusivo", "peso_vertical_referencia_kn", "volumen_m3")):
                    self.error(ruta, f"estado {it['estado']} no admite declaración, modo, patrones ni volumen")
                if it["estado"] == "desconocido":
                    self.r.faltantes.append({"ruta": ruta + ".estado", "fuente": it["fuente"],
                                             "motivo": f"estado de llenado de {it['deposito']} desconocido; no se asume vacío ni lleno"})
                continue
            if liq["aplicabilidad"] != "presente":
                self.error(ruta + ".estado", "lleno/vacio requieren aplicabilidad 'presente'")
                continue
            if not self.referencia(it["declaracion"], decl_ids, ruta + ".declaracion"):
                continue
            if it["declaracion"] in cubiertas:
                self.error(ruta + ".declaracion", "declaración contabilizada dos veces (peso estático doble)")
            cubiertas.add(it["declaracion"])
            self.opcion(it["modo"], ("patron_presion", "patron_masa_exclusivo"), ruta + ".modo")
            self.numero(it["volumen_m3"], ruta + ".volumen_m3", minimo=0)
            if it["estado"] == "vacio" and it["volumen_m3"] != 0:
                self.error(ruta + ".volumen_m3", "estado vacio exige volumen 0")
            item = decl_ids[it["declaracion"]]
            decl = item["declaracion"]
            escenarios.append({"deposito": it["deposito"], "estado": it["estado"], "fuente": it["fuente"], "declaracion": it["declaracion"],
                               "volumen_m3": it["volumen_m3"], "peso_especifico_kn_m3": decl.get("peso_especifico_kn_m3"),
                               "gravedad_m_s2": (d.get("masa") or {}).get("gravedad_m_s2"), "nivel_libre_z_m": decl.get("nivel_libre_z_m"),
                               "modo": it["modo"], "patron_presion": item.get("patron"), "patron_masa_exclusivo": it["patron_masa_exclusivo"],
                               "peso_vertical_referencia_kn": it["peso_vertical_referencia_kn"]})
        sin_estado = sorted(set(decl_ids) - cubiertas)
        if sin_estado:
            self.error("$.liquidos.contenido", "declaraciones de líquido sin estado de contenido: " + ", ".join(sin_estado))
        if len(self.r.errores) > errores_previos or prep is None or self.geometria_liquidos is None or not escenarios:
            return
        from . import liquidos_malla as lm
        from . import masa_contenido as mc
        try:
            liq_prep = lm.preparar_liquidos(self.geometria_liquidos, d, prep)
            inventario = mc.auditar(escenarios, masa=d["masa"], patrones=d["patrones"], hosts=liq_prep["hosts"], casos=d["casos"],
                                    combinaciones=d["combinaciones"])
        except (lm.ErrorCargaLiquido, mc.ErrorContabilidad) as exc:
            self.error("$.liquidos.contenido", "contabilidad del contenido no coherente con la malla/fuente de masa vigentes: " + str(exc))
            return
        self.r.contenido_masa = {**inventario, "huella_liquidos": liq_prep["huella_liquidos"], "estados": estados,
                                 "masa_nativa_verificada": False,
                                 "nota": "Inventario declarado y coherente con presiones y fuente de masa; la masa ensamblada en ETABS "
                                         "se acredita aparte (masa_ensamblada) tras el análisis."}

    def liquidos(self, prep):
        d = self.data
        liq = d["liquidos"]
        claves = "aplicabilidad fuente motivo declaraciones" + (" contenido" if isinstance(liq, dict) and "contenido" in liq else "")
        if not self.objeto(liq, claves, "$.liquidos"):
            return
        fuentes = {f["id"] for f in d["fuentes"] if isinstance(f, dict) and isinstance(f.get("id"), str)} if isinstance(d["fuentes"], list) else set()
        if not self.opcion(liq["aplicabilidad"], APLICABILIDAD_LIQUIDOS, "liquidos.aplicabilidad"):
            return
        self.referencia(liq["fuente"], fuentes, "liquidos.fuente")
        self.texto(liq["motivo"], "liquidos.motivo")
        declaraciones = self.lista(liq["declaraciones"], "$.liquidos.declaraciones")
        if "contenido" in liq and (liq["aplicabilidad"] != "presente" or not declaraciones):
            self.contenido(liq, None)
        if liq["aplicabilidad"] != "presente":
            if declaraciones:
                self.error("$.liquidos.declaraciones", "solo la aplicabilidad 'presente' admite declaraciones de líquido")
            if liq["aplicabilidad"] == "informacion_insuficiente":
                self.r.faltantes.append({"ruta": "$.liquidos.aplicabilidad", "fuente": None,
                                         "motivo": "existencia de cisterna/tanque sin información suficiente; no se trata como ausencia"})
            return
        if not declaraciones:
            self.error("$.liquidos.declaraciones", "aplicabilidad 'presente' requiere al menos una declaración revisada")
            return
        patrones = {p["id"]: p for p in d["patrones"] if isinstance(p, dict) and isinstance(p.get("id"), str)} if isinstance(d["patrones"], list) else {}
        usados_carga = {c.get("patron") for c in d["cargas"] if isinstance(c, dict)} if isinstance(d["cargas"], list) else set()
        vistos_patron, vistas_sup = set(), {}
        niveles = set((prep or {}).get("cortes_nivel") and prep["cortes_nivel"]["niveles_z_m"] or [])
        for i, item in enumerate(declaraciones):
            ruta = f"$.liquidos.declaraciones[{i}]"
            if not self.objeto(item, "declaracion fuentes patron", ruta):
                continue
            patron = item["patron"]
            if not self.referencia(patron, patrones, ruta + ".patron"):
                continue
            if patrones[patron].get("multiplicador_peso_propio") != 0:
                self.error(ruta + ".patron", "patrón de líquido con peso propio: duplicaría la masa/peso")
            if patron in usados_carga:
                self.error(ruta + ".patron", "patrón de líquido no dedicado: ya contiene otras cargas declaradas")
            if patron in vistos_patron:
                self.error(ruta + ".patron", "patrón repetido entre declaraciones de líquido")
            vistos_patron.add(patron)
            decl = item["declaracion"]
            for sup in [s.get("superficie") for s in decl.get("superficies", [])] if isinstance(decl, dict) and isinstance(decl.get("superficies"), list) else []:
                if sup in vistas_sup:
                    self.error(ruta, f"superficie {sup} cargada por dos declaraciones ({vistas_sup[sup]} y {i}); declare el conflicto explícitamente")
                vistas_sup[sup] = i
            if self.geometria_liquidos is None:
                continue
            try:
                from .acciones_liquidos import declarar_acciones_liquidos, ErrorAccionesLiquidos
                from .cargas_liquidos_etabs import preparar_cargas_no_uniformes, ErrorCargaLiquido
                declarada = declarar_acciones_liquidos(self.geometria_liquidos, decl, item["fuentes"])
                presion = preparar_cargas_no_uniformes(self.geometria_liquidos, declarada, item["fuentes"])
            except (ErrorAccionesLiquidos, ErrorCargaLiquido) as exc:
                self.error(ruta, "declaración de líquido no válida contra la geometría vigente: " + str(exc))
                continue
            if prep is not None:
                for host in presion["superficies"]:
                    if host["superficie"] not in prep["hosts"]:
                        self.error(ruta, f"superficie {host['superficie']} sin malla asignada")
                    for z in host["cortes_obligatorios_z_m"]:
                        if z not in niveles:
                            self.error(ruta, f"falta corte explícito en Z={z} m (nivel libre) para {host['superficie']}; sin corte la presión parcial es errónea (185)")
        if "contenido" in liq:
            self.contenido(liq, prep)


def _validador(data: Any) -> _Validador:
    """Despacho explícito por versión; cualquier otra versión sigue el validador 0.1 y se rechaza allí."""
    if isinstance(data, dict) and data.get("version_contrato") == VERSION_LIQUIDOS:
        return _ValidadorLiquidos(data)
    if isinstance(data, dict) and data.get("version_contrato") == VERSION_MALLA:
        return _ValidadorMalla(data)
    if isinstance(data, dict) and data.get("version_contrato") == VERSION_ABERTURAS:
        return _ValidadorAberturas(data)
    if isinstance(data, dict) and data.get("version_contrato") == VERSION_SUPERFICIES:
        return _ValidadorSuperficies(data)
    return _Validador(data)


def validar_configuracion(data: Any, geometria: Any = None) -> ResultadoModelo:
    """API pura. La geometría opcional permite cobertura; no acredita evidencia en disco."""
    resultado = _validador(data).validar(geometria)
    resultado.bloqueos.append("Falta comprobar la versión geométrica contra el expediente vigente.")
    return resultado


def comprobar_configuracion(raiz: Path, data: Any) -> ResultadoModelo:
    """Recomprueba geometría, originales y hashes; nunca ejecuta ETABS."""
    previo = validar_configuracion(data)
    if not isinstance(data, dict) or not isinstance(data.get("geometria_origen"), dict) or not isinstance(data.get("caso"), str):
        return previo
    try:
        consulta = gg.consultar_version(raiz, data["caso"], data["geometria_origen"].get("version_id"))
    except (ErrorGestion, OSError) as exc:
        previo.errores.append("Geometría versionada no comprobable: " + str(exc))
        return previo
    resultado = _validador(data).validar(consulta.geometria)
    resultado.comprobacion_geometria = consulta.comprobacion.a_dict()
    if not consulta.comprobacion.correcta:
        resultado.errores.extend(consulta.comprobacion.problemas)
        resultado.bloqueos.append("Evidencia geométrica alterada o incompleta.")
    for clave in ("sha256_geometria", "huella_contenido"):
        if data["geometria_origen"].get(clave) != getattr(consulta.comprobacion, clave):
            resultado.errores.append("geometria_origen." + clave + ": no corresponde a la versión guardada")
    resultado.geometria_comprobada = consulta.comprobacion.correcta and not resultado.errores
    resultado.apto_para_adaptador = (resultado.consistente and not resultado.faltantes and
                                    resultado.aprobacion_configuracion_vigente and resultado.geometria_comprobada and
                                    not resultado.bloqueos)
    if resultado.version_contrato in (VERSION_MALLA, VERSION_LIQUIDOS):
        # Habilitación operativa (no aprobación de ingeniería): datos completos y único bloqueo el informativo 0.3.
        resultado.apto_para_adaptador = (
            resultado.consistente and not resultado.faltantes and resultado.aprobacion_configuracion_vigente
            and resultado.geometria_comprobada and resultado.geometria_aprobada_por_huella
            and resultado.preparacion_malla is not None and set(resultado.bloqueos) <= {BLOQUEO_GEOMETRIA_ABERTURAS})
    if resultado.version_contrato in (VERSION_SUPERFICIES, VERSION_ABERTURAS):
        # Solo autoriza compilar un plan de desarrollo: los dos bloqueos de integración permanecen.
        resultado.apto_para_plan_desarrollo = (
            resultado.consistente and not resultado.faltantes and resultado.aprobacion_configuracion_vigente
            and resultado.geometria_comprobada and resultado.geometria_aprobada_por_huella
            and set(resultado.bloqueos) <= ({BLOQUEO_INTEGRACION, BLOQUEO_SUPERFICIES} if resultado.version_contrato == VERSION_SUPERFICIES else {BLOQUEO_GEOMETRIA_ABERTURAS, BLOQUEO_ABERTURAS}))
    return resultado


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--entrada", required=True, type=Path)
    parser.add_argument("--raiz", type=Path, help="Recomprueba la geometría registrada; omitir permite validar solo JSON")
    args = parser.parse_args(argv)
    try:
        data = cargar_configuracion(args.entrada)
        resultado = comprobar_configuracion(args.raiz, data) if args.raiz else validar_configuracion(data)
    except (ErrorGestion, OSError) as exc:
        print(json.dumps({"correcta": False, "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(resultado.a_dict(), ensure_ascii=False, allow_nan=False, indent=2))
    return 2 if not resultado.consistente else 0


if __name__ == "__main__":
    raise SystemExit(main())
