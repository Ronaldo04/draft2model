# Conversión explícita de lecturas a superficies

La conversión transforma correspondencias físicas declaradas y lecturas revisadas en **geometría borrador**. No deduce escala desde imágenes, conectividad, tipo de losa, rigidez, cargas o acciones del agua. No importa ni aprueba automáticamente la geometría. Las referencias deben pertenecer a la exportación comprobada de la extracción vigente del caso.

## Versiones y campos exactos

`conversion_geometria.VERSION` permanece `0.1.0`; `VERSION_SUPERFICIES` es `0.2.0`. El contrato de manifiesto sigue siendo `draft2model.conversion_geometria`.

El manifiesto v0.1 conserva su esquema exacto y sus listas no vacías. No admite `vertices`/`superficies`. El manifiesto v0.2 exige todos los campos anteriores **más** ambas listas nuevas, sin campos adicionales:

```text
contrato, version_contrato, caso, datos_sinteticos, operador_declarado,
procedencia, unidad_longitud, sistema_coordenadas, ejes, escala,
niveles, nodos, muros, vertices, superficies
```

- `procedencia`: exactamente `tipo`, `descripcion`; tipo `sintetico` si `datos_sinteticos=true`, o `plano` si es falso. Una extracción sintética no puede convertirse en geometría real.
- `unidad_longitud`: `m`, `cm` o `mm`. `sistema_coordenadas`: `cartesiano_ortogonal`.
- `ejes`: exactamente `origen`, `direccion_x`, `direccion_y`, todos textos declarados. Al describir el origen, el operador debe dejar clara la referencia física vertical usada por sus coordenadas Z; las justificaciones de medidas conservan ese significado. No se infiere una cota desde bbox ni se añade una altura de piso por defecto.
- `escala`: exactamente `metodo="coordenadas_fisicas_declaradas"`, `descripcion` no vacía.
- `niveles`, `nodos`, `muros`: mismos elementos/campos v0.1; en v0.2 sus listas pueden estar vacías para no inventar objetos ajenos a un caso solo de superficies.
- `vertices`: lista de objetos con exactamente `id`, `x`, `y`, `z`. **Cada** coordenada usa una de las dos formas físicas siguientes; no admite números sueltos, `procedencia` manual ni otras claves.
- `superficies`: lista de objetos con exactamente `id`, `vertices`, `papel_geometrico`, `referencias`. El contorno es una lista ordenada de IDs de vértice; papel es texto declarado no vacío. `referencias` es una lista explícita no vacía de IDs de candidatos revisados, sin duplicados, que sustenta la conectividad declarada. No se decide que una etiqueta aislada prueba la conectividad técnica: esa correspondencia sigue siendo responsabilidad declarada del operador.

## Coordenadas físicas

Lectura de cota revisada:

```json
{"candidato":"C001"}
```

Declaración física del operador respaldada por referencias revisadas:

```json
{"valor":0,"unidad":"m","justificacion":"Origen vertical declarado para esta referencia física.","referencias":["C001"]}
```

El primer caso exige candidato de tipo `cota`, valor revisado numérico y unidad física conocida. El segundo exige justificación no vacía y referencias comprobadas; no constituye una medición automática de esos candidatos. Bool, null, valores no finitos, enteros sin representación exacta binary64, unidades desconocidas/píxeles o conversión numérica no representable se rechazan. Las unidades originales quedan trazadas; se normalizan a la unidad de geometría declarada.

## Geometría y trazabilidad

El manifiesto v0.2 produce geometría `draft2model.geometria` v0.2.0. Cada vértice obtiene procedencia derivada de la raíz más la unión ordenada y sin duplicados de las referencias de sus tres coordenadas. Cada superficie obtiene procedencia de la raíz más sus referencias explícitas. Ninguna procedencia o aprobación se fabrica desde una respuesta IA sin revisión.

Se conserva una correspondencia por coordenada con `ruta`, `modo` (`candidato_revisado` o `declaracion_operador`), referencias, valor/unidad original y valor/unidad de geometría. Cada superficie agrega:

```text
ruta=superficies[i], modo=conectividad_superficie_declarada,
referencias=[...], vertices=[IDs ordenados], papel_geometrico=texto declarado
```

La geometría final pasa por `validar_geometria`: referencias, unidades, planitud, área positiva, contorno simple y demás criterios de [GEOMETRIA_SUPERFICIES.md](GEOMETRIA_SUPERFICIES.md). Un contorno inválido se rechaza; no se triangula, rellena o reordena. La revisión final siempre es `borrador` sin aprobación. El bloqueo de integración estructural de superficies se conserva.

`convertir_lecturas` guarda `manifiesto.json`, `exportacion.json`, `geometria.json` y `trazabilidad.json`. La versión de trazabilidad corresponde a la del manifiesto. Sus hashes vinculan los bytes exactos de manifiesto/exportación/geometría, expediente y extracción; los IDs de candidato se interpretan contra esa exportación conservada, no contra otra lectura posterior.

La extracción y evidencia se comprueban al cargar, exportar y nuevamente antes de publicar. Se compara la exportación prevista con la vigente y se vuelven a leer los bytes exportados. Una mutación observada impide publicar la conversión; una exportación previa conservada no equivale a una geometría aceptada.

## Lectura, sellos y reproducción

API pura adicional:

```python
comprobar_reproduccion(exportacion, manifiesto, geometria, correspondencias)
```

Devuelve `None` solo si reconstruir desde manifiesto/exportación produce exactamente la misma geometría y correspondencias canónicas; de otro modo lanza `gestion_extraccion.ErrorEvidencia`. Acepta ambos manifiestos. No escribe, no aprueba y **no sustituye** comprobar que exportación, expediente y extracción siguen siendo fuentes legítimas y vigentes.

Los consumidores deben validar primero sellos/hashes/fuente conservada, verificar concordancia de versiones manifiesto↔trazabilidad↔geometría, ejecutar esta reproducción y revalidar fuentes al terminar. Un recibo con hashes recalculados de artefactos manipulados no basta para aceptar una conversión. La integración del lector HTTP/UI corresponde al coordinador; esta entrega no afirma haberla completado.

## Evidencia focal y límites

Ejecutado con TEMP/TMP en `tmp` del proyecto: `python -m unittest tests.test_conversion_superficies tests.test_conversion_geometria`: **16 pruebas correctas, 7.631 s**. Se cubren publicación sin importación, huellas de bytes, unidades equivalentes, coexistencia con muros, medidas/contornos/referencias inválidos, compatibilidad estricta v0.1, reproducción alterada y mutación del original después de exportar que impide publicar. Datos sintéticos; sin red, proveedor real ni ETABS.

Quedan fuera de esta entrega la revisión profesional de correspondencias físicas, propiedades estructurales, agujeros de superficie, representación de aligerados y ejecución ETABS del caso real. Una conversión válida acredita consistencia y procedencia declarada, no que ese modelo físico esté completo o sea seguro.
