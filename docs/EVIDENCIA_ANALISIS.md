# Evidencia verificable de análisis en informe y panel

Estado: **entrega local de Claude revisada e integrada por Codex, 17 de octubre de 2026.** El informe y el panel pueden adjuntar, de forma opcional, evidencia de que el cálculo ETABS terminó, ligada exactamente al modelo revisado, al EDB analizado y al resultado normalizado.

Sin esa evidencia todo sigue como antes: el estado del solver figura como **no disponible**.

| Archivo | Contenido |
| --- | --- |
| [`draft2model/evidencia_analisis.py`](../draft2model/evidencia_analisis.py) | `verificar_evidencia`, `validar_evidencia`, `huella_evidencia` y `fuente_desde_argumentos`. |
| [`draft2model/informe.py`](../draft2model/informe.py) | Argumento opcional `evidencia_analisis` en `crear_informe` y `exportar_informe`, y opciones `--analisis-*` en su CLI. |
| [`draft2model/panel_tecnico.py`](../draft2model/panel_tecnico.py) | Argumento opcional `evidencia_analisis` en `crear_panel` y opciones `--analisis-*`. |
| [`tests/test_evidencia_analisis.py`](../tests/test_evidencia_analisis.py) | 23 pruebas sobre copias de la evidencia real: vínculo, alteraciones, ausencia y compatibilidad. |

No se modificaron el analizador, la normalización, la revisión de modelos, la CLI general ni ningún expediente o evidencia.

## Qué se revalida

`verificar_evidencia(raiz, caso, resultado, corrida)` lee los ficheros y no escribe nada. Todos los controles deben pasar.

**1. Resultado normalizado** (`<raiz>/<caso>/resultados_estructurales/<resultado>`):

- **Resultados y trazabilidad:** `resultados.json` cumple su contrato, es del caso y coincide con la huella de `trazabilidad.json`.
- **Respuesta de tablas:** `respuesta_puente.json` tiene el SHA256 que citan la trazabilidad y el mapeo.
- **Mapeo:** mismo caso, misma naturaleza sintética y revisión de correspondencias vigente.
- **Configuración:** su huella e id coinciden con los del resultado, su geometría es la del resultado y sigue vigente (`comprobar_configuracion` → `apto_para_adaptador`).
- **Copia EDB:** el archivo del caso tiene el SHA256 de la trazabilidad.
- **Corrida de tablas:** `leer_tablas`, `ok`, id igual a `corrida_id`, mismo modo y versión del motor, y el modelo leído es el `archivo_motor` declarado.
- **Casos:** cada caso del resultado figura en esa lectura con **estado 4**.
- **Valores:** cada valor se **rederiva** de la fila y el campo CSI citados (filtros, índice, factor). Un `null` exige que no se haya citado fila.

**2. Corrida de análisis aceptada** (carpeta con nombre igual a su id):

- **Aceptación:** `aceptacion_analisis.json` tiene exactamente los campos del analizador. Declara `aceptada`, `analisis_ejecutado`, `aprueba_resultados: false` y todos los casos con estado 4. El modo doble solo se admite con datos sintéticos.
- **Solicitud y respuesta:** `solicitud.json` (`analizar_modelo`) y `respuesta.json` (`ok`) coinciden campo a campo con la aceptación: casos, estados, modelo, revisión, entrada y guardado.
- **Archivos:** el EDB analizado (`analizado.edb` de esa misma corrida) y `entrada.edb` tienen los SHA256 declarados.
- **Rechazo:** si existe `analisis_no_aceptado.json`, la evidencia se rechaza.

**3. Revisión del modelo que autorizó el análisis:** `revision_modelo.consultar_aprobacion` debe seguir vigente. Modelo, huella y SHA256 de la aprobación deben coincidir, y el análisis debe partir del EDB revisado.

**4. Vínculo:**

- el resultado se leyó del **mismo EDB analizado** (SHA256 y ruta declarada);
- sus casos fueron ejecutados con estado 4;
- misma configuración y geometría en el modelo construido;
- misma naturaleza sintética, mismo motor real o doble y misma versión de ETABS.

No basta la existencia de un JSON ni un campo `aceptada: true` o `exitosa: true`. Cualquier fallo lanza `ErrorEvidenciaAnalisis`, que es una subclase de `ValueError`.

## Qué se publica

Un diccionario `draft2model.evidencia_analisis` 0.1.0 **sin rutas locales**, seguro para un HTML compartible. Contiene:

- ids y huellas del resultado y de la corrida de tablas;
- id, modo, versión, casos y estados de la corrida de análisis;
- SHA256 de la aceptación, la solicitud, la respuesta, la entrada y el EDB analizado;
- ids y huellas del modelo y de su revisión (`identidad_revisor: declarada_no_verificada`).

Sus estados son fijos y separados:

| Estado | Valor | Significado |
| --- | --- | --- |
| `calculo` | `completado_verificado` | ETABS declaró los casos terminados (estado 4) y las huellas enlazan toda la cadena. |
| `revision_resultados` | `pendiente` | Nadie ha revisado los valores; la evidencia no lo hace. |
| `conformidad_normativa` | `no_evaluada` | Sin reglas ni fuentes revisadas, no hay juicio normativo. |
| `correspondencias_tablas` | `revision_declarada` | El mapeo tabla → indicador tiene revisión declarada (identidad no verificada). |

`aprueba_resultados` y `aprueba_ingenieria` son siempre `false`. La aprobación documental del informe tampoco los cambia.

## Uso

Con la evidencia real del ensayo sintético (rutas relativas a la raíz del proyecto):

```powershell
$R = "tmp\demo_integrada_revision_001\private"; $C = "demo-integrada-sintetica"; $RES = "72c06efb3bfe477bb1fe565809aeddec"
$EV = @("--analisis-raiz", $R, "--analisis-caso", $C, "--analisis-resultado", $RES, "--analisis-corrida", "tmp\a5\adf97fbc232141e8ae687872c0d71232")
.\.venv\Scripts\python.exe -m draft2model.informe --resultados "$R\$C\resultados_estructurales\$RES\resultados.json" `
    --contexto tmp\claude_evidencia_entrada\contexto.json `
    --geometria "$R\$C\geometrias\6f22b68880384eb296e0b09ffd68e5e3\geometria.json" --salida tmp\informe_evidencia_NUEVO @EV
.\.venv\Scripts\python.exe -m draft2model.panel_tecnico --resultados "$R\$C\resultados_estructurales\$RES\resultados.json" `
    --geometria "$R\$C\geometrias\6f22b68880384eb296e0b09ffd68e5e3\geometria.json" --salida tmp\panel_evidencia_NUEVO.html @EV
```

Las cuatro opciones `--analisis-*` van juntas o no van; si falta alguna, la ejecución termina con código 1 y no crea salida. Desde Python:

```python
fuente = {"raiz": raiz, "caso": caso, "resultado": resultado_id, "corrida": carpeta_corrida}
informe = crear_informe(resultados, None, contexto, evidencia_analisis=fuente)
exportar_informe(informe, carpeta_nueva, evidencia_analisis=fuente)   # se revalida al exportar
crear_panel(ruta_resultados, None, panel_nuevo, evidencia_analisis=fuente)
```

Al exportar, un informe con evidencia exige la misma fuente y la vuelve a verificar. Si la evidencia cambió, se rechaza sin crear la carpeta. Un informe sin evidencia no admite que se le adjunte al exportar.

### Salidas generadas el 17 de octubre de 2026

Se generaron con la evidencia real y no sobrescriben nada:

| Salida | SHA256 |
| --- | --- |
| `tmp/informe_evidencia_analisis_001/informe.pdf` (3 páginas) | `b418b4355485c99040c9928cf8700fa4884df1fc3792b8ac3233a0927539ebaf` |
| `informe.html` | `32d405ba91b11205add5489ee56ad966bf2b42f8e1c18a2dbd453f753fead7a1` |
| `informe.json` | `094ca8c39d6dc9365ed28a7017f90d02fb98ff555673cd03a99aed0d96677256` |
| `tmp/panel_evidencia_analisis_001.html` | `4828379cab5eba16ee999d4c668060635aa0fc5a47123cd89cc2445cde00a46e` |

El contexto, copiado del informe `_006`, está en `tmp/claude_evidencia_entrada/contexto.json`.

Comprobaciones realizadas:

- **PDF:** las 3 páginas se rasterizaron con PyMuPDF y se revisaron visualmente. Todas las secciones son visibles; la sección 1 muestra el estado separado, las tablas de derivas y cortantes están completas y la trazabilidad incluye las huellas de la evidencia. No hay tablas anidadas.
- **Panel:** se abrió en el navegador integrado. La tarjeta y la sección de evidencia se muestran, no hay errores de consola y `node --check` valida su script.
- **Rutas privadas:** ni el HTML del informe ni el panel contienen unidades, `tmp\a5`, el nombre del usuario ni `private`.
- **Evidencia original:** las huellas de `tmp/demo_integrada_revision_001/private` y de la corrida `tmp/a5/adf97…` se tomaron antes y después. Todos los archivos preexistentes quedaron idénticos. Durante la generación, el ensayo dinámico paralelo de Codex **añadió** al mismo expediente el modelo construido `f2fb9ada…` y la aprobación `0c81af8c…` (`analisis_dinamico_real_033.log`); no proceden de este módulo, que no escribe.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_evidencia_analisis tests.test_informe tests.test_panel_tecnico -v
```

Cada prueba extrae el paquete portable `tests/fixtures/etabs21_sintetico/evidencia.zip`, comprueba su manifiesto y altera solo la copia temporal. Las capturas proceden del motor real con datos sintéticos; estas pruebas no abren ETABS. No dependen de la existencia del antiguo `tmp`. Cubren:

- **Cadena real verificada:** sin rutas en el resultado y sin escrituras (instantánea byte a byte de las copias).
- **Alteraciones rechazadas:**
  - EDB analizado o entrada;
  - aceptación no aceptada, con estado 3, con `aprueba_resultados`, con un campo `exitosa` añadido, sin análisis, de otro modelo, o doble con datos reales;
  - un JSON mínimo con `exitosa: true`;
  - respuesta o solicitud distintas;
  - `analisis_no_aceptado.json` presente o carpeta renombrada;
  - valor del resultado, respuesta de tablas, filtro de la fila citada o mapeo sin revisión;
  - copia EDB del caso, otro caso o resultado inexistente;
  - **otra corrida real aceptada** de otro modelo (`tmp/etabs_sintetico_real_002/analisis/28f6…`);
  - aprobación del modelo editada u original del expediente alterado;
  - snapshot validado contra otros resultados o con estados, casos o rutas alterados.
- **Informe:**
  - estado separado y sin rutas ni tablas anidadas;
  - exportación que exige la fuente y la revalida, con PDF que conserva la evidencia y rechaza la evidencia alterada antes de exportar;
  - snapshot manipulado dentro del informe;
  - aprobación documental que no aprueba resultados;
  - evidencia ajena al resultado;
  - CLI completa y parcial.
- **Compatibilidad:** sin evidencia, el informe conserva su forma exacta (sin la clave nueva) y la ausencia explícita, y el informe histórico `_006` sigue validando.
- **Panel:** con evidencia y sin rutas; sin evidencia, sin la clave; evidencia alterada rechazada sin crear salida.

Resultado del 17 de octubre de 2026: `test_evidencia_analisis` 23/23, `test_informe` 14/14 y `test_panel_tecnico` 4/4 (**41 de 41, sin omisiones**). No se ejecutó la suite completa.

## Limitaciones

- **Autenticidad:** las huellas detectan alteraciones accidentales o parciales y la mezcla de evidencias. No autentican al productor ni impiden una reescritura coherente de todos los archivos. El estado 4 es lo que declaró ETABS a través del puente.
- **Rutas declaradas:** el vínculo con el EDB analizado se comprueba por SHA256 y por la ruta **declarada** (`archivo_motor` igual a `guardado.ruta`, sin distinguir mayúsculas). Los archivos se leen de la carpeta de corrida indicada, de modo que una copia íntegra de la evidencia también verifica.
- **Alcance:** cálculo completado no es una revisión de resultados ni conformidad normativa. Faltan periodos y sitio, la deriva Y es null y la evaluación sigue pendiente sin reglas.
- **Un análisis por resultado:** se adjunta una corrida. Resultados que combinen varias corridas de análisis no están contemplados.
- **Visualización:** la revisión visual del PDF se hizo con rasterización de PyMuPDF, no con Poppler; se recomienda que Codex repita su inspección habitual.
- **Cableado pendiente para Codex:** no se tocó la CLI general (`__main__`, `cli_etabs`). Si se quiere exponer la evidencia desde la demo integrada, basta con pasar las cuatro opciones `--analisis-*` (o el dict `fuente`) a `draft2model.informe` y `draft2model.panel_tecnico`.

## Revisión e integración posterior de Codex

Entrega local revisada contra archivos y ejecución. La suite integrada previa incluyó estas funciones:529 pruebas correctas, sin omisiones, archivos estables (`tmp/verificacion_dinamica_real_034.json`). Codex incorporó el campo Case observado para periodos/modales mediante política compartida con el normalizador; reforzó correspondencias con selectores revisados, factores, unicidad de fila y ausencia comprobable.31 pruebas pertinentes posteriores correctas (`tmp/revision_evidencia_modal_038.log`).

Vínculo real dinámico verificado: resultado `994e298b81b9435fbf9fde9f3eba2f30`, análisis `tmp/ad1/bcd0c0b7b407496b88976ddc3f23b7a9`. Informe de tres páginas generado con esa fuente e inspeccionado con Poppler. Los límites anteriores de falta de periodos describen solo el ensayo estático; el dinámico incluye tres periodos modales, conserva derivaY ausente y evaluación normativa pendiente. El empaquetado portable ya se verificó: copia limpia054 completa con546 pruebas correctas, sin omisiones, usando entorno aislado y archivos estables. Esa verificación precede a los servicios web nuevos de entregables y construcción.
