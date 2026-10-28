# Interfaz de contexto técnico y explicaciones

`contexto.js` y `explicaciones.js` se cargan desde `index.html` y registran controles en `app.js`. Consumen las APIs públicas existentes mediante las rutas HTTP del integrador. No modifican validadores, servicios Python, proveedor, informes ni cálculos. No generan reglas, umbrales, coordenadas, parámetros físicos, citas ni aprobaciones.

## Registro y selección de contexto

El panel solicita el tipo y JSON completos, sin rellenar valores. Se registran solo contratos que ya contienen su revisión declarada y pasan los validadores del backend. La declaración explícita de registro es un control local del cliente; no se añade al cuerpo de la API ni se presenta como aprobación profesional.

| Ruta | Cuerpo exacto |
|---|---|
| `POST /api/contexto/corpus/registrar` | `{caso,expediente_sha256,manifiesto_json,archivos:[{nombre,contenido_base64}]}` |
| `POST /api/contexto/reglas/registrar` | `{caso,expediente_sha256,reglas_json}` |
| `POST /api/contexto/sitio/registrar` | `{caso,expediente_sha256,capa_json}` |
| `POST /api/contexto/recuperar` | `{caso,expediente_sha256,corpus,consulta,limite,resultado}` |
| `POST /api/contexto/consultar-sitio` | `{caso,expediente_sha256,sitio,longitud,latitud,resultado}` |
| `POST /api/contexto/evaluar` | `{caso,expediente_sha256,resultado,reglas,huella_resultados,huella_reglas}` |

Consultas: `GET /api/contexto/historial?caso&expediente_sha256`, `/api/contexto/version?caso&expediente_sha256&tipo&version` y `/api/contexto/derivado?caso&expediente_sha256&version`. Los nombres expresan parámetros de query; sus valores se codifican con `URLSearchParams`. El historial no registra ni deriva.

Antes de leer documentos, el cliente comprueba 1–20 archivos, hasta 4 MiB cada uno y 16 MiB de suma. Rechaza nombres repetidos, rutas, `..` y nombres reservados. Lee bytes con `arrayBuffer`, comprueba su tamaño y genera base64; no convierte el documento a texto ni calcula un SHA alternativo. El JSON de contrato queda como texto exacto, hasta 1 MiB UTF-8. El backend contrasta documentos, manifiesto, revisión declarada y huellas; el límite HTTP para corpus incluye la expansión de base64.

Las versiones de corpus/reglas/sitio se seleccionan expresamente y se consultan antes de habilitar una operación. Recuperación exige consulta y límite; sitio exige coordenadas declaradas EPSG:4326, sin ubicación inferida. Por defecto no se vinculan a un resultado: esa vinculación requiere marcar su casilla. Evaluación siempre usa el resultado comprobado por `d2m-result` y ambas huellas exactas. Cada consulta crea un derivado nuevo; no hay idempotencia ni reintento automático de estas mutaciones.

Las tres selecciones de derivados se consultan y reproducen antes de publicarse. Un derivado ligado a otros resultados o huella se rechaza. La abstención es una salida válida y visible. Sitio conserva capacidad portante y parámetros geotécnicos nulos; no se deducen de cobertura cartográfica. Una versión sin vigencia pierde su selección al relistar. Revalidar el mismo derivado conserva su selección y no emite un falso cambio a los consumidores.

## Explicaciones y contingencia

| Ruta | Cuerpo exacto |
|---|---|
| `POST /api/explicaciones/preparar` | `{caso,expediente_sha256,resultado,huella_resultados,derivados:{recuperacion,evaluacion,sitio},modelo,opciones:{max_tokens,timeout_s},clave_solicitud}` |
| `POST /api/explicaciones/ejecutar` | `{caso,trabajo,huella_preparacion,expediente_sha256,confirmacion_explicita:true}` |
| `POST /api/explicaciones/recuperar` | `{caso,trabajo,huella_preparacion,confirmacion_explicita:true,resolucion:'cerrar_sin_reintento'}` |

Consultas: `GET /api/explicaciones/trabajos?caso` y `/api/explicaciones/trabajo?caso&trabajo`. Preparar exige resultado comprobado, modelo declarado y opciones explícitas: tokens enteros 256–16384 y espera entera 1–180 s. Cada derivado opcional se envía como UUID seleccionado o null. La misma preparación conserva su clave después de un fallo de red; otro contenido genera otra clave. No hay campo de credencial ni URL de proveedor en la UI.

Ejecutar requiere trabajo preparado vigente y coincidencia de resultado/huella, derivados, modelo y opciones actuales. La confirmación advierte transmisión potencial y costos, no estimados. Sin clave u otras causas documentadas por el backend se muestra `CONTINGENCIA DETERMINÍSTICA · SIN LLM REAL`. Una respuesta sintética verificada se distingue de una generación real. Toda salida mantiene `propuesta_pendiente_revision_humana`, `aprueba_resultados:false`, `aprueba_informe:false` y `conformidad_normativa:'no_evaluada'`. Verificar cifras y citas no verifica el sentido técnico del texto libre.

Solo el trabajo seleccionado `en_ejecucion` se sondea cada cuatro segundos, hasta 30 consultas. El sondeo no ejecuta, no prepara ni vacía otros paneles. Estados iguales conservan confirmaciones y no republican eventos idénticos. Cambiar fuentes, caso, huella o trabajo cancela consultas anteriores y descarta respuestas/errores obsoletos. Una salida sin vigencia no se publica ni se presenta como aceptada. Recuperar requiere confirmación propia, conserva evidencia y cierra sin reenvío; no elimina la posibilidad de que un envío incierto haya tenido costo.

## Eventos y contrato pendiente del informe

`d2m-context` publica solo selecciones comprobadas, con esta forma:

```text
{caso, expediente_sha256, resultado:{id,huella}|null,
 derivados:{recuperacion:consulta_derivado|null,
            evaluacion:consulta_derivado|null,
            sitio:consulta_derivado|null}}
```

Cada consulta incluye UUID, tipo, huella de salida, fuentes exactas, resultado vinculado cuando existe, salida y límites de aprobación. Cambiar el resultado limpia las selecciones derivadas anteriores. Seleccionar otra versión de fuente no reescribe un derivado histórico: su propio conjunto de fuentes sigue explícito en el detalle y se verifica al consultarlo.

`d2m-explanation` publica la proyección pública completa del trabajo con salida vigente ligada al resultado seleccionado, o null cuando se invalida. Incluye los UUID de sus derivados, huellas, modo y límites. No aprueba ni importa automáticamente nada.

La vinculación de contexto y explicación al informe **queda pendiente del contrato final de referencias opcionales**. Los paneles y eventos están disponibles; esta entrega no modifica `informes.js`, no añade referencias por omisión y no afirma que el informe ya las consume. El integrador mantiene HTTP y el servicio; ver [guía del contexto](REVISION_CONTEXTO_WEB.md) y [guía de explicaciones](REVISION_EXPLICACIONES_WEB.md) para validación y límites completos.

## Verificación focal

```powershell
& 'C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests/revision_contexto_frontend.cjs
& 'C:\Users\HP\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' tests/revision_explicaciones_frontend.cjs
```

**Una pasada: 10/10 contexto y 16/16 explicaciones OK.** Se ejecutan módulos reales con bus compartido, DOM/HTTP simulados y temporizadores controlados. Se comprueban base64 exacto, límites antes de leer, registro declarado, abstención, sitio explícito, evaluación con huellas, resultado ajeno, vigencia, clave idempotente, confirmación, contingencia, recuperación sin reenvío, sondeo acotado, conservación de otros paneles y carreras por caso/versión/huella. No se ejecutaron pruebas Python ni suite completa en esta entrega; HTTP fue asignado al integrador. Sin red, LLM real, API key, ETABS ni CU.
