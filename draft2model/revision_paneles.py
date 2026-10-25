"""Paneles técnicos persistidos: versiones nuevas desde resultados vigentes, consulta y descarga comprobadas.

`ServicioPaneles(app)` genera con `panel_tecnico.crear_panel` un HTML autónomo a partir de una versión de
`resultados_estructurales` vigente (consultada con `app.resultados.consultar_resultado`) y, si se selecciona,
de un análisis aceptado `<caso>/analisis_etabs/<uuid32>` revalidado con `verificar_evidencia` contra ese
resultado exacto. Cada panel se publica en `<caso>/paneles/<uuid32>/` (panel.html + manifiesto.json) con un
único rename y nunca sobrescribe. Consultar y descargar vuelven a comprobar expediente, fuentes, manifiesto,
hash del HTML y el contenido incrustado frente a las fuentes vigentes.

No recalcula ni aprueba resultados: cálculo verificado (o sin vínculo de análisis), revisión de resultados
pendiente, conformidad normativa no evaluada y reglas pendientes. Las proyecciones no contienen rutas.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
from uuid import uuid4

from .evidencia_analisis import huella_evidencia, verificar_evidencia
from .gestion_extraccion import json_desde_bytes
from .panel_tecnico import crear_panel

CONTRATO = "draft2model.panel_persistido"
VERSION = "0.1.0"
GRUPO = "paneles"
ARCHIVO_HTML = "panel.html"
ARCHIVO_MANIFIESTO = "manifiesto.json"
MARCA_DATOS = '<script type="application/json" id="datos">'
CAMPOS_CREAR = {"caso", "resultado", "expediente_sha256", "analisis"}
CAMPOS_MANIFIESTO = {"contrato", "version", "id", "caso", "resultado", "analisis", "expediente_sha256",
                     "huella_resultados", "fuentes", "artefacto", "estados", "creado_utc",
                     "aprueba_resultados", "aprueba_ingenieria"}
CAMPOS_FUENTES = {"sha256_resultados", "geometria_id", "sha256_geometria", "huella_evidencia", "sha256_edb_analizado"}
REGLAS_PENDIENTES = "pendientes"
AVISO = ("Panel técnico persistido: instantánea de resultados vigentes. No revisa resultados, no evalúa "
         "conformidad normativa ni aprueba ingeniería.")


class ErrorPaneles(ValueError):
    """Error publicable sin rutas ni contenido privado."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _hex(valor, longitud: int) -> bool:
    return isinstance(valor, str) and re.fullmatch(f"[0-9a-f]{{{longitud}}}", valor) is not None


def _id(valor) -> str:
    if not _hex(valor, 32):
        raise ErrorPaneles("Identificador inválido; se esperan 32 hexadecimales en minúsculas.")
    return valor


def _sin_enlace(path: Path) -> Path:
    info = path.lstat()
    if (path.resolve() != path or stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)):
        raise ErrorPaneles("Directorio o archivo enlazado no permitido.")
    return path


def _datos_embebidos(html: bytes):
    """JSON de datos incrustado por crear_panel (los '<', '>' y '&' van escapados como \\u003c...)."""
    texto = html.decode("utf-8")
    if texto.count(MARCA_DATOS) != 1:
        raise ErrorPaneles("El panel no contiene un único bloque de datos.")
    bloque = texto.split(MARCA_DATOS, 1)[1].split("</script>", 1)[0]
    return json_desde_bytes(bloque.encode("utf-8"), ARCHIVO_HTML)


def _estados(evidencia) -> dict:
    return {"calculo": evidencia["estados"]["calculo"] if evidencia else "sin_vinculo_de_analisis",
            "revision_resultados": "pendiente", "conformidad_normativa": "no_evaluada", "reglas": REGLAS_PENDIENTES}


class ServicioPaneles:
    def __init__(self, app):
        self.app = app

    # -- comprobaciones de rutas y fuentes ----------------------------------------
    def _caso(self, caso, fingerprint) -> Path:
        if not _hex(fingerprint, 64):
            raise ErrorPaneles("Huella de expediente inválida.")
        folder, _, actual = self.app.expediente(caso)
        folder = Path(folder)
        if actual != fingerprint:
            raise ErrorPaneles("El expediente cambió; vuelve a consultarlo.")
        _sin_enlace(Path(self.app.raiz))
        _sin_enlace(folder)
        if folder.parent != Path(self.app.raiz) or not folder.is_dir():
            raise ErrorPaneles("Expediente inválido o ausente.")
        return folder

    @staticmethod
    def _grupo(folder: Path, nombre: str, crear: bool = False) -> Path:
        base = folder / nombre
        if os.path.lexists(base):
            _sin_enlace(base)
            if not base.is_dir():
                raise ErrorPaneles("Directorio de versiones inválido.")
        elif crear:
            base.mkdir()
        return base

    @staticmethod
    def _archivo(path: Path) -> Path:
        _sin_enlace(path)
        if not path.is_file():
            raise ErrorPaneles("Archivo de fuente ausente.")
        return path

    def _fuente(self, caso, resultado, fingerprint, analisis) -> dict:
        _id(resultado)
        if analisis is not None:
            _id(analisis)
        checked = self.app.resultados.consultar_resultado(caso, resultado, expediente_sha256=fingerprint)
        folder = self._caso(caso, fingerprint)
        datos = checked["datos"]
        resultados_path = self._archivo(self._grupo(folder, "resultados_estructurales") / resultado / "resultados.json")
        raw_resultados = resultados_path.read_bytes()
        if json_desde_bytes(raw_resultados, "resultados.json") != datos:
            raise ErrorPaneles("El archivo de resultados no coincide con la versión consultada.")
        geometria_id = _id(datos["geometria"]["id"])
        geometria_path = self._archivo(self._grupo(folder, "geometrias") / geometria_id / "geometria.json")
        if _sha(geometria_path.read_bytes()) != datos["geometria"]["sha256"]:
            raise ErrorPaneles("La geometría ya no coincide con el resultado.")
        evidencia = fuente = None
        if analisis is not None:
            corrida = self._grupo(folder, "analisis_etabs") / analisis
            _sin_enlace(corrida)
            if not corrida.is_dir():
                raise ErrorPaneles("Análisis ausente.")
            for hijo in corrida.iterdir():
                _sin_enlace(hijo)
            evidencia = verificar_evidencia(self.app.raiz, caso, resultado, corrida)
            fuente = {"raiz": self.app.raiz, "caso": caso, "resultado": resultado, "corrida": corrida}
        return {"checked": checked, "resultados_path": resultados_path, "geometria_path": geometria_path,
                "evidencia": evidencia, "fuente_evidencia": fuente,
                "fuentes": {"sha256_resultados": _sha(raw_resultados), "geometria_id": geometria_id,
                            "sha256_geometria": datos["geometria"]["sha256"],
                            "huella_evidencia": huella_evidencia(evidencia) if evidencia else None,
                            "sha256_edb_analizado": evidencia["analisis"]["sha256_edb_analizado"] if evidencia else None}}

    @staticmethod
    def _misma_fuente(a: dict, b: dict) -> bool:
        return a["checked"] == b["checked"] and a["fuentes"] == b["fuentes"] and a["evidencia"] == b["evidencia"]

    def _sin_rutas(self, html: bytes, folder: Path) -> None:
        texto = html.decode("utf-8")
        for ruta in {str(self.app.raiz), str(folder)}:
            if ruta in texto or json.dumps(ruta)[1:-1] in texto:
                raise ErrorPaneles("El panel contiene rutas locales; no se publica.")

    # -- validación del manifiesto -------------------------------------------------
    @staticmethod
    def _validar_manifiesto(meta, caso, version, fingerprint) -> dict:
        if not isinstance(meta, dict) or set(meta) != CAMPOS_MANIFIESTO:
            raise ErrorPaneles("Manifiesto de panel inválido.")
        fuentes, artefacto, estados = meta["fuentes"], meta["artefacto"], meta["estados"]
        if not isinstance(fuentes, dict) or set(fuentes) != CAMPOS_FUENTES:
            raise ErrorPaneles("Fuentes del manifiesto inválidas.")
        if not isinstance(artefacto, dict) or set(artefacto) != {ARCHIVO_HTML} or not _hex(artefacto[ARCHIVO_HTML], 64):
            raise ErrorPaneles("Artefacto del manifiesto inválido.")
        con_analisis = meta["analisis"] is not None
        if (meta["contrato"] != CONTRATO or meta["version"] != VERSION or meta["id"] != version or meta["caso"] != caso
                or meta["expediente_sha256"] != fingerprint or not _hex(meta["resultado"], 32)
                or not (meta["analisis"] is None or _hex(meta["analisis"], 32)) or not _hex(meta["huella_resultados"], 64)
                or not isinstance(meta["creado_utc"], str) or meta["aprueba_resultados"] is not False
                or meta["aprueba_ingenieria"] is not False):
            raise ErrorPaneles("Identidad o alcance del manifiesto inválidos.")
        if (not _hex(fuentes["sha256_resultados"], 64) or not _hex(fuentes["geometria_id"], 32)
                or not _hex(fuentes["sha256_geometria"], 64)
                or (fuentes["huella_evidencia"] is None) == con_analisis
                or (fuentes["sha256_edb_analizado"] is None) == con_analisis
                or (con_analisis and not (_hex(fuentes["huella_evidencia"], 64) and _hex(fuentes["sha256_edb_analizado"], 64)))):
            raise ErrorPaneles("Huellas de fuentes del manifiesto inválidas.")
        if not isinstance(estados, dict) or set(estados) != {"calculo", "revision_resultados", "conformidad_normativa", "reglas"}:
            raise ErrorPaneles("Estados del manifiesto inválidos.")
        return meta

    # -- API ------------------------------------------------------------------------
    def crear(self, body) -> dict:
        if not isinstance(body, dict) or set(body) != CAMPOS_CREAR:
            raise ErrorPaneles("Selecciona exactamente caso, resultado, expediente_sha256 y analisis.")
        return self._publico(lambda: self._crear(body))

    def _crear(self, body) -> dict:
        with self.app.lock:
            caso, resultado, fingerprint, analisis = body["caso"], body["resultado"], body["expediente_sha256"], body["analisis"]
            fuente = self._fuente(caso, resultado, fingerprint, analisis)
            folder = self._caso(caso, fingerprint)
            base = self._grupo(folder, GRUPO, crear=True)
            ident = uuid4().hex
            destino = base / ident
            with tempfile.TemporaryDirectory(prefix=".panel-", dir=base) as temporal:
                etapa = Path(temporal).resolve()
                if etapa.parent != base:
                    raise ErrorPaneles("Temporal fuera del caso.")
                paquete = etapa / "paquete"
                paquete.mkdir()
                crear_panel(fuente["resultados_path"], None, paquete / ARCHIVO_HTML, geometria=fuente["geometria_path"],
                            evidencia_analisis=fuente["fuente_evidencia"])
                html = (paquete / ARCHIVO_HTML).read_bytes()
                self._sin_rutas(html, folder)
                self._comprobar_html(html, fuente)
                if not self._misma_fuente(self._fuente(caso, resultado, fingerprint, analisis), fuente):
                    raise ErrorPaneles("Las fuentes cambiaron al generar el panel.")
                manifiesto = {"contrato": CONTRATO, "version": VERSION, "id": ident, "caso": caso, "resultado": resultado,
                              "analisis": analisis, "expediente_sha256": fingerprint,
                              "huella_resultados": fuente["checked"]["huella"], "fuentes": fuente["fuentes"],
                              "artefacto": {ARCHIVO_HTML: _sha(html)}, "estados": _estados(fuente["evidencia"]),
                              "creado_utc": datetime.now(timezone.utc).isoformat(),
                              "aprueba_resultados": False, "aprueba_ingenieria": False}
                with (paquete / ARCHIVO_MANIFIESTO).open("x", encoding="utf-8") as stream:
                    stream.write(json.dumps(manifiesto, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
                if os.path.lexists(destino):
                    raise ErrorPaneles("Destino existente; no se sobrescribe.")
                paquete.rename(destino)  # publicación atómica dentro de paneles/
            return self.consultar(caso, ident, expediente_sha256=fingerprint)

    def _comprobar_html(self, html: bytes, fuente: dict) -> None:
        datos = _datos_embebidos(html)
        checked, evidencia = fuente["checked"], fuente["evidencia"]
        from .resumen_geometria import resumen_geometria
        geo = json_desde_bytes(fuente["geometria_path"].read_bytes(), "geometria.json")
        resumen = resumen_geometria(geo)
        esperados = ({"resultados", "evaluacion", "numero_muros", "huella_resultados"} | ({"evidencia_analisis"} if evidencia else set())
                     | ({"resumen_geometria"} if resumen is not None else set()))
        if (not isinstance(datos, dict) or set(datos) != esperados or datos["resultados"] != checked["datos"]
                or datos["huella_resultados"] != checked["huella"] or datos["evaluacion"] is not None
                or datos.get("evidencia_analisis") != evidencia
                or datos["numero_muros"] != len(geo["muros"]) or datos.get("resumen_geometria") != resumen):
            raise ErrorPaneles("El panel no corresponde a sus fuentes vigentes.")

        # El JSON auténtico no autentica el resto de un HTML ejecutable. Volver
        # a renderizar con el generador confiable impide sustituir texto, CSS o
        # JavaScript y rehacer el hash del manifiesto para legitimar el cambio.
        with tempfile.TemporaryDirectory(prefix="vp-") as temporal:
            esperado = Path(temporal) / "p.html"
            crear_panel(fuente["resultados_path"], None, esperado,
                        geometria=fuente["geometria_path"],
                        evidencia_analisis=fuente["fuente_evidencia"])
            if esperado.read_bytes() != html:
                raise ErrorPaneles("El HTML completo no corresponde al generador confiable.")

    def _cargar(self, caso, version, fingerprint) -> tuple[dict, dict, bytes, bytes]:
        _id(version)
        folder = self._caso(caso, fingerprint)
        destino = self._grupo(folder, GRUPO) / version
        _sin_enlace(destino)
        if not destino.is_dir():
            raise ErrorPaneles("Versión de panel ausente.")
        hijos = sorted(p.name for p in destino.iterdir())
        if hijos != sorted((ARCHIVO_HTML, ARCHIVO_MANIFIESTO)):
            raise ErrorPaneles("Contenido de la versión de panel inválido.")
        manifiesto_raw = self._archivo(destino / ARCHIVO_MANIFIESTO).read_bytes()
        meta = self._validar_manifiesto(
            json_desde_bytes(manifiesto_raw, ARCHIVO_MANIFIESTO), caso, version, fingerprint)
        html = self._archivo(destino / ARCHIVO_HTML).read_bytes()
        if _sha(html) != meta["artefacto"][ARCHIVO_HTML]:
            raise ErrorPaneles("Panel alterado.")
        fuente = self._fuente(caso, meta["resultado"], fingerprint, meta["analisis"])
        if (meta["huella_resultados"] != fuente["checked"]["huella"] or meta["fuentes"] != fuente["fuentes"]
                or meta["estados"] != _estados(fuente["evidencia"])):
            raise ErrorPaneles("El panel se generó con otras fuentes.")
        self._sin_rutas(html, folder)
        self._comprobar_html(html, fuente)
        if not self._misma_fuente(self._fuente(caso, meta["resultado"], fingerprint, meta["analisis"]), fuente):
            raise ErrorPaneles("Las fuentes cambiaron durante la consulta.")
        _sin_enlace(destino)
        if (sorted(p.name for p in destino.iterdir()) != hijos
                or self._archivo(destino / ARCHIVO_MANIFIESTO).read_bytes() != manifiesto_raw
                or self._archivo(destino / ARCHIVO_HTML).read_bytes() != html):
            raise ErrorPaneles("El panel o su manifiesto cambiaron durante la consulta.")
        return meta, fuente, html, manifiesto_raw

    @staticmethod
    def _proyeccion(meta: dict, fuente: dict) -> dict:
        return {"id": meta["id"], "caso": meta["caso"], "resultado": meta["resultado"], "analisis": meta["analisis"],
                "expediente_sha256": meta["expediente_sha256"], "huella_resultados": meta["huella_resultados"],
                "creado_utc": meta["creado_utc"], "sha256_html": meta["artefacto"][ARCHIVO_HTML],
                "fuentes": dict(meta["fuentes"]), "estados": dict(meta["estados"]), "vigente": True,
                "evidencia_analisis": fuente["evidencia"], "aprueba_resultados": False, "aprueba_ingenieria": False,
                "aviso": AVISO}

    def _publico(self, operacion):
        try:
            with self.app.lock:
                return operacion()
        except ErrorPaneles:
            raise
        except (ValueError, OSError, TypeError, KeyError, RuntimeError, UnicodeError):
            raise ErrorPaneles("Panel, resultado o análisis inválido, ausente o sin evidencia vigente; "
                               "vuelve a consultar el expediente.") from None

    def consultar(self, caso, version, *, expediente_sha256) -> dict:
        def operacion():
            meta, fuente, _, _ = self._cargar(caso, version, expediente_sha256)
            return self._proyeccion(meta, fuente)
        return self._publico(operacion)

    def listar(self, caso, resultado, *, expediente_sha256) -> dict:
        def operacion():
            self._fuente(caso, resultado, expediente_sha256, None)
            base = self._grupo(self._caso(caso, expediente_sha256), GRUPO)
            filas = []
            for path in sorted(base.iterdir()) if base.is_dir() else []:
                if not _hex(path.name, 32):
                    continue  # temporales .panel-* y nombres ajenos no son versiones
                try:
                    candidate=json_desde_bytes(self._archivo(path / ARCHIVO_MANIFIESTO).read_bytes(),ARCHIVO_MANIFIESTO)
                    if not isinstance(candidate,dict) or candidate.get('resultado')!=resultado:continue
                except (ValueError,OSError,TypeError):continue  # sin identidad atribuible a este resultado
                try:
                    meta, _, _, _ = self._cargar(caso, path.name, expediente_sha256)
                except (ValueError, OSError, TypeError, KeyError, RuntimeError, UnicodeError):
                    filas.append({"id": path.name, "vigente": False, "problemas": ["version_no_vigente"]})
                    continue
                if meta["resultado"] == resultado:
                    filas.append({"id": path.name, "vigente": True, "analisis": meta["analisis"],
                                  "creado_utc": meta["creado_utc"], "estados": dict(meta["estados"])})
            self._caso(caso, expediente_sha256)
            return {"caso": caso, "resultado": resultado, "expediente_sha256": expediente_sha256, "versiones": filas}
        return self._publico(operacion)

    def archivo(self, caso, version, *, expediente_sha256) -> bytes:
        def operacion():
            meta, fuente, html, manifiesto_raw = self._cargar(caso, version, expediente_sha256)
            raw = self._archivo(self._grupo(self._caso(caso, expediente_sha256), GRUPO) / version / ARCHIVO_HTML).read_bytes()
            if raw != html or _sha(raw) != meta["artefacto"][ARCHIVO_HTML]:
                raise ErrorPaneles("Panel cambiado durante la descarga.")
            segundo_meta, segunda_fuente, segundo_html, segundo_manifiesto = self._cargar(caso, version, expediente_sha256)
            if (segundo_meta != meta or not self._misma_fuente(segunda_fuente, fuente)
                    or segundo_html != raw or segundo_manifiesto != manifiesto_raw):
                raise ErrorPaneles("El panel o su manifiesto cambiaron durante la descarga.")
            return raw
        return self._publico(operacion)
