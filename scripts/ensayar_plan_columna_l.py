"""Ensayo nativo SINTÉTICO del recorrido normal 0.5 con sección L nativa e inserción en el centroide (Codex 246).

Configuración 0.5 en disco (escenario «conectados»: losa + muro + viga subdividida) con la viga en `frame_l_concreto`
(espejo_eje_2) e `insercion_frames` (cardinal 10, desplazamiento global) → plan 0.5 → construcción en instancia NUEVA
sobre copia de plantilla sintética (el ejecutor relee GetConcreteL/GetInsertionPoint) → guardado → cierre SOLO del PID
propio → relectura independiente del EDB guardado en otra instancia propia (verificacion_modelo_guardado, incluida la L
y la inserción). Sin análisis ni aprobación: acredita transporte y relectura, no ingeniería.
"""
import argparse
import importlib.util
import json
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from draft2model import adaptador_etabs as ad, ejecutor_etabs as ej  # noqa: E402
from draft2model import operaciones_etabs as op, revision_modelo as rm  # noqa: E402
from draft2model import verificacion_modelo_guardado as vmg  # noqa: E402
from draft2model.ejecucion_modelo import EjecutorVerificado  # noqa: E402
from draft2model.ingreso import registrar_expediente  # noqa: E402
from tests import test_gestion_geometria as disco  # noqa: E402
from tests.test_columna_l_246 import con_l  # noqa: E402
from tests.test_liquidos_ruta201 import CasoLiquidos  # noqa: E402

_spec = importlib.util.spec_from_file_location("ensayar_plan_liquidos", ROOT / "scripts/ensayar_plan_liquidos.py")
epl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(epl)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trabajo", type=Path, required=True)
    parser.add_argument("--confirmar-sintetico", action="store_true", required=True)
    args = parser.parse_args()
    work = args.trabajo.absolute()
    if not work.is_relative_to(ROOT / "tmp") or work.resolve() != work:
        raise ValueError("Carpeta nueva dentro de tmp requerida.")
    lock = ROOT / "tmp/d2/motor.lock"
    if Path(str(lock) + ".incierto.json").exists():
        raise ValueError("Hay incertidumbre del motor; no se abre instancia.")
    work.mkdir(exist_ok=False)
    source = ROOT / "tmp/d4/copia/plantilla_vacia.edb"
    original = epl.sha(source)
    report = {"ensayo": "columna_l_insercion_0.5", "datos_sinteticos": True, "etabs_real": True, "sha256_original": original,
              "fases": {}, "aprueba_ingenieria": False}
    firmas = op.verificar_firmas_dll()
    epl.guardar(work / "firmas.json", firmas)
    if firmas["diferencias"]:
        raise ValueError("Firmas distintas; no se abre ETABS.")
    (work / "fuentes").mkdir()
    cm = CasoLiquidos()
    cm.f = disco.CasoGeometria()
    cm.f.trabajo = work / "fuentes"
    cm.f.raiz = cm.f.trabajo / "private"
    pdf = cm.f.trabajo / "plano_sintetico.pdf"
    pdf.write_bytes(b"%PDF-1.4\ncontenido sintetico para pruebas de geometria\n")
    cm.f.manifest = registrar_expediente(disco.CASO, [pdf], cm.f.raiz, uso_autorizado=True, provisional_fuera_alcance=True)
    cm.f.caso_dir = cm.f.manifest.parent
    cm.f.original = cm.f.caso_dir / "originales/lamina-0001.pdf"
    cm.f.entrada = cm.f.trabajo / "geometria.json"
    cm.f.entrada.write_bytes(disco.EJEMPLO.read_bytes())
    cm.raiz = cm.f.raiz
    data = con_l(cm.montar_liquidos("conectados", "ausente_confirmado", patrones=()))
    data["plantilla"]["sha256"] = original
    cm.destino = str(work / "modelo.edb")
    config = cm.aprobar_en_disco(data)
    plan = op.generar_plan_por_version(cm.raiz, config, **cm.opciones(config)).datos
    epl.guardar(work / "configuracion.json", config)
    epl.guardar(work / "plan.json", plan)
    nuevos = [o["metodo"] for o in plan["operaciones"] if o["metodo"] in
              ("cPropFrame.SetConcreteL", "cPropFrame.GetConcreteL", "cFrameObj.SetInsertionPoint", "cFrameObj.GetInsertionPoint")]
    report.update(plan_huella=plan["huella_plan"], operaciones_plan=len(plan["operaciones"]), operaciones_l_insercion=nuevos)
    (work / "apertura").mkdir(); (work / "motor").mkdir()
    bridge = ad.AdaptadorEtabs(ad.ConfiguracionPuente.real(work / "apertura", lock, timeout_s=180))
    opened = None
    try:
        opened = bridge.abrir_copia_plantilla(source, original, work / "copia", instancia="nueva")
        epl.guardar(work / "apertura.json", opened.datos)
        pid = opened.datos["id_proceso"]; copia = Path(opened.datos["modelo_abierto"])
        executor = EjecutorVerificado(ej.configuracion_real(work / "motor", lock, timeout_s=300))
        prepared = executor.preparar(cm.raiz, config, plan, copia=copia, modelo_esperado=copia, id_proceso=pid)
        result = executor.ejecutar(prepared, confirmar_mutacion=True)
        registro = rm.registrar(cm.raiz, disco.CASO, config, plan, prepared.carpeta)
        report["fases"]["construccion"] = {"estado": "ok", "id_proceso": pid, "operaciones": result.operaciones_ejecutadas,
                                           "guardado": result.guardado, "registro_modelo": registro.name}
    except Exception as exc:
        report["fases"]["construccion"] = {"estado": "error", "tipo": type(exc).__name__, "error": str(exc)[:3000],
                                           "traza": traceback.format_exc()[-2000:]}
    finally:
        if opened is not None:
            try:
                ok = epl.cerrar_propio(opened.datos["id_proceso"], opened.datos["modelo_abierto"], work / "modelo.edb", work / "modelo.$et",
                                       report["fases"].get("construccion", {}).get("guardado", {}).get("sha256", ""), lock, work / "cierre.log")
                report["fases"].setdefault("construccion", {})["cierre_confirmado"] = ok
            except Exception as exc:
                report["fases"].setdefault("construccion", {})["error_cierre"] = str(exc)
        report["sha256_original_posterior"] = epl.sha(source)
        epl.guardar(work / "registro.json", report)
    cons = report["fases"]["construccion"]
    if cons.get("estado") != "ok" or not cons.get("cierre_confirmado"):
        print(json.dumps(report, ensure_ascii=True, indent=2, default=str))
        return 2
    try:
        (work / "lectura").mkdir()
        ver = vmg.VerificadorModeloGuardado(vmg.configuracion_real(work / "lectura", lock, timeout_s=600))
        edb = work / "modelo.edb"
        prep = ver.preparar_verificacion(edb, epl.sha(edb), plan, criterios=epl.CRITERIOS)
        r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
        res = r.resultado
        epl.guardar(work / "relectura_resultado.json", res)
        report["fases"]["relectura"] = {"estado": res["estado"], "discrepancias": res["discrepancias"][:20], "incompletos": res["incompletos"][:20],
                                        "cobertura_propiedades_frame": res["cobertura"].get("propiedades_frame"),
                                        "cobertura_frames": res["cobertura"].get("frames"), "corrida": str(r.corrida)}
    except Exception as exc:
        report["fases"]["relectura"] = {"estado": "error", "tipo": type(exc).__name__, "error": str(exc)[:3000],
                                        "traza": traceback.format_exc()[-2000:]}
    epl.guardar(work / "registro.json", report)
    print(json.dumps(report, ensure_ascii=True, indent=2, default=str))
    return 0 if report["fases"]["relectura"].get("estado") == "verificado" else 1


if __name__ == "__main__":
    raise SystemExit(main())
