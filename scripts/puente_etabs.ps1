<#
.SYNOPSIS
Puente local Draft2Model -> API CSI de ETABS (ETABSv1.dll). Requiere Windows PowerShell 5.1.

.DESCRIPTION
Lee una solicitud JSON (draft2model.etabs_solicitud), ejecuta UNA operación con la API
instalada y escribe una respuesta JSON nueva (draft2model.etabs_respuesta). La respuesta
se publica con un único Move y nunca sobrescribe un archivo existente.

Operaciones: diagnosticar, abrir_copia_plantilla, leer_tablas, guardar_como.
Cada operación valida primero sus parámetros y el sistema de archivos; solo después
carga la DLL y se conecta a ETABS.

Este puente NUNCA ejecuta análisis, NUNCA cierra ETABS, NUNCA cambia unidades y
NUNCA guarda sobre un archivo existente. No construye ni modifica elementos estructurales.

PowerShell 7 no sirve: la API usa Marshal.GetActiveObject, ausente en .NET Core.

Códigos de salida: 0 correcto; 10 solicitud inválida; 20 API o instancia no disponible;
30 una llamada de la API devolvió un código distinto de 0; 40 precondición no cumplida;
41 evidencia rechazada (huella de la copia); 50 error inesperado o respuesta no publicable.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Solicitud,
    [Parameter(Mandatory = $true)][string]$Respuesta
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$VersionPuente = '0.1.0'
$ContratoSolicitud = 'draft2model.etabs_solicitud'
$ContratoRespuesta = 'draft2model.etabs_respuesta'
$VersionContrato = '0.1.0'
$ProgId = 'CSI.ETABS.API.ETABSObject'
$DllPredeterminada = 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
$EstadoCasoTerminado = 4  # Analyze.GetCaseStatus: 1 sin ejecutar, 2 no pudo iniciar, 3 sin terminar, 4 terminado
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$CodigosSalida = @{ solicitud = 10; api_no_disponible = 20; api = 30; precondicion = 40; evidencia = 41; inesperado = 50 }

# -- errores y utilidades ------------------------------------------------------

function New-Fallo([string]$Tipo, [string]$Mensaje, $CodigoApi = $null) {
    $excepcion = New-Object System.InvalidOperationException($Mensaje)
    $excepcion.Data['draft2model_tipo'] = $Tipo
    $excepcion.Data['codigo_api'] = $CodigoApi
    return $excepcion
}

function Assert-Api([int]$Codigo, [string]$Llamada) {
    if ($Codigo -ne 0) { throw (New-Fallo 'api' "$Llamada devolvió $Codigo." $Codigo) }
}

function Get-Campo($Objeto, [string]$Nombre, [switch]$Opcional) {
    if ($null -ne $Objeto -and $null -ne $Objeto.PSObject.Properties[$Nombre]) { return $Objeto.$Nombre }
    if ($Opcional) { return $null }
    throw (New-Fallo 'solicitud' "Falta el campo '$Nombre'.")
}

function Get-Texto($Objeto, [string]$Nombre) {
    $valor = Get-Campo $Objeto $Nombre
    if ($valor -isnot [string] -or [string]::IsNullOrWhiteSpace($valor)) {
        throw (New-Fallo 'solicitud' "'$Nombre' debe ser texto no vacío.")
    }
    return $valor
}

function Get-ListaTexto($Objeto, [string]$Nombre) {
    $valor = Get-Campo $Objeto $Nombre -Opcional
    if ($null -eq $valor) { return ,([string[]]@()) }
    $lista = @($valor)
    foreach ($elemento in $lista) {
        if ($elemento -isnot [string] -or [string]::IsNullOrWhiteSpace($elemento)) {
            throw (New-Fallo 'solicitud' "'$Nombre' debe ser una lista de textos no vacíos.")
        }
    }
    if (@($lista | Select-Object -Unique).Count -ne $lista.Count) {
        throw (New-Fallo 'solicitud' "'$Nombre' contiene nombres repetidos.")
    }
    return ,([string[]]$lista)
}

function Get-IdProceso($Parametros) {
    $valor = Get-Campo $Parametros 'id_proceso' -Opcional
    if ($null -eq $valor) { return $null }
    if (($valor -isnot [int] -and $valor -isnot [long]) -or $valor -le 0) {
        throw (New-Fallo 'solicitud' "'id_proceso' debe ser un entero positivo.")
    }
    return [int]$valor
}

function Get-RutaEdb($Parametros, [string]$Nombre) {
    $ruta = Get-Texto $Parametros $Nombre
    if (-not [System.IO.Path]::IsPathRooted($ruta)) { throw (New-Fallo 'solicitud' "'$Nombre' debe ser una ruta absoluta.") }
    if ([System.IO.Path]::GetExtension($ruta) -ine '.edb') { throw (New-Fallo 'solicitud' "'$Nombre' debe ser un archivo .edb.") }
    return [System.IO.Path]::GetFullPath($ruta)
}

function Test-MismaRuta([string]$A, [string]$B) {
    if ([string]::IsNullOrEmpty($A) -or [string]::IsNullOrEmpty($B)) { return $false }
    return ([System.IO.Path]::GetFullPath($A).TrimEnd('\') -ieq [System.IO.Path]::GetFullPath($B).TrimEnd('\'))
}

function Get-Sha256([string]$Ruta) {
    # .NET evita depender de módulos PowerShell opcionales en el entorno ejecutor.
    $stream = [System.IO.File]::OpenRead($Ruta)
    $algorithm = [System.Security.Cryptography.SHA256]::Create()
    try { return ([System.BitConverter]::ToString($algorithm.ComputeHash($stream))).Replace('-', '').ToLowerInvariant() }
    finally { $algorithm.Dispose(); $stream.Dispose() }
}

# Emite un elemento por proceso; llamar siempre como @(Get-ProcesosEtabs): PowerShell 5.1
# desenrolla una lista de un solo elemento y Count de un diccionario cuenta sus claves.
function Get-ProcesosEtabs {
    Get-Process -Name 'ETABS' -ErrorAction SilentlyContinue | ForEach-Object {
        [ordered]@{ id = $_.Id; titulo_ventana = $_.MainWindowTitle.Trim() }
    }
}

# -- API ---------------------------------------------------------------------

function Import-Api([string]$Dll) {
    if (-not (Test-Path -LiteralPath $Dll -PathType Leaf)) {
        throw (New-Fallo 'api_no_disponible' "No existe la DLL de la API: $Dll")
    }
    try { Add-Type -LiteralPath $Dll } catch {
        throw (New-Fallo 'api_no_disponible' "No se pudo cargar la DLL de la API: $($_.Exception.Message)")
    }
    return (New-Object ETABSv1.Helper)
}

function Connect-Etabs($Contexto, $IdProceso) {
    $procesos = @(Get-ProcesosEtabs)
    try {
        if ($null -ne $IdProceso) {
            if (-not (@($procesos | Where-Object { $_.id -eq $IdProceso }).Count)) {
                throw (New-Fallo 'precondicion' "No hay un proceso ETABS con id $IdProceso.")
            }
            $instancia = $Contexto.helper.GetObjectProcess($ProgId, $IdProceso)
        } else {
            if ($procesos.Count -eq 0) { throw (New-Fallo 'api_no_disponible' 'No hay ninguna instancia de ETABS en ejecución.') }
            if ($procesos.Count -gt 1) {
                throw (New-Fallo 'precondicion' "Hay $($procesos.Count) instancias de ETABS; indique 'id_proceso'.")
            }
            $instancia = $Contexto.helper.GetObject($ProgId)
        }
    } catch {
        if ($_.Exception.Data.Contains('draft2model_tipo')) { throw }
        # Los errores COM llegan envueltos en MethodInvocationException.
        throw (New-Fallo 'api_no_disponible' "No se pudo conectar con ETABS: $($_.Exception.Message)")
    }
    if ($null -eq $instancia) { throw (New-Fallo 'api_no_disponible' 'La API no devolvió una instancia de ETABS.') }
    return $instancia
}

function Assert-ModeloEsperado($SapModel, [string]$Esperado) {
    $abierto = $SapModel.GetModelFilename($true)
    if (-not (Test-MismaRuta $abierto $Esperado)) {
        throw (New-Fallo 'precondicion' "El modelo abierto ('$abierto') no es el esperado ('$Esperado'); no se lee ni se guarda.")
    }
    return $abierto
}

function Get-Unidades($SapModel) { return $SapModel.GetPresentUnits().ToString() }

# -- operaciones ---------------------------------------------------------------
# Cada operación tiene 'validar' (sin DLL ni ETABS) y 'ejecutar' (con la API).

function Test-Diagnosticar($Parametros) {
    return [ordered]@{ id_proceso = (Get-IdProceso $Parametros) }
}

function Invoke-Diagnosticar($P, $Contexto) {
    $datos = [ordered]@{
        powershell = $PSVersionTable.PSVersion.ToString()
        proceso_64_bits = [Environment]::Is64BitProcess
        dll = $Contexto.dll
        dll_version_archivo = (Get-Item -LiteralPath $Contexto.dll).VersionInfo.FileVersion
        version_oapi_helper = $Contexto.helper.GetOAPIVersionNumber()
        procesos_etabs = @(Get-ProcesosEtabs)
    }
    $etabs = Connect-Etabs $Contexto $P.id_proceso
    $sap = $etabs.SapModel
    $version = ''; $numero = 0.0
    Assert-Api ($sap.GetVersion([ref]$version, [ref]$numero)) 'SapModel.GetVersion'
    $programa = ''; $versionPrograma = ''; $nivel = ''
    Assert-Api ($sap.GetProgramInfo([ref]$programa, [ref]$versionPrograma, [ref]$nivel)) 'SapModel.GetProgramInfo'
    $datos.version = $version
    $datos.numero_version = $numero
    $datos.programa = [ordered]@{ nombre = $programa; version = $versionPrograma; nivel = $nivel }
    $datos.unidades = Get-Unidades $sap
    $datos.modelo = $sap.GetModelFilename($true)
    $datos.modelo_bloqueado = $sap.GetModelIsLocked()
    $Contexto.avisos.Add('Diagnóstico de solo lectura: no se modificó la instancia.') | Out-Null
    return $datos
}

function Test-AbrirCopia($Parametros) {
    $copia = Get-RutaEdb $Parametros 'copia'
    $sha = Get-Texto $Parametros 'sha256_copia'
    if ($sha -notmatch '^[0-9a-f]{64}$') { throw (New-Fallo 'solicitud' "'sha256_copia' debe ser SHA256 hexadecimal en minúsculas.") }
    $instancia = Get-Texto $Parametros 'instancia'
    if ($instancia -notin @('activa', 'nueva')) { throw (New-Fallo 'solicitud' "'instancia' debe ser 'activa' o 'nueva'.") }
    $reemplazar = Get-Campo $Parametros 'reemplazar_modelo_activo' -Opcional
    if ($instancia -eq 'activa' -and $reemplazar -ne $true) {
        throw (New-Fallo 'solicitud' "Abrir en la instancia activa descarta su modelo actual sin guardarlo; exige 'reemplazar_modelo_activo': true.")
    }
    $idProceso = Get-IdProceso $Parametros
    if ($instancia -eq 'nueva' -and $null -ne $idProceso) { throw (New-Fallo 'solicitud' "'id_proceso' no se admite con instancia 'nueva'.") }
    if (-not (Test-Path -LiteralPath $copia -PathType Leaf)) { throw (New-Fallo 'precondicion' "No existe la copia: $copia") }
    $real = Get-Sha256 $copia
    if ($real -ne $sha) { throw (New-Fallo 'evidencia' 'La copia no coincide con la huella declarada; no se abre.') }
    return [ordered]@{ copia = $copia; sha256_copia = $sha; instancia = $instancia; id_proceso = $idProceso }
}

function Invoke-AbrirCopia($P, $Contexto) {
    if ($P.instancia -eq 'nueva') {
        $antes = @(Get-ProcesosEtabs | ForEach-Object { $_.id })
        try { $etabs = $Contexto.helper.CreateObjectProgID($ProgId) } catch {
            throw (New-Fallo 'api_no_disponible' "No se pudo crear la instancia de ETABS: $($_.Exception.Message)")
        }
        if ($null -eq $etabs) { throw (New-Fallo 'api_no_disponible' 'CreateObjectProgID no devolvió instancia.') }
        Assert-Api ($etabs.ApplicationStart()) 'ApplicationStart'
        $nuevos = @(Get-ProcesosEtabs | Where-Object { $antes -notcontains $_.id } | ForEach-Object { $_.id })
        $idProceso = $null
        if ($nuevos.Count -eq 1) { $idProceso = $nuevos[0] } else {
            $Contexto.avisos.Add("No se identificó un único proceso ETABS nuevo ($($nuevos.Count)); indique 'id_proceso' en las siguientes operaciones.") | Out-Null
        }
        $Contexto.avisos.Add('La instancia nueva queda abierta; el puente nunca cierra ETABS.') | Out-Null
    } else {
        $etabs = Connect-Etabs $Contexto $P.id_proceso
        $idProceso = $P.id_proceso
    }
    $sap = $etabs.SapModel
    # Segunda comprobación inmediatamente antes de abrir.
    if ((Get-Sha256 $P.copia) -ne $P.sha256_copia) { throw (New-Fallo 'evidencia' 'La copia cambió antes de abrirla; no se abre.') }
    Assert-Api ($sap.File.OpenFile($P.copia)) 'File.OpenFile'
    $abierto = Assert-ModeloEsperado $sap $P.copia
    $Contexto.avisos.Add('Se abrió una copia de la plantilla; no se construyó ni modificó ningún elemento estructural.') | Out-Null
    return [ordered]@{
        copia = $P.copia; sha256_copia_verificado = $P.sha256_copia; instancia = $P.instancia
        id_proceso = $idProceso; modelo_abierto = $abierto; unidades = Get-Unidades $sap
    }
}

function Test-LeerTablas($Parametros) {
    $tablas = Get-ListaTexto $Parametros 'tablas'
    $casos = Get-ListaTexto $Parametros 'casos'
    $combinaciones = Get-ListaTexto $Parametros 'combinaciones'
    if ($tablas.Count -eq 0) { throw (New-Fallo 'solicitud' "'tablas' no puede estar vacía.") }
    if ($casos.Count + $combinaciones.Count -eq 0) { throw (New-Fallo 'solicitud' 'Indique casos o combinaciones explícitos.') }
    return [ordered]@{
        modelo_esperado = (Get-RutaEdb $Parametros 'modelo_esperado'); tablas = $tablas; casos = $casos
        combinaciones = $combinaciones; id_proceso = (Get-IdProceso $Parametros)
    }
}

function ConvertTo-Filas([string[]]$Campos, [int]$Registros, [string[]]$Datos) {
    $filas = New-Object System.Collections.ArrayList
    $n = $Campos.Count
    if ($n -eq 0) { return ,$filas }
    if ($Datos.Count -ne $n * $Registros) { throw (New-Fallo 'api' "TableData tiene $($Datos.Count) valores; se esperaban $($n * $Registros).") }
    for ($r = 0; $r -lt $Registros; $r++) {
        $fila = [ordered]@{}
        for ($i = 0; $i -lt $n; $i++) { $fila[$Campos[$i]] = $Datos[$r * $n + $i] }
        [void]$filas.Add($fila)
    }
    return ,$filas
}

function Invoke-LeerTablas($P, $Contexto) {
    $etabs = Connect-Etabs $Contexto $P.id_proceso
    $sap = $etabs.SapModel
    $modelo = Assert-ModeloEsperado $sap $P.modelo_esperado
    $versionEtabs = ''; $numeroVersionEtabs = 0.0
    Assert-Api ($sap.GetVersion([ref]$versionEtabs, [ref]$numeroVersionEtabs)) 'SapModel.GetVersion'

    # Casos: deben existir y tener análisis terminado. El puente no ejecuta análisis.
    $numero = 0; [string[]]$nombres = @(); [int[]]$estados = @()
    Assert-Api ($sap.Analyze.GetCaseStatus([ref]$numero, [ref]$nombres, [ref]$estados)) 'Analyze.GetCaseStatus'
    $estadoCasos = [ordered]@{}
    foreach ($caso in $P.casos) {
        $indice = [Array]::IndexOf($nombres, $caso)
        if ($indice -lt 0) { throw (New-Fallo 'precondicion' "El caso '$caso' no existe en el modelo.") }
        if ($estados[$indice] -ne $EstadoCasoTerminado) {
            throw (New-Fallo 'precondicion' "El caso '$caso' no tiene análisis terminado (estado $($estados[$indice])); el puente no ejecuta análisis.")
        }
        $estadoCasos[$caso] = $estados[$indice]
    }
    if ($P.combinaciones.Count) {
        $numeroCombos = 0; [string[]]$combos = @()
        Assert-Api ($sap.RespCombo.GetNameList([ref]$numeroCombos, [ref]$combos)) 'RespCombo.GetNameList'
        foreach ($combo in $P.combinaciones) {
            if ($combos -notcontains $combo) { throw (New-Fallo 'precondicion' "La combinación '$combo' no existe en el modelo.") }
        }
        $Contexto.avisos.Add('El estado de análisis de los casos que componen cada combinación no se comprueba.') | Out-Null
    }

    $db = $sap.DatabaseTables
    $numeroTablas = 0; [string[]]$claves = @(); [string[]]$nombresTablas = @(); [int[]]$importacion = @()
    Assert-Api ($db.GetAvailableTables([ref]$numeroTablas, [ref]$claves, [ref]$nombresTablas, [ref]$importacion)) 'DatabaseTables.GetAvailableTables'
    foreach ($tabla in $P.tablas) {
        if ($claves -notcontains $tabla) { throw (New-Fallo 'precondicion' "La tabla '$tabla' no está disponible en el modelo.") }
    }

    # Selección de casos para visualización; se restaura la selección de casos previa al terminar.
    $previos = 0; [string[]]$casosPrevios = @()
    $hayPrevios = ($db.GetLoadCasesSelectedForDisplay([ref]$previos, [ref]$casosPrevios) -eq 0)
    $tablasLeidas = New-Object System.Collections.ArrayList
    try {
        [string[]]$seleccion = $P.casos
        Assert-Api ($db.SetLoadCasesSelectedForDisplay([ref]$seleccion)) 'DatabaseTables.SetLoadCasesSelectedForDisplay'
        [string[]]$seleccionCombos = $P.combinaciones
        if ($db.SetLoadCombinationsSelectedForDisplay([ref]$seleccionCombos) -ne 0) {
            $Contexto.avisos.Add('SetLoadCombinationsSelectedForDisplay devolvió un código distinto de 0; las filas se filtran por OutputCase.') | Out-Null
        }
        $permitidos = @($P.casos) + @($P.combinaciones)
        foreach ($tabla in $P.tablas) {
            [string[]]$camposPedidos = @('')
            $versionTabla = 0; [string[]]$campos = @(); $registros = 0; [string[]]$valores = @()
            Assert-Api ($db.GetTableForDisplayArray($tabla, [ref]$camposPedidos, '', [ref]$versionTabla, [ref]$campos, [ref]$registros, [ref]$valores)) "DatabaseTables.GetTableForDisplayArray($tabla)"
            $filas = ConvertTo-Filas $campos $registros $valores
            $filtradas = 0
            if ($campos -contains 'OutputCase') {
                $conservadas = New-Object System.Collections.ArrayList
                foreach ($fila in $filas) { if ($permitidos -contains $fila['OutputCase']) { [void]$conservadas.Add($fila) } else { $filtradas++ } }
                $filas = $conservadas
            } else {
                $Contexto.avisos.Add("La tabla '$tabla' no tiene campo OutputCase; no se filtró por caso.") | Out-Null
            }
            [void]$tablasLeidas.Add([ordered]@{
                clave = $tabla; version_tabla = $versionTabla; campos = @($campos); numero_registros_api = $registros
                registros_descartados_por_caso = $filtradas; filas = @($filas)
            })
        }
    } finally {
        if ($hayPrevios) {
            [string[]]$restaurar = $casosPrevios
            if ($db.SetLoadCasesSelectedForDisplay([ref]$restaurar) -ne 0) {
                $Contexto.avisos.Add('No se pudo restaurar la selección previa de casos para visualización.') | Out-Null
            }
        }
    }
    $Contexto.avisos.Add('Los valores se devuelven como texto, en las unidades presentes del modelo; no se cambiaron unidades.') | Out-Null
    return [ordered]@{
        modelo = $modelo; version_etabs = $versionEtabs; unidades = Get-Unidades $sap; casos = @($P.casos); combinaciones = @($P.combinaciones)
        estado_casos = $estadoCasos; tablas = @($tablasLeidas)
    }
}

function Test-GuardarComo($Parametros) {
    $modelo = Get-RutaEdb $Parametros 'modelo_esperado'
    $destino = Get-RutaEdb $Parametros 'destino'
    if (Test-MismaRuta $modelo $destino) { throw (New-Fallo 'solicitud' 'El destino debe ser distinto del modelo abierto.') }
    if (Test-Path -LiteralPath $destino) { throw (New-Fallo 'precondicion' "El destino ya existe; no se sobrescribe: $destino") }
    $carpeta = [System.IO.Path]::GetDirectoryName($destino)
    if (-not (Test-Path -LiteralPath $carpeta -PathType Container)) { throw (New-Fallo 'precondicion' "No existe la carpeta de destino: $carpeta") }
    return [ordered]@{ modelo_esperado = $modelo; destino = $destino; id_proceso = (Get-IdProceso $Parametros) }
}

function Invoke-GuardarComo($P, $Contexto) {
    $etabs = Connect-Etabs $Contexto $P.id_proceso
    $sap = $etabs.SapModel
    Assert-ModeloEsperado $sap $P.modelo_esperado | Out-Null
    if (Test-Path -LiteralPath $P.destino) { throw (New-Fallo 'precondicion' "El destino apareció antes de guardar; no se sobrescribe: $($P.destino)") }
    Assert-Api ($sap.File.Save($P.destino)) 'File.Save'
    if (-not (Test-Path -LiteralPath $P.destino -PathType Leaf)) { throw (New-Fallo 'api' 'File.Save devolvió 0 pero el destino no existe.') }
    $abierto = $sap.GetModelFilename($true)
    if (-not (Test-MismaRuta $abierto $P.destino)) {
        $Contexto.avisos.Add("Tras guardar, ETABS informa como modelo abierto '$abierto'.") | Out-Null
    }
    $Contexto.avisos.Add('Se guardó el modelo tal como estaba abierto; no se ejecutó análisis.') | Out-Null
    return [ordered]@{ destino = $P.destino; sha256 = (Get-Sha256 $P.destino); modelo_abierto = $abierto }
}

# Registro extensible: añadir aquí nuevas operaciones con su validación y ejecución.
$Operaciones = [ordered]@{
    diagnosticar          = @{ validar = ${function:Test-Diagnosticar}; ejecutar = ${function:Invoke-Diagnosticar} }
    abrir_copia_plantilla = @{ validar = ${function:Test-AbrirCopia};    ejecutar = ${function:Invoke-AbrirCopia} }
    leer_tablas           = @{ validar = ${function:Test-LeerTablas};    ejecutar = ${function:Invoke-LeerTablas} }
    guardar_como          = @{ validar = ${function:Test-GuardarComo};   ejecutar = ${function:Invoke-GuardarComo} }
}

# -- principal ---------------------------------------------------------------

$respuestaObj = [ordered]@{
    contrato = $ContratoRespuesta; version_contrato = $VersionContrato; version_puente = $VersionPuente
    modo_ejecucion = 'real'; id_solicitud = $null; operacion = $null; estado = 'error'
    error = $null; datos = $null; avisos = @(); inicio_utc = [DateTime]::UtcNow.ToString('o'); fin_utc = $null
    entorno = [ordered]@{ powershell = $PSVersionTable.PSVersion.ToString(); edicion = $PSVersionTable.PSEdition; proceso_64_bits = [Environment]::Is64BitProcess }
}
$contexto = @{ helper = $null; dll = $null; avisos = (New-Object System.Collections.ArrayList) }
$codigoSalida = 0

try {
    if ($PSVersionTable.PSVersion.Major -ne 5) {
        throw (New-Fallo 'api_no_disponible' "Se requiere Windows PowerShell 5.1; se ejecuta $($PSVersionTable.PSVersion).")
    }
    try { $sol = [System.IO.File]::ReadAllText($Solicitud, $Utf8) | ConvertFrom-Json } catch {
        throw (New-Fallo 'solicitud' "Solicitud ilegible: $($_.Exception.Message)")
    }
    $id = Get-Texto $sol 'id'
    if ($id -notmatch '^[0-9a-f]{32}$') { throw (New-Fallo 'solicitud' "'id' debe tener 32 hexadecimales.") }
    $respuestaObj.id_solicitud = $id
    if ((Get-Campo $sol 'contrato') -ne $ContratoSolicitud -or (Get-Campo $sol 'version_contrato') -ne $VersionContrato) {
        throw (New-Fallo 'solicitud' "Contrato de solicitud no admitido; se espera $ContratoSolicitud $VersionContrato.")
    }
    $operacion = Get-Texto $sol 'operacion'
    if (-not $Operaciones.Contains($operacion)) { throw (New-Fallo 'solicitud' "Operación no admitida: '$operacion'.") }
    $respuestaObj.operacion = $operacion
    $parametros = Get-Campo $sol 'parametros'
    if ($parametros -isnot [System.Management.Automation.PSCustomObject]) { throw (New-Fallo 'solicitud' "'parametros' debe ser un objeto.") }

    $validados = & $Operaciones[$operacion].validar $parametros

    $dll = Get-Campo $sol 'dll' -Opcional
    if ($null -eq $dll) { $dll = $DllPredeterminada }
    $contexto.dll = $dll
    $contexto.helper = Import-Api $dll
    $respuestaObj.datos = & $Operaciones[$operacion].ejecutar $validados $contexto
    $respuestaObj.estado = 'ok'
} catch {
    $excepcion = $_.Exception
    $tipo = 'inesperado'
    if ($excepcion.Data.Contains('draft2model_tipo')) { $tipo = $excepcion.Data['draft2model_tipo'] }
    $codigoApi = $null
    if ($excepcion.Data.Contains('codigo_api')) { $codigoApi = $excepcion.Data['codigo_api'] }
    $respuestaObj.error = [ordered]@{ tipo = $tipo; mensaje = $excepcion.Message; codigo_api = $codigoApi }
    if (-not $CodigosSalida.ContainsKey($tipo)) { $tipo = 'inesperado'; $respuestaObj.error.tipo = $tipo }
    $codigoSalida = $CodigosSalida[$tipo]
}

$respuestaObj.avisos = @($contexto.avisos)
$respuestaObj.fin_utc = [DateTime]::UtcNow.ToString('o')
$temporal = "$Respuesta.tmp-" + [guid]::NewGuid().ToString('N')
try {
    $json = ConvertTo-Json -InputObject $respuestaObj -Depth 32 -Compress
    [System.IO.File]::WriteAllText($temporal, $json, $Utf8)
    [System.IO.File]::Move($temporal, $Respuesta)  # falla si la respuesta ya existe: no se sobrescribe
} catch {
    if (Test-Path -LiteralPath $temporal) { Remove-Item -LiteralPath $temporal -Force }
    [Console]::Error.WriteLine("Respuesta no publicada: $($_.Exception.Message)")
    exit $CodigosSalida['inesperado']
}
exit $codigoSalida
