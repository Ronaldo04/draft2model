# Configuración local y pruebas visibles de ETABS

Preferencia del usuario: solo Google y OpenAI para IA. ETABS no utiliza ninguna de esas claves: su interfaz está instalada localmente junto al programa y requiere licencia válida.

En este equipo se comprobaron `ETABS.exe`21.1.0.3261 y `ETABSv1.dll`1.29.0.0 en `C:\Program Files\Computers and Structures\ETABS 21`. El puente del proyecto usa Windows PowerShell5.1 y el objeto `CSI.ETABS.API.ETABSObject`. No requiere un servicio ETABS en nube ni otra APIkey. No se cambian políticas de Windows para ejecutar scripts.

## Prueba visible

El puente existente abre una **instancia nueva** y conserva la copia abierta. El lector independiente, en cambio, crea una instancia propia, puede ocultarla y la cierra al finalizar. Esto explica las ventanas breves; no es evidencia por sí sola de construcción/análisis correctos.

Desde la carpeta del proyecto, para abrir una copia nueva de un EDB conocido:

```powershell
.venv/Scripts/python.exe -m draft2model etabs --trabajo tmp/etabs_interactivo --bloqueo tmp/d2/motor.lock abrir-copia --plantilla RUTA_ORIGINAL.edb --sha256 SHA256_VERIFICADO --destino CARPETA_NUEVA --instancia nueva --ejecutar
```

`--destino` debe ser una carpeta nueva. El SHA se contrasta antes/después de copiar y el puente comprueba qué archivo abrió. No utilizar `--instancia activa` para estos ensayos: la instancia nueva evita reemplazar un trabajo del usuario. El puente conserva la instancia abierta y devuelve su `id_proceso`; no guardar sobre el original.

Después, diagnóstico dirigido al PID que devolvió la apertura:

```powershell
.venv/Scripts/python.exe -m draft2model etabs --trabajo tmp/etabs_interactivo --bloqueo tmp/d2/motor.lock diagnosticar --id-proceso PID_DE_LA_PRUEBA --ejecutar
```

`scripts/comprobar_instancia_etabs.ps1` añade la consulta de visibilidad y conteos, exigiendo PID y ruta de la copia exacta. `-Mostrar` solo muestra esa ventana si está oculta; no guarda, analiza ni cierra el programa. La evidencia se escribe a un JSON nuevo. Compartir el bloqueo del motor para todas las operaciones del mismo ensayo; no crear otro para evitar una incertidumbre pendiente.

## Qué demuestra y qué falta

- Abrir y leer versión/modelo/unidades demuestra comunicación con la instalación/licencia en ese momento.
- Ver objetos de un EDB previo demuestra apertura de ese archivo, no construcción de nuevas capacidades.
- Construir requiere un plan/configuración/geometría vigentes y compatibles; analizar y revisar resultados son pasos separados. Las capacidades en desarrollo no se habilitan por abrir ETABS.
- El ensayo172 de relectura real se detuvo porque el EDB se abrió en N_mm_C y el lector exigía kN_m_C. Queda pendiente normalización/conversión explícita y verificable. No modificar unidades silenciosamente en una lectura ni presentar ese ensayo como aprobado.
- El modelo manual del usuario queda reservado para comparación después de producir los resultados finales. No se necesita ni se utiliza para esta prueba sintética visible.

Fuentes de interfaz: [ApplicationStart](https://docs.csiamerica.com/help-files/etabs-api-2016/html/da3c2062-cb41-dc93-8df2-64725899285e.htm), [visibilidad y Unhide](https://docs.csiamerica.com/help-files/etabs-api-2016/html/ce343756-311b-22b3-707b-fdac8a23e821.htm). Esas referencias explican el ciclo de vida; las firmas actuales se contrastaron por reflexión de la DLL instalada.
