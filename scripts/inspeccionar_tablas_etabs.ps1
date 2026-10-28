param([Parameter(Mandatory=$true)][int]$IdProceso,[Parameter(Mandatory=$true)][string]$ModeloEsperado,[Parameter(Mandatory=$true)][string]$Registro)
$ErrorActionPreference='Stop'
if (Test-Path -LiteralPath $Registro) { throw 'Registro debe ser nuevo.' }
Add-Type -Path 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
$helper=New-Object ETABSv1.Helper;$app=$helper.GetObjectProcess('CSI.ETABS.API.ETABSObject',$IdProceso);$sap=$app.SapModel
if (-not [string]::Equals($sap.GetModelFilename($true),[IO.Path]::GetFullPath($ModeloEsperado),[StringComparison]::OrdinalIgnoreCase)) { throw 'Modelo distinto.' }
[int]$count=0;[string[]]$keys=@();[string[]]$names=@();[int[]]$import=@();[bool[]]$empty=@()
$code=$sap.DatabaseTables.GetAllTables([ref]$count,[ref]$keys,[ref]$names,[ref]$import,[ref]$empty)
if ($code -ne 0) { throw "GetAllTables codigo=$code" }
$result=@()
for ($i=0;$i -lt $count;$i++) {
 if ($keys[$i] -notmatch 'Response Spectrum|Damping') { continue }
 [int]$version=0;[int]$fieldsCount=0;[string[]]$fieldKeys=@();[string[]]$fieldNames=@();[string[]]$description=@();[string[]]$units=@();[bool[]]$canImport=@()
 $code=$sap.DatabaseTables.GetAllFieldsInTable($keys[$i],[ref]$version,[ref]$fieldsCount,[ref]$fieldKeys,[ref]$fieldNames,[ref]$description,[ref]$units,[ref]$canImport)
 $result+=@{tabla=$keys[$i];nombre=$names[$i];tipo_importacion=$import[$i];vacia=$empty[$i];retorno_campos=$code;version=$version;campos=$fieldKeys;unidades=$units;importables=$canImport}
}
$json=@{solo_lectura=$true;modelo=$ModeloEsperado;tablas=$result} | ConvertTo-Json -Depth 12
$bytes=(New-Object Text.UTF8Encoding($false)).GetBytes($json)
$stream=[IO.File]::Open($Registro,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try { $stream.Write($bytes,0,$bytes.Length) } finally { $stream.Dispose() }
Write-Output ('Tablas inspeccionadas: '+$result.Count)
