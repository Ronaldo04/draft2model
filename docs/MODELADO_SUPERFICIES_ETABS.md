# Modelado de superficies: configuración 0.2 y operaciones ETABS

Estado al 19 de octubre de 2026. Este incremento es **fundamento de pisos y paneles**, no la representación completa del proyecto de referencia. Tiene configuración 0.2 y plan 0.2 implementados y probados con datos sintéticos y dobles. Sigue **sin autorización de ejecución** en ETABS: no se retiró ni se eludió `BLOQUEO_INTEGRACION`. No se usó API ni ETABS real; tampoco instalaciones ni la suite global.

Archivos:
- [`draft2model/modelo_estructural.py`](../draft2model/modelo_estructural.py)
- [`draft2model/operaciones_etabs.py`](../draft2model/operaciones_etabs.py)
- [`scripts/ejecutar_plan_etabs.ps1`](../scripts/ejecutar_plan_etabs.ps1)
- Pruebas: [`tests/test_modelo_superficies.py`](../tests/test_modelo_superficies.py) y [`tests/test_operaciones_superficies.py`](../tests/test_operaciones_superficies.py)

Base geométrica: [geometría de superficies v0.2](GEOMETRIA_SUPERFICIES.md) y [plan de representación](PLAN_REPRESENTACION_REFERENCIA.md).

## 1. Versiones y despacho

| Elemento | 0.1 (intacto) | 0.2 (nuevo) |
|---|---|---|
| Configuración | `VERSION = "0.1.0"` | `VERSION_SUPERFICIES = "0.2.0"`, despacho por `version_contrato` |
| Geometría exigida | cualquiera consistente | **solo 0.2.0**; otra versión se rechaza, no se reinterpreta |
| Resultado | `apto_para_adaptador` | `apto_para_adaptador` **siempre falso**; además `geometria_aprobada_por_huella` y `apto_para_plan_desarrollo` |
| Plan | `generar_plan` / `validar_plan` (0.1.0) | `generar_plan_superficies` / `validar_plan_superficies` (0.2.0, `estado = plan_desarrollo_no_ejecutable`, `ejecutable = false`) |

**El camino 0.1 se conserva byte a byte.** Se comparó con los módulos originales:
- 4305 validaciones idénticas (`a_dict`), con mutaciones de cada campo y con o sin geometría;
- los planes estático y dinámico 0.1 son idénticos en JSON;
- la salida `a_dict` de 0.1 no gana campos.

## 2. Configuración 0.2

Claves raíz: las de 0.1 más `asignaciones_superficies` y `vertices_compartidos`.

**Puntos**, con los campos exactos de una sola alternativa y sin coordenadas inferidas:
- `{id, nodo_geometria, nivel_geometria}`: punto heredado. Usa el XY del nodo y la cota del nivel.
- `{id, vertice_geometria}`: vértice XYZ de la geometría 0.2, en metros desde `geometria_m` (nunca píxeles). Puede estar a **cota intermedia** sin crear un Story.

**`vertices_compartidos`** `{vertice_geometria, punto, fuente}`: declara que un vértice se modela con un punto nodo+nivel existente. Sirve para unir una losa con columnas o muros. Exige **igualdad exacta** de coordenadas; no fusiona por proximidad.

**Reglas que generan error:**
- **Puntos:**
  - un vértice sin punto;
  - un punto que no usa ningún muro, frame ni superficie (**huérfano**);
  - dos puntos con coordenadas idénticas (**no se fusionan en silencio**);
  - un vértice con punto propio y además compartido.
- **Conexión:** todo grupo de puntos unido por frames, muros o superficies debe llegar a un **apoyo declarado** («conexión ausente»).
- **Secciones:**
  - la sección nueva `shell_losa_homogenea` (`espesor_m`, material isótropo lineal y fuente) es una placa homogénea de prueba y **no equivale a una losa aligerada**;
  - `shell_muro` y `frame_rectangular` se conservan;
  - el material debe ser compatible.
- **Asignaciones:**
  - cobertura completa de las superficies de la geometría;
  - la sección debe ser compatible;
  - `papel_geometrico` no elige sección ni rigidez;
  - una superficie vertical no admite sección de losa.
- **Cargas:** `objetivo_tipo = superficie`, en `kN/m2`, sistema global y tres componentes.
- **Masa:**
  - solo por patrones, con el control de doble peso propio heredado;
  - la masa puntual escalar se rechaza en 0.2.
- **Diafragmas:**
  - los puntos deben ser coplanares según su coordenada z real, también para puntos XYZ;
  - un diafragma de un solo punto se rechaza como falso;
  - la exclusión debe justificarse.
- **Trazabilidad:** fuentes, hipótesis, revisión por huella y cobertura heredadas de 0.1.

**Disponibilidad.**
- `geometria_aprobada_por_huella` es verdadera si la geometría 0.2 es consistente, no tiene faltantes y su único bloqueo es `BLOQUEO_INTEGRACION`. Es decir, la revisión está aprobada con la huella vigente.
- `apto_para_plan_desarrollo` es verdadero si, además:
  - la configuración es consistente y está aprobada;
  - la evidencia geométrica está comprobada;
  - los únicos bloqueos son `BLOQUEO_INTEGRACION` y `BLOQUEO_SUPERFICIES`.
- `apto_para_adaptador` permanece **falso**. Todos los consumidores existentes (gestión, normalización, evidencia de análisis, ejecutor) siguen rechazando 0.2.

## 3. Plan 0.2 de desarrollo

`generar_plan_superficies(raiz, config, **opciones)`. Opciones: las de 0.1, más `tipo_shell_losa`. `tipo_shell_muro` y `tipo_shell_losa` son **obligatorias si existen secciones de ese tipo y se rechazan si no existen**. En la línea de comandos se usa `python -m draft2model.operaciones_etabs ... --tipo-shell-losa`, que despacha según la versión de la configuración.

Fases: verificación, unidades, pisos, materiales, secciones, puntos, frames, muros, superficies, comprobacion_objetos, patrones, cargas, masa, apoyos, diafragmas, casos, combinaciones, análisis y guardado.

- **Puntos:** `AddCartesian` con XYZ declaradas y `MergeOff=True`. Los vértices compartidos no se duplican.
- **Superficies:** `cAreaObj.AddByPoint` con `NumberPoints` igual al número real de vértices y el contorno **en el orden exacto** de la geometría, sin triangular, reordenar ni fusionar. ETABS debe devolver como `Name` el ID declarado (`superficie:ID`).
- **Losa:** `cPropArea.SetSlab` con `SlabType=Slab (0)`, `ShellType` explícito, material y espesor.
- **Cargas:** `cAreaObj.SetLoadUniform` con Dir 4/5/6 globales, por unidad de **área real** (no proyectada).
- **Relectura (`comprobacion_objetos`)**, comparada con tolerancia relativa de 1e-12:
  - `GetCoordCartesian` de cada punto;
  - `GetPoints` y `GetProperty` de cada muro y superficie;
  - `GetSlab` y `GetWall` (material y espesor; los enumerados solo se registran).
- **Rechazo del plan completo:** un punto fuera de [cota base, cota tope], o un contorno **cóncavo** (geometría válida, pero transporte aún no verificado en ETABS).
- **Declaraciones en el plan:** `trazabilidad_superficies` (vértices geométricos, puntos, papel, procedencia, sección, área y normal), `integracion_pendiente`, `pendientes` y `constantes_adaptador`. Los ejes locales de ETABS **no** se fijan ni se declaran iguales a la normal geométrica.

## 4. Firmas contrastadas

Firmas obtenidas por **reflexión de metadatos** de la DLL local `ETABSv1.dll` 1.29.0.0 (ETABS 21.1.0), el 19-10-2026, sin iniciar ETABS. Registro en `tmp/superficies_qa/firmas_reflejadas.json`.

- `cPropArea.SetSlab(String Name, eSlabType SlabType, eShellType ShellType, String MatProp, Double Thickness, Int32 color, String notes, String GUID)`
- `cPropArea.GetSlab(...)` y `cPropArea.GetWall(...)`: los mismos parámetros, por referencia.
- `cAreaObj.GetPoints(String Name, Int32& NumberPoints, String[]& Point)`
- `cAreaObj.GetProperty(String Name, String& PropName)`
- `cPointObj.GetCoordCartesian(String Name, Double& X, Double& Y, Double& Z, String CSys)`
- `eSlabType`: Slab 0, Drop 1, Ribbed 3, Waffle 4, Mat 5, Footing 6. Solo se usa Slab.

`AddByPoint` y `SetLoadUniform` ya estaban en la lista blanca y se reconfirmaron. Con `verificar_firmas_dll()`, las **62 firmas** de `FIRMAS` coinciden con la DLL, sin diferencias. `$MetodosPermitidos` del script PowerShell es igual a `FIRMAS`; una prueba lo exige. Ampliar la lista no habilita una ejecución, porque el ejecutor Python solo prepara planes 0.1.

## 5. Pruebas y resultados

```powershell
$env:TEMP=(Resolve-Path tmp/superficies_qa).Path; $env:TMP=$env:TEMP
.venv/Scripts/python.exe -m unittest tests.test_modelo_superficies tests.test_operaciones_superficies
```

**Casos válidos:**
- un piso homogéneo sintético: losa S1 sobre cuatro columnas, con vértices compartidos;
- un panel inclinado S2 de 0 a 1.3 m, entre N0 = 0 y N1 = 2.6, sin piso ficticio.

**Casos inválidos:**
- referencias y cobertura;
- cotas;
- coincidencias;
- conexión;
- material;
- diafragmas falsos;
- masa;
- unidades;
- retornos de ETABS: fallo parcial, ID devuelto distinto y coordenada releída distinta, que detienen el script **sin guardar**.

**Dobles usados, que no acreditan ETABS ni solver:**
1. **Gestión aprobada por huella**: `consultar_version` sustituido en la prueba (ver §6). El caso en borrador usa la gestión real.
2. **Script PowerShell real** en modo doble contra un `ETABSv1` falso con estado. Es el mismo generador que usan las pruebas del ejecutor, con cuerpos que guardan puntos, áreas y propiedades para releerlos.

Resultados y regresiones: ver el marcador `seguimiento/ENTREGA_CLAUDE_SUPERFICIES_ETABS.json` y los logs en `tmp/superficies_qa/`.

## 6. Qué falta integrar (Codex)

1. **Gestión integrada por Codex (incremento162):** una aprobación declarada 0.2 se vincula a consistencia, ausencia de faltantes y huella exacta. Puede conservarse sin retirar `BLOQUEO_INTEGRACION`; `disponible_para_modelado` sigue falso. Las pruebas `test_gestion_superficies` usan versiones reales en disco y generan un plan de desarrollo desde configuración aprobada; no sustituyen la consulta de gestión.
2. **Configuración 0.2 integrada en gestión e interfaz:** la revisión declarada requiere geometría aprobada por huella, campos de revisión y confirmación; no habilita ejecución. Regresión focal162:49 pruebas (una comprobación de enlaces realizada separadamente en host) y estados del cliente0.1/0.2. La revisión profesional y los datos físicos del caso real siguen pendientes.
3. **Ejecutor**: aceptar el plan 0.2 (`validar_plan_superficies` y la regeneración con `generar_plan_superficies`) solo tras revisar el recorrido completo, y después retirar los bloqueos de forma explícita.
4. **Lectura posterior** (normalización, controles, informe) y **prueba local en ETABS** sobre una copia: coordenadas, contornos, sección, cargas y fuente de masa tras guardar y reabrir.

## 7. Límites

- **Fuera de alcance:** aberturas o huecos, aligerados (nervios más capa o equivalencia revisada), acciones de agua, efecto hidrodinámico y apoyos de tanque, y escalera completa. Un piso con huecos **no** puede representarse como un polígono relleno.
- **Sin inferencias:** no se infieren cargas, espesores, materiales ni valores normativos de los planos. Todo valor es declarado con su fuente.
- **Concavidad:** los contornos cóncavos se rechazan en el transporte, aunque la geometría los admita.
- **Cargas de área:** el constructor no las relee; el lector independiente añadido en incremento163 sí captura y compara `GetLoadUniform` tras reapertura con dobles. Falta integración y prueba real.
- **Bloqueos:** `BLOQUEO_INTEGRACION` y `BLOQUEO_SUPERFICIES` permanecen. Ningún plan 0.2 es ejecutable ni aprueba el modelo.

## Formulación de losas por sección (R241, encargo 09)

`tipo_shell_losa` admite dos formas.

**Texto global.** Una sola formulación (`ShellThin`, `ShellThick` o `Membrane`) para todas las secciones de losa. Es compatible con versiones anteriores; el plan añade un aviso porque no distingue pisos de fondos o tapas.

**Objeto por sección.** Tiene la forma `{sección: {tipo, funcion, justificacion}}` y debe cubrir **exactamente** todas las secciones de losa:
- `funcion` admite `piso`, `fondo_deposito`, `tapa_deposito` u `otra`. Se declara; no se deduce de que el polígono sea horizontal.
- La justificación es obligatoria.
- `Membrane` se rechaza en fondos y tapas de depósito, porque no resiste la presión normal por flexión.
- Un piso que no sea `Membrane` lleva un aviso de E.030 art. 30.8, que exige excluir la rigidez fuera del plano de las losas de piso en el modelo sísmico.

**Trazabilidad.** El plan registra la decisión en `idealizacion_losas`. `SetSlab` usa la formulación de cada sección y `GetSlab` la compara en la relectura. La relectura del modelo guardado espera y compara el `shell` de cada propiedad.

**Interfaz.** El panel de construcción ofrece controles explícitos por sección: función, formulación y justificación. No admite un JSON como segunda autoridad.

**Línea de comandos (BRECHA_CLI_247).** `plan-etabs` dirige las configuraciones 0.4 **y 0.5** al generador de malla y líquidos. Hay dos opciones **mutuamente excluyentes**; usar ambas termina con código 2:
- `--tipo-shell-losa <ShellThin|ShellThick|Membrane>`: formulación global, por compatibilidad.
- `--tipo-shell-losa-json <archivo>`: el mapa por sección, que se lee con el cargador JSON estricto. Se rechazan un archivo ilegible, un JSON inválido, un valor que no sea objeto o un objeto vacío. La cobertura, los tipos, la función y la justificación los valida el generador.

```powershell
.venv/Scripts/python.exe -m draft2model plan-etabs --raiz data/private --entrada cfg05.json --salida plan05.json `
  --destino-guardado D:uta
ueva\modelo.edb --tipo-shell-muro ShellThin --gravedad-programa 9.80665 `
  --tipo-shell-losa-json losas.json
```

Ejemplo de `losas.json` (no aprueba una solución estructural):

```json
{"PISO": {"tipo": "Membrane", "funcion": "piso", "justificacion": "Idealización de piso revisada"},
 "FONDO": {"tipo": "ShellThick", "funcion": "fondo_deposito", "justificacion": "Flexión fuera del plano revisada"}}
```

Pruebas: `tests/test_cli_plan_etabs_247.py` (despacho, conflicto, archivos inválidos y plan 0.5 real por la entrada pública).

**Límites.** No implica efectos hidrodinámicos ni cumplimiento por elegir `Membrane`.
