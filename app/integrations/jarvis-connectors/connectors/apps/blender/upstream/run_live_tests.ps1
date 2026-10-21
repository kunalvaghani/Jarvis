param([Parameter(Mandatory=$true)][string]$BlenderExe)
$ErrorActionPreference='Stop'
if (-not (Test-Path -LiteralPath $BlenderExe -PathType Leaf)) { throw 'Blender.exe not found' }
Set-Location $PSScriptRoot
& $BlenderExe --background --factory-startup --python (Join-Path $PSScriptRoot 'tests\run_inside_blender.py')
$exitCode=$LASTEXITCODE
if ($exitCode -ne 0) { throw "Blender live tests failed, Blender exit code $exitCode. Inspect blender_live_test_results.json" }
$report = Get-Content -Raw -LiteralPath 'blender_live_test_results.json' | ConvertFrom-Json
if ($report.failed -gt 0) { throw "Live tests failed ($($report.failed) failing checks). Inspect blender_live_test_results.json" }
Write-Host "PASS: Blender live tests $($report.passed)/$($report.checks.Count) actions + $($report.effects.PSObject.Properties.Count) effects"
