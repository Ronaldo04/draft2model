"""Tarea 6 (ruta 253): métricas de extracción y esfuerzo SOLO desde recibos existentes. Sin APIs, sin benchmark fabricado.

Ejecutar desde la raíz: python seguimiento/claude_ruta/metricas_extraccion_09.py  → seguimiento/claude_ruta/METRICAS_EXTRACCION_09.json

Separa (1) salidas originales de visión (OpenAI/Gemini), (2) correcciones/ingresos asistidos y (3) la ruta vectorial que realmente
alimentó la geometría del piloto. La precisión/recall de la extracción NO es calculable: no existe anotación humana revisada de
referencia (lecturas_aprobadas = 0 en todos los intentos); se informa como «no verificable», nunca se sustituye por la revisión
de Codex o Claude. Los tiempos de etapa provienen de recibos/logs o de fechas de archivo (marcadas como estimación).
"""
import hashlib
import json
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SEG = RAIZ / "seguimiento"


def leer(rel):
    p = RAIZ / rel
    return json.loads(p.read_text(encoding="utf-8")), hashlib.sha256(p.read_bytes()).hexdigest()


fuentes = {}


def fuente(rel):
    d, h = leer(rel)
    fuentes[rel] = h
    return d


consumo = fuente("seguimiento/CONSUMO_API_211.json")
e213 = fuente("seguimiento/PRIMERA_EXTRACCION_REAL_213.json")
e218 = fuente("seguimiento/TERCERA_EXTRACCION_REAL_218.json")
e221 = fuente("seguimiento/CUARTA_EXTRACCION_REAL_221.json")
g224 = fuente("seguimiento/PRIMERA_EXTRACCION_GEMINI_224.json")
antes_despues = fuente("seguimiento/claude_ruta/EVIDENCIA_ANTES_DESPUES_08.json")
muros = fuente("seguimiento/claude_ruta/MUROS_09.json")
diag235 = fuente("seguimiento/DIAGNOSTICO_GEMINI_235.json")
rec236 = fuente("seguimiento/REVISION_NORMATIVA_RECUPERACION_236.json")
# Gemini 2 por etapas (revisión Codex 263): respuesta cruda → validación inicial fallida (0 importadas) → recuperación LOCAL
# en memoria (no persistida, no productiva). El fallo histórico no se convierte en éxito.
GEMINI2 = {"crudos": diag235["candidatos"], "invalidos_validacion_inicial": len(diag235["invalidos_identificados"]),
           "importados": diag235["importadas"], "recuperacion_local_adaptables": rec236["recuperacion_real_en_memoria"]["candidatos"],
           "recuperacion_local_cuarentena": rec236["recuperacion_real_en_memoria"]["cuarentena"], "persistido": rec236["persistido"]}
assert GEMINI2["recuperacion_local_adaptables"] + GEMINI2["recuperacion_local_cuarentena"] == GEMINI2["crudos"]

# Coste OpenAI por petición: los recibos 213/218/221 dan el coste calculado con tarifa estándar sin caché; la petición 2
# (truncada, fallida) se obtiene por diferencia de los acumulados declarados (218: total tras 3 peticiones).
c1 = e213["coste_usd_calculado_tarifa_estandar_sin_cache"]
c3 = e218["coste_peticion3_usd"]
c2 = round(e218["coste_total_openai_usd"] - c1 - c3, 10)
c4 = e221["coste_peticion4_usd"]
coste = {1: c1, 2: c2, 3: c3, 4: c4}
trunc215 = fuente("seguimiento/DIAGNOSTICO_TRUNCAMIENTO_215.json")
assert abs(trunc215["coste_usd_segun_tokens"] - c2) < 1e-9, "coste de la petición 2 no cuadra con el recibo 215"
candidatos = {1: e213["candidatos"], 2: None, 3: e218["candidatos"], 4: e221["candidatos"]}   # 2: salida truncada, no contada
intentos = []
for it in consumo["openai"]:
    n = it["numero"]
    intentos.append({"proveedor": "openai", "numero": n, "modelo": it["modelo"], "fecha_utc": it["fecha_utc"], "estado": it["estado"],
                     "tokens_entrada": it["uso"]["input_tokens"], "tokens_salida": it["uso"]["output_tokens"],
                     "coste_usd": coste[n], "coste_base": "tarifa estándar sin caché (recibos 213/218/221; petición 2 por diferencia)",
                     "candidatos": candidatos[n], "lecturas_aprobadas": 0,
                     **({"etapas": {"respuesta_cruda": {"estado": "truncada", "causa": trunc215["causa"],
                                                        "bytes_salida_parcial": trunc215["bytes_salida_parcial"], "candidatos": "no contados"},
                                    "importacion": trunc215["importacion"]}} if n == 2 else {})})
for it in consumo["gemini"]:
    n = it["numero"]
    intentos.append({"proveedor": "gemini", "numero": n, "modelo": it["modelo"], "fecha_utc": it["fecha_utc"], "estado": it["estado"],
                     "tokens_entrada": it["uso"]["promptTokenCount"], "tokens_salida": it["uso"]["candidatesTokenCount"],
                     "coste_usd": None, "coste_base": "nivel gratuito declarado por el usuario (" + g224["gemini_nivel"] + "); tarifa no aplicada",
                     "candidatos": g224["candidatos"] if n == 1 else None, "lecturas_aprobadas": 0,
                     **({"etapas": {"respuesta_cruda": {"candidatos": GEMINI2["crudos"], "fuente": "DIAGNOSTICO_GEMINI_235"},
                                    "validacion_inicial": {"estado": "fallida", "invalidos": GEMINI2["invalidos_validacion_inicial"],
                                                           "importados": GEMINI2["importados"]},
                                    "recuperacion_local": {"adaptables": GEMINI2["recuperacion_local_adaptables"],
                                                           "cuarentena": GEMINI2["recuperacion_local_cuarentena"],
                                                           "persistido": GEMINI2["persistido"], "fuente": "REVISION_NORMATIVA_RECUPERACION_236",
                                                           "nota": "en memoria; no es extracción productiva ni importada"}}} if n == 2 else {})})
validos = [i for i in intentos if i["estado"] != "fallido"]
total_openai = round(sum(i["coste_usd"] for i in intentos if i["proveedor"] == "openai"), 10)
assert abs(total_openai - e221["coste_acumulado_openai_usd"]) < 1e-9, "coste acumulado OpenAI no cuadra con el recibo 221"

fechas = lambda *ps: {p: datetime.fromtimestamp((RAIZ / p).stat().st_mtime).isoformat(timespec="seconds") for p in ps}
mt = fechas("tmp/recorrido_09t4/plan.json", "tmp/recorrido_09t4/modelo.EDB", "tmp/recorrido_09t4/relectura_resultado.json")
dur = lambda a, b: round((datetime.fromisoformat(mt[b]) - datetime.fromisoformat(mt[a])).total_seconds() / 60, 1)
malla, hm = leer("tmp/ruta201/malla_real_09dt.json")
fuentes["tmp/ruta201/malla_real_09dt.json"] = hm

salida = {
    "tarea": "ruta253_tarea6_metricas_extraccion_esfuerzo", "fecha": "2026-10-22", "apis_ejecutadas_por_claude": 0,
    "extraccion_vision": {
        "intentos": intentos,
        "denominadores": {
            "peticiones": len(intentos), "fallidas_en_su_etapa_productiva": len(intentos) - len(validos),
            "respuestas_con_candidatos_crudos_contados": sum(1 for i in intentos if isinstance(i.get("etapas", {}).get("respuesta_cruda", {}).get("candidatos"), int) or i["candidatos"]),
            "candidatos_crudos_no_deduplicados": sum(i["candidatos"] or 0 for i in intentos) + GEMINI2["crudos"],
            "candidatos_importados_o_registrados": sum(i["candidatos"] or 0 for i in validos),
            "recuperacion_local_no_persistida": {"adaptables": GEMINI2["recuperacion_local_adaptables"], "cuarentena": GEMINI2["recuperacion_local_cuarentena"]},
            "nota": "OpenAI 2 truncada: sin candidatos parseables registrados (DIAGNOSTICO_TRUNCAMIENTO_215). Gemini 2: 71 crudos, validación "
                    "inicial fallida (12 inválidos, 0 importados); 59+12 solo en recuperación local en memoria."},
        "lecturas_aprobadas_totales": 0,
        "precision_recall": "NO VERIFICABLE: no existe anotación humana revisada de referencia; las revisiones de Codex/Claude no son "
                            "anotación humana. Contar candidatos o JSON válido no mide exactitud.",
        "cobertura_recortes_declarada": {"openai_1": "5 de 7 recortes con lecturas (213)", "openai_4": e221["cobertura_recortes"],
                                         "gemini_1": g224["cobertura_recortes"]},
        "coste_openai_usd_total": total_openai,
        "coste_gemini": "0 facturado según nivel gratuito declarado por el usuario; sin tarifa aplicada",
        "observaciones_de_recibos": e218["hallazgos"] + [g224["conclusion"]],
    },
    "correccion_asistida": {
        "reubicaciones": 1, "lecturas_manuales": 1,
        "detalle": "EVIDENCIA_ANTES_DESPUES_08: reubicación de C039 (región vacía → con trazos) y alta manual de f'c 175 omitida por las "
                   "extracciones; vacías 42 → 41. Ingresos de Claude (asistente), no de la IA original ni de un humano.",
        "revision": "pendiente (no aprobadas)",
    },
    "ruta_geometria_del_piloto": {
        "fuente": "vectores de los PDF (inventario vectorial + reglas de geometria_09*.py), NO salidas de visión",
        "muros_inventariados": len(muros.get("muros", muros)) if isinstance(muros, dict) else len(muros),
        "nota": "La geometría del piloto no depende de lecturas de visión aprobadas (no hay ninguna). Decisiones del usuario: arcilla "
                "King-Kong, alturas 0/2,60/5,20/7,80/10,40 y 16 contrahuellas solo del primer tramo.",
    },
    "tiempos_de_etapa": {
        "malla_09d_v3_s": malla["segundos"],
        "construccion_09t4_min_estimada": dur("tmp/recorrido_09t4/plan.json", "tmp/recorrido_09t4/modelo.EDB"),
        "relectura_09t4_min_cota_superior": dur("tmp/recorrido_09t4/modelo.EDB", "tmp/recorrido_09t4/relectura_resultado.json"),
        "metodo": "malla: recibo; construcción/relectura: fechas de modificación de plan.json → modelo.EDB → relectura_resultado.json "
                  "(estimación; incluye esperas). Extracción/revisión humana: sin cronómetro registrado → no medido.",
        "marcas": mt,
    },
    "no_afirma": ["exactitud de la extracción", "benchmark", "costo de horas humanas", "comparación con el modelo ETABS manual (aplazada)"],
    "fuentes_sha256": fuentes,
}
out = RAIZ / "seguimiento/claude_ruta/METRICAS_EXTRACCION_09.json"
out.write_text(json.dumps(salida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(json.dumps({k: salida["extraccion_vision"][k] for k in ("denominadores", "coste_openai_usd_total")}, ensure_ascii=False),
      salida["tiempos_de_etapa"]["construccion_09t4_min_estimada"], salida["tiempos_de_etapa"]["relectura_09t4_min_cota_superior"])
