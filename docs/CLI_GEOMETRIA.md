# Comandos de versiones geométricas

Estado: **entrega local de Claude, 16 de octubre de 2026, pendiente de revisión e integración por Codex.** Comandos de la CLI principal sobre la [gestión de versiones geométricas](GESTION_GEOMETRIA.md). No duplican su lógica: cada comando llama a una función pública de [`gestion_geometria.py`](../draft2model/gestion_geometria.py).

Implementación: [`draft2model/cli_geometria.py`](../draft2model/cli_geometria.py), registrada en [`__main__.py`](../draft2model/__main__.py) sin alterar los comandos existentes. Pruebas: [`tests/test_cli_geometria.py`](../tests/test_cli_geometria.py).

Estos comandos **no** convierten lecturas en geometría, generan planes o modelos, llaman a proveedores ni ejecutan ETABS. Una aprobación registrada no certifica seguridad estructural y no aprueba artefactos derivados.

## Comandos

Ejecutar con el Python de `.venv`. Por defecto la raíz es `data/private`; `--geometria` es siempre el ID de una versión (32 hexadecimales), nunca una ruta.

| Comando | Función | Escribe |
| --- | --- | --- |
| `importar-geometria --caso C --entrada geometria.json` | `importar_geometria` | Versión raíz nueva |
| `consultar-geometria --caso C --geometria ID [--json] [--salida nuevo.json]` | `consultar_version` | Solo `--salida`, que debe ser nuevo |
| `comprobar-geometria --caso C --geometria ID [--json]` | `comprobar_version` | Nada |
| `revisar-geometria --caso C --geometria PADRE --propuesta p.json --motivo M --fecha AAAA-MM-DD --revisor R` | `revisar_geometria` | Versión hija nueva |
| `aprobar-geometria --caso C --geometria ID --huella-esperada H --revisor R --fecha AAAA-MM-DD --motivo M --alcance A` | `aprobar_geometria` | Versión hija nueva |

Ejemplo sintético:

```powershell
$py = ".\.venv\Scripts\python.exe"
& $py -m draft2model importar-geometria --caso sintetico-001 --entrada examples\geometria_sintetica.json
& $py -m draft2model consultar-geometria --caso sintetico-001 --geometria <ID> --json
& $py -m draft2model revisar-geometria --caso sintetico-001 --geometria <ID> --propuesta revisada.json `
    --motivo "Se completa el espesor de M4." --fecha 2026-10-16 --revisor "Nombre declarado"
& $py -m draft2model aprobar-geometria --caso sintetico-001 --geometria <ID_REVISION> `
    --huella-esperada <huella_contenido revisada> --revisor "Nombre declarado" --fecha 2026-10-16 `
    --motivo "Geometría revisada frente a las láminas." --alcance "Niveles, nodos y muros."
```

### Detalles

- **Consulta y comprobación:** muestran comprobación, problemas de evidencia, `huella_contenido`, `sha256_geometria`, huella del expediente, originales verificados, cadena de padres, faltantes y bloqueos. Con `--json`, `consultar-geometria` imprime `geometria`, `metadatos`, `comprobacion` y `aviso`; `comprobar-geometria` imprime `ComprobacionGeometria.a_dict()`.
- **`--salida`:** se crea en modo exclusivo. Si el archivo existe o su carpeta no existe, se rechaza con código 1 y no se modifica nada.
- **Revisión:** `--propuesta` es la geometría **completa** en JSON, con `revision.estado: "borrador"` y `aprobacion: null`. Se lee con el lector estricto de bytes (sin claves repetidas ni `NaN`/`Infinity`). El padre no cambia; la nueva versión queda en borrador sin aprobación.
- **Aprobación:** exige de forma explícita la huella esperada, el revisor declarado, la fecha, el motivo y el alcance. La huella se obtiene de `consultar-geometria` sobre la versión revisada. Si no coincide con el contenido actual, la versión tiene faltantes o ya contiene una aprobación, se rechaza.
- **Caso:** se rechaza un caso que sea enlace o alias de otro expediente, como en los comandos de visión.

## Códigos de retorno

| Código | Significado |
| --- | --- |
| 0 | Operación completa; en consulta y comprobación, la versión supera la comprobación. |
| 1 | Solicitud inválida (`ErrorGestion`, `ValueError`, `OSError`): caso o ID inválido o inexistente, argumento obligatorio ausente o vacío, fecha o huella con formato inválido, archivo ilegible, JSON repetido o no finito, salida existente. |
| 2 | Geometría o evidencia rechazada (`ErrorEvidencia`) o versión que no supera la comprobación: original, expediente o versión alterados, huella que no coincide, faltantes al aprobar, aprobación declarada o heredada, otro caso, cambio de procedencia sintética. |

En los rechazos no se guarda ninguna versión. Los argumentos de texto de revisión y aprobación se validan dentro del comando para devolver código 1. `argparse` sigue terminando con código 2 ante errores de sintaxis propios (opción desconocida, falta `--caso` o `--geometria`) antes de ejecutar ninguna operación.

## Identidad y alcance

- `--revisor` es una declaración. La identidad y la competencia profesional **no se autentican**; la salida lo indica en cada operación.
- Las pruebas usan exclusivamente datos y revisores sintéticos. No deben registrarse aprobaciones sobre datos reales sin una revisión humana real ni declarando una identidad profesional ajena.
- Todo artefacto derivado debe citar el ID y la huella exactos de la versión de origen.

## Pruebas

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_cli_geometria -v
```

Si el sistema restringe la carpeta temporal, definir `TEMP` y `TMP` en una carpeta local (por ejemplo `tmp\cli_geometria_temp`).

Las 7 pruebas usan un PDF y geometrías sintéticas en carpetas temporales y cubren:

- importación, consulta, comprobación, revisión y aprobación por línea de comandos, con el padre intacto y la cadena completa;
- aprobación rechazada con faltantes, con huella errónea, con formato de huella inválido y sobre una versión ya aprobada;
- original y `geometria.json` alterados: código 2 en consulta, comprobación, revisión y aprobación;
- solicitudes inválidas con código 1: caso, ID, entrada o propuesta ausentes, argumentos vacíos y fecha inválida;
- propuestas rechazadas: JSON repetido o no finito (1); aprobación heredada, otro caso o cambio de procedencia sintética (2);
- `--salida` sin sobrescritura;
- ningún rechazo crea versiones, y ninguna operación modifica versiones anteriores.

Resultado local del 16 de octubre de 2026: 7 pruebas nuevas correctas y suite completa `unittest discover -s tests` con 302 pruebas correctas, sin omisiones.

## Limitaciones

- No hay comando para listar versiones; se consulta la carpeta `geometrias/` del caso.
- Las limitaciones de la gestión (concurrencia, coste de recalcular SHA256, uso de funciones privadas de extracciones) siguen vigentes; ver [GESTION_GEOMETRIA.md](GESTION_GEOMETRIA.md).
- No se integra con la interfaz web ni con `plan-modelado`; enlazar planes con la versión geométrica exacta queda para Codex.
