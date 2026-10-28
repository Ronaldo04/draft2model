# 05 — instalación limpia, regresiones y guía reproducible

Objetivo: un tercero puede instalar, configurar, arrancar y recorrer el proyecto desde la entrega actual con requisitos explícitos. No usar limpias antiguas146/148 como evidencia del árbol actual.

Revisa requirements/lock/runtimes/configuración/arranque y documentación. Prueba copia limpia usando scripts/verificar_copia_limpia.py y runtime existente cuando sea aplicable, excluyendo claves/privados/EDBusuario/tmp gigantes y sin descargar/instalar software no autorizado. No quitar pruebas para obtener verde. Completa suite pertinente UNA vez por hito estable, registra errores/omisiones/entorno y corrige causas verificables. PS -File bloqueado por aislamiento no acredita fallo de código ni autorizaBypass: usar entorno permitido o registrar limitación. Rutas>260 se detectan antes de abrir motor; explicar raíz corta sin desactivar guardas.

Guía final de configuración/uso con comandos exactos, Google/OpenAI multimodal opcional solo planos, APIlocalETABS/licencia, cómo declarar/salvar revisiones, elegir proyecto con/sinlíquidos, ejecutar y recuperar fallos sin reenviar, consultar fuentes/resultados/informe. Incluir distinción simulaciones/nativo/piloto y límites materiales reales. QA visual de recorridos nuevos y capturas acotadas; evitar sondeo continuo y pruebas redundantes. Pruebas sensibles no deben imprimir credenciales.

Aceptación: instalación/configuración/arranque demostrados desde copia limpia actual; comandos reproducibles y logs; regresiones verdes o bloqueos concretos sin éxito fingido. Si piloto04 quedó bloqueado por dato externo, verificar todavía toda infraestructura posible y conservarlo como pendiente de cierre. Entrega y continuar06.
