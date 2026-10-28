# Configuración estructural en la revisión local

La sección «Configurar el modelo» del servicio de revisión permite importar JSON en borrador, consultar su cadena, guardar una revisión completa y registrar aprobación propia de configuración. Usa las mismas sesiones locales, controles de Host/Origin y límite JSON del servicio existente. Ningún botón de esta sección llama a ETABS.

La configuración debe citar una versión geométrica real del expediente y sus huellas exactas. El ejemplo con hashes cero es una plantilla de software y no puede importarse como configuración válida de otro caso. Primero registrar y revisar geometría; luego completar parámetros, fuentes e hipótesis y vincular sus referencias. Los ausentes permanecen declarados y bloquean la aprobación.

La aprobación exige datos completos, geometría aprobada vigente, revisor/fecha/motivo/alcance, JSON sin cambios pendientes y declaración explícita. Una configuración ya aprobada admite revisión nueva en borrador, sin heredar aprobación. Revisor y competencia son declaraciones. La aprobación no se transfiere al EDB generado ni al informe.

API interna:

- GET /api/configuraciones?caso=... y /api/configuracion?caso=...&version=...
- POST /api/configuracion/importar, /revisar y /aprobar, con token de sesión, Origin local y huellas exactas del expediente/configuración.
- Los cuerpos no aceptan rutas del sistema; el JSON se registra dentro del expediente. Se rechazan evidencia alterada, huellas ajenas, campos desconocidos y aprobación sin confirmación.

La interfaz es un editor del contrato completo, no una deducción automática de cargas/materiales. Tras actualizar código hay que reiniciar el servicio y recargar la página para cargar configuracion.js. Las instancias ya abiertas no recargan Python automáticamente.

Verificaciones: cuatro pruebas HTTP nuevas más las 24 de revisión existente; ocho estados del frontend comprobados con `node tests/configuracion_html_check.cjs` y sintaxis JS verificada. El 17 de octubre se reinició el servicio actualizado en loopback y se comprobó en navegador real: consulta de configuración borrador, cambio de parámetro sintético, revisión nueva y aprobación explícita propia. Se conservó la versión anterior y se deshabilitó aprobar de nuevo. Evidencia en tmp/configuracion_web_verificada.png; todas las identidades y parámetros de ese ensayo son sintéticos, sin revisión profesional de obra ni ejecución ETABS.
