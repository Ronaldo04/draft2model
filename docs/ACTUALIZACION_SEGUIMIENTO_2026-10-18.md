# Actualización de seguimiento del 18 de octubre de 2026

Alcance: catálogo y evidencia del desarrollo local; no aceptación global del producto o del caso. Archivos modificados: `seguimiento/hitos.json`, `seguimiento/evidencias.json`, `docs/CONTROL_AVANCE.md` y este registro. No se modificaron controlador, HTML, tests del producto ni cachés generadas.

## Integración de cambios existentes

Al retomar se encontró el catálogo 1.15.0 con 85 criterios y 18 nuevos módulos O4.12–O4.29 añadidos por otra conversación de Claude. Se preservaron los 85 IDs y los 18 criterios: no se recrearon ni duplicaron para aumentar avance. La versión resultante es 1.15.1. Las dependencias entre O0–O6 y los criterios generales de piloto/ingeniería se conservan.

Se precisaron títulos/alcance y ampliaron `check_files` con dependencias locales inspeccionadas por importaciones estáticas, rutas HTTP, montaje de clientes, pruebas auxiliares y fixtures cuando son consumidas. Esto impide conservar una prueba como vigente si cambia un núcleo o el controlador de la ruta probada. Se mantienen las dependencias previas; no se eliminaron fallos ni módulos de pruebas para convertirlos en éxito.

| Criterios preservados | Cobertura y separación de aceptación |
| --- | --- |
| O4.12–O4.15 | Ingreso, lectura ETABS, paquetes y fotografía derivada. Lectura de tablas ETABS no se etiqueta como propuesta visual de lecturas. Matrices/píxeles no acreditan escala métrica ni precisión sobre planos reales. |
| O4.16–O4.17 | Proveedor y respuestas con vínculo/traslado/recuperación. Cliente, paquetes y revisiones pasan a ser dependencias pertinentes; transporte de prueba no se convierte en llamada real. |
| O4.18 | Servicio tabular: 6 pruebas focales correctas en 125. La futura HTTP/UI de Claude está en desarrollo y no se acepta como entregada por ese resultado. |
| O4.19–O4.20 | Correspondencias normalizadas y conversión geométrica revisable; geometría y extracción versionadas forman parte de las dependencias. |
| O4.21–O4.22 | Corpus/reglas/sitio, explicaciones y referencias exactas de informe. Se incluyen sus validadores/núcleos y el consumidor del informe. Las pruebas sin clave acreditan contingencia, no LLM real ni semántica profesional. |
| O4.23–O4.27 | Paneles, análisis/construcción, revisión del modelo y consulta de resultados. Sus dependencias y fixtures siguen distintas de una revisión de ingeniería. |
| O4.28 | Root128 comprobó 9 tests backend sin omisiones en host autorizado; se asocian ese servicio y sus pruebas. HTTP/UI sigue en desarrollo, sin aceptación por ese resultado ni revisión declarada de éxito del código actual. |
| O4.29 | Entregables con referencias exactas y aprobación documental propia. Se preservan sus pruebas; se añaden dependencias de contexto/explicaciones y cliente de opt-in. Aprobar un informe no aprueba resultados o modelo. |

No se añadió otro criterio con el mismo entregable ya cubierto por esos 18 módulos. Los criterios generales O3.5/O3.7/O4.2/O5.5/O6.1/O6.2 conservan su alcance; sus notas de pendiente distinguen infraestructura, prueba parcial, caso real y presentación. No se completó un hito general por existir una fixture.

## Evidencia conservada sin fabricar vigencia

`evidencias.json` conserva las tres revisiones históricas y añade una revisión **documental** de O0.2 (plan/contexto) sobre sus huellas Git actuales. No es revisión de software ni aprobación de ingeniería.

Se añadieron 22 `observations`, cada una con fecha, fuente, SHA256 y criterios relacionados. Se comprobaron los archivos conservados, sin atribuirles huellas de código que los logs no registran. Todas declaran `accepts_current_code:false` y `accepts_pilot:false`. El controlador actual solo consume `reviews`; **observations no verifica criterios ni incrementa porcentajes**. La cifra 15/18 de otra comprobación parcial es histórica y no se importa como aceptación del catálogo actualizado.

| Fuentes | Alcance observado |
| --- | --- |
| Logs113–118 | Backend de explicaciones, contexto HTTP, aprobación documental HTTP, fotos derivadas y rechazo de respuestas malformadas.114 incluye pruebas importadas accidentalmente; no sumarlo como ejecución independiente de115. |
| Logs119–121 | Node contexto 10/10, explicaciones 16/16, HTTP preprocesado 2 correctas e informe-contexto 10 correctas. Pruebas sintéticas; sin proveedor/ETABS reales. |
| Ensayo/captura122 | Navegador real creó informe con referencias exactas y contingencia sin LLM. `docs/ENSAYO_INTERFAZ_CONTEXTO.md` y `tmp/interfaz_informe_122.png`. La presentación inicial tenía encabezados huérfanos; no se borra esa observación. |
| Log123 | Node preprocesamiento 11/11; DOM/HTTP simulados, separado del navegador122. |
| `tmp/referencia_preparada_124.json` | Provisional-001: 3 PDF/3 páginas sin errores, originales iguales según registro y paquete preparado. Legibilidad humana pendiente; sin red, extracción de cotas, geometría o ETABS. |
| `tmp/tabular_codex_125.log` | 6 pruebas backend correctas; no aceptación de una UI aún en desarrollo. |
| Log Node informe-contexto126 | 15/15 correctas del cliente de selección explícita de referencias. |
| Sondas/puente126 | Mismo script PowerShell bloqueado en sandbox y permitido en host autorizado; allí 31 tests de puente/despacho con dobles pasaron sin omisiones. Esto no es una nueva copia global ni un análisis ETABS real. |
| `tmp/informe_contexto_http_codex_127.log` | 3 pruebas HTTP correctas de informe-contexto; sin proveedor/ETABS real. |
| `tmp/revision_resultados_codex_128.log` | 9 pruebas backend correctas en host autorizado, sin omisiones. La nueva UI sigue en desarrollo. |
| `tmp/paginacion_codex_127.log` | 4 pruebas focales correctas de reparación. Root informó inspección visual posterior de páginas 2/3; esa evidencia es posterior al PDF122 inicial y no lo convierte retroactivamente en aceptado. |

Los logs quedan en `tmp`, fuera del contenido publicable habitual. Las observaciones conservan sus hashes/referencias, no secretos ni una copia del contenido de expedientes. Si un archivo fuente cambia después, su hash histórico no describe los nuevos bytes.

## Comprobaciones de esta actualización

- Lectura de JSON estricta, sin claves repetidas; 85 IDs únicos, 7 hitos y dependencias existentes sin autorreferencia.
- Archivos/pruebas/check_files existentes y rutas relativas sin escapes; preservación de los IDs previos.
- SHA256 de las 22 fuentes históricas comprobado.
- Evaluación pura del catálogo mediante `seguimiento.control.evaluate`, sin caché de pruebas ni servidor: ningún módulo nuevo queda verificado por `observations`.
- Una prueba focal del catálogo: `tests.test_control_avance.ControlAvanceTests.test_catalog_has_unique_criteria_and_existing_test_dependencies`, correcta en 0.325 s. La prueba precede el ajuste final del backend128, comprobado después con lectura JSON/rutas/dependencias, sin repetir suite. No suite completa, red, Computer Use, proveedor ni ETABS.

Para repetir solo la comprobación focal:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_control_avance.ControlAvanceTests.test_catalog_has_unique_criteria_and_existing_test_dependencies -v
```

No se escribió `tests.json`, inventario, resumen o estado.js para insertar éxitos. Las dependencias ampliadas invalidan comprobaciones obsoletas; el porcentaje debe salir de la evidencia vigente del observador, no de este documento.

## Pendientes y cierre

La copia100 sigue fallida; la última copia068 plenamente verde es anterior a los módulos actuales. El contraste de host126 y las correcciones focales no sustituyen una nueva comprobación integrada del hito estable. Falta completar/revisar tabular HTTP/UI, la interfaz de revisión propia de resultados y las entregas activas, además de su recorrido pertinente; no inferir aceptación por actividad de Claude o existencia de archivos.

La muestra de referencia puede procesarse aunque pertenezca a otro sistema. Su preparación124 no es extracción medida ni valida el alcance original. Clave/modelo y ensayo visual reales, decisiones de ingeniería, referencia manual/tolerancias, comparación y tiempos/costos siguen en la fase final acordada. Los criterios de navegador, ingeniería y piloto permanecen separados del código/pruebas focales. Objetivo global no completado.
