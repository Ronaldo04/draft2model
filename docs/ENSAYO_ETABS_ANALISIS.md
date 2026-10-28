# Ensayo de revisión y análisis sintético

17 de octubre de 2026. Todos los datos del ensayo son fabricados; no es aprobación de ingeniería ni validación de los planos del usuario.

## Lectura independiente y corrección

El lector `scripts/leer_asignaciones_etabs.ps1` usa una lista fija de getters sobre la instancia/archivo exactos. Para el subconjunto estático con cargas puntuales recuperó 28 lecturas de material, secciones, conectividad, asignaciones, apoyos, diafragmas, patrones, cargas, fuente de masa, caso estático y combinación. Rechaza cargas/casos no soportados por este lector, sin omitirlos.

La primera configuración declaró gravedad 9.80665 m/s²; la razón peso/masa recuperada de ETABS 21.1 fue aproximadamente 9.806650199606521. La comparación numérica de software (tolerancia 1e-10) detectó la diferencia. Se preservó ese primer experimento sin concederle la revisión de prueba. El segundo declara 9.8066502 m/s² expresamente. No se cambió la tolerancia para ocultar el desacuerdo. Este valor observado no se impone universalmente a otros motores/versiones; el ejemplo de preparación ahora exige gravedad explícita.

En `tmp/etabs_sintetico_real_002` se conservaron nueva configuración, plan y EDB. Plan `548795ae734802686be10c4625d0f8d48cfe39a937fcb66087c48046ea7dac00`; EDB SHA256 `6a64847429bd78295f806c153277b2c18e814ad2dd6b4ad47823aa2d01451351`. Ejecutó nuevamente 42 operaciones reales.

El contraste de 55 controles pasó: `lectura_asignaciones.json`, `comprobacion_asignaciones.json`, script de contraste `tmp/comprobar_lectura_asignaciones.py`. También se comprobaron coordenadas exactas en `lectura_objetos.json`. Se registró modelo `225f8c4a9a0744fbb702a9f0b9affdc0` y revisión explícitamente sintética `b596d594ceaf4f8687f6ea502a376591`, dentro de la demo integrada. Alcance: ensayo de software, sin identidad de ingeniero ni aprobación de obra real.

## Fallos reales que se corrigieron

Primera corrida `5ec22987f819483089dff2a8a47ce6a8`: la instancia nueva abrió con unidades de presentación N_mm_C. Se detuvo antes de RunAnalysis. El puente ahora fija explícitamente kN_m_C tras OpenFile y verifica el resultado; no presume persistencia de las preferencias de otra instancia.

ETABS heredó stdout/stderr y retuvo los pipes aun después de que PowerShell emitiera el error. El adaptador ahora captura en archivos regulares y espera solo el proceso del puente. Una regresión con descendiente de prueba conserva los canales abiertos mientras el cliente puede terminar. Conjunto pertinente: `tmp/pruebas_transporte_004.log`, 27 pruebas OK, una clase omitida por política de PowerShell del sandbox.

Segunda corrida `f4e6eb04605840cda1e114f463861034`: PowerShell rechazó el cast del filtro CSI 0 a eLoadCaseType porque ese valor opcional del SDK no tiene nombre en el enum. Se corrigió mediante Enum.ToObject. También se detuvo antes de RunAnalysis.

Se cerraron exclusivamente las instancias propias fallidas 28884 y 34872, comprobando respuesta, traza sin inicio de cálculo, ruta y estado desbloqueado. Se archivaron sus marcadores con recuperación explícita antes de nuevas corridas. Todos sus artefactos se preservan. Ninguna de estas corridas acredita cálculo.

## Estado de validación

Actualización posterior: el ensayo de persistencia detectó que las primeras salidas perdían el estado calculado al reabrir. Se rechazaron esas corridas. La ruta corta tampoco lo resolvió; no se confirmó longitud como causa. Al usar Save con nombre vacío para guardar el modelo actual, la corrida `tmp/a5/adf97fbc232141e8ae687872c0d71232` conservó EST=4 después de reabrir y produjo aceptación integrada, EDB SHA256 `d317cb7f88b5d62cee61fae8a69a1bbf4e4cdfb07705e3bc595772801ed34bb7`. La traza conserva bloqueo antes/después de guardar y ruta API reportada. Esto verifica persistencia en este ensayo/version, no en todas las versiones CSI.

La [documentación oficial de CSI sobre guardado](https://docs.csiamerica.com/help-files/etabs/Menus/File/Saving_Models.htm) distingue el EDB binario principal del respaldo textual .$et. No se debe tratar ese respaldo como modelo binario equivalente aunque la API lo haya reportado después de Save. El flujo usa reapertura explícita del EDB y verifica estados, sin relajar comparaciones por nombre.

Respuesta de tablas real `tmp/a5/lectura/36f6fcef60a9412c8b8f6f527502b6a6/respuesta.json`. Normalización trazable del caso sintético: resultado `72c06efb3bfe477bb1fe565809aeddec`, cortantes X/Y=0 kN y deriva X=3e-6; deriva Y omitida como null por ausencia de fila. No hay periodo estático inventado. Los valores son los textos devueltos por tablas CSI, con su resolución de salida; no se atribuye precisión mayor ni se aplican límites normativos. Configuración, respuesta, mapeo y copia EDB se conservaron con huellas.

La tercera corrida `28f6d928fac949acadd19f294e6bf644` terminó en modo real, instancia propia 15888: caso EST estado 4, EDB guardado SHA256 `fb3c1743e674f41a887317797452d89c94dfc8015c660d8e3af39567b2a618aa`, aceptación_analisis.json presente. `trabajo_motor.LOG` informa análisis completo y cero autovalores negativos en la comprobación básica. También muestra el caso auxiliar ~LLRF generado por ETABS; no se atribuye a un caso solicitado del usuario. Un estado completo y un chequeo básico no acreditan toda la estabilidad o calidad del modelo. Las tablas/resultados todavía requieren lectura, correspondencias y revisión.
