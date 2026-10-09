$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent)
$jarvisStartApps = @(Get-StartApps | Select-Object Name,AppID)
$jarvisShell = New-Object -ComObject WScript.Shell
$jarvisShortcutRoots = @(
    [Environment]::GetFolderPath('StartMenu'),
    [Environment]::GetFolderPath('CommonStartMenu'),
    [Environment]::GetFolderPath('Desktop'),
    [Environment]::GetFolderPath('CommonDesktopDirectory')
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique
$jarvisShortcuts = @(foreach ($jarvisRoot in $jarvisShortcutRoots) {
    foreach ($jarvisLink in (Get-ChildItem -LiteralPath $jarvisRoot -Filter '*.lnk' -Recurse -File -ErrorAction SilentlyContinue)) {
        try {
            $jarvisShortcut = $jarvisShell.CreateShortcut($jarvisLink.FullName)
            [pscustomobject]@{name=$jarvisLink.BaseName; shortcut=$jarvisLink.FullName; target=$jarvisShortcut.TargetPath}
        } catch { }
    }
})
$jarvisAppPaths = @(foreach ($jarvisRegistryRoot in @(
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\App Paths',
    'HKLM:\Software\Microsoft\Windows\CurrentVersion\App Paths',
    'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths'
)) {
    foreach ($jarvisKey in (Get-ChildItem -LiteralPath $jarvisRegistryRoot -ErrorAction SilentlyContinue)) {
        $jarvisExe = $jarvisKey.GetValue('')
        if ($jarvisExe -is [string] -and $jarvisExe) {
            [pscustomobject]@{name=$jarvisKey.PSChildName; target=$jarvisExe.Trim('"')}
        }
    }
})
$jarvisDrives = @([System.IO.DriveInfo]::GetDrives() | Where-Object { $_.IsReady -and $_.DriveType -eq 'Fixed' } | ForEach-Object { $_.RootDirectory.FullName })
New-Item -ItemType Directory -Path '.jarvis-runtime/state' -Force | Out-Null
[pscustomobject]@{apps=$jarvisStartApps; shortcuts=$jarvisShortcuts; app_paths=$jarvisAppPaths; roots=$jarvisDrives} |
    ConvertTo-Json -Depth 6 | Set-Content -LiteralPath '.jarvis-runtime/state/installed_apps.scan.json' -Encoding utf8
& '.\.venv\Scripts\python.exe' -m scripts.catalog.scan_pc
if ($LASTEXITCODE -ne 0) { throw 'PC catalog scan failed.' }
