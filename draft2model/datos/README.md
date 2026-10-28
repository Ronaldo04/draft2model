# draft2model.datos

## Overview
Contiene los conjuntos de datos estáticos, tablas normativas y esquemas de referencia requeridos por el motor de análisis y la interfaz de usuario. En particular, almacena los coeficientes y factores sísmicos distritales de la Norma Técnica Peruana E.030 (Diseño Sismorresistente).

## Interface
- `anexo_ii_e030_2026.json`: Diccionario geográfico y normativo con parámetros sísmicos (Zonas sísmicas Z, factores de suelo S, períodos de suelo TP/TL, y factor de amplificación sísmica) indexados por departamento, provincia y distrito del Perú.

## Invariants
- Codificación estricta en UTF-8.
- Estructura JSON determinista y de sólo lectura.
- Búsqueda insensible a mayúsculas y acentos normalizada para nombres de distritos peruanos.

## Side Effects
- Ninguno (acceso exclusivo de lectura en memoria durante la evaluación sismorresistente).

## Verification
- Ejecutar: `python -m draft2model.normativa_e030`
