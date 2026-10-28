# Correspondencias visuales y contornos hacia geometría 0.3

Esta etapa combina una lectura de visión **sin coordenadas físicas en respuesta** con digitizaciones calibradas conservadas. `lectura_contornos.py` define y valida el contrato; `contornos_a_geometria.py` incorpora una transacción a una copia en borrador. Ambos son puros: no leen imágenes/expedientes, llaman proveedores ni ejecutan ETABS. No crean niveles, apoyos, propiedades, cargas, masa, suelo, continuidad ni aprobación.

## Contrato de red cerrado

`esquema()` devuelve `draft2model.contornos_planos`, versión `0.1.0`, utilizable como esquema estricto. `instruccion(caso, contexto)` explica los límites. La respuesta exige exactamente:

```text
contrato, version_contrato, caso,
evidencias: [{id, archivo_id, pagina, bbox_normalizada:[x0,y0,x1,y1], texto}],
dibujos: [{id, archivo_id, pagina, bbox_pagina:[x0,y0,x1,y1], plano_id,
  anclas: [{id,punto_resuelto,uv_local:[u,v],evidencias:[IDs]}],
  controles: [{id,punto_resuelto,uv_local:[u,v],evidencias:[IDs]}],
  puntos: [{id,uv_local:[u,v],relacionados:[IDs_resueltos],evidencias:[IDs]}]}],
elementos: [{id,tipo,accion:"nuevo",vertices:[IDs],dibujos:[IDs],evidencias:[IDs]}],
aberturas: [{id,host,vertices:[IDs],dibujos:[IDs],evidencias:[IDs]}],
faltantes: [textos]
```

`tipo` es `muro`, `losa`, `superficie_generica`, `columna` o `viga`. Caras y vanos necesitan al menos tres vértices distintos en su orden de contorno; frames necesitan dos extremos distintos. El host debe ser una superficie contextual o una cara nueva explícita. La topología global admite referencias entre dibujos/planos **ya resueltos**, sin inferir alturas entre ellos.

Todos los campos numéricos de red, salvo `pagina` entero positivo, son coordenadas normalizadas entre 0 y 1. `uv_local` se mide dentro del ROI del dibujo, origen superior izquierdo, u derecha y v abajo. Bboxes de dibujo/evidencia se miden sobre la página completa. El texto literal de una evidencia puede transcribir dimensiones, pero no se interpreta como coordenada métrica. Claves físicas adicionales, unidades, cotas, aprobación o actualización de objetos quedan fuera del esquema.

`validar_respuesta(respuesta, manifest, paginas_enviadas, contexto)` verifica caso, originales/SHA, páginas efectivamente enviadas, bboxes, IDs, puntos del plano contextual y evidencias por entidad. Cada evidencia debe estar dentro del ROI de alguno de los dibujos declarados para su entidad. Anclas/controles/puntos requieren evidencia propia. Los controles no pueden repetir un punto de ajuste. Las referencias de un punto nuevo son IDs usados por anclas/controles del mismo dibujo.

Menos de tres anclas conserva advertencia; no se inventan otras. Colisiones potenciales de puntos se conservan para que el merger las bloquee. Las listas de registros/referencias se ordenan para producir una huella independiente del orden de respuesta; **nunca se reordena el anillo de vértices**.

La salida enriquecida incluye `datos`, `contexto`, `huella_lectura`, `advertencias`, `faltantes`, revisión borrador y `ejecutable_etabs:false`. Cada dibujo incorpora `fuente:{original_id,sha256,pagina,dibujo_id,bbox_pagina}` y su `plano` contextual completo; cada evidencia incorpora `original_sha256`.

## Contexto construido por el servicio

`validar_contexto()` exige:

```text
geometria: {version_id, sha256_geometria, huella_contenido,
            sha256_geometria_canonica, unidad_longitud, datos_sinteticos},
planos: [{id,ejes,eje_constante,valor_constante,unidad_longitud,puntos_resueltos:[IDs]}],
puntos_resueltos:[IDs], superficies:[IDs], frames:[IDs],
catalogo_vertices:[{id,x,y,z,procedencia}]  # opcional, SOLO contexto
```

Las coordenadas contextuales pueden ser métricas: proceden de la geometría comprobada, nunca de la respuesta de IA. Si se aporta catálogo, sus IDs deben coincidir exactamente con `puntos_resueltos`, y el merger contrasta sus coordenadas/procedencia con la base. `frames` debe declarar los IDs ya preparados fuera del contrato geométrico, aunque sea una lista vacía explícita. Los planos deben declarar XY/Z, XZ/Y o YZ/X con unidad idéntica a la geometría; el merger verifica que sus referencias estén realmente en esa cota.

**Helper público:** `lectura_contornos.huella(geometria)` calcula `sha256_geometria_canonica`: SHA256 del JSON UTF8, `ensure_ascii=False`, `sort_keys=True`, `separators=(',',':')`, `allow_nan=False`, **sin newline**, incluyendo la revisión completa. `contratos.huella_contenido(geometria)` es diferente: excluye revisión. `sha256_geometria` sigue siendo la huella de los bytes del archivo comprobado por el servicio.

## Incorporación transaccional

```python
from draft2model.contornos_a_geometria import incorporar_contornos

# Cada valor procede de ServicioDigitizacion.consultar real y vigente.
registros = {dibujo_id: registro_completo_consultado}
resultado = incorporar_contornos(geometria_base, lectura_validada, registros)
if resultado["aplicado"] and resultado["validacion"]["consistente"]:
    geometria_hija_borrador = resultado["geometria"]
    frames_separados = resultado["frames_propuestos"]
```

El registro calculado debe tener `propuesta.id == dibujo.id`, la misma fuente, página, ROI, plano y correspondencias/puntos de la lectura. Para solicitar el cálculo353 se quitan de sus filas solamente las listas `evidencias`, conservándolas en la lectura; el servicio353 añade los vínculos fuente/plano. Los nueve límites métricos **no vienen en red**: se declaran por el procedimiento existente de digitización.

El merger comprueba huella de lectura/contexto, geometría canónica/contenido, naturaleza, huella y SHA del registro, vínculo geométrico, fuentes/planos y propuesta exacta. Reconstruye referencias métricas desde los vértices originales, reproduce `calibrar_digitizacion` y contrasta resultado, SHA y huella de entrada. No confía solo en `vigente`, en un resumen ni en números suministrados por IA. Rechaza acreditación documental/aprobación no permitidas. Deben cumplirse ajuste, error de controles presentes e incertidumbre máxima por punto; un umbral amplio de incertidumbre no permite ignorar un control que falla.

La incorporación mantiene los vértices referidos existentes **exactamente** y convierte los puntos nuevos calculados en metros a la unidad de la base, exigiendo representabilidad del viaje de ida/vuelta. Añade únicamente IDs nuevos; cualquier colisión con vértices, caras, huecos, niveles, nodos, muros o frames contextuales bloquea toda la transacción. No unifica automáticamente puntos físicamente coincidentes ni presupone continuidad.

Se validan juntas superficies/aberturas con `validar_geometria`. Ante un dibujo ausente/no reproducible, conflicto, punto fuera de límites o topología inválida se devuelven las colecciones originales y ningún frame nuevo; la lectura íntegra y diagnósticos permanecen disponibles. No se publica una parte incoherente. Una lectura vacía queda pendiente. Cada dibujo utilizado requiere un registro **calculado**: un registro solamente preparado o sin puntos calculados sigue pendiente, sin fabricar un cálculo para resolver topología.

Se conservan procedencia y faltantes anteriores, más los de la lectura y las carencias detectadas. La procedencia nueva referencia evidencias, lectura y digitizaciones. Conserva también las referencias de sus anclas/controles para evitar reutilizar puntos derivados como falsos controles independientes del mismo ajuste. La `trazabilidad` por punto conserva fuente/plano, incertidumbre y extrapolación. Las evidencias completas, incluidos SHA de originales, permanecen en `lectura_conservada`; las barras propuestas también las incluyen.

Tres anclas/sin controles suficientes pueden producir un cálculo en borrador, pero generan advertencias/faltantes. La extrapolación se conserva advertida si cumple el indicador declarado. Ninguna de estas condiciones acredita ingeniería ni ubicación documental real.

## Salidas y frontera de confianza

Salida: `geometria`, `aplicado`, `transaccion_completa`, `agregados:{vertices,superficies,aberturas,frames}`, `frames_propuestos`, `pendientes`, `conflictos`, `advertencias`, `faltantes`, `trazabilidad`, `lectura_conservada`, `validacion`, `validacion_propuesta`, `origen`, `revision_anterior`, `completo:false`, `aprueba_ingenieria:false`, `ejecutable_etabs:false`. `transaccion_completa` se refiere exclusivamente a esta incorporación, nunca al edificio completo. Frames tienen `{id,tipo,puntos,evidencias,procedencia}` y no se introducen en el contrato geométrico0.3.

La copia siempre termina en `revision:{estado:"borrador",aprobacion:null}`; la aprobación anterior se conserva solo como información externa. Una lectura/registro estructuralmente inválidos pueden lanzar `ValueError`; errores de un dibujo o de la transacción se devuelven como pendientes/conflictos.

**El módulo puro no autentica los bytes originales, archivos de código, revisión humana ni que `consultar()` se haya ejecutado.** Hashes que llegan juntos en datos modificables tampoco son una firma. La frontera exige que el servicio llamante obtenga y conserve versiones reales mediante `ServicioDigitizacion.consultar`, verifique original/geometría/código vigentes y vuelva a comprobar el padre antes de publicar. La reproducción algebraica protege números y relaciones con la base, no demuestra que un contorno o su uv correspondan al dibujo. Esta etapa no publica ni habilita ETABS.

Prueba focal propia: `.venv/Scripts/python.exe -B -m unittest tests.test_lectura_contornos tests.test_contornos_a_geometria -v`. Recibo con comando, salida y hashes: `seguimiento/CONTORNOS_AUTOMATICOS_357.json`. Solo fixtures propias sintéticas; sin planos reales, proveedores, GUI, integración HTTP ni suite completa.
