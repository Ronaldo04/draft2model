# Entrega reproducible para AECODE

El proyecto es el sistema Draft2Model completo. Una copia de fuentes no acredita por sí sola su aceptación: el informe de validación debe identificar exactamente la huella de fuentes entregada y distinguir el caso real, ensayos sintéticos y funciones pendientes. El modelo manual del usuario permanece reservado para el contraste posterior.

Corte325, 24 de octubre de2026: conserva la [estimación opcional del peso efectivo de vigas](ESTIMACION_EXTREMOS_AUTO.md) de322 y reutiliza particiones puras dentro de cada preparación. La fuente se compara completamente en cada acceso; el caché está limitado a16MiB y8192entradas, conserva el orden JSON y devuelve copias independientes. No almacena evidencias externas ni modifica el análisis. VALIDACION.json junto al ZIP identifica las comprobaciones de esta huella; no atribuir ensayos nativos anteriores a una nueva ejecución. El benchmark humano y la aceptación global permanecen abiertos.

## Preparar un paquete

Desde la carpeta del proyecto, con Python 3.10 x64 en Windows:

```powershell
.\.venv\Scripts\python.exe scripts/crear_paquete_aecode.py --comprobar --wheels tmp/wheels_clean_001
.\.venv\Scripts\python.exe scripts/crear_paquete_aecode.py --salida entregas/AECODE_VERSION_NUEVA --wheels tmp/wheels_clean_001
```

El destino debe ser nuevo. El script no descarga nada ni llama a proveedores o ETABS. Incluye fuentes, documentación, ejemplos, pruebas, recursos del control de avance y, si se solicita, los wheels que coinciden íntegramente con el lock. Excluye credenciales, expedientes privados, entornos y temporales. Detecta cambios concurrentes y registra un error en lugar de publicar un manifiesto de éxito. El manifiesto permite comprobar cada archivo y el ZIP; no equivale a una revisión de ingeniería ni a un ensayo funcional.

## Instalar en otra carpeta

Descomprimir `Draft2Model.zip` en una carpeta nueva y abrir allí PowerShell. Instalar previamente Python 3.10 x64 y, para el flujo real, ETABS con licencia y API local compatibles. No hace falta una clave de ETABS.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --no-index --find-links wheels --require-hashes -r requirements-win-py310.lock
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m draft2model --help
.\.venv\Scripts\python.exe -m draft2model.revision_visual --raiz data/private --puerto 8766
```

La instalación offline requiere que el manifiesto incluya `wheels/`; Python y ETABS se instalan por separado. Para proveedores reales configurar localmente OpenAI o Google según [accesos](ACCESOS_Y_PROVEEDORES.md), sin incluir claves en la entrega. Las llamadas son exclusivamente para lectura y extracción de planos y requieren presupuesto y confirmación específicos. Arrancar la aplicación no envía planos.

## Evidencia necesaria para presentar el sistema como terminado

- Instalación y arranque observados desde esta distribución, con su huella, códigos y logs.
- Entrada de planos, revisión y configuración trazables; hipótesis y limitaciones explícitas.
- Modelo real ETABS, análisis, relectura y controles coherentes con los mismos archivos y versiones.
- Panel e informes JSON/HTML/PDF inspeccionados: estado, geometría/muros, periodos, derivas, cortante basal, advertencias/inconsistencias y sitio referencial.
- Resultados y expediente autorizado en un complemento separado, revisado sin claves; métricas de extracción distinguiendo correcciones de referencia humana.

La [guía del operador](GUIA_REPRODUCIBLE.md) describe las etapas. La demo integrada permite comprobar infraestructura sin red y usa datos sintéticos: no sustituye esos criterios ni prueba soporte para cualquier tipología de construcción. Los requisitos abiertos se conservan en [RETOMAR](RETOMAR.md).


## Fuentes, expediente y resultados son entregables separados

`Draft2Model.zip` contiene software y dependencias seleccionadas. Excluye expedientes y credenciales. El complemento autorizado del caso debe contener `Caso.zip`, originales, EDB analizado, JSON/HTML/PDF, panel, evidencias de enlace y corpus público revisado. No adjuntar toda la carpeta `data/private` ni otros proyectos.

El exportador interno `seguimiento/exportar_complemento_291.py` verifica hashes del registro de resultados y rechaza fuentes fuera de la corrida seleccionada, cambios concurrentes y patrones de credenciales. Crea `Complemento.zip` y `MANIFIESTO_COMPLEMENTO.json` en un destino nuevo. El candidato291 procede de09d2, anterior a las correcciones de presentación; no es entrega final. La exportación definitiva debe usar la continuación corregida y revisada.

Los manifiestos acreditan integridad de transporte. Conservan rutas y recibos históricos; no demuestran que pueda repetirse una captura nativa en otro equipo. Para operar allí se necesita instalar ETABS/licencia y registrar una nueva ejecución mediante los flujos del producto, con sus propias rutas y evidencias. Los scripts de seguimiento empleados para preparar este caso no están incluidos por defecto en el paquete público.

Antes de presentar: asociar a la misma huella final los resultados de instalación, suite global, arranque y recorrido de interfaz; confirmar que el complemento contiene las versiones corregidas; declarar escenarios de suelo/sistema, ausencia de EMS, discrepancia de masa y comprobaciones no satisfechas. A fecha23de octubre estos pasos finales siguen abiertos. Ningún candidato anterior se presenta como versión aceptada.


## Comprobar los archivos recibidos

Desde una copia de fuentes que incluya `scripts/verificar_entrega_aecode.py`:

```powershell
.\.venv\Scripts\python.exe scripts/verificar_entrega_aecode.py --fuentes RUTA_PAQUETE_FUENTES --complemento RUTA_COMPLEMENTO --huella-esperada HUELLA_DE_LA_DISTRIBUCION
```

El verificador lee los ZIP sin extraerlos ni ejecutar su contenido. Contrasta inventarios, hashes, rutas, el caso anidado y las salidas obligatorias. Un error devuelve código1. El código0 acredita integridad respecto de los manifiestos y de la huella esperada, sin autenticar al autor ni acreditar funcionamiento, conformidad normativa o compatibilidad funcional entre versiones. Para eso hace falta el informe independiente de validación asociado a esa misma distribución y a sus resultados. No ejecutar archivos ajenos para comprobarlos.


## Consultar el caso entregado sin ejecutar proveedores

Después de verificar integridad, descomprimir `Complemento.zip` en una carpeta nueva. Dentro de ella:

- `resultados/informe/`: abrir `informe.html` o `informe.pdf`; `informe.json` conserva valores, reglas, hipótesis y evidencias.
- `resultados/panel.html`: abrir el panel y consultar sus filtros; no ejecuta ETABS ni proveedores.
- `caso_archivado/Caso.zip`: descomprimir en otra carpeta nueva. El modelo analizado está en `CASO/analisis_etabs/ANALISIS/analizado.EDB`, donde CASO y ANALISIS son los identificadores de `MANIFIESTO_COMPLEMENTO.json`.

Abrir ese EDB desde ETABS compatible para inspección. No confundirlo con `entrada.edb` o `trabajo_motor.edb`. Conservar la copia entregada si se quiere comparar sus hashes después. Las operaciones deliberadas de recalcular o guardar en ETABS generan otro estado; no equivalen a la consulta del archivo archivado.

Estos archivos permiten consultar el cálculo que se entregó sin nuevas llamadas a OpenAI o Google. Reproducir el cálculo en otra instalación requiere una nueva corrida, sus rutas locales y su propia evidencia; mover ZIP no adapta las rutas absolutas históricas de los recibos. El verificador conjunto también comprueba que el informe declare el mismo resultado, análisis y modelo que el complemento, y que el EDB archivado tenga el SHA analizado y leído.


Corte de integración303: el complemento corregido `COMPLEMENTO_CORREGIDO_303` conserva las salidas09d3 revisadas en302. Sustituye al candidato291 para estas correcciones. Sigue siendo un archivo de transporte, pendiente de aceptación conjunta con la distribución final. En los renders PDF se observaron diferencias entre motores; se entrega también HTML con el mismo contenido. No se atribuye al visor PDF integrado una revisión que no pudo mostrar.
