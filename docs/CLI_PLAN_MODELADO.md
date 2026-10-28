# Plan geométrico desde el comando principal

El plan desarrollado en `plan_modelado.py` puede generarse desde la CLI del proyecto:

```powershell
.\.venv\Scripts\python.exe -m draft2model plan-modelado --entrada examples/geometria_sintetica.json --salida tmp/plan_geometrico.json
```

La carpeta de salida debe existir y el nombre debe ser nuevo. Para repetir el comando se elige otro nombre. El comando integrado no ofrece una opción para sobrescribir archivos.

## Entrada y resultado

La entrada es un contrato `draft2model.geometria`, con nodos, niveles y muros. Una extracción de lecturas, incluso revisada, no sustituye este contrato: todavía faltan la definición de relaciones espaciales, escala y conversión revisada a geometría.

El ejemplo produce superficies M1, M2 y M3; M4 queda omitido por su espesor desconocido. El resultado es una propuesta parcial en metros, con huella del contenido geométrico de origen. `ejecutable_en_etabs` permanece `false` y `aprobacion_plan` permanece `null`.

Los estados de origen, cobertura y bloqueos se muestran en la terminal. Un código 0 indica que se guardó el plan, no que esté completo, aprobado o disponible para análisis. La aprobación de la geometría no se convierte en aprobación del plan.

| Código | Resultado |
| --- | --- |
| 0 | Plan guardado; puede contener omisiones y bloqueos explícitos. |
| 1 | Operación no completada: entrada ilegible, error de cálculo, salida existente, carpeta ausente, entrada modificada durante el cálculo o fallo de escritura. |
| 2 | Se guardó un diagnóstico de geometría inconsistente, sin superficies. También es el código de argparse para argumentos incompletos. |

## Conservación de archivos

La integración usa `archivo_plan.py`, separado del módulo puro. Comprueba la huella de los bytes de entrada antes y después del cálculo, escribe un temporal completo en la carpeta de salida y vuelve a comprobar la entrada antes de publicar.

En Windows publica mediante `os.rename`, que rechaza un destino existente. En otros sistemas usa un enlace duro exclusivo. No se usa `os.replace`: un destino creado por otro proceso durante el cálculo también queda protegido. Si el sistema de archivos no permite la operación, se informa el error, sin recurrir a sobrescritura ni dejar un archivo de salida parcial. Los temporales se eliminan ante errores normales de E/S; un cierre abrupto del proceso puede dejar un temporal `.plan-*.tmp`.

No hay bloqueo del sistema de archivos frente a ediciones externas posteriores a la última comprobación. La procedencia del plan se identifica por la huella del contenido geométrico que se procesó. No se conserva una copia de la entrada dentro de este comando ni se registra una versión en un expediente privado.

La CLI independiente `python -m draft2model.plan_modelado` sigue disponible con sus opciones originales. Esta integración usa un camino de escritura propio y no modifica sus archivos ni su opción `--sobrescribir`.

## Comprobaciones

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_cli_plan.py -v
```

Las pruebas comprueban reproducción exacta del ejemplo, conservación de entrada y salida, diagnóstico de datos inconsistentes, rechazo de lecturas como geometría, JSON ilegible, errores de cálculo/escritura y aparición concurrente de un destino. No requieren ETABS ni red. Las pruebas geométricas del plan se ejecutan por separado y en la suite completa.

El controlador separa esta entrega del adaptador, materiales, cargas, masa y comparación con una referencia. Los datos sintéticos prueban software; no validan el piloto.
