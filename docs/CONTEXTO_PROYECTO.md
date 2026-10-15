# Contexto del proyecto

Actualizado: 14 de octubre de 2026. Síntesis operativa de los dos documentos base; no constituye una validación técnica ejecutada ni una revisión de vigencia normativa.

## Fuentes y estado

1. [Desarrollo técnico](../SismoVivienda_AI_Desarrollo_Tecnico.pdf), 17 páginas: alcance, arquitectura, contratos, pruebas y secuencia; sus asignaciones históricas no gobiernan el desarrollo actual.
2. [Entrega de avance](<../SismoVivienda_AI_Entrega_Avance 01 - 03-10-2026.pdf>), 5 páginas: síntesis del problema, solución y validación prevista.
3. [Resumen reciente](../entregables/Draft2Model_One_Page.html): nombre Draft2Model y siguiente paso del piloto.

En los documentos se declara disponibilidad de ETABS y conexión API. El registro básico de ingreso local ya está implementado y probado con archivos sintéticos. Se dispone de una muestra provisional de planos fuera del MVP para probar procesamiento documental; los modelos de referencia y resultados estructurales aún no están disponibles. Su existencia en otras máquinas permanece por confirmar. Una tecnología mencionada no se considera instalada, integrada ni validada por esa sola mención.

La muestra provisional no cambia el alcance del MVP ni acredita su validación. La declaración de incompatibilidad se conserva en el expediente y el informe de revisión.

## Objetivo y usuarios

Desarrollar y validar un prototipo que transforme fotografías o escaneos legibles de planos estructurales de viviendas autoconstruidas en modelos parametrizados de ETABS. Obtener indicadores seleccionados de respuesta sísmica y generar un informe preliminar con fuentes, hipótesis, alertas y trazabilidad.

El usuario operativo es el ingeniero o equipo técnico. La familia propietaria es beneficiaria de una explicación profesional sobre lo evaluado y la información adicional necesaria. El beneficio de reducir tiempo y trabajo repetitivo debe medirse.

## Alcance del MVP

| Aspecto | Alcance documentado |
| --- | --- |
| Territorio | Lima Metropolitana. |
| Tipología | Albañilería confinada de uno a dos niveles. |
| Casos | Un caso piloto principal; casos adicionales condicionados por datos y tiempo. |
| Entrada | Planos estructurales legibles, ubicación y datos complementarios. |
| Parámetros | Alturas, espesores, materiales, cargas, sitio e hipótesis revisados. |
| Modelo | Una plantilla ETABS técnicamente revisada y parametrizada. |
| Salida | Modelo, indicadores, alertas e informe preliminar trazable. |
| Contingencia | CSV/Excel supervisado convertido al mismo contrato de datos. |

No se incluye certificación de seguridad, probabilidad de colapso, diseño de reforzamiento, capacidad portante, reconstrucción desde fotos de fachadas ni otros sistemas o mayores alturas. Un plano no acredita lo construido. Sin documentación suficiente se requiere información o levantamiento previo.

## Flujo y aprobaciones

1. Registrar expediente, originales, láminas y faltantes.
2. Preparar imágenes: perspectiva, rotación, contraste, escala y recortes.
3. Visión multimodal interpreta la vista general y los recortes para proponer textos, cotas, elementos y relaciones con evidencia. OCR puede asistir lecturas puntuales o contrastes, sin dirigir la extracción.
4. Comprobar unidades y geometría; corregir y **aprobar datos e hipótesis**.
5. Generar el modelo con el adaptador ETABS y **aprobar modelo y configuración**.
6. Analizar; extraer resultados y aplicar reglas reproducibles.
7. Recuperar fuentes aprobadas y redactar explicaciones con RAG y LLM.
8. Verificar cifras, citas, supuestos y presentación; **aprobar el informe** antes de entregarlo.

La IA propone datos y texto; ETABS calcula; las reglas procesan criterios previamente revisados. Los datos ausentes permanecen ausentes; las suposiciones necesitan identificación, justificación y aprobación.

## Contratos previstos

| Contrato | Función |
| --- | --- |
| `expediente.json` | Caso, láminas, niveles, ubicación y documentación. |
| `extraccion_preliminar.json` | Candidatos, textos, cotas, evidencia visual y dudas. |
| `estructura_validada.json` | Geometría, parámetros, hipótesis y aprobación; entrada al modelado. |
| `ejecucion.json` | Versión de entradas, configuración y corrida. |
| `resultados_etabs.json` | Valores con unidades, caso, nivel, dirección y objetos de origen. |
| `evaluacion.json` | Indicadores, reglas, alertas, faltantes y fuentes. |
| `informe.json` | Cifras verificadas, explicaciones, citas y limitaciones. |

El registro básico de expediente está implementado en v0.1.0 para originales, hashes y estado borrador. El contrato geométrico v0.1 y su validador se implementaron y probaron con datos sintéticos; siguen como propuesta inicial. Los contratos de ejecución, resultados, evaluación e informe continúan previstos. Cambiar geometría o hipótesis exige nueva aprobación y análisis. Modificar reglas invalida evaluación e informe; cambiar fuentes explicativas exige regenerar y revisar la explicación correspondiente.

## Tecnologías y operación previstas

Python modular; OpenCV y PyMuPDF/Pillow; primer conector OpenAI preparado para visión multimodal, con modelo configurable y prueba real pendiente; OCR opcional por validar como apoyo; JSON/Pydantic y SQLite; Shapely y herramientas geográficas; ETABS/API CSI; reglas reproducibles; RAG sobre corpus aprobado; generación de informes y figuras.

Streamlit y Tesseract son candidatos. El proveedor multimodal y el LLM se seleccionan mediante pruebas, no por reputación. Claude Code es una herramienta de desarrollo, no el motor de cálculo estructural.

El piloto técnico contempla Windows de 64 bits con licencia ETABS, un revisor y una corrida de ETABS activa a la vez. GitHub comparte archivos y versiones; no replica instalaciones, licencias, credenciales ni ejecuta ETABS automáticamente. La máquina ejecutora y su operador deben confirmarse durante la preparación técnica.

## Ejecución vigente

El avance se organiza por requisitos y criterios verificables, con apoyo de Codex y Claude Code para programación y documentación. El código puede consultarse según los permisos acordados; las observaciones y decisiones de las reuniones se registran en Markdown.

La planificación se organiza por requisitos, módulos, dependencias y criterios de aceptación. Se conservan las verificaciones de datos, modelo e informe. Una revisión de IA no sustituye la aprobación de ingeniería.

La distribución histórica y las evidencias de aportes para el programa se conservan únicamente en [Referencia para la sustentación](REFERENCIA_SUSTENTACION.md), fuera del flujo operativo. Los documentos fuente permanecen como antecedentes.

## Resultados y validación

Siete resultados previstos: estado de generación/análisis; geometría y número de muros; periodos seleccionados; derivas por nivel y dirección; cortante basal por dirección; advertencias/inconsistencias; condición referencial del sitio con fuente.

Comparación contra un modelo manual del mismo caso, con materiales, hipótesis, cargas, unidades, casos y versión ETABS equivalentes. Registrar precisión/cobertura inicial, lectura de cotas, error dimensional, número y tiempo de correcciones, diferencias de indicadores, tiempo total y costo. Aprobar tolerancias antes del ensayo; separar extracción inicial de resultado corregido.

Las pruebas P01-P14 del desarrollo técnico cubren conexión, imágenes, preprocesamiento, visión, contratos, revisión humana, sitio, generación, cálculo, reglas, RAG, informe, fallos y flujo completo. Conservar su evidencia. La concordancia entre modelos verifica el flujo y no certifica la seguridad de la vivienda.

## Definición de terminado

Un caso reproducible desde la imagen hasta el informe, con extracción evaluada, correcciones trazables, datos y modelo aprobados, análisis identificable, siete resultados, reglas documentadas e informe revisado. Acompañado de comparación manual/asistida, tiempos, costos y limitaciones. No se declara generalización a otras viviendas con un único ensayo.

## Decisión de interpretación visual

La secuencia prevista es vista general -> identificación de regiones -> interpretación de recortes con contexto -> candidatos estructurados con evidencia -> contraste y revisión -> geometría. La selección de regiones está implementada manualmente; su detección automática y la extracción multimodal siguen pendientes. No imponer un recorrido de lectura textual como sustituto de la interpretación espacial. Cada candidato debe identificar su origen, distinguir observación de hipótesis y admitir valor desconocido.
