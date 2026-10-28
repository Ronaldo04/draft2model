# Referencia humana pendiente: cómo completarla

Abrir `Anotar_referencia.html` en un navegador. Funciona sin conexión y no pide claves. Las tres imágenes se copiaron de las vistas previas registradas del expediente inicial `provisional-001`, correspondiente a los planos estructurales de Pueblo Libre. Conservan los hashes de sus PDF originales. No son los proyectos segundo o tercero.

La herramienta está vacía: **0 observaciones**. No contiene respuestas de OpenAI, Gemini ni valores propuestos por Codex. No se ha creado una referencia humana revisada ni se han medido precisión o cobertura.

1. Elegir lámina y ampliar a200% o300% si hace falta. Arrastrar sobre la imagen para marcar la región del dato.
2. Elegir cota, etiqueta o elemento. Transcribir lo que se lee y declarar unidad y legibilidad. No inferir unidades ausentes; mantener `null` si es ilegible o ambiguo. Para etiquetas/elementos usar `no_aplica`.
3. Conservar observaciones distribuidas entre clases y láminas. El protocolo pide al menos30; una categoría que no aparezca se documenta y no se inventa.
4. Completar revisor y fecha únicamente después de una lectura personal real. La declaración es humana y no la puede completar Codex en tu nombre.
5. Preparar y guardar `referencia_humana.json`. Indicar su ruta local en el chat; no hace falta enviar el modelo ETABS manual ni ninguna clave.

El archivo se validará y se revisarán las correspondencias con candidatos **anteriores a corrección** antes de calcular las métricas. Una muestra parcial solo permitirá conclusiones sobre esa muestra. La referencia anotada no es una aprobación estructural ni un estudio de suelos.

También se incluye `referencia_vision_vacia.csv` como alternativa de anotación. `fuentes.json` identifica imágenes, archivos, páginas y hashes. El anotador no guarda tus cambios automáticamente: exporta avances para conservarlos. Los planos permanecen privados; este kit no forma parte del ZIP de fuentes públicas.
