# Lectura de configuración sobre copia propia: sin solver, sin Save ni modelo manual.
$ErrorActionPreference='Stop'
$root318=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$work318=Join-Path $root318 'tmp/configuracion_318_reparacion'
if(Test-Path -LiteralPath $work318){throw 'Salida318 ya existe; no repetir automáticamente'}
[void][IO.Directory]::CreateDirectory($work318)
$source318=Join-Path $root318 'data/private/pueblo-libre-002/analisis_etabs/7203c79a3ece4438b36d267ba80f3c4b/analizado.EDB'
$copy318=Join-Path $work318 'copia_inspeccion.EDB'
function Hash318([string]$path318){
    $a318=[Security.Cryptography.SHA256]::Create();$f318=[IO.File]::OpenRead($path318)
    try{return [BitConverter]::ToString($a318.ComputeHash($f318)).Replace('-','').ToLowerInvariant()}
    finally{$f318.Dispose();$a318.Dispose()}
}
function Check318([int]$code318,[string]$method318){if($code318 -ne 0){throw "$method318 devolvió $code318"}}
$expected318='42371308a03d4f1bac8f5ed3aa5daf0421cdf3de27ff823f8f582c13ad2af394'
$before318=Hash318 $source318
if($before318 -ne $expected318){throw 'El EDB original difiere del análisis aceptado; no abrir'}
[IO.File]::Copy($source318,$copy318,$false)
if((Hash318 $copy318) -ne $before318){throw 'La copia difiere'}
$r318=[ordered]@{caso='pueblo-libre-002';analisis='7203c79a3ece4438b36d267ba80f3c4b';sha256_original=$before318;solver_ejecutado=$false;guardado=$false;llamadas_remotas=0;error=$null;cierre=$null}
function Publish318{[IO.File]::WriteAllText((Join-Path $work318 'registro.json'),($r318|ConvertTo-Json -Depth 10),[Text.UTF8Encoding]::new($false))}
Publish318
Add-Type -Path 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
$app318=$null;$own318=$null;$start318=$null
try{
    $previous318=@(Get-Process ETABS -ErrorAction SilentlyContinue|ForEach-Object Id)
    $helper318=New-Object ETABSv1.Helper
    $app318=$helper318.CreateObject('C:\Program Files\Computers and Structures\ETABS 21\ETABS.exe')
    Check318 ($app318.ApplicationStart()) 'ApplicationStart'
    $new318=@(Get-Process ETABS -ErrorAction SilentlyContinue|Where-Object {$_.Id -notin $previous318})
    if($new318.Count -ne 1){throw 'No se identifica exactamente una instancia propia'}
    $own318=$new318[0].Id;$start318=$new318[0].StartTime.ToUniversalTime().ToString('o')
    $r318.proceso_propio=@{pid=$own318;inicio_utc=$start318};Publish318
    $sap318=$app318.SapModel
    Check318 ($sap318.File.OpenFile($copy318)) 'OpenFile copia'
    $r318.unidades_antes=$sap318.GetPresentUnits().ToString()
    Check318 ($sap318.SetPresentUnits([ETABSv1.eUnits]::kN_m_C)) 'SetPresentUnits solo memoria'
    $r318.unidades_lectura=$sap318.GetPresentUnits().ToString()
    [double]$merge318=0
    Check318 ($sap318.GetMergeTol([ref]$merge318)) 'GetMergeTol'
    $r318.tolerancia_union_m=$merge318
    [string]$version318='';[double]$number318=0
    Check318 ($sap318.GetVersion([ref]$version318,[ref]$number318)) 'GetVersion'
    $r318.version_aplicacion=$version318
    Publish318
}catch{$r318.error=$_.Exception.Message;$r318.posicion_error=$_.InvocationInfo.PositionMessage}
finally{
    $close318=[ordered]@{application_exit=$null;pid=$own318;salio=$null}
    if($null -ne $app318){try{$close318.application_exit=$app318.ApplicationExit($false)}catch{$close318.error=$_.Exception.Message}}
    if($null -ne $own318){$p318=Get-Process -Id $own318 -ErrorAction SilentlyContinue
        if($p318){if($p318.StartTime.ToUniversalTime().ToString('o') -eq $start318){$close318.salio=$p318.WaitForExit(60000)}else{$close318.salio='pid_reutilizado'}}else{$close318.salio=$true}}
    $r318.cierre=$close318
    $r318.sha256_original_despues=Hash318 $source318
    $r318.sha256_copia_despues=Hash318 $copy318
    Publish318
}
if($r318.error -or $r318.sha256_original_despues -ne $before318 -or $r318.cierre.application_exit -ne 0 -or $r318.cierre.salio -ne $true){exit 2}
Write-Output 'Configuración318 leída; original íntegro, sin solver ni guardado, cierre propio0.'
