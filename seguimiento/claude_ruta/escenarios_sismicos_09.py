"""Escenarios sísmicos del piloto (autorización del usuario 246: SIN EMS, escenarios de suelo SOLO como hipótesis identificadas).

Ejecutar desde la raíz: python seguimiento/claude_ruta/escenarios_sismicos_09.py
Salida: seguimiento/claude_ruta/ESCENARIOS_SISMICOS_09.json.

Para cada perfil S1/S2/S3 (sin Vs30: S y TP/TL tabulados o nota de las Tablas 4/5) y cada sistema candidato (albañilería
confinada R0 = 3; muros de concreto R0 = 6, el que declara L0001 con la norma de 2003), con Ia = Ip = 1 COMO HIPÓTESIS (las
irregularidades se evalúan con el modelo): espectro E.030 tabulado, periodo aproximado (art. 36.1), cortante estático
(art. 34) y fuerzas por nivel (art. 35). El peso sísmico por nivel se deriva de la configuración 09C (peso propio de muros,
placas y columnas repartido mitad arriba/mitad abajo + cargas de losa D + 25 % L, art. 31) y del tanque (con y sin agua).
NO es suelo real ni sustituto del EMS; ningún escenario se elige ni se aprueba aquí.
"""
import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from draft2model import gestion_geometria as gg  # noqa: E402
from draft2model import normativa_e030 as e030  # noqa: E402

SEG = RAIZ / "seguimiento/claude_ruta"
cfg = json.loads((RAIZ / "tmp/ruta201/configuracion09c.json").read_text(encoding="utf-8"))
geo = gg.consultar_version(RAIZ / "data/private", cfg["caso"], cfg["geometria_origen"]["version_id"]).geometria
V = {v["id"]: (v["x"], v["y"], v["z"]) for v in geo["vertices"]}
NIV = [2.6, 5.2, 7.8, 10.4]
mat = {m["id"]: m for m in cfg["materiales"]}
sec = {s["id"]: s for s in cfg["secciones"]}
asig = {a["objetivo"]: a["seccion"] for a in cfg["asignaciones_superficies"]}


def area(pts):
    import itertools
    # área de un polígono plano 3D por producto vectorial
    o = pts[0]
    sx = sy = sz = 0.0
    for a, b in zip(pts[1:], pts[2:]):
        u = [a[i] - o[i] for i in range(3)]
        w = [b[i] - o[i] for i in range(3)]
        sx += u[1] * w[2] - u[2] * w[1]; sy += u[2] * w[0] - u[0] * w[2]; sz += u[0] * w[1] - u[1] * w[0]
    return 0.5 * (sx * sx + sy * sy + sz * sz) ** 0.5


peso = {z: 0.0 for z in NIV}
detalle = {z: {"vertical_kN": 0.0, "losa_kN": 0.0, "tanque_kN": 0.0} for z in NIV}
tanque_concreto = 0.0
for s in geo["superficies"]:
    pts = [V[v] for v in s["vertices"]]
    sc = sec[asig[s["id"]]]
    w = area(pts) * sc["dimensiones"]["espesor_m"] * mat[sc["material"]]["peso_kN_m3"]
    zs = [p[2] for p in pts]
    if s["id"].startswith("TAN-"):
        tanque_concreto += w
        continue
    if s["id"].startswith(("CIS-", "PL10-")) or max(zs) - min(zs) < 1e-9:   # cisterna/cercos: a su base; losas: membrana sin peso
        continue
    zi, zf = min(zs), max(zs)
    for z in NIV:
        if abs(z - zi) < 1e-9 or abs(z - zf) < 1e-9:
            peso[z] += w / 2; detalle[z]["vertical_kN"] += w / 2
frames = {f["id"]: f for f in cfg["frames"]}
fsec = {a["objetivo"]: a["seccion"] for a in cfg["asignaciones_frames"]}
for fid, f in frames.items():
    a, b = V[f["inicio"]], V[f["fin"]]
    d = sec[fsec[fid]]["dimensiones"]
    ar = (2 * d["alto_m"] * d["espesor_ala_m"] - d["espesor_ala_m"] ** 2) if "espesor_ala_m" in d else d["ancho_m"] * d["alto_m"]
    w = ar * ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5 * mat[sec[fsec[fid]]["material"]]["peso_kN_m3"]
    if f["id"].startswith("COL-NACE"):
        tanque_concreto += w
        continue
    for z in NIV:
        for p in (a, b):
            if abs(p[2] - z) < 1e-9:
                peso[z] += w / 2; detalle[z]["vertical_kN"] += w / 2
FCV = e030.fraccion_carga_viva("C")["fraccion"]
cargas = {}
for c in cfg["cargas"]:
    cargas.setdefault(c["objetivo"], {})[c["patron"]] = -c["componentes"][2]
for sid, q in cargas.items():
    s = next(x for x in geo["superficies"] if x["id"] == sid)
    pts = [V[v] for v in s["vertices"]]
    w = area(pts) * (q.get("D", 0) + FCV * q.get("L", 0))
    peso[pts[0][2]] += w; detalle[pts[0][2]]["losa_kN"] += w
agua_tanque = 10.0 * (13.748 - 11.335 - 0.20) * (5.018 - 3.118 - 0.20) * 1.10   # interior neto × 1,10 m (escenario)
variantes = {"tanque_vacio": 0.0, "tanque_1.10m": agua_tanque * e030.fraccion_carga_viva("tanque")["fraccion"]}
alturas = NIV
salida = {"caso": cfg["caso"], "configuracion_sha256": hashlib.sha256((RAIZ / "tmp/ruta201/configuracion09c.json").read_bytes()).hexdigest(),
          "estado": "escenarios_hipoteticos_no_aprobados", "advertencia": "SIN EMS: ningún perfil es suelo real; Ia = Ip = 1 es hipótesis.",
          "pesos_por_nivel_kN": {}, "escenarios": [], "referencia_L0001_norma_2003": "Z 0,40; U 1,0; S 1,0 (Tp 0,4); Rx = Ry = 6; C 2,5 → V = 0,166 P"}
for nombre, extra in variantes.items():
    pesos = [peso[z] + (tanque_concreto + extra if z == 10.4 else 0) for z in NIV]
    salida["pesos_por_nivel_kN"][nombre] = {"N1": round(pesos[0], 1), "N2": round(pesos[1], 1), "N3": round(pesos[2], 1), "N4": round(pesos[3], 1),
                                            "total": round(sum(pesos), 1)}
    P = sum(pesos)
    z = e030.factor_zona(4)["Z"]; u = e030.factor_uso("C")["U"]
    for perfil in ("S1", "S2", "S3"):
        sitio = e030.parametros_sitio(4, perfil)
        for sistema, ct in (("albanileria_armada_o_confinada", "albanileria_o_muros"), ("concreto_muros_estructurales", "albanileria_o_muros")):
            r = e030.coeficiente_r(sistema, 1.0, 1.0)
            t = e030.periodo_aproximado(10.4, ct)["T_s"]
            v = e030.cortante_basal_estatico(Z=z, U=u, S=sitio["S"], R=r["R"], T=t, TP=sitio["TP"], TL=sitio["TL"], P_kN=P)
            dist = e030.distribucion_altura(v["V_kN"], pesos, alturas, t)
            salida["escenarios"].append({"id": f"{perfil}-{'ALB' if sistema.startswith('alb') else 'MUR'}-{nombre}", "perfil_hipotesis": perfil,
                                         "sistema_hipotesis": sistema, "Ia": 1.0, "Ip": 1.0, "Z": z, "U": u, "S": sitio["S"], "TP": sitio["TP"],
                                         "TL": sitio["TL"], "metodo_sitio": sitio["metodo"], "R": r["R"], "T_aprox_s": round(t, 4),
                                         "C": v["C"], "ZUCS_R": round(z * u * v["C"] * sitio["S"] / r["R"], 4), "P_kN": round(P, 1),
                                         "V_kN": round(v["V_kN"], 1), "F_kN_por_nivel": [round(f, 1) for f in dist["F_kN"]],
                                         "variante_tanque": nombre})
salida["tanque_concreto_kN"] = round(tanque_concreto, 1)
salida["agua_tanque_escenario_kN"] = round(agua_tanque, 1)
salida["detalle_por_nivel_kN"] = {str(z): {k: round(v, 1) for k, v in d.items()} for z, d in detalle.items()}
(SEG / "ESCENARIOS_SISMICOS_09.json").write_text(json.dumps(salida, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print("pesos", salida["pesos_por_nivel_kN"])
for e in salida["escenarios"]:
    if e["variante_tanque"] == "tanque_1.10m":
        print(e["id"], "S", e["S"], "R", e["R"], "ZUCS/R", e["ZUCS_R"], "V", e["V_kN"])
