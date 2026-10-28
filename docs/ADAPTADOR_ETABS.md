# Adaptador ETABS: puente local

Estado: **infraestructura local v0.1 entregada por Claude el 16 de octubre de 2026, pendiente de revisión e integración por Codex.** Conecta Python con la API CSI instalada de ETABS 21 mediante un puente de Windows PowerShell 5.1 y archivos JSON locales.

Esta entrega **no construye modelos**. Abrir una copia de plantilla no convierte la geometría ni el contrato estructural en objetos ETABS, no ejecuta análisis y no produce resultados.

| Archivo | Contenido |
| --- | --- |
| [`draft2model/adaptador_etabs.py`](../draft2model/adaptador_etabs.py) | Preparación de solicitudes, ejecución con tiempo límite, bloqueo exclusivo, validación de respuestas, copia verificada de plantillas y códigos de retorno. |
| [`scripts/puente_etabs.ps1`](../scripts/puente_etabs.ps1) | Puente PowerShell 5.1 que usa `ETABSv1.dll` instalada. |
| [`tests/test_adaptador_etabs.py`](../tests/test_adaptador_etabs.py) | Pruebas con un proceso doble y con el puente real en rutas que fallan antes de la API. |

No se instalaron dependencias. No se modificaron `__main__.py`, `modelo_estructural.py` ni otros módulos.

## Por qué PowerShell 5.1

La API de CSI obtiene la instancia activa con `Marshal.GetActiveObject`, que no existe en .NET Core. Por eso PowerShell 7 falla, mientras que Windows PowerShell 5.1 (.NET Framework) funciona. Codex lo comprobó fuera del sandbox y esta entrega lo confirmó con el propio puente (sección [Verificación real](#verificación-real-de-solo-lectura)).

El puente se ejecuta con `powershell.exe -NoProfile -NonInteractive -File scripts\puente_etabs.ps1`, respetando la política de ejecución del equipo. Si el entorno impide ejecutar el archivo, se informa el error; no se desactivan políticas. Codex retiró la opción Bypass incluida en la primera entrega. El script se guarda en UTF-8 **con BOM**, porque PowerShell 5.1 lee como ANSI un `.ps1` sin BOM y algunas letras acentuadas se convertirían en comillas. Una prueba lo comprueba. El cálculo SHA256 usa .NET para no depender de que Get-FileHash esté disponible como cmdlet.

## Flujo de una corrida

1. `AdaptadorEtabs.preparar(operacion, parametros)` valida los parámetros, crea `<trabajo>/<uuid>/` (carpeta nueva) y escribe `solicitud.json`. Devuelve una `SolicitudPreparada` en modo **`preparado`** con el `argv` exacto; no ejecuta nada.
2. `ejecutar(preparada)`:
   - adquiere el bloqueo exclusivo;
   - lanza el proceso con `timeout_s`;
   - guarda `salida_puente.txt` (stdout/stderr, como máximo 1 MiB de cada uno);
   - valida `respuesta.json` y escribe `registro.json`.
3. El puente valida la solicitud y el sistema de archivos **antes** de cargar la DLL. Solo entonces se conecta a ETABS, ejecuta una operación y publica la respuesta con un `Move` que falla si el archivo ya existe.

Ningún archivo de la corrida se sobrescribe. Una solicitud ya ejecutada no puede ejecutarse otra vez; hay que preparar una nueva.

### Modos

| Modo | Qué significa |
| --- | --- |
| `preparado` | Solicitud y comando escritos; nada ejecutado. |
| `doble` | Proceso sustituto (`ConfiguracionPuente.doble`), solo para pruebas. Se rechaza una respuesta doble que declare `modo_ejecucion: real`. |
| `real` | `ConfiguracionPuente.real`: puente PowerShell contra la API instalada. Exige Windows y `powershell.exe`. |

La respuesta debe declarar el mismo modo configurado y el mismo `id_solicitud`, contrato y operación. Si no, se rechaza.

## Contratos JSON

**Solicitud** (`draft2model.etabs_solicitud` 0.1.0): `id` (32 hexadecimales), `operacion`, `parametros`, `creado_utc`, `modo_configurado` y opcionalmente `dll`. La ruta predeterminada de la DLL es `C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll`.

**Respuesta** (`draft2model.etabs_respuesta` 0.1.0):

- identificación: `version_puente`, `modo_ejecucion`, `id_solicitud`, `operacion`;
- resultado: `estado` (`ok` o `error`), `error {tipo, mensaje, codigo_api}`, `datos`, `avisos`;
- trazabilidad: `inicio_utc`, `fin_utc` y `entorno` (versión y edición de PowerShell, 64 bits).

Python la lee con el lector JSON estricto del proyecto: rechaza claves repetidas y `NaN`. El tamaño máximo es configurable (256 MiB por defecto).

## Operaciones

| Operación | API usada | Modifica ETABS | Escribe archivos |
| --- | --- | --- | --- |
| `diagnosticar` | `GetOAPIVersionNumber`, `GetVersion`, `GetProgramInfo`, `GetPresentUnits`, `GetModelFilename`, `GetModelIsLocked` | No | No |
| `abrir_copia_plantilla` | `CreateObjectProgID` + `ApplicationStart` (instancia nueva) o `GetObject`/`GetObjectProcess`; `File.OpenFile` | Sí: carga la copia | Copia en carpeta nueva (Python) |
| `leer_tablas` | `Analyze.GetCaseStatus`, `RespCombo.GetNameList`, `DatabaseTables.GetAvailableTables`, `SetLoadCasesSelectedForDisplay`, `SetLoadCombinationsSelectedForDisplay`, `GetTableForDisplayArray` | Solo la selección de visualización (se restauran los casos) | No |
| `guardar_como` | `File.Save(destino)` | Sí: el archivo actual pasa a ser el destino | `.edb` nuevo |

Firmas comprobadas por reflexión sobre la `ETABSv1.dll` instalada (versión de archivo 1.29.0.0). El puente **no contiene** `RunAnalysis`, `ApplicationExit`, `SetPresentUnits`, `InitializeNewModel` ni `SetModelIsLocked`; una prueba estática lo verifica.

### Reglas por operación

- **Selección de instancia:** con `id_proceso` se usa `GetObjectProcess`. Sin él, se exige exactamente un proceso ETABS; con varios, se rechaza (precondición) en lugar de elegir uno.
- **`abrir_copia_plantilla(plantilla, sha256_esperado, destino, instancia=...)`:**
  - Python verifica el SHA256 de la plantilla, crea `destino` (que no debe existir), copia sin sobrescribir y vuelve a verificar la copia y la plantilla;
  - si algo no coincide, borra solo la carpeta que acaba de crear y no ejecuta el puente;
  - el puente recibe **solo la copia**, recalcula su huella dos veces (al validar e inmediatamente antes de `OpenFile`) y confirma que el modelo abierto es la copia;
  - `instancia="activa"` descarta el modelo abierto sin guardarlo, por lo que exige `reemplazar_modelo_activo=True`;
  - `instancia="nueva"` deja ETABS abierto (el puente nunca lo cierra) e informa el `id_proceso` nuevo si es único.
- **`leer_tablas(modelo_esperado, tablas, casos=..., combinaciones=...)`:**
  - el modelo abierto debe ser `modelo_esperado`;
  - cada caso debe existir y tener estado 4 (análisis terminado). El puente **no ejecuta análisis**: si faltan resultados, se rechaza;
  - las combinaciones deben existir, aunque no se comprueba el estado de sus casos componentes (aviso);
  - las tablas deben aparecer en `GetAvailableTables`;
  - las filas se filtran además por `OutputCase`;
  - los valores se devuelven como texto, en las unidades presentes del modelo, que se informan y no se cambian.
- **`guardar_como(modelo_esperado, destino)`:** el destino `.edb` no debe existir, ni al preparar ni al ejecutar. Python verifica que el SHA256 del archivo guardado coincide con el informado.

## Códigos

**Python** (`codigo_salida(error)`, para una futura CLI):

| Código | Error | Caso |
| --- | --- | --- |
| 1 | `ErrorAdaptador` | Parámetros, rutas, operación no admitida o futura, destino existente. |
| 2 | `ErrorEvidenciaEtabs` | Plantilla, copia o archivo guardado con una huella distinta. |
| 3 | `ErrorPuente` (`tipo`, `corrida`, `respuesta`, `codigo_proceso`) | Salida distinta de 0, respuesta ausente, ilegible, ajena o incoherente, API no disponible, precondición. |
| 4 | `ErrorTiempo` | Tiempo agotado: el árbol de procesos se termina (`taskkill /T /F`) y el estado de ETABS es desconocido. |
| 5 | `ErrorBloqueo` | Otra corrida mantiene el bloqueo. |

**Puente** (código de salida → `tipo`): 10 `solicitud`, 20 `api_no_disponible`, 30 `api` (con `codigo_api`), 40 `precondicion`, 41 `evidencia` (se traduce a `ErrorEvidenciaEtabs`), 50 `inesperado` o respuesta no publicable.

## Bloqueo exclusivo

`BloqueoExclusivo` bloquea el byte 0 de un archivo (`msvcrt.locking`; `fcntl.flock` fuera de Windows). Por defecto el archivo es `<trabajo>/puente_etabs.lock`. Para serializar todas las corridas de la máquina, todos los adaptadores deben compartir la misma ruta.

El sistema operativo libera el bloqueo si el proceso muere, así que no quedan bloqueos huérfanos. El archivo no se borra; su contenido (pid y hora) es informativo.

## Interfaz para el contrato estructural

`PuenteEtabs` es un `Protocol` con `ejecutar_operacion(operacion, parametros) -> RespuestaPuente`, y `AdaptadorEtabs` lo cumple. `OPERACIONES` describe cada operación (si modifica la instancia y si escribe archivos). `OPERACIONES_FUTURAS` reserva `aplicar_modelo_estructural`, que hoy se rechaza con código 1.

Para añadir esa operación cuando `modelo_estructural.py` esté aceptado:

1. Python: añadir la entrada a `OPERACIONES` y su validación en `validar_parametros`. Debe exigir:
   - un resultado con `apto_para_adaptador` verdadero, su `huella_contenido` y la versión y huella geométricas exactas;
   - la copia abierta (`modelo_esperado`).
2. Puente: añadir `Test-<Operacion>` (sin API) e `Invoke-<Operacion>` al registro `$Operaciones`. Comprobar cada código de retorno con `Assert-Api` y no ejecutar análisis salvo que se defina una operación separada, explícita y autorizada.
3. Pruebas: doble para el flujo y pruebas reales solo cuando se autorice modificar ETABS.

## Verificación

### Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_adaptador_etabs -v
```

Las 23 pruebas cubren:

- **Preparación:** modo preparado sin ejecución; operaciones no admitidas o futuras; validación de parámetros.
- **Doble:** diagnóstico trazable; tiempo agotado con proceso terminado y bloqueo liberado; salida distinta de 0; respuesta ausente, ajena, que finge modo real o incoherente; evidencia; doble ejecución rechazada.
- **Bloqueo:** un **proceso separado** retiene el bloqueo, lo que da `ErrorBloqueo` sin respuesta; al morir ese proceso, la corrida funciona.
- **Plantillas:** copia verificada con el original intacto y sin enviar el original al puente; plantilla alterada (código 2, sin copia ni corrida); cambio durante la copia (copia descartada); destinos existentes intactos.
- **Guardar y leer:** huella del guardado verificada o rechazada; casos explícitos.
- **Puente estático:** BOM, llamadas prohibidas, lista de procesos no desenrollada, operaciones iguales en Python y PowerShell.
- **Puente real sin API** (se omiten sin PowerShell 5.1). Cada caso usa una DLL inexistente o falla en la validación previa, sin conectarse a ETABS:
  - DLL ausente (20);
  - operación desconocida (10);
  - copia alterada (41);
  - destino aparecido después de preparar (40);
  - respuesta existente no sobrescrita (50).

### Verificación real de solo lectura

El 16 de octubre de 2026 se ejecutó `diagnosticar` real con el puente (sin abrir, guardar ni analizar nada). Resultado:

- ETABS Ultimate 21.1.0, proceso 16320;
- modelo `(Untitled)`, unidades `lb_in_F`, no bloqueado;
- OAPI 1.029, PowerShell 5.1.26100 de 64 bits.

`numero_version` devolvió 0.

Esa corrida descubrió un error que ya está corregido. Con un solo proceso, PowerShell 5.1 desenrollaba la lista, y `Count` del diccionario resultante contaba sus 2 claves, de modo que se informaban falsamente "2 instancias". El puente lo rechazaba por precondición, no elegía mal. Tras la corrección, `diagnosticar` sin `id_proceso` detecta un único proceso. `leer_tablas` real se detuvo correctamente en la comprobación del modelo esperado (precondición 40), sin seleccionar casos ni leer tablas.

## Limitaciones

Codex añadió un bloqueo persistente de incertidumbre: si una operación que puede cambiar estado agota el tiempo, se conserva `<bloqueo>.incierto.json` y se rechazan nuevas operaciones salvo diagnóstico. `confirmar_recuperacion(motor_inactivo_declarado=True, revisor_declarado=..., motivo=...)` requiere comprobación externa, archiva la evidencia y libera el bloqueo bajo exclusión. No cierra ETABS ni autentica la declaración; terminar el cliente no demuestra que el servidor COM haya terminado. Una interrupción brusca del proceso Python fuera de su manejo de timeout todavía necesita reconciliación mediante el registro de corridas general.

- **No comprobado contra ETABS real:**
  - `abrir_copia_plantilla`, `leer_tablas` con un modelo analizado y `guardar_como`, porque este encargo prohíbe modificar ETABS;
  - la forma exacta de `GetTableForDisplayArray` con `FieldKeyList = @('')` (todos los campos);
  - `SetLoadCombinationsSelectedForDisplay` con una lista vacía;
  - el comportamiento de `GetObjectProcess`;
  - deben probarse con una plantilla y un modelo analizado de referencia cuando se autorice.
- **No hay plantilla `.edb` de referencia** en el proyecto; la operación exige una ruta y un SHA256 explícitos.
- **Instancia nueva:** si ETABS se inicia por COM, su proceso no es hijo del puente. Un tiempo agotado no lo cierra, y `ApplicationStart` puede tardar más que el tiempo límite predeterminado (120 s).
- **Selección de visualización:** `leer_tablas` cambia la selección de casos para visualización y la restaura. La de combinaciones no se puede leer y queda modificada.
- **Tablas grandes:** se convierten a JSON con `ConvertTo-Json` de PowerShell 5.1, que es lento con tablas grandes; no se paginan.
- **Abrir modelos:** `OpenFile` puede mostrar diálogos de ETABS (por ejemplo, de versión de archivo) que bloqueen hasta el tiempo límite.
- **Integridad:** las huellas detectan cambios accidentales, no ediciones deliberadas coherentes.
- **Sin CLI ni interfaz:** la integración en `__main__` corresponde a Codex.
