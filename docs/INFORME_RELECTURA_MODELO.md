# Incorporar la relectura del modelo al informe

Selecciona los resultados, su análisis y el modelo construido. En el panel de verificación del modelo, consulta el trabajo de relectura conservado. En el formulario del informe, activa **Incorporar la relectura seleccionada**. La selección es optativa y nunca se activa automáticamente. Cambiar modelo, análisis o trabajo obliga a confirmarla de nuevo.

El servidor conserva `relectura_modelo={trabajo,id,sha256_registro}`. Comprueba la vigencia del trabajo y del vínculo, reproduce la fuente del modelo y exige que el EDB construido corresponda al `sha256_entrada` del análisis. El EDB posterior al cálculo tiene su propia huella y no sustituye esa entrada. Vuelve a comprobar las fuentes al crear, consultar, aprobar documentalmente y descargar. Un cambio de fuente invalida el acceso; no se adopta automáticamente otra relectura.

El informe muestra el estado, modo real o doble, condición sintética, cobertura del plan, discrepancias y pendientes. Un trabajo aceptado significa evidencia conservada: puede tener resultado incompleto o discrepancias. Incorporarlo y aprobar documentalmente el informe no aprueba el modelo, el análisis ni ingeniería.

Validación local de esta integración: cuatro pruebas Python en `tests/test_informe_relectura_modelo.py`, con fixture y fuentes de relectura sustituidas explícitamente; controlador JavaScript real en `tests/informe_relectura_frontend.cjs`. No ejecutan ETABS ni usan proveedores. No sustituyen la revisión visual completa ni el ensayo de extremo a extremo con los planos de referencia.
