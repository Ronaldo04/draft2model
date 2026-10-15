# Control de avance local y publicado

Abrir **[Abrir control de avance.cmd](../Abrir%20control%20de%20avance.cmd)** desde la carpeta del proyecto. Inicia Python del entorno .venv y abre el navegador en `http://127.0.0.1:8765/`. El tablero necesita que ese proceso siga funcionando; cerrar solamente la pestaña no lo detiene. Para detenerlo, cerrar su ventana o usar Ctrl+C.

Alternativa desde PowerShell:

```powershell
.\.venv\Scripts\python.exe seguimiento/control.py
```

El servidor escucha exclusivamente en esta computadora. No publica un sitio ni modifica GitHub. No requiere instalar dependencias nuevas.

## Qué significa cada estado

| Estado | Evidencia |
| --- | --- |
| Pendiente | No hay evidencia suficiente del criterio. |
| En desarrollo | Solo está presente parte de la entrega definida. |
| Implementado | Están los archivos esperados; falta comprobación vigente. |
| Verificado | Pruebas pertinentes pasan sobre los archivos exactos, existe revisión declarada con huellas vigentes o se comprobó un metadato remoto. |
| Bloqueado | Hay una condición externa identificada que falta resolver. |

El porcentaje es **criterios verificados / criterios definidos**, con el mismo peso por criterio. No mide esfuerzo ni predice fecha de finalización. El catálogo vigente tiene 41 criterios distribuidos entre O0 y O6 (versión 1.3.0; evaluador, entrada/salida y cliente probado sin red se distinguen de la ejecución y precisión reales), desglosados del plan existente; no sustituye la aceptación global de cada hito. O0 controla desarrollo del proyecto; el dashboard técnico estructural previsto en O5 sigue pendiente.

## Actualización

- Al abrir: inventario actual, comprobación de pruebas y consulta de GitHub si existe autenticación disponible.
- Cada 2 segundos: detectar archivos nuevos, modificados o eliminados mediante metadatos y huellas de contenido. Se conserva historial local entre sesiones; no se ejecuta mientras el proceso esté detenido. Una edición y reversión completa entre dos lecturas puede no observarse.
- Código o pruebas modificados: esperar 3 segundos de quietud y ejecutar unittest en un proceso separado, con límite de 120 segundos. Las pruebas verificadas se vinculan a las huellas de sus archivos y dependencias declaradas. Si cambian durante la ejecución, no se acredita esa ejecución y se programa otra.
- Las pruebas omitidas por capacidades del entorno se registran por nombre y módulo. Una suite sin fallos puede contener omisiones; esas pruebas no acreditan el criterio y se muestran como comprobaciones pendientes.
- Cada 60 segundos: consultar GitHub con autenticación propia de lectura. Un fallo conserva la fecha de la última consulta y se muestra como desconexión; no se fabrica un estado remoto vacío.
- Una modificación invalida la comprobación afectada inmediatamente. Los cambios sin criterio asociado se registran como pendientes de clasificación y no aumentan porcentajes.

La interpretación automática es deliberadamente limitada: reconoce archivos asociados, pruebas y evidencias con huellas. No determina por sí sola que una nueva función satisface un requisito de ingeniería. La nueva funcionalidad y los criterios de aceptación que no estén descritos en el catálogo necesitan revisión y asociación explícita. Ningún sistema puede deducir perfectamente el cumplimiento técnico a partir de cualquier edición arbitraria.

## Local y GitHub

Ambas vistas utilizan el mismo catálogo local. La comparación se hace contra el commit consultado de la rama predeterminada, no contra trabajo sin subir o ramas aún no integradas. Las diferencias distinguen solo local, diferente y solo GitHub; no se hace push, pull ni borrado automático.

El estado publicado se evalúa sobre sus propios archivos. Si una prueba local pasa y los archivos y dependencias exigidos por el criterio son idénticos a los publicados, se indica **prueba local sobre archivos publicados idénticos**. No se presenta como CI ejecutada en GitHub. Las revisiones publicadas se leen del commit correspondiente; no se ejecuta código remoto.

Los criterios de repositorio privado e Issues se comprueban en la vista publicada, porque son propiedades remotas y no de la carpeta local. Por ello los porcentajes de ambas vistas pueden diferir incluso antes de considerar archivos pendientes de publicar.

## Conectar el remoto

La sesión del conector de GitHub del chat no se hereda en un programa Python independiente. Se incluye una lectura inicial obtenida con ese conector, guardada en `tmp/control_avance/github.json`, con fecha y SHA reales. Es una lectura guardada, no una conexión continua.

El controlador detecta, en este orden, `GH_TOKEN`/`GITHUB_TOKEN`, GitHub CLI autenticado o una credencial Git ya configurada. No imprime credenciales ni abre un inicio de sesión automáticamente.

También se puede pulsar **Conectar GitHub** y proporcionar en la página local un token de acceso detallado, limitado a `Ronaldo04/draft2model`, con Contents de solo lectura. El token se conserva únicamente en memoria hasta detener el controlador. Nunca debe pegarse en el chat ni guardarse en el repositorio. Crear el token requiere la intervención del titular de la cuenta; el tablero no puede concederse ese acceso.

La lectura usa las API oficiales de [ramas](https://docs.github.com/en/rest/branches/branches#get-a-branch) y [árboles Git](https://docs.github.com/en/rest/git/trees#get-a-tree), fijando la comparación al commit consultado. Un árbol truncado se rechaza.

## Mantenimiento de criterios y evidencias

- `seguimiento/hitos.json`: catálogo versionado. Cada criterio declara archivos, pruebas y dependencias pertinentes (`check_files`). Al cambiar dependencias de código, actualizar este conjunto para que una prueba no se considere vigente por error.
- `seguimiento/evidencias.json`: revisiones declaradas; cada una identifica criterio, revisor, fecha, nota y huellas Git de los archivos revisados. Una revisión no autentica al declarante ni sustituye aprobación de ingeniería.
- `tests/test_control_avance.py`: comprobaciones de regresiones, evidencia desactualizada y separación local/remoto.
- `tmp/control_avance/`: inventario, pruebas e historial generado, excluidos de GitHub. No editar estos archivos para simular avance.

Al agregar un módulo nuevo, asociar sus archivos y pruebas al criterio correcto. Si introduce requisitos nuevos, desglosarlos en criterios antes de acreditar su cumplimiento. No cerrar criterios generales de ETABS, visión o informe por la existencia de archivos con esos nombres.

Los originales privados se observan mediante huellas locales; su actividad se identifica de forma opaca. Se excluyen sus archivos de la comparación publicable, así como entornos, secretos y temporales. El historial tiene un máximo de 500 eventos y muestra los últimos 100 por API. No es un registro inalterable ni un sistema de auditoría forense.

Para generar un resumen sin servidor:

```powershell
.\.venv\Scripts\python.exe seguimiento/control.py --once
```

Esto actualiza el inventario y escribe `tmp/control_avance/resumen.json`; no ejecuta pruebas nuevas ni consulta GitHub. Conserva claramente las fechas de las evidencias anteriores.
