# Guía reproducible de Draft2Model

Corte323,24de octubre de2026: conserva la [estimación opcional de peso efectivo Auto](ESTIMACION_EXTREMOS_AUTO.md) de322 y optimiza la captura efímera de geometría, manteniendo comprobación completa y fallback. La instalación offline303 y su entorno se pueden reutilizar si lock y wheels siguen idénticos. Consultar VALIDACION.json junto al ZIP para conocer las comprobaciones de su huella exacta. Esta guía distingue demo, dobles, ensayos nativos sintéticos y piloto real; el benchmark humano y la aceptación global siguen abiertos. [RETOMAR](RETOMAR.md) corresponde al seguimiento del repositorio de desarrollo.

## 1. Entorno existente y archivos necesarios

Abrir PowerShell en la carpeta del proyecto. Usar Windows x64 y CPython 3.10; la instalación registrada utiliza 3.10.5. Conservar `.venv` si ya existe. No se necesita activar el entorno: los comandos usan su ejecutable explícito.

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m draft2model --help
```

Las dependencias actuales son PyMuPDF 1.28.2 y Pillow 12.3.0; SQLite y el lector XLSX limitado usan la biblioteca estándar. No hay una instalación automática de ETABS ni de credenciales. Los originales privados y `tmp/` no forman parte de una distribución de fuentes: preservar por separado los expedientes autorizados y sus artefactos necesarios.

### Instalación offline en otra carpeta nueva

Esta estación conserva los dos wheels en `tmp/wheels_clean_001`. `requirements-win-py310.lock` fija sus hashes para Windows x64/CPython3.10. Si esa carpeta no está en una copia del proyecto, aportar ambos wheels compatibles por un medio autorizado; no sustituir el lock ni afirmar que la distribución incluye los temporales.

```powershell
.\.venv\Scripts\python.exe scripts/verificar_instalacion_limpia.py --wheels tmp/wheels_clean_001 --salida tmp/instalacion_NUEVA
```

El script crea `tmp/instalacion_NUEVA/v`, instala con `--no-index --require-hashes`, comprueba dependencias/CLI y crea/verifica la demo. No cambia `.venv` ni usa red. Consultar `tmp/instalacion_NUEVA/verificacion.json` y sus logs; un error o informe incompleto no acredita instalación. La instalación vigente verificada es la **129** (`tmp/instalacion_129/verificacion.json`, [verificación de instalación](VERIFICACION_INSTALACION_ACTUAL.md)): seis pasos correctos en un entorno aislado. `tmp/inst19` queda como antecedente.

Para una máquina sin entorno previo, desde un Python3.10 x64 ya instalado:

```powershell
python -m venv .venv_nueva
.\.venv_nueva\Scripts\python.exe -m pip install --no-index --find-links tmp/wheels_clean_001 --require-hashes -r requirements-win-py310.lock
.\.venv_nueva\Scripts\python.exe -m pip check
```

Usar una carpeta de entorno que no exista. Para otra plataforma/Python hay que preparar distribuciones y hashes compatibles; este lock no los acredita. Ningún secreto se guarda en los ejemplos, la configuración versionada o el chat.

## 2. Demo integrada sin proveedor ni ETABS

```powershell
.\.venv\Scripts\python.exe -m draft2model demo-integrada --salida tmp/demo_NUEVA
.\.venv\Scripts\python.exe -m draft2model demo-integrada --salida tmp/demo_NUEVA --verificar
```

La creación exige carpeta nueva. La verificación reutiliza esa carpeta y comprueba entradas, versiones, fuentes, contratos y corridas; no regenera huellas para aceptar archivos alterados. Ambos comandos deben concluir correctamente. La demo no usa red, claves, licencia ni procesos ETABS: sus valores y aprobaciones están fabricados y el informe queda en borrador.

| Ruta bajo `tmp/demo_NUEVA` | Contenido |
| --- | --- |
| `DEMO.json` | Identificación y resumen de la demostración. |
| `private/corridas.sqlite3` | Seis etapas de software registradas, no seis análisis estructurales. |
| `private/demo-integrada-sintetica/resumen_demo.json` | Versiones, referencias, huellas y tiempos de software. |
| `private/demo-integrada-sintetica/demo/` | Configuración, resultados simulados, reglas, fuentes/citas y evaluación. |
| `private/demo-integrada-sintetica/demo/informe_borrador/` | `informe.json`, `informe.html`, `informe.pdf`. |

Abrir HTML/PDF desde la última carpeta. Para generar imágenes de revisión visual en otro destino nuevo:

```powershell
.\.venv\Scripts\python.exe scripts/renderizar_informe.py --pdf tmp/demo_NUEVA/private/demo-integrada-sintetica/demo/informe_borrador/informe.pdf --salida tmp/qa_informe_NUEVA
```

[DEMO_INTEGRADA](DEMO_INTEGRADA.md) detalla cada paso y sus límites. El PDF es una instantánea; antes de reutilizarlo, volver a verificar el expediente completo.

## 3. Iniciar la revisión local

Ejecutar **Abrir revision de planos.cmd** o, desde PowerShell:

```powershell
.\.venv\Scripts\python.exe -m draft2model.revision_visual --raiz data/private --puerto 8766
```

El servidor escucha solo en loopback y abre el navegador. `--sin-navegador` conserva el servidor sin abrir una pestaña. **Para un envío real a un proveedor de IA**, fijar la clave y arrancar el servidor en la **misma consola de PowerShell**: el `.cmd` inicia otro proceso y no hereda la variable. El método para PowerShell 5.1 y 7, sin persistir la clave, está en [accesos y proveedores](ACCESOS_Y_PROVEEDORES.md) §3. Mantener la consola activa y detener con Ctrl+C. Si el puerto está ocupado, elegir otro; no reutilizar PIDs/puertos de registros históricos como si fueran procesos propios actuales.

Para consultar la demo en otra sesión, cambiar la raíz a `tmp/demo_NUEVA/private` y elegir un puerto libre. No confundir ese expediente sintético con los datos del usuario. Los controles de sesión/origen/Host del servidor son locales; no equivalen a un sistema multiusuario desplegado.

## 4. Recorrido del operador

1. **Ingresar originales:** seleccionar PDF/JPG/PNG y declarar autorización. Para la muestra de referencia conservar su condición fuera del alcance original si corresponde. La carga admite hasta 20 archivos, 16 MiB cada uno y 48 MiB total; no acepta rutas del equipo ni sobrescribe casos. Un PDF ilegible conserva error documental visible.
2. **Preparar evidencia:** revisar documento, elegir archivo/página y región normalizada, conservar recortes y seleccionar paquete. Raster aplica orientación EXIF y registra píxeles; PDF usa su espacio de página. Para fotografías, el panel permite registrar perspectiva/contraste como versión derivada y trasladar un recorte al paquete conservando su transformación y vínculo con el original. Revisar la configuración en píxeles almacenados: no se infiere escala física ni se acredita mejora de precisión. Consultar [preprocesamiento web](REVISION_PREPROCESAMIENTO_WEB.md).
3. **Respuesta local o proveedor:** la respuesta local declara proveedor/modelo sin acreditar envío externo. El proveedor permite preparar sin clave/red y exige modelo/opciones explícitos. Enviar es otra acción con confirmación y eventual costo, usando la variable de credencial del **proceso servidor** (`OPENAI_API_KEY` o `GEMINI_API_KEY`). **Solo Google y OpenAI** son operativos, y exclusivamente para revisión/extracción de planos; Anthropic y el modo compatible no se ofrecen en el recorrido real. Ver [accesos y proveedores](ACCESOS_Y_PROVEEDORES.md). La prueba real se reserva a la etapa final acordada; no pegar claves en la UI o el chat.
4. **Vincular y revisar:** un trabajo de proveedor completado/verificado puede vincular su respuesta; importar esa respuesta al historial de extracciones es otra acción. Revisar/corregir candidatos crea versiones; los datos continúan pendientes de aprobación de ingeniería. Las pruebas sintéticas no se trasladan silenciosamente a expedientes reales.
5. **Convertir:** seleccionar extracción revisada y declarar manifiesto físico completo con ejes, unidades, escala y correspondencias. Crear conversión y luego confirmar importación de geometría borrador. No se rellenan coordenadas, conectividad o dimensiones desconocidas. Consultar [conversión web](REVISION_CONVERSION_WEB.md).
6. **Geometría/configuración:** revisar y aprobar versiones exactas mediante sus controles propios. CSV/XLSX es contingencia supervisada; XLSX no ejecuta fórmulas. La configuración técnica declara materiales, cargas/masa, apoyos/diafragmas, sitio, idealización y casos; sus valores no se deducen de una aprobación geométrica.
7. **Modelo/análisis:** preparar construcción sin motor, comprobar el trabajo y confirmar crear una copia. Revisar el modelo mediante sus controles propios antes de seleccionar su aprobación y confirmar análisis. Construcción, análisis y lectura comparten exclusión; consultar historial no relanza. Esta vía web se probó con dobles; no equivale al ensayo real CLI previo.
8. **Lectura y correspondencias:** confirmar lectura deliberada del modelo aceptado, elegir tablas/casos y trasladar internamente a mapeo. Declarar campos, filtros, dirección, ubicación y unidades; revisar y aprobar el mapeo antes de normalizar. Aprobar correspondencias no aprueba los resultados.
9. **Panel e informe:** seleccionar resultado vigente y evidencia de análisis cuando exista. Registrar corpus, reglas y sitio declarados; seleccionar sus derivados exactos para el mismo caso/resultado. Las explicaciones sin clave quedan en contingencia determinística y el texto propuesto exige revisión humana. El panel de revisión propia permite registrar una declaración con controles y faltantes explícitos; seleccionar después su versión vigente, sin elección automática. En el formulario de informe, activar expresamente las referencias de contexto, explicación o revisión declarada que se quieran vincular. La revisión exige el análisis exacto y conserva advertencias y omisiones; el estado nativo del resultado sigue pendiente. Generar otra versión y descargar. La aprobación documental crea una hija ligada al informe exacto; no aprueba resultados ni conformidad normativa. Consultar [informe con contexto](INFORME_CONTEXTO_EXPLICACION.md), [revisión de resultados en informe](INFORME_REVISION_RESULTADOS.md) y [ensayo de interfaz](ENSAYO_INTERFAZ_CONTEXTO.md). Los encabezados separados de su contenido detectados en el ensayo122 se corrigieron y verificaron; véase [paginación](REVISION_PAGINACION_INFORME.md).

10. **Contraste espacial geometría↔plano:** en «Esquema por nivel y contraste con el plano original», elegir geometría y nivel. Sin anclas solo se dibuja el esquema métrico, con la advertencia de que no está alineado. Para superponer, declarar tres anclas no colineales (nodo, u, v de la página original), revisor, fecha, motivo y confirmación. Cada versión corregida exige una correspondencia nueva. La superposición no prueba que un elemento esté documentado y solo dibuja los muros del contrato. Consultar [superposición](REVISION_SUPERPOSICION.md).
11. **Controles postsolver:** en «Controles internos posteriores al análisis», elegir una lectura aceptada y declarar en JSON las tres familias, con aplicabilidad, criticidad, criterio y parámetros. No hay tolerancias por defecto. La fuente de avisos del solver es opcional y declarada; si falta, ese control queda `sin_datos`. Registrar, seleccionar la versión manualmente y revisar estados, fórmulas, valores y faltantes. CSI 4 no equivale a controlado. En el informe, activar «Incorporar los controles…» solo con el mismo análisis. Consultar [controles](CONTROLES_ANALISIS.md).
12. **Contingencia tabular web:** adjuntar los metadatos del contrato geométrico y tres CSV exactos o un XLSX, registrar una versión borrador y, en otra acción confirmada, importarla al historial geométrico. Consultar [tabular](REVISION_TABULAR_INTERFAZ.md).

Las guías [preparación](REVISION_PREPARACION_WEB.md), [respuestas](REVISION_RESPUESTAS_WEB.md), [proveedor](REVISION_PROVEEDOR_INTERFAZ.md), [vínculo](VINCULO_PROVEEDOR_REVISION.md), [lectura](REVISION_LECTURAS_WEB.md), [mapeos](REVISION_MAPEOS.md), [paneles](REVISION_PANELES.md) y [aprobación documental](REVISION_APROBACION_INFORME.md) precisan contratos y límites. Algunas páginas conservan estados históricos: prevalecen la matriz vigente y la evidencia de la integración correspondiente.

Corpus, sitio, reglas y explicaciones están conectados a HTTP/UI e informe mediante selección explícita. El ensayo122 creó y comprobó un informe con esas referencias en el navegador usando datos sintéticos y contingencia sin LLM. Las pruebas focales están registradas en RETOMAR; la omisión histórica de enlaces del backend de contexto y la copia global100 fallida conservan su condición pendiente. Esta integración no acredita extracción real, precisión del texto, conformidad normativa ni un LLM externo.

## 5. Comandos por módulo

El punto de entrada es `python -m draft2model`; usar el Python de `.venv` como arriba. Cada comando conserva `--help`; no ejecutar una operación ETABS de escritura/análisis solo para probar el arranque.

| Etapa | Comando y guía |
| --- | --- |
| Documentos/recortes | `ingresar`, `revisar`, `recortar`; [ingreso](INGRESO_EXPEDIENTES.md), [raster](RECORTES_RASTER.md). |
| Fotografía derivada | `preprocesar`; [preprocesamiento](PREPROCESAMIENTO.md), [integración de recortes/paquetes](REVISION_PREPROCESAMIENTO_WEB.md). |
| Visión | `preparar-vision`, `preparar-openai`, `registrar-respuesta-vision`; [CLI visual](CLI_VISION.md). El envío CLI no está en el punto de entrada unificado: `python -m draft2model.proveedor_openai ejecutar --expediente … --plan … --autorizar-envio`, ver [conexión OpenAI](CONEXION_OPENAI.md). Vías de transmisión y claves: [accesos y proveedores](ACCESOS_Y_PROVEEDORES.md). |
| Lecturas/geometría | `importar/corregir/validar/exportar-extraccion`, `convertir-geometria`, `importar-tablas`; [conversión](CONVERSION_GEOMETRIA.md), [CSV/XLSX](IMPORTACION_TABULAR.md). |
| Versiones/planes | Comandos de geometría, `planes-versionados`, `plan-modelado`; [CLI geométrica](CLI_GEOMETRIA.md), [planes](PLANES_VERSIONADOS.md). |
| Configuración | `modelo-estructural`, `configuracion`; [modelo](MODELO_ESTRUCTURAL.md), [versiones](VERSIONES_CONFIGURACION.md). |
| ETABS | `etabs`, `plan-etabs`, `construir-etabs`, `revision-modelo`, `analizar-etabs`, `normalizar-etabs`; [CLI](CLI_ETABS.md), [análisis](ANALISIS_ETABS.md). |
| Evaluación/fuentes/sitio | APIs de [resultados/evaluación](RESULTADOS_EVALUACION.md), [fuentes](FUENTES_LOCALES.md), [sitio](SITIO.md). |
| Entrega/corridas | `panel-tecnico`, `informe`; [panel](PANEL_TECNICO.md), [informe](INFORME.md), [orquestación](ORQUESTACION.md). |
| Solo web/servicio (sin comando CLI propio) | Superposición `/api/superposicion/*`, controles postsolver `/api/controles/*`, tabular `/api/tabular/*`, revisión declarada de resultados `/api/revision-resultados/*`; [superposición](REVISION_SUPERPOSICION.md), [controles](CONTROLES_ANALISIS.md), [tabular](REVISION_TABULAR_INTERFAZ.md), [revisión de resultados](INTEGRACION_REVISION_RESULTADOS.md). Estado consolidado: [cierre del desarrollo](CIERRE_DESARROLLO.md). |

ETABS necesita instalación/licencia compatibles y un entorno donde el puente PowerShell esté autorizado. Consultar [adaptador](ADAPTADOR_ETABS.md) antes de operar: abrir copia, guardar, seleccionar tablas y analizar tienen efectos distintos. No se cambia ni elude la política del equipo para convertir una prueba bloqueada en éxito.

## 6. Verificación y reanudación

**Antes de operar ETABS o un proveedor:** `.\.venv\Scripts\python.exe -m draft2model.preflight --raiz data/private`. Comprueba la instalación, la DLL de ETABS y su versión verificada, PowerShell 5.1 y su directiva efectiva, los permisos, el presupuesto de rutas (límite 260) y la incertidumbre del motor, con una acción concreta para cada error. No inicia ETABS ni lee claves.

**Evidencia local de la ruta 201** (registros 198/200, plan 194 y ensayos `tmp/l2` y `tmp/r3`): `.\.venv\Scripts\python.exe scripts/verificar_evidencia_ruta201.py`. No forma parte de la suite porque `tmp/` no se distribuye.

Elegir pruebas focales según el cambio y sus guías. Los tests del navegador con Node usan DOM/HTTP simulados: no sustituyen inspección visual ni llamadas reales. No relanzar la suite completa por cada edición documental.

Cuando corresponda cerrar un hito integrado, los verificadores disponibles son:

```powershell
.\.venv\Scripts\python.exe scripts/verificar_proyecto.py --salida tmp/verificacion_NUEVA.json --temporales tmp/temporales_NUEVOS
.\.venv\Scripts\python.exe scripts/verificar_copia_limpia.py --python "$((Get-Location).Path)\.venv\Scripts\python.exe" --salida tmp/copia_NUEVA
```

Las salidas deben ser nuevas según el verificador. Consultar códigos, logs, estabilidad de fuentes, omisiones y bloqueos; un proceso iniciado o código0 aislado no basta. El verificador comprueba ejecución normal de scripts PowerShell mediante una sonda y no modifica políticas. La suite Python dispone de 3000 s y las pruebas JavaScript `tests/*frontend.cjs` de 300 s; la copia reserva 3600 s (presupuestos de observación ampliados en la ruta 201 por los puentes dobles PowerShell; no relajan pruebas). Un timeout no equivale a aprobación.

Para comprobar la interfaz hace falta Node.js como herramienta de desarrollo, aunque el servidor no lo necesita para arrancar. El verificador busca `node` en PATH; si se utiliza otro ejecutable local, añadir `--node RUTA_ABSOLUTA_NODE` a cualquiera de los dos comandos. Las pruebas de interfaz se ejecutan con el reporter TAP: un fallo, Node ausente, omisión o TODO impide `validacion_local_completa`. El informe conserva el inventario de comandos y su log separado `interfaz.log`. Esto verifica lógica con DOM simulado, además de la suite Python; la revisión visual del navegador sigue siendo otra comprobación.

**Evidencia histórica (ruta 201, 21 de octubre de 2026; no acredita las fuentes actuales):**
- **Copia limpia `tmp/c201b/copia_limpia.json`:** `completa: true`, código 0, sin red ni ETABS, ejecutada con el Python aislado 129.
  - 1160 pruebas Python y 30 archivos Node correctos, **sin omisiones**, con fuentes estables y sonda PowerShell `-File` correcta.
  - El único cambio posterior a esa copia es la redacción del estado aprobado en `configuracion.js`, cuyas pruebas Node se repitieron en verde.
- **Instalación offline `tmp/instalacion_201`:** 6 de 6 pasos correctos (entorno, wheels con hashes, `pip check`, arranque, demo y verificación).
- **Antecedente inmediato:** la copia `tmp/c201` falló con 4 fallos, 2 errores y 2 omisiones (expectativas antiguas de proveedores y explicaciones, esquema observado no registrado de la tabla no uniforme, y pruebas que dependían de `tmp/`). Se corrigió antes de la 201b.
- La copia 146/148 (850 Python, 26 Node) acredita solo el árbol de entonces.

**Antecedentes:** la copia 068 precede a varios módulos. La copia 100 falló con 18 fallos, 4 errores y 9 omisiones; [DIAGNOSTICO_COPIA_100](DIAGNOSTICO_COPIA_100.md) conserva su clasificación.

Para retomar: leer [RETOMAR](RETOMAR.md), comprobar propietarios antes de editar y consultar el último registro/artefacto terminal, sin sondear continuamente ni relanzar una operación incierta. Recuperar explícitamente o conservar el bloqueo y pedir solo el dato/acción imprescindible. Las claves de OpenAI y Google ya están configuradas localmente; no deben incluirse en la distribución. No hay autorización para usarlas fuera de lectura de planos. La comparación manual está aplazada; la revisión profesional sigue pendiente. No repetir llamadas por reanudar el trabajo. No declarar completado el piloto por una demo o fixture.


## 7. Ruta 201: malla, líquidos opcionales y referencia completa

- **Configuración 0.4 (malla)** y **0.5 (líquidos opcionales)**:
  - Generar un borrador sin datos inventados con `python -m draft2model.plantilla_configuracion borrador --raiz data/private --caso C --geometria V [--version 0.5.0] --salida cfg.json`.
  - Ligar a la geometría la declaración revisada de bordes conectados con `... conexiones --entrada bordes.json --salida cx.json`; las huellas se calculan solas.
  - Importar y revisar en el editor web. «Consultar preparación de malla» lista los nodos derivados, las subdivisiones y los cortes; la exportación sirve de plantilla de la política.
  - Guías: [INTEGRACION_MALLA_ETABS](INTEGRACION_MALLA_ETABS.md), [CONFIGURACION_MALLA_WEB](CONFIGURACION_MALLA_WEB.md) y [LIQUIDOS_OPCIONALES](LIQUIDOS_OPCIONALES.md).
- **Proyectos con o sin líquidos:**
  - sin cisterna ni tanque: configuración 0.4, o 0.5 con `ausente_confirmado`, sin cargas de agua;
  - si la información es dudosa: `informacion_insuficiente`, que bloquea la aprobación;
  - si hay recipiente: `presente`, con su declaración revisada, un patrón dedicado y el corte Z del nivel libre.
- **Construcción y lectura:** recorrido normal (`plan-etabs`/ejecución verificada/registro); relectura con `verificacion_modelo_guardado` (malla y líquidos); análisis y `lectura_analisis` con `resultados_api=["BaseReact"]` para obtener reacciones en dobles. Ensayo nativo sintético reproducible: `python scripts/ensayar_plan_liquidos.py --trabajo tmp/<NUEVA> --confirmar-sintetico [--escenario referencia]`. Devuelve un código distinto de 0 si falla alguna fase obligatoria o el equilibrio estricto.
- **Recuperar fallos sin reenviar:**
  - una marca `motor.lock.incierto.json` se resuelve con `confirmar_recuperacion` y evidencia (Exit 0 observado en la traza, o comprobación en el host), nunca borrándola;
  - las peticiones a la API no se reintentan automáticamente.
- **Distinción de evidencias:**
  - **dobles:** pruebas, que no acreditan ETABS ni el proveedor;
  - **nativo sintético:** `tmp/l2` y `tmp/r3`;
  - **piloto real actual:** `pueblo-libre-002`, con construcción, análisis y resultados reales; `provisional-001` es antecedente. Véase el corte actual al final de esta guía.
  - La **comparación manual** está aplazada por el usuario.

## 8. Encargo 08: evidencias, arquitectura y RNE vigente

- Revisión de evidencias y lecturas omitidas, cuarentena explícita y vigencia de derivados: [LECTURAS_SEMANTICAS](LECTURAS_SEMANTICAS.md).
- Normas aplicadas con cita, verificación contra el texto oficial y calibración por cadenas de cotas: [NORMATIVA_APLICADA](NORMATIVA_APLICADA.md).
- Un expediente ampliado (nuevas láminas) es un **caso nuevo** registrado con `ingresar`; las lecturas de otro caso se traen con una derivación explícita (IDs prefijados, evidencia en la página original con el mismo SHA), nunca reparando huellas antiguas.

## 9. Antecedente 09: preparación inicial de la configuración

Orden reproducible desde la raíz, sin red ni API. Cada guion escribe su informe en `seguimiento/claude_ruta/`:

1. `python seguimiento/claude_ruta/inventario_09.py`: columnas, placas y franjas de L0001 (`INVENTARIO_GEOMETRICO_09.json`).
2. `python seguimiento/claude_ruta/muros_09.py`: muros de L0004/L0005, pluma 1,68 pt (`MUROS_09.json` y superposiciones en `evidencia09/`).
3. `python seguimiento/claude_ruta/geometria_09b.py`: geometría 0.3 conforme por `importacion_tabular`. Después, el registro como versión hija:
   ```
   python -m draft2model revisar-geometria --caso pueblo-libre-002 --geometria 8b39dd52d4d448e5acfe64aa8ec05a2d --propuesta tmp/ruta201/geometria09b/geometria.json --motivo "…" --fecha AAAA-MM-DD --revisor "…"
   ```
   La versión resultante en este equipo es `7c84de15…`.
4. Plantilla propia del caso, una sola vez y en una instancia ETABS **nueva**: el guion no toca instancias abiertas y cierra solo la suya.
   ```
   powershell -File scripts/crear_plantilla_etabs_caso.ps1 -Destino <abs>\plantilla_vacia_caso.edb -Registro <abs>\creacion_plantilla.json -Caso pueblo-libre-002
   ```
5. `python seguimiento/claude_ruta/configuracion_09b.py`: configuración 0.5 en borrador (`CONFIGURACION_CASO_09B.json`), con plantilla, hipótesis, cargas, masa, apoyos, diafragmas y casos.

Este registro es histórico. Después el usuario confirmó ladrillo de arcilla y alturas; autorizó escenarios de suelo ante ausencia de EMS. El recorrido real posterior emplea hipótesis explícitas de suelo/sistema, sin convertirlas en datos reales del edificio.

## 10. Receta histórica del caso real 09D (ruta 253)

Esta receta registra la corrida original: no volver a ejecutarla contra sus carpetas publicadas. Los scripts internos de seguimiento no forman parte del paquete público de fuentes; sirven para auditar este expediente, no como requisito para un proyecto nuevo. Escenario de **transporte de software**, autorizado por el usuario con suelo/sistema hipotético (S1, R0 = 6). No es ingeniería. Todo
se ejecuta desde la raíz, sin red ni API. Cada etapa de ETABS abre una instancia **nueva** y cierra solo la suya.

1. **Geometría 09D-v3** (`seguimiento/claude_ruta/geometria_09d.py`):
   - incluye caras mojadas, el tanque en su recinto físico y la escalera (primer tramo confirmado, U superior hipotética);
   - NCF/NTF/NTT son cotas `auxiliar` (`docs/COTAS_AUXILIARES.md`);
   - se registra con `revisar-geometria`, y la variante de transporte con `geometria_09t.py geometria09d` + `aprobar-geometria`.
     Las versiones quedan en `VERSIONES_09.json`.
2. **Configuración** con contenido declarado (`liquidos.contenido`) y malla real:
   ```
   python seguimiento/claude_ruta/configuracion_09d.py --transporte --con-malla
   ```
3. **Construcción, relectura y análisis** con el runner seguro, en una carpeta nueva de `tmp/`:
   ```
   python seguimiento/claude_ruta/recorrido_etabs_09t.py --trabajo tmp/recorrido_09d1 --etapa construccion --configuracion tmp/ruta201/configuracion09dt.json
   python seguimiento/claude_ruta/recorrido_etabs_09t.py --trabajo tmp/recorrido_09d1 --etapa relectura --configuracion tmp/ruta201/configuracion09dt.json
   python seguimiento/claude_ruta/revision_controles_09.py --trabajo tmp/recorrido_09d1 --modelo <registro_modelo> --salida tmp/recorrido_09d1/revision_controles.json
   python seguimiento/claude_ruta/recorrido_etabs_09t.py --trabajo tmp/recorrido_09d1 --etapa analisis --configuracion tmp/ruta201/configuracion09dt.json --revision-controles tmp/recorrido_09d1/revision_controles.json
   ```
   - El análisis exige el sidecar de controles: revisor real con su alcance, y evidencias con SHA.
   - El análisis registra la masa ensamblada nativa frente al libro de contribuciones (`fases.masa_nativa`; `docs/MASA_ENSAMBLADA.md`).
4. **Resultados, controles e informe** por el flujo general del producto (lector, normalización, `ServicioControles`, informe):
   ```
   python seguimiento/claude_ruta/resultados_09.py --trabajo tmp/recorrido_09d1
   ```
   - Produce `resultados/informe/informe.{json,html,pdf}` con evidencia de análisis, controles, inventario de contenido y masa nativa.
   - En esa etapa las reglas estaban en borrador. Las continuaciones posteriores ya evaluaron 18 comparaciones; véase el corte actual. No sobrescribir aquellos borradores históricos.
   - El sitio referencial queda «no disponible».
5. **Métricas de extracción y esfuerzo** desde los recibos existentes:
   ```
   python seguimiento/claude_ruta/metricas_extraccion_09.py
   ```
   La precisión es no verificable mientras no exista anotación humana de referencia.

Límites que el informe conserva visibles:
- sin EMS ni hidrodinámica;
- la U de la escalera superior es hipotética;
- no hay comparación con el modelo manual (aplazada);
- no hay aprobación de ingeniería ni de reglas.


## Corte del piloto real: 23 de octubre de 2026

| Componente | Evidencia observada | Pendiente para cierre |
| --- | --- | --- |
| Planos y datos | Seis PDF originales de Pueblo Libre con integridad comprobada; arcilla y cotas0/2,60/5,20/7,80/10,40m confirmadas, primer tramo16contrahuellas | Precisión de extracción no medible sin referencia humana completa; revisiones siguen siendo necesarias |
| Modelo y análisis | Geometría25ef94672fac4e53863701b55e32f97d, modelo0f37271307b6449c89c458c60a1640c7, análisis7203c79a3ece4438b36d267ba80f3c4b; EDB analizado con SHA42371308a03d4f1bac8f5ed3aa5daf0421cdf3de27ff823f8f582c13ad2af394 | No se declara revisión profesional ni reproducción nativa en otro equipo |
| Resultados | Resultado697bb37e9ce64f90ba1ef3e25733c8cc:13indicadores; T1=1,339s, VX=672,5354kN, VY=528,1533kN | Interfaz y descarga de la versión final por comprobar |
| Evaluación |18comparaciones de escenarios:8satisfacen y10no;8fallos de deriva (2SX,6SY) y2de cortante mínimo | Son comprobaciones parciales; no aprobación normativa. Suelo/sistema siguen siendo hipótesis |
| Masa | Masa nativa548,7267285730835 frente a libro549,4269889710316; contraste oficial no_coherente | Diferencia principal explicada por extremos efectivos de vigas; no se amplió tolerancia ni se sustituyó la predicción independiente por un ajuste |
| Informe y panel | Salidas corregidas09d3:18evaluaciones conservadas, unidad de cociente1, captura nativa incluida con contraste no_coherente; PDF y panel revisados302 | Contenido técnico conservado. Contraste309/310 con MuPDF, Poppler y Windows.Data.Pdf; fuente del pie incrustada en312. No acredita todos los visores ni aprobación de ingeniería |
| Distribución | Instalación offline287:6/6 sobre fuentes285. Complemento291 conserva un solo caso, resultados seleccionados y20fuentes normativas públicas; hashes revisados | Ambos son antecedentes/candidatos, no la distribución final aceptada |

La ausencia de EMS se conserva como faltante. Los escenarios no sustituyen investigación geotécnica. No se afirma extracción automática sin revisión, diseño de armado, hidrodinámica ni soporte validado para cualquier construcción. La comparación con el modelo manual sigue aplazada. Los proyectos2y3 no se han procesado.

En el repositorio de desarrollo las evidencias son `seguimiento/REVISION_REGLAS_REALES_286.json`, `REVISION_CONTROLES_REALES_285.json`, `REVISION_INFORME_PANEL_290.json`, `REVISION_UNIDADES_292.json`, `REVISION_COMPLEMENTO_291.json` y `REVISION_INSTALACION_287.json`. Estos registros internos no se incluyen automáticamente en el paquete público; la entrega final debe adjuntar un resumen de validación asociado a su huella.
