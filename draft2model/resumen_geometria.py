"""Resumen geométrico compartido por informe y panel (hallazgo Codex 283).

En las geometrías por superficies (contratos 0.2/0.3) los muros y placas son SUPERFICIES con papel declarado y la lista de muros
lineales del contrato 0.1 queda vacía: contar `muros` daba «Muros 0». Este resumen informa la representación y las superficies
por papel declarado (piezas de modelación, NO muros físicos contados) y separa niveles de piso (base incluida) de las cotas
auxiliares, que no son Story de ETABS. No infiere cantidades físicas no declaradas. Para el contrato 0.1 devuelve None y los
consumidores conservan su forma anterior.
"""
from __future__ import annotations

from collections import Counter
from typing import Any

NOTA = ("Superficies por papel declarado en la geometría: piezas de modelación (fragmentos de malla conforme), no un recuento de muros "
        "físicos. Niveles de piso incluyen la base; las cotas auxiliares no son pisos ni Story de ETABS.")


def resumen_geometria(datos: dict | None) -> dict[str, Any] | None:
    if not isinstance(datos, dict) or not isinstance(datos.get("superficies"), list):
        return None
    papeles = Counter(s.get("papel_geometrico") or "sin papel declarado" for s in datos["superficies"])
    niveles = sorted(datos.get("niveles") or [], key=lambda n: (n.get("cota") is None, n.get("cota")))
    pisos = [n["id"] for n in niveles if n.get("tipo", "piso") == "piso"]
    auxiliares = [n["id"] for n in niveles if n.get("tipo") == "auxiliar"]
    return {"representacion": "superficies", "version_contrato": datos.get("version_contrato"),
            "muros_lineales": len(datos.get("muros") or []), "superficies": len(datos["superficies"]),
            "superficies_por_papel": dict(sorted(papeles.items())),
            "niveles_piso": pisos, "base": pisos[0] if pisos else None, "pisos_sobre_base": max(len(pisos) - 1, 0),
            "niveles_auxiliares": auxiliares, "nota": NOTA}


def texto_resumen(r: dict[str, Any]) -> str:
    papeles = " · ".join(f"{k}: {v}" for k, v in r["superficies_por_papel"].items())
    return (f"Representación por superficies (contrato {r['version_contrato']}): {r['superficies']} superficies; por papel declarado: "
            f"{papeles}. Muros lineales del contrato 0.1: {r['muros_lineales']}. Niveles de piso: {len(r['niveles_piso'])} "
            f"(base {r['base']} + {r['pisos_sobre_base']} pisos: {', '.join(r['niveles_piso'])}); cotas auxiliares: "
            f"{len(r['niveles_auxiliares'])} ({', '.join(r['niveles_auxiliares']) or 'ninguna'}). {r['nota']}")
