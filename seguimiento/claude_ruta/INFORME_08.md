# Informe 08 — cierre de brechas de evidencia, arquitectura y RNE vigente

Fecha: 21 de octubre de 2026.

**Estado:** el piloto real está **en curso**. No se declara cierre y no se aprueba ingeniería.
- Claude no ejecutó ninguna API. El contador de Codex está en 4/5 en OpenAI y 2/5 en Gemini.
- La comparación manual sigue aplazada.

## 1. Entregas previas publicadas antes de 08

Las entregas correctivas del 07 se publicaron con la validación c207 **terminada**: 1175 pruebas Python y 31 Node, sin omisiones y con las fuentes estables.

| Entrega | Contenido | ZIP (SHA-256) |
|---|---|---|
| `entregas/04-900585f146cf4335aed45768d8bc6747` | 23 archivos | `39228e96…` |
| `entregas/06-e96facbfa6d84161b3be7aafcf02e828` | 522 archivos, con el código de credenciales (R223-06) | `60372f85…` |

La entrega 06 se restauró sin red ni claves (`RESTAURACION_06C.json`): compilación correcta, 89 módulos importados y 9 pruebas OK. R233 aceptó ese incremento.

## 2. Brechas cerradas en el producto

| Brecha | Implementación | Verificación |
|---|---|---|
| Reubicar evidencia sin aprobar la lectura (08.1; R232) | Operación `reubicacion_evidencia`: versión nueva con `historial_evidencia` (región anterior y nueva, autor declarado, motivo). El valor, el tipo y el estado no cambian. Se sustituye la `evidencia_revisada` del 07, que ligaba la región a «revisado» y nunca se usó en datos reales. CLI `reubicar-extraccion`, servicio `/api/reubicar` y UI con previsualización antes de guardar. | `OperacionesEvidenciaTests` cubre la persistencia, los límites (sin cambio, fuera de página, área nula, índice, candidato y motivo), el historial incoherente, la 0.1 rechazada y el padre intacto. Prueba Node y QA en navegador. |
| Lecturas omitidas, de forma manual (08.2) | Operación `lectura_manual`: ID `M###` sin colisiones, `metodo.tipo = manual` («no proviene de un modelo de IA»), literal obligatorio, evidencia en el original con hash y estado pendiente. CLI `lectura-manual-extraccion`, `/api/lectura-manual` y UI. | Pruebas de procedencia, IDs y límites: sin literal, unidad de otro tipo, original o página inexistentes, cantidad fraccionaria. |
| Integración 0.2 y derivados (08.3) | `vigencia`: versiones descendientes y exportaciones «superadas» cuando cambió un candidato exportado. La UI la muestra en la cabecera. Los tipos 0.2 siguen separados de las longitudes y `resultado_impreso` queda excluido de la exportación. | `test_exportacion_queda_superada_por_cambio_posterior` y servicio web (`test_servicio_web_reubica_agrega_y_expone_vigencia`). |
| Gemini 2 / protocolo 0.2 inválido (R235) | Recuperación **explícita** `--cuarentena` / `cuarentena=True`: los candidatos inválidos quedan íntegros en `cuarentena` con sus errores y recortes. No se recorta, reordena ni corrige nada, y la cobertura declarada se mantiene con advertencias. Sin el indicador, la respuesta entera se rechaza. El esquema estricto usa una variante por grupo de tipos (no admite «elemento + m») y el prompt exige x0 < x1 e y0 < y1. | `CuarentenaTests`; el servicio web acepta el registro con cuarentena y vuelve a comprobarlo. |
| Normas vigentes aplicables (08.6) | `normativa_e030` (RM 183-2026) y `normativa_rne` (E.060, E.070, E.020), con cita por función. | 8 pruebas con valores calculados a mano. `verificar_normativa_e030.py`: 26/26 fragmentos coinciden con los textos oficiales (huellas en el log). E.070 24.7 se verificó visualmente. |
| Cotas y registro entre vistas | `calibracion_ejes`: ejes por globos, k por fila de cotas con residuos, ambigüedades rechazadas o declaradas (`fijar`), registro con correspondencias declaradas. | 3 pruebas sobre un PDF sintético y aplicación real (§3). |

## 3. Aplicación al caso real (`pueblo-libre-002`)

- **Expediente nuevo** con 6 originales.
  - L0001–L0003 tienen el mismo SHA que en `provisional-001` y L0004–L0006 son la arquitectura del usuario.
  - `provisional-001` y sus respuestas siguen **intactos**. La derivación explícita está en `DERIVACION_PUEBLO_LIBRE_002.json`:
    - extracción `010d5641`, con 194 candidatos de las versiones 0.2.0 `3bc8d0fd`, `bcd21202` y `9099a5c1`;
    - IDs prefijados;
    - evidencia reducida a la página original;
    - ninguna huella antigua reparada.
- **Demostración de evidencias** (`EVIDENCIA_ANTES_DESPUES_08.json`, imágenes en `evidencia08/`):
  - O3.C039 «2.00 cm.»: la bbox del proveedor estaba vacía (tinta 0,0). Se reubicó en la versión `d35a979d` (tinta 0,148) y la lectura sigue pendiente.
  - M001 «CONCRETO f'c=175 Kg/cm2» (corte 2-2): alta manual en la versión `442b5d4d` (tinta 0,135), pendiente.
  - Evidencias vacías: de 42 a 41.
- **Recuperación de Gemini 2** desde la respuesta conservada, con SHA `7ccd952e…` igual antes y después:
  - registro `f51b8418` y versión `f505c6df` de `provisional-001`;
  - 59 candidatos recuperados y 12 en cuarentena (C007, C011, C015, C019, C023, C026, C041, C042, C043, C045, C046, C071), igual que en el diagnóstico de Codex;
  - cobertura declarada intacta (el recorte de columnas, «parcial»).
- **QA visual** contra el caso real en un servidor local (`QA_VISUAL_08.json`):
  - se comprobaron la versión 0.2.0, el tipo y la unidad por tipo, el literal y el símbolo, la marca en el plano, la previsualización sin guardar y el aviso de versiones posteriores;
  - consola sin errores y nada guardado.
- **Borrador trazable** (`BORRADOR_CASO_08.json`, reproducible con `seguimiento/claude_ruta/borrador_caso_08.py`):
  - **Arquitectura:**
    - cadena 1→8 con 7/7 tramos impresos: k = 0,012583 m/pt, total 20,010 m (20.00 impreso), residuo máximo de 8,5 mm;
    - cadena A–E con 4/4 tramos: total 10,000 m, residuo ≤ 0,5 mm.
  - **Estructura** registrada con A↔8, B↔7, C↔6, H↔2 e I↔1 (residuo ≤ 8,7 mm).
    - D, E, F y G no coinciden con ningún eje arquitectónico: posiciones 5,50, 8,58, 11,63 y 13,81 m, solo derivadas.
    - En Y: 3, 2 y 1 a 0, 5,00 y 10,00 m, con la orientación 3↔A declarada (decisión D5).
  - **Niveles:**
    - leídos: ±0.00 (L0004), +2.60 (L0005) y techo +10.40 (L0006);
    - derivados: 5.20 y 7.80, por progresión uniforme compatible con los extremos impresos (hipótesis).
  - **F3 resuelto con la arquitectura:** el «4.º nivel» estructural es el techo (S/C 150 = azotea).
  - **Discrepancias registradas:**
    - el eje central rotulado «1» a la derecha en L0001/L0002;
    - el eje F desplazado entre L0001 y L0003;
    - el tanque: NT +10.35 frente a NTT +10.40, y una altura total de 14.40 frente a 14.60 impreso.
  - **Normativa calculada con cita:**
    - Z = 0,45; U = 1,0;
    - S/TP/TL para S1 y para S2 sin Vs30;
    - T ≈ 0,17 s (hn/60);
    - V/P = 0,375 (S1) o 0,4125 (S2), si el sistema es albañilería confinada regular (R = 3);
    - deriva 0,005 con 0,75R;
    - Ec(210) = 21 329 MPa; Ec(175); Em(35, si la unidad es de arcilla) = 1 716 MPa;
    - γ del agua = 10 kN/m³;
    - fracciones de P: 25 % de la carga viva, 25 % en azotea y 100 % del tanque.
  - Todo lo anterior se marca como **«no es verificación de cumplimiento»**.

## 4. Lista única de decisiones restantes

La lista completa está en `BORRADOR_CASO_08.json → decisiones_restantes`:

| ID | Decisión | ¿La resuelve la norma? |
|---|---|---|
| D1 | Sistema estructural y R0 | No |
| D2 | Perfil de suelo: el EMS es obligatorio para ≥ 4 pisos | No |
| D3 | Unidad de albañilería, que fija Em | Sí, una vez declarada la unidad |
| D4 | NPT de los pisos 3.º y 4.º, o aceptar 2,60 uniforme | No |
| D5 | Orientación Y entre láminas | No |
| D6 | Metrado de cargas muertas no impresas | Sí, según E.020 |
| D7 | Nivel de agua de operación | Parcial |
| D8 | Apoyos | No |
| D9 | Ia/Ip | Sí, con resultados del modelo |

Ya no se piden la arquitectura, las cotas, la edición de la norma ni f'c, fy, f'm, S/C o σt.

## 5. Pendiente para completar el piloto

- Conversión a geometría 0.3 y configuración 0.5. Las coordenadas ya están derivadas; requieren aceptar D4 y D5 y localizar placas y columnas.
  - La detección vectorial de columnas es solo parcial: 8 rectángulos de .15x.40 y 1 de .15x.60.
- Plan, construcción nativa propia, relectura, análisis, lectura y controles, e informe del caso real.
- No se inició ninguno de esos tramos. El escenario sintético `r3` no los acredita.
- La recuperación con cuarentena existe en CLI y API. El formulario web de respuestas **no** tiene aún el indicador (se usa la CLI).

## 6. Verificación

- **Pruebas focales:** 412 Python OK en los grupos afectados y todas las Node OK, incluida la nueva.
- **Copia limpia `tmp/c208`** (hito integrado):
  - **1195 pruebas Python OK** y **31 pruebas Node OK**, 0 omitidas;
  - dependencias, arranque y PowerShell con código 0;
  - fuentes estables e idénticas a las entregadas.
