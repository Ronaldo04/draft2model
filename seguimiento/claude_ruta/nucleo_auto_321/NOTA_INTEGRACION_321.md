# Núcleo 321: nota de integración (núcleo aislado, NO flujo integrado)

Propuesta en `fuentes/estimacion_extremos_auto.py` (destino sugerido `draft2model/estimacion_extremos_auto.py`). Mantiene el algoritmo y las restricciones de 319. No se modifica el producto 312 ni 319. Sin ETABS, nube ni claves.

## Superficie

- `estimar_desde_plan(plan, config, validador=None)` (pública):
  1. valida la configuración;
  2. exige `operaciones_etabs.validar_plan_por_version(plan) == []` (lista blanca, firmas, tipos, referencias y huella), sin duplicar esas validaciones;
  3. solo entonces llama al núcleo.
  - Estados: `estimacion`, `plan_rechazado` o `abstencion_global`.
- `nucleo(plan, config)`: análisis puro, sin abrir archivos (comprobado sobre el código del núcleo); lo usan las pruebas con mini-planes.
- CLI: `python -m draft2model.estimacion_extremos_auto --plan P.json --configuracion C.json --salida NUEVA.json`.
  - JSON estricto: rechaza NaN/Infinity y claves duplicadas.
  - Salida nueva con `open('x')`, nunca sobrescribe.
  - Incluye las huellas SHA-256 de plan y configuración, y el perfil.
  - Códigos: 0 estimación; 2 entrada inválida o salida existente; 3 plan rechazado o abstención.
- `procedencia_tolerancia` es una **declaración**: el resultado la conserva (`procedencia_tolerancia_declarada`) y advierte que el consumidor debe vincular el recibo o modelo. La CLI no acepta un libro para restar pesos.

## Operaciones (perfil)

Clasificación explícita de las **40 escrituras** de la lista blanca real (`operaciones_etabs.FIRMAS`) y de las **4 tablas editables**; una prueba lo comprueba frente al código real.
- **Interpretadas:** AddCartesian, frames AddByPoint, SetRectangle, SetWeightAndMass, SetInsertionPoint (abstención), áreas AddByPoint y SetOpening (por nombre registrado `superficie:`/`abertura:`/`muro:`), LoadPatterns.Add (multiplicador de peso propio), SetPresentUnits (debe coincidir), SetMassSource_1 (se registra en el perfil), SetConcreteL (sección L, abstención).
- **Neutras:** casos, combinaciones, espectros, cargas de punto, frame o área, apoyos, diafragmas, propiedades de área, isotropía elástica, pisos, Save y las ediciones de tablas de cargas y espectros.
- **Bloqueo si afecta**, en mini-planes (fuera de la lista blanca): SetEndLengthOffset (no Auto o longitudes no nulas), SetModifiers (frame o sección), SetSection, SetMass, SetLocalAxes (≠ 0/90° en columnas; cualquier giro en la viga), SetLocalAxesAdvanced.
- **Toda otra escritura** `c*.Set*` es un problema del plan: sin totales. Si apunta a un frame, ese frame también se abstiene.
- `ItemType` distinto de Objects (grupo o selección) y referencias a frames o áreas inexistentes son problemas del plan.

## Consumo junto al libro bruto (pendiente de integración por Codex)

- **Backend:** guardar el resultado como artefacto nuevo ligado a `huella_plan`, a la configuración y al recibo de verificación de la tolerancia (p. ej. `tmp/configuracion_318_reparacion/registro.json`). No reescribir `libro_masa.json` ni los JSON históricos.
- **Libro:** columnas separadas para el bruto histórico (sin cambios), el descuento estimado (`totales.descuento_kN`, solo si existe) y el neto estimado.
  - El neto se muestra como «estimado» solo si el estado es `estimacion`, no hay problemas del plan, la cobertura es completa, `perfil_peso.salvedades` está vacío y el consumidor verificó la tolerancia con el recibo vinculado.
  - En cualquier otro caso: «no estimable» con los motivos.
- **Interfaz:** mostrar por viga los offsets, la regla de exceso, las procedencias (documental o experimental) y las abstenciones; nunca un total parcial.
- **Trazabilidad mínima:** versión del núcleo, huellas de entrada, plan validado (contrato, versión, huella), configuración con procedencia declarada y referencia al recibo, perfil de peso y fuente de masa.

## Comprobaciones pendientes (Codex)

- Revisión del código e integración real.
- Pruebas en el paquete público.
- Verificación de la vinculación tolerancia–recibo en el consumidor.
- Decisión sobre el multiplicador de peso propio con varios patrones.
- **El residuo de CM de 0,006877 kN fuera de las VS sigue sin atribuir.** La masa oficial no es coherente por esta coincidencia retrospectiva.

## Evidencia

- Pruebas en `pruebas/`:
  - `test_nucleo_317_en_321.py` (8) y `test_nucleo_validacion_321.py` (11): portadas de 319 con un adaptador `nucleo`. Cambios: la comprobación de independencia se acota a las funciones del núcleo (la CLI abre archivos) y se restaura el mensaje «AutoOffset».
  - `test_entrada_publica_321.py` (13): plan real generado con la fixture existente `PlanBase` (`generar_plan`), huella alterada, operación fuera de la lista blanca, selección inexistente, configuración antes del validador, CLI (huellas, sin sobrescritura, NaN, claves duplicadas, código 3), grupo/selección, frame inexistente, escritura no clasificada, unidades, aberturas por nombre registrado, multiplicador de peso propio y clasificación completa.
- Se ejecutan desde PROYECTO FINAL con `python -m unittest <ruta>`, sin instalar ni modificar el paquete (las pruebas anteponen `fuentes/` a `sys.path`).
- `PILOTO_ENTRADA_PUBLICA_321.json`:
  - entrada pública sobre el plan real validado con la configuración 318 (procedencia declarada y referencia al recibo): 45/45 y 6,86124 kN;
  - offsets idénticos a `PREDICCION_AUTO_320.json` de Codex en las 45 vigas.
  - No contiene el plan, solo su estimación.
