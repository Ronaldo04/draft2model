# Informe Encargo 350 — Políticas Automáticas de Nodos y Subdivisión de Barras

- **Responsable:** Antigravity | **Corte base:** 349 | **Alcance:** Sintético, puro, sin llamadas a APIs (`0`) ni uso de ETABS (`false`).
- **Raíz verificada:** `D:/RONALDO CUCHILLA/1. RONALDO CUCHILLA/2. INGENIERÍA CIVIL DOCS AND PROJECTS/AECODE CURSOS/AECODE AI TALENT/PROYECTO FINAL`

## 1. Diseño e implementación (`draft2model/politicas_malla_automatica.py`)

Se implementó un módulo puro (sin I/O en disco ni red) sobre `malla_preparacion.preparar_malla` y `validacion_geometria.validar_geometria`, compatible con configuraciones `0.4.0` y `0.5.0` y geometría `0.3.0`:

1. **Contrato cerrado de reglas (`draft2model.reglas_politica_malla` v`0.1.0`):**
   - `validar_reglas_politica` y `plantilla_reglas_vacia`: exigen claves exactas, unidad explícita `unidad_longitud == "m"`, números finitos y seis booleanos estrictos `[Ux, Uy, Uz, Rx, Ry, Rz]`.
   - Selectores cerrados sin fusión por cercanía: `plano_z` (`z_m`, `hosts`, `solo_corte`), `borde_entre_puntos` (`inicio`, `fin`, `hosts` usando el criterio exacto con `Fraction` de `malla_preparacion`), `entidades` (`hosts`, `aberturas`, `conexiones_borde`, `nodos_corte`, incluyendo propagación topológica a nodos de corte `MC_*`) y `nodos`.
   - Subdivisión de barras (`subdivision_frames`): `autorizar_calculadas` o `por_frame` (`autorizar` / `bloquear`), conservando orden e IDs `<frame>_Sk` calculados por el algoritmo.
2. **Cero supuestos estructurales implícitos:**
   - No asume apoyo en `z=0`, diafragmas por nivel, continuidad desde extremos apoyados (`W1-W2`) ni condición libre/sin diafragma para el resto salvo declaración explícita (`resto_restricciones`, `resto_diafragma`).
   - Cuando faltan reglas, lista `pendientes` concretos sin inventar registros. Cuando dos reglas se contradicen en nodo, barra o fuente del mismo nivel, registra `conflictos` y fija `listo_para_aplicar = False` sin elegir la primera.
3. **Vista previa y aplicación inmutable:**
   - `previsualizar_politicas_malla(geometria, configuracion, reglas=None)` devuelve `draft2model.propuesta_politicas_malla` v`0.1.0` con inventario enriquecido, trazabilidad, pendientes, conflictos, errores y `huella_propuesta`.
   - `aplicar_politicas_malla(geometria, configuracion, reglas)` verifica `listo_para_aplicar` (lanza `ErrorPoliticaMalla` en caso contrario), comprueba por SHA canónico que las entradas no mutan, devuelve copia profunda con `revision = {"estado": "borrador", "aprobacion": None}`, preserva `datos_sinteticos` y deja intactos otros faltantes (p. ej. `sitio` o `liquidos` en `0.5.0`).

## 2. Verificación focal (`tests/test_politicas_malla_automatica.py`)

- Comando: `.\.venv\Scripts\python.exe -X utf8 -m unittest -v tests.test_politicas_malla_automatica` → **10 pruebas `OK` en memoria**.
- Cobertura: ausencia de reglas, 6 topologías base (`horizontal`, `vertical`, `inclinado`, `conectados`, `vertical_corte`, `conectados_corte`), no herencia en `z=0`, malla numerosa ($\ge 60$ nodos derivados y 10 huecos resuelta con reglas concisas), contradicciones de reglas/fuentes, errores de unidades/coordenadas/coplanaridad, incompatibilidad de origen/huella, fuentes/entidades inexistentes, bloqueo de barra e inmutabilidad/no herencia de aprobación.

## 3. Limitaciones y entrega para integración

- Queda lista la API pura y su especificación (`docs/POLITICAS_MALLA_AUTOMATICA.md`) para que Codex la conecte con el editor web y la persistencia de versiones de configuración.
- Todas las pruebas se ejecutaron sobre fixtures sintéticas; no sustituyen revisión estructural profesional, cumplimiento normativo ni validación nativa del piloto en ETABS.
