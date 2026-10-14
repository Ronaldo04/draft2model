# Plan de operación

Actualizado: 13 de octubre de 2026. Base documental publicada en GitHub; acceso de consulta y entorno técnico pendientes.

## 1. Organización del avance

El avance se organiza por requisitos, dependencias técnicas, entregas y criterios de aceptación. Codex y Claude Code apoyan la programación y documentación.

Las reuniones por Teams, todos los días a las 22:00 hora de Perú, permiten mostrar avance y discutir cambios en conjunto. Sus acuerdos se registran en Markdown. La duración de las reuniones y el plazo final permanecen pendientes.

Los requisitos y verificaciones técnicas se mantienen. La IA apoya programación, análisis y documentación; no sustituye la aprobación humana de datos, modelo e informe. Una prueba incompleta o una incertidumbre crítica se registra y bloquea la etapa técnica correspondiente.

## 2. Estado de partida

| Elemento | Estado comprobado |
| --- | --- |
| Documentación base y entregables de definición | Disponibles y revisados; se conservan como antecedentes. |
| Contexto y planificación Markdown | Preparados con requisitos y criterios verificables. |
| Referencia para sustentación | Separada de la documentación operativa; no implica aportes ya realizados. |
| Git local | No existente durante la inspección inicial. |
| GitHub remoto | [Ronaldo04/draft2model](https://github.com/Ronaldo04/draft2model), privado, rama main; 23 archivos publicados y verificados. |
| Acceso | El usuario informó acceso concedido a un colaborador; permiso y aceptación no auditados. |
| Seguimiento | Issues #1–#7 para O0–O6, con entregas y criterios de cierre. |
| Preparación O1 | Entorno .venv y diagnóstico ejecutado; ETABS 21.1 detectado. Piloto, licencia y conexión API pendientes. |
| Base de ingreso | Registro local de PDF/imágenes, originales y SHA256 implementado; siete pruebas automatizadas pasan. |
| Contrato geométrico | Propuesta v0.1 implementada; 22 pruebas geométricas pasan. Adaptador ETABS y caso de referencia pendientes. |
| Recortes PDF | Regiones ampliadas con coordenadas y hashes, cinco pruebas adicionales y siete regiones provisionales generadas localmente. |
| Revisión documental | Apertura, páginas y vistas previas implementadas; muestra provisional fuera del MVP procesada localmente. |
| Flujo técnico | Extracción multimodal principal, modelado ETABS, análisis e informe pendientes; falta caso compatible para validar el MVP. |

No confundir una propuesta de arquitectura con un módulo implementado. El remoto confirmado es [draft2model](https://github.com/Ronaldo04/draft2model).

## 3. O0: preparar el repositorio y la consulta

El trabajo inmediato es disponer de una base privada, documentada y accesible para consulta.

| Tarea | Qué requiere hacerse | Criterio de cierre |
| --- | --- | --- |
| O0.1 Modalidad de acceso | Elegir cuenta personal sin acceso de escritura no deseado, o una organización si se exige solo lectura del mismo repositorio. | Propietario y permisos reales registrados; no prometer solo lectura personal. |
| O0.2 Crear remoto | Crear repositorio privado con nombre y URL confirmados. | Visibilidad Private comprobada. |
| O0.3 Preparar contenido | Revisar README, docs, fuentes autorizadas, entregables y exclusiones. | Lista revisada sin credenciales ni material privado no autorizado. |
| O0.4 Carga inicial | Inicializar o clonar según la guía y cargar el contenido revisado. | Archivos visibles, enlaces correctos y copia de trabajo vigente identificada. |
| O0.5 Consulta del equipo | Configurar únicamente el acceso aprobado y comprobarlo con las cuentas elegidas. | Las cuentas autorizadas consultan el código; una sesión anónima no accede. |
| O0.6 Seguimiento | Crear Issues por requisito y acordar la forma de registrar cambios. | Tareas con entregas, dependencias y criterios verificables. |

La implementación puede avanzar una vez que la base de trabajo está disponible. O0.5 registra por separado la comprobación de acceso; mientras siga pendiente, pueden continuar los requisitos cuyas dependencias técnicas estén resueltas.

## 4. Hitos de desarrollo

La secuencia conserva la lógica técnica de los documentos base: primero el caso y el núcleo ETABS con datos aprobados; después incorporar interpretación, revisión, sitio, evaluación y explicación.

| Hito | Desarrollo requerido | Dependencias técnicas | Evidencia para cerrar |
| --- | --- | --- | --- |
| O1 Base de ingeniería y entorno | Obtener caso autorizado; verificar datos; construir referencia manual; fijar hipótesis/tolerancias; comprobar Python y API ETABS. | Información suficiente, estación Windows y licencia válida. | Expediente utilizable, referencia revisada, versiones registradas y lectura real de resultados. |
| O2 Contratos y generación | Implementar esquemas, validaciones, plantilla, generación y extracción desde datos aprobados. | O1 y contrato de entrada definido. | Modelo generado consistente con referencia; objetos, unidades, cargas, masa y resultados comprobados. |
| O3 Interpretación visual | Preparar vistas generales y recortes; interpretación multimodal principal; OCR opcional; evidencia; comparación de candidatos; geometría y faltantes. | Plano y referencia anotada, contrato de extracción. | Precisión inicial medida, errores visibles y salida estructurada corregible. |
| O4 Revisión, persistencia y sitio | Construir interfaz de carga/corrección; aprobaciones/versiones; almacenamiento; condición referencial del sitio. | O2/O3 para integración completa y fuentes cartográficas disponibles. | Correcciones trazables; datos críticos completos; bloqueo de entradas no aprobadas y resultados obsoletos. |
| O5 Evaluación, explicación y entrega | Programar reglas revisadas; corpus y recuperación; explicaciones; dashboard y generador de informe. | Resultados identificados, criterios/fuentes aprobados y contratos coherentes. | Indicadores reproducibles, cifras y citas verificadas, informe técnicamente revisado y legible. |
| O6 Validación y demostración | Integrar ruta desde imagen; ejecutar pruebas P01-P14; medir comparación, tiempos/costos; ensayar recuperación. | Módulos del flujo disponibles y referencia manual. | Caso reproducible, evidencias completas, limitaciones y contingencias identificadas. |

Los hitos describen resultados verificables y no son promesas de duración. O3 puede prepararse mientras se construye O2 cuando sus dependencias técnicas estén resueltas. Las muestras simuladas sirven para implementar interfaces; no se presentan como cálculo ETABS ni validación estructural.

## 5. Requisitos por módulo

| Módulo | Función mínima que debe desarrollarse | Comprobación |
| --- | --- | --- |
| Ingreso | Abrir PDF/JPG/PNG, inventariar láminas y conservar originales autorizados. | Archivo dañado, lámina ausente o imagen ilegible quedan identificados. |
| Imágenes | Corrección de perspectiva/rotación, recortes y escala con referencias. | Coordenadas y cotas se conservan respecto de la referencia. |
| Visión multimodal y apoyo OCR opcional | Interpretar contexto y regiones; proponer textos, elementos, dimensiones y asociaciones con evidencia. | Error y cobertura iniciales medidos; ausencia de datos no se rellena como observación. |
| Contratos y geometría | Esquemas, unidades, identificadores, conectividad y valores válidos. | Rechazo de referencias rotas, unidades incompatibles y datos imposibles. |
| Revisión e interfaz | Plano superpuesto, tablas/formularios y correcciones. | Guardar borrador se distingue de aprobar; cambios actualizan geometría. |
| Persistencia | Expedientes, estados, revisiones y versiones de entrada. | Resultados asociados a la corrida correcta; cambios invalidan salidas afectadas. |
| Sitio | Ubicación, cobertura, cartografía y parámetros aprobados. | Límites y falta de cobertura visibles; sin inferir capacidad portante. |
| Adaptador ETABS | Conectar, parametrizar, guardar modelo y comprobar operaciones API. | Conectividad, unidades, cargas/masa y códigos de error revisados. |
| Análisis y extracción | Ejecutar casos y normalizar valores por nivel, dirección y unidad. | Tablas contrastadas y corrida identificada; fallos no se presentan como resultados. |
| Evaluación | Reglas con fórmula, aplicabilidad, fuente, edición y umbral revisados. | Casos por debajo, en y sobre límites; faltantes/no aplicable diferenciados. |
| RAG | Corpus aprobado, búsqueda y fragmentos identificables. | Recuperación esperada y separación de versiones; abstención sin sustento. |
| Explicación | Texto sobre datos calculados y fragmentos recuperados. | Ninguna cifra alterada ni cita inexistente; incertidumbres visibles. |
| Dashboard e informe | Mostrar siete resultados y producir informe desde contratos verificados. | Valores concordantes, fuentes y supuestos visibles, presentación legible. |
| Orquestación | Una corrida ETABS activa, errores, reintentos acotados y recuperación. | Sin trabajos duplicados ni mezcla de resultados; contingencias identificadas. |
| Reproducibilidad | Instalación, configuración sin secretos, instrucciones y registro de versiones. | Repetir el caso usando la evidencia e instrucciones conservadas. |

La documentación de trabajo se mantiene en Markdown. El PDF técnico generado por el producto sigue siendo una salida prevista: no es una nueva obligación de redactar la planificación en PDF.

## 6. Ciclo de trabajo

**Requisito -> tarea -> cambio -> comprobación -> integración -> actualización Markdown.**

1. Elegir una tarea por su dependencia y criterio de aceptación.
2. Usar una rama cuando convenga aislar cambios; evitar que sesiones de Codex y Claude Code editen simultáneamente el mismo archivo sin coordinación.
3. Revisar los cambios generados y ejecutar comprobaciones pertinentes al módulo.
4. Registrar resultado, límites y evidencia. Un PR puede utilizarse como registro del cambio. La integración se sustenta en criterios y comprobaciones verificables.
5. Integrar solo cuando se cumpla el criterio técnico; actualizar decisiones y avances.

Los campos mínimos de una Issue son objetivo, módulo, entrega, dependencias, comprobación y evidencia.

Estados: Pendiente, En curso, Bloqueado, En verificación y Terminado. Un bloqueo describe el dato, acceso o condición técnica faltante. Una sugerencia de reunión no se transforma automáticamente en dependencia; registrar primero la decisión y su efecto.

## 7. Reuniones y consulta

Mostrar el estado del proyecto y los cambios, discutir observaciones en conjunto y registrar decisiones, límites y siguiente requisito.

Teams se usa para la reunión. GitHub y Markdown conservan el resultado. El acceso permite leer, consultar y verificar el código según los permisos disponibles. La aceptación técnica se sustenta con pruebas y comprobaciones documentadas.

## 8. Documentación viva

| Archivo | Qué se registra |
| --- | --- |
| `README.md` | Entrada al proyecto, estado y modo de ejecución vigente. |
| `docs/CONTEXTO_PROYECTO.md` | Objetivo, alcance, arquitectura y verificación requeridos. |
| `docs/PLAN_OPERACION.md` | Hitos, requisitos, dependencias y aceptación. |
| `docs/GUIA_GITHUB_PRIVADO.md` | Puesta en marcha y acceso de consulta. |
| `docs/REGISTRO_DECISIONES.md` | Decisiones aceptadas, motivo y cambios de dirección. |
| `docs/AVANCES.md` | Entregas, pruebas, bloqueos y próximos requisitos. |

Registrar fecha, motivo y evidencia de procedencia cuando sea útil para trazabilidad. Usar historial Git en lugar de copias final/final2. La documentación histórica queda como antecedente, no como instrucción de ejecución.

## 9. Acceso y entorno

Repositorio privado y cuentas autorizadas. Un privado personal no permite un lector sin escritura; para Read efectivo sobre ese repositorio se necesita una organización. No conceder escritura al equipo suponiendo que es solo consulta. La modalidad definitiva requiere confirmar ese límite antes de invitar.

GitHub comparte código/documentos, no ejecuta ETABS ni sincroniza automáticamente instalaciones. Registrar la estación real de desarrollo, licencia, versiones y configuración. Mantener claves y expedientes privados fuera del seguimiento inicial. Las fuentes y muestras deben tener autorización de uso.

## 10. Definición de terminado y siguiente paso

Completar un caso desde la imagen hasta el informe con datos/modelo aprobados, extracción evaluada, correcciones trazables, siete resultados, reglas y fuentes identificadas, comparación manual/asistida y tiempos/costos. Conservar pruebas P01-P14 y distinguir resultado inicial de IA de resultado corregido.

La base privada de GitHub está disponible. El siguiente paso técnico es O1; O0 conserva pendientes de acceso y copia Git local. No se estima fecha final hasta conocer plazo y disponibilidad del desarrollo.
