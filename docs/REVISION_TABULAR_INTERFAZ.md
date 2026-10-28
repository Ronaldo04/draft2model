# Interfaz y HTTP de la contingencia tabular CSV/XLSX

- **Ruta:** `D:/RONALDO CUCHILLA/1. RONALDO CUCHILLA/2. INGENIERÍA CIVIL DOCS AND PROJECTS/AECODE CURSOS/AECODE AI TALENT/PROYECTO FINAL`.
- **Servicio:** se reutiliza `ServicioTabular` (`draft2model/revision_tabular.py`) sin modificarlo ni duplicar su validación.
- **Nombres reales:** la carpeta web es `draft2model/revision_web/` (no `web/`) y la prueba de frontend sigue la convención `tests/revision_*_frontend.cjs`.

## Cambios por archivo

**`draft2model/revision_visual.py`** (cambios localizados, sin reformatear):
- Importa `ServicioTabular` y `ErrorTabular`, y añade `tabular.js` a `WEB_ASSETS`.
- `RevisionLocal.tabular` es una instancia de `ServicioTabular`.
- `RevisionLocal.tabular_version`, bajo `app.lock`, devuelve la proyección del servicio más la geometría reconvertida y comprobada mediante `_cargar`. No incluye bytes de las fuentes.
- **Rutas GET:**
  - `/api/tabular/historial?caso&expediente_sha256` llama a `listar`.
  - `/api/tabular/version?caso&version&expediente_sha256` devuelve la proyección más `geometria`.
- **Rutas POST:**
  - `/api/tabular/crear` llama a `crear`. Es la **única** ruta tabular con límite de 24 MiB.
  - `/api/tabular/importar` llama a `importar`, con el límite general de 2 MiB.
- Mantiene la sesión `X-Revision-Session`, el `Origin` exacto en POST, `application/json`, las cabeceras de seguridad y no-store.
- `ErrorTabular` responde 409 con el mensaje fijo del servicio, que no contiene rutas. Los demás errores conservan el mensaje genérico.

**`draft2model/revision_web/index.html`:** nueva sección «Contingencia tabular CSV/XLSX hacia geometría borrador», situada antes de «Geometría versionada», y la etiqueta `<script src="/tabular.js">`.

**`draft2model/revision_web/app.js`:** solo añade `window.tabularControls?.()` en `controls()`.

**`draft2model/revision_web/tabular.js`** (nuevo), con el mismo patrón que `conversion.js`:
- **Estado ligado a caso y huella:** se usan `ticket`, `read` y `listRead`. Al cambiar de caso, `d2m-case` limpia el estado y se descartan las respuestas antiguas. La confirmación se desmarca al abrir o refrescar una versión.
- **Validación previa a la lectura:**
  - un único JSON de metadatos de hasta 256 KiB;
  - en CSV, exactamente `niveles.csv`, `nodos.csv` y `muros.csv`, de hasta 4 MiB cada uno;
  - en XLSX, un único `.xlsx` de hasta 16 MiB;
  - nombres simples.

  Sin eso, no se lee ningún archivo.
- **Lectura y envío:** lee los metadatos como texto (sin interpretar sus campos ni unidades) y los originales como base64, y envía `{caso, expediente_sha256, metadatos_json, formato, archivos}`.
- **Crear no importa:** exige una respuesta `borrador`, sin aprobación y con `importacion:null`.
- **Importar:** solo con una versión abierta y vigente en borrador, sin importación interrumpida, y con la casilla marcada. Envía `{caso, expediente_sha256, version, huella_tabular, confirmacion_explicita:true}` y verifica que la respuesta sea borrador, sin aprobación y no disponible para modelado.
  - Después emite `d2m-geometry-created` con el recibo del servicio (contrato `{caso, expediente_sha256, estado, aprobacion, geometria}`); `app.js` refresca el historial geométrico.
  - En un replay, el servicio devuelve el mismo recibo.
- **Texto seguro:** todo se muestra con `textContent`, nunca HTML de los archivos. El estado usa `role="status"` y `aria-live`.
- **Avisos visibles:** la UI muestra «contingencia tabular supervisada», «sin aprobación», «importación interrumpida: requiere revisión» o «ya importada como geometría …».

## Pruebas

```bash
TEMP=$PWD/tmp TMP=$PWD/tmp python -m unittest tests.test_revision_tabular_http tests.test_revision_tabular tests.test_revision_visual tests.test_revision_contexto_http
```

```bash
node tests/revision_tabular_frontend.cjs
```

```bash
node tests/revision_conversion_frontend.cjs
```

```bash
node tests/revision_preparacion_frontend.cjs
```

```bash
node tests/revision_resultados_frontend.cjs
```

**Resultados:**
- Python: 37 OK. De ellas, `test_revision_tabular_http` aporta 4 nuevas y el resto es regresión focal.
- Node: tabular 5/5 (nuevas). Conversión 10/10, preparación 13/13 y resultados OK, como regresión de `app.js`.

**`test_revision_tabular_http` cubre:**
- Flujo CSV y XLSX: crear, historial, versión con geometría y sin bytes de las fuentes ni rutas.
- Crear no importa.
- Importación con confirmación false y con huella errónea (409), importación correcta y replay idéntico, con una sola versión geométrica.
- Sesión y origen incorrectos (403), huella de expediente errónea (409 sin rutas), fuente alterada (409 en versión e importación) y UUID inválido.
- Cuerpo de 3 MiB admitido en `crear` (rechazado por el servicio) y 413 en `importar`. Más de 24 MiB devuelve 413.
- Recursos servidos: `/tabular.js` y la sección en `/`.

**`revision_tabular_frontend.cjs` cubre:**
- La validación previa no lee archivos y no hace POST.
- Registrar envía los bytes exactos sin importar ni emitir eventos.
- Importación separada y confirmada, con payload exacto, evento y refresco de `geoVersion`.
- Respuesta tardía al cambiar de caso descartada y confirmación no heredada.
- Importación interrumpida bloqueada; registro aprobado o ajeno rechazado.

## Límites y observaciones

- **Inestabilidad conocida en una prueba previa** (`tests/test_revision_tabular.py`, que no está entre los archivos de este encargo): `test_csv_y_xlsx_equivalentes_al_mismo_contrato` compara los bytes del libro guardado con una nueva llamada a `libro()`. El ZIP incluye la hora actual, así que puede fallar si las dos llamadas caen en segundos distintos. Lo observé una vez durante esta pasada; luego pasó. La corrección sugerida es generar el libro una sola vez y reutilizar esos bytes.
- `tabular_version` usa el método interno `_cargar` del servicio para obtener la geometría ya verificada. Con eso se evita duplicar validación, pero acopla la ruta a un método privado.
- No hay endpoint de recuperación de una importación interrumpida; la UI solo la señala.
- **No verificado:** navegador real (se usó `node:vm` con DOM simulado), red, API, ETABS, Computer Use y la suite completa.
