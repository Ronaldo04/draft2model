# Plan declarativo de operaciones ETABS

Estado: **entrega local v0.1 de Claude, 17 de octubre de 2026, pendiente de revisión e integración por Codex.** Desde una configuración [`modelo_estructural`](MODELO_ESTRUCTURAL.md) apta y su geometría versionada, genera la lista ordenada de llamadas a la API CSI que un ejecutor futuro aplicaría sobre una **copia** de la plantilla.

**Un plan no es una ejecución.** No contacta ni modifica ETABS, no ejecuta análisis, no aprueba el modelo ni certifica seguridad estructural. El plan lo declara así: `ejecutado: false`, `aprueba_modelo: false` y `certifica_seguridad_estructural: false`.

| Archivo | Contenido |
| --- | --- |
| [`draft2model/operaciones_etabs.py`](../draft2model/operaciones_etabs.py) | Generación (`generar_plan`), validación (`validar_plan`), lista blanca `FIRMAS`/`ENUMS`, verificación contra la DLL (`verificar_firmas_dll`) y CLI propia. |
| [`tests/test_operaciones_etabs.py`](../tests/test_operaciones_etabs.py) | 10 pruebas del subconjunto estático con configuración y geometría sintéticas aprobadas en carpetas temporales. |
| [`tests/test_operaciones_dinamicas.py`](../tests/test_operaciones_dinamicas.py) | 12 pruebas de modal Eigen y espectro de respuesta: plan, opciones, rechazos, regresión estática, firmas y despacho con un ETABSv1 falso con estado y los esquemas observados. |
| [`tests/test_esquema_csi_real.py`](../tests/test_esquema_csi_real.py) | 7 pruebas: esquema embebido igual a la lectura real, tablas editables importables, regresión de la corrida que devolvió -96 y script de lectura sin llamadas mutantes. |

No se modificaron el puente, `__main__`, `modelo_estructural.py` ni otros archivos.

**Ampliación del 17 de octubre de 2026:** el plan traduce ya los casos `modal_eigen` y `espectro_respuesta` y las funciones espectrales tabuladas del contrato. Ver la sección [Modal Eigen y espectro de respuesta](#modal-eigen-y-espectro-de-respuesta). La cobertura es con dobles: **no hay validación física** ni ejecución contra ETABS real de esta parte.

## Uso

```python
from pathlib import Path
from draft2model import operaciones_etabs as o, modelo_estructural as me

plan = o.generar_plan(Path("data/private"), me.cargar_configuracion(Path("config.json")),
                      destino_guardado=r"C:\...\salida\modelo.edb",  # absoluto, .edb; el ejecutor exige que no exista
                      tipo_shell_muro="ShellThin",                   # ShellThin | ShellThick | Membrane, sin valor por defecto
                      gravedad_programa_m_s2=9.80665)                # obligatoria con masa por patrones (ver abajo)
assert o.validar_plan(plan.datos) == []
```

Con la CLI propia (no se registra en `__main__`):

```powershell
.\.venv\Scripts\python.exe -m draft2model.operaciones_etabs --raiz data\private --entrada config.json --salida plan.json `
    --destino-guardado C:\ruta\nueva\modelo.edb --tipo-shell-muro ShellThin --gravedad-programa 9.80665
.\.venv\Scripts\python.exe -m draft2model.operaciones_etabs --verificar-firmas
```

`--salida` se crea en modo exclusivo y nunca se sobrescribe. Códigos de retorno:

- `0`: plan generado, o firmas sin diferencias;
- `1`: solicitud u opciones inválidas, o salida existente;
- `2`: configuración rechazada o firmas distintas de la DLL.

## Condiciones para generar un plan

1. `comprobar_configuracion(raiz, config)` devuelve `apto_para_adaptador: true`. Esto implica:
   - configuración consistente, sin faltantes, con aprobación declarada vigente;
   - geometría aprobada vigente, con hashes y cobertura comprobados.
2. La geometría se vuelve a consultar en `gestion_geometria`. Su `sha256_geometria` y su `huella_contenido` deben seguir coincidiendo con `geometria_origen`.
3. Toda característica de la configuración pertenece al subconjunto soportado. Si no, `ErrorPlanRechazado` (código 2) enumera **todos** los motivos y no se genera nada: no hay planes parciales ni omisiones silenciosas.

Las entradas no se modifican (se trabaja sobre una copia) y no se escribe nada en el expediente; las pruebas lo verifican.

## Subconjunto soportado y rechazos

| Se planifica | Se rechaza |
| --- | --- |
| Casos `estatico_lineal`, `modal_eigen` y `espectro_respuesta` | Caso espectral con `respuesta_rigida_espectral: true` (pendiente explícito en `pendientes`) |
| Espectros tabulados en m/s² | Falta u opción inválida de las opciones dinámicas: es un error de solicitud (código 1), no un rechazo |
| Masa `patrones` | Masa `explicita`: el contrato no indica a qué grados de libertad asignar la masa escalar |
| `gravedad_m_s2` igual a `gravedad_programa_m_s2` declarada | Gravedad no declarada o distinta. ETABS usa una gravedad interna que la API **no permite leer ni fijar**, y no se supone su valor. |
| Combinaciones `lineal` (0) y `envolvente` (1) | Combinación con el mismo nombre que un caso (ETABS lo prohíbe) |
| Cargas con componentes no nulas | Dos cargas sobre el mismo objetivo, patrón y dirección: la acumulación en ETABS no está verificada |
| Geometría con base y al menos un nivel superior | Un único nivel, o un nivel superior llamado `Base` |

Las cargas con todas sus componentes nulas no generan llamadas y se listan en `no_aplicados_por_api.cargas_sin_efecto`.

## Contrato del plan (`draft2model.plan_operaciones_etabs` 0.1.0)

| Campo | Contenido |
| --- | --- |
| `origen` | `configuracion_id`, `caso`, `datos_sinteticos`, `huella_configuracion`, `geometria {version_id, sha256_geometria, huella_contenido}`, `plantilla {id, version, sha256}`. |
| `comprobacion` | `apto_para_adaptador`, `geometria_comprobada`, `ejecutable_en_etabs: false`. |
| `unidades_etabs` | `kN_m_C` (el contrato fija m, kN, s, C; no hay conversión). |
| `api` | DLL y versión de archivo verificada. |
| `opciones` | Las tres opciones explícitas. |
| `precondiciones` | Copia de la plantilla con el SHA256 declarado; modelo vacío y nombres libres; parada sin reparación ante cualquier discrepancia; destino inexistente. |
| `constantes_adaptador` | Cada valor que la API exige y el contrato no aporta, con su motivo (ver abajo). |
| `pendientes` | Capacidades fuera del subconjunto. |
| `no_aplicados_por_api` | Sitio, fuentes e hipótesis (trazabilidad sin llamada), `combinaciones_resultados` (para la futura lectura de tablas) y cargas sin efecto. |
| `mapeo_ids` | ID de la configuración → nombre esperado en ETABS por colección. El nivel base se convierte en `Base`; los demás conservan su ID. |
| `operaciones` | Lista ordenada (formato abajo). |
| `resumen` | Número de operaciones por fase. |
| `huella_plan` | SHA256 del JSON canónico sin este campo. |

Cada operación tiene esta forma:

```json
{"orden": 20, "fase": "puntos", "interfaz": "SapModel.PointObj", "metodo": "cPointObj.AddCartesian",
 "argumentos": [{"nombre": "X", "tipo": "Double", "valor": 4.0}, ..., {"nombre": "Name", "tipo": "String&", "valor": ""},
                {"nombre": "UserName", "tipo": "String", "valor": "C0"}, ...],
 "retorno": {"tipo": "Int32", "esperado": 0}, "origen": "$.puntos.C0",
 "salidas": [{"parametro": "Name", "registra": "punto:C0", "debe_ser": "C0"}]}
```

- **Argumentos:** todos son explícitos, también los opcionales de la API, en el orden exacto de la firma. Los tipos con `&` son `ref`/`out`.
- **Enumeraciones:** `{"enum": "eUnits", "nombre": "kN_m_C", "valor": 6}`. En `GetNameList`, `valor: 0` con `nombre: null` significa "todos".
- **Referencias:** `{"ref": "punto:A0"}` apunta al nombre que registró una operación anterior; también puede ir dentro de arreglos.
- **`salidas`:** ETABS ignora `UserName` si el nombre ya existe. Por eso el ejecutor debe comprobar que el `Name` devuelto sea `debe_ser` y detenerse si no.
- **`verificar_ausentes`:** los nombres que el plan creará no deben aparecer en la lista devuelta.
- **`Count()`:** en estas operaciones, `retorno.esperado: 0` significa literalmente cero objetos.

`validar_plan(datos)` comprueba:

- contrato y huella;
- `ejecutado` y `aprueba_modelo` en `false`;
- orden consecutivo;
- pertenencia a la lista blanca, interfaz y tipo de retorno;
- nombres, tipos y orden de los argumentos;
- valores por tipo, incluidos los enteros de 32 bits y los valores de enumeración;
- referencias registradas antes;
- salidas sobre parámetros por referencia y sin duplicados;
- `cFile.Save` como única operación de guardado y en último lugar.

## Orden de las fases

| Fase | Llamadas (lista blanca) | Notas |
| --- | --- | --- |
| `verificacion` | `PointObj.Count`, `FrameObj.Count("All")`, `AreaObj.Count`; `GetNameList` de materiales, propiedades de área y frame, patrones, casos, combinaciones y diafragmas | Modelo vacío y nombres libres. Casos y combinaciones comparten espacio de nombres. |
| `unidades` | `SapModel.SetPresentUnits(kN_m_C)` | Antes de cualquier valor dimensional. |
| `pisos` | `Story.SetStories_2` | Base en la cota mínima; un piso por nivel superior, con altura igual a la diferencia de cotas. Debe preceder a los objetos. |
| `materiales` | `PropMaterial.SetMaterial(NoDesign)`, `SetMPIsotropic(E, ν, A=0)`, `SetWeightAndMass(1, peso)` | kN/m², kN/m³. |
| `secciones` | `PropArea.SetWall(Specified, tipo_shell_muro, material, espesor)`, `PropFrame.SetRectangle(material, T3=alto, T2=ancho)` | |
| `puntos` | `PointObj.AddCartesian(x, y, cota, Name&, UserName=ID, "Global", MergeOff=True, 0)` | Coordenadas desde `geometria_m` (metros). |
| `frames` | `FrameObj.AddByPoint(ref, ref, Name&, sección, ID)` | |
| `muros` | `AreaObj.AddByPoint(4, [inicio-inf, fin-inf, fin-sup, inicio-sup], Name&, sección, ID)` | Orden perimetral. |
| `patrones` | `LoadPatterns.Add(ID, Dead/Live/Quake/Other, multiplicador, AddAnalysisCase=False)` | muerta, viva, sismo, otro. |
| `cargas` | `PointObj.SetLoadForce([Fx,Fy,Fz,0,0,0])`; `FrameObj.SetLoadDistributed(MyType=1, Dir 4/5/6, 0→1 relativa)`; `AreaObj.SetLoadUniform(Dir 4/5/6)` | Una llamada por componente no nula en frames y muros, `Replace=False`, sistema `Global`. |
| `masa` | `PropMaterial.SetMassSource_1(masa propia, sin masas añadidas, desde cargas, patrones, factores)` | |
| `apoyos` | `PointObj.SetRestraint([Ux..Rz])` | |
| `diafragmas` | `Diaphragm.SetDiaphragm(ID, SemiRigid)`; `PointObj.SetDiaphragm(DefinedDiaphragm, ID)`; `Disconnect` para `sin_diafragma` | Todos los puntos quedan asignados explícitamente. |
| `casos` | `LoadCases.StaticLinear.SetCase`, `SetLoads(["Load"...], patrones, factores)` | |
| `combinaciones` | `RespCombo.Add(0 o 1)`, `SetCaseList(LoadCase, caso, factor)` | |
| `analisis` | `Analyze.SetRunCaseFlag("", False, All=True)` y después `True` por cada caso de `casos_ejecutar` | Solo marca; **no hay `RunAnalysis`** en la lista blanca. |
| `guardado` | `File.Save(destino_guardado)` | Única y última. |

El plan sintético de las pruebas (2 niveles, 8 puntos, 2 frames, 4 muros, 3 cargas con efecto y 1 sin efecto) tiene **57 operaciones**. Por fase: verificación 10, unidades 1, pisos 1, materiales 3, secciones 2, puntos 8, frames 2, muros 4, patrones 2, cargas 3, masa 1, apoyos 4, diafragmas 9, casos 2, combinaciones 2, análisis 2 y guardado 1.

### Constantes del adaptador

| Parámetro | Valor | Motivo |
| --- | --- | --- |
| `SetMPIsotropic.A` | 0 | El contrato no incluye coeficiente térmico ni cargas térmicas. |
| `SetMaterial.MatType` | `NoDesign` | Material isótropo lineal; no se infiere hormigón, acero ni albañilería. |
| `Temp` | 0 | Sin dependencia de la temperatura. |
| Color, notas y GUID | -1, `""`, `""` | Solo presentación. |
| `SetStories_2` | pisos maestros, sin empalmes, color 0 | Pisos independientes. |
| `AddCartesian.MergeOff` | `True` | Evita fusiones que cambiarían los identificadores. |
| `LoadPatterns.Add.AddAnalysisCase` | `False` | Los casos se crean desde la configuración. |

## Modal Eigen y espectro de respuesta

### Corrección del 17 de octubre de 2026: esquema CSI real

**Qué falló.** La primera ejecución dinámica real (Codex, plan sintético de 66 operaciones, corrida `tmp/d1/construccion/b8b0a4e5…`) se detuvo **antes de mutar** en la operación 13. `GetAllFieldsInTable('Load Cases - Response Spectrum')` devolvió **-96**: esa clave, deducida de cadenas de `ETABS.exe`, no existe como tabla editable.

**Qué se observó.** Una lectura real de solo lectura (`tmp/d1/tablas_dinamicas_reales.json` y `tablas_damping_reales.json`) mostró:

| Tabla real | Campos (importables salvo indicación) | Uso en el plan |
| --- | --- | --- |
| `Functions - Response Spectrum - User Defined` | `Name`, `Period` (sec), `Value`, `DampRatio`, `GUID`; no vacía en la copia: ya contiene funciones | Edición `agregar` de `Name`, `Period`, `Value`, `DampRatio`. |
| `Load Case Definitions - Response Spectrum` | `Name`, `MassSource` (no importable), `LoadName`, `Function`, `TransAccSF` (m/sec2), `RotAccSF`, `CoordSys` (no importable), `Angle`, `ModalCase`, `ModalCombo`, `RigidResp`, `f1`, `f2`, `RigidCombo`, `td`, `DirCombo`, `AbsSF`, `EccenRatio`, `OverStory`, `OverDiaph`, `OverEccen`, `DesignType`, `UserDesType`, `GUID`, `Notes`. **Sin `ConstDamp`.** | Edición `modificar` de `ModalCombo` y `RigidResp`. |
| `Load Case Definitions - Damping - Modal` | `Name`, `MaxFreq`, `DampType`, `ConstDamp`, `IntBy`, `IntTimeVal`, `IntDamping`, `ProBy`, `MassCoeff`, `StiffCoeff`, `ProTimeVal1`, `ProDamping1`, `ProTimeVal2`, `ProDamping2`, `Mode4Ratio`, `OverMode`, `OverDamp` | Edición `modificar` de `ConstDamp` del mismo `Name`, separada del caso. `DampType` no se toca. |

Estos datos están embebidos en `operaciones_etabs.ESQUEMAS_OBSERVADOS` (campos, importabilidad, unidades, versión y tipo de importación). Una prueba los compara con la evidencia real; los dobles de prueba se generan a partir de ellos. El retorno -96 para una tabla inexistente figura como `RETORNO_TABLA_INEXISTENTE_OBSERVADO`.

**Qué sigue sin observarse** (se protege, no se supone):

- **Textos de celda** `CQC`/`SRSS` (`ModalCombo`) y `No` (`RigidResp`). Antes de mutar, `verificar_textos` exige que la descripción real del campo, devuelta por `GetAllFieldsInTable`, los nombre como palabra completa. Si no los nombra, el plan se detiene por precondición.
- **Código de `GetModalComb_1`** (1 = CQC, 2 = SRSS, según la convención CSI documentada para SAP2000). Se comprueba tras editar; si difiere, la ejecución se detiene con incertidumbre.
- **Tipo de amortiguamiento** (`DampType`) de un caso espectral nuevo. No se escribe; `GetDampType` se registra en la traza sin compararse y `GetDampConstant` sí se compara.
- **Fila de damping:** que un caso espectral recién creado tenga ya su fila en `Load Case Definitions - Damping - Modal`. Si no la tiene, la edición se detiene (precondición, ya con mutaciones, por tanto con incertidumbre).

Para observarlos queda [`tmp/claude_lectura_damping.ps1`](../tmp/claude_lectura_damping.ps1), un script de **solo lectura** para que Codex lo revise y lo ejecute. Registra descripciones de campo, filas de muestra de las tres tablas y getters de los casos espectrales y modales del modelo abierto. No abre ni modifica modelos y su salida nunca sobrescribe.

### Qué ofrece la API de ETABS 21.1

| Dato del contrato | Vía exacta | Por qué |
| --- | --- | --- |
| `modal_eigen.numero_modos` | `LoadCases.ModalEigen.SetCase`, `SetNumberModes(Name, MaxModes, MinModes)` | Setter OAPI. |
| Parámetros eigen (no están en el contrato) | `ModalEigen.SetParameters(Name, EigenShiftFreq, EigenCutOff, EigenTol, AllowAutoFreqShift)` | Setter OAPI; valores exigidos como opción. |
| `espectro_respuesta.modal` | `ResponseSpectrum.SetModalCase` | Setter OAPI. |
| `direccion`, `espectro`, `factor` | `ResponseSpectrum.SetLoads(Name, 1, [U1/U2/U3], [función], [factor], ["Global"], [0])` | Setter OAPI. |
| Excentricidad de diafragma (no está en el contrato) | `ResponseSpectrum.SetEccentricity` | Setter OAPI; exigida explícita. |
| Función tabulada (`espectros`) | Tabla `Functions - Response Spectrum - User Defined` | `cFunctionRS` solo tiene `SetNTC2008`/`SetNTC2018` (normativas, no se usan); no existe `SetUser`. |
| `combinacion_modal` | `Load Case Definitions - Response Spectrum.ModalCombo` | Solo existe `GetModalComb`/`GetModalComb_1`. |
| Respuesta rígida (no está en el contrato) | `Load Case Definitions - Response Spectrum.RigidResp` | Afecta también a CQC y SRSS según la ayuda; se exige declararla. |
| `amortiguamiento` del caso | `Load Case Definitions - Damping - Modal.ConstDamp` | `cCaseResponseSpectrum` solo expone getters de damping (la DLL lo confirma). |

El amortiguamiento de la función (`DampRatio`) es un dato técnico explícito. La ayuda del programa indica que el espectro se ajusta desde ese valor al amortiguamiento real, y la definición del campo indica *"0.05 assumed"* si falta.

### Opciones explícitas adicionales

Son obligatorias **solo** si la configuración tiene las entidades correspondientes, con una entrada por cada caso o espectro. Faltar, sobrar, nombrar un caso inexistente o declarar un valor inválido es error de solicitud (código 1). Declararlas sin entidades también es error: no se ignoran.

| Opción | Forma | Uso |
| --- | --- | --- |
| `parametros_modales` | `{caso_modal: {frecuencia_desplazamiento_hz ≥ 0, frecuencia_corte_hz ≥ 0, tolerancia > 0, desplazamiento_automatico: bool}}` | `SetParameters` (cyc/s; 1/0). |
| `amortiguamiento_funciones` | `{espectro: 0 ≤ ξ < 1}` | `DampRatio` de cada fila de la función. |
| `excentricidad_espectral` | `{caso_espectral: razón ≥ 0}` | `SetEccentricity`. |
| `respuesta_rigida_espectral` | `{caso_espectral: bool}` | `false` → `RigidResp = No`. `true` rechaza el plan (pendiente: f1, f2 y combinación periódica+rígida). |

No se inventan valores normativos: el espectro, su amortiguamiento y los parámetros vienen de la configuración o de estas opciones.

### Fases y operaciones

El orden es `… casos` (estáticos), `casos_modales`, `funciones_espectrales`, `casos_espectrales`, `comprobacion_dinamica`, `combinaciones`, `analisis`, `guardado`.

- **Verificación** (antes de mutar):
  - `cFunction.GetNameList(FuncType 0)`: los nombres de función deben estar libres.
  - `GetAllFieldsInTable` de cada tabla usada (función; caso y damping si hay casos espectrales), con tres comprobaciones:
    - `verificar_presentes`: existen los campos;
    - `verificar_importables`: los campos editados son importables;
    - en la tabla del caso, `verificar_textos`: la descripción nombra los textos que se escribirán.
  - Un retorno distinto de 0 (como el -96 observado) es una precondición: la tabla no existe en esa versión.
- **`casos_modales`:** `SetCase`, `SetNumberModes(n, n)` y `SetParameters`.
- **`funciones_espectrales`:** `edicion_tabla` en modo `agregar`, con una fila por par `[periodo_s, aceleracion_m_s2]`.
- **`casos_espectrales`:** `SetCase`, `SetModalCase`, `SetLoads` y `SetEccentricity` por caso. Después, dos ediciones separadas en modo `modificar`:
  - en `Load Case Definitions - Response Spectrum`, `ModalCombo` y `RigidResp`;
  - en `Load Case Definitions - Damping - Modal`, `ConstDamp`.
- **`comprobacion_dinamica`:**
  - caso modal: `GetNumberModes`, `GetParameters` y `GetLoads` (0 cargas);
  - función: `cFunction.GetValues`;
  - caso espectral: `GetModalCase`, `GetLoads`, `GetEccentricity`, `GetDampConstant` (comparado) y `GetModalComb_1` (comparado), además de `GetDampType` (solo registrado, con `registrar_valores`).
- **`analisis`:** `SetRunCaseFlag` marca también los casos modales y espectrales. No hay `RunAnalysis`.

**Operación `edicion_tabla`.** Declara `tabla`, `modo`, `clave` (`Name`), `campos`, `registros` y las cuatro llamadas que usa:

1. `GetAllFieldsInTable` (importabilidad);
2. `GetTableForEditingArray`;
3. fusión por `Name`, conservando las filas ajenas;
4. `SetTableForEditingArray`, **solo con las columnas importables**, de modo que `MassSource` y `CoordSys` del caso no se escriben;
5. `ApplyEditedTables`, con cero errores fatales, errores y advertencias;
6. una nueva lectura que comprueba cada campo declarado.

`validar_plan` exige tabla, modo, clave, campos y llamadas de `TABLAS_EDITABLES`, que ahora contiene solo claves observadas. Un plan anterior con la clave inventada ya no supera la validación.

Con el ejemplo del contrato (EST, MOD con 3 modos, ESP-PRUEBA con 3 puntos, EX en UX con CQC y ξ = 0.05), el plan añade:

- 4 verificaciones previas;
- 3 operaciones modales;
- 1 edición de función;
- 4 llamadas espectrales y 2 ediciones (caso y damping);
- 10 relecturas.

Con la configuración de las pruebas suma **84 operaciones**.

### Constantes dinámicas del adaptador

Solo aparecen en planes con contenido dinámico.

| Parámetro | Valor | Motivo |
| --- | --- | --- |
| `SetNumberModes` | `MaxModes = MinModes = numero_modos` | El contrato fija un número de modos. |
| `SetLoads` | `U1/U2/U3`, `Global`, ángulo 0 | Traducción directa de UX/UY/UZ. |
| `SetLoads.SF` | `factor` | La función guarda el número igual a la aceleración en m/s²; ETABS lo trata como adimensional y el factor lleva las unidades de aceleración del modelo (m con kN_m_C). |
| `RigidResp` | `No` | Solo con `respuesta_rigida_espectral = false`. Texto no observado, exigido en la descripción real. |
| `Load Case Definitions - Damping - Modal.ConstDamp` | amortiguamiento del caso | Sin campo en el caso. `DampType` no se toca; se registra `GetDampType`. |
| Combinación direccional | no se fija | Una sola dirección por caso, así que no interviene. |

## Verificación de firmas contra la DLL instalada

`FIRMAS` contiene 56 métodos (34 del subconjunto estático y 22 modales, espectrales, de funciones y de tablas) con su ruta desde `SapModel`, el tipo de retorno y los parámetros con tipo y nombre exactos. `ENUMS` contiene los valores de enumeración usados.

`verificar_firmas_dll()` ejecuta Windows PowerShell 5.1 con `-EncodedCommand`, así que no depende de la directiva de scripts. Carga **solo los metadatos** de `ETABSv1.dll` por reflexión (`Assembly.LoadFrom`), sin iniciar ni contactar ETABS, y compara cada firma y cada valor.

Resultado del 17 de octubre de 2026 con `ETABSv1.dll` 1.29.0.0 (ETABS 21.1.0): **34 métodos y todos los valores de enumeración sin diferencias**. Tras la ampliación dinámica: **55 métodos sin diferencias**; con `GetDampType`, **56 sin diferencias** (`python -m draft2model.operaciones_etabs --verificar-firmas` y `test_firmas_dinamicas_contra_dll`). La prueba `test_firmas_contra_dll_instalada` repite la comprobación y otra prueba confirma que `comparar_firmas` detecta un tipo o un valor alterados.

La semántica se contrastó con la ayuda local `CSI API ETABS v1.chm`, descompilada en una carpeta temporal fuera del proyecto:

- `Dir` 4/5/6 = X/Y/Z globales y 10 = gravedad;
- `SetWeightAndMass` `MyOption` 1 = peso por volumen;
- `Combo.Add` 0 = aditiva lineal y 1 = envolvente; los nombres deben diferir de los casos;
- `AddCartesian` y `AddByPoint`: `UserName` se ignora si ya existe;
- `SetLoads`: `LoadType` = `"Load"`;
- `PointObj.SetDiaphragm` y sus opciones;
- `SetMassSource_1`.

La ayuda no documenta ninguna API para la gravedad, y `cOptions` solo tiene la carpeta de funciones.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_operaciones_etabs -v
```

Las pruebas usan una configuración sintética estática derivada del ejemplo, aprobada y ligada a una geometría sintética aprobada en un expediente temporal. Incluye cargas en punto, frame y muro, una carga nula y gravedad 9.80665 declarada en la configuración y en la opción. Cubren:

- **Orden y vínculo:** fases en orden, `Save` al final, sin `RunAnalysis`, pisos antes que puntos y puntos antes que frames; hashes de origen; huella determinista; configuración y expediente intactos (comparación byte a byte de toda la raíz).
- **Unidades y valores:** `kN_m_C` = 6; altura de piso 2.6; E, ν, peso, espesor, T3 y T2; coordenadas de B1 (4, 0, 2.6); esquinas de M1; direcciones y valores de las cargas; fuente de masa; diafragmas definidos o desconectados; factores de casos y combinaciones; destino.
- **No aptas:** configuración en borrador, cambio posterior a la aprobación y original alterado (código 2).
- **No soportadas:** respuesta rígida espectral declarada, masa explícita, gravedad ausente o distinta, cargas acumuladas, combinación con nombre de caso. Cada configuración es apta por sí misma; aun así, el plan completo se rechaza con su motivo.
- **Opciones inválidas:** código 1.
- **Manipulación:** `validar_plan` detecta huella, método fuera de la lista blanca, tipo, orden, referencia inexistente, valor de enumeración, `ejecutado` y guardado no final.
- **CLI:** salida nueva, sin sobrescritura.
- **Lista blanca:** sin análisis, cierre ni borrado; firmas contra la DLL.

Resultados del 17 de octubre de 2026: 10 de 10 pruebas correctas. La suite completa (`unittest discover -s tests`, con `TEMP`/`TMP` locales) dio 429 pruebas correctas, sin omisiones.

### Pruebas dinámicas

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_operaciones_dinamicas -v
```

Usan el ejemplo completo del contrato (EST, MOD, EX, ESP-PRUEBA, COMB1 = EST + EX), aprobado y ligado a una geometría sintética aprobada. Cubren:

- **Plan completo:** fases y dependencias en orden, argumentos exactos de cada setter, filas de la función, campos de la edición del caso, relecturas esperadas, verificaciones previas, marcas de ejecución, constantes dinámicas, mapeo de funciones, entradas y expediente intactos, huella determinista y validación.
- **Direcciones y combinación:** UY → U2, UZ → U3, SRSS → `ModalCombo` SRSS y `MyType` 2.
- **Opciones** (14 casos, código 1): cada opción ausente, parámetros eigen incompletos, tolerancia 0, frecuencia negativa, automático no booleano, amortiguamiento 1 o booleano, excentricidad negativa, rígida como texto, caso inexistente, espectro sin entrada.
- **Rechazos** (código 2): respuesta rígida y masa explícita.
- **`validar_plan`:** detecta la clave inventada anterior, `ConstDamp` en el caso, campo extra, valor vacío, modo cambiado, llamada de tabla suelta, mutación en verificación, tolerancia excesiva, presentes sobre un parámetro de entrada, textos vacíos, `registrar_valores` sobre una entrada e importables en otro método.
- **Regresión estática:** 57 operaciones, sin fases ni constantes dinámicas; una opción dinámica sin casos que la usen es un error.
- **Firmas:** 56 contra la DLL.
- **Despacho:** 5 pruebas; se describen en [EJECUTOR_ETABS.md](EJECUTOR_ETABS.md).

Resultado de la ampliación (40 de 40). Tras la corrección del esquema real, en las pruebas pertinentes (`test_esquema_csi_real`, `test_operaciones_dinamicas`, `test_operaciones_etabs`, `test_ejecutor_etabs`): **47 de 47 correctas, sin omisiones**, con la evidencia `tmp/d1` presente. No se ejecutó la suite completa porque Codex trabaja en paralelo.

## Limitaciones

- **Ejecución:** el ejecutor está en [EJECUTOR_ETABS.md](EJECUTOR_ETABS.md). Codex ejecutó en real el subconjunto estático (42 operaciones, ver [ENSAYO_ETABS_ANALISIS.md](ENSAYO_ETABS_ANALISIS.md)). La única ejecución dinámica real se detuvo antes de mutar por la clave de tabla inventada, ya corregida. **Ninguna mutación modal ni espectral se ha ejecutado aún contra ETABS real.**
- **Observado en una instancia real:** las claves y campos de las tres tablas, su importabilidad y sus unidades (`ESQUEMAS_OBSERVADOS`), y el retorno -96 para una tabla inexistente.
- **Dinámico, por confirmar en una instancia real** (cualquier discrepancia se detiene antes de mutar o en la relectura, con incertidumbre). El script de solo lectura `tmp/claude_lectura_damping.ps1` ayuda a observarlo:
  - los textos `CQC`/`SRSS` y `No`; los protege `verificar_textos` sobre la descripción real;
  - que `GetModalComb_1` devuelva 1/2 para CQC/SRSS;
  - el texto o código de `DampType` de un caso espectral nuevo, y que sea constante (`GetDampType` se registra, no se compara);
  - que la fila del caso aparezca en `Load Case Definitions - Damping - Modal` nada más crearlo;
  - qué hace ETABS con las columnas no importables omitidas al reescribir la tabla del caso;
  - que `ApplyEditedTables` no emita advertencias benignas, que hoy detendrían el plan;
  - que la tabla de funciones conserve las funciones ajenas al reescribirla fusionada;
  - que un caso modal nuevo no tenga cargas iniciales;
  - que `cFunction.GetNameList` con `FuncType` 0 liste todas las funciones.
- **ApplyEditedTables:** la ayuda CSI advierte que un error fatal puede dejar el modelo corrupto y recomienda guardar antes. El plan trabaja sobre una copia desechable; un fallo deja incertidumbre y obliga a descartarla.
- **Validación física:** las pruebas dinámicas usan dobles y comprueban traducción, orden y detección de efectos no aplicados. No comprueban periodos, formas modales ni respuestas espectrales; eso requiere análisis real y comparación con una referencia.
- **Planes estáticos anteriores:** su contenido cambia solo en `pendientes` (ya no lista modal ni espectro). Un plan estático generado antes de esta ampliación no regenera idéntico y el ejecutor lo rechaza: hay que regenerarlo, por ejemplo el de `tmp/etabs_sintetico_real_002`.
- **Comportamiento real sin comprobar** con una plantilla de referencia:
  - `SetStories_2` sobre la plantilla real;
  - `SetRunCaseFlag` con `Name=""` y `All=True`;
  - si un patrón `Quake` creado con `Add` exige parámetros de carga lateral automática;
  - la orientación local del shell de muro;
  - la acumulación de cargas con `Replace=False`.
- **Gravedad:** depende de una declaración externa; se recomienda comprobarla en ETABS antes de declarar `gravedad_programa_m_s2`.
- **Plantilla:** el plan exige una copia vacía de objetos. No reutiliza objetos de la plantilla ni comprueba otros ajustes de la plantilla, como opciones de mallado o de análisis.
- **Fuera del contrato y de este plan:** respuesta rígida espectral, masas puntuales, losas, liberaciones, offsets, resortes, P-Delta, mallado y modificadores de rigidez.
- **Alcance:** la `representacion` declarada (shell isotrópico) no se calibra ni se valida como albañilería. Plan y modelo siguen requiriendo revisión de ingeniería.
