# Ensayo de construcción estática en ETABS

17 de octubre de 2026. Codex ejecutó el puente y el ejecutor integrado contra ETABS 21.1.0 instalado. Se creó una instancia de ensayo mediante CreateObjectProgID; no se reutilizó un modelo del usuario. Toda geometría, parámetros y aprobaciones del experimento son sintéticos. No se ejecutó RunAnalysis.

## Resultado

La plantilla vacía se guardó, se copió con SHA256 comprobado y se abrió en el PID de ensayo 30684. La configuración estática del experimento se preparó con `examples.preparar_ensayo_etabs`, separada de la demo modal/espectral original. El plan `ade032da348e5262c4f25e46a849787da6eb286d4c1240150fffa7b309a9332d` ejecutó sus 42 operaciones y guardó un EDB nuevo. La puerta integrada revalidó origen/plan y salida bajo el bloqueo; dejó aceptación y archivó la marca de operación no confirmada.

En `tmp/etabs_sintetico_real_001` se conservan plantilla, configuración, plan, solicitud, respuesta, traza, EDB, aceptación y lecturas posteriores. El EDB `ensayo/modelo_construido.edb` tiene SHA256 `52563a2c96686c848c6935990ee1eef9febfc4df6ec4a2b9e249b305e10a0fc0`.

Una lectura independiente mediante `scripts/inspeccionar_modelo_etabs.ps1` encontró puntos A0/B0/A1/B1, frames COL1/V1 y muro M1. Coordenadas: (0,0,0), (4,0,0), (0,0,2.6), (4,0,2.6), unidades kN_m_C. Se reabrió una copia del EDB guardado y se repitió la lectura: `lectura_persistida.json`. Esto comprueba persistencia de esos objetos y coordenadas, además de retornos API y archivo guardado.

## Límites observados

- El ensayo no verifica todas las propiedades/asignaciones por lectura independiente. Retorno cero y traza no equivalen a equivalencia estructural.
- NewBlank conserva propiedades y casos predeterminados adicionales. El plan desactiva todos los casos de análisis antes de activar los declarados; no los elimina.
- Tras guardar, GetModelFilename devolvió la ruta de trabajo `modelo_construido.$et`. Tras reabrir devolvió `.EDB`. La primera lectura independiente con ruta EDB exacta se rechazó; se diagnosticó y se leyó la ruta realmente reportada. No se relajó la comparación exacta de rutas del producto. Falta resolver de forma explícita esa transición para análisis y tablas posteriores.
- No hay aprobación de ingeniería, análisis, periodos/derivas/cortante calculados, calibración de albañilería ni procesamiento de planos reales en esta prueba. Modal/espectro siguen fuera de la construcción disponible y pendientes del alcance global.

## Repetición

Crear una carpeta de ensayo nueva y una instancia nueva con `scripts/crear_plantilla_etabs_vacia.ps1`; preservar el registro con PID/hash. Preparar la fixture con `python -m examples.preparar_ensayo_etabs --help`. Abrir una copia verificada con `python -m draft2model etabs ... abrir-copia`, seleccionando únicamente el PID propio y compartiendo el bloqueo con `construir-etabs`. Preparar primero y añadir `--ejecutar` para aplicar las operaciones. Leer CONSTRUCCION_ETABS.md y CLI_ETABS.md.

No reutilizar el PID histórico sin comprobarlo, no sobrescribir destinos y no reintentar una operación incierta. La copia reabierta comprueba persistencia, no sustituye la revisión del modelo. Los scripts respetan la política de PowerShell del equipo; no utilizan Bypass.
