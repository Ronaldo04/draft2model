# Servicio persistente e interfaz web de digitización calibrada (v0.1.0)

`draft2model/revision_digitizacion.py` (`ServicioDigitizacion(app)`) y `draft2model/revision_web/digitizacion.js` conectan el núcleo algebraico puro `draft2model.digitizacion_calibrada.calibrar_digitizacion` con la etapa 3 (`geometria`) de la interfaz local. Toda salida permanece en **borrador** (`revision: {estado: "borrador", aprobacion: null}`, `disponible_para_modelado: false`, `aprueba_ingenieria: false`, `ejecuta_etabs: false`) y no modifica geometrías ni incorpora contornos automáticamente al modelo.

---

## 1. Integración de rutas y recursos para `revision_visual.py` / `index.html`

El módulo está diseñado para conectarse como propiedad perezosa `app.digitizacion = ServicioDigitizacion(self)` en `RevisionLocal` y cargar `<script src="/digitizacion.js" defer></script>` tras `etapas.js` y `app.js`:

| Ruta HTTP | Método en `ServicioDigitizacion` | Parámetros / Cuerpo |
| --- | --- | --- |
| `GET /api/digitizacion/historial` | `listar(arg('caso'), arg('expediente_sha256'))` | Query: `caso`, `expediente_sha256` |
| `GET /api/digitizacion/registro` | `consultar(arg('caso'), arg('expediente_sha256'), arg('id'))` | Query: `caso`, `expediente_sha256`, `id` |
| `POST /api/digitizacion/preparar` | `preparar(body)` | JSON cerrado sin coordenadas métricas |
| `POST /api/digitizacion/calcular` | `calcular(body)` | JSON cerrado sin coordenadas métricas |

Los rechazos de seguridad, vigencia o álgebra lanzan `ErrorRevisionDigitizacion(codigo, mensaje, **detalles)` (subclase de `ValueError`), apto para responder HTTP `409` sin exponer rutas locales del sistema de archivos.

---

## 2. Contratos cerrados del servicio (`ServicioDigitizacion`)

### Prohibición de coordenadas métricas desde navegador o IA
Tanto `preparar(body)` como `calcular(body)` inspeccionan recursivamente toda la carga recibida y rechazan (`coordenadas_metricas_no_admitidas`) cualquier clave física: `puntos_resueltos`, `coordenadas`, `coordenadas_m`, `xy`, `xy_m`, `xyz`, `x`, `y`, `z`, `metros`. Las coordenadas métricas de referencia provienen **exclusivamente** de los vértices coplanares de la versión `0.3.0` vigente de geometría comprobada en disco.

### `POST /api/digitizacion/preparar` (`preparar(body)`)
Claves obligatorias:
- `caso`, `expediente_sha256`
- `geometria` (UUID 32 hex), `huella_geometria` (SHA-256 canónico), `sha256_geometria` (SHA-256 de `geometria.json`)
- `fuente`: `{"original_id", "pagina", "dibujo_id", "bbox_pagina"}` y opcionales `"sha256"`, `"revision_documental"`, `"recorte"`
- `plano`: `{"id", "ejes", "eje_constante", "valor_constante", "unidad_longitud"}`
- Opcional: `origen_propuesta`: `{"modo", "referencia_origen", "editada_en_pantalla"}`

Comprobaciones ejecutadas:
1. Verifica ausencia de enlaces simbólicos o *reparse points* en raíz, expediente, originales, geometría y subcarpetas.
2. Verifica bytes reales de todos los originales del expediente mediante `app._original` y renderizado efectivo de la página mediante `app.pagina`; comprueba coherencia con `revision_documental` y `recorte` si existen o se vinculan.
3. Exige geometría `0.3.0` consistente, unidad del plano idéntica a `geometria.unidad_longitud` y cota constante existente en vértices o niveles de la geometría (no inventa cotas ni unidades).
4. Extrae `catalogo_referencias` coplanar y persiste atómicamente `<caso>/digitizaciones/<id>/{registro.json, version.json}` con etapa `"preparada"`.

### `POST /api/digitizacion/calcular` (`calcular(body)`)
Claves obligatorias:
- `caso`, `expediente_sha256`, `geometria`, `huella_geometria`, `sha256_geometria`, `propuesta_id`
- `fuente`: `{"original_id", "sha256", "pagina", "dibujo_id", "bbox_pagina"}` ( más `"revision_documental"` / `"recorte"` opcionales)
- `plano`: `{"id", "ejes", "eje_constante", "valor_constante", "unidad_longitud"}`
- `limites`: las 9 claves positivas finitas exigidas por `digitizacion_calibrada`
- `anclas`: lista de `{"id", "punto_resuelto", "uv_local"}` (o con `fuente` y `plano_id` idénticos al activo)
- `controles`: lista de `{"id", "punto_resuelto", "uv_local"}`
- `puntos`: lista de `{"id", "uv_local", "relacionados"}`
- Opcionales: par conjunto `preparacion_id` + `huella_preparacion`, y `origen_propuesta`.

### Vínculo documental honesto, referencias insuficientes y vigencia semántica
- **Sin fabricar referencias documentales:** Si un vértice de la geometría `0.3.0` no posee `procedencia.referencias`, el servicio nunca inventa IDs documentales. Para permitir el cálculo numérico en borrador emplea el descriptor explícito `descriptor_geometrico:<geometria_id>`, registra `carencia_vinculo_documental_puntos` en `pendientes` y mantiene `exactitud_documental_acreditada: false`. Las referencias textuales de geometría o conversión tampoco acreditan ubicación `uv_local` en el dibujo (`ubicacion_en_dibujo_acreditada: false`). Como todos los vértices sin referencia documental comparten ese único descriptor geométrico, el núcleo puro impide usarlos como falsos controles independientes (`control_dependiente`).
- **Referencias insuficientes en la geometría:** Si el plano existente en la geometría tiene menos de 3 referencias coplanares no colineales utilizables, `preparar` y `calcular` conservan un registro con `calculo_posible: false` y pendiente explícito `referencias_coplanares_insuficientes`, sin fabricar puntos.
- **Rederivación semántica íntegra en lectura (`_cargar_y_comprobar`):** Los hashes locales (`huella_version` y `version.json.sha256_registro`) no se aceptan como prueba independiente de autenticidad semántica. Al consultar o listar cualquier etapa (`preparada`, `pendiente_referencias`, `calculada`), el servicio vuelve a comprobar bytes de originales, vista previa, geometría `0.3.0`, hashes de código, preparación vinculada (si existe) y propuesta normalizada; reejecuta `calibrar_digitizacion` en registros calculados y reconstruye íntegramente `resumen`, `pendientes`, `catalogo_referencias`, `cotas_disponibles_eje`, `hashes_entradas` e invariantes de borrador mediante los mismos constructores puros usados al guardar (`_construir_registro_preparada`, `_construir_registro_pendiente_referencias`, `_construir_registro_calculada`). Cualquier discrepancia canónica en resumen, pendientes, catálogo, flags o propuesta se rechaza con `registro_alterado` (y `calculo_alterado` si cambió el resultado algebraico), incluso si ambos SHA-256 locales fueron recalculados en disco.

---

## 3. Evento de interfaz `d2m-digitizacion-propuesta`

`digitizacion.js` se monta en `D2MEtapas.containers.get('geometria')` sin usar `innerHTML`, `eval`, carga de archivos ni `textarea` de JSON externo. Separa visualmente la recepción automática y la revisión del ingeniero, y acepta el evento `CustomEvent('d2m-digitizacion-propuesta', { detail })` con este esquema:

```json
{
  "caso": "identificador-caso",
  "expediente_sha256": "64-hex",
  "geometria": "32-hex-opcional",
  "huella_geometria": "64-hex-opcional",
  "referencia_origen": "ID_TRAZA_IA_OPCIONAL",
  "propuesta_id": "PROP_DIG_1",
  "fuente": {
    "original_id": "L0001",
    "pagina": 1,
    "dibujo_id": "PLANTA_N0",
    "bbox_pagina": [0.0, 0.0, 1.0, 1.0]
  },
  "plano": {
    "id": "PLANO_Z_0",
    "ejes": ["x", "y"],
    "eje_constante": "z",
    "valor_constante": 0.0,
    "unidad_longitud": "m"
  },
  "limites": {
    "residuo_ajuste_max_m": 0.02,
    "error_control_max_m": 0.03,
    "incertidumbre_max_m": 0.08,
    "localizacion_uv": 0.005,
    "referencia_m": 0.005,
    "condicion_max": 50.0,
    "escala_min_m_por_uv": 0.1,
    "escala_max_m_por_uv": 500.0,
    "coordenada_abs_max_m": 1000.0
  },
  "anclas": [
    { "id": "A1", "punto_resuelto": "VA", "uv_local": [0.1, 0.875] },
    { "id": "A2", "punto_resuelto": "VB", "uv_local": [0.9, 0.875] },
    { "id": "A3", "punto_resuelto": "VC", "uv_local": [0.9, 0.125] }
  ],
  "controles": [],
  "puntos": [
    { "id": "PN1", "uv_local": [0.5, 0.5], "relacionados": ["VA", "VB", "VC"] }
  ]
}
```

Reglas de interfaz:
- Rechaza cualquier `detail` de otro expediente, de otra geometría/unidad o que incluya claves métricas físicas.
- Rellena los campos en pantalla **sin ejecutar ni aprobar automáticamente**; si el ingeniero edita cualquier valor normalizado o tolerancia, marca `editada_en_pantalla: true` e invalida cualquier cálculo/huella previa.
- Destaca expresamente que **3 anclas con residuo 0 m no constituyen verificación independiente** y mantiene visible la carencia de vínculo documental e incertidumbre indicativa.
- **Concurrencia por expediente, geometría exacta y generación de formulario:** Cada operación asíncrona (`preparar`, `calcular`, `abrir` registro e `historial`) queda vinculada a un identificador de solicitud y a contadores de generación de expediente (`d2m-case`), geometría abierta (`d2m-geometry-opened` + firma exacta `version_id`, `huella` y `sha256_geometria`), fuente/plano y edición de formulario/tolerancias/entradas `[u, v]`. Cualquier cambio de caso, geometría, propuesta estructurada o edición de entradas cancela las solicitudes en vuelo, libera controles para el contexto nuevo y descarta respuestas tardías o registros pertenecientes a otra versión geométrica sin restaurar métricas, huellas ni habilitar `digCalcular` sobre otra geometría.

---

## 4. Pruebas focales reproducibles (sintéticas, sin red ni ETABS)

```powershell
.\.venv\Scripts\python.exe -X utf8 -B -m unittest -v tests.test_revision_digitizacion
node tests/digitizacion_353_frontend.cjs
```
