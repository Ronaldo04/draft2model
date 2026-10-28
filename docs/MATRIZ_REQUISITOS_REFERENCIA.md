# Matriz de requisitos de la referencia completa (ruta 201, auditada en la etapa 06)

Corte actual: 23 de octubre de 2026. Las tablas de ensayos201 conservan su evidencia histórica; el apartado «Corte del piloto real» registra los avances posteriores y prevalece sobre estados históricos. La aceptación global sigue abierta. Sustituye a [MATRIZ_CIERRE_VIGENTE](MATRIZ_CIERRE_VIGENTE.md) (18 de octubre, que se conserva como historia) para el estado por requisito.

**Estados:**
- **implementado**: hay código.
- **doble**: probado con dobles o transportes simulados, que **no** prueban ETABS ni el proveedor.
- **nativo sintético**: ejecutado en ETABS 21.1 local sobre una fixture sintética.
- **pendiente de dato o piloto**: falta información del proyecto real o una autorización (etapa 04).
- **pendiente de código**: no hay soporte.

Una prueba verde solo acredita lo que cubre. No se afirma validación profesional, normativa ni comparación manual: el usuario la aplazó hasta tener nuestros resultados y no es condición del cierre actual.

## Componentes de la referencia (planos de hasta 4 niveles)

| Requisito | Módulo / recorrido | Criterio verificable | Evidencia | Estado |
|---|---|---|---|---|
| **Hasta 4 niveles** (sin límite de 2) | `validacion_geometria`, `operaciones_etabs` (`SetStories_2`) | Pisos = niveles − 1; puntos entre la base y el techo | `test_referencia_ruta201`; nativo `tmp/r3` (4 pisos, 320 operaciones) | nativo sintético |
| **Losas aligeradas** (nervada/casetonada); no se sustituyen por macizas | Configuración 0.2–0.5: `SetSlab` (capa) + `SetSlabRibbed`/`Waffle`, `SetLocalAxes` por triángulo; lector | Capa = `Thickness`; subtipo, parámetros y ejes releídos | Ensayo real 181 (Codex); `tmp/r3` nervada con relectura verificada | nativo sintético (casetonada: real 181) |
| **Frames: columnas y vigas** (rectangulares) | `SetRectangle`, `AddByPoint`; subdivisión conforme en bordes compartidos | Extremos, sección y cargas por subframe releídos; conservación | 194/198 (Codex, viga subdividida); `tmp/r3` (8 columnas, 4 vigas) | nativo sintético |
| **Placas / muros** (shell) con huecos | Superficies verticales 0.3/0.4 + `SetWall`; partición con huecos | Área neta, huecos libres, malla conforme | 183 (Codex); `tmp/l2` (muro con puerta); `tmp/r3` | nativo sintético |
| **Escaleras** | Idealización declarada: descanso horizontal + tramo inclinado shell (losa de garganta), conectados por `conexiones_borde` | Nodos compartidos descanso–losa y tramo–descanso; carga en el tramo | `test_referencia_ruta201`; `tmp/r3` | nativo sintético. **Límite:** los peldaños no se modelan como geometría; la idealización la declara el revisor |
| **Cisterna o tanque** (presión hidrostática) | Configuración/plan 0.5 (`liquidos`), tabla no uniforme, cortes Z | Filas releídas; equilibrio de reacciones de `BaseReact` frente a la integral analítica | `tmp/l2` y `tmp/r3`: equilibrio estricto ≤ 2e-12 | nativo sintético |
| **Vivienda sin cisterna** | 0.4, o 0.5 con `ausente_confirmado`, sin cargas de agua | Sin filas ni patrones ficticios; información insuficiente = faltante | `test_liquidos_ruta201`; 198 (0.4 sin líquidos) | nativo sintético (0.4) / doble (0.5 ausente) |
| **Huecos y aberturas** | Partición 180 + triangulación; sin material en huecos | Área neta exacta; relectura de malla | 183, 194 y 198 (Codex); `tmp/l2` | nativo sintético |
| **Compatibilidad y topología** | Compatibilidad 182; lector de malla (conformidad y nodos compartidos) | Sin nodos colgantes; nodos compartidos por ambos hosts | 198 (relectura 199/200), `tmp/l2`, `tmp/r3` | nativo sintético |
| **Materiales y propiedades** | Configuración + `SetMaterial`/`SetMPIsotropic`/`SetWeightAndMass` | Relectura E, U, A y W | 180, 198, `tmp/r3` | nativo sintético |
| **Masas** | Fuente de masa por patrones (`SetMassSource_1` + relectura) | Patrones y factores releídos | 198, `tmp/r3` | nativo sintético. **No afirmado:** masa propia por elemento (sin getter) |
| **Cargas** (punto, frame, área uniforme e hidrostática) | Plan; lector con Dir10/11 (CSI 9398) | Fuerza y momento conservados frente a la fuente | 192/194 (Codex), `tmp/l2`, `tmp/r3` | nativo sintético |
| **Apoyos y diafragmas** (incluidos los nodos derivados) | Política explícita en 0.4/0.5; lector por nodo | Restricciones y diafragma releídos | 198, `tmp/r3` | nativo sintético |
| **Casos, combinaciones y análisis** | Estático, modal y espectral; analizador | Casos en estado 4; tablas leídas | 180 (Codex, dinámico); `tmp/l2`, `tmp/r3` (estático) | nativo sintético |
| **Lectura de resultados** | `lectura_analisis` (tablas + `BaseReact` tipado) | Unidades de presentación kN_m_C; dobles sin redondeo | `tmp/l2`, `tmp/r3` | nativo sintético |
| **Normalización, controles e informe** | `normalizacion_etabs`, `controles_analisis`, `informe` | 7 categorías; límites visibles | 180 (Codex) hasta PDF; dobles | nativo sintético (180) / doble |

## Recorrido desde los planos sin programar

| Requisito | Módulo / recorrido | Criterio | Evidencia | Estado |
|---|---|---|---|---|
| **Ingreso de planos**, originales y hashes | `ingreso`, revisión documental (UI) | Originales intactos; páginas y errores visibles | Pruebas web; caso `provisional-001` registrado; paquete 135 revalidado por Codex (R205-01) | implementado (real: integridad) / pendiente de piloto |
| **Recortes y paquete visual** | `recortes`, `entrada_vision` | Paquete 135 (10 imágenes) y paquete `ace03b8b` con prompt de cobertura exhaustiva | `tmp/referencia_preparada_135.json`; `INFORME_04.md` | implementado; 135 enviado una vez por Codex |
| **Lectura por Google u OpenAI** (solo planos) | `proveedor_openai` / `proveedor_gemini`; compuerta `politica_uso_ia` | Solo estos dos proveedores en UI, CLI y servicio real; ejecutar exige autorización explícita; Codex es el ejecutor exclusivo (R211-01) | `test_preflight_ruta201`, `test_proveedores_intercambiables`; petición real 1 (gpt-5.4, `CONSUMO_API_211`): 34 candidatos, muestra asistida 8/10 valores | real: OpenAI 4/5 (petición 2 **enviada y fallida por truncamiento**, no repetir) y Gemini 2/5 (la 2.ª recuperada con cuarentena: 59 + 12); lecturas pendientes de revisión |
| **Revisión explícita y conversión** a geometría 0.3 | `revision_conversion`, `conversion_geometria` (0.1–0.3) | Correspondencias, escala y unidades declaradas; borrador sin aprobación | Pruebas de conversión | doble / pendiente de piloto |
| **Configuración sin programar** | Editor web (importar/revisar/aprobar), preparación de malla 0.4/0.5 con exportación, `plantilla_configuracion` (borrador y conexiones ligadas con huellas calculadas) | Sin datos técnicos inventados; errores y faltantes enumerados | `test_plantilla_configuracion_ruta201`, `test_ui_malla` | implementado / doble |
| **Datos técnicos del proyecto real** (materiales, cargas, sitio, normativa) | Declaración del revisor | Fuentes revisadas | — | **escenarios declarados disponibles; EMS y revisión profesional pendientes** |
| **Proveedores no autorizados** ocultos | UI, CLI y servicio real | Anthropic y la API compatible solo se leen en la historia o se usan con dobles | `test_preflight_ruta201` | implementado |
| **Validación de entorno** (instalación, rutas, permisos, ETABS) | `python -m draft2model.preflight` | Errores con acción; sin ETABS ni claves | `test_preflight_ruta201`; host: listo, con aviso de rutas de 244 caracteres | implementado / probado en el host |
| **Recuperación de incertidumbre** | `confirmar_recuperacion` con evidencia | Sin borrar marcas a mano | Recuperación de la lectura `dde566db` (`tmp/l2`) | nativo |
| **Copia limpia y guía reproducible** | `verificar_copia_limpia.py`, [GUIA_REPRODUCIBLE](GUIA_REPRODUCIBLE.md) | Instalación y arranque desde copia | `tmp/c201b` completa (etapa 05) y repetida en la 06; instalación sin red `tmp/instalacion_201` 6/6 | probado |
| **QA visual de recorridos** | Navegador | Capturas acotadas | Etapa 05: selector solo openai/gemini, panel de malla 0.5, sin errores de consola | probado (servidor local con datos sintéticos) |
| **Piloto con los planos adjuntos** | Recorrido completo | Resultados propios trazables | Extracciones revisadas contra originales (07/08); calibración por arquitectura; inventario vectorial 09; muros L0004/L0005 (`MUROS_09.json`); geometría conforme 7c84de15 (2083 superficies, 0 nodos colgantes); plantilla ETABS propia del caso; configuración 0.5 con 2 errores = puerta de albañilería (`CONFIGURACION_CASO_09B.json`) | **nativo real parcial verificado**: modelo, análisis y13indicadores; informe/panel finales e interfaz pendientes. Arcilla y alturas confirmadas; sin EMS, suelo/sistema como escenarios explícitos. Véase corte actual. |
| **Comparación con el modelo manual** | — | — | Aplazada por el usuario | **fuera del cierre actual** |

## Alcance normativo (R204-01)

Referencia: `seguimiento/REFERENCIA_NORMATIVA_Y_ENTRADAS_204.md`. El soporte genérico (patrones, espectro tabulado, reglas `factor · x + desplazamiento`, corpus léxico) **no** acredita cumplimiento de ninguna norma.

| Requisito | Criterio verificable | Evidencia | Estado |
|---|---|---|---|
| **Normas, ediciones y artículos aplicados** al caso (norma + edición/modificatoria + artículo/tabla + motivo) | Cada parámetro o regla normativa del expediente cita su fuente exacta | Usuario eligió RNE vigente (229). Corpus 229 auditado por Codex; funciones con cita y verificación textual 26/26 (08); borrador del caso con Z, U, R, deriva y espectros (08) | **aplicado a escenarios del piloto; conformidad global no acreditada** |
| **E.020, E.030, E.050, E.060, E.070** | No se declara cumplimiento por el soporte genérico; cobertura automatizada por demostrar requisito a requisito | — | **no afirmado** |
| **Corpus oficial revisado y reglas peruanas aprobadas** | Corpus con SHA y edición; reglas con fuente aplicadas al caso real de principio a fin | Infraestructura `fuentes_locales`/`evaluacion` probada con dobles | **corpus revisado y evaluaciones reales disponibles; aprobación profesional pendiente** |
| **Ediciones vigentes** (p. ej. RM 183-2026 y 217-2026 sobre E.030) | El revisor fija qué texto rige el expediente | Decisión del usuario (229): RNE vigente; E.030 RM 183-2026 implementada con cita | **decidido; implementado** |
| **Diseño de elementos** (armado E.060, albañilería confinada E.070) | — | El contrato admite E, peso y secciones; no diseña | **fuera del alcance actual** |

**Limitaciones materiales:**
- Los ensayos201 son sintéticos; el piloto posterior es real, pero solo acredita el escenario revisado de Pueblo Libre. No prueba generalización ni cumplimiento integral de albañilería confinada.
- La presión estática no cubre hidrodinámica, geotecnia ni flotación.
- Las aprobaciones son declaradas («solo software» en los ensayos).


## Corte del piloto real: 23 de octubre de 2026

| Componente | Evidencia observada | Pendiente para cierre |
| --- | --- | --- |
| Planos y datos | Seis PDF originales de Pueblo Libre con integridad comprobada; arcilla y cotas0/2,60/5,20/7,80/10,40m confirmadas, primer tramo16contrahuellas | Precisión de extracción no medible sin referencia humana completa; revisiones siguen siendo necesarias |
| Modelo y análisis | Geometría25ef94672fac4e53863701b55e32f97d, modelo0f37271307b6449c89c458c60a1640c7, análisis7203c79a3ece4438b36d267ba80f3c4b; EDB analizado con SHA42371308a03d4f1bac8f5ed3aa5daf0421cdf3de27ff823f8f582c13ad2af394 | No se declara revisión profesional ni reproducción nativa en otro equipo |
| Resultados | Resultado697bb37e9ce64f90ba1ef3e25733c8cc:13indicadores; T1=1,339s, VX=672,5354kN, VY=528,1533kN | Interfaz y descarga de la versión final por comprobar |
| Evaluación |18comparaciones de escenarios:8satisfacen y10no;8fallos de deriva (2SX,6SY) y2de cortante mínimo | Son comprobaciones parciales; no aprobación normativa. Suelo/sistema siguen siendo hipótesis |
| Masa | Masa nativa548,7267285730835 frente a libro549,4269889710316; contraste oficial no_coherente | Diferencia principal explicada por extremos efectivos de vigas; no se amplió tolerancia ni se sustituyó la predicción independiente por un ajuste |
| Informe y panel | Salidas corregidas09d3:18evaluaciones conservadas, unidad de cociente1, captura nativa incluida con contraste no_coherente; PDF y panel revisados302 | QA real de la integración301, compatibilidad entre renderizadores PDF y validación global final |
| Distribución | Instalación offline287:6/6 sobre fuentes285. Complemento291 conserva un solo caso, resultados seleccionados y20fuentes normativas públicas; hashes revisados | Ambos son antecedentes/candidatos, no la distribución final aceptada |

La ausencia de EMS se conserva como faltante. Los escenarios no sustituyen investigación geotécnica. No se afirma extracción automática sin revisión, diseño de armado, hidrodinámica ni soporte validado para cualquier construcción. La comparación con el modelo manual sigue aplazada. Los proyectos2y3 no se han procesado.

En el repositorio de desarrollo las evidencias son `seguimiento/REVISION_REGLAS_REALES_286.json`, `REVISION_CONTROLES_REALES_285.json`, `REVISION_INFORME_PANEL_290.json`, `REVISION_UNIDADES_292.json`, `REVISION_COMPLEMENTO_291.json` y `REVISION_INSTALACION_287.json`. Estos registros internos no se incluyen automáticamente en el paquete público; la entrega final debe adjuntar un resumen de validación asociado a su huella.
