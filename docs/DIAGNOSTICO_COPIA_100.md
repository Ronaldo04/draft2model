# Diagnóstico de la copia limpia 100

Fecha: 18 de octubre de 2026. No se encontraron archivos `AGENTS.md` en el proyecto durante este diagnóstico.

## Evidencia y clasificación

La ejecución de referencia está en `tmp/copia_limpia_100/fuentes/tmp/verificacion/611035a112b64c24b823b909d700c65c/suite.log`: **668 pruebas, 343.032 s, 18 fallos, 4 errores y 9 omisiones**. Sigue siendo una ejecución fallida; no se acredita el proyecto ni el piloto con ese resultado.

Los fallos examinados se concentran en `DespachoNetFalsoTests` de `test_ejecutor_etabs` y `DespachoDinamicoTests` de `test_operaciones_dinamicas`. El proceso termina con salida 1 sin publicar respuesta; el cliente conserva `ErrorPuente.tipo == "puente"`. Las aserciones esperaban errores de API/precondición o datos de despacho que solo pueden producirse después de iniciar el script. Por ello el resultado observado no demuestra un defecto de firmas, despacho, relectura o semántica estructural: el script no confirmó haber alcanzado esas operaciones. Tampoco permite afirmar que esas operaciones funcionan.

En este entorno, una sonda independiente y benigna ejecutada **con `-File`**, sin cargar el backend, ensamblados ni ETABS, terminó también con salida 1:

```text
AuthorizationManager check failed.
CategoryInfo: SecurityError
FullyQualifiedErrorId: UnauthorizedAccess
```

La evidencia de esa sonda es `tmp/diagnostico_copia100_e889ac5becdf41b190c7426fc3d7fccc/sonda.json`; conserva comando, salida, error y declaraciones de que no se modificó política ni se ejecutó ETABS. Además, `Get-ExecutionPolicy -List` falló con `SecurityException: Requested registry access is not allowed`. No se pudo leer la política efectiva: no se afirma qué ámbito o configuración la impone. Es un bloqueo del host/entorno compatible con los fallos de la copia, no un diagnóstico de una política concreta.

Una repetición focal de `DespachoNetFalsoTests.test_plan_completo_despachado_en_orden` encontró antes otro límite de sandbox: `WinError 5` al renombrar una carpeta temporal en `registrar_expediente`. No llegó al puente. No se sustituyó el renombrado atómico ni se relajaron sus garantías para hacer pasar la prueba.

El log histórico no incluye el stderr del puente de cada caso, y sus temporales ya se limpiaron; por tanto **no se demuestra que todos los 22 resultados fallidos tengan exclusivamente la misma causa**. Se necesita repetir los dos módulos en un entorno donde la ejecución normal de scripts y las operaciones atómicas estén autorizadas, conservando los errores originales. Las 9 omisiones previas permanecen pendientes; este trabajo no las reclasifica ni las convierte en éxitos.

## Corrección focal

`scripts/verificar_proyecto.py` incorporó en Windows una comprobación independiente `powershell_scripts`: escribe una sonda inocua y la ejecuta con Windows PowerShell 5.1 mediante `-NoProfile -NonInteractive -File`. Comprueba tanto el código cero como una marca exacta de salida. No cambia políticas, no usa `Bypass`, no cambia a `-Command`/`-EncodedCommand` para ejecutar el archivo ni omite la suite cuando la sonda falla.

El informe conserva su log y agrega `bloqueos_entorno`. Una sonda bloqueada, sin marca o un host que no arranca impiden `validacion_local_completa`; los códigos de pruebas y omisiones se mantienen. Una salida cero sin marca recibe código 126; no poder iniciar el proceso recibe 127. Esta corrección mejora el diagnóstico del verificador: no repara ni autentica el backend ETABS. No se modificaron los tests de despacho, firmas, puente, política ni backend.

Se verificaron **7 pruebas focales de `tests.test_verificar_proyecto`**, incluidas política bloqueada, salida cero sin marca y error de arranque; todas pasan. Son pruebas del contrato del verificador con subprocess simulado, no ejecución real del puente. No se repitió la suite completa, no hubo red, instalación, Computer Use ni ETABS real.

## Reproducir

### Contraste posterior126: sandbox y host

La misma sonda preservada se ejecutó sin cambiar políticas: dentro del sandbox falló con AuthorizationManager/SecurityError y código1 (tmp/sonda_ps_codex_126.log); en el host autorizado emitió DRAFT2MODEL_SONDA_PS51_FILE_OK y código0 (tmp/sonda_ps_host_codex_126.log). Después, los dos módulos afectados `tests.test_ejecutor_etabs` y `tests.test_operaciones_dinamicas` pasaron31pruebas en60.224s en ese host (tmp/puente_host_codex_126.log), con motores .NET simulados y sin análisis ETABS real. Esto resuelve la reproducción focal de esos módulos en entorno autorizado; no modifica el resultado histórico100 ni sustituye una nueva copia limpia completa sobre las fuentes actuales.

Desde la raíz del proyecto, las pruebas del verificador:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_verificar_proyecto -v
```

La sonda preservada puede repetirse sin cambiar la política:

```powershell
& "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe" -NoProfile -NonInteractive -File .\tmp\diagnostico_copia100_e889ac5becdf41b190c7426fc3d7fccc\sonda_powershell.ps1
```

Para continuar la investigación en el entorno autorizado por el responsable —sin modificar ni eludir su política— ejecutar únicamente los módulos afectados:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_ejecutor_etabs tests.test_operaciones_dinamicas -v
```

Si el entorno vuelve a bloquearlos, registrar ese bloqueo y conservar el resultado fallido. No cambiar las expectativas de las pruebas ni presentar una omisión como validación. Cuando se autorice posteriormente una verificación completa, el comando existente `python scripts/verificar_proyecto.py --salida tmp/verificacion_repetida.json --temporales RUTA_CORTA_AUTORIZADA` incluirá automáticamente la nueva sonda y conservará sus registros.
