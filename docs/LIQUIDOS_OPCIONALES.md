# Cargas de líquido opcionales (cisterna o tanque): configuración 0.5 y plan 0.5

Estado al 21 de octubre de 2026 (ruta 201, etapa 02).

**Módulos:**
- [`modelo_estructural.py`](../draft2model/modelo_estructural.py) (`_ValidadorLiquidos`);
- [`liquidos_malla.py`](../draft2model/liquidos_malla.py);
- [`operaciones_etabs.py`](../draft2model/operaciones_etabs.py) (`generar_plan_malla` 0.4/0.5 y `validar_plan_liquidos`);
- [`verificacion_modelo_guardado.py`](../draft2model/verificacion_modelo_guardado.py) (categoría `cargas_liquidos`);
- [`scripts/ejecutar_plan_etabs.ps1`](../scripts/ejecutar_plan_etabs.ps1) (tabla editable).

**Pruebas:**
- [`test_liquidos_ruta201.py`](../tests/test_liquidos_ruta201.py);
- [`test_relectura_liquidos_ruta201.py`](../tests/test_relectura_liquidos_ruta201.py).

**Ensayo nativo:** [`scripts/ensayar_plan_liquidos.py`](../scripts/ensayar_plan_liquidos.py).

## Regla de aplicabilidad

Las viviendas o proyectos **sin** cisterna ni tanque funcionan sin módulo ni cargas de agua:
- **Configuración 0.4:** sigue igual y no conoce líquidos.
- **Configuración 0.5:** declara `liquidos.aplicabilidad` explícitamente.

| Aplicabilidad | Efecto |
|---|---|
| `ausente_confirmado` | No hay declaraciones, filas ni patrones ficticios. El plan 0.5 equivale al 0.4 con la ausencia registrada (fuente y motivo). |
| `informacion_insuficiente` | Faltante calculado `$.liquidos.aplicabilidad`: el borrador se puede importar y la aprobación queda bloqueada. **La falta de documentación no equivale a ausencia.** |
| `presente` | Una o más declaraciones revisadas, cada una `{declaracion, fuentes, patron}`. |

**Declaración presente:** `declaracion` usa el contrato `draft2model.acciones_liquidos` 0.1.0:
- nivel libre `h` y γ explícitos;
- superficies y `sentido_normal`;
- origen de momentos;
- revisión con fuentes revisadas.

Los valores no se asumen a partir del nombre del recipiente.

**Se rechazan:**
- una declaración inválida contra la geometría aprobada;
- un patrón con peso propio (duplicaría el peso) o no dedicado (con otras cargas);
- un patrón repetido entre declaraciones;
- una superficie cargada por dos declaraciones (conflicto que se debe declarar);
- **falta de corte explícito** (`cortes_nivel`) en un nivel libre que atraviesa una superficie cargada. Sin corte, ETABS dio 62,5 kN frente a 43,75 kN (ensayo 185); con corte, 43,75 kN (ensayo 186).

Declaraciones, patrones, cortes y fuentes forman parte de la huella de la configuración y de su aprobación: cambiar una fuente invalida la aprobación.

## Plan 0.5

`generar_plan_por_version` **regenera el plan entero**: partición, compatibilidad, triangulación, cortes y líquidos. El ejecutor y el registro exigen igualdad canónica con el plan recibido, así que una huella rehecha no basta.

1. **Verificación previa** (antes de cualquier mutación), con `GetAllFieldsInTable("Area Load Assignments - Non-uniform")`:
   - existen los campos `UniqueName, LoadPattern, Dir, A, B, C, D, Restriction` y son importables;
   - las descripciones nombran los textos usados («Global-X», «Gravity», «Zero Negative Values»…).
   - `Story` y `Label` son de solo lectura y **no** se reenvían.
2. **Edición de tabla `agregar`** (fase `cargas_liquidos`), una fila por triángulo y componente global: `p = γ·max(0, h − z)` como `A·x + B·y + C·z + D` con restricción de signo. Unidades: A, B y C en kN/m³; D en kN/m².
   - Se conservan las filas ajenas.
   - Si un objeto ya tiene filas, la colisión se rechaza.
   - Los errores o advertencias de `ApplyEditedTables` detienen la ejecución.
   - Se relee la tabla completa y se contrasta campo a campo antes de `cFile.Save`.
3. **Sección `liquidos`:**
   - aplicabilidad, declaraciones (huellas), patrones y filas;
   - por host: triángulos, fuerza y momento integrados sobre las piezas frente al contorno fuente menos huecos (≤ 1e-9 relativo, computacional), aberturas y cortes.
   - Las piezas secas se conservan como material (presión cero por restricción). No se rellenan huecos ni se crean pisos.

## Relectura (lector 0.4.0)

- **Inventario:** `edicion_tabla:Area Load Assignments - Non-uniform` → `cargas_liquidos`.
- **Comparación de filas:**
  - clave compuesta `(UniqueName, LoadPattern, Dir)`, solo en los patrones de líquido del plan; las filas ajenas se cuentan;
  - A, B, C y D con conversión dimensional (fuerza/longitud³ y fuerza/longitud²);
  - restricción comparada como texto exacto;
  - una fila faltante, extra o duplicada es una discrepancia.
- **Resultante:** se integra desde las **filas, coordenadas y contornos leídos** y se compara con la integral fuente. Una dirección proyectada o local, o una restricción no hidrostática, queda incompleta (no se reinterpreta).
- **No afirmado:** hidrodinámica, geotecnia, flotación ni equilibrio del solver.

## Uso

1. En la configuración 0.5, declara `liquidos` (y, si hay recipiente, sus patrones dedicados en `patrones` y los cortes en `cortes_nivel`).
2. Impórtala y revísala; luego consulta la preparación de malla para declarar la política de los nodos nuevos del corte.
3. Apruébala.

El plan, el ejecutor y el registro son los del recorrido normal (`generar_plan_por_version`, `ejecucion_modelo`).

## Límites

- **Presión estática:** no demuestra hidrodinámica, geotecnia ni flotación.
- **Masa del líquido:** no se modela como masa; solo como carga en un patrón dedicado.
- **Ensayos nativos:** ver la entrega de la etapa 02 (`entregas/02-*`), separados de los dobles.

## Resultados observados (21 de octubre de 2026)

Los resultados simulados y los nativos se informan por separado.

### Simulado (dobles; no prueba ETABS)

- `test_liquidos_ruta201` (9 pruebas) y `test_relectura_liquidos_ruta201` (4 pruebas) cubren los casos:
  - sin líquido (0.4 y 0.5 con ausencia confirmada);
  - información insuficiente como faltante;
  - muro con puerta parcialmente sumergido;
  - fondo;
  - inclinado con componentes X y Z;
  - dos recipientes con patrones distintos.
- Negativos de configuración: corte faltante, patrón duplicado, patrón con peso propio o no dedicado, superficie en dos declaraciones, aplicabilidad incoherente y fuente sin revisar.
- Plan alterado o con huella rehecha.
- Script PowerShell real contra un ETABSv1 falso con estado de tabla:
  - guarda y registra, conservando una fila ajena;
  - una colisión, un error de importación o una tabla releída distinta impiden `Save`.
- Lector: verificado en kN_m_C y N_mm_C. Una fila faltante, extra, duplicada, con signo, magnitud o restricción cambiados, o proyectada, da discrepancia; una tabla no leída queda incompleta.

### Nativo (ETABS 21.1 local, ensayo sintético `tmp/l2`, driver `scripts/ensayar_plan_liquidos.py`)

- **Construcción** por el recorrido normal 0.5:
  - 209 operaciones (22 filas de presión);
  - guardado con SHA `46c298c9…a2fa4`;
  - registro `25e0a61d…`;
  - cierre propio confirmado del PID 38952;
  - SHA de la plantilla original sin cambios.
- **Relectura independiente** (instancia nueva propia): `verificado`, 0 discrepancias y 0 incompletos, cobertura completa de malla y de líquidos. El EDB se reabre en N_mm_C y se normaliza.
- **Análisis** con aprobación sintética declarada «solo software»:
  - la primera corrida quedó fuera del grupo controlado (`an/`) por un error del driver y se conserva como antecedente;
  - la corrida controlada `analisis_etabs/f3e7586f…` terminó con casos en estado 4.
- **Lectura de Base Reactions de CHIDRO:**
  - Primer intento: se detuvo en la guarda de unidades (el EDB reabre en N_mm_C). La instancia propia se cerró con `ApplicationExit = 0` según la traza, y la incertidumbre se resolvió con evidencia mediante `confirmar_recuperacion`.
  - Corrección: `leer_analisis_etabs.ps1` fija unidades de presentación kN_m_C, como ya hacía `analizar_modelo_etabs.ps1`.
  - Lectura nueva: FX = −53,8 kN frente a 53,8 aplicados; MY = −25,5933 y MZ = 135,725 kN·m frente a 25,59333 y −135,725.
  - **Tabla de visualización** (6 cifras): MY = −25,5933 frente a −25,593333…; residuo 3,3e-5.
    - Es compatible con el redondeo de la tabla (≤ 5e-5).
    - **No** cumple el criterio estricto (umbral 1e-7 relativo a max(1, |valor|)), y esta lectura **no** demuestra el equilibrio interno (revisión Codex R208-01). Se conserva como fallo del criterio estricto.
  - **Lectura tipada `cAnalysisResults.BaseReact`** (dobles como texto `R` invariante), sobre la **misma corrida** `f3e7586f…` y sin reanalizar:
    - punto de reacción (0, 0, 0) en kN_m_C;
    - FX = −53,799999999999535;
    - MY = −25,593333333332723 y MZ = 135,7249999999993;
    - residuos ≤ 6,9e-13 → **equilibrio estricto** (umbral computacional 1e-7, no tolerancia de ingeniería).
  - **Resultado global del driver:** aceptado, con código de salida 0. Desde R207-01, el driver devuelve un código no cero si falla una fase obligatoria o el equilibrio estricto.
