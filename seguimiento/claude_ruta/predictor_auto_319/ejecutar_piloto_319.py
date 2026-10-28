"""319: candidato sobre el plan del piloto con configuración VERIFICADA por Codex en copia (tmp/configuracion_318_reparacion/registro.json).
El predictor recibe solo plan + config; el recibo se cita como procedencia, no como entrada. Exposición previa declarada (no ciego)."""
import hashlib, json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from predictor_auto_319 import predecir
RAIZ = Path(__file__).resolve().parents[3]
PLAN = RAIZ / "data/private/pueblo-libre-002/modelos_construidos/0f37271307b6449c89c458c60a1640c7/plan.json"
REC = RAIZ / "tmp/configuracion_318_reparacion/registro.json"
CFG = {"etabs_version": "21.1.0", "unidades": "kN_m_C", "tolerancia_union_m": 0.001, "procedencia_tolerancia": "configuracion_verificada", "vigas": None,
       "referencia_configuracion": {"ruta": str(REC.relative_to(RAIZ)), "sha256": hashlib.sha256(REC.read_bytes()).hexdigest(),
                                    "nota": "GetMergeTol 0,001 m, versión 21.1.0, en copia del EDB analizado 42371308… (Codex 318)"}}
out = predecir(json.loads(PLAN.read_text(encoding="utf-8")), CFG)
out["plan"] = {"ruta": str(PLAN.relative_to(RAIZ)), "sha256": hashlib.sha256(PLAN.read_bytes()).hexdigest()}
Path(sys.argv[1]).write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
print(out["estado"], out["cobertura"], out["totales"], out["bloqueo_totales"], len(out["problemas_plan"]))
