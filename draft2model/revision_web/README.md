# draft2model.revision_web

## Overview
Proporciona la interfaz gráfica de usuario web (Single Page Application) servida de forma local mediante el módulo HTTP integrado. Permite la revisión interactiva paso a paso de planos, cotas, contornos vectoriales, modelos 3D y reportes de cálculo sísmico.

## Interface
- `index.html`: Plantilla principal de la interfaz web responsiva y modular.
- `app.js`: Controlador principal de eventos, navegación entre etapas y llamadas a la API local.
- `etapas.js` / `etapas.css`: Gestión visual del flujo secuencial de revisión (Ingreso, Calibración, Visión, Geometría, Modelo ETABS, Resultados).
- `digitizacion.js` / `contornos.js`: Lienzo interactivo (Canvas/SVG) para inspección y calibración geométrica de planos estructurales.
- `modelo_3d.js`: Renderizador tridimensional interactivo para visualización espacial de elementos de barras (columnas, vigas) y áreas (muros, losas).
- `herramienta_e030.js` / `configuracion.js`: Panel interactivo para cálculo y visualización del espectro de respuesta según la norma E.030.
- `katex/`: Librería local para renderizado tipográfico offline de fórmulas matemáticas y ecuaciones normativas.

## Invariants
- Ejecución 100% local en loopback (`localhost` / `127.0.0.1`), sin dependencias de internet ni telemetría externa.
- Ninguna acción crítica (envío a modelos de IA o ejecución de ETABS) se dispara automáticamente al abrir la interfaz; requiere confirmación explícita del operador.
- Sincronización bidireccional entre el estado local y los archivos JSON de sesión.

## Side Effects
- Escucha solicitudes entrantes en el puerto TCP especificado (por defecto `8766`).
- Lee y escribe artefactos de revisión dentro del directorio `--raiz` proporcionado al arrancar el servidor.

## Verification
- Ejecutar: `python -m draft2model.revision_visual --help`
