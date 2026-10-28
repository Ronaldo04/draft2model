# Diagnóstico para el cierre de Draft2Model

Fecha local: 16 de octubre de 2026, aproximadamente 20:08 (America/Lima). Responsable de este diagnóstico: subagente de diagnóstico de Codex. Coordinación, integración, pruebas generales y trabajo con Claude: Codex principal. Este documento es una fotografía previa a las nuevas entregas de esta sesión; una implementación posterior debe actualizar su evidencia de aceptación, sin interpretar esta fotografía como estado definitivo.

## Base y alcance vigente

Se contrastaron README, CONTEXTO_PROYECTO, PLAN_OPERACION, ESTADO_DESARROLLO, REGISTRO_DECISIONES, O1_PREPARACION, CONTROL_AVANCE, catálogo `seguimiento/hitos.json` v1.7.0, inventario de módulos y pruebas, CLI y documentos fuente PDF (desarrollo técnico de 17 páginas y entrega de avance de 5 páginas). Los PDF conservan requisitos y antecedentes; las decisiones posteriores de Markdown prevalecen en organización y selección de tecnologías. La visión multimodal es la interpretación principal; OCR es opcional. Las asignaciones históricas de personas no constituyen encargos operativos actuales.

El alcance que permite declarar cerrado el proyecto es un caso autorizado de albañilería confinada de uno o dos niveles en Lima Metropolitana, desde fotografía/escaneo hasta modelo y análisis ETABS, siete resultados e informe preliminar revisado. Deben conservarse extracción inicial evaluada, correcciones, aprobaciones de datos/modelo/informe, referencia manual equivalente, tolerancias previas, tiempos/costos y recuperación de fallos. La muestra provisional declarada fuera del MVP no acredita este cierre. Una demostración sintética o una ruta manual tiene valor técnico, pero debe identificarse y no sustituye la validación visual y estructural real.

Los siete resultados exigidos son: estado de generación/análisis; geometría y número de muros; periodos seleccionados; derivas por nivel/dirección; cortante basal por dirección; advertencias/inconsistencias; condición referencial del sitio con fuente. El dashboard de seguimiento del desarrollo no satisface el dashboard técnico del producto.

## Comprobaciones locales ejecutadas

Todas fueron de lectura, sin red ni proveedores, sin inspección de secretos, sin abrir/modificar modelos y sin iniciar ETABS o COM.

| Comprobación reproducible | Resultado observado |
| --- | --- |
| `.\.venv\Scripts\python.exe -B scripts/diagnosticar_entorno.py` | Ejecución correcta, sello UTC `2026-10-17T01:07:33.602879+00:00` (16 de octubre en Lima). Windows, Python 3.10.5 de 64 bits, entorno aislado. |
| Paquetes inventariados | Pillow 12.3.0 y PyMuPDF 1.28.2 presentes; comtypes, pydantic y pytest ausentes. Son alternativas de implementación: su ausencia no demuestra un fallo de los módulos actuales, que utilizan validadores propios y unittest. |
| `.\.venv\Scripts\python.exe -B -m pip check` | `No broken requirements found.` No acredita una instalación limpia ni compatibilidad ETABS. |
| `.\.venv\Scripts\python.exe -B -m draft2model --help` | Arranque correcto. Ingreso, revisión, recortes, versiones de extracción, plan geométrico y preparación/registro visual disponibles. En esta fotografía no aparecen comandos ETABS, evaluación estructural, informe o geometría persistente. |
| Inventario instalación ETABS | Ejecutable, `ETABSv1.dll` y ayuda CHM presentes en `C:/Program Files/Computers and Structures/ETABS 21`. Versión de ejecutable/producto 21.1.0.3261. |
| Registro COM | `CSI.ETABS.API.ETABSObject` y `ETABSv1.Helper` presentes; `CSiAPIv1.Helper` ausente. Esto no valida activación, API ni licencia. |
| `Get-Process ETABS -ErrorAction SilentlyContinue` | No se observó proceso ETABS. No se inició ninguno. |
| Búsqueda del diagnóstico de `.edb/.e2k/.dwg/.dxf` | Ningún candidato en el proyecto, excluyendo `.venv`, `tmp`, `.git`, `node_modules`, cachés. No afirma ausencia en otras carpetas o equipos. |
| Lectura de fuentes PDF | Texto extraído localmente; requisitos P01–P14 comprobados en página 12 del desarrollo técnico. No se hizo revisión de vigencia normativa ni se adoptaron umbrales desde los antecedentes. |

No se ejecutó una suite adicional en este encargo: la ejecución y aceptación de pruebas de código corresponden a Codex principal. La presencia de archivos/pruebas se registra como implementación aparente, sin elevarla a validación real o aceptación estructural.

## Matriz de aceptación y brechas

Estados: **implementado** = archivos funcionales existentes que aún necesitan evidencia vigente; **parcial** = cubre una parte del requisito; **pendiente** = desarrollo o integración faltante; **dependencia externa** = precisa dato o validación que no puede inventarse. Las filas agrupan criterios del catálogo sin cambiar su significado ni acreditar porcentajes.

| Criterios / prueba | Aceptación verificable | Estado inicial y evidencia/brecha |
| --- | --- | --- |
| O0.1–O0.5: base/documentación/acceso | Plan y exclusiones revisados; remoto privado/Issues comprobados y acceso real del colaborador auditado. | Documentación presente; remoto/acceso no consultados en este encargo. No bloquea desarrollo local. |
| O0.6: seguimiento | Datos derivados de archivos exactos, sin acreditar cachés obsoletas o pruebas omitidas; vista local/publicada distinguida. | Implementado en `seguimiento/` con pruebas y HTML. Requiere resultado vigente de Codex. |
| O1.1–O1.2 / P02: ingreso/calidad | Abrir PDF/JPG/PNG válidos; identificar dañados, faltantes/insuficientes; conservar originales y hashes. | Ingreso y vistas implementados. No equivale a verificar legibilidad, correspondencia construida o completitud técnica del piloto. |
| O1.3 / P01: entorno | Instalación reproducible y versiones registradas; adaptador compatible en esta estación. | Inventario verificado arriba; licencia/API/cálculo no ejecutados. |
| O1.4: caso MVP | Caso autorizado 1–2 niveles/albañilería confinada, ubicación, planos y parámetros suficientes. | Dependencia externa: la muestra actual está declarada fuera del MVP. No cambiar tipología para acomodarla sin decisión de alcance. |
| O1.5 / P09: referencia | Modelo manual revisado; materiales, hipótesis, cargas, unidades/casos equivalentes; tolerancias aprobadas antes del ensayo. | Dependencia externa: no existe candidato local encontrado. IA puede preparar ficha/comparador; no autoproclamar revisión de ingeniería. |
| O1.6 / P01: ETABS real | Abrir copia autorizada, leer versión/unidades, analizar un caso y extraer tabla real con retornos registrados. | Pendiente de comprobación, no licencia inválida demostrada. Instalación y COM detectados no bastan. |
| O2.1 / P05: contratos | Rechazar referencias rotas, no finitos, dimensiones imposibles; normalizar deliberadamente m/cm/mm. | Implementado en `contratos.py`/`validacion_geometria.py` con pruebas; contrato geométrico v0.1 provisional. No incluye ingeniería completa. |
| O2.2: entrada estructural | Contrato de materiales, secciones, cargas/masa, apoyos/diafragmas, sitio, idealización y análisis; supuestos explícitos y aprobados. | Pendiente. Código puede validar completitud, pero valores/plantilla deben revisarse técnicamente. |
| O2.3 / P08: adaptador/plantilla | Generar una copia nueva; mapear IDs; verificar todos los retornos API, objetos, conectividad, cargas/masa y aprobación del modelo. | Pendiente; no hay módulo ETABS en el inventario inicial. Pruebas con doble sirven para errores, no para validar cálculo. |
| O2.4 / P09: ejecución/resultados | Corrida identificada con huellas/versiones/casos; análisis completo, controles solver/masa/participación y resultados crudos/normalizados. | Pendiente: contratos de ejecución/resultados y conexión real faltantes. |
| O2.5 / P09: comparación | Periodos, derivas y cortantes comparados a referencia equivalente; diferencias absolutas cerca de cero. | Pendiente y dependiente de referencia/tolerancias aprobadas. |
| O2.6: plan geométrico | Superficies/omisiones trazables, metros, errores numéricos controlados y salida nueva sin sobrescritura. | Implementado con módulos/pruebas y CLI; declara explícitamente que no ejecuta ETABS. |
| O3.1 / P03: preprocesamiento | Rotación/perspectiva/contraste cuando corresponda; escala comprobada; transformaciones reversibles y evidencia original conservada. | Recortes PDF y coordenadas implementados; corrección de fotografía/perspectiva y evaluación de mejora no aparecen implementadas. |
| O3.2: candidatos | Valor, unidad, clase, región/origen, duda y revisión separados; ausentes permanecen ausentes. | Implementado en extracción preliminar y ejemplo sintético; falta comprobar salida del piloto. |
| O3.3–O3.4 / P04: referencia visual | Referencia humana revisada por clase/cota y asociaciones; protocolo de correspondencia/tolerancias previo. | Protocolo/plantillas presentes; referencia del piloto pendiente externa. No convertir propuestas IA en verdad de referencia. |
| O3.5 / P04: extracción real | Llamada multimodal registrada, modelo/instrucciones/errores/reintentos/costo; respuesta original preservada. | Cliente OpenAI preparado sin red; ejecución real pendiente. Requiere configuración de acceso y selección de modelo conforme a decisión vigente. |
| O3.6 / P04: métricas | Precisión/cobertura, cotas, errores dimensionales, tiempos y costo iniciales separados de corrección humana. | Evaluador sintético disponible; medición real pendiente. |
| O3.7: conversión espacial | Correspondencias, origen/ejes/escala explícitos; candidatos revisados -> geometría versionada con evidencia, sin inventar conectividad. | Pendiente en la fotografía; no se deriva geometría por exportar lecturas. |
| O3.8–O3.11 | Evaluador, paquetes, cliente y CLI verificables sin red; adaptación estricta y evidencia vigente. | Implementados con pruebas; no acreditan conexión, precisión ni costo reales. |
| O4.1 / P06: extracción versionada | Importar, corregir, validar y exportar nuevas versiones; comprobar originales/evidencias. | Implementado en gestión/CLI y pruebas. |
| O4.2/O4.5 / P06: interfaz | En navegador cargar plano/lectura, seleccionar evidencia, corregir y ver nueva versión; conservar historial y rutas seguras. | Interfaz/servicio presentes; falta sesión operativa completa y enlace a geometría/parámetros/modelado. |
| O4.3 / P06: aprobación/vigencia | Borrador distinto de aprobación; bloquear críticos ausentes; una modificación invalida entrada/salidas dependientes. | Gestión geométrica entregada localmente, pendiente de revisión/integración. Aún faltan aprobaciones y huellas integradas de ingeniería, modelo, resultados e informe. |
| O4.4 / P07: sitio | Fuente/fecha/CRS/precisión; dentro, límite y fuera cobertura; parámetros aprobados. No inferir perfil normativo o capacidad portante. | Pendiente. Cartografía/ubicación y revisión técnica requeridas para piloto; construir controles puede avanzar. |
| O5.1 / P10: evaluación | Reglas con variables/unidades/aplicabilidad/fórmula/umbral/fuente/edición/apartado; ensayos debajo/en/sobre límite y ausentes. | Pendiente. Umbrales no deben inventarse para producir semáforos. |
| O5.2 / P11: corpus/RAG | Corpus aprobado con huellas y fragmentos/páginas; recuperar referencia esperada, separar versiones, abstenerse sin sustento. | Pendiente. Fuente normativa vigente y aprobación técnica faltan; búsqueda local puede implementarse independiente de LLM. |
| O5.3 / P11: explicación | Cifras idénticas a contratos; citas existentes y recuperadas; límites claros; fallo LLM conserva plantilla determinística. | Pendiente. La contingencia determinística está contemplada por las fuentes, sin presentarla como generación LLM real. |
| O5.4: dashboard técnico | Mostrar plano, versión aprobada, corrida, siete resultados, unidades/casos y origen. | Pendiente; el control de avance no es esta pantalla. |
| O5.5 / P12: informe | JSON y PDF coherentes con resultados, citas, hipótesis/limitaciones/estado; revisión visual sin cortes; aprobación técnica de entrega. | Pendiente. Generación y validación visual/formal pueden desarrollarse con fixture declarado; aceptación real requiere resultados revisados. |
| O6.1/O6.2 / P14 | Imagen -> extracción -> revisión -> datos/modelo aprobados -> ETABS -> evaluación -> informe, con evidencia P01–P14. | Pendiente; la suite de módulos no es evidencia integral del caso. |
| O6.3: comparación/tipos de tiempo | Registro manual/asistido incluyendo correcciones y cálculo, costo/tarifa/fecha; no atribuir ahorro sin medición. | Pendiente externa/ejecución real. |
| O6.4 / P13: recuperación | Una corrida ETABS activa; persistencia, no duplicar API/modelos, reintentos acotados, reinicio seguro, entradas vigentes. | Pendiente. Persistencia de versiones no equivale a cola y orquestación integral. |
| O6.4: contingencia | CSV/XLSX supervisado -> mismo contrato; fallo LLM conserva tablas; precalculado/grabado claramente identificado. | Pendiente: no se inventar importadores o considerar edición JSON equivalente a CSV/XLSX. |
| O6.5: reproducibilidad | Instalación limpia, configuración sin secretos, ETABS y guía de piloto/pruebas; artefactos/versiones suficientes para repetir. | Guías de módulos presentes; README inicial describe preparación histórica y necesita guía integral vigente. |

## Dependencias que realmente pueden requerir al usuario

1. Proporcionar o identificar **un caso autorizado compatible** y sus datos complementarios, o acordar expresamente una modificación material del alcance. Codex puede preparar formularios e importar lo suministrado; no puede convertir la muestra incompatible en validación del MVP.
2. Identificar al responsable técnico que revisará **plantilla, idealizaciones, materiales/cargas/sitio, modelo manual y tolerancias previas**. Una aprobación declarada debe corresponder a esa revisión; no se deduce de pruebas automatizadas ni del permiso de programación.
3. Configurar acceso al proveedor elegido por un mecanismo local seguro y elegir modelo cuando llegue la prueba visual. El antecedente dice que no había clave; este encargo no inspeccionó secretos ni confirma que siga ausente. La autorización amplia de desarrollar no resuelve por sí sola costo/modelo/datos de una llamada concreta prevista como pendiente en D09; Codex debe resolverlo con el contexto humano disponible antes de enviar.
4. Si la comprobación real descubre licencia no disponible, diálogo de acceso o estación distinta, resolver **esa condición observada**. Hoy solo está sin comprobar: no atribuir todavía un bloqueo de licencia al usuario.
5. Confirmar cobertura/fuentes oficiales e hipótesis aplicables con el revisor. Codex puede investigar fuentes e implementar recuperación, pero este diagnóstico no verificó vigencia normativa/cartográfica ni fija valores.

El token para monitoreo continuo de GitHub, aceptación del colaborador, fecha final o reunión no impiden desarrollar/verificar el producto local. No pedirlos como condición artificial para avanzar. El uso de Claude y subagentes ya está autorizado; el coordinador comprueba disponibilidad y entrega real.

## Orden de cierre recomendado

| Etapa | Responsable operativo | Entrega y evidencia |
| --- | --- | --- |
| A. Consolidar base | Codex, con encargos acotados a Claude | Suite vigente, revisión visual operativa, persistencia geométrica integrada, conversión y contingencias sin pérdida de trazabilidad. |
| B. Núcleo estructural | Codex/Claude implementan; responsable técnico revisa | Contrato estructural y plantilla, adaptador con pruebas de fallos y comprobación real ETABS sobre copia autorizada. Preparar sin esperar a visión. |
| C. Evaluación/entrega | Desarrollo paralelo sin solapar archivos | Contratos de corrida/resultados, reglas configuradas, sitio, corpus/RAG, dashboard y PDF; fixtures explícitamente sintéticos para desarrollo. |
| D. Caso y benchmark | Responsable técnico + Codex | Caso compatible, anotaciones/referencia/tolerancias; llamada visual configurada y medición antes/después de correcciones. |
| E. Validación final | Codex integra/revisa | P01–P14, comparación manual/asistida, tiempos/costos, fallo/recuperación y guía desde instalación limpia. Solo entonces declarar objetivo cumplido. |

La primera extracción PDF emitida por consola encontró una limitación de codificación CP1252 al imprimir una flecha; se repitió la lectura restante con salida UTF-8 y se comprobó P01–P14. No fue un fallo del proyecto ni se modificaron los originales. No se emitió conclusión de seguridad estructural ni de normativa vigente en este diagnóstico.
