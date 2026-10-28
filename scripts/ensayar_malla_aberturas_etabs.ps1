param(
    [Parameter(Mandatory=$true)][string]$CarpetaTrabajo,
    [switch]$ConfirmarEnsayoSintetico,
    [string]$ParticionesJson=''
)
# Ensayo acotado propio, no ejecutor de producción: modelo nuevo sintético; sin OpenFile/GetObject.
$ErrorActionPreference='Stop'
if (-not $ConfirmarEnsayoSintetico) { throw 'Requiere confirmar el ensayo sintético.' }
$workspace=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$work=[IO.Path]::GetFullPath($CarpetaTrabajo)
$limite=[IO.Path]::GetFullPath((Join-Path $workspace 'tmp'))+[IO.Path]::DirectorySeparatorChar
if (-not [IO.Path]::IsPathRooted($CarpetaTrabajo) -or -not $work.StartsWith($limite,[StringComparison]::OrdinalIgnoreCase)) { throw 'Trabajo absoluto dentro de tmp del proyecto requerido.' }
if (-not (Test-Path -LiteralPath $work -PathType Container) -or @(Get-ChildItem -LiteralPath $work -Force).Count -ne 0) { throw 'Trabajo existente y vacío requerido.' }
Add-Type -Path 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
$app=$null
$registro=[ordered]@{ datos_sinteticos=$true; finalidad='inspeccionar_malla_no_aprobar_ingenieria'; guardados=@(); escenarios=@(); instancia_nueva=$false; cierre_confirmado=$false; error=$null }
$bundle=$null
if($ParticionesJson){
    $bundle=([IO.File]::ReadAllText([IO.Path]::GetFullPath($ParticionesJson))|ConvertFrom-Json)
    if($bundle.contrato -ne 'draft2model.ensayo_triangulacion_sintetica' -or $bundle.datos_sinteticos -ne $true){throw 'Solo bundle sintético de ensayo requerido.'}
}
function Check([int]$Codigo,[string]$Metodo) { if ($Codigo -ne 0) { throw "$Metodo devolvio $Codigo" } }
function HashArchivo([string]$Ruta) {
    $alg=[Security.Cryptography.SHA256]::Create();$file=[IO.File]::OpenRead($Ruta)
    try { return [BitConverter]::ToString($alg.ComputeHash($file)).Replace('-','').ToLowerInvariant() }
    finally { $file.Dispose();$alg.Dispose() }
}
function EscribirRegistro {
    [IO.File]::WriteAllText((Join-Path $work 'registro.json'),($registro|ConvertTo-Json -Depth 30),[Text.UTF8Encoding]::new($false))
}
function Coordenadas([string]$Nombre) {
    [double]$x=0;[double]$y=0;[double]$z=0
    Check ($sap.PointElm.GetCoordCartesian($Nombre,[ref]$x,[ref]$y,[ref]$z,'Global')) 'PointElm.GetCoordCartesian'
    return ,@($x,$y,$z)
}
try {
    if($null -ne $bundle){$registro.sha256_particiones=(HashArchivo $ParticionesJson)}
    $previos=@(Get-Process ETABS -ErrorAction SilentlyContinue | ForEach-Object Id)
    $helper=New-Object ETABSv1.Helper
    $app=$helper.CreateObject('C:\Program Files\Computers and Structures\ETABS 21\ETABS.exe')
    Check ($app.ApplicationStart()) 'ApplicationStart'
    $registro.instancia_nueva=$true
    $registro.procesos_nuevos_observados=@(Get-Process ETABS -ErrorAction SilentlyContinue | Where-Object { $_.Id -notin $previos } | ForEach-Object Id)
    EscribirRegistro
    $sap=$app.SapModel
    foreach($caso in @('piso','muro','inclinado')) {
        Check ($sap.InitializeNewModel([ETABSv1.eUnits]::kN_m_C)) 'InitializeNewModel'
        Check ($sap.File.NewBlank()) 'File.NewBlank'
        Check ($sap.SetPresentUnits([ETABSv1.eUnits]::kN_m_C)) 'SetPresentUnits en modelo sintético propio'
        [string[]]$sn=@('N1');[double[]]$sh=@(3);[bool[]]$sm=@($true);[string[]]$ss=@('None')
        [bool[]]$sp=@($false);[double[]]$spl=@(0);[int[]]$sc=@(0)
        Check ($sap.Story.SetStories_2(0,1,[ref]$sn,[ref]$sh,[ref]$sm,[ref]$ss,[ref]$sp,[ref]$spl,[ref]$sc)) 'Story.SetStories_2'
        Check ($sap.PropMaterial.SetMaterial('MAT_SINTETICO',[ETABSv1.eMatType]::Concrete,0,'','')) 'PropMaterial.SetMaterial'
        Check ($sap.PropMaterial.SetMPIsotropic('MAT_SINTETICO',25000000,0.2,0.00001,0)) 'PropMaterial.SetMPIsotropic'
        if($caso -eq 'muro') { Check ($sap.PropArea.SetWall('SEC_SINTETICA',[ETABSv1.eWallPropType]::Specified,[ETABSv1.eShellType]::ShellThin,'MAT_SINTETICO',0.2,0,'','')) 'SetWall' }
        else { Check ($sap.PropArea.SetSlab('SEC_SINTETICA',[ETABSv1.eSlabType]::Slab,[ETABSv1.eShellType]::ShellThin,'MAT_SINTETICO',0.2,0,'','')) 'SetSlab' }
        $nombres=@()
        if($null -ne $bundle){
            $sources=@($bundle.escenarios|Where-Object caso -eq $caso)
            if($sources.Count -ne 1){throw 'Un escenario de triangulación exacto requerido.'}
            $mesh=$sources[0].triangulacion
            if($mesh.contrato -notin @('draft2model.triangulacion_particion','draft2model.corte_malla_niveles') -or $mesh.ejecutable -ne $false){throw 'Contrato de triangulación/corte no admitido.'}
            $pointMap=@{};$index=0
            foreach($node in $mesh.nodos){
                $index++;[string]$name='';$xyz=$node.xyz_m
                if($xyz.Count -ne 3 -or $pointMap.ContainsKey($node.id)){throw 'Nodo inválido o duplicado.'}
                Check ($sap.PointObj.AddCartesian([double]$xyz[0],[double]$xyz[1],[double]$xyz[2],[ref]$name,('P'+$index),'Global',$false,0)) 'PointObj.AddCartesian'
                $pointMap[$node.id]=$name
            }
            $index=0
            foreach($cell in $mesh.triangulos){
                $index++;[string[]]$points=@();[string]$name=''
                foreach($id in $cell.nodos){if(-not $pointMap.ContainsKey($id)){throw 'Triángulo con nodo ausente.'};$points+=$pointMap[$id]}
                if($points.Count -ne 3){throw 'Solo triángulos explícitos admitidos.'}
                Check ($sap.AreaObj.AddByPoint(3,[ref]$points,[ref]$name,'SEC_SINTETICA',('CELDA'+$index))) 'AreaObj.AddByPoint'
                Check ($sap.AreaObj.SetOpening($name,$false,[ETABSv1.eItemType]::Objects)) 'AreaObj.SetOpening false en pieza'
                $nombres+=@{nombre=$name;abertura=$false;celda=$cell.id}
            }
        }else{
        foreach($hueco in @($false,$true)) {
            [double[]]$x=if($hueco){@(1,2,2,1)}else{@(0,4,4,0)}
            [double[]]$v=if($hueco){@(1,1,2,2)}else{@(0,0,3,3)}
            [double[]]$y=@();[double[]]$z=@()
            foreach($valor in $v) {
                if($caso -eq 'muro') { $y+=0.;$z+=$valor }
                elseif($caso -eq 'inclinado') { $y+=$valor;$z+=$valor }
                else { $y+=$valor;$z+=3. }
            }
            [string]$name=''
            $prop=if($hueco){'None'}else{'SEC_SINTETICA'}
            $user=if($hueco){'HUECO_SINTETICO'}else{'HOST_SINTETICO'}
            Check ($sap.AreaObj.AddByCoord(4,[ref]$x,[ref]$y,[ref]$z,[ref]$name,$prop,$user,'Global')) 'AreaObj.AddByCoord'
            if (-not $name) { throw 'Nombre de área vacío.' }
            Check ($sap.AreaObj.SetOpening($name,$hueco,[ETABSv1.eItemType]::Objects)) 'AreaObj.SetOpening'
            [bool]$opening=$false
            Check ($sap.AreaObj.GetOpening($name,[ref]$opening)) 'AreaObj.GetOpening'
            if($opening -ne $hueco) { throw 'La designación de abertura no persiste.' }
            $nombres+=@{ nombre=$name; abertura=$hueco }
        }
        }
        $destino=Join-Path $work ($caso+'.edb')
        Check ($sap.File.Save($destino)) 'File.Save sintético'
        $registro.guardados+=@{caso=$caso;archivo=$destino;sha256=(HashArchivo $destino)}
        EscribirRegistro
        Check ($sap.Analyze.CreateAnalysisModel()) 'Analyze.CreateAnalysisModel'
        $areas=@()
        foreach($obj in $nombres) {
            [int]$numero=0;[string[]]$elm=@()
            $retElm=$sap.AreaObj.GetElm($obj.nombre,[ref]$numero,[ref]$elm)
            if($numero -ne $elm.Length) { throw 'Cantidad de elementos inconsistente.' }
            $elementos=@()
            foreach($en in $elm) {
                [int]$np=0;[string[]]$pn=@()
                Check ($sap.AreaElm.GetPoints($en,[ref]$np,[ref]$pn)) 'AreaElm.GetPoints'
                if($np -ne $pn.Length -or $np -lt 3) { throw 'Contorno de elemento incompleto.' }
                $puntos=@();foreach($point in $pn){$puntos+=@{nombre=$point;xyz=(Coordenadas $point)}}
                $elementos+=@{nombre=$en;puntos=$puntos}
            }
            $areas+=@{nombre=$obj.nombre;abertura=$obj.abertura;retorno_getelm=$retElm;elementos=$elementos}
        }
        $registro.escenarios+=@{caso=$caso;unidades=$sap.GetPresentUnits().ToString();areas=$areas;solver_ejecutado=$false}
        EscribirRegistro
    }
} catch {
    $registro.error=$_.Exception.Message
} finally {
    if($null -ne $app) {
        try { $code=$app.ApplicationExit($false);$registro.cierre_confirmado=($code -eq 0);$registro.retorno_cierre=$code }
        catch { $registro.error_cierre=$_.Exception.Message }
    }
    EscribirRegistro
}
if ($null -ne $registro.error -or -not $registro.cierre_confirmado) { exit 2 }
Write-Output 'Ensayo sintético conservado; falta evaluar cobertura geométrica. No aprueba ingeniería.'
