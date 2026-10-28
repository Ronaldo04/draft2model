# Continuación270 — mostrar listados independientes sin esperar modelos históricos

Continúa268 y la misma cadena viva. Este encargo es independiente del núcleo numérico y no exige nuevas llamadas remotas ni reiniciar ETABS.

Codex observa la UI REAL del runtime fijo269 con el expediente reubicado, servidor propio18269. Al seleccionar el caso, `resultados.js::listing` espera `Promise.all` de `/api/modelos` y `/api/resultados` antes de mostrar cualquiera: los resultados quedan ocultos mientras se revalidan todos los modelos históricos. La UI conserva «Sin modelos»/«Sin resultados» y «Selecciona una versión» durante la espera, lo que aparenta ausencia de datos. No se declara fallo de las respuestas pendientes ni aceleración del solver.

## Implementación revisable

`tmp/candidato_listados_270/resultados.js`, preparado desde el hash de `ORIGEN.json`, modifica SOLO la función listing. Mantiene peticiones paralelas, pero cada columna publica su respuesta sin depender de la otra. Muestra consulta en curso y aísla errores; conserva guardas de caso/contexto/ticket, vigencia y selección preferida. No evita ni rebaja revalidaciones del backend. **No copies el archivo entero sobre cambios tuyos posteriores**: revisar/rebasar el bloque sobre el archivo vigente.

Propiedad propuesta: Claude integra `draft2model/revision_web/resultados.js` y sus pruebas normales. Codex conserva candidato, prueba y QA en seguimiento/tmp. No hay cambios de Codex al producto.

## Evidencia y aceptación

`node seguimiento/test_listados_270.cjs` pasa: resultados visibles antes de que resuelva modelos; error de modelos no borra resultados; respuestas/errores de caso viejo no reemplazan columnas vigentes; pruebas EXISTENTES de éxito/error tardío y descarga del expediente vigente, ejecutadas contra candidato, pasan. Son pruebas con DOM/HTTP simulados, no piloto.

Integrar y portar pruebas de esos casos, sin omitir las regresiones existentes. Verificar errores independientes, selección preferida de modelo/resultado, cambio de caso y descarga correcta. La aceptación exige luego QA visual en caso real. El candidato no deduplica cálculos simultáneos de malla ni resuelve por sí solo latencia de backend; no afirmar lo contrario.

## Resultados de Codex que no se deben repetir

- Reubicación269 terminó0: análisis aceptado y vínculo de resultado normalizado comprobados, expediente/runtime intactos. `REUBICACION_CASO_269.json`:687,944s y127,842s;1miss/2hits de malla. No nueva lectura nativa ni reconstrucción.
- Cache producto12pruebasOK; regresión malla2468/8OK;2adversariales sobre archivos alterados con cache calienteOK. `REVISION_CACHE_PRODUCTO_268.json`, `REGRESION_MALLA_CACHE_269.json`, `REVISION_CACHE_EVIDENCIA_269.json`.
- P por pisos ejercitado en destinos propios:4792,877604kN; ausencia de lectura produce abstención (`REVISION_REGLAS_P_269.json`).
- La integral de peso desde geometría/propiedades/cargas de la relectura N_mm_C reproduce EXACTAMENTE el libro (salvo redondeo1e-12), así que no se demostró aún la causa del desfase6,868112kN frente aCM: `DIAGNOSTICO_PESO_RELECTURA_268.json`. Mantener diferencia y tolerancia visibles.
- Paquete268 NO publicable por edición concurrente de lectura_analisis.py durante captura; ERROR conservado. Congelar el paquete final al terminar cambios.

Al terminar, sigue panel/informes/guía/paquete y el resto de268. Dejar marcador final con hashes y pruebas, sin declarar cierre completo mientras permanezca un criterio abierto de `seguimiento/CRITERIOS_CIERRE_269.json`.
