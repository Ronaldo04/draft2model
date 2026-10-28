# Derivación local de presión estática de líquidos

El módulo `draft2model.acciones_liquidos` deriva presiones y sus integrales sobre superficies planas de geometría0.3. Necesita nivel libre Z en metros, peso específico en kN/m³, origen de momentos XYZ y sentido de la normal (+1 o −1), todos explícitos y vinculados a fuentes con revisión declarada. No toma valores por defecto del agua ni de los planos.

La relación de presión manométrica es `p = gamma * max(0, nivel - z)` para un líquido estático de peso específico constante. Base física: [OpenStax, University Physics, 14.1](https://openstax.org/books/university-physics-volume-1/pages/14-1-fluids-density-and-pressure). El código integra fuerza y momento de esa presión lineal; la selección de condiciones del proyecto requiere revisión técnica propia.

El cálculo triangula el contorno simple, recorta cada triángulo por el nivel libre y resta las integrales de todas las aberturas de la superficie. Conserva vértices, procedencia, intersecciones calculadas, áreas, fuerzas, momentos y centro de presión. El centro es nulo si no existe fuerza. Las comprobaciones de área y finitud son numéricas, no tolerancias de ingeniería.

## Uso reproducible

```powershell
.venv/Scripts/python.exe -m draft2model acciones-liquidos --geometria geometria.json --declaracion declaracion.json --fuentes fuentes.json --salida derivacion.json
```

La geometría debe cumplir el contrato0.3 completo. `fuentes.json` es una lista de objetos `{id, contenido, revision}`; el contenido JSON debe ser explícito y no vacío. La revisión de cada fuente es `{estado: "revisado", declarada_por, fecha, motivo}`.

`declaracion.json` contiene exactamente `contrato: "draft2model.acciones_liquidos"`, `version_contrato: "0.1.0"`, `id`, `nivel_libre_z_m`, `peso_especifico_kn_m3`, `origen_momentos_m`, `superficies` y `revision`. Cada selección de superficie contiene `{superficie, sentido_normal, fuentes}`. La revisión de la declaración añade la lista `fuentes` a los cuatro campos anteriores. Fechas ISO, referencias existentes y fuentes usadas son obligatorias.

La API Python es `declarar_acciones_liquidos(geometria, declaracion, fuentes)` seguida de `calcular_acciones_liquidos(geometria, vinculada, fuentes)`. La segunda vuelve a comprobar los hashes canónicos completos de geometría, declaración y fuentes: un cambio requiere nueva declaración. No modifica las entradas. La CLI rechaza JSON duplicado/no finito y nunca reemplaza una salida existente. Código0 indica derivación publicada; código2 indica rechazo.

## Alcance comprobado y pendiente

Diez pruebas sintéticas verifican solución analítica de pared vertical completa y parcial, hueco completo y parcialmente sumergido, fondo uniforme, normal invertida, cambio de origen, panel inclinado, concavidad, equivalencia m/cm/mm, fuentes cambiadas y publicación CLI. No usan red ni motor.

La derivación conserva `aplicado=false`, `ejecutable=false` y `aprobacion_ingenieria=null`. **Todavía falta su transporte como presión distribuida a ETABS y la lectura posterior de ese efecto.** Las resultantes no se aplican como cargas puntuales sustitutas. No implementa hidrodinámica, impulsivo/convectivo, suelo, flotación, apoyos ni diseño de cisterna/tanque. Tampoco demuestra que el caso de referencia aporte todas las condiciones necesarias.
