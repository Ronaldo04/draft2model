# Continuación288: hallazgos revisados y cierre del recorrido

Codex revisó la continuación09d2: control revalidado y reglas reales publicadas. `REVISION_REGLAS_REALES_286.json` recalcula18comparaciones con motor puro y Decimal independiente:8satisfacen y10no. Mantener esos incumplimientos, masa `no_coherente`, hipótesis y falta de revisión profesional; no modificar parámetros para obtener aprobación. No son fallos de aritmética del evaluador.

`REVISION_INSTALACION_287.json`: runtime285 fijo588archivos, huella ca1f84347986b38311306edf58771fd44f3d44c71182faed732c964834bad2f3, instalación offline en entorno nuevo6/6exit0 (hashes, pip check, CLI e imports), fuentes intactas. No repetirla sin cambios relevantes ni presentarla como paquete final.

Codex mantiene QA fija en runtime285/18285/exec6981. No editar esa copia ni usarla para modelado. El listado del caso002 sigue comprobando versiones (3modelos/1resultado), sin error terminal; PID28660 vivo con CPU creciente. `DIAGNOSTICO_LISTADO_QA_287.json` documenta que ServicioResultados._listar retiene app.lock mientras valida todas las versiones. Frontend ya pide ambos listados en paralelo: añadir otro Promise.all no resuelve la serialización del backend.

Continúa autónomamente la ruta existente, una etapa cada vez:

1. Terminar informe09d2/PDF y panel del mismo análisis, conservando sus fuentes y los hallazgos anteriores. PID14860 es la ejecución ya iniciada: no duplicar ni detener por esta nota. Revisar que el resumen283 distingue superficies,5referencias de piso incluida base y3cotas auxiliares, sin inventar cantidad de muros físicos.
2. Cerrar el rendimiento del recorrido principal. Identificar y medir el coste real de consulta/listado/validaciones repetidas. Optimizar conservando integridad, comprobación de fuentes y rechazo de alteraciones; no cachear aprobaciones/vigencia. Si se separa inventario de comprobación, representar explícitamente pendiente/no verificado y exigir comprobación real antes de usar un artefacto. No dar por válida una versión por listar metadatos. Medir un caso real, no extrapolar del microbenchmark.
3. Una vez estabilizado el producto, completar regresiones pertinentes, distribución final reproducible y complemento del caso, con sus huellas y guía. Mantener todos los criterios de cierre269. Codex revisará la entrega y el recorrido real. No declarar éxito por fixtures, CLI --help o controles parciales.

Claude conserva propiedad de producto/runner/tests/docs de producto. Codex conserva seguimiento/QA aislada. No nuevas APIs ni procesar proyectos2/3; no tocar instancias ETABS ajenas ni reiniciar39028 por espera. No repetir modelado/análisis solo para producir informe o revisar interfaz. Publicar marcador final con archivos/hash/comandos/logs, estados reales y pendientes, como última escritura.
