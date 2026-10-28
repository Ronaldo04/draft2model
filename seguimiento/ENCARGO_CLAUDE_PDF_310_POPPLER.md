# Encargo310 — Contraste y candidato para Poppler

Responsable: Claude. Codex ya revisó el marcador309 y sus hashes. La conclusión «no reproducido» se sostiene para MuPDF/Windows, pero no se acepta como cierre general: Codex observa prefijos incompletos en Poppler. No modificar309: es una entrega inmutable. La distribución308 sigue congelada.

## Reproducción nueva de Codex

- PDF original: el mismo09d3, SHA `ca4fc1432c509af1bc944f376e8f60f4a16f94fc3a8eff4e63b59ef2dbb5acf9`.
- Poppler está disponible, aunque no aparezca en tu PATH: `C:/Users/HP/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/poppler/Library/bin/pdftoppm.exe`. Versión observada:26.07.0. No instalar nada.
- Renders nuevos: `tmp/pdfs/revision_310/poppler-7.png` y `poppler-8.png`, a96dpi. Entrada solo lectura. Se observan enp7 los dos primeros bloques con comienzos «do:», «ula:» y «te de regla» en vez de «Estado:», «Fórmula:» y «Fuente de regla». Los bloques posteriores aparecen completos. Compruébalo objetivamente y visualmente; no asumir que la presencia de tinta equivale a texto correcto. Se emitieron otra vez avisos Symbol/ArialUnicode; no prueban por sí solos la causa.

## Objetivo y perímetro

Investigar la discrepancia y producir una corrección candidata mínima si se reproduce. Escribir **solo** en `seguimiento/claude_ruta/diagnostico_pdf_310/` y `seguimiento/claude_ruta/MARCADOR_PDF_310.json`. No editar producto, tests públicos, docs, paquetes, fuentes del caso, informes publicados,309 ni referencias humanas. Codex integra después.

1. Verificar PDF/versión de Poppler y comparar aisladamente p7/p8 con MuPDF/Windows. Conservar parámetros y evidencia. Si no reproduces, comparar exactamente los PNG de Codex, no declarar completa una línea solo por texto extraído o tinta en una caja.
2. Investigar mapeo de glifos/recursos/CFF y clipping. El hallazgo de CFF sin ROS es una hipótesis, no causa demostrada. Ensayar variantes aisladas si ayudan: sin deduplicación de recursos, fuentes TrueType cargadas explícitamente mediante Archive/@font-face o la alternativa mínima que justifique la evidencia. Una familia CSS por nombre sin cargar su archivo no garantiza cambiar la fuente de Story.
3. Las variantes se generan desde el HTML ya publicado o un mínimo; sin `_fuente` ni regenerar el expediente. Se pueden usar fuentes ya instaladas solo para diagnóstico: no redistribuir archivos de fuente con licencia desconocida. Documentar las necesidades de integración/licencia si la corrección depende de una fuente nueva. No descargar paquetes ni actualizar el entorno.
4. Comparar original/candidato en Poppler y MuPDF, y Windows cuando sea pertinente. Revisar visualmente prefijos, finales de línea, tablas y pies; conservar13indicadores,18comparaciones (8True/10False), unidades, hipótesis y masa NO COHERENTE. Sin cambiar tolerancias, reglas o datos. No declarar compatibilidad universal.
5. Entregar diagnóstico, candidato aislado o parche propuesto y comprobaciones reproducibles. No ejecutar suites globales ni empaquetar. No volcar HTML/JSON completos: extraer fragmentos y metadatos necesarios para ahorrar cuota.

Fuentes técnicas primarias de consulta si hacen falta: `https://pymupdf.readthedocs.io/en/latest/recipes-stories.html`, `https://github.com/pymupdf/PyMuPDF/issues/3083`, `https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/font-replacement/readme.md`. Son referencias de carga de fuentes; no constituyen prueba de la causa en este archivo.

Sin APIs/LLM externos, claves, credenciales, ETABS, nuevas lecturas de planos ni proyectos2/3. El usuario está preparando la referencia humana; no tocarla ni inventar métricas.

Última escritura: `MARCADOR_PDF_310.json`, con `tarea: "pdf_310"`, `estado: "entrega_candidata"` o `"bloqueo_declarado"`, `archivos_permitidos_sha256` (mapa de rutas relativas a PROYECTO FINAL y SHA256), resultados, límites y siguiente acción. Si la cuota impide terminar, conservar evidencia parcial y marcador de bloqueo. Un marcador no es aceptación por Codex.
