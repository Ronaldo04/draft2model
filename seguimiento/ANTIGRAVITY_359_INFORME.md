# Informe de ejecución · Encargo 359 (Interfaz de contornos automáticos y calibración)

Fecha: 2026-10-26
Agente: Antigravity
Entorno: Local sintético (Windows / Node.js)
Estado: Completado y verificado

---

## 1. Alcance y archivos asignados

Se implementó de forma exclusiva y consecutiva la interfaz web del recorrido automático de contornos, sus pruebas en Node/DOM y su documentación técnica, respetando la lista cerrada de archivos nuevos sin modificar servicios compartidos ni dependencias de otros agentes:

1. `draft2model/revision_web/contornos.js`
2. `tests/contornos_359_frontend.cjs`
3. `docs/INTERFAZ_CONTORNOS.md`
4. `seguimiento/ANTIGRAVITY_359_INFORME.md`
5. `seguimiento/ANTIGRAVITY_359_ENTREGA.json`

---

## 2. Hitos completados

1. **Hito 1 · Vínculo con geometría y preparación (`D2MEtapas.containers.get('geometria')`):**
   - Integración reactiva a `d2m-case`, `d2m-geometry-opened`, `d2m-preconfig-opened` y `d2m-preconfig-edited`.
   - Consulta de `GET /api/configuracion/preparacion/para-geometria` con soporte para preparaciones reutilizables únicas y selector explícito con botón para ramas múltiples.
   - Bloqueo total ante ediciones sin guardar (`dirty`) o desvínculo de geometría.

2. **Hito 2 · Formulario intuitivo, cuota compartida, criterios de calibración y etapas claras:**
   - Proveedor (`OpenAI` / `Google Gemini`), modelo y límite de tokens (`32768`, 256..65536) sin exponer claves API ni nombres internos de eventos.
   - Sección avanzada `<details>` con los 9 criterios de calibración y sus valores predeterminados de `digitizacion.js`, con confirmación obligatoria previa a la preparación.
   - Casilla de consentimiento para envío único (`confirmacion_explicita: true`) y seguimiento visual de las cuatro etapas (*leyendo*, *calibrando*, *comprobando geometría*, *guardando*).
   - Bloqueo inmediato ante cuota 0 y detención sin reintento ante `fallido_no_reintentar`.
   - Observaciones deduplicadas y agrupadas mostrando claramente `Elemento`, `Dibujo` y `Causa`.

3. **Hito 3 · Publicación idempotente de hijos derivados:**
   - Emisión de `d2m-proposed-frames`, `d2m-preconfig-created` (con `configuracion_preparacion`, `sha256_configuracion` y `preparacion_origen`) y `d2m-geometry-created` exactamente una vez al finalizar en la rama limpia original.
   - Supresión de navegación automática ante cambios de rama o ediciones sin guardar, ofreciendo el botón «Abrir versión derivada en borrador».

4. **Hito 4 · Puente hacia el panel de calibración manual:**
   - Selector de dibujos propuestos y emisión de `d2m-digitizacion-propuesta` conforme a `docs/INTERFAZ_DIGITIZACION.md`.
   - Exclusión de `evidencias` exclusivamente en el payload del evento emitido, conservándolas intactas en el estado local.
   - Bloqueo y advertencia al estar en la geometría derivada, requiriendo abrir la original por el selector normal.

5. **Hito 5 · Verificación sintética Node/DOM:**
   - Suite `tests/contornos_359_frontend.cjs` ejecutada con éxito total: **7/7 bloques superados**.

---

## 3. Resultados de pruebas sintéticas

```text
OK: 7/7 bloques DOM/Node superados en contornos_359_frontend.cjs
- Bloque 1: Montaje, higiene DOM/seguridad, valores predeterminados y ausencia de nombres internos.
- Bloque 2: Vínculo geometría-preparación, ramas múltiples, dirty/desvínculo y preparar local sin API.
- Bloque 3: Cuota 0, invalidación al editar formulario/criterios, 1 envío y fallo sin reintento.
- Bloque 4: Publicación idempotente de hijos (2 IDs + SHA + origen), respeto de rama/dirty y recuperar sin API.
- Bloque 5: Agrupación de observaciones (elemento / dibujo / causa, sin objetos crudos ni duplicados).
- Bloque 6: Puente hacia panel de digitización (limpieza de evidencias y guardia de geometría derivada).
- Bloque 7: Concurrencia estricta (descarte de respuestas/sondeos tardíos de otro caso, geometría, versión y edición).
```

---

## 4. Limitaciones y restricciones respetadas

- **Consumo de APIs externas:** 0 llamadas reales (todos los ensayos se realizaron con dobles de prueba sintéticos).
- **ETABS:** No se invocó ni ejecutó ninguna instancia de ETABS.
- **Git / Servidores:** No se modificaron ramas ni se reiniciaron procesos de servidor.
- **Borrador técnico:** Toda salida generada permanece en estado de borrador y no constituye aprobación de ingeniería ni conformidad reglamentaria.
