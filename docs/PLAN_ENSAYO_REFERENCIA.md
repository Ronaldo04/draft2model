# Ensayo final con el expediente de referencia

Plan para que el coordinador ejecute al terminar la infraestructura. Esta revisión **solo leyó metadatos, documentación y código de las puertas necesarias**; no extrajo texto de los planos, abrió sus imágenes, leyó credenciales, llamó a red/proveedor/ETABS, configuró ingeniería ni repitió pruebas. No se ha realizado el ensayo descrito.

## Punto de partida comprobado por metadatos

| Referencia | Identidad conservada |
| --- | --- |
| Caso | `provisional-001` |
| SHA256 de expediente | `3b1ca4a73227157f7a1987b4c95623b72aa7f6c90da3bc30cbd326d0c3f9f98b` |
| Revisión documental preparada | `e9a600f3df2242a48bbe905d880123d0` |
| **Paquete**, ID del contenedor para preparar proveedor | `b7f15fc5620e4f4d8b8a5282a1f8b568` |
| Solicitud interna, distinta del paquete | `7ff70189043a4469b0f37df3c4e2733d` |
| SHA256 de solicitud | `5aae1b68a3435221145fe1a4b3eda5b54804793c075b3d72ee0cab4ebafbcf53` |
| Alcance | `fuera_mvp_declarado`, uso `pruebas_procesamiento` |
| **Paquete detallado 135** (preferente para el ensayo) | `bfda0ef3570049b1bc4dca02f11848c6`: 3 vistas generales y 7 recortes, **10 imágenes**. Solicitud `9b138db0348b40478efccd0341f0343b`, SHA256 `256170601baa00656fd7c902453e15a1c208a2ef8e8044da577e6c43cd50d181`. Petición local de 5 293 080 bytes, por debajo de 40 MiB. Fuente: `tmp/referencia_preparada_135.json` y `seguimiento/REFERENCIA_PAQUETE_135.json`. Preparado sin envío y sin modelo real seleccionado; no sustituye silenciosamente al paquete general 124. |

Fuente del estado: `tmp/referencia_preparada_124.json` y `data/private/provisional-001/expediente.json`. Hay tres PDF registrados, tres páginas renderizadas sin errores documentales y seis imágenes en el paquete: tres contextos de 2399×1698 y tres recortes generales de 3359×2376, uno por primera página. La preparación declara originales conservados, `api_real:false`, `etabs:false` y `preparado_sin_envio`. No son tres recortes detallados de cotas: su nota dice vistas generales completas, sin inferir ni seleccionar regiones de detalle.

El caso contiene actualmente originales, revisiones documentales, recortes y solicitudes visuales; no se observaron grupos de geometrías, configuraciones ni modelos construidos. `datos_ingenieria` y `aprobacion_tecnica` del expediente están null. Esto significa **información no registrada/verificada**, no que los dibujos carezcan necesariamente de ella.

El alcance fuera del MVP debe conservarse en cada etapa. No impide por sí mismo el ensayo de infraestructura, no impone dos pisos ni convierte el caso en validación de albañilería confinada.

## Datos que se pueden afirmar y decisiones todavía abiertas

| Materia | Qué está disponible o acreditado ahora | Qué se necesita antes de utilizarlo |
| --- | --- | --- |
| Documentos | Tres fuentes PDF registradas y sus páginas/imágenes vinculadas mediante hashes. | Revisar integridad y legibilidad de regiones concretas. La renderización correcta no acredita lectura correcta. |
| Tema de láminas | Los nombres registrados sugieren cimentación y estructura/modelado. | No inferir elementos, niveles, tipología o parámetros físicos por el nombre del archivo. |
| Cotas, ejes y unidades | Ningún valor físico fue leído ni verificado en este encargo. | Lectura localizada, revisión del valor y unidad; referencias explícitas a cotas y definición del origen/ejes. |
| Niveles, coordenadas, espesores y conexiones | Aún no hay geometría registrada en el caso. | Manifiesto físico completo; número de niveles real declarado, coordenadas y conectividad revisadas. Una bbox no aporta metros. |
| Materiales, secciones y representación | No hay configuración estructural del caso acreditada. | Localizar y revisar lo que efectivamente consta en las láminas; declarar como pendientes los datos no sustentados. Elegir representación compatible sin suponer equivalencia física. |
| Cargas, masa, apoyos y diafragmas | No están configurados/verificados. | Fuentes de carga y unidades; composición de masa y gravedad; condiciones de borde y diafragmas o exclusiones explícitas. No completar con un ejemplo sintético. |
| Sitio, espectro y decisiones normativas | No existe en estos metadatos una base técnica verificada para asignarlos. | Fuentes/ubicación aplicables revisadas y parámetros declarados. No copiar un espectro, suelo o umbral de las fixtures. |
| Plantilla EDB | No hay plantilla de este caso identificada en el estado preparado. | Copia `.edb` autorizada, vacía y compatible, huella exacta y representación revisada. |
| Referencia para precisión | Paquete preparado; no referencia humana medida. | Anotación humana y correspondencias revisadas cuando se realice el benchmark final. La respuesta de IA no sustituye esa referencia. |

No puede concluirse desde los metadatos si un valor falta **en el plano**. El inventario anterior distingue datos disponibles del documento de datos aún no verificados; la lectura final debe resolver esa diferencia con evidencia localizada.

## Capacidades que delimitan el ensayo

### Modelo visual

El código no fija ni valida previamente un ID comercial de modelo; admite un identificador explícito de hasta 128 caracteres de su patrón local. **No se recomienda aquí un modelo reciente ni se afirma disponibilidad en una cuenta.** El coordinador debe elegir un ID autorizado cuando llegue el ensayo final y confirmar compatibilidad con el payload real del conector, no con una suscripción de chat.

`proveedor_openai.py` usa endpoint fijo de Responses, imágenes PNG base64 con `input_image/detail`, mensaje developer, `max_output_tokens`, `store:false` y `text.format` con JSON Schema estricto. No configura esfuerzo de razonamiento ni usa herramientas remotas. El modelo debe aceptar esas capacidades/opciones y devolver una respuesta completa con el único texto JSON esperado, sin rechazo ni llamadas a herramientas. El parser admite un ítem de razonamiento, pero no convierte cualquier salida libre en un contrato válido.

**Proveedores intercambiables:** el usuario pidió no atarse a una empresa.
- Hoy el proveedor soportado y verificado (copia 146/148, transporte de prueba) es **OpenAI**.
- Gemini (`GEMINI_API_KEY`) y el protocolo compatible con Chat Completions (`COMPATIBLE_API_KEY` más un endpoint local explícito en `D2M_COMPATIBLE_ENDPOINT`) están **en implementación y pruebas por Codex**, sin API real.
- Un proveedor registrado necesita clave y modelo. El protocolo personalizado necesita además el endpoint y un modelo con visión y JSON Schema.
- Ninguna clave garantiza compatibilidad. Elegir un único proveedor ya integrado y verificado al llegar a esta puerta. Ver [accesos y proveedores](ACCESOS_Y_PROVEEDORES.md).

Límites locales: hasta **16 imágenes**, petición JSON hasta **40 MiB**, salida **256–16384 tokens**, detalle `low/high/auto` y timeout web **1–180 s**. Las seis imágenes actuales cumplen el conteo; el tamaño completo codificado debe comprobarlo la preparación real. Estos no son límites ni precios universales del proveedor. Preparar sin red no demuestra compatibilidad de cuenta/modelo; una salida truncada tampoco acredita fallo de extracción del documento.

### Representación y motor

Las puertas vigentes permiten geometría por nodos en planta, cotas de niveles y muros rectangulares verticales, sin límite de dos pisos. La configuración aporta puntos nodo/nivel, frames explícitos, material isotrópico lineal y secciones shell de muro/frame rectangular. La construcción contempla estático lineal, modal Eigen y espectro tabulado con las opciones dinámicas explícitas de `OPERACIONES_ETABS.md`.

No declarar compatible un modelo que requiera silenciosamente capacidades ausentes: aberturas/losas horizontales como geometría general, elementos de confinamiento inferidos, sección no rectangular, resortes/liberaciones/offsets, no linealidad/P-Delta o una representación constitutiva distinta deben revisarse contra contrato y plan. La documentación de capacidades y el rechazo del generador prevalecen sobre una apariencia gráfica de modelo completo. El material API `NoDesign` no acredita diseño normativo ni equivalencia de albañilería.

El plan rechaza masa `explicita` sin grados de libertad declarados, respuesta rígida espectral activada, nombres de combinaciones que colisionan con casos y cargas duplicadas sobre el mismo objetivo/patrón/dirección cuya acumulación no está verificada. Para masa por patrones exige gravedad de programa declarada y compatible con la configuración: la API no permite leerla/fijarla, por lo que no se inventa. Casos dinámicos exigen las opciones completas del generador. No reducir el caso a un subconjunto sin registrar qué se dejó fuera y el alcance estrictamente operativo de esa corrida.

## Secuencia de ejecución con puertas de aceptación

Usar la UI local ya autenticada y sus helpers HTTP; no copiar tokens o claves al documento. Todos los cuerpos siguientes usan `caso` y **`expediente_sha256`** vigentes; `fp` es solo abreviatura explicativa. Los marcadores entre `<...>` se reemplazan por IDs/huellas o decisiones revisadas: no son valores ejecutables predeterminados. Cada POST es una acción separada; consultar no debe ejecutarla otra vez.

### 0. Revalidar paquete y estado del equipo

Al abrir el caso, consultar `GET /api/documentos?caso=provisional-001`; si la huella difiere de la tabla inicial, detener y volver a preparar/seleccionar el estado vigente. Consultar `GET /api/visual/paquete` con caso, `version=bfda0ef3570049b1bc4dca02f11848c6` (paquete detallado 135) y `expediente_sha256=fp`. Exigir fuentes, render y transformaciones vigentes, **diez imágenes** y `transmision_externa:false`. El paquete general 124 (`b7f15fc5620e4f4d8b8a5282a1f8b568`, seis imágenes) sigue disponible; usar uno u otro de forma explícita, sin mezclarlos.

Comando de verificación local equivalente, que solo imprime identidades y conteos, no texto del plano/prompt ni base64:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; from draft2model.entrada_vision import cargar_paquete; p=Path('data/private/provisional-001'); r,s,_,_=cargar_paquete(p/'expediente.json',p/'vision/solicitudes/bfda0ef3570049b1bc4dca02f11848c6/solicitud.json'); print({'solicitud':r['id'],'sha256':s,'imagenes':len(r['imagenes'])})"
```

Revisar si las vistas generales permiten leer los objetivos. Si no, conservar recortes detallados del PDF y otro paquete, con las mismas fuentes y regiones explícitas; no declarar que aumentar imágenes o DPI mejora precisión sin medirlo. No hace falta preprocesamiento raster para estos PDF; no convertirlos en fotografías para eludir su contrato.

Antes del tramo ETABS verificar el host autorizado, ausencia de una operación incierta activa y preflight de rutas. La raíz del caso observada tiene 152 caracteres y el destino de construcción típico 229; eso **no** certifica todas las rutas anidadas ni las de la plantilla. El servicio rechaza rutas previstas de 260 o más caracteres antes de contactar el motor. Si se necesita copia limpia en raíz corta, la prepara el coordinador por su flujo autorizado, con todo el expediente/evidencia y hashes comprobados; no usar junctions, cambiar originales o fabricar aceptaciones.

Si no hay servidor abierto, el comando local existente es:

```powershell
.\.venv\Scripts\python.exe -m draft2model.revision_visual --raiz data/private --puerto 8766 --sin-navegador
```

El servidor que vaya a ejecutar el proveedor debe **heredar** la credencial: fijar la variable y arrancar `revision_visual` en la **misma consola de PowerShell**. El `.cmd` no la hereda. Ver el método para PowerShell 5.1 y 7, sin persistir la clave, en [accesos y proveedores](ACCESOS_Y_PROVEEDORES.md) §3. Este plan no comprueba si la clave existe ni solicita leer o imprimir su valor. No hace falta para la preparación restante.

### 1. Preparar y ejecutar proveedor una sola vez, al final autorizado

`POST /api/proveedor/preparar`:

```text
{caso, expediente_sha256, paquete:ID_PAQUETE,
 modelo:ID_COMPATIBLE_ELEGIDO,
 opciones:{max_tokens:LIMITE_DECLARADO,detalle:DETALLE_DECLARADO,timeout_s:TIEMPO_DECLARADO},
 clave_solicitud:UUID32_NUEVO}
```

Conservar trabajo, huella de preparación y hashes de solicitud/plan/petición. Verificar la selección de paquete/modelo/opciones que se mostrará al usuario. Este paso no transmite imágenes ni prueba la clave.

Solo cuando credencial/modelo estén disponibles y el envío de ese paquete esté autorizado, `POST /api/proveedor/ejecutar` con `{caso,trabajo,huella_preparacion,expediente_sha256,confirmacion_explicita:true}`. La confirmación del contrato HTTP la aporta el coordinador conforme a la autorización vigente; no exige repetir una aprobación humana ya otorgada. Puede generar costo y transmitir las imágenes privadas seleccionadas; no enviar el expediente completo ni las futuras referencias humanas de evaluación. Consultar `GET /api/proveedor/trabajo?caso&trabajo` hasta estado terminal, sin volver a enviar.

**Puerta:** `completado_verificado`, `vigente:true`, `modo:real` y `llamada_real_acreditada:true`; guardar modelo solicitado/devuelto, duración y uso observado. Consumo ausente y costo sin tarifa siguen null. Transporte Python/simulado no acredita esta puerta real.

### 2. Vincular respuesta, trasladar extracción y revisar lecturas

`POST /api/respuestas/vincular-proveedor` exige `{caso,expediente_sha256,trabajo,huella_preparacion,confirmacion_explicita:true}`. Consultar la respuesta y comprobar que es `proveedor_verificado`, del trabajo/paquete exactos, no una respuesta pegada con un nombre comercial declarado.

Después, `POST /api/respuesta/importar` con `{caso,expediente_sha256,respuesta:ID_RESPUESTA,sha256_extraccion:SHA_CONSULTADO,confirmacion_explicita:true}`. Conservar el ID de extracción; no confundirlo con respuesta, solicitud, paquete o trabajo. El traslado deja todos los candidatos **pendientes**; no aprueba nada.

Revisar contra sus regiones cada cota/etiqueta/elemento que se utilizará. Corregir o rechazar mediante la interfaz existente (`POST /api/corregir`) o CLI:

```powershell
.\.venv\Scripts\python.exe -m draft2model validar-extraccion --caso provisional-001 --extraccion ID_EXTRACCION
# Al revisar cada candidato, usar corregir-extraccion con el valor/unidad realmente comprobados,
# motivo, fecha y revisor declarados; no copiar valores de las fixtures.
```

**Puerta:** versión de extracción comprobada, evidencia localizada en el original exacto y candidatos utilizados en estado revisado. Null/desconocido/ambiguo se conserva o se rechaza; nunca se convierte en cero o una longitud conocida. Guardar también la propuesta inicial intacta para evaluar precisión después.

### 3. Declarar manifiesto físico y producir geometría

Completar el manifiesto de `CONVERSION_GEOMETRIA.md`: caso exacto, `datos_sinteticos:false` para las fuentes reales declaradas, procedencia coherente, operador, unidad m/cm/mm, ejes/origen/escala física declarada, niveles/nodos/muros y conectividad. Cada medida toma una cota revisada o una declaración del operador justificada con referencias revisadas. Los valores declarados por operador se distinguen de lecturas literales. No medir metros de la imagen/bbox ni inferir conexiones.

`POST /api/conversion/crear` con `{caso,extraccion:VERSION_REVISADA,expediente_sha256,manifiesto_json:JSON_COMPLETO}`. Consultar la conversión y contrastar sus correspondencias, hashes y geometría completa. Solo después, `POST /api/conversion/importar-geometria` con `{caso,version:ID_CONVERSION,expediente_sha256,huella_conversion:HUELLA_CONSULTADA,confirmacion_explicita:true}`.

**Puerta:** geometría importada en borrador, expediente y originales vigentes, identidad/versiones y huellas exactas. La revisión geométrica debe comprobar niveles, coordenadas, conectividad y espesores; completar faltantes antes de una aprobación explícita. `POST /api/geometria/aprobar` requiere `{caso,expediente_sha256,version,huella,sha256_geometria,motivo,fecha,revisor_declarado,alcance_revision,confirmacion_explicita:true}`. Codex no sustituye la declaración técnica ni debe crearla solo para desbloquear la siguiente puerta.

**Revisión espacial antes de aprobar:** con la geometría en borrador, usar el panel de superposición. Cargar el esquema del nivel y declarar **tres anclas no colineales** (nodo del modelo → punto normalizado de la página original), con revisor, fecha, motivo y confirmación (`POST /api/superposicion/crear`). La correspondencia es una declaración, no una detección. Solo dibuja muros y no prueba que un elemento esté documentado. Cada versión corregida exige anclas nuevas. Ver [superposición](REVISION_SUPERPOSICION.md).

Alternativa de captura humana: tablas CSV/XLSX de niveles/nodos/muros mediante `/api/tabular/crear` y `/api/tabular/importar`, conservando su origen supervisado. Es contingencia declarada; no presentarla como éxito de extracción automática del proveedor.

### 4. Configuración estructural revisada y plan compatible

Preparar configuración completa conforme a `MODELO_ESTRUCTURAL.md`, vinculada al ID y ambos hashes de la geometría aprobada. Exigir materiales/secciones, cobertura completa de muros/frames, cargas/masa, apoyos/diafragmas, casos/combos, sitio/hipótesis/fuentes y plantilla. Dejar null con declaración de faltante si no hay base para un parámetro; eso bloquea disponibilidad en lugar de inventarlo.

`POST /api/configuracion/importar` con `{caso,expediente_sha256,configuracion_json}` crea borrador. Consultar `/api/configuracion?caso&version`; revisar el contenido y `comprobacion`. Aprobar solo tras revisión concreta, mediante `{caso,expediente_sha256,version,huella,sha256_configuracion,revisor_declarado,fecha,motivo,alcance,confirmacion_explicita:true}` a `/api/configuracion/aprobar`.

**Puerta:** configuración aprobada sin faltantes, geometría aprobada vigente y `apto_para_adaptador:true`. Ese estado no prueba ejecución, equivalencia física ni seguridad. Elegir tipo shell, gravedad comprobada y opciones dinámicas por decisión técnica explícita. El generador debe rechazar todas las capacidades no soportadas antes de aplicar; no borrar requisitos para obtener un plan aparente.

### 5. Construir copia nueva, revisar modelo y analizar

`POST /api/construccion/preparar` con `{caso,configuracion_version:UUID_APROBADO,plantilla_relativa:RUTA_EDB_DEL_CASO,expediente_sha256,clave_solicitud:UUID32_NUEVO,opciones:OPCIONES_REVISADAS}`. La plantilla real debe coincidir con su hash declarado; la copia se mantiene separada y el destino es nuevo. Conservar huella del plan, número de operaciones y snapshots.

**Puerta previa:** preparación vigente, firmas/unidades compatibles, plantilla verificada, representación soportada y host/ejecutor disponible. Luego `/api/construccion/ejecutar` con el cuerpo común `{caso,trabajo,huella_preparacion,expediente_sha256,confirmacion_explicita:true}`. Consultar su trabajo hasta `aceptado`, `vigente:true`, `modo_ejecucion:real`, modelo registrado y aceptación integrada/EDB/traza completos. Retornos API cero sin aceptación final no bastan. Construir no ejecuta análisis.

Consultar `/api/modelo/revision` y revisar los cinco controles: geometría/conectividad, materiales/secciones, cargas/masa, apoyos/diafragmas, casos/combinaciones. La aprobación propia `/api/modelo/aprobar` usa modelo y huella exactos, revisor/fecha/alcance, los cinco booleanos explícitos y confirmación. No se hereda de configuración o geometría.

Preparar análisis en `/api/analisis/preparar` con `{caso,modelo:MODELO_REGISTRADO,aprobacion:ID_APROBACION_PROPIA,expediente_sha256,clave_solicitud:UUID32_NUEVO}`; ejecutarlo mediante `/api/analisis/ejecutar` con el cuerpo común confirmado y consultar el trabajo. No seleccionar PID o instancia activa del usuario; el flujo integrado utiliza instancia propia y exclusión compartida.

**Puerta:** `aceptado`, vigente, modo real, `calculo_verificado:true`, exactamente los casos previstos con estado CSI **entero 4**, y recibos ligados al EDB exacto. No implica normalización, revisión de resultados o conformidad normativa.

### 6. Leer tablas, revisar selectores y normalizar

`POST /api/lectura/preparar` con `{caso,analisis:ID_ANALISIS_ACEPTADO,expediente_sha256,clave_solicitud:UUID32_NUEVO,tablas:LISTA_EXPLICITA,casos:CASOS_DEL_ANALISIS}`. Ejecutar con cuerpo común confirmado y consultar hasta lectura aceptada, vigente y verificada. Conservar tablas/unidades/campos crudos y su SHA; no inventar nombres, modos, envolventes o direcciones.

`POST /api/mapeo/importar-lectura` con `{caso,trabajo_lectura,expediente_sha256,mapeo_json}`. El mapeo debe definir filtros únicos, variable/caso/dirección/ubicación, campo numérico y unidad de origen. Usar `Case` en las tablas modales admitidas y `OutputCase` en los demás selectores según el contrato; declarar `Mode` si corresponde. Cero filas produce null con motivo; varias filas rechazan la correspondencia.

Revisar previsualización; guardar/reaprobar una versión cuando cambien selectores. `/api/mapeo/aprobar` requiere `{caso,version,expediente_sha256,huella_mapeo,revisor,fecha,motivo,alcance,confirmacion_explicita:true}`. Después `/api/mapeo/normalizar` con `{caso,version,expediente_sha256,huella_mapeo,clave_solicitud:UUID32_NUEVO,confirmacion_explicita:true}`.

**Puerta:** resultado normalizado vigente, mapeo revisado, traza tabla/fila/campo/filtros/unidad, vínculo al análisis y mismo EDB. Revisar indicadores esperados según alcance; un análisis exclusivamente estático no recibe un periodo modal inventado. Los valores siguen pendientes de revisión y conformidad no evaluada.

### 6b. Controles internos postsolver (opcionales, con criterios revisados)

Con la lectura aceptada, se puede registrar `POST /api/controles/crear` con `{caso,expediente_sha256,lectura:ID_LECTURA,sha256_respuesta,avisos_solver_json|null,revisor_declarado,fecha,alcance,controles:[participacion_modal, equilibrio, advertencias_solver],confirmacion_explicita:true}`.
- **Criterios:** tolerancias, mínimos, selectores de modo/caso y aplicabilidad **declarados por quien revisa**. No hay valores por defecto.
- **Tablas:** pedir en la lectura las tablas necesarias (por ejemplo, la de participación modal y la de reacciones).
- **Avisos del solver:** sin una fuente declarada quedan `sin_datos`, porque el lector no extrae el log.

**Puerta:** registro vigente consultado por ID; estado global y faltantes críticos visibles. `apto_proyeccion_controlado:true` exige todos los aplicables satisfactorios y al menos uno calculado desde la lectura. CSI 4 no equivale a controlado. Esta puerta **no** aprueba resultados, ingeniería ni conformidad. Ver [controles](CONTROLES_ANALISIS.md).

### 7. Resultado revisado e informe completo en su alcance

La revisión propia de resultados es separada: si hay faltantes críticos, no declarar que están resueltos para habilitarla. `REVISION_APROBACION_RESULTADOS.md` exige las huellas de resultado/evidencia, análisis seleccionado, seis controles explícitos, revisor/fecha/alcance/motivo, observaciones y `faltantes_criticos:[]` declarados por quien revisa. La lista vacía no la deduce el software.

Se puede generar el borrador informativo sin afirmar revisión o cumplimiento: `POST /api/informe/crear` con `{caso,resultado:ID_RESULTADO,expediente_sha256,contexto:{titulo,hipotesis,faltantes,sitio:null},analisis:ID_ANALISIS}`. Si existen derivados de evaluación/corpus/sitio/explicación verificados y pertinentes, añadir `referencias:{evaluacion,recuperacion,sitio,explicacion}`, cada ID o null. Opcionalmente, y solo con el **mismo análisis** explícito:
- `revision_resultados:{id,sha256_revision}`: revisión declarada vigente;
- `controles_analisis:{id,sha256_controles}`: controles de §6b.

Omitir el campo cuando no se use; `null` se rechaza. Son referencias exactas que se revalidan al consultar, descargar y aprobar. No convierten el informe en aprobación de resultados ni de ingeniería. No insertar texto libre de IA como si estuviera verificado, copiar un corpus sintético o fabricar reglas/ubicación para llenar secciones.

Descargar `/api/informe/archivo?caso&version&expediente_sha256&formato=pdf` y su JSON; comprobar manifiesto SHA y vínculo de fuentes. Contrastar cifras/unidades, omisiones, número de muros/niveles, estado de generación/análisis, periodos/derivas/cortantes según lo disponible, reglas/sitio con su alcance y trazabilidad. Inspeccionar títulos/tablas entre páginas y conservación de todas las filas. El paginador corregido evita huérfanos de títulos sin convertirlo en revisión de ingeniería.

La aprobación posterior de `/api/informe/aprobar` es **documental**, no sustituye la de modelo/resultados ni evalúa seguridad o normativa. No es condición para acreditar que el recorrido operativo llegó a un borrador íntegro.

## Evidencias y criterios de éxito separados

| Dimensión | Evidencia necesaria | Qué no demuestra |
| --- | --- | --- |
| Operación real del proveedor | Trabajo real completado/verificado, huellas exactas, modelo solicitado/devuelto, respuesta persistida, uso/duración observados. | Exactitud de las lecturas, geometría correcta o costo conocido si no hay tarifa. |
| Operación integrada | Cadena paquete→respuesta→extracción→conversión→geometría→configuración→plan→modelo→análisis→lectura→mapeo→resultado→informe vigente; IDs/SHAs, aceptaciones, estados y modos reales donde corresponda. | Validez física o normativa por el mero éxito del software. |
| Precisión de visión | Referencia humana revisada + correspondencias y huellas, medidas sobre la propuesta inicial preservada: cobertura, lecturas completas, valor/unidad/evidencia, duplicados, sin respaldo y sin clasificar; por lámina/tipo, con numeradores/denominadores. | Un porcentaje válido sin referencia, una corrección humana atribuida a IA o una evaluación de ingeniería. |
| Ingeniería | Parámetros/hipótesis/representación y fuentes adecuados, revisión competente del modelo/cálculo/resultados y alcance profesional. | Certificación por checkbox, hash, identidad declarada, informe documental o caso fuera del MVP. |
| Comparación manual ETABS | Modelo manual y criterios equivalentes revisados, mismas unidades/casos/hipótesis y comparación numérica con tolerancias justificadas, tiempos y cambios registrados. | Ahorro, equivalencia o precisión estructural antes de medirlos. |

El benchmark de precisión y la comparación manual ETABS se realizan al final según lo solicitado por el usuario. **Su aplazamiento no bloquea la infraestructura ni el éxito operativo de una cadena declarada**; se registran como evaluación pendiente y no se presentan porcentajes, equivalencia, ahorro o aprobación profesional inventados. Las puertas de datos completos/revisión explícita previas al motor sí siguen vigentes.

Para medir visión después, usar el evaluador existente con archivos privados revisados:

```powershell
.\.venv\Scripts\python.exe -m draft2model.evaluacion_vision --referencia RUTA_REFERENCIA_HUMANA.json --extraccion RUTA_PROPUESTA_ORIGINAL.json --correspondencias RUTA_CORRESPONDENCIAS_REVISADAS.json --salida RUTA_NUEVA_METRICAS.json
```

No llenar la referencia con la salida del mismo modelo y llamarla humana. Un denominador vacío produce null; no 100 %. No excluir fallos ni omisiones para mejorar métricas.

## Recuperación y criterios para detener un tramo

- **Paquete o fuente no vigente:** no enviar ni ejecutar. Conservar versiones, revisar el cambio y preparar una nueva cadena sobre fuentes correctas. No rehashar archivos alterados para hacer pasar recibos anteriores.
- **Proveedor sin clave o rechazo antes del intento:** mantener plan preparado/fallido sin envío; resolver presencia local o selección compatible al final. No leer/imprimir la clave. Un HTTP no 2xx o timeout puede haber generado consumo: no asumir costo cero.
- **Proveedor incierto:** consultar el mismo trabajo. `/api/proveedor/recuperar` solo acepta evidencia conservada completa o cierra con `{caso,trabajo,huella_preparacion,confirmacion_explicita:true,resolucion:'cerrar_sin_reintento'}`; no reenvía. Solo una decisión posterior explícita puede preparar otra llamada.
- **Importación interrumpida con reserva y sin recibo:** no duplicar extracción/geometría con otra clave. Revisar evidencia publicada y marcador, conservar ambos. Los flujos de respuesta/conversión/tabular pueden bloquear replay sin recibo; no hay recuperación genérica que permita borrar la reserva.
- **Faltante físico o representación no soportada:** no inventar un valor ni silenciar el requisito. Completar fuente/decisión revisada o detener ese tramo con el motivo exacto; se puede terminar una prueba operativa de subconjunto solo si ese alcance fue declarado y no se presenta como modelo completo del proyecto.
- **Motor incierto, worker interrumpido, retorno no cero, cierre no confirmado o hash cambiado:** conservar EDB/copias/trazas/recibos y la exclusión/marcador. No conectar a un PID histórico, reanudar automáticamente o borrar locks para seguir. Usar la recuperación controlada documentada y la revisión del coordinador. Una aceptación inferior no sustituye `aceptacion_integracion.json` o la aceptación web completa.
- **Lectura/mapeo incorrecto:** no recalcular el modelo para arreglar un filtro. Conservar tablas crudas, corregir/revisar correspondencias y normalizar aparte. Consultar `/api/normalizacion/estado`; usar su recuperación confirmada cuando exista publicación pendiente, sin generar resultados duplicados.
- **Informe no íntegro o fuentes cambiadas:** no descargarlo como vigente/aprobado. Revalidar y producir una versión nueva; no modificar cifras o el PDF publicado para ocultar un fallo.

## Intervención final imprescindible y bloqueos concretos actuales

1. **Proveedor real aún no ejecutado:** hace falta ID de modelo compatible autorizado para esa cuenta y credencial disponible localmente en el proceso ejecutor; su presencia no se comprobó. Solo si falta autorización para el envío/costo concreto se solicita al usuario al llegar al ensayo final; no se repite una autorización vigente. No se necesita esa intervención para seguir completando infraestructura.
2. **Los paquetes preparados (general 124 y detallado 135) no son una extracción revisada:** seleccionar detalles y revisar lecturas/ambigüedades de los planos, conservando propuestas y evidencia. Aún no hay valores físicos registrados que permitan saltar directamente al modelo.
3. **Faltan manifiesto físico y configuración del caso:** se necesitan datos/hipótesis/fuentes reales y declaraciones de revisión sobre geometría, configuración y modelo; no se sustituyen por la fixture, por el nombre de los PDF ni por aprobaciones de Codex para desbloquear puertas.
4. **Plantilla/capacidades y host deben confirmarse antes del motor:** plantilla EDB exacta, opciones representativas revisadas y preflight autorizado sin operación incierta. No se considera bloqueado por número de pisos o por `fuera_mvp_declarado`; el límite concreto lo determina el contrato/plan aplicable.
5. **Benchmark manual y precisión permanecen aplazados:** preparar su registro final y declarar no evaluado hasta contar con referencia humana/modelo manual. No bloquear por ello el cierre del tramo operativo ni afirmar que ese cierre ya demuestra ingeniería.

El coordinador puede avanzar autónomamente por todas las preparaciones, verificaciones de fuentes y borradores que no requieran una decisión física no documentada. Debe pedir únicamente el dato, acceso local o declaración que falte al llegar a su puerta, y continuar los tramos independientes sin solicitar nuevamente aprobación para cada paso rutinario.
