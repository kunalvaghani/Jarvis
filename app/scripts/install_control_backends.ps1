# Install the pinned PC/web control backends (agent-desktop, agent-browser) into a git-ignored folder.
# Approved by the user 2026-11-02. Re-check versions before bumping: docs/control/UPGRADING.md.
# Checksums are GitHub's published release digests; a mismatch stops the install and leaves nothing behind.
$ErrorActionPreference = 'Stop'
$Root = Join-Path $PSScriptRoot '..\.jarvis-runtime\tools\control-backends'
$Pins = @(
    @{ Name = 'agent-desktop-v1.0.2-x86_64-pc-windows-msvc.tar.gz'
       Url = 'https://github.com/vercel-labs/agent-desktop/releases/download/v1.0.2/agent-desktop-v1.0.2-x86_64-pc-windows-msvc.tar.gz'
       Sha256 = '2186c76e7df197c0e67365e45d36d869f74714c56bb8a73817e2a66f3e18e222'; Dir = 'agent-desktop-1.0.2' },
    @{ Name = 'agent-desktop-ffi-v1.0.2-x86_64-pc-windows-msvc.zip'
       Url = 'https://github.com/vercel-labs/agent-desktop/releases/download/v1.0.2/agent-desktop-ffi-v1.0.2-x86_64-pc-windows-msvc.zip'
       Sha256 = 'baf08bdca22cced212f258455cad9835b06678a3e1969a3b21cb501c377d35dc'; Dir = 'agent-desktop-ffi-1.0.2' },
    @{ Name = 'agent-browser-win32-x64.exe'
       Url = 'https://github.com/vercel-labs/agent-browser/releases/download/v0.41.1/agent-browser-win32-x64.exe'
       Sha256 = 'ddab45e8bae84e5bc6aa1b084bceca9b579aff2e8272474d7d26953cf10965ee'; Dir = 'agent-browser-0.41.1' }
)
New-Item -ItemType Directory -Force $Root | Out-Null
foreach ($p in $Pins) {
    $target = Join-Path $Root $p.Dir
    $file = Join-Path $Root $p.Name
    if (-not (Test-Path $file)) { Invoke-WebRequest -Uri $p.Url -OutFile $file -UseBasicParsing }
    $hash = (Get-FileHash $file -Algorithm SHA256).Hash.ToLower()
    if ($hash -ne $p.Sha256) { Remove-Item $file -Force; throw "Checksum mismatch for $($p.Name): $hash" }
    New-Item -ItemType Directory -Force $target | Out-Null
    if ($p.Name.EndsWith('.tar.gz')) { tar -xzf $file -C $target }
    elseif ($p.Name.EndsWith('.zip')) { Expand-Archive -Path $file -DestinationPath $target -Force }
    else { Copy-Item $file (Join-Path $target 'agent-browser.exe') -Force }
    "{0}  {1}" -f $hash, $p.Name
}
