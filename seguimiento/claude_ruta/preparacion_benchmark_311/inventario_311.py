"""311: inventario compacto de cohortes reales del primer proyecto (provisional-001), ANTERIORES a corrección.

Solo lectura local. No llama APIs, no lee credenciales, no vuelca respuestas ni imágenes: extrae metadatos, huellas y recuentos.
Cada intento = una cohorte separada (proveedor/modelo/plan); no se suman candidatos entre cohortes ni etapas.
Uso: python inventario_311.py SALIDA.json
"""
import hashlib, json, sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
from draft2model.extraccion_preliminar import validar_extraccion, huella  # noqa: E402

CASO = "provisional-001"
EXP = RAIZ / "data/private" / CASO
CONSUMO = RAIZ / "seguimiento/CONSUMO_API_211.json"
METRICAS = RAIZ / "seguimiento/claude_ruta/METRICAS_EXTRACCION_09.json"
KIT = RAIZ / "seguimiento/referencia_humana_308/fuentes.json"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def resumen_extraccion(path):
    d = json.loads(path.read_text(encoding="utf-8"))
    v = validar_extraccion(d)
    cands = d.get("candidatos", [])
    ev = [e for c in cands for e in c.get("evidencia", [])]
    return {
        "ruta": path.relative_to(RAIZ).as_posix(), "sha256": sha(path), "huella_contrato": huella(d),
        "contrato": d.get("contrato"), "version_contrato": d.get("version_contrato"), "caso": d.get("caso"),
        "procedencia_tipo": (d.get("procedencia") or {}).get("tipo"), "consistente": v.consistente, "errores": len(v.errores),
        "candidatos": len(cands), "por_tipo": dict(Counter(c.get("tipo") for c in cands)),
        "valor_null": sum(c.get("valor_propuesto") is None for c in cands),
        "por_lamina": dict(Counter(f'{e.get("archivo_id")}/p{e.get("pagina")}' for e in (c["evidencia"][0] for c in cands if c.get("evidencia")))),
        "originales_sha256": sorted({e.get("original_sha256") for e in ev}),
        "candidatos_sin_evidencia": sum(not c.get("evidencia") for c in cands),
    }


def main(salida):
    consumo = json.loads(CONSUMO.read_text(encoding="utf-8"))
    metr = {(a["proveedor"], a["numero"]): a for a in json.loads(METRICAS.read_text(encoding="utf-8"))["extraccion_vision"]["intentos"]}
    kit = json.loads(KIT.read_text(encoding="utf-8"))
    kit_orig = {p["original_sha256"]: f'{p["archivo_id"]}/p{p["pagina"]}' for p in kit["paginas"]}
    cohortes = []
    for prov, filas in consumo.items():
        for r in filas:
            res_path = RAIZ / r["resultado"].replace("\\", "/")
            res = json.loads(res_path.read_text(encoding="utf-8"))
            api = res_path.parent / "respuesta_api.json"
            m = metr.get((prov, r["numero"]), {})
            c = {"cohorte": f'{prov}_{r["numero"]}', "proveedor": prov, "numero": r["numero"], "modelo_solicitado": r["modelo"],
                 "modelo_devuelto": res.get("modelo_devuelto"), "fecha_utc": r["fecha_utc"], "caso": CASO,
                 "estado": res["estado"], "simulada": res.get("simulada"), "plan_sha256": res["plan_sha256"],
                 "plan_coincide_consumo": res["plan_sha256"] == r.get("plan_sha256"),
                 "respuesta_api": {"ruta": api.relative_to(RAIZ).as_posix(), "sha256_registrado": res.get("respuesta_api_sha256"),
                                   "sha256_actual": sha(api) if api.exists() else None},
                 "candidatos_metricas09": m.get("candidatos"), "etapas_metricas09": m.get("etapas"),
                 "aprobacion_ingenieria": res.get("aprobacion_ingenieria"), "version_importada": res.get("version_importada")}
            c["respuesta_api"]["coincide"] = c["respuesta_api"]["sha256_registrado"] == c["respuesta_api"]["sha256_actual"]
            if res.get("extraccion"):
                e = resumen_extraccion(EXP / res["extraccion"])
                e["originales_en_kit_humano"] = {s: kit_orig.get(s) for s in e["originales_sha256"]}
                c["extraccion_previa_correccion"] = e
                c["candidatos_coinciden_metricas09"] = e["candidatos"] == m.get("candidatos")
                c["uso_en_benchmark"] = "propuestas_originales_evaluables_con_referencia_y_correspondencias_revisadas"
            else:
                c["extraccion_previa_correccion"] = None
                c["uso_en_benchmark"] = "excluida_de_metricas_de_exactitud: sin extracción importada (fallo registrado; se informa aparte)"
                c["motivo"] = res.get("mensaje")
            cohortes.append(c)
    ok = [c for c in cohortes if c["extraccion_previa_correccion"]]
    # Registros de respuesta NO ligados a un recibo de petición (p. ej. importación web de Gemini 2 con cuarentena, QA 09/239):
    # se listan como cohorte derivada separada; son adaptaciones posteriores a la validación, no propuestas crudas.
    ligadas = {Path(c["extraccion_previa_correccion"]["ruta"]).parent.name for c in ok}
    derivados = []
    for d in sorted((EXP / "vision/respuestas").iterdir()):
        if d.name in ligadas or not (d / "extraccion.json").exists():
            continue
        e = resumen_extraccion(d / "extraccion.json")
        x = json.loads((d / "extraccion.json").read_text(encoding="utf-8"))
        e.update({"procedencia_descripcion": x["procedencia"].get("descripcion", "")[:160], "archivos": sorted(p.name for p in d.iterdir()),
                  "originales_en_kit_humano": {s: kit_orig.get(s) for s in e["originales_sha256"]},
                  "clasificacion": "derivada_recuperacion_con_cuarentena (no cruda; separada de cohortes primarias; no sumar copias)"})
        derivados.append(e)
    out = {
        "tarea": "benchmark_311_inventario", "caso": CASO, "apis_ejecutadas": 0,
        "fuentes_sha256": {p.relative_to(RAIZ).as_posix(): sha(p) for p in (CONSUMO, METRICAS, KIT)},
        "limites_consumo_registrados": {"openai": f'{len(consumo["openai"])}/5', "gemini": f'{len(consumo["gemini"])}/5',
                                        "nota": "Incluye OpenAI 2 truncada y Gemini 2 fallida. No se ejecuta otra petición."},
        "kit_humano": {"caso": kit["caso"], "observaciones_anotadas": kit["observaciones_anotadas"],
                       "revision_humana_realizada": kit["revision_humana_realizada"], "paginas": list(kit_orig.values())},
        "cohortes": cohortes,
        "registros_derivados_no_ligados_a_recibo": derivados,
        "denominadores": {"peticiones": len(cohortes), "fallidas": sum(c["estado"] == "fallido" for c in cohortes),
                          "cohortes_con_extraccion_previa": len(ok),
                          "candidatos_por_cohorte": {c["cohorte"]: c["extraccion_previa_correccion"]["candidatos"] for c in ok},
                          "nota": "Recuentos por cohorte; NO sumar entre cohortes (mismas láminas/recortes en distintas peticiones)."},
        "excluidas_correcciones": "Versiones en extracciones/ (importaciones y correcciones asistidas, p. ej. reubicación C039) no se usan como propuestas originales.",
        "metricas_de_exactitud": None,
        "motivo_sin_metricas": "No existe referencia humana revisada ni correspondencias revisadas.",
    }
    Path(salida).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    for c in cohortes:
        e = c["extraccion_previa_correccion"]
        print(c["cohorte"], c["estado"], c["modelo_devuelto"], "api_sha_ok" if c["respuesta_api"]["coincide"] else "API_SHA_DISTINTA",
              (e["candidatos"], e["por_tipo"], e["consistente"], c["candidatos_coinciden_metricas09"], list(e["originales_en_kit_humano"].values())) if e else c["motivo"])


if __name__ == "__main__":
    main(sys.argv[1])
