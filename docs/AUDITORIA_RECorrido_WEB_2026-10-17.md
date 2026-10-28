# Auditoría del recorrido web hacia cálculo y entrega

Fecha: 17 de octubre de 2026. Revisión estática acotada del código local; no se ejecutó ETABS, red, navegador, Computer Use ni suite de pruebas. No se modificaron código, pruebas u otros documentos. No se encontraron instrucciones AGENTS.md en los ancestros consultados ni en docs/draft2model. Esta auditoría no acredita cierre del proyecto ni decisiones de ingeniería.

## Conclusión comprobada

La interfaz de revisión llega a geometría y configuración versionadas con aprobación explícita. La construcción ETABS, revisión propia del modelo, análisis, normalización, panel e informe existen en módulos y puntos de entrada CLI; **no están conectados a esta interfaz HTTP**. El cálculo dinámico con motor real y fixture sintética y sus entregables registrados en la parte superior de RETOMAR.md son evidencia de otra vía operativa, no de un recorrido web completo.

CONTEXTO_PROYECTO.md y PLAN_OPERACION.md definen la secuencia y las aprobaciones, pero sus cuadros de estado de octubre 13/14 son antecedentes: no deben usarse para negar los módulos posteriores que el código y RETOMAR.md ya documentan. El estado superior de RETOMAR.md mantiene pendientes integración UI, reproducibilidad y planos/visión finales; además mantiene Computer Use detenido por Escape.

## Frontera actual de producto

| Tramo requerido | Evidencia local de implementación | Alcance de la pantalla actual |
| --- | --- | --- |
| Ingreso de originales | `__main__.main`, comando `ingresar`, llama `ingreso.registrar_expediente` | Solo elige casos ya registrados. `app.js` indica usar ingreso por comando si no existen casos; no carga planos nuevos. |
| Planos y lecturas | `RevisionLocal.documentos`, `_original`, `pagina`, `version`, `actuar`; `app.js` `openCase`, `openPage`, corrección y exportación | Consulta páginas, superposición de bbox de candidatos, importación JSON, corrección versionada y exportación local. No ejecuta proveedor ni convierte lecturas automáticamente. |
| Geometría | `RevisionLocal.geometria`, `actuar_geometria`; `app.js` `openGeo`, `geoBody`, aprobación | Importación/revisión de JSON completo, consulta de evidencia y aprobación propia explícita. El visor superpone evidencia de lecturas; no dibuja la geometría como planta editable. |
| Configuración estructural | `revision_configuracion.ServicioConfiguracion.listar/consultar/actuar`; `configuracion.js` `reason`, `open`, `base` | Importación/revisión de JSON completo y aprobación propia condicionada a geometría aprobada, consistencia y faltantes. No crea una configuración guiada desde geometría. |
| Plan y construcción | `operaciones_etabs.generar_plan`; `ejecucion_modelo.EjecutorVerificado.preparar/ejecutar`; CLI `plan-etabs`, `construir-etabs` | Sin selector, resumen, preparación ni botón de ejecución. `planes-versionados` corresponde al plan geométrico ligado a versión; no debe confundirse con el plan ejecutable CSI. |
| Modelo construido y su aprobación | `revision_modelo.registrar`, `consultar`, `aprobar`, `consultar_aprobacion`; CLI `revision-modelo` | No lista modelos ni acepta los controles de revisión del modelo. La aprobación de configuración mostrada no autoriza por sí sola análisis. |
| Análisis y tablas | `analisis_etabs.AnalizadorEtabs.preparar_analisis/ejecutar_analisis`; CLI `analizar-etabs`; `cli_etabs.main`, operación `leer-tablas` | Sin preparación, ejecución explícita, estado de trabajo, fallos, recuperación o consulta de tablas. |
| Indicadores normalizados y evidencia | `normalizacion_etabs.registrar_resultados`; `evidencia_analisis.verificar_evidencia/verificar_fuente`; CLI `normalizar-etabs` | No selecciona mapeo revisado, corrida ni resultado; no muestra cadena modelo/análisis/EDB/resultado. |
| Panel, evaluación e informe | `panel_tecnico.crear_panel`; `informe.crear_informe/validar_informe/exportar_informe/aprobar_informe`; CLI `panel-tecnico`, `informe` | No abre ni genera esos artefactos, no selecciona reglas/contexto/corpus ni registra revisión documental. La CLI de informe exporta borrador; la aprobación documental es capacidad Python separada. |

La frontera se verifica exhaustivamente en `revision_visual.ManejadorRevision.do_GET/do_POST`: GET publica únicamente `/api/casos`, `/api/documentos`, `/api/version`, `/api/geometrias`, `/api/geometria`, `/api/configuraciones`, `/api/configuracion` y `/api/pagina`. POST admite solo importar/corregir/exportar extracción e importar/revisar/aprobar geometría o configuración. El resto responde 404. `revision_web/index.html` carga exclusivamente `/app.js` y `/configuracion.js` y termina después de la sección de configuración; tampoco hay enlaces al panel o informe. `style.css` presenta estas mismas secciones sin comportamiento de integración.

## Protecciones existentes que debe conservar la integración

- HTTP: `ServidorRevision` escucha en 127.0.0.1. `permitido` comprueba Host, Origin, Sec-Fetch-Site y token de sesión; POST exige Origin exacto. Se limita JSON a 2 MiB y se ocultan rutas/contenidos privados en errores. Los endpoints nuevos deben pasar por las mismas comprobaciones.
- Evidencia: `RevisionLocal.expediente/_original` comprueban autorización declarada, rutas internas sin enlaces y SHA256. Las mutaciones comparan el SHA del expediente y la huella abierta; geometría/configuración comparan también el SHA del archivo. No aceptar rutas absolutas arbitrarias enviadas por el navegador como sustituto de identificadores controlados.
- Revisión: guardar crea borrador y conserva versiones anteriores. `geoApprovalReason` y `configuracion.js reason` bloquean aprobación si hay cambios sin guardar/faltantes o faltan declaraciones. La validación y autorización definitivas deben seguir en servidor y módulos, no depender del botón deshabilitado.
- Construcción: `EjecutorVerificado._revalidar` regenera/compara plan, revisa configuración/geometría y copia exacta; preserva incertidumbre ante fallo. `ejecutar` exige confirmación real y consume una preparación propia. No sustituir esta puerta por llamada directa al ejecutor base.
- Modelo/análisis: `revision_modelo.aprobar` liga huella y origen y exige todos sus controles explícitos; `consultar_aprobacion` los revalida. `AnalizadorEtabs` exige esa aprobación, copia exacta, casos explícitos y revalidación de solicitud/entradas. Aceptar cálculo mantiene `aprueba_resultados: false`.
- Concurrencia: el `RLock` de revisión solo ordena mutaciones de esa instancia web. No reemplaza exclusión de motor entre clientes/procesos. Los trabajos nuevos deben compartir el bloqueo ETABS existente y conservar marcadores de incertidumbre. `RegistroCorridas` ofrece persistencia/huellas/transiciones pero no ejecuta ni reintenta ETABS; tampoco lo instancia la interfaz actual.
- Salidas: `evidencia_analisis` cruza resultado, selectores, tablas, análisis aceptado y EDB exacto. Panel/informe revalidan la fuente cuando se proporciona; no basta `motor.tipo=real`. `exportar_informe` vuelve a exigir evidencia, geometría y corpus exactos; `aprobar_informe` es aprobación documental propia y ligada a huella.

## Brechas concretas y siguiente implementación propuesta

Esta secuencia es una propuesta de programación, no una autorización para ejecutar motor ni aprobar ingeniería durante la auditoría.

### 1. Navegación y consulta de resultados ya existentes

Crear un servicio acotado, por ejemplo `draft2model/revision_resultados.py`, con resolución de identificadores de caso/resultado/corrida desde raíces controladas y revalidación mediante `verificar_evidencia`. Añadir rutas de consulta a `revision_visual.py`, sección en `revision_web/index.html` y controlador nuevo `revision_web/resultados.js`; añadir estilos mínimos a `style.css`.

Criterios: seleccionar resultado y corrida explícitos del mismo caso; mostrar huellas y vínculo a modelo/aprobación/EDB; mantener visible motor real con datos sintéticos y resultados sin revisar; rechazar mezcla de casos o evidencia alterada; no recalcular ni normalizar al abrir una página; no elegir la última carpeta por nombre como si fuera el resultado vigente.

El panel HTML autónomo contiene scripts y estilos inline; servirlo con la CSP actual del manejador (`default-src 'self'`, scripts restringidos) requiere diseño deliberado. Preferir datos JSON revalidados y JS externo de la interfaz, o una vista aislada con política explícita y restringida. No relajar globalmente la CSP para habilitar todos los artefactos.

### 2. Trabajos de preparación, construcción y análisis deliberados

Crear `draft2model/revision_ejecucion.py` como servicio de trabajos y añadir controlador `revision_web/ejecucion.js`. Reutilizar `EjecutorVerificado`, `revision_modelo` y `AnalizadorEtabs`, manteniendo sus puertas. Las operaciones largas deben devolver identificador/estado y consultarse después; no ejecutar ETABS dentro del hilo HTTP de una solicitud hasta terminar ni tratar `busy` de JS como bloqueo global.

Criterios: preparar no toca ETABS; ejecutar se presenta aparte sobre los mismos IDs/huellas; dos solicitudes concurrentes no crean dos operaciones de motor; reintento de POST no duplica mutaciones; reinicio del servidor conserva estado/artefactos; timeout o desconexión no declara éxito ni borra incertidumbre; se distingue preparación, ejecución, aceptación, fallo y recuperación. Confirmaciones de modelo deben seguir siendo independientes de geometría/configuración y de ejecutar análisis. Probar con dobles antes de cualquier ensayo real explícitamente autorizado.

### 3. Lectura y normalización revisadas

Extender el servicio anterior o añadir `revision_normalizacion.py` para ligar lectura de tablas a corrida aceptada, EDB y mapeo revisado; reutilizar `registrar_resultados` y el verificador de evidencia.

Criterios: conservar respuesta CSI original y mapeo; no escoger tablas/ejes/factores por aproximación; diferencias `Case`/`OutputCase` siguen la política acotada del normalizador; ausencia de fila permanece null; un periodo modal sin eje no se transforma en periodo X/Y; publicar una versión nueva y mostrar por qué se rechazó una mezcla de entradas. La aprobación del mapeo no aprueba resultados ni normativa.

### 4. Panel e informe desde los contratos elegidos

Crear `revision_entregables.py` que llame a `crear_panel`, `crear_informe` y `exportar_informe`; registrar versiones de los artefactos y fuentes exactas. Añadir selección explícita de reglas/contexto/geometría/corpus y descarga por identificador controlado. Incorporar acción separada para `aprobar_informe` con declaración propia y validación vigente del contenido antes de publicar una nueva versión.

Criterios: cifras/unidades/casos coinciden entre contrato, panel e informe; siete bloques conservan faltantes y estado pendiente cuando corresponda; sin reglas no se declara conformidad; el sitio del panel actual es «No disponible» y no debe presentarse como consulta ya integrada; cambiar resultados/reglas/corpus exige regenerar y revisar lo afectado; no se sobrescriben entregables existentes; las aprobaciones no se heredan. Un borrador puede consultarse/exportarse con su estado visible y no se presenta como informe aprobado para entrega.

### 5. Completar tramo documental antes del ensayo final

La web todavía requiere trabajo de ingreso, preprocesamiento/recortes, ejecución de visión, correspondencias de conversión y una corrección geométrica más accesible que JSON completo. Integrar esos módulos existentes preservando procedencia, observación/hipótesis y cambios versionados. Validar primero el recorrido local reproducible con fixture portable; después ejecutar la etapa acordada de planos de referencia, proveedor real y comparación manual, sin reclasificar una tipología fuera del MVP.

## Contrato concreto propuesto: ServicioResultados(app)

Primera capa de solo lectura, en un archivo nuevo `draft2model/revision_resultados.py`. `app` es `RevisionLocal`, utilizado para `app.raiz` y `app.expediente(caso)`. No importar clases de `revision_visual` desde el servicio para evitar dependencia circular. No añadir `actuar`, ejecutar motor, normalizar, aprobar o generar archivos en esta capa.

Métodos propuestos:

```python
listar_resultados(caso: str) -> dict
consultar_resultado(caso: str, version: str, *, expediente_sha256: str) -> dict
listar_modelos(caso: str) -> dict
consultar_modelo(caso: str, version: str, *, expediente_sha256: str) -> dict
```

Endpoints GET sugeridos: `/api/resultados`, `/api/resultado`, `/api/modelos`, `/api/modelo`. Las consultas de detalle requieren `caso`, `version` y `expediente_sha256` obtenido en el listado; una huella desactualizada responde 409 y exige recargar. Listados: `{caso, expediente_sha256, versiones: [...]}`. Cada fila: `{id, vigente, problemas: [codigo_estable], resumen: {...} | null}`. Un identificador de carpeta de 32 hexadecimales es candidato a versión, no acredita validez. Incluir inválidos con estado y sin valores no verificados, en vez de ocultar silenciosamente el problema. Carpeta ausente produce lista vacía; carpeta enlazada o fuera de raíz se rechaza. Ordenar IDs para estabilidad, sin llamar «más reciente» al último UUID.

Detalle de resultado propuesto:

```json
{
  "id": "UUID de la carpeta resultados_estructurales",
  "caso": "identificador del caso",
  "expediente_sha256": "SHA256 actual del expediente",
  "vigente": true,
  "huella_resultados": "huella semántica verificada",
  "datos": "objeto completo del contrato resultados_estructurales",
  "metadatos": {
    "configuracion_id": "identidad interna de la configuración",
    "huella_configuracion": "huella semántica",
    "geometria_version_id": "versión geométrica",
    "sha256_geometria": "SHA256 de bytes geométricos",
    "sha256_respuesta_tablas": "SHA256 de respuesta cruda",
    "sha256_edb_leido": "SHA256 del EDB",
    "corrida_tablas_id": "corrida de lectura",
    "mapeo_revision_vigente": true
  },
  "evidencia_analisis": null,
  "estado_evidencia_analisis": "no_vinculada",
  "revision_resultados": "pendiente",
  "conformidad_normativa": "no_evaluada"
}
```

Los textos explicativos en el ejemplo JSON representan valores, no tipos de un contrato implementado. `vigente=true` aquí significa paquete normalizado íntegro, entradas actualmente comprobables y mapeo revisado: **no significa análisis aceptado vinculado ni resultados aprobados**. En la primera capa se puede dejar `evidencia_analisis=null` aunque `motor.tipo=real`. La vinculación posterior exige corrida seleccionada explícitamente y `verificar_evidencia`; nunca deducir una ruta de análisis desde el UUID de lectura, porque son identidades diferentes. No exponer mapeo/trazabilidad/respuesta/configuración crudos: incluyen rutas locales.

Detalle de modelo propuesto: `{id, caso, expediente_sha256, vigente, huella_modelo, metadatos, revision: {estado: "pendiente", aprobacion: null}}`. Metadatos por lista permitida: `datos_sinteticos`, `modo`, `huella_plan`, `sha256_modelo`, `configuracion_id`, `huella_configuracion`, `geometria_version_id`, `sha256_geometria`; sin devolver `ruta` ni el objeto `origen` anidado completo. `revision_modelo.consultar` devuelve pendiente aunque exista una aprobación en otra carpeta: no inventar un estado agregado aprobado. Si se incorpora después un `aprobacion_id` explícito, validarlo con `consultar_aprobacion` y comprobar que corresponde al modelo elegido; presentar su alcance e identidad declarada independientemente de configurar/construir.

Reutilización y API que falta:

| Necesidad | Función pública reutilizable / cambio acotado |
| --- | --- |
| Autorización y SHA del manifiesto actual | `app.expediente(caso)` antes y después de leer. Si cambió durante la operación, rechazar y recargar. No afirmar que el contrato histórico guarda SHA del expediente cuando no lo contiene. |
| Modelo íntegro y entradas vigentes | `revision_modelo.consultar(raiz, caso, modelo)`. Internamente regenera el plan y comprueba configuración/geometría, aceptación integrada, EDB y traza. Proyectar campos de salida para eliminar rutas. |
| Aprobación propia de modelo | `revision_modelo.consultar_aprobacion(raiz, caso, aprobacion)` solo con ID explícito; no llamar `aprobar`. |
| Configuración vigente | `modelo_estructural.comprobar_configuracion` y `huella_configuracion`; si la selección aporta UUID de versión registrada, usar además `gestion_configuracion.consultar` para validar su cadena y comparar contenido. El `configuracion.id` interno no es el UUID de `configuraciones_estructurales`; no pasarlo como si lo fuera. Una configuración snapshot puede ser operativa sin fila de versión registrada: declararlo, no fabricar vínculo. |
| Resultado normalizado sin exigir análisis enlazado | **Falta función pública** en `evidencia_analisis`: proponer `verificar_resultado_normalizado(raiz, caso, resultado) -> dict` que reutilice internamente `_verificar_resultado` y devuelva únicamente `{resultado_id, resultados, huella_resultados, sha256_respuesta_tablas, sha256_edb_leido, configuracion_id, huella_configuracion, geometria_version_id, sha256_geometria, mapeo_revision_vigente}`. Revalidación actual completa de paquete, mapeo, rederivación, configuración/geometría y EDB, sin exigir carpeta de análisis. No devolver `traz`, `modelo`, `datos_tablas` del retorno privado. |
| Análisis aceptado vinculado, cuando se seleccione después | API pública existente `evidencia_analisis.verificar_evidencia(raiz, caso, resultado, corrida)` devuelve snapshot sin rutas locales y valida el vínculo fuerte. `validar_evidencia` solo valida snapshot/resultado; no reemplaza relectura de ficheros. |
| Forma y huella de resultados | `resultados_estructurales.exigir_resultados` y `huella_resultados`, ya usados por el verificador. Leer solo `resultados.json` y llamar estas funciones sería insuficiente para vigencia del paquete. |

El servicio web no debe llamar `_verificar_resultado`, `_folder`, `_leer` ni `_verificar_analisis`. Encapsular esas funciones dentro de la nueva API pública de evidencia permite mantener una única política de verificación. Para enumerar carpetas, usar el directorio de caso devuelto por `app.expediente`, validar confinamiento/enlaces y nombres, y delegar el significado de cada versión a las APIs anteriores. Los errores HTTP deben mapearse a códigos estables sin interpolar mensajes internos con rutas. No serializar objetos `Path` ni configuraciones anidadas «por comodidad».

Criterios focales de esta capa: listados de cero/una/múltiples versiones; candidato corrupto visible sin cifras; modelo consultado siempre sin aprobación implícita; rechazo de ID/ruta/enlace/caso ajeno; expediente cambiado; alteraciones de EDB/tablas/selectores/configuración/geometría; respuesta completa sin rutas de Windows ni directorios del host; datos sintéticos conservados; resultado real declarado visible como no vinculado cuando no se seleccionó análisis. Verificar ausencia de llamadas a preparación/ejecución/aprobación y de escrituras durante todos los GET.

## Comprobación mínima de la siguiente entrega

Pruebas focales HTTP/servicio: IDs/rutas inválidos, token/origen, huella obsoleta, aprobaciones independientes, resultado de otra corrida, evidencia alterada, trabajo duplicado, exclusión y recuperación. Prueba integrada sin ETABS real: configuración sintética aprobada -> preparación -> doble de construcción -> revisión explícita de modelo -> doble de análisis -> tablas/mapeo -> resultados -> panel/informe borrador -> revisión documental propia. Verificación de recursos JS/CSP y navegación de artefactos sin Computer Use mientras siga detenido. Una comprobación visual posterior requiere autorización humana vigente para reanudar esa vía; no es condición para continuar implementación y pruebas de archivo/HTTP.

No se repitió la suite completa ni se reinterpretó su estado: la suite en curso que figura en RETOMAR.md corresponde a la coordinación principal. Esta revisión aporta frontera de código y criterios de integración; no sustituye evidencia de ejecución o revisión técnica de los planos.
