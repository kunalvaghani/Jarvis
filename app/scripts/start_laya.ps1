# Start Laya (local decision model, GPU) for Jarvis's agent-desktop backend. Loopback only, key from secrets.
# Installed in its own environment: py -3.11 -m venv .venv-laya; torch 2.6.0 cu124; pip install "laya[serve]==0.4.21".
$ErrorActionPreference = 'Stop'
$App = Join-Path $PSScriptRoot '..'
$env:LAYA_HOST = '127.0.0.1'
$env:LAYA_PORT = '8765'
$env:LAYA_DEVICE = 'cpu'             # On the GPU it pushed the 9B planner 82% onto the CPU (measured 2026-11-03)
$env:LAYA_THREADS = '4'
$env:LAYA_PRELOAD = '1'
$env:LAYA_MODELS = 'english'
$env:LAYA_DEFAULT_MODEL = 'english'
$env:LAYA_MAX_LOADED = '1'
$env:LAYA_TOURNAMENT_GROUP = '16'
$env:USE_TF = '0'
$env:LAYA_API_KEY = (Get-Content (Join-Path $App 'secrets\laya.key') -Raw).Trim()
& (Join-Path $App '.venv-laya\Scripts\laya-serve.exe')
