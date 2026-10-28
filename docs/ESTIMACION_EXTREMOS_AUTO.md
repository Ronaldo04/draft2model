# Estimación opcional del peso efectivo de vigas

Esta función experimental calcula un descuento de peso a partir del plan de operaciones validado y de la configuración capturada en ETABS. Conserva el libro bruto y su contraste nativo. Un contraste estimado coherente no aprueba el modelo, sus hipótesis, el cumplimiento normativo ni la distribución de masa por piso.

## Uso en la interfaz

1. Seleccionar un análisis real aceptado y vigente.
2. En la lectura, seleccionar masa ensamblada y la opción de configuración Auto. Confirmar y ejecutar la lectura. No se recalcula el modelo.
3. En el informe, incluir la masa nativa de esa lectura y seleccionar la estimación Auto. La configuración debe proceder de la misma captura aceptada.
4. Crear el informe. Revisar por separado el contraste bruto, el estimado, los descuentos por viga y las abstenciones. Cambiar la selección invalida el informe preparado.

La opción está desactivada por defecto. Sin ella se conserva el comportamiento anterior. No requiere llamadas a OpenAI o Google. El lector usa una instancia nueva de ETABS y cierra únicamente la suya, sin guardar el modelo analizado.

## Uso por CLI

El generador de informes admite `--estimar-auto` junto con `--masa-nativa-lectura <id>`. La lectura aceptada debe contener `AssembledJointMass` y `ConfiguracionAuto`; se verifican el análisis, EDB, versión, unidades, expediente y huellas. Consulte las demás opciones con:

```powershell
python -m draft2model.informe --help
```

Para examinar únicamente la predicción del plan, sin abrir ETABS:

```powershell
python -m draft2model.estimacion_extremos_auto --plan plan.json --configuracion configuracion_auto.json --salida prediccion_nueva.json
```

La configuración de este último comando contiene `etabs_version`, `unidades`, `tolerancia_union_m`, `procedencia_tolerancia` y `vigas`. No es la configuración estructural completa. El flujo de informe obtiene estos valores de una captura nativa verificada, en lugar de aceptar que el usuario atribuya procedencia verificada a un archivo arbitrario.

## Perfil y cálculo

El perfil observado corresponde a ETABS 21.1.0, unidades `kN_m_C`, columnas rectangulares verticales con ejes locales de 0/90 grados y vigas cubiertas por las comprobaciones geométricas del núcleo. La cara de la columna inferior se proyecta sobre la dirección de la viga. Se ensayaron tolerancias de unión de 0,001 y 0,005 m; los casos cortos se limitan a la regla observada. Otros casos producen abstención cuando no hay evidencia suficiente. No se promete soporte universal para otras versiones, secciones o geometrías.

La masa estimada es la masa bruta menos el descuento independiente de peso multiplicado por el factor efectivo de peso propio de los patrones y dividido entre la gravedad configurada. Se conserva la tolerancia del contraste bruto. El perfil se abstiene si incluye masa propia directa adicional, cobertura incompleta o condiciones globales no cubiertas. No toma los offsets ni el peso nativo como entradas de predicción.

El contraste reutiliza la captura completa de masa: una coincidencia del total no convierte en éxito errores de ejes, fuente o datos. La exportación vuelve a comprobar las fuentes y recalcula la sección. El informe identifica el plan, configuración capturada, versión del núcleo, cobertura y motivos de abstención.

## Evidencia y límites del piloto

Antes de integrar el flujo, la predicción independiente coincidió en los 90 extremos de las 45 vigas del primer piloto: descuento de 6,86124 kN. Las pruebas de transporte del software y los ensayos sintéticos no constituyen aprobación de ingeniería. El contraste bruto conserva su discrepancia y queda un residuo de aproximadamente 0,0069 kN en CM sin atribuir.

El informe de validación de cada distribución debe indicar si el recorrido integrado real terminó satisfactoriamente; no atribuir esa prueba por la sola existencia del módulo. Se mantienen las comprobaciones estructurales no satisfechas, ausencia de EMS y benchmark humano pendiente.
