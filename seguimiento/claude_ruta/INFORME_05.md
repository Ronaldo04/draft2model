# Etapa 05 — instalación limpia, regresiones y guía reproducible (ruta 201)

## Resultados

- **Instalación offline `tmp/instalacion_201`:** wheels fijados con hashes y sin red; 6 de 6 pasos correctos (entorno, instalación, `pip check`, arranque, demo y verificación de la demo).
- **Copia limpia `tmp/c201`** (primer intento, árbol de la etapa 04): 1162 pruebas con 4 fallos, 2 errores y 2 omisiones. Se conserva como antecedente. Causas y correcciones:
  - **Proveedores:** las pruebas de CLI y de la página esperaban Anthropic y la API compatible. Actualicé las expectativas a la política R202-03, solo Google y OpenAI.
  - **Explicaciones:** la prueba esperaba `clave_ausente`. La actualicé a la política vigente, `api_restringida_a_revision_planos`.
  - **Esquema de la tabla no uniforme:** no estaba registrado como observado. Lo registré en `ESQUEMAS_OBSERVADOS` con la evidencia real 185 (`tests/fixtures/tabla_no_uniforme_etabs21_185.json`, contrastada por la prueba) y lo añadí al script de vocabulario de solo lectura.
  - **Omisiones:** eran pruebas que dependían de evidencia en `tmp/`. Las trasladé a `scripts/verificar_evidencia_ruta201.py`, cuyo resultado actual es OK.
- **Copia limpia `tmp/c201b`:** `completa: true`; **1160 Python OK, 30 Node OK, 0 omisiones**; fuentes estables y sonda PowerShell `-File` OK.
- **Presupuestos de observación** (no relajan pruebas): suite 3000 s, interfaz 300 s y copia 3600 s. La suite tarda unos 730–770 s.
- **QA visual acotada** (navegador integrado, servidor local, expediente sintético `tmp/qa201` con configuración 0.5):
  - El selector de proveedor muestra solo openai y gemini.
  - El panel de malla 0.5 muestra el contrato y la aplicabilidad de líquidos, los recuentos, el corte Z con su motivo y fuente, los nodos `MC_*` con XYZ y «FALTA política», y los faltantes.
  - Las versiones aprobadas y en borrador se distinguen. No hubo errores de consola.
  - Ajuste aplicado: la redacción del estado ya aprobado.
- **Guía:** `docs/GUIA_REPRODUCIBLE.md` actualizada con la validación previa, la evidencia local, la sección de la ruta 201 (autoría 0.4/0.5, proyectos con y sin líquidos, construcción y lectura, recuperación sin reenvío, distinción entre simulación, nativo y piloto) y la evidencia vigente.

## Límites

- La QA visual es acotada (panel de malla y líquidos, y selector de proveedor); no hubo un recorrido visual completo de todas las pantallas.
- La copia limpia corre dentro del proyecto. Los avisos de rutas cercanas a 260 caracteres se documentan con la recomendación de usar una raíz corta, sin desactivar guardas.
- El piloto 04 sigue bloqueado: falta la segunda petición (Codex) y los datos técnicos.
