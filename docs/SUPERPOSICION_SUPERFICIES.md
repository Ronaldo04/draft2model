# Superposición horizontal de superficies v0.2

Extensión visual del servicio de superposición: permite contrastar contornos geométricos v0.2 con una página original mediante tres anclas **declaradas**, sin estimar escala por IA ni aprobar geometría/ingeniería. Conserva la ruta histórica de muros por nivel. Una superficie puede mostrarse en metros sin correspondencia; solo un registro consultado y vigente permite dibujarla sobre el original.

## Contrato de creación

Se conserva `POST /api/superposicion/crear`. El cuerpo v0.1 mantiene sus campos exactos y anclas `{nodo,punto}`. El cuerpo nuevo exige exactamente estos campos:

```text
caso, expediente_sha256, geometria, huella_geometria, sha256_geometria,
archivo, pagina, version_contrato, plano, superficies, anclas,
revisor_declarado, fecha, motivo, confirmacion_explicita
```

- `version_contrato="0.2.0"` selecciona explícitamente esta modalidad; no se admite el campo `nivel` ni mezcla de esquemas.
- `plano={"tipo":"horizontal","cota_m":2.6}` declara una cota Z física finita en metros, aunque la geometría fuente esté expresada en cm/mm. No crea un Story ni infiere niveles.
- `superficies`: lista no vacía de IDs de superficie existentes, sin duplicados. Todos los vértices de cada contorno deben tener Z normalizada **exactamente igual** a `cota_m`. No se aplica una tolerancia de ingeniería para aplanar un panel inclinado.
- `anclas`: exactamente tres objetos `{ "vertice":"V0", "punto":[u,v] }`, con tres IDs distintos y tres puntos distintos, dentro de [0,1]. Deben pertenecer a las superficies seleccionadas, por tanto al plano declarado. El campo `nodo` histórico se rechaza en esta modalidad incluso si el texto del ID coincide.
- Declaración/fecha/motivo/confirmación mantienen sus restricciones históricas; la identidad del operador continúa declarada, no verificada. La transformación afín requiere anclas bien separadas en modelo e imagen; no usa bbox como dimensión.

Ejemplo de anclas (las coordenadas de página son solo ilustrativas):

```json
[{"vertice":"V0","punto":[0.2,0.3]},
 {"vertice":"V1","punto":[0.8,0.3]},
 {"vertice":"V2","punto":[0.8,0.7]}]
```

## Esquema y consulta

`GET /api/superposicion/esquema` conserva niveles/nodos/muros de la fuente histórica. Para geometría v0.2 agrega `version_geometria`, `vertices_m` y `superficies`. Cada vértice normalizado conserva ID/XYZ/procedencia; cada superficie conserva sus campos de contrato más vértices XYZ normalizados, área geométrica m2, normal y criterio computacional derivados del validador. Los niveles pueden estar vacíos; no se inventan para que la UI funcione.

El registro persistido usa `version="0.2.0"`, `plano`, lista de superficies y anclas de vértice. Vincula versión/huella/SHA de geometría, unidad fuente, original/página, hash de vista previa y transformación. `transformacion.de="plano_horizontal_xy_m"` deja explícito que las coordenadas de la afín son metros; no cambia la unidad declarada del archivo original.

La consulta expone `version_contrato="0.2.0"`, `plano` y objetos `superficies` con área/procedencia/XYZ/contorno más `proyeccion=[{vertice,u,v,dentro_imagen},...]`. `nivel=null` se conserva solo como compatibilidad de lectura con el historial histórico: no identifica un piso ficticio. El historial incluye plano e IDs de superficie para esta modalidad.

Vértices fuera de la página se conservan en `fuera_imagen` con superficie/vértice/coordenadas, sin recortar el contorno ni cambiar la geometría para hacerlo encajar. La consulta reconstruye selección/plano/anclas/afín desde la geometría exacta; un hash recalculado de un registro incompatible no evita esa comprobación. No hay selección automática de una correspondencia anterior para una geometría nueva.

## Vigencia de fuentes

El servicio utiliza la consulta de geometría existente, que comprueba el contrato, su versión y las fuentes persistidas. Vuelve a obtener la página original visible y compara sus hashes/dimensiones. Tras renderizar comprueba de nuevo la geometría y los bytes del registro; una alteración observada impide devolver vigencia. Los contornos/procedencias derivan de esa geometría, no de IDs del contrato legado ni de una extracción diferente.

Las referencias documentales declaradas en una geometría importada no se convierten por este servicio en una certificación de que cada superficie existe o fue bien idealizada. La conversión y revisión de fuentes deben aportar esa evidencia. El registro visual no autentica competencia profesional ni sustituye revisar el plano.

## Montaje de interfaz

El coordinador debe montar en `index.html` estos controles usados por `superposicion.js`:

- `supTipo`: select con valores `muros_nivel` y `superficies_horizontal`.
- `supCota`: número con `step="any"`, etiqueta «Cota física Z (m), plano horizontal declarado».
- Mantener `supElemento`, `supNodo1..3`, `supU1..3`, `supV1..3` y demás controles históricos. Las etiquetas de ancla deben indicar nodo/vértice según modalidad; el selector de esta modalidad contiene exclusivamente vértices del contorno elegido.

La UI selecciona una superficie por registro; la API admite varias declaradas. Cambiar tipo/cota/superficie elimina la imagen/correspondencia abierta y consume la confirmación. Una cota vacía no se interpreta como cero. El detalle muestra ID, XYZ, área geométrica, papel declarado, procedencia y versión; los polígonos son contornos sin relleno/mallado. Un registro reabierto restaura su modalidad/cota y muestra la página vinculada.

## Verificación y capacidad pendiente

Ejecutado con TEMP/TMP en `tmp`: `python -m unittest tests.test_superposicion_superficies tests.test_revision_superposicion`: **14 pruebas correctas, 8.363 s**. Se verifican creación/consulta/listado, página PNG local, proyección afín conocida, unidades, área/procedencia, separación de IDs, rechazo de inclinados/cotas/anclas inválidas, puntos fuera de página, registro alterado con hashes rehechos y mutación de geometría después del render/original. Sin red/ETABS/proveedor.

La batería Node histórica pasó inicialmente **5 casos**. El coordinador agregó dos casos DOM de superficies y el log `tmp/superposicion_cliente_160.log` acredita **7 casos correctos**, incluidos polígono horizontal/cuerpo con vértice y plano/imagen y cambio de cota que consume confirmación sin enviar. El recorrido visual en navegador sigue pendiente de validación integrada; estas pruebas no lo sustituyen.

**Pendiente del objetivo completo:** vistas declaradas para superficies inclinadas/verticales, cortes pertinentes y revisión de su correspondencia espacial; esta modalidad horizontal no las sustituye. Mostrar un contorno no acredita sección de aligerado, huecos, malla/conectividad estructural, cargas, rigidez ni operación de cisterna/tanque. La capacidad física y su ejecución ETABS siguen sus propias puertas verificables.


Actualización164: la modalidad adicional v0.3 para planos inclinados/verticales está implementada y revisada localmente; ver [SUPERPOSICION_PLANO3D.md](SUPERPOSICION_PLANO3D.md). Se añadieron dos comprobaciones DOM (9 casos de cliente en total). Su QA navegador específica sigue pendiente. La QA horizontal160 sí quedó registrada en seguimiento/QA_SUPERFICIES_160.json. Las limitaciones físicas de componentes y la prueba con planos reales permanecen.
