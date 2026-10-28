# Análisis deliberado desde un modelo revisado

`python -m draft2model analizar-etabs --raiz RUTA --caso CASO --aprobacion ID --trabajo CARPETA` prepara una solicitud y una copia nueva del EDB aprobado, sin contactar ETABS. `--ejecutar` confirma el análisis real. `--timeout` limita la espera del puente; no garantiza que el servidor COM haya terminado. Compartir `--bloqueo` entre todos los clientes de la misma operación/motor.

## Comportamiento

Requiere aprobación propia vigente de REVISION_MODELO.md y coincidencia del modo real/doble. Recomprueba origen, aprobación, EDB copiado y solicitud inmediatamente antes de lanzar y al validar la salida. Todo ocurre bajo la misma exclusión.

El puente crea una instancia ETABS nueva, identifica su PID y oculta únicamente esa instancia. Abre otra copia de trabajo para conservar intacta la entrada revisada. Así no presupone equivalencia de la ruta temporal .$et de una sesión anterior y no reemplaza un modelo activo del usuario.

Desactiva todos los casos, activa únicamente los declarados en configuración, ejecuta RunAnalysis y exige estado 4 de todos los seleccionados. Guarda un EDB nuevo y devuelve versión, PID, ruta reportada por ETABS, estados y huella. El cliente verifica archivo/huella/estados, vuelve a comprobar el origen y conserva `aceptacion_analisis.json`. No aprueba resultados ni informe; un estado de caso completo tampoco certifica estabilidad o calidad del modelo. Revisar advertencias/logs del solver y los resultados en el siguiente paso.

## Interrupción y recuperación

Antes de lanzar se escribe `<bloqueo>.incierto.json`. Si el proceso termina abruptamente, falla o la salida no corresponde, se conserva ese marcador junto con `analisis_no_aceptado.json`, registros y traza del puente. Ninguna nueva operación mutante que comparta el bloqueo puede continuar hasta diagnosticar el motor y registrar recuperación explícita. No borrar el marcador ni reintentar automáticamente. La instancia nueva permanece disponible para inspección; un timeout del proceso cliente no demuestra que ETABS haya detenido el cálculo.

## Evidencia actual y pendientes

Cinco pruebas con transporte Python fabricado cubren preparación sin proceso, salida correcta sin aprobar resultados, cambio de origen antes/durante, estado incompleto, terminación abrupta y alteración de la solicitud en memoria. No contactan ETABS. Sintaxis PowerShell y firmas RunAnalysis/GetCaseStatus/SetRunCaseFlag/GetNameList/Hide contrastadas contra la DLL instalada mediante lectura de metadatos. Se explicitó el argumento opcional de LoadCases.GetNameList para evitar el fallo de resolución de sobrecarga de PowerShell.

Ensayo posterior: modelo sintético revisado mediante 55 controles y coordenadas, análisis real EST y lectura de tablas, con verificación de estado4 después de reabrir. Ver ENSAYO_ETABS_ANALISIS.md. Se guarda primero con nombre definitivo y, tras calcular, con nombre vacío (modelo actual); un Save As posterior perdió disponibilidad de resultados en los ensayos previos y esas corridas se rechazaron. El EDB no debe separarse de su paquete de resultados sin comprobar estados. No se afirma convergencia de proyectos reales ni validez de ingeniería. La construcción modal/espectral está encargada a Claude; su entrega e integración siguen pendientes.
