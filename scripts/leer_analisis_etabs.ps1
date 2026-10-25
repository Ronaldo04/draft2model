param(
    [Parameter(Mandatory=$true)][string]$Solicitud,
    [Parameter(Mandatory=$true)][string]$Respuesta,
    [Parameter(Mandatory=$true)][string]$Sha256Solicitud
)
# Solo instancia NUEVA y su objeto COM propio. No recalcula, copia EDB ni guarda.
Set-StrictMode -Version 2.0
$ErrorActionPreference='Stop'
$Utf8=New-Object System.Text.UTF8Encoding($false)
function Hash-Archivo([string]$Ruta) {
    $stream=[IO.File]::OpenRead($Ruta);$algorithm=[Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-','').ToLowerInvariant() }
    finally { $stream.Dispose();$algorithm.Dispose() }
}
function Exigir-Cero([int]$Valor,[string]$Nombre) {
    if ($Valor -ne 0) { throw "$Nombre devolvio codigo $Valor" }
}
function Traza([string]$Evento,$Datos) {
    $row=@{evento=$Evento;datos=$Datos;utc=[DateTime]::UtcNow.ToString('o')}
    [IO.File]::AppendAllText((Join-Path (Split-Path $Respuesta) 'traza_lectura.jsonl'),
        (($row | ConvertTo-Json -Depth 12 -Compress)+"`n"),$Utf8)
}
function Ruta-Segura([string]$Ruta) {
    if (-not [IO.Path]::IsPathRooted($Ruta)) { throw 'Ruta no absoluta.' }
    $full=[IO.Path]::GetFullPath($Ruta)
    if (-not [string]::Equals($full,$Ruta,[StringComparison]::OrdinalIgnoreCase)) { throw 'Ruta no normalizada.' }
    $current=$full
    while (-not [string]::IsNullOrEmpty($current)) {
        $item=Get-Item -LiteralPath $current -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Ruta enlazada no permitida.' }
        $parent=Split-Path -Parent $current
        if ($parent -eq $current) { break }
        $current=$parent
    }
    return $full
}
function Lista-Explicita($Valor,[string]$Nombre) {
    if ($null -eq $Valor -or $Valor -is [string] -or $Valor -isnot [array] -or $Valor.Count -eq 0) {
        throw "$Nombre debe ser lista no vacia."
    }
    foreach ($item in $Valor) { if ($item -isnot [string] -or [string]::IsNullOrWhiteSpace($item)) { throw "$Nombre invalido." } }
    if (@($Valor | Select-Object -Unique).Count -ne $Valor.Count) { throw "$Nombre repetido." }
    return ,([string[]]$Valor)
}
function Comprobar-Casos($Sap,$Casos) {
    [int]$n=0;[string[]]$names=@();[int[]]$states=@()
    Exigir-Cero ($Sap.Analyze.GetCaseStatus([ref]$n,[ref]$names,[ref]$states)) 'GetCaseStatus'
    $selected=[ordered]@{}
    foreach ($name in $Casos) {
        $index=[Array]::IndexOf($names,[string]$name)
        if ($index -lt 0 -or $states[$index] -ne 4) { throw "Caso no persistido con estado4: $name" }
        $selected[$name]=[int]$states[$index]
    }
    return $selected
}
function Comprobar-Modelo($Sap,[string]$Esperado) {
    $opened=$Sap.GetModelFilename($true)
    if (-not [string]::Equals([IO.Path]::GetFullPath($opened),$Esperado,[StringComparison]::OrdinalIgnoreCase)) {
        throw 'El modelo abierto no coincide con el EDB aceptado.'
    }
}
$code=1;$app=$null;$owned=$null;$ownConfirmed=$false;$pidPropio=$null;$inicioPropio=$null;$request=$null;$readData=$null
$out=[ordered]@{contrato='draft2model.etabs_respuesta';version_contrato='0.1.0';operacion='leer_tablas';
    modo_ejecucion='real';id_solicitud=$null;estado='error';datos=@{};avisos=@();error=$null;
    inicio_utc=[DateTime]::UtcNow.ToString('o');fin_utc=$null}
try {
    if ($PSVersionTable.PSVersion.Major -ne 5) { throw 'Se requiere Windows PowerShell5.1.' }
    if (Test-Path -LiteralPath $Respuesta) { throw 'Respuesta existente; no se sobrescribe.' }
    if ($Sha256Solicitud -notmatch '^[0-9a-f]{64}$' -or (Hash-Archivo (Ruta-Segura $Solicitud)) -ne $Sha256Solicitud) { throw 'Solicitud alterada.' }
    $request=[IO.File]::ReadAllText($Solicitud,$Utf8) | ConvertFrom-Json
    $fields=@('contrato','version_contrato','id','operacion','modo_configurado','corrida_analisis_id','modelo_esperado',
        'sha256_edb','sha256_aceptacion_analisis','version_etabs_esperada','unidades_esperadas','tablas','casos','combinaciones','dll')
    # Campo opcional resultados_api: lectura tipada de dobles (BaseReact y/o AssembledJointMass), sin redondeo de tabla.
    $apiPedida=@()
    if ($request -is [Management.Automation.PSCustomObject] -and @($request.PSObject.Properties.Name) -contains 'resultados_api') {
        $apiPedida=@($request.resultados_api)
        $permitidos=@('BaseReact','AssembledJointMass','ConfiguracionAuto')
        if ($apiPedida.Count -lt 1 -or $apiPedida.Count -gt 2 -or @($apiPedida | Select-Object -Unique).Count -ne $apiPedida.Count -or
            @($apiPedida | Where-Object { $permitidos -notcontains $_ }).Count) { throw 'resultados_api no admitidos.' }
        $fields+='resultados_api'
    }
    if ($request -isnot [Management.Automation.PSCustomObject] -or
        @($request.PSObject.Properties.Name).Count -ne $fields.Count -or
        @($request.PSObject.Properties.Name | Where-Object { $fields -notcontains $_ }).Count) { throw 'Campos de solicitud no permitidos.' }
    if ($request.contrato -ne 'draft2model.etabs_solicitud' -or $request.version_contrato -ne '0.1.0' -or
        $request.operacion -ne 'leer_tablas' -or $request.modo_configurado -ne 'real' -or
        $request.id -notmatch '^[0-9a-f]{32}$' -or $request.corrida_analisis_id -notmatch '^[0-9a-f]{32}$') { throw 'Contrato/identidad de solicitud invalidos.' }
    $out.id_solicitud=$request.id
    $model=Ruta-Segura ([string]$request.modelo_esperado)
    $run=Split-Path -Parent $model
    if ((Split-Path -Leaf $model) -ine 'analizado.edb' -or (Split-Path -Leaf $run) -ne $request.corrida_analisis_id -or
        (Split-Path -Leaf (Split-Path -Parent $run)) -ne 'analisis_etabs') { throw 'EDB fuera de la corrida controlada.' }
    if ($request.sha256_edb -notmatch '^[0-9a-f]{64}$' -or (Hash-Archivo $model) -ne $request.sha256_edb) { throw 'EDB analizado alterado.' }
    $acceptance=Join-Path $run 'aceptacion_analisis.json'
    if ($request.sha256_aceptacion_analisis -notmatch '^[0-9a-f]{64}$' -or
        (Hash-Archivo (Ruta-Segura $acceptance)) -ne $request.sha256_aceptacion_analisis) { throw 'Aceptacion de analisis alterada.' }
    $source=[IO.File]::ReadAllText($acceptance,$Utf8) | ConvertFrom-Json
    if ($source.aceptada -ne $true -or $source.analisis_ejecutado -ne $true -or $source.aprueba_resultados -ne $false -or
        $source.modo -ne 'real' -or $source.guardado.sha256 -ne $request.sha256_edb) { throw 'Analisis no aceptado.' }
    [string[]]$tables=Lista-Explicita $request.tablas 'tablas'
    [string[]]$cases=Lista-Explicita $request.casos 'casos'
    if ($null -eq $request.combinaciones -or $request.combinaciones -isnot [array] -or $request.combinaciones.Count -ne 0) { throw 'No se admiten combinaciones.' }
    foreach ($name in $cases) { if ($source.casos_ejecutados -notcontains $name -or $source.estados_casos.$name -ne 4) { throw 'Caso fuera del analisis aceptado.' } }
    if ($request.unidades_esperadas -ne 'kN_m_C' -or [string]::IsNullOrWhiteSpace($request.version_etabs_esperada)) { throw 'Unidades/version esperadas invalidas.' }
    $dll=Ruta-Segura ([string]$request.dll)
    Add-Type -LiteralPath $dll
    $before=@(Get-Process ETABS -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id)
    $helper=New-Object ETABSv1.Helper
    $app=$helper.CreateObjectProgID('CSI.ETABS.API.ETABSObject')
    Exigir-Cero ($app.ApplicationStart()) 'ApplicationStart'
    $new=@(Get-Process ETABS -ErrorAction SilentlyContinue | Where-Object { $before -notcontains $_.Id })
    if ($new.Count -ne 1) { throw 'No se identifico una sola instancia propia nueva.' }
    $owned=$new[0];$null=$owned.Handle # fija handle de esta creacion; no se reconecta por numero historico
    $pidPropio=$owned.Id;$inicioPropio=$owned.StartTime.ToUniversalTime().ToString('o');$ownConfirmed=$true
    Traza 'instancia_nueva' @{id_proceso=$pidPropio;inicio_proceso_utc=$inicioPropio}
    Exigir-Cero ($app.Hide()) 'Hide'
    $sap=$app.SapModel
    if ((Hash-Archivo $model) -ne $request.sha256_edb) { throw 'EDB cambio antes de abrir.' }
    Exigir-Cero ($sap.File.OpenFile($model)) 'OpenFile analizado original'
    Comprobar-Modelo $sap $model
    $selected=Comprobar-Casos $sap $cases
    [string]$version='';[double]$number=0
    Exigir-Cero ($sap.GetVersion([ref]$version,[ref]$number)) 'GetVersion'
    # ETABS 21.1 reabre el EDB en sus unidades de base de datos (observado N_mm_C, relecturas 199/l2). Igual que
    # analizar_modelo_etabs.ps1: unidades de PRESENTACION kN_m_C en esta instancia propia (se cierra sin guardar).
    $unidadesAlAbrir=$sap.GetPresentUnits().ToString()
    Exigir-Cero ($sap.SetPresentUnits([ETABSv1.eUnits]::kN_m_C)) 'SetPresentUnits presentacion'
    $units=$sap.GetPresentUnits().ToString()
    Traza 'unidades_api' @{al_abrir=$unidadesAlAbrir;presentacion=$units}
    if ($version -ne $request.version_etabs_esperada -or $units -ne $request.unidades_esperadas) { throw 'Version/unidades no coinciden con el analisis esperado.' }
    $db=$sap.DatabaseTables
    [int]$count=0;[string[]]$keys=@();[string[]]$titles=@();[int[]]$types=@()
    Exigir-Cero ($db.GetAvailableTables([ref]$count,[ref]$keys,[ref]$titles,[ref]$types)) 'GetAvailableTables'
    foreach ($table in $tables) { if ($keys -notcontains $table) { throw "Tabla ausente: $table" } }
    [string[]]$selection=$cases
    Exigir-Cero ($db.SetLoadCasesSelectedForDisplay([ref]$selection)) 'SetLoadCasesSelectedForDisplay'
    [string[]]$combos=@()
    Exigir-Cero ($db.SetLoadCombinationsSelectedForDisplay([ref]$combos)) 'SetLoadCombinationsSelectedForDisplay'
    $readTables=New-Object System.Collections.ArrayList
    foreach ($table in $tables) {
        [string[]]$wanted=@('');[int]$tableVersion=0;[string[]]$fieldsRead=@();[int]$records=0;[string[]]$values=@()
        Exigir-Cero ($db.GetTableForDisplayArray($table,[ref]$wanted,'',[ref]$tableVersion,[ref]$fieldsRead,[ref]$records,[ref]$values)) 'GetTableForDisplayArray'
        if ($fieldsRead.Count -eq 0 -or @($fieldsRead | Select-Object -Unique).Count -ne $fieldsRead.Count -or
            $values.Count -ne $records*$fieldsRead.Count) { throw 'Esquema CSI incoherente.' }
        $caseField=$null
        if ($fieldsRead -contains 'OutputCase') { $caseField='OutputCase' }
        elseif ($table -in @('Modal Periods And Frequencies','Modal Participating Mass Ratios') -and $fieldsRead -contains 'Case') { $caseField='Case' }
        # Tablas de modelo/masa sin campo de caso: solo las de la lista explícita, completas y sin filtrar (nunca por inferencia).
        $sinCaso=@('Mass Summary by Story','Centers Of Mass And Rigidity','Material List by Object Type','Material List by Section Property','Material List by Story','Frame Assignments - End Length Offsets')
        if ($null -eq $caseField -and $sinCaso -notcontains $table) { throw 'Tabla sin campo de caso admitido.' }
        $rows=New-Object System.Collections.ArrayList;$discarded=0
        for ($rowIndex=0;$rowIndex -lt $records;$rowIndex++) {
            $row=[ordered]@{}
            for ($column=0;$column -lt $fieldsRead.Count;$column++) { $row[$fieldsRead[$column]]=$values[$rowIndex*$fieldsRead.Count+$column] }
            if ($null -eq $caseField -or $cases -contains $row[$caseField]) { [void]$rows.Add($row) } else { $discarded++ }
        }
        [void]$readTables.Add([ordered]@{clave=$table;version_tabla=$tableVersion;campos=@($fieldsRead);
            numero_registros_api=$records;registros_descartados_por_caso=$discarded;filas=@($rows)})
    }
    $api=$null
    if ($apiPedida -contains 'BaseReact') {
        $inv=[Globalization.CultureInfo]::InvariantCulture
        $setup=$sap.Results.Setup
        Exigir-Cero ($setup.DeselectAllCasesAndCombosForOutput()) 'DeselectAllCasesAndCombosForOutput'
        foreach ($name in $cases) { Exigir-Cero ($setup.SetCaseSelectedForOutput($name,$true)) 'SetCaseSelectedForOutput' }
        [int]$n=0;[string[]]$lc=@();[string[]]$st=@();[double[]]$sn=@();[double[]]$fx=@();[double[]]$fy=@();[double[]]$fz=@()
        [double[]]$mx=@();[double[]]$my=@();[double[]]$mz=@();[double]$gx=0;[double]$gy=0;[double]$gz=0
        Exigir-Cero ($sap.Results.BaseReact([ref]$n,[ref]$lc,[ref]$st,[ref]$sn,[ref]$fx,[ref]$fy,[ref]$fz,[ref]$mx,[ref]$my,[ref]$mz,[ref]$gx,[ref]$gy,[ref]$gz)) 'BaseReact'
        if ($lc.Count -ne $n -or $fx.Count -ne $n -or $my.Count -ne $n -or $mz.Count -ne $n) { throw 'BaseReact con longitudes incoherentes.' }
        $filasApi=New-Object System.Collections.ArrayList
        for ($i=0;$i -lt $n;$i++) {
            if ($cases -notcontains $lc[$i]) { throw 'BaseReact devolvio un caso no seleccionado.' }
            [void]$filasApi.Add([ordered]@{LoadCase=$lc[$i];StepType=[string]$st[$i];StepNum=$sn[$i].ToString('R',$inv);
                FX=$fx[$i].ToString('R',$inv);FY=$fy[$i].ToString('R',$inv);FZ=$fz[$i].ToString('R',$inv);
                MX=$mx[$i].ToString('R',$inv);MY=$my[$i].ToString('R',$inv);MZ=$mz[$i].ToString('R',$inv)})
        }
        $api=[ordered]@{BaseReact=[ordered]@{unidades=$sap.GetPresentUnits().ToString();punto_reaccion=@($gx.ToString('R',$inv),$gy.ToString('R',$inv),$gz.ToString('R',$inv));
            casos_seleccionados=@($cases);filas=@($filasApi)}}
        Traza 'resultados_api' @{metodo='BaseReact';registros=$n}
    }
    if ($apiPedida -contains 'AssembledJointMass') {
        # Masa ensamblada del EDB analizado (MassSourceName vacio = todas las fuentes; no se inventa un nombre). Se conservan los
        # arrays crudos completos, incluida una posible cola de asignacion; Python decide con masa_ensamblada, sin recortes aqui.
        $inv=[Globalization.CultureInfo]::InvariantCulture
        [int]$nm=0;[string[]]$pe=@();[string[]]$ms=@();[double[]]$u1=@();[double[]]$u2=@();[double[]]$u3=@();[double[]]$r1=@();[double[]]$r2=@();[double[]]$r3=@()
        $retorno=$sap.Results.AssembledJointMass_1('','ALL',[ETABSv1.eItemTypeElm]::GroupElm,[ref]$nm,[ref]$pe,[ref]$ms,[ref]$u1,[ref]$u2,[ref]$u3,[ref]$r1,[ref]$r2,[ref]$r3)
        Exigir-Cero $retorno 'AssembledJointMass_1'
        $texto={ param($arr) @($arr | ForEach-Object { if ($null -eq $_) { $null } else { ([double]$_).ToString('R',$inv) } }) }
        $ident={ param($arr) @($arr | ForEach-Object { if ($null -eq $_) { $null } else { [string]$_ } }) }
        $obs=New-Object System.Collections.ArrayList
        for ($i=0;$i -lt $nm;$i++) {
            [double]$x=0;[double]$y=0;[double]$z=0;[double]$ax=0;[double]$ay=0;[double]$az=0
            Exigir-Cero ($sap.PointElm.GetCoordCartesian($pe[$i],[ref]$x,[ref]$y,[ref]$z,'Global')) 'PointElm.GetCoordCartesian'
            Exigir-Cero ($sap.PointElm.GetLocalAxes($pe[$i],[ref]$ax,[ref]$ay,[ref]$az)) 'PointElm.GetLocalAxes'
            [void]$obs.Add([ordered]@{point_element=[string]$pe[$i];mass_source=[string]$ms[$i];
                global_xyz=@($x.ToString('R',$inv),$y.ToString('R',$inv),$z.ToString('R',$inv));
                point_axes_deg=@($ax.ToString('R',$inv),$ay.ToString('R',$inv),$az.ToString('R',$inv));
                U1=$u1[$i].ToString('R',$inv);U2=$u2[$i].ToString('R',$inv);U3=$u3[$i].ToString('R',$inv);
                R1=$r1[$i].ToString('R',$inv);R2=$r2[$i].ToString('R',$inv);R3=$r3[$i].ToString('R',$inv)})
        }
        if ($null -eq $api) { $api=[ordered]@{} }
        $api.AssembledJointMass=[ordered]@{unidades=$sap.GetPresentUnits().ToString();retorno=[int]$retorno;numero_resultados=[int]$nm;
            point_elements=(& $ident $pe);mass_sources=(& $ident $ms);U1=(& $texto $u1);U2=(& $texto $u2);U3=(& $texto $u3);
            R1=(& $texto $r1);R2=(& $texto $r2);R3=(& $texto $r3);observaciones=@($obs)}
        Traza 'resultados_api' @{metodo='AssembledJointMass_1';registros=$nm}
    }
    if ($apiPedida -contains 'ConfiguracionAuto') {
        [double]$tolAuto=0
        $rcAuto=$sap.GetMergeTol([ref]$tolAuto)
        Exigir-Cero $rcAuto 'GetMergeTol'
        if ($null -eq $api) { $api=[ordered]@{} }
        $api.ConfiguracionAuto=[ordered]@{unidades=$units;version_etabs=$version;retorno=[int]$rcAuto;
            tolerancia_union_m=$tolAuto.ToString('R',[Globalization.CultureInfo]::InvariantCulture)}
        Traza 'configuracion_auto' @{metodo='GetMergeTol';retorno=$rcAuto}
    }
    Comprobar-Modelo $sap $model
    $null=Comprobar-Casos $sap $cases
    if ((Hash-Archivo $model) -ne $request.sha256_edb -or (Hash-Archivo $acceptance) -ne $request.sha256_aceptacion_analisis) { throw 'Fuente cambio durante lectura.' }
    $readData=[ordered]@{modelo=$model;version_etabs=$version;unidades=$units;casos=@($cases);combinaciones=@();
        estado_casos=$selected;tablas=@($readTables);instancia='nueva';id_proceso=$pidPropio;inicio_proceso_utc=$inicioPropio;
        instancia_cerrada=$false;sha256_modelo_verificado=$request.sha256_edb;corrida_analisis_id=$request.corrida_analisis_id;
        analisis_ejecutado=$false;aprueba_resultados=$false}
    if ($null -ne $api) { $readData.resultados_api=$api }
    $code=0
} catch {
    $out.error=@{tipo='lectura';mensaje=$_.Exception.Message;id_proceso=$pidPropio}
    try { Traza 'error' $out.error } catch { }
    $code=1
} finally {
    if ($ownConfirmed) {
        try {
            if ($owned.HasExited -or $owned.StartTime.ToUniversalTime().ToString('o') -ne $inicioPropio) { throw 'Instancia propia perdida antes del cierre.' }
            Exigir-Cero ($app.ApplicationExit($false)) 'ApplicationExit propia sin guardar'
            if (-not $owned.WaitForExit(10000)) { throw 'Cierre propio no confirmado.' }
            Traza 'instancia_propia_cerrada' @{id_proceso=$pidPropio;inicio_proceso_utc=$inicioPropio}
            if ($null -ne $readData) { $readData.instancia_cerrada=$true }
        } catch {
            $out.error=@{tipo='cierre_propio';mensaje=$_.Exception.Message;id_proceso=$pidPropio};$code=1
        }
    }
}
if ($code -eq 0) {
    try {
        if ($null -eq $readData -or -not $readData.instancia_cerrada -or (Hash-Archivo $model) -ne $request.sha256_edb) { throw 'Lectura/cierre/fuente final no confirmados.' }
        $out.datos=$readData;$out.estado='ok'
        $out.avisos=@('Lectura en instancia propia nueva cerrada sin guardar; no se recalculo ni se aprobaron resultados.')
    } catch { $out.error=@{tipo='verificacion_final';mensaje=$_.Exception.Message};$code=1 }
}
$out.fin_utc=[DateTime]::UtcNow.ToString('o')
$temporary=$Respuesta+'.tmp-'+[guid]::NewGuid().ToString('N')
try {
    [IO.File]::WriteAllText($temporary,($out | ConvertTo-Json -Depth 32 -Compress),$Utf8)
    [IO.File]::Move($temporary,$Respuesta)
} catch { [Console]::Error.WriteLine('Respuesta de lectura no publicada.');exit 1 }
exit $code
