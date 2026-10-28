# Control de avance local y publicado

Abrir **[Control de avance.html](../Control%20de%20avance.html)** desde la carpeta del proyecto. Carga el dashboard directamente, sin un servidor HTTP, y vuelve a leer sus datos enlazados cada dos segundos. Mantener el HTML en esa carpeta para conservar sus rutas relativas.

Para detectar cambios nuevos en el código y recalcular la evidencia, ejecutar **[Abrir control de avance.cmd](../Abrir%20control%20de%20avance.cmd)**. Inicia el observador de Python y abre el mismo HTML. Mantener su ventana abierta; para detenerlo, usar Ctrl+C o cerrar esa ventana. Abrir solo el HTML muestra la última lectura y sus fechas, pero el navegador no puede arrancar Python automáticamente.

Alternativa desde PowerShell:

```powershell
.\.venv\Scripts\python.exe seguimiento/control.py --watch-only
```

El observador sin servidor no necesita un puerto ni publica un sitio. No modifica GitHub ni requiere dependencias nuevas. La interfaz HTTP anterior continúa disponible ejecutando el comando sin `--watch-only`; sirve para acciones manuales y conexión de una credencial de lectura desde su formulario.

## Archivo base y vínculo

- `seguimiento/hitos.json`: definición de hitos y criterios. Editarlo no acredita por sí solo avances.
- `tmp/control_avance/resumen.json`: resumen JSON calculado por el observador.
- `tmp/control_avance/estado.js`: archivo de datos que carga directamente el HTML, con el mismo resumen y sin la clave de sesión. Se genera automáticamente; no se edita para simular avances.
- `Control de avance.html`: dashboard enlazado a los recursos de `seguimiento/web/`. Recarga el archivo de datos cada dos segundos mediante un script local, evitando las restricciones de lectura JSON con `fetch` en `file://`.

Si `estado.js` cambia, el HTML abierto refleja la nueva información sin recargar la página. Si el observador está detenido, mantiene la lectura guardada y señala su antigüedad. Un fallo de lectura conserva la vista anterior. El archivo HTML por sí solo no ejecuta pruebas ni consulta el repositorio privado.

El modo archivo es de consulta: no envía credenciales ni ejecuta acciones HTTP. “Actualizar” relee el archivo de datos. Las pruebas y la consulta continua de GitHub corresponden al observador; su autenticación se describe más abajo. La escritura del JS es atómica y no incluye una clave de sesión de escritura.

## Qué significa cada estado

Las cachés generadas ilegibles se conservan como `*.invalid-*` y se recalculan cuando es posible. Una caché de pruebas dañada se descarta como evidencia, sin dar criterios por verificados. El catálogo de hitos y las revisiones documentales siguen exigiendo JSON válido: no se reemplazan silenciosamente.

Comprobación adicional de la lógica de carga local: `node tests/control_html_check.cjs`. Usa un DOM mínimo para verificar recarga, ausencia de peticiones HTTP y conservación de la lectura ante errores; no sustituye la validación operativa en un navegador real.

| Estado | Evidencia |
| --- | --- |
| Pendiente | No hay evidencia suficiente del criterio. |
| En desarrollo | Solo está presente parte de la entrega definida. |
| Implementado | Están los archivos esperados; falta comprobación vigente. |
| Verificado | Pruebas pertinentes pasan sobre los archivos exactos, existe revisión declarada con huellas vigentes o se comprobó un metadato remoto. |
| Bloqueado | Hay una condición externa identificada que falta resolver. |

El porcentaje es **criterios verificados / criterios definidos**, con el mismo peso por criterio. No mide esfuerzo ni predice fecha de finalización. El catálogo 1.15.1 define 85 criterios (incluye los 18 de módulos de revisión web de O4.12–O4.29 y los 20 de infraestructura y pruebas sintéticas incorporados en 1.11.0). No acredita los criterios generales de ejecución/precisión/ingeniería reales por sus fixtures. No sustituye la aceptación global de cada hito. El panel técnico local desde resultados declarados está separado de este control de desarrollo y aún debe vincularse al flujo ETABS real.

## Actualización

- Al abrir: inventario actual, comprobación de pruebas y consulta de GitHub si existe autenticación disponible.
- Cada 2 segundos: detectar archivos nuevos, modificados o eliminados mediante metadatos y huellas de contenido. Se conserva historial local entre sesiones; no se ejecuta mientras el proceso esté detenido. Una edición y reversión completa entre dos lecturas puede no observarse.
- Código o pruebas modificados: esperar 3 segundos de quietud y ejecutar unittest en un proceso separado, con límite de 1800 segundos (la suite ya dura unos 565 s). Las pruebas verificadas se vinculan a las huellas de sus archivos y dependencias declaradas. Si cambian durante la ejecución, no se acredita esa ejecución y se programa otra.
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

Esto actualiza el inventario y escribe `tmp/control_avance/resumen.json` y `estado.js`; no ejecuta pruebas nuevas ni consulta GitHub. El HTML abierto recibe esa lectura. Conserva las fechas de las evidencias anteriores.

El observador admite hasta 600 s para la suite ampliada y usa temporales cortos en `tmp/control_t`, dentro del mismo volumen. Un timeout sigue siendo fallo y no acredita criterios. La copia limpia068 completó590 pruebas en174.613s; el antiguo límite120s ya era insuficiente. Este cambio no transforma una lectura histórica fallida en una suite correcta: el tablero debe ejecutar y registrar una comprobación nueva sobre los archivos vigentes.26 pruebas del controlador pasaron con TEMP/TMP del workspace (`tmp/revision_control_timeout_078.log`).


## Actualización de criterios y observaciones del 18 de octubre

El catálogo 1.15.1 conserva los 85 criterios y los 18 módulos O4.12–O4.29 incorporados por la actualización anterior: no duplica esos hitos para aumentar avance. Se completaron dependencias de núcleos, rutas HTTP, montaje de clientes, pruebas auxiliares y fixtures cuando corresponden. Cambiar una de esas fuentes debe invalidar la comprobación afectada. El criterio tabular actual cubre backend; su interfaz sigue en desarrollo. Root128 comprobó 9 pruebas del backend de revisión propia de resultados sin omisiones; su HTTP/UI permanece en desarrollo. Se asocia ese módulo de pruebas, sin declarar vigente una caché histórica. La aprobación documental de informes permanece independiente de revisión de resultados, modelo o ingeniería.

`seguimiento/evidencias.json` conserva `reviews`, que el controlador sí evalúa, y añade `observations` como registro de fuentes históricas comprobadas por SHA256. El controlador actual **no usa observations para verificar criterios ni calcular porcentajes**. Cada observación declara su alcance y `accepts_current_code:false`: un log focal conservado no demuestra que esos tests se ejecutaran sobre los bytes que existen hoy. Las pruebas Node se registran aparte; listar sus archivos como dependencias tampoco equivale a ejecutarlas. No se modificó la caché generada `tests.json` para importar éxitos históricos.

La única revisión declarada nueva es documental para O0.2, con huellas Git actuales de plan/contexto; no acredita código ni piloto. Para los nuevos módulos no se registraron revisiones declaradas de éxito que sustituyan pruebas, navegador o ingeniería. La cifra parcial 15/18 comunicada para una revisión anterior de módulos no se reutiliza como aceptación de este catálogo: fuentes, dependencias y producto han seguido cambiando. El porcentaje que derive el observador puede bajar al detectar pruebas obsoletas; no mide esfuerzo.

El ensayo de navegador122 creó un informe con referencias y contingencia sin LLM; no acreditó extracción/cálculo del caso. La preparación124 conservó tres PDF/tres páginas sin error y hashes originales iguales, sin red ni extracción métrica. Se conservan sus registros sin completar criterios generales por esa evidencia parcial. La reparación de paginación127 tiene comprobación focal y revisión visual posterior separada; no transforma retroactivamente el PDF122 inicial en una presentación aceptada.

La copia100 sigue siendo una ejecución global fallida. El contraste126 mostró que la sonda PowerShell bloqueada en sandbox funciona en host autorizado; allí 31 pruebas del puente/despacho con dobles pasaron sin omisiones. Eso aporta diagnóstico y regresión focal, no una nueva copia global aceptada ni cálculo ETABS real. La última copia068 plenamente verde precede módulos actuales. Detalle y fuentes: [actualización de seguimiento](ACTUALIZACION_SEGUIMIENTO_2026-10-18.md).
