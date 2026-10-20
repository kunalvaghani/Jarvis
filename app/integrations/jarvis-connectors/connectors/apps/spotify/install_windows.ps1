# Explicitly invoked optional dependency setup; never login, start Spotify or change playback.
param([string]$Python='')
$ErrorActionPreference = 'Stop'
$taskAppRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../../../..'))
if (-not $Python) { $Python = Join-Path $taskAppRoot '.venv/Scripts/python.exe' }
if (-not (Test-Path -LiteralPath $Python -PathType Leaf)) { throw 'Supply an existing compatible Python executable.' }
& $Python -m pip install -r (Join-Path $taskAppRoot 'requirements/spotify.txt')
if ($LASTEXITCODE -ne 0) { throw 'Optional Spotify dependencies did not install.' }
& $Python (Join-Path $PSScriptRoot 'client_smoke.py')
if ($LASTEXITCODE -ne 0) { throw 'Spotify MCP smoke failed.' }
Write-Output 'Dependencies checked. Register via scripts/setup/register_spotify_connector.py; OAuth remains human-only.'
