# Uso de Draft2Model

Abrir la aplicación según la [instalación](GUIA_REPRODUCIBLE.md). Trabajar con documentos cuyo uso esté autorizado y una raíz local propia. El ingreso mantiene hashes de los originales y revisiones separadas; las aprobaciones son declaraciones explícitas.

1. Registrar el expediente y susPDF/JPG/PNG. Revisar páginas y preparar recortes/paquetes visuales cuando sea necesario. Las imágenes derivadas conservan su procedencia.
2. Revisar las lecturas y su evidencia. Las solicitudes a Google u OpenAI requieren configuración y confirmación deliberadas. Los originales y derivados pueden contener información del proyecto; la aplicación no los envía al abrirse.
3. Reconstruir relaciones y coordenadas como propuesta. El flujo conserva trabajos y permite reevaluación local sin nuevo envío. Una unidad faltante requiere declaración trazable del operador. Conflictos o faltantes bloquean la geometría disponible para modelar; no se completan por suposición silenciosa.
4. Revisar la geometría mediante editor y visor3D. La conversión y la importación tabular requieren correspondencias y unidades físicas explícitas. Crear la configuración de materiales, secciones, cargas, sitio y sistema desde los datos revisados. La plantilla se genera mediante el módulo `plantilla_configuracion`; no existe una configuración de ingeniería universal preaprobada.
5. Aprobar por separado geometría/configuración/modelo cuando corresponda. Preparar y revisar el planETABS antes de construir. El acceso al motor es local, con bloqueo exclusivo y rutas explícitas; los scripts requeridos están en `scripts/`.
6. Ejecutar el análisis deliberadamente, releer y normalizar los resultados con correspondencias revisadas. Las omisiones y los retornos del motor no constituyen aceptación de ingeniería.
7. Revisar resultados, fuentes, contexto y controles antes de exportar el informe preliminar. La aprobación documental, la aprobación del modelo y la revisión de resultados son actos distintos.

La [interfaz por etapas](INTERFAZ_POR_ETAPAS.md), [contrato geométrico](CONTRATO_GEOMETRIA.md), [conversión](CONVERSION_GEOMETRIA.md), [configuración](MODELO_ESTRUCTURAL.md) y [controles](CONTROLES_ANALISIS.md) amplían los requisitos. Los comandos operativos distribuidos se consultan con `python -m draft2model --help`; cada módulo ofrece su ayuda.

Esta distribución no contiene datos de demostración, fixtures ni suites. Los archivos de entrada, corpus aprobado, capas de sitio y documentos reales los aporta el operador. La autonomía es parcial: no está acreditada la lectura completa de cualquier construcción, la configuración automática ni el procesamiento de lotes mayores de ocho páginas. Todo borrador exige revisión profesional y no certifica seguridad estructural.
