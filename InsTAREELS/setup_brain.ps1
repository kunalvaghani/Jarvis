$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath '.venv-brain\Scripts\python.exe')) {
    & '.\.venv\Scripts\python.exe' -m venv .venv-brain
    if ($LASTEXITCODE -ne 0) { throw 'Could not create isolated brain environment.' }
}
& '.\.venv-brain\Scripts\python.exe' -m pip --isolated install --upgrade pip --index-url https://pypi.org/simple --timeout 30 --retries 2
if ($LASTEXITCODE -ne 0) { throw 'Could not update pip for resumable downloads.' }
& '.\.venv-brain\Scripts\python.exe' -m pip --isolated install 'torch==2.6.0' --index-url https://download.pytorch.org/whl/cpu --timeout 60 --retries 2 --resume-retries 5
if ($LASTEXITCODE -ne 0) { throw 'CPU runtime download interrupted. Rerun this setup to resume.' }
& '.\.venv-brain\Scripts\python.exe' -m pip --isolated install -r requirements-brain.txt --index-url https://pypi.org/simple --timeout 60 --retries 2 --resume-retries 5
if ($LASTEXITCODE -ne 0) { throw 'Brain dependencies could not be installed.' }
& '.\.venv\Scripts\python.exe' -c 'from jarvis.knowledge_worker import ensure_server, session; ensure_server(session())'
if ($LASTEXITCODE -ne 0) { throw 'Start Ollama and rerun setup.' }
& '.\.venv-brain\Scripts\python.exe' setup_brain.py
if ($LASTEXITCODE -ne 0) { throw 'Model download interrupted. Rerun this setup to resume.' }
& '.\.venv\Scripts\python.exe' verify_brain.py
if ($LASTEXITCODE -ne 0) { throw 'Models downloaded, but verification failed. See the message above.' }
Write-Host 'Models ready. Restart Jarvis and say: task followed by your goal.'
