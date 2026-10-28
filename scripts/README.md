# scripts

## Overview
Colección de herramientas de automatización, diagnósticos de entorno, puentes PowerShell para la API de ETABS, generadores de casos sintéticos y utilitarios para empaquetado y verificación de copias limpias.

## Interface
- **Diagnósticos y Entorno**:
  - `diagnosticar_entorno.py`: Verifica la versión de Python, dependencias instaladas y rutas de trabajo.
  - `diagnosticar_api_etabs.ps1`: Inspecciona el registro de Windows y comprueba la disponibilidad de la interfaz OAPI COM de CSI ETABS.
- **Automatización y Flujo ETABS**:
  - `ejecutar_corrida_integral.py`: Ejecuta el flujo completo de prueba desde datos de entrada hasta reporte final.
  - `analizar_modelo_etabs.ps1` / `ejecutar_plan_etabs.ps1`: Scripts PowerShell para control de procesos ETABS en segundo plano.
  - `crear_plantilla_etabs_vacia.ps1`: Inicializa una plantilla limpia con materiales estándar de concreto armado y albañilería.
- **Generación y Verificación de Casos**:
  - `crear_caso_sintetico_albanileria.py`: Genera un caso de prueba reproducible con geometría conocida y sin requerir planos confidenciales.
  - `verificar_proyecto.py`: Ejecuta la batería de validación general del repositorio.
  - `verificar_copia_limpia.py` & `crear_paquete_aecode.py`: Empaquetan y auditan la integridad de las fuentes sin temporales ni datos privados.
- **Renderizado de Documentación**:
  - `renderizar_informe.py`: Compilador de reportes a PDF/HTML estáticos.

## Invariants
- Todos los scripts verifican previamente la existencia de sus argumentos de entrada y rutas de destino.
- Ningún script escribe en directorios del sistema fuera del workspace o del directorio temporal designado.
- Salidas en formato estructurado JSON cuando son invocados por otros procesos.

## Side Effects
- Ejecución de comandos del sistema operativo (procesos Python y PowerShell).
- Apertura o cierre de instancias locales de CSI ETABS durante las pruebas de integración.

## Verification
- Diagnóstico general del entorno:
  ```powershell
  python scripts/diagnosticar_entorno.py
  ```
- Comprobación de integridad de fuentes:
  ```powershell
  python scripts/crear_paquete_aecode.py --comprobar
  ```
