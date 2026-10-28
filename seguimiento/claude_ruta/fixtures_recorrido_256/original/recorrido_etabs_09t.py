"""Recorrido ETABS propio POR ETAPAS del caso real en el ESCENARIO DE TRANSPORTE (autorización del usuario 2026-10-22).

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
REVISOR = "Usuario (autorización en chat 2026-10-22: aprobación declarada SOLO de transporte de software), registrada por Claude"
ALCANCE = ("TRANSPORTE DE SOFTWARE del piloto (escenario de transporte 09T: S1 + R0 = 6 hipotéticos, escalera como cargas, agua en "
           "escenarios). NO es aprobación de ingeniería ni de diseño; no certifica seguridad ni cumplimiento normativo.")
EIGEN = {"frecuencia_desplazamiento_hz": 0.0, "frecuencia_corte_hz": 0.0, "tolerancia": 1e-9, "desplazamiento_automatico": True}
LOSAS = {"LOSA-MEMB-05": ("Membrane", "piso", "Piso con diafragma rígido; E.030 30.8 excluye la rigidez fuera del plano del piso."),
         "DEP-FONDO-20": ("ShellThick", "fondo_deposito", "Fondo de depósito: resiste la presión del agua por flexión (R241)."),
         "DEP-TAPA-15": ("ShellThick", "tapa_deposito", "Tapa de cisterna con flexión (R241)."),
         "DEP-TAPA-20": ("ShellThick", "tapa_deposito", "Tapa de tanque con flexión (R241).")}


def opciones(config, destino):
    return {"destino_guardado": str(destino), "tipo_shell_muro": "ShellThin", "gravedad_programa_m_s2": 9.80665,
            "tipo_shell_losa": {s: {"tipo": t, "funcion": f, "justificacion": j} for s, (t, f, j) in LOSAS.items()
                                if s in {x["id"] for x in config["secciones"]}},
            "parametros_modales": {"MODAL": EIGEN}, "amortiguamiento_funciones": {"ESP-S1-R6-HIP": 0.05},
            "excentricidad_espectral": {"SX": 0.05, "SY": 0.05}, "respuesta_rigida_espectral": {"SX": False, "SY": False}}


def registro(work):
    p = work / "registro.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {
        "recorrido": "caso_real_transporte_09t", "caso": CASO, "datos_sinteticos": False, "etabs_real": True,
        "aprobacion": "declarada SOLO de transporte de software (autorización del usuario)", "aprueba_ingenieria": False, "fases": {}}


def etapa_construccion(work, rep):
    if (work / "plan.json").exists():
        raise ValueError("La construcción ya se ejecutó en esta carpeta; use otra carpeta nueva.")
    cfg = json.loads((RAIZ / "tmp/ruta201/configuracion09t.json").read_text(encoding="utf-8"))
    imp = gc.importar(PRIV, CASO, RAIZ / "tmp/ruta201/configuracion09t.json")
    rev = gc.revisar(PRIV, CASO, imp["id"], cfg, revisor=REVISOR, fecha=FECHA,
                     motivo="Configuración 09T revisada para transporte (política de nodos derivados declarada por el guion 09C).")
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
    if original != config["plantilla"]["sha256"]:
        raise ValueError("La plantilla del caso no coincide con la configuración.")
    (work / "apertura").mkdir(); (work / "motor").mkdir()
    bridge = ad.AdaptadorEtabs(ad.ConfiguracionPuente.real(work / "apertura", LOCK, timeout_s=300))
    opened = None
    try:
        opened = bridge.abrir_copia_plantilla(PLANTILLA, original, work / "copia", instancia="nueva")
        epl.guardar(work / "apertura.json", opened.datos)
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
    plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
    (work / "lectura").mkdir(exist_ok=False)
    ver = vmg.VerificadorModeloGuardado(vmg.configuracion_real(work / "lectura", LOCK, timeout_s=3600))
    edb = work / "modelo.edb"
    prep = ver.preparar_verificacion(edb, epl.sha(edb), plan, criterios=epl.CRITERIOS)
    r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
    epl.guardar(work / "relectura_resultado.json", r.resultado)
    rep["fases"]["relectura"] = {"estado": r.resultado["estado"], "discrepancias": len(r.resultado["discrepancias"]),
                                 "incompletos": len(r.resultado["incompletos"]), "cobertura": r.resultado["cobertura"], "corrida": str(r.corrida)}


def etapa_analisis(work, rep):
    modelo = rep["fases"]["construccion"]["registro_modelo"]
    if rep["fases"].get("relectura", {}).get("estado") != "verificado":
        raise ValueError("Sin relectura verificada no se aprueba el modelo para transporte ni se analiza.")
    estado = rm.consultar(PRIV, CASO, modelo)
    aprob = rm.aprobar(PRIV, CASO, modelo, huella_esperada=estado["huella_modelo"], revisor=REVISOR, fecha=FECHA, alcance=ALCANCE,
                       controles={k: True for k in rm.CONTROLES})
    rep["fases"]["aprobacion_modelo_transporte"] = {"estado": "ok", "id": aprob.name}
    epl.guardar(work / "registro.json", rep)
    carpeta = carpeta_caso(PRIV, CASO)
    trabajo_an = carpeta / "analisis_etabs"
    trabajo_an.mkdir(exist_ok=True)
    analizador = an.AnalizadorEtabs(ad.ConfiguracionPuente.real(trabajo_an, LOCK, timeout_s=3600, script=an.SCRIPT))
    prep_an = analizador.preparar_analisis(PRIV, CASO, aprob.name)
    res_an = analizador.ejecutar_analisis(prep_an, confirmar_analisis=True)
    rep["fases"]["analisis"] = {"estado": "ok", "corrida": str(res_an.corrida)}
    epl.guardar(work / "registro.json", rep)
    trabajo_le = carpeta / "lecturas_analisis"
    trabajo_le.mkdir(exist_ok=True)
    lector = la.LectorAnalisis(la.configuracion_real(trabajo_le, LOCK, timeout_s=900))
    lecturas = {}
    for nombre, tablas, casos in (("reacciones", ["Base Reactions"], ["CM", "CV", "CAGUA", "SX", "SY"]),
                                  ("modal", ["Modal Periods And Frequencies", "Modal Participating Mass Ratios"], ["MODAL"]),
                                  ("derivas", ["Story Drifts"], ["SX", "SY"])):
        prep_le = lector.preparar_lectura(PRIV, CASO, res_an.corrida, tablas=tablas, casos=casos)
        res_le = lector.ejecutar_lectura(prep_le, confirmar_lectura=True)
        epl.guardar(work / f"lectura_{nombre}.json", res_le.datos)
        lecturas[nombre] = {"estado": "ok", "corrida": str(getattr(res_le, "corrida", ""))}
    rep["fases"]["lecturas"] = lecturas


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trabajo", type=Path, required=True)
    ap.add_argument("--etapa", choices=("construccion", "relectura", "analisis"), required=True)
    a = ap.parse_args()
    work = (RAIZ / a.trabajo).resolve() if not a.trabajo.is_absolute() else a.trabajo
    if not work.is_relative_to(RAIZ / "tmp"):
        raise ValueError("Carpeta de trabajo dentro de tmp requerida.")
    if Path(str(LOCK) + ".incierto.json").exists():
        raise ValueError("Hay incertidumbre del motor; no se abre instancia.")
    work.mkdir(parents=True, exist_ok=a.etapa != "construccion")
    rep = registro(work)
    try:
        {"construccion": etapa_construccion, "relectura": etapa_relectura, "analisis": etapa_analisis}[a.etapa](work, rep)
    except Exception as exc:
        rep["fases"][a.etapa + "_error"] = {"tipo": type(exc).__name__, "error": str(exc)[:4000], "traza": traceback.format_exc()[-2500:]}
    epl.guardar(work / "registro.json", rep)
    print(json.dumps(rep["fases"], ensure_ascii=True, indent=1, default=str)[:6000])
    fallo = any(k.endswith("_error") or (isinstance(v, dict) and v.get("estado") == "error") for k, v in rep["fases"].items())
    return 1 if fallo else 0


if __name__ == "__main__":
    raise SystemExit(main())
