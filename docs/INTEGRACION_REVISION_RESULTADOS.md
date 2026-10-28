# Integración HTTP y montaje de la revisión propia declarada de resultados

- **Ruta:** `D:/RONALDO CUCHILLA/1. RONALDO CUCHILLA/2. INGENIERÍA CIVIL DOCS AND PROJECTS/AECODE CURSOS/AECODE AI TALENT/PROYECTO FINAL`.
- **Componentes que se usan sin modificar:**
  - el backend `ServicioRevisionResultados` (`draft2model/revision_aprobacion_resultados.py`), con el contrato de `docs/REVISION_APROBACION_RESULTADOS.md`;
  - el componente del subagente `draft2model/revision_web/revision_resultados.js`, con su guía `docs/REVISION_APROBACION_RESULTADOS_INTERFAZ.md`.

  No se duplicó código del componente.

## HTTP (`draft2model/revision_visual.py`, cambios localizados)

- Importa `ServicioRevisionResultados` y `ErrorRevisionResultados`. `RevisionLocal.revision_resultados = ServicioRevisionResultados(self)`.
- `revision_resultados.js` se añade a `WEB_ASSETS`, por lo que se sirve como `text/javascript` con las mismas cabeceras.

| Método | Ruta | Llamada |
|---|---|---|
| GET | `/api/revision-resultados/fuentes?caso&resultado&analisis&expediente_sha256` | `consultar_fuentes` |
| GET | `/api/revision-resultados/historial?caso&resultado&expediente_sha256` | `listar` (no selecciona la última; `seleccion_automatica:false`) |
| GET | `/api/revision-resultados/version?caso&revision&expediente_sha256` | `consultar` |
| POST | `/api/revision-resultados/registrar` | `registrar`, con el cuerpo exacto del backend y el límite general de 2 MiB |

- Se mantienen la sesión, el `Origin` exacto, el `Host` local, `application/json`, no-store y CSP.
- `ErrorRevisionResultados` responde 409 con `{error: codigo, codigo}`, igual que otros servicios con código público.
- El estado nativo del resultado (`/api/resultado`) sigue en `revision_resultados:'pendiente'`: nunca se eleva.

## Montaje (`index.html` y `app.js`, solo montaje)

- **`index.html`:**
  - el fragmento HTML de la guía del subagente se inserta una sola vez, justo después del panel de resultados (el que contiene `resultadoVersion`);
  - se añade `<script src="/revision_resultados.js">` **antes** de `app.js`.
- **`app.js`:**
  - `controls()` llama a `window.resultReviewControls?.()`;
  - al final del archivo se ejecuta el montaje que indica la guía, protegido por `if(window.D2MRevisionResultados)`:

    ```
    D2MRevisionResultados.crearRevisionResultados({get:$, api, options, getContext:()=>docs, isBusy:()=>busy,
      action, message, events:window, emit:(tipo,detalle)=>window.dispatchEvent(new CustomEvent(tipo,{detail:detalle}))})
    ```

  - la guarda evita romper los arneses existentes que cargan `app.js` sin el componente.
- **Comportamiento que aporta el componente:**
  - escucha `d2m-case` y `d2m-result`;
  - empieza con el análisis sin preselección y los seis controles desmarcados;
  - el registro es separado y confirmado, con `faltantes_criticos` explícito;
  - después del registro no hay selección automática;
  - emite `d2m-result-review` solo tras consultar la versión exacta;
  - invalida el formulario y la selección al cambiar las fuentes y descarta respuestas tardías.

## Pruebas

```bash
TEMP=$PWD/tmp TMP=$PWD/tmp python -m unittest tests.test_revision_aprobacion_resultados_http tests.test_revision_visual tests.test_revision_tabular_http tests.test_revision_resultados_http
```

```bash
node tests/revision_aprobacion_resultados_frontend.cjs
```

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

**Resultados:**
- Python: 37 OK. Las 5 nuevas son de `test_revision_aprobacion_resultados_http`; el resto es regresión focal HTTP.
- Componente del subagente: una ejecución, 21/21 OK.
- Regresión de `app.js`: tabular 5/5, conversión 10/10, resultados OK y preparación 13/13.
- **Montaje real:** comprobado con un script temporal fuera del repositorio que carga `revision_resultados.js`, `app.js` y `resultados.js` reales. Confirma la exportación global, `resultReviewControls`, que tras `d2m-result` se listan los análisis sin preselección, y que los controles empiezan desmarcados.

**`test_revision_aprobacion_resultados_http` cubre:**
- Flujo fuentes → registro → historial → consulta exacta, sin elevar el resultado nativo ni exponer rutas privadas.
- Rechazos con su código: `confirmacion_requerida`, `controles_explicitos_requeridos`, `faltantes_criticos_declarados` y `campos_invalidos`. También 409 por huellas, caso ajeno, expediente, UUID o análisis inexistente, sin publicar nada.
- EDB alterado: invalida fuentes, consulta y registro, y deja la fila del historial como no vigente; al restaurarlo, todo vuelve a funcionar.
- Sesión, `Host` y `Origin` incorrectos (403), y cuerpo de más de 2 MiB (413).
- Recurso servido, script montado una sola vez antes de `app.js` y controles sin marcar en el HTML.

## Límites

- La conexión opcional del informe con una revisión seleccionada la hará root más adelante. Esta entrega no toca el informe.
- La verificación de montaje en el navegador real no se hizo: se usó `node:vm` con DOM simulado.
- Repetir `registrar` crea otra declaración independiente, como define el backend. El componente no reintenta por su cuenta.
- **No ejecutado:** red, API, ETABS, Computer Use y la suite completa.
