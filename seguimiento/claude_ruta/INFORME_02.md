# Etapa 02 — cargas hidrostáticas opcionales de extremo a extremo (ruta 201)

## Implementado

- **Configuración 0.5** (`modelo_estructural._ValidadorLiquidos`): `liquidos.aplicabilidad` con tres valores.
  - `ausente_confirmado`: el proyecto sin cisterna ni tanque funciona sin cargas de agua ni ceros ficticios. La 0.4 sigue intacta.
  - `informacion_insuficiente`: faltante que bloquea la aprobación (no equivale a ausencia).
  - `presente`: declaraciones revisadas con patrón dedicado (sin peso propio ni otras cargas, sin repetirse) y sin superficies en conflicto. Exige corte explícito en cada nivel libre que atraviese una superficie.
- **`liquidos_malla.preparar_liquidos`**: filas por triángulo y componente, y conservación de fuerza y momento frente al contorno neto (≤ 1e-9). Admite varios recipientes.
- **Plan 0.5** (`generar_plan_malla` 0.4/0.5 y `validar_plan_liquidos`):
  - verificación previa del esquema nativo, antes de mutar;
  - edición `agregar` de `Area Load Assignments - Non-uniform`, sin Story ni Label;
  - sección `liquidos`;
  - despacho por versión en ejecutor, ejecución, revisión y gestión;
  - estado visible en la UI.
- **Puente PS1:** tabla editable añadida.
- **`leer_analisis_etabs.ps1`:**
  - unidades de presentación kN_m_C al reabrir (el EDB reabre en N_mm_C);
  - `resultados_api` opcional con `BaseReact` tipado (R208-01), validado en `lectura_analisis.py`.
- **Lector 0.4.0:** categoría `cargas_liquidos`, con filas por clave compuesta y unidades, y resultante integrada desde lo leído. Si la restricción no es hidrostática, queda incompleto en lugar de fallar.
- **Driver `scripts/ensayar_plan_liquidos.py`** (sintético, ETABS local):
  - fases con estado propio;
  - resultado global explícito y código no cero si falla una fase obligatoria o el equilibrio estricto (R207-01);
  - modos `--reanudar-analisis` y `--leer`.
- **Documentación:** `docs/LIQUIDOS_OPCIONALES.md` y `docs/LECTURA_ANALISIS.md` (unidades y `resultados_api`).

## Resultados simulados (dobles; no prueban ETABS)

- **Regresión de 27 módulos** (`etapa02_pruebas.log`): 209 OK, 0 omitidas; 3 scripts Node OK.
- **Batería de cierre** (`etapa02_cierre.log`, sobre el árbol final de la etapa): 90 OK, 0 omitidas. Cubre:
  - `test_reacciones_api_ruta201`;
  - lectura de análisis y web;
  - líquidos;
  - relectura de líquidos y de malla;
  - verificación;
  - `ScriptEstaticoTests`.

## Resultados nativos (ETABS 21.1 local, ensayo sintético `tmp/l2`)

1. **Construcción** por el recorrido normal 0.5:
   - 209 operaciones (22 filas de presión);
   - EDB `46c298c9…a2fa4`;
   - registro `25e0a61d…`;
   - cierre propio confirmado del PID 38952;
   - plantilla original intacta.
2. **Relectura independiente:** verificada, 0 discrepancias y 0 incompletos, malla y líquidos completos.
3. **Análisis:**
   - la corrida `an/b7c7159d…` quedó fuera del grupo controlado por un error del driver y se conserva como antecedente (Codex R207-02);
   - la corrida controlada `analisis_etabs/f3e7586f…` terminó con casos en estado 4.
4. **Lectura de Base Reactions:**
   - **Intento 1:** se detuvo en la guarda de unidades. La instancia propia se cerró con `ApplicationExit = 0` según la traza, y la incertidumbre se resolvió con evidencia (`evid02/recuperacion_lectura_dde566db.json`).
   - **Tabla de visualización:** residuo MY = 3,3e-5. Es compatible con el redondeo de 6 cifras, pero **no cumple el criterio estricto** (R208-01). Se conserva.
   - **`BaseReact` tipado** sobre la misma corrida, sin reanalizar: residuos ≤ 6,9e-13 → **equilibrio estricto**. Resultado global del driver: aceptado, código 0.

## Límites

- La presión estática no demuestra hidrodinámica, geotecnia ni flotación; tampoco se modela la masa del líquido.
- Son datos sintéticos; no hay aprobación de ingeniería.
- La aprobación del modelo para el análisis es sintética y declarada («solo software»).
- No hubo QA visual en navegador en esta etapa.
