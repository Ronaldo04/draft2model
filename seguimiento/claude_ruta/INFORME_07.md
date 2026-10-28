# Informe 07 — continuación del piloto real

Fecha: 21 de octubre de 2026. Corresponde a las entregas correctivas 04 y 06.

**Estado:** el piloto está **incompleto** y avanza. No se declara cierre.

**Alcance de lo hecho:**
- Claude no ejecutó ninguna API. El contador de Codex está en 4/5 en OpenAI y 1/5 en Gemini.
- No se aprobaron lecturas ni hipótesis.

## 1. Fallos de implementación corregidos

| Problema observado en el piloto | Corrección | Prueba |
|---|---|---|
| Cantidades de barras y cargas clasificadas como «cota desconocida»; f'c, fy y f'm sin magnitud; resultados impresos mezclados con entradas (R218, R221) | Contrato **0.2.0** con los tipos `carga`, `propiedad`, `parametro`, `cantidad`, `texto` y `resultado_impreso`. Cada tipo tiene sus unidades (`kgf/cm2`, `kgf/m2`, `adimensional`, `s`…). La exportación excluye `resultado_impreso` | `tests/test_vision_semantica_ruta07.py` |
| El prompt pedía `texto_fuente`, pero `preparar_peticion` mandaba omitirlo | En los paquetes 0.2.0 (predeterminados), el esquema estricto exige `texto_fuente` y `simbolo` y ya no se pide omitirlos. Los paquetes 0.1.0 conservan su contrato | Ídem: paquete nuevo frente a paquete heredado |
| Un JSON válido no prueba que la lectura sea suficiente (R213) | `cobertura` obligatoria por recorte (`completa`, `parcial` o `sin_lecturas`), con coherencia frente a los candidatos. La advertencia `cobertura_incompleta` llega a la extracción y a la UI | Ídem |
| Reclasificar exigía programar | Revisión con `tipo_revisado` (CLI `--tipo` y selector en la UI). Las propuestas pendientes van en una versión 0.2.0 derivada (`migrar-extraccion`) sin tocar las lecturas | Ídem y `tests/revision_lecturas_semanticas_frontend.cjs` |
| Bboxes desplazadas o vacías sin forma de corregirlas | Reubicación revisada `evidencia_revisada`, solo dentro de la misma evidencia (CLI `--bbox`, campo en la UI). `auditar-evidencia` detecta regiones sin trazos | Ídem |
| R223-06: el snapshot 06 excluía 3 archivos de código | Lista explícita `CODIGO_CREDENCIALES`; se rechazan `.local.`, `.env`, `.key`, `.pem`, otros nombres con «credencial» y patrones de clave real (se admiten las ficticias marcadas). Nuevo `scripts/verificar_restauracion_entrega.py` | `tests/test_crear_entrega_ruta201.py`; restauración de la entrega 06 correctiva (log) |

Compatibilidad: las extracciones y paquetes 0.1.0 guardados se cargan, validan y exportan igual que antes. Comprobado con las pruebas heredadas y con las cuatro extracciones reales.

## 2. Datos reales revisados contra los originales

**Extracciones migradas.** Las cuatro extracciones reales (OpenAI 1, 3 y 4, y Gemini 1) se migraron a 0.2.0 con 88 clasificaciones propuestas y pendientes:

| Versión 0.2.0 | Extracción de origen |
|---|---|
| `fe3eb621` | OpenAI 1 |
| `3bc8d0fd` | OpenAI 3 |
| `bcd21202` | OpenAI 4 |
| `9099a5c1` | Gemini 1 |

Cada motivo cita lo visto en el original.

**Error de valor detectado:** OpenAI4 C033 leyó NFC = -2.6; el plano imprime **-2.65**. La propuesta lo corrige y queda pendiente.

**Evidencias vacías** según la auditoría de tinta: 2/34, 8/60, 30/102 y 4/32. Además, en REC0002 y REC0003 de la petición 3 hay un desplazamiento de aproximadamente una línea, comprobado visualmente.

**Omisiones comprobadas:**
- tabla de placas;
- patas de C-1;
- estribos;
- traslapes de 50 y 60;
- «POBREMENTE GRADUADA»;
- f'c = 175 de los cortes 2-2 y 5-5;
- peldaños.

Gemini omite f'm, σt y los parámetros sísmicos.

Inventario completo y trazable: [INVENTARIO_PILOTO_07.md](INVENTARIO_PILOTO_07.md).

## 3. Calibración (hipótesis, no lectura)

Las láminas estructurales **no imprimen cotas entre ejes**, y la escala nominal 1/50 no corresponde al PDF.

En `CALIBRACION_L0001_07.json` figuran:
- k por cada referencia impresa, con su residuo;
- intervalo de k (dispersión del 0.5 %);
- referencia de control R4 fuera del intervalo;
- tramos entre ejes como intervalos;
- discrepancia del eje F entre L0001 y L0003 (≈ 0.50 m).

No se construyó geometría con estas distancias: falta la aceptación del usuario o cotas de arquitectura.

## 4. Lo que falta, separado

- **Usuario** ([FALTANTES_USUARIO_07.json](FALTANTES_USUARIO_07.json)):
  1. Alturas de entrepiso y NPT.
  2. Cotas entre ejes, o aceptar la calibración, y aclarar el eje F.
  3. S/C del 4.º nivel (200 frente a 150).
  4. Edición sísmica.
  5. Idealización de la albañilería y módulos E.
  6. Cargas muertas.
  7. Niveles de agua.
  8. Apoyos.

  No se piden f'c, fy, f'm, S/C, σt, secciones, e = 17 ni los cortes de los recipientes: están documentados.
- **Revisión o lectura** (no del usuario): reubicar o rechazar evidencias débiles; recuperar las omisiones mediante lectura manual con evidencia o con una petición focal que solo ejecutaría Codex.
- **Recorrido nativo propio del caso real** (geometría, configuración, plan, construcción, relectura, análisis e informe): **no iniciado**. Depende de F1 y F2 como mínimo. El escenario sintético `r3` no lo acredita.

## 5. Verificación

- Pruebas focales de los grupos afectados: 392 pruebas. Los únicos fallos (los esquemas de Anthropic con solicitud mínima) se corrigieron. `test_cli_extraccion` falla solo cuando se invoca como `tests.X` fuera de `discover`; eso ocurría ya antes de este cambio.
- Todas las pruebas Node de interfaz están en verde, incluida la nueva.
- Copia limpia completa `tmp/c207` (hito integrado):
  - **1175 pruebas Python OK** y **31 pruebas Node OK**, 0 omitidas;
  - dependencias, arranque y PowerShell con código 0;
  - fuentes estables, iguales byte a byte a las de la entrega 04 correctiva.

## 6. Entregas publicadas

| Entrega | Contenido | ZIP (SHA-256) |
|---|---|---|
| `entregas/04-900585f146cf4335aed45768d8bc6747` | 23 archivos | `39228e96…` |
| `entregas/06-e96facbfa6d84161b3be7aafcf02e828` (estado `bloqueado`) | 522 archivos, con los 3 archivos de código de credenciales | `60372f85…` |

La entrega 06 se restauró y verificó sin red ni variables de clave (`RESTAURACION_06C.json`): 522 miembros con hash comprobado, 89 módulos importados, compilación correcta y 9 pruebas OK.
