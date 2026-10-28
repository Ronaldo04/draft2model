# Auditoría final de guía y cobertura — Claude

Contexto: cierre_desarrollo revisado por Codex146 (27 hashes correctos). QA143 y145 comprobaron registro de controles e informe desde navegador con datos sintéticos; JSON/PDF conservan sin_datos y faltante SOLVER. Copia limpia146 corre por Codex en exec99501 sobre snapshot; no repetirla ni modificar fuentes. Ensayo real API/planos/ETABS aún pendiente; comparación manual aplazada por usuario. Clave/modelo/presupuesto consultados al usuario, nunca leer/divulgar secretos.

Objetivo sustancial independiente: auditar que una persona pueda configurar, arrancar y recorrer la versión entregada con la documentación vigente, y que sus afirmaciones de soporte correspondan al código y a los criterios de cierre. Detectar contradicciones accionables, no añadir recomendaciones genéricas ni certificar cumplimiento por tests.

Leer docs/GUIA_REPRODUCIBLE.md, README.md, docs/CIERRE_DESARROLLO.md, docs/MATRIZ_CIERRE_VIGENTE.md, docs/PLAN_ENSAYO_REFERENCIA.md y módulos necesarios. Contrastar comandos/flags/rutas/recursos/orden de selección de la UI y separación entre configuración de ejemplo, transporte doble y motor real. Comprobar qué pasos exactos faltan para los planos de referencia y qué representaciones están realmente disponibles (sin inferir materiales, cargas ni dimensiones). Revisar también documentación de instalación/Node y credencial sin valores secretos.

Archivos permitidos para escribir SOLO:
- seguimiento/AUDITORIA_GUIA_FINAL_CLAUDE.md
- seguimiento/ENTREGA_CLAUDE_AUDITORIA_GUIA_FINAL.json (última escritura)
No editar otros archivos ni lanzar suites, red, API, ETABS, instalaciones, CU, cambios de catálogo o tests.json. No tocar data/private ni tmp/c146. Puede usarse lectura y --help si aclara una discrepancia; no repetir comprobaciones ya acreditadas.

Entregable: informe breve con ruta/línea y evidencia para cada fallo real, efecto en la reproducción y corrección concreta propuesta. Si no hay hallazgos en una parte, declarar la cobertura exacta y su límite. Separar errores documentales, código faltante fundado y decisiones/datos externos pendientes. No rebajar el alcance para declarar completo. Inventariar todos los requisitos materiales pendientes con responsable y evidencia que los cerraría. Hasta10líneas finales en conversación.

Marcador: {"tarea":"auditoria_guia_final","estado":"entregado","archivos":{"seguimiento/AUDITORIA_GUIA_FINAL_CLAUDE.md":"SHA256"},"hallazgos":[],"limites":[],"conflictos":[]}.
La auditoría no prueba ejecución real. Codex revisará e integrará correcciones después de la copia limpia. No modificar código en paralelo.
