# Integración de la malla triangulada en el recorrido ETABS (configuración y plan 0.4)

Estado al 20 de octubre de 2026 (encargo 184).

**Módulos:**
- [`draft2model/malla_preparacion.py`](../draft2model/malla_preparacion.py) (nuevo);
- [`modelo_estructural.py`](../draft2model/modelo_estructural.py), [`operaciones_etabs.py`](../draft2model/operaciones_etabs.py), [`triangulacion_particiones.py`](../draft2model/triangulacion_particiones.py);
- [`ejecutor_etabs.py`](../draft2model/ejecutor_etabs.py), [`ejecucion_modelo.py`](../draft2model/ejecucion_modelo.py), [`revision_modelo.py`](../draft2model/revision_modelo.py);
- [`gestion_configuracion.py`](../draft2model/gestion_configuracion.py), [`revision_configuracion.py`](../draft2model/revision_configuracion.py);
- [`scripts/ejecutar_plan_etabs.ps1`](../scripts/ejecutar_plan_etabs.ps1).

**Pruebas:** [`tests/test_integracion_malla.py`](../tests/test_integracion_malla.py).

## Recorrido

1. Geometría 0.3 aprobada.
2. Configuración 0.4, importada en borrador.
3. Preparación de malla, reproducible y expuesta: nodos derivados, triángulos, subdivisiones y faltantes.
4. Política explícita de nodos y frames.
5. Revisión y aprobación propias.
6. Plan 0.4.
7. Ejecutor verificado: regenera el plan, aplica guardas, ejecuta la relectura y guarda.
8. Registro del modelo construido.

**Malla:**
- **Partición** (módulo 180) de **todos** los hosts asignados, con **todos** sus huecos.
- **Compatibilidad** (módulo 182), solo en bordes declarados en `conexiones_borde`.
- **Triangulación** (`triangulacion_particiones.triangular_compatibilidad`): recorte de orejas exacto sobre la cadena completa de cada celda. Conserva **todos** los nodos colineales de borde; no hay abanico que los omita.
- **Cortes Z explícitos** (adenda 186, `cortes_superficies.cortar_malla_por_niveles` de Codex, API intacta): se aplican a toda la malla después de la triangulación y **antes** de nombres CSI y políticas. Conservan ambos lados (la pieza seca es material estructural y no se elimina), comparten los nodos de corte por aristas y **no crean Storys**.

**Qué no hace:**
- No crea el host completo ni aberturas `Opening`, y no pone material sobre huecos.
- No une por proximidad.
- No infiere material, malla, apoyos ni diafragmas.

**Alcance:** la habilitación operativa (`apto_para_adaptador`, plan `ejecutable: true`) significa datos completos y sin faltantes. **No aprueba ingeniería** (`aprueba_ingenieria: false`) y no sustituye el ensayo nativo en ETABS.

## Configuración 0.4 (`draft2model.modelo_estructural`, `version_contrato: "0.4.0"`)

Lleva las claves de 0.3 más estas:

| Clave | Contenido |
|---|---|
| `conexiones_borde` | Documento `draft2model.conexiones_borde` 0.1.0 embebido (ver [COMPATIBILIDAD_PARTICIONES.md](COMPATIBILIDAD_PARTICIONES.md)). Va ligado al SHA canónico y a la huella de la geometría aprobada; su `huella_conexiones` es la declarada. `conexiones: []` declara que no hay uniones. |
| `malla` | `{"estrategia": "particion_franjas_triangulada_v1", "fuente": <fuente>}` |
| `cortes_nivel` | `[{"z_m": <número>, "fuente": <fuente>, "motivo": <texto>}]`: niveles de corte declarados y revisados (por ejemplo, un nivel libre de líquido). `[]` significa sin corte. No se infieren ni son pisos. |
| `nodos_derivados` | `[{"nodo": "MN_<host>_<k>"\|"MC_<k>", "xyz_m": [x, y, z], "restricciones": [6 bool], "diafragma": <id>\|null, "motivo_sin_diafragma": <texto>\|null, "fuente": <fuente>}]`. Exactamente uno de `diafragma` o `motivo_sin_diafragma`. Con `restricciones` todas falsas el nodo es libre; con alguna verdadera, es un apoyo. |
| `subdivision_frames` | `[{"frame": <id>, "nodos": [inicio, ..., fin], "fuente": <fuente>}]`, igual a la subdivisión reproducida. |

**Reglas:**
- **`asignaciones_muros`** debe ser `[]`, y la geometría no puede tener muros 0.1: los muros son superficies verticales con `shell_muro`.
- **Cargas:** objetivos `punto`, `frame` y `superficie`.
- **Posición ligada:** `xyz_m` debe ser igual a la posición reproducida. Si un cambio de geometría o de corte reutiliza un nombre en otra posición, la política no se hereda: es un error.
- **Política no declarada:** cada nodo derivado o frame atravesado que falta da un faltante calculado (`$.nodos_derivados.<n>`, `$.subdivision_frames.<f>`). El borrador se puede importar; la aprobación queda bloqueada.
- **Se rechazan como errores:**
  - un nodo ajeno, una subdivisión distinta o de un frame sin nodos interiores;
  - un conflicto entre diafragma y motivo, o la ausencia de ambos;
  - restricciones incompletas o una fuente inexistente;
  - un diafragma fuera de la cota de sus puntos;
  - una estrategia distinta, o muros 0.1.
- **Aptitud (`comprobar_configuracion`):**
  - consistente, sin faltantes y aprobada;
  - geometría comprobada y aprobada por huella;
  - preparación reproducida;
  - único bloqueo restante, el informativo de la geometría 0.3.
- **Salida de `a_dict()`:** añade `version_contrato`, `geometria_aprobada_por_huella` y `preparacion_malla` (huellas y recuentos). Las salidas 0.1 a 0.3 no cambian.
- **Contratos previos:** 0.1 a 0.3 conservan su semántica. 0.2 y 0.3 siguen siendo de desarrollo (plan no ejecutable). El único cambio en la base es que 0.4 no añade un bloqueo propio.

## Nombres CSI (deterministas y sin colisiones)

| Objeto | Nombre |
|---|---|
| Nodo que es vértice fuente | Su punto de configuración (`vertice_geometria` o `vertices_compartidos`). Debe ser único, con coordenadas idénticas. |
| Nodo derivado | `MN_<host>_<k>`, desde `<host>#n<k>`. El representante de compatibilidad es el ID menor, y un nodo de borde compartido lleva **un solo** nombre. |
| Nodo de corte | `MC_<k>`, desde `CORTE#<k>` (compartido entre hosts por arista) |
| Triángulo | `MA_<host>_<celda>_<t>`, y `..._K<n>` si procede de un corte |
| Subframe | `<frame>_S<k>`, en orden de inicio a fin |

**Rechazos:**
- una colisión con IDs de la configuración o entre clases;
- un nodo derivado que coincide con un punto de la configuración (no se fusiona por proximidad);
- nodos de malla sobre un frame más cercanos que el criterio.

## Preparación

**API:**

```python
from draft2model.malla_preparacion import preparar_malla
prep = preparar_malla(geometria_0_3, configuracion_0_4)
```

Es pura y determinista. Devuelve `draft2model.preparacion_malla` 0.1.0 con estos campos:
- `origen`: huellas de geometría, conexiones, compatibilidad, triangulación y particiones;
- `hosts`: sección, normal, área neta, huecos y triángulos;
- `nodos`: `csi`, `xyz_m`, tipo, trazas y alias;
- `triangulos`: `csi`, `id_malla`, host, celda, sección, nodos, `area_m2` (respecto a la normal del host) y `centroide_m`;
- `nodos_derivados` y `plantilla_nodos_derivados` (con `xyz_m`);
- `cortes_nivel`: niveles, declaraciones con su fuente, `nodos_corte`, `no_crea_pisos` y `conserva_ambos_lados`. El plan lo copia en `malla.cortes_nivel` y `origen.huella_corte`;
- `frames_subdivision_requerida`, `conexiones`, `bordes_no_conectados` y `huella_preparacion`.

**Gestión** (lee la versión registrada y su geometría):

```powershell
.venv/Scripts/python.exe -m draft2model.gestion_configuracion --raiz data/private --caso <caso> malla --version <id>
```

**Servicio web:** `revision_configuracion.ServicioConfiguracion.malla(caso, version)`. La conexión HTTP y la interfaz corresponden a Codex.

## Plan 0.4 (`draft2model.plan_operaciones_etabs`, `version_contrato: "0.4.0"`)

**Funciones:**
- `generar_plan_malla(raiz, config, **opciones)`;
- `generar_plan_por_version`: 0.1 da un plan 0.1, 0.4 da un plan 0.4, y 0.2/0.3 se rechazan;
- `validar_plan_malla` y `validar_plan_por_version`.

**Opciones:** como las de 0.2/0.3: `destino_guardado`, `tipo_shell_losa` y/o `tipo_shell_muro` según las secciones, y `gravedad_programa_m_s2`.

**Construcción:** reutiliza el compilador común con una configuración expandida interna.
- Puntos más nodos derivados, con las coordenadas de la malla.
- Triángulos `AddByPoint` con 3 nodos y la sección del host. Las propiedades son las nativas (`SetSlab` con la **capa** en aligerados, corrección 181; `SetSlabRibbed`/`Waffle`; `SetWall`). Se fija `SetLocalAxes` por triángulo en aligerados.
- Frames subdivididos que conservan sección, tipo y fuente.
- Cargas:
  - **de área:** la misma intensidad en cada triángulo del host; nunca en huecos;
  - **de frame:** la misma intensidad kN/m en cada subframe;
  - **puntuales:** sin cambios.
- Apoyos y diafragmas ampliados con la política declarada.

**Relecturas, antes de `cFile.Save`:**
- puntos (`GetCoordCartesian`);
- contorno y propiedad de cada triángulo (`GetPoints`, `GetProperty`);
- propiedades (`GetSlab*`, `GetWall`) y ejes (`GetLocalAxes`);
- apoyos (`GetRestraint`);
- cargas por triángulo (`GetLoadUniform`: número de cargas; valores completos cuando hay una sola);
- fuente de masa (`GetMassSource_1`, escalares; patrones y factores registrados);
- extremos de frames (`cFrameObj.GetPoints`).

**Validación por reproducción:**
- El ejecutor (`preparar`), `EjecutorVerificado._revalidar` y `revision_modelo._validar` regeneran el plan desde la configuración y la geometría vigentes, rehaciendo partición, compatibilidad y triangulación, y exigen igualdad canónica.
- `validar_plan_malla` comprueba:
  - las áreas creadas son exactamente los triángulos: sin host completo y sin `SetOpening`/`GetOpening`;
  - cada triángulo tiene sus tres relecturas, cada apoyo su `GetRestraint` y cada frame su relectura de extremos;
  - la fuente de masa se relee una sola vez;
  - las cargas de área solo van a triángulos;
  - el error de conservación es ≤ 1e-9;
  - además, las reglas comunes de firma, tipos, orden, referencias, huella y guardado final.

**Conservación** (sección `conservacion`, calculada sin solver):
- **Área:** la suma de los triángulos es igual al área neta fuente.
- **Fuerza y momento** de cada carga distribuida (`M = (∫r dA) × w`): se comparan con el polígono fuente (exterior menos huecos) o con el frame original.
- **Masa propia:** por material de cada triángulo. El área total es la neta, sin host completo, por lo que no hay duplicación.

**Lo que no se convierte:** no hay presión hidrostática ni variable (`pendientes`).

**Nuevas firmas (`FIRMAS` y lista blanca PS1):**
- `cPointObj.GetRestraint`, `cAreaObj.GetLoadUniform` y `cPropMaterial.GetMassSource_1`: reflejadas en ETABS 21.1.
- `cFrameObj.GetPoints`: tomada de la ayuda CSI. **`--verificar-firmas` debe confirmarla antes de la ejecución real.** Si la firma no coincide, el script falla en la resolución, antes de mutar.

**CLI:**

```powershell
.venv/Scripts/python.exe -m draft2model.operaciones_etabs --raiz data/private --entrada config04.json --salida plan04.json `
  --destino-guardado D:\ruta\nueva\modelo.edb --tipo-shell-losa ShellThin [--tipo-shell-muro ShellThin] --gravedad-programa 9.80665
```

Las configuraciones 0.5 siguen el mismo camino. Para la formulación por sección (R241), `--tipo-shell-losa-json <mapa.json>` sustituye a `--tipo-shell-losa`; ver [MODELADO_SUPERFICIES_ETABS](MODELADO_SUPERFICIES_ETABS.md).

## Ejecución y registro

- `ejecutor_etabs.preparar` usa `validar_plan_por_version` y `generar_plan_por_version`. Acepta 0.1 y 0.4 y rechaza 0.2/0.3.
- `ejecucion_modelo` y `revision_modelo` regeneran por versión.
- **Fallos:** un retorno distinto, un nombre reasignado o una relectura discrepante detienen la ejecución **antes** de `cFile.Save`. Quedan la traza, `revision_integracion_fallida.json` y la marca de motor incierto, y el registro se rechaza.

## Ensayo real reproducible (Codex)

Los dobles no acreditan ETABS. Con ETABS 21 abierto sobre una **copia** de la plantilla, sin otras instancias ni bloqueo previo:

```powershell
$env:TEMP=(Resolve-Path tmp).Path; $env:TMP=$env:TEMP
.venv/Scripts/python.exe -m draft2model.operaciones_etabs --verificar-firmas
.venv/Scripts/python.exe -m draft2model.gestion_configuracion --raiz data/private --caso <caso> malla --version <id>
.venv/Scripts/python.exe -m draft2model.operaciones_etabs --raiz data/private --entrada <config04_aprobada.json> --salida <plan04.json> --destino-guardado <nuevo.edb> --tipo-shell-losa ShellThin --gravedad-programa <g_programa>
.venv/Scripts/python.exe -m draft2model.ejecucion_modelo --raiz data/private --configuracion <config04_aprobada.json> --plan <plan04.json> --copia <copia.edb> --bloqueo tmp/d2/motor.lock
# solo tras revisar la preparación: añadir --ejecutar para mutar la copia y guardar
```

**Verificación posterior:** reabrir el EDB guardado y releerlo con el lector de verificación (de Codex). Hay que comprobar:
- área neta y ausencia de material en huecos;
- nodos compartidos y frames conformes;
- cargas por triángulo y fuente de masa.

## Pruebas

```powershell
$env:TEMP=(Resolve-Path tmp/claude_integracion_184).Path; $env:TMP=$env:TEMP
.venv/Scripts/python.exe -m unittest -v tests.test_integracion_malla
```

**Gestión real en disco** (geometría 0.3 importada y aprobada; configuración importada, revisada y aprobada):
- casos horizontal con dos huecos, vertical (muro con puerta), inclinado, y dos hosts conectados (piso y muro con huecos, más una viga en el borde compartido);
- faltantes de política expuestos y cobertura total de hosts y huecos;
- ningún triángulo sobre huecos, normales conservadas y un nombre único por nodo compartido;
- subdivisión conforme con su carga;
- conservación de fuerza y momento;
- 13 políticas ausentes, en conflicto o con posición distinta;
- cortes Z en un muro con puerta y en dos hosts conectados: ningún triángulo atraviesa el nivel, los nodos de corte están compartidos, se conservan ambos lados y el área neta, se exige política para los nodos `MC_`, no se crean pisos, y se rechazan declaraciones de corte inválidas o un corte movido;
- aligerado: `Thickness` igual a la capa, tipo nervado y ejes por triángulo;
- un cambio de geometría en disco invalida la configuración y el plan;
- planes manipulados o de desarrollo rechazados;
- contratos previos intactos.

**Doble PowerShell** (script real con `ETABSv1` falso con estado; **no** es ETABS):
- el recorrido normal guarda y registra (dos hosts, viga conforme y corte Z);
- una discrepancia en apoyo, carga o coordenada, un fallo parcial o un nombre reasignado impiden `Save` y el registro;
- un plan no regenerable no se prepara.

## Pendientes

- **Ensayo nativo** de transporte, guardado, reapertura y relectura (Codex).
- **Calidad de malla y rigidez**, sin evaluar.
- **Diafragma de nodos derivados:** no tiene getter en la lista blanca.
- **Interfaz y HTTP** de la preparación.
- **Tablas de presión variable o hidrostática** (`cargas_liquidos_etabs`): siguen siendo de Codex. 186 queda como evidencia positiva y 185 como negativa (restricción de signo sin corte). Los cortes se exponen para conectar después; aquí solo se copian cargas uniformes.
- **Módulos de otros responsables:** `revision_ejecucion.py` y `gestion_planes.py` siguen llamando a `generar_plan` (0.1) y no generan planes 0.4.
