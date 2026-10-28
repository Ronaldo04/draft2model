# Metodología de entrada: contraste solicitado por el usuario

Consulta del 23/10/2026. Referencia pública leída por navegador: https://share.gemini.google/shEhY7e9Vtgm (redirige a Gemini share341374c9a302). No se utilizó una API de modelos. Es una guía secundaria sobre un ejemplo, no una norma ni una validación independiente del sistema.

La secuencia general coincide: geometría y unidades → materiales/secciones → cargas y masa → sitio y parámetros sísmicos → modelo → análisis → comprobaciones. Draft2Model añade procedencia, versiones, faltantes y relectura del archivo ETABS.

## Cobertura observada del producto

- `draft2model/configuracion_normativa.py::aplicar` exige decisiones con valor, estado y fuente. Genera propiedades de materiales y espectro con citas oficiales; registra hipótesis y faltantes. No clasifica por sí mismo el suelo ni el sistema resistente.
- `normativa_e030.py` calcula parámetros seleccionados, valida dominios y registra citas. `normativa_rne.py` aporta propiedades y cargas seleccionadas. No equivalen a implementar todas las disposiciones de E.020/E.030/E.050/E.060/E.070.
- La propia aplicación deja irregularidades, cortante dinámico, derivas y diseño de elementos como no evaluados en la etapa de entrada. Suelo real no confirmado: se mantienen escenarios porque el usuario no dispone de EMS.
- Los ensayos del piloto y los sintéticos no prueban soporte de cualquier tipología. Los proyectos2 y3 continúan sin procesarse por instrucción del usuario.

La guía externa mezcla ediciones y deja alternativas ambiguas de clasificación (por ejemplo70%/80%). No importar sus tablas o recomendaciones de rigidez como reglas aprobadas. El corpus oficial y la implementación deben contrastarse por edición, artículo y aplicabilidad; ver `seguimiento/NORMATIVA_OFICIAL_229.md` y `docs/NORMATIVA_APLICADA.md`.

## Generalización y autonomía

Las correcciones de código/mallado deben ser generales, determinísticas y acompañadas de regresiones pertinentes. No introducir coordenadas o identificadores exclusivos del piloto como reparación del algoritmo. Las decisiones físicas o datos faltantes requieren un diagnóstico accionable y entrada del usuario; no inventarlos ni prometer reparación automática de cualquier caso. El resultado futuro deseado es resolver los casos soportados sin cambios de código y señalar de forma concreta los casos que no puede resolver. Eso todavía no está demostrado universalmente.

Este contraste no declara cierre ni cumplimiento normativo del piloto. Estado completo y criterios de aceptación: `docs/RETOMAR.md` y `seguimiento/CRITERIOS_CIERRE_269.json`.
