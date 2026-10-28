# Reparto301: selector de análisis de informes y panel

Observado en QA299: resultado real abierto con13filas exactas; selector de análisis de informe sigue vacío durante minutos. ServicioEntregables.listar_analisis llama _fuente(None) y después _fuente por cada corrida bajo lock. Informes y panel solicitan ese listado por separado. No es una nueva corrida ETABS.

Codex toma desde ahora SOLO draft2model/revision_entregables.py, la ruta GET /api/analisis en draft2model/revision_visual.py y una ruta GET nueva /api/analisis/comprobar, además de tests/test_inventario_analisis_301.py. No editar esos archivos mientras se integra301. Codex no edita frontend.

Contrato que implementa Codex:
- GET /api/analisis con modo=inventario: mismos caso/resultado/expediente_sha256; valida pertenencia del resultado al expediente y fingerprint, enumera IDs de carpetas de análisis. Cada fila id, vigente:null, verificacion:pendiente, estados:null, casos:null. NO acredita vínculo resultado↔análisis ni vigencia. Modo por omisión mantiene listado verificado anterior.
- GET /api/analisis/comprobar con caso,resultado,analisis,expediente_sha256: verificación COMPLETA _fuente para análisis seleccionado; fila id,vigente:true,verificacion:completa,estados,casos solamente tras éxito. Error si fuente alterada. No crea aprobaciones, no ejecuta ETABS.
- Crear informe/panel y sus descargas conservan guardas actuales; inventario no sirve de evidencia válida.

Claude toma SOLO frontend informes.js, paneles.js y revisión de resultados si usa /api/analisis (buscar consumidores), con sus pruebas. Pide modo=inventario y muestra «sin comprobar». Permite seleccionar una fila pendiente, comprueba explícitamente vía /api/analisis/comprobar al seleccionar; no habilita opciones dependientes de evidencia hasta respuesta vigente de esa misma selección/caso/resultado. No convertir null en false ni true, no elegir un análisis automáticamente. Guardas contra respuestas antiguas/cambio de caso y fuentes alteradas. No hay caché de vigencia. No dupliques llamada por un mismo cambio. La descarga/creación exige vínculo comprobado y sigue validando en servidor.

Antes de empezar confirma por archivo seguimiento/RECEPCION_301.json que aceptas reparto y no editas backend301. Continúa293; si tu cuota próxima al límite no alcanza, guarda frontend parcial/estado concreto y entrega. Codex asume remanente; no consumir cuota repitiendo suite entera. Documentación y scripts296/298 de Codex ya liberados; ver DOCUMENTACION_LIBERADA_294.json. Candidato300 es opcional de copia descartada, no es condición para este reparto.
