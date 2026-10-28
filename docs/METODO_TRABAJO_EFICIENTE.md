# Método de trabajo eficiente

Decisión del usuario, 18 de octubre de 2026: reducir consumo de contexto y avanzar por entregables amplios. El objetivo completo y sus criterios de calidad se conservan.

1. Un responsable por conjunto de archivos. Encargos amplios y autónomos; evitar microtareas y revisiones duplicadas entre Claude y subagentes.
2. Claude se consulta cuando entrega, aparece un bloqueo concreto o vence un plazo razonable sin artefactos. No sondear su pantalla continuamente. Primero revisar archivos locales; Computer Use solo para enviar/confirmar instrucciones o resolver un bloqueo de coordinación.
3. Entrega de cada participante: hasta10 líneas con archivos, resultado, comando/pruebas observadas, límites y siguiente dependencia. Los detalles extensos van al proyecto, no al chat.
4. Revisión de Codex: una lectura del cambio y una prueba focal pertinente. Repetir o profundizar únicamente ante un fallo material, evidencia dudosa o cambios posteriores. Para persistencia, coordenadas y vínculo ETABS se mantiene revisión suficiente para evitar resultados falsos.
5. Una suite completa por hito integrado y con fuentes estables. No ejecutar toda la suite después de cada archivo. Conservar logs y mostrar solo resultado/tail o error pertinente; no reenviar salidas largas.
6. RETOMAR.md debe contener el estado vigente breve. Conservar la historia en archivos de historial y evitar releerla completa. Registrar decisiones, propietarios, procesos vivos y próximos pasos antes de una pausa por cuota.
7. No acreditar archivos por existir, borradores como mensajes enviados, actividad como finalización, simulaciones como motor real ni omisiones/timeouts como verificación completa.

La revisión automática de una captura del navegador falló por límite de uso. No se elude: se continúa por implementación y verificación local que estén permitidas. El siguiente envío a Claude se conserva preparado y no se declara enviado hasta observarlo realmente en el historial.

## Detección económica de entregas

Se configuró heartbeat cada3minutos por petición del usuario; actualmente permanece pausado. El registro de seguimiento indica su estado vigente; no se promete supervisión durante pausas o límites. Ejecutar solo `.venv/Scripts/python.exe seguimiento/estado_claude.py` primero: devuelve un JSON compacto. Sin marcador, continuar el trabajo independiente sin Computer Use ni pruebas repetidas. Una entrega candidata exige hashes coincidentes, revisión breve y prueba focal; no es aceptación automática. Los encargos futuros deben exigir marcador como última escritura. Tras revisión, actualizar CLAUDE_ESTADO.json a revisado y después registrar nuevo encargo enviado. Usar CU solo para confirmación/envío, nunca sondeo rutinario. La automatización y el trabajo respetan cuotas; no puede garantizar ejecución durante una suspensión por límites.
