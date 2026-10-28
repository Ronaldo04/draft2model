# Informe con contexto verificado y explicación sustentada

- **Ruta:** `D:/RONALDO CUCHILLA/1. RONALDO CUCHILLA/2. INGENIERÍA CIVIL DOCS AND PROJECTS/AECODE CURSOS/AECODE AI TALENT/PROYECTO FINAL`.
- **Archivos modificados:** `draft2model/informe.py` (núcleo) y `draft2model/revision_entregables.py` (servicio).
- **Integración posterior HTTP/UI:** `informes.js`, su bloque en `index.html` y pruebas focales adicionales. Contexto, explicaciones y proveedor permanecen sin cambios en esta integración.

## Servicio: `crear(body)` compatible

El cuerpo anterior sigue siendo válido tal cual: `{caso, resultado, expediente_sha256, contexto, analisis}`. Sin referencias, el comportamiento y la forma del informe y de `paquete.json` no cambian: evaluación pendiente, sitio declarado y ningún campo nuevo.

**Campo opcional nuevo, con claves exactas:**

```
referencias: {evaluacion, recuperacion, sitio, explicacion}   // cada valor: UUID de 32 hex o null
```

**Reglas:**
- Solo se aceptan IDs del caso. No se aceptan rutas, texto ni JSON de explicación desde el navegador. Un campo `explicacion` u otro campo extra en el cuerpo se rechaza.
- **Derivados:** se leen con `ServicioContexto.consultar_derivado`, que los reproduce desde sus fuentes. Cada uno debe ser del tipo indicado.
  - La evaluación debe estar ligada a `{id: resultado, huella}`.
  - Cualquier derivado ligado a otro resultado se rechaza.
- **Reglas exactas:** `consultar(caso,'reglas',id)`, que aplica el validador nativo, y después lectura de `reglas.json`, que debe coincidir con la huella citada por el derivado.
  - `crear_informe` recalcula la evaluación y la compara con la salida del derivado, sin modificar valores ni umbrales.
- **Corpus y citas:** `consultar(caso,'corpus',id)` y el `corpus.json` de esa versión. Las citas son todos los fragmentos de la recuperación y se pasan a `crear_informe` y `exportar_informe`, que las verifican con `verificar_citas`. Una recuperación con abstención produce `citas: []`.
- **Sitio:** con referencias, `contexto.sitio` debe llegar como `null` y se rellena con la salida comprobada del derivado. Un sitio pegado se rechaza.
- **Explicación:** se consulta con `ServicioExplicaciones.consultar`. Se exige que el trabajo:
  - esté en estado `completado_llm_verificado`, `contingencia` o `incierto_resuelto`;
  - sea vigente y tenga salida;
  - corresponda al mismo resultado, huella y expediente;
  - use **exactamente** los mismos derivados que las referencias.

## Núcleo: campos opcionales del informe

Si no se aportan, `validar_informe` acepta la forma anterior sin cambios.

**`contexto_verificado`:**
- Formato: `{evaluacion, recuperacion, sitio}`, cada uno `{id, sha256_salida, fuentes}` o `null`.
- Se exige coherencia: la huella de las reglas debe coincidir con `huella_declaracion(reglas)`, la del corpus con `fuentes.huella_corpus`, y la de la capa con `contexto.sitio.huella_capa`.

**`explicacion`:**
- Formato:

  ```
  {trabajo, estado_trabajo, huella_salida, modo, causa, generacion_llm_real,
   modo_transporte, modelo_declarado, declaraciones, abstenciones,
   limites_verificables, estado_revision:"propuesta_pendiente_revision_humana"}
  ```

- Exige que también exista `contexto_verificado`.
- **Modo LLM:** cada declaración tiene que cumplir todo lo siguiente:
  - llevar `estado` `propuesta_pendiente_revision_humana`;
  - apuntar a indicadores `R:<fila>` o `E:<regla>:<caso>:<dir>:<ubic>` que existan en el propio informe;
  - incluir cifras iguales al valor y la unidad vigentes;
  - usar citas idénticas a las del bloque de fuentes del informe.
- **Contingencia:** `generacion_llm_real:false`, `declaraciones:null` y una causa obligatoria.

**Otras reglas del núcleo:**
- `huellas` incluye `contexto_verificado` y `explicacion` solo cuando esos campos están presentes. Cualquier cambio posterior invalida el informe.
- La tabla de cifras, las reglas y las siete secciones siguen siendo determinísticas.
- La explicación se muestra en una sección propia con estos encabezados:
  - «PROPUESTA DE TEXTO (LLM REAL)» o «(TRANSPORTE DE PRUEBA, NO ES UNA LLAMADA REAL)», ambos con «SENTIDO TÉCNICO PENDIENTE DE REVISIÓN HUMANA · NO ES CONCLUSIÓN NI CONFORMIDAD»;
  - o «CONTINGENCIA DETERMINÍSTICA (causa) · NO ES GENERACIÓN LLM».
- El sitio verificado se muestra como «CONSULTA DE COBERTURA COMPROBADA por el derivado …», con la huella de la capa y la ubicación declarada. El sitio declarado sin referencias mantiene su aviso anterior.

## Persistencia, revalidación y aprobación

- **`paquete.json`** incluye `referencias` solo cuando se aportaron.
- **`consultar`, `listar`, `archivo` y `aprobar`** hacen lo siguiente:
  1. Vuelven a resolver los derivados, las reglas, el corpus y la explicación.
  2. Reconstruyen el informe con `crear_informe`, sin generar el PDF, y exigen igualdad con el JSON guardado en todo salvo `revision`.
  3. Comparan una firma de todo el contexto (derivados, reglas, citas, sitio, explicación y bytes del corpus) antes y después de la operación.
- **Efecto:** si cambia una fuente de contexto o el trabajo de explicación, el informe, su aprobación y su descarga quedan invalidados, aunque los hashes del paquete no cambien.
- **Aprobación documental:** crea una versión hija con las mismas referencias y el mismo contenido salvo `revision`, ligada al padre exacto. Siempre `aprueba_resultados:false` y `conformidad_normativa:"no_evaluada"`.
- **Proyección:** añade `contexto_verificado` (id y sha256 de salida) y un resumen de `explicacion` (`trabajo`, `modo`, `causa`, `generacion_llm_real`, `estado_revision`), sin rutas.
- **Staging:** carpeta temporal `.informe-*`, revalidación del paquete preparado y `rename` atómico. Las versiones y los originales anteriores no se tocan.

## Uso desde HTTP/UI

La creación mantiene `POST /api/informe/crear`; no se añade ruta nueva. El panel de informes consume `d2m-context` y `d2m-explanation` y muestra las selecciones candidatas para el próximo borrador, separadas de las referencias conservadas en el informe abierto.

- «Usar los derivados …» incorpora los UUID de evaluación, recuperación y sitio seleccionados explícitamente en Contexto, tras comprobar tipo, caso, expediente, vigencia reproducible, huella de salida y asociación al resultado cuando existe. No se omite ni sustituye un derivado inválido por otro.
- «Usar la explicación …» es otra opción independiente. Solo se habilita para un trabajo vigente con salida en `completado_llm_verificado`, `contingencia` o `incierto_resuelto`, ligado al resultado/huella/expediente actuales y con exactamente los mismos derivados que se incluirán. Si esos derivados no están activados, no se activan por cuenta del cliente. Una explicación con los tres derivados null puede usarse por sí sola, explícitamente.
- Ambos controles comienzan apagados. Recibir eventos no incorpora referencias al informe, no prepara una explicación, no aprueba resultados y no declara normativa. Sin opciones activadas se omite por completo `referencias`, conservando la forma anterior. Con alguna opción, se envía el objeto exacto de cuatro claves UUID/null; `contexto.sitio` siempre permanece null.
- La selección candidata identifica contingencia como «CONTINGENCIA DETERMINÍSTICA · SIN LLM REAL» y mantiene visible «revisión semántica humana pendiente». Propuestas reales y de transporte de prueba se distinguen; ninguna se presenta como conclusión aprobada.
- Al abrir un informe se muestran sus propias `referencias`, `contexto_verificado` y resumen de explicación. Cambiar la selección candidata no reescribe un informe previo. Sus descargas y la aprobación documental continúan verificando las fuentes que quedaron conservadas en él.
- Cambiar caso, resultado, contexto o explicación consume las opciones correspondientes y la confirmación documental y descarta respuestas/errores anteriores. Repetir el mismo evento comprobado conserva las elecciones explícitas. Modificar los controles de uso también consume la confirmación documental. Los controles no sustituyen la revalidación completa del backend.

HTTP conserva sesión/origen, JSON acotado y respuestas `no-store`: creación aceptada **201**; referencias, fuente, contrato o asociación rechazados **409**; sesión/origen inválidos **403**. El navegador no aporta reglas, citas, cartografía ni texto LLM dentro de `referencias`.

### Pruebas focales de esta integración

Con `TEMP` y `TMP` en `workspace/tmp`:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_revision_informe_contexto_http -v
& 'C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests/revision_informe_contexto_frontend.cjs
& 'C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests/revision_aprobacion_informe_frontend.cjs
& 'C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests/revision_informes_frontend.cjs
```

Resultado en una pasada: **3 HTTP OK (31.574 s)**; Node **15/15** nuevos, **13/13** de aprobación documental y regresión existente de consultas/descargas OK. HTTP usa una fixture portable sintética, parser en memoria y guardas contra red/procesos; comprueba contexto, contingencia sin clave, referencias exactas, compatibilidad, sitios pegados rechazados, hija documental y descarga con fuentes alteradas. No se ejecuta suite completa, proveedor real, CU ni ETABS.

## Pruebas del núcleo y servicio

Comando:

```bash
TEMP=$PWD/tmp TMP=$PWD/tmp python -m unittest tests.test_informe tests.test_revision_entregables tests.test_revision_entregables_http tests.test_revision_aprobacion_informe tests.test_revision_aprobacion_informe_http tests.test_informe_explicacion tests.test_revision_informe_contexto
```

Resultado: 42 OK. Son 32 pruebas previas sin cambios y 10 nuevas, con `_http`, `Popen`, `urlopen` y `socket` bloqueados.

**`test_informe_explicacion` (núcleo):**
- Compatibilidad sin campos nuevos.
- Explicación LLM válida: render, exportación PDF y aprobación.
- Contingencia identificada que no puede presentarse como LLM.
- Rechazo de cifras, unidades, citas e indicadores alterados, de una declaración aprobada o sin sustento, y de una explicación sin contexto.
- Referencias incoherentes con el contenido.

**`test_revision_informe_contexto` (servicio):**
- Recorrido completo: LLM por transporte falso, consulta, descarga JSON/HTML/PDF, aprobación hija y listado.
- Contingencia y abstención.
- Reglas o salida de la explicación alteradas: invalidan consulta, descarga y aprobación, y todo vuelve a funcionar al restaurar.
- Rechazo de explicación con otros derivados, tipo cambiado, UUID inválido, campo extra, sitio pegado, texto arbitrario y derivado de otro resultado.
- Compatibilidad sin referencias.

## Límites

- Cada consulta de un informe con referencias reconstruye el JSON y revalida contexto y explicación, lo que resulta más costoso que antes. El PDF no se regenera; su integridad se cubre con el hash del paquete.
- El renderizado HTML/PDF no se vuelve a ejecutar en la consulta.
- El sentido técnico del texto LLM no se verifica: queda como propuesta pendiente de revisión humana.
- El servicio lee `reglas.json` y `corpus.json` desde `<caso>/contexto/...` después de validarlos por la API pública de contexto.
- **No verificado por esta integración:** fotos, red, API real, ETABS, Computer Use y la suite completa. La UI no verifica el sentido técnico o semántico de las explicaciones.
