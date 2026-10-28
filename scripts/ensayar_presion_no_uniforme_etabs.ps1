param([Parameter(Mandatory=$true)][string]$CarpetaTrabajo,[switch]$ConfirmarEnsayoSintetico,[switch]$ModeloCortado)
# Prueba explícitamente sintética de importación y equilibrio; no configuración del proyecto real.
$ErrorActionPreference='Stop'
if(-not $ConfirmarEnsayoSintetico){throw 'Confirmación sintética requerida.'}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'));$work=[IO.Path]::GetFullPath($CarpetaTrabajo)
if(-not [IO.Path]::IsPathRooted($CarpetaTrabajo) -or -not $work.StartsWith((Join-Path $root 'tmp')+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Trabajo absoluto dentro de tmp requerido.'}
if(-not (Test-Path -LiteralPath $work -PathType Container) -or @(Get-ChildItem -LiteralPath $work -Force).Count -ne 0){throw 'Trabajo vacío existente requerido.'}
function Check([int]$c,[string]$m){if($c -ne 0){throw "$m devolvio $c"}}
function Hash([string]$p){$alg=[Security.Cryptography.SHA256]::Create();$f=[IO.File]::OpenRead($p);try{return [BitConverter]::ToString($alg.ComputeHash($f)).Replace('-','').ToLowerInvariant()}finally{$f.Dispose();$alg.Dispose()}}
$source=Join-Path $root 'tmp\particion183\muro.edb'
$expected='9427e97d193822d71b7d4f35da08477bea533ec828d6dc2839ccd30dabbd0075';$expectedAreas=12
if($ModeloCortado){
    $source=Join-Path $root 'tmp\particion186\muro.edb'
    $record=([IO.File]::ReadAllText((Join-Path $root 'tmp\particion186\registro.json'))|ConvertFrom-Json)
    if($record.cierre_confirmado -ne $true -or $null -ne $record.error){throw 'Ensayo de corte previo sin cierre o con error.'}
    $expected=($record.guardados|Where-Object caso -eq 'muro').sha256
    $bundle=([IO.File]::ReadAllText((Join-Path $root 'tmp\triangulaciones186.json'))|ConvertFrom-Json)
    $expectedAreas=($bundle.escenarios|Where-Object caso -eq 'muro').triangulacion.triangulos.Count
}
$sha=Hash $source
if($sha -ne $expected){throw 'Modelo sintético fuente cambiado.'}
$copy=Join-Path $work 'presion.edb';[IO.File]::Copy($source,$copy,$false)
Add-Type -Path 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
$r=[ordered]@{datos_sinteticos=$true;sha256_original=$sha;instancia_nueva=$false;cierre_confirmado=$false;solver_ejecutado=$false;error=$null;hipotesis='Solo ensayo software: muro XZ4x3 con hueco1x1, gamma10kN/m3, nivel1.5m, presión hacia -Y, empotramiento de nodos de borde z0.'}
$app=$null
try{
    $old=@(Get-Process ETABS -ErrorAction SilentlyContinue|ForEach-Object Id)
    $helper=New-Object ETABSv1.Helper;$app=$helper.CreateObject('C:\Program Files\Computers and Structures\ETABS 21\ETABS.exe')
    Check ($app.ApplicationStart()) 'ApplicationStart';$r.instancia_nueva=$true
    $r.procesos_nuevos_observados=@(Get-Process ETABS -ErrorAction SilentlyContinue|Where-Object {$_.Id -notin $old}|ForEach-Object Id)
    $sap=$app.SapModel;Check ($sap.File.OpenFile($copy)) 'OpenFile copia propia'
    if([IO.Path]::GetFullPath($sap.GetModelFilename($true)) -ine $copy){throw 'Modelo distinto de la copia propia.'}
    if($sap.GetModelIsLocked()){Check ($sap.SetModelIsLocked($false)) 'Unlock solo copia propia de ensayo'}
    Check ($sap.SetPresentUnits([ETABSv1.eUnits]::kN_m_C)) 'SetPresentUnits construcción propia'
    Check ($sap.LoadPatterns.Add('HIDRO',[ETABSv1.eLoadPatternType]::Other,0,$false)) 'LoadPatterns.Add sin peso propio'
    Check ($sap.LoadCases.StaticLinear.SetCase('HIDRO')) 'StaticLinear.SetCase'
    [string[]]$loadType=@('Load');[string[]]$loadName=@('HIDRO');[double[]]$loadScale=@(1)
    Check ($sap.LoadCases.StaticLinear.SetLoads('HIDRO',1,[ref]$loadType,[ref]$loadName,[ref]$loadScale)) 'StaticLinear.SetLoads'
    [int]$np=0;[string[]]$pn=@();Check ($sap.PointObj.GetNameList([ref]$np,[ref]$pn)) 'PointObj.GetNameList'
    $coords=@{};$r.apoyos=@()
    foreach($p in $pn){
        [double]$x=0;[double]$y=0;[double]$z=0
        Check ($sap.PointObj.GetCoordCartesian($p,[ref]$x,[ref]$y,[ref]$z,'Global')) 'GetCoordCartesian'
        $coords[$p]=@($x,$y,$z)
        if([Math]::Abs($z) -lt 1e-12){[bool[]]$fixed=@($true,$true,$true,$true,$true,$true);Check ($sap.PointObj.SetRestraint($p,[ref]$fixed,[ETABSv1.eItemType]::Objects)) 'SetRestraint propio';$r.apoyos+=$p}
    }
    if($r.apoyos.Count -lt 2){throw 'Faltan apoyos de ensayo.'}
    [int]$na=0;[string[]]$an=@();Check ($sap.AreaObj.GetNameList([ref]$na,[ref]$an)) 'AreaObj.GetNameList'
    if($na -ne $expectedAreas){throw 'Cantidad de triángulos distinta al ensayo sintético de origen.'}
    [int]$ver=1;[string[]]$fields=@('UniqueName','LoadPattern','Dir','A','B','C','D','Restriction');[string[]]$data=@()
    foreach($name in $an){$data+=@($name,'HIDRO','Global-Y','0','0','10','-15','Zero Positive Values')}
    Check ($sap.DatabaseTables.SetTableForEditingArray('Area Load Assignments - Non-uniform',[ref]$ver,[ref]$fields,$na,[ref]$data)) 'SetTableForEditingArray'
    [int]$fatal=0;[int]$errors=0;[int]$warn=0;[int]$info=0;[string]$log=''
    Check ($sap.DatabaseTables.ApplyEditedTables($true,[ref]$fatal,[ref]$errors,[ref]$warn,[ref]$info,[ref]$log)) 'ApplyEditedTables'
    $r.importacion=@{fatales=$fatal;errores=$errors;avisos=$warn;informativos=$info;log=$log}
    if($fatal -ne 0 -or $errors -ne 0 -or $warn -ne 0){throw 'Importación con errores/avisos; no se analiza.'}
    Check ($sap.File.Save($copy)) 'Save copia propia'
    [string[]]$fk=@();[string[]]$included=@();[string[]]$flat=@();[int]$version=0;[int]$nr=0
    Check ($sap.DatabaseTables.GetTableForDisplayArray('Area Load Assignments - Non-uniform',[ref]$fk,'',[ref]$version,[ref]$included,[ref]$nr,[ref]$flat)) 'Relectura tabla'
    $r.tabla=@{version=$version;campos=$included;registros=$nr;datos=$flat;unidades=$sap.GetPresentUnits().ToString()}
    if($nr -ne $expectedAreas -or $flat.Length -ne $nr*$included.Length){throw 'Carga releída incompleta.'}
    Check ($sap.Analyze.SetRunCaseFlag('',$false,$true)) 'Desmarcar casos'
    Check ($sap.Analyze.SetRunCaseFlag('HIDRO',$true,$false)) 'Marcar HIDRO'
    Check ($sap.Analyze.RunAnalysis()) 'RunAnalysis';$r.solver_ejecutado=$true
    Check ($sap.Results.Setup.DeselectAllCasesAndCombosForOutput()) 'DeselectAllCasesAndCombosForOutput'
    Check ($sap.Results.Setup.SetCaseSelectedForOutput('HIDRO',$true)) 'SetCaseSelectedForOutput'
    [int]$count=0;[string[]]$obj=@();[string[]]$elm=@();[string[]]$cases=@();[string[]]$steps=@();[double[]]$sn=@()
    [double[]]$f1=@();[double[]]$f2=@();[double[]]$f3=@();[double[]]$m1=@();[double[]]$m2=@();[double[]]$m3=@()
    Check ($sap.Results.JointReact('ALL',[ETABSv1.eItemTypeElm]::GroupElm,[ref]$count,[ref]$obj,[ref]$elm,[ref]$cases,[ref]$steps,[ref]$sn,[ref]$f1,[ref]$f2,[ref]$f3,[ref]$m1,[ref]$m2,[ref]$m3)) 'JointReact'
    $r.reacciones=@()
    for($i=0;$i -lt $count;$i++){
        if($cases[$i] -ne 'HIDRO' -or -not $coords.ContainsKey($obj[$i])){throw 'Reacción ajena al caso/nodo esperado.'}
        $r.reacciones+=@{nodo=$obj[$i];elemento=$elm[$i];caso=$cases[$i];paso=$steps[$i];xyz_m=$coords[$obj[$i]];fuerza=@($f1[$i],$f2[$i],$f3[$i]);momento=@($m1[$i],$m2[$i],$m3[$i])}
    }
    $r.unidades_reacciones=$sap.GetPresentUnits().ToString()
}catch{$r.error=$_.Exception.Message;$r.error_posicion=$_.InvocationInfo.PositionMessage}
finally{
    if($null -ne $app){try{$rc=$app.ApplicationExit($false);$r.cierre_confirmado=($rc -eq 0);$r.retorno_cierre=$rc}catch{$r.error_cierre=$_.Exception.Message}}
    $r.sha256_original_posterior=Hash $source
    [IO.File]::WriteAllText((Join-Path $work 'registro.json'),($r|ConvertTo-Json -Depth 16),[Text.UTF8Encoding]::new($false))
}
if($null -ne $r.error -or -not $r.cierre_confirmado){exit 2}
Write-Output 'Caso HIDRO sintético importado y analizado; evaluar balance, no aprueba ingeniería.'
