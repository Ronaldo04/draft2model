param(
    [Parameter(Mandatory=$true)][int]$IdProceso,
    [Parameter(Mandatory=$true)][string]$ModeloEsperado,
    [Parameter(Mandatory=$true)][string]$Registro
)
# Lectura exclusiva: no abre, guarda, analiza ni modifica modelos.
$ErrorActionPreference = 'Stop'
if (Test-Path -LiteralPath $Registro) { throw 'El registro debe ser nuevo.' }
Add-Type -Path 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
$helper = New-Object ETABSv1.Helper
$app = $helper.GetObjectProcess('CSI.ETABS.API.ETABSObject', $IdProceso)
$sap = $app.SapModel
$opened = $sap.GetModelFilename($true)
if (-not [string]::Equals([IO.Path]::GetFullPath($opened), [IO.Path]::GetFullPath($ModeloEsperado), [StringComparison]::OrdinalIgnoreCase)) {
    throw 'El modelo abierto no coincide con el esperado.'
}
$data = [ordered]@{ solo_lectura=$true; proceso=$IdProceso; modelo=$opened; unidades=$sap.GetPresentUnits().ToString(); objetos=[ordered]@{} }
foreach ($name in @('PointObj','FrameObj','AreaObj','PropMaterial','PropFrame','PropArea','LoadPatterns','LoadCases','RespCombo')) {
    [int]$number = 0
    [string[]]$names = @()
    $interface = if ($name -eq 'RespCombo') { 'cCombo' } else { 'c'+$name }
    $method = ([type]('ETABSv1.'+$interface)).GetMethods() | Where-Object Name -eq 'GetNameList'
    $parameters = $method.GetParameters()
    [object[]]$values = @([int]0, [string[]]@())
    for ($index=2; $index -lt $parameters.Length; $index++) {
        if (-not $parameters[$index].IsOptional) { throw "Firma no soportada: $interface.GetNameList" }
        $values += $parameters[$index].DefaultValue
    }
    $code = $method.Invoke($sap.$name, $values)
    $number = $values[0]; $names = $values[1]
    if ($code -ne 0 -or $number -ne $names.Length) { throw "Lectura fallida: $name codigo=$code" }
    $data.objetos[$name] = [ordered]@{ cantidad=$number; nombres=@($names) }
}
$data.puntos = @()
foreach ($name in $data.objetos.PointObj.nombres) {
    [double]$x=0; [double]$y=0; [double]$z=0
    $code=$sap.PointObj.GetCoordCartesian($name,[ref]$x,[ref]$y,[ref]$z,'Global')
    if ($code -ne 0) { throw "No se pudo leer punto $name" }
    $data.puntos += [ordered]@{ nombre=$name; x=$x; y=$y; z=$z }
}
$data.fecha_utc=[DateTime]::UtcNow.ToString('o')
$json=$data | ConvertTo-Json -Depth 12
$stream=[IO.File]::Open($Registro,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try {
    $bytes=(New-Object Text.UTF8Encoding($false)).GetBytes($json)
    $stream.Write($bytes,0,$bytes.Length)
} finally { $stream.Dispose() }
Write-Output $json
