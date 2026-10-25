# Controles internos posteriores al análisis (postsolver)

Corresponde al requisito de desarrollo técnico §5.10 (O2.4/O2.13/O5.1, P09/P10):
- participación modal acumulada;
- equilibrio, cuando se declare aplicable;
- advertencias del solver.

Todos se calculan desde datos crudos con aplicabilidad y criterios **declarados**.

**Reglas generales:**
- El estado CSI 4 solo significa que el motor terminó; aquí se conserva como `estado_motor: csi_4_terminado_no_equivale_a_controlado`.
- No hay tolerancias normativas por defecto.
- La identidad y la competencia del revisor son declaradas, no verificadas.
- No se certifica normativa ni seguridad, no se aprueban resultados y no se reescribe el estado del motor ni los resultados nativos.

## Piezas

| Capa | Archivo |
|---|---|
| Núcleo puro | `draft2model/controles_analisis.py` (`crear_controles`, `recalcular_controles`, `validar_controles`) |
| Servicio persistente | `draft2model/revision_controles.py` (`ServicioControles`) |
| HTTP | `draft2model/revision_visual.py` |
| UI | `draft2model/revision_web/controles.js` y la sección «Controles internos posteriores al análisis» de `index.html` |
| Informe (opt-in) | `informe.py`, `revision_entregables.py` y `revision_web/informes.js` |

## Núcleo: contrato y semántica

**Declaración**, con campos exactos:

```
caso, expediente_sha256, corrida_analisis, lectura, modelo{id, sha256_edb}, datos_sinteticos, casos,
sha256_respuesta, sha256_avisos_solver, revisor_declarado, fecha, alcance, controles[≥3]
```

Hay que declarar las tres familias: `participacion_modal`, `equilibrio` y `advertencias_solver`. Cada control tiene esta forma:

```
{id, tipo, caso, aplica, critico, motivo, fuente_criterio, parametros}
```

Si un control no aplica, sus parámetros deben ser `{}` y su motivo, explícito.

**Cálculo por familia:**
- **`participacion_modal`:** solo se admiten campos acumulados observados (`SumUX`, `SumUY`, `SumUZ`, `SumRX`, `SumRY`, `SumRZ`) de `Modal Participating Mass Ratios`, con la dirección coherente con el campo.
  - El selector debe ser exacto: un filtro con el caso y el modo; no se elige el máximo ni la última fila.
  - La participación es una fracción entre 0 y 1; no se interpretan porcentajes.
  - Fórmula: `acumulado_seleccionado >= minimo_acumulado`.
- **`equilibrio`:** términos de cargas y reacciones con signo explícito (+1 o −1), en unidad `kN` o `kN_m`, sin reutilizar un componente en ambos lados.
  - Fórmula: `abs(Σ) <= max(tol_abs, tol_rel·escala)`, con `escala > 0`.
  - Las tablas de cargas aplicadas deben salir de la lectura. En las pruebas, la tabla de cargas es **solo un doble**.
- **`advertencias_solver`:** se compara una **fuente declarada** (`draft2model.avisos_solver_declarados`, ligada a la corrida, el modelo, el EDB y los casos) con `codigos_admitidos`.
  - Los avisos del lector **no** son el log del solver.
  - Sin fuente, el control queda `sin_datos`.

**Estados por control:** `satisfactorio`, `discrepante`, `sin_datos` o `no_aplicable`. Cada control conserva la fórmula, los valores con su unidad, las trazas (selector, SHA de la tabla, índice de fila y valor crudo) y los motivos.

**Origen de cada control:**
- `base_datos` vale `tablas_lectura` o `fuente_solver_declarada`.
- `verificacion` vale `recalculada_desde_bytes_de_lectura` o `declarada_no_verificada`.

**Resultado global:**
- `estado_global`.
- `faltantes_criticos` (controles críticos en `sin_datos`).
- `controles_solo_declarados`.
- `criticos_no_aplicables`.
- `apto_proyeccion_controlado`: vale `true` solo si **todos** los controles aplicables son satisfactorios **y** al menos uno se calcula desde las tablas de la lectura. Así, una declaración humana sin datos (por ejemplo, una lista vacía de avisos) nunca se presenta como control automatizado satisfactorio.
- Los bytes crudos se embeben como base64 y el documento lleva `huella_contenido`. `validar_controles` lo recalcula desde los bytes originales y exige igualdad exacta.

## Servicio `ServicioControles(app)`

**`crear(body)`**

Cuerpo exacto:

```
{caso, expediente_sha256, lectura, sha256_respuesta, avisos_solver_json|null,
 revisor_declarado, fecha, alcance, controles, confirmacion_explicita:true}
```

Pasos:
1. Exige una lectura de `ServicioLecturas` con `estado: aceptado`, vigente, `lectura_verificada` y el mismo expediente y SHA.
2. Toma sus bytes exactos con `respuesta_bytes`.
3. Obtiene el análisis aceptado con `verificar_analisis_aceptado` (modelo, EDB y naturaleza).
4. Construye la declaración del núcleo; el vínculo no se toma del cuerpo.
5. Persiste en `<caso>/controles_analisis/<uuid>/`: `controles.json` (documento del núcleo) y `version.json` (vínculo y SHA). Se publica mediante staging en `.ctl-*` y `rename`. Las versiones son inmutables.

**Consulta y listado:** `consultar(caso, version, expediente_sha256=)` y `listar(caso, expediente_sha256=)`.
- Revalidan la lectura (aceptada y vigente), sus bytes, el análisis, el modelo y el EDB, y el vínculo registrado.
- Recalculan el documento con `validar_controles`.
- La proyección excluye los bytes embebidos (`fuentes` solo con SHA) y no contiene rutas privadas.
- `listar` no selecciona automáticamente.

**Errores:** `ErrorControles` (`ValueError`), con mensajes fijos. Los motivos de rechazo del núcleo se exponen truncados y sin rutas.

## HTTP

| Método | Ruta |
|---|---|
| GET | `/api/controles/historial?caso&expediente_sha256` |
| GET | `/api/controles/version?caso&version&expediente_sha256` |
| POST | `/api/controles/crear` |

Se aplican la sesión, el `Origin`, el `Host` y el límite de 2 MiB. Los errores responden 409.

## UI

- Muestra solo lecturas aceptadas, vigentes y verificadas.
- Los controles se declaran como JSON explícito, sin plantillas con tolerancias.
- La fuente solver es opcional; si se deja vacía, el control queda `sin_datos`.
- Revisor, fecha y alcance son obligatorios y requieren confirmación.
- El historial se selecciona manualmente.
- La tabla de controles (estado, base, verificación, fórmula y criterio, valores y motivos) y las listas (faltantes críticos, solo declarados, críticos no aplicables, avisos del lector, advertencias del solver) se construyen con nodos y `textContent`.
- `d2m-controls-review` se emite **solo** después de una consulta exacta, y emite `null` al invalidarse.

## Informe (opt-in)

- `POST /api/informe/crear` admite el campo opcional `controles_analisis: {id, sha256_controles}`. Exige un análisis explícito y `null` no se acepta.
- El núcleo valida la coherencia de la proyección con el caso, el análisis, el EDB, el modelo y la naturaleza sintética, y obtiene la proyección viva del servicio al crear y al exportar.
- `consultar`, `listar`, `archivo` y `aprobar` revalidan los controles antes y después de cada operación.
- La aprobación documental hija conserva la referencia exacta.
- **Compatibilidad:** los informes sin selección no cambian.
- La sección «Controles internos postsolver seleccionados» muestra APTO o NO APTO según los criterios DECLARADOS, el estado global, la base y la verificación de cada control, los faltantes, los avisos del lector y las advertencias declaradas.

## Límites

- Hoy el lector no extrae el log del solver. Las advertencias solo pueden venir de una fuente **declarada**, marcada como `declarada_no_verificada`; sin ella, el control queda `sin_datos`. No se inventa una tabla API.
- En las pruebas, la cadena real lectura → controles usa el **transporte doble** de Python. Sus tablas (`Drift`) no son fuerzas reales: solo prueban la cadena de software.
- La prueba del informe con controles construye la proyección con el núcleo real, pero sustituye `ServicioControles.consultar`, porque la fixture de resultados usa un análisis en modo real que no admite una lectura doble.
- Sin datos reales de ETABS ni criterios revisados del caso, nada acredita controles físicos.

## Revalidación final (hallazgo Codex 136, corrección 137)

`ServicioControles._cargar` vuelve a resolver la lectura aceptada, sus bytes, el análisis, el modelo y el EDB **después** de `validar_controles`, y exige igualdad con el snapshot inicial. Antes solo se releía el registro. Así, un cambio en `respuesta.json` durante la validación ya no produce `vigente:true`. La regresión es `test_fuente_cambia_despues_del_recalculo_no_es_vigente`. El parche de Codex se integró con SHA idénticos a los de su ficha (`seguimiento/CORRECCION_REVALIDACION_137.json`).
