# Contexto del proyecto

Actualizado:24de octubre de2026, corte312. La base306 pasó1424Python y36pruebas de interfaz.312 integra la fuente del pie PDF y una prueba adicional;67pruebas focales de informes correctas. El resumen junto al ZIP informa la validación de su huella exacta. Piloto construido y analizado; extracción sin benchmark humano completo, masa no_coherente y diez comparaciones no satisfactorias conservadas. La aceptación global sigue abierta; no se ha demostrado generalización a cualquier construcción. [RETOMAR](RETOMAR.md) conserva el seguimiento interno.

## Objetivo, fuentes y alcance

Desarrollar y validar un prototipo que transforme fotografías/escaneos legibles de planos en datos revisados, modelos parametrizados ETABS e indicadores seleccionados de respuesta sísmica, con informe preliminar, fuentes, hipótesis y trazabilidad. Lo opera un ingeniero o equipo técnico. La reducción de trabajo y tiempo se mide; no se presupone por existir automatización.

El alcance original procede del desarrollo técnico (`SismoVivienda_AI_Desarrollo_Tecnico.pdf`, antecedente del repositorio de desarrollo) y la entrega de avance (`SismoVivienda_AI_Entrega_Avance 01 - 03-10-2026.pdf`, antecedente del repositorio de desarrollo). Las decisiones posteriores de operación están en Markdown. Los PDF originales y sus asignaciones históricas se conservan como antecedentes.

| Aspecto | Compromiso vigente |
| --- | --- |
| Validación original | Un caso principal de albañilería confinada de uno o dos niveles en Lima Metropolitana; más casos según datos disponibles. |
| Referencia de desarrollo | Procesar los planos ya presentes, aunque correspondan a otro sistema, conservando procedencia y diferencias de alcance. |
| Entrada | PDF/JPG/PNG legibles, ubicación y datos complementarios documentados; falta de datos visible. |
| Parámetros/modelo | Geometría, idealización, materiales, secciones, cargas, masa, apoyos/diafragmas, sitio y casos explícitos y revisados. |
| Salida | Modelo, siete categorías de resultados, alertas e informe preliminar trazable. |
| Contingencia | CSV/XLSX supervisado convertido al mismo contrato geométrico, sin fórmulas ni unidades inferidas. |
| Secuencia acordada | Completar infraestructura; clave/ensayo real de visión y comparación manual al final, con ajustes según los resultados. |

La marca histórica de muestra fuera del MVP no impide procesar o modelar la referencia existente. Tampoco se convierte en prueba de albañilería confinada por cambiar una etiqueta. La capacidad de representar cada sistema requiere configuración técnica explícita; no se afirma que una plantilla genérica valide todas las tipologías.

No se incluyen certificación de seguridad, probabilidad de colapso, diseño de reforzamiento, capacidad portante ni reconstrucción desde fotos de fachadas. Un plano no acredita lo construido; sin datos suficientes se requiere información o levantamiento adicional.

## Arquitectura implementada y flujo de revisión

Python modular, JSON con validadores propios, archivos versionados, SQLite, Pillow/PyMuPDF y aplicación HTTP/JavaScript local. El puente ETABS utiliza Windows PowerShell 5.1 y la biblioteca instalada en Windows x64. La recuperación de fuentes es léxica local; el informe determinístico conserva indicadores y citas sin exigir un LLM. Streamlit, OCR, embeddings y otras bibliotecas mencionadas en antecedentes no son dependencias actuales por esa sola mención.

1. Registrar originales autorizados y hashes; revisar páginas y faltantes.
2. Preparar contexto/recortes PDF o raster con coordenadas declaradas. Rotación/perspectiva/contraste tienen módulo propio; su integración completa como fuente derivada de paquetes está en desarrollo.
3. Preparar proveedor sin envío o registrar una respuesta local. Ejecutar un envío requiere modelo/opciones/confirmación explícitos y credencial local del servidor; no se pide la clave en el navegador o el repositorio.
4. Conservar respuesta original, vincularla y trasladarla a extracción pendiente mediante acciones separadas; revisar candidatos y corregir creando versiones.
5. Convertir con correspondencias, unidades, escala/ejes y conectividad explícitos. Importar geometría borrador no constituye aprobación.
6. Revisar y aprobar geometría/configuración exactas; generar una copia ETABS. La revisión propia del modelo es posterior e independiente.
7. Seleccionar esa revisión y confirmar análisis; leer tablas deliberadamente, revisar correspondencias y normalizar resultados con unidades/casos/niveles/direcciones.
8. Aplicar reglas revisadas, recuperar fuentes y presentar sitio referencial; generar panel e informe. La aprobación documental propia es otra versión, sin aprobar resultados o conformidad normativa.

La IA propone; ETABS calcula; reglas configuradas evalúan criterios explícitos. Los valores desconocidos permanecen ausentes. Las identidades y aprobaciones son declaraciones registradas, no autenticación profesional ni firma digital. Cambiar entradas, modelo, reglas o fuentes invalida los derivados afectados; no se reparan huellas para hacerlos parecer vigentes.

## Contratos y persistencia actuales

Los nombres del diseño original no implican que todo el contrato deba estar concentrado en un único archivo `estructura_validada.json` o `ejecucion.json`. La implementación separa artefactos y vínculos exactos:

| Área | Implementación disponible |
| --- | --- |
| Expediente/extracción | `ingreso.py`, `revision_documental.py`, `extraccion_preliminar.py`, `gestion_extraccion.py`: originales, candidatos, evidencias y versiones. |
| Preparación/proveedor | `recortes.py`, `entrada_vision.py`, `preprocesamiento.py`, `proveedor_openai.py`: paquetes, transformaciones, planes, intentos y respuestas conservadas. |
| Geometría | `contratos.py`, `validacion_geometria.py`, `conversion_geometria.py`, `gestion_geometria.py`: contratos v0.1 (muros), v0.2 (superficies XYZ) y v0.3 (superficies con aberturas), faltantes, procedencia y aprobación ligada al contenido; partición/compatibilidad/triangulación (`particion_superficies`, `compatibilidad_particiones`, `triangulacion_particiones`, `malla_preparacion`). |
| Configuración/modelo | `modelo_estructural.py`, `gestion_configuracion.py`, `operaciones_etabs.py`, `ejecucion_modelo.py`, `revision_modelo.py`: configuración versionada, plan, copia y revisión propia. |
| Corrida/resultados | `orquestacion.py`, `analisis_etabs.py`, `lectura_analisis.py`, `normalizacion_etabs.py`, `resultados_estructurales.py`, `evidencia_analisis.py`: estados, tablas, normalización, huellas y evidencia de análisis. |
| Evaluación/contexto | `evaluacion_estructural.py`, `fuentes.py`, `sitio.py`: reglas/fórmulas/aplicabilidad, corpus/citas y cobertura referencial con límites. |
| Entrega | `panel_tecnico.py`, `informe.py`, `revision_entregables.py`: panel, JSON/HTML/PDF y versiones de aprobación documental propia. |

Los contratos de resultados, evaluación e informe **ya están implementados**, y la aprobación documental, el contexto técnico y las explicaciones están integrados en HTTP/UI/informe (las explicaciones no usan APIs: plantilla determinística o contingencia). Configuración/plan 0.4 (malla) y 0.5 (líquidos opcionales) recorren construcción, relectura, análisis y lectura en ETABS real con fixtures **sintéticas** (`tmp/l2`, `tmp/r3`). Su existencia no acredita resultados del caso de referencia ni revisión de ingeniería.

La geometría de resultados se vincula a una versión y SHA256 de bytes; la configuración tiene huella canónica sin revisión. No intercambiar ambos tipos de huella. Las consultas/descargas vuelven a comprobar fuentes y rechazan obsolescencia. Operaciones inciertas se conservan para recuperación explícita; no se relanzan modelos, normalizaciones o envíos por actualizar una pantalla.

## Estado comprobado y límites de evidencia

- La demo offline integra módulos con datos y aprobaciones fabricados, seis corridas SQLite e informe borrador. Prueba software sin IA ni ETABS reales.
- Los ensayos CLI de ETABS 21.1 incluyeron construcción estática/dinámica sintética, copia guardada/reabierta, controles independientes, análisis EST/MOD/EX, lectura, normalización y evidencia hasta informe. Ver [ensayo dinámico](ENSAYO_ETABS_DINAMICO.md). No corresponden a la vivienda de referencia.
- Ingreso, preparación, respuestas, proveedor, conversión y recorrido estructural web tienen comprobaciones focales. HTTP/DOM simulados y transportes Python dobles no acreditan proveedor o ETABS real desde la nueva vía ni un ensayo visual completo de todas las pantallas.
- Copias limpias históricas: la 100 terminó fallida (18 fallos, 4 errores, 9 omisiones) y la 146/148 cubrió el árbol previo a multiproveedor/superficies (850 Python, 26 Node). **Ninguna acredita el árbol actual**; la copia limpia del árbol de la ruta 201 es la etapa 05. No se atribuyen pruebas antiguas al árbol actual.

## Aceptación final

Las siete categorías son estado de generación/análisis; geometría/número de muros; periodos; derivas por nivel/dirección; cortante basal por dirección; advertencias/inconsistencias; sitio referencial con fuente. Un indicador no disponible se declara, sin rellenarlo con cero. Una regla satisfecha no se traduce en seguridad global.

El cierre exige un recorrido reproducible desde imagen hasta informe, extracción inicial medida contra anotación humana, correcciones trazables, datos/configuración/modelo revisados, cálculo identificable, reglas/fuentes aplicables e informe revisado. La comparación manual/asistida utiliza hipótesis, materiales, cargas, unidades, casos y versión ETABS equivalentes, con tolerancias previas; registra tiempos y costos reales. Se preservan pruebas P01–P14, recuperación de fallos y limitaciones. La comparación manual y el ensayo del proveedor se realizan al final según el usuario; no se fabrican mientras tanto ni se declara éxito global por la demo.

**Comparación manual (aplazada por el usuario):** el usuario retiene su modelo ETABS manual hasta que entreguemos nuestros resultados finales. No se usa como guía ni se pide para desbloquear infraestructura, y **no es condición del cierre actual**; el piloto real con los planos (etapa 04) es distinto de esa comparación. Funcionar con esta referencia no demuestra generalización a albañilería confinada de 1–2 niveles.
