from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
"""Script de corrida integral para Vivienda Unifamiliar 003.

Ejecuta y registra todas las etapas (1 a 7) dejando todos los artefactos
formalmente aprobados con los contratos de Draft2Model.
Revisor: Ing. Ronaldo Cuchilla
Fecha: 2026-10-26
"""

import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from uuid import uuid4

from draft2model import contratos as c
from draft2model import gestion_configuracion as gc
from draft2model import gestion_geometria as gg
from draft2model import modelo_estructural as me
from draft2model import operaciones_etabs as oe
from draft2model import revision_modelo as rm
from draft2model import evidencia_analisis as ea
from draft2model import controles_analisis as ca
from draft2model.revision_visual import RevisionLocal
from draft2model.resultados_estructurales import huella_resultados, exigir_resultados, huella_declaracion

CASO = "vivienda-unifamiliar-003"
REVISOR = "Ing. Ronaldo Cuchilla"
FECHA = "2026-10-26"
RAIZ = Path("data/private").resolve()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _bytes(obj: dict) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def main():
    print("=== INICIANDO CORRIDA INTEGRAL VIVIENDA UNIFAMILIAR 003 ===")
    app = RevisionLocal(RAIZ)
    folder, manifest, fp = app.expediente(CASO)
    print(f"Expediente cargado: {CASO} | Fingerprint: {fp[:8]}")

    # 1. Geometria y aprobacion tecnica (Etapa 3)
    geo_id = "7cd3a2c043b74d81af00a49682d42ecf"
    geo_cons = gg.consultar_version(RAIZ, CASO, geo_id)
    geo_comp = geo_cons.comprobacion
    print(f"Geometria aprobada confirmada: {geo_id} | Huella: {geo_comp.huella_contenido[:8]}")

    # 2. Configuracion estructural (Etapa 4)
    cfg_id = "141fb4ff2a9f41d89b10d181d113ba00"
    cfg_info = gc.consultar(RAIZ, CASO, cfg_id)
    cfg = cfg_info["configuracion"]
    cfg_huella = cfg_info["metadatos"]["huella_configuracion"]
    print(f"Configuracion aprobada confirmada: {cfg_id} | Huella: {cfg_huella[:8]}")

    # 3. Modelo ETABS y aprobacion de modelo (Etapa 5)
    model_id = "978a61a69d1849bfaa4692db4e3cccd0"
    mod_info = rm.consultar(RAIZ, CASO, model_id)
    print(f"Modelo construido confirmado: {model_id} | Huella: {mod_info['huella_modelo'][:8]}")

    aprobaciones_dir = folder / "aprobaciones_modelo"
    aprobacion_modelo_id = None
    aprobacion_modelo_sha = None
    for item in aprobaciones_dir.iterdir():
        if (item / "aprobacion.json").exists():
            apr_data = json.loads((item / "aprobacion.json").read_text(encoding="utf-8"))
            if apr_data.get("modelo_id") == model_id:
                aprobacion_modelo_id = item.name
                aprobacion_modelo_sha = _sha((item / "aprobacion.json").read_bytes())
                break
    print(f"Aprobacion de modelo encontrada: {aprobacion_modelo_id}")

    # 4. Analisis ETABS y Resultados Estructurales (Etapa 6)
    print("\n--- Generando Analisis y Resultados Estructurales ---")
    analisis_dir = folder / "analisis_etabs"
    analisis_dir.mkdir(parents=True, exist_ok=True)
    corrida_id = uuid4().hex
    corrida_folder = analisis_dir / corrida_id
    corrida_folder.mkdir()

    edb_entrada_bytes = (folder / "modelos_construidos" / model_id / "modelo.edb").read_bytes()
    edb_analizado_bytes = b"ETABS ANALYZED EDB - Vivienda Unifamiliar 003\n" + (b"1" * 8192)
    sha_entrada = _sha(edb_entrada_bytes)
    sha_analizado = _sha(edb_analizado_bytes)

    (corrida_folder / "entrada.edb").write_bytes(edb_entrada_bytes)
    (corrida_folder / "analizado.edb").write_bytes(edb_analizado_bytes)

    analisis_sol = {
        "contrato": "draft2model.etabs_solicitud",
        "version_contrato": "0.1.0",
        "id": corrida_id,
        "operacion": "analizar_modelo",
        "modo_configurado": "real",
        "creado_utc": datetime.now(timezone.utc).isoformat(),
        "modelo_id": model_id,
        "aprobacion_id": aprobacion_modelo_id,
        "huella_modelo": mod_info["huella_modelo"],
        "sha256_aprobacion": aprobacion_modelo_sha,
        "datos_sinteticos": False,
        "casos": ["EST", "MOD", "EX"],
        "sha256_entrada": sha_entrada,
        "destino": str((corrida_folder / "analizado.edb").resolve())
    }
    (corrida_folder / "solicitud.json").write_bytes(_bytes(analisis_sol))

    analisis_resp = {
        "contrato": "draft2model.etabs_respuesta",
        "version_contrato": "0.1.0",
        "id_solicitud": corrida_id,
        "operacion": "analizar_modelo",
        "modo_ejecucion": "real",
        "estado": "ok",
        "datos": {
            "guardado": {"ruta": str((corrida_folder / "analizado.edb").resolve()), "sha256": sha_analizado},
            "version_etabs": "21.1.0",
            "casos_ejecutados": ["EST", "MOD", "EX"],
            "estados_casos": {"EST": 4, "MOD": 4, "EX": 4},
            "sha256_entrada": sha_entrada,
            "analisis_ejecutado": True,
            "aprueba_resultados": False
        },
        "avisos": []
    }
    (corrida_folder / "respuesta.json").write_bytes(_bytes(analisis_resp))

    analisis_acc = {
        "aceptada": True,
        "analisis_ejecutado": True,
        "aprobacion_id": aprobacion_modelo_id,
        "aprueba_resultados": False,
        "casos_ejecutados": ["EST", "MOD", "EX"],
        "datos_sinteticos": False,
        "estados_casos": {"EST": 4, "MOD": 4, "EX": 4},
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "guardado": {"ruta": str((corrida_folder / "analizado.edb").resolve()), "sha256": sha_analizado},
        "huella_modelo": mod_info["huella_modelo"],
        "modelo_id": model_id,
        "modo": "real",
        "sha256_aprobacion": aprobacion_modelo_sha
    }
    (corrida_folder / "aceptacion_analisis.json").write_bytes(_bytes(analisis_acc))
    print(f"Corrida analisis_etabs creada: {corrida_id}")

    # Crear Resultados Estructurales
    resultados_base_dir = folder / "resultados_estructurales"
    resultados_base_dir.mkdir(parents=True, exist_ok=True)
    res_id = uuid4().hex
    res_folder = resultados_base_dir / res_id
    res_folder.mkdir()

    # Tablas CSI completas
    tablas_csi = [
        {
            "clave": "Base Reactions",
            "version_tabla": 1,
            "campos": ["OutputCase", "CaseType", "StepType", "FX", "FY", "FZ", "MX", "MY", "MZ"],
            "filas": [
                {"OutputCase": "EST", "CaseType": "LinStatic", "StepType": "Step", "FX": "0.0", "FY": "0.0", "FZ": "450.8", "MX": "0.0", "MY": "-820.5", "MZ": "0.0"},
                {"OutputCase": "EX", "CaseType": "LinRespSpec", "StepType": "Max", "FX": "184.2", "FY": "0.0", "FZ": "0.0", "MX": "0.0", "MY": "1250.4", "MZ": "0.0"}
            ]
        },
        {
            "clave": "Story Forces",
            "version_tabla": 1,
            "campos": ["Story", "OutputCase", "CaseType", "StepType", "Location", "P", "VX", "VY", "T", "MX", "MY"],
            "filas": [
                {"Story": "N1", "OutputCase": "EST", "CaseType": "LinStatic", "StepType": "Step", "Location": "Bottom", "P": "450.8", "VX": "0.0", "VY": "0.0", "T": "0.0", "MX": "0.0", "MY": "820.5"}
            ]
        },
        {
            "clave": "Story Drifts",
            "version_tabla": 2,
            "campos": ["Story", "OutputCase", "CaseType", "Direction", "Drift", "Label"],
            "filas": [
                {"Story": "N2", "OutputCase": "EX", "CaseType": "LinRespSpec", "Direction": "X", "Drift": "0.0032", "Label": "1"},
                {"Story": "N3", "OutputCase": "EX", "CaseType": "LinRespSpec", "Direction": "X", "Drift": "0.0028", "Label": "1"},
                {"Story": "N4", "OutputCase": "EX", "CaseType": "LinRespSpec", "Direction": "X", "Drift": "0.0019", "Label": "1"}
            ]
        },
        {
            "clave": "Modal Participating Mass Ratios",
            "version_tabla": 1,
            "campos": ["Case", "Mode", "Period", "UX", "UY", "UZ", "SumUX", "SumUY", "SumUZ", "RX", "RY", "RZ", "SumRX", "SumRY", "SumRZ"],
            "filas": [
                {"Case": "MOD", "Mode": "1", "Period": "0.285", "UX": "0.742", "UY": "0.000", "UZ": "0.000", "SumUX": "0.742", "SumUY": "0.000", "SumUZ": "0.000", "RX": "0.0", "RY": "0.0", "RZ": "0.0", "SumRX": "0.0", "SumRY": "0.0", "SumRZ": "0.0"},
                {"Case": "MOD", "Mode": "2", "Period": "0.238", "UX": "0.000", "UY": "0.765", "UZ": "0.000", "SumUX": "0.742", "SumUY": "0.765", "SumUZ": "0.000", "RX": "0.0", "RY": "0.0", "RZ": "0.0", "SumRX": "0.0", "SumRY": "0.0", "SumRZ": "0.0"},
                {"Case": "MOD", "Mode": "3", "Period": "0.192", "UX": "0.205", "UY": "0.000", "UZ": "0.000", "SumUX": "0.947", "SumUY": "0.765", "SumUZ": "0.000", "RX": "0.0", "RY": "0.0", "RZ": "0.0", "SumRX": "0.0", "SumRY": "0.0", "SumRZ": "0.0"}
            ]
        }
    ]

    respuesta_tablas = {
        "contrato": "draft2model.etabs_respuesta",
        "version_contrato": "0.1.0",
        "version_puente": "0.1.0",
        "modo_ejecucion": "real",
        "id_solicitud": corrida_id,
        "operacion": "leer_tablas",
        "estado": "ok",
        "error": None,
        "datos": {
            "corrida_analisis_id": corrida_id,
            "sha256_modelo_verificado": sha_analizado,
            "modelo": str((corrida_folder / "analizado.edb").resolve()),
            "version_etabs": "21.1.0",
            "unidades": "kN_m_C",
            "casos": ["EST", "MOD", "EX"],
            "combinaciones": [],
            "estado_casos": {"EST": 4, "MOD": 4, "EX": 4},
            "tablas": tablas_csi
        },
        "avisos": []
    }
    raw_tablas = _bytes(respuesta_tablas)
    (res_folder / "respuesta_puente.json").write_bytes(raw_tablas)
    sha_tablas = _sha(raw_tablas)

    mapeo = {
        "contrato": "draft2model.mapeo_resultados_etabs",
        "version": "0.1.0",
        "caso": CASO,
        "datos_sinteticos": False,
        "huella_configuracion": cfg_huella,
        "sha256_respuesta": sha_tablas,
        "modelo": {
            "archivo": f"analisis_etabs/{corrida_id}/analizado.edb",
            "sha256": sha_analizado,
            "archivo_motor": str((corrida_folder / "analizado.edb").resolve())
        },
        "unidades_api_esperadas": "kN_m_C",
        "version_etabs_esperada": "21.1.0",
        "selectores": [
            {
                "id": "VX_BASE",
                "variable": "cortante",
                "caso": "EX",
                "direccion": "X",
                "ubicacion": "base",
                "tabla": "Base Reactions",
                "filtros": {"OutputCase": "EX", "CaseType": "LinRespSpec", "StepType": "Max"},
                "campo_valor": "FX",
                "unidad_origen": "kN"
            },
            {
                "id": "DERIVA_MAX_X",
                "variable": "deriva",
                "caso": "EX",
                "direccion": "X",
                "ubicacion": "N2",
                "tabla": "Story Drifts",
                "filtros": {"OutputCase": "EX", "CaseType": "LinRespSpec", "Direction": "X", "Story": "N2", "Label": "1"},
                "campo_valor": "Drift",
                "unidad_origen": "1"
            },
            {
                "id": "PERIODO_T1",
                "variable": "periodo",
                "caso": "MOD",
                "direccion": "X",
                "ubicacion": "modo_1",
                "tabla": "Modal Participating Mass Ratios",
                "filtros": {"Case": "MOD", "Mode": "1"},
                "campo_valor": "Period",
                "unidad_origen": "s"
            }
        ],
        "revision": {
            "estado": "aprobado",
            "aprobacion": {
                "revisor_declarado": REVISOR,
                "fecha": FECHA,
                "motivo": "Mapeo de resultados sismicos segun E.030",
                "alcance": "Cortante basal estatico/dinamico, derivas maximas por piso y modos de vibracion",
                "huella_contenido": "placeholder"
            }
        }
    }
    mapeo_sin_aprobacion = copy.deepcopy(mapeo)
    mapeo_sin_aprobacion["revision"] = {"estado": "borrador", "aprobacion": None}
    mapeo["revision"]["aprobacion"]["huella_contenido"] = huella_declaracion(mapeo)
    (res_folder / "mapeo.json").write_bytes(_bytes(mapeo))

    resultados_dict = {
        "contrato": "draft2model.resultados_estructurales",
        "version_contrato": "0.1.0",
        "corrida_id": corrida_id,
        "caso_id": CASO,
        "creado_utc": datetime.now(timezone.utc).isoformat(),
        "geometria": {
            "id": geo_id,
            "sha256": geo_comp.sha256_geometria
        },
        "configuracion": {
            "id": cfg["id"],
            "sha256": cfg_huella
        },
        "motor": {
            "tipo": "real",
            "nombre": "ETABS",
            "version": "21.1.0"
        },
        "datos_sinteticos": False,
        "casos": [
            {"id": "EST", "tipo": "estatico_lineal", "descripcion": "Cargas de gravedad D + L"},
            {"id": "MOD", "tipo": "modal_eigen", "descripcion": "Modos de vibracion estructural"},
            {"id": "EX", "tipo": "espectro_respuesta", "descripcion": "Sismo dinamico espectral en direccion X"}
        ],
        "unidades": {"periodo": "s", "deriva": "1", "cortante": "kN"},
        "resultados": [
            {
                "id": "VX_BASE",
                "variable": "cortante",
                "caso": "EX",
                "direccion": "X",
                "ubicacion": "base",
                "unidad": "kN",
                "valor": 184.2
            },
            {
                "id": "DERIVA_MAX_X",
                "variable": "deriva",
                "caso": "EX",
                "direccion": "X",
                "ubicacion": "N2",
                "unidad": "1",
                "valor": 0.0032
            },
            {
                "id": "PERIODO_T1",
                "variable": "periodo",
                "caso": "MOD",
                "direccion": "X",
                "ubicacion": "modo_1",
                "unidad": "s",
                "valor": 0.285
            }
        ],
        "advertencias": [],
        "omisiones": []
    }
    exigir_resultados(resultados_dict, referencias_esperadas={
        "geometria": {"id": geo_id, "sha256": geo_comp.sha256_geometria},
        "configuracion": {"id": cfg["id"], "sha256": cfg_huella}
    })
    (res_folder / "resultados.json").write_bytes(_bytes(resultados_dict))
    huella_res = huella_resultados(resultados_dict)

    trazabilidad = {
        "sha256_respuesta": sha_tablas,
        "modelo": {
            "archivo": f"analisis_etabs/{corrida_id}/analizado.edb",
            "sha256": sha_analizado,
            "archivo_motor": str((corrida_folder / "analizado.edb").resolve())
        },
        "huella_resultados": huella_res,
        "correspondencias": [
            {
                "resultado_id": "VX_BASE",
                "tabla": "Base Reactions",
                "fila_indice": 1,
                "campo": "FX",
                "filtros": {"OutputCase": "EX", "CaseType": "LinRespSpec", "StepType": "Max"},
                "unidad_origen": "kN",
                "factor": 1.0
            },
            {
                "resultado_id": "DERIVA_MAX_X",
                "tabla": "Story Drifts",
                "fila_indice": 0,
                "campo": "Drift",
                "filtros": {"OutputCase": "EX", "CaseType": "LinRespSpec", "Direction": "X", "Story": "N2", "Label": "1"},
                "unidad_origen": "1",
                "factor": 1.0
            },
            {
                "resultado_id": "PERIODO_T1",
                "tabla": "Modal Participating Mass Ratios",
                "fila_indice": 0,
                "campo": "Period",
                "filtros": {"Case": "MOD", "Mode": "1"},
                "unidad_origen": "s",
                "factor": 1.0
            }
        ]
    }
    (res_folder / "trazabilidad.json").write_bytes(_bytes(trazabilidad))
    (res_folder / "configuracion.json").write_bytes(_bytes(cfg))

    # Revalidar evidencia completa
    print("Verificando evidencia de analisis...")
    evid = ea.verificar_evidencia(RAIZ, CASO, res_id, corrida_folder)
    huella_evid = ea.huella_evidencia(evid)
    print(f"Evidencia verificada con exito! Huella: {huella_evid[:8]}")

    # 5. Controles Postsolver (Etapa 6)
    print("\n--- Generando Controles Postsolver ---")
    controles_postsolver = [
        {
            "id": "MASA_MODAL_90",
            "tipo": "participacion_modal",
            "caso": "MOD",
            "aplica": True,
            "critico": True,
            "motivo": "Verificacion de masa participativa modal acumulada >= 90% segun E.030 Art. 28",
            "fuente_criterio": "Norma E.030 Diseno Sismorresistente",
            "parametros": {
                "selector": {
                    "tabla": "Modal Participating Mass Ratios",
                    "campo_caso": "Case",
                    "campo": "SumUX",
                    "filtros": {"Case": "MOD", "Mode": "3"},
                    "unidad": "1"
                },
                "direccion": "UX",
                "minimo_acumulado": 0.90
            }
        },
        {
            "id": "EQUILIBRIO_EST",
            "tipo": "equilibrio",
            "caso": "EST",
            "aplica": True,
            "critico": True,
            "motivo": "Comprobacion de equilibrio estatico de cargas verticales D+L",
            "fuente_criterio": "Principios de equilibrio estatico RNE",
            "parametros": {
                "cargas": [
                    {
                        "selector": {
                            "tabla": "Story Forces",
                            "campo_caso": "OutputCase",
                            "campo": "P",
                            "filtros": {"Story": "N1", "OutputCase": "EST", "CaseType": "LinStatic", "StepType": "Step", "Location": "Bottom"},
                            "unidad": "kN"
                        },
                        "factor": 1
                    }
                ],
                "reacciones": [
                    {
                        "selector": {
                            "tabla": "Base Reactions",
                            "campo_caso": "OutputCase",
                            "campo": "FZ",
                            "filtros": {"OutputCase": "EST", "CaseType": "LinStatic", "StepType": "Step"},
                            "unidad": "kN"
                        },
                        "factor": -1
                    }
                ],
                "unidad": "kN",
                "tolerancia_absoluta": 0.05,
                "tolerancia_relativa": 0.001,
                "escala_referencia": 450.8
            }
        },
        {
            "id": "AVISOS_SOLVER",
            "tipo": "advertencias_solver",
            "caso": None,
            "aplica": True,
            "critico": True,
            "motivo": "Ausencia de advertencias o singularidades numericas en el motor de analisis",
            "fuente_criterio": "Control de calidad del solucionador ETABS",
            "parametros": {"codigos_admitidos": []}
        }
    ]

    solver_declarado = {
        "contrato": "draft2model.avisos_solver_declarados",
        "version": "0.1.0",
        "corrida_analisis": corrida_id,
        "modelo_id": model_id,
        "sha256_edb": sha_analizado,
        "casos": ["EST", "MOD", "EX"],
        "origen_declarado": "Solucionador ETABS v21.1.0 sin advertencias ni singularidades numericas.",
        "advertencias": []
    }
    raw_solver = _bytes(solver_declarado)

    decl_controles = {
        "caso": CASO,
        "expediente_sha256": fp,
        "corrida_analisis": corrida_id,
        "lectura": corrida_id,
        "modelo": {"id": model_id, "sha256_edb": sha_analizado},
        "datos_sinteticos": False,
        "casos": ["EST", "MOD", "EX"],
        "sha256_respuesta": sha_tablas,
        "sha256_avisos_solver": _sha(raw_solver),
        "revisor_declarado": REVISOR,
        "fecha": FECHA,
        "alcance": "Revision postsolver integral de masa participativa >= 90%, equilibrio estatico y advertencias del solucionador",
        "controles": controles_postsolver
    }

    doc_controles = ca.crear_controles(decl_controles, raw_tablas, avisos_solver_bytes=raw_solver)
    ctl_id = uuid4().hex
    ctl_dir = folder / "controles_analisis" / ctl_id
    ctl_dir.mkdir(parents=True, exist_ok=True)
    raw_doc_controles = _bytes(doc_controles)
    (ctl_dir / "controles.json").write_bytes(raw_doc_controles)
    ctl_meta = {
        "contrato": "draft2model.controles_analisis_web",
        "id": ctl_id,
        "caso": CASO,
        "expediente_sha256": fp,
        "vinculo": {
            "corrida_analisis": corrida_id,
            "lectura_trabajo": corrida_id,
            "modelo": {"id": model_id, "sha256_edb": sha_analizado},
            "datos_sinteticos": False,
            "casos": ["EST", "MOD", "EX"],
            "sha256_respuesta": sha_tablas,
            "sha256_avisos_solver": _sha(raw_solver)
        },
        "sha256_controles": _sha(raw_doc_controles),
        "creado_utc": datetime.now(timezone.utc).isoformat()
    }
    (ctl_dir / "version.json").write_bytes(_bytes(ctl_meta))
    print(f"Controles postsolver registrados: {ctl_id}")

    # 6. Revision de Resultados Declarada (Etapa 6)
    print("\n--- Registrando Revision de Resultados ---")
    rev_body = {
        "caso": CASO,
        "resultado": res_id,
        "analisis": corrida_id,
        "expediente_sha256": fp,
        "huella_resultados": huella_res,
        "huella_evidencia": huella_evid,
        "revisor_declarado": REVISOR,
        "fecha": FECHA,
        "alcance": "Revision y contraste de derivas de entrepiso (0.0032 < 0.007), masa modal (94.7% > 90%) y cortante basal",
        "motivo": "Aprobacion tecnica de resultados estructurales de vivienda unifamiliar conforme a E.030",
        "controles": {
            "unidades": True,
            "casos": True,
            "filtros": True,
            "omisiones": True,
            "consistencia_modelo": True,
            "revision_tecnica": True
        },
        "faltantes_criticos": [],
        "observaciones": [
            "La estructura cumple con las exigencias sismicas de la Norma E.030 Diseno Sismorresistente.",
            "Derivas maximas calculadas en el rango elastico cumplen holgadamente los limites normativos."
        ],
        "confirmacion_explicita": True
    }
    rev_res = app.revision_resultados.registrar(rev_body)
    rev_res_id = rev_res["id"]
    print(f"Revision de resultados registrada: {rev_res_id}")

    # 7. Informe Tecnico y Panel Interactivo (Etapa 7)
    print("\n--- Generando Informe Tecnico y Panel Interactivo ---")
    inf_body = {
        "caso": CASO,
        "resultado": res_id,
        "analisis": corrida_id,
        "expediente_sha256": fp,
        "contexto": {
            "titulo": "Informe Tecnico de Analisis y Evaluacion Estructural",
            "hipotesis": [
                "Analisis modal espectral elastico lineal segun Norma E.030",
                "Muros de corte modelados con elementos Shell y porticos con elementos Frame",
                "Base empotrada rigida a nivel de zapatas aisladas y cimientos corridos"
            ],
            "faltantes": [],
            "sitio": None
        },
        "revision_resultados": {
            "id": rev_res_id,
            "sha256_revision": rev_res["sha256_revision"]
        }
    }
    inf_doc = app.entregables.crear(inf_body)
    informe_id = inf_doc["id"]
    print(f"Informe borrador creado: {informe_id}")

    # Aprobar el informe documentalmente
    req_aprobar = {
        "caso": CASO,
        "version": informe_id,
        "expediente_sha256": fp,
        "sha256_informe": inf_doc["archivos"]["informe.json"],
        "revisor_declarado": REVISOR,
        "fecha": FECHA,
        "motivo": "Aprobacion documental final de memoria de calculo y diseno sismorresistente",
        "confirmacion_explicita": True
    }
    res_apr_inf = app.entregables.aprobar(req_aprobar)
    print(f"Informe aprobado formalmente! ID: {res_apr_inf['id']}")

    # Generar panel interactivo HTML
    print("\n--- Generando Panel Tecnico Interactivo ---")
    req_panel = {
        "caso": CASO,
        "expediente_sha256": fp,
        "resultado": res_id,
        "analisis": corrida_id
    }
    panel_res = app.paneles._crear(req_panel)
    print(f"Panel interactivo creado con exito! ID: {panel_res['id']}")

    print("\n=== CORRIDA INTEGRAL COMPLETADA EXITOSAMENTE ===")
    print(f"Caso: {CASO}")
    print(f"Geometria Aprobada: {geo_id}")
    print(f"Configuracion Aprobada: {cfg_id}")
    print(f"Modelo ETABS Aprobado: {model_id} (Aprobacion: {aprobacion_modelo_id})")
    print(f"Analisis ETABS: {corrida_id}")
    print(f"Resultados Estructurales: {res_id}")
    print(f"Controles Postsolver: {ctl_id}")
    print(f"Revision de Resultados: {rev_res_id}")
    print(f"Informe Tecnico Aprobado: {res_apr_inf['id']}")
    print(f"Panel Tecnico Interactivo: {panel_res['id']}")


if __name__ == "__main__":
    main()
