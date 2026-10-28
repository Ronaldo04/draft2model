"""Configuración 0.5 del caso real sobre la geometría 3905c919 (insumos 248: depósitos, PL-10, C-6). No aprueba ni inventa datos.

Ejecutar desde la raíz: python seguimiento/claude_ruta/configuracion_09c.py [--con-malla]
Salidas: tmp/ruta201/configuracion09c.json (configuración en borrador) y seguimiento/claude_ruta/CONFIGURACION_CASO_09C.json (informe).
Con --con-malla prepara la malla real UNA vez (recibo con tiempo y huella), declara la política de sus nodos derivados y valida.

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

CASO = "pueblo-libre-002"
# --transporte: ESCENARIO DE TRANSPORTE autorizado por el usuario (aprobación declarada solo de software, no ingeniería) sobre la
# geometría aprobada b145a29d (= 3905c919 con faltantes como hipótesis). Un único escenario sísmico, etiquetado como hipótesis.
TRANSPORTE = "--transporte" in sys.argv
_VERS = json.loads((Path(__file__).resolve().parent / "VERSIONES_09.json").read_text(encoding="utf-8"))
GEO = _VERS["09t_aprobada"] if TRANSPORTE else _VERS["09c"]   # versiones con niveles físicos de los depósitos (NCF, NTF, NTT)
SUF = "09t" if TRANSPORTE else "09c"
PRIV = RAIZ / "data/private"
ORIG = PRIV / CASO / "originales"
SEG = RAIZ / "seguimiento/claude_ruta"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
GEO09B = json.loads((SEG / "GEOMETRIA_09C.json").read_text(encoding="utf-8"))
MUROS = json.loads((SEG / "MUROS_09.json").read_text(encoding="utf-8"))
geo = gg.consultar_version(PRIV, CASO, GEO).geometria
V = {v["id"]: (v["x"], v["y"], v["z"]) for v in geo["vertices"]}
COTAS = [0.0, 2.6, 5.2, 7.8, 10.4]          # pisos N0–N4 (confirmados por el usuario, DECISION_USUARIO_246)
Z_TECHO = max(COTAS)
Z_APOYO = {0.0: "base de los pisos (N0)", -0.05: "base de los cercos PL-10 (NFP −0,05, corte 2-2)",
           -2.50: "fondo de la cisterna (plano medio; hipótesis NFC = solado)"}

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
     "referencia": "seguimiento/claude_ruta/geometria_09c.py", "sha256": sha(SEG / "geometria_09c.py")},
    {"id": "F-L0001-CORTE22", "descripcion": "Corte 2-2 de L0001 (PL-10): muro .10, altura 2,40 desde NFP −0,05, concreto f'c 175, malla "
                                             "Ø3/8\"@.25; A01 «CERCO H=2.40» (auditoría Codex 248).",
     "referencia": "L0001 · corte 2-2", "sha256": sha(ORIG / "lamina-0001.pdf")},
    {"id": "F-L0003-DEPOSITOS", "descripcion": "E03: corte tanque (2,00/.20/1,10/.45/.20/.10 desde NT +10,35), «NACE C-2», corte y techo de "
                                               "cisterna (2,22 interior; .15/.20; claro 2,00 × 2,15; acceso .55) (auditoría Codex 248).",
     "referencia": "L0003", "sha256": sha(ORIG / "lamina-0003.pdf")},
    {"id": "F-AUDITORIAS-248", "descripcion": "Auditorías de depósitos, escalera, C-6/PL-10 revisadas por Codex 248.",
     "referencia": "seguimiento/REVISION_AUDITORIAS_248.json", "sha256": sha(RAIZ / "seguimiento/REVISION_AUDITORIAS_248.json")},
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
        {"id": "CONCRETO-FC175", "clase": "concreto", "resistencia": 175, "unidad": "kgf/cm2", "fuente": "F-L0001-CORTE22"},
        {"id": "ALBANILERIA-FM35", "clase": "albanileria", "resistencia": 35, "unidad": "kgf/cm2", "tipo_unidad": "arcilla",
         "peso_kN_m3": rne.peso_especifico("albanileria_cocida_solida")["peso_kN_m3"], "fuente": "F-DECISION-USUARIO-246"},
    ],
    "zona": {"valor": 4, "estado": "lectura_expediente", "fuente": "F-L0001-ROTULO"},       # Pueblo Libre, provincia de Lima → zona 4
    "categoria": {"valor": "C", "estado": "lectura_expediente", "fuente": "F-L0001-ROTULO"},  # vivienda multifamiliar
}
if TRANSPORTE:
    cfg["fuentes"].append({"id": "F-ESCENARIO-TRANSPORTE", "referencia": "seguimiento/claude_ruta/ESCENARIOS_SISMICOS_09.json",
                           "sha256": sha(SEG / "ESCENARIOS_SISMICOS_09.json"),
                           "descripcion": "Escenario de transporte autorizado por el usuario (2026-10-22): perfil S1 y muros de concreto R0 = 6, "
                                          "ambos de la lectura de L0001 (GP; S = 1,0; Rx = Ry = 6 con la norma de 2003), Ia = Ip = 1. "
                                          "HIPÓTESIS: sin EMS, no es suelo real ni sustituto del EMS; no aprueba ingeniería."})
    E = lambda v: {"valor": v, "estado": "hipotesis_piloto", "fuente": "F-ESCENARIO-TRANSPORTE"}
    decisiones.update(perfil=E("S1"), sistema=E("concreto_muros_estructurales"), Ia=E(1.0), Ip=E(1.0), id_espectro="ESP-S1-R6-HIP")
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
                "sistema_resistente": ("HIPÓTESIS DE TRANSPORTE: muros estructurales de concreto (R0 = 6, L0001) con albañilería confinada "
                                       "en el perímetro y el eje central; no confirmado por el usuario.") if TRANSPORTE else None,
                "parametros": [{"id": "Z", "valor": z["Z"], "unidad": "1", "fuente": "RNE-E030-RM183-2026"},
                               {"id": "U", "valor": u["U"], "unidad": "1", "fuente": "RNE-E030-RM183-2026"}],
                "fuente": "F-L0001-ROTULO"}

# Secciones.
COL_DIM = {"C-1": (0.15, 0.40), "C-2": (0.15, 0.40), "C-3": (0.15, 0.60), "C-4": (0.15, 0.40), "C-5": (0.15, 0.30),
           "C-6": (0.20, 0.75)}   # C-6: espesor dibujado .20 en tres plantas (cuadro .15): discrepancia declarada
secciones = [
    {"id": "MURO-KK-15", "tipo": "shell_muro", "material": ALB, "dimensiones": {"espesor_m": 0.15}, "fuente": "F-MUROS-09"},
    {"id": "PLACA-10", "tipo": "shell_muro", "material": "CONCRETO-FC210", "dimensiones": {"espesor_m": 0.10}, "fuente": "F-MUROS-09"},
    {"id": "CERCO-10", "tipo": "shell_muro", "material": "CONCRETO-FC175", "dimensiones": {"espesor_m": 0.10}, "fuente": "F-L0001-CORTE22"},
    {"id": "DEP-MURO-20", "tipo": "shell_muro", "material": "CONCRETO-FC210", "dimensiones": {"espesor_m": 0.20}, "fuente": "F-L0003-DEPOSITOS"},
    {"id": "DEP-MURO-15", "tipo": "shell_muro", "material": "CONCRETO-FC210", "dimensiones": {"espesor_m": 0.15}, "fuente": "F-L0003-DEPOSITOS"},
    {"id": "DEP-FONDO-20", "tipo": "shell_losa_homogenea", "material": "CONCRETO-FC210", "dimensiones": {"espesor_m": 0.20}, "fuente": "F-L0003-DEPOSITOS"},
    {"id": "DEP-TAPA-15", "tipo": "shell_losa_homogenea", "material": "CONCRETO-FC210", "dimensiones": {"espesor_m": 0.15}, "fuente": "F-L0003-DEPOSITOS"},
    {"id": "DEP-TAPA-20", "tipo": "shell_losa_homogenea", "material": "CONCRETO-FC210", "dimensiones": {"espesor_m": 0.20}, "fuente": "F-L0003-DEPOSITOS"},
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
SEC_CLASE = {"albanileria_king_kong": "MURO-KK-15", "concreto": "PLACA-10", "losa": "LOSA-MEMB-05", "cerco_concreto": "CERCO-10",
             ("deposito_muro", 0.20): "DEP-MURO-20", ("deposito_muro", 0.15): "DEP-MURO-15", ("deposito_fondo", 0.20): "DEP-FONDO-20",
             ("deposito_tapa", 0.15): "DEP-TAPA-15", ("deposito_tapa", 0.20): "DEP-TAPA-20"}
FUENTE_CLASE = {"cerco_concreto": "F-L0001-CORTE22", "deposito_muro": "F-L0003-DEPOSITOS", "deposito_fondo": "F-L0003-DEPOSITOS",
                "deposito_tapa": "F-L0003-DEPOSITOS", "losa": "F-L0002-ALIGERADO"}
sec_de = lambda c: SEC_CLASE.get(c["clase"]) or SEC_CLASE[(c["clase"], c["espesor_m"])]
cfg["asignaciones_superficies"] = [{"objetivo": a["objetivo"], "seccion": sec_de(clases[a["objetivo"]]),
                                    "fuente": FUENTE_CLASE.get(clases[a["objetivo"]]["clase"], "F-MUROS-09")}
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
base = sorted(p for v, p in pid.items() if V[v][2] in Z_APOYO)
cfg["apoyos"] = [{"punto": p, "restricciones": [True] * 6, "fuente": "F-HIPOTESIS-PILOTO-09"} for p in base]
X_LOSA = max(GEO09B["lineas_x"]) + 1e-6
en_losa = lambda v: V[v][2] in COTAS[1:] and V[v][0] <= X_LOSA      # C-6 queda fuera (zona de escalera)
cfg["diafragmas"] = [{"id": f"DIAF-{['N0', 'N1', 'N2', 'N3', 'N4'][COTAS.index(zc)]}", "tipo": "rigido",
                      "puntos": sorted(p for v, p in pid.items() if V[v][2] == zc and en_losa(v)), "fuente": "F-HIPOTESIS-PILOTO-09"}
                     for zc in COTAS[1:]]


def motivo_sin(v):
    z = V[v][2]
    if z in Z_APOYO:
        return f"Apoyo empotrado: {Z_APOYO[z]}."
    if z in COTAS:
        return "C-6 fuera de la losa (zona de escalera no modelada): sin diafragma."
    return "Nodo de depósito o de cerco fuera de los pisos: sin diafragma."


cfg["sin_diafragma"] = [{"punto": p, "motivo": motivo_sin(v), "fuente": "F-HIPOTESIS-PILOTO-09"} for v, p in sorted(pid.items(), key=lambda x: x[1])
                        if not en_losa(v)]

# Casos: gravedad y modal (el sismo estático/espectral espera perfil, sistema e irregularidades).
# «MODAL-E030»: la plantilla vacía de ETABS ya contiene el caso por defecto «Modal» (corrida 36cba119).
cfg["casos"] = [
    {"id": "CM", "tipo": "estatico_lineal", "parametros": {"patrones": [{"patron": "D", "factor": 1}]}, "fuente": "F-HIPOTESIS-PILOTO-09"},
    {"id": "CAGUA", "tipo": "estatico_lineal", "parametros": {"patrones": [{"patron": "AGUA-TAN", "factor": 1}, {"patron": "AGUA-CIS", "factor": 1}]},
     "fuente": "F-L0003-DEPOSITOS"},
    {"id": "CV", "tipo": "estatico_lineal", "parametros": {"patrones": [{"patron": "L", "factor": 1}]}, "fuente": "F-L0001-ESPEC"},
    {"id": "MODAL-E030", "tipo": "modal_eigen", "parametros": {"numero_modos": 12}, "fuente": "RNE-E030-RM183-2026"},
]
cfg["combinaciones"] = [{"id": "U1", "tipo": "lineal", "casos": [{"caso": "CM", "factor": 1.4}, {"caso": "CV", "factor": 1.7}],
                         "fuente": "RNE-E060-DS010-2009"}]
cfg["analisis"] = {"casos_ejecutar": ["CM", "CV", "CAGUA", "MODAL-E030"], "combinaciones_resultados": ["U1"], "fuente": "F-HIPOTESIS-PILOTO-09"}
if TRANSPORTE:
    # Espectro E.030 (m/s², incluye g y R): factor 1; amortiguamiento 5 %; CQC; excentricidad accidental 0,05 en las opciones del plan.
    for ident, direccion in (("SX", "UX"), ("SY", "UY")):
        cfg["casos"].append({"id": ident, "tipo": "espectro_respuesta", "fuente": "F-ESCENARIO-TRANSPORTE",
                             "parametros": {"modal": "MODAL-E030", "espectro": "ESP-S1-R6-HIP", "direccion": direccion, "factor": 1.0,
                                            "amortiguamiento": 0.05, "combinacion_modal": "CQC"}})
        cfg["analisis"]["casos_ejecutar"].append(ident)

# Conexiones de borde. Los vértices se comparten por identidad, pero la partición en franjas SUBDIVIDE las celdas no
# rectangulares (cortadas por las diagonales de PL-4) e inserta nodos en sus aristas; sin conexión declarada esos nodos quedan
# colgantes en la superficie vecina (relectura del recorrido 09T, corrida 2af8b738: 32 nodos colgantes). Se declara cada arista
# de una superficie no rectangular compartida (mismos dos vértices) con otra superficie; la compatibilidad propaga los nodos.
def conexiones_aristas():
    sups = geo["superficies"]
    def rectangulo(sv):
        q = [V[v] for v in sv["vertices"]]
        if len(q) != 4:
            return False
        if all(abs(p[2] - q[0][2]) < 1e-9 for p in q):              # horizontal: alineado con X e Y
            return len({p[0] for p in q}) == 2 and len({p[1] for p in q}) == 2
        return len({round(p[2], 9) for p in q}) == 2                  # vertical: dos cotas
    aristas = {}
    for sv in sups:
        vs = sv["vertices"]
        for u, v in zip(vs, vs[1:] + vs[:1]):
            aristas.setdefault(frozenset((u, v)), []).append((sv["id"], u, v))
    irregulares = {sv["id"] for sv in sups if not rectangulo(sv)}
    out, vistos = [], set()
    for clave, lados in sorted(aristas.items(), key=lambda kv: sorted(kv[0])):
        for i, a in enumerate(lados):
            for b in lados[i + 1:]:
                if a[0] == b[0] or not ({a[0], b[0]} & irregulares):
                    continue
                par = tuple(sorted((a[0], b[0]))) + tuple(sorted(clave))
                if par in vistos:
                    continue
                vistos.add(par)
                out.append({"id": f"CX{len(out) + 1:04d}", "a": {"superficie": a[0], "desde": a[1], "hasta": a[2]},
                            "b": {"superficie": b[0], "desde": b[1], "hasta": b[2]}, "fuente": "F-CX"})
    return out, sorted(irregulares)


conexiones, irregulares = conexiones_aristas()
cfg["conexiones_borde"] = pc.documento_conexiones(
    geo, conexiones, [{"id": "F-CX", "descripcion": "Aristas compartidas de superficies no rectangulares (geometria_09c.py)",
                       "referencia": "GEOMETRIA_09C.json", "sha256": sha(SEG / "GEOMETRIA_09C.json")}],
    {"declarado_por": "Claude (ruta autónoma 09), declaración no verificada", "fecha": "2026-10-22",
     "alcance": f"{len(conexiones)} aristas compartidas (mismos dos vértices) de {len(irregulares)} superficies no rectangulares con sus "
                "vecinas; el resto comparte vértices por identidad. Sin uniones por proximidad."})
cfg["malla"]["fuente"] = "F-MODELACION-09B"
# Agua (escenarios declarados, no nivel operativo confirmado): presión estática γ = 10 kN/m³ (E.020 anexo 1) sobre muros y fondo.
GAMMA_AGUA = rne.peso_especifico("agua_dulce")["peso_kN_m3"]
ESCENARIOS_AGUA = {"TAN": ("AGUA-TAN", 12.60 + 1.10, "Tanque: tramo inferior 1,10 m del corte E03 como lámina de agua (sin rótulo N.A.: hipótesis)."),
                   "CIS": ("AGUA-CIS", -2.40 + 2.22, "Cisterna: llena hasta la altura interior impresa 2,22 m (límite superior, no operación).")}
sup_geo = {x["id"]: x for x in geo["superficies"]}


def normal(sid):
    a, b, c = (V[v] for v in sup_geo[sid]["vertices"][:3])
    u, w = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
    return [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]


def sentido(sid, centro):
    """+1/−1 para que la fuerza (normal × sentido) salga del líquido: muros hacia fuera, fondo hacia −Z."""
    n = normal(sid)
    pts = [V[v] for v in sup_geo[sid]["vertices"]]
    c = [sum(p[i] for p in pts) / len(pts) for i in range(3)]
    hacia_fuera = [c[0] - centro[0], c[1] - centro[1], 0.0] if clases[sid]["clase"] == "deposito_muro" else [0.0, 0.0, -1.0]
    return 1 if sum(n[i] * hacia_fuera[i] for i in range(3)) > 0 else -1


REV = {"estado": "revisado", "declarada_por": "Claude (ruta 09): cotejo con E03 y auditoría Codex 248; NO revisión de ingeniería",
       "fecha": "2026-10-22", "motivo": "Escenario de agua del piloto, identificado como hipótesis."}
declaraciones = []
for pref, (patron, nivel, texto) in ESCENARIOS_AGUA.items():
    caja = GEO09B["depositos"]["cisterna" if pref == "CIS" else "tanque"]
    centro = [(caja["x"][0] + caja["x"][-1]) / 2, (caja["y"][0] + caja["y"][-1]) / 2, 0.0]
    hosts = sorted(sid for sid in sup_geo if sid.startswith(pref + "-M") or sid.startswith(pref + "-F-"))
    fuentes_liq = [{"id": "F1", "contenido": {"escenario": texto, "nivel_libre_z_m": nivel, "gamma_kn_m3": GAMMA_AGUA,
                                              "fuente_registrada": "F-L0003-DEPOSITOS"}, "revision": REV}]
    d = {"contrato": "draft2model.acciones_liquidos", "version_contrato": "0.1.0", "id": "AGUA-" + pref, "nivel_libre_z_m": round(nivel, 6),
         "peso_especifico_kn_m3": GAMMA_AGUA, "origen_momentos_m": [0, 0, 0],
         "superficies": [{"superficie": h, "sentido_normal": sentido(h, centro), "fuentes": ["F1"]} for h in hosts],
         "revision": {**REV, "fuentes": ["F1"]}}
    declaraciones.append({"declaracion": d, "fuentes": fuentes_liq, "patron": patron})
# acciones_liquidos exige geometría SIN faltantes; la 3905c919 declara 6 (escalera no modelada, alternativas). Los escenarios
# quedan preparados en DEPOSITOS_09C.json y la aplicabilidad es «informacion_insuficiente» (faltante, no ausencia).
ACTIVAR_AGUA = TRANSPORTE   # la geometría de transporte no tiene faltantes: el escenario de agua se aplica
if ACTIVAR_AGUA:
    cfg["patrones"] += [{"id": p, "tipo": "otro", "multiplicador_peso_propio": 0, "fuente": "F-L0003-DEPOSITOS"} for p, _, _ in ESCENARIOS_AGUA.values()]
    cfg["masa"]["factores_patrones"].append({"patron": "AGUA-TAN", "factor": cn.e030.fraccion_carga_viva("tanque")["fraccion"]})
    cfg["cortes_nivel"] = [{"z_m": round(n, 6), "fuente": "F-L0003-DEPOSITOS", "motivo": "Nivel libre del escenario de agua: " + t}
                           for _, n, t in ESCENARIOS_AGUA.values()]
    cfg["liquidos"] = {"aplicabilidad": "presente", "fuente": "F-L0003-DEPOSITOS",
                       "motivo": "Cisterna y tanque EXISTEN (E03). Niveles como escenarios declarados (no nivel operativo confirmado); sin "
                                 "hidrodinámica, empuje de suelo ni flotación (sin EMS).", "declaraciones": declaraciones}
else:
    cfg["casos"] = [c for c in cfg["casos"] if c["id"] != "CAGUA"]
    cfg["analisis"]["casos_ejecutar"] = [c for c in cfg["analisis"]["casos_ejecutar"] if c != "CAGUA"]
    cfg["liquidos"] = {"aplicabilidad": "informacion_insuficiente", "fuente": "F-L0003-DEPOSITOS",
                       "motivo": "Cisterna y tanque EXISTEN y están modelados; los escenarios de agua (tanque 1,10 m, cisterna 2,22 m) están "
                                 "preparados en DEPOSITOS_09C.json, pero acciones_liquidos exige geometría sin faltantes y la escalera "
                                 "sigue sin modelar. No se asume ausencia ni se aplica agua parcial.", "declaraciones": []}
(SEG / ("DEPOSITOS_09C.json" if not TRANSPORTE else "DEPOSITOS_09T.json")).write_text(json.dumps({
    "caso": CASO, "geometria": GEO, "estado": ("escenarios_aplicados_en_configuracion_de_transporte; masa nativa del contenido NO verificada" if TRANSPORTE else "escenarios_preparados_no_aplicados"), "aprobacion_ingenieria": None,
    "tanque": {"alternativa_modelada": "E03-apoyos: C-2 «NACE C-2» (11,315/13,59 × 3,09/5,02 vectorizados en E03) + C-2 del eje 2; caja en "
                                       "x 11,335–13,748, y 3,118–5,018 (líneas de modelación); fondo +12,50, tapa +14,25 (planos medios).",
               "alternativa_no_modelada": "A03: rectángulo «TANQUE DE AGUA» ≈ x 10,98–13,80, y 3,07–6,99 (2,82 × 3,92), NTT +14,60.",
               "cadena_E03": "NT +10,35 · 2,00 apoyo · .20 fondo · 1,10 · .45 · .20 tapa · .10 resalto → +14,40 (no a escala: medición "
                             "vectorial 1,68 m para «2.00»).", "base_modelada": "N4 +10,40 (A03): 5 cm sobre NT +10,35."},
    "cisterna": {"caja_L0001_m": json.loads((SEG / "INVENTARIO_GEOMETRICO_09.json").read_text(encoding="utf-8"))["cisterna"]["caja_aprox_m"],
                 "cadena": "NFC −2,65 = solado .05 (hipótesis) → fondo −2,60/−2,40 → interior 2,22 → −0,18 → tapa .15 → −0,03 (NPT ±0,00 − 3 cm)"},
    "escenarios_agua": [{"patron": it["patron"], "declaracion": it["declaracion"], "fuentes": it["fuentes"]} for it in declaraciones],
    "escalera": {"estado": "no_modelada", "evidencia": "AUDITORIA_ESCALERA_248 S1–S8", "trazado_planta_m": {
                     "x": [14.94, 16.89], "tramo_superior_y": [3.0, 4.2], "tramo_derecho_x": [15.69, 16.89], "tramo_inferior_y": [5.99, 7.17],
                     "ojo": "x 14,94–15,69, y 4,2–5,95 (C-6 en el ojo)"},
                 "hipotesis_A03": "Último entrepiso: huellas 50–52 / 53–60 / 61–64 → 16 contrahuellas de 0,1625 m (no aplicada a otros pisos: "
                                  "A01/A02 difieren).",
                 "masa_estimada_fuera_del_modelo_kN_por_piso": "≈ 40 (rampas e = .15 + peldaños y descansos .20 sobre ≈ 7 m² de planta), sin "
                                                               "sobrecarga 2,0 kPa; ≈ 4 % del peso de un piso típico."}},
    ensure_ascii=False, indent=1) + chr(10), encoding="utf-8")

H = lambda i, t: {"id": i, "descripcion": t, "fuente": "F-HIPOTESIS-PILOTO-09"}
cfg["hipotesis"] += [
    H("H-GEO-LINEAS", "Ejes de muros, extremos y columnas ajustados a líneas de modelación (±6 cm eje, ±20 cm extremo); malla conforme."),
    H("H-VANOS", "Vanos de puertas y ventanas en toda la altura del muro; dinteles y alféizares no se modelan (rigidez menor). "
                 "Vigas soleras VS 0,15×0,30 sobre los vanos de los ejes 3, 1, A y 2."),
    H("H-LOSA", f"Losa aligerada e=17 cm como membrana homogénea de 5 cm sin peso; peso E.020 Anexo 1 {PESO_ALIG} kPa + acabados "
                f"{ACABADOS} kPa (hipótesis) + tabiques no estructurales {q_tab} kPa (pesos reales de MUROS_09 repartidos)."),
    H("H-BASE", "Base empotrada en z = 0 (cimiento corrido y zapatas rígidos), en la base de los cercos PL-10 (−0,05) y en el fondo de la "
                "cisterna (−2,50); sin interacción suelo-estructura, empuje de suelo ni flotación (sin EMS)."),
    H("H-DIAFRAGMA", "Diafragma rígido por nivel con los puntos de la losa (x ≤ eje H); C-6, depósitos y cercos quedan fuera."),
    H("H-DEPOSITOS", "Cisterna: caja L0001 + E03; NFC −2,65 = cara inferior del solado .05 → fondo −2,50 (plano medio), tapa −0,105; "
                     "subestructura independiente (conexión con C-3/C-6 no acotada). Tanque (alternativa E03-apoyos): 4 C-2 de N4 a +12,40, "
                     "fondo +12,50, tapa +14,25; muros .20 (hipótesis); base N4 +10,40 en vez de NT +10,35 (E03). Alternativa A03 (huella "
                     "2,82 × 3,92) no modelada. Fondos y tapas con flexión (ShellThick por sección, R241)."),
    H("H-AGUA", "Agua como escenarios: tanque 1,10 m sobre el fondo (+13,70), cisterna llena 2,22 m (−0,18); γ = 10 kN/m³; masa 100 % "
                "del contenido del tanque (E.030 art. 31.e); la cisterna se apoya en su base y no aporta masa a los pisos."),
    H("H-PL10", "PL-10: dos cercos .10 de −0,05 a +2,35 (corte 2-2, A01), concreto f'c 175, base propia, independientes del edificio."),
    H("H-C6", "C-6: frame .20 × .75 (dibujo; cuadro .15) de N0 a N3 (ausente en E03 4.º nivel); voladizo sin diafragma porque la escalera "
              "no está modelada."),
    H("H-ESCALERA", "Escalera en U NO modelada (reparto vertical no cerrado por las fuentes, auditoría 248): su masa y rigidez faltan; "
                    "estimación en DEPOSITOS_09C."),
    H("H-COLUMNAS", "Columnas rectangulares orientadas por su lado largo dibujado. C-1 como L NATIVA (SetConcreteL .40×.40, brazos .15) "
                    "con espejo por instancia e inserción en su centroide real (cardinal 10 + desplazamiento global, rigidez "
                    "transformada); el nudo conserva su conexión con muros y losas. En el montaje del ensayo propio 246 la respuesta no "
                    "mostró acople por producto de inercia (I22 = I33 sobre ejes paralelos a los brazos); no se generaliza."),
    H("H-ESPESOR-MURO", "Espesor de albañilería 0,15 m dibujado (corte 1-1); el espesor efectivo E.070 sin tarrajeo queda por confirmar."),
]
if TRANSPORTE:
    # Escalera fuera del modelo: su peso estimado entra como fuerzas en sus llegadas sobre el eje H (mitad de cada tramo a cada
    # nivel), repartido por igual entre los nudos de esas franjas. Estimación: 40 kN de peso propio y 2,0 kPa × 7 m² de sobrecarga por tramo.
    llegadas = lambda zc: sorted(v for v, p in V.items() if abs(p[2] - zc) < 1e-9 and abs(p[0] - max(GEO09B["lineas_x"])) < 1e-6
                                 and (3.0 <= p[1] <= 4.2 or 5.99 <= p[1] <= 7.17))
    for zc in COTAS[1:]:
        nudos = llegadas(zc)
        mitades = 1 if zc == Z_TECHO else 2
        for patron, total in (("D", 40.0), ("L", 2.0 * 7.0)):
            f = round(total / 2 * mitades / len(nudos), 4)
            for v in nudos:
                cfg["cargas"].append({"id": f"ESC-{patron}-{v}", "patron": patron, "objetivo_tipo": "punto", "objetivo": pid[v],
                                      "componentes": [0, 0, -f], "unidad": "kN", "sistema": "global", "fuente": "F-ESCENARIO-TRANSPORTE"})
    cfg["hipotesis"].append(H("H-TRANSPORTE", "Escenario de TRANSPORTE autorizado por el usuario (aprobación declarada solo de software): "
                                              "S1 + muros de concreto R0 = 6, Ia = Ip = 1; escalera fuera del modelo con su peso como fuerzas en "
                                              "las llegadas del eje H; agua en los escenarios de DEPOSITOS_09C. No es ingeniería ni suelo real."))
cfg["faltantes"] += [] if TRANSPORTE else [
    {"ruta": "$.sitio.sistema_resistente", "motivo": "Sistema estructural (albañilería confinada o muros de concreto; L0001 declara Rx=Ry=6) "
                                                    "por decidir con el usuario.", "fuente": "F-L0001-ESPEC"},
    {"ruta": "$.casos.sismo", "motivo": "Sismo estático y espectral: requieren perfil de suelo/EMS, sistema (R0) e irregularidades.",
     "fuente": "RNE-E030-RM183-2026"},
    {"ruta": "$.geometria.escalera", "motivo": "Escalera en U no modelada: reparto vertical por tramo, descansos y apoyos no cerrados por las "
                                              "fuentes (auditoría 248).", "fuente": "F-AUDITORIAS-248"},
]
cfg["insercion_frames"] = insercion
cfg["id"] = CASO + "-config-" + SUF
# Con geometría y sin errores, el validador PREPARA la malla real (≈ 160 s tras la optimización de Codex 247). Se valida solo
# con --con-malla, una vez estable la geometría (sin geometría la conectividad no es comprobable y el resultado no informa).
CON_MALLA = "--con-malla" in sys.argv
recibo_malla = None
if CON_MALLA:
    import time
    t0 = time.time()
    prep = m.mp.preparar_malla(geo, cfg)
    recibo_malla = {"segundos": round(time.time() - t0, 1), "huella_preparacion": prep["huella_preparacion"],
                    "nodos_derivados": len(prep["nodos_derivados"]), "triangulos": len(prep["triangulos"]),
                    "frames_subdivididos": len(prep["frames_subdivision_requerida"])}
    xyz = {n["csi"]: n["xyz_m"] for n in prep["nodos"]}
    dia = {d["id"]: d for d in cfg["diafragmas"]}
    cfg["nodos_derivados"] = []
    for nodo in prep["nodos_derivados"]:
        x, y, zc = xyz[nodo]
        ident = f"DIAF-{['N0', 'N1', 'N2', 'N3', 'N4'][COTAS.index(zc)]}" if zc in COTAS[1:] and x <= X_LOSA else None
        cfg["nodos_derivados"].append({"nodo": nodo, "xyz_m": xyz[nodo], "restricciones": [zc in Z_APOYO] * 6,
                                       "diafragma": ident, "motivo_sin_diafragma": None if ident else "Nodo de malla fuera de la losa.",
                                       "fuente": "F-HIPOTESIS-PILOTO-09"})
    cfg["subdivision_frames"] = [{"frame": r["frame"], "nodos": r["nodos"], "fuente": "F-HIPOTESIS-PILOTO-09"}
                                 for r in prep["frames_subdivision_requerida"]]
    # Comprobación local de conformidad antes de ETABS: ningún nodo de malla dentro de una arista de un triángulo que no lo use.
    nodos_xyz = {n["csi"]: n["xyz_m"] for n in prep["nodos"]}
    def dentro(pn, a, b):
        ab = [b[k] - a[k] for k in range(3)]; ap = [pn[k] - a[k] for k in range(3)]
        L2 = sum(x * x for x in ab)
        t = sum(ap[k] * ab[k] for k in range(3)) / L2
        if not 1e-9 < t < 1 - 1e-9:
            return False
        return sum((ap[k] - t * ab[k]) ** 2 for k in range(3)) < 1e-12
    por_z = {}
    for t in prep["triangulos"]:
        zs = {round(nodos_xyz[n][2], 6) for n in t["nodos"]}
        for z in zs:
            por_z.setdefault(z, []).append(t)
    colgantes_malla = []
    for nombre, pn in nodos_xyz.items():
        for t in por_z.get(round(pn[2], 6), []):
            if nombre in t["nodos"]:
                continue
            q = [nodos_xyz[n] for n in t["nodos"]]
            if any(dentro(pn, q[i], q[(i + 1) % 3]) for i in range(3)):
                colgantes_malla.append({"nodo": nombre, "triangulo": t["csi"]})
                break
    recibo_malla["nodos_colgantes_locales"] = len(colgantes_malla)
    recibo_malla["colgantes_muestra"] = colgantes_malla[:10]
    (RAIZ / f"tmp/ruta201/malla_real_{SUF}.json").write_text(json.dumps(recibo_malla, indent=1) + "\n", encoding="utf-8")
resultado = m.validar_configuracion(cfg, geo) if CON_MALLA else None
salida = RAIZ / f"tmp/ruta201/configuracion{SUF}.json"
salida.write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
errores = [str(e) for e in resultado.errores] if resultado else []
resumen_err = {}
for e in errores:
    resumen_err[e.split(":")[0]] = resumen_err.get(e.split(":")[0], 0) + 1
inf = {"validacion": "con geometría y malla real" if CON_MALLA else "pendiente: ejecutar con --con-malla con la geometría estable",
       "recibo_malla": recibo_malla,
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
(SEG / f"CONFIGURACION_CASO_{SUF.upper()}.json").write_text(json.dumps(inf, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
print("consistente:", resultado.consistente if resultado else "sin validar (--con-malla)", "| errores:", len(errores), resumen_err)
print("conteos", inf["conteos"], "| q_tab", q_tab, "| faltantes", inf["faltantes"])
for e in errores[:15]:
    print("  ", e)
