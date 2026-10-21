param(
  [Parameter(Mandatory=$true)][string]$BlenderExe,
  [Parameter(Mandatory=$true)][string[]]$AllowedRoots,
  [string]$ProjectPath = '',
  [int]$Port = 8769
)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $BlenderExe -PathType Leaf)) { throw 'Blender.exe not found at provided path.' }
$resolved = @()
foreach($path in $AllowedRoots) {
  if (-not (Test-Path -LiteralPath $path -PathType Container)) { throw "Allowed directory does not exist: $path" }
  $resolved += (Resolve-Path -LiteralPath $path).Path
}
$env:JARVIS_BLENDER_ALLOWED_ROOTS = ($resolved -join ';')
$env:JARVIS_BLENDER_PORT = [string]$Port
$args = @()
if ($ProjectPath) {
    if (-not (Test-Path -LiteralPath $ProjectPath -PathType Leaf)) { throw 'Project file does not exist.' }
    $args += (Resolve-Path -LiteralPath $ProjectPath).Path
}
$args += @('--python', (Join-Path $PSScriptRoot 'start_blender_bridge.py'))
Write-Host "Starting Blender bridge on 127.0.0.1:$Port"
& $BlenderExe @args
