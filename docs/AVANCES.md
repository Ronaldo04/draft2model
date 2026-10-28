# Registro de avances

## 17 de octubre de 2026: infraestructura integrada y continuidad

- Integradas versiones geométricas/CLI/interfaz, planes versionados, conversión explícita, contingencia CSV y preprocesamiento reversible. Tres fallos de integridad de geometría corregidos con regresiones.
- Contrato estructural, resultados/evaluación/comparación, fuentes/citas, sitio referencial, SQLite/exclusión, panel técnico e informe JSON/HTML/PDF presentes. Demo integrada ejecutada por Codex y recomprobada: seis corridas completadas, datos/aprobaciones/resultados fabricados, cero IA y cero ETABS. Informe permanece borrador.
- PDF integrado de tres páginas rasterizado e inspeccionado visualmente: márgenes, tablas, encabezados y pies legibles, sin cortes observados. Evidencia tmp/qa_informe_integrado_001/contacto.png. Recorrido de revisión real en navegador documentado en VALIDACION_INTEGRADA.md.
- Puente ETABS de Claude en revisión: preparación, copia/diagnóstico/tablas/guardado; no construye modelos ni ejecuta análisis. Codex retiró ExecutionPolicy Bypass y corrigió dependencia Get-FileHash mediante SHA256 .NET. Pruebas del puente real se omiten con causa cuando la política del entorno bloquea .ps1; no se elude.
- Catálogo 1.8.0: 14 criterios nuevos de infraestructura separados de los requisitos reales pendientes. Guía unificada GUIA_REPRODUCIBLE.md y punto de reanudación RETOMAR.md. Subagentes interrumpidos por límite de uso; archivos preservados y revisados desde la sesión principal.
- Aclaración del usuario: usar planos de referencia actuales; configuración de API y benchmark manual al final. Reducir Computer Use y consultas extensas; continuar por hitos con registros en disco.
- Pendiente prioritario: generación/aplicación real de configuración estructural en ETABS, análisis deliberado, tablas normalizadas, aprobaciones de modelo e integración del flujo del caso. No se declara terminado el goal.

## 15 de octubre de 2026: controlador de hitos y avance

- Tablero local con 38 criterios O0–O6 derivados del plan, vistas local/publicado, diferencias de archivos y actividad reciente.
- Observación cada 2 segundos; pruebas tras cambios pertinentes con huellas vigentes; consulta GitHub cada 60 segundos cuando exista autenticación independiente. No se publican ni descargan cambios de código automáticamente.
- Lectura inicial del remoto obtenida mediante el conector GitHub, fijada al commit 7ad7d1bc10977cbbbd1fe0961dd63e3959a325d8. Sin credenciales locales, se muestra como lectura guardada con fecha, no como conexión continua.
- Comprobadas regresiones, separación local/remoto, exclusión de privados, pruebas sobre contenido exacto y controles del servidor mediante pruebas sin navegador. Ver conteo y fecha vigentes en el tablero.
- Revisión visual no completada: el navegador integrado rechazó acceso al servidor local por su política. Se conserva la herramienta ejecutable para abrirla directamente en la computadora.
- Nuevos requisitos y criterios de ingeniería necesitan asociación y evidencia explícitas; el controlador no deduce aprobación técnica a partir de cambios arbitrarios.
- Instrucciones: [CONTROL_AVANCE.md](CONTROL_AVANCE.md). Inicio: Abrir control de avance.cmd.

## 14 de octubre de 2026: arquitectura de extracción aclarada

- Visión multimodal definida como intérprete principal de planos y relaciones espaciales. OCR queda como apoyo opcional, no como eje de la extracción.
- Documentación ajustada; registro de candidatos y correcciones debe ser independiente del método de obtención y permitir evidencia visual.
- Vistas generales y recortes disponibles; llamadas a modelos, detección automática y medición de extracción todavía no implementadas. No se enviaron planos a proveedores externos en esta actualización.


## 13 de octubre de 2026: recortes PDF trazables

- Comando recortar implementado: región normalizada de página visible, selección de archivo/página, render ampliado, hashes y matrices de transformación a página visible y espacio PyMuPDF sin rotación. No se infiere escala geométrica.
- Se generaron siete regiones manuales del caso provisional para preparar lectura y extracción. Los PNG y metadatos permanecen privados; la selección no se presenta como detección automática.
- Cinco pruebas nuevas pasan, incluidas comparación visual con cuatro rotaciones, transformación desplazada, entradas inválidas, hash alterado y reducción de resolución para limitar memoria. Suite completa: 40 pruebas pasan.
- Vistas de las siete regiones inspeccionadas; la revisión de datos y escala permanece pendiente. Estado de recortes pendiente_revision y alcance provisional conservado.
- Contrato de evidencia en [RECORTES.md](RECORTES.md). OCR y registro de candidatos/correcciones todavía no implementados.


## 13 de octubre de 2026: contrato geométrico publicado

- Contrato geométrico v0.1, validador, ejemplo sintético, documentación y 22 pruebas geométricas incorporados al estado del proyecto.
- Verificaciones: unidades explícitas y normalización a metros, referencias e identificadores, valores finitos, faltantes, longitudes/alturas positivas y aprobación registrada vinculada a la huella del contenido.
- Suite completa: 35 pruebas unittest pasan. El ejemplo sintético es consistente y permanece no disponible para modelado por faltantes y estado borrador.
- Alcance: consistencia interna de una propuesta de geometría; no verifica competencia del declarante de aprobación ni certifica seguridad estructural. Materiales, cargas y traducción ETABS pendientes.
- Publicación limitada a código, ejemplo sintético y Markdown. Planos de muestra y expedientes privados no se publican.
- Recortes ampliados y extracción con evidencia siguen previstos, no implementados.


## 13 de octubre de 2026: revisión documental y muestra provisional

- Muestra autorizada por el usuario para pruebas locales de procesamiento, declarada fuera del sistema constructivo y cantidad de pisos del MVP. No amplía el alcance ni constituye validación estructural.
- Tres PDF registrados como provisional-001; tres páginas abiertas y renderizadas sin errores. Originales y copias preservados y contrastados mediante SHA256.
- Inventario de dimensiones, rotación, texto embebido y vistas previas. Una página declara rotación PDF de 270 grados; el render respeta su orientación. Las cotas pequeñas requieren ampliación por recortes.
- Módulo revision_documental.py, comando revisar y dependencias reproducibles implementados. Trece pruebas de ingreso y revisión pasan.
- Planos, expediente y PNG permanecen locales en carpetas excluidas; solo código y documentación sin datos del proyecto se publican.
- OCR, extracción geométrica, modelo de referencia y análisis ETABS siguen pendientes. Una apertura correcta no aprueba legibilidad ni datos de ingeniería.
- Instrucciones en [REVISION_DOCUMENTAL.md](REVISION_DOCUMENTAL.md).


## 13 de octubre de 2026: base de ingreso implementada

- El usuario informó que aún no dispone de los planos piloto y solicitó continuar con los componentes independientes.
- Módulo draft2model.ingreso y CLI local disponibles para PDF/JPG/PNG autorizados. Originales preservados, SHA256 contrastados, archivos duplicados e identificadores inválidos rechazados; sin sobrescribir expedientes.
- Expedientes en data/private, excluidos del seguimiento; no se envía contenido a proveedores ni al repositorio por el comando de ingreso.
- Siete pruebas unittest ejecutadas correctamente con archivos sintéticos. Ayuda del comando comprobada.
- Alcance comprobado: registro, copia, trazabilidad y estado borrador. La firma de archivo no valida integridad completa o legibilidad; datos de ingeniería y aprobación permanecen ausentes.
- Contrato de ingreso v0.1.0; contratos de geometría, modelado, resultados, evaluación e informe pendientes. No se ejecutó ETABS ni cálculo estructural.
- Instrucciones en [INGRESO_EXPEDIENTES.md](INGRESO_EXPEDIENTES.md). O1/O2 permanecen abiertos hasta completar sus criterios técnicos.


## 13 de octubre de 2026: inicio de O1

- Entorno Python 3.10.5 de 64 bits aislado en .venv, excluido del versionado.
- ETABS 21.1.0.3261, ejecutable, biblioteca API y ayuda local detectados. Clases COM CSI.ETABS.API.ETABSObject y ETABSv1.Helper registradas.
- Script reproducible [diagnosticar_entorno.py](../scripts/diagnosticar_entorno.py) ejecutado correctamente; informe local en tmp/diagnostico_entorno.json, excluido del remoto. No se leyeron archivos de licencia ni secretos.
- [Preparación O1](O1_PREPARACION.md) documenta datos del piloto, referencia de ingeniería y secuencia de verificación.
- No se encontraron modelos ni dibujos piloto en la carpeta del proyecto. Licencia, conexión API y lectura de resultados todavía no verificadas; O1 sigue abierto.
- El usuario informó haber concedido acceso a un colaborador. No se ha auditado el permiso concreto ni la aceptación; esta información no se presenta como comprobación de solo lectura.

## 13 de octubre de 2026: repositorio y carga verificados

- URL: [Ronaldo04/draft2model](https://github.com/Ronaldo04/draft2model). Propietario: cuenta personal Ronaldo04.
- Visibilidad privada, rama predeterminada main e Issues habilitado comprobados por el plugin GitHub.
- 23 archivos publicados: README, seis documentos de docs, dos plantillas de .github, .gitignore, dos PDF fuente y once entregables. Carpetas preservadas; tmp y credenciales fuera del árbol remoto.
- Contenido remoto comparado con las copias locales mediante los hashes de los blobs Git: 23 coincidencias, sin diferencias. Los PDF y PNG originales se conservaron.
- Seguimiento creado: [O0 #1](https://github.com/Ronaldo04/draft2model/issues/1), [O1 #2](https://github.com/Ronaldo04/draft2model/issues/2), [O2 #3](https://github.com/Ronaldo04/draft2model/issues/3), [O3 #4](https://github.com/Ronaldo04/draft2model/issues/4), [O4 #5](https://github.com/Ronaldo04/draft2model/issues/5), [O5 #6](https://github.com/Ronaldo04/draft2model/issues/6), [O6 #7](https://github.com/Ronaldo04/draft2model/issues/7). Cada Issue contiene objetivos, dependencias y criterios; todavía no acredita implementación técnica.
- Pages desactivado y sin workflows cargados. No se contrataron planes ni se enviaron invitaciones.
- main sin protección. La API de reglas devuelve que se requiere GitHub Pro para el repositorio privado; la lectura detallada de protección no está permitida por la integración. Los controles de integración documentados son convenciones.
- Los hitos O0–O6 se representan con Issues. No se crearon registros Milestone ni tablero Project: el conector disponible no expone esas operaciones.
- Copia local vigente: esta carpeta de proyecto; todavía sin .git. El paquete de carga en tmp es solo una copia de preparación.
- Pendientes: modalidad de consulta, cuentas y verificación de acceso; sincronización mediante Git local cuando se prepare el entorno. O0 permanece abierto.


## 13 de octubre de 2026: preparación documental

### Preparado

- Contexto, plan, guía y plantillas preparados para registrar requisitos, dependencias y verificaciones.
- Criterios de integración sustentados en comprobaciones y evidencia técnica.
- Conservados requisitos, dependencias técnicas, controles y criterios de aceptación del producto.
- Separada la referencia académica histórica; las contribuciones reales quedan por documentar con evidencia.
- Consulta del código por el equipo diferenciada de acceso de escritura en GitHub.

### No ejecutado

- Inicialización Git local y acceso de consulta mediante cuentas autorizadas.
- Implementación o pruebas del prototipo, confirmación de instalación/licencia ETABS o disponibilidad del caso.

### Próximo paso

Continuar con O1 y resolver la modalidad de consulta y las cuentas autorizadas con la [guía](GUIA_GITHUB_PRIVADO.md).

### Antecedente de esta actualización

Los PDF y entregables iniciales se conservan como antecedentes. La planificación y las comprobaciones vigentes se registran en los documentos de trabajo.

## Plantilla de sesión

- Fecha:
- Requisito / Issue / hito:
- Cambio realizado:
- Evidencia / PR / archivos:
- Comprobaciones y resultado:
- Observaciones discutidas en reunión, si existen:
- Decisiones registradas:
- Bloqueo técnico o dato necesario:
- Próximo requisito:

Distinguir realizado, probado, propuesto y pendiente. La reunión o una respuesta de IA no acredita por sí sola una prueba técnica. La evidencia debe permitir verificar la procedencia y el resultado del cambio.


## 14 de octubre de 2026: registro de extracción y preparación de evaluación visual

- Registro de candidatos, validación de evidencias, correcciones con historial y exportación de revisados implementados en extraccion_preliminar.py. Ejemplo sintético y contrato documentados.
- Verificación independiente: 56 pruebas pasan, incluidas 16 de extracción. Compatibilidad comprobada en memoria con tres documentos y siete recortes del piloto, sin extraer valores ni escribir nuevos datos privados. Se conserva fuera_mvp_declarado.
- Las 45 000 mutaciones aleatorias fueron reportadas por Claude Code; no forman parte de esta verificación independiente.
- [Protocolo de evaluación visual](EVALUACION_VISION.md) y plantilla vacía de referencia preparados. Referencia manual, ejecución de visión y mediciones todavía pendientes.
- Siguiente implementación delimitada: comandos y persistencia de importación, validación, corrección y exportación; comprobación de archivos de evidencia vigentes antes de guardar resultados.
- La visión multimodal sigue como extractor principal. OCR auxiliar, proveedor externo, geometría derivada y ETABS todavía no implementados.


## 15 de octubre de 2026: evaluador de lecturas y siguiente integracion

- Evaluador de propuestas originales implementado como modulo independiente, con referencia y correspondencias revisadas declaradas, huellas y comparaciones sin inferir unidades ni emparejar por valores.
- Metricas reproducibles de cobertura, exactitud, lecturas completas, abstenciones y evidencia; duplicados, propuestas sin respaldo y candidatos sin clasificar separados. Resultados por tipo y lamina.
- Ejemplos exclusivamente sinteticos: la puntuacion del software no representa precision real de un modelo. El caso provisional fuera del MVP conserva su marca; referencia humana y corrida visual real siguen pendientes.
- 18 pruebas nuevas del evaluador verifican denominadores, omisiones, vigencia de correspondencias, separacion de correcciones, unidades, evidencia y CLI sin sobrescritura. Resultado vigente de suite completa en el controlador.
- Catalogo de seguimiento 1.1.0: 39 criterios. O3.8 distingue el evaluador implementado de O3.6, que sigue pendiente hasta medir corridas reales.
- Integracion local de comandos, versiones y comprobacion de evidencias delimitada para Claude Code, sin editar los archivos del evaluador ni seguimiento. La entrega aun no esta presente en esta carpeta.
- Instrucciones de evaluacion: [EVALUADOR_VISION.md](EVALUADOR_VISION.md).


## 15 de octubre de 2026: entrada y salida multimodal local

- Preparacion de paquetes con contexto general y recortes comprobados contra PDF y metadatos. Prompt independiente del proveedor y respuesta JSON estricta. No hay llamadas API.
- Adaptacion de regiones de imagen a pagina visible usando la transformacion real del raster; valores desconocidos y alcance preservados, lecturas pendientes de revision. Respuestas de prueba marcadas sinteticas.
- Piloto: paquete local con tres vistas de contexto y siete recortes, sin lecturas propuestas ni transmision externa. Copias dentro de data/private, excluidas del remoto.
- Pruebas sinteticas incluyen rotaciones 0/90/180/270, redondeo, modificaciones de fuentes, metadatos, copias o prompt, JSON invalido, respuesta vacia y CLI.
- Catalogo 1.2.0, 40 criterios: O3.9 registra la entrada/salida; O3.5 (ejecucion real de vision) y O3.6 (precision medida) siguen pendientes.
- No se modificaron los archivos asignados a Claude para comandos y versiones de extracciones.
- Uso y limites: [ENTRADA_VISION.md](ENTRADA_VISION.md). Resultado vigente de suite completa en el registro del controlador.


## 15 de octubre de 2026: primer cliente OpenAI y enlace con versiones

- El usuario eligio preparar OpenAI y declaro no disponer aun de clave API. Modelo configurable, sin proveedor llamado ni costo real generado por estas pruebas.
- Cliente Responses API preparado: PNG inline, esquema estricto, plan local verificable, envio explicito, un intento por plan, sin reintentos automaticos y sin claves en planes.
- Registro de respuesta, duracion de API y total, consumo informado o null. Respuestas incompletas/rechazadas/invalidas no se importan.
- Recorrido completo hasta importar, corregir y exportar comprobado con PDF sintetico y HTTP sustituido. Los transportes simulados se identifican y no se importan como lecturas reales.
- Integracion local de Claude presente: comandos, gestion, documentacion y pruebas. O4.1 exige ahora tanto pruebas de gestion como de CLI y sus dependencias.
- Catalogo 1.3.0, 41 criterios. O3.10 acredita el cliente probado sin red; O3.5 y O3.6 siguen pendientes de corrida real y precision medida.
- Uso: [CONEXION_OPENAI.md](CONEXION_OPENAI.md). Resultado vigente de suite completa en el controlador.

## 15 de octubre de 2026: revisión visual local

- Interfaz para consultar expedientes, elegir lámina/página, ampliar el plano y seleccionar regiones de evidencia. Si no hay extracción, muestra documentos sin inventar candidatos.
- Importación de JSON, corrección con motivo/fecha/revisor declarado y exportación de revisados usando la gestión existente. Cada corrección crea una versión hija; los anteriores permanecen intactos. No otorga aprobación de ingeniería.
- Renderizado desde originales comprobados: rotaciones PDF y orientación EXIF; lectura bloqueada ante huellas alteradas. Servicio solo en loopback con sesión, comprobaciones de Host/Origin y respuestas sin caché.
- Pruebas sintéticas del recorrido y del manejador HTTP con transporte en memoria; las conexiones de sockets están restringidas en el entorno. La revisión operativa en navegador sigue pendiente.
- Catálogo 1.4.0: O4.2 distingue la interfaz implementada de su validación operativa; O4.5 acredita por separado el servicio probado. Resultado vigente de la suite completa en el controlador.
- Instrucciones: [REVISION_VISUAL.md](REVISION_VISUAL.md). Ejecutar `Abrir revision de planos.cmd`. No se modifican los cuatro archivos del plan geométrico asignados a Claude.

## 15 de octubre de 2026: integración del plan geométrico

- Revisada la entrega de Claude del plan geométrico: 17 pruebas pasaron en la revisión inicial. Se confirmaron limitaciones numéricas del validador y diagnósticos ante tipos inválidos, asignados a Claude en una tarea separada.
- Comando `plan-modelado` añadido a la CLI principal. Recibe el contrato geométrico existente, informa cobertura y bloqueos y guarda una propuesta o un diagnóstico sin ejecutar ETABS. No interpreta una extracción de lecturas como geometría.
- Escritura separada en `archivo_plan.py`: entrada conservada y comprobada durante el cálculo, temporal completo, publicación sin reemplazo y limpieza ante fallos. Una salida creada concurrentemente tampoco se reemplaza.
- Doce pruebas de integración verifican reproducción del ejemplo, errores de lectura/cálculo/escritura, conservación de archivos y cambios concurrentes. El resultado vigente de la suite completa se consulta en el controlador.
- Catálogo 1.5.0: O2.6 registra el plan y su comando; O2.2–O2.5 conservan sus pendientes de ingeniería y ETABS. No se modifican los archivos asignados a Claude para robustecer el validador y adaptar el plan.
- Uso y límites en [CLI_PLAN_MODELADO.md](CLI_PLAN_MODELADO.md).

## 15 de octubre de 2026: comandos visuales integrados

- Añadidos `preparar-vision`, `preparar-openai` y `registrar-respuesta-vision` a la CLI principal. Selección por caso e IDs, sin llamadas externas ni clave requerida.
- Se reutilizan comprobaciones, adaptación de coordenadas y cliente de preparación existentes. Las lecturas permanecen pendientes; la procedencia del proveedor/modelo es declarada, no autenticada.
- Importación a versiones opcional y explícita. Simulaciones separadas y no importables como lecturas reales. Si falla una importación posterior, la adaptación se conserva y la recuperación es exclusivamente local.
- Pruebas nuevas con PDF y respuestas sintéticos, transporte de red bloqueado, modelos explícitos, límites, rutas, evidencia alterada y respuestas ajenas. Resultado vigente de la suite conjunta en el controlador.
- Catálogo 1.6.0: O3.11 registra los comandos probados; ejecución visual real y precisión del piloto siguen pendientes. No se modifican los archivos de persistencia geométrica asignados a Claude.
- Uso: [CLI_VISION.md](CLI_VISION.md).

## 16 de octubre de 2026: HTML enlazado del controlador

- `Control de avance.html` abre directamente el dashboard y relee `tmp/control_avance/estado.js` cada dos segundos. Los datos se generan también como JSON sin clave de sesión.
- Lanzador actualizado al modo observador sin servidor HTTP. El HTML refleja cambios de datos mientras está abierto; el observador calcula inventario, pruebas y consulta remota según autenticación disponible. Sin observador se conserva la lectura anterior y su fecha.
- Se mantiene el modo HTTP para las acciones y conexión manual existentes. No se añaden publicaciones ni credenciales al HTML.
- Resumen operativo y reparto de trabajo en [ESTADO_DESARROLLO.md](ESTADO_DESARROLLO.md), con entregas implementadas, comprobaciones pendientes y dependencias de ingeniería.
- Catálogo 1.7.0, 44 criterios. Las pruebas del controlador verifican exportación actualizable, ausencia de sesión, escape de contenido y conservación de datos completos ante fallos de escritura.
