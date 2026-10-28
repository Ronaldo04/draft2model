# 309: segundo motor de render ya instalado (Windows.Data.Pdf, WinRT). Solo lectura del PDF; escribe PNG en la carpeta de diagnóstico.
param([string]$Pdf, [string]$OutDir, [string]$PagesCsv = "7,8", [double]$Scale = 1.3333, [switch]$Secuencial)
$ErrorActionPreference = 'Stop'
$Pages = [int[]]($PagesCsv -split ",")
Add-Type -AssemblyName System.Runtime.WindowsRuntime
$null = [Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime]
$null = [Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime]
$null = [Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime]
$asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' }
function Await($op, [Type]$t) { $m = $asTask.MakeGenericMethod($t); $task = $m.Invoke($null, @($op)); $task.Wait(); $task.Result }
$asTaskA = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncAction' }
function AwaitA($op) { $task = $asTaskA[0].Invoke($null, @($op)); $task.Wait() }
$file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync((Resolve-Path $Pdf).Path)) ([Windows.Storage.StorageFile])
$doc = Await ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($file)) ([Windows.Data.Pdf.PdfDocument])
$lista = if ($Secuencial) { 1..$doc.PageCount } else { $Pages }
foreach ($p in $lista) {
  $page = $doc.GetPage($p - 1)
  $opt = New-Object Windows.Data.Pdf.PdfPageRenderOptions
  $opt.DestinationWidth = [uint32]([math]::Round($page.Size.Width * $Scale))
  $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
  AwaitA ($page.RenderToStreamAsync($stream, $opt))
  if ($Pages -contains $p) {
    $net = [System.IO.WindowsRuntimeStreamExtensions]::AsStreamForRead($stream.GetInputStreamAt(0))
    $tag = if ($Secuencial) { 'secuencial' } else { 'aislado' }
    $out = Join-Path $OutDir ("windows_{0}_p{1}.png" -f $tag, $p)
    $fs = [System.IO.File]::Create($out); $net.CopyTo($fs); $fs.Close()
    Write-Output ("{0} {1}x{2}" -f $out, $opt.DestinationWidth, $page.Size.Height)
  }
  $page.Dispose()
}
