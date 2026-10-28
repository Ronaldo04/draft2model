"""Revisión explícita de los 5 controles de modelo para la etapa de análisis (runner 256), SOLO de transporte de software.

Ejecutar desde la raíz:
    python seguimiento/claude_ruta/revision_controles_09.py --trabajo tmp/recorrido_09t4 --modelo <id> --salida <json>

Quién revisa: Claude (ruta autónoma 09), revisión PROPIA de software sobre la relectura independiente del EDB construido.
No es aprobación de ingeniería ni del usuario. La autorización del usuario (chat 2026-10-22) es solo de transporte de software
con escenario de suelo/sistema hipotético; se registra aparte. Cada control se marca True únicamente si la relectura del modelo
lo verificó sin discrepancias ni incompletos en las coberturas que se citan; si no, el guion falla y no escribe nada.
"""
import argparse
import hashlib
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
PRIV = RAIZ / "data/private"
CASO = "pueblo-libre-002"
COBERTURAS = {
    "geometria_conectividad": ("unidades", "pisos", "puntos", "frames", "areas", "aberturas", "malla"),
    "materiales_secciones": ("materiales", "propiedades_area", "propiedades_frame"),
    "cargas_masa": ("cargas_area", "cargas_punto", "cargas_frame", "cargas_liquidos", "fuente_masa", "patrones"),
    "apoyos_diafragmas": ("apoyos", "diafragmas"),
    "casos_combinaciones": ("casos", "combinaciones", "funciones_espectrales", "tablas_dinamicas"),
}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trabajo", type=Path, required=True)
    ap.add_argument("--modelo", required=True)
    ap.add_argument("--salida", type=Path, required=True)
    ap.add_argument("--fecha", default="2026-10-22")
    a = ap.parse_args(argv)
    work = (RAIZ / a.trabajo).resolve()
    rel_path = work / "relectura_resultado.json"
    rel = json.loads(rel_path.read_text(encoding="utf-8"))
    if not (rel["estado"] == "verificado" and rel["verificado"] is True and not rel["discrepancias"] and not rel["incompletos"]):
        raise SystemExit("Relectura no verificada: no se declara ningún control.")
    cob = rel["cobertura"]
    faltan = {c: [k for k in ks if cob.get(k) != "completa"] for c, ks in COBERTURAS.items()}
    if any(faltan.values()):
        raise SystemExit("Cobertura incompleta, no se declaran controles: " + json.dumps(faltan))
    version = PRIV / CASO / "modelos_construidos" / a.modelo / "version.json"
    manifiesto = json.loads(version.read_text(encoding="utf-8"))
    if manifiesto["origen"]["sha256_modelo"] != rel["sha256_edb"]:
        raise SystemExit("La relectura no corresponde al EDB registrado del modelo.")
    referencia = rel_path.relative_to(RAIZ).as_posix()
    no_afirmados = ", ".join(rel["controles_no_afirmados"])
    evidencias = {c: {"referencia": referencia, "sha256": sha(rel_path),
                      "alcance": ("Relectura independiente del EDB " + rel["sha256_edb"][:16] + "… (instancia nueva cerrada): coberturas "
                                  + ", ".join(ks) + " completas, 0 discrepancias, 0 incompletos. Solo correspondencia plan↔EDB; no "
                                  "afirma: " + no_afirmados + ".")}
                  for c, ks in COBERTURAS.items()}
    revision = {"modelo_id": a.modelo, "huella_modelo": sha(version),
                "revisor": "Claude (ruta autónoma 09): revisión propia de software sobre la relectura; NO ingeniería ni usuario",
                "fecha": a.fecha,
                "alcance": ("Transporte de software autorizado por el usuario (chat 2026-10-22) con escenario de suelo/sistema HIPOTÉTICO. "
                            "Cada control confirma que el EDB reproduce el plan aprobado en esa materia; no revisa idoneidad estructural, "
                            "normativa, suelo ni resultados."),
                "controles": {c: True for c in COBERTURAS}, "evidencias": evidencias}
    salida = (RAIZ / a.salida).resolve()
    if salida.exists():
        raise SystemExit("Salida existente; no se sobrescribe.")
    salida.write_text(json.dumps(revision, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(salida.relative_to(RAIZ).as_posix(), sha(salida))


if __name__ == "__main__":
    main()
