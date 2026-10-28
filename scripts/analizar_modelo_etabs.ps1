param(
    [Parameter(Mandatory=$true)][string]$Solicitud,
    [Parameter(Mandatory=$true)][string]$Respuesta,
    [Parameter(Mandatory=$true)][string]$Sha256Solicitud
)
# Instancia NUEVA de ensayo/trabajo. Nunca GetObject ni modelo activo del usuario.
$ErrorActionPreference='Stop'
$Utf8=New-Object Text.UTF8Encoding($false)
function Hash-Archivo([string]$Path) {
    $stream=[IO.File]::OpenRead($Path);$hash=[Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($hash.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose();$hash.Dispose() }
}
function Exigir-Cero($Code,[string]$Name) { if ($Code -ne 0) { throw "$Name codigo=$Code" } }
function Traza([string]$Event,$Data) {
    $row=[ordered]@{evento=$Event;datos=$Data;utc=[DateTime]::UtcNow.ToString('o')}
    [IO.File]::AppendAllText((Join-Path (Split-Path $Respuesta) 'traza_analisis.jsonl'),(($row | ConvertTo-Json -Depth 10 -Compress)+"`n"),$Utf8)
}
$code=1;$request=$null;$pidNuevo=$null;$owned=$null;$inicioPropio=$null;$app=$null
$out=[ordered]@{contrato='draft2model.etabs_respuesta';version_contrato='0.1.0';operacion='analizar_modelo';
    modo_ejecucion='real';estado='error';datos=@{};avisos=@();error=$null}
try {
    if (Test-Path -LiteralPath $Respuesta) { throw 'La respuesta ya existe.' }
    if ((Hash-Archivo $Solicitud) -ne $Sha256Solicitud) { throw 'Solicitud alterada.' }
    $request=[IO.File]::ReadAllText($Solicitud,$Utf8) | ConvertFrom-Json
    $out.id_solicitud=$request.id
    if ($request.operacion -ne 'analizar_modelo' -or $request.modo_configurado -ne 'real') { throw 'Solicitud ajena.' }
    if ((Hash-Archivo $request.entrada) -ne $request.sha256_entrada) { throw 'Entrada alterada.' }
    if (Test-Path -LiteralPath $request.destino) { throw 'El destino ya existe.' }
    if (@($request.casos).Count -eq 0) { throw 'Faltan casos.' }
    $working=Join-Path (Split-Path $Solicitud) 'trabajo_motor.edb'
    [IO.File]::Copy($request.entrada,$working,$false)
    if ((Hash-Archivo $working) -ne $request.sha256_entrada) { throw 'Copia distinta de la entrada.' }
    Add-Type -Path $request.dll
    $before=@(Get-Process ETABS -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    $helper=New-Object ETABSv1.Helper
    $app=$helper.CreateObjectProgID('CSI.ETABS.API.ETABSObject')
    Exigir-Cero ($app.ApplicationStart()) 'ApplicationStart'
    $new=@(Get-Process ETABS -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id })
    if ($new.Count -ne 1) { throw 'No se pudo identificar una sola instancia nueva.' }
    $pidNuevo=$new[0].Id
    $owned=Get-Process -Id $pidNuevo -ErrorAction Stop
    $inicioPropio=$owned.StartTime.ToUniversalTime().ToString('o')
    Traza 'instancia_nueva' @{id_proceso=$pidNuevo;inicio_proceso_utc=$inicioPropio}
    Exigir-Cero ($app.Hide()) 'Hide'
    $sap=$app.SapModel
    Exigir-Cero ($sap.File.OpenFile($working)) 'OpenFile'
    $opened=$sap.GetModelFilename($true)
    if (-not [string]::Equals([IO.Path]::GetFullPath($opened),[IO.Path]::GetFullPath($working),[StringComparison]::OrdinalIgnoreCase)) {
        throw 'La copia abierta no coincide.'
    }
    $unidadesIniciales=$sap.GetPresentUnits().ToString()
    Exigir-Cero ($sap.SetPresentUnits([ETABSv1.eUnits]::kN_m_C)) 'SetPresentUnits'
    if ($sap.GetPresentUnits().ToString() -ne 'kN_m_C') { throw 'No se pudieron establecer las unidades revisadas.' }
    Traza 'unidades_api' @{antes=$unidadesIniciales;despues=$sap.GetPresentUnits().ToString()}
    [int]$count=0;[string[]]$names=@()
    # El SDK usa 0 como filtro "todos", aunque no figura entre nombres del enum.
    $todosTipos=[Enum]::ToObject([ETABSv1.eLoadCaseType],0)
    Exigir-Cero ($sap.LoadCases.GetNameList([ref]$count,[ref]$names,$todosTipos)) 'LoadCases.GetNameList'
    foreach ($name in $request.casos) { if ($names -notcontains $name) { throw "Caso ausente: $name" } }
    Exigir-Cero ($sap.Analyze.SetRunCaseFlag('', $false, $true)) 'Desactivar casos'
    foreach ($name in $request.casos) { Exigir-Cero ($sap.Analyze.SetRunCaseFlag($name,$true,$false)) 'Activar caso' }
    # CSI liga resultados auxiliares al nombre del modelo. Guardar el destino
    # ANTES de calcular, para que todo el paquete use ese mismo nombre.
    Exigir-Cero ($sap.File.Save($request.destino)) 'Save antes de analizar'
    Traza 'inicio_analisis' @{casos=@($request.casos)}
    Exigir-Cero ($sap.Analyze.RunAnalysis()) 'RunAnalysis'
    [int]$statusCount=0;[string[]]$statusNames=@();[int[]]$statuses=@()
    Exigir-Cero ($sap.Analyze.GetCaseStatus([ref]$statusCount,[ref]$statusNames,[ref]$statuses)) 'GetCaseStatus'
    $selected=[ordered]@{}
    foreach ($name in $request.casos) {
        $index=[Array]::IndexOf($statusNames,[string]$name)
        if ($index -lt 0 -or $statuses[$index] -ne 4) { throw "Caso sin resultado completo: $name" }
        $selected[$name]=$statuses[$index]
    }
    Traza 'estado_antes_guardado' @{bloqueado=$sap.GetModelIsLocked();modelo=$sap.GetModelFilename($true);estados=$selected}
    # Nombre vacío pide guardar el modelo actual, evitando otro Save As.
    Exigir-Cero ($sap.File.Save('')) 'Save modelo actual'
    Traza 'estado_despues_guardado' @{bloqueado=$sap.GetModelIsLocked();modelo=$sap.GetModelFilename($true)}
    Exigir-Cero ($sap.File.OpenFile($request.destino)) 'Reabrir resultado persistido'
    Exigir-Cero ($sap.SetPresentUnits([ETABSv1.eUnits]::kN_m_C)) 'Unidades al reabrir'
    [int]$persistedCount=0;[string[]]$persistedNames=@();[int[]]$persistedStates=@()
    Exigir-Cero ($sap.Analyze.GetCaseStatus([ref]$persistedCount,[ref]$persistedNames,[ref]$persistedStates)) 'GetCaseStatus persistido'
    foreach ($name in $request.casos) {
        $index=[Array]::IndexOf($persistedNames,[string]$name)
        if ($index -lt 0 -or $persistedStates[$index] -ne 4) { throw "Resultados no persistidos al reabrir: $name" }
    }
    if ((Hash-Archivo $request.entrada) -ne $request.sha256_entrada) { throw 'Entrada revisada cambió.' }
    [string]$version='';[double]$number=0
    Exigir-Cero ($sap.GetVersion([ref]$version,[ref]$number)) 'GetVersion'
    $out.datos=[ordered]@{id_proceso=$pidNuevo;version_etabs=$version;modelo_abierto=$sap.GetModelFilename($true);
        guardado=@{ruta=$request.destino;sha256=(Hash-Archivo $request.destino)};
        sha256_entrada=$request.sha256_entrada;casos_ejecutados=@($request.casos);estados_casos=$selected;
        analisis_ejecutado=$true;aprueba_resultados=$false;inicio_proceso_utc=$inicioPropio;instancia_cerrada=$false}
    Traza 'fin_analisis' $out.datos
    $out.estado='ok';$code=0
} catch {
    $out.error=@{tipo='analisis';mensaje=$_.Exception.Message;id_proceso=$pidNuevo}
    try { Traza 'error' $out.error } catch { }
} finally {
    # Cierre SOLO de la instancia nueva que este puente creó (mismo PID y mismo inicio), sin guardar: el resultado ya está
    # guardado y reabierto arriba. Un cierre no confirmado convierte la respuesta en error (nunca éxito con instancia viva).
    if ($null -ne $owned -and $null -ne $app) {
        try {
            $owned.Refresh()
            if ($owned.HasExited -or $owned.StartTime.ToUniversalTime().ToString('o') -ne $inicioPropio) { throw 'Instancia propia perdida antes del cierre.' }
            Exigir-Cero ($app.ApplicationExit($false)) 'ApplicationExit propia sin guardar'
            if (-not $owned.WaitForExit(30000)) { throw 'Cierre propio no confirmado.' }
            Traza 'instancia_propia_cerrada' @{id_proceso=$pidNuevo;inicio_proceso_utc=$inicioPropio}
            if ($out.estado -eq 'ok') { $out.datos.instancia_cerrada=$true }
        } catch {
            $out.error=@{tipo='cierre_propio';mensaje=$_.Exception.Message;id_proceso=$pidNuevo}
            $out.estado='error';$code=1
            try { Traza 'error' $out.error } catch { }
        }
    }
}
$temporary=$Respuesta+'.tmp-'+[guid]::NewGuid().ToString('N')
[IO.File]::WriteAllText($temporary,($out | ConvertTo-Json -Depth 12 -Compress),$Utf8)
[IO.File]::Move($temporary,$Respuesta)
exit $code
