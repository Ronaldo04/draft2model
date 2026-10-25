<#
.SYNOPSIS
Relectura de SOLO LECTURA de la copia privada de un EDB guardado, en una instancia ETABS NUEVA y propia.
Requiere Windows PowerShell 5.1.

.DESCRIPTION
Contrato: solicitud draft2model.etabs_solicitud 0.1.0 con operacion 'verificar_modelo_guardado'
(preparada por draft2model.verificacion_modelo_guardado); respuesta draft2model.etabs_respuesta 0.1.0.

- Nunca usa GetObject ni la instancia activa del usuario: CreateObjectProgID + ApplicationStart.
  En modo real identifica exactamente un proceso ETABS nuevo; en modo doble rechaza la DLL de CSI.
- Lector 0.2.0: además relee apoyos, diafragmas (definición y asignación por punto; el de área solo se
  registra), patrones, casos, combinaciones, funciones, campos de tablas de VISUALIZACIÓN (GetTableForDisplayArray,
  de solo lectura) y marcas de ejecución. Una solicitud de otra versión de lector se rechaza.
- Lector 0.3.0: además relee losas nervadas (GetSlabRibbed) y casetonadas (GetSlabWaffle) con sus
  parámetros de API; la orientación local de áreas se sigue leyendo con GetLocalAxes.
- Lista blanca reflejada: antes de crear la instancia, cada método se resuelve por reflexión y su firma
  debe coincidir EXACTAMENTE con la lista (ETABSv1 1.29.0.0). Solo lectores Get*/GetNameList y el ciclo
  de vida imprescindible: CreateObjectProgID, ApplicationStart, Hide, OpenFile (de la copia privada),
  GetModelFilename, GetPresentUnits y ApplicationExit(false) de la instancia propia.
- No guarda, no analiza, no fija unidades ni modifica geometría, asignaciones, cargas o masa. Lector 0.4.0:
  las unidades presentes se REGISTRAN tal como están (p. ej. N_mm_C) y los valores se devuelven sin convertir;
  la normalización dimensional y su evidencia las hace Python. Nunca SetPresentUnits.
- Lector 0.4.0: GetOpening en cada área (host False / hueco True), sin afirmar efecto estructural.
- SHA256 de la copia antes de abrir, tras leer y tras cerrar; cualquier cambio invalida la lectura.
- Los valores esperados NO viajan al lector: la solicitud solo nombra las propiedades a consultar.
  Todo retorno distinto de 0 se registra (retornos_no_cero) y no se rellena con supuestos.
- La instancia propia se cierra sin guardar también tras errores; un cierre no confirmado es error.

Códigos de salida: 0 correcto; 10 solicitud; 20 API no disponible; 30 API/cierre; 40 precondición;
41 evidencia; 42 firma; 50 inesperado.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Solicitud,
    [Parameter(Mandatory = $true)][string]$Respuesta,
    [Parameter(Mandatory = $true)][string]$Sha256Solicitud,
    [Parameter(Mandatory = $true)][ValidateSet('real', 'doble')][string]$Modo
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$ProgId = 'CSI.ETABS.API.ETABSObject'
$TokenCsi = '453d728ef24c6f5e'
$UnidadesPlan = 'kN_m_C'
$Codigos = @{ solicitud = 10; api_no_disponible = 20; api = 30; cierre_propio = 30; precondicion = 40; evidencia = 41; firma = 42; inesperado = 50 }

# Lista blanca exacta (reflejada de ETABSv1.dll 1.29.0.0 el 19-10-2026). Nada fuera de ella se invoca.
$Firmas = [ordered]@{
    'cHelper.CreateObjectProgID'       = 'cOAPI (String progID)'
    'cOAPI.ApplicationStart'           = 'Int32 ()'
    'cOAPI.Hide'                       = 'Int32 ()'
    'cOAPI.ApplicationExit'            = 'Int32 (Boolean FileSave)'
    'cFile.OpenFile'                   = 'Int32 (String FileName)'
    'cSapModel.GetModelFilename'       = 'String (Boolean IncludePath)'
    'cSapModel.GetVersion'             = 'Int32 (String& Version, Double& MyVersionNumber)'
    'cSapModel.GetPresentUnits'        = 'eUnits ()'
    'cStory.GetStories_2'              = 'Int32 (Double& BaseElevation, Int32& NumberStories, String[]& StoryNames, Double[]& StoryElevations, Double[]& StoryHeights, Boolean[]& IsMasterStory, String[]& SimilarToStory, Boolean[]& SpliceAbove, Double[]& SpliceHeight, Int32[]& color)'
    'cPointObj.GetNameList'            = 'Int32 (Int32& NumberNames, String[]& MyName)'
    'cPointObj.GetCoordCartesian'      = 'Int32 (String Name, Double& X, Double& Y, Double& Z, String CSys)'
    'cPointObj.GetLoadForce'           = 'Int32 (String Name, Int32& NumberItems, String[]& PointName, String[]& LoadPat, Int32[]& LcStep, String[]& CSys, Double[]& F1, Double[]& F2, Double[]& F3, Double[]& M1, Double[]& M2, Double[]& M3, eItemType ItemType)'
    'cFrameObj.GetNameList'            = 'Int32 (Int32& NumberNames, String[]& MyName)'
    'cFrameObj.GetPoints'              = 'Int32 (String Name, String& Point1, String& Point2)'
    'cFrameObj.GetSection'             = 'Int32 (String Name, String& PropName, String& SAuto)'
    'cFrameObj.GetLoadDistributed'     = 'Int32 (String Name, Int32& NumberItems, String[]& FrameName, String[]& LoadPat, Int32[]& MyType, String[]& CSys, Int32[]& Dir, Double[]& RD1, Double[]& RD2, Double[]& Dist1, Double[]& Dist2, Double[]& Val1, Double[]& Val2, eItemType ItemType)'
    'cAreaObj.GetNameList'             = 'Int32 (Int32& NumberNames, String[]& MyName)'
    'cAreaObj.GetPoints'               = 'Int32 (String Name, Int32& NumberPoints, String[]& Point)'
    'cAreaObj.GetProperty'             = 'Int32 (String Name, String& PropName)'
    'cAreaObj.GetLocalAxes'            = 'Int32 (String Name, Double& Ang, Boolean& Advanced)'
    'cAreaObj.GetOpening'              = 'Int32 (String Name, Boolean& IsOpening)'
    'cAreaObj.GetLoadUniform'          = 'Int32 (String Name, Int32& NumberItems, String[]& AreaName, String[]& LoadPat, String[]& CSys, Int32[]& Dir, Double[]& Value, eItemType ItemType)'
    'cPropArea.GetNameList'            = 'Int32 (Int32& NumberNames, String[]& MyName, Int32 PropType)'
    'cPropArea.GetSlab'                = 'Int32 (String Name, eSlabType& SlabType, eShellType& ShellType, String& MatProp, Double& Thickness, Int32& color, String& notes, String& GUID)'
    'cPropArea.GetWall'                = 'Int32 (String Name, eWallPropType& WallPropType, eShellType& ShellType, String& MatProp, Double& Thickness, Int32& color, String& notes, String& GUID)'
    'cPropArea.GetSlabRibbed'          = 'Int32 (String Name, Double& OverallDepth, Double& SlabThickness, Double& StemWidthTop, Double& StemWidthBot, Double& RibSpacing, Int32& RibsParallelTo)'
    'cPropArea.GetSlabWaffle'          = 'Int32 (String Name, Double& OverallDepth, Double& SlabThickness, Double& StemWidthTop, Double& StemWidthBot, Double& RibSpacingDir1, Double& RibSpacingDir2)'
    'cPropFrame.GetNameList'           = 'Int32 (Int32& NumberNames, String[]& MyName, eFramePropType PropType)'
    'cPropFrame.GetRectangle'          = 'Int32 (String Name, String& FileName, String& MatProp, Double& T3, Double& T2, Int32& Color, String& Notes, String& GUID)'
    'cPropMaterial.GetNameList'        = 'Int32 (Int32& NumberNames, String[]& MyName, eMatType MatType)'
    'cPropMaterial.GetMaterial'        = 'Int32 (String Name, eMatType& MatType, Int32& Color, String& Notes, String& GUID)'
    'cPropMaterial.GetMPIsotropic'     = 'Int32 (String Name, Double& E, Double& U, Double& A, Double& G, Double Temp)'
    'cPropMaterial.GetWeightAndMass'   = 'Int32 (String Name, Double& W, Double& M, Double Temp)'
    'cPropMaterial.GetMassSource_1'    = 'Int32 (Boolean& IncludeElements, Boolean& IncludeAddedMass, Boolean& IncludeLoads, Int32& NumberLoads, String[]& LoadPat, Double[]& sf)'
    # Lector 0.2.0: apoyos, diafragmas, patrones, casos, combinaciones, funciones, tablas de visualización y marcas.
    'cPointObj.GetRestraint'           = 'Int32 (String Name, Boolean[]& Value)'
    'cPointObj.GetDiaphragm'           = 'Int32 (String Name, eDiaphragmOption& DiaphragmOption, String& DiaphragmName)'
    'cAreaObj.GetDiaphragm'            = 'Int32 (String Name, String& DiaphragmName)'
    'cDiaphragm.GetNameList'           = 'Int32 (Int32& NumberNames, String[]& MyName)'
    'cDiaphragm.GetDiaphragm'          = 'Int32 (String Name, Boolean& SemiRigid)'
    'cLoadPatterns.GetNameList'        = 'Int32 (Int32& NumberNames, String[]& MyName)'
    'cLoadPatterns.GetLoadType'        = 'Int32 (String Name, eLoadPatternType& MyType)'
    'cLoadPatterns.GetSelfWTMultiplier' = 'Int32 (String Name, Double& SelfWTMultiplier)'
    'cLoadCases.GetNameList'           = 'Int32 (Int32& NumberNames, String[]& MyName, eLoadCaseType CaseType)'
    'cLoadCases.GetTypeOAPI'           = 'Int32 (String Name, eLoadCaseType& CaseType, Int32& SubType)'
    'cCaseStaticLinear.GetLoads'       = 'Int32 (String Name, Int32& NumberLoads, String[]& LoadType, String[]& LoadName, Double[]& SF)'
    'cCaseModalEigen.GetNumberModes'   = 'Int32 (String Name, Int32& MaxModes, Int32& MinModes)'
    'cCaseModalEigen.GetParameters'    = 'Int32 (String Name, Double& EigenShiftFreq, Double& EigenCutOff, Double& EigenTol, Int32& AllowAutoFreqShift)'
    'cCaseModalEigen.GetLoads'         = 'Int32 (String Name, Int32& NumberLoads, String[]& LoadType, String[]& LoadName, Double[]& TargetPar, Boolean[]& StaticCorrect)'
    'cCaseResponseSpectrum.GetModalCase' = 'Int32 (String Name, String& ModalCase)'
    'cCaseResponseSpectrum.GetLoads'   = 'Int32 (String Name, Int32& NumberLoads, String[]& LoadName, String[]& Func, Double[]& SF, String[]& CSys, Double[]& Ang)'
    'cCaseResponseSpectrum.GetEccentricity' = 'Int32 (String Name, Double& Eccen)'
    'cCaseResponseSpectrum.GetDampConstant' = 'Int32 (String Name, Double& Damp)'
    'cCaseResponseSpectrum.GetDampType' = 'Int32 (String Name, Int32& DampType)'
    'cCaseResponseSpectrum.GetModalComb_1' = 'Int32 (String Name, Int32& MyType, Double& F1, Double& F2, Int32& PeriodicRigidCombType, Double& Td)'
    'cFunction.GetNameList'            = 'Int32 (Int32& NumberNames, String[]& MyName, Int32 FuncType)'
    'cFunction.GetValues'              = 'Int32 (String Name, Int32& NumberItems, Double[]& MyTime, Double[]& Value)'
    'cCombo.GetNameList'               = 'Int32 (Int32& NumberNames, String[]& MyName)'
    'cCombo.GetTypeOAPI'               = 'Int32 (String name, Int32& ComboType)'
    'cCombo.GetCaseList'               = 'Int32 (String Name, Int32& NumberItems, eCNameType[]& CNameType, String[]& CName, Double[]& SF)'
    'cAnalyze.GetRunCaseFlag'          = 'Int32 (Int32& NumberItems, String[]& CaseName, Boolean[]& Run)'
    'cDatabaseTables.GetTableForDisplayArray' = 'Int32 (String TableKey, String[]& FieldKeyList, String GroupName, Int32& TableVersion, String[]& FieldsKeysIncluded, Int32& NumberRecords, String[]& TableData)'
}
$VersionLector = '0.4.0'
$Metodos = @{}
$Retornos = New-Object System.Collections.ArrayList
$RutasPrivadas = New-Object System.Collections.ArrayList

# -- utilidades ----------------------------------------------------------------

function New-Fallo([string]$Tipo, [string]$Mensaje) {
    $excepcion = New-Object System.InvalidOperationException($Mensaje)
    $excepcion.Data['draft2model_tipo'] = $Tipo
    return $excepcion
}

function Get-Sha256([string]$Ruta) {
    $flujo = [IO.File]::OpenRead($Ruta); $algoritmo = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($algoritmo.ComputeHash($flujo))).Replace('-', '').ToLowerInvariant() }
    finally { $flujo.Dispose(); $algoritmo.Dispose() }
}

function Get-RutaSegura([string]$Ruta) {
    if (-not [IO.Path]::IsPathRooted($Ruta)) { throw (New-Fallo 'solicitud' 'Ruta no absoluta.') }
    $completa = [IO.Path]::GetFullPath($Ruta)
    if (-not [string]::Equals($completa, $Ruta, [StringComparison]::OrdinalIgnoreCase)) { throw (New-Fallo 'solicitud' 'Ruta no normalizada.') }
    $actual = $completa
    while (-not [string]::IsNullOrEmpty($actual)) {
        $item = Get-Item -LiteralPath $actual -Force
        if (($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) { throw (New-Fallo 'solicitud' 'Ruta enlazada no permitida.') }
        $padre = Split-Path -Parent $actual
        if ([string]::IsNullOrEmpty($padre) -or $padre -eq $actual) { break }
        $actual = $padre
    }
    [void]$RutasPrivadas.Add($completa)
    return $completa
}

function Get-MensajePublico([string]$Mensaje) {
    # Sin rutas absolutas en mensajes públicos: la ruta privada queda en la carpeta de la corrida.
    foreach ($ruta in $RutasPrivadas) { $Mensaje = $Mensaje.Replace($ruta, '<ruta>') }
    return ($Mensaje -replace '[A-Za-z]:\\[^\s''"]*', '<ruta>')
}

function Add-Traza([string]$Evento, $Datos) {
    $linea = [ordered]@{ evento = $Evento; datos = $Datos; utc = [DateTime]::UtcNow.ToString('o') }
    [IO.File]::AppendAllText((Join-Path (Split-Path -Parent $Respuesta) 'traza_verificacion.jsonl'),
        (ConvertTo-Json -InputObject $linea -Depth 8 -Compress) + "`n", $Utf8)
}

function Get-Base($Objeto) {
    if ($Objeto -is [System.Management.Automation.PSObject]) { return $Objeto.PSObject.BaseObject }
    return $Objeto
}

# Configuración 0.5: sección L nativa e inserción. Solo se resuelven si la consulta las pide (los dobles previos no las definen).
$FirmasOpcionales = [ordered]@{
    'cPropFrame.GetConcreteL'          = 'Int32 (String Name, String& FileName, String& MatProp, Double& T3, Double& T2, Double& Tf, Double& TwC, Double& TwT, Boolean& MirrorAbout2, Boolean& MirrorAbout3, Int32& Color, String& Notes, String& GUID)'
    'cFrameObj.GetInsertionPoint'      = 'Int32 (String Name, Int32& CardinalPoint, Boolean& Mirror2, Boolean& StiffTransform, Double[]& Offset1, Double[]& Offset2, String& CSys)'
}
$CamposConsultaOpcionales = @{ secciones_l = 'cPropFrame.GetConcreteL'; insercion_frames = 'cFrameObj.GetInsertionPoint' }

function Resolve-Firmas($Asm, $Consulta) {
    foreach ($campo in $CamposConsultaOpcionales.Keys) {
        if ($null -ne $Consulta.PSObject.Properties[$campo]) { $Firmas[$CamposConsultaOpcionales[$campo]] = $FirmasOpcionales[$CamposConsultaOpcionales[$campo]] }
    }
    foreach ($clave in @($Firmas.Keys)) {
        $interfaz, $nombre = $clave.Split('.')
        $tipo = $Asm.GetType("ETABSv1.$interfaz")
        if ($null -eq $tipo) { throw (New-Fallo 'firma' "La DLL no define ETABSv1.$interfaz.") }
        $Metodos[$clave] = $null
        foreach ($candidato in $tipo.GetMethods()) {
            if ($candidato.Name -ne $nombre) { continue }
            $firma = $candidato.ReturnType.Name + ' (' + ((@($candidato.GetParameters() | ForEach-Object { $_.ParameterType.Name + ' ' + $_.Name })) -join ', ') + ')'
            if ($firma -ceq $Firmas[$clave]) { $Metodos[$clave] = $candidato }
        }
        if ($null -eq $Metodos[$clave]) { throw (New-Fallo 'firma' "Firma de $clave distinta de la lista blanca.") }
    }
}

function Get-ArregloEnum([string]$Clave, [int]$Indice) {
    $tipo = $Metodos[$Clave].GetParameters()[$Indice].ParameterType
    if ($tipo.IsByRef) { $tipo = $tipo.GetElementType() }
    return ,([Array]::CreateInstance($tipo.GetElementType(), 0))
}

function Get-Enum([string]$Clave, [int]$Indice, [int]$Numero) {
    $tipo = $Metodos[$Clave].GetParameters()[$Indice].ParameterType
    if ($tipo.IsByRef) { $tipo = $tipo.GetElementType() }
    return [Enum]::ToObject($tipo, $Numero)
}

function Invoke-Api([string]$Clave, $Objeto, [object[]]$Valores) {
    try { $retorno = $Metodos[$Clave].Invoke((Get-Base $Objeto), $Valores) }
    catch {
        $interna = $_.Exception
        while ($null -ne $interna.InnerException) { $interna = $interna.InnerException }
        throw (New-Fallo 'api' "Excepción de la API en ${Clave}: $($interna.Message)")
    }
    return $retorno
}

# Lector: retorno 0 -> valores; otro retorno -> registrado y $null (nunca se rellena con supuestos).
function Read-Api([string]$Clave, $Objeto, [string]$Nombre, [object[]]$Valores) {
    $retorno = Invoke-Api $Clave $Objeto $Valores
    if ([int]$retorno -ne 0) {
        [void]$Retornos.Add([ordered]@{ metodo = $Clave; objeto = $Nombre; codigo = [int]$retorno })
        return $null
    }
    return ,$Valores
}

function Assert-Cero([string]$Clave, $Objeto, [object[]]$Valores, [string]$Tipo) {
    $retorno = Invoke-Api $Clave $Objeto $Valores
    if ([int]$retorno -ne 0) { throw (New-Fallo $Tipo "$Clave devolvió $retorno.") }
}

function ConvertTo-Lista($Valor) {
    if ($null -eq $Valor) { return ,@() }
    return ,@($Valor)
}

function ConvertTo-Enum($Valor) { return [ordered]@{ nombre = $Valor.ToString(); valor = [int]$Valor } }

function Read-Nombres([string]$Clave, $Objeto, [object[]]$Extra) {
    $valores = Read-Api $Clave $Objeto '*' (@([int]0, [string[]]@()) + $Extra)
    if ($null -eq $valores) { return $null }
    $nombres = ConvertTo-Lista $valores[1]
    if ([int]$valores[0] -ne $nombres.Count -or @($nombres | Select-Object -Unique).Count -ne $nombres.Count) {
        throw (New-Fallo 'api' "$Clave devolvió una lista incoherente.")
    }
    return ,([string[]]$nombres)
}

function Test-Consulta($Valor) {
    $campos = @('losas', 'losas_nervadas', 'losas_casetonadas', 'muros', 'rectangulos', 'materiales', 'diafragmas', 'patrones', 'casos_estaticos', 'casos_modales',
        'casos_espectrales', 'combinaciones', 'funciones', 'tablas')
    if ($Valor -is [Management.Automation.PSCustomObject]) {
        foreach ($campo in $CamposConsultaOpcionales.Keys) { if ($null -ne $Valor.PSObject.Properties[$campo]) { $campos += $campo } }
    }
    if ($Valor -isnot [Management.Automation.PSCustomObject] -or @($Valor.PSObject.Properties.Name).Count -ne $campos.Count -or
        @($Valor.PSObject.Properties.Name | Where-Object { $campos -notcontains $_ }).Count) { throw (New-Fallo 'solicitud' 'Consulta inválida.') }
    foreach ($campo in $campos) {
        $lista = $Valor.$campo
        if ($null -eq $lista -or $lista -isnot [array]) { $lista = @($lista | Where-Object { $null -ne $_ }) }
        foreach ($item in $lista) { if ($item -isnot [string] -or [string]::IsNullOrWhiteSpace($item)) { throw (New-Fallo 'solicitud' 'Nombre de consulta inválido.') } }
        if (@($lista | Select-Object -Unique).Count -ne @($lista).Count) { throw (New-Fallo 'solicitud' 'Consulta con nombres repetidos.') }
    }
}

# -- lectura ---------------------------------------------------------------------

function Read-Modelo($Sap, $Consulta) {
    $lec = [ordered]@{}
    $story = $Sap.Story; $puntos = $Sap.PointObj; $frames = $Sap.FrameObj; $areas = $Sap.AreaObj
    $propArea = $Sap.PropArea; $propFrame = $Sap.PropFrame; $propMat = $Sap.PropMaterial

    $v = Read-Api 'cStory.GetStories_2' $story '*' @([double]0, [int]0, [string[]]@(), [double[]]@(), [double[]]@(), [bool[]]@(), [string[]]@(), [bool[]]@(), [double[]]@(), [int[]]@())
    if ($null -eq $v) { throw (New-Fallo 'api' 'Los pisos no son legibles.') }
    $lec.pisos = [ordered]@{ base = [double]$v[0]; nombres = (ConvertTo-Lista $v[2]); elevaciones = (ConvertTo-Lista $v[3]); alturas = (ConvertTo-Lista $v[4]) }

    $nombresPuntos = Read-Nombres 'cPointObj.GetNameList' $puntos @()
    if ($null -eq $nombresPuntos) { throw (New-Fallo 'api' 'La lista de puntos no es legible.') }
    $coordenadas = [ordered]@{}; $cargasPunto = [ordered]@{}
    foreach ($n in $nombresPuntos) {
        $c = Read-Api 'cPointObj.GetCoordCartesian' $puntos $n @($n, [double]0, [double]0, [double]0, 'Global')
        if ($null -ne $c) { $coordenadas[$n] = @([double]$c[1], [double]$c[2], [double]$c[3]) }
        $f = Read-Api 'cPointObj.GetLoadForce' $puntos $n (@($n, [int]0, [string[]]@(), [string[]]@(), [int[]]@(), [string[]]@()) + @(1..6 | ForEach-Object { ,([double[]]@()) }) + @(Get-Enum 'cPointObj.GetLoadForce' 12 0))
        if ($null -ne $f) {
            $items = New-Object System.Collections.ArrayList
            for ($i = 0; $i -lt [int]$f[1]; $i++) {
                [void]$items.Add([ordered]@{ objeto = [string]$f[2][$i]; patron = [string]$f[3][$i]; csys = [string]$f[5][$i]
                    valores = @([double]$f[6][$i], [double]$f[7][$i], [double]$f[8][$i], [double]$f[9][$i], [double]$f[10][$i], [double]$f[11][$i]) })
            }
            $cargasPunto[$n] = @($items)
        }
    }
    $lec.puntos = [ordered]@{ nombres = @($nombresPuntos); coordenadas = $coordenadas }
    $lec.cargas_punto = $cargasPunto

    $nombresFrames = Read-Nombres 'cFrameObj.GetNameList' $frames @()
    if ($null -eq $nombresFrames) { throw (New-Fallo 'api' 'La lista de frames no es legible.') }
    $ptsFrame = [ordered]@{}; $secciones = [ordered]@{}; $cargasFrame = [ordered]@{}
    foreach ($n in $nombresFrames) {
        $p = Read-Api 'cFrameObj.GetPoints' $frames $n @($n, '', '')
        if ($null -ne $p) { $ptsFrame[$n] = @([string]$p[1], [string]$p[2]) }
        $s = Read-Api 'cFrameObj.GetSection' $frames $n @($n, '', '')
        if ($null -ne $s) { $secciones[$n] = [string]$s[1] }
        $d = Read-Api 'cFrameObj.GetLoadDistributed' $frames $n (@($n, [int]0, [string[]]@(), [string[]]@(), [int[]]@(), [string[]]@(), [int[]]@()) + @(1..6 | ForEach-Object { ,([double[]]@()) }) + @(Get-Enum 'cFrameObj.GetLoadDistributed' 13 0))
        if ($null -ne $d) {
            $items = New-Object System.Collections.ArrayList
            for ($i = 0; $i -lt [int]$d[1]; $i++) {
                [void]$items.Add([ordered]@{ objeto = [string]$d[2][$i]; patron = [string]$d[3][$i]; tipo = [int]$d[4][$i]; csys = [string]$d[5][$i]
                    dir = [int]$d[6][$i]; rd1 = [double]$d[7][$i]; rd2 = [double]$d[8][$i]; val1 = [double]$d[11][$i]; val2 = [double]$d[12][$i] })
            }
            $cargasFrame[$n] = @($items)
        }
    }
    $lec.frames = [ordered]@{ nombres = @($nombresFrames); puntos = $ptsFrame; secciones = $secciones }
    if ($null -ne $Consulta.PSObject.Properties['insercion_frames']) {
        $insercion = [ordered]@{}
        foreach ($n in @($Consulta.insercion_frames)) {
            $q = Read-Api 'cFrameObj.GetInsertionPoint' $frames $n @($n, [int]0, $false, $false, [double[]]@(), [double[]]@(), '')
            if ($null -ne $q) { $insercion[$n] = [ordered]@{ cardinal = [int]$q[1]; mirror2 = [bool]$q[2]; stiff_transform = [bool]$q[3]
                offset1 = @($q[4] | ForEach-Object { [double]$_ }); offset2 = @($q[5] | ForEach-Object { [double]$_ }); csys = [string]$q[6] } }
        }
        $lec.frames.insercion = $insercion
    }
    $lec.cargas_frame = $cargasFrame

    $nombresAreas = Read-Nombres 'cAreaObj.GetNameList' $areas @()
    if ($null -eq $nombresAreas) { throw (New-Fallo 'api' 'La lista de áreas no es legible.') }
    $ptsArea = [ordered]@{}; $propiedades = [ordered]@{}; $ejes = [ordered]@{}; $cargasArea = [ordered]@{}; $huecos = [ordered]@{}
    foreach ($n in $nombresAreas) {
        $p = Read-Api 'cAreaObj.GetPoints' $areas $n @($n, [int]0, [string[]]@())
        if ($null -ne $p) {
            $lista = ConvertTo-Lista $p[2]
            if ([int]$p[1] -ne $lista.Count) { throw (New-Fallo 'api' "GetPoints de un área devolvió un recuento incoherente.") }
            $ptsArea[$n] = @($lista | ForEach-Object { [string]$_ })
        }
        $q = Read-Api 'cAreaObj.GetProperty' $areas $n @($n, '')
        if ($null -ne $q) { $propiedades[$n] = [string]$q[1] }
        $h = Read-Api 'cAreaObj.GetOpening' $areas $n @($n, $false)
        if ($null -ne $h) { $huecos[$n] = [bool]$h[1] }
        $x = Read-Api 'cAreaObj.GetLocalAxes' $areas $n @($n, [double]0, $false)
        if ($null -ne $x) { $ejes[$n] = [ordered]@{ angulo_deg = [double]$x[1]; avanzado = [bool]$x[2] } }
        $u = Read-Api 'cAreaObj.GetLoadUniform' $areas $n @($n, [int]0, [string[]]@(), [string[]]@(), [string[]]@(), [int[]]@(), [double[]]@(), (Get-Enum 'cAreaObj.GetLoadUniform' 7 0))
        if ($null -ne $u) {
            $items = New-Object System.Collections.ArrayList
            for ($i = 0; $i -lt [int]$u[1]; $i++) {
                [void]$items.Add([ordered]@{ objeto = [string]$u[2][$i]; patron = [string]$u[3][$i]; csys = [string]$u[4][$i]; dir = [int]$u[5][$i]; valor = [double]$u[6][$i] })
            }
            $cargasArea[$n] = @($items)
        }
    }
    $lec.areas = [ordered]@{ nombres = @($nombresAreas); puntos = $ptsArea; propiedades = $propiedades; ejes = $ejes; aberturas = $huecos }
    $lec.cargas_area = $cargasArea

    $nombresPA = Read-Nombres 'cPropArea.GetNameList' $propArea @([int]0)
    $losas = [ordered]@{}; $muros = [ordered]@{}
    foreach ($n in @($Consulta.losas)) {
        $s = Read-Api 'cPropArea.GetSlab' $propArea $n @($n, (Get-Enum 'cPropArea.GetSlab' 1 0), (Get-Enum 'cPropArea.GetSlab' 2 0), '', [double]0, [int]0, '', '')
        if ($null -ne $s) { $losas[$n] = [ordered]@{ subtipo = (ConvertTo-Enum $s[1]); shell = (ConvertTo-Enum $s[2]); material = [string]$s[3]; espesor = [double]$s[4] } }
    }
    foreach ($n in @($Consulta.muros)) {
        $s = Read-Api 'cPropArea.GetWall' $propArea $n @($n, (Get-Enum 'cPropArea.GetWall' 1 1), (Get-Enum 'cPropArea.GetWall' 2 0), '', [double]0, [int]0, '', '')
        if ($null -ne $s) { $muros[$n] = [ordered]@{ subtipo = (ConvertTo-Enum $s[1]); shell = (ConvertTo-Enum $s[2]); material = [string]$s[3]; espesor = [double]$s[4] } }
    }
    $nervadas = [ordered]@{}; $casetonadas = [ordered]@{}
    foreach ($n in @($Consulta.losas_nervadas)) {
        $s = Read-Api 'cPropArea.GetSlabRibbed' $propArea $n @($n, [double]0, [double]0, [double]0, [double]0, [double]0, [int]0)
        if ($null -ne $s) { $nervadas[$n] = [ordered]@{ OverallDepth = [double]$s[1]; SlabThickness = [double]$s[2]; StemWidthTop = [double]$s[3]
            StemWidthBot = [double]$s[4]; RibSpacing = [double]$s[5]; RibsParallelTo = [int]$s[6] } }
    }
    foreach ($n in @($Consulta.losas_casetonadas)) {
        $s = Read-Api 'cPropArea.GetSlabWaffle' $propArea $n @($n, [double]0, [double]0, [double]0, [double]0, [double]0, [double]0)
        if ($null -ne $s) { $casetonadas[$n] = [ordered]@{ OverallDepth = [double]$s[1]; SlabThickness = [double]$s[2]; StemWidthTop = [double]$s[3]
            StemWidthBot = [double]$s[4]; RibSpacingDir1 = [double]$s[5]; RibSpacingDir2 = [double]$s[6] } }
    }
    $lec.propiedades_area = [ordered]@{ nombres = @(if ($null -eq $nombresPA) { } else { $nombresPA }); losas = $losas; muros = $muros
        nervadas = $nervadas; casetonadas = $casetonadas }

    $nombresPF = Read-Nombres 'cPropFrame.GetNameList' $propFrame @((Get-Enum 'cPropFrame.GetNameList' 2 0))
    $rect = [ordered]@{}
    foreach ($n in @($Consulta.rectangulos)) {
        $r = Read-Api 'cPropFrame.GetRectangle' $propFrame $n @($n, '', '', [double]0, [double]0, [int]0, '', '')
        if ($null -ne $r) { $rect[$n] = [ordered]@{ material = [string]$r[2]; t3 = [double]$r[3]; t2 = [double]$r[4] } }
    }
    $lec.propiedades_frame = [ordered]@{ nombres = @(if ($null -eq $nombresPF) { } else { $nombresPF }); rectangulos = $rect }
    if ($null -ne $Consulta.PSObject.Properties['secciones_l']) {
        $seccionesL = [ordered]@{}
        foreach ($n in @($Consulta.secciones_l)) {
            $r = Read-Api 'cPropFrame.GetConcreteL' $propFrame $n @($n, '', '', [double]0, [double]0, [double]0, [double]0, [double]0, $false, $false, [int]0, '', '')
            if ($null -ne $r) { $seccionesL[$n] = [ordered]@{ material = [string]$r[2]; t3 = [double]$r[3]; t2 = [double]$r[4]; tf = [double]$r[5]
                twc = [double]$r[6]; twt = [double]$r[7]; espejo2 = [bool]$r[8]; espejo3 = [bool]$r[9] } }
        }
        $lec.propiedades_frame.secciones_l = $seccionesL
    }

    $nombresMat = Read-Nombres 'cPropMaterial.GetNameList' $propMat @((Get-Enum 'cPropMaterial.GetNameList' 2 0))
    $detalle = [ordered]@{}
    foreach ($n in @($Consulta.materiales)) {
        $t = Read-Api 'cPropMaterial.GetMaterial' $propMat $n @($n, (Get-Enum 'cPropMaterial.GetMaterial' 1 0), [int]0, '', '')
        $i = Read-Api 'cPropMaterial.GetMPIsotropic' $propMat $n @($n, [double]0, [double]0, [double]0, [double]0, [double]0)
        $w = Read-Api 'cPropMaterial.GetWeightAndMass' $propMat $n @($n, [double]0, [double]0, [double]0)
        if ($null -ne $t -and $null -ne $i -and $null -ne $w) {
            $detalle[$n] = [ordered]@{ tipo = (ConvertTo-Enum $t[1]); E = [double]$i[1]; U = [double]$i[2]; A = [double]$i[3]; G = [double]$i[4]
                W = [double]$w[1]; M = [double]$w[2] }
        }
    }
    $lec.materiales = [ordered]@{ nombres = @(if ($null -eq $nombresMat) { } else { $nombresMat }); detalle = $detalle }

    $m = Read-Api 'cPropMaterial.GetMassSource_1' $propMat '*' @($false, $false, $false, [int]0, [string[]]@(), [double[]]@())
    if ($null -eq $m) { throw (New-Fallo 'api' 'La fuente de masa no es legible.') }
    $patrones = ConvertTo-Lista $m[4]; $factores = ConvertTo-Lista $m[5]
    if ([int]$m[3] -ne $patrones.Count -or $patrones.Count -ne $factores.Count) { throw (New-Fallo 'api' 'Fuente de masa incoherente.') }
    $lec.fuente_masa = [ordered]@{ incluir_elementos = [bool]$m[0]; incluir_masa_adicional = [bool]$m[1]; incluir_cargas = [bool]$m[2]
        patrones = @($patrones | ForEach-Object { [string]$_ }); factores = @($factores | ForEach-Object { [double]$_ }) }
    Read-Configuracion $Sap $Consulta $lec @($nombresPuntos) @($nombresAreas)
    return $lec
}

function ConvertTo-Nombres($Lista) { if ($null -eq $Lista) { return ,@() }; return ,@($Lista) }

# Apoyos, diafragmas, patrones, casos, combinaciones, funciones, tablas de VISUALIZACIÓN y marcas de ejecución.
function Read-Configuracion($Sap, $Consulta, $Lec, $NombresPuntos, $NombresAreas) {
    $puntos = $Sap.PointObj; $areas = $Sap.AreaObj
    $apoyos = [ordered]@{}; $diaPuntos = [ordered]@{}
    foreach ($n in $NombresPuntos) {
        $r = Read-Api 'cPointObj.GetRestraint' $puntos $n @($n, [bool[]]@())
        if ($null -ne $r) {
            $vector = ConvertTo-Lista $r[1]
            if ($vector.Count -ne 6) { throw (New-Fallo 'api' 'GetRestraint devolvió un vector distinto de seis valores.') }
            $apoyos[$n] = @($vector | ForEach-Object { [bool]$_ })
        }
        $d = Read-Api 'cPointObj.GetDiaphragm' $puntos $n @($n, (Get-Enum 'cPointObj.GetDiaphragm' 1 1), '')
        if ($null -ne $d) { $diaPuntos[$n] = [ordered]@{ opcion = (ConvertTo-Enum $d[1]); diafragma = [string]$d[2] } }
    }
    $Lec.apoyos = $apoyos; $Lec.diafragmas_puntos = $diaPuntos
    $diaAreas = [ordered]@{}
    foreach ($n in $NombresAreas) {
        $d = Read-Api 'cAreaObj.GetDiaphragm' $areas $n @($n, '')
        if ($null -ne $d) { $diaAreas[$n] = [string]$d[1] }
    }
    $Lec.diafragmas_areas = $diaAreas

    $diaf = $Sap.Diaphragm
    $nombresDia = Read-Nombres 'cDiaphragm.GetNameList' $diaf @()
    $semi = [ordered]@{}
    foreach ($n in @($Consulta.diafragmas)) {
        $s = Read-Api 'cDiaphragm.GetDiaphragm' $diaf $n @($n, $false)
        if ($null -ne $s) { $semi[$n] = [bool]$s[1] }
    }
    $Lec.diafragmas = [ordered]@{ nombres = (ConvertTo-Nombres $nombresDia); semirrigido = $semi }

    $pat = $Sap.LoadPatterns
    $nombresPat = Read-Nombres 'cLoadPatterns.GetNameList' $pat @()
    $detPat = [ordered]@{}
    foreach ($n in @($Consulta.patrones)) {
        $t = Read-Api 'cLoadPatterns.GetLoadType' $pat $n @($n, (Get-Enum 'cLoadPatterns.GetLoadType' 1 1))
        $w = Read-Api 'cLoadPatterns.GetSelfWTMultiplier' $pat $n @($n, [double]0)
        if ($null -ne $t -and $null -ne $w) { $detPat[$n] = [ordered]@{ tipo = (ConvertTo-Enum $t[1]); multiplicador = [double]$w[1] } }
    }
    $Lec.patrones = [ordered]@{ nombres = (ConvertTo-Nombres $nombresPat); detalle = $detPat }

    $lc = $Sap.LoadCases
    $nombresCasos = ConvertTo-Nombres (Read-Nombres 'cLoadCases.GetNameList' $lc @((Get-Enum 'cLoadCases.GetNameList' 2 0)))
    $tipos = [ordered]@{}
    foreach ($n in $nombresCasos) {
        $t = Read-Api 'cLoadCases.GetTypeOAPI' $lc $n @($n, (Get-Enum 'cLoadCases.GetTypeOAPI' 1 1), [int]0)
        if ($null -ne $t) { $tipos[$n] = [ordered]@{ tipo = (ConvertTo-Enum $t[1]); subtipo = [int]$t[2] } }
    }
    $estaticos = [ordered]@{}; $sl = $lc.StaticLinear
    foreach ($n in @($Consulta.casos_estaticos)) {
        $g = Read-Api 'cCaseStaticLinear.GetLoads' $sl $n @($n, [int]0, [string[]]@(), [string[]]@(), [double[]]@())
        if ($null -ne $g) {
            $items = New-Object System.Collections.ArrayList
            for ($i = 0; $i -lt [int]$g[1]; $i++) { [void]$items.Add([ordered]@{ tipo_carga = [string]$g[2][$i]; nombre = [string]$g[3][$i]; factor = [double]$g[4][$i] }) }
            $estaticos[$n] = @($items)
        }
    }
    $modales = [ordered]@{}; $me = $lc.ModalEigen
    foreach ($n in @($Consulta.casos_modales)) {
        $a = Read-Api 'cCaseModalEigen.GetNumberModes' $me $n @($n, [int]0, [int]0)
        $b = Read-Api 'cCaseModalEigen.GetParameters' $me $n @($n, [double]0, [double]0, [double]0, [int]0)
        $c = Read-Api 'cCaseModalEigen.GetLoads' $me $n @($n, [int]0, [string[]]@(), [string[]]@(), [double[]]@(), [bool[]]@())
        if ($null -ne $a -and $null -ne $b -and $null -ne $c) {
            $modales[$n] = [ordered]@{ modos = @([int]$a[1], [int]$a[2]); desplazamiento = [double]$b[1]; corte = [double]$b[2]
                tolerancia = [double]$b[3]; automatico = [int]$b[4]; numero_cargas = [int]$c[1] }
        }
    }
    $espectrales = [ordered]@{}; $rs = $lc.ResponseSpectrum
    foreach ($n in @($Consulta.casos_espectrales)) {
        $mc = Read-Api 'cCaseResponseSpectrum.GetModalCase' $rs $n @($n, '')
        $ld = Read-Api 'cCaseResponseSpectrum.GetLoads' $rs $n @($n, [int]0, [string[]]@(), [string[]]@(), [double[]]@(), [string[]]@(), [double[]]@())
        $ec = Read-Api 'cCaseResponseSpectrum.GetEccentricity' $rs $n @($n, [double]0)
        $dc = Read-Api 'cCaseResponseSpectrum.GetDampConstant' $rs $n @($n, [double]0)
        $dt = Read-Api 'cCaseResponseSpectrum.GetDampType' $rs $n @($n, [int]0)
        $cm = Read-Api 'cCaseResponseSpectrum.GetModalComb_1' $rs $n @($n, [int]0, [double]0, [double]0, [int]0, [double]0)
        if ($null -ne $mc -and $null -ne $ld -and $null -ne $ec -and $null -ne $dc -and $null -ne $dt -and $null -ne $cm) {
            $items = New-Object System.Collections.ArrayList
            for ($i = 0; $i -lt [int]$ld[1]; $i++) {
                [void]$items.Add([ordered]@{ nombre = [string]$ld[2][$i]; funcion = [string]$ld[3][$i]; factor = [double]$ld[4][$i]
                    csys = [string]$ld[5][$i]; angulo = [double]$ld[6][$i] })
            }
            $espectrales[$n] = [ordered]@{ modal = [string]$mc[1]; cargas = @($items); excentricidad = [double]$ec[1]; amortiguamiento = [double]$dc[1]
                tipo_amortiguamiento = [int]$dt[1]
                comb_modal = [ordered]@{ tipo = [int]$cm[1]; f1 = [double]$cm[2]; f2 = [double]$cm[3]; periodica_rigida = [int]$cm[4]; td = [double]$cm[5] } }
        }
    }
    $Lec.casos = [ordered]@{ nombres = $nombresCasos; tipos = $tipos; estaticos = $estaticos; modales = $modales; espectrales = $espectrales }

    $rc = $Sap.RespCombo
    $nombresCombo = Read-Nombres 'cCombo.GetNameList' $rc @()
    $detCombo = [ordered]@{}
    foreach ($n in @($Consulta.combinaciones)) {
        $t = Read-Api 'cCombo.GetTypeOAPI' $rc $n @($n, [int]0)
        $l = Read-Api 'cCombo.GetCaseList' $rc $n @($n, [int]0, (Get-ArregloEnum 'cCombo.GetCaseList' 2), [string[]]@(), [double[]]@())
        if ($null -ne $t -and $null -ne $l) {
            $items = New-Object System.Collections.ArrayList
            for ($i = 0; $i -lt [int]$l[1]; $i++) { [void]$items.Add([ordered]@{ tipo = (ConvertTo-Enum $l[2][$i]); nombre = [string]$l[3][$i]; factor = [double]$l[4][$i] }) }
            $detCombo[$n] = [ordered]@{ tipo = [int]$t[1]; casos = @($items) }
        }
    }
    $Lec.combinaciones = [ordered]@{ nombres = (ConvertTo-Nombres $nombresCombo); detalle = $detCombo }

    $fn = $Sap.Func
    $nombresFn = Read-Nombres 'cFunction.GetNameList' $fn @([int]0)
    $valores = [ordered]@{}
    foreach ($n in @($Consulta.funciones)) {
        $v = Read-Api 'cFunction.GetValues' $fn $n @($n, [int]0, [double[]]@(), [double[]]@())
        if ($null -ne $v) {
            $tiempos = ConvertTo-Lista $v[2]; $vals = ConvertTo-Lista $v[3]
            if ($tiempos.Count -ne $vals.Count) { throw (New-Fallo 'api' 'GetValues devolvió listas de distinta longitud.') }
            $valores[$n] = [ordered]@{ numero = [int]$v[1]; tiempos = @($tiempos | ForEach-Object { [double]$_ }); valores = @($vals | ForEach-Object { [double]$_ }) }
        }
    }
    $Lec.funciones = [ordered]@{ nombres = (ConvertTo-Nombres $nombresFn); valores = $valores }

    $db = $Sap.DatabaseTables
    $tablas = [ordered]@{}
    foreach ($clave in @($Consulta.tablas)) {
        $v = Read-Api 'cDatabaseTables.GetTableForDisplayArray' $db $clave @($clave, [string[]]@(''), '', [int]0, [string[]]@(), [int]0, [string[]]@())
        if ($null -ne $v) {
            $campos = ConvertTo-Lista $v[4]; $datosTabla = ConvertTo-Lista $v[6]; $n = [int]$v[5]
            if ($campos.Count -eq 0 -or @($campos | Select-Object -Unique).Count -ne $campos.Count -or $datosTabla.Count -ne $n * $campos.Count) {
                throw (New-Fallo 'api' 'Tabla de visualización con esquema incoherente.') }
            $filas = New-Object System.Collections.ArrayList
            for ($r = 0; $r -lt $n; $r++) {
                $fila = [ordered]@{}
                for ($c = 0; $c -lt $campos.Count; $c++) { $fila[[string]$campos[$c]] = [string]$datosTabla[$r * $campos.Count + $c] }
                [void]$filas.Add($fila)
            }
            $tablas[$clave] = [ordered]@{ campos = @($campos | ForEach-Object { [string]$_ }); filas = @($filas) }
        }
    }
    $Lec.tablas = $tablas

    $f = Read-Api 'cAnalyze.GetRunCaseFlag' $Sap.Analyze '*' @([int]0, [string[]]@(), [bool[]]@())
    if ($null -eq $f) { $Lec.ejecucion = [ordered]@{ casos = @(); ejecutar = @() } }
    else {
        $casosRun = ConvertTo-Lista $f[1]; $run = ConvertTo-Lista $f[2]
        if ($casosRun.Count -ne [int]$f[0] -or $run.Count -ne $casosRun.Count) { throw (New-Fallo 'api' 'GetRunCaseFlag incoherente.') }
        $Lec.ejecucion = [ordered]@{ casos = @($casosRun | ForEach-Object { [string]$_ }); ejecutar = @($run | ForEach-Object { [bool]$_ }) }
    }
}

# -- principal ---------------------------------------------------------------------

$out = [ordered]@{ contrato = 'draft2model.etabs_respuesta'; version_contrato = '0.1.0'; operacion = 'verificar_modelo_guardado'
    modo_ejecucion = $Modo; id_solicitud = $null; estado = 'error'; datos = $null; avisos = @(); error = $null
    inicio_utc = [DateTime]::UtcNow.ToString('o'); fin_utc = $null }
$inst = [ordered]@{ instancia = $null; id_proceso = $null; inicio_proceso_utc = $null; instancia_cerrada = $false }
$app = $null; $propio = $null; $modelo = $null; $request = $null; $datos = $null; $codigo = 0
$idCorrida = Split-Path -Leaf (Split-Path -Parent $Respuesta)
if ($idCorrida -match '^[0-9a-f]{32}$') { $out.id_solicitud = $idCorrida }

try {
    if ($PSVersionTable.PSVersion.Major -ne 5) { throw (New-Fallo 'api_no_disponible' 'Se requiere Windows PowerShell 5.1.') }
    if (Test-Path -LiteralPath $Respuesta) { throw (New-Fallo 'solicitud' 'Respuesta existente; no se sobrescribe.') }
    $rutaSolicitud = Get-RutaSegura $Solicitud
    if ($Sha256Solicitud -notmatch '^[0-9a-f]{64}$' -or (Get-Sha256 $rutaSolicitud) -ne $Sha256Solicitud) { throw (New-Fallo 'evidencia' 'Solicitud alterada.') }
    try { $request = [IO.File]::ReadAllText($rutaSolicitud, $Utf8) | ConvertFrom-Json } catch { throw (New-Fallo 'solicitud' 'Solicitud no es JSON.') }
    $campos = @('contrato', 'version_contrato', 'id', 'operacion', 'modo_configurado', 'modelo_lectura', 'sha256_edb', 'unidades_esperadas',
        'version_etabs_esperada', 'dll', 'consulta', 'sha256_expectativa', 'huella_plan', 'version_lector')
    if ($request -isnot [Management.Automation.PSCustomObject] -or @($request.PSObject.Properties.Name).Count -ne $campos.Count -or
        @($request.PSObject.Properties.Name | Where-Object { $campos -notcontains $_ }).Count) { throw (New-Fallo 'solicitud' 'Campos de solicitud no permitidos.') }
    if ($request.contrato -ne 'draft2model.etabs_solicitud' -or $request.version_contrato -ne '0.1.0' -or $request.operacion -ne 'verificar_modelo_guardado' -or
        $request.id -notmatch '^[0-9a-f]{32}$' -or $request.id -ne $idCorrida -or $request.modo_configurado -ne $Modo) { throw (New-Fallo 'solicitud' 'Contrato o identidad de solicitud inválidos.') }
    if ($request.unidades_esperadas -ne $UnidadesPlan -or $request.sha256_edb -notmatch '^[0-9a-f]{64}$') { throw (New-Fallo 'solicitud' 'Unidades o huella esperadas inválidas.') }
    if ($request.version_lector -ne $VersionLector) { throw (New-Fallo 'solicitud' 'Versión de lector distinta; no se mezclan lectores.') }
    if ($null -ne $request.version_etabs_esperada -and ($request.version_etabs_esperada -isnot [string] -or [string]::IsNullOrWhiteSpace($request.version_etabs_esperada))) {
        throw (New-Fallo 'solicitud' 'Versión de ETABS esperada inválida.') }
    Test-Consulta $request.consulta
    $modelo = Get-RutaSegura ([string]$request.modelo_lectura)
    if ((Split-Path -Leaf $modelo) -ne 'modelo_lectura.edb' -or (Split-Path -Parent $modelo) -ne (Split-Path -Parent ([IO.Path]::GetFullPath($Respuesta)))) {
        throw (New-Fallo 'solicitud' 'La copia de lectura debe estar en la carpeta de la corrida.') }
    if ((Get-Sha256 $modelo) -ne $request.sha256_edb) { throw (New-Fallo 'evidencia' 'La copia de lectura no coincide con el SHA256 del EDB.') }
    $dll = Get-RutaSegura ([string]$request.dll)
    try { $asm = [Reflection.Assembly]::LoadFrom($dll) } catch { throw (New-Fallo 'api_no_disponible' 'No se pudo cargar la DLL.') }
    $token = (@($asm.GetName().GetPublicKeyToken() | ForEach-Object { $_.ToString('x2') }) -join '')
    if ($Modo -eq 'real' -and $token -ne $TokenCsi) { throw (New-Fallo 'precondicion' 'Modo real exige la DLL firmada por CSI.') }
    if ($Modo -eq 'doble' -and $token -eq $TokenCsi) { throw (New-Fallo 'precondicion' 'Modo doble no puede cargar la DLL real de CSI.') }
    $versionDll = (Get-Item -LiteralPath $dll).VersionInfo.FileVersion
    Resolve-Firmas $asm $request.consulta  # todas las firmas antes de crear la instancia

    $helper = $asm.CreateInstance('ETABSv1.Helper')
    if ($null -eq $helper) { throw (New-Fallo 'api_no_disponible' 'La DLL no define ETABSv1.Helper.') }
    $antes = @()
    if ($Modo -eq 'real') { $antes = @(Get-Process ETABS -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Id) }
    $app = Invoke-Api 'cHelper.CreateObjectProgID' $helper @($ProgId)
    if ($null -eq $app) { throw (New-Fallo 'api_no_disponible' 'CreateObjectProgID no devolvió instancia.') }
    Assert-Cero 'cOAPI.ApplicationStart' $app @() 'api'
    if ($Modo -eq 'real') {
        $nuevos = @(Get-Process ETABS -ErrorAction SilentlyContinue | Where-Object { $antes -notcontains $_.Id })
        if ($nuevos.Count -ne 1) { throw (New-Fallo 'precondicion' 'No se identificó una sola instancia propia nueva.') }
        $propio = $nuevos[0]; $null = $propio.Handle
        $inst.instancia = 'nueva'; $inst.id_proceso = $propio.Id; $inst.inicio_proceso_utc = $propio.StartTime.ToUniversalTime().ToString('o')
    } else { $inst.instancia = 'doble' }
    Add-Traza 'instancia_creada' $inst
    Assert-Cero 'cOAPI.Hide' $app @() 'api'
    $sap = (Get-Base $app).SapModel
    if ((Get-Sha256 $modelo) -ne $request.sha256_edb) { throw (New-Fallo 'evidencia' 'La copia cambió antes de abrir.') }
    Assert-Cero 'cFile.OpenFile' $sap.File @($modelo) 'api'
    $abierto = Invoke-Api 'cSapModel.GetModelFilename' $sap @($true)
    if (-not [string]::Equals([IO.Path]::GetFullPath([string]$abierto), $modelo, [StringComparison]::OrdinalIgnoreCase)) {
        throw (New-Fallo 'precondicion' 'El modelo abierto no es la copia de lectura.') }
    $unidades = (Invoke-Api 'cSapModel.GetPresentUnits' $sap @()).ToString()
    $ver = Read-Api 'cSapModel.GetVersion' $sap '*' @('', [double]0)
    if ($null -eq $ver) { throw (New-Fallo 'api' 'Versión de ETABS no legible.') }
    if ($null -ne $request.version_etabs_esperada -and [string]$ver[0] -ne $request.version_etabs_esperada) {
        throw (New-Fallo 'precondicion' 'Versión de ETABS distinta de la esperada.') }
    $lecturas = Read-Modelo $sap $request.consulta
    $lecturas.unidades = $unidades
    $lecturas.version_etabs = [string]$ver[0]
    $lecturas.retornos_no_cero = @($Retornos)
    $abierto = Invoke-Api 'cSapModel.GetModelFilename' $sap @($true)
    if (-not [string]::Equals([IO.Path]::GetFullPath([string]$abierto), $modelo, [StringComparison]::OrdinalIgnoreCase)) {
        throw (New-Fallo 'precondicion' 'El modelo abierto cambió durante la lectura.') }
    if ((Get-Sha256 $modelo) -ne $request.sha256_edb) { throw (New-Fallo 'evidencia' 'La copia cambió durante la lectura.') }
    $datos = [ordered]@{ sha256_antes = $request.sha256_edb; sha256_despues = $null; instancia = $inst.instancia; id_proceso = $inst.id_proceso
        inicio_proceso_utc = $inst.inicio_proceso_utc; instancia_cerrada = $false; firmas_verificadas = $Metodos.Count; version_dll = $versionDll
        consulta = $request.consulta; lecturas = $lecturas; guardado = $false; modificaciones = @(); version_lector = $VersionLector }
} catch {
    $excepcion = $_.Exception
    $tipo = 'inesperado'
    if ($excepcion.Data.Contains('draft2model_tipo')) { $tipo = $excepcion.Data['draft2model_tipo'] }
    if (-not $Codigos.ContainsKey($tipo)) { $tipo = 'inesperado' }
    $out.error = [ordered]@{ tipo = $tipo; mensaje = (Get-MensajePublico $excepcion.Message) }
    try { Add-Traza 'error' $out.error } catch { }
    $codigo = $Codigos[$tipo]
} finally {
    if ($null -ne $app) {
        try {
            if ($Modo -eq 'real' -and ($null -eq $propio -or $propio.HasExited -or $propio.StartTime.ToUniversalTime().ToString('o') -ne $inst.inicio_proceso_utc)) {
                throw (New-Fallo 'cierre_propio' 'Instancia propia no identificada o perdida antes del cierre.') }
            Assert-Cero 'cOAPI.ApplicationExit' $app @($false) 'cierre_propio'
            if ($Modo -eq 'real' -and -not $propio.WaitForExit(15000)) { throw (New-Fallo 'cierre_propio' 'Cierre propio no confirmado.') }
            $inst.instancia_cerrada = $true
            Add-Traza 'instancia_cerrada' $inst
        } catch {
            $out.error = [ordered]@{ tipo = 'cierre_propio'; mensaje = (Get-MensajePublico $_.Exception.Message); error_previo = $out.error }
            $codigo = $Codigos['cierre_propio']
        }
    }
}

if ($codigo -eq 0) {
    try {
        if ($null -eq $datos -or -not $inst.instancia_cerrada) { throw (New-Fallo 'evidencia' 'Lectura o cierre no confirmados.') }
        $final = Get-Sha256 $modelo
        if ($final -ne $request.sha256_edb) { throw (New-Fallo 'evidencia' 'La copia cambió tras cerrar.') }
        $datos.sha256_despues = $final; $datos.instancia_cerrada = $true
        $out.datos = $datos; $out.estado = 'ok'
        $out.avisos = @('Lectura en instancia propia nueva cerrada sin guardar; no se analizó ni se aprobó el modelo.')
    } catch {
        $out.error = [ordered]@{ tipo = 'evidencia'; mensaje = (Get-MensajePublico $_.Exception.Message) }; $codigo = $Codigos['evidencia']
    }
} else {
    $out.datos = [ordered]@{ instancia = $inst.instancia; id_proceso = $inst.id_proceso; instancia_cerrada = $inst.instancia_cerrada
        retornos_no_cero = @($Retornos) }
}
$out.fin_utc = [DateTime]::UtcNow.ToString('o')
$temporal = $Respuesta + '.tmp-' + [guid]::NewGuid().ToString('N')
try {
    [IO.File]::WriteAllText($temporal, (ConvertTo-Json -InputObject $out -Depth 32 -Compress), $Utf8)
    [IO.File]::Move($temporal, $Respuesta)
} catch {
    if (Test-Path -LiteralPath $temporal) { Remove-Item -LiteralPath $temporal -Force }
    [Console]::Error.WriteLine('Respuesta de verificación no publicada.'); exit 50
}
exit $codigo
