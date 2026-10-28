param([Parameter(Mandatory=$true)][string]$Destino,[Parameter(Mandatory=$true)][string]$Registro)
# Creates a NEW ETABS instance and a NEW empty template for synthetic software tests.
# Never attaches to, closes or modifies an existing instance or user model.
$ErrorActionPreference='Stop'
$target=[IO.Path]::GetFullPath($Destino)
$reportPath=[IO.Path]::GetFullPath($Registro)
if (-not [IO.Path]::IsPathRooted($Destino) -or [IO.Path]::GetExtension($target) -ne '.edb') { throw 'Absolute new EDB destination required.' }
if ((Test-Path -LiteralPath $target) -or (Test-Path -LiteralPath $reportPath)) { throw 'Destination exists; no overwrite.' }
if (-not (Test-Path -LiteralPath ([IO.Path]::GetDirectoryName($target)) -PathType Container)) { throw 'Destination directory missing.' }
$before=@(Get-Process ETABS -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
$report=[ordered]@{started_utc=[DateTime]::UtcNow.ToString('o');synthetic_test=$true;existing_instances_modified=$false;analysis_executed=$false;status='failed'}
try {
    Add-Type -Path 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
    $helper=New-Object ETABSv1.Helper
    $created=$helper.CreateObjectProgID('CSI.ETABS.API.ETABSObject')
    if ($null -eq $created) { throw 'Failed to create a new API object.' }
    $code=$created.ApplicationStart()
    if ($code -ne 0) { throw "ApplicationStart returned $code" }
    $owned=@(Get-Process ETABS -ErrorAction Stop | Where-Object { $before -notcontains $_.Id } | ForEach-Object { $_.Id })
    $report.new_process_ids=$owned
    if ($owned.Count -ne 1) { throw 'Cannot identify exactly one new test instance; no model operations performed.' }
    $report.process_id=$owned[0]
    $code=$created.Hide()
    if ($code -ne 0) { throw "Hide returned $code" }
    $sap=$created.SapModel
    $code=$sap.InitializeNewModel([ETABSv1.eUnits]::kN_m_C)
    if ($code -ne 0) { throw "InitializeNewModel returned $code" }
    $code=$sap.File.NewBlank()
    if ($code -ne 0) { throw "File.NewBlank returned $code" }
    if (Test-Path -LiteralPath $target) { throw 'Destination appeared; no overwrite.' }
    $code=$sap.File.Save($target)
    if ($code -ne 0) { throw "File.Save returned $code" }
    $version='';$number=0.0
    $code=$sap.GetVersion([ref]$version,[ref]$number)
    if ($code -ne 0) { throw "GetVersion returned $code" }
    $stream=[IO.File]::OpenRead($target);$algorithm=[Security.Cryptography.SHA256]::Create()
    try { $sha=([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose();$algorithm.Dispose() }
    $report.version=$version;$report.units=$sap.GetPresentUnits().ToString();$report.template=$target;$report.sha256=$sha;$report.status='created'
} catch { $report.error=$_.Exception.Message }
$report.finished_utc=[DateTime]::UtcNow.ToString('o')
$json=$report | ConvertTo-Json -Depth 8
$bytes=([Text.UTF8Encoding]::new($false)).GetBytes($json)
$file=[IO.File]::Open($reportPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try { $file.Write($bytes,0,$bytes.Length) } finally { $file.Dispose() }
Write-Output $json
if ($report.status -ne 'created') { exit 1 }
