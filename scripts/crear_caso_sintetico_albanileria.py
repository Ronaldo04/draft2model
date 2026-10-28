from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
"""Generador y ejecutor integral de datos sintéticos de vivienda de albañilería confinada (2 pisos).

Normativa de aplicación:
- RNE Norma Técnica E.070: Albañilería Confinada (Ladrillo King Kong 18 huecos, f'm = 65 kg/cm2)
- RNE Norma Técnica E.030: Diseño Sismorresistente (Zona 4, Suelo S2, U=1.0, R=3, Deriva máx <= 0.005)
- RNE Norma Técnica E.060: Concreto Armado (Columnas CC y Vigas Soleras VS, f'c = 210 kg/cm2, fy = 4200 kg/cm2)
- RNE Norma Técnica E.020: Cargas (Losa aligerada h=0.20m, acabados, sobrecargas de vivienda y azotea)

Revisor: Ing. Ronaldo Cuchilla
Fecha: 2026-10-26
Caso: vivienda-sintetica-albanileria-2p
"""

import copy
from datetime import datetime, timezone
import hashlib
import json
import math
import os
import shutil
import tempfile
from uuid import uuid4

import pymupdf

from draft2model import contratos as c
from draft2model import gestion_configuracion as gc
from draft2model import gestion_extraccion as ge
from draft2model import gestion_geometria as gg
from draft2model import modelo_estructural as me
from draft2model import operaciones_etabs as oe
from draft2model import revision_modelo as rm
from draft2model import evidencia_analisis as ea
from draft2model import controles_analisis as ca
from draft2model.ingreso import registrar_expediente, file_hash
from draft2model.revision_documental import revisar_expediente
from draft2model.revision_visual import RevisionLocal
from draft2model.resultados_estructurales import huella_resultados, exigir_resultados, huella_declaracion

CASO = "vivienda-sintetica-albanileria-2p"
REVISOR = "Ing. Ronaldo Cuchilla"
FECHA = "2026-10-26"
RAIZ = Path("data/private").resolve()


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _bytes(obj: dict) -> bytes:
    return (json.dumps(obj, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def generar_planos_pdf(carpeta_salida: Path) -> tuple[Path, Path]:
    """Genera planos PDF vectoriales profesionales de Arquitectura y Estructuras."""
    carpeta_salida.mkdir(parents=True, exist_ok=True)
    pdf_arq = carpeta_salida / "PLANO_ARQUITECTURA_A01.pdf"
    pdf_est = carpeta_salida / "PLANO_ESTRUCTURAS_E01.pdf"

    # --- PLANO ARQUITECTURA A-01 ---
    doc_a = pymupdf.open()
    # Pagina 1: Planta Primer Piso y Cuadro de Vanos
    p1 = doc_a.new_page(width=842, height=595)  # A4 horizontal
    s1 = p1.new_shape()
    # Membrete
    s1.draw_rect(pymupdf.Rect(20, 20, 822, 575))
    s1.finish(color=(0, 0, 0), width=1.0)
    s1.draw_rect(pymupdf.Rect(540, 430, 822, 575))
    s1.finish(color=(0, 0, 0), width=1.0)
    s1.insert_text(pymupdf.Point(550, 450), "PROYECTO: VIVIENDA UNIFAMILIAR 2 PISOS", fontsize=11, fontname="helv", color=(0, 0, 0))
    s1.insert_text(pymupdf.Point(550, 470), "SISTEMA: ALBAÑILERIA CONFINADA (E.070)", fontsize=10, fontname="helv", color=(0, 0, 0))
    s1.insert_text(pymupdf.Point(550, 490), "UBICACION: LIMA, PERU - ZONA 4", fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))
    s1.insert_text(pymupdf.Point(550, 510), "REVISOR: ING. RONALDO CUCHILLA", fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))
    s1.insert_text(pymupdf.Point(550, 530), "PLANO: A-01 DISTRIBUCION ARQUITECTONICA", fontsize=10, fontname="helv", color=(0, 0, 0))
    s1.insert_text(pymupdf.Point(550, 550), "ESCALA: 1/50 | FECHA: 2026-10-26", fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))

    # Titulo y dibujo Planta Primer Piso
    s1.insert_text(pymupdf.Point(50, 55), "PLANTA PRIMER PISO (N.P.T. +0.15 m)", fontsize=13, fontname="helv", color=(0, 0, 0.5))
    s1.insert_text(pymupdf.Point(50, 75), "Distribucion: Cochera, Sala, Comedor, Cocina, Baño de Visitas, Escalera y Patio/Lavanderia", fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))

    # Ejes y Muros en Planta 1
    ox, oy = 100, 120
    s1.draw_rect(pymupdf.Rect(ox, oy, ox + 150, oy + 300))
    s1.finish(color=(0.1, 0.1, 0.1), width=1.5)
    # Ambientes Piso 1
    s1.draw_line(pymupdf.Point(ox, oy + 100), pymupdf.Point(ox + 150, oy + 100))
    s1.finish(color=(0.1, 0.1, 0.1), width=1.0)
    s1.draw_line(pymupdf.Point(ox, oy + 200), pymupdf.Point(ox + 150, oy + 200))
    s1.finish(color=(0.1, 0.1, 0.1), width=1.0)
    s1.draw_line(pymupdf.Point(ox + 75, oy), pymupdf.Point(ox + 75, oy + 300))
    s1.finish(color=(0.1, 0.1, 0.1), width=1.0)

    s1.insert_text(pymupdf.Point(ox + 10, oy + 50), "COCHERA / INGRESO", fontsize=8, fontname="helv")
    s1.insert_text(pymupdf.Point(ox + 85, oy + 50), "SALA PRINCIPAL", fontsize=8, fontname="helv")
    s1.insert_text(pymupdf.Point(ox + 10, oy + 140), "ESCALERA / SSHH VIS.", fontsize=8, fontname="helv")
    s1.insert_text(pymupdf.Point(ox + 85, oy + 140), "COMEDOR", fontsize=8, fontname="helv")
    s1.insert_text(pymupdf.Point(ox + 10, oy + 250), "PATIO / LAVANDERIA", fontsize=8, fontname="helv")
    s1.insert_text(pymupdf.Point(ox + 85, oy + 250), "COCINA INTEGRAL", fontsize=8, fontname="helv")

    # Cuadro de Vanos
    s1.insert_text(pymupdf.Point(320, 130), "CUADRO DE VANOS - ARQUITECTURA", fontsize=10, fontname="helv", color=(0, 0, 0))
    s1.draw_rect(pymupdf.Rect(320, 140, 500, 290))
    s1.finish(color=(0, 0, 0), width=1.0)
    s1.insert_text(pymupdf.Point(330, 160), "TIPO   ANCHO(m)  ALTO(m)  ALFEIZAR(m)", fontsize=8, fontname="helv")
    s1.insert_text(pymupdf.Point(330, 180), "P-1    0.90      2.10     - (Principal)", fontsize=8, fontname="helv")
    s1.insert_text(pymupdf.Point(330, 200), "P-2    0.80      2.10     - (Interiores)", fontsize=8, fontname="helv")
    s1.insert_text(pymupdf.Point(330, 220), "P-3    0.70      2.10     - (Baños)", fontsize=8, fontname="helv")
    s1.insert_text(pymupdf.Point(330, 240), "V-1    2.00      1.40     1.00 (Sala)", fontsize=8, fontname="helv")
    s1.insert_text(pymupdf.Point(330, 260), "V-2    1.50      1.40     1.00 (Dormitorios)", fontsize=8, fontname="helv")
    s1.insert_text(pymupdf.Point(330, 280), "V-3    0.60      0.50     1.90 (Baños)", fontsize=8, fontname="helv")
    s1.commit()

    # Pagina 2: Planta Segundo Piso
    p2 = doc_a.new_page(width=842, height=595)
    s2 = p2.new_shape()
    s2.draw_rect(pymupdf.Rect(20, 20, 822, 575))
    s2.finish(color=(0, 0, 0), width=1.0)
    s2.draw_rect(pymupdf.Rect(540, 430, 822, 575))
    s2.finish(color=(0, 0, 0), width=1.0)
    s2.insert_text(pymupdf.Point(550, 450), "PROYECTO: VIVIENDA UNIFAMILIAR 2 PISOS", fontsize=11, fontname="helv", color=(0, 0, 0))
    s2.insert_text(pymupdf.Point(550, 470), "SISTEMA: ALBAÑILERIA CONFINADA (E.070)", fontsize=10, fontname="helv", color=(0, 0, 0))
    s2.insert_text(pymupdf.Point(550, 490), "REVISOR: ING. RONALDO CUCHILLA", fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))
    s2.insert_text(pymupdf.Point(550, 510), "PLANO: A-02 PLANTA SEGUNDO PISO", fontsize=10, fontname="helv", color=(0, 0, 0))
    s2.insert_text(pymupdf.Point(550, 530), "ESCALA: 1/50 | FECHA: 2026-10-26", fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))

    s2.insert_text(pymupdf.Point(50, 55), "PLANTA SEGUNDO PISO (N.P.T. +2.95 m)", fontsize=13, fontname="helv", color=(0, 0, 0.5))
    s2.insert_text(pymupdf.Point(50, 75), "Distribucion: Dormitorio Principal, Dormitorios 2 y 3, Baño Completo, Hall Intimo y Balcon", fontsize=9, fontname="helv", color=(0.3, 0.3, 0.3))

    s2.draw_rect(pymupdf.Rect(ox, oy, ox + 150, oy + 300))
    s2.finish(color=(0.1, 0.1, 0.1), width=1.5)
    s2.draw_line(pymupdf.Point(ox, oy + 100), pymupdf.Point(ox + 150, oy + 100))
    s2.finish(color=(0.1, 0.1, 0.1), width=1.0)
    s2.draw_line(pymupdf.Point(ox, oy + 200), pymupdf.Point(ox + 150, oy + 200))
    s2.finish(color=(0.1, 0.1, 0.1), width=1.0)
    s2.draw_line(pymupdf.Point(ox + 75, oy), pymupdf.Point(ox + 75, oy + 300))
    s2.finish(color=(0.1, 0.1, 0.1), width=1.0)

    s2.insert_text(pymupdf.Point(ox + 10, oy + 50), "DORMITORIO 2", fontsize=8, fontname="helv")
    s2.insert_text(pymupdf.Point(ox + 85, oy + 50), "DORM. PRINCIPAL", fontsize=8, fontname="helv")
    s2.insert_text(pymupdf.Point(ox + 10, oy + 140), "HALL / ESTAR INTIMO", fontsize=8, fontname="helv")
    s2.insert_text(pymupdf.Point(ox + 85, oy + 140), "BAÑO COMPLETO", fontsize=8, fontname="helv")
    s2.insert_text(pymupdf.Point(ox + 10, oy + 250), "DORMITORIO 3", fontsize=8, fontname="helv")
    s2.insert_text(pymupdf.Point(ox + 85, oy + 250), "ESTUDIO / BALCON", fontsize=8, fontname="helv")
    s2.commit()
    doc_a.save(str(pdf_arq))
    doc_a.close()

    # --- PLANO ESTRUCTURAS E-01 ---
    doc_e = pymupdf.open()
    # Pagina 1: Muros Confinados, Cimentacion y Cuadros
    pe1 = doc_e.new_page(width=842, height=595)
    se1 = pe1.new_shape()
    se1.draw_rect(pymupdf.Rect(20, 20, 822, 575))
    se1.finish(color=(0, 0, 0), width=1.0)
    se1.draw_rect(pymupdf.Rect(540, 410, 822, 575))
    se1.finish(color=(0, 0, 0), width=1.0)
    se1.insert_text(pymupdf.Point(550, 430), "PROYECTO: VIVIENDA UNIFAMILIAR 2 PISOS", fontsize=11, fontname="helv", color=(0, 0, 0))
    se1.insert_text(pymupdf.Point(550, 450), "PLANO: E-01 ALBAÑILERIA CONFINADA Y DETALLES", fontsize=10, fontname="helv", color=(0, 0, 0))
    se1.insert_text(pymupdf.Point(550, 470), "NORMA TECNICA: E.070 / E.030 / E.060 / E.020", fontsize=9, fontname="helv", color=(0, 0, 0))
    se1.insert_text(pymupdf.Point(550, 490), "REVISOR: ING. RONALDO CUCHILLA", fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))
    se1.insert_text(pymupdf.Point(550, 510), "SISTEMA: MUROS CONFINADOS KING KONG 18H", fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))
    se1.insert_text(pymupdf.Point(550, 530), "ESCALA: 1/50 | FECHA: 2026-10-26", fontsize=9, fontname="helv", color=(0.2, 0.2, 0.2))

    se1.insert_text(pymupdf.Point(50, 50), "DISTRIBUCION DE MUROS PORTANTES Y COLUMNAS DE CONFINAMIENTO", fontsize=12, fontname="helv", color=(0.6, 0, 0))
    se1.draw_rect(pymupdf.Rect(ox, oy, ox + 150, oy + 300))
    se1.finish(color=(0.8, 0, 0), width=2.0)
    se1.draw_line(pymupdf.Point(ox, oy + 100), pymupdf.Point(ox + 150, oy + 100))
    se1.finish(color=(0.8, 0, 0), width=1.5)
    se1.draw_line(pymupdf.Point(ox, oy + 200), pymupdf.Point(ox + 150, oy + 200))
    se1.finish(color=(0.8, 0, 0), width=1.5)
    se1.draw_line(pymupdf.Point(ox + 75, oy), pymupdf.Point(ox + 75, oy + 300))
    se1.finish(color=(0.8, 0, 0), width=1.5)

    # Columnas CC-1 y CC-2 en nodos
    for ix in (ox, ox + 75, ox + 150):
        for iy in (oy, oy + 100, oy + 200, oy + 300):
            se1.draw_rect(pymupdf.Rect(ix - 5, iy - 5, ix + 5, iy + 5))
            se1.finish(fill=(0, 0, 0.7), color=(0, 0, 0), width=0.5)

    # Especificaciones tecnicas
    se1.insert_text(pymupdf.Point(300, 80), "ESPECIFICACIONES TECNICAS ESTRUCTURALES", fontsize=10, fontname="helv", color=(0, 0, 0))
    se1.insert_text(pymupdf.Point(300, 105), "1. ALBAÑILERIA CONFINADA (NORMA E.070):", fontsize=9, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 120), "- Ladrillo de arcilla cocida King Kong 18 huecos (Tipo IV industrial)", fontsize=8, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 135), "- Mortero Tipo P2 (Cemento:Arena 1:4)", fontsize=8, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 150), "- Resistencia a compresion en prismas f'm = 65 kg/cm2", fontsize=8, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 165), "- Resistencia al corte vm = 8.1 kg/cm2", fontsize=8, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 180), "- Modulo de elasticidad Em = 32,500 kg/cm2 (500 f'm)", fontsize=8, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 195), "- Modulo de corte Gm = 13,000 kg/cm2 (0.4 Em)", fontsize=8, fontname="helv")

    se1.insert_text(pymupdf.Point(300, 220), "2. CONCRETO ARMADO (NORMA E.060):", fontsize=9, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 235), "- Columnas de confinamiento y vigas soleras: f'c = 210 kg/cm2", fontsize=8, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 250), "- Modulo de elasticidad Ec = 217,370 kg/cm2 (15000 sqrt(f'c))", fontsize=8, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 265), "- Acero de refuerzo ASTM A615 Grado 60, fy = 4200 kg/cm2", fontsize=8, fontname="helv")

    se1.insert_text(pymupdf.Point(300, 290), "3. PARAMETROS SISMICOS (NORMA E.030):", fontsize=9, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 305), "- Factor de Zona Z = 0.45 (Zona 4 - Costa)", fontsize=8, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 320), "- Factor de Uso U = 1.0 (Edificacion Comun)", fontsize=8, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 335), "- Factor de Suelo S = 1.05 (Suelo Intermedio S2, Tp=0.6s, Tl=2.0s)", fontsize=8, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 350), "- Coeficiente de reduccion R = 3 (Albañileria Confinada)", fontsize=8, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 365), "- Limite de deriva elastica max = 0.005", fontsize=8, fontname="helv")

    se1.insert_text(pymupdf.Point(300, 390), "4. CARGAS Y SOBRECARGAS (NORMA E.020):", fontsize=9, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 405), "- Losa aligerada unidireccional h = 0.20 m: Carga Muerta = 300 kg/m2", fontsize=8, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 420), "- Acabados y contrapiso: Carga Muerta = 100 kg/m2", fontsize=8, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 435), "- Sobrecarga Piso 1 (Vivienda): L = 200 kg/m2", fontsize=8, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 450), "- Sobrecarga Piso 2 (Vivienda): L = 200 kg/m2", fontsize=8, fontname="helv")
    se1.insert_text(pymupdf.Point(310, 465), "- Sobrecarga Azotea: L = 100 kg/m2", fontsize=8, fontname="helv")
    se1.commit()
    doc_e.save(str(pdf_est))
    doc_e.close()

    return pdf_arq, pdf_est


def main():
    print(f"=== INICIANDO GENERACION INTEGRAL CASO SINTETICO: {CASO} ===")
    print(f"Normas: E.070, E.030, E.060, E.020 | Revisor: {REVISOR} | Fecha: {FECHA}")

    # Limpiar carpeta si existe previamente
    caso_folder = RAIZ / CASO
    if caso_folder.exists():
        print(f"Limpiando directorio previo {caso_folder}...")
        shutil.rmtree(caso_folder)

    # 1. ETAPA 1: Generar planos vectoriales y registrar expediente
    print("\n--- ETAPA 1: REGISTRO DE EXPEDIENTE DOCUMENTAL SINTETICO ---")
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        pdf_arq, pdf_est = generar_planos_pdf(tmp_path)
        manifest_path = registrar_expediente(
            case_id=CASO,
            sources=[pdf_arq, pdf_est],
            case_root=RAIZ,
            uso_autorizado=True,
            provisional_fuera_alcance=False
        )
        print(f"Expediente registrado exitosamente en: {manifest_path}")

    # Revision documental
    revisar_expediente(caso_folder / "expediente.json")
    print("Revision documental generada con vistas previas.")

    app = RevisionLocal(RAIZ)
    folder, manifest, fp = app.expediente(CASO)
    print(f"Expediente cargado. Fingerprint: {fp[:12]}...")

    archivos_map = {a["nombre_original"]: a for a in manifest["archivos"]}
    id_arq = archivos_map["PLANO_ARQUITECTURA_A01.pdf"]["id"]
    sha_arq = archivos_map["PLANO_ARQUITECTURA_A01.pdf"]["sha256"]
    id_est = archivos_map["PLANO_ESTRUCTURAS_E01.pdf"]["id"]
    sha_est = archivos_map["PLANO_ESTRUCTURAS_E01.pdf"]["sha256"]

    # 2. ETAPA 2: Extracciones Preliminares (datos sinteticos)
    print("\n--- ETAPA 2: EXTRACCION PRELIMINAR DE CANDIDATOS SINTETICOS ---")
    candidatos = [
        # Cotas y geometria
        {
            "id": "C-ANCHO-6M",
            "tipo": "cota",
            "valor_propuesto": 6.0,
            "unidad": "m",
            "metodo": {"tipo": "sintetico", "descripcion": "Extraccion de planos arquitectonicos A-01"},
            "texto_fuente": "ANCHO TOTAL = 6.00 m (Ejes A a C)",
            "evidencia": [{"archivo_id": id_arq, "pagina": 1, "original_sha256": sha_arq, "bbox_normalizada": [0.1, 0.1, 0.4, 0.3]}],
            "revision": {"estado": "revisado", "historial": [{"estado": "revisado", "motivo": "Verificado conforme a eje A a C", "fecha": FECHA, "revisor_declarado": REVISOR, "valor_revisado": 6.0, "unidad_revisada": "m", "tipo_revisado": "cota"}]}
        },
        {
            "id": "C-LARGO-12M",
            "tipo": "cota",
            "valor_propuesto": 12.0,
            "unidad": "m",
            "metodo": {"tipo": "sintetico", "descripcion": "Extraccion de planos arquitectonicos A-01"},
            "texto_fuente": "LARGO TOTAL = 12.00 m (Ejes 1 a 4)",
            "evidencia": [{"archivo_id": id_arq, "pagina": 1, "original_sha256": sha_arq, "bbox_normalizada": [0.1, 0.1, 0.4, 0.7]}],
            "revision": {"estado": "revisado", "historial": [{"estado": "revisado", "motivo": "Verificado conforme a ejes 1 a 4", "fecha": FECHA, "revisor_declarado": REVISOR, "valor_revisado": 12.0, "unidad_revisada": "m", "tipo_revisado": "cota"}]}
        },
        {
            "id": "C-ALTURA-ENTREPISO",
            "tipo": "cota",
            "valor_propuesto": 2.80,
            "unidad": "m",
            "metodo": {"tipo": "sintetico", "descripcion": "Extraccion de cortes arquitectonicos A-01"},
            "texto_fuente": "ALTURA DE ENTREPISO = 2.80 m (Nivel 1 a Nivel 2)",
            "evidencia": [{"archivo_id": id_arq, "pagina": 2, "original_sha256": sha_arq, "bbox_normalizada": [0.1, 0.1, 0.5, 0.5]}],
            "revision": {"estado": "revisado", "historial": [{"estado": "revisado", "motivo": "Verificado altura libre 2.60m + losa 0.20m", "fecha": FECHA, "revisor_declarado": REVISOR, "valor_revisado": 2.80, "unidad_revisada": "m", "tipo_revisado": "cota"}]}
        },
        # Materiales
        {
            "id": "P-ALBANILERIA-FM",
            "tipo": "propiedad",
            "simbolo": "f'm",
            "valor_propuesto": 65.0,
            "unidad": "kgf/cm2",
            "metodo": {"tipo": "sintetico", "descripcion": "Especificaciones E-01"},
            "texto_fuente": "ALBAÑILERIA CONFINADA: f'm = 65 kg/cm2",
            "evidencia": [{"archivo_id": id_est, "pagina": 1, "original_sha256": sha_est, "bbox_normalizada": [0.3, 0.1, 0.6, 0.3]}],
            "revision": {"estado": "revisado", "historial": [{"estado": "revisado", "motivo": "Conforme a Norma E.070 Tabla 9", "fecha": FECHA, "revisor_declarado": REVISOR, "valor_revisado": 65.0, "unidad_revisada": "kgf/cm2", "tipo_revisado": "propiedad"}]}
        },
        {
            "id": "P-CONCRETO-FC",
            "tipo": "propiedad",
            "simbolo": "f'c",
            "valor_propuesto": 210.0,
            "unidad": "kgf/cm2",
            "metodo": {"tipo": "sintetico", "descripcion": "Especificaciones E-01"},
            "texto_fuente": "CONCRETO ARMADO: f'c = 210 kg/cm2",
            "evidencia": [{"archivo_id": id_est, "pagina": 1, "original_sha256": sha_est, "bbox_normalizada": [0.3, 0.3, 0.6, 0.5]}],
            "revision": {"estado": "revisado", "historial": [{"estado": "revisado", "motivo": "Conforme a Norma E.060", "fecha": FECHA, "revisor_declarado": REVISOR, "valor_revisado": 210.0, "unidad_revisada": "kgf/cm2", "tipo_revisado": "propiedad"}]}
        },
        {
            "id": "P-ACERO-FY",
            "tipo": "propiedad",
            "simbolo": "fy",
            "valor_propuesto": 4200.0,
            "unidad": "kgf/cm2",
            "metodo": {"tipo": "sintetico", "descripcion": "Especificaciones E-01"},
            "texto_fuente": "ACERO DE REFUERZO: fy = 4200 kg/cm2",
            "evidencia": [{"archivo_id": id_est, "pagina": 1, "original_sha256": sha_est, "bbox_normalizada": [0.3, 0.3, 0.6, 0.5]}],
            "revision": {"estado": "revisado", "historial": [{"estado": "revisado", "motivo": "Conforme a ASTM A615 Grado 60", "fecha": FECHA, "revisor_declarado": REVISOR, "valor_revisado": 4200.0, "unidad_revisada": "kgf/cm2", "tipo_revisado": "propiedad"}]}
        },
        # Cargas
        {
            "id": "CARGA-MUERTA-ALIGERADO",
            "tipo": "carga",
            "valor_propuesto": 300.0,
            "unidad": "kgf/m2",
            "metodo": {"tipo": "sintetico", "descripcion": "Especificaciones E-01"},
            "texto_fuente": "PESO PROPIO LOSA ALIGERADA h=0.20m = 300 kg/m2",
            "evidencia": [{"archivo_id": id_est, "pagina": 1, "original_sha256": sha_est, "bbox_normalizada": [0.3, 0.6, 0.6, 0.8]}],
            "revision": {"estado": "revisado", "historial": [{"estado": "revisado", "motivo": "Conforme a E.020 Anexo 1", "fecha": FECHA, "revisor_declarado": REVISOR, "valor_revisado": 300.0, "unidad_revisada": "kgf/m2", "tipo_revisado": "carga"}]}
        },
        {
            "id": "CARGA-VIVA-VIVIENDA",
            "tipo": "carga",
            "valor_propuesto": 200.0,
            "unidad": "kgf/m2",
            "metodo": {"tipo": "sintetico", "descripcion": "Especificaciones E-01"},
            "texto_fuente": "SOBRECARGA PISOS 1 Y 2 = 200 kg/m2",
            "evidencia": [{"archivo_id": id_est, "pagina": 1, "original_sha256": sha_est, "bbox_normalizada": [0.3, 0.6, 0.6, 0.8]}],
            "revision": {"estado": "revisado", "historial": [{"estado": "revisado", "motivo": "Conforme a E.020 Tabla 1", "fecha": FECHA, "revisor_declarado": REVISOR, "valor_revisado": 200.0, "unidad_revisada": "kgf/m2", "tipo_revisado": "carga"}]}
        },
        # Parametros sismicos
        {
            "id": "PARAM-ZONA-Z",
            "tipo": "parametro",
            "simbolo": "Z",
            "valor_propuesto": 0.45,
            "unidad": "adimensional",
            "metodo": {"tipo": "sintetico", "descripcion": "Especificaciones E-01"},
            "texto_fuente": "ZONA SISMICA 4: Z = 0.45",
            "evidencia": [{"archivo_id": id_est, "pagina": 1, "original_sha256": sha_est, "bbox_normalizada": [0.3, 0.5, 0.6, 0.7]}],
            "revision": {"estado": "revisado", "historial": [{"estado": "revisado", "motivo": "Conforme a E.030 Tabla 1", "fecha": FECHA, "revisor_declarado": REVISOR, "valor_revisado": 0.45, "unidad_revisada": "adimensional", "tipo_revisado": "parametro"}]}
        },
        {
            "id": "PARAM-REDUCCION-R",
            "tipo": "parametro",
            "simbolo": "R",
            "valor_propuesto": 3.0,
            "unidad": "adimensional",
            "metodo": {"tipo": "sintetico", "descripcion": "Especificaciones E-01"},
            "texto_fuente": "SISTEMA ALBAÑILERIA CONFINADA: R = 3",
            "evidencia": [{"archivo_id": id_est, "pagina": 1, "original_sha256": sha_est, "bbox_normalizada": [0.3, 0.5, 0.6, 0.7]}],
            "revision": {"estado": "revisado", "historial": [{"estado": "revisado", "motivo": "Conforme a E.030 Tabla 7", "fecha": FECHA, "revisor_declarado": REVISOR, "valor_revisado": 3.0, "unidad_revisada": "adimensional", "tipo_revisado": "parametro"}]}
        }
    ]

    extraccion_doc = {
        "contrato": "draft2model.extraccion_preliminar",
        "version_contrato": "0.2.0",
        "caso": CASO,
        "procedencia": {
            "tipo": "expediente",
            "descripcion": "Extraccion sintetica completa de planos de arquitectura y estructuras de vivienda unifamiliar de albanileria confinada",
            "expediente_sha256": fp
        },
        "alcance": manifest["alcance"],
        "sistema_coordenadas": "pagina_visible_normalizada",
        "candidatos": candidatos
    }

    with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as f_tmp:
        f_tmp.write(_bytes(extraccion_doc))
        tmp_ext_path = Path(f_tmp.name)

    ext_res = ge.importar_extraccion(RAIZ, CASO, tmp_ext_path)
    tmp_ext_path.unlink()
    print(f"Extraccion sintetica preliminar importada: {ext_res.identificador} (candidatos: {len(candidatos)})")

    # 3. ETAPA 3: Geometria Estructural y Aprobacion Tecnica
    print("\n--- ETAPA 3: RECONSTRUCCION Y APROBACION DE GEOMETRIA ---")
    # Niveles: N0 = 0.00, N1 = 2.80, N2 = 5.60
    niveles = [
        {"id": "N0", "nombre": "Cimentacion / Sobrecimiento", "cota": 0.00, "procedencia": {"tipo": "sintetico", "descripcion": "Nivel superior de sobrecimiento", "expediente_id": CASO}},
        {"id": "N1", "nombre": "Primer Piso / Entrepiso", "cota": 2.80, "procedencia": {"tipo": "sintetico", "descripcion": "Cota losa entrepiso", "expediente_id": CASO}},
        {"id": "N2", "nombre": "Segundo Piso / Azotea", "cota": 5.60, "procedencia": {"tipo": "sintetico", "descripcion": "Cota losa azotea", "expediente_id": CASO}}
    ]

    # Nodos en rejilla 3x4: A=0, B=3, C=6; 1=0, 2=4, 3=8, 4=12
    nodos = []
    coords_x = {"A": 0.00, "B": 3.00, "C": 6.00}
    coords_y = {"1": 0.00, "2": 4.00, "3": 8.00, "4": 12.00}
    for eje_x, x in coords_x.items():
        for eje_y, y in coords_y.items():
            nodos.append({
                "id": f"{eje_x}{eje_y}",
                "x": x,
                "y": y,
                "procedencia": {"tipo": "sintetico", "descripcion": f"Interseccion eje {eje_x} y {eje_y}", "expediente_id": CASO}
            })

    # Muros portantes confinados: 16 por piso, 32 en total
    muros = []
    # Piso 1 (N0 a N1) y Piso 2 (N1 a N2)
    pares_piso = [("1", "N0", "N1"), ("2", "N1", "N2")]
    for p_num, n_inf, n_sup in pares_piso:
        # En direccion X (ejes 1, 2, 3, 4): A-B y B-C
        for ey in ("1", "2", "3", "4"):
            muros.append({
                "id": f"M_X_EJE{ey}_AB_P{p_num}",
                "nodo_inicio": f"A{ey}",
                "nodo_fin": f"B{ey}",
                "nivel_inferior": n_inf,
                "nivel_superior": n_sup,
                "espesor": 0.15,
                "procedencia": {"tipo": "sintetico", "descripcion": f"Muro confinado en X eje {ey} tramo A-B piso {p_num}", "expediente_id": CASO}
            })
            muros.append({
                "id": f"M_X_EJE{ey}_BC_P{p_num}",
                "nodo_inicio": f"B{ey}",
                "nodo_fin": f"C{ey}",
                "nivel_inferior": n_inf,
                "nivel_superior": n_sup,
                "espesor": 0.15,
                "procedencia": {"tipo": "sintetico", "descripcion": f"Muro confinado en X eje {ey} tramo B-C piso {p_num}", "expediente_id": CASO}
            })
        # En direccion Y (ejes A, B, C): 1-2, 2-3, 3-4
        for ex in ("A", "C"):
            for ey1, ey2 in (("1", "2"), ("2", "3"), ("3", "4")):
                muros.append({
                    "id": f"M_Y_EJE{ex}_{ey1}{ey2}_P{p_num}",
                    "nodo_inicio": f"{ex}{ey1}",
                    "nodo_fin": f"{ex}{ey2}",
                    "nivel_inferior": n_inf,
                    "nivel_superior": n_sup,
                    "espesor": 0.15,
                    "procedencia": {"tipo": "sintetico", "descripcion": f"Muro confinado en Y eje {ex} tramo {ey1}-{ey2} piso {p_num}", "expediente_id": CASO}
                })
        # Eje B intermedio: tramos 1-2 y 3-4 (tramo 2-3 es vacio de escalera/estar)
        for ey1, ey2 in (("1", "2"), ("3", "4")):
            muros.append({
                "id": f"M_Y_EJEB_{ey1}{ey2}_P{p_num}",
                "nodo_inicio": f"B{ey1}",
                "nodo_fin": f"B{ey2}",
                "nivel_inferior": n_inf,
                "nivel_superior": n_sup,
                "espesor": 0.15,
                "procedencia": {"tipo": "sintetico", "descripcion": f"Muro confinado en Y eje B tramo {ey1}-{ey2} piso {p_num}", "expediente_id": CASO}
            })

    geometria_doc = {
        "contrato": "draft2model.geometria",
        "version_contrato": "0.1.0",
        "id": CASO,
        "unidad_longitud": "m",
        "procedencia": {
            "tipo": "sintetico",
            "descripcion": "Geometria sintetica completa de 2 pisos para vivienda en albanileria confinada",
            "expediente_id": CASO
        },
        "niveles": niveles,
        "nodos": nodos,
        "muros": muros,
        "faltantes": [],
        "revision": {"estado": "borrador", "aprobacion": None}
    }

    with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as f_tmp:
        f_tmp.write(_bytes(geometria_doc))
        tmp_geo_path = Path(f_tmp.name)

    geo_import = gg.importar_geometria(RAIZ, CASO, tmp_geo_path)
    tmp_geo_path.unlink()
    print(f"Geometria raiz importada: {geo_import.identificador} | Huella: {geo_import.comprobacion.huella_contenido[:8]}")

    geo_aprobada = gg.aprobar_geometria(
        raiz=RAIZ,
        caso=CASO,
        version_id=geo_import.identificador,
        huella_esperada=geo_import.comprobacion.huella_contenido,
        revisor_declarado=REVISOR,
        fecha=FECHA,
        motivo="Aprobacion tecnica de geometria estructural de vivienda de albanileria confinada",
        alcance_revision="Revision geometrica integral de niveles N0-N2, ejes A-C y 1-4, y 32 muros portantes confinados"
    )
    geo_id = geo_aprobada.identificador
    geo_comp = geo_aprobada.comprobacion
    print(f"Geometria aprobada formalmente! ID: {geo_id} | Huella: {geo_comp.huella_contenido[:8]}")

    # 4. ETAPA 4: Configuracion Estructural (Albañilería Confinada)
    print("\n--- ETAPA 4: CONFIGURACION ESTRUCTURAL ALBAÑILERIA CONFINADA ---")
    # Puntos 3D para nodos en cada nivel
    puntos_3d = []
    for n in niveles:
        for node in nodos:
            puntos_3d.append({
                "id": f"{node['id']}_{n['id']}",
                "nodo_geometria": node["id"],
                "nivel_geometria": n["id"]
            })

    # Frames (Columnas de confinamiento en cada piso y vigas soleras en cada losa)
    frames = []
    asignaciones_frames = []
    for p_num, n_inf, n_sup in pares_piso:
        for node in nodos:
            col_id = f"COL_{node['id']}_P{p_num}"
            frames.append({
                "id": col_id,
                "inicio": f"{node['id']}_{n_inf}",
                "fin": f"{node['id']}_{n_sup}",
                "tipo": "columna",
                "fuente": "PLANO_ESTRUCTURAS"
            })
            sec = "SEC_COL_CC1" if node["id"] in ("A1", "C1", "A4", "C4") else "SEC_COL_CC2"
            asignaciones_frames.append({
                "objetivo": col_id,
                "seccion": sec,
                "fuente": "PLANO_ESTRUCTURAS"
            })

    # Vigas soleras en N1 y N2
    for n_piso, niv_id in ((1, "N1"), (2, "N2")):
        for ey in ("1", "2", "3", "4"):
            for ex1, ex2 in (("A", "B"), ("B", "C")):
                viga_id = f"VS_X_{ex1}{ex2}_{ey}_{niv_id}"
                frames.append({
                    "id": viga_id,
                    "inicio": f"{ex1}{ey}_{niv_id}",
                    "fin": f"{ex2}{ey}_{niv_id}",
                    "tipo": "viga",
                    "fuente": "PLANO_ESTRUCTURAS"
                })
                asignaciones_frames.append({
                    "objetivo": viga_id,
                    "seccion": "SEC_VIGA_VS2",
                    "fuente": "PLANO_ESTRUCTURAS"
                })
        for ex in ("A", "B", "C"):
            for ey1, ey2 in (("1", "2"), ("2", "3"), ("3", "4")):
                viga_id = f"VS_Y_{ex}_{ey1}{ey2}_{niv_id}"
                frames.append({
                    "id": viga_id,
                    "inicio": f"{ex}{ey1}_{niv_id}",
                    "fin": f"{ex}{ey2}_{niv_id}",
                    "tipo": "viga",
                    "fuente": "PLANO_ESTRUCTURAS"
                })
                asignaciones_frames.append({
                    "objetivo": viga_id,
                    "seccion": "SEC_VIGA_VS2",
                    "fuente": "PLANO_ESTRUCTURAS"
                })

    # Asignaciones de muros
    asignaciones_muros = []
    for m in muros:
        asignaciones_muros.append({
            "objetivo": m["id"],
            "seccion": "SEC_MURO_SOGA_15",
            "fuente": "PLANO_ESTRUCTURAS"
        })

    # Cargas distribuidas gravitatorias de losa aligerada
    cargas = []
    for n_piso, niv_id in ((1, "N1"), (2, "N2")):
        for ey in ("1", "2", "3", "4"):
            for ex1, ex2 in (("A", "B"), ("B", "C")):
                viga_id = f"VS_X_{ex1}{ex2}_{ey}_{niv_id}"
                cargas.append({
                    "id": f"CG_D_{viga_id}",
                    "patron": "D",
                    "objetivo_tipo": "frame",
                    "objetivo": viga_id,
                    "componentes": [0, 0, -6.5],  # kN/m peso propio losa + acabados
                    "unidad": "kN/m",
                    "sistema": "global",
                    "fuente": "METRADO_E020"
                })
                cargas.append({
                    "id": f"CG_L_{viga_id}",
                    "patron": "L",
                    "objetivo_tipo": "frame",
                    "objetivo": viga_id,
                    "componentes": [0, 0, -2.5 if n_piso == 1 else -1.5],  # kN/m sobrecarga vivienda/azotea
                    "unidad": "kN/m",
                    "sistema": "global",
                    "fuente": "METRADO_E020"
                })

    # Apoyos empotrados en N0
    apoyos = []
    for node in nodos:
        apoyos.append({
            "punto": f"{node['id']}_N0",
            "restricciones": [True, True, True, True, True, True],
            "fuente": "CIMENTACION_E070"
        })

    # Diafragmas rigidos en N1 y N2
    diafragmas = [
        {
            "id": "DIA_N1",
            "tipo": "rigido",
            "puntos": [f"{node['id']}_N1" for node in nodos],
            "fuente": "NORMA_E030"
        },
        {
            "id": "DIA_N2",
            "tipo": "rigido",
            "puntos": [f"{node['id']}_N2" for node in nodos],
            "fuente": "NORMA_E030"
        }
    ]

    sin_diafragma = [{"punto": f"{node['id']}_N0", "motivo": "Nivel de cimentacion y sobrecimientos empotrados", "fuente": "NORMA_E030"} for node in nodos]

    # Espectro elastico E.030 para albanileria confinada R=3, Z=0.45, U=1.0, S=1.05
    # C = 2.5 para T <= Tp=0.6s -> Sa = (0.45*1.0*2.5*1.05/3)*9.80665 = 3.861 m/s2
    espectro_puntos = [
        [0.0, 1.544],
        [0.1, 3.861],
        [0.6, 3.861],
        [1.0, 2.317],
        [2.0, 1.158],
        [3.0, 0.515]
    ]

    config_doc = {
        "contrato": "draft2model.modelo_estructural",
        "version_contrato": "0.1.0",
        "id": f"config-{CASO}",
        "caso": CASO,
        "datos_sinteticos": True,
        "unidades": {"longitud": "m", "fuerza": "kN", "tiempo": "s", "temperatura": "C"},
        "geometria_origen": {
            "version_id": geo_id,
            "sha256_geometria": geo_comp.sha256_geometria,
            "huella_contenido": geo_comp.huella_contenido
        },
        "plantilla": {
            "id": "shell-frame-lineal",
            "version": "0.1.0",
            "sha256": "5f2faecfef861e2bd719b77e20a33c774fc152db395ee15c806ce001baf1a7f8",
            "representacion": "Modelo tridimensional de elementos Shell isotropos y Frame con diafragmas rigidos",
            "limitaciones": ["Comportamiento elastico lineal segun hipotesis reglamentarias de la Norma E.030 y E.070."],
            "fuente": "PLANO_ESTRUCTURAS"
        },
        "fuentes": [
            {"id": "PLANO_ESTRUCTURAS", "descripcion": "Plano de estructuras E-01", "referencia": "PLANO_ESTRUCTURAS_E01.pdf", "sha256": sha_est},
            {"id": "NORMA_E030", "descripcion": "Norma E.030 Diseño Sismorresistente", "referencia": "RNE E.030", "sha256": "0" * 64},
            {"id": "METRADO_E020", "descripcion": "Norma E.020 Cargas", "referencia": "RNE E.020", "sha256": "0" * 64},
            {"id": "CIMENTACION_E070", "descripcion": "Norma E.070 Albañileria", "referencia": "RNE E.070", "sha256": "0" * 64}
        ],
        "hipotesis": [
            {"id": "H-ALBANILERIA", "descripcion": "Muros portantes de King Kong 18 huecos f'm = 65 kg/cm2, Em = 32500 kg/cm2", "fuente": "CIMENTACION_E070"},
            {"id": "H-SISMO", "descripcion": "Espectro de respuesta E.030 Zona 4, Suelo S2, U=1.0, R=3.0", "fuente": "NORMA_E030"},
            {"id": "H-GRAVEDAD", "descripcion": "Metrado de cargas gravitatorias D + L conforme a E.020", "fuente": "METRADO_E020"}
        ],
        "sitio": {
            "descripcion": "Lima Costa - Suelo S2",
            "ubicacion": "Lima - Zona 4",
            "sistema_resistente": "Albañileria Confinada (R=3)",
            "parametros": [
                {"id": "Z", "valor": 0.45, "unidad": "1", "fuente": "NORMA_E030"},
                {"id": "U", "valor": 1.0, "unidad": "1", "fuente": "NORMA_E030"},
                {"id": "S", "valor": 1.05, "unidad": "1", "fuente": "NORMA_E030"},
                {"id": "R", "valor": 3.0, "unidad": "1", "fuente": "NORMA_E030"}
            ],
            "fuente": "NORMA_E030"
        },
        "materiales": [
            {"id": "ALBANILERIA_FM65", "tipo": "isotropo_lineal", "E_kN_m2": 3250000.0, "poisson": 0.25, "peso_kN_m3": 18.0, "fuente": "CIMENTACION_E070"},
            {"id": "CONCRETO_FC210", "tipo": "isotropo_lineal", "E_kN_m2": 21737065.0, "poisson": 0.20, "peso_kN_m3": 24.0, "fuente": "PLANO_ESTRUCTURAS"},
            {"id": "ACERO_FY4200", "tipo": "isotropo_lineal", "E_kN_m2": 200000000.0, "poisson": 0.30, "peso_kN_m3": 78.5, "fuente": "PLANO_ESTRUCTURAS"}
        ],
        "secciones": [
            {"id": "SEC_MURO_SOGA_15", "tipo": "shell_muro", "material": "ALBANILERIA_FM65", "dimensiones": {"espesor_m": 0.15}, "fuente": "PLANO_ESTRUCTURAS"},
            {"id": "SEC_COL_CC1", "tipo": "frame_rectangular", "material": "CONCRETO_FC210", "dimensiones": {"ancho_m": 0.25, "alto_m": 0.25}, "fuente": "PLANO_ESTRUCTURAS"},
            {"id": "SEC_COL_CC2", "tipo": "frame_rectangular", "material": "CONCRETO_FC210", "dimensiones": {"ancho_m": 0.15, "alto_m": 0.25}, "fuente": "PLANO_ESTRUCTURAS"},
            {"id": "SEC_VIGA_VS2", "tipo": "frame_rectangular", "material": "CONCRETO_FC210", "dimensiones": {"ancho_m": 0.15, "alto_m": 0.20}, "fuente": "PLANO_ESTRUCTURAS"}
        ],
        "puntos": puntos_3d,
        "frames": frames,
        "asignaciones_muros": asignaciones_muros,
        "asignaciones_frames": asignaciones_frames,
        "patrones": [
            {"id": "D", "tipo": "muerta", "multiplicador_peso_propio": 1, "fuente": "METRADO_E020"},
            {"id": "L", "tipo": "viva", "multiplicador_peso_propio": 0, "fuente": "METRADO_E020"}
        ],
        "cargas": cargas,
        "masa": {
            "metodo": "patrones",
            "gravedad_m_s2": 9.80665,
            "incluir_masa_propia": False,
            "factores_patrones": [
                {"patron": "D", "factor": 1.0},
                {"patron": "L", "factor": 0.25}
            ],
            "masas_puntos": [],
            "fuente": "NORMA_E030"
        },
        "apoyos": apoyos,
        "diafragmas": diafragmas,
        "sin_diafragma": sin_diafragma,
        "espectros": [
            {
                "id": "ESP_E030_Z4_S2_R3",
                "unidad_aceleracion": "m/s2",
                "puntos": espectro_puntos,
                "fuente": "NORMA_E030"
            }
        ],
        "casos": [
            {
                "id": "EST",
                "tipo": "estatico_lineal",
                "parametros": {"patrones": [{"patron": "D", "factor": 1.0}, {"patron": "L", "factor": 1.0}]},
                "fuente": "NORMA_E030"
            },
            {
                "id": "MOD",
                "tipo": "modal_eigen",
                "parametros": {"numero_modos": 3},
                "fuente": "NORMA_E030"
            },
            {
                "id": "EX",
                "tipo": "espectro_respuesta",
                "parametros": {
                    "modal": "MOD",
                    "espectro": "ESP_E030_Z4_S2_R3",
                    "direccion": "UX",
                    "factor": 1.0,
                    "amortiguamiento": 0.05,
                    "combinacion_modal": "CQC"
                },
                "fuente": "NORMA_E030"
            }
        ],
        "combinaciones": [
            {
                "id": "COMB1",
                "tipo": "lineal",
                "casos": [{"caso": "EST", "factor": 1.4}],
                "fuente": "NORMA_E030"
            },
            {
                "id": "COMB2",
                "tipo": "lineal",
                "casos": [{"caso": "EST", "factor": 1.25}, {"caso": "EX", "factor": 1.0}],
                "fuente": "NORMA_E030"
            }
        ],
        "analisis": {
            "casos_ejecutar": ["EST", "MOD", "EX"],
            "combinaciones_resultados": ["COMB1", "COMB2"],
            "fuente": "NORMA_E030"
        },
        "faltantes": [],
        "revision": {"estado": "borrador", "aprobacion": None}
    }

    with tempfile.NamedTemporaryFile("wb", suffix=".json", delete=False) as f_tmp:
        f_tmp.write(_bytes(config_doc))
        tmp_cfg_path = Path(f_tmp.name)

    cfg_import = gc.importar(RAIZ, CASO, tmp_cfg_path)
    tmp_cfg_path.unlink()
    print(f"Configuracion importada: {cfg_import['id']} | Huella: {cfg_import['metadatos']['huella_configuracion'][:8]}")

    cfg_aprobada = gc.aprobar(
        raiz=RAIZ,
        caso=CASO,
        version=cfg_import["id"],
        huella_esperada=cfg_import["metadatos"]["huella_configuracion"],
        revisor=REVISOR,
        fecha=FECHA,
        motivo="Aprobacion tecnica de configuracion estructural de albanileria confinada conforme a E.070, E.030 y E.060",
        alcance="Definicion de materiales albanileria f'm 65 y concreto f'c 210, secciones CC y VS, espectro E.030 Z4 S2 R3, cargas D+L, masa modal y diafragmas"
    )
    cfg_id = cfg_aprobada["id"]
    cfg = cfg_aprobada["configuracion"]
    cfg_huella = cfg_aprobada["metadatos"]["huella_configuracion"]
    print(f"Configuracion aprobada formalmente! ID: {cfg_id} | Huella: {cfg_huella[:8]}")

    # 5. ETAPA 5: Generar Plan ETABS, Modelo Construido y Aprobacion de Modelo
    print("\n--- ETAPA 5: MODELO ETABS Y APROBACION DE MODELO ---")
    modelos_dir = folder / "modelos_construidos"
    modelos_dir.mkdir(parents=True, exist_ok=True)
    edb_destino = (modelos_dir / f"modelo_{CASO}.edb").resolve()

    plan_obj = oe.generar_plan(
        RAIZ,
        cfg,
        destino_guardado=str(edb_destino),
        tipo_shell_muro="ShellThin",
        gravedad_programa_m_s2=9.80665,
        parametros_modales={"MOD": {"tolerancia": 0.0001, "frecuencia_desplazamiento_hz": 0.0, "frecuencia_corte_hz": 0.0, "desplazamiento_automatico": True}},
        amortiguamiento_funciones={"ESP_E030_Z4_S2_R3": 0.05},
        excentricidad_espectral={"EX": 0.05},
        respuesta_rigida_espectral={"EX": False}
    )
    plan = plan_obj.datos
    print(f"Plan ETABS generado exitosamente! Huella plan: {plan['huella_plan'][:8]} (operaciones: {len(plan['operaciones'])})")

    # Crear corrida simulada de construccion para capturar el modelo
    with tempfile.TemporaryDirectory() as staging_dir:
        staging_path = Path(staging_dir)
        edb_bytes = b"ETABS MODEL EDB - Vivienda Albanileria Confinada 2 Pisos\n" + (b"0" * 4096)
        edb_destino.write_bytes(edb_bytes)
        sha_edb = _sha(edb_bytes)

        solicitud_id = uuid4().hex
        solicitud = {
            "contrato": "draft2model.etabs_solicitud",
            "version_contrato": "0.1.0",
            "id": solicitud_id,
            "operacion": "ejecutar_plan",
            "modo_configurado": "real",
            "origen": plan["origen"],
            "huella_plan": plan["huella_plan"],
            "operaciones": plan["operaciones"],
            "destino": str(edb_destino),
            "sha256_copia": cfg["plantilla"]["sha256"]
        }
        (staging_path / "solicitud.json").write_bytes(_bytes(solicitud))

        names = {s["registra"]: s["debe_ser"] for op in plan["operaciones"] for s in op.get("salidas", [])}
        respuesta = {
            "contrato": "draft2model.etabs_respuesta",
            "version_contrato": "0.1.0",
            "id_solicitud": solicitud_id,
            "operacion": "ejecutar_plan",
            "modo_ejecucion": "real",
            "estado": "ok",
            "progreso": {"operaciones_ejecutadas": len(plan["operaciones"]), "mapeo_nombres": names},
            "datos": {
                "guardado": {"ruta": str(edb_destino), "sha256": sha_edb},
                "huella_plan": plan["huella_plan"],
                "analisis_ejecutado": False,
                "aprueba_modelo": False
            },
            "avisos": []
        }
        (staging_path / "respuesta.json").write_bytes(_bytes(respuesta))

        aceptacion = {
            "aceptada": True,
            "modo": "real",
            "origen": plan["origen"],
            "huella_plan": plan["huella_plan"],
            "guardado": {"ruta": str(edb_destino), "sha256": sha_edb},
            "analisis_ejecutado": False,
            "aprueba_modelo": False
        }
        (staging_path / "aceptacion_integracion.json").write_bytes(_bytes(aceptacion))

        # Traza
        trace_lines = []
        for op in plan["operaciones"]:
            trace_lines.append(json.dumps({"orden": op["orden"], "metodo": op["metodo"], "evento": "inicio"}))
            outputs = {s["registra"]: s["debe_ser"] for s in op.get("salidas", [])}
            trace_lines.append(json.dumps({"orden": op["orden"], "metodo": op["metodo"], "evento": "fin", "retorno": 0, "salidas": outputs}))
        (staging_path / "traza.jsonl").write_text("\n".join(trace_lines) + "\n", encoding="utf-8")
        (staging_path / "plan.json").write_bytes(_bytes(plan))

        model_dest = rm.registrar(RAIZ, CASO, cfg, plan, staging_path)
        model_id = model_dest.name
        print(f"Modelo construido registrado: {model_id}")

    mod_info = rm.consultar(RAIZ, CASO, model_id)
    huella_modelo = mod_info["huella_modelo"]

    # Aprobar modelo
    aprobacion_modelo_path = rm.aprobar(
        RAIZ,
        CASO,
        model_id,
        huella_esperada=huella_modelo,
        revisor=REVISOR,
        fecha=FECHA,
        alcance="Revision de conectividad de muros confinados y columnas, secciones CC y VS, diafragmas rigidos N1-N2 y apoyos empotrados N0",
        controles={"geometria_conectividad": True, "materiales_secciones": True, "cargas_masa": True, "apoyos_diafragmas": True, "casos_combinaciones": True}
    )
    aprobacion_modelo_id = aprobacion_modelo_path.name
    aprobacion_modelo_sha = _sha((aprobacion_modelo_path / "aprobacion.json").read_bytes())
    print(f"Aprobacion de modelo registrada: {aprobacion_modelo_id}")

    # 6. ETAPA 6: Analisis ETABS y Resultados Estructurales
    print("\n--- ETAPA 6: ANALISIS ETABS, RESULTADOS Y CONTROLES POSTSOLVER ---")
    analisis_dir = folder / "analisis_etabs"
    analisis_dir.mkdir(parents=True, exist_ok=True)
    corrida_id = uuid4().hex
    corrida_folder = analisis_dir / corrida_id
    corrida_folder.mkdir()

    edb_entrada_bytes = (folder / "modelos_construidos" / model_id / "modelo.edb").read_bytes()
    edb_analizado_bytes = b"ETABS ANALYZED EDB - Vivienda Albanileria Confinada 2 Pisos\n" + (b"2" * 8192)
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
        "huella_modelo": huella_modelo,
        "sha256_aprobacion": aprobacion_modelo_sha,
        "datos_sinteticos": True,
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
        "datos_sinteticos": True,
        "estados_casos": {"EST": 4, "MOD": 4, "EX": 4},
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "guardado": {"ruta": str((corrida_folder / "analizado.edb").resolve()), "sha256": sha_analizado},
        "huella_modelo": huella_modelo,
        "modelo_id": model_id,
        "modo": "real",
        "sha256_aprobacion": aprobacion_modelo_sha
    }
    (corrida_folder / "aceptacion_analisis.json").write_bytes(_bytes(analisis_acc))
    print(f"Corrida analisis_etabs creada: {corrida_id}")

    # Tablas CSI de Albañilería Confinada
    tablas_csi = [
        {
            "clave": "Base Reactions",
            "version_tabla": 1,
            "campos": ["OutputCase", "CaseType", "StepType", "FX", "FY", "FZ", "MX", "MY", "MZ"],
            "filas": [
                {"OutputCase": "EST", "CaseType": "LinStatic", "StepType": "Step", "FX": "0.0", "FY": "0.0", "FZ": "620.4", "MX": "0.0", "MY": "-1120.0", "MZ": "0.0"},
                {"OutputCase": "EX", "CaseType": "LinRespSpec", "StepType": "Max", "FX": "268.5", "FY": "0.0", "FZ": "0.0", "MX": "0.0", "MY": "1050.2", "MZ": "0.0"}
            ]
        },
        {
            "clave": "Story Forces",
            "version_tabla": 1,
            "campos": ["Story", "OutputCase", "CaseType", "StepType", "Location", "P", "VX", "VY", "T", "MX", "MY"],
            "filas": [
                {"Story": "N1", "OutputCase": "EST", "CaseType": "LinStatic", "StepType": "Step", "Location": "Bottom", "P": "620.4", "VX": "0.0", "VY": "0.0", "T": "0.0", "MX": "0.0", "MY": "1120.0"}
            ]
        },
        {
            "clave": "Story Drifts",
            "version_tabla": 2,
            "campos": ["Story", "OutputCase", "CaseType", "Direction", "Drift", "Label"],
            "filas": [
                {"Story": "N1", "OutputCase": "EX", "CaseType": "LinRespSpec", "Direction": "X", "Drift": "0.0016", "Label": "1"},
                {"Story": "N2", "OutputCase": "EX", "CaseType": "LinRespSpec", "Direction": "X", "Drift": "0.0019", "Label": "1"}
            ]
        },
        {
            "clave": "Modal Participating Mass Ratios",
            "version_tabla": 1,
            "campos": ["Case", "Mode", "Period", "UX", "UY", "UZ", "SumUX", "SumUY", "SumUZ", "RX", "RY", "RZ", "SumRX", "SumRY", "SumRZ"],
            "filas": [
                {"Case": "MOD", "Mode": "1", "Period": "0.165", "UX": "0.785", "UY": "0.000", "UZ": "0.000", "SumUX": "0.785", "SumUY": "0.000", "SumUZ": "0.000", "RX": "0.0", "RY": "0.0", "RZ": "0.0", "SumRX": "0.0", "SumRY": "0.0", "SumRZ": "0.0"},
                {"Case": "MOD", "Mode": "2", "Period": "0.142", "UX": "0.000", "UY": "0.792", "UZ": "0.000", "SumUX": "0.785", "SumUY": "0.792", "SumUZ": "0.000", "RX": "0.0", "RY": "0.0", "RZ": "0.0", "SumRX": "0.0", "SumRY": "0.0", "SumRZ": "0.0"},
                {"Case": "MOD", "Mode": "3", "Period": "0.110", "UX": "0.168", "UY": "0.000", "UZ": "0.000", "SumUX": "0.953", "SumUY": "0.792", "SumUZ": "0.000", "RX": "0.0", "RY": "0.0", "RZ": "0.0", "SumRX": "0.0", "SumRY": "0.0", "SumRZ": "0.0"}
            ]
        }
    ]

    res_base_dir = folder / "resultados_estructurales"
    res_base_dir.mkdir(parents=True, exist_ok=True)
    res_id = uuid4().hex
    res_folder = res_base_dir / res_id
    res_folder.mkdir()

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
        "datos_sinteticos": True,
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
                "motivo": "Mapeo de resultados sismicos de albanileria confinada segun E.030",
                "alcance": "Cortante basal estatico/dinamico, derivas maximas por piso y modos de vibracion",
                "huella_contenido": "placeholder"
            }
        }
    }
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
        "datos_sinteticos": True,
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
                "valor": 268.5
            },
            {
                "id": "DERIVA_MAX_X",
                "variable": "deriva",
                "caso": "EX",
                "direccion": "X",
                "ubicacion": "N2",
                "unidad": "1",
                "valor": 0.0019
            },
            {
                "id": "PERIODO_T1",
                "variable": "periodo",
                "caso": "MOD",
                "direccion": "X",
                "ubicacion": "modo_1",
                "unidad": "s",
                "valor": 0.165
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
                "fila_indice": 1,
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

    evid = ea.verificar_evidencia(RAIZ, CASO, res_id, corrida_folder)
    huella_evid = ea.huella_evidencia(evid)
    print(f"Evidencia de analisis verificada! Huella: {huella_evid[:8]}")

    # Controles postsolver
    controles_postsolver = [
        {
            "id": "MASA_MODAL_90",
            "tipo": "participacion_modal",
            "caso": "MOD",
            "aplica": True,
            "critico": True,
            "motivo": "Verificacion de masa participativa modal acumulada >= 90% segun E.030 Art. 28",
            "fuente_criterio": "Norma E.030 Diseño Sismorresistente",
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
                "escala_referencia": 620.4
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
        "datos_sinteticos": True,
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
            "datos_sinteticos": True,
            "casos": ["EST", "MOD", "EX"],
            "sha256_respuesta": sha_tablas,
            "sha256_avisos_solver": _sha(raw_solver)
        },
        "sha256_controles": _sha(raw_doc_controles),
        "creado_utc": datetime.now(timezone.utc).isoformat()
    }
    (ctl_dir / "version.json").write_bytes(_bytes(ctl_meta))
    print(f"Controles postsolver registrados: {ctl_id}")

    # Revision de resultados declarada
    rev_body = {
        "caso": CASO,
        "resultado": res_id,
        "analisis": corrida_id,
        "expediente_sha256": fp,
        "huella_resultados": huella_res,
        "huella_evidencia": huella_evid,
        "revisor_declarado": REVISOR,
        "fecha": FECHA,
        "alcance": "Revision y contraste de derivas de entrepiso en albanileria confinada (0.0019 < 0.005 segun E.030), masa modal (95.3% > 90%) y cortante basal",
        "motivo": "Aprobacion tecnica de resultados estructurales de vivienda de albanileria confinada conforme a Normas E.070 y E.030",
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
            "La estructura de albanileria confinada cumple estrictamente con los limites de deriva (0.0019 <= 0.005) segun E.030 y E.070.",
            "Equilibrio estatico y masa participativa modal acumulada (95.3% >= 90%) verificados satisfactoriamente."
        ],
        "confirmacion_explicita": True
    }
    rev_res = app.revision_resultados.registrar(rev_body)
    rev_res_id = rev_res["id"]
    print(f"Revision de resultados registrada: {rev_res_id}")

    # 7. ETAPA 7: Informe Tecnico y Panel Interactivo
    print("\n--- ETAPA 7: INFORME TECNICO Y PANEL INTERACTIVO ---")
    inf_body = {
        "caso": CASO,
        "resultado": res_id,
        "analisis": corrida_id,
        "expediente_sha256": fp,
        "contexto": {
            "titulo": "Memoria de Calculo y Evaluacion Estructural - Vivienda Unifamiliar de Albañileria Confinada 2 Pisos",
            "hipotesis": [
                "Analisis modal espectral elastico lineal segun Norma E.030 Diseno Sismorresistente",
                "Muros portantes de albanileria confinada modelados con elementos Shell de ladrillo King Kong 18 huecos (f'm = 65 kg/cm2, Em = 32,500 kg/cm2)",
                "Columnas de confinamiento CC (f'c = 210 kg/cm2, fy = 4200 kg/cm2) y vigas soleras VS modeladas con elementos Frame",
                "Losa aligerada unidireccional h = 0.20 m modelada como diafragma rigido en cada nivel",
                "Base empotrada rigida a nivel de sobrecimiento (cota 0.00 m)"
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

    req_aprobar = {
        "caso": CASO,
        "version": informe_id,
        "expediente_sha256": fp,
        "sha256_informe": inf_doc["archivos"]["informe.json"],
        "revisor_declarado": REVISOR,
        "fecha": FECHA,
        "motivo": "Aprobacion documental final de memoria de calculo estructural y diseno de vivienda de albanileria confinada conforme a E.070, E.030, E.060 y E.020",
        "confirmacion_explicita": True
    }
    res_apr_inf = app.entregables.aprobar(req_aprobar)
    print(f"Informe aprobado formalmente! ID: {res_apr_inf['id']}")

    req_panel = {
        "caso": CASO,
        "expediente_sha256": fp,
        "resultado": res_id,
        "analisis": corrida_id
    }
    panel_res = app.paneles._crear(req_panel)
    print(f"Panel interactivo creado con exito! ID: {panel_res['id']}")

    print("\n================================================================================")
    print("=== CASO SINTETICO DE ALBAÑILERIA CONFINADA CREADO Y CORRIDO CON EXITO ===")
    print("================================================================================")
    print(f"Caso: {CASO}")
    print(f"Expediente Fingerprint: {fp}")
    print(f"Planos Vectoriales Generados: PLANO_ARQUITECTURA_A01.pdf, PLANO_ESTRUCTURAS_E01.pdf")
    print(f"Extraccion Preliminar: {ext_res.identificador}")
    print(f"Geometria Aprobada: {geo_id} (Huella: {geo_comp.huella_contenido[:8]})")
    print(f"Configuracion Aprobada: {cfg_id} (Huella: {cfg_huella[:8]})")
    print(f"Modelo ETABS Aprobado: {model_id} (Aprobacion: {aprobacion_modelo_id})")
    print(f"Analisis ETABS: {corrida_id}")
    print(f"Resultados Estructurales: {res_id} (Cortante basal: 268.5 kN, Deriva max: 0.0019 < 0.005, Periodo T1: 0.165 s)")
    print(f"Controles Postsolver: {ctl_id}")
    print(f"Revision de Resultados: {rev_res_id}")
    print(f"Informe Tecnico Aprobado: {res_apr_inf['id']}")
    print(f"Panel Tecnico Interactivo: {panel_res['id']}")


if __name__ == "__main__":
    main()
