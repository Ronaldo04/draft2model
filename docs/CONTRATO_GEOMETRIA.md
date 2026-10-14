# Contrato de geometría v0.1: propuesta inicial

Estado: **propuesta inicial**, 13 de octubre de 2026. No es una especificación de ingeniería aprobada. Debe revisarse con el primer caso piloto y con los requisitos del adaptador ETABS antes de fijarse.

Implementación: [`draft2model/contratos.py`](../draft2model/contratos.py) y [`draft2model/validacion_geometria.py`](../draft2model/validacion_geometria.py). Ejemplo sintético: [`examples/geometria_sintetica.json`](../examples/geometria_sintetica.json). Pruebas: [`tests/test_validacion_geometria.py`](../tests/test_validacion_geometria.py).

El contrato corresponde a la parte geométrica de `estructura_validada.json` prevista en el [contexto del proyecto](CONTEXTO_PROYECTO.md). No incluye materiales, cargas, sitio, diafragmas, aberturas ni elementos de confinamiento.

## Estructura

```json
{
  "contrato": "draft2model.geometria",
  "version_contrato": "0.1.0",
  "id": "sintetico-001",
  "unidad_longitud": "m",
  "procedencia": {"tipo": "sintetico", "descripcion": "..."},
  "niveles": [{"id": "N0", "cota": 0.0}, {"id": "N1", "cota": 2.6}],
  "nodos": [{"id": "A", "x": 0.0, "y": 0.0}, {"id": "B", "x": 4.0, "y": 0.0}],
  "muros": [{"id": "M1", "nodo_inicio": "A", "nodo_fin": "B",
             "nivel_inferior": "N0", "nivel_superior": "N1", "espesor": 0.15}],
  "faltantes": [],
  "revision": {"estado": "borrador", "aprobacion": null}
}
```

| Campo | Contenido | Reglas |
| --- | --- | --- |
| `contrato`, `version_contrato` | Identificador `draft2model.geometria` y versión `0.1.0`. | Coincidencia exacta; otra versión se rechaza. |
| `id` | Identificador del caso. | 1–64 caracteres: letras, números, `.`, `_`, `-`. |
| `unidad_longitud` | Unidad única de todas las longitudes. | Solo `m`, `cm` o `mm`, escritos exactamente así. |
| `procedencia` | `tipo`, `descripcion` y opcionalmente `expediente_id`, `lamina`, `referencias`, `justificacion`. | `tipo`: `sintetico`, `plano`, `levantamiento`, `supuesto`. Un `supuesto` exige `justificacion`. |
| `niveles[]` | `id`, `cota`; opcionales `nombre`, `procedencia`. | `cota` puede ser cero o negativa; admite `null` como faltante. |
| `nodos[]` | `id`, `x`, `y` en planta; opcional `procedencia`. | Coordenadas obligatorias y finitas; no admiten `null`. |
| `muros[]` | `id`, `nodo_inicio`, `nodo_fin`, `nivel_inferior`, `nivel_superior`, `espesor`; opcionales `procedencia`, `observaciones`. | Referencias existentes, extremos distintos, longitud no nula, cota superior mayor que inferior, `espesor` positivo o `null` como faltante. |
| `faltantes[]` | `descripcion`; opcionalmente `coleccion`, `id` y `campo` juntos. | Todo `null` debe declararse; un faltante no puede apuntar a un campo con valor. |
| `revision` | `estado` y `aprobacion` (`null` u objeto). | `estado`: `borrador`, `en_revision`, `observado`, `aprobado`. |
| `revision.aprobacion` | `declarada_por`, `fecha` (AAAA-MM-DD), `huella_contenido`; opcionales `alcance`, `observaciones`. | Solo con estado `aprobado`; el estado `aprobado` la exige. |

Los identificadores son únicos dentro de cada colección. Los campos no definidos se rechazan para detectar errores de escritura como `espesr`.

## Decisiones de la propuesta

1. **Nodos en planta y niveles con cota.** Los muros se definen por dos nodos en planta y dos niveles. La altura se deriva de las cotas, de modo que una misma planta repetida en varios niveles no duplica coordenadas. Los muros de altura parcial, parapetos y aberturas quedan fuera de v0.1.
2. **Unidad única y explícita.** Todas las longitudes del archivo usan `unidad_longitud`. No hay unidad por defecto ni unidades mixtas. La salida normalizada a metros se entrega en `geometria_m`; la entrada original no se modifica.
3. **Conversión exacta.** La normalización divide por 1, 100 o 1000 en lugar de multiplicar por 0.01 o 0.001. Con una sola operación redondeada, `260` cm, `2600` mm y `2.6` m producen el mismo valor en metros.
4. **Ausente, nulo y cero son distintos.** Una clave ausente es un error de contrato (`campo_ausente`). Un `null` representa un dato desconocido y solo se admite en campos anulables (`niveles.cota`, `muros.espesor`) cuando se declara en `faltantes`. Un cero o negativo en `espesor` es un error (`no_positivo`), nunca un faltante.
5. **Sin tolerancias.** Longitud nula significa coordenadas exactamente iguales; altura no positiva significa cota superior menor o igual que la inferior. No se aplican umbrales normativos, longitudes mínimas ni espesores mínimos.
6. **Procedencia trazable.** El contrato completo y cada elemento pueden indicar su origen. Un contrato sintético no puede contener elementos con otra procedencia, ni viceversa, para que los datos de prueba sigan claramente identificados.
7. **Consistencia separada de aprobación.** El validador informa `consistente` y, por separado, `disponible_para_modelado`. Ningún estado se cambia automáticamente.
8. **Aprobación ligada al contenido.** La aprobación registra `huella_contenido`, un SHA256 del JSON canónico sin el bloque `revision` (función `huella_contenido`). Si la geometría, procedencia o faltantes cambian después, la huella deja de coincidir y la aprobación no habilita el modelado.

## Resultado de la validación

`validar_geometria(data)` y `validar_archivo(ruta)` devuelven un `ResultadoValidacion`; `a_dict()` lo serializa.

| Campo | Significado |
| --- | --- |
| `consistente` | Sin errores de estructura, tipos, referencias o geometría básica. |
| `disponible_para_modelado` | Consistente, sin faltantes, estado `aprobado` y huella vigente. |
| `errores`, `advertencias` | Lista de `{ruta, codigo, mensaje}`; la ruta indica el campo, por ejemplo `$.muros[2].espesor`. |
| `faltantes` | Declarados (`origen: declarado`) y alturas no determinables por cotas faltantes (`origen: derivado`). |
| `bloqueos` | Motivos por los que no está disponible para modelado. |
| `datos_sinteticos` | `true` cuando la procedencia es sintética. |
| `geometria_m`, `derivados_m` | Copia normalizada a metros y longitud/altura derivadas de cada muro; solo si es consistente. |
| `huella_contenido` | Huella actual, que una aprobación debería declarar. |

Advertencias actuales: datos sintéticos, nodos sin uso, nodos con coordenadas coincidentes y muros repetidos. No impiden la consistencia.

`cargar_geometria` rechaza claves JSON repetidas y los literales `NaN`/`Infinity`, que el módulo `json` de Python aceptaría por defecto.

## Lo que la aprobación no significa

Una aprobación registrada es un **dato de entrada**. El validador comprueba su forma y su correspondencia con el contenido; no verifica la identidad, firma ni competencia de quien la declara. `disponible_para_modelado: true` con datos sintéticos solo sirve para probar software. Un contrato consistente no es una validación estructural, y ninguna salida de este módulo certifica la seguridad de una vivienda.

## Uso

```python
from pathlib import Path
from draft2model.validacion_geometria import validar_archivo

resultado = validar_archivo(Path("examples/geometria_sintetica.json"))
print(resultado.consistente, resultado.disponible_para_modelado, resultado.bloqueos)
```

El ejemplo es consistente y no está disponible: el espesor de `M4` está declarado como faltante y la revisión está en `borrador`.

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

## Pendientes antes de fijar el contrato

- Contrastar campos y supuestos con el primer caso piloto real y con la referencia manual.
- Definir con el adaptador ETABS cómo se traducen niveles, nodos, muros y espesores a objetos, secciones y unidades del modelo.
- Decidir la representación de aberturas, muros de altura parcial, elementos de confinamiento, losas y materiales.
- Definir cómo se generan y registran las aprobaciones: interfaz de revisión, persistencia y versión.
- Decidir si se agrega un comando de validación a la interfaz de línea de comandos.
- Revisar si se necesitan comprobaciones de topología (muros cruzados o superpuestos) y, de ser así, con qué criterio aprobado.
