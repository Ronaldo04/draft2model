# Operaciones ETABS desde la CLI principal

`python -m draft2model etabs --trabajo tmp/etabs diagnosticar` prepara una solicitud, sin iniciar el puente. Añadir `--ejecutar` al subcomando llama al puente real bajo las políticas del equipo. Windows PowerShell 5.1 y ETABS deben estar disponibles en el mismo entorno que el proceso; no se cambian políticas para acceder a la instancia del host.

Subcomandos: diagnosticar, abrir-copia, leer-tablas, guardar-como y recuperar. Consultar `python -m draft2model etabs --help` y la ayuda de cada subcomando. Las rutas de modelo introducidas se normalizan a absolutas antes de enviar al puente; las rutas de transporte permanecen correctas aunque el llamador indique trabajo relativo.

- abrir-copia requiere --plantilla, --sha256 y --destino (carpeta nueva). Puede copiar archivos aun sin --ejecutar, pero solo llama a ETABS al añadir esa opción. Instancia nueva por defecto; usar activa requiere además --reemplazar-modelo-activo porque podría descartar cambios no guardados.
- leer-tablas requiere --modelo, uno o más --tabla y casos/combinaciones explícitos con --caso/--combinacion. Solo lee análisis terminados, no calcula.
- guardar-como requiere --modelo y --destino EDB nuevo. No reemplaza archivos existentes.
- recuperar exige --motor-inactivo, --revisor y --motivo después de comprobar externamente que la operación terminó. Conserva la evidencia del timeout; no detiene ni inspecciona ETABS por sí solo.

Todos los clientes que operen una misma instancia deben compartir --bloqueo; si se omite, se usa el archivo del directorio de trabajo. Usar carpetas de trabajo distintas con bloqueos diferentes no garantiza exclusión mutua sobre la misma instancia. No se ejecuta automáticamente ninguna solicitud preparada.

Códigos: 0 correcto, 1 solicitud, 2 evidencia, 3 puente/API, 4 timeout y 5 bloqueo. Ver ADAPTADOR_ETABS.md para contratos y límites. Esta CLI no construye ni analiza un modelo estructural.
