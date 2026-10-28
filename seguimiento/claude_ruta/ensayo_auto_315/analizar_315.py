"""315: contraste posterior del registro nativo sintético contra MATRIZ_PREVIA_315.json (sellada antes de ejecutar).
Separa observación nativa (API GetEndLengthOffset y tabla) de hipótesis. Uso: python analizar_315.py REGISTRO MATRIZ SALIDA
"""
import json, math, sys

TOL = 0.0005


def tabla_filas(t):
    campos, datos = t.get("campos") or [], t.get("datos") or []
    n = len(campos)
    return [dict(zip(campos, datos[i:i + n])) for i in range(0, len(datos), n)] if n else []


def main(reg_path, matriz_path, salida):
    reg = json.load(open(reg_path, encoding="utf-8-sig")); mat = json.load(open(matriz_path, encoding="utf-8"))
    casos = {c["id"]: c for c in mat["modelo_A"]["casos"]}
    out = {"tarea": "auto_315_contraste", "ensayo_ciego": False, "tolerancia_m": TOL, "error_registro": reg.get("error"), "cierre": reg.get("cierre"),
           "version_etabs": reg.get("version_etabs"), "modelos": []}
    for fase in reg.get("fases", []):
        m = fase["modelo"]; info = fase["construccion"]; vigas = info["vigas"]
        res = {"modelo": m, "tolerancia_por_defecto": info["tolerancia_por_defecto"], "tolerancia_aplicada": info["tolerancia_aplicada"],
               "unidades": fase.get("unidades"), "retorno_analisis": fase.get("retorno_analisis"), "casos": []}
        for etapa in ("antes_analisis", "despues_analisis"):
            filas_t = {f.get("UniqueName") or f.get("Label"): f for f in tabla_filas(fase[etapa]["tabla"])}
            res.setdefault("tabla_campos", fase[etapa]["tabla"].get("campos")); res.setdefault("tabla_retorno_" + etapa, fase[etapa]["tabla"].get("retorno"))
            for k, nombre in vigas.items():
                a = fase[etapa]["api"][nombre]; L = math.dist(a["coord_i"], a["coord_j"])
                row = next((c for c in res["casos"] if c["id"] == k), None)
                if row is None:
                    row = {"id": k, "frame": nombre, "L_m": round(L, 6), "pred": casos[k]["pred"], "discrimina": casos[k].get("discrimina")}; res["casos"].append(row)
                obs = {"auto": a["auto"], "I": a["Length1"], "J": a["Length2"], "retorno": a["retorno"], "Lc_m": round(L - a["Length1"] - a["Length2"], 6)}
                t = filas_t.get(nombre)
                if t:
                    obs["tabla"] = {kk: t[kk] for kk in t if kk in ("OffsetI", "OffsetJ", "OffsetOpt", "SelfWtOpt", "RigidFact")}
                row[etapa] = obs
        for row in res["casos"]:
            obs = row.get("despues_analisis") or row.get("antes_analisis")
            ev = {}
            for h, val in row["pred"].items():
                if any(isinstance(v, str) for v in val):
                    ev[h] = "indeterminado_previo"
                else:
                    ev[h] = "coincide" if abs(val[0] - obs["I"]) <= TOL and abs(val[1] - obs["J"]) <= TOL else "no_coincide"
            row["evaluacion"] = ev
            row["cambio_por_analisis"] = (row.get("antes_analisis", {}).get("I"), row.get("antes_analisis", {}).get("J")) != (obs["I"], obs["J"])
        out["modelos"].append(res)
    json.dump(out, open(salida, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for res in out["modelos"]:
        print("modelo", res["modelo"], "tol", res["tolerancia_aplicada"], "analisis", res["retorno_analisis"], res["unidades"])
        for c in res["casos"]:
            o = c.get("despues_analisis") or {}
            print(f'  {c["id"]} L={c["L_m"]} auto={o.get("auto")} I={o.get("I")} J={o.get("J")} Lc={o.get("Lc_m")} cambio={c["cambio_por_analisis"]} {c["evaluacion"]} tabla={o.get("tabla")}')


if __name__ == "__main__":
    main(*sys.argv[1:4])
