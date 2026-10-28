param([Parameter(Mandatory=$true)][string]$CarpetaTrabajo,[switch]$ConfirmarEnsayoSintetico)
# Ensayo propio y sintético; no habilita ejecutores ni modifica modelos del usuario.
$ErrorActionPreference='Stop'
if(-not $ConfirmarEnsayoSintetico){throw 'Confirmación del ensayo sintético requerida.'}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$work=[IO.Path]::GetFullPath($CarpetaTrabajo)
if(-not [IO.Path]::IsPathRooted($CarpetaTrabajo) -or -not $work.StartsWith((Join-Path $root 'tmp')+[IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Trabajo absoluto dentro de tmp requerido.'}
if(-not (Test-Path -LiteralPath $work -PathType Container) -or @(Get-ChildItem -LiteralPath $work -Force).Count -ne 0){throw 'Trabajo existente y vacío requerido.'}
Add-Type -Path 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
$registro=[ordered]@{datos_sinteticos=$true;solver_ejecutado=$false;fases=@();error=$null;cierres=@()}
$edb=Join-Path $work 'aligerados.edb'
function Check([int]$Codigo,[string]$Metodo){if($Codigo -ne 0){throw "$Metodo devolvio $Codigo"}}
function Hash([string]$Path){$a=[Security.Cryptography.SHA256]::Create();$f=[IO.File]::OpenRead($Path);try{return [BitConverter]::ToString($a.ComputeHash($f)).Replace('-','').ToLowerInvariant()}finally{$f.Dispose();$a.Dispose()}}
function Publicar{[IO.File]::WriteAllText((Join-Path $work 'registro.json'),($registro|ConvertTo-Json -Depth 24),[Text.UTF8Encoding]::new($false))}
function Leer([object]$Target,[string]$Interface,[string]$Method,[string]$Name){
    $methodInfo=([ETABSv1.cSapModel].Assembly.GetType('ETABSv1.'+$Interface)).GetMethods()|Where-Object Name -eq $Method
    if(@($methodInfo).Count -ne 1){throw "Firma no única $Interface.$Method"}
    $parameters=$methodInfo.GetParameters();[object[]]$values=@($Name)
    for($i=1;$i -lt $parameters.Length;$i++){
        $t=$parameters[$i].ParameterType
        if(-not $t.IsByRef){throw 'Solo getters con salidas por referencia admitidos.'}
        $t=$t.GetElementType()
        if($t -eq [string]){$values+=''}else{$values+=[Activator]::CreateInstance($t)}
    }
    Check ($methodInfo.Invoke($Target,$values)) ($Interface+'.'+$Method)
    $result=[ordered]@{}
    for($i=1;$i -lt $parameters.Length;$i++){
        $value=$values[$i]
        if($null -ne $value -and $value.GetType().IsEnum){$value=@{nombre=$value.ToString();valor=[int]$value}}
        $result[$parameters[$i].Name]=$value
    }
    return $result
}
foreach($fase in @('construccion','reapertura')){
    $app=$null;$cierre=$false
    try{
        $previos=@(Get-Process ETABS -ErrorAction SilentlyContinue|ForEach-Object Id)
        $helper=New-Object ETABSv1.Helper
        $app=$helper.CreateObject('C:\Program Files\Computers and Structures\ETABS 21\ETABS.exe')
        Check ($app.ApplicationStart()) 'ApplicationStart'
        $pids=@(Get-Process ETABS -ErrorAction SilentlyContinue|Where-Object {$_.Id -notin $previos}|ForEach-Object Id)
        $sap=$app.SapModel
        if($fase -eq 'construccion'){
            Check ($sap.InitializeNewModel([ETABSv1.eUnits]::kN_m_C)) 'InitializeNewModel'
            Check ($sap.File.NewBlank()) 'NewBlank'
            Check ($sap.SetPresentUnits([ETABSv1.eUnits]::kN_m_C)) 'SetPresentUnits solo construcción sintética'
            [string[]]$sn=@('N1');[double[]]$sh=@(3);[bool[]]$sm=@($true);[string[]]$ss=@('None');[bool[]]$sp=@($false);[double[]]$sl=@(0);[int[]]$sc=@(0)
            Check ($sap.Story.SetStories_2(0,1,[ref]$sn,[ref]$sh,[ref]$sm,[ref]$ss,[ref]$sp,[ref]$sl,[ref]$sc)) 'SetStories_2'
            Check ($sap.PropMaterial.SetMaterial('MAT_SINTETICO',[ETABSv1.eMatType]::Concrete,0,'','')) 'SetMaterial'
            Check ($sap.PropMaterial.SetMPIsotropic('MAT_SINTETICO',25000000,0.2,0.00001,0)) 'SetMPIsotropic'
            $registro.nombres_areas=@{}
            foreach($tipo in @('Ribbed','Waffle')){
                $enum=[Enum]::Parse([ETABSv1.eSlabType],$tipo)
                Check ($sap.PropArea.SetSlab($tipo,$enum,[ETABSv1.eShellType]::ShellThin,'MAT_SINTETICO',0.25,0,'','')) 'SetSlab'
                if($tipo -eq 'Ribbed'){Check ($sap.PropArea.SetSlabRibbed($tipo,0.25,0.05,0.12,0.1,0.6,1)) 'SetSlabRibbed'}
                else{Check ($sap.PropArea.SetSlabWaffle($tipo,0.25,0.05,0.12,0.1,0.6,0.7)) 'SetSlabWaffle'}
                $dx=if($tipo -eq 'Ribbed'){0.0}else{6.0}
                [double[]]$x=@($dx,($dx+4),($dx+4),$dx);[double[]]$y=@(0,0,3,3);[double[]]$z=@(3,3,3,3);[string]$name=''
                Check ($sap.AreaObj.AddByCoord(4,[ref]$x,[ref]$y,[ref]$z,[ref]$name,$tipo,('AREA_'+$tipo),'Global')) 'AddByCoord'
                Check ($sap.AreaObj.SetLocalAxes($name,30,[ETABSv1.eItemType]::Objects)) 'SetLocalAxes'
                $registro.nombres_areas[$tipo]=$name
            }
            Check ($sap.File.Save($edb)) 'Save solo construcción propia'
        }else{
            $registro.sha256_antes_reapertura=Hash $edb
            Check ($sap.File.OpenFile($edb)) 'OpenFile solo modelo propio'
        }
        $reads=[ordered]@{}
        foreach($tipo in @('Ribbed','Waffle')){
            $reads[$tipo]=@{slab=(Leer $sap.PropArea 'cPropArea' 'GetSlab' $tipo);parametros=(Leer $sap.PropArea 'cPropArea' ('GetSlab'+$tipo) $tipo);ejes=(Leer $sap.AreaObj 'cAreaObj' 'GetLocalAxes' $registro.nombres_areas[$tipo])}
        }
        $registro.fases+=@{fase=$fase;unidades=$sap.GetPresentUnits().ToString();lecturas=$reads;procesos_nuevos=$pids;guardado=($fase -eq 'construccion')}
    }catch{$registro.error=$_.Exception.Message}
    finally{
        if($null -ne $app){try{$rc=$app.ApplicationExit($false);$cierre=($rc -eq 0)}catch{$registro.error_cierre=$_.Exception.Message}}
        $registro.cierres+=@{fase=$fase;confirmado=$cierre}
        Publicar
    }
    if(-not $cierre -or $null -ne $registro.error){exit 2}
}
$registro.sha256_despues_reapertura=Hash $edb
Publicar
Write-Output 'Propiedades sintéticas guardadas y releídas; evaluar parámetros y ejes antes de aceptarlas.'
