# examples

## Overview
Colección de plantillas, fixtures sintéticas y demostraciones reproducibles. Proporciona datos de entrada de muestra totalmente sintéticos (sin información confidencial de clientes ni planos con derechos de autor) para verificar el funcionamiento integral del sistema sin dependencias externas.

## Interface
- `flujo_integrado_sintetico.py`: Demostración end-to-end ejecutable que procesa una geometría sintética completa hasta la generación del reporte.
- `geometria_sintetica.json` & `modelo_estructural_sintetico.json`: Especificaciones de modelo en formato JSON para verificar importación y ensamblado.
- `referencia_vision_sintetica.json` / `referencia_vision.csv`: Respuestas sintéticas simuladas de modelos de visión artificial.
- **Subdirectorios**:
  - `conversion_sintetica/`: Ejemplos de mapeo entre tablas CSV y geometrías CAD.
  - `informe_sintetico/`: Muestra de informe estructural generado (HTML, JSON y PDF de muestra).
  - `superficies_sinteticas/`: Modelado de muros y losas poligonales con huecos.
  - `tabular_sintetico/`: Archivos CSV de ejemplo para nodos, muros y niveles.

## Invariants
- Todos los datos son completamente sintéticos y públicos.
- Ejecución sin conexión a internet ni llamadas a APIs de pago.

## Side Effects
- Ninguno sobre el proyecto en sí.

## Verification
- Ejecutar el flujo sintético:
  ```powershell
  python examples/flujo_integrado_sintetico.py
  ```
