# Verificación integrada actual en copia limpia

Ejecutada por Codex el 18 de octubre de 2026 (Lima). Evidencia: `tmp/c146/copia_limpia.json`, su verificación interna y logs; resumen independiente `seguimiento/VERIFICACION_COPIA_148.json`.

```powershell
.venv/Scripts/python.exe scripts/verificar_copia_limpia.py --python tmp/instalacion_129/v/Scripts/python.exe --node C:/Users/HP/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe --salida tmp/c146
```

`--salida` exige una carpeta nueva. Para repetir deliberadamente una comprobación necesaria, elegir otra carpeta; no sobrescribir evidencias. Node es el ejecutable instalado en este equipo, no una ruta universal.

Resultado: código0, copia completa y `validacion_local_completa=true`; inventario estable durante ejecución. Python3.10.5 x64 en entorno aislado, user_site=false y módulo importado desde la copia. Dependencias/pip check, CLI y ejecución de script PowerShell pasaron. Suite: **850 pruebas Python OK en484.394s**, sin omisiones. Interfaz: **26 archivos Node OK**,0fallos,0omitidos,0TODO. Código, pruebas, scripts y ejemplos de la copia coinciden por SHA256 con los actuales al aceptar el resultado. La copia no hereda `tmp/`, expedientes privados ni el entorno del proyecto; utiliza el Python aislado129 ya instalado y probado por separado.

La pasada previa de Claude138 tuvo todos los comandos correctos pero inventario inestable por cuatro archivos nuevos de seguimiento de Codex. Se conserva como incompleta; esta copia independiente resuelve esa puerta sin cambiar el verificador ni ocultar resultados.

**Límites:** validación local del software con pruebas y dobles; `alcanza_validacion_piloto=false`. No ejecutó API ni ETABS real ni probó fidelidad física sobre los planos del usuario. QA143/145 acreditan navegador y JSON/PDF con datos sintéticos; tampoco sustituyen el ensayo real. Las adiciones posteriores de documentación/seguimiento no son nuevas fuentes ejecutables. No se declara completado el goal.

Siguiente puerta: `PLAN_ENSAYO_REFERENCIA.md`, paquete135 localizado, modelo/credencial/presupuesto locales, extracción y configuración físicas revisadas y recorrido ETABS del caso. Comparación manual aplazada por decisión del usuario. Instalación reproducible y uso: `GUIA_REPRODUCIBLE.md`.
