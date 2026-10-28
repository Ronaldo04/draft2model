# Informe 09 — integración del piloto

Fecha: 21 de octubre de 2026.

**Estado:** el piloto real está **incompleto**. El recorrido nativo propio no se inició porque sus puertas no se cumplen (§3).
- Sin API.
- Sin aprobaciones.
- Ninguna afirmación de cumplimiento.
- La comparación manual sigue aplazada.

## 1. Matriz requisito → archivo → comprobación → resultado

| Requisito (09 / revisión) | Archivo | Comprobación | Resultado |
|---|---|---|---|
| R236: V utilizable con C/R ≥ 0,11 y coeficiente bruto separado | `draft2model/normativa_e030.py` (`cortante_basal_estatico`) | `tests/test_normativa_rne.py`: caso de Codex V = 49,5 kN (bruto 1,40625), frontera C/R = 0,11 exacta y dominios | OK. El único consumidor (borrador 08, R = 3) no cambia |
| R236: 0 < TP < TL siempre, incluida la rama estática | `normativa_e030.py` (`_periodos_sitio`, `espectro`) | Misma prueba: TL < TP, TL = TP, TP = 0, T < 0, R = 0, P = 0, Z = ∞ | OK |
| R236: cobertura efectiva sin elevar lo declarado | `entrada_vision.py` (`_cobertura_efectiva`), `extraccion_preliminar.py` (`cobertura_efectiva`) | `test_cobertura_efectiva_no_se_eleva`. Respuesta real de Gemini: 32/38, 14/19 y 13/14, todas «parcial» | OK (`QA_CUARENTENA_09.json`) |
| R236: cuarentena en el formulario web | `revision_respuestas.py`, `respuestas.js`, `index.html` | `test_cuarentena_explicita_desde_el_formulario`; Node 12/12. QA HTTP con la respuesta real: sin cuarentena, 409 y nada guardado; con cuarentena, 34528ff1 queda pendiente sin importar | OK. El clic sobre la casilla lo cubre la prueba Node, no el navegador |
| R239: documentación vigente | `docs/RETOMAR.md`, `docs/MATRIZ_REQUISITOS_REFERENCIA.md` | Revisión del texto: la petición 2 consta como enviada y fallida; se elige el RNE vigente; recibos 4/5 y 2/5 | OK |
| R241: idealización por sección (piso frente a fondo/tapa) | `operaciones_etabs.py` (`tipo_shell_losa` por sección, `idealizacion_losas`) | `tests/test_idealizacion_losas_r241.py` (5 pruebas): `SetSlab` Membrane/ShellThick a la vez; `GetSlab` compara el tipo; el comparador del modelo guardado informa solo `FONDO25.shell`; la membrana en un fondo se rechaza; el modo global queda compatible y con aviso | OK. La UI de construcción está reservada a Codex (244); se conservó el campo JSON |
| R243-01: el ajuste exige ambos cierres laterales | `inventario_vectorial.py` (`_lado_cubierto`, estado `incompleto`) | `AdversasR243Tests`: cero, uno y dos lados, duplicados, lado partido que cubre o no (junta de 0,6 pt) | OK |
| R243-02: unión por distancia real | `inventario_vectorial.py` (`componentes`) | Separación de 0,84 / 0,61 / 0,60 / 0,30 pt y cadenas | OK. **Inventario real sin cambios**: 40 elementos, 29 componentes y 69 franjas idénticos |
| Inventario geométrico real | `inventario_vectorial.py` y `seguimiento/claude_ruta/inventario_09.py` | 40 elementos ajustados: C-1 ×2, C-2 ×10, C-3 ×2, C-4 ×3, C-5 ×2, C-6, PL-1…PL-10; superposición en `evidencia09/` | Parcial. C-3 dibujada .15×.55 y C-6 .20×.75, con discrepancia registrada. Faltan muros (73 ejes candidatos de franja), diagonales, escalera y tanque |
| Huecos de losa por nivel | Detección de X (diagonales cruzadas) en L0002 y L0003 | 5 huecos por nivel, coherentes entre niveles (≤ 2 cm) | Parcial: falta el hueco de escalera en 2–3 (lo corta C-6) |
| Geometría 0.3 por el flujo normal | `seguimiento/claude_ruta/geometria_09.py` → `importacion_tabular` → `importar-geometria` | Versión `8b39dd52` registrada, comprobación correcta, SHA de L0001–L0006 | Borrador con niveles (N2/N3 como hipótesis), 4 losas y 20 huecos; faltantes explícitos |
| Normativa integrada en la configuración | `draft2model/configuracion_normativa.py` | `tests/test_configuracion_normativa.py`: puertas separadas, espectro trazable con la hipótesis de escala 1 y decisiones mal formadas rechazadas | OK |
| Vs30 (Tabla 3 y nota de las Tablas 4/5) | `normativa_e030.parametros_sitio(vs30=…)` | Referencias de Codex (S2/450 → 1,05/0,5/2,25; S3/275 → 1,15/0,75/1,8); fronteras sin extrapolación; `verificar_normativa_e030.py` 29/29 | OK |
| Configuración 0.5 del caso | `seguimiento/claude_ruta/configuracion_09.py` → `CONFIGURACION_CASO_09.json` | Contrato no consistente: 18 errores que enumeran las puertas | Borrador. Hecho: concreto f'c 210 (E.060) y zona 4 / categoría C (lectura). Pendientes: albañilería (tipo de unidad), espectro (perfil), sistema, apoyos, masa, casos |

## 2. Hipótesis explícitas del piloto (no aprobadas)

- **Orientación 3↔A:** la favorece la escalera (auditoría 237), pero no está corroborada por dos rasgos independientes.
- **Alturas 5,20 y 7,80 m:** progresión uniforme. Las respuestas del usuario sobre niveles y EMS están pendientes; no se asumen.
- **Contorno de losas sobre los ejes A–H × 3–1:** no descuenta el espesor de los muros perimetrales.
- **Eje F:** L0001 difiere en ≈ 0,50 m de L0002/L0003. El borrador usa L0001 para la cimentación y las láminas de losa para los huecos.

## 3. Puertas del recorrido nativo (pendientes)

1. ~~Muros portantes revisados~~ → hecho en §6 (geometría 7c84de15). Queda por confirmar el espesor efectivo de la albañilería.
2. Sistema estructural y R0, y perfil de suelo/EMS: decisiones del usuario (§6, hallazgo material).
3. ~~Apoyos, masa, diafragmas, casos y análisis~~ → declarados en la configuración 09B como hipótesis. El sismo espera la puerta 2; el material de la albañilería espera el tipo de unidad.
4. Tanque y cisterna: nivel libre de operación, geometría y apoyos. La masa del agua es el 100 % del contenido (art. 31.e), sin duplicar la presión.

Mientras no se cumplan, **no se construye ni analiza el caso real**. El escenario sintético `r3` no lo sustituye.

## 4. Coordinación

- La reserva de UI de Codex (244) quedó **liberada**; los tres archivos entraron en la copia integrada del hito 09B.
- Suite amplia del hito: c210 pasó con 1211 pruebas OK. Entregas 04-f6bf94dd… y 06-1da89b0c… publicadas, con restauración verificada (código 0).

## 5. Regresión detectada por la suite integrada y corregida

**Fallo.** La copia c209 falló con 6 fallos y 60 errores (1211 pruebas).

**Causa.** `revision_modelo` regenera los planes históricos y los compara con los guardados. Dos cambios de R241 los alteraban:
- la clave nueva `idealizacion_losas`, que se añadía también en modo global;
- el texto de la constante `ShellType`.

**Corrección.**
- `idealizacion_losas` solo aparece con la formulación por sección.
- La constante recupera su texto original; la explicación de la formulación por sección queda en la documentación.
- Los planes globales vuelven a ser idénticos byte a byte, y no se repara ninguna huella.

**Verificación.**
- Los 17 módulos afectados pasan: 118 pruebas OK.
- Prueba nueva `test_global_conserva_el_plan_historico`.
- Copia integrada c210 repetida: el resultado figura en el log de la entrega.

## 6. Faltantes técnicos resueltos tras 09B (`punto_retomar_09`)

Ninguno de estos pasos aprueba nada; todos son reproducibles desde la raíz, sin red ni API.

| Paso | Archivo | Comprobación | Resultado |
|---|---|---|---|
| Plantilla ETABS propia del caso | `scripts/crear_plantilla_etabs_caso.ps1` → `data/private/pueblo-libre-002/plantillas/` | Instancia **propia** (PID 10072) identificada por diferencia de procesos y cerrada por la misma API; las 3 instancias previas siguen abiertas y sin tocar (`remaining_preexisting`). `synthetic_test: false` | EDB vacío ETABS 21.1.0, kN_m_C, SHA `e4759527…`. `$.plantilla` declara representación lineal y limitaciones de la albañilería. No se reutilizó la plantilla sintética 94006e0d |
| Muros portantes y placas | `seguimiento/claude_ruta/muros_09.py` → `MUROS_09.json`, `evidencia09/muros_L0004.png`, `muros_L0005.png` | Pluma de muros 1,68 pt de L0004/L0005; control de escala 8–1 = 20,01 m y A–E = 10,00 m | 8 muros de albañilería de 0,15 (ejes 3, 1, A y 2) y tramos de placa de 0,10, más 2 diagonales de PL-4. Fuera, con su motivo: los ductos de 0,10 sin placa y las bandas de columna |
| Lecturas de L0001 que fijan la clase | Cortes 1-1 y 5-5, especificaciones y nota | Revisión visual de la lámina | Sobrecimiento .15 bajo muro; muro de concreto .10 con malla; nota «paredes indicadas en aligerados = King-Kong» |
| Franjas de cimiento | `INVENTARIO_GEOMETRICO_09.json` | Contraste muro ↔ franja | Las franjas 0,50 incluyen pares falsos (bordes de celdas de terreno, p. ej. y = 1,80): **no se usan como ejes**; solo sirven para confirmar la continuidad vertical |
| Primer piso frente a típico | `MUROS_09.json` (`comparacion_L0004_L0005`) | Cobertura recíproca | Iguales salvo dos líneas de 0,10 en y = 3,12/6,92, continuas en L0004; solo se modela la parte cubierta por PL-5 y PL-7 |
| Geometría conforme | `seguimiento/claude_ruta/geometria_09b.py` → `revisar-geometria` → versión **7c84de15** (hija de 8b39dd52) | `validar_geometria`: consistente, 0 errores, 0 advertencias. Comprobación propia de nodos colgantes: 0 | 23 × 20 líneas; 2083 superficies (518 tramos de muro ortogonales, 32 diagonales de PL-4, 1533 celdas de losa) y 1931 vértices compartidos por identidad. Borrador con 5 faltantes declarados |
| Configuración 0.5 | `seguimiento/claude_ruta/configuracion_09b.py` → `CONFIGURACION_CASO_09B.json` | `validar_configuracion(cfg, geometría)` | De **18 a 2 errores**: `seccion.material` (la albañilería espera el tipo de unidad) y la malla, que espera a ese error. Datos: 76 columnas, 45 vigas VS sobre vanos, 161 apoyos, 4 diafragmas, 3066 cargas de losa, casos CM/CV/MODAL y combinación 1,4CM + 1,7CV |

**Hipótesis nuevas (declaradas en `$.hipotesis`, no aprobadas):**
- **Líneas de modelación:** el eje se ajusta a ±6 cm y los extremos a ±20 cm.
- **Vanos en toda la altura:** dinteles y alféizares no se modelan.
- **Losa:** membrana homogénea de 5 cm sin peso. El peso va como carga: 2,8 kPa del aligerado (E.020 Anexo 1, verificado en el texto oficial), 1,0 kPa de acabados (hipótesis) y 0,248 kPa de tabiques no estructurales, con pesos reales por E.020 1.1 repartidos.
- **Base empotrada.**
- **Diafragma rígido por nivel.**
- **C-1 en L:** se representa como 0,15×0,40.
- **C-6, escalera, tanque y PL-10:** fuera del modelo, como faltantes.
- **Espesor efectivo de la albañilería:** por confirmar.
- **Masa:** 100 % CM + 25 % CV (E.030 art. 31).

**Hallazgo material para el usuario.** En planta típica solo hay **8 muros de albañilería**: perímetro y eje central, todos en X salvo el eje A. La rigidez en Y depende de las placas de concreto de 0,10, y L0001 declara Rx = Ry = 6, el valor de muros de concreto en la norma de 2003. El sistema estructural (R0) **no se decide aquí**: se suma a las preguntas pendientes.

**Lo que sigue bloqueando el recorrido nativo (decisiones del usuario):**
- tipo de unidad de albañilería para Em;
- EMS o perfil de suelo;
- sistema estructural;
- alturas del 3.º y 4.º piso.

Sin la primera no hay material para los muros, y la configuración no es consistente. Sin las tres siguientes no hay sismo estático ni espectral.

**Malla (diagnóstico, sin material de albañilería).** Se ejecutó `malla_preparacion.preparar_malla` sobre la geometría 7c84de15 y la configuración 09B (`tmp/ruta201/muros/diag_malla.py`, registro `diag_malla.log`):
- 2083 hosts, 4182 triángulos y 0 conexiones de borde;
- **0 subdivisiones de frame**;
- 32 nodos derivados en celdas de losa cortadas por las diagonales de PL-4. Cuando se resuelva la puerta de material, habrá que declararlos en el diafragma de su nivel.

Tardó 2133 s: cada partición vuelve a validar la geometría completa. El rendimiento es una mejora posible, no un bloqueo.

**Hito 09C.** Copia limpia c211 completa: dependencias, CLI, PowerShell, suite e interfaz con código 0; 1211 pruebas OK; fuentes estables.
- Entregas: `entregas/04-dd25d50b…` (3 archivos cambiados: `scripts/crear_plantilla_etabs_caso.ps1`, `docs/GUIA_REPRODUCIBLE.md` §9 y `docs/MATRIZ_REQUISITOS_REFERENCIA.md`) y `entregas/06-26f220ab…` (536 archivos, bloqueada por las decisiones del usuario).
- Restauración verificada: `RESTAURACION_06F.json`, código 0.
- **No es el cierre del encargo 09.**

## 7. Hito 09D: C-1 en L nativa, cola 247 y decisiones 246

| Requisito | Archivo | Comprobación | Resultado |
|---|---|---|---|
| Reserva 246 de Codex | `seguimiento/ACUERDO_RESERVA_246.json` | `aceptada: true` antes de autorizar al agente; liberada por Codex 247 | Los 5 archivos entran en la instantánea 09D sin editarlos |
| C-1 en L nativa (AUDITORIA_C1_L_246) | `modelo_estructural.py` (`frame_l_concreto`, `insercion_frames` opcional, solo 0.5), `operaciones_etabs.py`, `ejecutar_plan_etabs.ps1`, `verificacion_modelo_guardado.py`/`.ps1` | `tests/test_columna_l_246.py` (7) y focales del hito (182 OK) | OK; los planes y lecturas sin L no cambian |
| Semántica nativa | `scripts/ensayar_columna_l_etabs.ps1` → fixture `columna_l_etabs21_246.json` | Voladizos propios. La carga axial revela el vector nudo → centroide; la lateral, el acople | Espejos ↔ brazos fijados (`docs/COLUMNA_L_NATIVA.md`). en el montaje ensayado la respuesta no mostró acople por producto de inercia (observación de ese montaje, no generalizada; R249-01) |
| Recorrido completo nativo | `scripts/ensayar_plan_columna_l.py` → `tmp/columna_l_plan_246a` | Plan 0.5 de 241 operaciones; el ejecutor relee la L y 3 inserciones; relectura independiente del EDB | `verificado`, 0 discrepancias, cobertura completa. Instancias propias cerradas |
| C-1 del caso | `configuracion_09b.py` | Dos L por instancia (A/3 con `espejo_eje_2`, A/1 sin espejos) e inserción en el centroide real | Desplazamientos (+0,0769; +0,0579) y (+0,0769; −0,0979) m, iguales a la auditoría |
| Decisiones del usuario 246 | `seguimiento/DECISION_USUARIO_246.json` (fuente F-DECISION-USUARIO-246) | Ladrillo de arcilla (Em = 500 f'm), peso 18 kN/m³ (E.020, cocida sólida, hipótesis de clasificación) y niveles confirmados | Material de albañilería completo: la configuración pasa de 2 errores a **0** |
| Pesos E.020 citados | `normativa_rne.py` (`albanileria_cocida_*`, `peso_aligerado`) y `verificar_normativa_e030.py` | Texto oficial | 32/32 fragmentos |
| CLI 0.5 (BRECHA_CLI_247) | `operaciones_etabs.main` | `tests/test_cli_plan_etabs_247.py` (4): despacho 0.4/0.5, mapa por sección desde archivo, conflicto, archivos inválidos y plan 0.5 real | OK |
| Ciclo de vida de la plantilla (REVISION_PLANTILLA_247) | `scripts/crear_plantilla_etabs_caso.ps1` | Rama de validación (exit 1 y recibo, sin ETABS). Rama feliz en tmp (`created`, cierre 0, PID propio desaparecido, 3 ajenas intactas) | Éxito solo si hay archivo, hash, cierre y proceso verificado. Cierre por el objeto propio tras arranque parcial; recibo con respaldo en stderr. La plantilla del caso (`e4759527…`) no se regeneró |
| Malla real tras la optimización 246 | `tmp/ruta201/malla_real_c1_246.json` | Validación con geometría 7c84de15 | 160,6 s (antes 2133 s), con la **misma huella de preparación**. Se ejecutó dos veces: la primera, implícita al validar. Desde ahora el guion solo valida con `--con-malla` |

**Pendiente en la geometría (insumos 248):**
- cisterna y tanque (este último con alternativas E03/A03);
- escalera en U;
- C-6 (N0–N3 como idealización declarada);
- PL-10 como cercos de 2,40 m.

**Pendiente en la configuración:** la política de los 32 nodos derivados, los escenarios de suelo y sistema como hipótesis, y el recorrido ETABS propio por etapas.

## 8. Hito 09E: geometría con insumos 248, configuración 09C y escenarios sísmicos

| Elemento | Archivo | Evidencia y comprobación | Resultado |
|---|---|---|---|
| Geometría 09C | `geometria_09c.py` → versión **3905c919** (hija de 7c84de15) | Validador: 0 errores y 0 advertencias. Nodos colgantes: 0 tras ajustar el tanque a la línea de la C-2 del eje 2 (x = 11,335) | 2040 superficies y 1896 vértices; 6 faltantes declarados |
| PL-10 | Ídem | Corte 2-2 + A01 «CERCO H=2.40», contorno de E01 | Dos cercos de 0,10 m (f'c 175) de −0,05 a +2,35, con base propia e independientes del edificio. No se extruyen de N0 a N4 |
| C-6 | Ídem | Huella en tres plantas, .20 × .75; el cuadro dice .15 × .75 | Frame de N0 a N3, sin diafragma; no llega a N4 (ausente en E03). Ya no añade la línea artificial y = 4,798 a la cuadrícula |
| Cisterna | Ídem | Caja de L0001 2,35 × 2,55 = claro 2,00 × 2,15 + muros .15/.20 (E03). NFC −2,65 = solado .05 (hipótesis): la tapa queda a −0,03, 3 cm bajo el NPT, cadena coherente | Muros, fondo .20 y tapa .15 con acceso .55; base empotrada en −2,50 |
| Tanque | Ídem | Tres «NACE C-2» vectorizados en E03 + la C-2 del eje 2. El corte de E03 no está a escala («2.00» mide 1,68 m) | Alternativa **E03-apoyos** modelada: 4 C-2 desde N4 y caja de 0,20 con fondo +12,50 y tapa +14,25. Alternativa **A03** (2,82 × 3,92, NTT +14,60) registrada y no modelada. Base +10,40 frente a NT +10,35, declarada |
| Escalera | `DEPOSITOS_09C.json` | Auditoría 248. A03 da 50–52 / 53–60 / 61–64 = 16 contrahuellas de 0,1625 en el último entrepiso, pero A01/A02 difieren | **No modelada**: su trazado, ojo e hipótesis A03 quedan registrados. Masa estimada fuera del modelo ≈ 40 kN por piso (≈ 4 %) |
| Configuración 09C | `configuracion_09c.py --con-malla` → `CONFIGURACION_CASO_09C.json` | **Una** preparación de malla real: 144,3 s, 4096 triángulos, 32 nodos derivados con diafragma de su nivel y 0 subdivisiones. Validación con geometría | **Consistente, 0 errores**. Faltantes: sitio (perfil, sistema, Ia, Ip), sismo, escalera y líquidos |
| Agua | `DEPOSITOS_09C.json` | Tanque 1,10 m sobre el fondo y cisterna llena hasta 2,22 m, con sentido de presión calculado por superficie | Escenarios **preparados y no aplicados**: `acciones_liquidos` exige una geometría sin faltantes, y la escalera sigue sin modelar |
| Escenarios sísmicos | `escenarios_sismicos_09.py` → `ESCENARIOS_SISMICOS_09.json` | Perfiles S1/S2/S3 sin Vs30 × albañilería confinada (R0 = 3) o muros de concreto (R0 = 6), con Ia = Ip = 1 (hipótesis), T = hn/60 = 0,173 s y C = 2,5 | P ≈ 4614 kN con el tanque en escenario de 1,10 m. V va de 865 (S1, R = 6) a 2077 kN (S3, R = 3). **Ninguno se elige ni se aprueba**. Como referencia, L0001 (norma 2003) declara V = 0,166 P |

**Por qué el recorrido ETABS del caso real no se ejecuta.**
- El plan exige `apto_para_adaptador`, lo que supone geometría y configuración **aprobadas** y sin faltantes.
- Siguen abiertos el sitio/sistema (con escenarios hipotéticos preparados), la escalera y el agua (que depende de la escalera).
- La aprobación, aunque se limitara al transporte de software, es una decisión que no tomo por mi cuenta.

Hasta esa decisión, la cadena nativa queda acreditada con los ensayos sintéticos propios: L nativa y recorrido verificado (09D).


## 9. Recorrido ETABS propio del caso real: escenario de transporte 09T

**Autorización del usuario (chat, 2026-10-22):** «aprobación declarada limitada a transporte de software (no ingeniería) para el recorrido ETABS del caso real por etapas, usando un escenario de suelo/sistema etiquetado como hipótesis».

### Escenario y versiones

- **Sitio y sistema (hipótesis):** S1 y muros de concreto R0 = 6, ambos de la lectura de L0001 (GP; S = 1,0; Rx = Ry = 6 con la norma de 2003), con Ia = Ip = 1.
  - Espectro E.030 `ESP-S1-R6-HIP`.
  - Casos espectrales SX/SY: CQC, 5 % de amortiguamiento, excentricidad 0,05 y factor 1 (el espectro ya incluye g y R).
- **Geometría:**
  - 09C con los niveles físicos de los depósitos (NCF −2,50; NTF +12,50; NTT +14,25): versión `8860a4f0`.
  - Variante de transporte (los 6 faltantes pasan a hipótesis declaradas): `a970ed40`.
  - Aprobación declarada de transporte: `0e1295e1`.
  - La geometría honesta del caso (`8860a4f0`/`3905c919`) conserva sus faltantes.
- **Configuración 09T** (`configuracion_09c.py --transporte`): 0 errores y 0 faltantes.
  - El agua se aplica en sus escenarios: tanque 1,10 m y cisterna 2,22 m.
  - El peso de la escalera (no modelada) se aplica como fuerzas en sus llegadas del eje H: 40 kN de peso propio y 14 kN de sobrecarga por tramo.
- **Aprobación de la configuración:** declarada de transporte, versión ``fc65c6c7fe104e21a114c345a0cf713f` (09t4)`.

### Fallos encontrados por las etapas y su corrección (sin ocultar)

| Intento | Etapa | Hallazgo | Corrección |
|---|---|---|---|
| `tmp/recorrido_09t` | Plan | Rechazo: puntos de cisterna y tanque fuera de [N0, N4] («no se crean pisos ficticios») | Niveles físicos NCF/NTF/NTT en la geometría; no son pisos de losa |
| `tmp/recorrido_09t2` | Precondición del ejecutor (orden 8, solo lectura) | La plantilla vacía ya trae el caso por defecto «Modal» de ETABS; choca con «MODAL» | Caso renombrado a `MODAL-E030`. Sin mutación ni guardado; cierre propio confirmado; recuperación del motor registrada. Lista de nombres de la plantilla en `tmp/nombres_plantilla_09t` (sin más colisiones) |
| — | Documentación | La «plantilla vacía» contiene las definiciones por defecto de ETABS (4 materiales, 126 secciones de frame, Dead/Live, D1, funciones) | Texto de limitaciones corregido en `$.plantilla` |
| `tmp/recorrido_09t3` | Relectura independiente | **32 nodos colgantes** (8 por piso): la partición subdivide las celdas cortadas por las diagonales de PL-4 y, sin conexiones declaradas, sus nodos no llegan a la vecina | `conexiones_borde` declara las aristas compartidas de las superficies no rectangulares. Comprobación local antes de ETABS: 0 colgantes; en control, sin conexiones, 32. El modelo `b85244d8` queda registrado **no verificado**, sin aprobar ni analizar |
| `tmp/recorrido_09t4` | Construcción | 29 416 operaciones; modelo `8ed9474e…`, EDB `b86b0222…`; cierre propio confirmado | — |
| `tmp/recorrido_09t4` | Relectura independiente | **verificado**: 0 discrepancias, 0 incompletos; cobertura completa salvo `ejes_locales_area` (sin criterio). Aceptada por Codex (REVISION_RELECTURA_259) | — |
| `tmp/recorrido_09t4` | Análisis (runner 256) | **Rechazado por la guarda de etapa**: el registro, escrito por el runner anterior, no tiene `sha256_plantilla_esperada/anterior`. El registro conserva `analisis_error` | No se editó el registro ni se eludió la guarda. El recorrido completo se repite en 09D con el runner fusionado, que registra todas las huellas |

09T es un **diagnóstico**: la escalera va como cargas, el agua está en planos medios y los niveles de los depósitos son Story. No valida
la escalera ni las caras mojadas de 09D.

## 10. Bloque 258: integración en el flujo general y escenario 09D

- **Cotas auxiliares** (`docs/COTAS_AUXILIARES.md`): `niveles[].tipo = auxiliar` en el contrato de geometría. NCF/NTF/NTT ya no son
  Story (09D-v3: `d0acfe83` → transporte `561fc15d` → aprobada `25ef9467`); N0 es la base y N1–N4 los únicos pisos. Se apoya en el
  ensayo nativo de Codex 257, que no se repitió.
- **Contenido** (`docs/MASA_CONTENIDO.md` §Integración): `liquidos.contenido` en el contrato 0.5, auditado por el validador general
  con `masa_contenido` sobre la malla vigente.
  - 09D: tanque lleno 3,9392 m³ / 39,392 kN; cisterna llena 9,5559 m³ / 95,559 kN. Fz = −γV en ambos.
  - Masa nativa **no** verificada.
  - El plan lleva `contenido_masa`. El informe lo toma del plan del modelo analizado y exige `masa_nativa_verificada = false`
    (Codex 261). Los JSON malformados dan error controlado (Codex 260).
- **Runner 256 fusionado**: 16 pruebas. Se añadieron `--configuracion` (aplicada), alcance 09D, `configuracion_fuente` y `ESC-15`, y una
  lectura de masa por piso como diagnóstico no bloqueante. El análisis exige el sidecar `revision_controles_09.py`.
  - En ese sidecar, el revisor es Claude: revisión propia de software sobre la relectura.
  - Es una pieza distinta de la autorización del usuario y de cualquier aprobación de ingeniería.
- **09D-v3, configuración de transporte:**
  - Contrato consistente, 0 errores.
  - Malla: 311 s, 104 nodos derivados, 5231 triángulos, 0 colgantes locales.
  - Conteos: 2356 puntos, 2502 superficies, 128 frames, 203 apoyos, 4 diafragmas.
- **Entregas:**
  - `06-85895489…` contiene solo los 10 archivos cambiados.
  - `06-05696cd0…` es el snapshot completo: restauración código 0, con 559 miembros, 96 módulos y 16 pruebas.
  - Marcador: `MARCADOR_258.json`.
- **Métricas** (`METRICAS_EXTRACCION_09.json`):
  - 6 peticiones de visión, 2 de ellas fallidas; 228 candidatos sin deduplicar; 0 lecturas aprobadas.
  - Coste OpenAI USD 0,5404 (tarifa estándar sin caché); Gemini en nivel gratuito declarado.
  - Precisión **no verificable**: no hay anotación humana de referencia.
  - La geometría del piloto proviene de los vectores PDF, no de la visión.
