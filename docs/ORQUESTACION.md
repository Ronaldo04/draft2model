# Corridas persistentes y exclusión

`RegistroCorridas(raiz_privada)` en draft2model.orquestacion mantiene `corridas.sqlite3`: caso, etapa, estado, entradas/salidas con SHA256, fechas UTC y motivos. Cada entrada/salida debe ser un archivo existente dentro del caso. El registro no ejecuta comandos ni ETABS: los consumidores deben llamar crear/iniciar/finalizar/fallar alrededor de su operación y comprobar vigencia antes de aceptar resultados.

Un índice único transaccional permite una sola corrida en ejecución en esta base compartida, incluso entre procesos. El alcance de exclusión es la raíz privada: no coordina dos bases distintas ni una instancia ETABS operada manualmente. Preparar no es ejecutar. Un cambio en las entradas/salidas hace que consultar devuelva vigente=false sin borrar historial. Las salidas no pueden reemplazar entradas de la misma corrida.

No hay reintentos automáticos. Después de una interrupción, `recuperar(..., motor_detenido_declarado=True, motivo=...)` registra interrumpida y libera el turno solo tras comprobación externa del motor; no vuelve a lanzar la operación. Una declaración no comprueba por sí misma que ETABS haya terminado. Mientras no se revise, el turno permanece ocupado para evitar duplicar análisis. El registro conserva huellas, no copias ni firmas inviolables; los módulos consumidores preservan sus propias versiones. Entre comprobación y operación externa hay una posible edición concurrente: volver a comprobar al terminar.

Pruebas incluyen dos clientes concurrentes, persistencia al reabrir, entradas modificadas, recuperación explícita y rechazo de rutas/salidas inválidas. La infraestructura aún debe enlazarse al adaptador y al flujo integral; no equivale a una corrida estructural real.
