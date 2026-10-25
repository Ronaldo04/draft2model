"""Evidencia verificable de análisis ETABS ligada a un resultado normalizado del expediente.

`verificar_evidencia` revalida desde los ficheros, sin escribir nada:

1. El resultado `resultados_estructurales/<id>` del caso: contrato, huella de resultados, respuesta de
   tablas por SHA256, mapeo con revisión vigente, configuración vigente (`comprobar_configuracion`),
   copia EDB del caso por SHA256 y cada valor rederivado de la fila CSI citada en la trazabilidad.
2. La corrida de análisis aceptada (`aceptacion_analisis.json`, `solicitud.json`, `respuesta.json`):
   campos exactos, casos con estado CSI 4, `aprueba_resultados` falso, EDB analizado y entrada por
   SHA256, sin `analisis_no_aceptado.json`.
3. La revisión del modelo construido que autorizó el análisis (`revision_modelo.consultar_aprobacion`).
4. El vínculo exacto entre ambos: mismo EDB analizado (SHA256 y ruta declarada), mismos casos con
   estado 4, misma configuración y geometría, misma naturaleza sintética y misma versión del motor.

Devuelve un diccionario sin rutas locales, apto para un HTML compartible. No basta la existencia de un
JSON ni un campo `aceptada: true`. Separa cálculo completado de revisión de resultados y de conformidad
normativa: la evidencia no aprueba resultados ni ingeniería.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import stat
from pathlib import Path
from typing import Any

from . import revision_modelo as rm
from .modelo_estructural import comprobar_configuracion, huella_configuracion
from .normalizacion_etabs import _numero
from .resultados_estructurales import aprobacion_vigente, exigir_resultados, huella_resultados

CONTRATO = "draft2model.evidencia_analisis"
VERSION = "0.1.0"
ESTADO_CSI_TERMINADO = 4
ESTADOS = {"calculo": "completado_verificado", "revision_resultados": "pendiente",
           "conformidad_normativa": "no_evaluada", "correspondencias_tablas": "revision_declarada"}
AVISO = ("El motor declaró los casos como terminados (estado CSI 4) y las huellas enlazan modelo revisado, EDB "
         "analizado y resultado normalizado. No autentica al productor, no revisa los resultados, no evalúa "
         "conformidad normativa ni aprueba ingeniería.")
CAMPOS_ACEPTACION = {"aceptada", "analisis_ejecutado", "aprobacion_id", "aprueba_resultados", "casos_ejecutados",
                     "datos_sinteticos", "estados_casos", "fecha_utc", "guardado", "huella_modelo", "modelo_id",
                     "modo", "sha256_aprobacion"}
ARCHIVOS_RESULTADO = ("resultados.json", "trazabilidad.json", "mapeo.json", "respuesta_puente.json", "configuracion.json")
HEX32 = r"[0-9a-f]{32}"
HEX64 = r"[0-9a-f]{64}"


class ErrorEvidenciaAnalisis(ValueError):
    """La evidencia falta, está alterada o no corresponde al resultado, modelo o caso."""


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _exigir(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise ErrorEvidenciaAnalisis(mensaje)


def _json(raw: bytes, nombre: str) -> Any:
    try:
        return rm._json(raw)
    except ValueError as error:
        raise ErrorEvidenciaAnalisis(f"{nombre}: JSON inválido ({error}).") from error


def _misma_ruta_declarada(a: Any, b: Any) -> bool:
    return isinstance(a, str) and isinstance(b, str) and bool(a) and os.path.normcase(a) == os.path.normcase(b)


def _carpeta_corrida(corrida: Path) -> Path:
    carpeta = Path(corrida).absolute()
    _exigir(carpeta.is_dir() and carpeta.resolve() == carpeta, "Corrida de análisis ausente, enlazada o con ruta no normalizada.")
    _exigir(re.fullmatch(HEX32, carpeta.name) is not None, "La carpeta de la corrida debe llamarse como su id (32 hexadecimales).")
    _exigir(not (carpeta / "analisis_no_aceptado.json").exists(), "La corrida registra un análisis no aceptado.")
    return carpeta


def _leer(ruta: Path) -> bytes:
    try:
        return rm._leer(ruta)
    except ValueError as error:
        raise ErrorEvidenciaAnalisis(f"{Path(ruta).name}: {error}") from error


# -- resultado normalizado ------------------------------------------------------

def _verificar_resultado(raiz: Path, caso: str, resultado_id: str) -> dict:
    try:
        carpeta = rm._folder(raiz, caso, "resultados_estructurales", resultado_id)
    except ValueError as error:
        raise ErrorEvidenciaAnalisis(f"Resultado del expediente: {error}") from error
    crudos = {n: _leer(carpeta / n) for n in ARCHIVOS_RESULTADO}
    res, traz, mapeo, tablas, config = (_json(crudos[n], n) for n in ARCHIVOS_RESULTADO)
    try:
        exigir_resultados(res)
    except ValueError as error:
        raise ErrorEvidenciaAnalisis(f"resultados.json no cumple su contrato: {error}") from error
    _exigir(res["caso_id"] == caso, "El resultado pertenece a otro caso.")
    _exigir(isinstance(traz, dict) and traz.get("huella_resultados") == huella_resultados(res),
            "resultados.json no corresponde a la huella de su trazabilidad.")
    sha_tablas = _sha(crudos["respuesta_puente.json"])
    _exigir(traz.get("sha256_respuesta") == sha_tablas and isinstance(mapeo, dict) and mapeo.get("sha256_respuesta") == sha_tablas,
            "La respuesta de tablas no coincide con la trazabilidad y el mapeo.")
    _exigir(mapeo.get("caso") == caso and mapeo.get("datos_sinteticos") is res["datos_sinteticos"] and aprobacion_vigente(mapeo),
            "Mapeo de otro caso, de distinta naturaleza o sin revisión vigente.")
    modelo = traz.get("modelo")
    _exigir(isinstance(modelo, dict) and modelo == mapeo.get("modelo") and re.fullmatch(HEX64, str(modelo.get("sha256", ""))),
            "Referencia de modelo de la trazabilidad inválida o distinta del mapeo.")
    _exigir(isinstance(config, dict) and huella_configuracion(config) == res["configuracion"]["sha256"] == mapeo.get("huella_configuracion")
            and config.get("id") == res["configuracion"]["id"], "La configuración no corresponde al resultado.")
    origen = config.get("geometria_origen") or {}
    _exigir(origen.get("version_id") == res["geometria"]["id"] and origen.get("sha256_geometria") == res["geometria"]["sha256"],
            "La geometría de la configuración no corresponde al resultado.")
    _exigir(comprobar_configuracion(raiz, config).apto_para_adaptador, "La configuración o su geometría ya no están vigentes.")
    relativo = Path(str(modelo.get("archivo", "")))
    caso_dir = carpeta.parent.parent
    copia = caso_dir / relativo
    _exigir(not relativo.is_absolute() and ".." not in relativo.parts and relativo.suffix.lower() == ".edb",
            "El EDB del resultado debe ser un archivo del caso.")
    _exigir(_sha(_leer(copia)) == modelo["sha256"], "La copia EDB del caso no coincide con la trazabilidad.")

    _exigir(isinstance(tablas, dict) and tablas.get("contrato") == "draft2model.etabs_respuesta"
            and tablas.get("operacion") == "leer_tablas" and tablas.get("estado") == "ok"
            and tablas.get("id_solicitud") == res["corrida_id"], "La respuesta de tablas no es la corrida del resultado.")
    _exigir((tablas.get("modo_ejecucion") == "real") == (res["motor"]["tipo"] == "real"),
            "El modo de la respuesta de tablas no coincide con el motor del resultado.")
    datos = tablas.get("datos") or {}
    _exigir(datos.get("version_etabs") == res["motor"]["version"], "La versión ETABS de las tablas no es la del resultado.")
    if "archivo_motor" in modelo:
        _exigir(_misma_ruta_declarada(datos.get("modelo"), modelo["archivo_motor"]),
                "La respuesta de tablas leyó un modelo distinto del declarado.")
    casos_res = sorted({c["id"] for c in res["casos"]} | {r["caso"] for r in res["resultados"]})
    for caso_id in casos_res:
        _exigir(caso_id in (datos.get("casos") or []) and (datos.get("estado_casos") or {}).get(caso_id) == ESTADO_CSI_TERMINADO,
                f"El caso {caso_id} no figura como terminado en la lectura de tablas.")
    selectores=mapeo.get('selectores')
    _exigir(isinstance(selectores,list) and all(isinstance(s,dict) for s in selectores), 'Mapeo sin selectores.')
    por_id={s.get('id'):s for s in selectores}
    _exigir(len(por_id)==len(selectores) and set(por_id)=={r['id'] for r in res['resultados']},
            'El resultado no cubre exactamente los selectores revisados.')
    correspondencias=traz.get('correspondencias')
    _exigir(isinstance(correspondencias,list) and all(isinstance(c,dict) for c in correspondencias), 'Correspondencias inválidas.')
    for c in correspondencias:
        s=por_id.get(c.get('resultado_id'))
        _exigir(s is not None and all(c.get(k)==s.get(v) for k,v in
            [('tabla','tabla'),('campo','campo_valor'),('filtros','filtros'),('unidad_origen','unidad_origen')]),
            'La trazabilidad no corresponde al selector revisado.')
        factor=0.001 if s['variable']=='cortante' and s['unidad_origen']=='N' else 1.0
        _exigir(type(c.get('factor')) in (int,float) and c['factor']==factor, 'Factor distinto de la conversión revisada.')
    for r in res['resultados']:
        s=por_id[r['id']]
        _exigir(all(r.get(k)==s.get(k) for k in ('variable','caso','direccion','ubicacion')),
                'El indicador no corresponde al selector revisado.')
    _rederivar(res, traz, datos)
    return {"res": res, "traz": traz, "modelo": modelo, "datos_tablas": datos, "casos": casos_res,
            "sha_tablas": sha_tablas, "huella": huella_resultados(res)}


def _rederivar(res: dict, traz: dict, datos: dict) -> None:
    """Cada valor del resultado debe salir de la fila y el campo CSI citados en la trazabilidad."""
    tablas = {t.get("clave"): t for t in datos.get("tablas") or [] if isinstance(t, dict)}
    filas = {r["id"]: r for r in res["resultados"]}
    correspondencias = traz.get("correspondencias")
    _exigir(isinstance(correspondencias, list) and sorted(c.get("resultado_id") for c in correspondencias) == sorted(filas),
            "La trazabilidad no cubre exactamente los resultados.")
    for c in correspondencias:
        fila_res, tabla = filas[c["resultado_id"]], tablas.get(c.get("tabla"))
        from .normalizacion_etabs import campo_caso_csi
        tipos={caso['id']:caso['tipo'] for caso in res['casos']}
        campo_caso=campo_caso_csi(c.get('tabla'),fila_res['variable'],tipos[fila_res['caso']])
        _exigir(tabla is not None and isinstance(c.get("filtros"), dict) and c["filtros"].get(campo_caso) == fila_res["caso"],
                f"Correspondencia de {c['resultado_id']} sin tabla o sin caso explícito.")
        candidatas=[i for i,fila in enumerate(tabla.get('filas') or [])
                    if all(fila.get(k)==v for k,v in c['filtros'].items())]
        _exigir(len(candidatas)<=1 and (candidatas[0] if candidatas else None)==c.get('fila_indice'),
                f"{c['resultado_id']}: ausencia, ambigüedad o índice incoherentes con los filtros.")
        if c.get("fila_indice") is None:
            _exigir(fila_res["valor"] is None, f"{c['resultado_id']}: valor sin fila CSI citada.")
            continue
        indice = c["fila_indice"]
        _exigir(isinstance(indice, int) and not isinstance(indice, bool) and 0 <= indice < len(tabla.get("filas") or []),
                f"{c['resultado_id']}: índice de fila fuera de la tabla.")
        fila = tabla["filas"][indice]
        _exigir(all(fila.get(k) == v for k, v in c["filtros"].items()), f"{c['resultado_id']}: la fila citada no cumple sus filtros.")
        try:
            valor = _numero(fila.get(c.get("campo"))) * float(c.get("factor"))
        except (TypeError, ValueError) as error:
            raise ErrorEvidenciaAnalisis(f"{c['resultado_id']}: valor CSI no legible ({error}).") from error
        _exigir(fila_res["valor"] is not None and math.isclose(valor, fila_res["valor"], rel_tol=1e-12, abs_tol=0.0),
                f"{c['resultado_id']}: el valor no coincide con la tabla CSI citada.")


# -- corrida de análisis ---------------------------------------------------------

def _verificar_analisis(raiz: Path, caso: str, corrida: Path) -> dict:
    carpeta = _carpeta_corrida(corrida)
    crudos = {n: _leer(carpeta / n) for n in ("aceptacion_analisis.json", "solicitud.json", "respuesta.json")}
    acc = _json(crudos["aceptacion_analisis.json"], "aceptacion_analisis.json")
    sol = _json(crudos["solicitud.json"], "solicitud.json")
    resp = _json(crudos["respuesta.json"], "respuesta.json")
    _exigir(isinstance(acc, dict) and set(acc) == CAMPOS_ACEPTACION, "aceptacion_analisis.json no tiene los campos exactos del analizador.")
    _exigir(acc["aceptada"] is True and acc["analisis_ejecutado"] is True and acc["aprueba_resultados"] is False,
            "La aceptación no declara análisis ejecutado y aceptado sin aprobar resultados.")
    _exigir(acc["modo"] in ("real", "doble") and type(acc["datos_sinteticos"]) is bool
            and (acc["modo"] == "real" or acc["datos_sinteticos"] is True), "Modo de análisis inválido para la naturaleza de los datos.")
    casos = acc["casos_ejecutados"]
    _exigir(isinstance(casos, list) and casos and len(set(casos)) == len(casos) and all(isinstance(c, str) and c for c in casos),
            "Casos ejecutados inválidos.")
    _exigir(acc["estados_casos"] == {c: ESTADO_CSI_TERMINADO for c in casos}, "No todos los casos tienen estado CSI 4 (terminado).")
    guardado = acc["guardado"]
    _exigir(isinstance(guardado, dict) and set(guardado) == {"ruta", "sha256"} and re.fullmatch(HEX64, str(guardado["sha256"])),
            "Registro del EDB analizado inválido.")
    ruta_declarada = Path(str(guardado["ruta"]))
    _exigir(ruta_declarada.name.lower() == "analizado.edb" and ruta_declarada.parent.name == carpeta.name,
            "El EDB analizado no pertenece a esta corrida.")
    for clave in ("modelo_id", "aprobacion_id"):
        _exigir(re.fullmatch(HEX32, str(acc[clave])) is not None, f"{clave} inválido.")

    _exigir(isinstance(sol, dict) and sol.get("contrato") == "draft2model.etabs_solicitud" and sol.get("operacion") == "analizar_modelo"
            and sol.get("id") == carpeta.name and sol.get("modo_configurado") == acc["modo"] and sol.get("casos") == casos
            and sol.get("destino") == guardado["ruta"]
            and all(sol.get(k) == acc[k] for k in ("modelo_id", "huella_modelo", "aprobacion_id", "sha256_aprobacion", "datos_sinteticos")),
            "La solicitud de análisis no corresponde a la aceptación.")
    datos = resp.get("datos") if isinstance(resp, dict) else None
    _exigir(isinstance(resp, dict) and resp.get("contrato") == "draft2model.etabs_respuesta" and resp.get("operacion") == "analizar_modelo"
            and resp.get("estado") == "ok" and resp.get("id_solicitud") == carpeta.name and resp.get("modo_ejecucion") == acc["modo"]
            and isinstance(datos, dict) and datos.get("guardado") == guardado and datos.get("casos_ejecutados") == casos
            and datos.get("estados_casos") == acc["estados_casos"] and datos.get("sha256_entrada") == sol.get("sha256_entrada")
            and datos.get("analisis_ejecutado") is True and datos.get("aprueba_resultados") is False
            and isinstance(datos.get("version_etabs"), str) and datos["version_etabs"],
            "La respuesta del análisis no corresponde a la aceptación.")
    _exigir(_sha(_leer(carpeta / ruta_declarada.name)) == guardado["sha256"], "El EDB analizado fue alterado.")
    _exigir(_sha(_leer(carpeta / "entrada.edb")) == sol.get("sha256_entrada"), "La copia de entrada del análisis fue alterada.")
    try:
        revision = rm.consultar_aprobacion(raiz, caso, acc["aprobacion_id"])
    except ValueError as error:
        raise ErrorEvidenciaAnalisis(f"La revisión del modelo que autorizó el análisis no está vigente: {error}") from error
    origen = revision["origen"]
    _exigir(revision["modelo_id"] == acc["modelo_id"] and revision["huella_modelo"] == acc["huella_modelo"]
            and revision["sha256_aprobacion"] == acc["sha256_aprobacion"], "La aceptación cita otro modelo o revisión.")
    _exigir(origen["sha256_modelo"] == sol.get("sha256_entrada") and origen["modo"] == acc["modo"]
            and origen["datos_sinteticos"] is acc["datos_sinteticos"], "El análisis no partió del modelo revisado.")
    return {"acc": acc, "sol": sol, "resp": resp, "revision": revision, "carpeta": carpeta,
            "sha": {n: _sha(r) for n, r in crudos.items()}}


# -- API -------------------------------------------------------------------------

def verificar_analisis_aceptado(raiz: Path, caso: str, corrida: Path) -> dict:
    """Análisis controlado del caso, sin resultados, escrituras, rutas ni PID en salida."""
    try:
        from .gestion_extraccion import carpeta_caso
        root = Path(raiz).absolute()
        folder = carpeta_caso(root, caso)
        run = Path(corrida).absolute()
        _exigir(re.fullmatch(HEX32, run.name) is not None and run.parent == folder/'analisis_etabs',
                'Corrida de análisis fuera del grupo controlado del caso.')
        for path in (root, folder, run.parent, run):
            info = path.lstat()
            _exigir(path.resolve() == path and not stat.S_ISLNK(info.st_mode)
                    and not (getattr(info, 'st_file_attributes', 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT),
                    'Directorio de análisis enlazado no permitido.')
        checked = _verificar_analisis(root, caso, run)
        acc, source = checked['acc'], checked['revision']['origen']['origen']
        states = acc['estados_casos']
        _exigir(isinstance(states, dict) and all(type(value) is int and value == 4 for value in states.values()),
                'Los estados de análisis deben ser enteros CSI 4.')
        response_states = checked['resp']['datos']['estados_casos']
        _exigir(isinstance(response_states, dict) and all(type(value) is int and value == 4 for value in response_states.values())
                and checked['sol'].get('version_contrato') == '0.1.0' and checked['resp'].get('version_contrato') == '0.1.0',
                'Versión/estados de respuesta no admitidos.')
        for name, digest in checked['sha'].items():
            _exigir(_sha(_leer(run/name)) == digest, 'Fuentes de análisis cambiaron durante comprobación.')
        _exigir(_sha(_leer(run/'entrada.edb')) == checked['sol']['sha256_entrada']
                and _sha(_leer(run/Path(acc['guardado']['ruta']).name)) == acc['guardado']['sha256'],
                'Los EDB cambiaron durante comprobación.')
        return {'caso': caso, 'corrida_id': run.name, 'modo': acc['modo'],
                'datos_sinteticos': acc['datos_sinteticos'], 'modelo_id': acc['modelo_id'],
                'huella_modelo': acc['huella_modelo'], 'aprobacion_id': acc['aprobacion_id'],
                'sha256_aprobacion': acc['sha256_aprobacion'],
                'sha256_edb_analizado': acc['guardado']['sha256'],
                'sha256_entrada': checked['sol']['sha256_entrada'],
                'sha256_aceptacion': checked['sha']['aceptacion_analisis.json'],
                'sha256_solicitud': checked['sha']['solicitud.json'],
                'sha256_respuesta': checked['sha']['respuesta.json'],
                'version_etabs': checked['resp']['datos']['version_etabs'],
                'casos': list(acc['casos_ejecutados']), 'estados_casos': dict(states),
                'configuracion': {'id': source['configuracion_id'], 'huella': source['huella_configuracion']},
                'geometria': {'id': source['geometria']['version_id'], 'sha256': source['geometria']['sha256_geometria']},
                'analisis_ejecutado': True, 'aprueba_resultados': False}
    except (ValueError, OSError, RuntimeError, TypeError, KeyError, AttributeError):
        raise ErrorEvidenciaAnalisis('Análisis del caso inválido, alterado o sin aceptación vigente.') from None


def verificar_resultado_normalizado(raiz: Path, caso: str, resultado: str) -> dict:
    """Paquete comprobado sin inferir análisis vinculado ni conceder aprobación.

    Proyección sin rutas de ficheros; la verificación de fuentes y
    correspondencias permanece encapsulada en este módulo.
    """
    import copy
    checked=_verificar_resultado(Path(raiz),caso,resultado)
    return {'datos':copy.deepcopy(checked['res']), 'huella':checked['huella'],
            'sha256_edb':checked['modelo']['sha256'],'estado':'paquete_verificado',
            'analisis_vinculado':False,'aprueba_resultados':False}


def verificar_evidencia(raiz: Path, caso: str, resultado: str, corrida: Path) -> dict:
    """Revalida resultado, análisis, revisión del modelo y su vínculo. No escribe nada."""
    raiz = Path(raiz)
    r = _verificar_resultado(raiz, caso, resultado)
    a = _verificar_analisis(raiz, caso, corrida)
    res, acc, origen = r["res"], a["acc"], a["revision"]["origen"]["origen"]
    _exigir(r["modelo"]["sha256"] == acc["guardado"]["sha256"], "El resultado no se leyó del EDB que produjo este análisis.")
    if "archivo_motor" in r["modelo"]:
        _exigir(_misma_ruta_declarada(r["modelo"]["archivo_motor"], acc["guardado"]["ruta"]),
                "La lectura de tablas declara otro EDB analizado.")
    _exigir(set(r["casos"]) <= set(acc["casos_ejecutados"]), "El resultado usa casos que este análisis no ejecutó.")
    _exigir(res["datos_sinteticos"] is acc["datos_sinteticos"], "Naturaleza sintética distinta entre análisis y resultado.")
    _exigir((res["motor"]["tipo"] == "real") == (acc["modo"] == "real"), "Motor real/simulación distinto entre análisis y resultado.")
    _exigir(res["motor"]["version"] == a["resp"]["datos"]["version_etabs"], "Versión de ETABS distinta entre análisis y resultado.")
    _exigir(origen["huella_configuracion"] == res["configuracion"]["sha256"] and origen["configuracion_id"] == res["configuracion"]["id"],
            "El modelo analizado se construyó con otra configuración.")
    _exigir(origen["geometria"]["version_id"] == res["geometria"]["id"] and origen["geometria"]["sha256_geometria"] == res["geometria"]["sha256"],
            "El modelo analizado se construyó con otra geometría.")
    evidencia = {
        "contrato": CONTRATO, "version": VERSION, "caso_id": caso, "datos_sinteticos": res["datos_sinteticos"],
        "resultado": {"id": resultado, "huella_resultados": r["huella"], "corrida_tablas_id": res["corrida_id"],
                      "sha256_respuesta_tablas": r["sha_tablas"], "sha256_edb_leido": r["modelo"]["sha256"]},
        "analisis": {"corrida_id": a["carpeta"].name, "modo": acc["modo"], "version_etabs": a["resp"]["datos"]["version_etabs"],
                     "casos": [{"id": c, "estado_csi": ESTADO_CSI_TERMINADO} for c in acc["casos_ejecutados"]],
                     "fecha_aceptacion_utc": acc["fecha_utc"], "sha256_aceptacion": a["sha"]["aceptacion_analisis.json"],
                     "sha256_solicitud": a["sha"]["solicitud.json"], "sha256_respuesta": a["sha"]["respuesta.json"],
                     "sha256_entrada": a["sol"]["sha256_entrada"], "sha256_edb_analizado": acc["guardado"]["sha256"]},
        "modelo": {"modelo_id": acc["modelo_id"], "huella_modelo": acc["huella_modelo"], "aprobacion_id": acc["aprobacion_id"],
                   "sha256_aprobacion": acc["sha256_aprobacion"], "identidad_revisor": "declarada_no_verificada"},
        "estados": dict(ESTADOS), "aprueba_resultados": False, "aprueba_ingenieria": False, "aviso": AVISO,
    }
    validar_evidencia(evidencia, res)
    return evidencia


def _hex(valor: Any, patron: str) -> bool:
    return isinstance(valor, str) and re.fullmatch(patron, valor) is not None


def validar_evidencia(evidencia: Any, resultados: dict) -> None:
    """Forma exacta del snapshot y vínculo con el resultado; no relee ficheros (eso es verificar_evidencia)."""
    _exigir(isinstance(evidencia, dict) and set(evidencia) == {"contrato", "version", "caso_id", "datos_sinteticos", "resultado",
            "analisis", "modelo", "estados", "aprueba_resultados", "aprueba_ingenieria", "aviso"}, "Evidencia de análisis con campos inválidos.")
    _exigir(evidencia["contrato"] == CONTRATO and evidencia["version"] == VERSION and evidencia["aviso"] == AVISO
            and evidencia["estados"] == ESTADOS and evidencia["aprueba_resultados"] is False and evidencia["aprueba_ingenieria"] is False,
            "Contrato, estados o alcance de la evidencia alterados.")
    r, a, m = evidencia["resultado"], evidencia["analisis"], evidencia["modelo"]
    _exigir(isinstance(r, dict) and set(r) == {"id", "huella_resultados", "corrida_tablas_id", "sha256_respuesta_tablas", "sha256_edb_leido"}
            and _hex(r["id"], HEX32) and _hex(r["corrida_tablas_id"], HEX32)
            and all(_hex(r[k], HEX64) for k in ("huella_resultados", "sha256_respuesta_tablas", "sha256_edb_leido")),
            "Bloque de resultado de la evidencia inválido.")
    _exigir(isinstance(a, dict) and set(a) == {"corrida_id", "modo", "version_etabs", "casos", "fecha_aceptacion_utc", "sha256_aceptacion",
            "sha256_solicitud", "sha256_respuesta", "sha256_entrada", "sha256_edb_analizado"} and _hex(a["corrida_id"], HEX32)
            and a["modo"] in ("real", "doble") and isinstance(a["version_etabs"], str) and a["version_etabs"]
            and isinstance(a["fecha_aceptacion_utc"], str)
            and all(_hex(a[k], HEX64) for k in ("sha256_aceptacion", "sha256_solicitud", "sha256_respuesta", "sha256_entrada", "sha256_edb_analizado")),
            "Bloque de análisis de la evidencia inválido.")
    _exigir(isinstance(a["casos"], list) and a["casos"] and all(isinstance(c, dict) and set(c) == {"id", "estado_csi"}
            and isinstance(c["id"], str) and c["id"] and c["estado_csi"] == ESTADO_CSI_TERMINADO for c in a["casos"])
            and len({c["id"] for c in a["casos"]}) == len(a["casos"]), "Casos de la evidencia inválidos o no terminados.")
    _exigir(isinstance(m, dict) and set(m) == {"modelo_id", "huella_modelo", "aprobacion_id", "sha256_aprobacion", "identidad_revisor"}
            and _hex(m["modelo_id"], HEX32) and _hex(m["aprobacion_id"], HEX32) and _hex(m["huella_modelo"], HEX64)
            and _hex(m["sha256_aprobacion"], HEX64) and m["identidad_revisor"] == "declarada_no_verificada",
            "Bloque de modelo de la evidencia inválido.")
    casos_res = {c["id"] for c in resultados["casos"]} | {x["caso"] for x in resultados["resultados"]}
    _exigir(evidencia["caso_id"] == resultados["caso_id"] and evidencia["datos_sinteticos"] is resultados["datos_sinteticos"]
            and r["huella_resultados"] == huella_resultados(resultados) and r["corrida_tablas_id"] == resultados["corrida_id"]
            and r["sha256_edb_leido"] == a["sha256_edb_analizado"] and casos_res <= {c["id"] for c in a["casos"]}
            and (a["modo"] == "real") == (resultados["motor"]["tipo"] == "real") and a["version_etabs"] == resultados["motor"]["version"],
            "La evidencia de análisis no corresponde a estos resultados.")


def huella_evidencia(evidencia: dict) -> str:
    return _sha(json.dumps(evidencia, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8"))


def fuente_desde_argumentos(raiz, caso, resultado, corrida) -> dict | None:
    """Localizador de la evidencia para CLI: los cuatro datos o ninguno."""
    valores = (raiz, caso, resultado, corrida)
    if all(v is None for v in valores):
        return None
    _exigir(all(v is not None for v in valores),
            "La evidencia de análisis requiere --analisis-raiz, --analisis-caso, --analisis-resultado y --analisis-corrida.")
    return {"raiz": Path(raiz), "caso": caso, "resultado": resultado, "corrida": Path(corrida)}


def verificar_fuente(fuente: dict) -> dict:
    _exigir(isinstance(fuente, dict) and set(fuente) == {"raiz", "caso", "resultado", "corrida"},
            "Fuente de evidencia: se requieren raiz, caso, resultado y corrida.")
    return verificar_evidencia(fuente["raiz"], fuente["caso"], fuente["resultado"], fuente["corrida"])

