"""Resultados → informe del recorrido 09D (ruta 253, tarea 5) con el flujo GENERAL del producto.

Ejecutar desde la raíz, tras la etapa de análisis del runner:
    python seguimiento/claude_ruta/resultados_09.py --trabajo tmp/recorrido_09d1 [--etapa lectura|normalizacion|informe]

1. lectura: una lectura propia (instancia nueva) de las tablas Modal/Story Drifts/Base Reactions del EDB analizado.
2. normalizacion: mapeo explícito de selectores construido desde las filas leídas (unicidad comprobada), revisión DECLARADA de
   software por Claude (no ingeniería), registro de resultados_estructurales.
3. controles (ServicioControles) y reglas E.030 aplicadas a los escenarios identificados (aprobación declarada de software).
4. informe: crear_informe + exportar JSON/HTML/PDF con evidencia de análisis, controles, evaluación condicionada, inventario de
   contenido y masa nativa (si existe).
   Sitio referencial: no disponible (no hay capa revisada); el suelo S1 es hipótesis de transporte, no EMS.
Cada etapa escribe en <trabajo>/resultados/ y en registro_resultados.json; nada se sobrescribe.
"""
import argparse
import hashlib
import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
import sys  # noqa: E402
sys.path.insert(0, str(RAIZ))
PRIV, CASO = RAIZ / "data/private", "pueblo-libre-002"
LOCK = RAIZ / "tmp/d2/motor.lock"
FECHA = "2026-10-22"
TABLAS = ["Modal Periods And Frequencies", "Story Drifts", "Base Reactions"]
CASOS = ["MODAL-E030", "SX", "SY"]
PISOS = ["N1", "N2", "N3", "N4"]
REVISOR = "Claude (ruta 09): revisión propia de software de los selectores; NO ingeniería ni usuario"


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def guardar(p, obj):
    p = Path(p)
    if p.exists():
        raise SystemExit("No se sobrescribe: " + str(p))
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def unico(filas, filtros, tabla):
    c = [f for f in filas if all(f.get(k) == v for k, v in filtros.items())]
    if len(c) != 1:
        raise SystemExit(f"Selector no único en {tabla}: {filtros} → {len(c)} filas; no se elige automáticamente.")
    return c[0]


def etapa_lectura(work, reg):
    from draft2model import lectura_analisis as la
    from draft2model.gestion_extraccion import carpeta_caso
    rep = json.loads((work / "registro.json").read_text(encoding="utf-8"))
    corrida = Path(rep["fases"]["analisis"]["corrida"])
    trabajo = carpeta_caso(PRIV, CASO) / "lecturas_analisis"
    trabajo.mkdir(exist_ok=True)
    lector = la.LectorAnalisis(la.configuracion_real(trabajo, LOCK, timeout_s=900))
    prep = lector.preparar_lectura(PRIV, CASO, corrida, tablas=TABLAS, casos=CASOS)
    res = lector.ejecutar_lectura(prep, confirmar_lectura=True)
    reg["lectura"] = {"id": prep.solicitud.id, "respuesta": str(prep.solicitud.respuesta), "sha256": sha(prep.solicitud.respuesta),
                      "corrida_analisis": str(corrida)}


def etapa_masa(work, reg):
    """Masa ensamblada NATIVA: lectura del lector general (instancia nueva, mismo análisis/EDB) con AssembledJointMass_1 y una
    tabla con campo de caso (Base Reactions/CM: «Mass Summary by Story» no tiene campo de caso y el lector la rechaza, como
    registró el runner) + libro de contribuciones + contraste masa_ensamblada (tolerancia relativa 1e-3, fuente MsSrc1)."""
    from draft2model import gestion_geometria as ggm, libro_masa as lb, liquidos_malla as lmq, malla_preparacion as mpr
    from draft2model import lectura_analisis as la
    from draft2model.gestion_extraccion import carpeta_caso
    from draft2model.validacion_geometria import validar_geometria
    rep = json.loads((work / "registro.json").read_text(encoding="utf-8"))
    corrida = Path(rep["fases"]["analisis"]["corrida"])
    trabajo = carpeta_caso(PRIV, CASO) / "lecturas_analisis"
    lector = la.LectorAnalisis(la.configuracion_real(trabajo, LOCK, timeout_s=1800))
    prep = lector.preparar_lectura(PRIV, CASO, corrida, tablas=["Base Reactions"], casos=["CM"], resultados_api=["AssembledJointMass"])
    res = lector.ejecutar_lectura(prep, confirmar_lectura=True)
    captura = res.datos["resultados_api"]["AssembledJointMass"]
    cfg = json.loads((work / "configuracion.json").read_text(encoding="utf-8"))
    geo = ggm.consultar_version(PRIV, CASO, cfg["geometria_origen"]["version_id"]).geometria
    malla = mpr.preparar_malla(geo, cfg)
    liq = lmq.preparar_liquidos(geo, cfg, malla)
    libro = lb.libro_masa(cfg, validar_geometria(geo), malla, liq)
    out = work / "resultados"
    out.mkdir(exist_ok=True)
    guardar(out / "libro_masa.json", libro)
    contraste = lb.contrastar_masa_nativa(captura, libro, capture_id=prep.solicitud.id, fuente_esperada="MsSrc1", tolerancia_relativa=1e-3)
    guardar(out / "contraste_masa_nativa.json", contraste)
    # Masa sísmica sobre la base (z > 0): puntos no apoyados en la base ni de la cisterna; incluye el tanque (sobre N4).
    obs = captura["observaciones"]
    m_sobre = sum(float(o["U1"]) for o in obs if float(o["global_xyz"][2]) > 1e-6)
    reg["masa"] = {"lectura": prep.solicitud.id, "respuesta_sha256": sha(prep.solicitud.respuesta), "estado": contraste["estado"],
                   "codigo": contraste.get("codigo"), "masa_libro": libro["masa_total_kn_s2_m"],
                   "masa_observada_U1": contraste.get("masa_observada_U1"), "masa_observada_U2": contraste.get("masa_observada_U2"),
                   "diferencia_relativa_U1": contraste.get("diferencia_relativa_U1"),
                   "contribuciones": {k: v["masa_kn_s2_m"] for k, v in libro["contribuciones"].items()},
                   "masa_sobre_base_U1": m_sobre, "P_sobre_base_kN": m_sobre * cfg["masa"]["gravedad_m_s2"], "puntos": len(obs)}


def etapa_normalizacion(work, reg):
    from draft2model import normalizacion_etabs as ne
    from draft2model.gestion_extraccion import carpeta_caso
    from draft2model.modelo_estructural import huella_configuracion
    from draft2model.resultados_estructurales import huella_declaracion
    resp_path = Path(reg["lectura"]["respuesta"])
    resp = json.loads(resp_path.read_text(encoding="utf-8"))
    datos = resp["datos"]
    tablas = {t["clave"]: t for t in datos["tablas"]}
    cfg_path = work / "configuracion.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    sel = []
    modal = tablas["Modal Periods And Frequencies"]["filas"]
    modos = sorted({f["Mode"] for f in modal if f["Case"] == "MODAL-E030"}, key=lambda m: int(float(m)))[:3]
    for m in modos:
        unico(modal, {"Case": "MODAL-E030", "Mode": m}, "modal")
        sel.append({"id": f"T{int(float(m))}", "variable": "periodo", "caso": "MODAL-E030", "direccion": "modal", "ubicacion": f"modo-{int(float(m))}",
                    "tabla": "Modal Periods And Frequencies", "filtros": {"Case": "MODAL-E030", "Mode": m}, "campo_valor": "Period", "unidad_origen": "s"})
    derivas = tablas["Story Drifts"]["filas"]
    for caso, d in (("SX", "X"), ("SY", "Y")):
        for piso in PISOS:
            filtros = {"OutputCase": caso, "Story": piso, "Direction": d}
            if "StepType" in tablas["Story Drifts"]["campos"]:
                pasos = {f["StepType"] for f in derivas if all(f.get(k) == v for k, v in filtros.items())}
                if pasos == {"Max"}:
                    filtros["StepType"] = "Max"
            unico(derivas, filtros, "derivas")
            sel.append({"id": f"D-{caso}-{piso}", "variable": "deriva", "caso": caso, "direccion": d, "ubicacion": piso,
                        "tabla": "Story Drifts", "filtros": filtros, "campo_valor": "Drift", "unidad_origen": "1"})
    base = tablas["Base Reactions"]["filas"]
    for caso, campo, d in (("SX", "FX", "X"), ("SY", "FY", "Y")):
        filtros = {"OutputCase": caso}
        if "StepType" in tablas["Base Reactions"]["campos"]:
            filtros["StepType"] = "Max"
        unico(base, filtros, "reacciones")
        sel.append({"id": f"V-{caso}", "variable": "cortante", "caso": caso, "direccion": d, "ubicacion": "base", "tabla": "Base Reactions",
                    "filtros": filtros, "campo_valor": campo, "unidad_origen": datos["unidades"].split("_")[0]})
    caso_dir = carpeta_caso(PRIV, CASO)
    edb = Path(datos["modelo"])
    mapeo = {"contrato": "draft2model.mapeo_resultados_etabs", "version": "0.1.0", "caso": CASO, "datos_sinteticos": False,
             "huella_configuracion": huella_configuracion(cfg), "sha256_respuesta": sha(resp_path),
             "modelo": {"archivo": edb.relative_to(caso_dir).as_posix(), "sha256": sha(edb)},
             "unidades_api_esperadas": datos["unidades"], "version_etabs_esperada": datos["version_etabs"], "selectores": sel,
             "revision": {"estado": "borrador", "aprobacion": None}}
    mapeo["revision"] = {"estado": "aprobado", "aprobacion": {
        "revisor_declarado": REVISOR, "fecha": FECHA,
        "motivo": "Selectores construidos desde las filas leídas con unicidad comprobada (periodos 3 primeros modos, derivas máximas "
                  "por piso y dirección del espectro, cortante basal FX/FY de SX/SY).",
        "alcance": "Correspondencia tabla→indicador para el escenario de transporte 09D; no revisa resultados ni cumplimiento.",
        "huella_contenido": huella_declaracion({k: v for k, v in mapeo.items() if k != "revision"})}}
    out = work / "resultados"
    out.mkdir(exist_ok=True)
    guardar(out / "mapeo.json", mapeo)
    previa = ne.previsualizar_resultados(PRIV, cfg_path, resp_path, out / "mapeo.json")
    guardar(out / "previsualizacion.json", previa)
    carpeta = ne.registrar_resultados(PRIV, cfg_path, resp_path, out / "mapeo.json")
    reg["resultados"] = {"id": Path(carpeta).name, "carpeta": str(carpeta), "selectores": len(sel),
                         "omisiones": previa["resultados"]["omisiones"]}


def etapa_controles(work, reg):
    """Controles de análisis por los SERVICIOS de la aplicación (RevisionLocal): lectura web aceptada + ServicioControles."""
    import time
    import uuid
    from draft2model.revision_visual import RevisionLocal
    rep = json.loads((work / "registro.json").read_text(encoding="utf-8"))
    corrida = Path(rep["fases"]["analisis"]["corrida"])
    app = RevisionLocal(PRIV)
    fp = app.expediente(CASO)[2]
    casos = ["CM", "CAGUA", "MODAL-E030"]
    job = app.lecturas.preparar({"caso": CASO, "analisis": corrida.name, "expediente_sha256": fp, "clave_solicitud": uuid.uuid4().hex,
                                 "tablas": ["Base Reactions", "Modal Participating Mass Ratios"], "casos": casos})
    job = app.lecturas.ejecutar({"caso": CASO, "trabajo": job["id"], "huella_preparacion": job["huella_preparacion"],
                                 "expediente_sha256": fp, "confirmacion_explicita": True})
    t0 = time.time()
    while job["estado"] == "en_ejecucion" and time.time() - t0 < 14400:   # la aceptación revalida el análisis (>300 s por consulta)
        time.sleep(5)
        job = app.lecturas.consultar(CASO, job["id"])
    if job["estado"] != "aceptado" or not job["lectura_verificada"]:
        raise SystemExit("Lectura web no aceptada: " + json.dumps({k: job[k] for k in ("estado", "vigente", "problemas")}))
    tablas = {t["clave"]: t for t in job["datos_tablas"]["tablas"]}
    modal = [f for f in tablas["Modal Participating Mass Ratios"]["filas"] if f["Case"] == "MODAL-E030"]
    ultimo = max(modal, key=lambda f: int(float(f["Mode"])))["Mode"]
    analisis = json.loads((corrida / "respuesta.json").read_text(encoding="utf-8"))
    acc = json.loads((corrida / "aceptacion_analisis.json").read_text(encoding="utf-8"))
    avisos = [{"caso": None, "codigo": f"AVISO-{i + 1:03d}", "texto": a} for i, a in enumerate(analisis.get("avisos", []))]
    solver = {"contrato": "draft2model.avisos_solver_declarados", "version": "0.1.0", "corrida_analisis": corrida.name,
              "modelo_id": acc["modelo_id"], "sha256_edb": acc["guardado"]["sha256"], "casos": casos,
              "origen_declarado": "Avisos de la respuesta del puente de análisis (respuesta.json de la corrida), transcritos sin filtrar.",
              "advertencias": avisos}
    sel = lambda campo: {"tabla": "Modal Participating Mass Ratios", "campo_caso": "Case",
                         "filtros": {"Case": "MODAL-E030", "Mode": ultimo}, "campo": campo, "unidad": "1"}
    controles = [
        {"id": "MOD-X", "tipo": "participacion_modal", "caso": "MODAL-E030", "aplica": True, "critico": True,
         "motivo": "Masa participativa acumulada en X en el último modo leído.", "fuente_criterio": "E.030 art. 29.1.2 (≥ 90 %)",
         "parametros": {"selector": sel("SumUX"), "minimo_acumulado": 0.9, "direccion": "UX"}},
        {"id": "MOD-Y", "tipo": "participacion_modal", "caso": "MODAL-E030", "aplica": True, "critico": True,
         "motivo": "Masa participativa acumulada en Y en el último modo leído.", "fuente_criterio": "E.030 art. 29.1.2 (≥ 90 %)",
         "parametros": {"selector": sel("SumUY"), "minimo_acumulado": 0.9, "direccion": "UY"}},
        {"id": "EQ-CM", "tipo": "equilibrio", "caso": "CM", "aplica": False, "critico": False,
         "motivo": "La lectura no contiene una tabla de cargas aplicadas totales; el contraste de reacciones con el libro de "
                   "cargas/masa se registra aparte (contraste_gravitatorio en registro_resultados).",
         "fuente_criterio": "Sin tabla de cargas en esta lectura.", "parametros": {}},
        {"id": "SOLVER", "tipo": "advertencias_solver", "caso": None, "aplica": True, "critico": True,
         "motivo": "Avisos transcritos de la respuesta del análisis; ninguno se admite por omisión.",
         "fuente_criterio": "Revisión de avisos del motor.", "parametros": {"codigos_admitidos": []}}]
    item = app.controles.crear({"caso": CASO, "expediente_sha256": fp, "lectura": job["id"], "sha256_respuesta": job["sha256_respuesta"],
                                "avisos_solver_json": json.dumps(solver, ensure_ascii=False), "revisor_declarado": REVISOR, "fecha": FECHA,
                                "alcance": "Controles de software del escenario de transporte 09D; no revisa ingeniería ni normativa.",
                                "controles": controles, "confirmacion_explicita": True})
    reg["controles"] = {"id": item["id"], "sha256_controles": item["sha256_controles"], "expediente_sha256": fp, "lectura_web": job["id"],
                        "estados": {c["id"]: c["estado"] for c in item["contenido"]["controles"]},
                        "valores": {c["id"]: c["valores"] for c in item["contenido"]["controles"]}}
    # Contraste gravitatorio independiente: FZ de CM/CAGUA frente al libro (no forma parte del contrato de controles).
    lp = work / "resultados" / "libro_masa.json"
    libro = json.loads(lp.read_text(encoding="utf-8")) if lp.exists() else None
    base = {f["OutputCase"]: f for f in tablas["Base Reactions"]["filas"] if f["OutputCase"] in ("CM", "CAGUA")}
    if libro:
        c = libro["contribuciones"]
        esperado = {"CM": c["peso_propio_por_patrones"]["peso_kn"] + c.get("cargas_D", {}).get("peso_kn", 0.0),
                    "CAGUA": sum(v["peso_kn"] for k, v in c.items() if k.startswith("liquido_"))}
        reg["contraste_gravitatorio"] = {k: {"FZ_reaccion_kn": float(base[k]["FZ"]), "peso_libro_kn": esperado[k],
                                             "diferencia_relativa": (float(base[k]["FZ"]) - esperado[k]) / esperado[k]}
                                         for k in esperado if k in base}


def etapa_reglas(work, reg):
    """Reglas E.030 aplicadas a los escenarios IDENTIFICADOS (ESCENARIOS_SISMICOS_09: S1 con R0 = 6 muros de concreto y R0 = 3
    albañilería; Ia = Ip = 1 hipótesis). Aprobación DECLARADA como aplicación de software por Claude, no profesional.

    - Deriva: inelástica = 0,75·R·elástica (art. 50.1, regular como hipótesis). El espectro es lineal en 1/R, así que el producto
      0,75·R·Δ(R) es el mismo para R = 3 y R = 6: factor 4,5 sobre la deriva del análisis (R = 6). Límite Tabla 14: 0,007
      (concreto armado, escenario MUR) y 0,005 (albañilería, escenario ALB).
    - Cortante mínimo (art. 44.1, regular): V_din ≥ 0,80·V_est; V_est (art. 34) con P = g·Σ masas de N1–N4 de la tabla nativa
      «Mass Summary by Story» (sin Base). El cociente no depende de R. Sin esa tabla, la regla se ABSTIENE (no se inventa P).
    """
    from draft2model import normativa_e030 as e
    from draft2model.evaluacion_estructural import validar_reglas
    from draft2model.resultados_estructurales import huella_declaracion
    cita = e.deriva_admisible("concreto_armado", regular=True, R=6)["cita"][0]
    fuente = lambda apartado: {"titulo": "Norma E.030 Diseño Sismorresistente", "edicion": cita["dispositivo"] + " (" + cita["publicacion"] + ")",
                               "apartado": apartado, "referencia": cita["texto_registrado"]}
    reglas = []
    for esc, material in (("S1-MUR", "concreto_armado"), ("S1-ALB", "albanileria")):
        d = e.deriva_admisible(material, regular=True, R=6.0)   # factor sobre la deriva elástica del análisis con R = 6
        for caso, dir_ in (("SX", "X"), ("SY", "Y")):
            reglas.append({"id": f"DERIVA-{esc}-{caso}", "variable": "deriva", "unidad": "1",
                           "formula": {"expresion": "factor * x + desplazamiento", "factor": d["factor_desplazamiento"], "desplazamiento": 0.0},
                           "limite": d["limite"], "comparador": "<=",
                           "aplicabilidad": {"aplica": True, "casos": [caso], "direcciones": [dir_], "ubicaciones": PISOS,
                                             "motivo": f"Escenario {esc} (hipótesis identificada en ESCENARIOS_SISMICOS_09; Ia = Ip = 1, regular). "
                                                       "0,75·R·Δ(R) invariante en R por linealidad del espectro."},
                           "fuente": fuente("Arts. 50.1 y 51, Tabla N° 14 (" + material + ")")})
    abstenciones = []
    # P = g·Σ UX de N1–N4 en «Mass Summary by Story», lectura ACEPTADA del mismo análisis/EDB (revisión Codex 268). La cota de los nudos
    # de AssembledJointMass no prueba el piso con diafragmas rígidos (HALLAZGO_MASA_09D1), así que no se usa para P.
    p_kn, origen_p = None, None
    try:
        from draft2model.gestion_extraccion import carpeta_caso
        rep_an = json.loads((work / "registro.json").read_text(encoding="utf-8"))
        corrida = Path(rep_an["fases"]["analisis"]["corrida"])
        acc_an = json.loads((corrida / "aceptacion_analisis.json").read_text(encoding="utf-8"))
        lid = json.loads((work / "masa_pisos_diagnostico.json").read_text(encoding="utf-8"))["lectura"]
        lec = carpeta_caso(PRIV, CASO) / "lecturas_analisis" / lid
        acc = json.loads((lec / "aceptacion_lectura.json").read_text(encoding="utf-8"))
        raw = (lec / "respuesta.json").read_bytes()
        if (acc.get("aceptada") is not True or acc.get("corrida_analisis_id") != corrida.name
                or acc.get("sha256_edb") != acc_an["guardado"]["sha256"] or hashlib.sha256(raw).hexdigest() != acc.get("sha256_respuesta")):
            raise ValueError("lectura de masas por piso no ligada al análisis/EDB")
        tabla = next(t for t in json.loads(raw)["datos"]["tablas"] if t["clave"] == "Mass Summary by Story")
        filas = {f["Story"]: f for f in tabla["filas"]}
        if not set(PISOS) <= set(filas):
            raise ValueError("faltan pisos en Mass Summary by Story")
        cfg = json.loads((work / "configuracion.json").read_text(encoding="utf-8"))
        p_kn = cfg["masa"]["gravedad_m_s2"] * sum(float(filas[n]["UX"]) for n in PISOS)
        origen_p = f"g·Σ UX de N1–N4 en Mass Summary by Story (lectura aceptada {lid}, análisis {corrida.name}, EDB {acc['sha256_edb'][:16]}…)"
    except (OSError, KeyError, StopIteration, ValueError) as exc:
        abstenciones.append("Cortante mínimo: sin masas por piso nativas aceptadas y ligadas al análisis (" + str(exc)[:200] + ") → abstención.")
    else:
        sitio = e.parametros_sitio(4, "S1")
        t = e.periodo_aproximado(10.4, "albanileria_o_muros")["T_s"]
        v = e.cortante_basal_estatico(Z=e.factor_zona(4)["Z"], U=e.factor_uso("C")["U"], S=sitio["S"], R=6.0, T=t,
                                      TP=sitio["TP"], TL=sitio["TL"], P_kN=p_kn)
        minimo = e.cortante_minimo(regular=True)["fraccion_del_estatico"]
        reg["cortante_estatico"] = {"P_kN": p_kn, "V_est_kN_R6": v["V_kN"], "T_s": t, "fraccion_minima": minimo,
                                    "origen_P": origen_p}
        for caso, dir_ in (("SX", "X"), ("SY", "Y")):
            reglas.append({"id": f"VMIN-{caso}", "variable": "cortante", "unidad": "kN", "unidad_resultado": "1",   # Vdin/Vest adimensional (290)
                           "formula": {"expresion": "factor * x + desplazamiento", "factor": 1.0 / v["V_kN"], "desplazamiento": 0.0},
                           "limite": minimo, "comparador": ">=",
                           "aplicabilidad": {"aplica": True, "casos": [caso], "direcciones": [dir_], "ubicaciones": ["base"],
                                             "motivo": f"V_din/V_est con V_est = {v['V_kN']:.1f} kN (Z 0,45; U 1; S1; R 6; T {t:.3f} s; "
                                                       f"P {p_kn:.1f} kN nativo). Cociente invariante en R."},
                           "fuente": fuente("Arts. 34, 36.1 y 44.1")})
    doc = {"contrato": "draft2model.reglas_estructurales", "version_contrato": "0.1.0", "id": "reglas-e030-09d-escenarios",
           "datos_sinteticos": False, "reglas": reglas, "revision": {"estado": "borrador", "aprobacion": None}}
    doc["revision"] = {"estado": "aprobado", "aprobacion": {
        "revisor_declarado": "Claude (ruta 09): aplicación de SOFTWARE de E.030 a escenarios hipotéticos identificados; NO aprobación profesional",
        "fecha": FECHA, "motivo": "Transcripción de límites/factores de normativa_e030 (citas RNE registradas) a los escenarios S1-MUR y S1-ALB.",
        "alcance": "Evaluación condicionada a las hipótesis (sin EMS, Ia = Ip = 1, regularidad no verificada); no certifica cumplimiento.",
        "huella_contenido": huella_declaracion({k: v for k, v in doc.items() if k != "revision"})}}
    v = validar_reglas(doc)
    if not v["correcta"]:
        raise SystemExit("Reglas inválidas: " + "; ".join(v["errores"]))
    guardar(work / "resultados" / "reglas_e030.json", doc)
    reg["reglas"] = {"archivo": str(work / "resultados" / "reglas_e030.json"), "reglas": len(reglas), "abstenciones": abstenciones}


CONTINUACIONES = RAIZ / "seguimiento/claude_ruta/CONTINUACIONES_RESULTADOS.json"


def _continuaciones():
    return json.loads(CONTINUACIONES.read_text(encoding="utf-8")) if CONTINUACIONES.exists() else {}


def preparar_continuacion(work, origen):
    """Continuación AISLADA (Cierre285) desde artefactos inmutables ya publicados: no escribe en `origen` ni repite ETABS.

    Copia las fuentes locales (registro del runner, configuración aprobada, masas por piso, libro) y siembra el registro con
    lectura/masa/resultados del origen tras comprobar sus hashes y que las carpetas publicadas existen.
    """
    import shutil
    if work.exists():
        raise SystemExit("La carpeta de continuación ya existe; no se sobrescribe.")
    reg_o = json.loads((origen / "registro_resultados.json").read_text(encoding="utf-8"))
    for clave in ("lectura", "masa", "resultados"):
        if clave not in reg_o:
            raise SystemExit("El origen no tiene la etapa " + clave + " publicada.")
    if sha(reg_o["lectura"]["respuesta"]) != reg_o["lectura"]["sha256"] or not Path(reg_o["resultados"]["carpeta"]).is_dir():
        raise SystemExit("Lectura o resultados del origen alterados o ausentes.")
    work.mkdir(parents=True)
    (work / "resultados").mkdir()
    copias = {}
    for rel in ("registro.json", "configuracion.json", "masa_pisos_diagnostico.json", "resultados/libro_masa.json"):
        shutil.copyfile(origen / rel, work / rel)
        copias[rel] = sha(work / rel)
        if copias[rel] != sha(origen / rel):
            raise SystemExit("Copia distinta del origen: " + rel)
    reg = {"caso": CASO, "aprueba_ingenieria": False, "continuacion_de": {"origen": origen.relative_to(RAIZ).as_posix(), "copias_sha256": copias},
           **{k: reg_o[k] for k in ("lectura", "masa", "resultados")}}
    for clave in ("contraste_gravitatorio",):
        if clave in reg_o:
            reg[clave] = reg_o[clave]
    cont = _continuaciones()
    cont[origen.relative_to(RAIZ).as_posix()] = {"continuacion": work.relative_to(RAIZ).as_posix(), "fecha": FECHA,
                                                 "etapas_delegadas": ["controles", "reglas", "informe", "panel"]}
    CONTINUACIONES.write_text(json.dumps(cont, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return reg


def etapa_controles_publicados(work, reg, controles_id):
    """Revalida un control YA publicado mediante el servicio vigente (fuentes exactas, sin crear otro) y guarda su referencia."""
    from draft2model.revision_visual import RevisionLocal
    app = RevisionLocal(PRIV)
    fp = app.expediente(CASO)[2]
    item = app.controles.consultar(CASO, controles_id, expediente_sha256=fp)
    if item.get("vigente") is not True or item["analisis"] != Path(json.loads((work / "registro.json").read_text(encoding="utf-8"))["fases"]["analisis"]["corrida"]).name:
        raise SystemExit("El control publicado no está vigente o corresponde a otro análisis.")
    reg["controles"] = {"id": item["id"], "sha256_controles": item["sha256_controles"], "expediente_sha256": fp, "lectura_web": item["lectura"],
                        "estados": {c["id"]: c["estado"] for c in item["contenido"]["controles"]},
                        "valores": {c["id"]: c["valores"] for c in item["contenido"]["controles"]},
                        "revalidado": "ServicioControles.consultar (servicio vigente) en la continuación"}


def etapa_panel(work, reg):
    from draft2model.panel_tecnico import crear_panel
    rep_an = json.loads((work / "registro.json").read_text(encoding="utf-8"))
    cfg = json.loads((work / "configuracion.json").read_text(encoding="utf-8"))
    res_dir = Path(reg["resultados"]["carpeta"])
    geo_arch = PRIV / CASO / "geometrias" / cfg["geometria_origen"]["version_id"] / "geometria.json"
    salida = work / "resultados" / "panel.html"
    crear_panel(res_dir / "resultados.json", Path(reg["reglas"]["archivo"]) if "reglas" in reg else None, salida, geometria=geo_arch,
                evidencia_analisis={"raiz": PRIV, "caso": CASO, "resultado": reg["resultados"]["id"], "corrida": Path(rep_an["fases"]["analisis"]["corrida"])})
    reg["panel"] = {"archivo": str(salida), "sha256": sha(salida)}


def etapa_informe(work, reg):
    from draft2model import informe as inf
    from draft2model.evidencia_analisis import fuente_desde_argumentos
    rep = json.loads((work / "registro.json").read_text(encoding="utf-8"))
    res_dir = Path(reg["resultados"]["carpeta"])
    resultados = json.loads((res_dir / "resultados.json").read_text(encoding="utf-8"))
    cfg = json.loads((work / "configuracion.json").read_text(encoding="utf-8"))
    fuente = fuente_desde_argumentos(PRIV, CASO, reg["resultados"]["id"], Path(rep["fases"]["analisis"]["corrida"]))
    geo_arch = PRIV / CASO / "geometrias" / cfg["geometria_origen"]["version_id"] / "geometria.json"
    masa = reg.get("masa", {})
    contexto = {
        "titulo": "Pueblo Libre 002 — escenario de transporte 09D (hipótesis; no ingeniería)",
        "hipotesis": [h["descripcion"] for h in cfg["hipotesis"]][:40] + [
            "Reglas E.030 aplicadas a los escenarios identificados S1-MUR (R0 = 6, deriva ≤ 0,007) y S1-ALB (R0 = 3, deriva ≤ 0,005), "
            "con aprobación DECLARADA de aplicación de software (no profesional); evaluación condicionada a las hipótesis."]
            + [a for a in reg.get("reglas", {}).get("abstenciones", [])],
        "faltantes": ["Sitio referencial: no hay capa de zonificación revisada; S1 es hipótesis de transporte (sin EMS).",
                      "Aprobación de ingeniería: no existe; las reglas tienen solo aprobación declarada de software.",
                      "Escalera: entrepisos 2,60→10,40 con U hipotética; solo el primer tramo está confirmado por el usuario.",
                      "Masa nativa: " + str(masa.get("estado", "no ejecutada")) + "."]
                     + ([json.loads((RAIZ / "seguimiento/claude_ruta/HALLAZGO_MASA_09D1.json").read_text(encoding="utf-8"))["lectura"][:900],
                         json.loads((RAIZ / "seguimiento/claude_ruta/HALLAZGO_MASA_09D1.json").read_text(encoding="utf-8"))["consecuencia"]]
                        if (RAIZ / "seguimiento/claude_ruta/HALLAZGO_MASA_09D1.json").exists() else []),
        "sitio": None}
    guardar(work / "resultados" / "contexto.json", contexto)
    f_cont = {"raiz": str(PRIV), "caso": CASO}
    f_nat = {**f_cont, "lectura_id": masa["lectura"]} if masa.get("estado") in ("coherente", "no_coherente") else None
    f_ctl = None
    if "controles" in reg:
        from draft2model.revision_visual import RevisionLocal
        ctl = reg["controles"]
        f_ctl = {"app": RevisionLocal(PRIV), "caso": CASO, "id": ctl["id"], "sha256_controles": ctl["sha256_controles"],
                 "expediente_sha256": ctl["expediente_sha256"]}
    reglas = json.loads(Path(reg["reglas"]["archivo"]).read_text(encoding="utf-8")) if "reglas" in reg else None
    informe = inf.crear_informe(resultados, reglas, contexto, geometria_archivo=geo_arch, evidencia_analisis=fuente,
                                fuente_controles_analisis=f_ctl, fuente_contenido_masa=f_cont, fuente_masa_nativa=f_nat)
    salida = work / "resultados" / ("informe" if not (work / "resultados" / "informe").exists() else "informe_" + str(len(list((work / "resultados").glob("informe*")))))
    inf.exportar_informe(informe, salida, geometria_archivo=geo_arch, evidencia_analisis=fuente, fuente_controles_analisis=f_ctl,
                         fuente_contenido_masa=f_cont, fuente_masa_nativa=f_nat)
    reg["informe"] = {"carpeta": str(salida), **{n: sha(salida / n) for n in ("informe.json", "informe.html", "informe.pdf")},
                      "secciones": sorted(informe), "masa_nativa_incluida": f_nat is not None}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--trabajo", type=Path, required=True)
    ap.add_argument("--etapa", choices=("lectura", "masa", "normalizacion", "controles", "controles_publicados", "reglas", "informe", "panel",
                                        "todas"), default="todas")
    ap.add_argument("--continuar-desde", type=Path, help="Carpeta de trabajo de origen con artefactos publicados (Cierre285).")
    ap.add_argument("--controles-id", help="Control ya publicado a revalidar (etapa controles_publicados).")
    a = ap.parse_args(argv)
    work = (RAIZ / a.trabajo).resolve()
    reg_path = work / "registro_resultados.json"
    rel = work.relative_to(RAIZ).as_posix()
    if a.etapa in ("controles", "reglas", "informe", "panel") and rel in _continuaciones():
        print(f"Etapa {a.etapa} delegada a la continuación {_continuaciones()[rel]['continuacion']}; no se repite en {rel}.")
        return
    if a.continuar_desde is not None:
        reg = preparar_continuacion(work, (RAIZ / a.continuar_desde).resolve())
        reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    reg = json.loads(reg_path.read_text(encoding="utf-8")) if reg_path.exists() else {"caso": CASO, "aprueba_ingenieria": False}
    etapas = ["lectura", "masa", "normalizacion", "controles", "reglas", "informe"] if a.etapa == "todas" else [a.etapa]
    try:
        for e in etapas:
            if e in reg and e != "informe":
                continue
            if e == "controles_publicados":
                etapa_controles_publicados(work, reg, a.controles_id)
            else:
                {"lectura": etapa_lectura, "masa": etapa_masa, "normalizacion": etapa_normalizacion, "controles": etapa_controles,
                 "reglas": etapa_reglas, "informe": etapa_informe, "panel": etapa_panel}[e](work, reg)
            reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    except Exception as exc:
        reg.setdefault("errores", []).append({"etapa": e, "tipo": type(exc).__name__, "error": str(exc)[:3000]})
        reg_path.write_text(json.dumps(reg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        raise
    print(json.dumps({k: v for k, v in reg.items() if k != "errores"}, ensure_ascii=False, indent=1)[:3000])


if __name__ == "__main__":
    main()
