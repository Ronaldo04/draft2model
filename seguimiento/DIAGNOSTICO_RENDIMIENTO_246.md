# Diagnóstico de rendimiento 246

Fecha: 2026-10-22. Estado: implementación estable y pruebas focales completadas; reserva aceptada por Claude y todavía activa, pendiente revisión de root.

## Evidencia

INFORME_09.md §6 y tmp/ruta201/muros/diag_malla.log: geometría 7c84de15, 2083 hosts, 4182 triángulos, 32 nodos derivados, 0 subdivisiones, 2133,1 s. No se volvió a ejecutar ese benchmark.

Cadena inspeccionada:

- preparar_malla valida una vez y genera N particiones.
- particionar_superficie serializa, copia y valida toda la geometría por host.
- compatibilizar_particiones valida toda la geometría y reproduce N particiones, comparando documentos completos.
- triangular_compatibilidad reproduce compatibilidad, que valida otra vez y reproduce otras N particiones.

Total deducido: 3N + 3 validaciones completas; para N=2083: 6252. Baseline sintético acotado confirma 6 llamadas para un host y 9 para dos. Mediciones y resultados completos en tmp/revision_rendimiento_246/baseline_medidas.json y *_baseline.json.

## Plan y dependencias

No resulta apropiado parchear globalmente funciones o validadores desde malla_preparacion: interferiría con invocaciones concurrentes. Se requiere ampliar alcance a particion_superficies.py, compatibilidad_particiones.py y triangulacion_particiones.py además de malla_preparacion.py y tests/test_malla_rendimiento_246.py.

Propuesta: contexto privado local por invocación en particion_superficies; conserva resultado completo de una validación y bytes canónicos de la fuente. Toda reutilización exige igualdad de contenido canónico actual, no mera identidad. Propagación explícita por keyword privado en la cadena. Sin caché global ni caché permanente por identidad.

Las particiones se siguen calculando íntegramente y se siguen reproduciendo/comparando íntegramente contra la fuente. También se reproduce y compara la compatibilidad. No cambia aritmética, tolerancias, controles de áreas/topología/orientación, formatos ni huellas. Las funciones públicas sin contexto mantienen el recorrido previo de validación.

Cotejar de nuevo la fuente al publicar evita aceptar una mutación posterior al último uso del contexto. El contexto no sale en el resultado y no se reutiliza en una segunda preparación.

## Aceptación prevista

- Igualdad de todo el documento de preparación, incluidas huellas, contra baseline previo y ruta sin contexto, en seis escenarios sintéticos: horizontal con varios huecos, vertical, inclinado, hosts conectados con frame, corte vertical y conectados con corte.
- Igual rechazo de geometría inválida y particiones/compatibilidad manipuladas aunque se recalcule su hash.
- Mutación de geometría durante preparación rechazada; segunda invocación tras cambio valida de nuevo y no devuelve caché obsoleta.
- Conteo instrumentado de validaciones completas independiente del número de hosts: una por preparación válida.
- Regresión acotada de particiones, compatibilidad, triangulación y preparación; sin API, ETABS, red ni suite amplia repetida.

## Implementación y verificación final

Reserva aceptada por Claude en seguimiento/ACUERDO_RESERVA_246.json. Los cuatro módulos se cotejaron contra tmp/c211/fuentes antes de editar: coincidencia SHA256 completa (huellas_antes.json). Los cinco archivos de producto/prueba se declararon estables a root; la reserva NO se liberó.

Implementación: _ContextoGeometria valida su propia copia y conserva bytes canónicos, SHA e índices normalizados de superficies, vértices y huecos. El contexto se crea en preparar_malla y se pasa explícitamente por keyword privado. Cada consumo compara la fuente íntegra; las particiones y compatibilidad siguen reproduciéndose y comparándose completas. Hay guardas después de triangular y antes de devolver. Las funciones públicas sin contexto conservan la ruta previa. No se guarda contexto entre llamadas ni en el documento resultante.

Resultados:

- Comparación íntegra contra los SIETE JSON guardados antes de editar: igualdad total, incluidas todas las huellas.
- 48 hosts / 576 triángulos: 147 → 1 validación completa; 4,260 → 1,188 s (~3,59×) en una medición acotada orientativa. No es extrapolación del caso real.
- 8 pruebas nuevas OK en 9,544 s: equivalencia completa, contador, inválidos, mutaciones durante partición y después de triangulación (incluido NaN), huellas recalculadas sobre partición/compatibilidad alteradas, ejecuciones sucesivas y preparaciones concurrentes independientes.
- 20 pruebas de partición/compatibilidad/triangulación OK en 3,036 s.
- 8 pruebas de integración de configuración/plan OK en 21,004 s. La primera ejecución encontró permisos del temporal Windows; se corrigió el entorno del runner con tempfile.tempdir en tmp/revision_rendimiento_246 y se completó sin cambiar producto por esa causa.

Evidencia: tmp/revision_rendimiento_246/medidas_despues.json, pruebas_nuevas.log, integracion.log, huellas_despues.json y cambios.diff.

Limitación explícita: la comprobación canónica de toda la fuente por consumo sigue siendo O(N × tamaño_documento), O(N²) si el documento crece con hosts. Se conserva deliberadamente para detectar mutación antes de reutilizar datos validados; sustituye la serialización de origen que ya se hacía por host. El perfil acotado de 48 hosts muestra que la aritmética racional/verificación de celdas domina ahora: todas las llamadas JSON juntas consumen 0,429 s de 6,018 s bajo instrumentación (tiempos perfilados, distintos del benchmark sin profiler). No se afirma eliminación de toda complejidad cuadrática ni un tiempo previsto para los 2083 hosts reales.

No se ejecutó la malla real, suite general, API, ETABS ni CU. Contratos, tolerancias y huellas de salida sin cambios. Pendiente revisión independiente de root y liberación coordinada de reserva.
