param([Parameter(Mandatory=$true)][string]$Salida,[switch]$ConfirmarEnsayoSintetico)
# 315: ensayo SINTÉTICO de end length offsets Auto en ETABS 21 (MATRIZ_PREVIA_315.json). Instancia nueva propia; nunca GetActiveObject,
# nunca cierra ni toca otras sesiones; no abre EDB reales. Una sola instancia para los modelos A (tolerancia por defecto) y B (5x).
$ErrorActionPreference='Stop'
if(-not $ConfirmarEnsayoSintetico){throw 'Confirmación de ensayo sintético requerida.'}
$work=[IO.Path]::GetFullPath($Salida)
if(-not (Test-Path -LiteralPath $work -PathType Container) -or @(Get-ChildItem -LiteralPath $work -Force).Count -ne 0){throw 'Se requiere carpeta de salida vacía existente.'}
Add-Type -Path 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
$r=[ordered]@{datos_sinteticos=$true;llamadas_remotas=0;fases=@();error=$null;cierre=$null}
function Check([int]$Code,[string]$Method){if($Code -ne 0){throw "$Method devolvió $Code"}}
function Hash([string]$Path){$a=[Security.Cryptography.SHA256]::Create();$f=[IO.File]::OpenRead($Path);try{return [BitConverter]::ToString($a.ComputeHash($f)).Replace('-','').ToLowerInvariant()}finally{$f.Dispose();$a.Dispose()}}
function Publish{[IO.File]::WriteAllText((Join-Path $work 'registro_315.json'),($r|ConvertTo-Json -Depth 30),[Text.UTF8Encoding]::new($false))}
$SEC=[ordered]@{VIGA_15X30=@(0.30,0.15);COL_40X15=@(0.40,0.15);COL_25X25=@(0.25,0.25);COL_60X20=@(0.60,0.20)}

function Frame($sap,[double[]]$a,[double[]]$b,[string]$sec,[string]$user){
    [string]$n=''; Check ($sap.FrameObj.AddByCoord($a[0],$a[1],$a[2],$b[0],$b[1],$b[2],[ref]$n,$sec,$user,'Global')) "AddByCoord $user"; return $n }
function Fix($sap,[string]$frame){ [string]$pi='';[string]$pj=''; Check ($sap.FrameObj.GetPoints($frame,[ref]$pi,[ref]$pj)) 'GetPoints'
    [bool[]]$f=@($true,$true,$true,$true,$true,$true); Check ($sap.PointObj.SetRestraint($pi,[ref]$f,[ETABSv1.eItemType]::Objects)) "SetRestraint $frame" }
function Columna($sap,[double]$x,[double]$y,[string]$sec,[string]$user,[bool]$superior=$false,[double]$ang=0){
    if($superior){$n=Frame $sap @($x,$y,3.0) @($x,$y,6.0) $sec $user}else{$n=Frame $sap @($x,$y,0.0) @($x,$y,3.0) $sec $user; Fix $sap $n}
    if($ang -ne 0){Check ($sap.FrameObj.SetLocalAxes($n,$ang,[ETABSv1.eItemType]::Objects)) "SetLocalAxes $user"}
    return $n }
function Viga($sap,[double]$x,[double]$y,[string]$dir,[double]$L,[string]$user){
    if($dir -eq 'X'){return Frame $sap @($x,$y,3.0) @(($x+$L),$y,3.0) 'VIGA_15X30' $user}else{return Frame $sap @($x,$y,3.0) @($x,($y+$L),3.0) 'VIGA_15X30' $user} }
function Muro($sap,[double]$x,[double]$y,[string]$user){
    foreach($k in @(@(-1.5,0.0),@(0.0,1.5))){
        [double[]]$X=@($x,$x,$x,$x);[double[]]$Y=@(($y+$k[0]),($y+$k[1]),($y+$k[1]),($y+$k[0]));[double[]]$Z=@(0,0,3,3);[string]$n=''
        Check ($sap.AreaObj.AddByCoord(4,[ref]$X,[ref]$Y,[ref]$Z,[ref]$n,'MURO_15',($user+'_'+$k[1]),'Global')) "Area $user"
        [int]$np=0;[string[]]$pts=@(); Check ($sap.AreaObj.GetPoints($n,[ref]$np,[ref]$pts)) 'Area.GetPoints'
        foreach($p in $pts){[double]$px=0;[double]$py=0;[double]$pz=0; Check ($sap.PointObj.GetCoordCartesian($p,[ref]$px,[ref]$py,[ref]$pz,'Global')) 'GetCoord'
            if([math]::Abs($pz) -lt 1e-9){[bool[]]$f=@($true,$true,$true,$true,$true,$true); Check ($sap.PointObj.SetRestraint($p,[ref]$f,[ETABSv1.eItemType]::Objects)) 'Restraint muro'}}
    } }

function Construir($sap,[string]$modelo,[double]$tol){
    Check ($sap.InitializeNewModel([ETABSv1.eUnits]::kN_m_C)) 'InitializeNewModel'
    Check ($sap.File.NewBlank()) 'NewBlank'
    [double]$t0=0; Check ($sap.GetMergeTol([ref]$t0)) 'GetMergeTol'
    $info=[ordered]@{modelo=$modelo;tolerancia_por_defecto=$t0}
    if($tol -gt 0){ Check ($sap.SetMergeTol($tol)) 'SetMergeTol'; [double]$t1=0; Check ($sap.GetMergeTol([ref]$t1)) 'GetMergeTol'; $info.tolerancia_aplicada=$t1 } else { $info.tolerancia_aplicada=$t0 }
    [string[]]$sn=@('P1','P2');[double[]]$sh=@(3.0,3.0);[bool[]]$sm=@($true,$false);[string[]]$ss=@('None','None');[bool[]]$sp=@($false,$false);[double[]]$sl=@(0,0);[int[]]$sc=@(0,0)
    Check ($sap.Story.SetStories_2(0,2,[ref]$sn,[ref]$sh,[ref]$sm,[ref]$ss,[ref]$sp,[ref]$sl,[ref]$sc)) 'SetStories_2'
    Check ($sap.PropMaterial.SetMaterial('MAT_SINT',[ETABSv1.eMatType]::Concrete,0,'','')) 'SetMaterial'
    Check ($sap.PropMaterial.SetMPIsotropic('MAT_SINT',25000000,0.2,0.00001,0)) 'SetMPIsotropic'
    foreach($k in $SEC.Keys){Check ($sap.PropFrame.SetRectangle($k,'MAT_SINT',$SEC[$k][0],$SEC[$k][1],-1,'','')) "SetRectangle $k"}
    Check ($sap.PropArea.SetWall('MURO_15',[ETABSv1.eWallPropType]::Specified,[ETABSv1.eShellType]::ShellThin,'MAT_SINT',0.15,-1,'','')) 'SetWall'
    $vigas=[ordered]@{}
    $todos=@('K01','K02','K03','K04','K05','K06','K07','K08','K09','K10','K11'); if($modelo -eq 'B'){$todos=@('K01','K06','K08','K10')}
    $fila=0
    foreach($k in $todos){
        $x=0.0;$y=10.0*$fila;$fila++
        switch($k){
            'K01'{Columna $sap $x $y 'COL_40X15' "$k-CI"|Out-Null; Columna $sap ($x+3) $y 'COL_40X15' "$k-CJ"|Out-Null; $v=Viga $sap $x $y 'X' 3.0 $k}
            'K02'{Columna $sap $x $y 'COL_40X15' "$k-CI"|Out-Null; Columna $sap $x ($y+3) 'COL_40X15' "$k-CJ"|Out-Null; $v=Viga $sap $x $y 'Y' 3.0 $k}
            'K03'{Columna $sap $x $y 'COL_25X25' "$k-CI"|Out-Null; Columna $sap ($x+3) $y 'COL_60X20' "$k-CJS" $true|Out-Null; $v=Viga $sap $x $y 'X' 3.0 $k}
            'K04'{Columna $sap $x $y 'COL_60X20' "$k-CI"|Out-Null; Muro $sap ($x+3) $y "$k-M"; $v=Viga $sap $x $y 'X' 3.0 $k}
            'K05'{Columna $sap $x $y 'COL_25X25' "$k-CI"|Out-Null; Columna $sap ($x+3) ($y+3) 'COL_25X25' "$k-CP"|Out-Null; Viga $sap ($x+3) $y 'Y' 3.0 "$k-VP"|Out-Null; $v=Viga $sap $x $y 'X' 3.0 $k}
            'K06'{Columna $sap $x $y 'COL_60X20' "$k-CI"|Out-Null; $v=Viga $sap $x $y 'X' 0.29 $k}
            'K07'{Columna $sap $x $y 'COL_60X20' "$k-CI"|Out-Null; $v=Viga $sap $x $y 'X' 0.55 $k}
            'K08'{Columna $sap $x $y 'COL_60X20' "$k-CI"|Out-Null; Columna $sap ($x+0.35) $y 'COL_60X20' "$k-CJ"|Out-Null; $v=Viga $sap $x $y 'X' 0.35 $k}
            'K09'{Columna $sap $x $y 'COL_60X20' "$k-CI"|Out-Null; Columna $sap ($x+0.50) $y 'COL_60X20' "$k-CJ"|Out-Null; $v=Viga $sap $x $y 'X' 0.50 $k}
            'K10'{Columna $sap $x $y 'COL_60X20' "$k-CI"|Out-Null; $v=Viga $sap $x $y 'Y' 0.27 $k}
            'K11'{Columna $sap $x $y 'COL_60X20' "$k-CI" $false 90|Out-Null; Columna $sap ($x+3) $y 'COL_25X25' "$k-CJ"|Out-Null; $v=Viga $sap $x $y 'X' 3.0 $k}
        }
        $vigas[$k]=$v
    }
    $info.vigas=$vigas
    return $info
}
function LeerOffsets($sap,$info){
    $out=[ordered]@{}
    [int]$nf=0;[string[]]$fn=@(); Check ($sap.FrameObj.GetNameList([ref]$nf,[ref]$fn)) 'FrameObj.GetNameList'
    foreach($name in $fn){
        [bool]$auto=$false;[double]$l1=0;[double]$l2=0;[double]$rz=0; $code=$sap.FrameObj.GetEndLengthOffset($name,[ref]$auto,[ref]$l1,[ref]$l2,[ref]$rz)
        [string]$pi='';[string]$pj=''; Check ($sap.FrameObj.GetPoints($name,[ref]$pi,[ref]$pj)) 'GetPoints'
        $c=@(); foreach($p in @($pi,$pj)){[double]$px=0;[double]$py=0;[double]$pz=0; Check ($sap.PointObj.GetCoordCartesian($p,[ref]$px,[ref]$py,[ref]$pz,'Global')) 'GetCoord'; $c+=,@($px,$py,$pz)}
        [string]$prop='';[string]$sa=''; Check ($sap.FrameObj.GetSection($name,[ref]$prop,[ref]$sa)) 'GetSection'
        [double]$ang=0;[bool]$adv=$false; Check ($sap.FrameObj.GetLocalAxes($name,[ref]$ang,[ref]$adv)) 'GetLocalAxes'
        $out[$name]=[ordered]@{retorno=$code;auto=$auto;Length1=$l1;Length2=$l2;RZ=$rz;punto_i=$pi;punto_j=$pj;coord_i=$c[0];coord_j=$c[1];seccion=$prop;angulo=$ang}
    }
    [string[]]$fk=@();[int]$ver=0;[string[]]$inc=@();[int]$nr=0;[string[]]$flat=@()
    $tc=$sap.DatabaseTables.GetTableForDisplayArray('Frame Assignments - End Length Offsets',[ref]$fk,'',[ref]$ver,[ref]$inc,[ref]$nr,[ref]$flat)
    return [ordered]@{api=$out;tabla=[ordered]@{retorno=$tc;version=$ver;campos=$inc;registros=$nr;datos=$flat}}
}

$app=$null;$ownPid=$null;$ownStart=$null
try{
    $before=@(Get-Process ETABS -ErrorAction SilentlyContinue|ForEach-Object Id)
    $r.etabs_previos_ajenos=$before
    $helper=New-Object ETABSv1.Helper
    $app=$helper.CreateObject('C:\Program Files\Computers and Structures\ETABS 21\ETABS.exe')
    Check ($app.ApplicationStart()) 'ApplicationStart'
    $own=@(Get-Process ETABS -ErrorAction SilentlyContinue|Where-Object {$_.Id -notin $before})
    if($own.Count -ne 1){throw 'No se identifica exactamente una instancia propia.'}
    $ownPid=$own[0].Id;$ownStart=$own[0].StartTime.ToUniversalTime().ToString('o'); $r.proceso_propio=[ordered]@{pid=$ownPid;inicio_utc=$ownStart}; Publish
    $sap=$app.SapModel
    [string]$vs='';[double]$vn=0; $null=$sap.GetVersion([ref]$vs,[ref]$vn); $r.version_etabs=@($vs,$vn)
    $tolA=$null
    foreach($modelo in @('A','B')){
        $fase=[ordered]@{modelo=$modelo}
        $tol=0.0; if($modelo -eq 'B'){$tol=5*$tolA}
        $info=Construir $sap $modelo $tol; if($modelo -eq 'A'){$tolA=$info.tolerancia_aplicada}
        $fase.construccion=$info; $fase.unidades=$sap.GetPresentUnits().ToString()
        $edb=Join-Path $work ("auto_315_$modelo.edb"); Check ($sap.File.Save($edb)) "Save $modelo"
        $fase.antes_analisis=LeerOffsets $sap $info; Publish
        Check ($sap.LoadPatterns.Add('PP_SINT',[ETABSv1.eLoadPatternType]::Dead,1,$true)) 'LoadPatterns.Add'
        Check ($sap.Analyze.SetRunCaseFlag('',$false,$true)) 'Unset cases'
        Check ($sap.Analyze.SetRunCaseFlag('PP_SINT',$true,$false)) 'Set PP_SINT'
        $fase.retorno_analisis=$sap.Analyze.RunAnalysis()
        $fase.despues_analisis=LeerOffsets $sap $info
        Check ($sap.File.Save($edb)) "Save analizado $modelo"; $fase.edb=[ordered]@{ruta=(Split-Path $edb -Leaf);sha256=(Hash $edb)}
        $r.fases+=$fase; Publish
    }
}catch{$r.error=$_.Exception.Message;$r.error_posicion=$_.InvocationInfo.PositionMessage}
finally{
    $c=[ordered]@{application_exit=$null;pid=$ownPid;salio=$null}
    if($null -ne $app){try{$c.application_exit=$app.ApplicationExit($false)}catch{$c.error=$_.Exception.Message}}
    if($null -ne $ownPid){ $p=Get-Process -Id $ownPid -ErrorAction SilentlyContinue
        if($p){ if($p.StartTime.ToUniversalTime().ToString('o') -eq $ownStart){ $c.salio=$p.WaitForExit(60000) } else { $c.salio='pid_reutilizado' } } else { $c.salio=$true } }
    $c.etabs_tras_cierre=@(Get-Process ETABS -ErrorAction SilentlyContinue|ForEach-Object Id)
    $r.cierre=$c; Publish
}
if($null -ne $r.error -or $r.cierre.salio -ne $true){exit 2}
Write-Output 'Ensayo sintético 315 terminado.'
