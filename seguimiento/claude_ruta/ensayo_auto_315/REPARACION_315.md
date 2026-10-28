# Reparación única 315

- Corrida principal (08:07:38–08:08:17 UTC): falló en K04 (`Muro`) con «Cannot convert System.Double[] to System.Double». Causa: en PowerShell los nombres de variable no distinguen mayúsculas; `[double[]]$X` reutilizaba el parámetro `[double]$x`. Error de harness, no de ETABS.
- Instancia propia PID 14212: `ApplicationExit` = 0 y el proceso salió. Las sesiones ajenas 6988, 23928 y 38168 quedan intactas. No se guardó ningún EDB.
- Reparación: renombrar los arreglos del muro a `$AX/$AY/$AZ`. Sin cambios en la matriz, los casos, las predicciones ni la lectura. El script original se conserva como `ensayar_auto_315_corrida_principal.ps1`.
- Se ejecuta una sola vez en `corrida_reparacion/`. No habrá más reintentos.
