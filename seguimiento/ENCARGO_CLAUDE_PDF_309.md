# Encargo309 — Reproducción y diagnóstico de compatibilidad del PDF

Responsable: Claude. Codex conserva integración, revisión y cierre. Trabajar en la misma carpeta PROYECTO FINAL. No editar archivos compartidos de producto: la distribución308 está congelada y conserva el código306 validado con1424Python y36pruebas de interfaz. Codex mantiene entrega/auditoría y el usuario está preparando la referencia humana de visión.

## Objetivo

Determinar por qué algunos renders de las páginas7 y8 del informe técnico pierden prefijos, sin alterar cifras, criterios o límites. Entregar causa reproducible y una corrección candidata si procede. Un PDF con texto extraíble no prueba legibilidad; un visor vacío tampoco prueba corrupción del PDF.

## Entradas de solo lectura

- `tmp/recorrido_09d3/resultados/informe/informe.pdf`: informe técnico de8páginas, SHA256 `ca4fc1432c509af1bc944f376e8f60f4a16f94fc3a8eff4e63b59ef2dbb5acf9`.
- HTML/JSON del mismo directorio; `seguimiento/REVISION_INFORME_302.json`; renders existentes en `tmp/pdfs/revision_302/`.
- `draft2model/informe.py`, especialmente `_story_paginada` y `_pdf`; dependencias fijadas. PDF se genera mediante PyMuPDF Story/DocumentWriter y después añade pies de página con `insert_text`, guarda con `garbage=4, deflate=True`.
- Distribuciones303/306/308 y entorno offline303 para contrastar versiones, sin modificarlos.

Observación previa: páginas1–6 legibles. Página7 legible completa en Poppler; página8 legible completa en MuPDF aislada. Algunos renders secuenciales muestran prefijos incompletos; texto y sus cajas están dentro de página. Poppler informó falta de fuentes Symbol/ArialUnicode. No hay causa confirmada. El informe conserva18comparaciones,10no satisfactorias y masa `no_coherente`: no cambiar estos resultados para aparentar éxito.

## Archivos permitidos

Escribir únicamente dentro de `seguimiento/claude_ruta/diagnostico_pdf_309/` y el marcador final `seguimiento/claude_ruta/MARCADOR_PDF_309.json`. Crear carpeta si no existe. No editar `draft2model/`, `tests/`, `docs/`, `entregas/`, expedientes privados, registros ni informes existentes. Codex integrará la propuesta tras revisarla. No tocar el anotador ni las referencias humanas del usuario.

## Investigación y entregables

Economía de cuota: empezar por páginas7/8 y fragmentos de `_pdf`; no volcar HTML/JSON completos ni releer historiales. Extraer por código únicamente las partes y metadatos necesarios. No repetir suites globales, empaquetado ni QA301: Codex ya los completó.

1. Verificar SHA del PDF antes de diagnosticar. Registrar versiones efectivas de Python, PyMuPDF, Poppler y fuentes relevantes. Usar lo instalado; no actualizar dependencias o descargar programas.
2. Reproducir con renders aislados y secuenciales. Conservar parámetros y capturas relevantes, distinguir motor/versión, texto esperado y lo visible. Investigar recursos de fuente, cajas, clipping, paginación y el posprocesado sin asumir una causa por una sola captura.
3. Si hay defecto del generador, preparar parche mínimo o módulo candidato en la carpeta permitida y un caso mínimo reproducible; no ejecutar reconstrucciones del expediente ni comprobaciones completas repetidas de sus fuentes. Se puede trabajar desde el HTML/JSON ya publicados o un HTML mínimo aislado.
4. Verificar el candidato con lectura visual suficiente y, cuando estén disponibles, dos motores de render. Conservar valores,18evaluaciones, unidades, hipótesis, avisos y pies; evitar desbordes, prefijos cortados o cambios de contenido. Si no hay causa o segundo motor disponible, explicarlo sin declarar compatibilidad universal.
5. Entregar un informe breve con diagnóstico, archivos, pruebas, resultados, límites y siguiente acción concreta. El marcador debe ser la última escritura: estado `entrega_candidata` o `bloqueo_declarado`, tarea309, archivos permitidos y SHA256, comprobaciones y restricciones. Un marcador no es aceptación por Codex.

## Restricciones

Sin llamadas a OpenAI, Google u otras APIs/LLM externos; sin claves, sin lectura de credenciales, sin ETABS ni nuevo análisis/modelo. No regenerar el informe sobre el expediente privado, no modificar tolerancias ni eliminar evidencia. No subir archivos a servicios externos. No consultar continuamente ventanas. Si una cuota o herramienta bloquea la tarea, dejar diagnóstico mínimo y marcador de bloqueo; no inventar una entrega ni reclamar aprobación de ingeniería.
