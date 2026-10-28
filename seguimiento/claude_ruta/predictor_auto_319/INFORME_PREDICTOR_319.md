# Predictor 319: validación conservadora del candidato

317 queda intacto. Módulo autónomo `predictor_auto_319.py`: puro y sin importar 317. Sin ETABS, APIs ni Save. No se toca el producto, el libro ni los resultados. **Exposición previa declarada:** no es un ensayo ciego.

## Correcciones (REVISION_PREDICTOR_318)

| Fallo 317 | 319 | Prueba |
|---|---|---|
| `FANTASMA` omitida | toda solicitud (inexistente, duplicada o nombre inválido) es una fila abstenida dentro del denominador; sin totales | `test_viga_fantasma_permanece_en_denominador` |
| Punto duplicado con totales | duplicados de puntos, frames, secciones, pesos o ejes, argumentos duplicados y referencias inválidas son problemas del plan: bloquean los totales y el miembro afectado se abstiene | `test_punto_duplicado_bloquea`, `test_argumento_y_referencia_duplicados_o_invalidos` |
| `SetEndLengthOffset` con AutoOffset False ignorado | abstención en la viga y en la columna de apoyo. Auto explícito con longitudes nulas se acepta como coherente | `test_offsets_explicitos_no_auto` |
| Peso −25 da descuento −1 kN | peso volumétrico negativo o no finito: problema del plan y sin descuento. Peso 0 se acepta y se declara `peso_cero_declarado` | `test_peso_negativo_y_no_finito` |

`COMPARACION_FALLOS_317_319.json`: con los mismos 4 casos, 317 da totales (incluido −1 kN) y 319 da totales `null`.

## Validación añadida

- **Configuración** primero (incluso con un plan mal formado):
  - `vigas` obligatorio, `None` o lista; un texto u otro tipo produce abstención global;
  - una lista vacía da cobertura 0 y sin totales.
- **Plan:** objeto con `operaciones` en lista; cada operación con argumentos {nombre, valor} sin duplicados; `unidades_etabs` del plan igual a la configuración.
- **Miembro objetivo y columnas de apoyo:** abstención ante
  - sección ausente, no rectangular o con dimensiones ≤ 0 o no finitas;
  - inserción o ejes avanzados;
  - `SetModifiers` (de objeto o de sección), `SetSection`, `SetMass` o cualquier otra escritura `cFrameObj.*`/`cPropFrame.*` no interpretada;
  - viga con ejes girados.
- Nunca hay descuentos negativos ni no finitos. Totales solo si no hay problemas del plan, la selección no está vacía y la cobertura es completa.

## Pruebas

- `test_predictor_auto_317_en_319.py`: las 8 pruebas de 317 con cambios mínimos (importación y dos textos de mensaje). OK.
- `test_validacion_319.py`: 11 pruebas negativas y de control. Comprueban la ausencia de totales y que las abstenidas cuentan en el denominador. OK.

## Piloto (configuración verificada por Codex en copia: `tmp/configuracion_318_reparacion/registro.json`, sha `d75b43f8…`)

- Tolerancia 0,001 m, versión 21.1.0, lectura en kN_m_C; hash del EDB original y de la copia `42371308…` sin cambios.
- El recibo se cita como procedencia; el predictor solo recibe plan y configuración.
- Predicción sellada (`SELLO_PREDICCION_319.sha256`) antes del contraste: 45/45 completas, 0 problemas del plan, offsets 6,353 m, descuento 6,86124 kN.
- Contraste separado con la lectura nativa `6da62ea3…`: **90/90 extremos de acuerdo**, error máximo 4,6·10⁻¹⁶ m.
- Peso VS neto predicho 24,25572 kN frente a 24,2557 kN de la tabla nativa (4 decimales).

## Qué podría integrarse sin cambiar el libro bruto histórico

Un bloque opcional `descuento_offsets_auto` junto al libro con:
- la versión del candidato;
- la configuración y la referencia a su verificación;
- la cobertura y el estado por viga;
- columnas separadas para bruto, descuento predicho y neto predicho.

El neto solo se presenta como predicción cuando no hay problemas del plan, la cobertura es completa y la tolerancia está verificada. **No hace coherente la masa oficial:** el residuo de CM de 0,006877 kN fuera de las VS sigue sin atribuir y el libro sigue `no_coherente`. La integración la decide Codex.

## Límites

- ETABS 21.1.0, kN-m, secciones rectangulares, columnas verticales, 0/90°, vigas alineadas.
- Tolerancias de unión ensayadas: 0,001 y 0,005 m.
- Un solo caso sintético de muro.
- La lista de operaciones neutras es implícita: solo se bloquean las escrituras `cFrameObj.*`/`cPropFrame.*` no interpretadas. Otras familias que pudieran afectar al peso propio (p. ej. fuente de masa) no se analizan aquí.
