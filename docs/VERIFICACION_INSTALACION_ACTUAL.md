# Verificación de instalación actual

Fecha local: 18 de octubre de 2026 (Lima). Ejecución iniciada a las 15:24:33; sello del verificador `2026-10-18T20:24:33.541554+00:00`. **Instalación aislada offline aceptada para Windows x64/CPython 3.10 y demo sintética; no aceptación global del producto.**

Se leyeron la guía, el script y el lock antes de ejecutar. Se usaron los wheels locales existentes de `tmp/wheels_clean_001` y una carpeta nueva `tmp/instalacion_129`. Hubo una sola ejecución; terminó con **código 0** sin necesidad de escalación al host ni cambios de políticas. El entorno `.venv` existente se conservó. `PYTHONDONTWRITEBYTECODE=1` evitó nuevas cachés Python en las fuentes.

## Comando y entorno

Desde la raíz del proyecto en PowerShell:

```powershell
$env:PYTHONDONTWRITEBYTECODE = '1'
.\.venv\Scripts\python.exe -B scripts/verificar_instalacion_limpia.py --wheels tmp/wheels_clean_001 --salida tmp/instalacion_129
```

Para repetir, elegir otra salida que no exista. El script no admite reutilizar esta carpeta.

| Componente | Resultado observado |
| --- | --- |
| Sistema/intérprete | Windows, Python 3.10.5 de 64 bits. |
| Entorno creado | `tmp/instalacion_129/v`; `include-system-site-packages = false`; intérprete aislado. |
| Pillow | 12.3.0, instalado desde wheel local. |
| PyMuPDF | 1.28.2, instalado desde wheel local. |
| Instalación pip | `--no-index --find-links tmp/wheels_clean_001 --require-hashes -r requirements-win-py310.lock --disable-pip-version-check`. |
| Red/proveedor/ETABS | No ejecutados por este recorrido; `sin_red:true`, `vision_real:false`, `analisis_etabs:false`. |

Se confirmó la versión de los dos paquetes mediante `importlib.metadata` usando el Python nuevo. Sus SHA256 locales coinciden con el lock que pip exigió:

- Pillow: `300557495eb45ebb8aec96c2da9c4be642fbf7cd937278b4013ba894ea8eb0eb`.
- PyMuPDF: `ebd244918798502d7b4504c90410d1711a4d7675a32584ca30f1bab419ecbffe`.

No se descargó ningún wheel ni se agregó una dependencia al proyecto.

## Resultados terminales comprobados

| Paso | Código | Evidencia bajo `tmp/instalacion_129` |
| --- | --- | --- |
| Crear venv | 0 | `crear_entorno.log` (sin salida de error). |
| Instalar wheels con hashes | 0 | `instalar.log`: ambos paquetes instalados correctamente desde la carpeta local. |
| `pip check` | 0 | `dependencias.log`: sin requisitos rotos. |
| Arranque CLI | 0 | `arranque.log`: ayuda del punto de entrada. |
| Crear demo integrada | 0 | `demo.log` y carpeta `demo/`. |
| Verificar demo existente | 0 | `verificar_demo.log`: `correcta:true`, `corridas_completadas:6`, `datos_sinteticos:true`. |

Se leyó y contrastó [verificacion.json](../tmp/instalacion_129/verificacion.json): `completa:true`, `entorno_aislado:true` y seis comprobaciones terminales con código 0. Se volvió a leer el JSON de verificación de demo y se comprobó la existencia de cada log, sin aceptar solo el mensaje de lanzamiento.

La [comprobación independiente](../tmp/instalacion_129/comprobacion_independiente.json) conserva versiones, códigos, hashes de logs/wheels y el contraste de 45 fuentes seleccionadas antes/después. No cambiaron durante esta ejecución. El inventario previo está en `tmp/instalacion_129_fuentes_previas.json`. Se inventariaron requisitos/lock/script, helper/demo y núcleos Python seleccionados; **no se congeló ni auditó todo el checkout HTTP/UI**, que seguía en desarrollo paralelo.

La salida de informe de la demo está en `tmp/instalacion_129/demo/private/demo-integrada-sintetica/demo/informe_borrador/`, con JSON/HTML/PDF. Es un informe de fixture; no se hizo revisión visual de su presentación en este encargo.

## Alcance y pendientes

Esta ejecución comprueba instalación de dependencias fijadas en un entorno nuevo, arranque y creación/verificación de la demo de software. Sus seis corridas tienen datos, revisores y aprobaciones fabricados; no son seis análisis estructurales. No acredita precisión visual, proveedor real, nueva ejecución ETABS, HTTP/UI, revisión de ingeniería o comparación manual del caso.

No se ejecutó suite completa ni copia de distribución. La evidencia no convierte la copia100 fallida en aceptada ni sustituye la próxima verificación del hito estable. El lock es específico de Windows x64/CPython 3.10; otras plataformas requieren sus wheels/hashes compatibles. Los wheels y la evidencia `tmp` no están incluidos automáticamente en una distribución pública y deben preservarse cuando sea necesario reproducir offline.
