"""Contrasta las constantes de normativa_e030.py y normativa_rne.py con los textos oficiales registrados por Codex.

Uso: python scripts/verificar_normativa_e030.py [--texto seguimiento/normativa_229/E030_RM183_2026.txt]
Normaliza espacios y ligaduras del PDF (ﬁ) y busca, para cada valor, el fragmento literal de su tabla/artículo.
Devuelve 0 solo si todos los fragmentos aparecen. No interpreta la norma: confirma transcripción.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
from draft2model import normativa_e030 as n  # noqa: E402

# (constante, fragmento literal esperado en el texto, artículo/tabla)
FRAGMENTOS = [
    ("Z zona 4..1", "Zona Z 4 0,45 3 0,35 2 0,25 1 0,10", "Art. 11, Tabla N° 1"),
    ("Lima, todos los distritos: zona 4", "LIMA ANCÓN 4 TODOS LOS DISTRITOS", "Anexo de zonificación"),
    ("Pueblo Libre en la provincia de Lima", "PACHACÁMAC PUCUSANA PUEBLO LIBRE PUENTE PIEDRA", "Anexo de zonificación"),
    ("S zona 4", "Z4 0,80 1,00 1,00 – 1,10 1,10 – 1,20", "Art. 17, Tabla N° 4"),
    ("TP", "TP (s) 0,3 0,4 0,4 – 0,6 0,6 – 0,9 1,2", "Art. 17, Tabla N° 5"),
    ("TL", "TL (s) 3,0 2,5 2,5 – 2,0 2,0 – 1,6 1,6", "Art. 17, Tabla N° 5"),
    ("Regla sin Vs30", "TP = 0,6 s y TL = 2,0 s para suelos S2 y TP = 0,9 s y TL = 1,60 s para suelos S3", "Art. 17, nota"),
    ("U categoría C", "Edificaciones comunes tales como: viviendas, oficinas, hoteles, restaurantes, depósitos e instalaciones industriales cuya falla no acarree peligros adicionales de incendios o fugas de contaminantes. 1,0", "Art. 19, Tabla N° 7"),
    ("R0 albañilería", "Albañilería Armada o Confinada 3", "Art. 22, Tabla N° 10"),
    ("R0 concreto", "Concreto Armado: Pórticos 8 Dual 7 De muros estructurales 6 Muros de ductilidad limitada 3.5", "Art. 22, Tabla N° 10"),
    ("R = R0·Ia·Ip", "R = R0 · Ia · Ip", "Art. 26"),
    ("C = 2,5 estático hasta TP", "se debe usar un valor de C igual a 2,5 en todo el rango", "Art. 18.3"),
    ("Desplazamientos 0,75R / 0,85R", "multiplicando por 0,75 R", "Art. 50.1"),
    ("Desplazamientos irregulares", "multiplicando por 0,85 R", "Art. 50.2"),
    ("Distorsión", "Concreto armado 0,007 Acero 0,010 Albañilería 0,005 Madera 0,010", "Art. 51, Tabla N° 14"),
    ("Cortante mínimo", "no debe ser menor que el 80% del valor calculado", "Art. 44.1"),
    ("Excentricidad", "igual a 0,05 veces la dimensión del", "Art. 45"),
    ("Peso sísmico C 25 %", "En edificaciones de la categoría C, se toma el 25% de la carga viva", "Art. 31.b"),
    ("Peso sísmico tanques 100 %", "En estructuras de tanques, silos y estructuras similares se considera el 100% de la carga que puede contener", "Art. 31.e"),
    ("C/R mínimo", "34.2. El valor de C/R debe cumplir con", "Art. 34.2"),
    ("CT = 60 albañilería", "CT = 60 Para edificios de albañilería", "Art. 36.1"),
    ("Vs30 S2", "S2 ≥ 350 m/s a < 550 m/s", "Art. 14.7, Tabla N° 3"),
    ("Vs30 S3", "S3 ≥ 200 m/s a < 350 m/s", "Art. 14.7, Tabla N° 3"),
    ("Interpolación lineal por Vs30", "deben definirse interpolando linealmente entre los extremos del intervalo en función de las velocidades de ondas de corte", "Art. 17, nota de Tablas 4 y 5"),
]
# Otros textos (E.060 y E.020); E.070 24.7 es imagen: verificación visual en la p. 21 (registrada en el informe 08).
OTROS = [
    ("E060_DS010_2009.txt", "Ec 4700 √f'c", "4700 Ec f c (en MPa) (8-3)", "E.060 8.5.2"),
    ("E060_DS010_2009.txt", "G = Ec/2,3", "2,3 Ec G", "E.060 8.5.4"),
    ("E020_DS011_2006.txt", "Vivienda 2,0 kPa", "Viviendas 2,0 (200)", "E.020 Tabla 1"),
    ("E020_DS011_2006.txt", "Agua dulce 10 kN/m3", "Agua dulce 10,0 (1000)", "E.020 Anexo 1"),
    ("E020_DS011_2006.txt", "Concreto armado = simple + 1", "Concreto Armado Añadir 1,0 (100) al peso del concreto simple", "E.020 Anexo 1"),
    ("E020_DS011_2006.txt", "Albañilería cocida sólida 18 kN/m3", "Unidades de albañilería cocida sólidas 18,0 (1800)", "E.020 Anexo 1"),
    ("E020_DS011_2006.txt", "Albañilería cocida hueca 13,5 kN/m3", "Unidades de albañilería cocida huecas 13,5 (1350)", "E.020 Anexo 1"),
    ("E020_DS011_2006.txt", "Aligerado 0,17 → 2,8 kPa", "0,17 0,05 2,8 (280)", "E.020 Anexo 1"),
]


def _normal(texto: str) -> str:
    texto = texto.replace("ﬁ ", "fi").replace("ﬁ", "fi").replace("ﬂ ", "fl").replace("ﬂ", "fl")
    texto = re.sub("[-]", " ", texto)  # glifos de uso privado del PDF (′, =) en fórmulas
    return re.sub(r"\s+", " ", texto)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--texto", type=Path, default=RAIZ / "seguimiento/normativa_229/E030_RM183_2026.txt")
    a = ap.parse_args(argv)
    raw = a.texto.read_bytes()
    texto = _normal(raw.decode("utf-8", errors="replace"))
    resultados = [{"constante": c, "referencia": r, "encontrado": _normal(f) in texto} for c, f, r in FRAGMENTOS]
    huellas = {a.texto.name: hashlib.sha256(raw).hexdigest()}
    for archivo, c, f, r in OTROS:
        otro = a.texto.parent / archivo
        bruto = otro.read_bytes()
        huellas[archivo] = hashlib.sha256(bruto).hexdigest()
        resultados.append({"constante": c, "referencia": r, "encontrado": _normal(f) in _normal(bruto.decode("utf-8", errors="replace"))})
    salida = {"texto": a.texto.as_posix(), "sha256": hashlib.sha256(raw).hexdigest(), "huellas": huellas, "norma": n.NORMA,
              "resultados": resultados, "correcto": all(x["encontrado"] for x in resultados)}
    print(json.dumps(salida, ensure_ascii=False, indent=2))
    return 0 if salida["correcto"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
