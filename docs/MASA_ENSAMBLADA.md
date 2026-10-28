# Validador puro de masa ensamblada - 254

Biblioteca pura incorporada por Codex como archivo nuevo `draft2model/masa_ensamblada.py`, sin modificar los archivos que Claude integra. No importa ETABS, no abre archivos, no usa red y no ejecuta análisis. Únicamente las pruebas leen el fixture histórico local en `tests/fixtures/masa_ensamblada_253f/`.

## Contrato de entrada

```python
validate_assembled_joint_mass(
    raw, observations,
    units="kN_m_C",
    expected_source="MsSrc1",
    expected_mass=masa_total_de_la_fuente,
    absolute_mass_tolerance=tolerancia_absoluta_explicita,
    axes_tolerance_deg=1e-9,
)
```

Todos los argumentos de criterio son explícitos. Las unidades deben ser `kN_m_C` en el argumento, en raw y en observations; no hay conversión implícita desde N/mm. La masa está en kN·s²/m y las coordenadas en m.

**expected_mass significa el total completo de la fuente seleccionada.** Si MsSrc1 incluye peso propio, D, L y agua, el caller debe calcular el ledger completo o aislar la contribución mediante un control aparte. No comparar el total mezclado con solo el agua. El validador no deduce patrones, factores, g ni composición de la fuente a partir de su nombre o del total. Tampoco obtiene g ajustando masa observada. El nombre esperado es obligatorio y debe coincidir exactamente: una fuente única no basta para identificarla.

`raw` contiene:

- `capture_id`: identidad de la captura establecida por el lector.
- `units`: `kN_m_C`.
- `return_code`: entero exactamente 0, nunca bool.
- `number_results`: entero N positivo, nunca bool/float/string.
- Ocho arrays: `point_elements`, `mass_sources`, `U1`, `U2`, `U3`, `R1`, `R2`, `R3`.

Cada array puede tener exactamente N o N+1 elementos. Solo se admite **una cola neutral demostrada**: None o cadena vacía para identificadores; cero numérico finito para componentes. False, None numérico, NaN o una segunda cola se rechazan. La biblioteca valida antes de retirar la cola y declara cuáles arrays la tenían; nunca recorta valores no neutros.

`observations` contiene el mismo `capture_id`, las mismas unidades y N filas. Cada fila debe tener:

- `point_element` y `mass_source`, ligados a un par único existente en raw.
- Los seis componentes U1/U2/U3/R1/R2/R3, iguales a esa fila cruda por identidad.
- `global_xyz` y `point_axes_deg`, triples numéricos finitos.

La ligadura es por **(fuente, PointElm)**, no por posición de lista. Se permite distinto orden, pero no otro conjunto de identidades, duplicados, filas sobrantes o faltantes. Repetir los seis componentes y capture_id impide mezclar inadvertidamente otra lectura de masas con las coordenadas de esta captura. El caller sigue siendo responsable de que las coordenadas/ejes provengan realmente de esa identidad y de esa captura; una etiqueta suministrada no constituye una firma criptográfica ni prueba de ejecución.

## Validación y salida

- Una fuente única, no vacía, igual a expected_source.
- Componentes finitos, numéricos y no negativos, sin clamping de valores negativos pequeños ni aceptación de bool como número.
- Ejes canónicos Global alrededor de cero. Tolerancia angular explícita entre 0 y 1e-6 grados; no se transforma masa de ejes rotados.
- Totales U1 y U2 comparados **por separado** con expected_mass y tolerancia absoluta. Masa parcial en cualquiera de ellos falla.
- Centroides observables calculados por separado con pesos U1 y U2. No se supone que sus distribuciones coincidan. Si el total de una dirección es exactamente cero, su centroide es None.
- U3 se suma como observación, sin exigir equivalencia a masa lateral; las opciones de masa vertical quedan fuera de este contrato.
- `MassSummary` es inmutable y conserva filas, fuente real, unidades, arrays con cola, masas observadas, centroides y `declared_expected_mass` separado.

La salida siempre declara `native_execution_verified=False` y scope `observed_payload_consistency_only_not_native_execution_or_EDB_verification`. **No aprueba ingeniería, no verifica un EDB, no acredita un nuevo ensayo ni hace el piloto ejecutable.** Un retornoAPI0 suministrado y un JSON consistente no prueban por sí solos ejecución real.

N=0 genera `MassValidationError(code="EMPTY_RESULT")`: diagnóstico vacío, nunca éxito aun cuando expected_mass=0. Si un flujo superior dispone de evidencia externa de una ejecución vacía, debe evaluarla fuera de esta API. El baseline253f sí contiene N=14 observaciones explícitas de masa cero y se valida como payload, manteniendo el límite de evidencia anterior.

Los demás errores tienen código estable, por ejemplo NONNEUTRAL_PADDING, ARRAY_LENGTH, MULTIPLE_SOURCES, SOURCE_MISMATCH, DUPLICATE_RAW_ROW, CAPTURE_MISMATCH, UNLINKED_OBSERVATION, MASS_OBSERVATION_MISMATCH, ROTATED_AXES y MASS_TOTAL. No se corrigen los datos en silencio.

## Fixture y trazabilidad

`fixtures/extracto_sintetico_253f.json` es un extracto del ensayo sintético **ya existente** `tmp/ensayo_masa_contenido_251/runs/codex253f/registro.json`. No es una nueva ejecución ni el caso real.

- SHA del recibo fuente: `e0b76392a71c49e10dc0911d0f7e4bb37d37153415807b679d1c955ff5ac8dd0`.
- SHA del fixture copiado: `96b17ec8e2d09b1a77a44692cd9f7b9e16f1f7fb283fa802dc8bc40b20a2d425`.
- El manifest conserva ambas huellas y las pruebas verifican el fixture local.
- Arrays y filas originales se mantienen; el adaptador agrega units, return_code e identidad `SHA:control:mass_reads[i]` desde el recibo y su orden de lecturas API. Las lecturas AssembledJointMass_1 del recibo tienen retorno0.
- Los expected_mass de los tres controles provienen de 2×2.15×2.22×10/g y factores0/.25/1, con g desde la calibración W/M del material no asignado. Esa fuente fue aislada por diseño del ensayo253; no generalizar el oracle del agua a una fuente D+L+agua.
- Observados: 0, 2.433552692738806 y 9.734210770955224 kN·s²/m, centroide del plano de fondo(1,1.075,3)m cuando hay masa positiva. No es el centro de volumen real del aguaZ4.11 ni valida hidrodinámica.

## Pruebas offline

Desde la raíz del workspace:

```text
python -B -m unittest tests.test_masa_ensamblada -v
```

**29 pruebas OK**, incluidos múltiples subcasos negativos: padding no neutro y tipo inválido, doble padding, fuentes múltiples y única inesperada, duplicados, ejes rotados, NaN/infinito/bool/string, tamaños/N inválidos y N=0, masa parcial X/Y, unidades incompatibles, captura distinta, ligadura por identidad, coordenadas/ejes inválidos, overflow y conservación de entradas. También se verifican los tres controles del fixture histórico, sus hashes y la ausencia de atribución de ejecución/EDB.

Módulo, pruebas, fixture y manifest portados tras revisión de Codex; sus consumidores siguen pendientes. No hay runner API ni integración con contratos/CLI/plan/lector del producto.

## Integración en el flujo general (263)

1. **Captura nativa.**
   - `scripts/leer_analisis_etabs.ps1` admite `resultados_api` con `AssembledJointMass` (sola o junto a `BaseReact`).
   - En la misma instancia nueva que lee las tablas del EDB analizado (huella comprobada), el script llama a
     `Results.AssembledJointMass_1('', 'ALL', GroupElm)`.
   - Conserva los ocho arrays crudos completos, incluida la cola, como texto `R`. Añade por punto `PointElm.GetCoordCartesian` y
     `GetLocalAxes`.
   - `lectura_analisis._validar_masa_api` comprueba la forma: N/N+1, observaciones = N y unidades. La coherencia no se decide aquí.
2. **Libro de contribuciones** (`draft2model/libro_masa.py`). Se calcula desde la configuración aprobada, la geometría y la malla
   vigentes, más los líquidos:
   - peso propio de shells (área de malla × espesor × γ) y de frames (longitud × área × γ), a través del multiplicador de peso
     propio de los patrones de la fuente;
   - cargas de superficie, frame y punto (componente −Z × factor);
   - Fz de las presiones de líquido por patrón.
   El libro no ajusta nada a la respuesta.
3. **Contraste.**
   - `libro_masa.contrastar_masa_nativa` convierte la captura al formato de este validador y llama a `validate_assembled_joint_mass`.
   - Usa una fuente esperada explícita (`MsSrc1`, la fuente por defecto que edita `SetMassSource_1`) y una tolerancia relativa
     declarada (1e-3 en el recorrido y el informe).
   - Resultado `coherente` o `no_coherente` con su código; nunca se fuerza el éxito.
4. **Recorrido y informe.**
   - La etapa de análisis del runner registra `fases.masa_nativa` sin relajar su guarda.
   - El informe (`--masa-nativa-lectura <id>`) recalcula la sección desde la lectura aceptada del MISMO análisis/EDB y desde el
     modelo analizado.
   - El inventario de contenido conserva `masa_nativa_verificada = false`: la evidencia nativa es una sección aparte, ligada por
     huellas.

Pruebas: `tests/test_libro_masa_263.py` (libro sintético y contraste con el extracto 253f) y `tests/test_informe_masa_nativa_263.py`.
Límites: sin masa vertical ni rotacional, sin hidrodinámica; la coherencia de totales no prueba la distribución por nudo.

### Observación real con diafragmas rígidos (09d1)

ETABS 21.1 asigna en `AssembledJointMass_1` la masa lateral de cada diafragma rígido a **un único nudo** por diafragma. Las
coordenadas de ese nudo no son el centro de masa. En 09d1 eran cuatro nudos de N4 con 127,25 / 124,50 / 107,61 / 122,17 kN·s²/m,
iguales a las masas de diafragma de N1–N4 publicadas en `Centers Of Mass And Rigidity`.

Consecuencias:
- el total U1/U2 sigue siendo válido para el contraste;
- los centroides «observables» por nudo de este validador no son físicos cuando hay diafragmas rígidos;
- la distribución por piso debe leerse en `Mass Summary by Story` y `Centers Of Mass And Rigidity`, tablas sin campo de caso que
  el lector general admite por lista explícita (`TABLAS_SIN_CASO`).

### Convención del libro frente a ETABS: tramos extremos de vigas (09d1)

`libro_masa` cuenta el peso propio de los frames con la longitud total entre nudos («sin descuento de solapes»). En 09d1, ETABS
informó en `Material List by Section Property` la misma longitud total de las vigas VS-15X30 (28,812 m), pero un peso equivalente
a unos 22,46 m: 24,256 kN frente a 31,117 kN. Esto explica 6,861 de los 6,868 kN de diferencia en CM y la mayor parte del −0,127 %
de masa.

No se cambió el libro ni la tolerancia; el contraste se mantiene como no coherente con causa identificada. Para modelar esa
exclusión haría falta evidencia de la regla de longitudes de extremo que usa ETABS. Ver
`seguimiento/claude_ruta/HALLAZGO_DESFASE_CM_09D1.json`.

**Comprobación 274.** Se leyó `Frame Assignments - End Length Offsets` del mismo EDB analizado; la tabla está en `TABLAS_SIN_CASO`.
- Los 128 frames tienen `OffsetOpt=Auto`, `RigidFact=0` y `SelfWtOpt=Auto`.
- Vigas: Σ(OffsetI + OffsetJ) × w = 6,86124 kN, frente a 6,86126 kN de la lista de materiales.
- Las columnas también tienen offsets, pero ETABS no descontó su peso.

`libro_masa.conciliar_extremos_vigas` aplica SOLO esa regla observada, con la tabla leída como entrada declarada:
- conciliación **no independiente**: 548,727337 frente a 548,726729 observada (−1,1·10⁻⁶);
- el contraste oficial frente al libro independiente sigue siendo no coherente;
- quedan 0,0069 kN sin asignar.

### Estimación independiente opcional

El desarrollo322 añade una [estimación de extremos Auto](ESTIMACION_EXTREMOS_AUTO.md) a partir del plan validado y configuración nativa, sin usar offsets del solver como entrada. La conciliación274 anterior conserva su carácter no independiente. La nueva sección es opcional, mantiene el libro bruto y su contraste y se abstiene fuera del perfil comprobado. Su integración y validación se identifican en la distribución entregada; no implica aprobación de ingeniería.
