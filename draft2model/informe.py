"""Informe preliminar JSON/HTML/PDF desde contratos verificados, sin LLM ni red."""

from __future__ import annotations

import argparse
import copy
from datetime import date
import hashlib
import html
import io
import json
import math
from pathlib import Path
import sys

import pymupdf

from .evaluacion_estructural import evaluar_resultados, validar_reglas
from .resultados_estructurales import (
    cargar_json, exigir_resultados, huella_resultados, huella_declaracion, aprobacion_vigente,
)
from .validacion_geometria import validar_geometria

CONTRATO = "draft2model.informe_preliminar"
VERSION = "0.1.0"
AVISO = "Evaluación preliminar de indicadores declarados. No certifica seguridad estructural ni cumplimiento normativo integral."


def _texto(valor):
    return isinstance(valor, str) and bool(valor.strip()) and len(valor) <= 20_000


def _lista_texto(valor):
    return isinstance(valor, list) and len(valor) <= 1000 and all(_texto(x) for x in valor)


def _contexto(contexto):
    if not isinstance(contexto, dict) or set(contexto) != {"titulo", "hipotesis", "faltantes", "sitio"}:
        raise ValueError("Contexto requiere titulo, hipotesis, faltantes y sitio explícitos.")
    if not _texto(contexto["titulo"]) or not all(_lista_texto(contexto[k]) for k in ("hipotesis", "faltantes")):
        raise ValueError("Título/listas de contexto inválidos o exceden límites.")
    sitio = contexto["sitio"]
    if sitio is not None:
        campos = {"contrato", "version", "ubicacion", "estado", "zonas", "fuente", "fecha_fuente", "precision_m",
                  "datos_sinteticos", "sha256_capa", "huella_capa", "parametros_geotecnicos", "capacidad_portante", "aviso"}
        if (not isinstance(sitio, dict) or set(sitio) != campos or sitio["contrato"] != "draft2model.sitio"
                or sitio["version"] != "0.1.0" or sitio["estado"] not in ("dentro", "limite", "ambiguo", "sin_cobertura")
                or type(sitio["datos_sinteticos"]) is not bool or sitio["parametros_geotecnicos"] is not None
                or sitio["capacidad_portante"] is not None or not _texto(sitio["aviso"])
                or not isinstance(sitio["fuente"],dict) or set(sitio["fuente"]) != {"titulo","edicion","referencia"}
                or not all(_texto(v) for v in sitio["fuente"].values()) or not isinstance(sitio["zonas"],list)
                or type(sitio["precision_m"]) not in (int,float) or not math.isfinite(sitio["precision_m"]) or sitio["precision_m"] <= 0):
            raise ValueError("Sitio requiere salida declarada del contrato draft2model.sitio 0.1.0; no se recomputa el cruce.")
        date.fromisoformat(sitio["fecha_fuente"])
        for zona in sitio["zonas"]:
            if not isinstance(zona,dict) or set(zona) != {"id","etiqueta","posicion"} or not all(_texto(v) for v in zona.values()):
                raise ValueError("Zona declarada de sitio inválida.")
    return copy.deepcopy(contexto)


def _evaluar(resultados, reglas):
    # Acotar antes de la expansión cartesiana de selectores del evaluador.
    contenido = json.dumps([resultados, reglas], ensure_ascii=False, allow_nan=False)
    if len(contenido.encode("utf-8")) > 10_000_000:
        raise ValueError("Entradas del informe superan 10 MB.")
    rc = exigir_resultados(resultados)
    if reglas is None:
        return {'contrato':'draft2model.evaluacion_pendiente','version_contrato':'0.1.0',
                'estado':'pendiente','evaluaciones':[],
                'motivo':'No se aportaron reglas revisadas. No se declara cumplimiento ni evaluación normativa.',
                'huella_resultados':rc['huella']}
    reglas_check = validar_reglas(reglas)
    if not reglas_check["correcta"]:
        raise ValueError("Reglas inválidas: " + "; ".join(reglas_check["errores"]))
    expansiones = sum(len(r["aplicabilidad"]["casos"]) * len(r["aplicabilidad"]["direcciones"])
                      * len(r["aplicabilidad"]["ubicaciones"]) for r in reglas["reglas"])
    if len(resultados["resultados"]) > 2000 or expansiones > 5000:
        raise ValueError("Informe supera 2000 resultados o 5000 evaluaciones.")
    return evaluar_resultados(resultados, reglas, huella_resultados_esperada=rc["huella"],
                              huella_reglas_esperada=reglas_check["huella"])


def _geometria(archivo, resultados):
    if archivo is None:
        return None
    archivo = Path(archivo)
    original = archivo.read_bytes()
    datos = cargar_json(archivo)
    check = validar_geometria(datos)
    if not check.consistente:
        raise ValueError("Geometría inconsistente para informe.")
    sha = hashlib.sha256(original).hexdigest()
    if sha != resultados["geometria"]["sha256"]:
        raise ValueError("Geometría no corresponde al SHA256 de la corrida.")
    return {"datos": datos, "sha256_archivo": sha,
            "version_id_declarada": resultados["geometria"]["id"]}


def _fuentes(manifiesto, citas, resultados):
    citas = [] if citas is None else citas
    if manifiesto is None:
        if citas:
            raise ValueError("No se admiten citas sin un corpus verificable.")
        return None
    from .fuentes import cargar_corpus, huella_corpus, verificar_citas
    corpus = cargar_corpus(Path(manifiesto))
    huella = huella_corpus(corpus)
    verificar_citas(Path(manifiesto), citas, huella)
    if corpus["datos_sinteticos"] and not resultados["datos_sinteticos"]:
        raise ValueError("Corpus sintético no sustenta un informe de datos reales.")
    ids = [x["fragmento_id"] for x in citas]
    if len(ids) != len(set(ids)):
        raise ValueError("Citas repetidas.")
    fragmentos = [copy.deepcopy(f) for f in corpus["fragmentos"] if f["id"] in ids]
    documentos = [copy.deepcopy(d) for d in corpus["documentos"]
                  if any(f["documento"] == d["id"] for f in fragmentos)]
    return {"huella_corpus": huella, "datos_sinteticos": corpus["datos_sinteticos"], "corpus": copy.deepcopy(corpus),
            "citas": copy.deepcopy(citas), "fragmentos": fragmentos, "documentos": documentos}


def _estado_modelo_analisis(evidencia):
    if evidencia is None:
        return {"generacion": "no_disponible", "analisis": "no_disponible",
                "motivo": "El contrato de resultados declara valores; no acredita por sí solo generación ni terminación del solver."}
    a, m = evidencia["analisis"], evidencia["modelo"]
    return {"generacion": "modelo_construido_con_revision_declarada", "analisis": evidencia["estados"]["calculo"],
            "casos": copy.deepcopy(a["casos"]), "revision_resultados": evidencia["estados"]["revision_resultados"],
            "conformidad_normativa": evidencia["estados"]["conformidad_normativa"],
            "motivo": (f"Evidencia de análisis revalidada: modelo {m['modelo_id']} con revisión declarada {m['aprobacion_id']}; "
                       f"análisis {a['corrida_id']} aceptado ({a['modo']}, ETABS {a['version_etabs']}); el resultado se leyó del "
                       "mismo EDB analizado. Cálculo completado no equivale a resultados revisados ni a conformidad normativa.")}


def _evidencia(fuente, resultados):
    """Verificar la evidencia desde sus ficheros; None conserva el estado no disponible."""
    if fuente is None:
        return None
    from . import evidencia_analisis as ea
    evidencia = ea.verificar_fuente(fuente)
    ea.validar_evidencia(evidencia, resultados)
    return evidencia


def _siete(resultados, evaluacion, geometria, contexto, evidencia=None):
    datos = geometria["datos"] if geometria else None
    from .resumen_geometria import resumen_geometria
    resumen = resumen_geometria(datos)   # solo geometrías por superficies (0.2/0.3); el contrato 0.1 conserva su forma
    siete = {
        "estado_modelo_analisis": _estado_modelo_analisis(evidencia),
        "geometria_muros": {"numero_muros": len(datos["muros"]) if datos else None,
            "numero_niveles": len(datos["niveles"]) if datos else None,
            "unidad_longitud": datos["unidad_longitud"] if datos else None,
            "referencia": copy.deepcopy(resultados["geometria"]),
            "estado": "archivo_y_consistencia_verificados" if datos else "no_disponible"},
        "periodos": [copy.deepcopy(r) for r in resultados["resultados"] if r["variable"] == "periodo"],
        "derivas": [copy.deepcopy(r) for r in resultados["resultados"] if r["variable"] == "deriva"],
        "cortante_basal": [copy.deepcopy(r) for r in resultados["resultados"] if r["variable"] == "cortante" and r["ubicacion"] == "base"],
        "advertencias": {"declaradas": copy.deepcopy(resultados["advertencias"]),
                         "omisiones": copy.deepcopy(resultados["omisiones"]),
                         "reglas": copy.deepcopy(evaluacion["evaluaciones"])},
        "sitio": copy.deepcopy(contexto["sitio"]),
    }
    if resumen is not None:
        siete["geometria_muros"]["resumen_superficies"] = resumen
    return siete


def _huella_reglas(reglas):
    return huella_declaracion(reglas) if reglas is not None else huella_resultados(None)


def _huellas(resultados, reglas, calculada, evidencia, opcionales=None):
    huellas = {"resultados": huella_resultados(resultados), "reglas": _huella_reglas(reglas),
               "evaluacion": huella_resultados(calculada)}
    if evidencia is not None:
        from .evidencia_analisis import huella_evidencia
        huellas["evidencia_analisis"] = huella_evidencia(evidencia)
    for nombre, valor in (opcionales or {}).items():  # solo campos presentes: forma previa intacta
        huellas[nombre] = huella_resultados(valor)
    return huellas


OPCIONALES = ("contexto_verificado", "explicacion", "revision_resultados", "controles_analisis", "relectura_modelo", "contenido_masa",
              "masa_nativa")
FUENTE_MASA_ESPERADA = "MsSrc1"   # fuente por defecto de la plantilla, editada por SetMassSource_1 en el plan
TOLERANCIA_MASA_NATIVA = 1e-3     # criterio relativo explícito frente al libro; no se ajusta a la respuesta
CAMPOS_INVENTARIO = {"estado", "escenarios", "peso_total_kn", "masa_total_kn_s2_m", "aprueba_ingenieria", "crea_cargas", "ejecutable",
                     "huella_liquidos", "estados", "masa_nativa_verificada", "nota"}


def _finito(valor, nombre, signo=None):
    import math
    if type(valor) not in (int, float) or not math.isfinite(valor) or (signo == "no_negativo" and valor < 0):
        raise ValueError("Inventario de contenido: " + nombre + " no es un número finito válido.")
    return valor


def _validar_contenido_masa(value, resultados, evidencia=None):
    """Forma exacta del inventario (plan 0.5, liquidos.contenido) ligado al modelo de la evidencia de análisis.

    No relee ficheros (eso hace _contenido_masa desde su fuente). masa_nativa_verificada debe ser False: ninguna captura nativa
    de masa ensamblada está ligada todavía al análisis/EDB; una declaración no se convierte en prueba (revisión Codex 261).
    """
    import math
    import re
    if not isinstance(value, dict) or set(value) != {"caso_id", "modelo_id", "huella_plan", "inventario"}:
        raise ValueError("Contenido de masa del informe inválido.")
    if evidencia is None:
        raise ValueError("El contenido de masa exige evidencia de análisis que identifique el modelo y su plan.")
    if value["caso_id"] != resultados["caso_id"] or value["modelo_id"] != evidencia["modelo"]["modelo_id"]:
        raise ValueError("El contenido de masa no corresponde al caso/modelo analizado del informe.")
    if not isinstance(value["huella_plan"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["huella_plan"]):
        raise ValueError("Huella de plan del contenido inválida.")
    inv = value["inventario"]
    if not isinstance(inv, dict) or set(inv) != CAMPOS_INVENTARIO or inv["estado"] != "contabilidad_declarada_coherente":
        raise ValueError("Inventario de contenido inválido o no coherente.")
    if inv["aprueba_ingenieria"] is not False or inv["crea_cargas"] is not False or inv["ejecutable"] is not False:
        raise ValueError("El inventario de contenido no puede aprobar ingeniería, crear cargas ni ser ejecutable.")
    if inv["masa_nativa_verificada"] is not False:
        raise ValueError("Masa ensamblada nativa no ligada a una captura del análisis: masa_nativa_verificada debe ser False.")
    if not isinstance(inv["huella_liquidos"], str) or not re.fullmatch(r"[0-9a-f]{64}", inv["huella_liquidos"]):
        raise ValueError("Huella de líquidos del inventario inválida.")
    if not isinstance(inv["nota"], str) or not isinstance(inv["estados"], dict) or not all(
            isinstance(k, str) and v in ("lleno", "vacio", "desconocido", "ausente_confirmado") for k, v in inv["estados"].items()):
        raise ValueError("Estados del inventario de contenido inválidos.")
    filas = inv["escenarios"]
    if not isinstance(filas, list) or not filas:
        raise ValueError("Inventario de contenido sin escenarios.")
    cerca = lambda a, b: abs(a - b) <= 1e-9 * max(1, abs(a), abs(b))
    campos = {"deposito", "estado", "fuente", "declaracion", "modo", "patron_masa", "volumen_m3", "peso_kn", "masa_kn_s2_m",
              "factor_contenido", "fz_presion_kn"}
    for f in filas:
        if not isinstance(f, dict) or set(f) != campos or not all(isinstance(f[k], str) for k in ("deposito", "estado", "fuente",
                                                                                                    "declaracion", "modo", "patron_masa")):
            raise ValueError("Escenario del inventario de contenido inválido.")
        if inv["estados"].get(f["deposito"]) != f["estado"] or f["modo"] not in ("patron_presion", "patron_masa_exclusivo"):
            raise ValueError("Estado/modo del escenario de contenido incoherente.")
        for k in ("volumen_m3", "peso_kn", "masa_kn_s2_m"):
            _finito(f[k], k, "no_negativo")
        _finito(f["fz_presion_kn"], "fz_presion_kn")
        if f["factor_contenido"] != 1 or type(f["factor_contenido"]) is bool:
            raise ValueError("Factor de contenido distinto de 1.")
        if f["modo"] == "patron_presion" and not cerca(f["fz_presion_kn"], -f["peso_kn"]):
            raise ValueError("Fz de presión distinto de −γV en el inventario de contenido.")
    if not cerca(_finito(inv["peso_total_kn"], "peso_total_kn", "no_negativo"), math.fsum(f["peso_kn"] for f in filas)) or \
            not cerca(_finito(inv["masa_total_kn_s2_m"], "masa_total_kn_s2_m", "no_negativo"), math.fsum(f["masa_kn_s2_m"] for f in filas)):
        raise ValueError("Totales del inventario de contenido alterados.")


def _validar_masa_nativa(value, resultados, evidencia=None):
    """Forma y vínculo de la sección: lectura aceptada del mismo análisis/EDB; contraste coherente o no, nunca aprobado."""
    import math
    import re
    campos = {"caso_id", "lectura_id", "sha256_respuesta", "corrida_analisis_id", "sha256_edb", "libro", "contraste"}
    if not isinstance(value, dict) or set(value) not in (campos, campos | {"estimacion_auto"}):
        raise ValueError("Sección de masa nativa inválida.")
    if evidencia is None or value["caso_id"] != resultados["caso_id"]:
        raise ValueError("La masa nativa exige evidencia de análisis del mismo caso.")
    if value["corrida_analisis_id"] != evidencia["analisis"]["corrida_id"] or value["sha256_edb"] != evidencia["analisis"]["sha256_edb_analizado"]:
        raise ValueError("La lectura de masa no corresponde al análisis/EDB del informe.")
    if not all(isinstance(value[k], str) and re.fullmatch(p, value[k]) for k, p in
               (("lectura_id", r"[0-9a-f]{32}"), ("sha256_respuesta", r"[0-9a-f]{64}"))):
        raise ValueError("Identidad de lectura de masa inválida.")
    c, lb = value["contraste"], value["libro"]
    if not isinstance(c, dict) or c.get("estado") not in ("coherente", "no_coherente") or c.get("aprueba_ingenieria") is not False \
            or c.get("capture_id") != value["lectura_id"] or c.get("fuente_esperada") != FUENTE_MASA_ESPERADA \
            or c.get("tolerancia_relativa") != TOLERANCIA_MASA_NATIVA:
        raise ValueError("Contraste de masa nativa inválido.")
    if not isinstance(lb, dict) or set(lb) != {"masa_total_kn_s2_m", "contribuciones_kn_s2_m"} or lb["masa_total_kn_s2_m"] != c.get("masa_libro_kn_s2_m"):
        raise ValueError("Libro de masa del informe inválido.")
    numeros = [lb["masa_total_kn_s2_m"], *lb["contribuciones_kn_s2_m"].values(), c.get("masa_observada_U1"), c.get("masa_observada_U2")]
    if any(type(v) not in (int, float) or not math.isfinite(v) for v in numeros):
        raise ValueError("Masa nativa con valores no finitos.")
    if abs(math.fsum(lb["contribuciones_kn_s2_m"].values()) - lb["masa_total_kn_s2_m"]) > 1e-9 * max(1.0, lb["masa_total_kn_s2_m"]):
        raise ValueError("Total del libro de masa alterado.")
    if 'estimacion_auto' in value:
        from .estimacion_masa_auto import validar
        validar(value['estimacion_auto'], lb, c)


def _masa_nativa(fuente, resultados, evidencia):
    """fuente = {"raiz", "caso", "lectura_id"}: lectura en lecturas_analisis del caso; el libro se recalcula del modelo analizado."""
    if fuente is None:
        return None
    estimar = isinstance(fuente, dict) and fuente.get('estimar_auto') is True
    if isinstance(fuente, dict) and 'estimar_auto' in fuente:
        if fuente['estimar_auto'] is not True:
            raise ValueError('La estimación opcional requiere true; omite el campo si no se selecciona.')
        fuente = {k:v for k,v in fuente.items() if k != 'estimar_auto'}
    if evidencia is None:
        raise ValueError("La masa nativa exige evidencia de análisis.")
    web = isinstance(fuente, dict) and set(fuente) == {"app", "caso", "expediente_sha256", "trabajo", "lectura_id", "sha256_respuesta"}
    if not isinstance(fuente, dict) or (not web and set(fuente) != {"raiz", "caso", "lectura_id"}) or fuente["caso"] != resultados["caso_id"]:
        raise ValueError("Fuente de masa nativa inválida.")
    from . import gestion_geometria as ggm
    from . import libro_masa as lbm
    from . import liquidos_malla as lmq
    from . import malla_preparacion as mpr
    from . import revision_modelo as rmod
    from .validacion_geometria import validar_geometria as vgeo
    if web:
        app = fuente["app"]
        raiz = Path(app.raiz)
        verified = app.lecturas.captura_masa_para_informe(
            fuente["caso"], fuente["trabajo"], lectura_id=fuente["lectura_id"],
            sha256_respuesta=fuente["sha256_respuesta"],
            expediente_sha256=fuente["expediente_sha256"],
            analisis=evidencia["analisis"]["corrida_id"],
            sha256_edb=evidencia["analisis"]["sha256_edb_analizado"])
        acc, captura = verified["recibo"], verified["captura"]
        configuracion_auto = verified.get('configuracion_auto')
    else:
        raiz = Path(fuente["raiz"])
        import re
        if not isinstance(fuente["lectura_id"], str) or not re.fullmatch(r"[0-9a-f]{32}", fuente["lectura_id"]):
            raise ValueError("Identificador de lectura inválido.")
        carpeta = rmod.carpeta_caso(raiz, fuente["caso"]) / "lecturas_analisis" / fuente["lectura_id"]
        acc = json.loads((carpeta / "aceptacion_lectura.json").read_text(encoding="utf-8"))
        raw_resp = (carpeta / "respuesta.json").read_bytes()
        if (acc.get("aceptada") is not True or acc.get("modo") != "real"
                or acc.get("lectura_id") != fuente["lectura_id"]
                or hashlib.sha256(raw_resp).hexdigest() != acc.get("sha256_respuesta")):
            raise ValueError("Lectura de masa no aceptada, real o inalterada.")
        api = json.loads(raw_resp)["datos"]["resultados_api"]
        captura = api["AssembledJointMass"]
        configuracion_auto = api.get('ConfiguracionAuto')
    modelo = evidencia["modelo"]["modelo_id"]
    estado_modelo = rmod.consultar(raiz, fuente["caso"], modelo)
    config = json.loads((rmod.carpeta_caso(raiz, fuente["caso"]) / "modelos_construidos" / modelo / "configuracion.json").read_text(encoding="utf-8"))
    geo = ggm.consultar_version(raiz, fuente["caso"], config["geometria_origen"]["version_id"]).geometria
    prep = mpr.preparar_malla(geo, config)
    liq = lmq.preparar_liquidos(geo, config, prep) if (config.get("liquidos") or {}).get("aplicabilidad") == "presente" else None
    libro = lbm.libro_masa(config, vgeo(geo), prep, liq)
    contraste = lbm.contrastar_masa_nativa(captura, libro, capture_id=fuente["lectura_id"], fuente_esperada=FUENTE_MASA_ESPERADA,
                                           tolerancia_relativa=TOLERANCIA_MASA_NATIVA)
    value = {"caso_id": resultados["caso_id"], "lectura_id": fuente["lectura_id"], "sha256_respuesta": acc["sha256_respuesta"],
             "corrida_analisis_id": acc["corrida_analisis_id"], "sha256_edb": acc["sha256_edb"],
             "libro": {"masa_total_kn_s2_m": libro["masa_total_kn_s2_m"],
                       "contribuciones_kn_s2_m": {k: v["masa_kn_s2_m"] for k, v in libro["contribuciones"].items()}},
             "contraste": contraste}
    if estimar:
        if configuracion_auto is None:
            raise ValueError('La estimación requiere una lectura que solicite ConfiguracionAuto junto con AssembledJointMass.')
        from .estimacion_masa_auto import crear
        plan_path = rmod.carpeta_caso(raiz, fuente['caso']) / 'modelos_construidos' / modelo / 'plan.json'
        plan = json.loads(plan_path.read_text(encoding='utf-8'))
        if plan.get('huella_plan') != estado_modelo['origen']['huella_plan']:
            raise ValueError('El plan del modelo analizado cambió.')
        value['estimacion_auto'] = crear(plan, config, libro, configuracion_auto, captura,
            lectura=fuente['lectura_id'],fuente=FUENTE_MASA_ESPERADA,tolerancia=TOLERANCIA_MASA_NATIVA)
    _validar_masa_nativa(value, resultados, evidencia)
    return value


def _contenido_masa(fuente, resultados, evidencia):
    """Deriva el inventario del plan registrado del MODELO ANALIZADO (fuente = {"raiz", "caso"}); None si no hay fuente."""
    if fuente is None:
        return None
    if evidencia is None:
        raise ValueError("El contenido de masa exige evidencia de análisis.")
    if not isinstance(fuente, dict) or set(fuente) != {"raiz", "caso"} or fuente["caso"] != resultados["caso_id"]:
        raise ValueError("Fuente del contenido de masa inválida.")
    from . import revision_modelo as rmod
    modelo = evidencia["modelo"]["modelo_id"]
    estado = rmod.consultar(Path(fuente["raiz"]), fuente["caso"], modelo)   # revalida plan/config/geometría/EDB del modelo
    carpeta = rmod.carpeta_caso(Path(fuente["raiz"]), fuente["caso"]) / "modelos_construidos" / modelo
    plan = json.loads((carpeta / "plan.json").read_text(encoding="utf-8"))
    if plan.get("huella_plan") != estado["origen"].get("huella_plan") or "contenido_masa" not in plan:
        raise ValueError("El plan del modelo analizado no contiene inventario de contenido vigente.")
    value = {"caso_id": resultados["caso_id"], "modelo_id": modelo, "huella_plan": plan["huella_plan"],
             "inventario": copy.deepcopy(plan["contenido_masa"])}
    _validar_contenido_masa(value, resultados, evidencia)
    return value
REF_TIPOS = ("evaluacion", "recuperacion", "sitio")
CAMPOS_EXPLICACION = {"trabajo", "estado_trabajo", "huella_salida", "modo", "causa", "generacion_llm_real",
                      "modo_transporte", "modelo_declarado", "declaraciones", "abstenciones",
                      "limites_verificables", "estado_revision"}
PENDIENTE_HUMANA = "propuesta_pendiente_revision_humana"


def _hex(valor, n):
    return isinstance(valor, str) and len(valor) == n and all(c in "0123456789abcdef" for c in valor)


SIGNIFICADO_SITIO = {
    "limite": "FRANJA INCIERTA: el punto está en el borde o dentro de la franja compatible con la precisión declarada; NO confirma pertenencia a ninguna zona.",
    "ambiguo": "AMBIGUO: pertenencia puntual a varias zonas; no se asigna una zona.",
    "sin_cobertura": "SIN COBERTURA: fuera de las zonas y de sus franjas de proximidad; no se asigna zona por cercanía.",
    "dentro": "Pertenencia puntual sin frontera próxima según la precisión declarada; no es certeza territorial, estudio de suelos ni parámetro geotécnico.",
}


def _validar_contexto_verificado(cv, reglas, fuentes, contexto):
    """Referencias exactas a derivados comprobados por el servicio; aquí se exige coherencia con el contenido."""
    if not isinstance(cv, dict) or set(cv) != set(REF_TIPOS):
        raise ValueError("contexto_verificado requiere evaluacion, recuperacion y sitio (objeto o null).")
    for tipo in REF_TIPOS:
        ref = cv[tipo]
        if ref is None:
            continue
        if (not isinstance(ref, dict) or set(ref) != {"id", "sha256_salida", "fuentes"} or not _hex(ref["id"], 32)
                or not _hex(ref["sha256_salida"], 64) or not isinstance(ref["fuentes"], dict)):
            raise ValueError("Referencia de contexto verificado inválida.")
    def huella(tipo, clave):
        valor = cv[tipo]["fuentes"].get(clave)
        return valor.get("huella") if isinstance(valor, dict) else None
    if cv["evaluacion"] is not None and (reglas is None or huella("evaluacion", "reglas") != huella_declaracion(reglas)):
        raise ValueError("Las reglas del informe no corresponden a la evaluación referenciada.")
    if cv["recuperacion"] is not None and (fuentes is None or huella("recuperacion", "corpus") != fuentes["huella_corpus"]):
        raise ValueError("Las fuentes del informe no corresponden a la recuperación referenciada.")
    sitio = contexto["sitio"]
    if cv["sitio"] is not None and (sitio is None or huella("sitio", "sitio") != sitio["huella_capa"]):
        raise ValueError("El sitio del informe no corresponde al derivado referenciado.")
    return True


def _validar_explicacion(ex, resultados, evaluacion, fuentes):
    """Propuesta o contingencia ligada a cifras y citas exactas del propio informe; nunca conclusión aprobada."""
    if not isinstance(ex, dict) or set(ex) != CAMPOS_EXPLICACION:
        raise ValueError("Explicación de informe inválida.")
    if (not _hex(ex["trabajo"], 32) or not _hex(ex["huella_salida"], 64) or ex["estado_revision"] != PENDIENTE_HUMANA
            or ex["modo"] not in ("llm_verificado", "contingencia_deterministica") or type(ex["generacion_llm_real"]) is not bool
            or not _texto(ex["modelo_declarado"]) or not _lista_texto(ex["limites_verificables"])
            or not isinstance(ex["abstenciones"], list)):
        raise ValueError("Identidad o estado de la explicación inválidos.")
    for a in ex["abstenciones"]:
        if not isinstance(a, dict) or set(a) != {"tema", "motivo"} or not all(_texto(v) for v in a.values()):
            raise ValueError("Abstención de explicación inválida.")
    if ex["modo"] == "contingencia_deterministica":
        if ex["generacion_llm_real"] or ex["declaraciones"] is not None or not _texto(ex["causa"]):
            raise ValueError("La contingencia no puede presentarse como generación LLM.")
        return True
    if ex["causa"] is not None or not isinstance(ex["declaraciones"], list):
        raise ValueError("Explicación LLM inválida.")
    valores = {"R:" + r["id"]: (r["valor"], r["unidad"]) for r in resultados["resultados"]}
    valores |= {"E:" + ":".join((e["regla_id"], e["caso"], e["direccion"], e["ubicacion"])): (e["valor_evaluado"], e.get("unidad_resultado", e["unidad"]))
                for e in evaluacion["evaluaciones"]}
    citas = {c["fragmento_id"]: c["texto"] for c in (fuentes["citas"] if fuentes else [])}
    for d in ex["declaraciones"]:
        if (not isinstance(d, dict) or set(d) != {"id", "texto", "indicadores", "cifras", "citas", "estado"}
                or d["estado"] != PENDIENTE_HUMANA or not _texto(d["id"]) or not _texto(d["texto"])
                or not all(isinstance(d[k], list) for k in ("indicadores", "cifras", "citas"))
                or (not d["indicadores"] and not d["citas"])):
            raise ValueError("Declaración de explicación inválida o sin sustento.")
        if any(r not in valores for r in d["indicadores"]):
            raise ValueError("La explicación cita indicadores ausentes del informe.")
        for c in d["cifras"]:
            if (not isinstance(c, dict) or set(c) != {"indicador", "valor", "unidad"} or c["indicador"] not in d["indicadores"]
                    or type(c["valor"]) not in (int, float) or valores[c["indicador"]][0] is None
                    or float(c["valor"]) != float(valores[c["indicador"]][0]) or c["unidad"] != valores[c["indicador"]][1]):
                raise ValueError("Cifra de la explicación distinta del contrato vigente.")
        for c in d["citas"]:
            if not isinstance(c, dict) or set(c) != {"fragmento_id", "texto"} or citas.get(c["fragmento_id"]) != c["texto"]:
                raise ValueError("Cita de la explicación ausente de las fuentes verificadas del informe.")
    return True


def _validar_revision_resultados(revision, resultados, evidencia):
    """Coherencia del snapshot; su autenticidad/vigencia requiere consultar el servicio al usarlo."""
    from .revision_aprobacion_resultados import CONTRATO as RC, VERSION as RV, _bytes, _declaracion, ServicioRevisionResultados
    if not isinstance(revision, dict) or evidencia is None:
        raise ValueError("La revisión seleccionada requiere análisis explícito y snapshot válido.")
    try:
        body = {k: revision[k] for k in ('caso','resultado','analisis','expediente_sha256','huella_resultados','huella_evidencia')}
        body.update(revision['declaracion']); body['confirmacion_explicita'] = True
        _declaracion(body)
        record = {'contrato': RC, 'version': RV, 'id': revision['id'], 'creado_utc': revision['creado_utc'],
                  'declaracion': body, 'fuentes': revision['fuentes']}
        if revision != ServicioRevisionResultados._proyeccion(record, _bytes(record)):
            raise ValueError("Snapshot de revisión alterado.")
        from .evidencia_analisis import huella_evidencia
        source = revision['fuentes']
        if (revision['caso'] != resultados['caso_id'] or revision['resultado'] != evidencia['resultado']['id']
                or revision['analisis'] != evidencia['analisis']['corrida_id']
                or revision['huella_resultados'] != huella_resultados(resultados)
                or revision['huella_evidencia'] != huella_evidencia(evidencia)
                or source['evidencia'] != evidencia or source['datos_sinteticos'] is not resultados['datos_sinteticos']
                or any(source[k] != revision[k] for k in ('resultado','analisis','expediente_sha256','huella_resultados','huella_evidencia'))
                or any(source[k] != resultados[k] for k in ('unidades','casos','advertencias','omisiones'))
                or source['indicadores'] != resultados['resultados']
                or source['filas_omitidas'] != [r for r in resultados['resultados'] if r['valor'] is None]):
            raise ValueError("Revisión de otras fuentes o naturaleza.")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Snapshot de revisión inválido.") from exc
    return True


def _revision_resultados(fuente, resultados, evidencia):
    if fuente is None:
        return None
    if not isinstance(fuente, dict) or set(fuente) != {'app','caso','id','sha256_revision','expediente_sha256'}:
        raise ValueError("La revisión requiere una fuente viva del servicio, no un snapshot.")
    from .revision_aprobacion_resultados import ServicioRevisionResultados
    revision = ServicioRevisionResultados(fuente['app']).consultar(
        fuente['caso'], fuente['id'], expediente_sha256=fuente['expediente_sha256'])
    if revision['sha256_revision'] != fuente['sha256_revision']:
        raise ValueError("SHA de revisión distinto de la selección explícita.")
    _validar_revision_resultados(revision, resultados, evidencia)
    return revision


def _validar_controles_analisis(ctl, resultados, evidencia):
    """Coherencia de la proyección de controles con este resultado y análisis; su vigencia exige el servicio."""
    from .controles_analisis import CONTRATO as CC
    if not isinstance(ctl, dict) or evidencia is None:
        raise ValueError("Los controles seleccionados requieren análisis explícito.")
    try:
        c = ctl['contenido']; d = c['declaracion']
        if (ctl['vigente'] is not True or ctl['aprueba_resultados'] is not False or ctl['conformidad_normativa'] != 'no_evaluada'
                or c['contrato'] != CC or ctl['caso'] != resultados['caso_id'] or d['caso'] != ctl['caso']
                or ctl['analisis'] != evidencia['analisis']['corrida_id'] or d['corrida_analisis'] != ctl['analisis']
                or ctl['modelo']['sha256_edb'] != evidencia['analisis']['sha256_edb_analizado'] or d['modelo'] != ctl['modelo']
                or ctl['datos_sinteticos'] is not resultados['datos_sinteticos'] or d['datos_sinteticos'] is not ctl['datos_sinteticos']
                or not isinstance(c['controles'], list) or type(c['apto_proyeccion_controlado']) is not bool
                or any(v is not None for v in (src.get('bytes_base64') for src in c['fuentes'].values() if isinstance(src, dict)))):
            raise ValueError("Controles de otro análisis, modelo, caso o naturaleza.")
    except (KeyError, TypeError, AttributeError) as exc:
        raise ValueError("Proyección de controles inválida.") from exc
    return True


def _controles_analisis(fuente, resultados, evidencia):
    if fuente is None:
        return None
    if not isinstance(fuente, dict) or set(fuente) != {'app', 'caso', 'id', 'sha256_controles', 'expediente_sha256'}:
        raise ValueError("Los controles requieren una fuente viva del servicio, no un snapshot.")
    from .revision_controles import ServicioControles
    ctl = ServicioControles(fuente['app']).consultar(fuente['caso'], fuente['id'], expediente_sha256=fuente['expediente_sha256'])
    if ctl['sha256_controles'] != fuente['sha256_controles']:
        raise ValueError("SHA de controles distinto de la selección explícita.")
    _validar_controles_analisis(ctl, resultados, evidencia)
    return ctl


def _validar_relectura_modelo(value, resultados, evidencia):
    fields={'trabajo','id','sha256_registro','caso','expediente_sha256','analisis','modelo','huella_modelo',
            'sha256_edb','huella_plan','modo','datos_sinteticos','resultado','aprueba_modelo','autoriza_analisis','aprueba_resultados'}
    if not isinstance(value,dict) or set(value)!=fields or evidencia is None:
        raise ValueError('Relectura sin análisis explícito o contrato inválido.')
    r=value['resultado'];m=evidencia['modelo'];a=evidencia['analisis']
    if (not all(_hex(value[k],32) for k in ('trabajo','id','modelo','analisis'))
            or not all(_hex(value[k],64) for k in ('sha256_registro','expediente_sha256','huella_modelo','sha256_edb','huella_plan'))
            or value['caso']!=resultados['caso_id'] or value['datos_sinteticos'] is not resultados['datos_sinteticos']
            or value['modelo']!=m['modelo_id'] or value['huella_modelo']!=m['huella_modelo']
            or value['analisis']!=a['corrida_id'] or value['sha256_edb']!=a['sha256_entrada']
            or value['modo']!=a['modo'] or any(value[k] is not False for k in ('aprueba_modelo','autoriza_analisis','aprueba_resultados'))
            or not isinstance(r,dict) or r.get('sha256_edb')!=value['sha256_edb']
            or r.get('origen_plan',{}).get('huella_plan')!=value['huella_plan']
            or r.get('modo')!=value['modo'] or r.get('ejecutable') is not False
            or r.get('estado') not in ('verificado','discrepancias','incompleto')
            or type(r.get('verificado')) is not bool or type(r.get('verificacion_global_del_plan')) is not bool
            or not isinstance(r.get('cobertura_plan'),dict)):
        raise ValueError('Relectura ajena al modelo/EDB/plan/análisis del resultado.')


def _relectura_modelo(fuente,resultados,evidencia):
    if fuente is None:return None
    fields={'app','caso','expediente_sha256','trabajo','id','sha256_registro'}
    if not isinstance(fuente,dict) or set(fuente)!=fields:
        raise ValueError('Relectura requiere selección viva exacta, no un snapshot.')
    from . import vinculo_verificacion_modelo as vinculo
    job=fuente['app'].verificacion_modelo.consultar(fuente['caso'],fuente['trabajo'])
    if (job['estado']!='aceptado' or job['vigente'] is not True or job['lectura_comprobada'] is not True
            or job['verificacion_id']!=fuente['id'] or job['expediente_sha256']!=fuente['expediente_sha256']):
        raise ValueError('Trabajo de relectura sin evidencia vigente seleccionada.')
    proof=vinculo.consultar(fuente['app'].raiz,fuente['caso'],fuente['id'])
    if proof['sha256_registro']!=fuente['sha256_registro'] or proof['resultado']!=job['resultado']:
        raise ValueError('SHA o observaciones de otra relectura.')
    state,plan,_=vinculo._fuente(fuente['app'].raiz,fuente['caso'],proof['modelo'],proof['huella_modelo'])
    value={k:fuente[k] for k in ('trabajo','id','sha256_registro','caso','expediente_sha256')}
    value.update(analisis=evidencia['analisis']['corrida_id'] if evidencia else None,modelo=proof['modelo'],huella_modelo=proof['huella_modelo'],
        sha256_edb=state['origen']['sha256_modelo'],huella_plan=plan['huella_plan'],modo=proof['modo'],
        datos_sinteticos=state['origen']['datos_sinteticos'],resultado=proof['resultado'],aprueba_modelo=False,autoriza_analisis=False,aprueba_resultados=False)
    _validar_relectura_modelo(value,resultados,evidencia)
    return value


def crear_informe(resultados, reglas, contexto, *, evaluacion=None, geometria_archivo=None,
                  corpus=None, citas=None, evidencia_analisis=None, contexto_verificado=None, explicacion=None, fuente_revision_resultados=None,
                  fuente_controles_analisis=None,fuente_relectura_modelo=None, fuente_contenido_masa=None, fuente_masa_nativa=None):
    """Construir borrador; recomputa evaluación y comprueba las fuentes aportadas.

    `fuente_contenido_masa` (opcional): {"raiz", "caso"}; el inventario se toma del plan registrado del modelo de
    `evidencia_analisis` (liquidos.contenido, plan 0.5), nunca de un valor declarado.

    `evidencia_analisis` (opcional): {"raiz", "caso", "resultado", "corrida"}. Se revalida desde los ficheros
    y solo se acepta si corresponde exactamente a estos resultados. Sin ella, el estado sigue no disponible.
    `contexto_verificado` y `explicacion` (opcionales) los arma el servicio desde derivados y trabajos
    comprobados; aquí se exige su coherencia con reglas, fuentes, sitio y cifras del propio informe.
    """
    if explicacion is not None and contexto_verificado is None:
        raise ValueError("Una explicación requiere referencias de contexto verificado.")
    contexto = _contexto(contexto)
    calculada = _evaluar(resultados, reglas)
    if evaluacion is not None and evaluacion != calculada:
        raise ValueError("Evaluación alterada u obsoleta: no corresponde a resultados/reglas vigentes.")
    geometria = _geometria(geometria_archivo, resultados)
    fuentes = _fuentes(corpus, citas, resultados)
    if contexto["sitio"] and contexto["sitio"]["datos_sinteticos"] and not resultados["datos_sinteticos"]:
        raise ValueError("Un sitio sintético no sustenta resultados declarados reales.")
    evidencia = _evidencia(evidencia_analisis, resultados)
    revision_resultados = _revision_resultados(fuente_revision_resultados, resultados, evidencia)
    controles_analisis = _controles_analisis(fuente_controles_analisis, resultados, evidencia)
    relectura_modelo = _relectura_modelo(fuente_relectura_modelo,resultados,evidencia)
    contenido_masa = _contenido_masa(fuente_contenido_masa, resultados, evidencia)
    masa_nativa = _masa_nativa(fuente_masa_nativa, resultados, evidencia)
    informe = {"contrato": CONTRATO, "version_contrato": VERSION,
            "caso_id": resultados["caso_id"], "corrida_id": resultados["corrida_id"],
            "motor": copy.deepcopy(resultados["motor"]), "datos_sinteticos": resultados["datos_sinteticos"],
            "contexto": contexto, "resultados": copy.deepcopy(resultados), "reglas": copy.deepcopy(reglas),
            "evaluacion": calculada, "geometria": geometria, "fuentes": fuentes,
            "huellas": _huellas(resultados, reglas, calculada, evidencia,
                                {k: v for k, v in (("contexto_verificado", contexto_verificado),
                                                   ("explicacion", explicacion), ("revision_resultados", revision_resultados),
                                                   ("controles_analisis", controles_analisis),("relectura_modelo", relectura_modelo),
                                                   ("contenido_masa", contenido_masa), ("masa_nativa", masa_nativa)) if v is not None}),
            "siete_resultados": _siete(resultados, calculada, geometria, contexto, evidencia),
            "aviso": AVISO, "revision": {"estado": "borrador", "aprobacion": None}}
    if evidencia is not None:  # sin evidencia, el informe conserva exactamente su forma anterior
        informe["evidencia_analisis"] = evidencia
    if contexto_verificado is not None:
        _validar_contexto_verificado(contexto_verificado, reglas, fuentes, contexto)
        informe["contexto_verificado"] = copy.deepcopy(contexto_verificado)
    if explicacion is not None:
        _validar_explicacion(explicacion, resultados, calculada, fuentes)
        informe["explicacion"] = copy.deepcopy(explicacion)
    if revision_resultados is not None:
        informe["revision_resultados"] = copy.deepcopy(revision_resultados)
        if _revision_resultados(fuente_revision_resultados, resultados, _evidencia(evidencia_analisis, resultados)) != revision_resultados:
            raise ValueError("La revisión cambió al crear el informe.")
    if controles_analisis is not None:
        informe["controles_analisis"] = copy.deepcopy(controles_analisis)
        if _controles_analisis(fuente_controles_analisis, resultados, _evidencia(evidencia_analisis, resultados)) != controles_analisis:
            raise ValueError("Los controles cambiaron al crear el informe.")
    if contenido_masa is not None:
        informe["contenido_masa"] = copy.deepcopy(contenido_masa)
    if masa_nativa is not None:
        informe["masa_nativa"] = copy.deepcopy(masa_nativa)
    if relectura_modelo is not None:
        informe['relectura_modelo']=copy.deepcopy(relectura_modelo)
        if _relectura_modelo(fuente_relectura_modelo,resultados,_evidencia(evidencia_analisis,resultados))!=relectura_modelo:
            raise ValueError('La relectura cambió al crear el informe.')
    return informe


def validar_informe(informe):
    """Recalcular cifras/secciones; la aprobación es propia, ligada al contenido."""
    campos = {"contrato", "version_contrato", "caso_id", "corrida_id", "motor", "datos_sinteticos",
              "contexto", "resultados", "reglas", "evaluacion", "geometria", "fuentes", "huellas",
              "siete_resultados", "aviso", "revision"}
    extra = set(informe) - campos if isinstance(informe, dict) else set()
    if (not isinstance(informe, dict) or not campos <= set(informe)
            or not extra <= {"evidencia_analisis", *OPCIONALES}
            or ("explicacion" in extra and "contexto_verificado" not in extra)):
        raise ValueError("Contrato de informe inválido.")
    if informe["contrato"] != CONTRATO or informe["version_contrato"] != VERSION or informe["aviso"] != AVISO:
        raise ValueError("Contrato/versión/aviso de informe alterados.")
    contexto = _contexto(informe["contexto"])
    resultados, reglas = informe["resultados"], informe["reglas"]
    calculada = _evaluar(resultados, reglas)
    if calculada != informe["evaluacion"]:
        raise ValueError("Evaluación de informe no corresponde al contenido vigente.")
    evidencia = informe.get("evidencia_analisis")
    if "evidencia_analisis" in informe:
        from .evidencia_analisis import validar_evidencia
        validar_evidencia(evidencia, resultados)
    if "revision_resultados" in informe:
        _validar_revision_resultados(informe["revision_resultados"], resultados, evidencia)
    if "controles_analisis" in informe:
        _validar_controles_analisis(informe["controles_analisis"], resultados, evidencia)
    if 'relectura_modelo' in informe:
        _validar_relectura_modelo(informe['relectura_modelo'],resultados,evidencia)
    if "contenido_masa" in informe:
        _validar_contenido_masa(informe["contenido_masa"], resultados, evidencia)
    if "masa_nativa" in informe:
        _validar_masa_nativa(informe["masa_nativa"], resultados, evidencia)
    expected = _huellas(resultados, reglas, calculada, evidencia, {k: informe[k] for k in OPCIONALES if k in informe})
    if informe["huellas"] != expected:
        raise ValueError("Huellas del informe no corresponden a las entradas.")
    if any(informe[k] != resultados[k] for k in ("caso_id", "corrida_id", "motor", "datos_sinteticos")):
        raise ValueError("Identidad/motor/naturaleza del informe alterados.")
    geometria = informe["geometria"]
    if geometria is not None:
        if (not isinstance(geometria, dict) or set(geometria) != {"datos", "sha256_archivo", "version_id_declarada"}
                or geometria["sha256_archivo"] != resultados["geometria"]["sha256"]
                or geometria["version_id_declarada"] != resultados["geometria"]["id"]
                or not validar_geometria(geometria["datos"]).consistente):
            raise ValueError("Geometría de informe inválida.")
    if informe["siete_resultados"] != _siete(resultados, calculada, geometria, contexto, evidencia):
        raise ValueError("Las cifras/secciones del informe no corresponden a sus contratos.")
    fuentes = informe["fuentes"]
    if fuentes is not None:
        from .fuentes import huella_corpus
        campos_fuente = {"huella_corpus","datos_sinteticos","corpus","citas","fragmentos","documentos"}
        if not isinstance(fuentes,dict) or set(fuentes) != campos_fuente:
            raise ValueError("Fuentes de informe inválidas.")
        corpus = fuentes["corpus"]
        if fuentes["huella_corpus"] != huella_corpus(corpus) or fuentes["datos_sinteticos"] != corpus["datos_sinteticos"]:
            raise ValueError("Huella de fuentes alterada.")
        if not isinstance(fuentes["citas"],list):
            raise ValueError("Citas inválidas.")
        fragmentos = {f["id"]:f for f in corpus["fragmentos"]}
        ids = []
        for cita in fuentes["citas"]:
            if (not isinstance(cita,dict) or set(cita) != {"fragmento_id","texto"}
                    or cita["fragmento_id"] not in fragmentos or cita["texto"] != fragmentos[cita["fragmento_id"]]["texto"]):
                raise ValueError("Cita no corresponde al fragmento del corpus.")
            ids.append(cita["fragmento_id"])
        esperado_f = [f for f in corpus["fragmentos"] if f["id"] in ids]
        esperado_d = [d for d in corpus["documentos"] if any(f["documento"] == d["id"] for f in esperado_f)]
        if len(ids) != len(set(ids)) or fuentes["fragmentos"] != esperado_f or fuentes["documentos"] != esperado_d:
            raise ValueError("Selección de fuentes alterada.")
    if "contexto_verificado" in informe:
        _validar_contexto_verificado(informe["contexto_verificado"], reglas, fuentes, contexto)
    if "explicacion" in informe:
        _validar_explicacion(informe["explicacion"], resultados, calculada, fuentes)
    revision = informe["revision"]
    if revision != {"estado": "borrador", "aprobacion": None} and not aprobacion_vigente(informe):
        raise ValueError("Aprobación documental de informe ausente o desactualizada.")
    return True


def aprobar_informe(informe, *, revisor_declarado, fecha, motivo):
    """Aprobación DOCUMENTAL explícita; no hereda revisión de geometría/reglas."""
    validar_informe(informe)
    if not all(_texto(v) for v in (revisor_declarado, motivo)) or not isinstance(fecha, str) or len(fecha) != 10:
        raise ValueError("Aprobación requiere revisor, fecha ISO y motivo explícitos.")
    date.fromisoformat(fecha)
    copia = copy.deepcopy(informe)
    copia["revision"] = {"estado": "aprobado", "aprobacion": {
        "revisor_declarado": revisor_declarado, "fecha": fecha, "motivo": motivo,
        "alcance": "Revisión documental declarada del informe; identidad no autenticada. No certifica seguridad.",
        "huella_contenido": huella_declaracion(copia)}}
    return copia


def _e(valor):
    return html.escape(str(valor), quote=True)


def _p(valor, clase=""):
    return f'<p class="{clase}">{_e(valor)}</p>'


def _lista(valores):
    return "<ul>" + "".join("<li>" + _e(x) + "</li>" for x in valores) + "</ul>" if valores else _p("No disponible / no declarado.", "muted")


def _tabla(cabeceras, filas):
    return ('<table><thead><tr>'+''.join('<th>'+_e(x)+'</th>' for x in cabeceras)+'</tr></thead><tbody>'
            + ''.join('<tr>'+''.join('<td>'+_e(x)+'</td>' for x in fila)+'</tr>' for fila in filas)+'</tbody></table>')


def _filas(filas):
    if not filas:
        return _p("No disponible: no se proporcionaron resultados para esta categoría.", "muted")
    salida = '<table><tr><th>ID / caso</th><th>Dirección / ubicación</th><th>Valor</th><th>Unidad</th></tr>'
    for fila in filas:
        valor = "No disponible: " + fila.get("motivo_omision", "sin dato") if fila["valor"] is None else str(fila["valor"])
        salida += "<tr>" + "".join("<td>" + _e(x) + "</td>" for x in (
            fila["id"] + " / " + fila["caso"], fila["direccion"] + " / " + fila["ubicacion"], valor, fila["unidad"])) + "</tr>"
    return salida + "</table>"


def _grupo_corto(contenido):
    # No anidar tablas para mantener secciones juntas: Story puede omitir el
    # bloque intermedio cuando una celda con otra tabla cruza de página. Para
    # PDF, el vínculo título/contenido lo verifica _story_paginada.
    return '<div style="page-break-inside:avoid">' + contenido + '</div>'


CSS = """
body { font-family: sans-serif; font-size: 10pt; color: #243447; line-height: 1.3; }
h1 { font-size: 23pt; color: #123f54; margin-bottom: 8pt; }
h2 { font-size: 14pt; color: #123f54; margin-top: 18pt; }
h3 { font-size: 11pt; color: #123f54; margin-top: 12pt; }
h1, h2, h3 { page-break-after: avoid; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; font-size: 9pt; }
td, th { border: 0.5pt solid #b8c8d2; padding: 6pt; text-align: left; }
th { font-weight: bold; color: #123f54; } .banner { color: #79520a; padding: 10pt; font-weight: bold; }
.muted { color: #566976; } .hash { font-size: 8pt; font-family: monospace; }
@media screen { body { max-width: 900px; margin: 35px auto; padding: 0 20px; } }
"""


def renderizar_html(informe):
    validar_informe(informe)
    c, siete = informe["contexto"], informe["siete_resultados"]
    cuerpo = "<h1>" + _e(c["titulo"]) + "</h1>"
    etiqueta = ("SIMULACIÓN" if informe["motor"]["tipo"] == "simulacion" else "MOTOR REAL DECLARADO")
    etiqueta += " / " + ("DATOS SINTÉTICOS" if informe["datos_sinteticos"] else "DATOS REALES DECLARADOS")
    cuerpo += _p(etiqueta + " · INFORME " + informe["revision"]["estado"].upper(), "banner")
    cuerpo += _p(f'Caso: {informe["caso_id"]} · Corrida: {informe["corrida_id"]}')
    motor = informe["motor"]
    cuerpo += _p(f'Motor declarado: {motor["tipo"]} / {motor["nombre"]} / versión {motor["version"]}. Productor no autenticado.')
    cuerpo += _p(AVISO, "muted")
    cuerpo += "<h2>Hipótesis e información pendiente</h2><h3>Hipótesis declaradas</h3>" + _lista(c["hipotesis"])
    cuerpo += "<h3>Faltantes de contexto</h3>" + _lista(c["faltantes"])
    cuerpo += "<h2>1. Estado de generación y análisis</h2>" + _p(siete["estado_modelo_analisis"]["motivo"])
    evidencia = informe.get("evidencia_analisis")
    if evidencia is None:
        cuerpo += _p("Estado de generación: no disponible. Estado del solver: no disponible.")
    else:
        a, m, r = evidencia["analisis"], evidencia["modelo"], evidencia["resultado"]
        estado_revision = "ESTADO NATIVO PENDIENTE / REVISIÓN DECLARADA SEPARADA" if "revision_resultados" in informe else "RESULTADOS NO REVISADOS"
        cuerpo += _p("EVIDENCIA DE ANÁLISIS REVALIDADA · CÁLCULO COMPLETADO · " + estado_revision + " · CONFORMIDAD NO EVALUADA", "banner")
        cuerpo += _lista([
            "Estado de generación: modelo construido " + m["modelo_id"] + " con revisión declarada " + m["aprobacion_id"]
            + " (identidad del revisor no verificada).",
            "Estado del solver: " + ", ".join(c["id"] + " = estado CSI " + str(c["estado_csi"]) + " (terminado)" for c in a["casos"])
            + "; análisis " + a["corrida_id"] + " aceptado, modo " + a["modo"] + ", ETABS " + a["version_etabs"] + ".",
            "Vínculo: el resultado " + r["id"] + " se leyó (corrida de tablas " + r["corrida_tablas_id"] + ") del mismo EDB analizado.",
            "Revisión de resultados: " + evidencia["estados"]["revision_resultados"] + ". Conformidad normativa: "
            + evidencia["estados"]["conformidad_normativa"] + ".",
        ])
        cuerpo += _p(evidencia["aviso"], "muted")
    if "revision_resultados" in informe:
        rr = informe['revision_resultados']; d = rr['declaracion']
        cuerpo += "<h3>Revisión DECLARADA de resultados seleccionada</h3>"
        cuerpo += _p("Estado separado: revisados_declarados. El estado nativo de resultados y evidencia permanece pendiente.")
        cuerpo += _lista(["Origen: revisión " + rr['id'] + "; SHA256 " + rr['sha256_revision'],
                          "Resultado: " + rr['resultado'] + "; análisis: " + rr['analisis'],
                          "Revisor declarado: " + d['revisor_declarado'] + "; fecha: " + d['fecha'],
                          "Alcance declarado: " + d['alcance'], "Motivo: " + d['motivo'],
                          "Controles declarados: " + ", ".join(d['controles']),
                          "Faltantes críticos declarados: [] (lista explícita vacía; no acredita completitud)."])
        cuerpo += "<h3>Observaciones de quien declara la revisión</h3>" + _lista(d['observaciones'])
        cuerpo += "<h3>Advertencias y omisiones nativas conservadas</h3>" + _lista(rr['fuentes']['advertencias'] + rr['fuentes']['omisiones'])
        cuerpo += _p(rr['aviso'] + " No hay verificación profesional, conformidad normativa ni seguridad certificada.", "muted")
    if "controles_analisis" in informe:
        ca = informe["controles_analisis"]; cc = ca["contenido"]
        cuerpo += "<h3>Controles internos postsolver seleccionados</h3>"
        cuerpo += _p(("APTO" if cc["apto_proyeccion_controlado"] else "NO APTO") + " para proyectar «controlado» según criterios DECLARADOS · estado global "
                     + cc["estado_global"] + " · CSI 4 solo indica terminación del motor · no certifica normativa ni seguridad"
                     + (" · DATOS SINTÉTICOS fabricados" if ca["datos_sinteticos"] else ""), "banner")
        cuerpo += _lista(["Controles " + ca["id"] + "; SHA256 " + ca["sha256_controles"] + "; lectura " + ca["lectura"] + "; análisis " + ca["analisis"],
                          "Revisor declarado: " + cc["declaracion"]["revisor_declarado"] + "; fecha: " + cc["declaracion"]["fecha"]
                          + "; alcance: " + cc["declaracion"]["alcance"]]
                         + [r["id"] + " · " + r["tipo"] + " · " + r["estado"] + " · " + r["base_datos"] + " (" + r["verificacion"] + ")"
                            + (" · " + r["formula"] if r["formula"] else "") + (" · valores " + json.dumps(r["valores"], ensure_ascii=False) if r["valores"] is not None else "")
                            + " · " + " | ".join(r["motivos"]) for r in cc["controles"]]
                         + ["Faltantes críticos: " + (", ".join(cc["faltantes_criticos"]) or "ninguno"),
                            "Controles solo declarados (no verificados): " + (", ".join(cc["controles_solo_declarados"]) or "ninguno"),
                            "Avisos del lector (no son log del solver): " + (" | ".join(cc["avisos_lector"]) or "ninguno"),
                            "Advertencias del solver declaradas: " + ("sin fuente aportada" if cc["advertencias_solver"] is None
                                else (" | ".join(w["codigo"] + ": " + w["texto"] for w in cc["advertencias_solver"]) or "ninguna"))])
    if "masa_nativa" in informe:
        mn = informe["masa_nativa"]; contraste_masa = mn["contraste"]
        cuerpo += "<h3>Masa ensamblada nativa (ETABS) frente al libro de contribuciones</h3>"
        cuerpo += _p(("COHERENTE" if contraste_masa["estado"] == "coherente" else "NO COHERENTE (" + str(contraste_masa.get("codigo")) + ")")
                     + f" · libro {mn['libro']['masa_total_kn_s2_m']:.4f} kN·s²/m · observada U1 {contraste_masa['masa_observada_U1']:.4f} / U2 "
                     f"{contraste_masa['masa_observada_U2']:.4f} · tolerancia relativa {contraste_masa['tolerancia_relativa']} · fuente {contraste_masa['fuente_esperada']}. "
                     "Captura AssembledJointMass_1 del EDB analizado; no es hidrodinámica ni aprobación de ingeniería.", "banner")
        cuerpo += _lista([f"{k}: {v:.4f} kN·s²/m" for k, v in mn["libro"]["contribuciones_kn_s2_m"].items()]
                         + ["Lectura " + mn["lectura_id"] + " · análisis " + mn["corrida_analisis_id"] + " · EDB " + mn["sha256_edb"][:16] + "…"])
        if 'estimacion_auto' in mn:
            ea = mn['estimacion_auto']
            cuerpo += '<h3>Estimación independiente de peso efectivo por extremos de vigas</h3>'
            cuerpo += _p('El libro bruto y su contraste anterior se conservan. Este cálculo experimental usa la geometría del plan y la configuración leída del mismo EDB; no usa los offsets del solver como entradas ni aprueba ingeniería.')
            if ea['estado'] == 'estimado':
                cuerpo += _p(f"Bruto {ea['masa_bruta_kn_s2_m']:.6f} · descuento de peso {ea['descuento_peso_kn']:.6f} kN · masa estimada {ea['masa_estimada_kn_s2_m']:.6f} kN·s²/m. Contraste con estimación: " + ea['contraste_estimado']['estado'].upper().replace('_',' ') + '. Criterio de tolerancia sin cambios.')
                cuerpo += _tabla(['Viga','Extremo I (m)','Extremo J (m)','Peso excluido (kN)'],
                    [[v['viga'],f"{v['offsets']['I']:.6f}",f"{v['offsets']['J']:.6f}",f"{v['descuento_peso']['kN']:.6f}"] for v in ea['prediccion']['vigas']])
            else:
                cuerpo += _p('No estimable: ' + '; '.join(ea['motivos']))
            cuerpo += _p('Plan '+ea['huella_plan']+' · tolerancia de unión '+ea['configuracion_capturada']['tolerancia_union_m']+' m · perfil ETABS '+ea['configuracion_capturada']['version_etabs']+'. Las reglas experimentales y abstenciones por viga se conservan en el JSON del informe.')
    if "contenido_masa" in informe:
        cm = informe["contenido_masa"]; inv = cm["inventario"]
        cuerpo += "<h3>Contenido de depósitos (masa declarada)</h3>"
        cuerpo += _p("Inventario coherente entre volumen, presión (Fz = −γV) y fuente de masa del plan " + cm["huella_plan"][:16]
                     + "… del modelo " + cm["modelo_id"] + ". " + (
                         ("Masa ensamblada en ETABS: captura nativa ligada al análisis incluida en la sección de masa nativa, con contraste "
                          + informe["masa_nativa"]["contraste"]["estado"].upper().replace("_", " ") + " frente al libro (control independiente "
                          "de este inventario).") if "masa_nativa" in informe else
                         "Masa ensamblada en ETABS: NO verificada (sin captura nativa ligada al análisis).")
                     + " No es hidrodinámica ni aprobación de ingeniería.", "banner")
        cuerpo += _lista(["Estados: " + ", ".join(f"{k}: {v}" for k, v in sorted(inv["estados"].items()))]
                         + [f"{f['deposito']} · {f['estado']} · V {f['volumen_m3']:.4f} m³ · W {f['peso_kn']:.3f} kN · Fz {f['fz_presion_kn']:.3f} kN"
                            f" · masa {f['masa_kn_s2_m']:.4f} kN·s²/m · patrón {f['patron_masa']} ({f['modo']}) · fuente {f['fuente']}"
                            for f in inv["escenarios"]]
                         + [f"Total: W {inv['peso_total_kn']:.3f} kN · masa {inv['masa_total_kn_s2_m']:.4f} kN·s²/m", inv["nota"]])
    if 'relectura_modelo' in informe:
        vm=informe['relectura_modelo']; r=vm['resultado']
        cuerpo += '<h3>Relectura seleccionada del modelo construido</h3>'
        cuerpo += _p('Estado '+r['estado']+' · modo '+vm['modo']+' · verificación global del plan: '+str(r['verificacion_global_del_plan'])
                     +' · evidencia conservada no equivale a aprobación del modelo ni de resultados.', 'banner')
        cuerpo += _lista(['Vínculo '+vm['id']+' · trabajo '+vm['trabajo']+' · SHA256 '+vm['sha256_registro'],
                          'Modelo '+vm['modelo']+' · huella '+vm['huella_modelo'],
                          'EDB construido/entrada al análisis '+vm['sha256_edb']+' · plan '+vm['huella_plan'],
                          'Análisis vinculado '+vm['analisis']+' · datos sintéticos: '+str(vm['datos_sinteticos'])])
        cuerpo += '<h4>Cobertura del plan</h4>'+_p(json.dumps(r['cobertura_plan'],ensure_ascii=False))
        for key in ('unidades','discrepancias','incompletos','ejes_sin_criterio','cobertura','controles_no_afirmados','fuera_de_alcance'):
            cuerpo += '<h4>'+_e(key)+'</h4>'+_p(json.dumps(r.get(key,[]),ensure_ascii=False))
        if isinstance(r.get('malla'),dict):  # plan 0.4: comprobación geométrica independiente desde lo leído
            cuerpo += '<h4>Malla 0.4 (cobertura '+_e(r.get('cobertura',{}).get('malla','sin dato'))+')</h4>'+_p(json.dumps(r['malla'],ensure_ascii=False))
            cuerpo += _p('Áreas, orientación, conformidad, nodos compartidos, subframes y resultantes recalculados desde lo leído. '
                         'No afirma masa propia por elemento, calidad/rigidez de malla ni efecto estructural del diafragma.','muted')
        cuerpo += _p('Lectura del snapshot construido, no del EDB posterior al análisis. Instancia independiente; sin guardar ni modificar. '
                     'Las tolerancias son criterios explícitos de lectura. Los controles sin criterio o cobertura incompleta no son verificación. '
                     'No certifica idealización, ingeniería, normativa ni seguridad.','muted')
    cuerpo += "<h2>2. Geometría y número de muros</h2>"
    g = siete["geometria_muros"]
    if "resumen_superficies" in g:   # 0.2/0.3: no presentar «Muros 0» como ausencia de muros (hallazgo 283)
        from .resumen_geometria import texto_resumen
        cuerpo += _p(texto_resumen(g["resumen_superficies"]) + f' Unidad: {g["unidad_longitud"]}')
    else:
        cuerpo += _p(f'Muros: {g["numero_muros"]} · Niveles incluidos: {g["numero_niveles"]} · Unidad: {g["unidad_longitud"]}'
                     if g["numero_muros"] is not None else "No disponible: no se aportó el archivo geométrico vinculado a la corrida.")
    if informe["geometria"]:
        cuerpo += "<h3>Faltantes geométricos</h3>" + _lista([f["descripcion"] for f in informe["geometria"]["datos"]["faltantes"]])
    for numero, titulo, clave in ((3,"Periodos seleccionados","periodos"),(4,"Derivas por nivel y dirección","derivas"),
                                  (5,"Cortante basal por dirección","cortante_basal")):
        bloque = f"<h2>{numero}. {titulo}</h2>" + _filas(siete[clave])
        cuerpo += _grupo_corto(bloque) if len(siete[clave]) <= 5 else bloque
    cuerpo += "<h2>6. Advertencias, omisiones y reglas configuradas</h2>" + _lista(siete["advertencias"]["declaradas"])
    cuerpo += "<h3>Omisiones declaradas del cálculo</h3>" + _lista(siete["advertencias"]["omisiones"])
    if informe['reglas'] is None:
        cuerpo += _p(informe['evaluacion']['motivo'])
    for regla in informe["evaluacion"]["evaluaciones"]:
        cuerpo += "<h3>" + _e(regla["regla_id"] + " / " + regla["caso"] + " / " + regla["direccion"] + " / " + regla["ubicacion"]) + "</h3>"
        ures = regla.get("unidad_resultado", regla["unidad"])   # salida de la fórmula y límite (290); entrada en su unidad
        cuerpo += _p(f'Estado: {regla["estado"]}; entrada: {regla["valor_entrada"]} {regla["unidad"]}; evaluado: {regla["valor_evaluado"]} {ures}; límite configurado: {regla["comparador"]} {regla["limite"]} {ures}.')
        cuerpo += _p(f'Fórmula: {regla["formula"]["factor"]} * x + {regla["formula"]["desplazamiento"]}; satisfacción de regla configurada: {regla["satisface_regla_configurada"]}.')
        if regla.get("motivo"):
            cuerpo += _p(regla["motivo"])
        f = regla["fuente"]
        cuerpo += _p(f'Fuente de regla DECLARADA: {f["titulo"]} · Edición: {f["edicion"]} · Apartado: {f["apartado"]} · Referencia: {f["referencia"]}. Página: no disponible en este contrato.', "muted")
    cuerpo += "<h2>7. Condición referencial del sitio</h2>"
    sitio = siete["sitio"]
    if sitio is None:
        cuerpo += _p("No disponible: no se aportó condición de sitio con fuente y localización verificadas.")
    else:
        ref_sitio = (informe.get("contexto_verificado") or {}).get("sitio")
        if ref_sitio is not None:
            cuerpo += _p("CONSULTA DE COBERTURA COMPROBADA por el derivado " + ref_sitio["id"] + " sobre la capa registrada (huella "
                         + sitio["huella_capa"][:16] + "…); ubicación declarada " + str(sitio["ubicacion"]["longitud"]) + ", "
                         + str(sitio["ubicacion"]["latitud"]) + " (EPSG:4326). Cobertura referencial, sin parámetros geotécnicos.", "banner")
        else:
            cuerpo += _p("DECLARACIÓN CONTEXTUAL; este generador no ejecuta ni verifica un cruce cartográfico.", "banner")
        f = sitio["fuente"]
        cuerpo += _p(f'Estado declarado: {sitio["estado"]}; precisión de fuente: {sitio["precision_m"]} m; fecha de fuente: {sitio["fecha_fuente"]}.')
        cuerpo += _p(SIGNIFICADO_SITIO[sitio["estado"]], "banner" if sitio["estado"] != "dentro" else "")
        cuerpo += _p("Zonas que impiden una clasificación concluyente (no es asignación territorial):" if sitio["estado"] == "limite"
                     else "Zonas con pertenencia puntual según la capa (no es certeza territorial):" if sitio["zonas"] else "Sin zonas.", "muted")
        cuerpo += _lista([z["etiqueta"] + " / " + z["posicion"] for z in sitio["zonas"]])
        cuerpo += _p(f'Fuente: {f["titulo"]} · Edición: {f["edicion"]} · Referencia: {f["referencia"]} · Página: no disponible en este contrato.')
        cuerpo += _p(sitio["aviso"])
    cuerpo += "<h2>Fuentes y citas verificadas</h2>"
    fuentes = informe["fuentes"]
    if fuentes and fuentes["fragmentos"]:
        docs = {d["id"]: d for d in fuentes["documentos"]}
        for f in fuentes["fragmentos"]:
            d = docs[f["documento"]]
            cuerpo += _p(f'{d["titulo"]} · Edición: {d["edicion"]} · Página: {f["pagina"]} · Apartado: {f["apartado"]} · Fragmento: {f["id"]}')
            cuerpo += _p(f["texto"])
    else:
        cuerpo += _p("No se aportaron citas verificadas de un corpus aprobado. No se emite una conclusión normativa.")
    explicacion = informe.get("explicacion")
    if explicacion is not None:
        cuerpo += "<h2>Explicación sustentada (propuesta pendiente de revisión humana)</h2>"
        if explicacion["modo"] == "llm_verificado":
            origen = "LLM REAL" if explicacion["generacion_llm_real"] else "TRANSPORTE DE PRUEBA, NO ES UNA LLAMADA REAL"
            cuerpo += _p("PROPUESTA DE TEXTO (" + origen + ") · CIFRAS Y CITAS VERIFICADAS POR SOFTWARE · "
                         "SENTIDO TÉCNICO PENDIENTE DE REVISIÓN HUMANA · NO ES CONCLUSIÓN NI CONFORMIDAD", "banner")
            cuerpo += _p("Modelo declarado: " + explicacion["modelo_declarado"] + " · trabajo " + explicacion["trabajo"], "muted")
            for d in explicacion["declaraciones"]:
                cuerpo += _p(d["id"] + ": " + d["texto"])
                cuerpo += _p("Indicadores: " + (", ".join(d["indicadores"]) or "ninguno") + " · Citas: "
                             + (", ".join(c["fragmento_id"] for c in d["citas"]) or "ninguna"), "muted")
        else:
            cuerpo += _p("CONTINGENCIA DETERMINÍSTICA (" + explicacion["causa"] + ") · NO ES GENERACIÓN LLM · "
                         "solo se muestran las cifras, reglas y citas verificadas de este informe.", "banner")
        cuerpo += "<h3>Abstenciones</h3>" + _lista([a["tema"] + ": " + a["motivo"] for a in explicacion["abstenciones"]])
        cuerpo += "<h3>Límites de lo verificable por software</h3>" + _lista(explicacion["limites_verificables"])
    cuerpo += "<h2>Trazabilidad y revisión</h2>"
    for nombre, huella in informe["huellas"].items():
        cuerpo += _p(nombre + ": " + " ".join(huella[i:i+16] for i in range(0,len(huella),16)), "hash")
    for nombre in ("geometria", "configuracion"):
        r = informe["resultados"][nombre]
        cuerpo += _p(nombre + " / " + r["id"], "hash")
        cuerpo += _p("SHA256: " + " ".join(r["sha256"][i:i+16] for i in range(0,64,16)), "hash")
    if evidencia is not None:
        a = evidencia["analisis"]
        for nombre, huella in (("EDB analizado", a["sha256_edb_analizado"]), ("Aceptación del análisis", a["sha256_aceptacion"]),
                               ("Respuesta de tablas", evidencia["resultado"]["sha256_respuesta_tablas"]),
                               ("Revisión del modelo", evidencia["modelo"]["sha256_aprobacion"])):
            cuerpo += _p(nombre + ": " + " ".join(huella[i:i+16] for i in range(0, 64, 16)), "hash")
    version_reglas=informe['reglas']['version_contrato'] if informe['reglas'] is not None else 'pendientes'
    cuerpo += _p(f'Informe {VERSION}; resultados {informe["resultados"]["version_contrato"]}; reglas {version_reglas}; evaluación {informe["evaluacion"]["version_contrato"]}.')
    cuerpo += _p("Aprobación documental propia: " + informe["revision"]["estado"] + ". No se hereda de la revisión de reglas, datos o modelo.")
    if informe["revision"]["aprobacion"]:
        a = informe["revision"]["aprobacion"]
        cuerpo += _p(f'Revisor declarado: {a["revisor_declarado"]}; fecha: {a["fecha"]}; motivo: {a["motivo"]}. {a["alcance"]}')
    return '<!doctype html><html lang="es"><head><meta charset="utf-8"><title>' + _e(c["titulo"]) + '</title><style>' + CSS + "</style></head><body>" + cuerpo + "</body></html>"


def _story_con_anclas(contenido_html, saltos):
    """Anclar cada cadena de títulos al primer párrafo, ítem o fila de datos.

    El renderer usado no respeta keep-with-next de CSS. Mantener el documento entero
    permite que sus tablas se paginen normalmente, sin tablas envolventes.
    """
    story = pymupdf.Story(html=contenido_html)
    grupos, titulos = [], []
    node = story.body.find(None, None, None)
    while node:
        etiqueta = node.tagname
        if etiqueta in ("h1", "h2", "h3"):
            titulos.append(node)
        elif titulos:
            fila_datos = False
            if etiqueta == "tr":
                hijo = node.first_child
                while hijo:
                    if hijo.tagname == "td":
                        fila_datos = True
                        break
                    hijo = hijo.next
            if etiqueta in ("p", "li") or fila_datos:
                numero = len(grupos)
                ids = []
                for indice, titulo in enumerate(titulos):
                    ident = f"d2m-titulo-{numero}-{indice}"
                    titulo.set_attribute("id", ident)
                    ids.append(ident)
                inicio = f"d2m-contenido-{numero}"
                node.set_attribute("id", inicio)
                if numero in saltos:
                    # Usar atributos explícitos evita add_style() en el binding
                    # 1.28.2: sin style previo puede tomar el valor de id.
                    style = titulos[0].get_attributes().get("style", "")
                    titulos[0].set_attribute("style", style.rstrip("; ") + (";" if style.strip() else "")
                                             + "page-break-before: always")
                grupos.append((ids, inicio))
                titulos = []
        node = node.find_next(None, None, None)
    return story, grupos


def _story_paginada(contenido_html, rectangulo):
    """Medir y resolver el primer título huérfano antes de escribir páginas.

    Cada pasada añade a lo sumo un salto, en orden documental. Los saltos
    posteriores se deciden tras recomponer lo anterior para evitar hojas extra.
    """
    saltos = set()
    while True:
        story, grupos = _story_con_anclas(contenido_html, saltos)
        paginas = {}
        def posicion(item):
            if item.id and item.open_close & 1:
                paginas.setdefault(item.id, item.page_num)
        story.write(None, rectangulo, positionfn=posicion)
        huerfano = None
        for numero, (titulos, contenido) in enumerate(grupos):
            if contenido not in paginas or any(titulo not in paginas for titulo in titulos):
                raise ValueError("La paginación no conservó todas las anclas del informe.")
            if any(paginas[titulo] != paginas[contenido] for titulo in titulos):
                huerfano = numero
                break
        if huerfano is None:
            # El DOM de Story se consume durante place/write. Crear otro con
            # las mismas anclas y saltos; reset() no restaura ese DOM editable.
            return _story_con_anclas(contenido_html, saltos)[0]
        if huerfano in saltos:
            raise ValueError("Título y primer contenido exceden juntos el área de una página.")
        saltos.add(huerfano)


def _pdf(contenido_html):
    buffer = io.BytesIO()
    pagina = pymupdf.paper_rect("a4")
    area = pymupdf.Rect(42,42,pagina.width-42,pagina.height-48)
    def rectangulo(numero, previo):
        if numero >= 200:
            raise ValueError("Informe supera 200 páginas.")
        return pagina, area, None
    story = _story_paginada(contenido_html, rectangulo)
    writer = pymupdf.DocumentWriter(buffer)
    try:
        story.write(writer, rectangulo)
    finally:
        writer.close()
    fuente_pie = pymupdf.Font("helv").buffer
    with pymupdf.open(stream=buffer.getvalue(),filetype="pdf") as doc:
        for i,p in enumerate(doc):
            p.insert_font(fontname="D2MPie",fontbuffer=fuente_pie)
            p.insert_text((42,pagina.height-25),f'Draft2Model | Informe preliminar | {i+1} / {len(doc)}',fontsize=8,color=(.3,.4,.45),fontname="D2MPie")
        doc.set_metadata({"title":"Draft2Model - Informe preliminar", "author":"Draft2Model", "subject":AVISO})
        return doc.tobytes(garbage=4,deflate=True)


def exportar_informe(informe, salida, *, geometria_archivo=None, corpus=None, evidencia_analisis=None, fuente_revision_resultados=None,
                     fuente_controles_analisis=None,fuente_relectura_modelo=None, fuente_contenido_masa=None, fuente_masa_nativa=None):
    """Crear paquete nuevo; validar cifras y volver a comprobar artefactos fuente."""
    validar_informe(informe)
    if informe.get("masa_nativa") != _masa_nativa(fuente_masa_nativa, informe["resultados"], informe.get("evidencia_analisis")):
        raise ValueError("La exportación requiere la masa nativa vigente del análisis.")
    if informe.get("contenido_masa") != _contenido_masa(fuente_contenido_masa, informe["resultados"], informe.get("evidencia_analisis")):
        raise ValueError("La exportación requiere el inventario de contenido vigente del modelo analizado.")
    if informe.get("evidencia_analisis") != _evidencia(evidencia_analisis, informe["resultados"]):
        raise ValueError("La exportación necesita la evidencia de análisis exacta del informe, revalidada desde sus ficheros.")
    revision_actual = _revision_resultados(fuente_revision_resultados, informe["resultados"], informe.get("evidencia_analisis"))
    if informe.get("revision_resultados") != revision_actual:
        raise ValueError("La exportación requiere la revisión seleccionada vigente desde su servicio.")
    controles_actuales = _controles_analisis(fuente_controles_analisis, informe["resultados"], informe.get("evidencia_analisis"))
    if informe.get("controles_analisis") != controles_actuales:
        raise ValueError("La exportación requiere los controles seleccionados vigentes desde su servicio.")
    relectura_actual=_relectura_modelo(fuente_relectura_modelo,informe['resultados'],informe.get('evidencia_analisis'))
    if informe.get('relectura_modelo')!=relectura_actual:
        raise ValueError('La exportación requiere la relectura seleccionada vigente.')
    salida = Path(salida)
    if salida.exists():
        raise ValueError("Salida existente; no se sobrescribe.")
    if informe["geometria"] != _geometria(geometria_archivo,informe["resultados"]):
        raise ValueError("La exportación necesita el archivo geométrico exacto del informe.")
    fuentes = informe["fuentes"]
    verificadas = _fuentes(corpus,fuentes["citas"] if fuentes else None,informe["resultados"])
    if fuentes != verificadas:
        raise ValueError("Fuentes alteradas u obsoletas; regenerar informe.")
    contenido_html = renderizar_html(informe)
    contenido_pdf = _pdf(contenido_html)
    contenido_json = (json.dumps(informe,ensure_ascii=False,indent=2,allow_nan=False)+"\n").encode("utf-8")
    if revision_actual is not None and _revision_resultados(fuente_revision_resultados, informe["resultados"], _evidencia(evidencia_analisis, informe["resultados"])) != revision_actual:
        raise ValueError("La revisión cambió durante la exportación.")
    if controles_actuales is not None and _controles_analisis(fuente_controles_analisis, informe["resultados"], _evidencia(evidencia_analisis, informe["resultados"])) != controles_actuales:
        raise ValueError("Los controles cambiaron durante la exportación.")
    if relectura_actual is not None and _relectura_modelo(fuente_relectura_modelo,informe['resultados'],_evidencia(evidencia_analisis,informe['resultados']))!=relectura_actual:
        raise ValueError('La relectura cambió durante la exportación.')
    salida.mkdir()
    (salida/"informe.json").write_bytes(contenido_json)
    (salida/"informe.html").write_bytes(contenido_html.encode("utf-8"))
    (salida/"informe.pdf").write_bytes(contenido_pdf)
    return salida


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for nombre in ("resultados","contexto","salida"):
        parser.add_argument("--"+nombre,required=True,type=Path)
    parser.add_argument('--reglas',type=Path,help='Reglas revisadas; sin ellas se exporta evaluación pendiente')
    for nombre in ("evaluacion","geometria","corpus","citas"):
        parser.add_argument("--"+nombre,type=Path)
    parser.add_argument("--analisis-raiz",type=Path,help="Evidencia de análisis: raíz privada del expediente")
    parser.add_argument("--analisis-caso",help="Evidencia de análisis: caso")
    parser.add_argument("--analisis-resultado",help="Evidencia de análisis: id en resultados_estructurales")
    parser.add_argument("--analisis-corrida",type=Path,help="Evidencia de análisis: carpeta de la corrida aceptada")
    parser.add_argument("--contenido-masa",action="store_true",help="Incluir el inventario de contenido del plan del modelo analizado")
    parser.add_argument("--masa-nativa-lectura",help="Id de la lectura AssembledJointMass aceptada (lecturas_analisis) del mismo análisis")
    parser.add_argument('--estimar-auto',action='store_true',help='Añadir estimación independiente; exige ConfiguracionAuto en la misma lectura de masa')
    args = parser.parse_args(argv)
    try:
        from .evidencia_analisis import fuente_desde_argumentos
        fuente = fuente_desde_argumentos(args.analisis_raiz,args.analisis_caso,args.analisis_resultado,args.analisis_corrida)
        base_caso = {"raiz": str(args.analisis_raiz), "caso": args.analisis_caso} if args.analisis_raiz is not None else None
        if (args.contenido_masa or args.masa_nativa_lectura) and base_caso is None:
            raise ValueError("Contenido/masa nativa requieren la evidencia de análisis (--analisis-raiz/--analisis-caso).")
        f_cont = base_caso if args.contenido_masa else None
        f_nat = {**base_caso, "lectura_id": args.masa_nativa_lectura} if args.masa_nativa_lectura else None
        if args.estimar_auto:
            if f_nat is None:raise ValueError('--estimar-auto requiere --masa-nativa-lectura.')
            f_nat['estimar_auto'] = True
        informe = crear_informe(cargar_json(args.resultados),cargar_json(args.reglas) if args.reglas else None,cargar_json(args.contexto),
            evaluacion=cargar_json(args.evaluacion) if args.evaluacion else None, geometria_archivo=args.geometria,
            corpus=args.corpus,citas=cargar_json(args.citas) if args.citas else None, evidencia_analisis=fuente,
            fuente_contenido_masa=f_cont, fuente_masa_nativa=f_nat)
        carpeta = exportar_informe(informe,args.salida,geometria_archivo=args.geometria,corpus=args.corpus,evidencia_analisis=fuente,
                                   fuente_contenido_masa=f_cont, fuente_masa_nativa=f_nat)
    except (ValueError,OSError,TypeError,OverflowError,RecursionError) as error:
        print(f"Informe no generado: {error}",file=sys.stderr)
        return 1
    print(f"Informe documental en borrador JSON/HTML/PDF: {carpeta}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
