# Configuración estructural explícita y parametrizable

Estado: contrato local `draft2model.modelo_estructural` v0.1.0, 16 de octubre de 2026. Implementación: `draft2model/modelo_estructural.py`. Ejemplo: `examples/modelo_estructural_sintetico.json`. Pruebas: `tests/test_modelo_estructural.py`.

Esta infraestructura registra y valida una configuración estructural propuesta para un adaptador ETABS por plantilla revisada. No limita la cantidad de niveles a dos ni restringe la tipología a la del MVP inicial. Permite representar explícitamente los planos de referencia actuales conservando su alcance; no demuestra generalización a otras tipologías. Los parámetros de obras reales, la elección de representación y su benchmark deben revisarse posteriormente por los responsables de ingeniería.

El módulo no ejecuta ETABS, no calcula estabilidad o resistencia, no calibra una representación ni atribuye al shell isotrópico equivalencia con albañilería o sus elementos de confinamiento. `ejecutable_en_etabs` es siempre **false** en su resultado: el adaptador y la ejecución deben comprobar sus propias condiciones adicionales.

## API y estados

```python
from pathlib import Path
from draft2model.modelo_estructural import (
    cargar_configuracion, validar_configuracion,
    comprobar_configuracion, huella_configuracion,
)

config = cargar_configuracion(Path("configuracion.json"))
solo_json = validar_configuracion(config)  # Pura, sin acceso a archivos.
con_cobertura = validar_configuracion(config, geometria)  # Pura, cobertura de geometría aportada.
vigente = comprobar_configuracion(Path("data/private"), config)  # Consulta gestión geométrica.
print(vigente.a_dict())
```

Todas devuelven `ResultadoModelo` salvo el lector y la función de huella. No modifican la configuración ni la geometría aportadas. `a_dict()` informa:

| Campo | Significado |
| --- | --- |
| `consistente`, `errores` | Estructura, tipos, unidades y referencias aceptables para el contrato. No expresa aprobación ni estabilidad física. |
| `faltantes` | Declaraciones originales de datos pendientes; bloquean disponibilidad aunque la estructura del JSON sea consistente. |
| `huella_contenido` | Resultado de `huella_configuracion(config)`: SHA256 del JSON canónico completo **excepto `revision`**. |
| `aprobacion_configuracion_vigente` | Declaración de revisión completa ligada a esa huella. No autentica a la persona. |
| `geometria_comprobada` | La comprobación integrada pasó contra geometría, expediente y originales vigentes, sin errores de integración. |
| `apto_para_adaptador` | Configuración consistente, sin faltantes, aprobada mediante declaración vigente, geometría aprobada vigente, hashes exactos y cobertura comprobados. Solo puede ser true mediante `comprobar_configuracion`. |
| `bloqueos` | Razones de indisponibilidad detectadas. |
| `comprobacion_geometria` | Evidencia devuelta por `gestion_geometria`, incluido su alcance y validación donde corresponda a esa API. |
| `ejecutable_en_etabs` | Siempre false: este validador no acredita un adaptador ni ejecuta un análisis. |

La API pura acepta que falte geometría para revisar preliminarmente la forma del JSON. En ese modo no verifica cobertura de muros ni de sus cargas y nunca declara disponibilidad para el adaptador. Aportar geometría a la función pura comprueba contenido y cobertura pero tampoco acredita archivos vigentes. Para disponer de la configuración se debe usar la API integrada.

## Contrato explícito

Todos los campos de cada objeto son exactos: un campo ausente o desconocido es error. Las listas se declaran explícitamente; una lista vacía expresa ausencia de elementos de esa categoría. Debe existir al menos una fuente, hipótesis, caso de análisis y apoyo. Las entidades usan identificadores únicos dentro de su colección.

| Campo raíz | Contenido |
| --- | --- |
| `contrato`, `version_contrato`, `id`, `caso` | Contrato y versión exactos; identificador de configuración y de caso. |
| `datos_sinteticos` | Booleano que debe coincidir con la geometría. Nunca cambia la naturaleza de datos de origen. |
| `unidades` | Exactamente `{longitud: m, fuerza: kN, tiempo: s, temperatura: C}`. No hay unidades implícitas ni conversión automática. |
| `geometria_origen` | `{version_id, sha256_geometria, huella_contenido}`. Cita la versión registrada exacta y sus dos huellas. |
| `plantilla` | `{id, version, sha256, representacion, limitaciones, fuente}`. Identifica explícitamente la representación prevista y sus limitaciones. |
| `fuentes` | `{id, descripcion, referencia, sha256}`. Declaración de fuentes de ingeniería y sus huellas; los textos no se sustituyen por valores supuestos. |
| `hipotesis` | `{id, descripcion, fuente}`. Hipótesis expresas y su origen. |
| `sitio` | `{descripcion, ubicacion, sistema_resistente, parametros, fuente}`; cada parámetro `{id, valor, unidad, fuente}`. Unidades de parámetro: `1`, `m`, `s`, `m/s2`, `kN/m2`. No asigna una norma ni valores sísmicos por ubicación. |
| `materiales` | `{id, tipo, E_kN_m2, poisson, peso_kN_m3, fuente}`; tipo `isotropo_lineal`. E>0, −1<ν<0.5 y peso específico≥0. Son controles constitutivos básicos; no certifican pertinencia de los valores. |
| `secciones` | `{id, tipo, material, dimensiones, fuente}`. `shell_muro` requiere `{espesor_m}`; `frame_rectangular` requiere `{ancho_m, alto_m}`. Dimensiones positivas. |
| `puntos` | `{id, nodo_geometria, nivel_geometria}`. Posición derivable exactamente del nodo en planta y la cota del nivel versionados. No admite dos IDs para el mismo par. |
| `frames` | `{id, inicio, fin, tipo, fuente}`. Extremos distintos y existentes. Tipo `columna` requiere alineación vertical; `viga`, igual cota; `otro` permite inclinados explícitos. |
| `asignaciones_muros`, `asignaciones_frames` | `{objetivo, seccion, fuente}`. Cobertura completa de todos los muros y frames, sin duplicados, con tipo de sección compatible. El espesor shell coincide exactamente con el espesor geométrico en metros. |
| `patrones` | `{id, tipo, multiplicador_peso_propio, fuente}`; tipo `muerta`, `viva`, `sismo` u `otro`, multiplicador≥0. |
| `cargas` | `{id, patron, objetivo_tipo, objetivo, componentes, unidad, sistema, fuente}`. Fuerzas traslacionales globales `[Fx,Fy,Fz]`. Objetivo `punto`→`kN`, `frame`→`kN/m`, `muro`→`kN/m2`; sistema `global`. |
| `masa` | `{metodo, gravedad_m_s2, incluir_masa_propia, factores_patrones, masas_puntos, fuente}`. Método `patrones` con factores `{patron,factor}`≥0 y masas explícitas vacías, o `explicita` con `{punto,masa_kN_s2_m}`≥0 y factores vacíos. Gravedad positiva y declarada. No admite sumar masa propia y factores de patrones con peso propio que dupliquen esa contribución. |
| `apoyos` | `{punto, restricciones, fuente}`. Seis booleanos explícitos `[Ux,Uy,Uz,Rx,Ry,Rz]`, con al menos una restricción. No prueba estabilidad global. |
| `diafragmas` | `{id, tipo, puntos, fuente}`; `rigido` o `semirigido`, puntos coplanares en cota, no asignados más de una vez. |
| `sin_diafragma` | `{punto, motivo, fuente}`. Todo punto debe pertenecer a un diafragma o tener exclusión justificada. No se infieren diafragmas por nivel. |
| `espectros` | `{id, unidad_aceleracion, puntos, fuente}`; unidad `m/s2`, pares `[periodo_s,aceleracion_m_s2]` no negativos, al menos dos, periodos estrictamente crecientes. La tabla es aportada y revisada, no generada desde una norma. |
| `casos` | `{id, tipo, parametros, fuente}`, con parámetros tipados según la tabla siguiente. |
| `combinaciones` | `{id, tipo, casos, fuente}`; tipo `lineal` o `envolvente`; lista no vacía de `{caso,factor}`. No aplica coeficientes normativos predeterminados. |
| `analisis` | `{casos_ejecutar, combinaciones_resultados, fuente}`. Casos existentes, lista no vacía. Incluye dependencias modales y todos los casos usados por las combinaciones seleccionadas. |
| `faltantes` | `{ruta,motivo,fuente}`. Declaraciones preservadas que bloquean disponibilidad. |
| `revision` | `{estado,aprobacion}`. Estado `borrador` con null o `aprobado` con declaración ligada a la huella. |

La cobertura geométrica exige cada esquina de cada muro como punto nodo/nivel, y que cada punto tenga conexión a un muro o frame. Se detectan frames de longitud física nula incluso si sus IDs son diferentes. Estos controles no prueban que las conexiones declaradas reproduzcan correctamente el plano o que el modelo tenga rigidez suficiente.

### Casos de análisis

| Tipo | `parametros` exactos |
| --- | --- |
| `estatico_lineal` | `{patrones: [{patron, factor}, ...]}`, no vacío. |
| `modal_eigen` | `{numero_modos: entero positivo}`; representable como entero de 32 bits para interoperabilidad. |
| `espectro_respuesta` | `{modal, espectro, direccion, factor, amortiguamiento, combinacion_modal}`. Modal debe referenciar un caso `modal_eigen`; dirección `UX/UY/UZ`, factor>0, 0<amortiguamiento<1 y combinación `CQC/SRSS`. |

La plantilla y el adaptador deben demostrar soporte para cada tipo solicitado. Este contrato no incorpora análisis no lineal, P-Delta, historia temporal, resortes, secciones no rectangulares, losas horizontales, liberaciones o offsets, mallado, modificaciones de rigidez ni momentos aplicados. Si el caso requiere alguna de esas capacidades, debe extenderse el contrato y sus comprobaciones antes de declararlo ejecutable; no se sustituye por una aproximación silenciosa. Las cargas de piso pueden distribuirse externamente y declararse en los objetivos admitidos, con su fuente e hipótesis revisadas.

## Faltantes y revisión declarada

Un valor numérico crítico desconocido puede ser `null` si se declara su ruta semántica por ID en `faltantes`. Por ejemplo:

```json
{"ruta":"$.materiales.MAT1.E_kN_m2","motivo":"Ensayo pendiente","fuente":"F1"}
```

Las rutas numéricas usan IDs: `$.secciones.S1.dimensiones.espesor_m`, `$.patrones.D.multiplicador_peso_propio`, `$.masa.gravedad_m_s2`, `$.masa.masas_puntos.P1.masa_kN_s2_m`, `$.casos.MOD.parametros.numero_modos`, etc. Los campos textuales `$.sitio.descripcion/ubicacion/sistema_resistente` también pueden declararse pendientes. Los IDs rotos, unidades inválidas o cobertura incompleta son errores; una declaración de faltante no los convierte en entradas válidas. Toda declaración de faltante bloquea disponibilidad aunque se hayan completado otros valores.

La aprobación de configuración es independiente de la aprobación geométrica:

```python
config["revision"] = {
    "estado": "aprobado",
    "aprobacion": {
        "revisor_declarado": "Nombre declarado",
        "fecha": "2026-10-16",
        "huella_configuracion": huella_configuracion(config),
        "alcance": "Configuración, representación por plantilla, fuentes e hipótesis revisadas.",
        "identidad_revisor": "declarada_no_verificada",
    },
}
```

Esto ilustra el formato; no autoriza que el software apruebe parámetros reales. El revisor debe aportar su declaración después de revisar las entradas concretas. Cambiar materiales, cargas, geometría origen, plantilla, sitio, hipótesis, fuentes, análisis o cualquier otro campo del contenido invalida la huella anterior. La aprobación no elimina faltantes ni errores.

`comprobar_configuracion` consulta `gestion_geometria.consultar_version`, verifica los dos hashes declarados, procedencia sintética, cobertura y estado geométrico aprobado vigente, y rechaza originales o versiones alterados. Conserva la comprobación devuelta, sin interpretar `fuera_mvp_declarado` como incompatibilidad ni como validación de ingeniería.

Las fuentes y la plantilla en este contrato son referencias declaradas con hashes. Este módulo no resuelve rutas de esas fuentes ni comprueba los bytes de la plantilla: el adaptador debe cotejar su artefacto exacto con `plantilla.sha256` antes de ejecutarlo. No hay autenticación de identidad, competencia profesional o naturaleza de los archivos, ni firma externa que proteja contra reescrituras coherentes de todos los archivos y hashes.

## Uso de la CLI y del ejemplo

```powershell
.\.venv\Scripts\python.exe -m draft2model.modelo_estructural --entrada examples/modelo_estructural_sintetico.json
.\.venv\Scripts\python.exe -m draft2model.modelo_estructural --entrada configuracion_vinculada.json --raiz data/private
```

La primera forma valida solo JSON; la segunda comprueba geometría versionada. Código `0`: JSON consistente, que puede seguir bloqueado; `2`: configuración/evidencia inconsistente; `1`: error de lectura/solicitud. Comprobar siempre `apto_para_adaptador` en la salida, y luego las condiciones del adaptador. No se modifica el despachador principal.

El ejemplo contiene **únicamente valores inventados para pruebas de software**, sin obra ni ubicación real, y permanece en borrador. Los IDs y hashes cero de geometría/plantilla/fuente son marcadores explícitos, no huellas acreditadas de archivos reales. Antes de un uso integrado, se deben vincular las referencias y la plantilla exactas; no debe presentarse el ejemplo como una configuración de ingeniería validada.

## Evidencias

Las suites de configuración estructural, gestión geométrica y validación geométrica pasaron **69 pruebas, 1 omitida** por permisos para crear enlaces. Las 10 pruebas nuevas incluyen configuración aprobada contra geometría aprobada vigente, invalidación por cambio de parámetros/hashes/evidencia, bloqueo de geometría borrador, faltantes preservados, carga/unidad/material/sección/apoyo/diafragma/caso inválidos y un modelo sintético de **seis pisos** que llega a `apto_para_adaptador=true` tras registrar y aprobar su geometría y configuración sintéticas.

Se ejercitaron además 1.890 sustituciones de formas JSON (`null`, booleano, lista, objeto, NaN y texto en todas las rutas del ejemplo) verificando que no se produzcan excepciones no controladas y que el resultado siga siendo serializable con `allow_nan=False`.

Comando reproducible para el sandbox Windows:

```powershell
.\.venv\Scripts\python.exe -c "import pathlib,tempfile,unittest; p=pathlib.Path('tmp/pruebas_modelo'); p.mkdir(parents=True,exist_ok=True); tempfile.tempdir=str(p.resolve()); r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromNames(['tests.test_modelo_estructural','tests.test_gestion_geometria','tests.test_validacion_geometria'])); raise SystemExit(not r.wasSuccessful())"
```
