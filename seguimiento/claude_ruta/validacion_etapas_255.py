"""Pure, script-local gates. No product imports, approvals, ETABS or file I/O."""
from collections.abc import Mapping
from datetime import date
import re


CONTROLES_ESPERADOS = ("geometria_conectividad", "materiales_secciones", "cargas_masa",
                       "apoyos_diafragmas", "casos_combinaciones")


class StageOutcomeError(ValueError):
    pass


def _need(ok, message):
    if not ok:
        raise StageOutcomeError(message)


def _sha(value):
    return type(value) is str and re.fullmatch(r"[a-fA-F0-9]{64}", value) is not None


def validate_stage_outcome(stage, report):
    """Require positive evidence for the requested stage and all prerequisites."""
    _need(stage in ("construccion", "relectura", "analisis"), "Etapa desconocida")
    _need(isinstance(report, Mapping), "Registro inválido")
    phases = report.get("fases")
    _need(isinstance(phases, Mapping), "Fases ausentes")
    _need(not any(str(k).endswith("_error") or (isinstance(v, Mapping) and v.get("estado") == "error")
                  for k, v in phases.items()), "El registro conserva un error de etapa")
    construction = phases.get("construccion", {})
    _need(isinstance(construction, Mapping) and construction.get("estado") == "ok", "Construcción no exitosa")
    _need(construction.get("cierre_confirmado") is True and not construction.get("error_cierre"), "Cierre propio no confirmado")
    hashes = [report.get(k) for k in ("sha256_plantilla_esperada", "sha256_plantilla_anterior", "sha256_plantilla_posterior")]
    _need(all(_sha(h) for h in hashes) and len({h.lower() for h in hashes}) == 1, "SHA de plantilla ausente o alterado")
    if stage == "construccion":
        return
    reread = phases.get("relectura", {})
    _need(isinstance(reread, Mapping) and reread.get("estado") == "verificado", "Relectura no verificada")
    for field in ("discrepancias", "incompletos"):
        _need(type(reread.get(field)) is int and reread[field] == 0, "Relectura con discrepancias/incompletos o conteos inválidos")
    if stage == "relectura":
        return
    review = phases.get("revision_controles_transporte", {})
    _need(isinstance(review, Mapping) and review.get("estado") == "documentada" and _sha(review.get("sha256")), "Revisión explícita de controles ausente")
    _need(review.get("aprueba_ingenieria") is False and bool(review.get("alcance_autorizacion_software")), "Alcance de transporte separado requerido")
    validar_revision_controles({"modelo_id": review.get("modelo_id"), "huella_modelo": review.get("huella_modelo"),
        "revisor": review.get("revisor_declarado"), "fecha": review.get("fecha"), "alcance": review.get("alcance_revision"),
        "controles": review.get("controles"), "evidencias": review.get("evidencias")},
        CONTROLES_ESPERADOS, construction.get("registro_modelo"), review.get("huella_modelo"))
    for name in ("aprobacion_modelo_transporte", "analisis"):
        _need(isinstance(phases.get(name), Mapping) and phases[name].get("estado") == "ok", name + " no exitosa")
    reads = phases.get("lecturas")
    _need(isinstance(reads, Mapping) and set(reads) == {"reacciones", "modal", "derivas"}
          and all(isinstance(v, Mapping) and v.get("estado") == "ok" for v in reads.values()), "Lecturas de análisis incompletas")


def validar_revision_controles(review, required, model_id, model_hash):
    """Validate a sidecar of EXPLICIT declarations; not the truth of its review.

    This is local run evidence, not a change to draft2model's model contract.
    The caller must verify referenced files' hashes before forwarding controls.
    """
    _need(isinstance(review, Mapping), "Revisión de controles requerida")
    _need(review.get("modelo_id") == model_id and review.get("huella_modelo") == model_hash and _sha(model_hash), "Revisión no ligada al modelo/huella actual")
    for key in ("revisor", "fecha", "alcance"):
        _need(type(review.get(key)) is str and bool(review[key].strip()), key + " declarado requerido")
    try:
        _need(date.fromisoformat(review["fecha"]).isoformat() == review["fecha"], "Fecha no canónica")
    except (ValueError, TypeError):
        raise StageOutcomeError("Fecha de revisión inválida") from None
    controls = review.get("controles")
    _need(isinstance(controls, dict) and set(controls) == set(required)
          and all(v is True for v in controls.values()), "Cada control requiere confirmación explícita, no inferida de relectura")
    evidence = review.get("evidencias")
    _need(isinstance(evidence, dict) and set(evidence) == set(required), "Procedencia por control requerida")
    for name in required:
        item = evidence[name]
        _need(isinstance(item, Mapping), "Evidencia inválida: " + name)
        for field in ("referencia", "alcance"):
            _need(type(item.get(field)) is str and bool(item[field].strip()), "Referencia/alcance de evidencia requerido: " + name)
        _need(_sha(item.get("sha256")), "SHA de evidencia inválido: " + name)
    return review
