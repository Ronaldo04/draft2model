# Contraste espacial explícito de geometría y plano

- **Ruta:** `D:/RONALDO CUCHILLA/1. RONALDO CUCHILLA/2. INGENIERÍA CIVIL DOCS AND PROJECTS/AECODE CURSOS/AECODE AI TALENT/PROYECTO FINAL`.
- **Qué cubre:** la brecha P06/O4.2 con una previsualización por nivel y una correspondencia **declarada** de tres anclas. No es un editor gráfico.
- **Archivos sin tocar:** contratos geométricos, `sitio.py`, informe/core, paneles de informes, resultados y tabular, y las versiones existentes.

## Modelo y decisiones

- **Esquema por nivel:** muros cuyo `nivel_inferior` es el nivel seleccionado (planta del nivel). Cada muro incluye el ID, los extremos con su XY, la longitud euclídea en la `unidad_longitud` del contrato (sin conversión), el espesor (`null` si es un faltante declarado) y los niveles.
- **Origen de los datos:** la geometría se obtiene con `app.geometria` (`gestion_geometria.consultar_version`), así que no se duplica el validador. Se acepta un borrador para revisión; `disponible_para_modelado` solo es `true` si el contrato lo permite y la geometría está aprobada. La superposición nunca habilita el modelado.
- **Sistema de imagen:** coordenadas normalizadas `[0,1]` de la página visible que entrega `/api/pagina` (respeta `/Rotate`, CropBox y EXIF). Es el mismo sistema que `bbox_normalizada`. Solo se usa el original y su preview existente; nunca imágenes preprocesadas.
- **Anclas:** exactamente tres pares `{nodo, punto:[u,v]}` con `u,v ∈ [0,1]` finitos, nodos existentes que pertenezcan a muros del nivel, y tres nodos y tres puntos distintos.
  - **Estabilidad numérica:** se rechazan los triángulos casi colineales en el modelo o en la imagen. La medida es `área/(lado mayor)²`, con mínimo `1e-3`.
- **Transformación afín exacta** de modelo XY a página normalizada: `[[a,b,c],[d,e,f]]`, con `u=a·x+b·y+c` y `v=d·x+e·y+f`. Se resuelve con las tres anclas y se verifica de vuelta con tolerancia `1e-9`.
  - No se infiere escala ni unidad desde bboxes o lecturas.
  - La inversión del eje y (imagen hacia abajo) queda implícita en las anclas declaradas.
- **Sin correspondencia** solo se dibuja el esquema métrico, con la advertencia «NO está alineado».

## API del servicio `ServicioSuperposicion(app)` (`draft2model/revision_superposicion.py`)

**Lectura**

| Llamada | Qué devuelve |
|---|---|
| `esquema(caso, version, expediente_sha256=)` | Esquema por nivel, unidad, huella, SHA, estado de revisión y extensión. |
| `listar(caso, expediente_sha256=)` | `{versiones:[{id, vigente, geometria, nivel, archivo, pagina} \| {id, vigente:false}], seleccion_automatica:false}` |
| `consultar(caso, version, expediente_sha256=)` | El registro más `muros` con su `proyeccion` (u, v y `dentro_imagen` de cada extremo) y `fuera_imagen` **sin recortar**. Incluye `naturaleza:'correspondencia_declarada_no_deteccion'` y `aprueba_ingenieria:false`. |

**Registro: `crear(body)`**

Cuerpo exacto:

```
{caso, expediente_sha256, geometria, huella_geometria, sha256_geometria, archivo, pagina, nivel,
 anclas:[{nodo, punto:[u,v]}×3], revisor_declarado, fecha, motivo, confirmacion_explicita:true}
```

**Persistencia:** `<caso>/superposiciones/<uuid>/`.
- `correspondencia.json` contiene:
  - el caso, `fp`, y la geometría con `{id, huella, sha256, unidad_longitud, estado_revision}`;
  - la fuente: `{archivo, sha256_original, pagina, sha256_preview, preview_px, sistema}`;
  - el nivel, las anclas, la transformación y la declaración;
  - `aprueba_ingenieria:false` y `aprueba_geometria:false`.
- `version.json` guarda el SHA del registro.
- Se publica mediante staging en `.sup-*` y `rename`. Nada se sobrescribe ni se hereda.

**Revalidación en cada consulta**, sin autoajustar huellas:
1. Archivos exactos y SHA del registro.
2. Caso y `fp`.
3. Geometría vigente con la misma huella y SHA. Una versión corregida exige una correspondencia nueva; la antigua sigue ligada a su versión inmutable.
4. Unidad, nivel y nodos.
5. Recálculo de la matriz desde las anclas, que debe dar la misma matriz.
6. SHA del original y SHA de los bytes del preview.
7. Relectura final.

Los errores se lanzan como `ErrorSuperposicion` (`ValueError`), con mensajes fijos sin rutas.

## HTTP (`revision_visual.py`, cambios localizados)

| Método | Ruta |
|---|---|
| GET | `/api/superposicion/esquema?caso&version&expediente_sha256` |
| GET | `/api/superposicion/historial?caso&expediente_sha256` |
| GET | `/api/superposicion/version?caso&version&expediente_sha256` |
| POST | `/api/superposicion/crear` (límite general de 2 MiB) |

- Para el preview se reutiliza la ruta existente `/api/pagina`.
- Se mantienen la sesión, el `Origin` y el `Host`; los errores del servicio responden 409.
- `superposicion.js` se añade a `WEB_ASSETS`.

## UI (`revision_web/superposicion.js`; montaje en `index.html` y `app.js`)

**Montaje:**
- Sección «Esquema por nivel y contraste con el plano original», situada después de «Geometría versionada».
- `<script src="/superposicion.js">` y `window.overlayControls?.()` en `controls()`.
- Hook localizado sin editar `openGeo`: un `addEventListener('change')` sobre `geoVersion` recarga el esquema de esa versión y exige una correspondencia nueva.
- `d2m-geometry-created` refresca la lista de geometrías y `d2m-case` limpia todo el estado. Las respuestas tardías se descartan por caso, `fp` y secuencia.

**Funciones:**
- Seleccionar geometría, nivel, elemento, original y página.
- Detalle del elemento con `textContent`: ID, extremos, longitud y espesor con su unidad, niveles, versión y estado, y la proyección y la fuente cuando hay correspondencia.
- Dibujo en SVG creado con `createElementNS` y `setAttribute` numéricos; no hay `innerHTML` ni `eval`.
  - **Sin correspondencia:** esquema métrico ajustado con el eje y invertido.
  - **Con correspondencia consultada:** el preview como `<image>`, con `viewBox` del tamaño en píxeles del preview, y las líneas proyectadas (u·w, v·h). Fondo y geometría comparten el mismo sistema y el dibujo se adapta al ancho.
  - Las anclas se marcan con círculos y los puntos fuera de imagen se listan sin recortar.
- **Registro:** tres anclas (nodo, u y v), revisor, fecha, motivo y confirmación. Cualquier cambio desmarca la confirmación. Después del registro se lista y se consulta la nueva versión.

## Pruebas

```bash
TEMP=$PWD/tmp TMP=$PWD/tmp python -m unittest tests.test_revision_superposicion tests.test_revision_visual tests.test_revision_tabular_http tests.test_revision_aprobacion_resultados_http tests.test_gestion_geometria
```

```bash
node tests/revision_superposicion_frontend.cjs
```

Regresión de `app.js` en Node:

```bash
node tests/revision_tabular_frontend.cjs
```

```bash
node tests/revision_conversion_frontend.cjs
```

```bash
node tests/revision_resultados_frontend.cjs
```

```bash
node tests/revision_preparacion_frontend.cjs
```

```bash
node tests/revision_aprobacion_resultados_frontend.cjs
```

**Resultados:**
- Python: 68 OK, de las cuales 7 son nuevas: 6 del servicio y 1 HTTP.
- Node: superposición 5/5 (nuevas); tabular 5/5, conversión 10/10, resultados OK, preparación 13/13 y revisión de resultados 21/21.

**Las pruebas nuevas cubren:**
- Transformación conocida con rotación de 30°, escala 0.08, traslación e inversión de y: matriz y proyección de D con 12 decimales.
- Punto fuera de imagen: B en (1.3, 1.2) se lista sin recortarse.
- Anclas inválidas: duplicadas, colineales, casi colineales, fuera de rango, NaN, nodo inexistente, dos anclas, nivel sin muros o inexistente, sin confirmación, fecha imposible, campo extra, huella, página, archivo y expediente.
- Unidad cm sin conversión.
- Geometría corregida: exige correspondencia nueva y la antigua sigue vigente.
- Preview distinto, calibración alterada con hash rehecho, versión copiada a otro caso y original alterado.
- HTTP: rutas, sesión, origen, límite de 413, 409 sanitizado y recursos servidos.
- Cliente: esquema sin alineación; detalle; registro con payload exacto, fondo de página y lista de puntos fuera; cambio a geometría corregida; respuesta tardía descartada; ausencia de `innerHTML`/`eval` en el código.

## Límites

- **Solo planta por `nivel_inferior`.** Los muros que atraviesan varios niveles no se repiten en los niveles intermedios.
- **Huella de render:** el SHA del preview depende del renderizador (pymupdf/Pillow). Si se actualiza, la correspondencia queda invalidada y debe registrarse de nuevo, de forma conservadora.
- **Tres anclas sin residuo de error:** no hay mínimos cuadrados con más anclas ni una estimación del error de calibración. La transformación es afín, no proyectiva.
- **Estilos:** el CSS de `.overlay`/`.anchor` usa los estilos por defecto (`style.css` no estaba autorizado).
- **Prueba visual en navegador real:** pendiente; la hará Codex.
- **No ejecutado:** red, API, ETABS, Computer Use y la suite completa.

## Revalidación final de la geometría (cierre del desarrollo)

Por analogía con el hallazgo 136, `consultar` vuelve a comprobar la huella y el SHA de la geometría **después** de renderizar el preview y verificar el original. Regresión: `test_geometria_cambia_durante_render_no_es_vigente`.
