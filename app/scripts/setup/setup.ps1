$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.10 or newer is required.' }
}
& '.\.venv\Scripts\python.exe' -m pip --isolated install --upgrade pip --timeout 60 --retries 3 --index-url https://pypi.org/simple
if ($LASTEXITCODE -ne 0) { throw 'Could not update pip for resumable GPU-library downloads.' }
& '.\.venv\Scripts\python.exe' -m pip --isolated install --timeout 60 --retries 3 --resume-retries 8 --index-url https://pypi.org/simple -r requirements/runtime.txt
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
& '.\.venv\Scripts\python.exe' -m scripts.models.download_model --parallel 8
if ($LASTEXITCODE -ne 0) { throw 'Speech model download failed.' }
& '.\.venv\Scripts\python.exe' -m piper.download_voices --download-dir models/voices en_GB-alan-medium hi_IN-rohan-medium
if ($LASTEXITCODE -ne 0) { throw 'Voice download failed.' }
& '.\.venv\Scripts\python.exe' -m scripts.setup.setup_voice
if ($LASTEXITCODE -ne 0) { throw 'Free Kokoro voice download failed.' }
& '.\.venv\Scripts\python.exe' -m scripts.verification.verify_whisper --audio tests\fixtures\jarvis-command.wav
if ($LASTEXITCODE -ne 0) { throw 'Whisper GPU verification failed. See the error above.' }
Write-Host 'Ready. Double-click Start Jarvis.cmd.'
