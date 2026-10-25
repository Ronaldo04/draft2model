param([Parameter(Mandatory=$true)][string]$Destino,[Parameter(Mandatory=$true)][string]$Registro,[Parameter(Mandatory=$true)][string]$Caso)
# Creates a NEW ETABS instance and a NEW empty template for a REAL case (not synthetic metadata).
# Never attaches to, closes or modifies an existing instance or user model. The only instance it closes is the API object
# it created itself (ApplicationExit on that object), also after partial start-up or ambiguous process identification.
# Success (exit 0, status 'created') requires: file saved, SHA-256 computed, own close returned 0 and, when the own PID is
# known, the process is verified gone. Any other outcome exits non-zero with a structured receipt (fallback to stderr).
$ErrorActionPreference='Stop'
$report=[ordered]@{started_utc=[DateTime]::UtcNow.ToString('o');case_id=$Caso;synthetic_test=$false;purpose='empty template for the real case';
    attaches_to_existing_instances=$false;analysis_executed=$false;status='failed';stage='validation';file_saved=$false;
    own_instance_created=$false;own_close_attempted=$false;own_close_return=$null;own_close_confirmed=$false;own_process_gone=$null;errors=@()}
$target=$null;$reportPath=$null;$created=$null;$before=@()
function Add-Error([string]$Stage,[string]$Message){$script:report.errors+=@([ordered]@{stage=$Stage;message=$Message})}
try {
    $target=[IO.Path]::GetFullPath($Destino)
    $reportPath=[IO.Path]::GetFullPath($Registro)
    if (-not [IO.Path]::IsPathRooted($Destino) -or [IO.Path]::GetExtension($target) -ne '.edb') { throw 'Absolute new EDB destination required.' }
    if (-not [IO.Path]::IsPathRooted($Registro) -or [IO.Path]::GetExtension($reportPath) -ne '.json') { throw 'Absolute new JSON receipt destination required.' }
    if ($Caso -notmatch '^[a-z0-9][a-z0-9-]{1,62}$') { throw 'Invalid case id.' }
    if ((Test-Path -LiteralPath $target) -or (Test-Path -LiteralPath $reportPath)) { throw 'Destination exists; no overwrite.' }
    foreach ($dir in @([IO.Path]::GetDirectoryName($target),[IO.Path]::GetDirectoryName($reportPath))) {
        if (-not (Test-Path -LiteralPath $dir -PathType Container)) { throw "Destination directory missing: $dir" }
    }
    $before=@(Get-Process ETABS -ErrorAction SilentlyContinue | ForEach-Object { $_.Id })
    $report.preexisting_instances=$before
    $report.stage='start'
    Add-Type -Path 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
    $helper=New-Object ETABSv1.Helper
    $created=$helper.CreateObjectProgID('CSI.ETABS.API.ETABSObject')
    if ($null -eq $created) { throw 'Failed to create a new API object.' }
    $report.own_instance_created=$true
    $code=$created.ApplicationStart()
    if ($code -ne 0) { throw "ApplicationStart returned $code" }
    $owned=@(Get-Process ETABS -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id } | ForEach-Object { $_.Id })
    $report.new_process_ids=$owned
    if ($owned.Count -ne 1) { throw 'Cannot identify exactly one new instance; no model operations performed (own object will be closed).' }
    $report.process_id=$owned[0]
    $report.stage='model'
    $code=$created.Hide(); if ($code -ne 0) { throw "Hide returned $code" }
    $sap=$created.SapModel
    $code=$sap.InitializeNewModel([ETABSv1.eUnits]::kN_m_C); if ($code -ne 0) { throw "InitializeNewModel returned $code" }
    $code=$sap.File.NewBlank(); if ($code -ne 0) { throw "File.NewBlank returned $code" }
    if (Test-Path -LiteralPath $target) { throw 'Destination appeared; no overwrite.' }
    $code=$sap.File.Save($target); if ($code -ne 0) { throw "File.Save returned $code" }
    $report.file_saved=$true;$report.template=$target
    $version='';$number=0.0
    $code=$sap.GetVersion([ref]$version,[ref]$number); if ($code -ne 0) { throw "GetVersion returned $code" }
    $report.version=$version;$report.units=$sap.GetPresentUnits().ToString()
} catch { Add-Error $report.stage $_.Exception.Message }
# Close ONLY the object created here (also after partial start-up); never by PID difference.
if ($null -ne $created) {
    $report.own_close_attempted=$true
    try { $rc=$created.ApplicationExit($false); $report.own_close_return=[int]$rc; $report.own_close_confirmed=($rc -eq 0) }
    catch { Add-Error 'close' $_.Exception.Message }
    if ($null -ne $report.process_id) {
        $gone=$false
        for ($i=0; $i -lt 60 -and -not $gone; $i++) { if (Get-Process -Id $report.process_id -ErrorAction SilentlyContinue) { Start-Sleep -Milliseconds 500 } else { $gone=$true } }
        $report.own_process_gone=$gone
        if (-not $gone) { Add-Error 'close' "Own process $($report.process_id) still alive after close; it was not killed." }
    } elseif ($report.own_instance_created) {
        Add-Error 'close' 'Own process id unknown: closure requested through the own API object, disappearance not verifiable by PID.'
    }
}
if ($report.file_saved) {
    try {
        $stream=[IO.File]::OpenRead($target);$algorithm=[Security.Cryptography.SHA256]::Create()
        try { $report.sha256=([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
        finally { $stream.Dispose();$algorithm.Dispose() }
    } catch { Add-Error 'hash' $_.Exception.Message }
}
$report.remaining_preexisting=@(Get-Process ETABS -ErrorAction SilentlyContinue | Where-Object { $before -contains $_.Id } | ForEach-Object { $_.Id })
$ok=($report.errors.Count -eq 0 -and $report.file_saved -and $null -ne $report.sha256 -and $report.own_close_confirmed -and $report.own_process_gone -eq $true)
$report.status=$(if ($ok) { 'created' } elseif ($report.file_saved) { 'file_saved_incomplete' } else { 'failed' })
$report.finished_utc=[DateTime]::UtcNow.ToString('o')
$json=$report | ConvertTo-Json -Depth 8
$written=$false
if ($null -ne $reportPath) {
    try {
        $bytes=([Text.UTF8Encoding]::new($false)).GetBytes($json)
        $file=[IO.File]::Open($reportPath,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
        try { $file.Write($bytes,0,$bytes.Length); $file.Flush() } finally { $file.Dispose() }
        $written=$true
    } catch { [Console]::Error.WriteLine('RECEIPT_NOT_WRITTEN: ' + $_.Exception.Message) }
}
Write-Output $json
if (-not $written) { [Console]::Error.WriteLine($json); exit 3 }
if (-not $ok) { exit 1 }
