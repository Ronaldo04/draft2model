"""Configuración 0.5 del caso real sobre la geometría conforme 7c84de15 (encargo 09, pasos 4–5). No aprueba ni inventa datos.

Ejecutar desde la raíz: python seguimiento/claude_ruta/configuracion_09b.py
Salidas: tmp/ruta201/configuracion09b.json (configuración en borrador) y seguimiento/claude_ruta/CONFIGURACION_CASO_09B.json (informe).

Completa lo técnico (plantilla propia, secciones, frames de columnas y vigas soleras sobre vanos, apoyos, diafragmas, masa,
patrones, cargas de losa, casos D/L/modal, conexiones y malla) y deja como FALTANTES las decisiones del usuario: tipo de unidad
de albañilería (Em, E.070 24.7), perfil de suelo/EMS, sistema estructural (R0) e irregularidades. Sin ellas no hay sismo
estático ni espectral y la sección de albañilería no tiene material: la configuración no es ejecutable.
"""
import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from draft2model import configuracion_normativa as cn  # noqa: E402
from draft2model import gestion_geometria as gg  # noqa: E402
from draft2model import modelo_estructural as m  # noqa: E402
from draft2model import normativa_rne as rne  # noqa: E402
from draft2model import plantilla_configuracion as pc  # noqa: E402

CASO, GEO = "pueblo-libre-002", "7c84de1531744cf280dcd3231b7fa1cf"
PRIV = RAIZ / "data/private"
ORIG = PRIV / CASO / "originales"
SEG = RAIZ / "seguimiento/claude_ruta"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
GEO09B = json.loads((SEG / "GEOMETRIA_09B.json").read_text(encoding="utf-8"))
MUROS = json.loads((SEG / "MUROS_09.json").read_text(encoding="utf-8"))
geo = gg.consultar_version(PRIV, CASO, GEO).geometria
V = {v["id"]: (v["x"], v["y"], v["z"]) for v in geo["vertices"]}
COTAS = sorted({v[2] for v in V.values()})
Z_TECHO = max(COTAS)

cfg = pc.borrador(PRIV, CASO, GEO, version_contrato=m.VERSION_LIQUIDOS)
cfg["fuentes"] += [
    {"id": "F-L0001-ESPEC", "descripcion": "Especificaciones técnicas de L0001 (f'c 210, fy 4200, f'm 35 kgf/cm², ladrillo King-Kong a máquina; "
                                           "sobrecarga 1.º–4.º 200 y azotea 150 kgf/m²). Lecturas PENDIENTES de revisión.",
     "referencia": "L0001 · especificaciones técnicas", "sha256": sha(ORIG / "lamina-0001.pdf")},
    {"id": "F-L0001-ROTULO", "descripcion": "Rótulo: «EDIFICIO MULTIFAMILIAR», ubicación Calle Río Tambo 125, Pueblo Libre.",
     "referencia": "L0001 · rótulo", "sha256": sha(ORIG / "lamina-0001.pdf")},
    {"id": "F-L0001-COLUMNAS", "descripcion": "Cuadro de columnas C-1…C-6 de L0001 y contornos ajustados (INVENTARIO_GEOMETRICO_09).",
     "referencia": "seguimiento/claude_ruta/INVENTARIO_GEOMETRICO_09.json", "sha256": sha(SEG / "INVENTARIO_GEOMETRICO_09.json")},
    {"id": "F-L0002-ALIGERADO", "descripcion": "Aligerados 1.º–3.º nivel: e = 17 cm, S/C 200 kgf/m², vigas soleras VS 0,15×0,30 en ejes 3, 1, A y 2.",
     "referencia": "L0002", "sha256": sha(ORIG / "lamina-0002.pdf")},
    {"id": "F-MUROS-09", "descripcion": "Inventario de muros de L0004/L0005 (pluma 1,68 pt) con clase, cimiento y placa asociados.",
     "referencia": "seguimiento/claude_ruta/MUROS_09.json", "sha256": sha(SEG / "MUROS_09.json")},
    {"id": "F-MODELACION-09B", "descripcion": "Reglas de modelación de la geometría conforme (líneas, extremos, columnas, celdas de losa).",
     "referencia": "seguimiento/claude_ruta/geometria_09b.py", "sha256": sha(SEG / "geometria_09b.py")},
    {"id": "F-HIPOTESIS-PILOTO-09", "descripcion": "Hipótesis de representación del piloto (este script), declaradas y NO aprobadas.",
     "referencia": "seguimiento/claude_ruta/configuracion_09b.py", "sha256": sha(SEG / "configuracion_09b.py")},
]
DECISION = RAIZ / "seguimiento/DECISION_USUARIO_246.json"
cfg["fuentes"].append({"id": "F-DECISION-USUARIO-246", "referencia": "seguimiento/DECISION_USUARIO_246.json", "sha256": sha(DECISION),
                       "descripcion": "Usuario: ladrillo de ARCILLA King-Kong y niveles 0/2,60/5,20/7,80/10,40 confirmados; sin EMS "
                                      "(escenarios de suelo solo como hipótesis). f'm 35 kgf/cm² se lee de L0001."})
cfg["fuentes"].append({"id": "F-C1-L-246", "referencia": "tests/fixtures/columna_l_etabs21_246.json",
                       "sha256": sha(RAIZ / "tests/fixtures/columna_l_etabs21_246.json"),
                       "descripcion": "C-1 en L .40×.40 brazos .15 (auditoría Codex 246, detalle E01) y convención nativa de espejos e "
                                      "inserción ensayada en ETABS propio (columna_l_246b, plan columna_l_plan_246a verificado)."})
# Plantilla propia del caso (instancia ETABS propia, cerrada; no la sintética).
PLANT = PRIV / CASO / "plantillas"
reg = json.loads((PLANT / "creacion_plantilla.json").read_text(encoding="utf-8-sig"))
assert reg["status"] == "created" and not reg["synthetic_test"] and reg["case_id"] == CASO
assert sha(PLANT / "plantilla_vacia_caso.EDB") == reg["sha256"], "plantilla alterada"
cfg["fuentes"].append({"id": "F-PLANTILLA-CASO", "referencia": "data/private/pueblo-libre-002/plantillas/creacion_plantilla.json",
                       "descripcion": f"EDB vacío del caso: ETABS {reg['version']}, InitializeNewModel(kN_m_C) + File.NewBlank en instancia "
                                      f"propia PID {reg['process_id']} (cerrada); sin análisis.", "sha256": reg["sha256"]})
cfg["plantilla"] = {
    "id": "PLANTILLA-PUEBLO-LIBRE-002", "version": reg["version"], "sha256": reg["sha256"],
    "representacion": "Modelo lineal elástico ETABS: muros y placas como shell, columnas y vigas como frame, losas como shell "
                      "(idealización por sección), diafragmas y masa según la configuración.",
    "limitaciones": [
        "La albañilería confinada se representa como shell lineal isótropo (Em, Gm = 0,4 Em); no modela agrietamiento, "
        "interacción con confinamiento ni resistencia a corte (E.070 se verifica fuera del modelo).",
        "Plantilla sin geometría ni cargas, pero con las definiciones por defecto de ETABS (4 materiales, 126 secciones de frame, patrones Dead/Live, casos Dead/Live/Modal, diafragma D1, 3 funciones; leídas en tmp/nombres_plantilla_09t), que el plan no usa ni modifica; todo lo del modelo lo aporta el plan revisable.",
        "Sin análisis ni comprobación de derivas, cortantes o diseño; no declara cumplimiento normativo.",
    ],
    "fuente": "F-PLANTILLA-CASO",
}

# Normativa: materiales y sitio (puertas separadas; el espectro no se genera sin perfil/sistema).
decisiones = {
    "materiales": [
        {"id": "CONCRETO-FC210", "clase": "concreto", "resistencia": 210, "unidad": "kgf/cm2", "fuente": "F-L0001-ESPEC"},
        {"id": "ALBANILERIA-FM35", "clase": "albanileria", "resistencia": 35, "unidad": "kgf/cm2", "tipo_unidad": "arcilla",
         "peso_kN_m3": rne.peso_especifico("albanileria_cocida_solida")["peso_kN_m3"], "fuente": "F-DECISION-USUARIO-246"},
    ],
    "zona": {"valor": 4, "estado": "lectura_expediente", "fuente": "F-L0001-ROTULO"},       # Pueblo Libre, provincia de Lima → zona 4
    "categoria": {"valor": "C", "estado": "lectura_expediente", "fuente": "F-L0001-ROTULO"},  # vivienda multifamiliar
}
cfg, informe = cn.aplicar(cfg, decisiones)
c210 = next(x for x in cfg["materiales"] if x["id"] == "CONCRETO-FC210")
cfg["materiales"].append({**c210, "id": "CONCRETO-FC210-LOSA", "peso_kN_m3": 0.0, "fuente": "F-HIPOTESIS-PILOTO-09"})
ALB = "ALBANILERIA-FM35"   # arcilla King-Kong confirmada por el usuario (DECISION_USUARIO_246): Em = 500 f'm (E.070 24.7)

if "RNE-E030-RM183-2026" not in {f["id"] for f in cfg["fuentes"]}:   # cn.aplicar la añade solo con espectro
    cfg["fuentes"].append(cn.fuente_oficial("RNE-E030-RM183-2026", "11 (Tabla 1), 19.1 (Tabla 7), 31 (peso sísmico)"))
z = cn.e030.factor_zona(4)
u = cn.e030.factor_uso("C")
cfg["sitio"] = {"descripcion": "Edificio multifamiliar de 4 pisos y azotea (L0001–L0006).",
                "ubicacion": "Calle Río Tambo 125, Pueblo Libre, Lima (rótulo de L0001).",
                "sistema_resistente": None,
                "parametros": [{"id": "Z", "valor": z["Z"], "unidad": "1", "fuente": "RNE-E030-RM183-2026"},
                               {"id": "U", "valor": u["U"], "unidad": "1", "fuente": "RNE-E030-RM183-2026"}],
                "fuente": "F-L0001-ROTULO"}

# Secciones.
COL_DIM = {"C-1": (0.15, 0.40), "C-2": (0.15, 0.40), "C-3": (0.15, 0.60), "C-4": (0.15, 0.40), "C-5": (0.15, 0.30)}
secciones = [
    {"id": "MURO-KK-15", "tipo": "shell_muro", "material": ALB, "dimensiones": {"espesor_m": 0.15}, "fuente": "F-MUROS-09"},
    {"id": "PLACA-10", "tipo": "shell_muro", "material": "CONCRETO-FC210", "dimensiones": {"espesor_m": 0.10}, "fuente": "F-MUROS-09"},
    {"id": "LOSA-MEMB-05", "tipo": "shell_losa_homogenea", "material": "CONCRETO-FC210-LOSA", "dimensiones": {"espesor_m": 0.05},
     "fuente": "F-L0002-ALIGERADO"},
    {"id": "VS-15X30", "tipo": "frame_rectangular", "material": "CONCRETO-FC210", "dimensiones": {"ancho_m": 0.15, "alto_m": 0.30},
     "fuente": "F-L0002-ALIGERADO"},
]


# C-1 (E01 detalle): L .40×.40, brazos .15. Esquina exterior en la esquina de la caja ajustada; los brazos van hacia el
# interior de la planta. Convención ensayada: sin espejos brazos +local2/−local3 (= +X/−Y en columnas con ejes por defecto);
# espejo_eje_2: +X/+Y. Centroide a x̄ = ȳ = 0,151923 m de la esquina exterior; la inserción lo desplaza desde el nudo.
B_L, T_L = 0.40, 0.15
XC_L = (B_L * T_L * B_L / 2 + B_L * T_L * T_L / 2 - T_L ** 3 / 2) / (2 * B_L * T_L - T_L ** 2)
CAJAS = {e["id"]: e["caja_m"] for e in json.loads((SEG / "INVENTARIO_GEOMETRICO_09.json").read_text(encoding="utf-8"))["elementos"]}
insercion = []


def seccion_c1(c):
    caja = CAJAS[c["elemento"]]
    brazo_y_positivo = caja["y0"] < 5.0           # A/3 (y≈0): brazo hacia +Y; A/1 (y≈10): hacia −Y
    esquina = (caja["x0"], caja["y0"] if brazo_y_positivo else caja["y1"])
    centroide = (esquina[0] + XC_L, esquina[1] + (XC_L if brazo_y_positivo else -XC_L))
    ident = "COL-1-L-" + ("MAS-Y" if brazo_y_positivo else "MENOS-Y")
    if ident not in {s["id"] for s in secciones}:
        secciones.append({"id": ident, "tipo": "frame_l_concreto", "material": "CONCRETO-FC210", "fuente": "F-C1-L-246",
                          "dimensiones": {"alto_m": B_L, "ancho_m": B_L, "espesor_ala_m": T_L, "espesor_alma_m": T_L,
                                          "espejo_eje_2": brazo_y_positivo, "espejo_eje_3": False}})
    return ident, [round(centroide[0] - c["x"], 6), round(centroide[1] - c["y"], 6), 0.0]


def seccion_columna(c):
    """T3 = alto_m sobre el eje local 2 (X global en columnas por defecto de ETABS): el lado largo dibujado define la orientación."""
    b, h = COL_DIM[c["etiqueta"]]
    dx, dy = c["dibujo_m"]
    largo_en_x = dx >= dy
    ident = f"COL-{c['etiqueta'][2]}-{'X' if largo_en_x else 'Y'}"
    if ident not in {s["id"] for s in secciones}:
        secciones.append({"id": ident, "tipo": "frame_rectangular", "material": "CONCRETO-FC210",
                          "dimensiones": {"ancho_m": b, "alto_m": h} if largo_en_x else {"ancho_m": h, "alto_m": b},
                          "fuente": "F-L0001-COLUMNAS"})
    return ident


# Frames: columnas (sin C-6, fuera de la losa, en la zona de escalera) y vigas soleras sobre vanos.
frames, asign_frames, excluidas = [], [], []
for c in GEO09B["columnas"]:
    if c["etiqueta"] == "C-6":
        excluidas.append({"elemento": c["elemento"], "motivo": "Fuera de la losa (zona de escalera, faltante); quedaría aislada."})
        continue
    sec, desplazamiento = seccion_c1(c) if c["etiqueta"] == "C-1" else (seccion_columna(c), None)
    for k, (a, b) in enumerate(zip(c["vertices"], c["vertices"][1:]), 1):
        fid = f"COL-{c['elemento'].split('-')[1]}-P{k}"
        frames.append({"id": fid, "inicio": a, "fin": b, "tipo": "columna", "fuente": "F-L0001-COLUMNAS"})
        asign_frames.append({"objetivo": fid, "seccion": sec, "fuente": "F-L0001-COLUMNAS"})
        if desplazamiento is not None:
            insercion.append({"frame": fid, "punto_cardinal": 10, "desplazamiento_global_m": desplazamiento,
                              "transformar_rigidez": True, "fuente": "F-C1-L-246"})

papel = {s["id"]: s["papel_geometrico"] for s in geo["superficies"]}
verts_sup = {s["id"]: s["vertices"] for s in geo["superficies"]}
XS, YS = GEO09B["lineas_x"], GEO09B["lineas_y"]
LINEAS_VS = [("y", min(YS), "eje 3"), ("y", max(YS), "eje 1"), ("x", min(XS), "eje A"),
             ("y", min(YS, key=lambda y: abs(y - 5.0)), "eje 2")]
vigas = []
for zc in COTAS[1:]:
    for eje, val, nombre in LINEAS_VS:
        k = 0 if eje == "x" else 1          # coordenada fija
        t = 1 - k                           # coordenada a lo largo
        intervalos = []
        for sid, vs in verts_sup.items():
            if papel[sid].startswith("losa"):
                continue
            top = [V[v] for v in vs if abs(V[v][2] - zc) < 1e-9]
            if len(top) == 2 and all(abs(p[k] - val) < 1e-9 for p in top):
                intervalos.append(tuple(sorted(p[t] for p in top)))
        intervalos.sort()
        unidos = []
        for a, b in intervalos:
            if unidos and a <= unidos[-1][1] + 1e-9:
                unidos[-1] = (unidos[-1][0], max(unidos[-1][1], b))
            else:
                unidos.append((a, b))
        en_linea = {round(p[t], 6): vid for vid, p in V.items() if abs(p[2] - zc) < 1e-9 and abs(p[k] - val) < 1e-9}
        for (a0, a1), (b0, b1) in zip(unidos, unidos[1:]):
            puntos = sorted(x for x in en_linea if a1 - 1e-9 <= x <= b0 + 1e-9)
            for j, (p, q) in enumerate(zip(puntos, puntos[1:]), 1):
                fid = f"VS-Z{COTAS.index(zc)}-{nombre[-1]}-{len(vigas) + 1}"
                vigas.append({"linea": nombre, "z": zc, "desde": p, "hasta": q})
                frames.append({"id": fid, "inicio": en_linea[p], "fin": en_linea[q], "tipo": "viga", "fuente": "F-L0002-ALIGERADO"})
                asign_frames.append({"objetivo": fid, "seccion": "VS-15X30", "fuente": "F-L0002-ALIGERADO"})
cfg["frames"], cfg["asignaciones_frames"] = frames, asign_frames
usados_frames = {f[x] for f in frames for x in ("inicio", "fin")}
cfg["puntos"] = [p for p in cfg["puntos"] if p["vertice_geometria"] in usados_frames or
                 any(p["vertice_geometria"] in vs for vs in verts_sup.values())]

# Asignaciones de superficies por clase.
clases = GEO09B["clases_superficie"]
SEC_CLASE = {"albanileria_king_kong": "MURO-KK-15", "concreto": "PLACA-10", "losa": "LOSA-MEMB-05"}
cfg["asignaciones_superficies"] = [{"objetivo": a["objetivo"], "seccion": SEC_CLASE[clases[a["objetivo"]]["clase"]],
                                    "fuente": "F-MUROS-09" if clases[a["objetivo"]]["clase"] != "losa" else "F-L0002-ALIGERADO"}
                                   for a in cfg["asignaciones_superficies"]]
cfg["secciones"] = secciones

# Patrones y cargas de losa (kN/m², global, −Z). Peso del aligerado e=17 por E.020 Anexo 1 (la membrana no tiene peso).
PESO_ALIG = 2.8   # E.020 Anexo 1: aligerado 0,17 m, vigueta 0,10 m a 0,40 m, losa superior 0,05 m → 2,8 kPa (280 kgf/m²)
ACABADOS = 1.0    # hipótesis de piloto: piso terminado/cielo raso (no impreso)
area = lambda P: abs(sum(P[i][0] * P[(i + 1) % len(P)][1] - P[(i + 1) % len(P)][0] * P[i][1] for i in range(len(P)))) / 2
losas = [s for s in geo["superficies"] if papel[s["id"]].startswith("losa")]
area_nivel = {}
for s in losas:
    zc = V[s["vertices"][0]][2]
    area_nivel[zc] = area_nivel.get(zc, 0) + area([V[v] for v in s["vertices"]])
# Tabiques no estructurales (E.020 1.1, pesos reales en su ubicación): muros de 0,10 sin placa de L0005, repartidos en el piso
# (hipótesis de reparto uniforme; altura libre 2,60 − 0,17 m; concreto 24 kN/m³ por el corte 5-5).
gamma = rne.peso_especifico("concreto_armado")["peso_kN_m3"]
no_estr = [x for x in MUROS["laminas"]["L0005"]["muros"] if not x["modelable"] and x["motivo"].startswith("Muro de 0,10")]
peso_tabiques = sum(x["largo_m"] for x in no_estr) * (2.60 - 0.17) * 0.10 * gamma
pisos_tipicos = [zc for zc in COTAS[1:] if zc < Z_TECHO]
q_tab = round(peso_tabiques / (sum(area_nivel[zc] for zc in pisos_tipicos) / len(pisos_tipicos)), 3)
cfg["patrones"] = [
    {"id": "D", "tipo": "muerta", "multiplicador_peso_propio": 1, "fuente": "F-HIPOTESIS-PILOTO-09"},
    {"id": "L", "tipo": "viva", "multiplicador_peso_propio": 0, "fuente": "F-L0001-ESPEC"},
]
cargas = []
for s in losas:
    zc = V[s["vertices"][0]][2]
    techo = zc == Z_TECHO
    qd = PESO_ALIG + ACABADOS + (0 if techo else q_tab)
    ql = 1.5 if techo else 2.0          # L0001: azotea 150, 1.º–4.º 200 kgf/m² (E.020: vivienda 2,0; techo ≥ 1,0)
    cargas.append({"id": f"QD-{s['id']}", "patron": "D", "objetivo_tipo": "superficie", "objetivo": s["id"], "componentes": [0, 0, -round(qd, 3)],
                   "unidad": "kN/m2", "sistema": "global", "fuente": "F-HIPOTESIS-PILOTO-09"})
    cargas.append({"id": f"QL-{s['id']}", "patron": "L", "objetivo_tipo": "superficie", "objetivo": s["id"], "componentes": [0, 0, -ql],
                   "unidad": "kN/m2", "sistema": "global", "fuente": "F-L0001-ESPEC"})
cfg["cargas"] = cargas

# Masa (E.030 art. 31, categoría C: 100 % CM + 25 % CV; azotea 25 %). Peso propio por el patrón D (multiplicador 1).
FCV = cn.e030.fraccion_carga_viva("C")["fraccion"]
assert FCV == cn.e030.fraccion_carga_viva("azotea")["fraccion"]   # un único factor vale para pisos y azotea
cfg["masa"] = {"metodo": "patrones", "gravedad_m_s2": 9.80665, "incluir_masa_propia": False,
               "factores_patrones": [{"patron": "D", "factor": 1.0}, {"patron": "L", "factor": FCV}], "masas_puntos": [],
               "fuente": "RNE-E030-RM183-2026"}

# Apoyos: base empotrada (z = 0). Diafragmas rígidos por nivel.
pid = {p["vertice_geometria"]: p["id"] for p in cfg["puntos"]}
base = sorted(p for v, p in pid.items() if V[v][2] == 0)
cfg["apoyos"] = [{"punto": p, "restricciones": [True] * 6, "fuente": "F-HIPOTESIS-PILOTO-09"} for p in base]
cfg["diafragmas"] = [{"id": f"DIAF-{['N0', 'N1', 'N2', 'N3', 'N4'][COTAS.index(zc)]}", "tipo": "rigido",
                      "puntos": sorted(p for v, p in pid.items() if V[v][2] == zc), "fuente": "F-HIPOTESIS-PILOTO-09"} for zc in COTAS[1:]]
cfg["sin_diafragma"] = [{"punto": p, "motivo": "Punto de base con apoyo empotrado.", "fuente": "F-HIPOTESIS-PILOTO-09"} for p in base]

# Casos: gravedad y modal (el sismo estático/espectral espera perfil, sistema e irregularidades).
cfg["casos"] = [
    {"id": "CM", "tipo": "estatico_lineal", "parametros": {"patrones": [{"patron": "D", "factor": 1}]}, "fuente": "F-HIPOTESIS-PILOTO-09"},
    {"id": "CV", "tipo": "estatico_lineal", "parametros": {"patrones": [{"patron": "L", "factor": 1}]}, "fuente": "F-L0001-ESPEC"},
    {"id": "MODAL", "tipo": "modal_eigen", "parametros": {"numero_modos": 12}, "fuente": "RNE-E030-RM183-2026"},
]
cfg["combinaciones"] = [{"id": "U1", "tipo": "lineal", "casos": [{"caso": "CM", "factor": 1.4}, {"caso": "CV", "factor": 1.7}],
                         "fuente": "RNE-E060-DS010-2009"}]
cfg["analisis"] = {"casos_ejecutar": ["CM", "CV", "MODAL"], "combinaciones_resultados": ["U1"], "fuente": "F-HIPOTESIS-PILOTO-09"}

# Conexiones de borde: ninguna. La malla es conforme por vértices compartidos (sin nodos colgantes, GEOMETRIA_09B).
cfg["conexiones_borde"] = pc.documento_conexiones(
    geo, [], [{"id": "F-CX", "descripcion": "Malla conforme por construcción (geometria_09b.py)", "referencia": "GEOMETRIA_09B.json",
               "sha256": sha(SEG / "GEOMETRIA_09B.json")}],
    {"declarado_por": "Claude (ruta autónoma 09), declaración no verificada", "fecha": "2026-10-21",
     "alcance": "Sin conexiones de borde: todas las superficies comparten vértices por identidad; no hay uniones por proximidad."})
cfg["malla"]["fuente"] = "F-MODELACION-09B"
cfg["liquidos"] = {"aplicabilidad": "informacion_insuficiente", "fuente": "F-L0001-ESPEC",
                   "motivo": "Cisterna (L0001/L0003, NFC −2.65) y tanque elevado (L0003/L0006, NTT +14.60) EXISTEN; falta el nivel libre "
                             "de operación y su geometría/apoyos en el modelo. No se asume ausencia ni se crea agua ficticia.",
                   "declaraciones": []}

H = lambda i, t: {"id": i, "descripcion": t, "fuente": "F-HIPOTESIS-PILOTO-09"}
cfg["hipotesis"] += [
    H("H-GEO-LINEAS", "Ejes de muros, extremos y columnas ajustados a líneas de modelación (±6 cm eje, ±20 cm extremo); malla conforme."),
    H("H-VANOS", "Vanos de puertas y ventanas en toda la altura del muro; dinteles y alféizares no se modelan (rigidez menor). "
                 "Vigas soleras VS 0,15×0,30 sobre los vanos de los ejes 3, 1, A y 2."),
    H("H-LOSA", f"Losa aligerada e=17 cm como membrana homogénea de 5 cm sin peso; peso E.020 Anexo 1 {PESO_ALIG} kPa + acabados "
                f"{ACABADOS} kPa (hipótesis) + tabiques no estructurales {q_tab} kPa (pesos reales de MUROS_09 repartidos)."),
    H("H-BASE", "Base empotrada en z = 0 (cimiento corrido y zapatas rígidos); sin interacción suelo-estructura."),
    H("H-DIAFRAGMA", "Diafragma rígido por nivel con todos los puntos de la cota (losa continua alrededor de los huecos)."),
    H("H-COLUMNAS", "Columnas rectangulares orientadas por su lado largo dibujado. C-1 como L NATIVA (SetConcreteL .40×.40, brazos .15) "
                    "con espejo por instancia e inserción en su centroide real (cardinal 10 + desplazamiento global, rigidez "
                    "transformada); el nudo conserva su conexión con muros y losas. En el montaje del ensayo propio 246 la respuesta no "
                    "mostró acople por producto de inercia (I22 = I33 sobre ejes paralelos a los brazos); no se generaliza. C-6 excluida (zona de escalera)."),
    H("H-ESPESOR-MURO", "Espesor de albañilería 0,15 m dibujado (corte 1-1); el espesor efectivo E.070 sin tarrajeo queda por confirmar."),
]
cfg["faltantes"] += [
    {"ruta": "$.sitio.sistema_resistente", "motivo": "Sistema estructural (albañilería confinada o muros de concreto; L0001 declara Rx=Ry=6) "
                                                    "por decidir con el usuario.", "fuente": "F-L0001-ESPEC"},
    {"ruta": "$.casos.sismo", "motivo": "Sismo estático y espectral: requieren perfil de suelo/EMS, sistema (R0) e irregularidades.",
     "fuente": "RNE-E030-RM183-2026"},
    {"ruta": "$.geometria.escalera_tanque_PL10", "motivo": "Escalera, tanque elevado, cisterna y PL-10 fuera del modelo (faltantes de la geometría).",
     "fuente": "F-MODELACION-09B"},
]
cfg["insercion_frames"] = insercion
cfg["id"] = CASO + "-config-09b"
# Con geometría y sin errores, el validador PREPARA la malla real (≈ 160 s tras la optimización de Codex 247). Se valida solo
# con --con-malla, una vez estable la geometría (sin geometría la conectividad no es comprobable y el resultado no informa).
CON_MALLA = "--con-malla" in sys.argv
resultado = m.validar_configuracion(cfg, geo) if CON_MALLA else None
salida = RAIZ / "tmp/ruta201/configuracion09b.json"
salida.write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
errores = [str(e) for e in resultado.errores] if resultado else []
resumen_err = {}
for e in errores:
    resumen_err[e.split(":")[0]] = resumen_err.get(e.split(":")[0], 0) + 1
inf = {"validacion": "con geometría y malla real" if CON_MALLA else "pendiente: ejecutar con --con-malla con la geometría estable",
       "configuracion": salida.relative_to(RAIZ).as_posix(), "sha256": sha(salida), "geometria": GEO, "normativa": informe,
       "conteos": {"puntos": len(cfg["puntos"]), "superficies": len(cfg["asignaciones_superficies"]), "frames": len(frames),
                   "columnas": sum(1 for f in frames if f["tipo"] == "columna"), "vigas": len(vigas), "cargas": len(cargas),
                   "apoyos": len(base), "diafragmas": len(cfg["diafragmas"])},
       "cargas_kPa": {"aligerado": PESO_ALIG, "acabados": ACABADOS, "tabiques": q_tab, "peso_tabiques_piso_kN": round(peso_tabiques, 1),
                      "area_losa_m2": {str(k): round(v, 2) for k, v in area_nivel.items()}},
       "columnas_excluidas": excluidas, "contrato_consistente": resultado.consistente if resultado else None,
       "faltantes_calculados": [f["ruta"] for f in resultado.faltantes] if resultado else None,
       "preparacion_malla": resultado.preparacion_malla if resultado else None, "errores_por_ruta": resumen_err,
       "errores_contrato": errores[:40], "faltantes": [f["ruta"] for f in cfg["faltantes"]], "aprobacion_ingenieria": None}
(SEG / "CONFIGURACION_CASO_09B.json").write_text(json.dumps(inf, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
print("consistente:", resultado.consistente if resultado else "sin validar (--con-malla)", "| errores:", len(errores), resumen_err)
print("conteos", inf["conteos"], "| q_tab", q_tab, "| faltantes", inf["faltantes"])
for e in errores[:15]:
    print("  ", e)
