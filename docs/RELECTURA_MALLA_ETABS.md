# Relectura independiente del modelo 0.4 (malla) guardado

Estado al 21 de octubre de 2026 (encargo 196).

**Archivos:**
- Módulo: [`draft2model/verificacion_modelo_guardado.py`](../draft2model/verificacion_modelo_guardado.py). Lector 0.4.0, sin cambio de contrato de lectura; el script `scripts/verificar_modelo_guardado.ps1` no cambió.
- Pruebas: [`tests/test_relectura_malla.py`](../tests/test_relectura_malla.py).

**Qué se conserva de Codex:**
- la admisión del plan 0.4;
- `contorno_orientado_igual`: mismo ciclo y sentido, con otro inicio (ensayo 191);
- `carga_vertical_global`: Dir10/11 con signo invertido, solo en Global (CSI 9398, ensayo 192);
- los bytes crudos de la lectura.

## Qué se compara

1. **Inventario completo del plan**:
   - Los métodos modificadores van a `comprobada` (por categoría) o a `sin_lector`.
   - Los getters del propio plan 0.4 (`GetRestraint`, `GetLoadUniform`, `GetMassSource_1`, `cFrameObj.GetPoints`, `GetPoints`, `GetProperty`, `GetCoordCartesian`, `GetSlab`/`GetWall`) son **lecturas excluidas**, no mutaciones.
   - Una operación `sin_lector` impide `verificacion_global_del_plan`.
   - El plan real 194 (294 operaciones) da 136 comprobadas, 158 lecturas excluidas y 0 sin lector.
2. **Objetos y asignaciones** (lector existente, por nombre exacto):
   - puntos con XYZ;
   - triángulos con contorno orientado y propiedad;
   - frames y subframes con sus extremos y sección;
   - restricciones y diafragma **por nodo**, incluidos los derivados `MN_`/`MC_`;
   - propiedades nativas (capa en aligerados), materiales y ejes;
   - cargas por objeto: con varias cargas bajo la misma clave, no se emparejan por orden y quedan incompletas;
   - fuente de masa, patrones, casos, combinaciones y marcas.
3. **Malla** (nueva categoría `malla`, solo planes 0.4). Los valores se recalculan con las **coordenadas, contornos, extremos y cargas LEÍDOS**:
   - **Área neta por host:** la suma de las áreas de los triángulos leídos, proyectada sobre la normal del host, frente al `area_neta_m2` **fuente** de la geometría. El umbral es el de lectura más `eps_longitud × perímetro` (cota de primer orden del error de coordenadas). Una pieza faltante, extra o que cubre un hueco lo rompe.
   - **Orientación:** cada triángulo con normal positiva respecto del host.
   - **Conformidad:**
     - una arista dirigida aparece una sola vez por host;
     - ningún nodo de la malla queda dentro de una arista leída (nodo colgante).
   - **Nodos compartidos** de cada conexión: los usan triángulos de **≥2 hosts**. Los nombres de malla se resuelven con `nodos_derivados` y sus alias; si no se resuelven, quedan incompletos.
   - **Subframes:**
     - cadena continua del inicio al fin;
     - nodos intermedios sobre el eje y en orden;
     - suma de longitudes igual a la del frame original.
   - **Conservación:**
     - **fuerza** = Σ (carga leída × área o longitud leída), por eje global; **momento** = Σ (centroide leído × fuerza);
     - se compara con la resultante **fuente** del plan (`conservacion`, del polígono exterior menos huecos);
     - antes se aplica `carga_vertical_global`;
     - no se reinterpretan como carga completa las direcciones proyectadas (7 a 9), locales o no uniformes: quedan incompletas.

**Estados:** `discrepancias` > `incompleto` > `verificado`.
- Una lectura con código distinto de 0, un objeto no leído o unidades distintas de kN_m_C (la geometría no se reescala aquí) dan **incompleto**, nunca éxito.
- Si un host no se leyó completo, la ausencia de un nodo compartido no se juzga: queda incompleta.

**Expectativas incoherentes** (`ErrorVerificacion`, el plan no es fuente):
- triángulos de host sin `AddByPoint`;
- cobertura duplicada o parcial;
- subframes con extremos distintos de la subdivisión;
- partes de conservación distintas de las operaciones `$.cargas.<id>@<parte>`;
- una sección `malla` ausente;
- una huella alterada.

**No afirmados** (`controles_no_afirmados`): `masa_propia_por_elemento`, `calidad_y_rigidez_de_malla` y `efecto_estructural_del_diafragma`. Siempre se mantienen `aprueba_modelo: false` y `certifica_seguridad_estructural: false`.

## Uso (Codex)

```python
from draft2model import verificacion_modelo_guardado as v
exp = v.expectativa_desde_plan(plan_04)            # incluye exp["malla"]
r = v.comparar(exp, observado, criterios)          # r["malla"], r["cobertura"]["malla"]
```

Con el puente: `VerificadorModeloGuardado(...).preparar_verificacion(edb, sha, plan_04, criterios=...)` y luego `ejecutar_verificacion(..., confirmar_lectura=True)`. Los criterios son los mismos de antes; no hay magnitudes nuevas.

## Pruebas

```powershell
$env:TEMP=(Resolve-Path tmp/claude_relectura_196).Path; $env:TMP=$env:TEMP
.venv/Scripts/python.exe -m unittest -v tests.test_relectura_malla
```

**Fuentes:**
- un plan 0.4 generado desde configuración y geometría reales en disco (dos hosts conectados, huecos, viga subdividida y corte Z);
- el plan real 194, en solo lectura.

**Lecturas:** con las representaciones ETABS observadas (inicio cíclico rotado; gravedad Dir10 con signo invertido).

**Negativos:**
- orientación invertida;
- pieza faltante;
- pieza extra sobre un hueco;
- nodo compartido roto;
- nodo colgante;
- subframe ausente o con conectividad cambiada;
- carga con magnitud, signo o proyección cambiados (incluido un frame);
- apoyo, masa, espesor, propiedad de triángulo o diafragma de un nodo derivado equivocados;
- operación modificadora sin lector;
- lectura parcial;
- unidades N_mm_C;
- plan alterado o incoherente.

**Otras comprobaciones:**
- legado 0.3 sin sección malla;
- script PowerShell real contra un ETABSv1 falso que reabre un EDB persistido: verificado y alterado, sin ningún setter durante la relectura.

## Límites

- **Sin ETABS real:** no se reabrió el EDB real 194 ni se ejecutó el solver; los dobles no acreditan ETABS.
- **El ensayo nativo de relectura es de Codex.**
- **Sin getter de masa propia:** la masa propia por elemento no se puede leer, porque solo existe la fuente de masa.
- **Lo que no prueba una relectura:** la calidad de la malla y el efecto estructural.
