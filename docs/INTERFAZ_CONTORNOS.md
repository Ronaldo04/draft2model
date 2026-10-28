# Interfaz del recorrido automático de contornos (Etapa 3 · Geometría)

`draft2model/revision_web/contornos.js` proporciona el panel de la etapa 3 para el recorrido automático de contornos documentados en planos. Conecta las propuestas leídas por visión con la calibración afín local por dibujo, comprobando la consistencia topológica y publicando una geometría y una preparación de ingeniería derivadas en **borrador**.

Toda salida generada permanece en estado de borrador (`revision: {estado: "borrador", aprobacion: null}`, `aprueba_ingenieria: false`, `ejecutable_etabs: false`). El cálculo automático asiste al profesional pero no sustituye su criterio ni certifica conformidad normativa.

---

## 1. Vínculo con geometría y preparación de ingeniería

1. **Geometría abierta:** Requiere una versión geométrica comprobada activa (`0.3.0` o superior).
2. **Preparación de ingeniería (`para-geometria`):**
   - El panel consulta `GET /api/configuracion/preparacion/para-geometria?caso&expediente_sha256&geometria`.
   - Si existe una única preparación reusable, la vincula automáticamente.
   - Si existen múltiples ramas conservadas, despliega un selector explícito y el botón «Usar preparación seleccionada», sin adoptar otra rama silenciosamente.
   - Si no existe ninguna preparación, instruye al usuario a crearla en el panel de preparación de ingeniería (etapa 4).
3. **Bloqueo por ediciones sin guardar (`dirty`):**
   - Si la preparación o el contrato geométrico presentan cambios sin guardar en pantalla (`d2m-preconfig-edited` o edición de JSON), las acciones de preparación y ejecución quedan estrictamente bloqueadas.
   - El desbloqueo ocurre al guardar o reabrir una preparación válida vinculada a la geometría actual.

---

## 2. Parámetros de lectura y criterios numéricos de calibración

- **Proveedor y modelo:** Selector de proveedor (`OpenAI` predeterminado con `gpt-6.1-sol`; `Google Gemini` con `gemini-3.8-flash`). Salida máxima predeterminada en `32768` (rango `256` a `65536`). Sin ingreso de claves API en la interfaz.
- **Cuota compartida:** Consulta `GET /api/reconstruccion/cuota`. Si `restantes === 0` o la credencial no está configurada, el envío se bloquea y no se cambia de proveedor silenciosamente.
- **Criterios de calibración (desplegable avanzado):**
  1. `residuo_ajuste_max_m`: 0.02 m
  2. `error_control_max_m`: 0.03 m
  3. `incertidumbre_max_m`: 0.08 m
  4. `localizacion_uv`: 0.005
  5. `referencia_m`: 0.005 m
  6. `condicion_max`: 50
  7. `escala_min_m_por_uv`: 0.1 m/unidad
  8. `escala_max_m_por_uv`: 500 m/unidad
  9. `coordenada_abs_max_m`: 1000 m
- **Confirmación explícita:** Casilla obligatoria antes de preparar, advirtiendo que los criterios son tolerancias de cálculo y no representan límites normativos ni aprobación humana.
- **Invalidación reactiva:** Cualquier modificación en proveedor, modelo, tokens o criterios invalida el estado preparado y exige nueva preparación.

---

## 3. Ejecución, etapas claras y recuperación local

- **Envío único:** Casilla de consentimiento explícito (`confirmacion_explicita: true`) antes de llamar a `POST /api/contornos/ejecutar`. Ante fallo (`fallido_no_reintentar`), se detiene de inmediato sin reintentos automáticos.
- **Progreso claro por etapas:**
  1. *Leyendo planos y correspondencias*
  2. *Calibrando dibujos con referencias locales*
  3. *Comprobando geometría y topología*
  4. *Guardando geometría y preparación en borrador*
- **Sondeo local:** Consultas cada 2 segundos a `GET /api/contornos/estado?caso&expediente_sha256&trabajo` mientras esté en ejecución.
- **Recuperación sin API:** Botón «Reevaluar respuesta conservada sin proveedor» invoca `POST /api/contornos/recuperar` con `{caso, expediente_sha256, trabajo}` sin consumir cuota ni transmitir datos al exterior.

---

## 4. Publicación idempotente de hijos derivados (Hito 3)

Cuando un recorrido finaliza exitosamente con nueva geometría y preparación:
- Emite `d2m-proposed-frames` con `{geometria, frames}`.
- Emite `d2m-preconfig-created` con `{caso, expediente_sha256, configuracion_preparacion, sha256_configuracion, preparacion_origen}`.
- Emite `d2m-geometry-created` con `{caso, expediente_sha256, geometria, estado: "borrador", aprobacion: null}`.
- **Idempotencia:** Registra el artefacto emitido; consultas posteriores o relecturas del historial nunca repiten los eventos de navegación.
- **Protección de rama y ediciones:** Si el ingeniero cambió de geometría/rama o tiene cambios sin guardar, no se emite `d2m-geometry-created` para evitar sobreescribir su trabajo. En su lugar, se muestra un aviso de disponibilidad con el botón «Abrir versión derivada en borrador».

---

## 5. Observaciones estructuradas y puente a digitización manual (Hitos 2 y 4)

- **Observaciones agrupadas:** Organizadas en cuatro categorías (*Calibración local por dibujo*, *Comprobación geométrica e incorporación*, *Advertencias de lectura*, *Datos pendientes del edificio*). Cada fila detalla **Elemento**, **Dibujo** y **Causa**, eliminando objetos crudos y duplicados planos.
- **Puente a calibración manual:** Selector de dibujos propuestos y botón «Cargar dibujo en calibración manual». Emite `d2m-digitizacion-propuesta` omitiendo `evidencias` exclusivamente del evento emitido (preservándolas en la lectura conservada). Si el usuario se encuentra en la geometría derivada, el sistema bloquea el envío y solicita abrir la geometría original mediante el selector normal.
