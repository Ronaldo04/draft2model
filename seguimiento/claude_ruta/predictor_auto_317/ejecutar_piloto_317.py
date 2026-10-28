"""317: ejecuta el candidato sobre el plan del piloto con ESCENARIO DECLARADO de tolerancia (no configuración nativa verificada).
Exposición previa declarada: 313/314/315/316 ya conocidos. Uso: python ejecutar_piloto_317.py SALIDA.json"""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from predictor_auto_317 import predecir
RAIZ = Path(__file__).resolve().parents[3]
PLAN = RAIZ / "data/private/pueblo-libre-002/modelos_construidos/0f37271307b6449c89c458c60a1640c7/plan.json"
CFG = {"etabs_version": "21.1.0", "unidades": "kN_m_C", "tolerancia_union_m": 0.001, "procedencia_tolerancia": "escenario_declarado", "vigas": None,
       "nota": "El plan no declara SetMergeTol; 0,001 m es el valor por defecto observado en modelo nuevo (315). Codex verificará la configuración real del piloto/plantilla."}
plan = json.loads(PLAN.read_text(encoding="utf-8"))
assert plan["unidades_etabs"] == CFG["unidades"]
out = predecir(plan, CFG); out["plan"] = {"ruta": str(PLAN.relative_to(RAIZ)), "sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest()}
Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(out["estado"], out["cobertura"], out["totales"])
