# Informe Claude — UI de malla 189

Fecha: 21 de octubre de 2026. Carpeta verificada: `.../AECODE AI TALENT/PROYECTO FINAL`. Guía de uso: [docs/CONFIGURACION_MALLA_WEB.md](../docs/CONFIGURACION_MALLA_WEB.md).

## Cambios (solo archivos autorizados)

- **`draft2model/revision_visual.py`:** `GET /api/configuracion/malla`, de solo lectura, hacia `ServicioConfiguracion.malla`.
  - Usa el mismo acceso y la misma validación de caso y versión que `/api/configuracion`.
  - Rechaza cualquier parámetro distinto de `caso` y `version` (`409`).
  - `POST` responde `404`.
- **`draft2model/revision_web/index.html`:** panel «Malla 0.4: preparación reproducible (solo lectura)», con:
  - consulta y exportación;
  - identidad, resumen y faltantes;
  - nodos con su XYZ, subdivisiones, cortes y fuentes;
  - avisos honestos.
- **`draft2model/revision_web/configuracion.js`:**
  - el selector reconoce 0.4 y conserva 0.1 a 0.3;
  - consulta con ticket, caso, versión y huella, y descarta respuestas obsoletas;
  - un cambio de selección o de expediente invalida lo visible;
  - el contenido se muestra solo con `textContent`;
  - exportación revisable con plantillas `null` (no escribe políticas);
  - la aprobación 0.4 usa la geometría aprobada por huella y sigue bloqueada mientras haya faltantes.
- **Nuevos:** `tests/test_ui_malla.py`, `tests/ui_malla_frontend.cjs` y `docs/CONFIGURACION_MALLA_WEB.md`.
- **Sin editar:** el núcleo 184 (liberado a Codex), los servicios, las pruebas antiguas, `RETOMAR` y el control.

## Comandos y resultados

Con TEMP y TMP en `tmp/claude_ui_189`. Log: `tmp/claude_ui_189/pruebas.log`.

- `.venv/Scripts/python.exe -m unittest -v tests.test_ui_malla tests.test_revision_configuracion tests.test_revision_visual tests.test_integracion_malla.ConfiguracionYPlanMallaTests` → **41 OK, 0 omitidas**.
- `node tests/ui_malla_frontend.cjs` → OK.
- `node tests/configuracion_html_check.cjs` → OK (heredada, sin cambios).
- `node tests/control_html_check.cjs` → OK.

## Limitaciones

- **No ejecutado:**
  - QA visual en navegador;
  - ETABS o motor real;
  - suite global.
- **Ajuste sugerido a Codex (opcional):** `ServicioConfiguracion.malla` no devuelve la huella de configuración. El cliente la toma de la consulta abierta y exige que coincidan versión y expediente. Si se quiere una verificación de servidor por huella, habría que añadir `huella` a esa respuesta en `revision_configuracion.py`, que no es de mi propiedad.
