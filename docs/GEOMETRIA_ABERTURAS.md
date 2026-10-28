# Geometría con aberturas v0.3

Incremento local de geometría y propuesta geométrica. No habilita configuración ni ejecución ETABS v0.3. Conserva los contratos0.1 y0.2: sus campos y resultados no se reinterpretan. La lista `aberturas` es desconocida en ellos.

## Contrato y API

`draft2model.contratos.VERSION_GEOMETRIA_ABERTURAS = "0.3.0"`. La raíz contiene exactamente los campos0.2 y una lista **obligatoria** `aberturas`, que puede estar vacía. Cada abertura tiene exactamente:

```json
{"id":"A1","superficie":"S1","vertices":["H1","H2","H3","H4"],"procedencia":{"tipo":"sintetico","descripcion":"Hueco de prueba de software"}}
```

Los vértices son IDs de la colección raíz `vertices`, con sus XYZ físicos y procedencia. `superficie` referencia una superficie explícita, nunca un muro legado. IDs únicos dentro de cada colección; el contorno ordenado no repite el primer punto al final. No se reordenan puntos ni se reparan contornos. Las aberturas se comparan entre sí por superficie anfitriona.

Entrada pública: `validacion_geometria.validar_geometria(data)` despacha a `geometria_aberturas.validar_aberturas`. Es pura, no cambia la entrada ni consulta ETABS/red. Devuelve el mismo `ResultadoValidacion` usado por los contratos previos. Ante cualquier error de huecos no publica `geometria_m`, `derivados_m` ni huella parcial.

La copia normalizada conserva todos los contornos, IDs, procedencias y relaciones. Los XYZ se normalizan a metros con los divisores existentes m/cm/mm. En `derivados_m`:

- `superficies[S1]` conserva `area_m2` como área **bruta** y añade `area_bruta_m2`, `area_aberturas_m2`, `area_neta_m2`, `aberturas_ids`.
- `aberturas[A1]` contiene `vertices_m`, `area_m2`, `normal_unitaria`, `epsilon_relativo_computacional` del contorno, `superficie_id` y `epsilon_relativo_anfitriona_computacional`.
- Área neta = área bruta menos suma `math.fsum` de las áreas de sus huecos, y debe ser finita y positiva. No representa peso, masa, rigidez ni capacidad resistente.

`plan_modelado.preparar_plan_modelado(data)` genera un **plan geométrico0.3**, no un plan de operaciones. Conserva `vertices` normalizados con su procedencia, contornos de superficies y `aberturas` como objetos separados, cada uno ligado a anfitriona, IDs, XYZ y procedencia; añade las áreas bruta/huecos/neta y los IDs de huecos por anfitriona. `area_geometrica_m2` de una superficie sigue siendo bruta; usar el campo explícito `area_neta_m2` si se necesita área neta. Incluye huella de todo el contenido fuente y `cobertura_aberturas` para fuentes consistentes. Una fuente inválida no produce superficies ni huecos parciales. `ejecutable_en_etabs` siempre es falso.

`gestion_geometria` admite importación/revisión/aprobación declarada como versiones en disco, con las guardas existentes de contenido, archivo y parentesco. Aprobar exige consistencia, ausencia de faltantes y huella vigente; crea una versión hija y conserva el padre. La aprobación geométrica no quita `BLOQUEO_INTEGRACION`, no certifica seguridad ni habilita el adaptador. Modificar un hueco o sus vértices invalida la huella/aprobación.

## Criterios computacionales

Cada contorno anfitrión y cada hueco usa `_poligono`0.2: traslación al primer vértice, escala máxima de extensión, normal del mayor producto vectorial y proyección quitando el eje dominante de la normal. El epsilon relativo es `max(1e-12, 64*ulp(coordenada_máxima)/escala)`; se rechaza una condición superior a1e-6. Se comprueban finitud, área positiva, coplanaridad, aristas degeneradas/repetidas, autointersección y contactos no adyacentes. La orientación sigue el orden declarado.

Para comparar huésped y anfitriona se usa **una misma** traslación/escala/proyección de la anfitriona. El epsilon toma el mayor entre el de ella y `64*ulp(coordenada_máxima_del_hueco)/escala_anfitriona`; si no es finito o supera1e-6 se rechaza. La distancia normal dividida por esa escala no puede superar epsilon. Segmentos se comparan mediante orientación con epsilon y cajas ampliadas epsilon, conservadoramente: contacto numéricamente ambiguo se rechaza. El interior estricto se calcula por cruce de rayo, excluyendo previamente borde/contacto. Todos los vértices del hueco deben estar dentro y ninguna arista puede cruzar/tocar el contorno anfitrión. Esta segunda condición también detecta un puente a través de la entrante de una anfitriona cóncava. Entre huecos se rechazan cruces/contactos y contención en ambas direcciones, incluida anidación. Un contorno cóncavo simple es admisible geométricamente.

Estos epsilon son criterios de representabilidad binaria64, **no tolerancias de ingeniería**, ajuste de planos ni aceptación de fabricación. No se ajustan posiciones, no se deducen medidas desde imágenes y no se fusionan vértices. La representación explícita no prueba conectividad de una malla estructural.

## Verificación focal reproducible

Desde la raíz PowerShell:

```powershell
$env:TEMP=(Resolve-Path tmp).Path
$env:TMP=$env:TEMP
.venv/Scripts/python.exe -m unittest tests.test_geometria_aberturas -v
.venv/Scripts/python.exe -m unittest tests.test_validacion_geometria tests.test_geometria_superficies tests.test_plan_modelado tests.test_gestion_superficies -v
```

Pruebas nuevas: horizontal/inclinado/vertical y unidades, varias aberturas, orden invertido conservado, áreas netas/trazas/copia pura, lista vacía/versiones estrictas, hueco exterior/contacto/cruce/no coplanar/autointersección, concavidad y puente por entrante, contacto/solape/anidación en ambas direcciones, esquema/referencias/IDs/números inválidos, aprobación alterada y gestión real en disco. Son datos sintéticos. Los resultados y hashes del entregable se registran en `tmp/entrega_aberturas_geometria.json`; no equivalen a una suite global.

## Pendientes materiales de integración

No se modifica ni habilita `modelo_estructural`, configuración, conversión, tabular, superposición ni ejecutor para0.3. No hay migración automática0.2→0.3, transporte `SetOpening`, partición de superficies, mallado, verificación guardada, cálculo ni prueba API real de este incremento. Un consumidor no compatible debe rechazar0.3 íntegramente; jamás procesarlo como0.2 y rellenar silenciosamente sus huecos. Codex debe integrar y verificar esos consumidores por separado antes del recorrido real de los planos. Los aligerados, escalera y cisterna/tanque completos requieren todavía su representación/hipótesis/acciones revisadas.
