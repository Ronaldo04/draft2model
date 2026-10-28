# Informe 06 — auditoría final de la ruta 201

Fecha: 21 de octubre de 2026. **Estado: `bloqueado`** (solo restan bloqueos externos reales). No es `finalizado`. El goal de Codex **no** se marca completo; Codex revisa y decide.

## 1. Correcciones de esta etapa

| Observación | Cambio | Verificación |
|---|---|---|
| **R203-01** | `configuracion.js`: la preparación de malla exige `huella_configuracion` de tipo texto e igual a la de la versión abierta; se rechazan la ausencia, `null` y otros tipos. El mock de `ui_malla_frontend.cjs` ahora incluye la huella, igual que el servidor real. | `tests/ruta201_frontend.cjs` añade los casos `undefined`, `null` y `42` (sin resumen y con error); `ui_malla_frontend.cjs` y `configuracion_html_check.cjs` en verde. |
| **R203-02** | `crear_entrega_ruta.py`: el prefijo `requirements` se sustituye por una lista explícita de archivos raíz (`README.md`, `requirements.txt`, `requirements-win-py310.lock` y los dos lanzadores `.cmd`). La comprobación de claves reservadas y obligatorias pasa de `main()` a `crear()`, de modo que también cubre la API. | `tests/test_crear_entrega_ruta201.py` (4 pruebas) trabaja en un proyecto temporal aislado. Comprueba: archivos raíz admitidos; `requirements-extra.txt`, `notas.md`, `tmp/`, `data/` y `../` rechazados; `estado`, `snapshot`, `id`, claves ausentes y tipos inválidos rechazados sin crear carpeta; la CLI devuelve 2. |
| **R204-01** | La matriz añade la sección «Alcance normativo». No hay norma, edición ni artículo aplicado. No se afirma cumplimiento de E.020, E.030, E.050, E.060 ni E.070 por el soporte genérico. Corpus y reglas quedan pendientes de dato y piloto. Las ediciones (RM 183-2026 y 217-2026) quedan pendientes de decisión técnica, y el diseño de elementos queda fuera de alcance. | Revisión documental contra `seguimiento/REFERENCIA_NORMATIVA_Y_ENTRADAS_204.md`. |
| Matriz desactualizada | Filas corregidas:<br>• copia limpia → probado;<br>• QA visual → probado;<br>• lectura por proveedor → real parcial (1 petición, cobertura insuficiente);<br>• piloto → bloqueado externo;<br>• ingreso y paquete con R205-01. | Ver §2. |
| `docs/RETOMAR.md` | La lista de pendientes 02–06 (obsoleta) se sustituye por el estado de la ruta y los pendientes externos exactos. | — |

R205-01, R206-01 y R210-01 son evidencia de Codex: se incorporan a la matriz sin repetir los ensayos nativos. R209-01 y R211-01 son coordinación: Claude no lanzó ninguna llamada a API.

## 2. Matriz auditada (resumen; detalle en `docs/MATRIZ_REQUISITOS_REFERENCIA.md`)

Clasificación de la etapa 06: **probado**, **contradicho**, **incompleto**, **evidencia débil** o **ausente**.

| Requisito | Clasificación | Evidencia actual |
|---|---|---|
| Hasta 4 niveles | probado (nativo sintético) | `tmp/r3`: 320 operaciones, relectura verificada; `test_referencia_ruta201` |
| Losas aligeradas (nervada/casetonada) | probado (nervada en `r3`; casetonada en el ensayo real 181) | `tmp/r3`, entrega 181 |
| Frames y subdivisión | probado | 194/198, `tmp/r3` |
| Placas/muros con huecos | probado | 183, `tmp/l2`, `tmp/r3` |
| Escaleras | probado como idealización declarada | `tmp/r3`. **Límite:** los peldaños no son geometría |
| Cisterna/tanque | probado | `tmp/l2`, `tmp/r3`: reacciones `BaseReact` tipadas en equilibrio estricto ≤ 2e-12 (R210-01). La lectura redondeada 208 se conserva como negativa aparte |
| Vivienda sin cisterna | probado con 0.4 nativo; 0.5 `ausente_confirmado` con **evidencia débil** (solo dobles) | 198; `test_liquidos_ruta201` |
| Huecos, compatibilidad y topología | probado | 183/194/198, `tmp/l2`, `tmp/r3` |
| Materiales, masas, cargas, apoyos y diafragmas | probado. La masa propia por elemento está **ausente** (no hay getter) | 198, `tmp/r3` |
| Casos y análisis | probado: estático nativo en `l2`/`r3`; modal/espectral en 180 | — |
| Lectura de resultados | probado | `tmp/l2`, `tmp/r3`, `verificar_evidencia_ruta201.py` (exit 0) |
| Normalización, controles e informe | probado en 180 y con dobles; **incompleto** para el caso real | — |
| Ingreso y paquete visual | probado (integridad, R205-01) | Paquete 135 y `ace03b8b` |
| Lectura Google/OpenAI | **incompleto** | 1 petición real: 34 candidatos, 8/10 valores correctos; bboxes: 4 ajustadas, 4 desplazadas, 2 vacías. Cobertura insuficiente para modelar |
| Conversión revisada y configuración sin programar | probado con dobles; **incompleto** en el caso real | — |
| Datos técnicos del proyecto real | **ausente** (pendiente del usuario) | `SOLICITUD_PILOTO_04.json` |
| Alcance normativo | **ausente** (no afirmado) | §1, R204-01 |
| Validación de entorno | probado en el host | `preflight`: LISTO, con aviso de rutas de 244 caracteres |
| Recuperación de incertidumbre | probado | Lectura `dde566db` |
| Copia limpia y guía | probado | `tmp/c206` (§3); `GUIA_REPRODUCIBLE.md` |
| QA visual | probado | Etapa 05 |
| Piloto completo | **incompleto, bloqueado externo** | §4 |
| Comparación manual | fuera del cierre (aplazada por el usuario) | — |

**Contradicho:** ninguno tras las correcciones de la §1.

## 3. Verificaciones repetidas en la etapa 06

- Node: `ruta201_frontend.cjs`, `ui_malla_frontend.cjs` y `configuracion_html_check.cjs`: OK.
- Python: `tests.test_crear_entrega_ruta201`: 4 OK.
- `scripts/verificar_evidencia_ruta201.py`: exit 0; `l2` y `r3` aceptados con equilibrio estricto por API. Log en `logs/evidencia06.log`.
- `python -m draft2model.preflight`: LISTO, con aviso de rutas. Log en `logs/preflight06.log`.
- Copia limpia final `tmp/c206`:
  - `completa: true`, sin red y sin ETABS;
  - dependencias, arranque de la CLI, PowerShell, suite (**1164 pruebas OK**) e interfaz (**0 omitidas**) devolvieron 0;
  - `archivos_estables_durante_ejecucion: true`; `validacion_local_completa: true`; `alcanza_validacion_piloto: false`, correctamente.
  - El único archivo de la entrega que difiere de la copia es `docs/RETOMAR.md`, editado después de iniciarla. Es documentación de estado y ninguna prueba lo cubre.
  - Log en `logs/copia_c206.log`; informe en `tmp/c206/copia_limpia.json`.

No se ejecutó ETABS en esta etapa: ningún cambio afectó al adaptador nativo.

## 4. Pendientes externos exactos y cómo retomar

1. **Petición 2 del piloto (Codex, ejecutor exclusivo)**
   - Plan: `data/private/provisional-001/vision/planes_openai/2617a919bb2b47a2b4dddce1dc3f08e8`, SHA del plan `0ba6c68f…`, SHA de la petición `fd651754…`; está preparado y no se ha enviado.
   - Al llegar el recibo: revisión asistida de cobertura y bboxes sobre la página renderizada, decisión de suficiencia, conversión revisada a geometría 0.3, configuración 0.4/0.5 y recorrido nativo propio.
2. **Datos técnicos del usuario** para `provisional-001`:
   - materiales, cargas de uso y acabados, sitio y espectro, apoyos;
   - presencia o ausencia confirmada de cisterna o tanque, con su nivel libre si existe;
   - normas con edición y artículo.
   - Formato en `seguimiento/claude_ruta/SOLICITUD_PILOTO_04.json`. No se inventan.
3. **Comparación manual:** aplazada por el usuario. Se hará después de tener resultados propios.

## 5. Limitaciones materiales

- Los ensayos nativos son sintéticos: no validan la referencia real ni la albañilería confinada.
- La presión hidrostática es estática: no incluye efectos hidrodinámicos, geotecnia, flotación ni las situaciones lleno/vacío.
- Las aprobaciones son declaradas («solo software»). No hay validación profesional ni normativa.
- La masa propia por elemento no se relee.
- El margen de rutas es escaso (244 de 260 caracteres).

## 6. Snapshot

Entrega `entregas/06-a0292ab2b8154a109c9b19bbd38191c4/`, con estado `bloqueado`:
- `fuentes.zip`, SHA-256 `a88f6b7de4a92289c3985d9f9c3cb70e4718e5b44b30119e24afe92579d8cf06`.
- Contenido: instantánea **completa** del producto, con 513 archivos de `draft2model/`, `scripts/`, `tests/`, `examples/`, `docs/` y la raíz autorizada.
- La guarda excluyó tres archivos cuyo nombre contiene «credencial»: `draft2model/credenciales_locales.py`, `scripts/usar_credenciales_locales.py` y `tests/test_credenciales_locales.py`. Son código, no claves; la copia limpia `c206` los cubre y sus huellas están en `logs/copia_limpia_c206.json`. Se registran en `excluidos_por_guarda`.
- Comprobación con las reglas del lector de Codex: inventario y bytes del ZIP coinciden y no hay archivos fuera de alcance.
- `estado.json`: `estado` = `bloqueado`, y `ultima_entrega` apunta a este manifiesto.
