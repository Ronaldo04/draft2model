# Auditoría de gestión geométrica — 16 de octubre de 2026

Responsable: subagente de auditoría geométrica. Alcance inicial: lectura de `gestion_geometria.py`, contrato, documentación de gestión y sus pruebas. Tras informar los hallazgos, el coordinador asignó expresamente la corrección de `gestion_geometria.py` y sus pruebas. No se utilizaron datos reales. Las aprobaciones de las reproducciones corresponden exclusivamente a geometría sintética temporal; no constituyen validación de ingeniería.

## Estado tras correcciones

Los tres hallazgos siguientes quedan **corregidos y cubiertos por regresiones**. La sección de hallazgos conserva la reproducción y los resultados anteriores a la corrección como evidencia histórica. Ejecutar ahora esos bloques devuelve rechazo de las alteraciones.

- Cada eslabón de la cadena contrasta expediente, alcance y originales recalculados, además de geometría y fuente.
- Se contrastan versión del registro, contrato, identidad declarada, aviso y copias derivadas de procedencia, validación y estado. La comparación canónica distingue booleanos de números.
- El registro de aprobación debe coincidir con la aprobación de la geometría y conservar ambas limitaciones en `false`.
- Cada vínculo contrasta SHA256 geométrico y huella del contenido; tampoco admite cambiar la marca sintética entre padre e hija.
- Se valida la fecha ISO y la identidad declarada de la revisión persistida.

Validación posterior con el mismo comando: **59 pruebas, OK, 1 omitida** por imposibilidad de crear enlaces. Cinco nuevas pruebas ejercitan múltiples alteraciones de campos y comprueban que la consulta las informe y que nuevas escrituras sobre versiones alteradas sean rechazadas. Se conserva la API pública y el contrato de geometría de ingeniería. No se modificó la CLI.

Recomendación actual: integrar estas correcciones junto con las regresiones y ejecutar la verificación general del coordinador. Continúan las limitaciones documentadas sobre reescrituras deliberadas coherentes de todos los archivos y hashes, autenticación del revisor, concurrencia y carrera de enlaces. La comprobación no constituye aprobación estructural.

## Verificación ejecutada

Se ejecutaron las suites `tests.test_gestion_geometria` y `tests.test_validacion_geometria` con `.venv/Scripts/python.exe`: **54 pruebas, resultado OK, 1 omitida** porque el entorno no permitió crear junction ni symlink. Se fijó `tempfile.tempdir` en `tmp/auditoria_geometria`, dentro del espacio autorizado. Con el temporal predeterminado del sandbox, las 23 pruebas de gestión fallaban antes de entrar en sus operaciones por `PermissionError: WinError 5` en `ingreso.py:128` al renombrar el expediente. Es una diferencia de permisos del entorno; la repetición en el espacio autorizado pasó.

Comando reproducible (PowerShell, raíz del repositorio):

```powershell
.venv/Scripts/python.exe -c "import tempfile,pathlib,unittest; p=pathlib.Path('tmp/auditoria_geometria'); p.mkdir(parents=True,exist_ok=True); tempfile.tempdir=str(p.resolve()); suite=unittest.defaultTestLoader.loadTestsFromNames(['tests.test_gestion_geometria','tests.test_validacion_geometria']); r=unittest.TextTestRunner(verbosity=1).run(suite); raise SystemExit(not r.wasSuccessful())"
```

## Hallazgos reproducidos

### P1 — La comprobación de una hija acepta un padre rechazado directamente

Ubicación: `draft2model/gestion_geometria.py:345-365`. La comparación de `expediente_sha256` y `alcance` contra el expediente vigente solo se aplica a la versión solicitada. El bucle de padres llama `_comprobar_una`, que no comprueba esos campos.

Reproducción sintética: importar el ejemplo, crear una revisión, cambiar únicamente `expediente_sha256` del `version.json` de la importación por 64 ceros y su `alcance` por `{"estado":"otro"}`. Sin cambiar geometría, originales ni huellas adicionales, `comprobar_version(..., importacion_id).correcta` devuelve `False`, pero `comprobar_version(..., revision_id).correcta` devuelve **`True`**. Contradice la regla documental de comprobar cada padre completo. Las operaciones posteriores que llaman `_exigir` sobre la hija tampoco detectan el padre inconsistente.

Corrección recomendada: aplicar a cada eslabón las mismas comprobaciones contra el expediente y sus originales, y agregar prueba de rechazo transitivo.

### P1 — Metadatos de aprobación y procedencia incoherentes pasan como correctos

Ubicación: `draft2model/gestion_geometria.py:260-310`. La aprobación solo verifica su `huella_contenido`; no contrasta revisor, fecha, motivo o alcance con el bloque `revision.aprobacion` de la geometría, ni exige las marcas de limitación documentadas. Otros campos duplicados tampoco se contrastan con los valores recalculados.

Reproducciones sintéticas independientes: crear importación, revisión completa y aprobación mediante las utilidades de `CasoGeometria`; modificar solo uno de estos campos en `version.json`, conservar los demás bytes de la versión y llamar `comprobar_version`:

| Modificación aislada | Resultado observado |
| --- | --- |
| `procedencia = {"tipo":"plano","descripcion":"dato alterado"}` en una revisión sintética | `correcta=True`, problemas vacíos |
| `originales_verificados = []` | `correcta=True`, problemas vacíos |
| `validacion = {"disponible_para_modelado":true}` en una revisión borrador | `correcta=True`, problemas vacíos |
| `estado_revision_geometria = "aprobado"` en una revisión borrador | `correcta=True`, problemas vacíos |
| `version_registro = "999"` | `correcta=True`, problemas vacíos |
| Sustituir `aprobacion` por `{huella_contenido: huella actual, revisor_declarado: "Otro revisor", certifica_seguridad_estructural: true}` | `correcta=True`, problemas vacíos |

No fue necesario rehacer ninguna huella para obtener estos resultados. Por tanto, exceden la limitación ya declarada sobre ediciones deliberadas que rehagan todos los archivos y hashes. `ConsultaGeometria` devuelve esos metadatos alterados junto con una comprobación correcta, aunque `comp.validacion` sí se recalcula correctamente. Un consumidor que lea exclusivamente la geometría validada conserva su bloqueo, pero la evidencia de auditoría resulta contradictoria.

Corrección recomendada: validar el esquema y versión del registro, contrastar sus copias de procedencia, originales, validación y estado, y exigir la correspondencia exacta de los campos de aprobación con la geometría. Verificar las marcas `identidad_revisor`, `certifica_seguridad_estructural=False` y `aprueba_artefactos_derivados=False`. Incorporar regresiones de alteración de un solo campo sin regeneración de hashes.

### P2 — La huella de contenido del vínculo padre no se compara con el padre real

Ubicación: `draft2model/gestion_geometria.py:364-365`. El vínculo documentado contiene ID, SHA256 geométrico y huella de contenido, pero el recorrido solo compara el SHA256 geométrico.

Reproducción: importar y revisar el ejemplo; cambiar únicamente `revision/version.json → padre.huella_contenido` por 64 ceros. `comprobar_version(..., revision_id).correcta` sigue siendo **`True`**. No cambia ningún archivo padre ni se rehace ninguna huella.

Corrección recomendada: contrastar ambos hashes con el padre comprobado y validar la estructura del vínculo, también en revisiones.

## Reproducción de los hallazgos con las utilidades existentes

Este bloque puede ejecutarse con `.venv/Scripts/python.exe`; usa exclusivamente temporales sintéticos y restaura cada archivo antes del siguiente caso:

```python
import json, pathlib, tempfile
from tests.test_gestion_geometria import CasoGeometria, CASO
from draft2model import gestion_geometria as g

p = pathlib.Path('tmp/auditoria_geometria')
p.mkdir(parents=True, exist_ok=True)
tempfile.tempdir = str(p.resolve())
t = CasoGeometria()
t.setUp()
try:
    imp = t.importar()
    rev = t.revisar(imp.identificador)
    ap = t.aprobar(rev.identificador, rev.comprobacion.huella_contenido)
    ruta = imp.ruta / 'version.json'
    original = ruta.read_bytes()
    meta = json.loads(original)
    meta['expediente_sha256'] = '0' * 64
    meta['alcance'] = {'estado': 'otro'}
    ruta.write_text(json.dumps(meta), encoding='utf-8')
    print('padre directo:', g.comprobar_version(t.raiz, CASO, imp.identificador).correcta)
    print('hija:', g.comprobar_version(t.raiz, CASO, rev.identificador).correcta)
    ruta.write_bytes(original)
    for obj, campo, valor in [
        (rev, 'procedencia', {'tipo': 'plano', 'descripcion': 'dato alterado'}),
        (rev, 'originales_verificados', []),
        (rev, 'validacion', {'disponible_para_modelado': True}),
        (rev, 'estado_revision_geometria', 'aprobado'),
        (rev, 'version_registro', '999'),
        (ap, 'aprobacion', {
            'huella_contenido': ap.comprobacion.huella_contenido,
            'revisor_declarado': 'Otro revisor',
            'certifica_seguridad_estructural': True,
        }),
    ]:
        ruta = obj.ruta / 'version.json'
        original = ruta.read_bytes()
        meta = json.loads(original)
        meta[campo] = valor
        ruta.write_text(json.dumps(meta), encoding='utf-8')
        print(campo, g.comprobar_version(t.raiz, CASO, obj.identificador).correcta)
        ruta.write_bytes(original)
    ruta = rev.ruta / 'version.json'
    original = ruta.read_bytes()
    meta = json.loads(original)
    meta['padre']['huella_contenido'] = '0' * 64
    ruta.write_text(json.dumps(meta), encoding='utf-8')
    print('huella padre:', g.comprobar_version(t.raiz, CASO, rev.identificador).correcta)
    ruta.write_bytes(original)
finally:
    t.doCleanups()
```

## Recomendación inicial de integración (antes de corregir)

El flujo nominal sintético está cubierto y pasa. No aceptar todavía la afirmación de integridad completa de metadatos y cadena: resolver los hallazgos anteriores y volver a ejecutar estas regresiones antes de integrar la gestión geométrica en recorridos que consuman su comprobación como garantía de evidencia. La CLI sigue pendiente según la documentación leída; su implementación e integración corresponden al coordinador. Esta auditoría no acredita ETABS ni modelado estructural, ni aprobación de casos reales.
