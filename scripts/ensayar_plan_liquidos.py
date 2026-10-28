"""Ensayo nativo SINTÉTICO del recorrido normal 0.5 (presión hidrostática) en ETABS local; no usa planos ni el modelo manual.

Configuración 0.5 real en disco (muro 5×2,6 m con puerta, corte Z=1,5 m, nivel libre 1,5 m, γ=10 kN/m³, patrón HIDRO
dedicado y caso estático CHIDRO) → plan 0.5 regenerado → construcción en instancia NUEVA sobre copia de plantilla →
guardado y registro → cierre SOLO del PID y rutas propios → relectura independiente (instancia nueva propia) →
aprobación SINTÉTICA declarada (solo software) → análisis → lectura de «Base Reactions» de CHIDRO frente a la
integral analítica del contorno neto. Todo en una carpeta NUEVA bajo tmp, con fuentes permanentes (sin TemporaryDirectory).
"""
import argparse
import base64
import hashlib
import json
import math
import subprocess
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from draft2model import adaptador_etabs as ad, ejecutor_etabs as ej  # noqa: E402
from draft2model import gestion_configuracion as gc, modelo_estructural as m  # noqa: E402
from draft2model import operaciones_etabs as op, revision_modelo as rm  # noqa: E402
from draft2model import verificacion_modelo_guardado as vmg  # noqa: E402
from draft2model import analisis_etabs as an, lectura_analisis as la  # noqa: E402
from draft2model.ejecucion_modelo import EjecutorVerificado  # noqa: E402
from draft2model.ingreso import registrar_expediente  # noqa: E402
from tests import test_gestion_geometria as disco  # noqa: E402
from tests.test_integracion_malla import REVISOR, F  # noqa: E402
from tests.test_liquidos_ruta201 import CasoLiquidos, declaracion  # noqa: E402
from tests.test_referencia_ruta201 import CasoReferencia  # noqa: E402

CRITERIOS = {"relativo": 1e-8, "absolutos": {k: 1e-8 for k in vmg.MAGNITUDES}}  # lectura, como relectura real 199
UMBRAL_EQUILIBRIO = 1e-7  # computacional (como ensayo 186); no tolerancia de ingeniería


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def guardar(p, x):
    Path(p).write_text(json.dumps(x, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def cerrar_propio(pid, copia, destino, alias, esperado, lock, salida):
    """Cierre por ApplicationExit(false) SOLO del PID nuevo y de sus rutas propias verificadas (patrón 198)."""
    q = lambda s: "'" + str(s).replace("'", "''") + "'"
    command = """$ErrorActionPreference='Stop'
function Hash([string]$ruta){$alg=[Security.Cryptography.SHA256]::Create();$f=[IO.File]::OpenRead($ruta);try{return [BitConverter]::ToString($alg.ComputeHash($f)).Replace('-','').ToLowerInvariant()}finally{$f.Dispose();$alg.Dispose()}}
Add-Type -Path 'C:\\Program Files\\Computers and Structures\\ETABS 21\\ETABSv1.dll'
$null=Get-Process -Id PID -ErrorAction Stop
$h=New-Object ETABSv1.Helper
$a=$h.GetObjectProcess('CSI.ETABS.API.ETABSObject',PID)
if($null -eq $a){throw 'Instancia propia no disponible; no se cierra otra.'}
$p=[IO.Path]::GetFullPath($a.SapModel.GetModelFilename($true))
Write-Output ('MODELO_OBSERVADO: '+$p)
if($p -ieq ALIAS){
 if(EXPECTED -eq '' -or -not (Test-Path -LiteralPath DEST)){throw 'Alias sin guardado verificable'}
 if((Hash DEST) -cne EXPECTED){throw 'Guardado cambiado; cierre cancelado'}
} elseif($p -ine COPY -and $p -ine DEST){throw 'Modelo distinto; cierre cancelado.'}
$rc=$a.ApplicationExit($false)
if($rc -ne 0){throw "Cierre devolvio $rc"}
Write-Output 'CIERRE_PROPIO_CONFIRMADO'
""".replace("PID", str(pid)).replace("COPY", q(copia)).replace("DEST", q(destino)).replace("ALIAS", q(alias)).replace("EXPECTED", q(esperado))
    with ad.BloqueoExclusivo(lock):
        close = subprocess.run([str(ad.POWERSHELL_51), "-NoProfile", "-NonInteractive", "-EncodedCommand",
                                base64.b64encode(command.encode("utf-16le")).decode()], capture_output=True, timeout=60)
    Path(salida).write_bytes(close.stdout + close.stderr)
    return close.returncode == 0 and b"CIERRE_PROPIO_CONFIRMADO" in close.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trabajo", type=Path, required=True)
    parser.add_argument("--confirmar-sintetico", action="store_true", required=True)
    parser.add_argument("--escenario", choices=("muro", "referencia"), default="muro",
                        help="muro: muro con puerta y cisterna; referencia: edificio sintético completo de 4 niveles (etapa 03)")
    args = parser.parse_args()
    work = args.trabajo.absolute()
    if not work.is_relative_to(ROOT / "tmp") or work.resolve() != work:
        raise ValueError("Carpeta nueva dentro de tmp requerida.")
    lock = ROOT / "tmp/d2/motor.lock"
    if Path(str(lock) + ".incierto.json").exists():
        raise ValueError("Hay incertidumbre del motor; no se abre instancia.")
    work.mkdir(exist_ok=False)
    source = ROOT / "tmp/d4/copia/plantilla_vacia.edb"
    original = sha(source)
    report = {"ensayo": "liquidos_0.5_muro_puerta_corte1.5_gamma10" if args.escenario == "muro" else "referencia_sintetica_4niveles_0.5", "datos_sinteticos": True, "etabs_real": True,
              "sha256_original": original, "fases": {}, "aprueba_ingenieria": False}
    firmas = op.verificar_firmas_dll()
    guardar(work / "firmas.json", firmas)
    if firmas["diferencias"]:
        raise ValueError("Firmas distintas; no se abre ETABS.")
    # Fuentes permanentes (no TemporaryDirectory: su finalizador las borraría).
    (work / "fuentes").mkdir()
    cm = CasoLiquidos() if args.escenario == "muro" else CasoReferencia()
    cm.f = disco.CasoGeometria()
    cm.f.trabajo = work / "fuentes"
    cm.f.raiz = cm.f.trabajo / "private"
    pdf = cm.f.trabajo / "plano_sintetico.pdf"
    pdf.write_bytes(b"%PDF-1.4\ncontenido sintetico para pruebas de geometria\n")  # no acredita render de planos
    cm.f.manifest = registrar_expediente(disco.CASO, [pdf], cm.f.raiz, uso_autorizado=True, provisional_fuera_alcance=True)
    cm.f.caso_dir = cm.f.manifest.parent
    cm.f.original = cm.f.caso_dir / "originales/lamina-0001.pdf"
    cm.f.entrada = cm.f.trabajo / "geometria.json"
    cm.f.entrada.write_bytes(disco.EJEMPLO.read_bytes())
    cm.raiz = cm.f.raiz
    if args.escenario == "muro":
        d, fuentes = declaracion("CISTERNA", 1.5, [("S1", 1)])
        data = cm.montar_liquidos("vertical_corte", "presente", [(d, fuentes, "HIDRO")])
    else:
        data = cm.montar_referencia()
    data["plantilla"]["sha256"] = original
    data["casos"].append({"id": "CHIDRO", "tipo": "estatico_lineal", "parametros": {"patrones": [{"patron": "HIDRO", "factor": 1}]}, "fuente": F})
    data["analisis"]["casos_ejecutar"].append("CHIDRO")
    cm.destino = str(work / "modelo.edb")
    config = cm.aprobar_en_disco(data)
    plan = op.generar_plan_por_version(cm.raiz, config, **cm.opciones(config)).datos
    guardar(work / "configuracion.json", config); guardar(work / "plan.json", plan)
    esperado_f = [math.fsum(h["fuerza_fuente_kn"][k] for h in plan["liquidos"]["hosts"]) for k in range(3)]
    esperado_m = [math.fsum(h["momento_fuente_kn_m"][k] for h in plan["liquidos"]["hosts"]) for k in range(3)]
    report.update(plan_huella=plan["huella_plan"], operaciones_plan=len(plan["operaciones"]), filas_liquido=len(plan["liquidos"]["filas"]),
                  fuerza_aplicada_fuente_kn=esperado_f, momento_aplicado_fuente_kn_m=esperado_m)
    caso = disco.CASO
    # 1. Construcción.
    (work / "apertura").mkdir(); (work / "motor").mkdir()
    bridge = ad.AdaptadorEtabs(ad.ConfiguracionPuente.real(work / "apertura", lock, timeout_s=180))
    opened = None
    try:
        opened = bridge.abrir_copia_plantilla(source, original, work / "copia", instancia="nueva")
        guardar(work / "apertura.json", opened.datos)
        pid = opened.datos["id_proceso"]; copia = Path(opened.datos["modelo_abierto"])
        executor = EjecutorVerificado(ej.configuracion_real(work / "motor", lock, timeout_s=300))
        prepared = executor.preparar(cm.raiz, config, plan, copia=copia, modelo_esperado=copia, id_proceso=pid)
        result = executor.ejecutar(prepared, confirmar_mutacion=True)
        registro = rm.registrar(cm.raiz, caso, config, plan, prepared.carpeta)
        report["fases"]["construccion"] = {"estado": "ok", "id_proceso": pid, "operaciones": result.operaciones_ejecutadas,
                                           "guardado": result.guardado, "registro_modelo": registro.name}
    except Exception as exc:
        report["fases"]["construccion"] = {"estado": "error", "tipo": type(exc).__name__, "error": str(exc)[:2000]}
    finally:
        if opened is not None:
            try:
                ok = cerrar_propio(opened.datos["id_proceso"], opened.datos["modelo_abierto"], work / "modelo.edb", work / "modelo.$et",
                                   report["fases"].get("construccion", {}).get("guardado", {}).get("sha256", ""), lock, work / "cierre.log")
                report["fases"].setdefault("construccion", {})["cierre_confirmado"] = ok
            except Exception as exc:
                report["fases"].setdefault("construccion", {})["error_cierre"] = str(exc)
        report["sha256_original_posterior"] = sha(source)
        guardar(work / "registro.json", report)
    cons = report["fases"]["construccion"]
    if cons.get("estado") != "ok" or not cons.get("cierre_confirmado"):
        resultado_global(report)
        guardar(work / "registro.json", report)
        print(json.dumps(report, ensure_ascii=True, indent=2)); return 2
    # 2. Relectura independiente del EDB guardado.
    try:
        (work / "lectura").mkdir()
        ver = vmg.VerificadorModeloGuardado(vmg.configuracion_real(work / "lectura", lock, timeout_s=600))
        edb = work / "modelo.edb"
        prep = ver.preparar_verificacion(edb, sha(edb), plan, criterios=CRITERIOS)
        r = ver.ejecutar_verificacion(prep, confirmar_lectura=True)
        res = r.resultado
        guardar(work / "relectura_resultado.json", res)
        report["fases"]["relectura"] = {"estado": res["estado"], "discrepancias": len(res["discrepancias"]), "incompletos": len(res["incompletos"]),
                                        "cobertura_malla": res["cobertura"].get("malla"), "cobertura_liquidos": res["cobertura"].get("cargas_liquidos"),
                                        "corrida": str(r.corrida)}
    except Exception as exc:
        report["fases"]["relectura"] = {"estado": "error", "tipo": type(exc).__name__, "error": str(exc)[:2000],
                                        "traza": traceback.format_exc()[-1500:]}
    guardar(work / "registro.json", report)
    # 3. Aprobación SINTÉTICA declarada (solo software), análisis y reacciones.
    try:
        modelo = cons["registro_modelo"]
        estado = rm.consultar(cm.raiz, caso, modelo)
        aprob = rm.aprobar(cm.raiz, caso, modelo, huella_esperada=estado["huella_modelo"], revisor="Revisor SINTÉTICO de software",
                           fecha="2026-10-21", alcance="Ensayo sintético de presión hidrostática; NO ingeniería ni proyecto real.",
                           controles={k: True for k in rm.CONTROLES})
        report["fases"]["aprobacion_sintetica"] = {"estado": "ok", "id": aprob.name}
    except Exception as exc:
        report["fases"]["aprobacion_sintetica"] = {"estado": "error", "tipo": type(exc).__name__, "error": str(exc)[:2000]}
    guardar(work / "registro.json", report)
    if report["fases"]["aprobacion_sintetica"]["estado"] == "ok":
        analizar_y_leer(work, cm.raiz, caso, report["fases"]["aprobacion_sintetica"]["id"], lock, report, esperado_f, esperado_m)
    codigo = resultado_global(report)
    guardar(work / "registro.json", report)
    print(json.dumps(report, ensure_ascii=True, indent=2, default=str))
    return codigo


def analizar_y_leer(work, raiz, caso, aprobacion, lock, report, esperado_f, esperado_m, sufijo=""):
    """Análisis en el grupo controlado `analisis_etabs` del caso, lectura de Base Reactions de CHIDRO y equilibrio.

    Cada fase registra su propio estado; un error nunca se oculta tras una fase anterior correcta.
    """
    from draft2model.gestion_extraccion import carpeta_caso
    carpeta = carpeta_caso(raiz, caso)
    try:
        trabajo_an = carpeta / "analisis_etabs"
        trabajo_an.mkdir(exist_ok=True)
        analizador = an.AnalizadorEtabs(ad.ConfiguracionPuente.real(trabajo_an, lock, timeout_s=900, script=an.SCRIPT))
        prep_an = analizador.preparar_analisis(raiz, caso, aprobacion)
        res_an = analizador.ejecutar_analisis(prep_an, confirmar_analisis=True)
        report["fases"]["analisis" + sufijo] = {"estado": "ok", "corrida": str(res_an.corrida), "aprobacion_sintetica": aprobacion}
    except Exception as exc:
        report["fases"]["analisis" + sufijo] = {"estado": "error", "tipo": type(exc).__name__, "error": str(exc)[:2000],
                                                "traza": traceback.format_exc()[-1500:]}
        guardar(work / "registro.json", report)
        return
    guardar(work / "registro.json", report)
    try:
        trabajo_le = carpeta / "lecturas_analisis"
        trabajo_le.mkdir(exist_ok=True)
        lector = la.LectorAnalisis(la.configuracion_real(trabajo_le, lock, timeout_s=300))
        prep_le = lector.preparar_lectura(raiz, caso, res_an.corrida, tablas=["Base Reactions"], casos=["CHIDRO"], resultados_api=["BaseReact"])
        res_le = lector.ejecutar_lectura(prep_le, confirmar_lectura=True)
        datos = res_le.datos
        guardar(work / ("lectura_reacciones" + sufijo + ".json"), datos)
        report["fases"]["lectura_resultados" + sufijo] = {"estado": "ok", "corrida": str(getattr(res_le, "corrida", ""))}
        report["fases"]["equilibrio" + sufijo] = equilibrio(datos, esperado_f, esperado_m)
        report["fases"]["equilibrio_api" + sufijo] = equilibrio_api(datos, esperado_f, esperado_m)
    except Exception as exc:
        report["fases"]["lectura_resultados" + sufijo] = {"estado": "error", "tipo": type(exc).__name__, "error": str(exc)[:2000],
                                                          "traza": traceback.format_exc()[-1500:]}
    guardar(work / "registro.json", report)


def equilibrio_api(datos, esperado_f, esperado_m):
    """Criterio ESTRICTO con dobles tipados de BaseReact (sin redondeo de tabla). Punto de reacción declarado por ETABS."""
    br = (datos.get("resultados_api") or {}).get("BaseReact")
    if not isinstance(br, dict):
        return {"estado": "no_disponible", "motivo": "La lectura no incluye BaseReact tipado."}
    filas = [f for f in br["filas"] if f["LoadCase"] == "CHIDRO"]
    punto = [float(x) for x in br["punto_reaccion"]]
    if len(filas) != 1 or punto != [0.0, 0.0, 0.0]:
        return {"estado": "no_comparable", "motivo": f"{len(filas)} filas CHIDRO o punto de reacción {punto} distinto del origen de momentos (0,0,0)"}
    f = filas[0]
    reaccion_f = [float(f[k]) for k in ("FX", "FY", "FZ")]
    reaccion_m = [float(f[k]) for k in ("MX", "MY", "MZ")]
    residuo_f = [reaccion_f[k] + esperado_f[k] for k in range(3)]
    residuo_m = [reaccion_m[k] + esperado_m[k] for k in range(3)]
    umbrales = [UMBRAL_EQUILIBRIO * max(1.0, abs(e)) for e in esperado_f + esperado_m]
    ok = all(abs(r) <= u for r, u in zip(residuo_f + residuo_m, umbrales))
    return {"estado": "equilibrio_estricto" if ok else "residuo_excede", "fuente": "cAnalysisResults.BaseReact (dobles, texto R invariante)",
            "unidades": br["unidades"], "punto_reaccion": br["punto_reaccion"], "fila": f, "reaccion_fuerza_kn": reaccion_f,
            "reaccion_momento_kn_m": reaccion_m, "residuo_fuerza_kn": residuo_f, "residuo_momento_kn_m": residuo_m,
            "umbral_computacional_por_componente": umbrales, "aprueba_ingenieria": False}


def resultado_global(report):
    """Aceptación del ensayo SOLO si todas las fases obligatorias pasan y el equilibrio ESTRICTO (API) se cumple."""
    f = report["fases"]
    cons = f.get("construccion", {})
    rel = f.get("relectura", {})
    lecturas = [k for k in f if k.startswith("lectura_resultados")]
    eq_api = [f[k] for k in f if k.startswith("equilibrio_api")]
    fallos = []
    if cons.get("estado") != "ok" or not cons.get("cierre_confirmado"):
        fallos.append("construccion/cierre")
    if rel.get("estado") != "verificado":
        fallos.append("relectura")
    if not any(f[k].get("estado") == "ok" for k in f if k.startswith("analisis")):
        fallos.append("analisis")
    if not any(f[k].get("estado") == "ok" for k in lecturas):
        fallos.append("lectura_resultados")
    if not any(e.get("estado") == "equilibrio_estricto" for e in eq_api):
        fallos.append("equilibrio_estricto_api")
    report["resultado_global"] = {"aceptado": not fallos, "fases_pendientes_o_fallidas": fallos,
                                  "aprueba_ingenieria": False, "datos_sinteticos": True}
    return 0 if not fallos else 2


def equilibrio(datos, esperado_f, esperado_m):
    """Reacción de base de CHIDRO = −(carga aplicada); momentos respecto del origen global (0,0,0) de la declaración."""
    filas = []

    def buscar(x):
        if isinstance(x, dict):
            if x.get("OutputCase") == "CHIDRO" and "FX" in x:
                filas.append(x)
            for valor in x.values():
                buscar(valor)
        elif isinstance(x, list):
            for valor in x:
                buscar(valor)
    buscar(datos)
    if len(filas) != 1:
        return {"estado": "no_comparable", "motivo": f"{len(filas)} filas Base Reactions de CHIDRO (se esperaba una)"}
    f = filas[0]
    reaccion_f = [float(f[k]) for k in ("FX", "FY", "FZ")]
    reaccion_m = [float(f[k]) for k in ("MX", "MY", "MZ")]
    residuo_f = [reaccion_f[k] + esperado_f[k] for k in range(3)]
    residuo_m = [reaccion_m[k] + esperado_m[k] for k in range(3)]
    ok = all(abs(r) <= UMBRAL_EQUILIBRIO * max(1.0, abs(e)) for r, e in zip(residuo_f + residuo_m, esperado_f + esperado_m))

    def media_unidad(texto):
        """Resolución del texto mostrado por la tabla: media unidad de la última cifra (p. ej. '-25.5933' → 5e-5)."""
        t = texto.strip().lower().lstrip("+-")
        mantisa, _, exp = t.partition("e")
        dec = len(mantisa.split(".")[1]) if "." in mantisa else 0
        return 0.5 * 10 ** (-dec + (int(exp) if exp else 0))
    resol = [media_unidad(f[k]) for k in ("FX", "FY", "FZ", "MX", "MY", "MZ")]
    ok_mostrado = all(abs(r) <= h for r, h in zip(residuo_f + residuo_m, resol))
    return {"estado": "equilibrio_sintetico" if ok else "residuo_excede",
            "estado_precision_mostrada": "equilibrio_a_precision_de_tabla" if ok_mostrado else "residuo_excede_precision_de_tabla",
            "resolucion_texto_tabla": resol,
            "nota": "Base Reactions se lee de la tabla de visualización (texto con ~6 cifras significativas); el umbral 1e-7 "
                    "solo aplica a dobles de la API. Ambos estados se informan; no se sustituye uno por otro.",
            "fila": f, "reaccion_fuerza_kn": reaccion_f,
            "reaccion_momento_kn_m": reaccion_m, "aplicado_fuente_kn": esperado_f, "aplicado_fuente_kn_m": esperado_m,
            "residuo_fuerza_kn": residuo_f, "residuo_momento_kn_m": residuo_m, "umbral_computacional": UMBRAL_EQUILIBRIO,
            "aprueba_ingenieria": False}


def reanudar(work):
    """Continúa SOLO análisis/lectura de un ensayo con construcción, registro, cierre y aprobación sintética ya hechos."""
    work = Path(work).absolute()
    report = json.loads((work / "registro.json").read_text(encoding="utf-8"))
    plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
    aprob = (report["fases"].get("aprobacion_sintetica") or {}).get("id") or report["fases"]["analisis"]["aprobacion_sintetica"]
    lock = ROOT / "tmp/d2/motor.lock"
    if Path(str(lock) + ".incierto.json").exists():
        raise ValueError("Hay incertidumbre del motor; no se abre instancia.")
    ef = [math.fsum(h["fuerza_fuente_kn"][k] for h in plan["liquidos"]["hosts"]) for k in range(3)]
    em = [math.fsum(h["momento_fuente_kn_m"][k] for h in plan["liquidos"]["hosts"]) for k in range(3)]
    analizar_y_leer(work, work / "fuentes" / "private", disco.CASO, aprob, lock, report, ef, em, sufijo="_controlado")
    codigo = resultado_global(report)
    guardar(work / "registro.json", report)
    print(json.dumps({k: v for k, v in report["fases"].items() if k.endswith("_controlado")}, ensure_ascii=True, indent=2, default=str))
    print(json.dumps(report["resultado_global"], ensure_ascii=True))
    return codigo


def leer(work, corrida_id, sufijo):
    """Solo lectura de Base Reactions de una corrida de análisis ACEPTADA (sin nuevo análisis) y equilibrio."""
    work = Path(work).absolute()
    report = json.loads((work / "registro.json").read_text(encoding="utf-8"))
    plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
    lock = ROOT / "tmp/d2/motor.lock"
    if Path(str(lock) + ".incierto.json").exists():
        raise ValueError("Hay incertidumbre del motor; no se abre instancia.")
    from draft2model.gestion_extraccion import carpeta_caso
    raiz = work / "fuentes" / "private"
    carpeta = carpeta_caso(raiz, disco.CASO)
    ef = [math.fsum(h["fuerza_fuente_kn"][k] for h in plan["liquidos"]["hosts"]) for k in range(3)]
    em = [math.fsum(h["momento_fuente_kn_m"][k] for h in plan["liquidos"]["hosts"]) for k in range(3)]
    try:
        lector = la.LectorAnalisis(la.configuracion_real(carpeta / "lecturas_analisis", lock, timeout_s=300))
        prep = lector.preparar_lectura(raiz, disco.CASO, carpeta / "analisis_etabs" / corrida_id, tablas=["Base Reactions"], casos=["CHIDRO"], resultados_api=["BaseReact"])
        res = lector.ejecutar_lectura(prep, confirmar_lectura=True)
        guardar(work / ("lectura_reacciones" + sufijo + ".json"), res.datos)
        report["fases"]["lectura_resultados" + sufijo] = {"estado": "ok", "corrida_analisis": corrida_id}
        report["fases"]["equilibrio" + sufijo] = equilibrio(res.datos, ef, em)
        report["fases"]["equilibrio_api" + sufijo] = equilibrio_api(res.datos, ef, em)
    except Exception as exc:
        report["fases"]["lectura_resultados" + sufijo] = {"estado": "error", "tipo": type(exc).__name__, "error": str(exc)[:2000],
                                                          "traza": traceback.format_exc()[-1500:]}
    codigo = resultado_global(report)
    guardar(work / "registro.json", report)
    print(json.dumps({k: v for k, v in report["fases"].items() if k.endswith(sufijo)}, ensure_ascii=True, indent=2, default=str))
    print(json.dumps(report["resultado_global"], ensure_ascii=True))
    return codigo


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--reanudar-analisis":
        raise SystemExit(reanudar(sys.argv[2]))
    if len(sys.argv) == 5 and sys.argv[1] == "--leer":
        raise SystemExit(leer(sys.argv[2], sys.argv[3], sys.argv[4]))
    raise SystemExit(main())
