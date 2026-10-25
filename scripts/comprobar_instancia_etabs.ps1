param(
    [Parameter(Mandatory=$true)][int]$IdProcesoEtabs,
    [Parameter(Mandatory=$true)][string]$ModeloEsperado,
    [Parameter(Mandatory=$true)][string]$Salida,
    [switch]$Mostrar
)
# Solo consulta la instancia seleccionada y, si se pide, muestra su ventana.
# No crea objetos estructurales, guarda, analiza ni cierra ETABS.
$ErrorActionPreference='Stop'
$expected=[IO.Path]::GetFullPath($ModeloEsperado)
$target=[IO.Path]::GetFullPath($Salida)
if (-not [IO.Path]::IsPathRooted($ModeloEsperado) -or -not (Test-Path -LiteralPath $expected -PathType Leaf)) { throw 'Modelo absoluto existente requerido.' }
if (Test-Path -LiteralPath $target) { throw 'La salida ya existe; no se sobrescribe.' }
Add-Type -Path 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
$helper=New-Object ETABSv1.Helper
$app=$helper.GetObjectProcess('CSI.ETABS.API.ETABSObject',$IdProcesoEtabs)
if ($null -eq $app) { throw 'Instancia seleccionada no disponible.' }
$sap=$app.SapModel
$actual=$sap.GetModelFilename($true)
if (-not $actual -or [IO.Path]::GetFullPath($actual) -ine $expected) { throw 'La instancia no contiene la copia esperada; no se modifica su visibilidad.' }
if ($Mostrar -and -not $app.Visible()) {
    $ret=$app.Unhide()
    if ($ret -ne 0) { throw "Unhide devolvio $ret" }
}
$version='';$number=0.0
$ret=$sap.GetVersion([ref]$version,[ref]$number)
if ($ret -ne 0) { throw "GetVersion devolvio $ret" }
$record=[ordered]@{
    fecha_utc=[DateTime]::UtcNow.ToString('o');id_proceso=$IdProcesoEtabs
    version=$version;modelo=$actual;visible=[bool]$app.Visible()
    unidades_presentes=$sap.GetPresentUnits().ToString()
    puntos=$sap.PointObj.Count();areas=$sap.AreaObj.Count()
    modelo_bloqueado=[bool]$sap.GetModelIsLocked()
    geometria_modificada=$false;guardado=$false;analisis_ejecutado=$false;instancia_cerrada=$false
}
$raw=([Text.UTF8Encoding]::new($false)).GetBytes(($record|ConvertTo-Json -Depth 5))
$stream=[IO.File]::Open($target,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try{$stream.Write($raw,0,$raw.Length)}finally{$stream.Dispose()}
Write-Output ($record|ConvertTo-Json -Depth 5)
