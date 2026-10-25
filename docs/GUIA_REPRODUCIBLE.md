# Instalación de la aplicación

Esta distribución contiene aplicación y documentación. Python3.10 x64 en Windows y las versiones de PyMuPDF y Pillow del lock son el entorno de referencia. Node.js no es necesario para ejecutar la interfaz servida en el navegador.

Desde la carpeta descargada, crear un entorno con `py -3.10 -m venv .venv` e instalar con `.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-win-py310.lock`. Usar `.\.venv\Scripts\python.exe -m pip check` para comprobar dependencias. El lock fija versiones y hashes; esta distribución no contiene wheels. Si se instala sin red, el operador debe aportar las dependencias exactas por su propio canal local.

Arrancar con `.\.venv\Scripts\python.exe -m draft2model.revision_visual --raiz data/private --puerto 8766`. La raíz elegida contiene los expedientes del operador y debe quedar fuera del versionado. El servidor solo escucha en loopback. Detener con Ctrl+C.

La aplicación usa módulos propios y archivos estáticos dentro de `draft2model/revision_web/`. No necesita carpetas de pruebas, fixtures, ejemplos ni seguimiento para iniciar. Los formatos de entrada se describen en los contratos de esta carpeta; las plantillas se generan con `python -m draft2model.plantilla_configuracion --help` a partir de datos del operador.

Para ETABS se requieren Windows, su licencia e instalación compatibles, la API local y capacidad de ejecutar los scriptsPowerShell. `python -m draft2model.preflight --help` describe las comprobaciones de entorno; ejecutarlas es una operación del operador y puede consultar la instalación local de ETABS. No se incluyen plantillasEDB: los scripts de creación de plantilla reciben rutas explícitas y requieren su propia operación local.

Los envíos a proveedores se configuran en el servidor; ver [accesos](ACCESOS_Y_PROVEEDORES.md). El cargador opcional `scripts/usar_credenciales_locales.py` lee un archivo local aportado por el operador y hereda variables en memoria. Nunca guardar claves en el repositorio ni pegarlas en documentos distribuidos.
