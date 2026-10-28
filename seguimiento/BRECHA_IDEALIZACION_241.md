# Idealización de pisos y superficies auxiliares — revisión241

Revisión estática independiente de snapshot08 congelado `tmp/revision_codex_236`. No afirma que el piloto haya usado una opción incorrecta: todavía no existe modelo real aceptado. Sin API/ETABS ni cambios de producto.

## Evidencia

- Texto oficial E030/RM183-2026 conservado en `seguimiento/normativa_229/E030_RM183_2026.txt`, artículo30.8: excluir rigidez fuera del plano de **losas de piso**; excepción detallada para alas de vigasT/L. Art30.3/30.4 exige justificar diafragmas rígidos y considerar flexibilidad cuando no se satisfaga hipótesis. Art30.7 exige interacción de muros perpendiculares en sistemas de muros predominantes.
- `draft2model/operaciones_etabs.py`, snapshot236: `TIPOS_SHELL_LOSA` ofreceShellThin/ShellThick/Membrane. En la generación de secciones (~líneas754–759), **todas** las secciones `shell_losa_homogenea` y tiposaligerados reciben `opciones['tipo_shell_losa']` enSetSlab.ShellType. El contrato de opciones (~1005–1025) no admite selección por sección. Los planes0.4/0.5 reutilizan esta generación; declarar diferentes secciones/espesores no cambia esa única selección global.
- No se encontró transporte deSetModifiers para resolver la diferencia fuera del plano por propiedad. El aviso histórico `NO_SOPORTADO['tanque_agua']` ~383 todavía dice fondos/tapas noimplementados, mientras plan0.5 ya permite presiónsobre superficies declaradas. Debe conciliarse en documentación sin atribuir hidrodinámica implementada.

## Implicación que debe resolver integración

Un piso aligerado y el fondo/tapa de un depósito no son intercambiables por compartir etiqueta geométrica `losa`. Si el modelo del piloto requiere idealizaciones distintas, la opción global no puede expresarlas simultáneamente. ElegirMembranepara todos no acredita comportamiento de un fondo a carga normal; elegirShellThinpara todos no acredita exclusión de rigidez fuera del plano de pisos. Un eventual modelo separado y justificado es una alternativa técnica, pero debe ser explícito y reproducible; no usarlo para omitir el depósito del alcance.

## Aceptación propuesta para09

1. Declarar función estructural y elección explícita por sección o superficie, o documentar otra representación técnicamente equivalente con evidencia. La elección de la función no se deduce solo de que el polígono sea horizontal.
2. Si se amplía contrato/opciones, conservar compatibilidad de versiones y prohibir ambigüedades/desconocidos; transportar selección a plan, scripts y expectativas de relectura. Las propiedades de malla deben heredar la elección de su anfitrión.
3. Prueba focal con **piso y fondo simultáneos** que exijan elecciones diferentes: comprobar argumentos nativos, relectura y detección de cambio de tipo; una prueba de soloMembrane o soloShellThin no cubre la mezcla.
4. En el piloto, justificar diafragmas, escaleras/depósitos y masa/carga/presión sin duplicación. Mostrar no evaluado donde falte dato; no declarar cumplimiento universalE030por elegirMembrane.

Estas son restricciones de integración detectadas sobre08. Si09ya contiene una solución, aportar su evidencia y evitar implementar una segunda vía.
