param([switch]$Cuda)
$ErrorActionPreference = 'Stop'
$base = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
Set-Location -LiteralPath $base
& '.venv/Scripts/python.exe' -m venv '.venv-f5'
if ($LASTEXITCODE) { throw 'F5 environment creation failed' }
& '.venv-f5/Scripts/python.exe' -m pip install -r requirements/f5.txt
if ($LASTEXITCODE) { throw 'F5 dependency installation failed' }
if ($Cuda) {
    & '.venv-f5/Scripts/python.exe' -m pip install 'torch==2.6.0+cu124' 'torchaudio==2.6.0+cu124' --index-url https://download.pytorch.org/whl/cu124
    if ($LASTEXITCODE) { throw 'F5 CUDA installation failed' }
}
& '.venv-f5/Scripts/python.exe' -c 'from f5_tts.api import F5TTS; import sounddevice, soundfile'
if ($LASTEXITCODE) { throw 'F5 import check failed' }
Write-Output 'F5 dependencies ready. Configure speech.f5.reference_audio and reference_text, then select engine f5. First synthesis downloads the model.'
