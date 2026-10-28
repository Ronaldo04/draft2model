# Informe Claude — relectura de malla 196

Fecha: 21 de octubre de 2026. Carpeta verificada: `.../AECODE AI TALENT/PROYECTO FINAL`. Guía: [docs/RELECTURA_MALLA_ETABS.md](../docs/RELECTURA_MALLA_ETABS.md).

## Cambios

- **`draft2model/verificacion_modelo_guardado.py`** (hash previo `91b68901…`, con los arreglos de Codex):
  - `_expectativa_malla`: solo para planes 0.4, con rechazo de expectativas incoherentes.
  - Categoría `malla` en `_Comparador`:
    - área neta por host desde lo leído frente a la fuente;
    - orientación;
    - aristas dirigidas únicas y ausencia de nodos colgantes;
    - nodos compartidos entre hosts;
    - cadena colineal de subframes;
    - conservación de fuerza y momento con cargas, áreas y longitudes leídas.
  - En el resultado, `malla`, `alcance` y `controles_no_afirmados` solo se amplían en 0.4.
  - **Conservado de Codex:** `contorno_orientado_igual`, `carga_vertical_global` y los bytes crudos de la lectura.
  - **Sin cambios en el legado 0.1 a 0.3:** pruebas existentes en verde.
- **`scripts/verificar_modelo_guardado.ps1`:** sin cambios (`e44676be…`). El lector ya devuelve todo lo necesario.
- **Docs:** se añade una sección 0.4 a `docs/VERIFICACION_MODELO_GUARDADO.md` y se crea `docs/RELECTURA_MALLA_ETABS.md`.
- **Pruebas:** se crea `tests/test_relectura_malla.py` (12 pruebas).

## Hallazgos durante el trabajo

- **Plan real 194** (`tmp/n194/plan.json`, sha `6057be56…`, solo lectura): 294 operaciones, de ellas 136 comprobadas y 158 lecturas excluidas. Las 4 relecturas nuevas del plan no se confunden con mutaciones, y hay **0 operaciones sin lector**.
- **Falsa discrepancia corregida:** un triángulo no legible producía una discrepancia falsa de «nodo compartido». Ahora queda incompleto mientras algún host no se haya leído completo.
- **Partes de conservación:** se validan contra todas las operaciones `$.cargas.<id>@`, de modo que omitir una parte se detecta.

## Comandos y resultados

Con TEMP y TMP en `tmp/claude_relectura_196`. Log: `tmp/claude_relectura_196/pruebas.log`.

- `.venv/Scripts/python.exe -m unittest -v tests.test_relectura_malla tests.test_verificacion_modelo_guardado tests.test_contorno_nativo tests.test_relectura_representaciones_csi tests.test_relectura_presion tests.test_vinculo_verificacion_modelo tests.test_revision_verificacion_modelo tests.test_revision_verificacion_modelo_http tests.test_informe_relectura_modelo` → **75 OK, 0 omitidas, código 0**.
- Esto incluye el script PowerShell real contra un ETABSv1 falso que reabre un EDB JSON persistido. Es un doble: no acredita ETABS.

## Límites

- **No ejecutado:**
  - ETABS real;
  - la reapertura del EDB 194;
  - el solver;
  - la suite global.

  No toqué PID, instancias ni registros previos.
- **No afirmado:** masa propia por elemento (sin getter), calidad y rigidez de malla, y efecto estructural del diafragma.
- **Pendiente para Codex:**
  - el ensayo nativo de relectura;
  - presentar `r["malla"]` y `cobertura.malla` en servicio, UI e informe.
