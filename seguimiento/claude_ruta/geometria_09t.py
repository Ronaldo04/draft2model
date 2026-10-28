"""Variante de TRANSPORTE de la geometría 09C (autorización del usuario: aprobación declarada SOLO de transporte de software).

Ejecutar desde la raíz: python seguimiento/claude_ruta/geometria_09t.py
Toma tmp/ruta201/geometria09c/geometria.json (versión 3905c919, que CONSERVA sus 6 faltantes) y escribe
tmp/ruta201/geometria09t/geometria.json con la MISMA geometría y los faltantes convertidos en hipótesis declaradas del
escenario de transporte (procedencia raíz). No cambia vértices ni superficies: la escalera sigue sin modelar y su peso entra
como carga en la configuración de transporte. La versión 3905c919 sigue siendo la referencia honesta del caso.
"""
import copy
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
FUENTE = sys.argv[1] if len(sys.argv) > 1 else "geometria09c"   # carpeta de tmp/ruta201 (09c por defecto, 09d desde la tarea 253)
origen = json.loads((RAIZ / "tmp/ruta201" / FUENTE / "geometria.json").read_text(encoding="utf-8"))
g = copy.deepcopy(origen)
hipotesis = [f["descripcion"] for f in origen["faltantes"]]
g["faltantes"] = []
g["procedencia"]["justificacion"] = (
    "ESCENARIO DE TRANSPORTE (aprobación declarada solo de software, autorizada por el usuario; NO ingeniería). Geometría idéntica a la "
    f"de {FUENTE}; sus faltantes pasan a hipótesis declaradas de este escenario: " + " | ".join(hipotesis))
g["procedencia"]["descripcion"] = f"Variante de transporte de {FUENTE} (misma geometría; faltantes como hipótesis declaradas)."
salida = RAIZ / "tmp/ruta201" / (FUENTE.replace("geometria", "geometria_t_"))
salida.mkdir(parents=True, exist_ok=True)
(salida / "geometria.json").write_text(json.dumps(g, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
assert g["vertices"] == origen["vertices"] and g["superficies"] == origen["superficies"]
print("hipótesis de transporte:", len(hipotesis))
