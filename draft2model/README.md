# draft2model

## Overview
Motor central de Draft2Model. Este paquete contiene la lógica de procesamiento para transformar planos estructurales (imágenes y PDFs) en datos estructurados trazables, ensamblar geometrías bidimensionales y tridimensionales, interactuar con la API OAPI de CSI ETABS, calcular espectros sísmicos según la normativa peruana E.030, y emitir reportes técnicos de ingeniería.

## Interface
- **Punto de Entrada CLI**: `python -m draft2model` ([`__main__.py`](__main__.py)) con comandos para `demo-integrada`, `extraer`, `geometria`, `modelo`, `evaluar` e `informe`.
- **Servidor Web Local**: `python -m draft2model.revision_visual` ([`revision_visual.py`](revision_visual.py)) para revisión supervisada vía navegador web.
- **Módulos Principales**:
  - `entrada_vision.py` & `extraccion_preliminar.py`: Ingesta, hashing SHA-256, rasterización de PDFs y comunicación deliberada con APIs multimodales (Gemini / OpenAI).
  - `geometria_superficies.py`, `conversion_geometria.py` & `contornos_a_geometria.py`: Ensamblado de mallas poligonales, cotas físicas, detección de aberturas y correspondencias espaciales.
  - `normativa_e030.py` & `configuracion_normativa.py`: Modelado de espectro elástico e inelástico según la Norma Técnica Peruana E.030 (Z, U, S, C, R).
  - `adaptador_etabs.py`, `ejecutor_etabs.py` & `analisis_etabs.py`: Puente de automatización OAPI COM hacia CSI ETABS v18-v22 para creación de elementos frame/shell, asignación de cargas y corrida de análisis modal y espectral.
  - `informe.py` & `evidencia_analisis.py`: Generación de informes de ingeniería en formatos JSON, HTML y PDF con trazabilidad de decisiones humanas.
- **Subdirectorios y Contratos Hijos**:
  - [`datos`](./datos/README.md): Tablas normativas y parámetros sísmicos distritales E.030.
  - [`revision_web`](./revision_web/README.md): Interfaz web local SPA para revisión y validación visual.

## Invariants
- **Reproducibilidad y Trazabilidad**: Todo archivo o plano procesado se indexa mediante su hash criptográfico SHA-256.
- **Aislamiento de Proveedores**: Opera en modo sintético local por defecto; ninguna llamada de red a proveedores de IA ocurre a menos que el usuario active deliberadamente las credenciales y envíe la solicitud.
- **Validación Humana Explícita**: La aprobación de un plano, una geometría o un informe son actos diferenciados que no se deducen automáticamente.
- **Invarianza de Cero Modificaciones a ETABS sin Permiso**: No se altera ningún archivo `.EDB` o modelo fuera del directorio temporal o de salida indicado por el operador.

## Side Effects
- Lectura de archivos PDF/PNG/JPG desde la carpeta de trabajo del usuario.
- Escritura de modelos temporales, geometrías `.json` y reportes en la ruta `--salida`.
- Lanzamiento opcional del proceso ejecutable de CSI ETABS mediante la interfaz COM de Windows.

## Verification
- Ejecutar suite de validación integrada:
  ```powershell
  python -m draft2model demo-integrada --salida tmp/demo_verificacion --verificar
  ```
