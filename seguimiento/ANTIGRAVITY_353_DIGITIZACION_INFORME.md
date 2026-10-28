# Informe Encargo 353 — Servicio e interfaz de digitización calibrada

**Raíz verificada:** `D:/RONALDO CUCHILLA/1. RONALDO CUCHILLA/2. INGENIERÍA CIVIL DOCS AND PROJECTS/AECODE CURSOS/AECODE AI TALENT/PROYECTO FINAL`  
**Responsable:** Antigravity (`353_digitizacion_web`) · **APIs usadas:** `0` · **ETABS usado:** `false` · **Encargo 351:** no ejecutado ni tocado.

## 1. Implementación completada (lista cerrada exclusiva)
- `draft2model/revision_digitizacion.py`: define `ErrorRevisionDigitizacion` y `ServicioDigitizacion(app)` con `preparar(body)`, `calcular(body)`, `consultar(caso, fp, id)` y `listar(caso, fp)`, reutilizando sin duplicar álgebra `draft2model.digitizacion_calibrada.calibrar_digitizacion`.
- `draft2model/revision_web/digitizacion.js`: IIFE autónoma para etapa 3 (`D2MEtapas.containers.get('geometria')`) con separación explícita entre panel de propuesta estructurada (`d2m-digitizacion-propuesta`) y panel de revisión/criterios del ingeniero, edición exclusiva en coordenadas locales normalizadas `[u, v]` en `[0, 1]²`, sin campos métricos ni carga de JSON externo.
- `docs/INTERFAZ_DIGITIZACION.md`: documenta rutas HTTP para integración por Codex (`/api/digitizacion/historial`, `/registro`, `/preparar`, `/calcular`), contratos cerrados, esquema del evento `d2m-digitizacion-propuesta` y límites técnicos.

## 2. Controles de seguridad e integridad técnica verificados
- **Verificación de bytes y cadenas:** comprueba `expediente.json`, bytes reales de cada original (`app._original`), renderizado real de página (`app.pagina`), coherencia con `revision_documental`/`recortes`, ausencia de enlaces simbólicos o *reparse points*, geometría `0.3.0` vigente (`app.geometria` + `validar_geometria`), hashes de código cargado y reejecución pura de `calibrar_digitizacion` al abrir cualquier registro persistido.
- **Rechazo de coordenadas métricas externas:** cualquier clave física (`puntos_resueltos`, `coordenadas`, `coordenadas_m`, `x`, `y`, `z`, `xy`, `xy_m`) enviada desde navegador o IA se rechaza antes de calcular; las coordenadas de referencia salen únicamente de la geometría `0.3.0` comprobada.
- **Honestidad documental:** no inventa cotas, unidades ni referencias documentales; cuando la geometría carece de `procedencia.referencias`, emplea `descriptor_geometrico:<geometria_id>` solo como descriptor numérico, conserva `exactitud_documental_acreditada: false` y pendiente explícito, e impide fingir controles independientes. Si el plano tiene `< 3` referencias coplanares no colineales, conserva registro con pendiente sin fabricar puntos.

## 3. Pruebas focales ejecutadas (alcance sintético)
1. `.\.venv\Scripts\python.exe -X utf8 -B -m unittest -v tests.test_revision_digitizacion` → **OK (10 pruebas)**.
2. `node tests/digitizacion_353_frontend.cjs` → **OK (5 bloques DOM/asíncronos)**.

## 4. Limitaciones explícitas
- No integra rutas ni etiquetas `<script>` en `draft2model/revision_visual.py` ni `index.html` (reservado a Codex).
- Toda salida queda en **borrador** (`disponible_para_modelado: false`); no incorpora puntos a la geometría, no crea superficies/frames, no valida planos reales piloto ni ejecuta ETABS.
