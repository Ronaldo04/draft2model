"""Borrador trazable del caso pueblo-libre-002 (encargo 08). Reproducible: usa solo módulos del producto.

Ejecutar desde la raíz: python seguimiento/claude_ruta/borrador_caso_08.py
Escribe seguimiento/claude_ruta/BORRADOR_CASO_08.json. No aprueba nada: separa leído / derivado / hipótesis / decisión.
"""
import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from draft2model import calibracion_ejes as ce  # noqa: E402
from draft2model import normativa_e030 as e030  # noqa: E402
from draft2model import normativa_rne as rne  # noqa: E402

O = RAIZ / "data/private/pueblo-libre-002/originales"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
L = {f"L000{i}": O / f"lamina-000{i}.pdf" for i in range(1, 7)}

# 1. Calibración de arquitectura por cadenas impresas y registro de la estructura.
ax = ce.ejes_desde_texto(L["L0004"], 1, list("12345678"), "y")
ay = ce.ejes_desde_texto(L["L0004"], 1, list("ABCDE"), "x", fijar={"B": 1118.4})
cx, cy = ce.calibrar_cadena(L["L0004"], 1, ax), ce.calibrar_cadena(L["L0004"], 1, ay)
sx = ce.ejes_desde_texto(L["L0001"], 1, list("ABCDEFGHI"), "x")
sy = ce.ejes_desde_texto(L["L0001"], 1, list("123"), "y", fijar={"2": 656.5})
rx = ce.registrar(ax, cx["k_m_por_pt"], sx, {"A": "8", "B": "7", "C": "6", "H": "2", "I": "1"}, origen_a="8")
ry = ce.registrar(ay, cy["k_m_por_pt"], sy, {"3": "A", "2": "C", "1": "E"}, origen_a="A")
corresp = {"A": "8", "B": "7", "C": "6", "H": "2", "I": "1"}
ejes_x = {e: {"x_m": round(v, 3), "estado": "registrado_con_eje_arquitectonico" if e in corresp else "derivado_sin_cota_impresa",
              **({"eje_arquitectura": corresp[e]} if e in corresp else {})} for e, v in rx["posiciones_b_m"].items()}
ejes_y = {e: {"y_m": round(abs(v), 3), "estado": "registrado_con_eje_arquitectonico", "eje_arquitectura": {"3": "A", "2": "C", "1": "E"}[e]}
          for e, v in ry["posiciones_b_m"].items()}

# 2. Niveles.
niveles = [
    {"id": "N0", "z_m": 0.00, "estado": "leido", "fuente": "L0004 «N.P.T. ±0.00» (planta primer piso)"},
    {"id": "N1", "z_m": 2.60, "estado": "leido", "fuente": "L0005 «N.P.T. +2.60» (planta típica 2.º–4.º)"},
    {"id": "N2", "z_m": 5.20, "estado": "hipotesis_progresion_uniforme",
     "fuente": "2,60 m por piso: compatible con +2.60 y techo +10.40 impresos; NPT del 3.º no impreso"},
    {"id": "N3", "z_m": 7.80, "estado": "hipotesis_progresion_uniforme", "fuente": "Ídem; NPT del 4.º no impreso"},
    {"id": "N4", "z_m": 10.40, "estado": "leido", "fuente": "L0006 «TECHO N.T.T. +10.40»"},
]
discrepancias = [
    "L0001/L0002: el eje central se rotula «2» a la izquierda y «1» a la derecha; se declaró 2 (posición única coherente).",
    "Eje F de L0003 desplazado ≈0.50 m respecto de L0001 (registro 07); este borrador usa L0001.",
    "Tanque: E-03 indica NT=+10.35 en la base de apoyos; arquitectura NTT techo +10.40 (5 cm: ¿NPT frente a losa?).",
    "Tanque: 10.35 + 2.00 (apoyos) + 2.05 (cuba impresa .20+1.10+.45+.20+.10) = 14.40 frente a NTT +14.60 impreso.",
    "Ejes estructurales D, E, F y G no coinciden con ejes de arquitectura (5.50/8.58/11.63/13.81 frente a 5.55/8.78/10.98): solo derivados.",
]

# 3. Criterios normativos aplicados (cálculo reproducible con cita); entradas declaradas en «hipotesis».
fc = rne.modulo_concreto(210, "kgf/cm2")
fc175 = rne.modulo_concreto(175, "kgf/cm2")
em_arcilla = rne.modulo_albanileria(35, "kgf/cm2", "arcilla")
sitio = {p: e030.parametros_sitio(4, p) for p in ("S1", "S2")}
T = e030.periodo_aproximado(10.40, "albanileria_o_muros")
R = e030.coeficiente_r("albanileria_armada_o_confinada", 1.0, 1.0)
cortantes = {p: e030.cortante_basal_estatico(Z=0.45, U=1.0, S=s["S"], R=R["R"], T=T["T_s"], TP=s["TP"], TL=s["TL"], P_kN=1.0)
             for p, s in sitio.items()}
espectros = {p: e030.espectro(Z=0.45, U=1.0, S=s["S"], R=R["R"], TP=s["TP"], TL=s["TL"],
                               periodos=[0.0, 0.05, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0, 1.5, 2.0, 2.5, 3.0])
             for p, s in sitio.items()}
normativa = {
    "Z": e030.factor_zona(4), "U": e030.factor_uso("C"), "sitio_alternativas": sitio,
    "periodo_aproximado": T, "R_si_albanileria_confinada_regular": R,
    "coeficiente_cortante_V_sobre_P": {p: round(c["V_kN"], 4) for p, c in cortantes.items()},
    "deriva": e030.deriva_admisible("albanileria", regular=True, R=R["R"]),
    "cortante_minimo_dinamico": e030.cortante_minimo(regular=True),
    "excentricidad_x_y_m": [e030.excentricidad_accidental(10.0)["e_m"], e030.excentricidad_accidental(20.0)["e_m"]],
    "peso_sismico": {"carga_viva_categoria_C": e030.fraccion_carga_viva("C"), "azotea": e030.fraccion_carga_viva("azotea"),
                     "tanque_contenido": e030.fraccion_carga_viva("tanque")},
    "espectros_m_s2": espectros,
    "materiales": {"concreto_fc210": fc, "concreto_fc175_muros_cortes_2_2_5_5": fc175,
                   "albanileria_fm35_si_unidad_de_arcilla": em_arcilla,
                   "pesos": {m: rne.peso_especifico(m) for m in ("concreto_armado", "agua_dulce")}},
    "cargas_vivas": {"vivienda": rne.carga_viva("vivienda"), "corredores_escaleras": rne.carga_viva("vivienda_corredores_escaleras"),
                     "techo_hasta_3_grados": rne.carga_viva("techo_pendiente_hasta_3")},
    "estado": "calculado con cita; aplica solo si se aceptan las decisiones marcadas; no es verificación de cumplimiento",
}

# 4. Elementos sustentados (lecturas pendientes de revisión en la extracción 442b5d4d del caso).
elementos = {
    "columnas_cuadro": {"C-1": "L .40x.40, patas .15 (detalle)", "C-2": ".15x.40", "C-3": ".15x.60", "C-4": ".15x.40",
                        "C-5": ".15x.30", "C-6": ".15x.75", "fuente": "L0001 cuadro de columnas (O3/G1, pendientes)"},
    "placas": "PL-1…PL-10 con armado en tabla; longitudes en planta sin cota: derivables con la calibración registrada",
    "vigas": "VS 0.15x0.30 (chatas) y cortes 1-1…6-6 de L0002",
    "losas": {"aligerado_e_m": 0.17, "niveles": "1.º a 3.º S/C 200 kgf/m²; 4.º nivel (techo +10.40) S/C 150 kgf/m²",
              "detalle": "capa .05, ladrillo .12, viguetas .10 @ .40 (L0003)"},
    "parapetos": "H = 0.90 en techo (L0006, leído)",
    "tanque_elevado": "existe: corte L0003 y planta L0006", "cisterna": "existe: L0001/L0003, NFC −2.65",
    "posiciones_columnas": "detección vectorial parcial (8 rectángulos .15x.40 y 1 de .15x.60 en L0001); pendiente",
}

decisiones = [
    {"id": "D1", "tema": "Sistema estructural y R0", "opciones": "albañilería confinada (R0=3, deriva 0,005) u otro", "derivable_con_norma": False,
     "por_que": "Clasificar el sistema es decisión técnica (E.030 art. 20–22; E.070 24.6)."},
    {"id": "D2", "tema": "Perfil de suelo", "opciones": "S1 (S=1,0; TP=0,4; TL=2,5) o S2 sin Vs30 (S=1,10; TP=0,6; TL=2,0)",
     "derivable_con_norma": False, "por_que": "E.030 art. 16 y E.050 6.2.1.c exigen EMS para ≥4 pisos; el plano declara GP y σt=4,00 kgf/cm²."},
    {"id": "D3", "tema": "Unidad de albañilería", "opciones": "arcilla (Em=500 f'm) u otra", "derivable_con_norma": True,
     "por_que": "E.070 24.7 fija Em según la unidad; «King-Kong a máquina» no se clasifica por nombre comercial."},
    {"id": "D4", "tema": "Alturas de los pisos 3.º y 4.º", "opciones": "aceptar 2,60 uniforme o aportar NPT", "derivable_con_norma": False,
     "por_que": "Solo constan ±0.00, +2.60 y techo +10.40."},
    {"id": "D5", "tema": "Orientación Y entre láminas", "opciones": "estructural 3↔A (declarado) o 3↔E", "derivable_con_norma": False,
     "por_que": "Edificio casi simétrico; afecta ubicación de escalera, cisterna y tanque."},
    {"id": "D6", "tema": "Cargas muertas no impresas (acabados, tabiquería)", "opciones": "metrado con fuente", "derivable_con_norma": True,
     "por_que": "E.020 arts. 3–6 y anexo 1: peso real documentado."},
    {"id": "D7", "tema": "Agua: nivel de operación de tanque y cisterna", "opciones": "nivel libre declarado; masa 100 % del contenido (E.030 art. 31.e)",
     "derivable_con_norma": "parcial", "por_que": "γ = 10 kN/m³ (E.020) y la fracción sísmica constan; el nivel libre no está impreso."},
    {"id": "D8", "tema": "Condición de apoyo", "opciones": "empotramiento a NFC −1.50 (E.030 48.6 lo permite) u otra", "derivable_con_norma": False,
     "por_que": "Idealización de la base: decisión técnica con el EMS."},
    {"id": "D9", "tema": "Irregularidades Ia/Ip", "opciones": "evaluar con el modelo (Tablas 11–12)", "derivable_con_norma": True,
     "por_que": "Requiere resultados del modelo; hasta entonces R se informa con Ia = Ip = 1 como hipótesis."},
]

salida = {
    "caso": "pueblo-libre-002", "fecha": "2026-10-21", "aprobacion_ingenieria": None,
    "originales": {k: {"archivo": p.name, "sha256": sha(p)} for k, p in L.items()},
    "calibracion": {"arquitectura_x": cx, "arquitectura_y": cy, "estructura_x": rx, "estructura_y": ry,
                    "declaraciones": {"L0004 eje B": "1118.4 pt (globo de eje; 1064.8 es el corte B–B; cota 3.15 centrada en A–B)",
                                      "L0001 eje 2": "656.5 pt (único globo «2»; el derecho dice «1»)"}},
    "ejes_estructurales": {"x": ejes_x, "y": ejes_y}, "niveles": niveles, "discrepancias": discrepancias,
    "elementos": elementos, "normativa": normativa, "decisiones_restantes": decisiones,
    "resueltos_con_arquitectura": ["F1 parcial: NPT ±0.00/+2.60 y techo +10.40 leídos (3.º/4.º derivados)",
                                   "F2: cotas entre ejes impresas en arquitectura; registro estructural con residuo ≤ 9 mm",
                                   "F3: el «4.º nivel» estructural es el techo (+10.40, S/C 150 = azotea)",
                                   "F4: decisión del usuario: RNE vigente (E.030 RM 183-2026)"],
}
destino = RAIZ / "seguimiento/claude_ruta/BORRADOR_CASO_08.json"
destino.write_text(json.dumps(salida, ensure_ascii=False, indent=2, default=float) + "\n", encoding="utf-8")
print(destino.relative_to(RAIZ), "| k_arq_x", round(cx["k_m_por_pt"], 6), "res", round(cx["residuo_max_m"], 4),
      "| registro x res", round(rx["residuo_max_m"], 4), "| V/P", normativa["coeficiente_cortante_V_sobre_P"])
