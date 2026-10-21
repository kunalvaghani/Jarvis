param([Parameter(Mandatory=$true)][string]$BlenderExe,[Parameter(Mandatory=$true)][string]$ReportPath)
$ErrorActionPreference='Stop'
if (-not (Test-Path -LiteralPath $BlenderExe -PathType Leaf)) { throw 'Blender executable missing' }
$env:JARVIS_BLENDER_LIVE_REPORT=[IO.Path]::GetFullPath($ReportPath)
& $BlenderExe --background --factory-startup --disable-autoexec --python (Join-Path $PSScriptRoot 'run_live_tests.py')
if ($LASTEXITCODE -ne 0) { throw "Blender process failed: $LASTEXITCODE" }
$report=Get-Content -LiteralPath $env:JARVIS_BLENDER_LIVE_REPORT -Raw | ConvertFrom-Json
if ($report.failed -gt 0) { throw "Live smoke failed: $($report.failed)" }
Write-Output "Verified live smoke: $($report.passed) actions plus $($report.effects.PSObject.Properties.Count) effect checks. Full catalog acceptance is separate."
