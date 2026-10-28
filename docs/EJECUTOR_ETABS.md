# Ejecutor del plan ETABS

Estado: **entrega local v0.1 de Claude, 17 de octubre de 2026, pendiente de revisión e integración por Codex.** Ejecuta el [plan declarativo](OPERACIONES_ETABS.md) sobre la copia de la plantilla abierta en ETABS:

- **Subconjunto estático:** Codex lo ejecutó después en real (42 operaciones).
- **Ampliación modal y espectral:** solo se verificó con el script real contra un ensamblado `ETABSv1` falso; **no se ha ejecutado contra ETABS real**.

Construir y guardar el modelo **no** ejecuta análisis, no aprueba el modelo y no certifica seguridad estructural.

| Archivo | Contenido |
| --- | --- |
| [`draft2model/ejecutor_etabs.py`](../draft2model/ejecutor_etabs.py) | `EjecutorPlanEtabs.preparar` y `ejecutar`, configuraciones real y doble, verificación posterior y marca de incertidumbre. |
| [`scripts/ejecutar_plan_etabs.ps1`](../scripts/ejecutar_plan_etabs.ps1) | Despacho tipado por reflexión en Windows PowerShell 5.1, con traza por operación. |
| [`tests/test_ejecutor_etabs.py`](../tests/test_ejecutor_etabs.py) | 18 pruebas con un ensamblado .NET falso, un proceso doble y comprobaciones estáticas. `generar_cs` acepta cuerpos C# con estado por método. |
| [`tests/test_operaciones_dinamicas.py`](../tests/test_operaciones_dinamicas.py) | 5 pruebas de despacho modal y espectral contra un ETABSv1 falso con estado (además de las pruebas del plan). |

**Corrección del 17 de octubre de 2026 (esquema CSI real):** la única ejecución dinámica real se detuvo antes de mutar porque `GetAllFieldsInTable` devolvió -96 para la clave inventada `Load Cases - Response Spectrum`. Las tablas editables del script son ahora las observadas:

- `Functions - Response Spectrum - User Defined`;
- `Load Case Definitions - Response Spectrum`;
- `Load Case Definitions - Damping - Modal`, donde está el amortiguamiento, separado del caso.

Además:

- la edición escribe solo columnas importables;
- `verificar_importables`, `verificar_textos` y `registrar_valores` son nuevas comprobaciones;
- un retorno no nulo de `GetAllFieldsInTable` se informa como precondición (tabla inexistente);
- los dobles reproducen los esquemas observados ([`tests/test_esquema_csi_real.py`](../tests/test_esquema_csi_real.py) los compara con la evidencia).

**Ampliación del 17 de octubre de 2026 (modal y espectro):**

- **Script:** admite lecturas `Get*` después de mutar (relecturas), las comprobaciones `verificar_presentes` y `verificar_valores`, y la operación compuesta `edicion_tabla` (sección [Ediciones de tabla](#ediciones-de-tabla)).
- **Pruebas:** la lista blanca del script incluye las 21 firmas nuevas de `FIRMAS`.
- **Alcance:** el ensayo real de Codex (42 operaciones estáticas) no cubre esta parte. **Modal y espectro no se han ejecutado contra ETABS real.**

No se modificaron el adaptador, el puente, `__main__`, `cli_etabs.py`, `normalizacion_etabs.py` ni los módulos del plan. Se reutilizan:

- de [`adaptador_etabs`](../draft2model/adaptador_etabs.py): `AdaptadorEtabs.ejecutar` (bloqueo, marca de incertidumbre, tiempo límite, terminación del árbol de procesos, registro y validación de la respuesta), sus errores y códigos;
- de [`operaciones_etabs`](../draft2model/operaciones_etabs.py): `generar_plan`, `validar_plan`, `FIRMAS` y `ENUMS`.

## Uso

```python
from pathlib import Path
from draft2model import ejecutor_etabs as ej, modelo_estructural as me
import json

ejecutor = ej.EjecutorPlanEtabs(ej.configuracion_real(Path("tmp/etabs").absolute()))  # mismo bloqueo que cli_etabs
preparada = ejecutor.preparar(Path("data/private"), me.cargar_configuracion(Path("config.json")),
                              json.loads(Path("plan.json").read_text(encoding="utf-8")),
                              copia=Path(r"C:\...\copia\plantilla.edb"),
                              modelo_esperado=Path(r"C:\...\copia\plantilla.edb"))   # modo 'preparado': nada ejecutado
resultado = ejecutor.ejecutar(preparada, confirmar_mutacion=True)                   # obligatorio en modo real
```

Antes de llamar a `preparar`, la copia debe estar abierta con `adaptador_etabs.abrir_copia_plantilla` (o `cli_etabs abrir-copia --ejecutar`).

### Modos

| Modo | Cómo se obtiene | Qué garantiza |
| --- | --- | --- |
| `preparado` | `preparar(...)` | Solicitud, plan y comando escritos en una corrida nueva. Nada ejecutado. |
| `doble` | `configuracion_doble(trabajo, comando)` o `configuracion_doble_powershell(trabajo, dll_prueba)` | El script **rechaza** la DLL firmada por CSI: un doble nunca contacta la API real. La respuesta declara `doble`. |
| `real` | `configuracion_real(trabajo)` y `ejecutar(..., confirmar_mutacion=True)` | El script **exige** el token de clave pública de CSI (`453d728ef24c6f5e`). |

La línea de comandos es `powershell.exe -NoProfile -NonInteractive -File scripts\ejecutar_plan_etabs.ps1`. No se pasa `-ExecutionPolicy` ni se elude ninguna directiva: si la política del equipo bloquea el script, el bloqueo se respeta.

## Comprobaciones antes de mutar

**En Python, durante `preparar`:**

1. `validar_plan(plan)` sin problemas.
2. **Regeneración:** `generar_plan(raiz, configuracion, **plan["opciones"])` debe dar un plan idéntico en JSON canónico. La regeneración vuelve a exigir `apto_para_adaptador`, geometría vigente con sus huellas y el subconjunto soportado. Un plan alterado con `huella_plan` rehecha pasa `validar_plan`, pero aquí se rechaza.
3. **Copia y destino:**
   - la copia existe, no es un enlace y su SHA256 es igual a `origen.plantilla.sha256`;
   - `modelo_esperado` es la copia;
   - `destino_guardado` no existe y su carpeta sí.
4. Se escriben `plan.json` y `solicitud.json` en una corrida nueva. El argumento `-Sha256Solicitud` lleva la huella de los bytes de la solicitud.

**En Python, al llamar a `ejecutar`:** el modo real exige `confirmar_mutacion=True`. Se vuelven a comprobar el destino inexistente y la huella de la copia.

**En el script, antes de conectar:**

1. Huella de la solicitud (si no coincide, evidencia 41) y el `id` igual al nombre de la corrida.
2. **Plan:**
   - orden consecutivo;
   - lista blanca, copia de `FIRMAS` (una prueba exige que coincidan);
   - la fase `verificacion` solo contiene lecturas (`Count`, `Get*`) y precede a toda mutación; las lecturas posteriores son relecturas;
   - los tres métodos de tabla solo aparecen dentro de una `edicion_tabla`, y la tabla, el modo y la clave deben estar entre las tablas editables del script;
   - `SetPresentUnits` una sola vez, como primera mutación y con `kN_m_C`;
   - `cFile.Save` única, final y hacia el destino declarado.
3. Destino inexistente y huella de la copia.
4. **DLL:** existe, su versión de archivo es la verificada para el plan (`1.29.0.0`) y su token corresponde al modo.
5. **Firmas y argumentos:** cada operación se resuelve como `MethodInfo` de `ETABSv1.<interfaz>`. Retorno, tipos y nombres de parámetros deben coincidir exactamente con el plan; si no, firma 42. Todos los argumentos se convierten en simulación: enumeraciones con nombre y valor según la DLL, arreglos tipados, enteros de 32 bits y referencias registradas antes.

**En el script, ya conectado, antes de la primera mutación:**

- `GetObject` o `GetObjectProcess(id_proceso)`, y el modelo abierto (`GetModelFilename`) debe ser la copia;
- los objetos de cada interfaz se obtienen recorriendo la ruta declarada (`SapModel.LoadCases.StaticLinear`, ...) y deben implementar la interfaz;
- las operaciones de verificación del plan se ejecutan primero: `Count` debe ser 0 y `verificar_ausentes` no debe encontrar nombres ya usados.

## Despacho

Para cada operación, en orden:

1. **Argumentos:** se resuelven las referencias con el mapeo de nombres de salidas anteriores y se construye un `object[]` tipado.
2. **Comprobaciones previas:** antes de `cFile.Save` se repiten la comprobación del destino y la del modelo abierto. Antes de invocar una operación que no es de lectura se marca `mutaciones_realizadas`, porque una excepción a mitad de llamada puede haber mutado.
3. **Traza:** se escribe la línea `inicio` en `traza.jsonl`.
4. **Llamada:** `MethodInfo.Invoke(objetivo, valores)`. Los parámetros `ref`/`out` vuelven en `valores`. **Ningún texto se evalúa como código.**
5. **Resultado:**
   - el retorno debe ser `retorno.esperado`;
   - cada salida debe ser igual a `debe_ser`, y se registra (ETABS ignora `UserName` si ya existe);
   - se comprueban `verificar_ausentes` y `verificar_presentes` (por ejemplo, los campos de `GetAllFieldsInTable`);
   - con `verificar_valores`, cada salida releída se compara con lo asignado: números con tolerancia relativa del plan (1e-12), textos exactos, arreglos elemento a elemento y con la misma longitud;
   - tras `SetPresentUnits`, `GetPresentUnits` debe ser `kN_m_C`;
   - tras `Save`, el destino debe existir y se calcula su SHA256.
6. **Traza:** se escribe la línea `fin`, con el retorno, las salidas, los `releidos` y, en el guardado, el SHA256.

Al primer error se escribe la línea `error`, se informa `orden_fallida` y se termina. No hay reintentos, reparaciones ni deshacer. La copia en disco no se modifica, porque el guardado va a un destino nuevo, y no se borra nada.

### Ediciones de tabla

Una operación `edicion_tabla` del plan se marca como mutación y deja una línea `inicio` y otra `fin` (con `metodo: edicion_tabla` y retorno 0), igual que las demás operaciones; el formato es el que comprueba `revision_modelo`. Las cuatro llamadas (`GetAllFieldsInTable`, `GetTableForEditingArray`, `SetTableForEditingArray` y `ApplyEditedTables`) se resuelven por reflexión con sus firmas exactas antes de conectar. Al ejecutarse:

1. `GetAllFieldsInTable(tabla)`: retorno 0; si no, precondición (tabla inexistente). Cada campo declarado debe existir y ser importable.
2. `GetTableForEditingArray(tabla, "")`, comprobando que `TableData` tenga campos × registros valores.
3. **Columnas:** las de la tabla actual o, si está vacía, las declaradas. Cada campo declarado debe estar entre ellas. Después se quitan las **no importables**; en el caso espectral observado son `MassSource` y `CoordSys`.
4. **Fusión por la clave (`Name`):**
   - en `agregar`, ningún registro existente puede tener ese nombre (si no, precondición); se conservan todas las filas existentes y se añaden las declaradas, con texto vacío en las columnas no declaradas;
   - en `modificar`, un registro por nombre, que debe existir; se cambian solo los campos declarados en todas sus filas.
5. `SetTableForEditingArray` con todas las filas y las columnas importables.
6. `ApplyEditedTables(true, …)`: retorno 0 y **cero** errores fatales, errores y advertencias. Si no, error `api` con los recuentos y hasta 4000 caracteres del registro de importación. Una advertencia como *"0.05 assumed"* revelaría un campo no aplicado.
7. **Nueva lectura:**
   - en `agregar`, el número de filas de cada nombre debe ser el declarado y cada registro declarado debe aparecer;
   - en `modificar`, todas las filas del nombre deben tener los valores declarados;
   - los números se comparan como decimales con punto (cultura invariante) y el resto como texto exacto.

El resumen (`registros_totales`, `registros_declarados`, `columnas_escritas`, `info` y el registro de importación) va en la línea `fin`.

En una operación normal, `verificar_importables` exige que esos campos de `GetAllFieldsInTable` sean importables. `verificar_textos` exige que la `Description` real del campo nombre cada texto como palabra completa: así no se escribe un texto de celda no confirmado. `registrar_valores` copia salidas a `releidos` sin compararlas.

## Respuesta, verificación y resultado

La respuesta (`draft2model.etabs_respuesta`, operación `ejecutar_plan`) incluye `progreso`: `operaciones_totales`, `operaciones_ejecutadas`, `mutaciones_realizadas`, `orden_fallida` y `mapeo_nombres`. Si la ejecución termina bien, también incluye `datos`:

- `version_dll`, `modelo_abierto`, `unidades`;
- `guardado {ruta, sha256}`, `huella_plan`;
- `analisis_ejecutado: false`, `aprueba_modelo: false`.

Python vuelve a verificar:

- el destino existe y su SHA256 coincide;
- se ejecutaron todas las operaciones;
- el mapeo de nombres es igual al de las salidas del plan;
- la huella del plan es la preparada;
- la traza tiene una línea `fin` por operación;
- se declaran sin análisis y sin aprobación.

Después escribe `resultado_ejecucion.json`. La corrida conserva `plan.json`, `solicitud.json`, `respuesta.json`, `traza.jsonl`, `salida_puente.txt` y `registro.json`.

Para enlazar con la lectura de resultados, el modelo guardado debe analizarse en una operación futura, explícita y autorizada. Después, `leer_tablas` del adaptador aporta `version`, `modelo`, `unidades`, `casos`, `estado_casos` y `tablas`, que es lo que espera `normalizacion_etabs`.

## Errores, incertidumbre y bloqueo

| Situación | Error (código) | Incertidumbre |
| --- | --- | --- |
| Plan no idéntico al regenerado, configuración o evidencia no vigentes, copia distinta, solicitud alterada | `ErrorEvidenciaEtabs` (2) | No |
| Destino existente, `modelo_esperado` distinto de la copia, real sin confirmación | `ErrorAdaptador` (1) | No |
| Precondición o firma en el script antes de mutar (modelo equivocado, nombres ocupados, `Count` distinto de 0, DLL o token) | `ErrorPuente` (3), `tipo` `precondicion`, `firma`, `api` o `api_no_disponible` | No |
| Retorno distinto de 0, excepción de la API, nombre reasignado o guardado sin archivo **después** de mutar | `ErrorPuente` (3), `tipo` `api` | **Sí** |
| Proceso sin respuesta con traza de mutación iniciada | `ErrorPuente` (3) | **Sí** |
| Tiempo agotado | `ErrorTiempo` (4); el árbol de procesos se termina | **Sí** (la escribe el adaptador) |
| Otra corrida activa o incertidumbre pendiente | `ErrorBloqueo` (5) | — |

Cada error incluye `traza`, `progreso`, `incierto` y `corrida`.

**Incertidumbre:** se usa el mismo archivo `<bloqueo>.incierto.json` que el adaptador. Mientras exista, se bloquea toda operación salvo `diagnosticar`. Para levantarla hay que comprobar externamente el estado de ETABS y registrarlo con `AdaptadorEtabs.confirmar_recuperacion(...)` o `cli_etabs recuperar`, que archiva la evidencia sin borrarla.

**Bloqueo:** la ruta por defecto, `<trabajo>/puente_etabs.lock`, es la misma del adaptador. Para serializar con `cli_etabs`, use la misma carpeta de trabajo o pase la misma ruta de bloqueo.

## Pruebas

```powershell
$env:TEMP = "$PWD\tmp\ejecutor_temp"; $env:TMP = $env:TEMP   # si el sandbox restringe la carpeta temporal
.\.venv\Scripts\python.exe -m unittest tests.test_ejecutor_etabs -v
```

**Despacho real contra .NET falso** (8 pruebas, requieren PowerShell 5.1):

- *Cómo se monta:* la prueba genera desde `FIRMAS`/`ENUMS` un ensamblado C# `ETABSv1` con las mismas interfaces, firmas, enumeraciones, propiedades y `Helper`. Lo compila con `Add-Type`, con versión de archivo 1.29.0.0 y sin firma CSI. Cada llamada queda registrada con sus argumentos de entrada.
- *Comportamientos configurables por variables de entorno:* fallo, excepción, renombrado, recuentos, nombres ocupados, modelo, ausencia de instancia y guardado sin archivo.
- **Flujo completo:** las 57 llamadas en el orden exacto del plan. Comprueba:
  - enumeraciones (`eUnits.kN_m_C=6`, `eCNameType.LoadCase=0` por referencia, `eMatType` 0 = todos);
  - arreglos (`SetStories_2`, esquinas de muro);
  - referencias resueltas (`A0`, `A1`);
  - salidas `Name`, mapeo, traza de 2 líneas por operación, guardado y unidades;
  - copia intacta, sin `RunAnalysis` y sin incertidumbre.
- **Fallo intermedio** (`AddByPoint` devuelve 3): ninguna llamada posterior, `orden_fallida`, línea de error, `mutaciones_realizadas`, destino no creado e incertidumbre persistente que bloquea la siguiente corrida hasta registrar la recuperación.
- **Excepción de la API y nombre reasignado:** detenidos, con incertidumbre.
- **Precondiciones sin mutaciones** (solo lecturas registradas, sin incertidumbre): puntos existentes, nombre ocupado, modelo equivocado, sin instancia.
- **Solicitud manipulada:** evidencia sin llamadas. Con la huella rehecha y un tipo cambiado: firma 42, sin llamadas.
- **Guardado:** un destino existente se rechaza y no se toca; un `Save` sin archivo es un error con incertidumbre.
- **Modo real** con la DLL falsa: sin confirmación, error 1; con confirmación, rechazo por token antes de conectar.
- **Modo doble** con la DLL de CSI: rechazo por token antes de crear `Helper`. Solo se cargan metadatos.

**Preparación y transporte** (7 pruebas, proceso doble en Python):

- plan alterado con huella rehecha;
- configuración cambiada y original alterado;
- copia o modelo distintos;
- tiempo agotado con incertidumbre y bloqueo posterior;
- fallo parcial y salida sin respuesta tras mutar, con incertidumbre;
- fallo previo sin incertidumbre;
- bloqueo retenido por otro proceso, con la misma ruta que el adaptador.

**Estáticas** (3 pruebas): BOM; sin `Invoke-Expression`, `RunAnalysis`, `ApplicationExit`, `ExecutionPolicy` ni compilación dinámica; lista blanca igual a `FIRMAS`; configuración real sin `Bypass`.

Resultado del 17 de octubre de 2026: **18 de 18 correctas**. Suite completa (`unittest discover -s tests`, `TEMP`/`TMP` locales): **456 correctas, sin omisiones**.

**Despacho modal y espectral** (5 pruebas en `tests/test_operaciones_dinamicas.py`, requieren PowerShell 5.1):

- *Cómo se monta:* script real en modo doble contra un ETABSv1 falso. Los campos, la importabilidad y el retorno -96 de tabla inexistente se generan desde `ESQUEMAS_OBSERVADOS`, es decir, desde la evidencia real, no escritos a mano. Las descripciones de campo y los textos de celda del doble **no** son observados: llevan la marca `DOBLE`. `generar_cs` recibe cuerpos C# con estado.
- *Comportamientos configurables por variables de entorno:* función previa, campo ausente, campo no importable, descripción sin el texto, función ocupada, advertencia de importación y setter que devuelve 0 sin aplicar.
- **Flujo completo:** el orden exacto, con cada `edicion_tabla` expandida en importabilidad → leer → escribir → aplicar → releer. Comprueba:
  - argumentos de `SetNumberModes(MOD, 3, 3)` y `SetLoads(EX, 1, [U1], [ESP-PRUEBA], [1], [Global], [0])`;
  - la función previa `UnifRS` se conserva (5 filas);
  - la escritura del caso usa exactamente las columnas importables observadas (sin `MassSource` ni `CoordSys`) y conserva `Function`; `ModalCombo` pasa a CQC y `RigidResp` a No;
  - la tabla de damping recibe `ConstDamp` 0.05 sin cambiar `DampType`;
  - `GetDampConstant` se relee como 0.05 y `GetDampType` se registra; sin `RunAnalysis` y sin incertidumbre.
- **Regresión de la corrida real** `b8b0a4e5…`: una solicitud con la clave inventada da precondición con `codigo_api` -96 en la misma operación de verificación, sin mutaciones y sin incertidumbre.
- **Verificaciones previas sin mutar:** campo ausente (`DampRatio`), `ConstDamp` no importable, descripción que no nombra `No` y función ya existente.
- **Advertencia de `ApplyEditedTables`:** error `api` con los recuentos; la última llamada es `ApplyEditedTables`, no se crea el caso espectral y queda incertidumbre.
- **Efecto no aplicado aunque el setter devuelva 0** (`SetEccentricity`, `SetNumberModes` y `ApplyEditedTables`): lo detecta la relectura correspondiente (`GetEccentricity`, `GetNumberModes` o la nueva lectura de la tabla), que se detiene con incertidumbre.

Resultado de la ampliación: 40 de 40. Tras la corrección del esquema real: `test_esquema_csi_real` 7/7, `test_operaciones_dinamicas` 12/12, `test_operaciones_etabs` 10/10 y `test_ejecutor_etabs` 18/18 (**47 de 47, sin omisiones**). No se ejecutó la suite completa porque Codex trabaja en paralelo. **Es cobertura con dobles; no es validación física.**

## Limitaciones

- **Ninguna mutación modal ni espectral se ha ejecutado contra ETABS real.** Las claves, campos e importabilidad de las tres tablas sí están observados. Siguen por confirmar (ver [OPERACIONES_ETABS.md](OPERACIONES_ETABS.md); el script de solo lectura `tmp/claude_lectura_damping.ps1` ayuda a observarlo):
  - los textos `CQC`/`SRSS`/`No`;
  - el código de `GetModalComb_1`;
  - `DampType`;
  - la existencia inmediata de la fila de damping del caso.

  Si no coinciden, el plan se detiene en la verificación previa o en la relectura, nunca de forma silenciosa. Falta comprobar también:
  - que `ApplyEditedTables` no emita advertencias benignas, que hoy detendrían la ejecución;
  - que la reescritura fusionada sin las columnas no importables no altere filas ajenas ni esas columnas.
- **ApplyEditedTables:** la ayuda CSI advierte que un error fatal puede dejar el modelo corrupto. Se ejecuta solo sobre la copia desechable y cualquier fallo deja incertidumbre.
- **El subconjunto estático sí se ejecutó en real** (Codex, 42 operaciones; ver [ENSAYO_ETABS_ANALISIS.md](ENSAYO_ETABS_ANALISIS.md)). Lo que sigue a continuación queda pendiente para el resto. Falta comprobar sobre la API COM:
  - que `MethodInfo.Invoke` de la interfaz funciona sobre los objetos COM de ETABS (`__ComObject`);
  - que `IsInstanceOfType` reconoce la interfaz;
  - que los arreglos `ref` vuelven por el `object[]`;
  - que los recorridos por propiedades (`$objeto.$segmento`) se comportan como en el puente;
  - la semántica pendiente del plan (pisos, `SetRunCaseFlag`, patrón `Quake`, acumulación de cargas).
- **Una sola instancia sin `id_proceso`:** se usa `GetObject` (instancia activa) y se protege con la comprobación del modelo abierto. Con varias instancias conviene indicar `id_proceso`.
- **Sin deshacer:** un fallo deja la copia abierta en un estado parcial. Debe descartarse y repetir desde una copia nueva tras registrar la recuperación.
- **Diálogos:** si ETABS muestra un diálogo modal, la llamada puede bloquearse hasta el tiempo límite (900 s por defecto) y quedar en incertidumbre.
- **Rendimiento:** la traza se escribe por operación. Para planes grandes, la conversión y la escritura son lineales; no se midieron con modelos grandes.
- **Sin análisis ni CLI:** la integración en `cli_etabs` o en `__main__` corresponde a Codex.
