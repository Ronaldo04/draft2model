param([string]$Salida = 'tmp/diagnostico_api_etabs.json')
# Solo conexión a instancia activa y lecturas; no crea ni modifica modelos.
$ErrorActionPreference = 'Stop'
$etabsReport = [ordered]@{ fecha_utc = [DateTime]::UtcNow.ToString('o'); runtime = $PSVersionTable.PSVersion.ToString(); api = 'no_comprobada'; analisis = 'no_ejecutado' }
try {
    Add-Type -Path 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
    $etabsHelper = New-Object ETABSv1.Helper
    $etabsInstance = $etabsHelper.GetObject('CSI.ETABS.API.ETABSObject')
    if ($null -eq $etabsInstance) { throw 'No se obtuvo instancia activa de ETABS.' }
    $etabsVersion = ''
    $etabsNumeric = 0.0
    $etabsReturn = $etabsInstance.SapModel.GetVersion([ref]$etabsVersion, [ref]$etabsNumeric)
    if ($etabsReturn -ne 0) { throw "GetVersion devolvió $etabsReturn" }
    $etabsReport.api = 'lectura_real_correcta'
    $etabsReport.version = $etabsVersion
    $etabsReport.codigo_get_version = $etabsReturn
    $etabsReport.unidades = $etabsInstance.SapModel.GetPresentUnits().ToString()
    $etabsFilename = $etabsInstance.SapModel.GetModelFilename($true)
    $etabsReport.modelo_edb_abierto = [bool]($etabsFilename -and $etabsFilename -ne '(Untitled)')
} catch {
    $etabsReport.error = $_.Exception.Message
}
$etabsJson = $etabsReport | ConvertTo-Json -Depth 5
$etabsJson | Set-Content -LiteralPath $Salida -Encoding UTF8
Write-Output $etabsJson
if ($etabsReport.api -ne 'lectura_real_correcta') { exit 1 }
