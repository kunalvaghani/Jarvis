param([switch]$SkipMCP)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
Write-Host 'Installing Jarvis Blender MCP child connector'
if (-not (Test-Path '.venv-blender\Scripts\python.exe')) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        & py -3.12 -m venv .venv-blender
        if ($LASTEXITCODE -ne 0) { & py -3 -m venv .venv-blender }
    }
    elseif (Get-Command python -ErrorAction SilentlyContinue) { & python -m venv .venv-blender }
    else { throw 'Install Python 3.12+ first' }
    if ($LASTEXITCODE -ne 0) { throw 'Python virtual environment setup failed. Install Python 3.12+.' }
}
$python = Join-Path $PSScriptRoot '.venv-blender\Scripts\python.exe'
if (-not $SkipMCP) {
    & $python -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) { throw 'pip upgrade failed' }
    & $python -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'MCP SDK install failed' }
}
& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Unit tests failed; connector not ready' }
if (-not $SkipMCP) {
    & $python client_smoke.py
    if ($LASTEXITCODE -ne 0) { throw 'MCP protocol discovery failed' }
}
Write-Host 'Install and unit/MCP checks succeeded. Next run launch_blender.ps1 with explicit -AllowedRoots.'
