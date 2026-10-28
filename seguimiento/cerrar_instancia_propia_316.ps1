param([Parameter(Mandatory=$true)][int]$IdPropio,
      [Parameter(Mandatory=$true)][string]$InicioEsperado)
$ErrorActionPreference='Stop'
$p316=Get-Process -Id $IdPropio -ErrorAction SilentlyContinue
if($null -eq $p316){Write-Output 'PID propio ausente';exit 0}
if($p316.StartTime.ToUniversalTime().ToString('o') -ne $InicioEsperado){throw 'PID reutilizado: no cerrar'}
if($p316.Path -ne 'C:\Program Files\Computers and Structures\ETABS 21\ETABS.exe'){throw 'Proceso ajeno: no cerrar'}
# Último recurso tras180s de un fixture nuevo: nunca por nombre ni sobre otra sesión.
Stop-Process -Id $IdPropio -Force -ErrorAction Stop
Write-Output 'Cierre forzado del PID propio sintético tras timeout; no es ApplicationExit=0.'
