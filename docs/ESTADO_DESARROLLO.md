# Estado y secuencia de desarrollo

Actualizado: 16 de octubre de 2026. Resumen operativo de archivos y comprobaciones locales. Los porcentajes y fechas de pruebas se consultan en **Control de avance.html**; no representan tiempo ni esfuerzo restante.

## Procesos, reparto y requisitos

| Proceso | Estado actual | Claude | Codex | Qué se necesita para completarlo |
| --- | --- | --- | --- | --- |
| Control del proyecto y GitHub | Dashboard local/publicado implementado. HTML enlazado y observador sin servidor disponibles. Hay cambios locales posteriores a la última publicación. | Entregar código y resultados reales de pruebas, sin editar seguimiento en sus tareas acotadas. | Mantener catálogo, evidencias, integración y publicaciones autorizadas. | Asociar las entregas nuevas al criterio correcto y publicar después de revisarlas. Conexión local de lectura propia para consultar GitHub continuamente. |
| Ingreso y preparación de planos | Registro de PDF/JPG/PNG, originales con SHA256, revisión de páginas y recortes implementados. Piloto provisional con tres documentos, fuera del MVP. | Mantener compatibilidad al desarrollar módulos consumidores. | Integración de ingreso, consulta y preparación visual. | Referencia manual y un caso compatible con albañilería confinada de 1–2 niveles para validar el alcance final. La muestra actual sirve para procesamiento. |
| Visión multimodal | Paquetes de contexto/recortes, respuesta estructurada, adaptación de coordenadas y cliente OpenAI preparados. Comandos integrados y pruebas sin red. | Apoyar después en conversión geométrica explícita, sin sustituir la lectura por OCR. | Preparación y futura integración del proveedor, medición y recuperación de errores. | Clave y modelo cuando se retome esa etapa, autorización de un envío concreto, referencia humana anotada y evaluación de las propuestas originales. OCR sigue siendo opcional. |
| Revisión de lecturas | Versiones, correcciones y exportación implementadas. Interfaz con plano, evidencias e historial; servicio y lógica probados. | Gestión de extracciones entregada; corregir incidencias verificadas si aparecen. | Interfaz, comandos y pruebas de integración. | Sesión operativa de navegador, experiencia completa de carga y revisión y conexión con las siguientes etapas. Revisar una lectura no aprueba geometría. |
| Geometría y plan 3D | Contrato/validador, normalización m/cm/mm y plan geométrico implementados. Correcciones numéricas revisadas. Comando principal conserva entradas y salidas. | Entregó validador robusto y plan; mantener sus pruebas al evolucionarlos. | Revisar entregas, integrar comandos y registrar evidencia vigente. | Resolver representación espacial y trazabilidad desde lecturas revisadas. El plan todavía no es un modelo ETABS. |
| Versiones y aprobación geométrica | `gestion_geometria.py`, pruebas y documentación presentes como entrega local de Claude. Pendiente de auditoría e integración. | Tarea asignada: versiones inmutables, revisión, aprobación explícita y comprobación de originales. | Auditar la entrega, integrar CLI/interfaz y asociar planes a la versión geométrica exacta. | Aceptar pruebas y rutas, invalidar aprobaciones ante cambios y mantener el alcance provisional. No dar por completado O4.3 solo por existencia de archivos. |
| Conversión de lecturas a geometría | Pendiente. Las cotas/etiquetas revisadas aún no se convierten automáticamente en nodos, niveles y muros. | Próxima tarea técnica sugerida tras aceptar persistencia: conversión mediante correspondencias y escala explícitas. No está asignada todavía. | Definir el flujo de revisión y enlazar evidencia, versiones y aprobación. | Relaciones espaciales, unidades y referencias declaradas; control de faltantes; no asumir metros a partir de píxeles ni inventar conectividad. |
| ETABS y referencia de ingeniería | ETABS 21.1 detectado; conexión, licencia operativa, adaptador y lectura de resultados sin comprobar. | Futuro núcleo del adaptador con interfaz sustituible y pruebas; sin declarar éxito a partir de simulaciones. | Integración, control de ejecución, diagnóstico y comparación con referencia. | Representación estructural revisada, materiales/secciones, cargas, masa, apoyos/diafragmas, licencia válida y modelo manual de referencia con tolerancias acordadas. |
| Evaluación, fuentes e informe | Evaluador de lecturas implementado con ejemplos sintéticos. Evaluación estructural, corpus/RAG, explicaciones, dashboard técnico e informe pendientes. | Futuras funciones de evaluación y contratos de resultados con casos de frontera. | Fuentes, integración de resultados, presentación y generación de informe. | Resultados ETABS trazables y revisados; criterios, fórmulas, versiones y fuentes aprobados. Ninguna cifra o cita debe inventarse. |
| Validación integral y demostración | Pruebas de módulos disponibles; recorrido completo de imagen a informe todavía pendiente. | Pruebas de sus módulos y recuperación de fallos. | Suite conjunta, pruebas P01–P14, evidencia y demostración reproducible. | Comparación manual/asistida, mediciones reales de precisión, tiempos/costos y fallos ensayados. Distinguir pruebas sintéticas de validación real. |

## Orden recomendado

1. Auditar y aceptar la persistencia geométrica entregada por Claude; integrarla sin duplicar el validador.
2. Enlazar geometría/versiones con los planes derivados, y completar el uso operativo de la revisión visual.
3. Desarrollar conversión revisable desde lecturas a geometría, con correspondencias y escala explícitas.
4. Definir el modelo estructural y construir el adaptador ETABS con una referencia manual. Las decisiones de ingeniería deben preceder a un análisis utilizable.
5. Retomar la llamada de visión cuando estén disponibles clave y modelo; medir respuestas originales contra referencia humana. La preparación local puede continuar mientras tanto.
6. Integrar resultados, evaluación, fuentes e informe; ejecutar validación integral y demostración.

Las etapas con dependencias resueltas pueden avanzar en paralelo. No asignar a ambas sesiones los mismos archivos. Los encargos de Claude siguen siendo locales; Codex revisa e integra antes de publicar. Este reparto describe el trabajo acordado y las propuestas futuras, no atribuye tareas pendientes como ya realizadas.

## Lectura de los resultados

- Implementado significa que hay una entrega de código; verificado exige evidencia vigente sobre esos archivos.
- Una suite sin fallos puede contener omisiones por restricciones del entorno. Las omisiones no cuentan como pruebas aprobadas.
- Si los archivos cambian durante la ejecución, el controlador no acredita esa corrida.
- GitHub se compara con su rama principal y SHA consultado. La lectura del conector no se convierte automáticamente en credencial del observador local.
- La última publicación consultada el 16 de octubre es `9fa805d97dfb39aeb843f856426b78f27d9bfb31`. Los módulos posteriores siguen locales; este resumen no los publica.
