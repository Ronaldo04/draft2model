# Demostración integrada reproducible sin red ni ETABS

La demostración ejecuta los módulos locales reales de ingreso, revisión de lecturas, conversión, versiones geométricas, planes, configuración estructural, contratos de resultados, evaluación, citas, informe y registro SQLite. **Los datos, revisores, aprobaciones y resultados son fabricados para probar software.** No llama un proveedor de IA, no crea un modelo ETABS y no ejecuta un análisis estructural.

Las aprobaciones del ejemplo son declaraciones sintéticas identificadas como tales. No corresponden a una revisión técnica real ni acreditan competencia del revisor. El informe final queda en **borrador**, sin aprobación documental propia. Los números y límites de las fixtures carecen de valor normativo.

## Preparación y ejecución

Usar el entorno del proyecto con sus dependencias instaladas según la guía principal. Desde la raíz:

```powershell
.\.venv\Scripts\python.exe -m examples.flujo_integrado_sintetico --salida data/demo_integrada_001
```

`--salida` debe indicar una carpeta completamente nueva. Si existe, el comando falla antes de modificarla. Para otro ID:

```powershell
.\.venv\Scripts\python.exe -m examples.flujo_integrado_sintetico --salida data/demo_integrada_002 --caso otro-caso-sintetico
```

No requiere claves API, licencia de ETABS, servidor, navegador ni red. Usa PyMuPDF para crear y exportar PDF y SQLite de la biblioteca estándar. No instala dependencias durante la ejecución.

## Recorrido

1. Reutiliza `examples.conversion_sintetica.crear_demo.main`: crea un PDF sintético, registra su expediente fuera del MVP, prepara evidencia, importa cuatro lecturas fabricadas y guarda sus revisiones. Las cotas declaradas son 260 cm de altura, 400 cm de longitud y 15 cm de espesor. La conversión usa el manifiesto explícito del ejemplo; no deduce metros desde píxeles.
2. Importa la geometría convertida de un muro A-B entre N0 y N1. Crea una revisión hija en borrador y registra una aprobación geométrica **SIMULADA** sobre su huella exacta. Conserva las versiones anteriores y genera un plan geométrico versionado. El área bruta es 4 × 2.6 = 10.4 m²; el plan sigue sin aprobación propia y con `ejecutable_en_etabs: false`.
3. Crea un corpus PDF sintético de tres páginas para probar citas de periodo, deriva y cortante. Lo vincula por hash, aprueba el corpus como fixture y recupera sus tres fragmentos mediante el recuperador léxico local. No se presenta ese texto como norma real.
4. Adapta la configuración estructural de ejemplo al único muro: cuatro puntos, referencias exactas a la geometría aprobada, apoyos/asignaciones y diafragma declarados. Su fuente y su plantilla declarativa apuntan a archivos sintéticos con SHA256 reales. La plantilla es una **descripción JSON de prueba**, no una plantilla ETABS ejecutable ni un modelo calibrado. La configuración lleva una aprobación fabricada sobre `huella_configuracion`. El validador comprueba su vínculo con la geometría vigente; `apto_para_adaptador` expresa consistencia de infraestructura y no ejecución ni validez de ingeniería.
5. Registra una corrida de análisis con `motor.tipo: "simulacion"` y `datos_sinteticos: true`. Copia valores fabricados: periodo 0.5 s para MOD, deriva 0.002 para EX y cortante basal 100 kN para EX. Los casos EST/MOD/EX y COMB1 no se ejecutaron: esta omisión queda explícita. No existe archivo `.edb` ni evidencia de terminación de un solver.
6. Evalúa esos datos contra las reglas sintéticas aprobadas por hash. Conserva fuente/edición/apartado, aplicabilidad y huellas. La satisfacción de estas reglas fabricadas solo verifica el código.
7. Crea un informe JSON/HTML/PDF en borrador con las cifras y citas verificadas. Las siete secciones del informe distinguen geometría comprobada, resultados declarados, estado del análisis no acreditado y faltantes. El sitio se declara ausente; no se infiere estudio de suelos ni condición de sitio.

## Archivos y trazabilidad

```text
demo_integrada_001/
  DEMO.json
  private/
    corridas.sqlite3
    fuentes-demo-integrada-sintetica/      # entradas iniciales del helper
    demo-integrada-sintetica/
      expediente.json
      originales/
      extracciones/                      # originales y revisiones inmutables
      conversiones_geometria/             # manifiesto, exportación y trazas
      geometrias/                        # importación, revisión y aprobación simuladas
      planes/                            # propuesta geométrica sin ETABS
      resumen_demo.json
      demo/
        fuentes/                         # PDF, corpus por hash y citas
        plantilla_fixture.json
        configuracion.json
        comprobacion_configuracion.json
        resultados_simulados.json
        reglas_sinteticas.json
        evaluacion.json
        contexto_informe.json
        informe_borrador/
          informe.json
          informe.html
          informe.pdf
```

`resumen_demo.json` registra IDs de extracción, conversión, versiones geométricas, plan, configuración y seis corridas SQLite. Cada corrida conserva hashes de entradas y salidas y completa la transición preparada → en_ejecución → completada. Las etapas registradas son preparación, geometría, modelo, análisis, evaluación e informe.

La fase de creación/conversión inicial ocurre dentro del helper antes de que exista el caso; la corrida `preparacion` registra **su comprobación posterior**, no atribuye al registro la ejecución previa ni simula tiempos de una llamada de visión. El helper no realiza llamadas de IA.

Los resultados conservan `geometria.id` como ID de versión y `geometria.sha256` como hash de los bytes de `geometria.json`. `configuracion.sha256` es la huella canónica de configuración sin `revision`. El resumen conserva ambos artefactos con hashes de archivo adicionales. El hash del contenido y el hash de los bytes tienen propósitos distintos y no se intercambian.

Las entradas de las fases posteriores incluyen el original, el expediente, versiones de lecturas y trazas de conversión, ascendencia geométrica, corpus, fuente, plantilla y configuración que correspondan. Esto vincula las salidas con los archivos verificados, además de los hashes internos de cada contrato.

## Volver a comprobar

```powershell
.\.venv\Scripts\python.exe -m examples.flujo_integrado_sintetico --salida data/demo_integrada_001 --verificar
```

Si se usó un caso diferente, incluir el mismo `--caso`. La comprobación consulta cada corrida, vuelve a calcular sus hashes, verifica versiones y evidencia de lecturas/geometría, comprueba el plan y la configuración, las fuentes citadas y la consistencia del informe. Un original o una fuente citada alterados invalida la reutilización; no se actualizan huellas ni aprobaciones automáticamente.

Leer únicamente el PDF guardado no comprueba de nuevo los archivos fuente. Es un artefacto estático: antes de reutilizarlo debe ejecutarse la verificación anterior. Los hashes y revisores declarados no protegen contra un actor local que reescriba todos los registros y artefactos.

## Métricas y límites

El resumen registra tiempos de software con reloj monotónico, el tiempo hasta terminar la exportación, cero llamadas de IA reales y cero ejecuciones ETABS. No declara ahorro de tiempo humano, costo de IA ni desempeño estructural. Esos campos permanecen `null` cuando corresponden a una medición no realizada. El tiempo de la última exportación incluye generación JSON/HTML/PDF; los tiempos dependen del equipo. No hay un objetivo de rendimiento estructural derivado de esas medidas.

Si una etapa falla, se conserva la carpeta parcial para diagnóstico y, cuando ya existe su corrida, se marca fallida. No se emite resumen de éxito ni se elimina trabajo. El ejemplo no recupera automáticamente una ejecución parcial ni reconcilia procesos externos.

Para repetir o hacer rollback, conservar la carpeta anterior como evidencia y ejecutar con una carpeta nueva. Para descartar una prueba, identificar primero su carpeta de salida y retirarla manualmente cuando ya no se necesite. El script no borra carpetas, no modifica expedientes ajenos y no sobrescribe informes o versiones.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p test_flujo_integrado.py -v
```

Cuatro pruebas comprueban el recorrido y sus cifras/citas/hashes/PDF/SQLite, repetición en carpeta nueva y conservación de la anterior, invalidación por cambio del plano original e invalidación por cambio de la fuente citada. El recorrido principal se ejecuta con creación de sockets bloqueada para detectar intentos de red. En Windows el sandbox puede impedir renombrados atómicos de carpetas: la suite se validó fuera de ese sandbox usando exclusivamente carpetas temporales sintéticas. Esto no acredita resultados ETABS, IA real ni una vivienda de obra.
