# Construcción verificada del modelo

La puerta integrada es `EjecutorVerificado` de draft2model.ejecucion_modelo. Reutiliza el despacho real de ejecutor_etabs y añade revalidación del expediente/configuración/plan antes y después, validación final y registro de incertidumbre dentro de una misma exclusión. No ejecuta análisis ni aprueba automáticamente el modelo.

Preparar: `python -m draft2model construir-etabs --raiz data/private --configuracion config.json --plan plan.json --copia RUTA_COPIA_EDB --trabajo tmp/etabs`. Añadir --ejecutar aplica realmente el plan a esa copia **ya abierta** en ETABS; --id-proceso selecciona la instancia. La copia debe coincidir con la huella de plantilla del plan y el destino de guardado ser nuevo. Compartir --bloqueo entre todos los clientes de esa instancia. La ejecución respeta las políticas del equipo, sin Bypass.

Preparar una solicitud no contacta ETABS. La aplicación requiere plan idéntico al regenerado desde configuración aprobada y evidencia geométrica vigente. Se admiten casos estáticos lineales, modal Eigen y espectro tabulado con las opciones explícitas de OPERACIONES_ETABS.md. La construcción dinámica sintética de 69 operaciones y su persistencia fueron comprobadas en ETABS 21.1; ver ENSAYO_ETABS_DINAMICO.md. No se descartan silenciosamente requisitos para obtener un modelo aparente.

Un marcador persistente se crea antes de lanzar el proceso y solo se archiva tras validar la salida y volver a comprobar las entradas. Por tanto, una interrupción abrupta del cliente o un éxito falso no permiten otro cliente mutante sin recuperación explícita. El diagnóstico permanece permitido. La liberación del lock por muerte de un proceso no demuestra que el servidor COM haya terminado.

La prueba de aceptación de esta capa es `aceptacion_integracion.json`; `resultado_ejecucion.json` es evidencia de la capa inferior y puede coexistir con `revision_integracion_fallida.json` si cambió el origen al terminar. Los consumidores no deben aceptar un registro parcial. La aceptación conserva origen, huella del plan, archivo guardado y SHA256. No autentica al revisor ni acredita seguridad estructural.

Regresiones verificadas con un transporte de prueba: original alterado entre preparación y ejecución no lanza proceso; evidencia modificada durante proceso se rechaza; éxito falso conserva incertidumbre; salida abrupta sin traza conserva bloqueo persistente; otro proceso no puede adquirir el lock mientras se valida el resultado final. Estos cinco ensayos no contactan ETABS y no prueban el comportamiento COM real.

La revisión de la primera entrega se conserva en REVISION_EJECUTOR_CODEX.md. Se integró una capa separada para preservar el reparto de archivos con Claude mientras terminaba su entrega. Toda integración de producto utiliza esta puerta de construcción; las APIs inferiores permanecen como transporte/driver.
