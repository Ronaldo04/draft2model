# Buscar la región de una lectura sin llamadas a modelos

En «Contrastar y corregir», seleccionar una lectura y pulsar **Buscar texto
literal en PDF local**. El sistema consulta las páginas de evidencia del
candidato y busca palabras completas contiguas de una misma línea. Admite
rotación y recorte de página. No convierte números, unidades ni escalas.

Cada región encontrada tiene un botón para previsualizarla en el plano. La
consulta no guarda versiones ni modifica la evidencia. Tras contrastar la
imagen, el operador puede usar el procedimiento existente de reubicación
del contrato 0.2.0, con motivo, fecha y revisor declarados. Cargar una región
no registra una aprobación.

Si el literal aparece varias veces se muestran las opciones; no se elige la
más próxima a la región antigua. Con más de 50 coincidencias no se muestran
regiones para evitar aparentar unicidad. Si falta `texto_fuente`, no se fabrica
su formato a partir del número propuesto. La búsqueda no combina líneas
distintas ni acepta coincidencias parciales como `C-1` dentro de `C-10`.

La fuente debe conservar las palabras como texto del PDF. Los rótulos dibujados
con trazos, los planos escaneados y algunas codificaciones de fuentes requieren
otro método. La capa de texto también puede contener errores: una coincidencia
única es una propuesta para contraste, no una lectura visual validada.

La consulta `/api/localizar-lectura` exige sesión local, versión, candidato y
huellas vigentes; rechaza parámetros extra, originales alterados y lecturas de
otra versión. No admite rutas arbitrarias a archivos. No usa red, claves ni ETABS.

## Evidencia y límites del piloto

En el contraste con 19 etiquetas de la referencia asistida por IA 328 se obtuvo
una coincidencia única, dos búsquedas ambiguas y 16 sin coincidencias. La región
única se renderizó desde la fuente y se inspeccionó. Esto demuestra el límite de
la capa de texto del caso, no una tasa global de precisión ni autonomía universal.

Existe un ensayo separado con Tesseract local instalado que reconoce rótulos
adicionales. **Ese OCR experimental no está conectado al botón ni incluido como
función operativa en esta versión.** No se afirma reconocimiento de imágenes
por la búsqueda vectorial ni se instala Tesseract automáticamente.
