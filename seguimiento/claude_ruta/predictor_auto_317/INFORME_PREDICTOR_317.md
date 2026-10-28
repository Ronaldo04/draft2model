# Predictor 317: candidato puro de offsets Auto y descuento de peso de vigas

Candidato aislado; no integrado. Sin ETABS ni APIs. No modifica el libro, las tolerancias ni los informes históricos. 313–316 son de solo lectura.

**Exposición previa declarada:** la regla se construyó conociendo 313/314 (patrones del piloto) y 315/316 (ensayos sintéticos). No es un ensayo ciego, y el sello `SELLO_PREDICCION_317.sha256` acredita integridad, no cronología.

## Contrato

`predecir(plan, config)` es puro: no abre archivos (comprobado por una prueba estática). `config` es explícita:
- `etabs_version`: solo "21.1.0";
- `unidades`: solo "kN_m_C";
- `tolerancia_union_m`: finita y > 0;
- `procedencia_tolerancia`: `configuracion_verificada` o `escenario_declarado`;
- `vigas` (lista o None, que significa todas las horizontales).

Una configuración inválida o ausente produce `abstencion_global`.

## Regla y procedencia por parte

- **Documental** (ayuda ETABS): solo columnas inferiores; columnas superiores y otras vigas aportan 0.
- **Experimental 315** (sintético): distancia a la cara a lo largo del eje de la viga según los ejes locales de la columna, solo con ángulos múltiplos de 90° y vigas alineadas con esos ejes; muro sin columna da 0, con salvedad (un solo caso).
- **Experimental 315/316**, cuando la suma de offsets es ≥ L:
  - con contribución en ambos extremos, 0/0;
  - con contribución en un solo extremo, L − 2·tol, solo con tol ∈ {0,001; 0,005} ensayadas y L − 2·tol > 0.
- **Experimental 278:** descuento de peso = (oi + oj)·T3·T2·γ, con γ de `SetWeightAndMass` (opción 1).
- **Abstenciones con motivo:**
  - columna con inserción;
  - ejes avanzados;
  - ángulo no múltiplo de 90°;
  - viga oblicua;
  - sección ausente o no rectangular;
  - frame inclinado conectado;
  - viga no horizontal;
  - longitud nula, coordenadas no finitas o frame duplicado;
  - tolerancia no ensayada en el caso de exceso;
  - zona límite (longitud libre entre 0 y 2·tol).
- Totales **solo** si todas las vigas pedidas tienen offsets y descuento.

## Pruebas

`test_predictor_auto_317.py`: 8 pruebas sintéticas.
- Varían dimensiones, orientación (0/90°), conectividad (columna superior, otra viga, muro), longitudes y tolerancia (0,001 y 0,005; 0,003 lleva a abstención).
- Cubren: exceso en uno y en ambos extremos, zona límite, L − 2·tol ≤ 0, versión/unidades/tolerancia inválidas, configuración ausente, valores no finitos, duplicados, inserción, ejes avanzados, 45°, sección ausente, diagonal conectada, viga oblicua, totales con cobertura incompleta e independencia estática (sin `open(`, nombres del piloto ni la constante 0,002).

## Piloto (escenario declarado de tolerancia 0,001 m; el plan no declara `SetMergeTol`)

- Predicción (`PREDICCION_PILOTO_317.json`, sellada antes del contraste): 45/45 vigas con offsets y descuento, sin abstenciones. Offsets 6,353 m y descuento 6,86124 kN.
- Contraste separado (`CONTRASTE_PILOTO_317.json`, lectura nativa `6da62ea3…`): **90/90 extremos de acuerdo**, error máximo 4,6·10⁻¹⁶ m.
- Peso VS neto predicho 24,25572 kN frente a 24,2557 kN de la tabla nativa (4 decimales).
- **Esto no hace coherente la masa oficial:**
  - la tolerancia del piloto no está verificada (Codex debe confirmarla en la plantilla o el modelo);
  - el residuo de CM de 0,006877 kN (313) queda fuera de las VS y sigue sin atribuir;
  - el libro sigue `no_coherente`.

## Interfaz propuesta para `libro_masa` (sin alterar el cálculo bruto histórico)

- Añadir, junto al libro bruto, un bloque opcional `descuento_offsets_auto` con:
  - `predecir(plan, config)` y su versión;
  - la `config` completa con la procedencia de la tolerancia;
  - la cobertura;
  - el estado por viga (offsets, regla, procedencias, salvedades, abstención);
  - totales solo si la cobertura es completa.
- El consumidor presenta «bruto», «descuento predicho» y «neto predicho» como columnas separadas. Con cualquier abstención, o con tolerancia en `escenario_declarado`, el neto se marca **no verificado** y no sustituye al bruto ni al contraste nativo.
- Campos que necesita el consumidor: versión de ETABS y unidades (del plan o la configuración), tolerancia de unión verificada (del plan, la plantilla o una lectura nativa de configuración), opción SelfWtOpt/OffsetOpt esperada (Auto) y la lista de vigas a considerar.

## Límites

- Afirmación empírica restringida a ETABS 21.1.0, kN-m, secciones rectangulares, columnas verticales, ángulos de 0/90° y vigas alineadas.
- Dos tolerancias ensayadas.
- Un único caso de muro.
- No se integra ni aprueba masa o ingeniería.
