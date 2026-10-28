# tests

## Overview
Suite integral de pruebas automatizadas que cubre pruebas unitarias de algoritmos geométricos, pruebas de integración con el adaptador ETABS, comprobación de contratos de API HTTP y pruebas funcionales de la interfaz web en Node.js.

## Interface
- **Pruebas de Geometría y Partición**:
  - `test_validacion_geometria.py`: Integridad topológica, polígonos cerrados y detección de colisiones.
  - `test_superposicion_superficies.py`: Coincidencia espacial entre elementos estructurales y el plano base.
  - `test_triangulacion_particiones.py`: Descomposición de superficies complejas en mallas discretas.
- **Pruebas de Adaptadores y Flujo ETABS**:
  - `fixture_etabs.py`: Proveedor de dobles de prueba y mocks para la API de ETABS cuando no se dispone de licencia activa en el entorno de pruebas.
  - `test_revision_modelo.py` & `test_revision_ejecucion.py`: Ciclos de vida del modelo y validación de parámetros de salida.
- **Pruebas del Servidor HTTP y API**:
  - `test_revision_*_http.py`: Comprobación de endpoints REST locales para ingreso, preprocesamiento, mapeos e informes.
- **Pruebas de Interfaz Web (Frontend)**:
  - Archivos `.cjs`: Scripts de prueba basados en Node.js para verificar el comportamiento de los componentes JavaScript (`digitizacion_353_frontend.cjs`, `contornos_359_frontend.cjs`, etc.).

## Invariants
- Pruebas herméticas e independientes del orden de ejecución.
- Por defecto, los tests unitarios no requieren una instalación de ETABS en ejecución ni credenciales activas de servicios cloud (usan fixtures sintéticas y dobles de prueba).
- Los archivos generados durante los tests se limpian automáticamente mediante los fixtures de `tmp_path` de pytest.

## Side Effects
- Creación y eliminación de directorios temporales de prueba.
- Levantamiento de servidores HTTP efímeros en puertos libres de loopback durante las pruebas de integración.

## Verification
- Ejecutar suite completa con pytest:
  ```powershell
  pytest tests/
  ```
- Ejecutar una prueba unitaria específica:
  ```powershell
  pytest tests/test_validacion_geometria.py -v
  ```
