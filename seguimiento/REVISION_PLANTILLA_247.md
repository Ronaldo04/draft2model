# Revisión focal de creación de plantilla ETABS - 247

Fecha: 2026-10-22. Solo lectura. Snapshot revisado: `tmp/revision_codex_246/scripts/crear_plantilla_etabs_caso.ps1` (56 líneas), SHA-256 `3D4C9A6C1EB04E854D6ADD000912F9261D3022436C63D33570D2CFA731848ACF`. Coincide byte a byte con el script actual en `scripts/`. No se revisan suite/manifiestos; no se ejecutó el script ni ETABS, GUI o red.

## Resultado del recibo real

Se leyó `data/private/pueblo-libre-002/plantillas/creacion_plantilla.json` (SHA-256 `8523E6C8A14FCBB2736F520C45CB5AAC063A33658F43408C4A1A8D63232C806E`). Su ruta template resuelve al EDB existente, de **104030 bytes**. Huella calculada ahora del EDB:

`e4759527ea4acd7af2f217bbdbf6c32003743d1171265f70ac5965c6133273e2`

**Coincide íntegramente con el SHA del recibo.** No se detectó alteración del EDB respecto de lo registrado.

El recibo declara caso pueblo-libre-002, synthetic_test=false, ETABS21.1.0, unidades kN_m_C, creación de 00:18:39 a 00:19:15 UTC del22 de octubre (19:18–19:19 hora Lima del21). Antes: PIDs6988,23928,38168; nuevo PID10072; remaining_preexisting conserva exactamente los tres previos; owned_instance_closed=true; status=created. Estos datos son coherentes con la rama feliz del script. La huella comprueba identidad de archivo, **no que el EDB sea vacío ni las unidades/contenido interno**, que no se abrieron en esta revisión.

## Hallazgos concretos

### P2 - Un fallo de cierre puede terminar con estado created y código0 (líneas39–43,56)

Tras Save/GetVersion, status se fija a created antes de ApplicationExit. Si ApplicationExit devuelve código distinto de0 o lanza excepción, solo cambia owned_instance_closed o añade close_error; status conserva created. Si el EDB sigue siendo legible, el script escribe el recibo y termina sin exit1. Por tanto la ejecución puede anunciar creación satisfactoria aunque deje abierta la instancia propia, contradiciendo el contrato de cierre que declara el comentario inicial.

Corrección mínima a cargo del dueño: separar creación de archivo de éxito completo; propagar fallo de cierre a resultado/código de salida y registrar el código real de ApplicationExit. Evitar que la falta de cierre desaparezca detrás de status=created. Confirmar desaparición del proceso propio si se declara cerrado, sin cerrar otros procesos.

El recibo real trae owned_instance_closed=true; **este defecto no demuestra que el cierre haya fallado en la ejecución conservada**. La afirmación actual de cierre proviene del retorno0 de API, no de comprobar que PID10072 ya no exista.

### P2 - Arranque parcial o identificación ambigua dejan la instancia nueva sin intento de limpieza (líneas20–25,41)

El cierre solo se intenta si report.process_id ya fue asignado. Si ApplicationStart falla después de producir una instancia, si Get-Process falla, o si la diferencia de procesos devuelve0 o más de1, el catch registra error pero process_id queda sin asignar; no se entra al bloque ApplicationExit aunque created ya exista.

La rama ambigua **sí protege el modelo** al detenerse antes de InitializeNewModel/NewBlank/Save. Además no mata PIDs ni intenta adivinar cuál cerrar, lo cual evita tocar una instancia ajena. El defecto es que esa protección no viene acompañada de una salida de limpieza segura para el objeto creado ni de un estado explícito de instancia huérfana. Resolver propiedad/limpieza mediante identidad verificable del objeto nuevo, y reportar imposibilidad de cierre cuando no se pueda resolver, sin cerrar por diferencia de PIDs a ciegas.

### P2 - Errores de hash o escritura del recibo quedan fuera del registro estructurado (líneas44–54)

OpenRead/ComputeHash y Open(CreateNew)/Write ocurren fuera del try/catch principal. Un EDB no legible, un directorio de Registro inexistente o sin permisos, o un error de escritura hacen abortar después de crear el archivo y posiblemente cerrar la instancia, sin emitir el JSON final que describa archivo parcial/fallo de auditoría. El directorio del EDB se valida antes de arrancar (línea10), pero el del recibo no. Para un flujo reproducible puede quedar un EDB existente que impida reintentar con los mismos destinos y sin recibo de creación.

Validar ambos destinos antes del arranque y envolver las fases posteriores para conservar un diagnóstico estructurado/fallback explícito. No borrar ni sobrescribir automáticamente un EDB ya guardado para ocultar ese fallo. CreateNew evita sobreescribir un recibo existente, pero no garantiza un recibo completo ante fallo durante Write.

## Instancia propia y límites de la evidencia

- El script crea `ETABSv1.Helper`, llama `CreateObjectProgID('CSI.ETABS.API.ETABSObject')` y mantiene el resultado en created. **No contiene GetObject, GetActiveObject ni adjunción a una instancia abierta.** Todas las llamadas al modelo se hacen a created.SapModel; ApplicationExit se hace sobre ese mismo objeto, no sobre un objeto obtenido de los PIDs previos. No hay Stop-Process ni comandos que cierren procesos ajenos.
- La diferencia antes/después exige exactamente un nuevo proceso antes de operar el modelo. Es una salvaguarda útil, pero no enlaza por sí misma report.process_id con created. Una apertura/cierre concurrente externa vuelve ambiguo ese registro; no usarlo como prueba independiente de pertenencia.
- GetVersion sí comprueba el código de retorno; InitializeNewModel, NewBlank, Hide, Save y ApplicationStart también. No hay llamadas Analyze/RunAnalysis/LoadCases en el script. `analysis_executed=false` concuerda con el código inspeccionado.
- `existing_instances_modified=false` se inicializa como afirmación y no se mide; `remaining_preexisting` confirma solamente supervivencia de PIDs. El mismo conjunto de PIDs no demuestra ausencia de modificaciones a los modelos. La ausencia de adjunción y el uso del objeto creado respaldan la intención de aislamiento; el recibo no constituye una auditoría de los modelos preexistentes.
- `purpose=empty template`, `case_id` y `synthetic_test=false` son etiquetas declaradas por el script/parámetro. NewBlank respalda la intención de plantilla vacía. No se validó contenido del EDB ni su asociación interna al caso sin abrirlo.
- Se exige Destino absoluto y extensión .edb; se comprueban no existencia al inicio y justo antes de Save, y el recibo usa CreateNew. La ausencia de sobrescritura del EDB no es atómica frente a otro escritor entre Test-Path y File.Save; la revisión no observó tal carrera. No se encontró sobrescritura efectiva en los artefactos conservados.

## Cierre de la revisión

**Recibo real y SHA del EDB consistentes; código de creación orientado a instancia nueva y sin análisis.** Quedan tres defectos de manejo de fallos/cierre/reportado que deben corregirse antes de sostener que el script garantiza limpieza y recibo completo en todos los resultados. Esta revisión no invalida la plantilla conservada por inferencia ni certifica su contenido interno.
