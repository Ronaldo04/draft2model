# Draft2Model

Asistente para transformar planos estructurales en modelos ETABS y una evaluación sismorresistente preliminar trazable, con revisión humana.

**Estado al 13 de octubre de 2026:** repositorio privado creado en [Ronaldo04/draft2model](https://github.com/Ronaldo04/draft2model). Carga inicial de 23 archivos completada y verificada; plantillas y seguimiento O0–O6 disponibles. Esta carpeta todavía no tiene historial Git local; O1 está en preparación; ingreso y revisión documental están implementados; el usuario informó acceso concedido a un colaborador.

## Documentación de trabajo

| Documento | Qué contiene |
| --- | --- |
| [Control de avance](docs/CONTROL_AVANCE.md) | Tablero local/publicado, criterios comprobados, cambios e historial. |
| [Contexto del proyecto](docs/CONTEXTO_PROYECTO.md) | Objetivo, alcance, arquitectura, resultados y validación. |
| [Registro de extracción](docs/EXTRACCION_PRELIMINAR.md) | Candidatos, evidencias, correcciones y exportación de lecturas revisadas. |
| [Evaluación de visión](docs/EVALUACION_VISION.md) | Protocolo de referencia manual y medición de precisión, omisiones y evidencia. |
| [Evaluador de lecturas](docs/EVALUADOR_VISION.md) | Comparación reproducible de propuestas originales y referencia declarada; ejemplo sintético. |
| [Entrada y salida de visión](docs/ENTRADA_VISION.md) | Paquetes locales de contexto/recortes y adaptación estricta de respuestas; proveedor pendiente. |
| [Primer conector OpenAI](docs/CONEXION_OPENAI.md) | Preparación sin clave, ejecución explícita y enlace con importación/revisión; prueba real pendiente. |
| [Comandos de extracciones](docs/CLI_EXTRACCION.md) | Importar, validar, corregir y exportar con versiones y comprobación de evidencia. |
| [Contrato geométrico](docs/CONTRATO_GEOMETRIA.md) | Propuesta v0.1, unidades, referencias, faltantes y aprobación ligada al contenido. |
| [Recortes trazables](docs/RECORTES.md) | Regiones PDF ampliadas y transformación de coordenadas para evidencia. |
| [Revisión documental](docs/REVISION_DOCUMENTAL.md) | Inventario de páginas, vistas previas y muestras fuera del alcance. |
| [Ingreso de expedientes](docs/INGRESO_EXPEDIENTES.md) | Comando de ingreso local, trazabilidad y controles implementados. |
| [Preparación O1](docs/O1_PREPARACION.md) | Entorno comprobado, datos del caso piloto y referencia de ingeniería. |
| [Plan de operación](docs/PLAN_OPERACION.md) | Cómo organizar, ejecutar, revisar y cerrar el trabajo remoto. |
| [Guía de GitHub privado](docs/GUIA_GITHUB_PRIVADO.md) | Creación, permisos, carga inicial y acceso de consulta. |
| [Registro de decisiones](docs/REGISTRO_DECISIONES.md) | Decisiones vigentes y asuntos pendientes. |
| [Registro de avances](docs/AVANCES.md) | Evidencia de lo terminado, bloqueos y próximos pasos. |

## Forma de ejecución

El avance se organiza por requisitos, hitos y comprobaciones. Codex y Claude Code apoyan la programación y documentación. Las reuniones permiten consultar el progreso y discutir los cambios; los acuerdos se registran en Markdown.

La planificación organiza requisitos, dependencias, verificaciones y entregas. La [referencia para la sustentación](docs/REFERENCIA_SUSTENTACION.md) conserva la distribución histórica del programa y permite registrar aportes reales con evidencia; no dirige la ejecución.

## Cómo comenzar

1. Leer el plan y elegir cómo proporcionar acceso de consulta al equipo antes de invitar personas.
2. Consultar el repositorio privado [draft2model](https://github.com/Ronaldo04/draft2model) y la guía de permisos.
3. Revisar el contenido a compartir y realizar la carga inicial.
4. Verificar que las cuentas autorizadas pueden consultar el código con los permisos acordados.
5. Consultar las [Issues O0–O6](https://github.com/Ronaldo04/draft2model/issues) y registrar el cierre de cada requisito con evidencia.

Reunión de coordinación: Teams, todos los días a las **22:00, hora de Perú**. Su duración y la fecha final del proyecto no están acordadas.

## Fuentes conservadas

- [Desarrollo técnico](SismoVivienda_AI_Desarrollo_Tecnico.pdf).
- [Entrega de avance](<SismoVivienda_AI_Entrega_Avance 01 - 03-10-2026.pdf>).
- [Resumen reciente](entregables/Draft2Model_One_Page.html).

SismoVivienda AI es el nombre utilizado en los documentos base; los entregables recientes utilizan Draft2Model. Los PDF y entregables originales se preservan como antecedentes históricos: sus asignaciones de personas no son instrucciones operativas vigentes. Los nuevos acuerdos, planes y avances se escriben en Markdown y se versionan.

La documentación operativa no sustituye la aprobación de datos, modelo e informe. El prototipo no certifica seguridad estructural, predice colapso ni diseña reforzamientos.

## Configuración verificada

Repositorio privado en la cuenta personal Ronaldo04; Issues habilitado; Pages desactivado; sin workflows de despliegue. main no tiene protección técnica: las reglas avanzadas requieren GitHub Pro en este privado. El flujo de comprobación e integración se aplica como convención.

El usuario informó acceso concedido a un colaborador; el permiso efectivo no se ha auditado. Los repositorios privados personales no ofrecen colaboradores de solo lectura.

## Primera función disponible

El [módulo de ingreso](docs/INGRESO_EXPEDIENTES.md) registra PDF e imágenes autorizadas, conserva originales y hashes SHA256 y genera un expediente en borrador. Sus siete pruebas automatizadas pasan. Se dispone de una muestra provisional fuera del MVP para pruebas de procesamiento. La revisión documental genera vistas previas y errores por archivo/página. La extracción mediante visión, OCR auxiliar, conexión ETABS, análisis e informe no están implementados.

## Contrato geométrico disponible

Contrato y validador v0.1 para niveles, nodos y muros, con normalización a metros, comprobación de referencias y separación entre consistencia y aprobación registrada. Es una propuesta inicial con ejemplo sintético; no incluye materiales, cargas ni validación estructural. La suite incluye el registro de extracción preliminar y el controlador de avance; el resultado vigente se consulta en el tablero. Los recortes PDF y el registro de candidatos con evidencia están implementados; la generación de candidatos mediante visión y su integración con comandos y almacenamiento siguen pendientes.

## Interpretación principal de planos

La extracción se basará en visión multimodal: vista general, recortes y contexto para proponer elementos, cotas y relaciones con evidencia. OCR será un apoyo opcional para lecturas puntuales o contraste, sin gobernar el flujo ni imponer un orden previo al plano. La salida debe ser estructurada, revisable y conservar faltantes; el proveedor y la precisión aún requieren pruebas.

## Ver el avance del desarrollo

Hacer doble clic en **Abrir control de avance.cmd** en esta carpeta. El tablero compara criterios O0–O6 locales y publicados, muestra pendientes y observa cambios mientras su proceso esté activo. La lectura continua de GitHub necesita una conexión de solo lectura propia; el acceso del conector del chat no se hereda automáticamente. Instrucciones y límites en [CONTROL_AVANCE.md](docs/CONTROL_AVANCE.md).
