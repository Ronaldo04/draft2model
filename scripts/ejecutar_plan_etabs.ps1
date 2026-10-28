<#
.SYNOPSIS
Ejecuta un plan declarativo draft2model.plan_operaciones_etabs sobre la copia abierta en ETABS.
Requiere Windows PowerShell 5.1.

.DESCRIPTION
Despacho tipado por reflexión: cada operación se resuelve como MethodInfo de la interfaz
ETABSv1 declarada, se exige que la firma reflejada coincida exactamente con la del plan
(tipos, nombres y retorno) y se invoca con un object[] tipado; los parámetros ref/out
vuelven en ese arreglo. Ningún texto se evalúa como código.

Antes de cualquier mutación se comprueban, en este orden: huella de la solicitud, estructura
y lista blanca del plan, unidades kN_m_C explícitas, destino inexistente, huella de la copia,
versión de archivo y token de la DLL, todas las firmas y conversiones de argumentos, modelo
abierto esperado y, ejecutando el plan, su fase de verificación (Count, nombres libres y campos
de tabla presentes).

Las lecturas Get* posteriores releen el efecto de las asignaciones (verificar_valores) o lo
registran (registrar_valores). En la verificación, GetAllFieldsInTable exige además campos
importables y que la descripción real de un campo nombre los textos que se escribirán.
Una operación 'edicion_tabla' consulta la importabilidad, lee la tabla editable, fusiona los
registros declarados por su clave, escribe solo columnas importables, aplica exigiendo cero
errores fatales, errores y advertencias, y vuelve a leer para comprobar cada campo declarado.
Las tablas y campos son los observados en ETABS 21.1 (ver operaciones_etabs.ESQUEMAS_OBSERVADOS).

Las operaciones se ejecutan en orden y se detienen en el primer error, sin reintentos ni
reparaciones. Cada operación deja en traza.jsonl una línea de inicio y otra de fin o error.
No ejecuta análisis, no cierra ETABS y no guarda sobre un archivo existente.

Modo real: la DLL debe llevar el token de clave pública de CSI. Modo doble: se rechaza esa DLL;
solo se admiten ensamblados de prueba, de modo que un doble nunca contacta la API real.

Códigos de salida: 0 correcto; 10 solicitud; 20 API no disponible; 30 retorno o salida distintos
de lo esperado, o excepción de la API; 40 precondición; 41 evidencia; 42 firma; 50 inesperado.
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

$VersionEjecutor = '0.1.0'
$ProgId = 'CSI.ETABS.API.ETABSObject'
$TokenCsi = '453d728ef24c6f5e'
$UnidadesPlan = 'kN_m_C'
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$CodigosSalida = @{ solicitud = 10; api_no_disponible = 20; api = 30; precondicion = 40; evidencia = 41; firma = 42; inesperado = 50 }

# Copia de operaciones_etabs.FIRMAS (una prueba exige que coincidan). Nada fuera de esta lista se invoca.
# Las superficies (SetSlab y relecturas Get*) nacieron para el plan 0.2 de desarrollo. El ejecutor Python
# prepara planes 0.1 y 0.4 (malla triangulada, sin host completo ni Opening); 0.2/0.3 siguen sin ejecutarse.
$MetodosPermitidos = @(
    'cSapModel.SetPresentUnits', 'cStory.SetStories_2',
    'cPropMaterial.GetNameList', 'cPropMaterial.SetMaterial', 'cPropMaterial.SetMPIsotropic',
    'cPropMaterial.SetWeightAndMass', 'cPropMaterial.SetMassSource_1',
    'cPropArea.GetNameList', 'cPropArea.SetWall', 'cPropFrame.GetNameList', 'cPropFrame.SetRectangle',
    'cPointObj.Count', 'cPointObj.AddCartesian', 'cPointObj.SetLoadForce', 'cPointObj.SetRestraint', 'cPointObj.SetDiaphragm',
    'cFrameObj.Count', 'cFrameObj.AddByPoint', 'cFrameObj.SetLoadDistributed',
    'cAreaObj.Count', 'cAreaObj.AddByPoint', 'cAreaObj.SetLoadUniform',
    'cLoadPatterns.GetNameList', 'cLoadPatterns.Add', 'cLoadCases.GetNameList',
    'cCaseStaticLinear.SetCase', 'cCaseStaticLinear.SetLoads',
    'cCombo.GetNameList', 'cCombo.Add', 'cCombo.SetCaseList',
    'cDiaphragm.GetNameList', 'cDiaphragm.SetDiaphragm', 'cAnalyze.SetRunCaseFlag', 'cFile.Save',
    'cCaseModalEigen.SetCase', 'cCaseModalEigen.SetNumberModes', 'cCaseModalEigen.SetParameters',
    'cCaseModalEigen.GetNumberModes', 'cCaseModalEigen.GetParameters', 'cCaseModalEigen.GetLoads',
    'cCaseResponseSpectrum.SetCase', 'cCaseResponseSpectrum.SetModalCase', 'cCaseResponseSpectrum.SetLoads',
    'cCaseResponseSpectrum.SetEccentricity', 'cCaseResponseSpectrum.GetModalCase', 'cCaseResponseSpectrum.GetLoads',
    'cCaseResponseSpectrum.GetEccentricity', 'cCaseResponseSpectrum.GetDampConstant', 'cCaseResponseSpectrum.GetDampType',
    'cCaseResponseSpectrum.GetModalComb_1',
    'cFunction.GetNameList', 'cFunction.GetValues', 'cDatabaseTables.GetAllFieldsInTable',
    'cDatabaseTables.GetTableForEditingArray', 'cDatabaseTables.SetTableForEditingArray', 'cDatabaseTables.ApplyEditedTables',
    'cPropArea.SetSlabRibbed', 'cPropArea.GetSlabRibbed', 'cPropArea.SetSlabWaffle', 'cPropArea.GetSlabWaffle', 'cAreaObj.SetOpening', 'cAreaObj.GetOpening', 'cAreaObj.SetLocalAxes', 'cAreaObj.GetLocalAxes', 'cPropArea.SetSlab', 'cPropArea.GetSlab', 'cPropArea.GetWall', 'cAreaObj.GetPoints', 'cAreaObj.GetProperty',
    'cPointObj.GetCoordCartesian',
    # Relecturas del plan 0.4 de malla triangulada (apoyos, cargas de área, fuente de masa, extremos de frames).
    'cPointObj.GetRestraint', 'cAreaObj.GetLoadUniform', 'cPropMaterial.GetMassSource_1', 'cFrameObj.GetPoints',
    # Sección L nativa e inserción en el centroide (configuración 0.5, ensayo propio columna_l_246b).
    'cPropFrame.SetConcreteL', 'cPropFrame.GetConcreteL', 'cFrameObj.SetInsertionPoint', 'cFrameObj.GetInsertionPoint'
)

# Solo se invocan dentro de una operación 'edicion_tabla', con estas firmas exactas.
$FirmasTabla = [ordered]@{
    campos = @('GetAllFieldsInTable', 'String TableKey, Int32& TableVersion, Int32& NumberFields, String[]& FieldKey, String[]& FieldName, String[]& Description, String[]& UnitsString, Boolean[]& IsImportable')
    leer = @('GetTableForEditingArray', 'String TableKey, String GroupName, Int32& TableVersion, String[]& FieldsKeysIncluded, Int32& NumberRecords, String[]& TableData')
    escribir = @('SetTableForEditingArray', 'String TableKey, Int32& TableVersion, String[]& FieldsKeysIncluded, Int32 NumberRecords, String[]& TableData')
    aplicar = @('ApplyEditedTables', 'Boolean FillImportLog, Int32& NumFatalErrors, Int32& NumErrorMsgs, Int32& NumWarnMsgs, Int32& NumInfoMsgs, String& ImportLog')
}
$MetodosSoloTabla = @('cDatabaseTables.GetTableForEditingArray', 'cDatabaseTables.SetTableForEditingArray', 'cDatabaseTables.ApplyEditedTables')
# Claves observadas en ETABS 21.1; una clave inexistente devolvió -96 en GetAllFieldsInTable.
$TablasEditables = @{
    'Functions - Response Spectrum - User Defined' = @{ clave = 'Name'; modo = 'agregar' }
    'Load Case Definitions - Response Spectrum' = @{ clave = 'Name'; modo = 'modificar' }
    'Load Case Definitions - Damping - Modal' = @{ clave = 'Name'; modo = 'modificar' }
    # Plan 0.5: presión hidrostática revisada. Agregar conserva filas ajenas y rechaza objetos ya cargados.
    'Area Load Assignments - Non-uniform' = @{ clave = 'UniqueName'; modo = 'agregar' }
}

# -- utilidades ----------------------------------------------------------------

function New-Fallo([string]$Tipo, [string]$Mensaje, $CodigoApi = $null) {
    $excepcion = New-Object System.InvalidOperationException($Mensaje)
    $excepcion.Data['draft2model_tipo'] = $Tipo
    $excepcion.Data['codigo_api'] = $CodigoApi
    return $excepcion
}

function Get-Campo($Objeto, [string]$Nombre, [switch]$Opcional) {
    if ($null -ne $Objeto -and $null -ne $Objeto.PSObject.Properties[$Nombre]) { return $Objeto.$Nombre }
    if ($Opcional) { return $null }
    throw (New-Fallo 'solicitud' "Falta el campo '$Nombre'.")
}

function Get-Texto($Objeto, [string]$Nombre) {
    $valor = Get-Campo $Objeto $Nombre
    if ($valor -isnot [string] -or [string]::IsNullOrWhiteSpace($valor)) { throw (New-Fallo 'solicitud' "'$Nombre' debe ser texto no vacío.") }
    return $valor
}

function Test-Entero($Valor) { return ($Valor -is [int] -or $Valor -is [long]) }

function Test-Numero($Valor) {
    return ($Valor -is [int] -or $Valor -is [long] -or $Valor -is [double] -or $Valor -is [decimal])
}

function Test-MismaRuta([string]$A, [string]$B) {
    if ([string]::IsNullOrEmpty($A) -or [string]::IsNullOrEmpty($B)) { return $false }
    return ([System.IO.Path]::GetFullPath($A).TrimEnd('\') -ieq [System.IO.Path]::GetFullPath($B).TrimEnd('\'))
}

function Get-Sha256Bytes([byte[]]$Bytes) {
    $algoritmo = [System.Security.Cryptography.SHA256]::Create()
    try { return ([System.BitConverter]::ToString($algoritmo.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $algoritmo.Dispose() }
}

function Get-Sha256([string]$Ruta) {
    $flujo = [System.IO.File]::OpenRead($Ruta)
    $algoritmo = [System.Security.Cryptography.SHA256]::Create()
    try { return ([System.BitConverter]::ToString($algoritmo.ComputeHash($flujo))).Replace('-', '').ToLowerInvariant() }
    finally { $algoritmo.Dispose(); $flujo.Dispose() }
}

function Get-Base($Objeto) {
    if ($Objeto -is [System.Management.Automation.PSObject]) { return $Objeto.PSObject.BaseObject }
    return $Objeto
}

function Test-Lectura([string]$Metodo) { return ($Metodo -match '^c\w+\.(Count|Get\w+)$') }

function Test-ValorIgual($Real, $Esperado, [double]$Tolerancia) {
    if ($null -ne $Esperado -and $null -ne $Esperado.PSObject.Properties['enum']) {
        if ($null -eq $Real -or -not $Real.GetType().IsEnum) { return $false }
        return ($Real.GetType().Name -ceq [string]$Esperado.enum -and
                $Real.ToString() -ceq [string]$Esperado.nombre -and [int]$Real -eq [int]$Esperado.valor)
    }
    if ($Esperado -is [array]) {
        $reales = @(); if ($null -ne $Real) { $reales = @($Real) }
        $esperados = @($Esperado)
        if ($reales.Count -ne $esperados.Count) { return $false }
        for ($i = 0; $i -lt $esperados.Count; $i++) { if (-not (Test-ValorIgual $reales[$i] $esperados[$i] $Tolerancia)) { return $false } }
        return $true
    }
    if ($Esperado -is [bool]) { return ($Real -is [bool] -and $Real -eq $Esperado) }
    if (Test-Numero $Esperado) {
        if (-not (Test-Numero $Real) -and $Real -isnot [single]) { return $false }
        $r = [double]$Real; $e = [double]$Esperado
        return ([Math]::Abs($r - $e) -le $Tolerancia * [Math]::Max(1.0, [Math]::Max([Math]::Abs($r), [Math]::Abs($e))))
    }
    return ([string]$Real -ceq [string]$Esperado)
}

function Test-ContornoOrientadoIgual($Real, $Esperado) {
    # GetPoints puede cambiar el inicio del ciclo; no se admite invertirlo ni ordenar sus nodos.
    $r = @($Real); $e = @($Esperado)
    if ($r.Count -lt 3 -or $r.Count -ne $e.Count) { return $false }
    if (@($r | Select-Object -Unique).Count -ne $r.Count -or @($e | Select-Object -Unique).Count -ne $e.Count) { return $false }
    for ($k = 0; $k -lt $r.Count; $k++) {
        $igual = $true
        for ($i = 0; $i -lt $r.Count; $i++) {
            if ($r[($i+$k)%$r.Count] -isnot [string] -or $e[$i] -isnot [string] -or $r[($i+$k)%$r.Count] -cne $e[$i]) { $igual=$false; break }
        }
        if ($igual) { return $true }
    }
    return $false
}

function Test-CampoIgual([string]$A, [string]$B) {
    $x = 0.0; $y = 0.0
    $estilo = [System.Globalization.NumberStyles]::Float
    $cultura = [System.Globalization.CultureInfo]::InvariantCulture
    if ([double]::TryParse($A, $estilo, $cultura, [ref]$x) -and [double]::TryParse($B, $estilo, $cultura, [ref]$y)) {
        return ([Math]::Abs($x - $y) -le 1e-12 * [Math]::Max(1.0, [Math]::Max([Math]::Abs($x), [Math]::Abs($y))))
    }
    return ($A -ceq $B)
}

function Get-RutaEdb($Objeto, [string]$Nombre) {
    $ruta = Get-Texto $Objeto $Nombre
    if (-not [System.IO.Path]::IsPathRooted($ruta) -or [System.IO.Path]::GetExtension($ruta) -ine '.edb') {
        throw (New-Fallo 'solicitud' "'$Nombre' debe ser una ruta absoluta .edb.")
    }
    return [System.IO.Path]::GetFullPath($ruta)
}

function Add-Traza([hashtable]$Contexto, $Linea) {
    $Linea['utc'] = [DateTime]::UtcNow.ToString('o')
    [System.IO.File]::AppendAllText($Contexto.traza, (ConvertTo-Json -InputObject $Linea -Depth 8 -Compress) + "`n", $Utf8)
}

function Test-Referencia($Valor) {
    return ($Valor -is [System.Management.Automation.PSCustomObject] -and $null -ne $Valor.PSObject.Properties['ref'] `
            -and @($Valor.PSObject.Properties).Count -eq 1 -and $Valor.ref -is [string])
}

# -- conversión tipada de argumentos ------------------------------------------

function ConvertTo-Escalar([Type]$Tipo, $Valor, $Mapeo, [switch]$Simular, [string]$Etiqueta) {
    if (Test-Referencia $Valor) {
        if ($Tipo -ne [string]) { throw (New-Fallo 'firma' "${Etiqueta}: una referencia solo se admite como String.") }
        if (-not $Mapeo.Contains($Valor.ref)) { throw (New-Fallo 'solicitud' "${Etiqueta}: referencia '$($Valor.ref)' no registrada antes.") }
        if ($Simular) { return 'referencia' }
        return [string]$Mapeo[$Valor.ref]
    }
    if ($Tipo.IsEnum) {
        if ($Valor -isnot [System.Management.Automation.PSCustomObject] -or (Get-Campo $Valor 'enum' -Opcional) -ne $Tipo.Name) {
            throw (New-Fallo 'firma' "${Etiqueta}: se esperaba un valor de $($Tipo.Name).")
        }
        $numero = Get-Campo $Valor 'valor'
        if (-not (Test-Entero $numero)) { throw (New-Fallo 'firma' "${Etiqueta}: valor de enumeración no entero.") }
        $nombre = Get-Campo $Valor 'nombre' -Opcional
        if ($null -ne $nombre -and [Enum]::GetName($Tipo, [int]$numero) -ne $nombre) {
            throw (New-Fallo 'firma' "${Etiqueta}: $($Tipo.Name).$nombre no vale $numero en la DLL.")
        }
        if ($null -eq $nombre -and $numero -ne 0) { throw (New-Fallo 'firma' "${Etiqueta}: solo 0 puede ir sin nombre.") }
        return [Enum]::ToObject($Tipo, [int]$numero)
    }
    if ($Tipo -eq [string]) { if ($Valor -is [string]) { return $Valor } }
    elseif ($Tipo -eq [bool]) { if ($Valor -is [bool]) { return $Valor } }
    elseif ($Tipo -eq [int]) {
        if ((Test-Entero $Valor) -and $Valor -ge [int]::MinValue -and $Valor -le [int]::MaxValue) { return [int]$Valor }
    }
    elseif ($Tipo -eq [double]) { if ((Test-Numero $Valor) -and $Valor -isnot [bool]) { return [double]$Valor } }
    else { throw (New-Fallo 'firma' "${Etiqueta}: tipo .NET no admitido $($Tipo.FullName).") }
    throw (New-Fallo 'firma' "${Etiqueta}: valor no convertible a $($Tipo.Name).")
}

function ConvertTo-Argumento([Type]$TipoParametro, $Valor, $Mapeo, [switch]$Simular, [string]$Etiqueta) {
    $tipo = $TipoParametro
    if ($tipo.IsByRef) { $tipo = $tipo.GetElementType() }
    if ($tipo.IsArray) {
        $elemento = $tipo.GetElementType()
        if ($null -eq $Valor -or -not ($Valor -is [array])) { throw (New-Fallo 'firma' "${Etiqueta}: se esperaba un arreglo.") }
        $elementos = @($Valor)
        $arreglo = [Array]::CreateInstance($elemento, $elementos.Count)
        for ($i = 0; $i -lt $elementos.Count; $i++) {
            $arreglo.SetValue((ConvertTo-Escalar $elemento $elementos[$i] $Mapeo -Simular:$Simular -Etiqueta "$Etiqueta[$i]"), $i)
        }
        return ,$arreglo
    }
    return (ConvertTo-Escalar $tipo $Valor $Mapeo -Simular:$Simular -Etiqueta $Etiqueta)
}

# -- validación del plan ------------------------------------------------------

function Test-Operaciones($Operaciones, [string]$Destino) {
    if ($Operaciones.Count -eq 0) { throw (New-Fallo 'solicitud' 'El plan no contiene operaciones.') }
    $primeraMutacion = -1
    $ultimaFueraVerificacion = -1
    $unidades = @()
    for ($i = 0; $i -lt $Operaciones.Count; $i++) {
        $op = $Operaciones[$i]
        if ((Get-Campo $op 'orden') -ne $i + 1) { throw (New-Fallo 'solicitud' "Orden no consecutivo en la operación $($i + 1).") }
        $metodo = Get-Texto $op 'metodo'
        $fase = Get-Texto $op 'fase'
        $null = Get-Texto $op 'interfaz'
        $retorno = Get-Campo $op 'retorno'
        if (-not (Test-Entero (Get-Campo $retorno 'esperado')) -or -not ((Get-Campo $retorno 'tipo') -is [string])) {
            throw (New-Fallo 'solicitud' "Operación $($i + 1): retorno esperado inválido.")
        }
        if ($metodo -eq 'edicion_tabla') {
            $tabla = Get-Texto $op 'tabla'
            if (-not $TablasEditables.ContainsKey($tabla)) { throw (New-Fallo 'solicitud' "Tabla no editable por el plan: $tabla.") }
            if ((Get-Texto $op 'modo') -ne $TablasEditables[$tabla].modo -or (Get-Texto $op 'clave') -ne $TablasEditables[$tabla].clave) {
                throw (New-Fallo 'solicitud' "Modo o clave no admitidos para $tabla.")
            }
            $campos = @(Get-Campo $op 'campos')
            if ($campos -notcontains $TablasEditables[$tabla].clave) { throw (New-Fallo 'solicitud' 'La clave debe ser uno de los campos.') }
            $registros = @(Get-Campo $op 'registros')
            if ($registros.Count -eq 0) { throw (New-Fallo 'solicitud' "La edición de $tabla no declara registros.") }
            foreach ($registro in $registros) {
                foreach ($campo in $campos) {
                    if ((Get-Campo $registro $campo) -isnot [string]) { throw (New-Fallo 'solicitud' "Registro de $tabla sin texto para '$campo'.") }
                }
                if (@($registro.PSObject.Properties).Count -ne $campos.Count) { throw (New-Fallo 'solicitud' "Registro de $tabla con campos no declarados.") }
            }
        } else {
            if ($MetodosPermitidos -notcontains $metodo) { throw (New-Fallo 'solicitud' "Método fuera de la lista blanca: $metodo.") }
            if ($MetodosSoloTabla -contains $metodo) { throw (New-Fallo 'solicitud' "$metodo solo se admite dentro de una edición de tabla.") }
            foreach ($argumento in @(Get-Campo $op 'argumentos')) {
                $null = Get-Texto $argumento 'nombre'; $null = Get-Texto $argumento 'tipo'; $null = Get-Campo $argumento 'valor'
            }
        }
        if ($fase -eq 'verificacion') {
            if (-not (Test-Lectura $metodo)) { throw (New-Fallo 'solicitud' 'La fase de verificación solo admite lecturas.') }
            if ($ultimaFueraVerificacion -ge 0) { throw (New-Fallo 'solicitud' 'Las verificaciones deben preceder a toda mutación.') }
        } else { $ultimaFueraVerificacion = $i }
        if (-not (Test-Lectura $metodo) -and $primeraMutacion -lt 0) { $primeraMutacion = $i }
        if ($metodo -eq 'cSapModel.SetPresentUnits') { $unidades += $i }
    }
    if ($unidades.Count -ne 1 -or $unidades[0] -ne $primeraMutacion) {
        throw (New-Fallo 'solicitud' 'El plan debe fijar unidades una sola vez y como primera mutación.')
    }
    $valorUnidades = (@($Operaciones[$unidades[0]].argumentos))[0].valor
    if ((Get-Campo $valorUnidades 'nombre' -Opcional) -ne $UnidadesPlan -or (Get-Campo $valorUnidades 'enum' -Opcional) -ne 'eUnits') {
        throw (New-Fallo 'solicitud' "Solo se admiten las unidades explícitas del plan ($UnidadesPlan).")
    }
    $guardados = @($Operaciones | Where-Object { $_.metodo -eq 'cFile.Save' })
    $ultima = $Operaciones[$Operaciones.Count - 1]
    if ($guardados.Count -ne 1 -or $ultima.metodo -ne 'cFile.Save') { throw (New-Fallo 'solicitud' 'cFile.Save debe ser la única y última operación.') }
    if (-not (Test-MismaRuta ((@($ultima.argumentos))[0].valor) $Destino)) { throw (New-Fallo 'solicitud' 'El guardado del plan no apunta al destino declarado.') }
}

function Resolve-Metodo($Asm, $Op) {
    $iface, $nombre = ([string]$Op.metodo).Split('.')
    $tipo = $Asm.GetType("ETABSv1.$iface")
    if ($null -eq $tipo) { throw (New-Fallo 'firma' "La DLL no define ETABSv1.$iface.") }
    $esperados = @(@($Op.argumentos) | ForEach-Object { "$($_.tipo) $($_.nombre)" }) -join ', '
    foreach ($candidato in $tipo.GetMethods()) {
        if ($candidato.Name -ne $nombre -or $candidato.ReturnType.Name -ne $Op.retorno.tipo) { continue }
        $reales = @($candidato.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ', '
        if ($reales -eq $esperados) { return $candidato }
    }
    throw (New-Fallo 'firma' "Ninguna sobrecarga de $($Op.metodo) coincide con la firma del plan ($esperados).")
}

function Resolve-Tabla($Asm) {
    $tipo = $Asm.GetType('ETABSv1.cDatabaseTables')
    if ($null -eq $tipo) { throw (New-Fallo 'firma' 'La DLL no define ETABSv1.cDatabaseTables.') }
    $resueltos = @{ declarante = $tipo }
    foreach ($clave in $FirmasTabla.Keys) {
        $nombre, $esperados = $FirmasTabla[$clave]
        $resueltos[$clave] = $null
        foreach ($candidato in $tipo.GetMethods()) {
            if ($candidato.Name -ne $nombre -or $candidato.ReturnType.Name -ne 'Int32') { continue }
            $reales = @($candidato.GetParameters() | ForEach-Object { "$($_.ParameterType.Name) $($_.Name)" }) -join ', '
            if ($reales -eq $esperados) { $resueltos[$clave] = $candidato }
        }
        if ($null -eq $resueltos[$clave]) { throw (New-Fallo 'firma' "cDatabaseTables.$nombre no coincide con la firma esperada.") }
    }
    return $resueltos
}

function Read-Tabla($Metodos, $Objetivo, [string]$Tabla) {
    $valores = New-Object 'object[]' 6
    $valores[0] = $Tabla; $valores[1] = ''; $valores[2] = [int]0; $valores[3] = [string[]]@(); $valores[4] = [int]0; $valores[5] = [string[]]@()
    $retorno = $Metodos.leer.Invoke($Objetivo, $valores)
    if ([int]$retorno -ne 0) { throw (New-Fallo 'api' "GetTableForEditingArray($Tabla) devolvió $retorno." ([int]$retorno)) }
    $campos = @(); if ($null -ne $valores[3]) { $campos = @($valores[3]) }
    $datos = @(); if ($null -ne $valores[5]) { $datos = @($valores[5]) }
    $n = [int]$valores[4]
    if ($datos.Count -ne $campos.Count * $n) { throw (New-Fallo 'api' "La tabla $Tabla devolvió $($datos.Count) valores para $n registros de $($campos.Count) campos.") }
    $filas = New-Object System.Collections.ArrayList
    for ($r = 0; $r -lt $n; $r++) {
        $fila = [ordered]@{}
        for ($c = 0; $c -lt $campos.Count; $c++) { $fila[$campos[$c]] = [string]$datos[$r * $campos.Count + $c] }
        [void]$filas.Add($fila)
    }
    return @{ version = [int]$valores[2]; campos = $campos; filas = $filas }
}

function Get-Importables($Metodos, $Objetivo, [string]$Tabla) {
    $valores = New-Object 'object[]' 8
    $valores[0] = $Tabla; $valores[1] = [int]0; $valores[2] = [int]0
    for ($i = 3; $i -le 6; $i++) { $valores[$i] = [string[]]@() }
    $valores[7] = [bool[]]@()
    $retorno = $Metodos.campos.Invoke($Objetivo, $valores)
    if ([int]$retorno -ne 0) { throw (New-Fallo 'precondicion' "GetAllFieldsInTable($Tabla) devolvió $($retorno): la tabla no existe en esta versión." ([int]$retorno)) }
    $claves = @($valores[3]); $importables = @($valores[7])
    if ($claves.Count -ne $importables.Count) { throw (New-Fallo 'api' "GetAllFieldsInTable($Tabla) devolvió listas de distinta longitud.") }
    $mapa = @{}
    for ($i = 0; $i -lt $claves.Count; $i++) { $mapa[[string]$claves[$i]] = [bool]$importables[$i] }
    return $mapa
}

function Invoke-EdicionTabla($Op, $Metodos, $Objetivo) {
    $tabla = [string]$Op.tabla; $clave = [string]$Op.clave; $declarados = @($Op.campos); $registros = @($Op.registros)
    $importables = Get-Importables $Metodos $Objetivo $tabla
    foreach ($campo in $declarados) {
        if (-not $importables.ContainsKey($campo)) { throw (New-Fallo 'precondicion' "La tabla $tabla no tiene el campo '$campo'.") }
        if (-not $importables[$campo]) { throw (New-Fallo 'precondicion' "El campo '$campo' de $tabla no es importable.") }
    }
    $actual = Read-Tabla $Metodos $Objetivo $tabla
    $columnas = $actual.campos
    if ($columnas.Count -eq 0) { $columnas = $declarados }  # tabla sin registros: solo los campos declarados
    foreach ($campo in $declarados) {
        if ($columnas -notcontains $campo) { throw (New-Fallo 'precondicion' "La tabla $tabla no ofrece el campo '$campo' para edición.") }
    }
    # Solo se escriben columnas importables (p. ej. MassSource y CoordSys del caso espectral no lo son).
    $columnas = @($columnas | Where-Object { $importables.ContainsKey([string]$_) -and $importables[[string]$_] })
    $nombres = @($registros | ForEach-Object { [string]$_.$clave } | Select-Object -Unique)
    $filas = $actual.filas
    if ($Op.modo -eq 'agregar') {
        foreach ($fila in $filas) {
            if ($nombres -contains $fila[$clave]) { throw (New-Fallo 'precondicion' "La tabla $tabla ya contiene '$($fila[$clave])'.") }
        }
        foreach ($registro in $registros) {
            $nueva = [ordered]@{}
            foreach ($columna in $columnas) { if ($declarados -contains $columna) { $nueva[$columna] = [string]$registro.$columna } else { $nueva[$columna] = '' } }
            [void]$filas.Add($nueva)
        }
    } else {
        if ($nombres.Count -ne $registros.Count) { throw (New-Fallo 'solicitud' "Modificar $tabla exige un registro por '$clave'.") }
        foreach ($registro in $registros) {
            $coincidentes = @($filas | Where-Object { $_[$clave] -ceq [string]$registro.$clave })
            if ($coincidentes.Count -eq 0) { throw (New-Fallo 'precondicion' "La tabla $tabla no contiene '$($registro.$clave)' para modificar.") }
            foreach ($fila in $coincidentes) { foreach ($campo in $declarados) { $fila[$campo] = [string]$registro.$campo } }
        }
    }
    $plano = New-Object System.Collections.ArrayList
    foreach ($fila in $filas) { foreach ($columna in $columnas) { [void]$plano.Add([string]$fila[$columna]) } }
    $escritura = New-Object 'object[]' 5
    $escritura[0] = $tabla; $escritura[1] = [int]$actual.version; $escritura[2] = [string[]]$columnas
    $escritura[3] = [int]$filas.Count; $escritura[4] = [string[]]$plano.ToArray([string])
    $retorno = $Metodos.escribir.Invoke($Objetivo, $escritura)
    if ([int]$retorno -ne 0) { throw (New-Fallo 'api' "SetTableForEditingArray($tabla) devolvió $retorno." ([int]$retorno)) }
    $aplicacion = New-Object 'object[]' 6
    $aplicacion[0] = $true; $aplicacion[1] = [int]0; $aplicacion[2] = [int]0; $aplicacion[3] = [int]0; $aplicacion[4] = [int]0; $aplicacion[5] = ''
    $retorno = $Metodos.aplicar.Invoke($Objetivo, $aplicacion)
    $bitacora = [string]$aplicacion[5]
    if ($bitacora.Length -gt 4000) { $bitacora = $bitacora.Substring(0, 4000) }
    if ([int]$retorno -ne 0 -or [int]$aplicacion[1] -ne 0 -or [int]$aplicacion[2] -ne 0 -or [int]$aplicacion[3] -ne 0) {
        throw (New-Fallo 'api' ("ApplyEditedTables($tabla): retorno $retorno, fatales $($aplicacion[1]), errores $($aplicacion[2]), " +
            "advertencias $($aplicacion[3]). Registro: $bitacora") ([int]$retorno))
    }
    $releida = Read-Tabla $Metodos $Objetivo $tabla
    # CSI emite DampRatio solo en la primera fila de cada función. Expandir
    # exclusivamente ese campo agrupado para contrastarlo; conservar datos crudos.
    if ($tabla -ceq 'Functions - Response Spectrum - User Defined') {
        $amortiguamientos = @{}
        foreach ($fila in $releida.filas) {
            $idFuncion = [string]$fila['Name']
            $damp = [string]$fila['DampRatio']
            if ($damp -ne '') { $amortiguamientos[$idFuncion] = $damp }
            elseif ($amortiguamientos.ContainsKey($idFuncion)) { $fila['DampRatio'] = $amortiguamientos[$idFuncion] }
        }
    }
    foreach ($nombre in $nombres) {
        $declaradosNombre = @($registros | Where-Object { [string]$_.$clave -ceq $nombre })
        $leidas = @($releida.filas | Where-Object { $_[$clave] -ceq $nombre })
        if ($Op.modo -eq 'agregar' -and $leidas.Count -ne $declaradosNombre.Count) {
            throw (New-Fallo 'api' "Tras aplicar, $tabla tiene $($leidas.Count) registros de '$nombre'; se declararon $($declaradosNombre.Count).")
        }
        if ($leidas.Count -eq 0) { throw (New-Fallo 'api' "Tras aplicar, $tabla no contiene '$nombre'.") }
        foreach ($declarado in $declaradosNombre) {
            $coincide = @($leidas | Where-Object {
                $fila = $_; @($declarados | Where-Object { -not (Test-CampoIgual $fila[$_] ([string]$declarado.$_)) }).Count -eq 0 })
            if ($coincide.Count -eq 0) { throw (New-Fallo 'api' "Tras aplicar, $tabla no refleja el registro declarado de '$nombre'.") }
        }
        if ($Op.modo -eq 'modificar') {
            foreach ($fila in $leidas) {
                foreach ($campo in $declarados) {
                    if (-not (Test-CampoIgual $fila[$campo] ([string]$declaradosNombre[0].$campo))) { throw (New-Fallo 'api' "Tras aplicar, $tabla.$campo de '$nombre' vale '$($fila[$campo])'.") }
                }
            }
        }
    }
    return [ordered]@{ tabla = $tabla; registros_totales = $filas.Count; registros_declarados = $registros.Count
                       columnas_escritas = @($columnas); info = [int]$aplicacion[4]; registro_importacion = $bitacora }
}

function Get-Objetivo($Etabs, [string]$Ruta, [Type]$TipoDeclarante) {
    $objeto = $Etabs
    foreach ($segmento in $Ruta.Split('.')) {
        try { $objeto = $objeto.$segmento } catch { throw (New-Fallo 'firma' "No se pudo obtener '$segmento' en '$Ruta'.") }
        if ($null -eq $objeto) { throw (New-Fallo 'api' "La API devolvió null para '$segmento' en '$Ruta'.") }
    }
    $base = Get-Base $objeto
    if (-not $TipoDeclarante.IsInstanceOfType($base)) { throw (New-Fallo 'firma' "'$Ruta' no implementa $($TipoDeclarante.Name).") }
    return $base
}

# -- principal ---------------------------------------------------------------

$respuestaObj = [ordered]@{
    contrato = 'draft2model.etabs_respuesta'; version_contrato = '0.1.0'; version_puente = "ejecutor-$VersionEjecutor"
    modo_ejecucion = $Modo; id_solicitud = $null; operacion = $null; estado = 'error'; error = $null; datos = $null
    avisos = @(); progreso = $null; inicio_utc = [DateTime]::UtcNow.ToString('o'); fin_utc = $null
    entorno = [ordered]@{ powershell = $PSVersionTable.PSVersion.ToString(); edicion = $PSVersionTable.PSEdition; proceso_64_bits = [Environment]::Is64BitProcess }
}
$progreso = [ordered]@{ operaciones_totales = 0; operaciones_ejecutadas = 0; mutaciones_realizadas = $false; orden_fallida = $null; mapeo_nombres = [ordered]@{} }
$contexto = @{ traza = (Join-Path (Split-Path -Parent $Respuesta) 'traza.jsonl'); avisos = (New-Object System.Collections.ArrayList) }
$opActual = $null
$codigoSalida = 0
# La corrida se llama como el id de la solicitud: permite asociar la respuesta aunque la solicitud esté alterada.
$idCorrida = Split-Path -Leaf (Split-Path -Parent $Respuesta)
if ($idCorrida -match '^[0-9a-f]{32}$') { $respuestaObj.id_solicitud = $idCorrida }

try {
    if ($PSVersionTable.PSVersion.Major -ne 5) { throw (New-Fallo 'api_no_disponible' "Se requiere Windows PowerShell 5.1; se ejecuta $($PSVersionTable.PSVersion).") }
    try { $bytes = [System.IO.File]::ReadAllBytes($Solicitud) } catch { throw (New-Fallo 'solicitud' "Solicitud ilegible: $($_.Exception.Message)") }
    if ((Get-Sha256Bytes $bytes) -ne $Sha256Solicitud) { throw (New-Fallo 'evidencia' 'La solicitud cambió después de prepararla; no se ejecuta.') }
    try { $sol = $Utf8.GetString($bytes) | ConvertFrom-Json } catch { throw (New-Fallo 'solicitud' "Solicitud no es JSON: $($_.Exception.Message)") }
    $id = Get-Texto $sol 'id'
    if ($id -notmatch '^[0-9a-f]{32}$' -or $id -ne $idCorrida) { throw (New-Fallo 'solicitud' "'id' debe tener 32 hexadecimales y coincidir con la corrida.") }
    if ((Get-Campo $sol 'contrato') -ne 'draft2model.etabs_solicitud' -or (Get-Campo $sol 'version_contrato') -ne '0.1.0' -or (Get-Campo $sol 'operacion') -ne 'ejecutar_plan') {
        throw (New-Fallo 'solicitud' 'Solicitud no corresponde a ejecutar_plan 0.1.0.')
    }
    $respuestaObj.operacion = 'ejecutar_plan'
    $modo = Get-Texto $sol 'modo_configurado'
    if ($modo -ne $Modo) { throw (New-Fallo 'solicitud' "La solicitud declara modo '$modo' y el proceso se lanzó en modo '$Modo'.") }

    $operaciones = @(Get-Campo $sol 'operaciones')
    $progreso.operaciones_totales = $operaciones.Count
    $destino = Get-RutaEdb $sol 'destino'
    $modelo = Get-RutaEdb $sol 'modelo_esperado'
    Test-Operaciones $operaciones $destino
    if (Test-Path -LiteralPath $destino) { throw (New-Fallo 'precondicion' "El destino ya existe; no se sobrescribe: $destino") }
    if (-not (Test-Path -LiteralPath ([System.IO.Path]::GetDirectoryName($destino)) -PathType Container)) { throw (New-Fallo 'precondicion' 'No existe la carpeta del destino.') }
    if (-not (Test-Path -LiteralPath $modelo -PathType Leaf)) { throw (New-Fallo 'precondicion' "No existe la copia: $modelo") }
    if ((Get-Sha256 $modelo) -ne (Get-Texto $sol 'sha256_copia')) { throw (New-Fallo 'evidencia' 'La copia no coincide con la huella de la plantilla del plan.') }

    $dll = Get-Texto $sol 'dll'
    if (-not (Test-Path -LiteralPath $dll -PathType Leaf)) { throw (New-Fallo 'api_no_disponible' "No existe la DLL: $dll") }
    $versionArchivo = (Get-Item -LiteralPath $dll).VersionInfo.FileVersion
    if ($versionArchivo -ne (Get-Texto $sol 'version_dll_esperada')) { throw (New-Fallo 'precondicion' "Versión de DLL $versionArchivo distinta de la verificada para el plan.") }
    try { $asm = [System.Reflection.Assembly]::LoadFrom($dll) } catch { throw (New-Fallo 'api_no_disponible' "No se pudo cargar la DLL: $($_.Exception.Message)") }
    $token = (@($asm.GetName().GetPublicKeyToken() | ForEach-Object { $_.ToString('x2') }) -join '')
    if ($modo -eq 'real' -and $token -ne $TokenCsi) { throw (New-Fallo 'precondicion' 'Modo real exige la DLL firmada por CSI.') }
    if ($modo -eq 'doble' -and $token -eq $TokenCsi) { throw (New-Fallo 'precondicion' 'Modo doble no puede cargar la DLL real de CSI.') }

    # Todas las firmas y conversiones se comprueban antes de conectar y de mutar.
    $metodos = @{}
    $simulado = @{}
    foreach ($op in $operaciones) {
        if ($op.metodo -eq 'edicion_tabla') { $metodos[$op.orden] = Resolve-Tabla $asm; continue }
        $metodos[$op.orden] = Resolve-Metodo $asm $op
        $parametros = $metodos[$op.orden].GetParameters()
        $argumentos = @($op.argumentos)
        for ($i = 0; $i -lt $parametros.Count; $i++) {
            $null = ConvertTo-Argumento $parametros[$i].ParameterType $argumentos[$i].valor $simulado -Simular -Etiqueta "Operación $($op.orden) $($argumentos[$i].nombre)"
        }
        foreach ($salida in @(Get-Campo $op 'salidas' -Opcional)) {
            if ($null -eq $salida) { continue }
            $registra = Get-Texto $salida 'registra'
            if ($simulado.Contains($registra)) { throw (New-Fallo 'solicitud' "Salida registrada dos veces: $registra.") }
            $simulado[$registra] = 'simulado'
        }
    }

    $helper = $asm.CreateInstance('ETABSv1.Helper')
    if ($null -eq $helper) { throw (New-Fallo 'api_no_disponible' 'La DLL no define ETABSv1.Helper.') }
    $idProceso = Get-Campo $sol 'id_proceso' -Opcional
    try {
        if ($null -ne $idProceso) { $etabs = $helper.GetObjectProcess($ProgId, [int]$idProceso) } else { $etabs = $helper.GetObject($ProgId) }
    } catch { throw (New-Fallo 'api_no_disponible' "No se pudo conectar con ETABS: $($_.Exception.Message)") }
    if ($null -eq $etabs) { throw (New-Fallo 'api_no_disponible' 'La API no devolvió una instancia de ETABS.') }
    $sap = $etabs.SapModel
    $abierto = $sap.GetModelFilename($true)
    if (-not (Test-MismaRuta $abierto $modelo)) { throw (New-Fallo 'precondicion' "El modelo abierto ('$abierto') no es la copia esperada ('$modelo').") }

    $objetivos = @{}
    foreach ($op in $operaciones) {
        $declarante = if ($op.metodo -eq 'edicion_tabla') { $metodos[$op.orden].declarante } else { $metodos[$op.orden].DeclaringType }
        if (-not $objetivos.Contains($op.interfaz)) { $objetivos[$op.interfaz] = Get-Objetivo $etabs $op.interfaz $declarante }
    }

    foreach ($op in $operaciones) {
        $opActual = $op
        if ($op.metodo -eq 'edicion_tabla') {
            $progreso.mutaciones_realizadas = $true
            Add-Traza $contexto ([ordered]@{ orden = $op.orden; metodo = 'edicion_tabla'; tabla = $op.tabla; evento = 'inicio'; lectura = $false })
            try { $resumen = Invoke-EdicionTabla $op $metodos[$op.orden] $objetivos[$op.interfaz] }
            catch {
                if ($_.Exception.Data.Contains('draft2model_tipo')) { throw }
                $interna = $_.Exception
                while ($null -ne $interna.InnerException) { $interna = $interna.InnerException }
                throw (New-Fallo 'api' "Excepción de la API editando $($op.tabla): $($interna.Message)")
            }
            Add-Traza $contexto ([ordered]@{ orden = $op.orden; metodo = 'edicion_tabla'; evento = 'fin'; retorno = 0; tabla = $resumen })
            $progreso.operaciones_ejecutadas++
            $opActual = $null
            continue
        }
        $metodo = $metodos[$op.orden]
        $parametros = $metodo.GetParameters()
        $argumentos = @($op.argumentos)
        $valores = New-Object 'object[]' $parametros.Count
        for ($i = 0; $i -lt $parametros.Count; $i++) {
            $valores[$i] = ConvertTo-Argumento $parametros[$i].ParameterType $argumentos[$i].valor $progreso.mapeo_nombres -Etiqueta "Operación $($op.orden) $($argumentos[$i].nombre)"
        }
        $lectura = Test-Lectura $op.metodo
        if ($op.metodo -eq 'cFile.Save') {
            if (Test-Path -LiteralPath $destino) { throw (New-Fallo 'precondicion' 'El destino apareció antes de guardar; no se sobrescribe.') }
            if (-not (Test-MismaRuta ($sap.GetModelFilename($true)) $modelo)) { throw (New-Fallo 'precondicion' 'El modelo abierto cambió durante la ejecución.') }
        }
        if (-not $lectura) { $progreso.mutaciones_realizadas = $true }  # se marca antes: una excepción puede haber mutado
        Add-Traza $contexto ([ordered]@{ orden = $op.orden; metodo = $op.metodo; evento = 'inicio'; lectura = $lectura })
        try { $retorno = $metodo.Invoke($objetivos[$op.interfaz], $valores) }
        catch {
            $interna = $_.Exception
            while ($null -ne $interna.InnerException) { $interna = $interna.InnerException }
            throw (New-Fallo 'api' "Excepción de la API en $($op.metodo): $($interna.Message)")
        }
        if ([int]$retorno -ne [int]$op.retorno.esperado) {
            if ($op.metodo -eq 'cDatabaseTables.GetAllFieldsInTable') {
                throw (New-Fallo 'precondicion' "GetAllFieldsInTable('$((@($op.argumentos))[0].valor)') devolvió $($retorno): la tabla no existe en esta versión de ETABS." ([int]$retorno))
            }
            throw (New-Fallo 'api' "$($op.metodo) devolvió $retorno; se esperaba $($op.retorno.esperado)." ([int]$retorno))
        }
        $nombres = @($parametros | ForEach-Object { $_.Name })
        $registradas = [ordered]@{}
        foreach ($salida in @(Get-Campo $op 'salidas' -Opcional)) {
            if ($null -eq $salida) { continue }
            $valor = [string]$valores[[Array]::IndexOf($nombres, $salida.parametro)]
            if ($valor -ne $salida.debe_ser) { throw (New-Fallo 'api' "$($op.metodo): ETABS asignó '$valor'; el plan exige '$($salida.debe_ser)'.") }
            $progreso.mapeo_nombres[$salida.registra] = $valor
            $registradas[$salida.registra] = $valor
        }
        foreach ($ausente in @(Get-Campo $op 'verificar_ausentes' -Opcional)) {
            if ($null -eq $ausente) { continue }
            $existentes = @($valores[[Array]::IndexOf($nombres, $ausente.parametro)])
            $choques = @(@($ausente.nombres) | Where-Object { $existentes -contains $_ })
            if ($choques.Count) { throw (New-Fallo 'precondicion' "$($op.metodo): ya existen $($choques -join ', ').") }
        }
        foreach ($presente in @(Get-Campo $op 'verificar_presentes' -Opcional)) {
            if ($null -eq $presente) { continue }
            $existentes = @($valores[[Array]::IndexOf($nombres, $presente.parametro)])
            $faltan = @(@($presente.nombres) | Where-Object { $existentes -notcontains $_ })
            if ($faltan.Count) { throw (New-Fallo 'precondicion' "$($op.metodo): faltan $($faltan -join ', ') en la versión de ETABS conectada.") }
        }
        $listaImportables = @(Get-Campo $op 'verificar_importables' -Opcional)
        $listaTextos = @(Get-Campo $op 'verificar_textos' -Opcional)
        if (($listaImportables | Where-Object { $null -ne $_ }) -or ($listaTextos | Where-Object { $null -ne $_ })) {
            $clavesCampo = @($valores[[Array]::IndexOf($nombres, 'FieldKey')])
            $esImportable = @($valores[[Array]::IndexOf($nombres, 'IsImportable')])
            $descripciones = @($valores[[Array]::IndexOf($nombres, 'Description')])
            foreach ($campo in $listaImportables) {
                if ($null -eq $campo) { continue }
                $i = [Array]::IndexOf($clavesCampo, [string]$campo)
                if ($i -lt 0 -or $i -ge $esImportable.Count -or -not [bool]$esImportable[$i]) {
                    throw (New-Fallo 'precondicion' "$($op.metodo): el campo '$campo' no es importable en esta versión de ETABS.")
                }
            }
            foreach ($texto in $listaTextos) {
                if ($null -eq $texto) { continue }
                $i = [Array]::IndexOf($clavesCampo, [string]$texto.campo)
                $descripcion = if ($i -ge 0 -and $i -lt $descripciones.Count) { [string]$descripciones[$i] } else { '' }
                foreach ($valorTexto in @($texto.valores)) {
                    $patron = '(?<![A-Za-z0-9])' + [Regex]::Escape([string]$valorTexto) + '(?![A-Za-z0-9])'
                    if ($descripcion -cnotmatch $patron) {
                        throw (New-Fallo 'precondicion' "$($op.metodo): la descripción de '$($texto.campo)' no nombra '$valorTexto'; no se escribe un texto no confirmado. Descripción: '$descripcion'")
                    }
                }
            }
        }
        $representaciones = New-Object System.Collections.ArrayList
        $normalizadosCarga = @{}
        if ($op.metodo -ceq 'cAreaObj.GetLoadUniform') {
            $dirsCarga = @($valores[[Array]::IndexOf($nombres,'Dir')])
            $valCarga = @($valores[[Array]::IndexOf($nombres,'Value')])
            $csCarga = @($valores[[Array]::IndexOf($nombres,'CSys')])
            $convertidos = $false
            if ($dirsCarga.Count -ne $valCarga.Count -or $dirsCarga.Count -ne $csCarga.Count) { throw (New-Fallo 'api' 'GetLoadUniform devolvio listas incompatibles.') }
            for ($i=0; $i -lt $dirsCarga.Count; $i++) {
                if ($csCarga[$i] -ceq 'Global' -and $dirsCarga[$i] -in @(10,11)) {
                    $dirsCarga[$i] = if ($dirsCarga[$i] -eq 10) {6} else {9}
                    $valCarga[$i] = -[double]$valCarga[$i]
                    $convertidos = $true
                }
            }
            if ($convertidos) {
                $normalizadosCarga['Dir']=$dirsCarga; $normalizadosCarga['Value']=$valCarga
                [void]$representaciones.Add([ordered]@{ tipo='gravedad';
                    dir_cruda=$valores[[Array]::IndexOf($nombres,'Dir')]; valor_crudo=$valores[[Array]::IndexOf($nombres,'Value')];
                    dir_global_z=$dirsCarga; valor_global_z=$valCarga })
            }
        }
        $releidos = [ordered]@{}
        foreach ($parametro in @(Get-Campo $op 'registrar_valores' -Opcional)) {
            if ($null -ne $parametro) { $releidos[[string]$parametro] = $valores[[Array]::IndexOf($nombres, [string]$parametro)] }
        }
        foreach ($comprobacion in @(Get-Campo $op 'verificar_valores' -Opcional)) {
            if ($null -eq $comprobacion) { continue }
            $real = $valores[[Array]::IndexOf($nombres, $comprobacion.parametro)]
            $releidos[$comprobacion.parametro] = $real
            if ($normalizadosCarga.ContainsKey([string]$comprobacion.parametro)) { $real=$normalizadosCarga[[string]$comprobacion.parametro] }
            # ETABS 21.1 observado: GetValues informa N puntos y devuelve N+1
            # elementos con centinela (0,0) inicial. Conservar crudo en traza;
            # adaptar solo esta representación reconocida, nunca truncar libremente.
            if ($op.metodo -ceq 'cFunction.GetValues' -and $comprobacion.parametro -in @('MyTime','Value')) {
                $nFuncion = [int]$valores[[Array]::IndexOf($nombres,'NumberItems')]
                $tiempos = @($valores[[Array]::IndexOf($nombres,'MyTime')])
                $amplitudes = @($valores[[Array]::IndexOf($nombres,'Value')])
                if ($nFuncion -gt 0 -and $tiempos.Count -eq $nFuncion+1 -and $amplitudes.Count -eq $nFuncion+1 -and
                    $tiempos[0] -eq 0 -and $amplitudes[0] -eq 0) { $real = @($real)[1..$nFuncion] }
            }
            $coincide = Test-ValorIgual $real $comprobacion.esperado ([double]$comprobacion.tolerancia_relativa)
            if (-not $coincide -and $op.metodo -ceq 'cAreaObj.GetPoints' -and $comprobacion.parametro -ceq 'Point') {
                $coincide = Test-ContornoOrientadoIgual $real $comprobacion.esperado
                if ($coincide) {
                    [void]$representaciones.Add([ordered]@{ tipo='ciclica';
                        esperado=$comprobacion.esperado; observado=$real; orientacion_conservada=$true })
                }
            }
            if (-not $coincide) {
                Add-Traza $contexto ([ordered]@{ orden=$op.orden; metodo=$op.metodo; evento='discrepancia';
                    parametro=$comprobacion.parametro; esperado=$comprobacion.esperado; observado=$real; releidos=$releidos })
                throw (New-Fallo 'api' "$($op.metodo): $($comprobacion.parametro) releído no coincide con lo asignado.")
            }
        }
        if ($op.metodo -eq 'cSapModel.SetPresentUnits' -and $sap.GetPresentUnits().ToString() -ne $UnidadesPlan) {
            throw (New-Fallo 'api' 'Las unidades presentes no son kN_m_C tras fijarlas.')
        }
        $fin = [ordered]@{ orden = $op.orden; metodo = $op.metodo; evento = 'fin'; retorno = [int]$retorno; salidas = $registradas }
        if ($releidos.Count) { $fin.releidos = $releidos }
        if ($representaciones.Count) { $fin.representaciones = @($representaciones) }
        if ($op.metodo -eq 'cFile.Save') {
            if (-not (Test-Path -LiteralPath $destino -PathType Leaf)) { throw (New-Fallo 'api' 'cFile.Save devolvió 0 pero el destino no existe.') }
            $fin.sha256 = Get-Sha256 $destino
        }
        Add-Traza $contexto $fin
        $progreso.operaciones_ejecutadas++
        $opActual = $null
    }
    $respuestaObj.datos = [ordered]@{
        version_dll = $versionArchivo; modelo_abierto = $sap.GetModelFilename($true); unidades = $sap.GetPresentUnits().ToString()
        guardado = [ordered]@{ ruta = $destino; sha256 = (Get-Sha256 $destino) }; huella_plan = (Get-Campo $sol 'huella_plan')
        analisis_ejecutado = $false; aprueba_modelo = $false
    }
    $contexto.avisos.Add('Modelo construido y guardado según el plan; no se ejecutó análisis ni se aprobó el modelo.') | Out-Null
    $respuestaObj.estado = 'ok'
} catch {
    $excepcion = $_.Exception
    $tipo = 'inesperado'
    if ($excepcion.Data.Contains('draft2model_tipo')) { $tipo = $excepcion.Data['draft2model_tipo'] }
    if (-not $CodigosSalida.ContainsKey($tipo)) { $tipo = 'inesperado' }
    $codigoApi = $null
    if ($excepcion.Data.Contains('codigo_api')) { $codigoApi = $excepcion.Data['codigo_api'] }
    $respuestaObj.error = [ordered]@{ tipo = $tipo; mensaje = $excepcion.Message; codigo_api = $codigoApi }
    if ($null -ne $opActual) {
        $progreso.orden_fallida = $opActual.orden
        try { Add-Traza $contexto ([ordered]@{ orden = $opActual.orden; metodo = $opActual.metodo; evento = 'error'; tipo = $tipo; mensaje = $excepcion.Message }) } catch { }
    }
    $codigoSalida = $CodigosSalida[$tipo]
}

$respuestaObj.progreso = $progreso
$respuestaObj.avisos = @($contexto.avisos)
$respuestaObj.fin_utc = [DateTime]::UtcNow.ToString('o')
$temporal = "$Respuesta.tmp-" + [guid]::NewGuid().ToString('N')
try {
    [System.IO.File]::WriteAllText($temporal, (ConvertTo-Json -InputObject $respuestaObj -Depth 16 -Compress), $Utf8)
    [System.IO.File]::Move($temporal, $Respuesta)  # falla si la respuesta existe: no se sobrescribe
} catch {
    if (Test-Path -LiteralPath $temporal) { Remove-Item -LiteralPath $temporal -Force }
    [Console]::Error.WriteLine("Respuesta no publicada: $($_.Exception.Message)")
    exit $CodigosSalida['inesperado']
}
exit $codigoSalida
