<#
.SYNOPSIS
SOLO LECTURA. Muestra el vocabulario real y filas de las tablas espectrales y de damping de ETABS 21.1.
Requiere Windows PowerShell 5.1. Preparado por Claude para que Codex lo revise y lo ejecute.

.DESCRIPTION
Se conecta a la instancia ETABS cuyo modelo abierto es -ModeloEsperado (comprobado con GetModelFilename)
y registra en un JSON nuevo:
  1. Para 'Functions - Response Spectrum - User Defined', 'Load Case Definitions - Response Spectrum' y
     'Load Case Definitions - Damping - Modal': GetAllFieldsInTable con FieldKey, FieldName, Description,
     UnitsString e IsImportable. Las descripciones deberían revelar los textos admitidos de ModalCombo,
     RigidResp y DampType, que el plan todavía no ha observado.
  2. Las mismas tablas con GetTableForDisplayArray (filas existentes; hasta 200 por tabla).
  3. Por cada caso espectral: GetModalCase, GetLoads, GetEccentricity, GetDampType, GetDampConstant,
     GetModalComb_1 y GetDirComb. Por cada caso modal Eigen: GetNumberModes, GetParameters y GetLoads.

Solo llama a métodos Get*/Count y a GetModelFilename/GetPresentUnits. No llama a Set*, Apply*, Add*,
Delete*, Save, OpenFile, RunAnalysis ni ApplicationExit, ni cambia la selección de visualización.
Si el modelo abierto no tiene casos espectrales, las tablas de caso y damping saldrán vacías: para ver
filas reales debe abrirse primero, por el procedimiento habitual de Codex, una copia de un modelo que ya
contenga un caso espectral; este script no abre ni modifica archivos.

.EXAMPLE
powershell -NoProfile -NonInteractive -File tmp\claude_lectura_damping.ps1 -Salida tmp\d1\lectura_damping_vocabulario.json -ModeloEsperado C:\...\copia.EDB -IdProceso 12345
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Salida,
    [Parameter(Mandatory = $true)][string]$ModeloEsperado,
    [int]$IdProceso = 0,
    [string]$Dll = 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$Tablas = @('Functions - Response Spectrum - User Defined', 'Load Case Definitions - Response Spectrum',
            'Load Case Definitions - Damping - Modal', 'Area Load Assignments - Non-uniform')
$MaxFilas = 200

if ($PSVersionTable.PSVersion.Major -ne 5) { throw 'Se requiere Windows PowerShell 5.1.' }
$Salida = [System.IO.Path]::GetFullPath($Salida)
if (Test-Path -LiteralPath $Salida) { throw "La salida ya existe; no se sobrescribe: $Salida" }

$asm = [System.Reflection.Assembly]::LoadFrom($Dll)
$token = (@($asm.GetName().GetPublicKeyToken() | ForEach-Object { $_.ToString('x2') }) -join '')
if ($token -ne '453d728ef24c6f5e') { throw 'La DLL no está firmada por CSI.' }
$helper = $asm.CreateInstance('ETABSv1.Helper')
if ($IdProceso -gt 0) { $etabs = $helper.GetObjectProcess('CSI.ETABS.API.ETABSObject', $IdProceso) }
else { $etabs = $helper.GetObject('CSI.ETABS.API.ETABSObject') }
if ($null -eq $etabs) { throw 'No se obtuvo una instancia de ETABS.' }
$sap = $etabs.SapModel
$abierto = $sap.GetModelFilename($true)
if ([System.IO.Path]::GetFullPath($abierto).TrimEnd('\') -ine [System.IO.Path]::GetFullPath($ModeloEsperado).TrimEnd('\')) {
    throw "El modelo abierto ('$abierto') no es el esperado ('$ModeloEsperado'); no se lee nada."
}

$informe = [ordered]@{
    solo_lectura = $true; preparado_por = 'Claude'; fecha_utc = [DateTime]::UtcNow.ToString('o')
    modelo = $abierto; dll_version = (Get-Item -LiteralPath $Dll).VersionInfo.FileVersion
    unidades = $sap.GetPresentUnits().ToString(); tablas = @(); casos_espectrales = @(); casos_modales = @()
}

$db = $sap.DatabaseTables
foreach ($tabla in $Tablas) {
    $version = 0; $numero = 0
    [string[]]$claves = @(); [string[]]$nombres = @(); [string[]]$descripciones = @(); [string[]]$unidades = @(); [bool[]]$importables = @()
    $retCampos = $db.GetAllFieldsInTable($tabla, [ref]$version, [ref]$numero, [ref]$claves, [ref]$nombres, [ref]$descripciones, [ref]$unidades, [ref]$importables)
    $campos = @()
    for ($i = 0; $i -lt @($claves).Count; $i++) {
        $campos += [ordered]@{ clave = $claves[$i]; nombre = $nombres[$i]; descripcion = $descripciones[$i]; unidades = $unidades[$i]; importable = $importables[$i] }
    }
    [string[]]$pedidos = @(''); $versionDisplay = 0; [string[]]$incluidos = @(); $registros = 0; [string[]]$datos = @()
    $retFilas = $db.GetTableForDisplayArray($tabla, [ref]$pedidos, '', [ref]$versionDisplay, [ref]$incluidos, [ref]$registros, [ref]$datos)
    $filas = @()
    $n = @($incluidos).Count
    for ($r = 0; $r -lt [Math]::Min($registros, $MaxFilas); $r++) {
        $fila = [ordered]@{}
        for ($c = 0; $c -lt $n; $c++) { $fila[$incluidos[$c]] = $datos[$r * $n + $c] }
        $filas += $fila
    }
    $informe.tablas += [ordered]@{ tabla = $tabla; retorno_campos = $retCampos; version = $version; campos = $campos
                                   retorno_filas = $retFilas; registros = $registros; filas = $filas }
}

$lc = $sap.LoadCases
foreach ($par in @(@(4, 'espectral'), @(3, 'modal'))) {
    $tipo = [Enum]::ToObject($asm.GetType('ETABSv1.eLoadCaseType'), [int]$par[0])
    $cuantos = 0; [string[]]$casos = @()
    $ret = $lc.GetNameList([ref]$cuantos, [ref]$casos, $tipo)
    foreach ($caso in @($casos)) {
        if ($par[1] -eq 'espectral') {
            $rs = $lc.ResponseSpectrum
            $modal = ''; $n = 0; [string[]]$ln = @(); [string[]]$fn = @(); [double[]]$sf = @(); [string[]]$cs = @(); [double[]]$ang = @()
            $ecc = 0.0; $tipoAmort = 0; $amort = 0.0; $comb = 0; $f1 = 0.0; $f2 = 0.0; $rigida = 0; $td = 0.0; $dir = 0; $sfDir = 0.0
            $informe.casos_espectrales += [ordered]@{
                caso = $caso; retorno_lista = $ret
                GetModalCase = [ordered]@{ retorno = $rs.GetModalCase($caso, [ref]$modal); ModalCase = $modal }
                GetLoads = [ordered]@{ retorno = $rs.GetLoads($caso, [ref]$n, [ref]$ln, [ref]$fn, [ref]$sf, [ref]$cs, [ref]$ang)
                                       LoadName = @($ln); Func = @($fn); SF = @($sf); CSys = @($cs); Ang = @($ang) }
                GetEccentricity = [ordered]@{ retorno = $rs.GetEccentricity($caso, [ref]$ecc); Eccen = $ecc }
                GetDampType = [ordered]@{ retorno = $rs.GetDampType($caso, [ref]$tipoAmort); DampType = $tipoAmort }
                GetDampConstant = [ordered]@{ retorno = $rs.GetDampConstant($caso, [ref]$amort); Damp = $amort }
                GetModalComb_1 = [ordered]@{ retorno = $rs.GetModalComb_1($caso, [ref]$comb, [ref]$f1, [ref]$f2, [ref]$rigida, [ref]$td)
                                             MyType = $comb; F1 = $f1; F2 = $f2; PeriodicRigidCombType = $rigida; Td = $td }
                GetDirComb = [ordered]@{ retorno = $rs.GetDirComb($caso, [ref]$dir, [ref]$sfDir); MyType = $dir; SF = $sfDir }
            }
        } else {
            $me = $lc.ModalEigen
            $max = 0; $min = 0; $shift = 0.0; $corte = 0.0; $tol = 0.0; $auto = 0
            $nl = 0; [string[]]$lt = @(); [string[]]$lnm = @(); [double[]]$tp = @(); [bool[]]$sc = @()
            $informe.casos_modales += [ordered]@{
                caso = $caso; retorno_lista = $ret
                GetNumberModes = [ordered]@{ retorno = $me.GetNumberModes($caso, [ref]$max, [ref]$min); MaxModes = $max; MinModes = $min }
                GetParameters = [ordered]@{ retorno = $me.GetParameters($caso, [ref]$shift, [ref]$corte, [ref]$tol, [ref]$auto)
                                            EigenShiftFreq = $shift; EigenCutOff = $corte; EigenTol = $tol; AllowAutoFreqShift = $auto }
                GetLoads = [ordered]@{ retorno = $me.GetLoads($caso, [ref]$nl, [ref]$lt, [ref]$lnm, [ref]$tp, [ref]$sc)
                                       NumberLoads = $nl; LoadType = @($lt); LoadName = @($lnm) }
            }
        }
    }
}

$json = ConvertTo-Json -InputObject $informe -Depth 10
$flujo = New-Object System.IO.FileStream($Salida, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
try {
    $bytes = (New-Object System.Text.UTF8Encoding($false)).GetBytes($json)
    $flujo.Write($bytes, 0, $bytes.Length)
} finally { $flujo.Dispose() }
Write-Output "Lectura registrada (solo lectura): $Salida"
