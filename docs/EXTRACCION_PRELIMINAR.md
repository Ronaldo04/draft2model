# Extracción preliminar: candidatos, evidencia y revisión

> **Contrato 0.2.0 (encargo 07):** tipos semánticos, texto literal, cobertura por recorte, reclasificación y reubicación revisadas. Ver [LECTURAS_SEMANTICAS](LECTURAS_SEMANTICAS.md). Lo descrito abajo para 0.1.0 sigue siendo válido para artefactos guardados.

Estado: **propuesta inicial v0.1**, 14 de octubre de 2026. Contrato para registrar lo que se lee en un plano, con su origen, y las correcciones declaradas por quien revisa. No es OCR, no genera geometría y no aprueba datos de ingeniería.

Implementación: [`draft2model/extraccion_preliminar.py`](../draft2model/extraccion_preliminar.py). Ejemplo sintético: [`examples/extraccion_sintetica.json`](../examples/extraccion_sintetica.json). Pruebas: [`tests/test_extraccion_preliminar.py`](../tests/test_extraccion_preliminar.py).

Corresponde a `extraccion_preliminar.json` del [contexto del proyecto](CONTEXTO_PROYECTO.md). Se sitúa entre los [recortes](RECORTES.md) y el [contrato de geometría](CONTRATO_GEOMETRIA.md), sin modificar ninguno de los dos.

## Estructura

```json
{
  "contrato": "draft2model.extraccion_preliminar",
  "version_contrato": "0.1.0",
  "caso": "sintetico-ext-001",
  "procedencia": {"tipo": "sintetico", "descripcion": "..."},
  "alcance": {"estado": "pendiente_verificar", "uso": "pendiente", "motivos": []},
  "sistema_coordenadas": "pagina_visible_normalizada",
  "candidatos": [{
    "id": "C001",
    "tipo": "cota",
    "valor_propuesto": 2.6,
    "unidad": "m",
    "texto_fuente": "2.60",
    "metodo": {"tipo": "manual"},
    "evidencia": [{
      "archivo_id": "L0001", "pagina": 1, "original_sha256": "<sha256>",
      "recorte_id": "<id>", "imagen_sha256": "<sha256>",
      "bbox_normalizada": [0.20, 0.30, 0.26, 0.33]
    }],
    "revision": {"estado": "pendiente", "historial": []}
  }]
}
```

| Campo | Reglas |
| --- | --- |
| `contrato`, `version_contrato` | Coincidencia exacta. |
| `caso` | Identificador del expediente. |
| `procedencia.tipo` | `sintetico` o `expediente`; `descripcion` obligatoria; `expediente_sha256` opcional. |
| `alcance` | Copia del bloque `alcance` del expediente, con `estado` obligatorio. Se conserva sin cambios. |
| `sistema_coordenadas` | Solo `pagina_visible_normalizada`. |
| `candidatos[].tipo` | `cota`, `etiqueta` o `elemento`. |
| `valor_propuesto` | Cota: número finito o `null`. Etiqueta y elemento: texto no vacío o `null`. Los booleanos no son números. |
| `unidad` | Obligatoria. Cota: `m`, `cm`, `mm` o `desconocida`. Etiqueta y elemento: `no_aplica`. |
| `metodo.tipo` | `manual`, `sintetico`, `ocr`, `vision` o `importado`; opcionales `herramienta`, `version`, `descripcion` y `confianza` (de 0 a 1). |
| `evidencia[]` | Lista no vacía. Obligatorios: `archivo_id`, `pagina` (entero desde 1), `original_sha256` y `bbox_normalizada`. Opcionales: `recorte_id` e `imagen_sha256`; este último exige `recorte_id`. |
| `revision` | Opcional; si falta, el candidato está pendiente. |

`bbox_normalizada = [x0, y0, x1, y1]` sigue la convención de [RECORTES.md](RECORTES.md): página visible con la rotación aplicada, origen en la esquina superior izquierda, X hacia la derecha, Y hacia abajo, `0 <= x0 < x1 <= 1` y `0 <= y0 < y1 <= 1`. **No son metros ni coordenadas CAD.**

Se rechazan los campos no definidos y los identificadores de candidato repetidos.

## Decisiones

1. **Lo desconocido permanece desconocido.** Un valor ilegible es `null` y una unidad no indicada es `desconocida`. El módulo no deduce unidades ni completa valores.
2. **La unidad siempre es explícita**, incluso cuando es `desconocida` o `no_aplica`. Una clave ausente es un error.
3. **Sin conversión de unidades.** Se exporta el valor y la unidad revisados tal como se declararon. La normalización a metros corresponde al contrato de geometría, cuando una persona construya esa geometría.
4. **Los candidatos no se convierten en geometría.** Una etiqueta `EJE A` o un elemento `muro` no crean ejes, nodos, muros ni niveles. La topología se definirá en una etapa posterior con revisión.
5. **Elementos con texto libre.** v0.1 no fija una taxonomía de elementos para no adelantar decisiones de modelado.
6. **`ocr` y `vision` son métodos declarables**, para registrar candidatos producidos por herramientas futuras. Este módulo no ejecuta OCR ni visión.

## Referencias a la evidencia

`validar_extraccion(data, inventario=None)` informa un estado por cada evidencia:

| Estado | Significado |
| --- | --- |
| `referencia_no_comprobada` | No se aportó inventario. La forma es válida, pero archivo, hash, página y recorte **no se verificaron**. |
| `comprobada` | Archivo, hash, página y, si se cita, recorte coinciden con el inventario. |
| `parcial` | Archivo y hash coinciden, pero el inventario no registra el número de páginas. |
| `incompatible` | Hay un error de referencia: archivo, recorte, hash o página. |
| `invalida` | La evidencia tiene errores de forma. |

`inventario_desde(expediente, revisiones, recortes)` construye el inventario a partir de los `expediente.json`, `revision.json` y `recorte.json` ya cargados. Resume lo que esos módulos registraron y no vuelve a calcular hashes de archivos: comprobar que los originales siguen intactos corresponde a la revisión documental. Con inventario se detectan:

- caso distinto;
- archivo inexistente o hash del original distinto;
- página mayor que la inventariada;
- recorte inexistente, o recorte cuyo archivo, página, hash original o hash de imagen no coinciden;
- alcance distinto del declarado en el expediente.

Una región que sobresale del recorte citado genera una advertencia, no un error: el recorte se reconstruye con matrices y redondeo, y no se fija una tolerancia arbitraria.

## Revisión y correcciones

`corregir(data, candidato_id, estado=..., motivo=..., fecha=..., revisor_declarado=..., valor_revisado=..., unidad_revisada=...)` devuelve una **copia** con una nueva entrada en `revision.historial`. La entrada original y `valor_propuesto` no cambian.

- Los estados posibles son `pendiente`, `revisado` y `rechazado`. Se puede volver a `pendiente` para reabrir un candidato.
- Toda entrada exige `motivo`, `fecha` (AAAA-MM-DD, sin retroceder respecto de la anterior) y `revisor_declarado`.
- `revisado` exige `valor_revisado` y `unidad_revisada` explícitos, aunque repitan lo propuesto, y no admite valor `null`: lo ilegible se deja pendiente o se rechaza. Sí admite unidad `desconocida`.
- `rechazado` y `pendiente` no llevan valor ni unidad.
- `revision.estado` debe coincidir con la última entrada del historial.

`revisor_declarado` es una declaración: el módulo no verifica identidad, firma ni competencia.

## Exportación

`exportar_revisados(data, inventario=None)` rechaza registros inconsistentes y produce un `draft2model.extraccion_revisada` con:

- `caso`, `procedencia`, `alcance` y `sistema_coordenadas` copiados sin cambios;
- `huella_extraccion`: SHA256 del registro exportado;
- solo los candidatos `revisado`, con valor y unidad propuestos y revisados, la marca `corregido`, el método, el historial y la evidencia con su `estado_referencia`;
- `excluidos.pendientes` y `excluidos.rechazados`, con sus identificadores;
- `aprobacion_ingenieria: null` y un aviso: **revisar un candidato no equivale a aprobar ingeniería.**

Si no se aporta inventario, la exportación indica `inventario_aportado: false` y cada evidencia mantiene `referencia_no_comprobada`.

## Datos sintéticos y casos fuera del MVP

- `procedencia.tipo: sintetico` genera una advertencia y se conserva en la exportación.
- `alcance.estado: fuera_mvp_declarado` genera la advertencia `fuera_mvp` y se exporta sin cambios. Con inventario, un alcance distinto del expediente es un error, para que la marca provisional no se pierda.

El ejemplo usa hashes calculados sobre textos de prueba, no sobre archivos. No contiene planos ni datos privados.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Cubren: caso válido; valores y unidades desconocidos; referencias no comprobadas, comprobadas, parciales y rotas; páginas inválidas; bbox mal formadas, con NaN o con booleanos; identificadores duplicados; correcciones con historial; exclusión de pendientes y rechazados; inmutabilidad de la entrada; conservación del alcance y la procedencia. No acreditan precisión de extracción ni validación estructural.

## Pendientes

- Integrar con la interfaz de línea de comandos y con la persistencia en `data/private/<caso>/`; corresponde a otra sesión.
- Definir cómo se generan candidatos desde OCR o visión y cómo se mide su precisión y cobertura frente a una referencia anotada.
- Definir la transformación, con revisión humana, de candidatos revisados a niveles, nodos y muros del contrato de geometría, incluida la escala y la referencia geométrica.
- Admitir evidencias sobre imágenes raster cuando los recortes las soporten.
- Definir la interfaz de revisión y el registro de identidad de quien revisa.
