# Columna en L nativa e inserción en el centroide (configuración 0.5)

Estado al 22 de octubre de 2026 (Codex 246).

**Archivos:**
- Contrato: [`modelo_estructural.py`](../draft2model/modelo_estructural.py).
- Plan: [`operaciones_etabs.py`](../draft2model/operaciones_etabs.py) y [`ejecutar_plan_etabs.ps1`](../scripts/ejecutar_plan_etabs.ps1).
- Relectura: [`verificacion_modelo_guardado.py`](../draft2model/verificacion_modelo_guardado.py) y [`verificar_modelo_guardado.ps1`](../scripts/verificar_modelo_guardado.ps1).
- Pruebas: [`tests/test_columna_l_246.py`](../tests/test_columna_l_246.py) y la fixture nativa `tests/fixtures/columna_l_etabs21_246.json`.

## Por qué

El detalle de C-1 en E01 acota una L de envolvente 0,40 × 0,40 m con brazos de 0,15 m (auditoría Codex 246). Representarla como un rectángulo de 0,15 × 0,40 pierde el 38,46 % del área y cambia sus inercias. La DLL de ETABS 21 ofrece `cPropFrame.SetConcreteL`/`GetConcreteL`, de modo que se usa la forma nativa y no un equivalente inventado.

## Contrato (solo 0.5; versiones anteriores sin cambio)

**Sección `frame_l_concreto`.** Sus dimensiones exactas son:
- `alto_m` (T3) y `ancho_m` (T2): la envolvente;
- `espesor_ala_m` (Tf);
- `espesor_alma_m` (TwC = TwT; el brazo es de espesor constante);
- `espejo_eje_2` y `espejo_eje_3`: booleanos explícitos.

Cada espesor debe ser menor que la dimensión que lo contiene. Las asignaciones de frames admiten secciones rectangulares y en L.

**`insercion_frames`.** Es una clave raíz **opcional**: sin ella, las configuraciones 0.5 existentes y su huella no cambian. Cada elemento es `{frame, punto_cardinal, desplazamiento_global_m, transformar_rigidez, fuente}`. Solo se admite lo ensayado:
- `punto_cardinal = 10` (centroide);
- un desplazamiento global igual en ambos extremos;
- `transformar_rigidez = true`.

Si el frame se subdivide en la malla, la inserción sigue a cada subframe.

## Plan y relectura

- **`SetConcreteL`** con relectura `GetConcreteL`: material, cinco dimensiones y espejos.
- **`SetInsertionPoint`** por frame con relectura `GetInsertionPoint`: cardinal, `Mirror2 = false`, rigidez transformada, desplazamientos y `CSys Global`.
- **Firmas:** contrastadas por reflexión de la DLL 1.29.0.0 (`verificar_firmas_dll` sin diferencias).
- **Planes sin L ni inserción:** quedan idénticos byte a byte.
- **Lector del modelo guardado:** pide `secciones_l` e `insercion_frames` solo cuando el plan las crea, y resuelve esas firmas únicamente en ese caso. Los dobles anteriores siguen siendo válidos.
- **Unidades:** la reapertura devuelve N_mm_C y la comparación convierte las longitudes.

## Semántica nativa ensayada (instancias propias, sintético)

`scripts/ensayar_columna_l_etabs.ps1` crea voladizos de 3 m con las cuatro combinaciones de espejos y cuatro inserciones. Una carga axial de 1000 kN con el nudo en el punto cardinal 1 (esquina mínima de la envolvente) produce un momento P·d que revela el vector nudo → centroide. Una carga lateral en el centroide revela el acople de flexión.

| Espejos (2, 3) | Brazos en ejes locales (2, 3) = globales (X, Y) con ejes por defecto de columna |
|---|---|
| (no, no) | +X, −Y |
| (sí, no) | +X, +Y |
| (no, sí) | −X, −Y |
| (sí, sí) | −X, +Y |

- **Propiedades:** área, I22 e I33 coinciden con la L acotada (0,0975 m² y 0,0012309 m⁴).
- **Observación del montaje ensayado (R249-01):** en el voladizo propio con `SetConcreteL` (ETABS 21.1), bajo FX en el centroide uy fue exactamente 0. En **ese** montaje la respuesta no mostró acople por el producto de inercia: se comportó con I22 e I33 sobre ejes paralelos a los brazos, sin los principales (0,000654 y 0,001808 m⁴). No se generaliza a todo ETABS ni a otras configuraciones. Se documenta y no se corrige con una propiedad general incompleta.
- **Punto cardinal 11:** dio el mismo resultado que el 10, así que no se admite.

## Recorrido completo verificado

`scripts/ensayar_plan_columna_l.py` (`tmp/columna_l_plan_246a`) recorre la cadena en instancias propias:
- **Configuración y plan:** configuración 0.5 aprobada (sintética) y plan 0.5 de 241 operaciones.
- **Construcción:** el ejecutor real relee la L y las 3 inserciones de los subframes.
- **Guardado y cierre:** se guarda el EDB y se cierra solo el PID propio.
- **Relectura independiente:** el EDB guardado da `verificado`, con 0 discrepancias y cobertura completa de frames y propiedades.

Sin análisis ni aprobación de ingeniería.

## Caso real

`seguimiento/claude_ruta/configuracion_09b.py` asigna una L nativa por instancia de C-1:
- A/3, con brazos +X/+Y: `espejo_eje_2`;
- A/1, con brazos +X/−Y: sin espejos.

La inserción en el centroide real va desde el nudo existente: (+0,0769; +0,0579) m y (+0,0769; −0,0979) m. Así se conservan las conexiones con muros y losas. El armado (8 Ø1/2") no se traduce a `SetRebarColumn`.
