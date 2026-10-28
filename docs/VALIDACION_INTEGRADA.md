# Evidencia de integración

Fecha local: 16 de octubre de 2026. Estado: desarrollo en curso, sin cierre global.

## Base y ejecución

La suite base tenía 263 pruebas. Una corrida posterior al primer bloque de integración ejecutó 312 pruebas sin fallos, con 7 omitidas por permisos de enlaces del sandbox. Registro en `tmp/verificacion/suite.log`; resumen en `tmp/verificacion_local.json`. Los módulos aún cambiaban en paralelo: se repetirá sobre archivos estables antes de aceptar el conjunto final. Las omisiones no se acreditan como pruebas aprobadas. `scripts/verificar_proyecto.py` conserva comandos, salidas y huellas y detecta cambios durante la corrida.

## Revisión en navegador real

Se creó un expediente sintético aislado con `scripts/preparar_demo_local.py`, se sirvió en loopback 127.0.0.1:8777 y se abrió en el navegador integrado. La instancia inicial dentro del sandbox no era accesible desde el navegador del host; se utilizó una instancia fuera del aislamiento manteniendo loopback y controles de sesión/origen.

Recorrido observado:

1. Seleccionar `sintetico-001`: plano renderizado, muestra fuera del MVP visible.
2. Abrir geometría raíz `16b8ebab9d0c472a94a3465faf154a15`: evidencia vigente, marca sintética y espesor faltante explícitos.
3. Completar espesor sintético y retirar su faltante mediante JSON revisado, revisor/fecha/motivo: nueva versión `7b3079de60494acdbf16d92672dd1238`, borrador sin aprobación.
4. Declarar alcance sintético y marcar confirmación explícita: nueva versión `74f6379f72b748ffb277e3600f987735`, aprobación ligada a huella `09bf167896fe85f0deea097fb8a2a6d382d3be1f3029b3fa8e2ead44cc5296c7`; versiones anteriores conservadas.
5. El botón de aprobación queda deshabilitado al faltar campos/confirmación, existir faltantes/cambios no guardados o una aprobación previa.

Captura completa: `tmp/revision_integrada_verificada.png`. Esta aprobación es exclusivamente una prueba de software sobre datos sintéticos; no representa revisión profesional de un caso real. La prueba HTTP automatizada cubre además evidencia alterada, huellas, originales, JSON inválido y rechazos sin versiones adicionales.

## Configuración estructural en navegador (17 de octubre)

Se abrió el servicio actualizado en 127.0.0.1:8778 sobre el expediente de la demo integrada. Configuración importada en borrador `42ced3b3625f46a5b195fea1724491ec`; revisión desde formulario JSON `1a2127bdef5842b6af1fe2791a471da5`; aprobación explícita sintética `a32f72fa6e7040fab6813c328385fb66`. La interfaz mostró datos sintéticos y «Configuración apta según contrato; modelo ETABS pendiente de comprobación». La aprobación solo se habilitó con campos/confirmación y quedó deshabilitada después. Se conservó captura tmp/configuracion_web_verificada.png. El parámetro cambiado y revisor fueron fabricados para prueba de software; no se ejecutó ETABS ni se aprobó un modelo real.

## Lectura ETABS real

Actualización posterior: se construyó un caso estático sintético mediante 42 operaciones reales, guardado EDB y lectura independiente también después de reapertura. Evidencias y límites en ENSAYO_ETABS_ESTATICO.md. No hubo análisis; no acredita el proyecto de referencia.

Suite integrada posterior: `tmp/verificacion_integracion_etabs_estable_002.json`, 461 pruebas correctas en 79.043 s, sin omisiones, pip check y arranque CLI correctos, hashes estables durante ejecución. Los logs se conservan en carpeta exclusiva enlazada por el informe. La corrida anterior de igual número de pruebas tuvo cambios durante su ejecución y no se usa como evidencia estable.

ETABS instalado se inició por Computer Use y mostró su pantalla inicial. La API se comprobó desde **Windows PowerShell 5.1 fuera del sandbox**, cargando la DLL instalada y conectando a la instancia activa. `SapModel.GetVersion` devolvió **0**, versión **21.1.0**, unidades `lb_in_F`, nombre `(Untitled)`. No se abrió un modelo de usuario, no se cambiaron unidades, no se ejecutó análisis ni se concluyó licencia válida para cálculo. La consulta demuestra conexión y lectura API reales.

PowerShell 7 falló por método `Marshal.GetActiveObject` ausente. La conexión desde el sandbox no localizaba la instancia del host; no era evidencia de ausencia de ETABS. La ejecución de un archivo .ps1 recibió `AuthorizationManager check failed`; no se cambiaron políticas de seguridad. La lectura explícita con `powershell.exe -NoProfile -Command` fuera del sandbox respondió correctamente. El puente deberá manejar compatibilidad y errores sin eludir controles del sistema.

## Coordinación con Claude

Ampliación del 17 de octubre: Codex ejecutó la demostración completa en `tmp/demo_integrada_revision_001` y su comprobación devolvió correcta=true y seis corridas completadas. Informe JSON/HTML/PDF borrador generado, tres páginas inspeccionadas en `tmp/qa_informe_integrado_001/contacto.png`: sin cortes observados, tablas y cifras legibles. Suite conjunta de ese bloque: 401 pruebas sin fallos y 8 omisiones explícitas (siete de enlaces y una clase del puente bloqueada por política). Después se añadió una regresión de incertidumbre del motor: suite del adaptador 20 pruebas sin fallos, una clase omitida por política. No equivale a ejecutar operaciones estructurales reales. Los cambios posteriores se registran en nuevas evidencias.

Primera entrega: CLI geométrica, archivo real/registro en __main__, 7 pruebas nuevas y guía. En conversación «Comandos CLI geometría» se verificó visualmente mensaje enviado y respuesta con ruta completa. Codex inspeccionó archivos y ejecutó su suite. Segunda tarea enviada y visible en historial: puente ETABS por plantilla/copia, transporte y errores; aún en desarrollo. Un indicador de actividad no se considera entrega.


## Extensión real dinámica del 17 de octubre

La evidencia operativa del motor ya incluye construcción modal/espectral sintética69 operaciones, reapertura y27 controles dinámicos,55 estáticos y coordenadas. Análisis EST/MOD/EX en estado4 tras reabrir y resultado normalizado994e298b81b9435fbf9fde9f3eba2f30. Informe con evidencia de análisis revalidada, tres páginas rasterizadas con Poppler e inspeccionadas en tmp/qa_dinamico_039; copia final output/pdf/ensayo_dinamico_preliminar.pdf (SHA25681d6d809132673c782d077772c70f3df0d74c9283cec2e912ce06eb6655c7f35). Ver ENSAYO_ETABS_DINAMICO.md para trazas, fallos y límites.

El panel dinámico con evidencia se genera en tmp/panel_dinamico_040.html; aún no acredita revisión visual del HTML ni integración del recorrido web hacia ETABS. No hay prueba de visión del proyecto real ni comparación de ingeniería completadas. La entrega local de Claude de evidencia/informe/panel fue comprobada y reforzada por Codex; no se atribuye un nuevo envío UI mientras Computer Use sigue detenido.
