param(
 [Parameter(Mandatory=$true)][int]$IdProceso,
 [Parameter(Mandatory=$true)][string]$ModeloEsperado,
 [Parameter(Mandatory=$true)][string]$Configuracion,
 [Parameter(Mandatory=$true)][string]$Registro
)
# Solo getters de una lista fija; no abre ni modifica el modelo.
$ErrorActionPreference='Stop'
if (Test-Path -LiteralPath $Registro) { throw 'El registro debe ser nuevo.' }
Add-Type -Path 'C:\Program Files\Computers and Structures\ETABS 21\ETABSv1.dll'
$helper=New-Object ETABSv1.Helper
$app=$helper.GetObjectProcess('CSI.ETABS.API.ETABSObject',$IdProceso);$sap=$app.SapModel
$opened=$sap.GetModelFilename($true)
if (-not [string]::Equals([IO.Path]::GetFullPath($opened),[IO.Path]::GetFullPath($ModeloEsperado),[StringComparison]::OrdinalIgnoreCase)) { throw 'Modelo abierto distinto.' }
if ($sap.GetPresentUnits().ToString() -ne 'kN_m_C') { throw 'Unidades inesperadas.' }
$config=[IO.File]::ReadAllText($Configuracion) | ConvertFrom-Json
$queries=New-Object 'Collections.Generic.List[object]'
function Agregar([string]$Type,[string]$Method,$Name) { $queries.Add(@{interfaz=$Type;metodo=$Method;nombre=$Name}) }
foreach ($mat in $config.materiales) { Agregar 'cPropMaterial' 'GetMPIsotropic' $mat.id;Agregar 'cPropMaterial' 'GetWeightAndMass' $mat.id }
Agregar 'cPropMaterial' 'GetMassSource_1' $null
foreach ($section in $config.secciones) {
 if ($section.tipo -eq 'shell_muro') { Agregar 'cPropArea' 'GetWall' $section.id }
 elseif ($section.tipo -eq 'frame_rectangular') { Agregar 'cPropFrame' 'GetRectangle' $section.id }
 else { throw 'Seccion no soportada por lector.' }
}
foreach ($frame in $config.frames) { Agregar 'cFrameObj' 'GetPoints' $frame.id;Agregar 'cFrameObj' 'GetSection' $frame.id }
foreach ($wall in $config.asignaciones_muros) { Agregar 'cAreaObj' 'GetPoints' $wall.objetivo;Agregar 'cAreaObj' 'GetProperty' $wall.objetivo }
foreach ($point in $config.puntos) { Agregar 'cPointObj' 'GetRestraint' $point.id;Agregar 'cPointObj' 'GetDiaphragm' $point.id }
foreach ($load in $config.cargas) {
 switch ($load.objetivo_tipo) {
  'punto' { Agregar 'cPointObj' 'GetLoadForce' $load.objetivo }
  'frame' { Agregar 'cFrameObj' 'GetLoadDistributed' $load.objetivo }
  'muro' { Agregar 'cAreaObj' 'GetLoadUniform' $load.objetivo }
  default { throw 'Tipo de carga no soportado; no omitir cargas.' }
 }
}
foreach ($pattern in $config.patrones) { Agregar 'cLoadPatterns' 'GetLoadType' $pattern.id;Agregar 'cLoadPatterns' 'GetSelfWTMultiplier' $pattern.id }
foreach ($case in $config.casos) {
 switch ($case.tipo) {
  'estatico_lineal' { Agregar 'cCaseStaticLinear' 'GetLoads' $case.id }
  'modal_eigen' {
   foreach ($method in @('GetNumberModes','GetParameters','GetLoads')) { Agregar 'cCaseModalEigen' $method $case.id }
  }
  'espectro_respuesta' {
   foreach ($method in @('GetModalCase','GetLoads','GetEccentricity','GetDampConstant','GetDampType','GetDampOverrides','GetModalComb_1')) { Agregar 'cCaseResponseSpectrum' $method $case.id }
  }
  default { throw 'Tipo de caso no soportado; no omitir casos.' }
 }
}
foreach ($function in $config.espectros) { Agregar 'cFunction' 'GetValues' $function.id }
foreach ($combo in $config.combinaciones) { Agregar 'cCombo' 'GetCaseList' $combo.id;Agregar 'cCombo' 'GetTypeCombo' $combo.id }
foreach ($dia in $config.diafragmas) { Agregar 'cDiaphragm' 'GetDiaphragm' $dia.id }
$rows=@()
foreach ($query in $queries) {
 $type=[type]('ETABSv1.'+$query.interfaz);$method=$type.GetMethod($query.metodo);$parameters=$method.GetParameters()
 [object[]]$argsMethod=[object[]]::new($parameters.Length)
 for ($i=0;$i -lt $parameters.Length;$i++) {
  $p=$parameters[$i];$t=$p.ParameterType
  if ($p.Name -eq 'Name') { $argsMethod[$i]=[string]$query.nombre }
  elseif ($t.IsByRef) {
   $element=$t.GetElementType()
   if ($element.IsArray) { $argsMethod[$i]=[Array]::CreateInstance($element.GetElementType(),0) }
   elseif ($element -eq [string]) { $argsMethod[$i]='' }
   else { $argsMethod[$i]=[Activator]::CreateInstance($element) }
  } elseif ($p.IsOptional) { $argsMethod[$i]=$p.DefaultValue }
  else { throw ('Parametro no soportado '+$query.metodo+'.'+$p.Name) }
 }
 $member=switch ($query.interfaz) {
  'cCaseStaticLinear' { $sap.LoadCases.StaticLinear }
  'cCaseModalEigen' { $sap.LoadCases.ModalEigen }
  'cCaseResponseSpectrum' { $sap.LoadCases.ResponseSpectrum }
  'cFunction' { $sap.Func }
  'cCombo' { $sap.RespCombo }
  default { $sap.($query.interfaz.Substring(1)) }
 }
 $code=$method.Invoke($member,$argsMethod)
 if ($code -ne 0) { throw ('Getter fallo '+$query.interfaz+'.'+$query.metodo+' codigo='+$code) }
 $values=[ordered]@{}
 for ($i=0;$i -lt $parameters.Length;$i++) { $values[$parameters[$i].Name]=$argsMethod[$i] }
 $rows+=@{interfaz=$query.interfaz;metodo=$query.metodo;nombre=$query.nombre;retorno=$code;valores=$values}
}
$tables=@()
$tableNames=@()
if (@($config.espectros).Count) { $tableNames+='Functions - Response Spectrum - User Defined' }
if (@($config.casos | Where-Object tipo -eq 'espectro_respuesta').Count) {
 $tableNames+=@('Load Case Definitions - Response Spectrum','Load Case Definitions - Damping - Modal')
}
foreach ($tableName in $tableNames) {
 [int]$version=0;[string[]]$fields=@();[int]$count=0;[string[]]$values=@()
 $code=$sap.DatabaseTables.GetTableForEditingArray($tableName,'',[ref]$version,[ref]$fields,[ref]$count,[ref]$values)
 if ($code -ne 0 -or $values.Length -ne $fields.Length*$count) { throw "Lectura incompleta de tabla $tableName" }
 $tableRows=@()
 for ($i=0;$i -lt $count;$i++) {
  $row=[ordered]@{}
  for ($j=0;$j -lt $fields.Length;$j++) { $row[$fields[$j]]=$values[$i*$fields.Length+$j] }
  $tableRows+=$row
 }
 $tables+=@{tabla=$tableName;version=$version;campos=$fields;filas=$tableRows}
}
$data=@{solo_lectura=$true;modelo=$opened;proceso=$IdProceso;unidades='kN_m_C';lecturas=$rows;tablas=$tables;fecha_utc=[DateTime]::UtcNow.ToString('o')}
$raw=(New-Object Text.UTF8Encoding($false)).GetBytes(($data | ConvertTo-Json -Depth 15))
$stream=[IO.File]::Open($Registro,[IO.FileMode]::CreateNew,[IO.FileAccess]::Write)
try { $stream.Write($raw,0,$raw.Length) } finally { $stream.Dispose() }
Write-Output ('Lecturas completadas: '+$rows.Count)
