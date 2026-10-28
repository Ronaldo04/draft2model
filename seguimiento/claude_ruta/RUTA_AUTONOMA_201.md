# Ruta autónoma201 — implementación completa hasta validación final

Autorización vigente del usuario: trabajar una tarea tras otra sin esperar nuevas asignaciones. Claude implementa, integra, depura, prueba y documenta. Codex revisa entregas y evidencias; NO editará simultáneamente tu código. Debes leer esta ruta y después cada tarea en orden. No terminar tu turno al completar una etapa: conservar entrega, actualizar tu estado y abrir la siguiente. Compáctate y conserva estado si hace falta; respeta cuotas, permisos e interrupciones. Una ruta no permite continuar durante una suspensión del servicio.

## Propiedad y límites

Tienes propiedad EXCLUSIVA de implementación en draft2model/, scripts/, tests/, examples/ y documentación de producto docs/, README.md, requirements.txt, requirements-win-py310.lock y los lanzadores raíz Abrir revision de planos.cmd/Abrir control de avance.cmd. Puedes crear auxiliares necesarios dentro del proyecto. Conserva cambios ajenos; no borrar originales, claves, modelos, evidencias históricas ni registros de incertidumbre. Codex conserva SOLO seguimiento/ de coordinación/revisiones y las copias de revisión tmp/revision_codex_*. Tú posees seguimiento/claude_ruta/estado.json, entregas/ y tus informes en esa subcarpeta. No modificar CLAUDE_ESTADO.json, estado_claude.py, REVISIONES.json ni encargos/ruta dados. Cambios necesarios a docs/RETOMAR.md están autorizados para mantener estado vigente breve, con historia separada. No existe Git: snapshots son obligatorios.

No instalar software ni cambiar políticas de seguridad para salvar fallos de entorno. No leer/imprimir claves. Las APIs Google/OpenAI SOLO para revisión de planos y extracción estructurada; prohibidas para programar, documentar, explicar resultados o pruebas genéricas. No otras APIs. Google/OpenAI son las únicas opciones operativas autorizadas; no habilitar proveedores adicionales. ETABS usa API local instalada, sin clave. Instancias NUEVAS propias, copias y destinos NUEVOS; ningún GetObject global/instancia activa del usuario. Verificar PID+modelo propio antes de modificar/cerrar. No tocar el modelo manual del usuario (retenido para comparación posterior).

## Ejecución continua y revisión

Orden fijo: 01_ESTABILIZAR.md → 02_LIQUIDOS_OPCIONALES.md → 03_INTEGRACION_REFERENCIA.md → 04_PILOTO_REAL.md → 05_REPRODUCIBILIDAD.md → 06_CIERRE.md. La revisión de Codex NO es condición para empezar la siguiente etapa. Consulta REVISIONES.json entre etapas si existe; corrige fallos críticos y registra correcciones sin detener trabajo independiente. No hace falta pedir permiso para cada cambio técnico rutinario dentro de este alcance.

Una dependencia de datos, gasto, licencia, cuota o permiso que no puedes resolver debe quedar descrita concretamente. Marca SOLO esa parte bloqueada y continúa las etapas/tareas independientes. No suplantar revisión profesional, inferir datos estructurales faltantes, inventar tolerancias normativas ni sustituir referencia por fixtures. No calificar como éxito un camino alternativo que omite requisitos. No reintentar operaciones API inciertas ni reiniciar procesos vivos por timeout de observación. Consulta el mismo handle o evidencia autoritativa antes de decidir que terminó. No prometer ejecución por encima de cuotas.

## Protocolo de entrega inmutable por etapa

Al terminar cada etapa, crea directorio NUEVO entregas/<numero>-<id_unico>/. Conserva ahí: fuentes.zip (solo archivos de código/docs/tests/examples y archivos raíz autorizados cambiados, rutas relativas seguras, sin credenciales/data/private/tmp originales), manifiesto.json y logs pertinentes. El manifiesto lleva tarea="ruta_autonoma_201", id único, etapa "01".."06", estado="entregado" o "bloqueado", snapshot={ruta:<ruta relativa proyecto de fuentes.zip>,sha256:<hash>}, archivos={ruta original:sha256 de bytes incluidos}, pruebas y resultados observados, limitaciones/bloqueos, siguiente_etapa. Añade docs/evidencias necesarias a la entrega. No edites después ni el ZIP ni el manifiesto; correcciones van a otra entrega. Los tests reportados deben corresponder a esa instantánea.

Luego actualiza TU estado.json con tarea="ruta_autonoma_201", etapa_actual, estado="trabajando"/"bloqueado"/"finalizado", ultima_entrega=<ruta relativa al manifiesto más reciente>, siguiente_accion, procesos_vivos y bloqueos. Mantén ultima_entrega mientras avanzas la siguiente etapa. Codex comprueba ZIP+manifiesto y revisa la instantánea aunque hayas avanzado en el árbol vivo. No publiques estado finalizado hasta auditar todos los requisitos. Al terminar una etapa lee inmediatamente la siguiente. Un borrador, indicador de actividad o marcador no acredita calidad.

## Punto de partida autoritativo

Lee docs/RETOMAR.md, documentación vigente y los seis encargos; contrastar código real antes de editar. Hay una salvedad reciente importante en 01. Relectura196:5SHA revisados,11tests propios con1omitida ambiental; la prueba omitida se ejecutó en host:1OK5.387s. Root añadió conversión dimensional a malla después:7testsComparacionMallaOK2.203s. No revertir. Sin nueva tarea enviada tras196 hasta esta ruta.

