param([Parameter(Mandatory=$true)][string]$CarpetaTrabajo,[switch]$ConfirmarEnsayoSintetico)
# Catálogo de la DLL instalada sobre copia sintética propia; solo lectura, sin solver ni Save.
$ErrorActionPreference='Stop'
if(-not $ConfirmarEnsayoSintetico){throw 'Confirmación explícita requerida.'}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$work=[IO.Path]::GetFullPath($CarpetaTrabajo)
if(-not [IO.Path]::IsPathRooted($CarpetaTrabajo) -or -not $work.StartsWith((Join-Path $root 'tmp')+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Trabajo absoluto dentro de tmp requerido.'}
if(-not (Test-Path -LiteralPath $work -PathType Container) -or @(Get-ChildItem -LiteralPath $work -Force).Count -ne 0){throw 'Carpeta de trabajo existente y vacía requerida.'}
$source=Join-Path $root 'tmp\particion183\muro.edb'
$copy=Join-Path $work 'copia.edb'
function Hash([string]$p){$alg=[Security.Cryptography.SHA256]::Create();$f=[IO.File]::OpenRead($p);try{return [BitConverter]::ToString($alg.ComputeHash($f)).Replace('-','').ToLowerInvariant()}finally{$f.Dispose();$alg.Dispose()}}
function Check([int]$c,[string]$m){if($c -ne 0){throw "$m devolvio $c"}}
$sha=Hash $source
[IO.File]::Copy($source,$copy,$false)
if((Hash $copy) -ne $sha){throw 'La copia no coincide.'}
Add-Type -Path 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
$r=[ordered]@{datos_sinteticos=$true;solo_lectura=$true;guardado=$false;solver_ejecutado=$false;sha256_origen=$sha;instancia_nueva=$false;cierre_confirmado=$false;tablas=@();error=$null}
$app=$null
try{
    $old=@(Get-Process ETABS -ErrorAction SilentlyContinue|ForEach-Object Id)
    $helper=New-Object ETABSv1.Helper;$app=$helper.CreateObject('C:\Program Files\Computers and Structures\ETABS 21\ETABS.exe')
    Check ($app.ApplicationStart()) 'ApplicationStart';$r.instancia_nueva=$true
    $r.procesos_nuevos_observados=@(Get-Process ETABS -ErrorAction SilentlyContinue|Where-Object {$_.Id -notin $old}|ForEach-Object Id)
    $sap=$app.SapModel;Check ($sap.File.OpenFile($copy)) 'File.OpenFile copia propia'
    $r.unidades=$sap.GetPresentUnits().ToString()
    [int]$n=0;[string[]]$keys=@();[string[]]$names=@();[int[]]$imports=@();[bool[]]$empty=@()
    Check ($sap.DatabaseTables.GetAllTables([ref]$n,[ref]$keys,[ref]$names,[ref]$imports,[ref]$empty)) 'GetAllTables'
    if($keys.Length -ne $n -or $names.Length -ne $n -or $imports.Length -ne $n -or $empty.Length -ne $n){throw 'Catálogo truncado.'}
    $r.cantidad_tablas=$n
    $r.claves_catalogo=@($keys)
    for($i=0;$i -lt $n;$i++){
        if($keys[$i] -notmatch 'Area Load|Shell Load|Non.?uniform|Joint Pattern'){continue}
        [int]$version=0;[int]$nf=0;[string[]]$fk=@();[string[]]$fn=@();[string[]]$des=@();[string[]]$units=@();[bool[]]$can=@()
        Check ($sap.DatabaseTables.GetAllFieldsInTable($keys[$i],[ref]$version,[ref]$nf,[ref]$fk,[ref]$fn,[ref]$des,[ref]$units,[ref]$can)) 'GetAllFieldsInTable'
        if($fk.Length -ne $nf -or $units.Length -ne $nf -or $can.Length -ne $nf -or $des.Length -ne $nf){throw 'Campos truncados.'}
        $r.tablas+=@{clave=$keys[$i];nombre=$names[$i];tipo_importacion=$imports[$i];vacia=$empty[$i];version=$version;campos=$fk;unidades=$units;importables=$can;descripciones=$des}
    }
}catch{$r.error=$_.Exception.Message}
finally{
    if($null -ne $app){try{$rc=$app.ApplicationExit($false);$r.cierre_confirmado=($rc -eq 0);$r.retorno_cierre=$rc}catch{$r.error_cierre=$_.Exception.Message}}
    $r.sha256_origen_posterior=Hash $source;$r.sha256_copia_posterior=Hash $copy
    [IO.File]::WriteAllText((Join-Path $work 'registro.json'),($r|ConvertTo-Json -Depth 14),[Text.UTF8Encoding]::new($false))
}
if($null -ne $r.error -or -not $r.cierre_confirmado){exit 2}
Write-Output ('Catalogo inspeccionado: '+$r.tablas.Count+' tablas candidatas; sin modificaciones.')
