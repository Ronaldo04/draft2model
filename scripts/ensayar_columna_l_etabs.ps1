param([Parameter(Mandatory=$true)][string]$CarpetaTrabajo,[switch]$ConfirmarEnsayoSintetico)
# Synthetic own test of the native concrete L section (SetConcreteL/GetConcreteL) and frame insertion points.
# Cantilever columns: lateral load reveals the product of inertia, axial load reveals the joint-to-centroid offset.
# Creates its own ETABS instances, never attaches to or closes other sessions; does not enable executors.
$ErrorActionPreference='Stop'
if(-not $ConfirmarEnsayoSintetico){throw 'Synthetic test confirmation required.'}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$work=[IO.Path]::GetFullPath($CarpetaTrabajo)
if(-not [IO.Path]::IsPathRooted($CarpetaTrabajo) -or -not $work.StartsWith((Join-Path $root 'tmp')+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Absolute work folder inside tmp required.'}
if(-not (Test-Path -LiteralPath $work -PathType Container) -or @(Get-ChildItem -LiteralPath $work -Force).Count -ne 0){throw 'Existing empty work folder required.'}
Add-Type -Path 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
$r=[ordered]@{datos_sinteticos=$true;fases=@();error=$null;cierres=@()}
$edb=Join-Path $work 'columna_l.edb'
$H=3.0;$E=25000000.0;$CARGAX=10.0;$CARGAZ=-1000.0
$mirrors=@(@($false,$false),@($true,$false),@($false,$true),@($true,$true))
$variants=@(@{id='C1';card=1;off=$null},@{id='C10';card=10;off=$null},@{id='C11';card=11;off=$null},@{id='C10G';card=10;off=@(0.1,0.05,0.0)})
function Check([int]$Code,[string]$Method){if($Code -ne 0){throw "$Method returned $Code"}}
function Hash([string]$Path){$a=[Security.Cryptography.SHA256]::Create();$f=[IO.File]::OpenRead($Path);try{return [BitConverter]::ToString($a.ComputeHash($f)).Replace('-','').ToLowerInvariant()}finally{$f.Dispose();$a.Dispose()}}
function Publish{[IO.File]::WriteAllText((Join-Path $work 'registro.json'),($r|ConvertTo-Json -Depth 24),[Text.UTF8Encoding]::new($false))}
function SectionName($m){return ('L_M2'+[int]$m[0]+'_M3'+[int]$m[1])}
function ReadSection($sap,[string]$name){
    [string]$file='';[string]$mat='';[double]$t3=0;[double]$t2=0;[double]$tf=0;[double]$twc=0;[double]$twt=0;[bool]$m2=$false;[bool]$m3=$false;[int]$col=0;[string]$notes='';[string]$guid=''
    Check ($sap.PropFrame.GetConcreteL($name,[ref]$file,[ref]$mat,[ref]$t3,[ref]$t2,[ref]$tf,[ref]$twc,[ref]$twt,[ref]$m2,[ref]$m3,[ref]$col,[ref]$notes,[ref]$guid)) 'GetConcreteL'
    [double]$a=0;[double]$as2=0;[double]$as3=0;[double]$j=0;[double]$i22=0;[double]$i33=0;[double]$s22=0;[double]$s33=0;[double]$z22=0;[double]$z33=0;[double]$r22=0;[double]$r33=0
    Check ($sap.PropFrame.GetSectProps($name,[ref]$a,[ref]$as2,[ref]$as3,[ref]$j,[ref]$i22,[ref]$i33,[ref]$s22,[ref]$s33,[ref]$z22,[ref]$z33,[ref]$r22,[ref]$r33)) 'GetSectProps'
    return [ordered]@{material=$mat;T3=$t3;T2=$t2;Tf=$tf;TwC=$twc;TwT=$twt;MirrorAbout2=$m2;MirrorAbout3=$m3;
        props=[ordered]@{Area=$a;As2=$as2;As3=$as3;Torsion=$j;I22=$i22;I33=$i33;S22=$s22;S33=$s33;Z22=$z22;Z33=$z33;R22=$r22;R33=$r33}}
}
function ReadFrame($sap,[string]$name){
    [int]$card=0;[bool]$mir=$false;[bool]$st=$false;[double[]]$o1=@();[double[]]$o2=@();[string]$cs=''
    Check ($sap.FrameObj.GetInsertionPoint($name,[ref]$card,[ref]$mir,[ref]$st,[ref]$o1,[ref]$o2,[ref]$cs)) 'GetInsertionPoint'
    [double]$ang=0;[bool]$adv=$false
    Check ($sap.FrameObj.GetLocalAxes($name,[ref]$ang,[ref]$adv)) 'GetLocalAxes'
    [string]$prop='';[string]$sauto=''
    Check ($sap.FrameObj.GetSection($name,[ref]$prop,[ref]$sauto)) 'GetSection'
    [string]$pi='';[string]$pj=''
    Check ($sap.FrameObj.GetPoints($name,[ref]$pi,[ref]$pj)) 'GetPoints'
    return [ordered]@{seccion=$prop;cardinal=$card;mirror2=$mir;stiff_transform=$st;offset_i=$o1;offset_j=$o2;csys=$cs;angulo=$ang;avanzado=$adv;punto_i=$pi;punto_j=$pj}
}
foreach($fase in @('construccion','reapertura')){
    $app=$null;$closed=$false
    try{
        $before=@(Get-Process ETABS -ErrorAction SilentlyContinue|ForEach-Object Id)
        $helper=New-Object ETABSv1.Helper
        $app=$helper.CreateObject('C:\Program Files\Computers and Structures\ETABS 21\ETABS.exe')
        Check ($app.ApplicationStart()) 'ApplicationStart'
        $own=@(Get-Process ETABS -ErrorAction SilentlyContinue|Where-Object {$_.Id -notin $before}|ForEach-Object Id)
        if($own.Count -ne 1){throw 'Cannot identify exactly one own instance.'}
        $sap=$app.SapModel
        $frames=[ordered]@{}
        if($fase -eq 'construccion'){
            Check ($sap.InitializeNewModel([ETABSv1.eUnits]::kN_m_C)) 'InitializeNewModel'
            Check ($sap.File.NewBlank()) 'NewBlank'
            [string[]]$sn=@('N1');[double[]]$sh=@($H);[bool[]]$sm=@($true);[string[]]$ss=@('None');[bool[]]$sp=@($false);[double[]]$sl=@(0);[int[]]$sc=@(0)
            Check ($sap.Story.SetStories_2(0,1,[ref]$sn,[ref]$sh,[ref]$sm,[ref]$ss,[ref]$sp,[ref]$sl,[ref]$sc)) 'SetStories_2'
            Check ($sap.PropMaterial.SetMaterial('MAT_SINTETICO',[ETABSv1.eMatType]::Concrete,0,'','')) 'SetMaterial'
            Check ($sap.PropMaterial.SetMPIsotropic('MAT_SINTETICO',$E,0.2,0.00001,0)) 'SetMPIsotropic'
            foreach($m in $mirrors){Check ($sap.PropFrame.SetConcreteL((SectionName $m),'MAT_SINTETICO',0.40,0.40,0.15,0.15,0.15,$m[0],$m[1],-1,'','')) 'SetConcreteL'}
            Check ($sap.LoadPatterns.Add('FX',[ETABSv1.eLoadPatternType]::Other,0,$true)) 'LoadPatterns.Add FX'
            Check ($sap.LoadPatterns.Add('PZ',[ETABSv1.eLoadPatternType]::Other,0,$true)) 'LoadPatterns.Add PZ'
            $i=0
            foreach($m in $mirrors){
                $j=0
                foreach($v in $variants){
                    $x=8.0*$i;$y=8.0*$j;[string]$name=''
                    Check ($sap.FrameObj.AddByCoord($x,$y,0,$x,$y,$H,[ref]$name,(SectionName $m),((SectionName $m)+'_'+$v.id),'Global')) 'FrameObj.AddByCoord'
                    if($null -ne $v.off){[double[]]$o1=$v.off;[double[]]$o2=$v.off;$csys='Global'}else{[double[]]$o1=@(0,0,0);[double[]]$o2=@(0,0,0);$csys='Local'}
                    $code=$sap.FrameObj.SetInsertionPoint($name,[int]$v.card,$false,$true,[ref]$o1,[ref]$o2,$csys,[ETABSv1.eItemType]::Objects)
                    [string]$pi='';[string]$pj=''
                    Check ($sap.FrameObj.GetPoints($name,[ref]$pi,[ref]$pj)) 'GetPoints'
                    [bool[]]$fixed=@($true,$true,$true,$true,$true,$true)
                    Check ($sap.PointObj.SetRestraint($pi,[ref]$fixed,[ETABSv1.eItemType]::Objects)) 'SetRestraint'
                    [double[]]$fx=@($CARGAX,0,0,0,0,0);[double[]]$pz=@(0,0,$CARGAZ,0,0,0)
                    Check ($sap.PointObj.SetLoadForce($pj,'FX',[ref]$fx,$true,'Global',[ETABSv1.eItemType]::Objects)) 'SetLoadForce FX'
                    Check ($sap.PointObj.SetLoadForce($pj,'PZ',[ref]$pz,$true,'Global',[ETABSv1.eItemType]::Objects)) 'SetLoadForce PZ'
                    $frames[$name]=[ordered]@{seccion=(SectionName $m);variante=$v.id;cardinal_pedido=$v.card;offset_pedido=$v.off;retorno_insercion=$code;xy=@($x,$y);tope=$pj}
                    $j++
                }
                $i++
            }
            Check ($sap.File.Save($edb)) 'Save own model'
            Check ($sap.Analyze.SetRunCaseFlag('',$false,$true)) 'Unset cases'
            Check ($sap.Analyze.SetRunCaseFlag('FX',$true,$false)) 'Set FX'
            Check ($sap.Analyze.SetRunCaseFlag('PZ',$true,$false)) 'Set PZ'
            Check ($sap.Analyze.RunAnalysis()) 'RunAnalysis'
            $res=[ordered]@{}
            foreach($case in @('FX','PZ')){
                Check ($sap.Results.Setup.DeselectAllCasesAndCombosForOutput()) 'Deselect'
                Check ($sap.Results.Setup.SetCaseSelectedForOutput($case,$true)) 'SelectCase'
                foreach($name in $frames.Keys){
                    $top=$frames[$name].tope
                    [int]$n=0;[string[]]$ob=@();[string[]]$el=@();[string[]]$lc=@();[string[]]$st=@();[double[]]$sn2=@()
                    [double[]]$u1=@();[double[]]$u2=@();[double[]]$u3=@();[double[]]$r1=@();[double[]]$r2=@();[double[]]$r3=@()
                    Check ($sap.Results.JointDispl($top,[ETABSv1.eItemTypeElm]::ObjectElm,[ref]$n,[ref]$ob,[ref]$el,[ref]$lc,[ref]$st,[ref]$sn2,[ref]$u1,[ref]$u2,[ref]$u3,[ref]$r1,[ref]$r2,[ref]$r3)) 'JointDispl'
                    if($n -ne 1 -or $lc[0] -ne $case){throw 'Unexpected result rows.'}
                    if(-not $res.Contains($name)){$res[$name]=[ordered]@{}}
                    $res[$name][$case]=@($u1[0],$u2[0],$u3[0],$r1[0],$r2[0],$r3[0])
                }
            }
            $r.resultados_tope=$res
            $r.carga=@{FX_kN=$CARGAX;PZ_kN=$CARGAZ;H_m=$H;E_kN_m2=$E}
        }else{
            $r.sha256_antes_reapertura=Hash $edb
            Check ($sap.File.OpenFile($edb)) 'OpenFile own model'
        }
        $secs=[ordered]@{};foreach($m in $mirrors){$secs[(SectionName $m)]=ReadSection $sap (SectionName $m)}
        [int]$nf=0;[string[]]$fn=@();Check ($sap.FrameObj.GetNameList([ref]$nf,[ref]$fn)) 'FrameObj.GetNameList'
        $lect=[ordered]@{};foreach($name in $fn){$lect[$name]=ReadFrame $sap $name}
        $r.fases+=@{fase=$fase;proceso_propio=$own[0];unidades=$sap.GetPresentUnits().ToString();secciones=$secs;frames=$lect;pedidos=$frames}
    }catch{$r.error=$_.Exception.Message;$r.error_posicion=$_.InvocationInfo.PositionMessage}
    finally{
        if($null -ne $app){try{$rc=$app.ApplicationExit($false);$closed=($rc -eq 0)}catch{$r.error_cierre=$_.Exception.Message}}
        $r.cierres+=@{fase=$fase;confirmado=$closed}
        Publish
    }
    if(-not $closed -or $null -ne $r.error){exit 2}
}
$r.sha256_final=Hash $edb
Publish
Write-Output 'Own synthetic L-section test finished; evaluate with the Python comparator.'
