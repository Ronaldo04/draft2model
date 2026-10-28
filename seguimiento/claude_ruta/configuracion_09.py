"""Borrador de configuración 0.5 del caso real (encargo 09, paso 3–4) con la normativa vigente integrada.

Ejecutar desde la raíz: python seguimiento/claude_ruta/configuracion_09.py
Salida: tmp/ruta201/configuracion09.json + informe (normativa aplicada, faltantes, comprobación del contrato).
Usa `plantilla_configuracion.borrador` y `configuracion_normativa.aplicar`; no aprueba ni inventa datos.
"""
import hashlib
import json
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ))
from draft2model import configuracion_normativa as cn  # noqa: E402
from draft2model import modelo_estructural as m  # noqa: E402
from draft2model import plantilla_configuracion as pc  # noqa: E402

CASO, GEO = "pueblo-libre-002", "8b39dd52d4d448e5acfe64aa8ec05a2d"
ORIG = RAIZ / "data/private/pueblo-libre-002/originales"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

cfg = pc.borrador(RAIZ / "data/private", CASO, GEO, version_contrato=m.VERSION_LIQUIDOS)
cfg["fuentes"] += [
    {"id": "F-L0001-ESPEC", "descripcion": "Especificaciones técnicas de L0001 (f'c 210, fy 4200, f'm 35 kgf/cm²). Lecturas O3.C030/C031/C035 "
                                           "de la extracción 442b5d4d, PENDIENTES de revisión.", "referencia": "L0001 · especificaciones técnicas",
     "sha256": sha(ORIG / "lamina-0001.pdf")},
    {"id": "F-L0001-ROTULO", "descripcion": "Rótulo: «EDIFICIO MULTIFAMILIAR», ubicación Calle Río Tambo 125, Pueblo Libre.",
     "referencia": "L0001 · rótulo", "sha256": sha(ORIG / "lamina-0001.pdf")},
]
# Plantilla propia del caso: EDB vacío creado en instancia ETABS propia (scripts/crear_plantilla_etabs_caso.ps1), no la sintética.
PLANTILLAS = RAIZ / "data/private/pueblo-libre-002/plantillas"
registro_plantilla = json.loads((PLANTILLAS / "creacion_plantilla.json").read_text(encoding="utf-8-sig"))
edb = PLANTILLAS / "plantilla_vacia_caso.EDB"
assert registro_plantilla["status"] == "created" and not registro_plantilla["synthetic_test"]
assert registro_plantilla["case_id"] == CASO and sha(edb) == registro_plantilla["sha256"], "plantilla alterada"
cfg["fuentes"].append({"id": "F-PLANTILLA-CASO", "referencia": "data/private/pueblo-libre-002/plantillas/creacion_plantilla.json",
                       "descripcion": f"EDB vacío del caso: ETABS {registro_plantilla['version']}, InitializeNewModel(kN_m_C) + "
                                      f"File.NewBlank en instancia propia PID {registro_plantilla['process_id']} (cerrada); sin análisis.",
                       "sha256": registro_plantilla["sha256"]})
cfg["plantilla"] = {
    "id": "PLANTILLA-PUEBLO-LIBRE-002", "version": registro_plantilla["version"], "sha256": registro_plantilla["sha256"],
    "representacion": "Modelo lineal elástico ETABS: muros y placas como shell, columnas y vigas como frame, losas como shell "
                      "(idealización por sección), diafragmas y masa según la configuración.",
    "limitaciones": [
        "La albañilería confinada se representa como shell lineal isótropo (Em, Gm = 0,4 Em); no modela agrietamiento, "
        "interacción con confinamiento ni resistencia a corte (E.070 se verifica fuera del modelo).",
        "Plantilla vacía: no contiene geometría, cargas ni definiciones; todo lo aporta el plan revisable.",
        "Sin análisis ni comprobación de derivas, cortantes o diseño; no declara cumplimiento normativo.",
    ],
    "fuente": "F-PLANTILLA-CASO",
}
decisiones = {
    "materiales": [
        {"id": "CONCRETO-FC210", "clase": "concreto", "resistencia": 210, "unidad": "kgf/cm2", "fuente": "F-L0001-ESPEC"},
        {"id": "ALBANILERIA-FM35", "clase": "albanileria", "resistencia": 35, "unidad": "kgf/cm2", "fuente": "F-L0001-ESPEC"},
    ],
    "zona": {"valor": 4, "estado": "lectura_expediente", "fuente": "F-L0001-ROTULO"},       # Pueblo Libre, provincia de Lima → zona 4
    "categoria": {"valor": "C", "estado": "lectura_expediente", "fuente": "F-L0001-ROTULO"},  # vivienda multifamiliar
}
nuevo, informe = cn.aplicar(cfg, decisiones)
nuevo["liquidos"] = {"aplicabilidad": "informacion_insuficiente", "fuente": "F-L0001-ESPEC",
                     "motivo": "Cisterna (L0001/L0003, NFC −2.65) y tanque elevado (L0003/L0006, NTT +14.60) EXISTEN; falta el nivel libre "
                               "de operación y su geometría/apoyos en el modelo. No se asume ausencia ni se crea agua ficticia.",
                     "declaraciones": []}
resultado = m.validar_configuracion(nuevo)
salida = RAIZ / "tmp/ruta201/configuracion09.json"
salida.write_text(json.dumps(nuevo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
inf = {"configuracion": salida.relative_to(RAIZ).as_posix(), "sha256": sha(salida), "geometria": GEO,
       "normativa": informe, "contrato_consistente": resultado.consistente,
       "errores_contrato": [str(e) for e in resultado.errores][:60], "faltantes_declarados": len(nuevo["faltantes"]),
       "aprobacion_ingenieria": None}
(RAIZ / "seguimiento/claude_ruta/CONFIGURACION_CASO_09.json").write_text(json.dumps(inf, ensure_ascii=False, indent=2, default=str) + "\n",
                                                                       encoding="utf-8")
print("consistente:", resultado.consistente, "| errores:", len(resultado.errores), "| faltantes:", len(nuevo["faltantes"]),
      "| materiales:", [x["id"] for x in nuevo["materiales"]], "| espectros:", len(nuevo["espectros"]))
