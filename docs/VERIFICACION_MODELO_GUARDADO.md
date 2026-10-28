# Verificación del modelo guardado (relectura independiente)

Estado al 20 de octubre de 2026. **Lector 0.4.0**: normalización dimensional de unidades, aberturas del plan 0.3 y diagnóstico del puente. Sobre el 0.3.0: losas nervadas y casetonadas, y orientación local del plan.

Corrección integrada181: el ensayo real de Ribbed/Waffle confirma que GetSlab.Thickness representa la capa (`SlabThickness`), mientras `OverallDepth` representa el alto total. La expectativa aplica el efecto final del setter específico y compara ambos parámetros separadamente. No toma como espesor final el argumento previo de SetSlab si después se asignan parámetros específicos. Véase LOSAS_ALIGERADAS_ETABS.md y evidencia ALIGERADOS_REALES_181.json.

## 0. Novedades 0.4.0 y guía reproducible

**Diagnóstico de la revisión 176** (1 fallo y 14 errores «puente sin respuesta, salida 1»):

- **Causa:** de **entorno**, no del código. La directiva de ejecución efectiva de PowerShell impide `-File`; el script ni siquiera se carga, por eso no hay respuesta.
- **Por qué compila el doble:** el ensamblado falso se compila con `-EncodedCommand`, que no está sujeto a la directiva.
- **Reproducción, sin cambiar políticas:** `powershell -ExecutionPolicy Restricted -File scripts/verificar_modelo_guardado.ps1 ...` devuelve salida 1, ninguna respuesta y el stderr «cannot be loaded because running scripts is disabled».
- **Evidencia:** `tmp/claude_relectura_176/reproduccion_restricted_stderr.txt`. En este host la directiva efectiva es RemoteSigned (CurrentUser; ver `directiva_efectiva.txt`) y el script no tiene `Zone.Identifier` (`flujos_alternos.txt`).
- **Cambios en 0.4.0:**
  - un puente sin respuesta lanza `ErrorPuente(tipo="entorno")`, conserva `codigo_proceso` y anota la causa `directiva_de_ejecucion_impide_file`, con stderr sin rutas absolutas, en `verificacion_no_completada.json`;
  - la marca de incertidumbre **no** se borra;
  - las pruebas del script real hacen una sonda previa con `-File`: si la directiva la bloquea, se **omiten con la causa**, en lugar de fallar;
  - `DiagnosticoEntornoTests` reproduce el caso siempre.
- **Simulación del entorno restringido:** variable `PSExecutionPolicyPreference=Restricted` solo en el proceso de prueba. Resultado: 25 OK y 1 omitida (la clase del script real, con causa), log en `simulacion_restringida.log`.

**Unidades** (bloqueo real: `tmp/d4/ensayo/modelo.edb`, SHA `c71d19cf…a305`, reabre en N_mm_C):

- **Qué hace el lector:**
  - registra las unidades presentes y devuelve los valores **sin convertir** (en la respuesta quedan los originales);
  - nunca llama a `SetPresentUnits`.
- **Normalización en Python, hacia las unidades del plan (kN_m_C):**
  - sistemas admitidos: `(N|kN)_(mm|cm|m)_C`;
  - factor racional exacto por magnitud, `fuerza^a · longitud^b`, con un solo redondeo;
  - evidencia en `resultado.unidades`: `leidas`, `plan`, `normalizacion` (`identidad` / `dimensional` / `no_admitida`), `factores`, `no_comparables` y `valores_normalizados`.
- **Unidad no admitida** (lb, kip, kgf, Ton, in, ft, F): todas las magnitudes con dimensión quedan **incompletas** y no hay verificación global.
- **Plan real d4** (0.1, 69 operaciones, ninguna sin lector): ensayo real180 en instancia propia cerrada sin guardar. Unidades N_mm_C; fuente y copia conservaron SHA. El resultado inicial quedó incompleto solo por SF. La respuesta bruta queda conservada y su comparación posterior aplica la conversión confirmada de SF; ver `seguimiento/REAL_RELECTURA_180.json`. Los criterios numéricos sintéticos de lectura no aprueban ingeniería.

| Magnitud | Exponentes (F, L) | Factor N_mm_C → kN_m_C | Campos |
|---|---|---|---|
| longitud_m | (0, 1) | 1/1000 | coordenadas, pisos, espesores, T3/T2, parámetros de nervadas y casetonadas |
| modulo_kN_m2 | (1, −2) | 1000 | E (G y M: leídos, no comparados) |
| peso_kN_m3 | (1, −3) | 1000000 | W |
| presion_kN_m2 | (1, −2) | 1000 | cargas de área |
| fuerza_kN | (1, 0) | 1/1000 | F1–F3 de punto |
| momento_kN_m | (1, 1) | 1/1000000 | M1–M3 de punto |
| fuerza_lineal_kN_m | (1, −1) | 1 | Val1/Val2 de frame |
| aceleracion_m_s2 | (0, 1) | 1/1000 | SF espectral: plan1m/s², GetLoads real1000mm/s²; lectura180 |
| adimensional, ángulo, s, Hz, 1/°C | — | 1 | factores, tolerancias, periodos, frecuencias, A, amortiguamientos y textos de tabla |

La [documentación CSI de Response Spectrum](https://docs.csiamerica.com/help-files/etabs/Menus/Define/Load_Cases/Response_Spectrum.htm) identifica SF como aceleración según la longitud actual. La respuesta real180 confirma el cambio1→1000 al reabrir en milímetros; la tabla nativa `TransAccSF` también devolvió1000. Se conserva el resultado inicial incompleto y una nueva comparación de los mismos bytes brutos tras incorporar esta evidencia. Esto no prueba losas aligeradas, huecos, mallado ni resultados del solver.

**Aberturas** (plan 0.3 del compilador en revisión de Codex; solo leído, sin editar):

- **Expectativa:** acepta `validar_plan_aberturas`. Cada `SetOpening` es expectativa exacta: host `False` y hueco `True`; un valor contradictorio invalida la expectativa.
- **Lector:** `cAreaObj.GetOpening(String Name, Boolean& IsOpening)` en todas las áreas (firma reflejada; **61 firmas**).
- **Contorno y propiedad del hueco:** se comparan como cualquier área (`None`, según el plan). Una carga sobre el hueco aparece como carga extra.
- **Inventario:** `SetOpening` se inventaría con lector real; si se retira del inventario, el resultado queda incompleto.
- **Lo que no se afirma:** `controles_no_afirmados` incluye `efecto_estructural_de_aberturas`. La persistencia de Opening **no** demuestra corte de rigidez, malla compatible ni cargas netas. Un área sin `SetOpening` en el plan solo se registra.

**Versión 0.4.0:** `VERSION` y `VERSION_LECTOR` pasan a 0.4.0, y la mezcla con un lector 0.3 se rechaza.
- `lecturas.unidades` admite cualquier nombre `eUnits`.
- `lecturas.areas.aberturas` es nuevo.
- La API pública no cambia y los criterios no cambian.

**Guía de ejecución:**

```powershell
$env:TEMP=(Resolve-Path tmp/claude_relectura_176).Path; $env:TMP=$env:TEMP
.venv/Scripts/python.exe -m unittest -v tests.test_verificacion_modelo_guardado      # 35 OK en este host
.venv/Scripts/python.exe -m unittest -v tests.test_vinculo_verificacion_modelo       # regresión Codex, 6 OK
```

Si el host bloquea `-File`, el script real se omite con la causa. Para cubrirlo hay que ejecutarlo en un host cuya directiva lo permita, sin `Bypass`.

**Pendientes de lectura real (Codex, copia propia de ETABS):**
1. Que la lectura se complete en N_mm_C y la normalización iguale al plan d4.
2. Si `cCaseResponseSpectrum.GetLoads.SF` usa unidades presentes; hasta comprobarlo queda incompleto.
3. Que Ribbed y Waffle persisten, y que `GetSlab` devuelve el alto total.
4. Convenio y rango de `GetLocalAxes`.
5. Si `GetOpening` y la propiedad `None` de los huecos persisten tras reabrir.
6. Forma de las tablas de visualización y centinela de `GetValues`.
7. Qué devuelve `GetDiaphragm` para `Disconnect`.
8. Orden de `GetPoints`. Lector y comparador implementados y probados **solo con dobles**: un ensamblado `ETABSv1` falso y un EDB falso persistido.
- No se abrió ETABS real; tampoco hubo red, instalaciones ni suite global.
- **No retira** `BLOQUEO_INTEGRACION` ni `BLOQUEO_SUPERFICIES`.
- No habilita el ejecutor ni el modelo 0.2.
- No aprueba el modelo ni certifica seguridad estructural.

Archivos:
- [`draft2model/verificacion_modelo_guardado.py`](../draft2model/verificacion_modelo_guardado.py)
- [`scripts/verificar_modelo_guardado.ps1`](../scripts/verificar_modelo_guardado.ps1)
- [`tests/test_verificacion_modelo_guardado.py`](../tests/test_verificacion_modelo_guardado.py)

### Plan 0.4 (malla): comprobación independiente (encargo 196)

Para planes 0.4, la expectativa añade `malla` (solo nombres, normales, áreas netas **fuente** y resultantes esperadas). La comparación recalcula desde lo **leído** del EDB reabierto, en una categoría `malla`:
- el área neta por host;
- la orientación respecto de la normal del host;
- aristas dirigidas únicas y ausencia de nodos colgantes;
- nodos compartidos entre hosts;
- la cadena colineal y ordenada de subframes;
- fuerza y momento de cada carga distribuida.

Lo no legible, en unidades distintas de kN_m_C, o con una dirección proyectada o local queda **incompleto**, nunca verificado. No se afirman `masa_propia_por_elemento`, `calidad_y_rigidez_de_malla` ni `efecto_estructural_del_diafragma`. Detalle en [RELECTURA_MALLA_ETABS.md](RELECTURA_MALLA_ETABS.md).

## 1. API para integrar (Codex)

```python
from draft2model import verificacion_modelo_guardado as vmg

config = vmg.configuracion_real(trabajo, bloqueo=None, timeout_s=600.0, dll=None)   # bloqueo: compartir con el adaptador
verificador = vmg.VerificadorModeloGuardado(config)
prep = verificador.preparar_verificacion(
    edb,                     # Path absoluto .edb guardado por la ejecución (no se abre: se copia)
    sha256_edb,              # SHA256 del guardado según la respuesta aceptada de la ejecución
    plan,                    # plan 0.1 (validar_plan) o 0.2 de desarrollo (validar_plan_superficies), ya aceptado
    criterios={"relativo": r, "absolutos": {magnitud: a, ...}},   # obligatorio, todas las magnitudes (§4)
    ejes_locales_area=None,  # opcional: {area: {"angulo_deg": x, "avanzado": bool}}
    version_etabs_esperada=None)
resultado = verificador.ejecutar_verificacion(prep, confirmar_lectura=True)
resultado.estado                                   # "verificado" | "discrepancias" | "incompleto"
resultado.resultado["verificacion_global_del_plan"]  # True solo si verificado y ninguna operación sin lector
resultado.resultado["cobertura_plan"]               # inventario por operación (§5)
```

**Funciones puras:**
- `expectativa_desde_plan(plan, *, ejes_locales_area=None)`
- `validar_criterios(criterios)`
- `consulta_desde_expectativa(exp)`: solo nombres.
- `validar_observado(obs, consulta)`
- `comparar(expectativa, observado, criterios)`
- `cargar_resultado(ruta)`: lee resultados 0.1.0 y 0.2.0 como evidencia histórica.

**Constantes:**
- `INVENTARIO`: método modificador → categoría.
- `EXCLUSIONES`: método → motivo.
- `CAMPOS_TABLA`: campos por tabla y magnitud.

Para pruebas existe `configuracion_doble_powershell(trabajo, dll_prueba, entorno=...)`, que solo admite planes sintéticos.

**Errores:**
- `ErrorVerificacion`: entrada inválida; no se lee nada.
- `adaptador_etabs.ErrorEvidenciaEtabs`: huella, respuesta o instancia no verificables.
- `ErrorPuente` / `ErrorTiempo`: transporte.

Ante cualquier fallo quedan `verificacion_no_completada.json` y `<bloqueo>.incierto.json`, y hay que llamar a `confirmar_recuperacion`.

### Migración de 0.2.0 a 0.3.0

- `VERSION` y `VERSION_LECTOR` pasan a `"0.3.0"`. El vínculo de Codex (`vinculo_verificacion_modelo.py`) las lee de forma dinámica y sus 6 pruebas pasan sin cambios. Un script o una respuesta de lector 0.2 se rechaza; `cargar_resultado` lee 0.1.0, 0.2.0 y 0.3.0.
- `consulta` añade `losas_nervadas` y `losas_casetonadas` (solo nombres).
- `lecturas.propiedades_area` añade `nervadas` y `casetonadas`, con los nombres de parámetro **de la API**.
- La expectativa añade `ejes_plan` y `ejes_origen`; el resultado añade `ejes_origen`.
- Los criterios no cambian (13 magnitudes).
- Si el plan declara `SetLocalAxes` para un área, un `ejes_locales_area` que la contradiga produce `ErrorVerificacion`. Uno coincidente se acepta como redundante.

### Migración de 0.1.0 a 0.2.0

La API pública no cambia de forma; cambia el contenido.

| Elemento | 0.1.0 | 0.2.0 |
|---|---|---|
| `criterios.absolutos` | 10 magnitudes | **13**: añade `frecuencia_hz`, `tiempo_s` y `aceleracion_m_s2`. Unos criterios 0.1 se rechazan (`ErrorVerificacion`). |
| Solicitud | sin versión de lector | `version_lector: "0.2.0"`; el script rechaza otra versión |
| Respuesta | — | `datos.version_lector`; Python rechaza la mezcla de un script 0.1 con Python 0.2 y la inversa |
| `consulta` | losas, muros, rectángulos, materiales | además diafragmas, patrones, casos por tipo, combinaciones, funciones y tablas (**solo nombres**) |
| Resultado | `verificado` sobre el alcance | además `verificacion_global_del_plan` y `cobertura_plan` |

## 2. Contratos

**Solicitud** (`draft2model.etabs_solicitud` 0.1.0, operación `verificar_modelo_guardado`). Claves exactas:
- identidad: `contrato`, `version_contrato`, `id` (igual a la carpeta), `operacion`, `modo_configurado`;
- modelo: `modelo_lectura` (copia privada `<id>/modelo_lectura.edb`), `sha256_edb`;
- entorno: `unidades_esperadas`, `version_etabs_esperada`, `dll`;
- `consulta`, `sha256_expectativa`, `huella_plan`, `version_lector`.

En la carpeta también quedan `expectativa.json` (`draft2model.expectativa_modelo_guardado` **0.2.0**, ligada a `huella_plan`, `origen` y `destino_guardado` del plan) y `criterios.json`. **Los valores esperados no viajan al lector.**

**Respuesta** (`draft2model.etabs_respuesta` 0.1.0), en `datos`:
- huellas: `sha256_antes` y `sha256_despues` (iguales a `sha256_edb`);
- instancia: `instancia`, `id_proceso`, `inicio_proceso_utc`, `instancia_cerrada: true`;
- lector: `firmas_verificadas` (61), `version_dll`, `consulta` (eco exacto), `lecturas`, `version_lector`;
- garantías: `guardado: false`, `modificaciones: []`.

`lecturas` añade a lo de la versión 0.1:
- `apoyos` y `diafragmas_puntos` (por punto) y `diafragmas_areas` (por área);
- `diafragmas` (nombres y semirrígido), `patrones`, `casos` (nombres, tipos y detalle estático, modal y espectral) y `combinaciones`;
- `funciones` (`GetValues` en bruto), `tablas` (campos y filas de visualización) y `ejecucion` (casos y marcas).

El esquema es estricto: una respuesta truncada, manipulada o con nombres fuera de la consulta se rechaza.

**Resultado** (`draft2model.verificacion_modelo_guardado` **0.2.0**). Contiene lo de la 0.1 más `verificacion_global_del_plan` y `cobertura_plan` (`operaciones`, `comprobadas`, `excluidas` con orden, método y motivo, `sin_lector` y `por_metodo`). Mantiene `aprueba_modelo: false`, `certifica_seguridad_estructural: false` y `ejecutable: false`.

## 3. Lectura de solo lectura

Igual que en la versión 0.1:
- **Instancia y copia:**
  - instancia **nueva** propia, con `CreateObjectProgID` + `ApplicationStart`; nunca `GetObject`;
  - en modo real se identifica exactamente un proceso nuevo, y `ApplicationExit(false)` lo cierra también ante errores;
  - se abre la **copia privada**, nunca el original.
- **Firmas:** las **61 firmas exactas** de la lista blanca se resuelven por reflexión antes de crear la instancia; una firma distinta da el código 42.
- **Lo que nunca hace:** guardar, analizar, `SetPresentUnits`, setters ni `GetTableForEditingArray`.
- **Huellas:**
  - SHA256 de la copia antes de abrir, tras leer y tras cerrar;
  - Python revalida además el original, la copia, la solicitud, la expectativa y los criterios.
- **Retornos y mensajes:** un retorno distinto de 0 queda en `retornos_no_cero` y no se rellena con supuestos; los mensajes públicos no llevan rutas absolutas.

Los campos de tabla se leen con `cDatabaseTables.GetTableForDisplayArray`, que es la tabla de **visualización** y no abre una edición.

## 4. Criterios

**Igualdad discreta** para:
- nombres, contornos ordenados y restricciones (6 booleanos);
- opción y nombre de diafragma, semirrígido y enumerados;
- tipos de caso y de combinación, número de modos, casos modales, `CSys` y textos de tabla (`ModalCombo`, `RigidResp`);
- marcas de ejecución.

**Valores numéricos:** `|obs − esp| ≤ max(absolutos[magnitud], relativo·max(|obs|,|esp|))`, con todos los umbrales en [0, 1e-6]. Son umbrales de **lectura**, no tolerancias de ingeniería. Las 13 magnitudes son: `longitud_m`, `modulo_kN_m2`, `adimensional`, `coeficiente_termico_1_C`, `peso_kN_m3`, `presion_kN_m2`, `fuerza_kN`, `momento_kN_m`, `fuerza_lineal_kN_m`, `angulo_deg`, `frecuencia_hz`, `tiempo_s` y `aceleracion_m_s2`.

**Conjuntos por clave exacta** (cargas, cargas de caso, casos de combinación y cargas espectrales):
- faltante o extra → discrepancia;
- recuentos iguales pero repetidos con la misma clave → **incompleto**: no se empareja por orden.

**Nombres:**
- **Objetos:** igualdad exacta de conjuntos.
- **Propiedades, materiales, diafragmas, patrones, casos, combinaciones y funciones:** los esperados deben existir. Los extras de plantilla no se juzgan, salvo sus **marcas de ejecución**, que deben ser falsas porque el plan desmarca todos los casos.

**Lista no legible:** si falla la lectura de una lista, la categoría queda incompleta y no se declaran ausencias.

## 5. Cobertura por operación del plan

Cada operación del plan queda **comprobada**, **excluida** con motivo o **sin lector**. Una operación sin lector deja el resultado incompleto y `verificacion_global_del_plan=false`.

| Operación del plan | Categoría | Lector independiente |
|---|---|---|
| `cSapModel.SetPresentUnits` | unidades | `GetPresentUnits` (se detiene si no es kN_m_C) |
| `cStory.SetStories_2` | pisos | `GetStories_2` (nombres, base y alturas) |
| `cPropMaterial.SetMaterial` / `SetMPIsotropic` / `SetWeightAndMass` | materiales | `GetMaterial`, `GetMPIsotropic`, `GetWeightAndMass` |
| `cPropArea.SetWall` / `SetSlab`, `cPropFrame.SetRectangle` | propiedades | `GetWall`, `GetSlab`, `GetRectangle` (subtipo Slab, Ribbed=3 o Waffle=4, shell, material y espesor = alto total declarado) |
| `cPropArea.SetSlabRibbed` | propiedades_area | `GetSlabRibbed`: OverallDepth, SlabThickness, StemWidthTop, StemWidthBot, RibSpacing (longitud) y RibsParallelTo (entero exacto) |
| `cPropArea.SetSlabWaffle` | propiedades_area | `GetSlabWaffle`: OverallDepth, SlabThickness, StemWidthTop, StemWidthBot, RibSpacingDir1 y RibSpacingDir2 |
| `cAreaObj.SetLocalAxes` | areas (ejes) | `GetLocalAxes`: el ángulo del plan es criterio **obligatorio**; Advanced solo si el plan lo declara en su relectura |
| `cPointObj.AddCartesian`, `cFrameObj.AddByPoint`, `cAreaObj.AddByPoint` | geometría | `GetNameList`, `GetCoordCartesian`, `GetPoints`, `GetSection`, `GetProperty` |
| `cPointObj.SetLoadForce`, `cFrameObj.SetLoadDistributed`, `cAreaObj.SetLoadUniform` | cargas | `GetLoadForce`, `GetLoadDistributed`, `GetLoadUniform` |
| `cPropMaterial.SetMassSource_1` | fuente_masa | `GetMassSource_1` |
| `cPointObj.SetRestraint` | apoyos | `cPointObj.GetRestraint` en **todos** los puntos; sin `SetRestraint`, el punto debe estar libre porque la configuración declara todos los apoyos |
| `cDiaphragm.SetDiaphragm`, `cPointObj.SetDiaphragm` | diafragmas | `cDiaphragm.GetNameList` / `GetDiaphragm`, `cPointObj.GetDiaphragm` |
| `cLoadPatterns.Add` | patrones | `GetNameList`, `GetLoadType`, `GetSelfWTMultiplier` |
| `cCaseStaticLinear.SetCase` / `SetLoads` | casos | `cLoadCases.GetTypeOAPI` (LinearStatic), `cCaseStaticLinear.GetLoads` |
| `cCaseModalEigen.SetCase` / `SetNumberModes` / `SetParameters` | casos | `GetTypeOAPI` (Modal), `GetNumberModes`, `GetParameters`, `GetLoads` (cargas iniciales que el plan declara) |
| `cCaseResponseSpectrum.SetCase` / `SetModalCase` / `SetLoads` / `SetEccentricity` | casos | `GetTypeOAPI` (ResponseSpectrum), `GetModalCase`, `GetLoads`, `GetEccentricity` |
| `edicion_tabla` Functions - Response Spectrum - User Defined | funciones_espectrales | Period/Value con `cFunction.GetValues` (adapta solo el centinela (0,0) observado); DampRatio por tabla de visualización |
| `edicion_tabla` Load Case Definitions - Response Spectrum | tablas_dinamicas | `ModalCombo` y `RigidResp` (texto exacto) por tabla de visualización |
| `edicion_tabla` Load Case Definitions - Damping - Modal | tablas_dinamicas | `ConstDamp` por tabla de visualización y `GetDampConstant` (OAPI) |
| `cCombo.Add` / `SetCaseList` | combinaciones | `GetNameList`, `GetTypeOAPI`, `GetCaseList` |
| `cAnalyze.SetRunCaseFlag` | marcas_de_ejecucion | `GetRunCaseFlag` en todos los casos |
| `cFile.Save` | **excluida** | El SHA256 del EDB leído acredita el guardado |
| `Count` / `Get*` del propio plan (verificación y relecturas) | **excluida** | No modifican el modelo |

**Aligerados sin equivalencia maciza:**
- Un `SetSlab` Ribbed o Waffle sin su `SetSlabRibbed`/`SetSlabWaffle` invalida la expectativa (`ErrorVerificacion`); no se supone una losa maciza.
- Un subtipo releído como Slab es discrepancia.

**Ángulos:** se comparan **tal como los escribe el compilador y los devuelve la API**, en grados, sin normalización modular (−330° frente a 30° es discrepancia) y sin tomar la normal geométrica como eje.
- Las áreas sin `SetLocalAxes` en el plan y sin criterio del solicitante quedan en `ejes_sin_criterio`.

**Aberturas:** `cAreaObj.SetOpening` existe en la DLL, pero **no** está en el inventario. Si un plan futuro la emitiera, quedaría sin lector (incompleto y sin verificación global) hasta una extensión real; hoy ningún plan aceptado la emite.

**Leído pero no afirmado** (en `controles_no_afirmados`; no hay expectativa en el plan ni representación verificada):
- diafragma de área (`cAreaObj.GetDiaphragm`);
- subtipo de caso;
- tipo de amortiguamiento espectral (`GetDampType`);
- combinación modal por OAPI (`GetModalComb_1`: el texto de tabla sí se compara);
- `G`, `M` y elevaciones derivadas;
- ejes locales sin criterio.

## 6. Firmas contrastadas

Firmas obtenidas por reflexión de metadatos de `ETABSv1.dll` 1.29.0.0, sin iniciar ETABS. Registros en `tmp/relectura_qa/firmas_reflejadas.json` y `tmp/cobertura_qa/firmas_reflejadas.json`.

Firmas nuevas:
- `cPointObj.GetRestraint(String Name, Boolean[]& Value)`
- `cPointObj.GetDiaphragm(String Name, eDiaphragmOption& DiaphragmOption, String& DiaphragmName)`
- `cAreaObj.GetDiaphragm(String Name, String& DiaphragmName)`
- `cDiaphragm.GetDiaphragm(String Name, Boolean& SemiRigid)`
- `cLoadPatterns.GetLoadType(String Name, eLoadPatternType& MyType)` y `GetSelfWTMultiplier(String Name, Double& SelfWTMultiplier)`
- `cLoadCases.GetTypeOAPI(String Name, eLoadCaseType& CaseType, Int32& SubType)`
- `cCaseStaticLinear.GetLoads(...)`
- `cCombo.GetTypeOAPI(String name, Int32& ComboType)`: con `name` en minúscula.
- `cCombo.GetCaseList(String Name, Int32& NumberItems, eCNameType[]& CNameType, String[]& CName, Double[]& SF)`
- `cAnalyze.GetRunCaseFlag(Int32& NumberItems, String[]& CaseName, Boolean[]& Run)`
- `cDatabaseTables.GetTableForDisplayArray(String TableKey, String[]& FieldKeyList, String GroupName, Int32& TableVersion, String[]& FieldsKeysIncluded, Int32& NumberRecords, String[]& TableData)`

**Lector 0.3.0:** `cPropArea.GetSlabRibbed(String Name, Double& OverallDepth, Double& SlabThickness, Double& StemWidthTop, Double& StemWidthBot, Double& RibSpacing, Int32& RibsParallelTo)` y `cPropArea.GetSlabWaffle(String Name, Double& OverallDepth, Double& SlabThickness, Double& StemWidthTop, Double& StemWidthBot, Double& RibSpacingDir1, Double& RibSpacingDir2)`. `eSlabType` vale Ribbed 3 y Waffle 4. Registro en `tmp/aligerados_qa/firmas_reflejadas.json`. **Total: 60 firmas exactas.**

**Enumerados:** `eLoadCaseType` vale LinearStatic 1, Modal 3 y ResponseSpectrum 4. `eCNameType` vale LoadCase 0. **No existe `cFunctionRS`** en esta DLL, por eso el amortiguamiento de la función se lee por tabla. La prueba `test_firmas_iguales_a_la_dll_instalada` compara las 61 firmas del script con la DLL instalada.

## 7. Pruebas (dobles; no acreditan ETABS)

```powershell
$env:TEMP=(Resolve-Path tmp/aligerados_qa).Path; $env:TMP=$env:TEMP
.venv/Scripts/python.exe -m unittest -v tests.test_verificacion_modelo_guardado
```

Resultado: **27 OK, 0 omitidas, código 0**. Log en `tmp/aligerados_qa/pruebas.log`. Regresión del vínculo de Codex (`tests.test_vinculo_verificacion_modelo`): 6 OK, log `tmp/aligerados_qa/vinculo_codex.log`.

**Nuevas en 0.3.0.** Usan los planes reales del compilador `losas_aligeradas` (marcador `tmp/entrega_losas_aligeradas.json`, `entrega_candidata`, 5 hashes contrastados) mediante su `tests.test_losas_aligeradas.configurar`: LOSA20 nervada o casetonada a 30° y S2 maciza.
- **Verificado:** con la orientación del plan obligatoria (`ejes_origen` plan); S2 queda sin criterio.
- **Discrepancia:** cada parámetro de API alterado, subtipo macizo, espesor, material, ángulo 0°, ángulo −330°, Advanced y propiedad maciza asignada al área.
- **Incompleto:** retorno distinto de 0 de `GetSlabWaffle` o de `GetLocalAxes`.
- **Rechazado:**
  - una lectura sin un parámetro (esquema inválido);
  - un criterio del solicitante que contradice el plan;
  - un Ribbed sin `SetSlabRibbed`.
- **Sin lector:** un método sin lector deja el resultado incompleto.
- **Script real contra el EDB falso persistido:** ambos tipos verificados; con la geometría igual, `StemWidthBot`, el ángulo y la carga de área alterados dan discrepancias; `GetSlabWaffle` con retorno 1 da incompleto. Se conservan contornos, cargas y masa.

**Corrección del doble:** el `eSlabType` falso carecía de Ribbed y Waffle; la lectura «3» se detectó como discrepancia, y se completó con los valores reflejados.

**Resultado 0.2.0:** 22 OK, log en `tmp/cobertura_qa/pruebas.log`.

**Nuevas en 0.2.0:**
- **Plan dinámico verificado:** inventario completo (comprobadas + excluidas = total) y consulta sin valores.
- **28 alteraciones con geometría idéntica, todas discrepancia:**
  - apoyos;
  - diafragmas (de punto, semirrígido y ausente);
  - patrones (tipo y peso propio);
  - casos: tipo, factor y carga extra del estático; modos y tolerancia modal; factor, función, caso modal, excentricidad y amortiguamiento espectral;
  - combinaciones (tipo, factor y caso extra);
  - función (valor y periodo);
  - tablas (`ModalCombo`, `RigidResp`, `DampRatio` y `ConstDamp`);
  - marcas de ejecución (caso del plan desmarcado y caso de plantilla marcado).
- **Lecturas fallidas** (`GetCaseList`, tabla de visualización, `GetRunCaseFlag`, lista de patrones, `GetRestraint` y parámetros modales) → incompleto. Los duplicados no se emparejan.
- **Método sin lector** → incompleto, con verificación global falsa.
- **Script real contra el ETABSv1 falso:**
  - planes 0.1, 0.2 y dinámico reabiertos y verificados;
  - configuración persistida alterada con geometría igual → discrepancias exactamente en apoyos, diafragmas, patrones, casos, combinaciones, tablas y marcas;
  - `GetCaseList` con retorno 5 → incompleto;
  - una respuesta de lector 0.1 se rechaza.

**Se conservan** todas las pruebas de la 0.1: geometría, cargas, masa, ejes, transporte manipulado, firma incompatible antes de la instancia y cierre con fallo.

## 8. Límites y siguiente dependencia

- **Aligerados (0.3.0):** pendiente de confirmar en ETABS real que `GetSlab` devuelve el alto total como espesor, que Ribbed y Waffle persisten tras reabrir, y la representación de `GetLocalAxes` (rango del ángulo y Advanced).
  - Una diferencia de convenio angular aparecerá como discrepancia, sin normalizarla.
  - No se verifican rigidez, peso equivalente, mallado ni rellenos.

- **Sin prueba real (Codex).** Pendiente de confirmar en ETABS 21.1:
  - unidades al reabrir;
  - orden de `GetPoints`;
  - qué devuelve `cPointObj.GetDiaphragm` para `Disconnect` (se espera el nombre `""` que escribe el plan);
  - forma de las tablas de visualización: campos, filas agrupadas y formato de números y textos (`No`, `CQC`);
  - centinela de `GetValues`;
  - agrupación de cargas repetidas.

  Si alguna difiere, el resultado será discrepancia o incompleto, nunca verificado.
- **Unidades:** si no son kN_m_C, el lector se detiene sin cambiarlas.
- **Plantilla:** los extras de plantilla (propiedades, patrones, casos, diafragmas y funciones) no se juzgan, salvo sus marcas de ejecución.
- **Diafragma de área:** se lee pero no se afirma. Hace falta confirmar en ETABS cómo representa «sin diafragma» para poder exigirlo.
- **Siguiente dependencia (Codex):**
  - prueba real sobre una copia guardada y reabierta;
  - recibir `sha256_edb` desde la respuesta aceptada del ejecutor;
  - actualizar los criterios a 13 magnitudes;
  - compartir el bloqueo;
  - presentar `estado`, `verificacion_global_del_plan` y `cobertura_plan` en servicios, UI e informe;
  - definir la política de aceptación.

  Este módulo no acepta ni aprueba nada por sí mismo.
