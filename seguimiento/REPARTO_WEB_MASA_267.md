# Reparto267: integrar masa en servicios e interfaz web

Estado: acuerdo confirmado visualmente y por respuesta de Claude; implementación en curso. Codex revisó el fix266 con6casos propiosOK, registro`REVISION_MASA_BOOL_267.json`. Corrida09d1 no se reinicia. Claude conserva núcleo de cálculo/lectorPowerShell/libro/normativa/runner/resultados y seguimiento de su handle.

Codex toma exclusivamente `draft2model/revision_lecturas.py`, `draft2model/revision_entregables.py`, `draft2model/informe.py` (solo puente de fuente web en `_masa_nativa`), `draft2model/revision_web/lecturas.js`, `informes.js`, `index.html`, más helper/tests nuevos. Claude no debe editar esos seis archivos hasta liberación; si tiene edición en curso, debe comunicarla y esperar reparto confirmado. No cambiar contratos numéricos, generación nativa ni criterio de masa de Claude.

## Contrato acordado para implementar

- `/api/lecturas/preparar` conserva payload existente; admite opcional `resultados_api: ["AssembledJointMass"]` (backend puede admitir valores exactos de `lectura_analisis.RESULTADOS_API`). Clave ausente mantiene solicitud anterior idéntica. No envío/lectura automático por activar checkbox. Se preservan opt-in, idempotencia, huellas, bloqueo motor, recuperación y revalidación. Se siguen declarando tablas/casos; no se agrega modo API-only.
- La selección de lectura aceptada publica evento `d2m-mass-reading`: `{caso, expediente_sha256, analisis, trabajo, lectura_id, sha256_respuesta, sha256_edb, modo_ejecucion, datos_sinteticos}` solo si la petición incluyó AssembledJointMass y está aceptada/vigente. Emite null al invalidar/cambiar selección. No enviar arrays enormes a eventos; datos crudos permanecen en backend.
- `/api/informe/crear` admite `contenido_masa: true` opcional y `masa_nativa: {trabajo, lectura_id, sha256_respuesta}` opcional. No se aceptan inventarios ni rutas del usuario. El servidor deriva fuentes del expediente/lectura exactos y verifica mismo análisis/modelo/EDB/huellas. Desmarcado omite campos para conservar payload previo. Inventario opcional se deriva del plan del modelo analizado; una casa sin depósitos conserva flujo previo sin agua ficticia.
- Meta/historial/aprobación documental/descargas conservan referencias optativas exactas y recomprueban procedencia. Referencias públicas: `contenido_masa_seleccionado` y `masa_nativa_seleccionada`; datos resultantes son separados. El almacenamiento web usa `lecturas_etabs`, mientras la CLI usa `lecturas_analisis`: se necesita puente explícito comprobado, sin copiar/mover evidencia ni aceptar una ruta arbitraria.
- El checkbox de masa nativa exige lectura real y analisis seleccionado coincidente. Datos de dobles se identifican y no se presentan como captura nativa. El informe debe rechazar fuentes de lectura simulada para la sección nativa; la selección de resultados/tablas sintéticos continúa funcionando con su estado previo.
- UI borra opt-in al cambiar caso, resultado, análisis o lectura; respuestas atrasadas no restauran selección vieja. No deduce cumplimiento normativo ni aprueba resultados/ingeniería.

## Verificación

Pruebas focales Python del servicio y recuperación/metadatos: opción ausente, opción solicitada, idempotencia, referencias exactas, SHA/analisis ajenos, mutación y falta de captura. Node con DOM/HTTP simulado: opt-in/payload, estado real/doble, invalidación y respuesta atrasada. Revisión visual después de integrar, sin APIs ni ETABS solo para probar la UI. La prueba real completa permanece pendiente del09D; no confundir dobles con motor.
