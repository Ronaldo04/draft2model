# seguimiento

## Overview
Sistema de trazabilidad, catálogo de hitos y panel de control de criterios técnicos cumplidos a lo largo del desarrollo de Draft2Model.

## Interface
- `hitos.json`: Registro estructurado de cada hito, criterio técnico exigido, estado de verificación y archivos fuente vinculados.
- `control.py`: Módulo CLI que evalúa programáticamente cada criterio de `hitos.json` contra los archivos reales de la distribución.
- `web/`: Panel visual en HTML/JS para consultar el estado del proyecto en el navegador.

## Invariants
- Esquema JSON estricto; cada criterio define sus `check_files` obligatorios.
- Evaluación determinista: si un archivo requerido falta en la distribución, el control reporta error.

## Side Effects
- Lectura de archivos de la distribución para verificación de integridad.

## Verification
- Evaluar cumplimiento de hitos:
  ```powershell
  python seguimiento/control.py
  ```
