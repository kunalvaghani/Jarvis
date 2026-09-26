$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$preferred = 'qwen3.5:4b'
$ollamaExecutable = (Get-Command ollama.exe -ErrorAction Stop).Source
foreach ($variable in 'HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','GIT_HTTP_PROXY','GIT_HTTPS_PROXY') {
    Remove-Item -Path "Env:$variable" -ErrorAction SilentlyContinue
}
$env:OLLAMA_HOST = '127.0.0.1:11435'
$temporaryServer = Start-Process -FilePath $ollamaExecutable -ArgumentList 'serve' -PassThru -WindowStyle Hidden
try {
    $ready = $false
    for ($attempt = 0; $attempt -lt 30; $attempt++) {
        try {
            Invoke-RestMethod -Uri 'http://127.0.0.1:11435/api/tags' -TimeoutSec 2 | Out-Null
            $ready = $true
            break
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    if (-not $ready) { throw 'The temporary Ollama download server did not start.' }
    & $ollamaExecutable pull $preferred
    if ($LASTEXITCODE -ne 0) { throw 'Download interrupted. Run Upgrade Jarvis Model.cmd again to resume.' }
} finally {
    Stop-Process -Id $temporaryServer.Id -ErrorAction SilentlyContinue
}
$env:OLLAMA_HOST = '127.0.0.1:11434'
& '.\.venv\Scripts\python.exe' verify_scenarios.py $preferred
if ($LASTEXITCODE -ne 0) { throw 'The candidate model did not pass the scenario checks; current Jarvis model remains active.' }
& '.\.venv\Scripts\python.exe' activate_model.py $preferred
if ($LASTEXITCODE -ne 0) { throw 'The model passed but could not be activated.' }
