"""311: helper aislado de recepción de la referencia humana y de correspondencias PENDIENTES (sin APIs, sin métricas inventadas).

Comandos:
  recibir   --referencia REF.json [--fuentes fuentes.json] --salida RECEPCION.json
            Valida con draft2model.evaluacion_vision.validar_referencia; comprueba caso, archivo/página/hashes y regiones contra el kit
            (fuentes.json de referencia_humana_308); clasifica «protocolo_completo» (≥30 observaciones, 3 clases, 3 láminas) o
            «referencia_parcial». La firma (revisor_declarado/fecha) es una DECLARACIÓN: no autentica identidad; nunca se completa aquí.
  sugerir   --referencia REF.json --extraccion EXTRACCION.json --cohorte ID --salida PROPUESTA.json
            Propone pares SOLO por archivo_id + página + original_sha256 + solapamiento de regiones + mismo tipo. Nunca compara valores.
            Todo queda PENDIENTE: contrato de propuesta (no el oficial), revision.estado «pendiente», principal/evidencia_correcta null.
            El evaluador oficial rechaza este archivo. Lista candidatos sin sugerencia (posibles sin_respaldo/sin_clasificar) y
            observaciones sin candidato (posibles omisiones) sin decidir por el humano.
  verificar --referencia REF.json --extraccion EXTRACCION.json --correspondencias CORR.json
            Comprobación previa a medir: referencia válida, correspondencias OFICIALES revisadas por humano y con huellas exactas
            (validar_correspondencias). No calcula métricas: indica el comando oficial de evaluación.
Códigos de salida: 0 ok; 2 entrada ausente o inválida; 3 incompatible con kit/inventario; 4 correspondencias no listas.
"""
from __future__ import annotations

import argparse, json, sys
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))
from draft2model.evaluacion_vision import ErrorEvaluacion, validar_referencia, validar_correspondencias  # noqa: E402
from draft2model.extraccion_preliminar import huella  # noqa: E402

KIT = RAIZ / "seguimiento/referencia_humana_308/fuentes.json"
PROTOCOLO = {"observaciones_minimas": 30, "clases": ("cota", "etiqueta", "elemento"), "laminas": 3}
CONTRATO_PROPUESTA = "draft2model.correspondencias_vision_propuesta_pendiente"


class Rechazo(Exception):
    def __init__(self, codigo, mensaje):
        super().__init__(mensaje if len(mensaje) <= 700 else mensaje[:700] + " …"); self.codigo = codigo


def cargar(path, que):
    p = Path(path) if path else None
    if p is None or not p.is_file():
        raise Rechazo(2, f"{que} ausente: {path}. Sin referencia no hay métricas (ni 0 % ni 100 %).")
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError) as e:
        raise Rechazo(2, f"{que} no es JSON UTF-8 válido: {e}") from None


def _escribir(salida, data):
    Path(salida).parent.mkdir(parents=True, exist_ok=True)
    with open(salida, "x", encoding="utf-8") as fh:   # nunca sobrescribe
        fh.write(json.dumps(data, ensure_ascii=False, indent=1) + "\n")


def recibir(ref, kit):
    try:
        validar_referencia(ref)
    except ErrorEvaluacion as e:
        raise Rechazo(2, "Referencia inválida según evaluacion_vision.validar_referencia: " + str(e)) from None
    if ref["caso"] != kit["caso"]:
        raise Rechazo(3, f"Caso {ref['caso']!r} distinto del kit ({kit['caso']!r}).")
    paginas = {(p["archivo_id"], p["pagina"]): p for p in kit["paginas"]}
    problemas = []
    for i, o in enumerate(ref["observaciones"]):
        for j, ev in enumerate(o["evidencia"]):
            p = paginas.get((ev.get("archivo_id"), ev.get("pagina")))
            if p is None:
                problemas.append(f"observaciones[{i}].evidencia[{j}]: lámina fuera del kit"); continue
            for k in ("original_sha256", "imagen_sha256"):
                if k in ev and ev[k] != p[k]:
                    problemas.append(f"observaciones[{i}].evidencia[{j}].{k} no coincide con el kit")
    if problemas:
        raise Rechazo(3, "Referencia incompatible con originales/regiones del kit: " + "; ".join(problemas[:10]))
    obs = ref["observaciones"]
    clases = Counter(o["tipo"] for o in obs)
    laminas = Counter((o["evidencia"][0]["archivo_id"], o["evidencia"][0]["pagina"]) for o in obs)
    faltan = []
    if len(obs) < PROTOCOLO["observaciones_minimas"]:
        faltan.append(f"observaciones {len(obs)} < {PROTOCOLO['observaciones_minimas']}")
    faltan += [f"clase sin observaciones: {c}" for c in PROTOCOLO["clases"] if not clases.get(c)]
    faltan += [f"lámina sin observaciones: {a}/p{p}" for (a, p) in paginas if not laminas.get((a, p))]
    return {"contrato": "benchmark_311.recepcion", "caso": ref["caso"], "huella_referencia": huella(ref),
            "estado": "protocolo_completo" if not faltan else "referencia_parcial", "faltantes_protocolo": faltan,
            "observaciones": len(obs), "por_clase": dict(clases), "por_lamina": {f"{a}/p{p}": n for (a, p), n in laminas.items()},
            "legibilidad": dict(Counter(o["legibilidad"] for o in obs)), "datos_sinteticos": ref["procedencia"]["tipo"] == "sintetico",
            "revision_declarada": dict(ref["revision"]), "identidad_revisor": "declarada_no_autenticada",
            "aviso": "Recepción no mide exactitud. Una referencia parcial solo admite conclusiones sobre su propia muestra."}


def _solapa(a, b):
    ix = min(a[2], b[2]) - max(a[0], b[0]); iy = min(a[3], b[3]) - max(a[1], b[1])
    if ix <= 0 or iy <= 0:
        return 0.0
    inter = ix * iy; ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def sugerir(ref, ext, cohorte):
    try:
        validar_referencia(ref)
    except ErrorEvaluacion as e:
        raise Rechazo(2, "Referencia inválida: " + str(e)) from None
    for k in ("caso", "alcance", "sistema_coordenadas"):
        if ref.get(k) != ext.get(k):
            raise Rechazo(3, f"{k}: referencia y extracción incompatibles.")
    if ref["procedencia"]["tipo"] != ext["procedencia"]["tipo"]:
        raise Rechazo(3, "No mezclar referencia sintética con extracción de expediente, o viceversa.")
    sugerencias, con_sugerencia, obs_con = [], set(), set()
    for o in ref["observaciones"]:
        for io, eo in enumerate(o["evidencia"]):
            for c in ext["candidatos"]:
                if c["tipo"] != o["tipo"]:      # solo tipo, archivo, página, hash y región; NUNCA el valor
                    continue
                for ic, ec in enumerate(c.get("evidencia", [])):
                    if (eo["archivo_id"], eo["pagina"], eo["original_sha256"]) != (ec["archivo_id"], ec["pagina"], ec["original_sha256"]):
                        continue
                    s = _solapa(eo["bbox_normalizada"], ec["bbox_normalizada"])
                    if s > 0:
                        sugerencias.append({"observacion_id": o["id"], "candidato_id": c["id"], "indice_evidencia_referencia": io,
                                            "indice_evidencia_candidato": ic, "iou_regiones": round(s, 4),
                                            "principal": None, "evidencia_correcta": None, "decision": "pendiente_humana"})
                        con_sugerencia.add(c["id"]); obs_con.add(o["id"])
    sugerencias.sort(key=lambda p: (p["observacion_id"], -p["iou_regiones"], p["candidato_id"]))
    return {"contrato": CONTRATO_PROPUESTA, "version_contrato": "0.1.0", "cohorte": cohorte, "caso": ref["caso"],
            "huella_referencia": huella(ref), "huella_extraccion": huella(ext),
            "revision": {"estado": "pendiente", "revisor_declarado": None, "fecha": None},
            "sugerencias": sugerencias,
            "candidatos_sin_sugerencia": sorted(c["id"] for c in ext["candidatos"] if c["id"] not in con_sugerencia),
            "observaciones_sin_candidato": sorted(o["id"] for o in ref["observaciones"] if o["id"] not in obs_con),
            # candidatos con más de una observación posible: el humano elige; el evaluador no admite emparejar un candidato dos veces
            "candidatos_varias_observaciones": sorted(c for c, n in Counter(p["candidato_id"] for p in sugerencias).items() if n > 1),
            "instrucciones": ("Propuesta NO evaluable. Un humano decide cada par (principal/duplicado, evidencia_correcta), marca sin_respaldo "
                              "y deja omisiones/sin clasificar visibles; después se escribe el contrato oficial "
                              "draft2model.correspondencias_vision con su propia revisión declarada. El helper no lo genera.")}


def verificar(ref, ext, corr):
    if corr.get("contrato") == CONTRATO_PROPUESTA or (corr.get("revision") or {}).get("estado") != "revisado":
        raise Rechazo(4, "Correspondencias pendientes o propuesta sin revisión humana: no se puede medir.")
    try:
        validar_referencia(ref)
        validar_correspondencias(ref, ext, corr)
    except ErrorEvaluacion as e:
        raise Rechazo(4, "Correspondencias no listas: " + str(e)) from None
    return {"listo_para_medir": True, "huellas": {"referencia": huella(ref), "extraccion": huella(ext), "correspondencias": huella(corr)},
            "comando": "python -m draft2model.evaluacion_vision --referencia REF --extraccion EXT --correspondencias CORR --salida NUEVA.json"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("recibir"); r.add_argument("--referencia"); r.add_argument("--fuentes", default=str(KIT)); r.add_argument("--salida", required=True)
    s = sub.add_parser("sugerir"); s.add_argument("--referencia"); s.add_argument("--extraccion", required=True); s.add_argument("--cohorte", required=True); s.add_argument("--salida", required=True)
    v = sub.add_parser("verificar"); v.add_argument("--referencia"); v.add_argument("--extraccion", required=True); v.add_argument("--correspondencias", required=True)
    a = ap.parse_args(argv)
    try:
        ref = cargar(a.referencia, "Referencia humana")
        if a.cmd == "recibir":
            out = recibir(ref, cargar(a.fuentes, "fuentes del kit")); _escribir(a.salida, out)
        elif a.cmd == "sugerir":
            out = sugerir(ref, cargar(a.extraccion, "Extracción"), a.cohorte); _escribir(a.salida, out)
        else:
            out = verificar(ref, cargar(a.extraccion, "Extracción"), cargar(a.correspondencias, "Correspondencias"))
        print(json.dumps({k: out[k] for k in list(out)[:6]}, ensure_ascii=False))
        return 0
    except Rechazo as e:
        print("RECHAZO " + str(e.codigo) + ": " + str(e), file=sys.stderr)
        return e.codigo
    except FileExistsError as e:
        print("RECHAZO 2: salida existente, no se sobrescribe: " + str(e), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
