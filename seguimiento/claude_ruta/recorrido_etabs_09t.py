"""Recorrido ETABS propio POR ETAPAS del caso real en el ESCENARIO DE TRANSPORTE.

Aprobaciones DECLARADAS SOLO DE TRANSPORTE DE SOFTWARE (no ingeniería). Escenario sísmico S1 + muros de concreto R0 = 6,
Ia = Ip = 1 (HIPÓTESIS, sin EMS). Instancias ETABS NUEVAS y propias; se cierran solo las propias (PID + rutas verificadas).

Uso desde la raíz:
  python seguimiento/claude_ruta/recorrido_etabs_09t.py --trabajo tmp/recorrido_09t --etapa construccion
  python seguimiento/claude_ruta/recorrido_etabs_09t.py --trabajo tmp/recorrido_09t --etapa relectura
  python seguimiento/claude_ruta/recorrido_etabs_09t.py --trabajo tmp/recorrido_09t --etapa analisis
Cada etapa escribe registro.json (acumulado) y se detiene ante cualquier error; ninguna fase oculta el fallo de otra.
"""
import argparse
import hashlib
import importlib.util
import json
import sys
import traceback
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from validacion_etapas_255 import validate_stage_outcome, validar_revision_controles


def cargar_dependencias():
    # Lazy imports: importing this candidate for offline tests must not load product.
    global ad, ej, gc, m, op, rm, vmg, an, la, EjecutorVerificado, carpeta_caso, epl
    from draft2model import adaptador_etabs as ad, ejecutor_etabs as ej  # noqa: E402
    from draft2model import gestion_configuracion as gc, modelo_estructural as m  # noqa: E402
    from draft2model import operaciones_etabs as op, revision_modelo as rm  # noqa: E402
    from draft2model import verificacion_modelo_guardado as vmg  # noqa: E402
    from draft2model import analisis_etabs as an, lectura_analisis as la  # noqa: E402
    from draft2model.ejecucion_modelo import EjecutorVerificado  # noqa: E402
    from draft2model.gestion_extraccion import carpeta_caso  # noqa: E402
    
    _spec = importlib.util.spec_from_file_location("epl", RAIZ / "scripts/ensayar_plan_liquidos.py")
    epl = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(epl)

PRIV, CASO = RAIZ / "data/private", "pueblo-libre-002"
PLANTILLA = PRIV / CASO / "plantillas/plantilla_vacia_caso.EDB"
LOCK = RAIZ / "tmp/d2/motor.lock"
FECHA = "2026-10-22"
REVISOR = "Operador del recorrido (revisión declarada de transporte de software; no ingeniería)"
ALCANCE = ("TRANSPORTE DE SOFTWARE del piloto (escenario de transporte 09T: S1 + R0 = 6 hipotéticos, escalera como cargas, agua en "
           "escenarios). NO es aprobación de ingeniería ni de diseño; no certifica seguridad ni cumplimiento normativo.")
EIGEN = {"frecuencia_desplazamiento_hz": 0.0, "frecuencia_corte_hz": 0.0, "tolerancia": 1e-9, "desplazamiento_automatico": True}
LOSAS = {"LOSA-MEMB-05": ("Membrane", "piso", "Piso con diafragma rígido; E.030 30.8 excluye la rigidez fuera del plano del piso."),
         "DEP-FONDO-20": ("ShellThick", "fondo_deposito", "Fondo de depósito: resiste la presión del agua por flexión (R241)."),
         "DEP-TAPA-15": ("ShellThick", "tapa_deposito", "Tapa de cisterna con flexión (R241)."),
         "DEP-TAPA-20": ("ShellThick", "tapa_deposito", "Tapa de tanque con flexión (R241)."),
         "ESC-15": ("ShellThick", "otra", "Escalera (rampas y descansos) con flexión fuera del plano; no es piso de diafragma.")}
CONFIG = RAIZ / "tmp/ruta201/configuracion09t.json"   # --configuracion la sustituye (p. ej. configuracion09dt.json, 09D)
ALCANCE_09D = ("TRANSPORTE DE SOFTWARE del piloto (escenario de transporte 09D: S1 + R0 = 6 hipotéticos; escalera modelada con el "
               "primer tramo confirmado y U superior hipotética; agua en caras mojadas con estado de contenido declarado; cotas "
               "auxiliares de depósitos). NO es aprobación de ingeniería ni de diseño; no certifica seguridad ni cumplimiento normativo.")


def opciones(config, destino):
    return {"destino_guardado": str(destino), "tipo_shell_muro": "ShellThin", "gravedad_programa_m_s2": 9.80665,
            "tipo_shell_losa": {s: {"tipo": t, "funcion": f, "justificacion": j} for s, (t, f, j) in LOSAS.items()
                                if s in {x["id"] for x in config["secciones"]}},
            "parametros_modales": {"MODAL-E030": EIGEN}, "amortiguamiento_funciones": {"ESP-S1-R6-HIP": 0.05},
            "excentricidad_espectral": {"SX": 0.05, "SY": 0.05}, "respuesta_rigida_espectral": {"SX": False, "SY": False}}


def registro(work):
    p = work / "registro.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {
        "recorrido": "caso_real_transporte_09t", "caso": CASO, "datos_sinteticos": False, "etabs_real": False, "etabs_solicitado": "real",
        "aprobacion": "declarada SOLO de transporte de software; no aprobación de ingeniería", "aprueba_ingenieria": False, "fases": {}}


def etapa_construccion(work, rep):
    if (work / "plan.json").exists():
        raise ValueError("La construcción ya se ejecutó en esta carpeta; use otra carpeta nueva.")
    cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    imp = gc.importar(PRIV, CASO, CONFIG)
    rev = gc.revisar(PRIV, CASO, imp["id"], cfg, revisor=REVISOR, fecha=FECHA,
                     motivo=f"Configuración {CONFIG.name} revisada para transporte (política de nodos derivados declarada por su guion).")
    apr = gc.aprobar(PRIV, CASO, rev["id"], huella_esperada=m.huella_configuracion(rev["configuracion"]), revisor=REVISOR, fecha=FECHA,
                     motivo="Aprobación declarada de transporte autorizada por el usuario.", alcance=ALCANCE)
    config = apr["configuracion"]
    rep["fases"]["configuracion"] = {"estado": "ok", "importada": imp["id"], "revisada": rev["id"], "aprobada": apr["id"]}
    destino = work / "modelo.edb"
    plan = op.generar_plan_por_version(PRIV, config, **opciones(config, destino)).datos
    epl.guardar(work / "configuracion.json", config)
    epl.guardar(work / "plan.json", plan)
    rep["fases"]["plan"] = {"estado": "ok", "version": plan["version_contrato"], "huella": plan["huella_plan"],
                            "operaciones": len(plan["operaciones"]), "resumen": plan.get("resumen")}
    epl.guardar(work / "registro.json", rep)
    firmas = op.verificar_firmas_dll()
    if firmas["diferencias"]:
        raise ValueError("Firmas distintas; no se abre ETABS.")
    original = epl.sha(PLANTILLA)
    rep["sha256_plantilla_anterior"] = original
    rep["sha256_plantilla_esperada"] = config["plantilla"]["sha256"]
    if original != config["plantilla"]["sha256"]:
        raise ValueError("La plantilla del caso no coincide con la configuración.")
    (work / "apertura").mkdir(); (work / "motor").mkdir()
    bridge = ad.AdaptadorEtabs(ad.ConfiguracionPuente.real(work / "apertura", LOCK, timeout_s=300))
    opened = None
    try:
        opened = bridge.abrir_copia_plantilla(PLANTILLA, original, work / "copia", instancia="nueva")
        epl.guardar(work / "apertura.json", opened.datos)
        rep["etabs_real"] = True  # Real adapter opening observed; not proof of completed construction/analysis.
        pid = opened.datos["id_proceso"]; copia = Path(opened.datos["modelo_abierto"])
        executor = EjecutorVerificado(ej.configuracion_real(work / "motor", LOCK, timeout_s=3600))
        prepared = executor.preparar(PRIV, config, plan, copia=copia, modelo_esperado=copia, id_proceso=pid)
        result = executor.ejecutar(prepared, confirmar_mutacion=True)
        registro_modelo = rm.registrar(PRIV, CASO, config, plan, prepared.carpeta)
        rep["fases"]["construccion"] = {"estado": "ok", "id_proceso": pid, "operaciones": result.operaciones_ejecutadas,
                                        "guardado": result.guardado, "registro_modelo": registro_modelo.name}
    except Exception as exc:
        rep["fases"]["construccion"] = {"estado": "error", "tipo": type(exc).__name__, "error": str(exc)[:4000],
                                        "traza": traceback.format_exc()[-2500:]}
    finally:
        if opened is not None:
            try:
                ok = epl.cerrar_propio(opened.datos["id_proceso"], opened.datos["modelo_abierto"], destino, work / "modelo.$et",
                                       rep["fases"].get("construccion", {}).get("guardado", {}).get("sha256", ""), LOCK, work / "cierre.log")
                rep["fases"].setdefault("construccion", {})["cierre_confirmado"] = ok
            except Exception as exc:
                rep["fases"].setdefault("construccion", {})["error_cierre"] = str(exc)
        rep["sha256_plantilla_posterior"] = epl.sha(PLANTILLA)


def etapa_relectura(work, rep):
    validate_stage_outcome("construccion", rep)
    plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
    (work / "lectura").mkdir(exist_ok=False)
    ver = vmg.VerificadorModeloGuardado(vmg.configuracion_real(work / "lectura", LOCK, timeout_s=3600))
    edb = work / "modelo.edb"
    prep = ver.preparar_verificacion(edb, epl.sha(edb), plan, criterios=epl.CRITERIOS)
    r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
    epl.guardar(work / "relectura_resultado.json", r.resultado)
    rep["fases"]["relectura"] = {"estado": r.resultado["estado"], "discrepancias": len(r.resultado["discrepancias"]),
                                 "incompletos": len(r.resultado["incompletos"]), "cobertura": r.resultado["cobertura"], "corrida": str(r.corrida)}


def etapa_analisis(work, rep, revision_controles=None):
    validate_stage_outcome("relectura", rep)
    modelo = rep["fases"]["construccion"]["registro_modelo"]
    if revision_controles is None:
        raise ValueError("Análisis requiere --revision-controles explícita; la relectura no confirma controles físicos.")
    revision_path = Path(revision_controles).resolve()
    review_raw = revision_path.read_bytes()
    review = json.loads(review_raw)
    review_sha = hashlib.sha256(review_raw).hexdigest()
    estado = rm.consultar(PRIV, CASO, modelo)
    validar_revision_controles(review, rm.CONTROLES, modelo, estado["huella_modelo"])
    for control, item in review["evidencias"].items():
        evidence_path = (RAIZ / item["referencia"]).resolve()
        if not evidence_path.is_relative_to(RAIZ.resolve()) or not evidence_path.is_file() or epl.sha(evidence_path).lower() != item["sha256"].lower():
            raise ValueError("Procedencia ausente/alterada del control: " + control)
    rep["fases"]["revision_controles_transporte"] = {
        "estado": "documentada", "procedencia": str(revision_path), "sha256": review_sha,
        "modelo_id": modelo, "huella_modelo": estado["huella_modelo"],
        "revisor_declarado": review["revisor"], "identidad_revisor": "declarada_no_verificada",
        "fecha": review["fecha"], "alcance_revision": review["alcance"],
        "controles": review["controles"], "evidencias": review["evidencias"],
        "alcance_autorizacion_software": ALCANCE, "aprueba_ingenieria": False}
    if revision_path.read_bytes() != review_raw:
        raise ValueError("La revisión cambió durante la comprobación; no se aprueba el modelo.")
    # Existing rm.aprobar contract: no new fields and no auto-generated True controls.
    aprob = rm.aprobar(PRIV, CASO, modelo, huella_esperada=estado["huella_modelo"],
                       revisor=review["revisor"], fecha=review["fecha"], alcance=ALCANCE,
                       controles=review["controles"])
    rep["fases"]["aprobacion_modelo_transporte"] = {"estado": "ok", "id": aprob.name}
    epl.guardar(work / "registro.json", rep)
    carpeta = carpeta_caso(PRIV, CASO)
    trabajo_an = carpeta / "analisis_etabs"
    trabajo_an.mkdir(exist_ok=True)
    analizador = an.AnalizadorEtabs(ad.ConfiguracionPuente.real(trabajo_an, LOCK, timeout_s=3600, script=an.SCRIPT))
    prep_an = analizador.preparar_analisis(PRIV, CASO, aprob.name)
    res_an = analizador.ejecutar_analisis(prep_an, confirmar_analisis=True)
    rep["fases"]["analisis"] = {"estado": "ok", "corrida": str(res_an.corrida)}
    # El puente de análisis guarda y reabre el resultado, pero NO cierra su instancia nueva (observado en 09d1, PID 35120).
    # Se cierra aquí SOLO esa instancia propia, con ApplicationExit verificado sobre su analizado.EDB y su huella aceptada.
    corrida_an = Path(res_an.corrida)
    resp_an = json.loads((corrida_an / "respuesta.json").read_text(encoding="utf-8"))
    acc_an = json.loads((corrida_an / "aceptacion_analisis.json").read_text(encoding="utf-8"))
    pid_an = resp_an["datos"]["id_proceso"]
    edb_an = corrida_an / "analizado.EDB"
    if resp_an["datos"].get("instancia_cerrada") is True:   # puente general corregido: ya cerró y lo declaró
        rep["fases"]["analisis"]["cierre_instancia_propia"] = {"id_proceso": pid_an, "confirmado": True, "por": "puente_analisis"}
    else:   # respuestas de puentes anteriores: cierre externo verificado de la instancia propia
        cerrado = epl.cerrar_propio(pid_an, edb_an, edb_an, corrida_an / "analizado.$et", acc_an["guardado"]["sha256"], LOCK,
                                    work / "cierre_analisis.log")
        rep["fases"]["analisis"]["cierre_instancia_propia"] = {"id_proceso": pid_an, "confirmado": bool(cerrado), "por": "runner"}
    epl.guardar(work / "registro.json", rep)
    trabajo_le = carpeta / "lecturas_analisis"
    trabajo_le.mkdir(exist_ok=True)
    lector = la.LectorAnalisis(la.configuracion_real(trabajo_le, LOCK, timeout_s=900))
    lecturas = {}
    for nombre, tablas, casos in (("reacciones", ["Base Reactions"], ["CM", "CV", "CAGUA", "SX", "SY"]),
                                  ("modal", ["Modal Periods And Frequencies", "Modal Participating Mass Ratios"], ["MODAL-E030"]),
                                  ("derivas", ["Story Drifts"], ["SX", "SY"])):
        prep_le = lector.preparar_lectura(PRIV, CASO, res_an.corrida, tablas=tablas, casos=casos)
        res_le = lector.ejecutar_lectura(prep_le, confirmar_lectura=True)
        epl.guardar(work / f"lectura_{nombre}.json", res_le.datos)
        lecturas[nombre] = {"estado": "ok", "corrida": str(getattr(res_le, "corrida", ""))}
    rep["fases"]["lecturas"] = lecturas
    # Masa ENSAMBLADA nativa (requisito del proyecto, R249-02): captura AssembledJointMass_1 del EDB analizado por el lector general
    # (instancia nueva, huellas) + libro completo de contribuciones desde la configuración aprobada, geometría y malla vigentes.
    # El resultado (coherente / no_coherente / no_leida) se registra tal cual; no relaja la guarda de etapa ni se convierte en éxito.
    try:
        from draft2model import libro_masa as lb, malla_preparacion as mpr, liquidos_malla as lmq
        from draft2model import gestion_geometria as ggm
        from draft2model.validacion_geometria import validar_geometria
        # «Mass Summary by Story» no tiene campo de caso y el lector la rechaza (09d1): tabla con caso + captura API de masa.
        prep_m = lector.preparar_lectura(PRIV, CASO, res_an.corrida, tablas=["Base Reactions"], casos=["CM"],
                                         resultados_api=["AssembledJointMass"])
        res_m = lector.ejecutar_lectura(prep_m, confirmar_lectura=True)
        epl.guardar(work / "lectura_masa.json", res_m.datos)
        config = json.loads((work / "configuracion.json").read_text(encoding="utf-8"))
        geo = ggm.consultar_version(PRIV, CASO, config["geometria_origen"]["version_id"]).geometria
        prep_malla = mpr.preparar_malla(geo, config)
        liq = lmq.preparar_liquidos(geo, config, prep_malla) if config.get("liquidos", {}).get("aplicabilidad") == "presente" else None
        libro = lb.libro_masa(config, validar_geometria(geo), prep_malla, liq)
        epl.guardar(work / "libro_masa.json", libro)
        contraste = lb.contrastar_masa_nativa(res_m.datos["resultados_api"]["AssembledJointMass"], libro,
                                              capture_id=prep_m.solicitud.id, fuente_esperada="MsSrc1", tolerancia_relativa=1e-3)
        epl.guardar(work / "contraste_masa_nativa.json", contraste)
        rep["fases"]["masa_nativa"] = {"estado": contraste["estado"], "masa_libro": contraste["masa_libro_kn_s2_m"],
                                       "masa_observada_U1": contraste.get("masa_observada_U1"),
                                       "diferencia_relativa_U1": contraste.get("diferencia_relativa_U1"),
                                       "codigo": contraste.get("codigo"), "lectura": prep_m.solicitud.id,
                                       "tolerancia_relativa": 1e-3, "fuente_esperada": "MsSrc1 (fuente por defecto editada por SetMassSource_1)"}
    except Exception as exc:
        rep["fases"]["masa_nativa"] = {"estado": "no_leida", "motivo": f"{type(exc).__name__}: {str(exc)[:800]}"}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trabajo", type=Path, required=True)
    ap.add_argument("--etapa", choices=("construccion", "relectura", "analisis"), required=True)
    ap.add_argument("--configuracion", type=Path, help="Configuración de transporte (por defecto tmp/ruta201/configuracion09t.json).")
    ap.add_argument("--revision-controles", type=Path, help="Evidencia explícita por control, solo para análisis; no se genera automáticamente.")
    a = ap.parse_args(argv)
    global CONFIG, ALCANCE
    if a.configuracion is not None:
        CONFIG = (RAIZ / a.configuracion).resolve()
        if not CONFIG.is_file() or not CONFIG.is_relative_to((RAIZ / "tmp").resolve()):
            raise ValueError("Configuración de transporte inexistente o fuera de tmp.")
        if "09d" in CONFIG.name:
            ALCANCE = ALCANCE_09D
    work = (RAIZ / a.trabajo).resolve()
    tmp_root = (RAIZ / "tmp").resolve()
    if work == tmp_root or not work.is_relative_to(tmp_root):
        raise ValueError("Carpeta de trabajo dentro de tmp requerida.")
    if Path(str(LOCK) + ".incierto.json").exists():
        raise ValueError("Hay incertidumbre del motor; no se abre instancia.")
    cargar_dependencias()
    work.mkdir(parents=True, exist_ok=a.etapa != "construccion")
    rep = registro(work)
    fuente_cfg = CONFIG.name   # nombre de la configuración de transporte usada por esta carpeta de trabajo
    if rep.get("configuracion_fuente", fuente_cfg) != fuente_cfg:
        raise ValueError("La carpeta de trabajo se construyó con otra configuración: " + rep["configuracion_fuente"])
    if a.etapa == "construccion":
        rep["configuracion_fuente"] = fuente_cfg   # registros previos (09t4) no la tienen y conservan su forma
    try:
        if a.etapa != "construccion":
            rep["sha256_plantilla_posterior"] = epl.sha(PLANTILLA)
            validate_stage_outcome("relectura" if a.etapa == "analisis" else "construccion", rep)
        if a.etapa == "analisis":
            revision = (RAIZ / a.revision_controles).resolve() if a.revision_controles is not None else None
            etapa_analisis(work, rep, revision_controles=revision)
        else:
            {"construccion": etapa_construccion, "relectura": etapa_relectura}[a.etapa](work, rep)
        rep["sha256_plantilla_posterior"] = epl.sha(PLANTILLA)
        validate_stage_outcome(a.etapa, rep)
    except Exception as exc:
        rep["fases"][a.etapa + "_error"] = {"tipo": type(exc).__name__, "error": str(exc)[:4000], "traza": traceback.format_exc()[-2500:]}
    epl.guardar(work / "registro.json", rep)
    print(json.dumps(rep["fases"], ensure_ascii=True, indent=1, default=str)[:6000])
    try:
        validate_stage_outcome(a.etapa, rep)
    except ValueError:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
