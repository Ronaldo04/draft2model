# Etapa 01 — estabilizar (ruta 201)

## Incrementos registrados

- **Entrega 196 y cambio posterior de Codex (conversión de unidades de malla):** conservados. `test_relectura_malla` está verde en la batería de esta etapa.
- **Fuentes permanentes 198:**
  - `revision_modelo.consultar(tmp/n198/fuentes/private, sintetico-001, 81af6b76…)` → `pendiente`, consultado tras salir de Python;
  - EDB SHA `a597406d…b571`;
  - recomparación 200 sobre los mismos bytes de la lectura 199 → verificado, 0 discrepancias y 0 incompletos, malla completa.

  No se hizo otra lectura. La prueba `Fuentes198Tests` lo comprueba en solo lectura.
- **Ensayos 190 a 194:** sus registros temporales no existen y no se acreditan.
- **Cierres:** el de 194/198 por host es evidencia de Codex. `cierre_observado_194` no acredita cierre.
- **UI de relectura** (`verificacion_modelo.js`): el estado muestra la cobertura de malla y el resumen por host cuando el resultado los trae.
- **Informe** (`informe.py`): añade una sección «Malla 0.4», con contenido escapado, cobertura y lo que no afirma, solo si está presente.
- **`gestion_configuracion.preparar_malla_version`:** añade `huella_configuracion`. Por tanto, `ServicioConfiguracion.malla` la expone y `configuracion.js` rechaza una preparación con otra huella.
- **`docs/RETOMAR.md`:** reescrito de forma breve. La historia está en `docs/historial/RETOMAR_ANTES_201.md`.
- **Nuevo `scripts/crear_entrega_ruta.py`:** crea entregas inmutables.

## Pruebas

- `py_compile` de `draft2model`, `scripts` y `tests`: sin errores.
- Sintaxis de todo `revision_web/*.js`: sin errores.
- **13 módulos y clases** (`test_ruta201_estabilizar`, `test_relectura_malla`, `test_ui_malla`, `test_revision_configuracion`, `test_informe_relectura_modelo`, `test_revision_verificacion_modelo`, `test_revision_verificacion_modelo_http`, `test_verificacion_modelo_guardado`, `test_contorno_nativo`, `test_relectura_representaciones_csi`, `test_integracion_malla`, `ScriptEstaticoTests`): **90 OK**.
  - El error del cargador correspondía a un nombre de clase inexistente (`FirmasYEnumsTests`).
  - La clase correcta, `ListaBlancaSuperficiesTests`, da 2 OK.
- **Node:** `ruta201_frontend`, `ui_malla_frontend`, `configuracion_html_check`, `revision_verificacion_modelo_frontend` e `informe_relectura_frontend`: OK.

Log: `tmp/ruta201/etapa01_pruebas.log`, copiado en la entrega.

## Límites

- No se hizo QA visual en navegador en esta etapa.
- No se ejecutó ETABS.
- El PDF de la fixture n198 no acredita el render de planos.
- No se habilita ingeniería.
