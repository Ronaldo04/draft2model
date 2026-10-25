# Draft2Model

Aplicación local para convertir planos estructurales en lecturas revisables, geometría, modelos ETABS e informes preliminares trazables. Esta distribución contiene **solo aplicación y documentación**, conforme al alcance solicitado.

El código base es el snapshot347: interfaz de siete etapas, editor geométrico, visor3D y reconstrucción de geometría borrador desde relaciones y coordenadas, con recuperación local y declaración trazable de unidad. **La autonomía sigue siendo parcial.** El flujo nuevo requiere comprobación real positiva; la configuración automática y los lotes mayores de ocho páginas siguen pendientes. El piloto anterior necesitó preparación asistida. El benchmark humano completo y la aceptación global continúan abiertos.

## Instalar y abrir

Entorno de referencia: Windows x64 y Python3.10. Desde la carpeta del proyecto:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes -r requirements-win-py310.lock
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m draft2model --help
.\.venv\Scripts\python.exe -m draft2model.revision_visual --raiz data/private --puerto 8766
```

Después de instalar también puede abrirse `Abrir revision de planos.cmd`. El servidor escucha en loopback y abre el navegador; detener con Ctrl+C. La instalación necesita acceso a las dependencias exactas del lock; no se incluyen entornos instalados ni wheels. [Guía de instalación](docs/GUIA_REPRODUCIBLE.md).

Los documentos del operador se guardan localmente en la raíz elegida. No se distribuyen planos, resultados, modelos, credenciales, fixtures, pruebas ni ensayos. La clave de visión se configura en el servidor local según [accesos y proveedores](docs/ACCESOS_Y_PROVEEDORES.md). El cargador `scripts/usar_credenciales_locales.py` contiene código, sin claves. Abrir la aplicación no envía planos ni ejecuta ETABS. Los proveedores operativos autorizados para planos son Google y OpenAI; las transmisiones y la ejecución de ETABS requieren operaciones deliberadas posteriores.

## Recorrido

La [guía de uso](docs/USO_APLICACION.md) describe ingreso, revisión de lecturas, reconstrucción, geometría/configuración, modelo, análisis e informe. La [interfaz por etapas](docs/INTERFAZ_POR_ETAPAS.md) y los contratos conservados en `docs/` detallan formatos y condiciones. Las plantillas de configuración se generan desde la geometría del operador mediante `python -m draft2model.plantilla_configuracion --help`; los CSV/JSON de entrada los aporta el operador según sus contratos. No hacen falta archivos de ejemplos para iniciar la aplicación.

ETABS requiere Windows, instalación y licencia compatibles, API local y PowerShell capaz de ejecutar los scripts. Se conservan todos los módulos de la aplicación y sus assets web, junto con los auxiliares ETABS necesarios. La CLI muestra los comandos distribuidos con `--help`. La entrada de demo fue retirada de esta distribución porque los datos y módulos de demostración no se incluyen.

## Verificación y límites

El snapshot347 completo tuvo1483 pruebas Python y39 de interfaz aprobadas, con cinco comprobaciones sin fallos ni omisiones. Esos resultados corresponden al conjunto completo de desarrollo, con sus pruebas y fixtures; **no se atribuyen a esta distribución ni a su huella**. La distribución de aplicación y documentación se verifica aparte mediante dependencias, imports, arranque CLI/HTTP, assets y enlaces. Se cambió únicamente el registro CLI de la demo; no se publican suites ni sus datos.

Las lecturas, coordenadas, geometría, configuración y resultados requieren revisión explícita. La reconstrucción produce un borrador; no resuelve información física ausente. El suelo exige información geotécnica y el sistema estructural requiere evaluación profesional. Las identidades y aprobaciones son declaradas. Aprobar un documento no acredita conformidad normativa ni aprueba resultados.

El producto no certifica seguridad, estima probabilidad de colapso, diseña reforzamientos ni deduce capacidad portante. El corpus normativo y las capas de sitio se aportan y aprueban por separado. Las rutas históricas `seguimiento/normativa_229` conservadas en metadatos de citas identifican auditorías de desarrollo, no dependencias distribuidas. La comparación con el modelo manual está aplazada. No se afirma funcionamiento universal ni validación global completa.
