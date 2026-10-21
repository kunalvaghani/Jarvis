param(
  [Parameter(Mandatory=$true)][string]$BlenderExe,
  [Parameter(Mandatory=$true)][string[]]$AllowedRoots,
  [string]$ProjectPath = '',
  [int]$Port = 8769,
  [Parameter(Mandatory=$true)][string]$BridgeConfig
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
$env:JARVIS_BLENDER_CONFIG = [IO.Path]::GetFullPath($BridgeConfig)
if (Test-Path -LiteralPath $env:JARVIS_BLENDER_CONFIG) { throw 'Scope file already exists. Attach explicitly or stop that instance first; never overwrite another scope.' }
$blenderArgs = @('--disable-autoexec')
if ($ProjectPath) {
    if (-not (Test-Path -LiteralPath $ProjectPath -PathType Leaf)) { throw 'Project file does not exist.' }
    $project = (Resolve-Path -LiteralPath $ProjectPath).Path
    if ([IO.Path]::GetExtension($project) -ne '.blend') { throw 'Project must be a .blend file.' }
    $blenderArgs += $project
}
$blenderArgs += @('--python', (Join-Path $PSScriptRoot 'start_blender_bridge.py'))
Write-Host "Starting Blender bridge on 127.0.0.1:$Port"
Start-Process -FilePath $BlenderExe -ArgumentList ($blenderArgs | ForEach-Object { '"' + $_ + '"' }) -WindowStyle Hidden
