# Configuración de malla 0.4 en la web

Estado al 21 de octubre de 2026 (encargo 189). La preparación de malla 0.4 ([INTEGRACION_MALLA_ETABS.md](INTEGRACION_MALLA_ETABS.md)) se consulta desde el panel **Configurar el modelo**, en modo de solo lectura.

**Qué no hace:**
- No ejecuta ETABS.
- No escribe políticas.
- No infiere apoyos, diafragmas ni materiales.

## Uso

1. **Importar.** Selecciona el expediente e importa la configuración 0.4 en borrador con **Importar configuración JSON**. Debe incluir `nodos_derivados: []`, `subdivision_frames: []` y los `cortes_nivel` declarados (o `[]`). El selector muestra `Contrato 0.4.0 (malla)`. Las versiones 0.1, 0.2 y 0.3 siguen con su recorrido; en 0.2 y 0.3 se indica «desarrollo, sin ETABS».
2. **Consultar.** Pulsa **Consultar preparación de malla**. El servidor reproduce partición, compatibilidad, triangulación y cortes Z desde la versión **registrada**, no desde el JSON editado. Se muestran:
   - **Identidad:** caso, versión, huella de configuración y huella de preparación.
   - **Recuentos:** hosts, triángulos, nodos, nodos derivados, frames a subdividir, cortes y faltantes.
   - **Faltantes de política:** bloquean la aprobación.
   - **Nodos derivados** con su XYZ y la política declarada. Puede aparecer «FALTA política» o «DECLARADA EN OTRA POSICIÓN».
   - **Subdivisiones de frames:** requeridas, declaradas o distintas.
   - **Cortes Z:** declarados con su motivo y su fuente, nodos de corte y la indicación de que no crean pisos. También estrategia, fuente y conexiones de borde.
3. **Exportar.** **Exportar preparación revisable (JSON)** descarga `draft2model.exportacion_preparacion_malla` 0.1.0 con:
   - la identidad de la selección;
   - los faltantes;
   - las plantillas de **nodos pendientes**, con valores `null`;
   - las subdivisiones pendientes (`fuente: null`);
   - los cortes y la preparación completa.

   Es un documento de revisión: no es una configuración y no modifica nada.
4. **Completar a mano** en el JSON del editor `nodos_derivados` (con `xyz_m`, restricciones, diafragma o motivo, y fuente) y `subdivision_frames`, con fuentes reales. Guárdalo con **Guardar configuración en borrador**. Al editar el JSON se avisa de que la preparación visible es la de la versión registrada.
5. **Comprobar de nuevo** con **Consultar preparación de malla**. Sin faltantes, la aprobación existente queda disponible. La geometría 0.3 debe estar aprobada por huella. Una aprobación declarada **no certifica ingeniería** y preparar **no es ejecutar**.

**Garantías del cliente:**
- **Respuestas obsoletas:** se descartan por ticket, caso, versión y huella.
- **Cambio de selección o de expediente:** borra la preparación visible.
- **Texto, no HTML:** todo el contenido JSON se muestra con `textContent`, nunca como HTML.

## API (solo lectura)

`GET /api/configuracion/malla?caso=<caso>&version=<id>`

- **Acceso:** el mismo que las rutas vecinas: cabecera `X-Revision-Session`, `Host`/`Origin` locales y `Cache-Control: no-store`.
- **Respuesta** (de `ServicioConfiguracion.malla`): `{id, preparacion, faltantes, apto_para_adaptador, aprueba_ingenieria: false, expediente_sha256}`.
- **Rechazos:**
  - un caso o versión inválidos, ausentes o repetidos, o una versión alterada en disco: `409`, con un mensaje genérico y sin rutas;
  - **cualquier parámetro distinto de `caso` y `version`** (intento de edición por consulta): `409`;
  - `POST`: `404`;
  - una sesión inválida: `403`.

## Pruebas

```powershell
$env:TEMP=(Resolve-Path tmp/claude_ui_189).Path; $env:TMP=$env:TEMP
.venv/Scripts/python.exe -m unittest -v tests.test_ui_malla
node tests/ui_malla_frontend.cjs
```

- **HTTP** (`tests/test_ui_malla.py`): versiones reales en disco (geometría 0.3 y configuración 0.4 importada, revisada y aprobada, con dos hosts, una viga y un corte Z).
  - el borrador muestra faltantes, incluidos nodos `MC_`, y la versión aprobada no tiene ninguno;
  - caso y versión inválidos;
  - edición por consulta y `POST` rechazados, sin cambios en disco;
  - versión alterada;
  - página y cliente sin `innerHTML`.
- **Node** (`tests/ui_malla_frontend.cjs`):
  - legado 0.1/0.3;
  - sin selección;
  - consulta 0.4 con faltantes, nodos, subdivisiones y cortes;
  - texto con `<script>` mostrado literalmente;
  - exportación coherente y sin políticas;
  - aviso al editar;
  - cambio de selección;
  - respuesta obsoleta descartada;
  - cambio de expediente;
  - aprobación 0.4 bloqueada por faltantes.

## Límites

- No se hizo QA visual en navegador ni ensayo de motor.
- La preparación es de solo lectura: no guarda políticas ni las propone con valores.
- Las tablas de presión y el motor son de Codex.
