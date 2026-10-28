# Relectura web de un modelo construido

El panel se activa al abrir un modelo construido comprobado. La preparación conserva expediente, origen del modelo, plan y expectativa; no abre ETABS. La lectura se inicia mediante una confirmación explícita separada. No recibe rutas, DLL, órdenes, procesos, claves ni fábricas desde HTTP.

La selección exige modelo y huella vigentes. `criterios` es el objeto completo de 13 magnitudes del lector, con `relativo` y `absolutos`, sin valores físicos o tolerancias por defecto. `ejes_locales_area` es un objeto explícito aceptado por el lector o `null`; no se inventan ejes. Véanse [lector](VERIFICACION_MODELO_GUARDADO.md) y [vínculo](VINCULO_VERIFICACION_MODELO.md).

## Protocolo

Todos los POST usan la sesión y comprobación de origen de revisión local. Campos exactos:

- POST `/api/modelo/verificacion/preparar`: `{caso,modelo,huella_modelo,expediente_sha256,clave_solicitud,criterios,ejes_locales_area}`. `modelo` y `clave_solicitud` son UUID hex de 32 caracteres. La misma clave y contenido devuelve el mismo trabajo; reutilizarla con otros datos falla. Cada clave diferente permite otra preparación explícita.
- POST `/api/modelo/verificacion/ejecutar`: `{caso,trabajo,huella_preparacion,expediente_sha256,confirmacion_explicita:true}`. La huella vincula toda la preparación. Repetir la petición de un trabajo iniciado consulta su estado; nunca relanza.
- GET `/api/modelo/verificacion/estado?caso=...&trabajo=...`: consulta y revalida fuentes y evidencia.
- GET `/api/modelo/verificacion/historial?caso=...`: devuelve `trabajos` del caso, revalidados, y huella del expediente vigente.

El servidor conserva SQLite y evidencia inmutable en `trabajos_verificacion_modelo`; el resultado publicado queda en `verificaciones_modelo`. El EDB procede exclusivamente del snapshot interno del modelo registrado. Reproduce el resultado desde observaciones usando el vínculo, verifica identidad, criterios, ejes y hash del registro. Cambiar una respuesta o la fuente invalida la presentación como comprobada.

## Estados y exclusión

`preparado` no significa leído. `en_ejecucion` mantiene una reserva compartida con construcción, análisis y lecturas. El worker no bloquea el servidor HTTP. El lector usa el mismo bloqueo de motor, instancia nueva y cierre sin guardar. `aceptado` indica evidencia de lectura conservada y reproducible; no significa que el modelo coincida. Hay que consultar conjuntamente `resultado.estado`, `verificado`, `verificacion_global_del_plan`, `cobertura_plan`, discrepancias y controles `sin_criterio`. Un resultado parcial o con discrepancias se conserva como tal.

`incierto` requiere recuperación fuera de este panel: no hay reenvío, limpieza de reserva ni recuperación automática. Un trabajo en ejecución sin reserva viva se considera huérfano y pasa a incierto; un error de worker conserva la reserva pendiente. Un origen alterado antes de lanzar produce `fallido_sin_lanzar`. Ninguno representa éxito.

El modo predeterminado es real. La fábrica del lector solo se inyecta desde código de pruebas, y su modo debe coincidir con el modelo y con el bloqueo compartido. Un modelo doble exige datos sintéticos declarados y no puede leerse con la configuración real predeterminada.

El cliente consume confirmación al editar criterios/ejes, cambiar caso/modelo/trabajo, consultar o ejecutar; descarta respuestas tardías mediante una generación de selección. Reutiliza una clave de preparación tras fallo de red hasta editar, sin reintento automático. No consulta periódicamente ni ejecuta desde historial.

## Límites

Este servicio no aprueba modelos, no autoriza análisis y no modifica sus gates. No habilita el ejecutor de desarrollo 0.2. Sus pruebas usan modelos sintéticos conservados en disco y transporte Python fabricado, sin ETABS real, red externa ni planos de referencia. La comprobación visual del panel integrado y el ensayo real corresponden a integración de Codex.
