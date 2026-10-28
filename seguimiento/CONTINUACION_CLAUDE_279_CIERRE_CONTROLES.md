# Continuación279: cerrar demora de controles y recorrido real

Codex retomó con99% de ventana tras límite. Estado: revisión propia de extremos `seguimiento/REVISION_EXTREMOS_278.json` pasa:45vigas, offsets6.353m, peso6.86124kN, neto24.25572kN vs tabla24.2557kN. Se conserva contraste independiente fallido/residuo; no repetir esa lectura ni análisis.

39028 sigue vivo con creación22oct21:24:50.286587-05:00 y CPU creciente; no reiniciarlo solo por tiempo ni matar instancias ajenas. GUI reporta12h44 de pared (puede incluir suspensión del equipo; no atribuir todo a CPU). Su lectura web4b6119a8 está aceptada y revisada en275. Falta publicar controles, reglas e informe.

Tu siguiente tarea sustancial, además de continuar la cadena pendiente, es localizar y corregir el coste repetido que impide un flujo utilizable. Mantienes producto/tests/runner; Codex solo QA y seguimiento. No dupliques su servidor.

## Evidencia de QA actual

Codex servidor propio sesión17813, puerto18276, runtime INMUTABLE `tmp/runtime_qa_276`, raíz `tmp/anexo_reubicado_268`. No tocar estos destinos. La UI terminó mostrando3modelos y1resultado; resultado697bb37e9ce64f90ba1ef3e25733c8cc abre y muestra13indicadores. Tras seleccionarlo, informeAnalisis/panelAnalisis siguen sin opciones mientras se consultan evidencias; no se recargó ni se ejecutó ETABS. Sin errores de consola observados. Esto no demuestra todavía fallo terminal, pero sí requiere medir carga/revalidación y esperas por locks.

## Entregables/criterios

1. Identificar qué operación exacta mantiene39028 pendiente (estado de trabajo real, fase y función/ruta relevante); separar tiempo de CPU, esperas y suspensión. Usar diagnóstico permitido de procesos propios/artefactos. No alterar evidencia ni reiniciar por timeout de observación.
2. Medir una reproducción focal de los cálculos/validaciones repetidos. Revisar duplicación de preparación pura por solicitudes concurrentes de la misma clave y eventual expulsión de claves. Corregir el cuello demostrado, sin saltarse revalidación de archivos, aprobaciones, hashEDB o vínculos. Si agrupas cálculos concurrentes, solo funciones puras JSON con clave completa, copias independientes, propagación correcta de errores, claves distintas independientes y espera acotada/recuperable; pruebas pertinentes de carreras y mutación. No caché de aceptaciones por mtime ni resultados de verificadores de evidencia.
3. Finalizar controles/reglas/informe/panel del caso vigente. Si la cadena vieja termina, inspeccionar sus resultados; no mezclar su huella con fuentes nuevas. Conservar incertidumbres normativas y desfase original.
4. Informar archivos/hashes, tiempos observados y límites, marcador al terminar. No repetir suites ya revisadas ni consultas nativas resueltas. No APIs; no proyectos2/3. Plan de cierre estable y paquete final sigue siendo obligatorio.

No hay candidato nuevo de concurrencia de Codex: solo se inspeccionó `cache_malla_pura.py`. No asumir implementación existente. Puedes resolver decisiones técnicas ordinarias dentro de este alcance sin pedir aprobación rutinaria.

## Hallazgo focal adicional reproducido por Codex

`seguimiento/HALLAZGO_CONCILIACION_279.json`: `conciliar_extremos_vigas` admite una fila duplicada y offsets negativos. En fixture B1 duplicada descuenta dos veces; OffsetI=-1 admite peso excluido negativo. Rechazar identificadores repetidos y longitudes negativas con ErrorLibroMasa, añadir regresiones pertinentes y conservar libro original. No invalida la tabla íntegra revisada278. Corregir también la frase de cabecera de libro_masa.py que asegura que ETABS tampoco descuenta solapes: contradice el caso observado de extremos de vigas. Mantener explícita la distinción entre libro independiente y conciliación con datos nativos.
