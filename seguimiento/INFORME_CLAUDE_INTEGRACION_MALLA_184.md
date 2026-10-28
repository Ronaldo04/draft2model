# Informe Claude — integración de malla 184 (con adenda de cortes 186)

Fecha: 20 de octubre de 2026. Carpeta verificada: `.../AECODE AI TALENT/PROYECTO FINAL`. Detalle técnico en [docs/INTEGRACION_MALLA_ETABS.md](../docs/INTEGRACION_MALLA_ETABS.md).

## Qué quedó integrado

1. **Triangulación de la compatibilidad** (`triangulacion_particiones.triangular_compatibilidad`, añadida; `triangular_particion` sin cambios):
   - reproduce la compatibilidad 182 con igualdad canónica;
   - recorte de orejas exacto que conserva todos los nodos colineales de borde (sin abanico);
   - verificaciones topológicas y de área.
2. **Preparación** (`draft2model/malla_preparacion.py`, nuevo), con una secuencia fija:
   1. partición de todos los hosts y huecos;
   2. compatibilidad en los bordes declarados;
   3. triangulación;
   4. **cortes Z explícitos**;
   5. nombres CSI deterministas (`MN_`, `MC_`, `MA_`, `_S<k>`);
   6. subdivisiones de frame requeridas y plantilla de política.

   Rechaza colisiones, uniones por proximidad y triángulos invertidos.
3. **Configuración 0.4** (`modelo_estructural`):
   - claves de 0.3 más `conexiones_borde`, `malla`, `cortes_nivel`, `nodos_derivados` (con `xyz_m` ligado a la posición) y `subdivision_frames`;
   - lo no declarado se convierte en faltante calculado: el borrador se puede importar y la aprobación queda bloqueada;
   - lo incorrecto es error;
   - `apto_para_adaptador` exige datos completos y no aprueba ingeniería;
   - 0.1 a 0.3 conservan su semántica.
4. **Plan 0.4** (`operaciones_etabs`):
   - triángulos `AddByPoint` sin host completo ni Opening;
   - propiedades nativas: `SetSlab` con la **capa** (181 no se revierte) y `SetSlabRibbed`/`Waffle`/`SetWall`, más ejes por triángulo;
   - frames subdivididos;
   - cargas copiadas por triángulo y subframe;
   - apoyos y diafragmas desde la política;
   - relecturas `GetRestraint`, `GetLoadUniform`, `GetMassSource_1` y `cFrameObj.GetPoints`, además de las existentes;
   - prueba de conservación de área, fuerza y momento ≤ 1e-9;
   - despacho `generar_plan_por_version` / `validar_plan_por_version` y CLI.
5. **Recorrido normal:**
   - `ejecutor_etabs.preparar` y `ejecucion_modelo._revalidar` regeneran por versión;
   - `revision_modelo` regenera 0.4 con `generar_plan_malla` y 0.1 con `generar_plan`, con el nombre conservado para los dobles existentes;
   - la lista blanca del PS1 está ampliada (BOM y CRLF conservados);
   - `gestion_configuracion.preparar_malla_version`, la CLI `malla` y `ServicioConfiguracion.malla`.

## Adenda 186 (cortes por nivel libre)

- **Cuándo se aplican:** después de compatibilidad y triangulación, y antes de nombres CSI y políticas.
- **Cómo se declaran:** solo los niveles declarados en `cortes_nivel` (z, fuente, motivo), cubiertos por la huella de la configuración y su aprobación.
- **Qué no hace:**
  - no crea Storys (se comprueba en el plan);
  - conserva ambos lados, y la pieza seca no se elimina;
  - los nodos `MC_` exigen política explícita, sin apoyos heredados;
  - no convierte carga parcial ni integra tablas de presión: siguen siendo de Codex.
- **`cortes_superficies.py`:** **sin editar**; su API se usa tal cual (hash `39d5b66c…`, igual al asignado).
- **Hallazgo al integrarla:** un corte movido reutilizaba nombres `MC_k` y la política se habría heredado en otra posición. Lo corregí: cada entrada de `nodos_derivados` declara `xyz_m`, que debe coincidir con la posición reproducida.

## Resultados observados

- **`tests.test_integracion_malla` (11 pruebas):**
  - gestión real en disco, en cinco configuraciones:
    - horizontal con 2 huecos;
    - muro con puerta, con y sin corte;
    - inclinado;
    - piso y muro conectados con una viga en el borde, con y sin corte;
  - 13 políticas inválidas o ausentes;
  - aligerado: capa y ejes;
  - invalidación por un cambio de geometría en disco;
  - planes manipulados;
  - contratos previos;
  - doble PowerShell real con `ETABSv1` falso con estado: guarda y registra, y 5 discrepancias o fallos parciales bloquean `Save` y el registro.
- **Regresión enfocada final:** 19 módulos (incluidos `test_cortes_superficies` y `test_cargas_liquidos_etabs` en solo lectura): **142 OK, 0 omitidas, código 0**.
  - Log: `tmp/claude_integracion_184/pruebas_final.log` (sha256 `387532ce…`).
  - TEMP y TMP en `tmp/claude_integracion_184`.
- **Primera regresión** (`pruebas_regresion.log`): 13 fallos.
  1. `test_revision_modelo`: un `patch` de `revision_modelo.generar_plan`. **Corregido** en `revision_modelo`; ahora 7 OK.
  2. `test_revision_ejecucion` y `test_revision_ejecucion_http` (10 errores y 1 fallo): `ruta_motor_demasiado_larga_use_raiz_mas_corta`. Es la guarda de 260 caracteres de Windows en `revision_ejecucion._rutas_motor` con TEMP dentro de la ruta larga del proyecto. Es **ambiental** y anterior a mi código: no se ejecuta nada mío antes de esa guarda. No se repitió con un TEMP corto fuera del proyecto, por la restricción de TEMP.
  3. `test_gestion_planes`: importa `test_gestion_geometria` sin el prefijo de paquete. Ejecutado desde `tests/` da **4 OK**.
- **Sin ETABS real.** No toqué PID 39368 ni `tmp/d2/motor.lock` (existe y está intacto). Sin API de IA, claves, instalaciones ni políticas.

## Pruebas o módulos ajenos que requieren actualización (Codex, solo lectura para mí)

- **`draft2model/revision_ejecucion.py` y `draft2model/gestion_planes.py`:** siguen llamando a `operaciones.generar_plan` (solo 0.1). Para construir 0.4 desde la web o los planes versionados deben usar `generar_plan_por_version`.
- **`tests/test_revision_ejecucion*.py`:** necesitan una raíz más corta, o un TEMP corto, para la guarda de 260 caracteres.
- **`tests/test_gestion_planes.py`:** usa la importación `from test_gestion_geometria …`, que falla al ejecutarse como `tests.test_gestion_planes`.
- **Interfaz y HTTP** de `ServicioConfiguracion.malla`: pendientes.

## Pendientes y límites

- **Ensayo nativo** (Codex): ejecutar `--verificar-firmas` antes de la primera ejecución real, porque `cFrameObj.GetPoints` se tomó de la ayuda CSI y no está reflejada. Comandos reproducibles en la documentación.
- **No acreditado:**
  - calidad de malla y rigidez;
  - getter de diafragma de nodos derivados;
  - presión variable o hidrostática.
- **Doble no es ETABS:** los dobles no acreditan ETABS real. La habilitación operativa no aprueba ingeniería.
