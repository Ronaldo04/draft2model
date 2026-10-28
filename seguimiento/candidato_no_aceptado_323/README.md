# Draft2Model

Asistente local para convertir planos estructurales en datos revisables, modelos ETABS e informes preliminares trazables.

**Corte323, 24 de octubre de 2026.** La entrega322 integró la estimación opcional de peso efectivo de vigas y completó lectura, creación y reapertura del informe real, conservando el EDB y el contraste bruto. Este corte reduce el coste de una captura binaria efímera de geometría, conservando la comparación completa y el fallback JSON ante diferencias. La validación de cada ZIP se identifica por su huella en VALIDACION.json junto al paquete: no atribuir automáticamente la suite anterior al código nuevo. El benchmark humano y la aceptación global siguen pendientes.

**El objetivo global continúa abierto:** falta una referencia humana completa para el benchmark de extracción, y un piloto no demuestra soporte validado para cualquier construcción. Permanecen las hipótesis de suelo/sistema, la discrepancia de masa y las comparaciones no satisfactorias. La comparación con el modelo manual está aplazada por el usuario y no condiciona el cierre actual. La [matriz de requisitos](../../docs/MATRIZ_REQUISITOS_REFERENCIA.md) y el resumen de validación externo al ZIP delimitan cada evidencia; las tablas históricas inferiores no sustituyen este corte.

## Comenzar

Abrir PowerShell en esta carpeta y conservar el entorno `.venv` existente:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m draft2model --help
.\.venv\Scripts\python.exe -m draft2model demo-integrada --salida tmp/demo_NUEVA
.\.venv\Scripts\python.exe -m draft2model demo-integrada --salida tmp/demo_NUEVA --verificar
```

La primera creación exige una carpeta nueva; la segunda operación comprueba sus artefactos. La demo usa documentos, revisores, aprobaciones y resultados **sintéticos**: no llama a IA ni calcula ETABS. La [guía reproducible](../../docs/GUIA_REPRODUCIBLE.md) explica instalación offline, rutas, interfaz y uso de módulos.

Para abrir la aplicación, ejecutar **Abrir revision de planos.cmd** o:

```powershell
.\.venv\Scripts\python.exe -m draft2model.revision_visual --raiz data/private --puerto 8766
```

El servidor escucha en loopback y abre el navegador. Detenerlo con Ctrl+C. El acceso a ETABS y los envíos al proveedor son operaciones deliberadas posteriores; abrir la pantalla no los inicia.

## Capacidades y límites actuales

| Etapa | Disponible | Falta acreditar o integrar |
| --- | --- | --- |
| Ingreso y preparación | PDF/JPG/PNG autorizados, originales con hashes, páginas, recortes raster/PDF y paquetes visuales; carga y preparación web; fotografías derivadas (perspectiva/contraste) trasladables a paquetes. | Ingreso y trazabilidad comprobados en el caso Pueblo Libre; no se dispone de referencia humana completa para medir precisión de extracción. |
| Visión y geometría | Respuestas locales; **solo Google (Gemini) y OpenAI** son proveedores operativos autorizados, y exclusivamente para revisión y extracción estructurada de planos (preparación, envío y recuperación deliberados). Conversión web mediante correspondencias físicas explícitas; CSV/XLSX supervisado; superposición geometría↔plano. Los adaptadores Anthropic y compatible con Chat Completions solo se conservan para la lectura de la historia y las pruebas con dobles: la UI, la CLI y el servicio real los rechazan. ETABS usa su API local, sin clave. | Hay llamadas reales autorizadas: OpenAI 4 de 5 y Gemini 2 de 5 consumidas. La extracción requirió revisión, calibración e incorporación de datos declarados; no acredita lectura autónoma de cualquier proyecto ni precisión medida contra una referencia humana completa. |
| Versiones y ETABS | Geometría/configuración versionadas, revisión propia del modelo, construcción, análisis, lectura y normalización; confirmaciones y recuperación separadas. | Caso real construido y analizado mediante el flujo CLI/servicios. Pendientes la aceptación integral de interfaz y la revisión de ingeniería. El contraste oficial de masa conserva el estado no_coherente; la causa principal está identificada, sin alterar tolerancias para aprobar. |
| Resultados y entrega | Contratos, evaluación configurable, corpus/citas, sitio referencial (con franja de proximidad), panel e informe JSON/HTML/PDF, corridas SQLite. Integrados en HTTP/UI e informe: aprobación documental, contexto, explicaciones sustentadas o contingencia, revisión declarada de resultados y controles postsolver opcionales. | 13 indicadores reales y 18 evaluaciones de escenarios comprobados; 8 satisfacen y 10 no. Los informes corregidos y sus18evaluaciones ya se contrastaron con el caso real; la distribución final requiere su propia aceptación. Faltan EMS, clasificación profesional del sistema y sitio referencial. El log completo del solver no se extrae automáticamente. |
| Reproducibilidad | Dependencias fijadas, wheels locales con hashes, demo y verificadores; `python -m draft2model.preflight` valida instalación, rutas, permisos y la API local de ETABS. | Las copias limpias anteriores son históricas. Instalación offline287: 6/6 pasos sobre fuentes285; falta validar y empaquetar la huella final tras las correcciones actuales. |

Se procesan los **planos de referencia existentes aunque correspondan a otro sistema**, conservando su procedencia y una configuración técnica explícita. El alcance de validación original sigue siendo albañilería confinada de uno a dos niveles en Lima Metropolitana; procesar otra referencia no demuestra generalización a esa tipología. El piloto actual tiene cuatro intervalos de piso y datos revisados; su éxito no prueba generalización. Los otros dos proyectos aportados permanecen sin procesar por instrucción del usuario. La revisión de datos físicos y normativos sigue siendo explícita; el sistema no resuelve por sí solo información ausente en los planos.

Aprobar una lectura, geometría, configuración, modelo, mapeo o informe son actos distintos. Las identidades son declaradas; una aprobación documental no aprueba resultados ni acredita conformidad normativa. El producto no certifica seguridad, estima probabilidad de colapso, diseña reforzamientos ni deduce capacidad portante.

## Documentación vigente

| Documento | Uso |
| --- | --- |
| [Guía reproducible](../../docs/GUIA_REPRODUCIBLE.md) | Configuración, demo, interfaz y módulos. |
| [Accesos y proveedores](../../docs/ACCESOS_Y_PROVEEDORES.md) | Qué clave, licencia o archivo local hace falta; cómo darla al servidor sin persistirla; vías que transmiten datos. |
| [Cierre del desarrollo](../../docs/CIERRE_DESARROLLO.md) | Historia de la etapa del18de octubre; sus pendientes no son el estado actual. |
| [Matriz de requisitos de la referencia](../../docs/MATRIZ_REQUISITOS_REFERENCIA.md) | Alcance, evidencia y límites; su corte histórico se complementa con el resumen de validación de la distribución. |
| [Contexto del proyecto](../../docs/CONTEXTO_PROYECTO.md) | Alcance, arquitectura, contratos y definición de terminado. |
| [Retomar](../../docs/RETOMAR.md) | Estado operativo, responsables activos y siguiente integración. |
| [Control de avance](../../docs/CONTROL_AVANCE.md) | Catálogo y evidencias locales/publicadas; no es el panel estructural del producto. |
| [Ensayo ETABS dinámico](../../docs/ENSAYO_ETABS_DINAMICO.md) | Cálculo real con fixture sintética y límites de esa evidencia. |
| [Diagnóstico copia100](../../docs/DIAGNOSTICO_COPIA_100.md) | Fallos, omisiones y límites de entorno sin relajar comprobaciones. |

El [repositorio privado](https://github.com/Ronaldo04/draft2model) y los antecedentes se conservan; este estado local no afirma que todos los cambios estén publicados. Los documentos históricos del repositorio de desarrollo son SismoVivienda_AI_Desarrollo_Tecnico.pdf, SismoVivienda_AI_Entrega_Avance 01 - 03-10-2026.pdf y entregables/Draft2Model_One_Page.html; no se incluyen automáticamente en la distribución pública. La documentación operativa distribuida está en la tabla anterior. Sus asignaciones históricas no sustituyen la coordinación actual de Codex, Claude Desktop y subagentes.
