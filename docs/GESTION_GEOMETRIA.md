# Versiones geométricas en el expediente

Estado: **primera implementación local v0.1**, 15 de octubre de 2026. Conserva geometrías del [contrato v0.1](CONTRATO_GEOMETRIA.md) como versiones inmutables dentro de cada expediente privado. Registra revisiones y aprobaciones explícitas y detecta evidencia o versiones alteradas.

Esta funcionalidad **no**:

- convierte lecturas ni candidatos de extracción en geometría;
- genera planes, modelos ni resultados;
- ejecuta ETABS;
- certifica seguridad estructural.

Implementación: [`draft2model/gestion_geometria.py`](../draft2model/gestion_geometria.py). Pruebas: [`tests/test_gestion_geometria.py`](../tests/test_gestion_geometria.py). Todavía no hay comando de línea; Codex hará la integración.

## API

Todas las funciones reciben una raíz privada (`raiz`; en uso normal, `data/private`) y el identificador del caso. Las operaciones que escriben devuelven `ResultadoGeometria(caso, identificador, ruta, comprobacion, metadatos)`.

```python
from pathlib import Path
from draft2model import gestion_geometria as g

raiz = Path("data/private")

imp = g.importar_geometria(raiz, "sintetico-001", Path("geometria.json"))
comp = g.comprobar_version(raiz, "sintetico-001", imp.identificador)       # no escribe
consulta = g.consultar_version(raiz, "sintetico-001", imp.identificador)   # geometría, metadatos y comprobación

rev = g.revisar_geometria(raiz, "sintetico-001", imp.identificador, geometria_propuesta,
                          motivo="Se completa el espesor de M4.", fecha="2026-10-15",
                          revisor_declarado="Nombre declarado")

ap = g.aprobar_geometria(raiz, "sintetico-001", rev.identificador,
                         huella_esperada=rev.comprobacion.huella_contenido,
                         revisor_declarado="Nombre declarado", fecha="2026-10-15",
                         motivo="Geometría revisada frente a las láminas.",
                         alcance_revision="Niveles, nodos y muros.")
```

| Función | Qué hace |
| --- | --- |
| `importar_geometria(raiz, caso, entrada)` | Lee el JSON de forma estricta y guarda una versión raíz. Admite faltantes declarados. Rechaza geometría inconsistente, de otro caso o con una aprobación declarada. |
| `comprobar_version(raiz, caso, version_id)` | Devuelve `ComprobacionGeometria`. Comprueba la versión, toda su cadena de padres, el expediente y sus originales. |
| `consultar_version(raiz, caso, version_id)` | Devuelve `ConsultaGeometria`, con copias independientes de la geometría y los metadatos más su comprobación. |
| `revisar_geometria(raiz, caso, padre_id, geometria_propuesta, *, motivo, fecha, revisor_declarado)` | Guarda la geometría completa propuesta como hija del padre. Exige estado `borrador` y aprobación `null`. |
| `aprobar_geometria(raiz, caso, version_id, *, huella_esperada, revisor_declarado, fecha, motivo, alcance_revision)` | Registra una aprobación explícita como versión hija. |

`ComprobacionGeometria` reúne:

- `correcta` y `problemas`;
- `expediente_sha256` y `originales_verificados` (id y SHA256 recalculado);
- `sha256_geometria` y `huella_contenido`;
- `cadena`: la versión y sus padres, en ese orden;
- `validacion`: el resumen de `validar_geometria`.

`a_dict()` es serializable con JSON estricto.

**Errores** (los mismos tipos que en la [gestión de extracciones](CLI_EXTRACCION.md)):

- `ErrorGestion`: solicitud inválida, como un caso o identificador inválido o inexistente, una carpeta enlazada, un JSON ilegible, repetido o con `NaN`/`Infinity`, o un motivo, fecha o revisor que falta.
- `ErrorEvidencia`, subclase de la anterior: geometría o evidencia rechazada, con su lista de `problemas`.

En ningún caso de rechazo se guarda una versión.

## Estructura persistida

```
<raiz>/<caso>/geometrias/<uuid>/
  geometria.json            contrato draft2model.geometria, sin campos añadidos
  version.json              metadatos de la versión
  fuente_importada.json     solo en importaciones: bytes exactos recibidos
```

`version.json` (`tipo: draft2model.version_geometria`, `version_registro: 0.1.0`) contiene:

| Campo | Contenido |
| --- | --- |
| `id`, `caso`, `operacion`, `creado_utc` | Operación: `importacion`, `revision` o `aprobacion`. |
| `padre` | `null` en importaciones; `{id, sha256_geometria, huella_contenido}` del padre en revisiones y aprobaciones. |
| `sha256_geometria` | SHA256 de los bytes de `geometria.json`. |
| `huella_contenido` | `huella_contenido()` del contrato, que excluye `revision`. |
| `contrato_geometria` | Contrato y versión de origen. |
| `expediente_sha256`, `originales_verificados` | Huella del expediente y SHA256 recalculado de cada original, en el momento de escribir. |
| `alcance` | Copia exacta del `alcance` del expediente, incluido `fuera_mvp_declarado`. |
| `procedencia`, `datos_sinteticos` | Procedencia de la geometría y marca sintética según el validador. |
| `validacion`, `estado_revision_geometria` | Resumen del validador al guardar y estado de revisión de la geometría. |
| `fuente` | Solo en importaciones: `{nombre, archivo, sha256}` de la fuente. |
| `revision` | Solo en revisiones: `{motivo, fecha, revisor_declarado, identidad_revisor}`. |
| `aprobacion` | Solo en aprobaciones: huellas, revisor, fecha, motivo, `alcance_revision`, `identidad_revisor` y `certifica_seguridad_estructural: false`, `aprueba_artefactos_derivados: false`. |
| `identidad_revisor`, `aviso` | `declarada_no_verificada` y el alcance de la versión. |

## Reglas

1. **Reutilización:** se usan `validar_geometria()` y `huella_contenido()` sin cambios. La entrada se lee con el lector estricto por bytes de la gestión de extracciones, que rechaza claves repetidas y `NaN`/`Infinity` como `cargar_geometria`. Así la geometría registrada procede exactamente de los bytes conservados.
2. **Importación:** se admite geometría consistente, también con faltantes declarados. Se rechazan:
   - las entradas inconsistentes;
   - las de otro caso;
   - las que declaran `revision.estado: aprobado` o una aprobación no nula. Una aprobación importada no autoriza nada: debe usarse `aprobar_geometria`, y esos campos no se borran ni se reescriben.
3. **Revisión:**
   - recibe la geometría completa y la versión padre, que debe superar la comprobación;
   - exige motivo, fecha ISO y revisor declarado;
   - la propuesta debe estar en `borrador` con aprobación `null`, así que nunca hereda la aprobación del padre;
   - no puede cambiar la marca sintética: no se convierten datos sintéticos en reales ni al revés;
   - cada revisión crea una hija y el padre queda intacto. Dos hijas del mismo padre son ramas y no se fusionan.
4. **Aprobación:**
   - solo sobre una versión que supere la comprobación, consistente y **sin faltantes**, con expediente y originales vigentes;
   - `huella_esperada` debe coincidir con la huella actual del contenido; si no, se rechaza;
   - el registro del contrato se construye con esa huella (`declarada_por`, `fecha`, `huella_contenido`, `alcance`, `observaciones`), se vuelve a validar (`disponible_para_modelado`) y se guarda como hija;
   - el contenido geométrico no cambia, y no se aprueba una versión que ya contiene una aprobación.
5. **Comprobación**, antes de escribir y al consultar:
   - identificadores y rutas;
   - carpetas de versión no enlazadas;
   - huella y estructura de `expediente.json` y SHA256 **recalculado** de todos sus originales;
   - SHA256 de `geometria.json`, validación y huella del contenido;
   - coherencia de los metadatos, del alcance y de la marca sintética;
   - reglas de la operación;
   - fuente importada (SHA256 de los bytes exactos y correspondencia de su JSON con `geometria.json`);
   - cada padre de la cadena, completo y por SHA256.

   La sola existencia de los archivos no cuenta como prueba de integridad.
6. **Escritura atómica:** se reutiliza la publicación de la gestión de extracciones. Se escribe en un temporal `.tmp-*` dentro de `geometrias/` y se publica con un único `rename`, sin sobrescribir. Si `geometrias/` es un symlink o una junction, se rechaza antes de crear nada. Ante un fallo de escritura normal no queda una versión parcial visible.

## Identidad, alcance y artefactos derivados

- `revisor_declarado` es una declaración: la identidad y la competencia del revisor **no se autentican**.
- Una aprobación registrada no certifica seguridad estructural y **no aprueba** el plan geométrico ni ningún otro artefacto derivado.
- Todo plan, modelo o resultado derivado debe citar la versión (`id`) y la huella (`huella_contenido`, y preferiblemente `sha256_geometria`) exactas de la geometría de origen.
- Cambiar la geometría crea una versión nueva y **no** actualiza ni valida automáticamente resultados anteriores: esos resultados siguen ligados a la versión de la que proceden.
- Un caso `fuera_mvp_declarado` conserva esa marca en cada versión. No se infiere compatibilidad con el MVP.

Las huellas detectan cambios accidentales o parciales y ediciones que no rehacen todas las huellas. **No protegen contra una edición deliberada** que reescriba de forma coherente todos los archivos y huellas, incluida la del expediente.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_gestion_geometria -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Las 23 pruebas usan PDF y geometrías sintéticas en carpetas temporales. Cubren:

- importación, consulta, revisión y aprobación;
- conservación exacta de versiones anteriores;
- faltantes admitidos al guardar y bloqueados al aprobar;
- rechazo de aprobaciones importadas;
- aprobación ligada a la huella esperada;
- revisión posterior sin aprobación heredada y ramas;
- expediente, original, fuente, geometría, metadatos, padre y aprobación alterados, incluso con hashes rehechos;
- rutas e identificadores inválidos;
- carpeta `geometrias` enlazada mediante junction o symlink (la prueba se omite si el sistema no permite ninguno);
- JSON repetido o no finito, incluidos `1e999` y enteros enormes;
- fallos de escritura sin versión parcial;
- conservación de procedencia, datos sintéticos y alcance.

## Limitaciones y cambios compartidos propuestos

- **Uso de funciones privadas:** se reutilizan funciones privadas de `gestion_extraccion.py` (`_publicar`, `_carpeta_propia`, `_misma_ruta`, `_archivo_del_caso` y `_entradas_expediente`). Se propone moverlas a un módulo compartido público, por ejemplo `almacen_privado.py`, para que un cambio en extracciones no afecte silenciosamente a la geometría. No se hizo porque esos archivos están fuera del alcance de esta tarea.
- **Integración:** falta un comando de línea con códigos de retorno, por ejemplo 1 para `ErrorGestion` y 2 para `ErrorEvidencia`, como en extracciones.
- **Concurrencia:** no hay bloqueo entre procesos, de modo que dos operaciones simultáneas sobre el mismo padre crean ramas. Tampoco hay orden para listar versiones; se consulta la carpeta `geometrias/`.
- **Coste:** la comprobación recalcula el SHA256 de todos los originales en cada operación, lo que con expedientes muy grandes puede tardar.
- **Enlaces:** un proceso que sustituya una carpeta por un enlace entre la comprobación y el `rename` no se detecta.
