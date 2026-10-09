# Jarvis — Windows 11 PC Automation Command Reference

**Environment:** Windows 11; PowerShell 5.1 or newer; optional Python 3.11+ and relevant applications installed. **Commands are examples, not proprietary VoiceOS code.**

## How to run the examples

- **PS** means copy and paste into **Windows PowerShell**. These commands cannot be run directly on Linux/macOS.
- **PY** means run in Python **after** the import block below. Code such as `pg.hotkey(...)` or `pg.click(...)` simulates input into the **focused window**. Do **not** paste Python into PowerShell without first invoking Python.
- **WEB** means a **Python Playwright statement**, after creating a `page` object in a browser you control. It does **not** automatically attach to existing Chrome tabs.
- `C:\Work\...`, coordinates, `PID`, app names and labels are **examples**: adapt them to real files/windows. Some items require installed apps, desktop sessions, permissions, or default keybindings. Some GUI shortcuts are context-sensitive.
- **Sensitive actions** (delete, close, kill, shutdown, overwrite, save, send or externally share) should have approvals, scope validation, logging and error handling. Do not allow an LLM to generate unrestricted shell commands.
- Mouse clicks use the active screen coordinate system, and GUI automation may fail with UAC prompts, lock screens, games with direct-input capture, admin-only interfaces or custom canvases. Prefer **UI Automation** (native desktops) or **Playwright locators** (webpages) whenever possible.
- Screenshot-based finding needs a reference image and appropriate resolution; `confidence` requires `opencv-python`.

### Python setup (run in PowerShell)

```powershell
python -m pip install pyautogui pywinauto pyperclip psutil pillow playwright pypdf
python -m playwright install chromium
# Optional for confidence matching:
python -m pip install opencv-python
```

### Python shared imports (interactive Python or a `.py` file)

```python
import pyautogui as pg
from pywinauto import Desktop, Application
import time
pg.FAILSAFE = True   # Move mouse to screen corner to abort PyAutoGUI
pg.PAUSE = 0.10
```

### Browser page setup, for WEB rows

```python
from playwright.sync_api import sync_playwright
p = sync_playwright().start()
browser = p.chromium.launch(headless=False)
page = browser.new_page()
page.goto('https://example.org')
# Now use the WEB commands. When finished:
# browser.close(); p.stop()
```

### Target a specific desktop window, for `w` rows

```python
w = Desktop(backend='uia').window(title_re='.*Notepad.*')
w.wait('visible', timeout=10)
w.print_control_identifiers()  # inspect real labels and control types
```

## Complete command index

## 01 Launch Windows built-ins (36 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 1 | Camera | PS | <code>Start-Process 'microsoft.windows.camera:'</code> | URI depends on Camera installation |
| 2 | Notepad | PS | <code>Start-Process 'notepad.exe'</code> |  |
| 3 | Calculator | PS | <code>Start-Process 'calc.exe'</code> |  |
| 4 | File Explorer | PS | <code>Start-Process 'explorer.exe'</code> |  |
| 5 | Paint | PS | <code>Start-Process 'mspaint.exe'</code> |  |
| 6 | Snipping Tool | PS | <code>Start-Process 'snippingtool.exe'</code> |  |
| 7 | Task Manager | PS | <code>Start-Process 'taskmgr.exe'</code> |  |
| 8 | Command Prompt | PS | <code>Start-Process 'cmd.exe'</code> |  |
| 9 | Windows PowerShell | PS | <code>Start-Process 'powershell.exe'</code> |  |
| 10 | Windows Terminal | PS | <code>Start-Process 'wt.exe'</code> | Requires Windows Terminal |
| 11 | Control Panel | PS | <code>Start-Process 'control.exe'</code> |  |
| 12 | Device Manager | PS | <code>Start-Process 'devmgmt.msc'</code> |  |
| 13 | Disk Management | PS | <code>Start-Process 'diskmgmt.msc'</code> |  |
| 14 | Services console | PS | <code>Start-Process 'services.msc'</code> |  |
| 15 | Event Viewer | PS | <code>Start-Process 'eventvwr.msc'</code> |  |
| 16 | Resource Monitor | PS | <code>Start-Process 'resmon.exe'</code> |  |
| 17 | Performance Monitor | PS | <code>Start-Process 'perfmon.msc'</code> |  |
| 18 | Registry Editor | PS | <code>Start-Process 'regedit.exe'</code> | Sensitive system tool |
| 19 | System Information | PS | <code>Start-Process 'msinfo32.exe'</code> |  |
| 20 | DirectX Diagnostics | PS | <code>Start-Process 'dxdiag.exe'</code> |  |
| 21 | Windows version dialog | PS | <code>Start-Process 'winver.exe'</code> |  |
| 22 | On-Screen Keyboard | PS | <code>Start-Process 'osk.exe'</code> |  |
| 23 | Magnifier | PS | <code>Start-Process 'magnify.exe'</code> |  |
| 24 | Character Map | PS | <code>Start-Process 'charmap.exe'</code> |  |
| 25 | Windows Media Player (legacy) | PS | <code>Start-Process 'wmplayer.exe'</code> | Optional Windows feature; may not exist |
| 26 | Remote Desktop | PS | <code>Start-Process 'mstsc.exe'</code> |  |
| 27 | Computer Management | PS | <code>Start-Process 'compmgmt.msc'</code> |  |
| 28 | Task Scheduler | PS | <code>Start-Process 'taskschd.msc'</code> |  |
| 29 | System Configuration | PS | <code>Start-Process 'msconfig.exe'</code> |  |
| 30 | Disk Cleanup | PS | <code>Start-Process 'cleanmgr.exe'</code> |  |
| 31 | Sound panel | PS | <code>Start-Process 'mmsys.cpl'</code> |  |
| 32 | Mouse properties | PS | <code>Start-Process 'main.cpl'</code> |  |
| 33 | Programs and Features | PS | <code>Start-Process 'appwiz.cpl'</code> |  |
| 34 | Firewall Control Panel | PS | <code>Start-Process 'firewall.cpl'</code> |  |
| 35 | Internet Options | PS | <code>Start-Process 'inetcpl.cpl'</code> |  |
| 36 | Credential Manager | PS | <code>Start-Process 'control.exe' -ArgumentList '/name Microsoft.CredentialManager'</code> | Protected credentials; do not extract secrets |

## 02 Windows Settings (28 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 37 | All Settings | PS | <code>Start-Process 'ms-settings:'</code> |  |
| 38 | Display | PS | <code>Start-Process 'ms-settings:display'</code> |  |
| 39 | Sound | PS | <code>Start-Process 'ms-settings:sound'</code> |  |
| 40 | Bluetooth and devices | PS | <code>Start-Process 'ms-settings:bluetooth'</code> |  |
| 41 | Wi-Fi | PS | <code>Start-Process 'ms-settings:network-wifi'</code> |  |
| 42 | Ethernet | PS | <code>Start-Process 'ms-settings:network-ethernet'</code> |  |
| 43 | VPN | PS | <code>Start-Process 'ms-settings:network-vpn'</code> |  |
| 44 | Data usage | PS | <code>Start-Process 'ms-settings:datausage'</code> |  |
| 45 | Windows Update | PS | <code>Start-Process 'ms-settings:windowsupdate'</code> |  |
| 46 | Power and battery | PS | <code>Start-Process 'ms-settings:powersleep'</code> |  |
| 47 | Storage | PS | <code>Start-Process 'ms-settings:storagesense'</code> |  |
| 48 | Default apps | PS | <code>Start-Process 'ms-settings:defaultapps'</code> |  |
| 49 | Installed apps | PS | <code>Start-Process 'ms-settings:appsfeatures'</code> |  |
| 50 | Startup apps | PS | <code>Start-Process 'ms-settings:startupapps'</code> |  |
| 51 | Notifications | PS | <code>Start-Process 'ms-settings:notifications'</code> |  |
| 52 | Focus settings | PS | <code>Start-Process 'ms-settings:quiethours'</code> |  |
| 53 | Taskbar settings | PS | <code>Start-Process 'ms-settings:taskbar'</code> |  |
| 54 | Personalization | PS | <code>Start-Process 'ms-settings:personalization'</code> |  |
| 55 | Themes | PS | <code>Start-Process 'ms-settings:themes'</code> |  |
| 56 | Lock screen | PS | <code>Start-Process 'ms-settings:lockscreen'</code> |  |
| 57 | Background | PS | <code>Start-Process 'ms-settings:personalization-background'</code> |  |
| 58 | Date and time | PS | <code>Start-Process 'ms-settings:dateandtime'</code> |  |
| 59 | Language | PS | <code>Start-Process 'ms-settings:regionlanguage'</code> |  |
| 60 | Accessibility | PS | <code>Start-Process 'ms-settings:easeofaccess'</code> |  |
| 61 | Camera permissions | PS | <code>Start-Process 'ms-settings:privacy-webcam'</code> |  |
| 62 | Microphone permissions | PS | <code>Start-Process 'ms-settings:privacy-microphone'</code> |  |
| 63 | Location permissions | PS | <code>Start-Process 'ms-settings:privacy-location'</code> |  |
| 64 | Privacy diagnostics | PS | <code>Start-Process 'ms-settings:privacy-feedback'</code> |  |

## 03 Third-party apps and web (30 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 65 | Microsoft Edge | PS | <code>Start-Process 'msedge.exe'</code> | Installed standard app |
| 66 | Google Chrome | PS | <code>Start-Process 'chrome.exe'</code> | Executable must be registered/on PATH |
| 67 | Firefox | PS | <code>Start-Process 'firefox.exe'</code> | Installed and discoverable |
| 68 | Brave | PS | <code>Start-Process 'brave.exe'</code> | Installed and discoverable |
| 69 | Opera | PS | <code>Start-Process 'opera.exe'</code> | Installed and discoverable |
| 70 | Visual Studio Code | PS | <code>Start-Process 'code'</code> | Install code CLI or add to PATH |
| 71 | Visual Studio | PS | <code>Start-Process 'devenv.exe'</code> | Installed and discoverable |
| 72 | Git Bash | PS | <code>Start-Process 'git-bash.exe'</code> | Installed and discoverable |
| 73 | Git GUI | PS | <code>Start-Process 'git-gui.exe'</code> | Installed and discoverable |
| 74 | Python interpreter | PS | <code>Start-Process 'python.exe'</code> | Installed and discoverable |
| 75 | Windows Store | PS | <code>Start-Process 'ms-windows-store:'</code> | URI registration required |
| 76 | Spotify | PS | <code>Start-Process 'spotify:'</code> | Spotify URI handler required |
| 77 | Steam | PS | <code>Start-Process 'steam://open/main'</code> | Steam protocol handler required |
| 78 | Discord | PS | <code>Get-StartApps &#124; Where-Object Name -like '*Discord*'</code> | Discover installed ID; not a launch command |
| 79 | Unreal Engine | PS | <code>Get-StartApps &#124; Where-Object Name -like '*Unreal*'</code> | Discover launch app ID; installation-specific |
| 80 | Unity Hub | PS | <code>Get-StartApps &#124; Where-Object Name -like '*Unity Hub*'</code> | Discover app ID |
| 81 | Epic Games Launcher | PS | <code>Get-StartApps &#124; Where-Object Name -like '*Epic Games*'</code> | Discover app ID |
| 82 | PDFGear | PS | <code>Get-StartApps &#124; Where-Object Name -like '*PDFgear*'</code> | Discover app ID |
| 83 | Obsidian | PS | <code>Get-StartApps &#124; Where-Object Name -like '*Obsidian*'</code> | Discover app ID |
| 84 | Office apps | PS | <code>Get-StartApps &#124; Where-Object Name -match 'Word&#124;Excel&#124;PowerPoint'</code> | Discover app IDs |
| 85 | Installed Start apps | PS | <code>Get-StartApps &#124; Sort-Object Name</code> |  |
| 86 | Run app by AppUserModelID | PS | <code>Start-Process explorer.exe -ArgumentList 'shell:AppsFolder\PUT_APPUSERMODELID_HERE'</code> | Replace placeholder using Get-StartApps |
| 87 | Open Google | PS | <code>Start-Process 'https://www.google.com'</code> |  |
| 88 | Open YouTube | PS | <code>Start-Process 'https://www.youtube.com'</code> |  |
| 89 | Open Gmail | PS | <code>Start-Process 'https://mail.google.com'</code> |  |
| 90 | Open GitHub | PS | <code>Start-Process 'https://github.com'</code> |  |
| 91 | Open Google Drive | PS | <code>Start-Process 'https://drive.google.com'</code> |  |
| 92 | Open ChatGPT | PS | <code>Start-Process 'https://chatgpt.com'</code> |  |
| 93 | Open a file with default app | PS | <code>Invoke-Item 'C:\Work\notes.txt'</code> | File must exist |
| 94 | Open a folder | PS | <code>Invoke-Item 'C:\Work'</code> | Folder must exist |

## 04 Processes, windows and jobs (28 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 95 | All processes | PS | <code>Get-Process</code> |  |
| 96 | Find Chrome process | PS | <code>Get-Process -Name chrome -ErrorAction SilentlyContinue</code> |  |
| 97 | Find process by name fragment | PS | <code>Get-Process &#124; Where-Object ProcessName -like '*code*'</code> |  |
| 98 | Top CPU processes | PS | <code>Get-Process &#124; Sort-Object CPU -Descending &#124; Select-Object -First 10</code> |  |
| 99 | Top RAM processes | PS | <code>Get-Process &#124; Sort-Object WorkingSet64 -Descending &#124; Select-Object -First 10</code> |  |
| 100 | Process with PID | PS | <code>Get-Process -Id 1234</code> | Replace PID |
| 101 | Process name + PID | PS | <code>Get-Process &#124; Select-Object Name,Id,CPU</code> |  |
| 102 | Process with main window title | PS | <code>Get-Process &#124; Where-Object MainWindowTitle &#124; Select-Object Name,Id,MainWindowTitle</code> |  |
| 103 | Close Notepad | PS | <code>Stop-Process -Name notepad</code> | May discard unsaved work |
| 104 | Close process by PID | PS | <code>Stop-Process -Id 1234</code> | May discard unsaved work |
| 105 | Force close unresponsive app | PS | <code>Stop-Process -Name notepad -Force</code> | Risk: unsaved work |
| 106 | Wait until app exits | PS | <code>Wait-Process -Name notepad</code> | Blocks until process exits |
| 107 | Start app and capture PID | PS | <code>$p = Start-Process notepad -PassThru; $p.Id</code> |  |
| 108 | Start app in target directory | PS | <code>Start-Process notepad -WorkingDirectory 'C:\Work'</code> |  |
| 109 | Run app minimized | PS | <code>Start-Process notepad -WindowStyle Minimized</code> | Applies to apps supporting launch window style |
| 110 | Run app maximized | PS | <code>Start-Process notepad -WindowStyle Maximized</code> | Applies to apps supporting launch window style |
| 111 | Get services | PS | <code>Get-Service</code> |  |
| 112 | Only running services | PS | <code>Get-Service &#124; Where-Object Status -eq Running</code> |  |
| 113 | Find Bluetooth service | PS | <code>Get-Service *Bluetooth*</code> |  |
| 114 | Get scheduled jobs | PS | <code>Get-ScheduledTask</code> |  |
| 115 | Get running scheduled tasks | PS | <code>Get-ScheduledTask &#124; Where-Object State -eq Running</code> |  |
| 116 | Current session and user | PS | <code>whoami</code> |  |
| 117 | Computer name | PS | <code>hostname</code> |  |
| 118 | Windows version details | PS | <code>Get-ComputerInfo &#124; Select-Object WindowsProductName,WindowsVersion,OsBuildNumber</code> |  |
| 119 | Current time | PS | <code>Get-Date</code> |  |
| 120 | Current directory | PS | <code>Get-Location</code> |  |
| 121 | PowerShell command history | PS | <code>Get-History</code> |  |
| 122 | Discover installed command | PS | <code>Get-Command 'code' -ErrorAction SilentlyContinue</code> |  |

## 05 File and directory actions (44 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 123 | List files | PS | <code>Get-ChildItem 'C:\Work'</code> |  |
| 124 | List hidden files | PS | <code>Get-ChildItem 'C:\Work' -Force</code> |  |
| 125 | List folders only | PS | <code>Get-ChildItem 'C:\Work' -Directory</code> |  |
| 126 | List files only | PS | <code>Get-ChildItem 'C:\Work' -File</code> |  |
| 127 | List files recursively | PS | <code>Get-ChildItem 'C:\Work' -File -Recurse</code> |  |
| 128 | Find PDFs recursively | PS | <code>Get-ChildItem 'C:\Work' -Filter '*.pdf' -File -Recurse</code> |  |
| 129 | Find screenshots | PS | <code>Get-ChildItem "$env:USERPROFILE\Pictures" -Filter '*.png' -Recurse</code> |  |
| 130 | Files modified recently | PS | <code>Get-ChildItem 'C:\Work' -File &#124; Sort-Object LastWriteTime -Descending</code> |  |
| 131 | Find large files | PS | <code>Get-ChildItem 'C:\Work' -File -Recurse &#124; Sort-Object Length -Descending &#124; Select-Object -First 10</code> |  |
| 132 | Current folder | PS | <code>Get-Location</code> |  |
| 133 | Change folder | PS | <code>Set-Location 'C:\Work'</code> |  |
| 134 | Create folder | PS | <code>New-Item 'C:\Work\NewFolder' -ItemType Directory -Force</code> |  |
| 135 | Create empty file | PS | <code>New-Item 'C:\Work\notes.txt' -ItemType File -ErrorAction Stop</code> | Fails if already exists |
| 136 | Read a text file | PS | <code>Get-Content 'C:\Work\notes.txt'</code> |  |
| 137 | Read entire file as string | PS | <code>Get-Content 'C:\Work\notes.txt' -Raw</code> |  |
| 138 | Read first 10 lines | PS | <code>Get-Content 'C:\Work\notes.txt' -TotalCount 10</code> |  |
| 139 | Read last 10 lines | PS | <code>Get-Content 'C:\Work\notes.txt' -Tail 10</code> |  |
| 140 | Write a text file | PS | <code>Set-Content 'C:\Work\notes.txt' 'Hello'</code> | Overwrites contents |
| 141 | Append to a text file | PS | <code>Add-Content 'C:\Work\notes.txt' 'More text'</code> |  |
| 142 | Replace word in file | PS | <code>(Get-Content 'C:\Work\notes.txt' -Raw).Replace('old','new') &#124; Set-Content 'C:\Work\notes.txt'</code> | Creates new encoding/layout; back up first |
| 143 | Copy file | PS | <code>Copy-Item 'C:\Work\a.txt' 'C:\Work\b.txt'</code> |  |
| 144 | Copy folder recursively | PS | <code>Copy-Item 'C:\Work\Src' 'C:\Work\Backup' -Recurse</code> |  |
| 145 | Move file | PS | <code>Move-Item 'C:\Work\a.txt' 'C:\Work\Archive\a.txt'</code> |  |
| 146 | Rename file | PS | <code>Rename-Item 'C:\Work\a.txt' 'renamed.txt'</code> |  |
| 147 | Delete file preview | PS | <code>Remove-Item 'C:\Work\a.txt' -WhatIf</code> | Preview only |
| 148 | Delete file | PS | <code>Remove-Item 'C:\Work\a.txt' -Confirm</code> | Requires confirmation |
| 149 | Delete folder preview | PS | <code>Remove-Item 'C:\Work\Old' -Recurse -WhatIf</code> | Preview only |
| 150 | Get file size | PS | <code>(Get-Item 'C:\Work\a.txt').Length</code> |  |
| 151 | Get file timestamps | PS | <code>Get-Item 'C:\Work\a.txt' &#124; Select-Object CreationTime,LastWriteTime</code> |  |
| 152 | Create ZIP | PS | <code>Compress-Archive 'C:\Work\Src\*' 'C:\Work\backup.zip'</code> |  |
| 153 | Extract ZIP | PS | <code>Expand-Archive 'C:\Work\backup.zip' 'C:\Work\Extracted'</code> |  |
| 154 | Calculate SHA256 | PS | <code>Get-FileHash 'C:\Work\a.txt' -Algorithm SHA256</code> |  |
| 155 | Check if file exists | PS | <code>Test-Path 'C:\Work\a.txt'</code> |  |
| 156 | Find text inside files | PS | <code>Get-ChildItem 'C:\Work' -Filter '*.txt' &#124; Select-String -Pattern 'error'</code> |  |
| 157 | Search a file | PS | <code>Select-String 'C:\Work\log.txt' -Pattern 'error'</code> |  |
| 158 | Compare text files | PS | <code>Compare-Object (Get-Content 'C:\Work\a.txt') (Get-Content 'C:\Work\b.txt')</code> |  |
| 159 | Count lines in file | PS | <code>(Get-Content 'C:\Work\a.txt' &#124; Measure-Object -Line).Lines</code> |  |
| 160 | Sort text lines | PS | <code>Get-Content 'C:\Work\a.txt' &#124; Sort-Object</code> |  |
| 161 | Remove duplicate lines | PS | <code>Get-Content 'C:\Work\a.txt' &#124; Sort-Object -Unique</code> |  |
| 162 | Read JSON | PS | <code>Get-Content 'C:\Work\config.json' -Raw &#124; ConvertFrom-Json</code> |  |
| 163 | Save object as JSON | PS | <code>@{name='Jarvis';enabled=$true} &#124; ConvertTo-Json &#124; Set-Content 'C:\Work\config.json'</code> |  |
| 164 | Import CSV | PS | <code>Import-Csv 'C:\Work\data.csv'</code> |  |
| 165 | Export CSV | PS | <code>Get-Process &#124; Select-Object Name,Id &#124; Export-Csv 'C:\Work\processes.csv' -NoTypeInformation</code> |  |
| 166 | Open file in Notepad | PS | <code>Start-Process notepad.exe -ArgumentList 'C:\Work\notes.txt'</code> |  |

## 06 Clipboard and OS utilities (20 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 167 | Read clipboard | PS | <code>Get-Clipboard</code> |  |
| 168 | Read clipboard as raw text | PS | <code>Get-Clipboard -Raw</code> |  |
| 169 | Set clipboard text | PS | <code>Set-Clipboard -Value 'Hello from Jarvis'</code> |  |
| 170 | Clear clipboard | PS | <code>Set-Clipboard -Value ''</code> |  |
| 171 | Current environment variables | PS | <code>Get-ChildItem Env:</code> |  |
| 172 | Get user profile folder | PS | <code>$env:USERPROFILE</code> |  |
| 173 | Get TEMP folder | PS | <code>$env:TEMP</code> |  |
| 174 | Create temporary file | PS | <code>New-TemporaryFile</code> |  |
| 175 | Refresh DNS cache | PS | <code>Clear-DnsClientCache</code> |  |
| 176 | Shutdown after 60 seconds | PS | <code>shutdown.exe /s /t 60</code> | Confirmation recommended |
| 177 | Restart after 60 seconds | PS | <code>shutdown.exe /r /t 60</code> | Confirmation recommended |
| 178 | Cancel scheduled shutdown | PS | <code>shutdown.exe /a</code> |  |
| 179 | Lock Windows | PS | <code>rundll32.exe user32.dll,LockWorkStation</code> | Interactive desktop |
| 180 | Battery report | PS | <code>powercfg.exe /batteryreport</code> |  |
| 181 | Active power scheme | PS | <code>powercfg.exe /getactivescheme</code> |  |
| 182 | List power schemes | PS | <code>powercfg.exe /list</code> |  |
| 183 | Open printers | PS | <code>Start-Process 'ms-settings:printers'</code> |  |
| 184 | List installed printers | PS | <code>Get-Printer</code> | PrintManagement module where available |
| 185 | Default printer | PS | <code>Get-CimInstance Win32_Printer &#124; Where-Object Default</code> |  |
| 186 | List print jobs | PS | <code>Get-PrintJob -PrinterName 'YourPrinter'</code> | Printer name required |

## 07 Network and hardware monitoring (38 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 187 | Network adapters | PS | <code>Get-NetAdapter</code> |  |
| 188 | Active network adapters | PS | <code>Get-NetAdapter &#124; Where-Object Status -eq Up</code> |  |
| 189 | IP addresses | PS | <code>Get-NetIPAddress</code> |  |
| 190 | IPv4 only | PS | <code>Get-NetIPAddress -AddressFamily IPv4</code> |  |
| 191 | Network interface configuration | PS | <code>Get-NetIPConfiguration</code> |  |
| 192 | DNS client configuration | PS | <code>Get-DnsClientServerAddress</code> |  |
| 193 | DNS lookup | PS | <code>Resolve-DnsName 'example.com'</code> |  |
| 194 | Check host reachability | PS | <code>Test-Connection 'example.com' -Count 2</code> |  |
| 195 | Test TCP port | PS | <code>Test-NetConnection 'example.com' -Port 443</code> |  |
| 196 | Current TCP connections | PS | <code>Get-NetTCPConnection</code> |  |
| 197 | Listening TCP ports | PS | <code>Get-NetTCPConnection -State Listen</code> |  |
| 198 | Network routing table | PS | <code>Get-NetRoute</code> |  |
| 199 | Local hostname | PS | <code>$env:COMPUTERNAME</code> |  |
| 200 | Wi-Fi status | PS | <code>netsh.exe wlan show interfaces</code> |  |
| 201 | Known Wi-Fi profiles | PS | <code>netsh.exe wlan show profiles</code> | Does not retrieve passwords |
| 202 | IP settings (classic) | PS | <code>ipconfig.exe /all</code> |  |
| 203 | Ping gateway | PS | <code>Test-Connection (Get-NetIPConfiguration &#124; Where-Object IPv4DefaultGateway &#124; Select-Object -First 1 -ExpandProperty IPv4DefaultGateway).NextHop -Count 2</code> | Requires default gateway |
| 204 | Traceroute | PS | <code>tracert.exe example.com</code> |  |
| 205 | Open firewall settings | PS | <code>Start-Process 'ms-settings:windowsdefender'</code> |  |
| 206 | Windows firewall profiles | PS | <code>Get-NetFirewallProfile</code> |  |
| 207 | CPU details | PS | <code>Get-CimInstance Win32_Processor</code> |  |
| 208 | RAM module details | PS | <code>Get-CimInstance Win32_PhysicalMemory</code> |  |
| 209 | Total RAM in GB | PS | <code>[math]::Round(((Get-CimInstance Win32_PhysicalMemory &#124; Measure-Object Capacity -Sum).Sum/1GB),2)</code> |  |
| 210 | GPU details | PS | <code>Get-CimInstance Win32_VideoController</code> |  |
| 211 | Disk drives | PS | <code>Get-CimInstance Win32_DiskDrive</code> |  |
| 212 | Logical disks | PS | <code>Get-CimInstance Win32_LogicalDisk</code> |  |
| 213 | Free disk space | PS | <code>Get-Volume &#124; Select-Object DriveLetter,SizeRemaining,Size</code> |  |
| 214 | Motherboard | PS | <code>Get-CimInstance Win32_BaseBoard</code> |  |
| 215 | BIOS version | PS | <code>Get-CimInstance Win32_BIOS</code> |  |
| 216 | Operating system | PS | <code>Get-CimInstance Win32_OperatingSystem</code> |  |
| 217 | Boot time | PS | <code>(Get-CimInstance Win32_OperatingSystem).LastBootUpTime</code> |  |
| 218 | Plug-and-play devices | PS | <code>Get-PnpDevice</code> |  |
| 219 | Problematic devices | PS | <code>Get-PnpDevice &#124; Where-Object Status -ne OK</code> |  |
| 220 | Display resolution | PS | <code>Get-CimInstance Win32_VideoController &#124; Select-Object CurrentHorizontalResolution,CurrentVerticalResolution</code> |  |
| 221 | List installed Windows updates | PS | <code>Get-HotFix</code> |  |
| 222 | Antivirus status | PS | <code>Get-MpComputerStatus</code> | Windows Defender environment |
| 223 | Run antivirus quick scan | PS | <code>Start-MpScan -ScanType QuickScan</code> | Windows Defender environment |
| 224 | Power-related sleep states | PS | <code>powercfg.exe /a</code> |  |

## 08 General keyboard and desktop actions (61 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 225 | Press Enter | PY | <code>pg.press('enter')</code> |  |
| 226 | Press Escape | PY | <code>pg.press('esc')</code> |  |
| 227 | Press Tab | PY | <code>pg.press('tab')</code> |  |
| 228 | Press Shift+Tab | PY | <code>pg.hotkey('shift','tab')</code> |  |
| 229 | Press Backspace | PY | <code>pg.press('backspace')</code> |  |
| 230 | Press Delete | PY | <code>pg.press('delete')</code> |  |
| 231 | Press Home | PY | <code>pg.press('home')</code> |  |
| 232 | Press End | PY | <code>pg.press('end')</code> |  |
| 233 | Press Page Down | PY | <code>pg.press('pagedown')</code> |  |
| 234 | Press Page Up | PY | <code>pg.press('pageup')</code> |  |
| 235 | Press Arrow Up | PY | <code>pg.press('up')</code> |  |
| 236 | Press Arrow Down | PY | <code>pg.press('down')</code> |  |
| 237 | Press Arrow Left | PY | <code>pg.press('left')</code> |  |
| 238 | Press Arrow Right | PY | <code>pg.press('right')</code> |  |
| 239 | Press F1 help | PY | <code>pg.press('f1')</code> | Application-dependent |
| 240 | Press F2 rename/edit | PY | <code>pg.press('f2')</code> | Application-dependent |
| 241 | Press F5 refresh | PY | <code>pg.press('f5')</code> | Application-dependent |
| 242 | Press Ctrl+A select all | PY | <code>pg.hotkey('ctrl','a')</code> |  |
| 243 | Press Ctrl+C copy | PY | <code>pg.hotkey('ctrl','c')</code> |  |
| 244 | Press Ctrl+X cut | PY | <code>pg.hotkey('ctrl','x')</code> |  |
| 245 | Press Ctrl+V paste | PY | <code>pg.hotkey('ctrl','v')</code> |  |
| 246 | Press Ctrl+Z undo | PY | <code>pg.hotkey('ctrl','z')</code> |  |
| 247 | Press Ctrl+Y redo | PY | <code>pg.hotkey('ctrl','y')</code> | Application-dependent |
| 248 | Press Ctrl+S save | PY | <code>pg.hotkey('ctrl','s')</code> |  |
| 249 | Press Ctrl+Shift+S save as | PY | <code>pg.hotkey('ctrl','shift','s')</code> | Application-dependent |
| 250 | Press Ctrl+O open file | PY | <code>pg.hotkey('ctrl','o')</code> |  |
| 251 | Press Ctrl+P print | PY | <code>pg.hotkey('ctrl','p')</code> |  |
| 252 | Press Ctrl+F find | PY | <code>pg.hotkey('ctrl','f')</code> |  |
| 253 | Press Ctrl+H replace/history | PY | <code>pg.hotkey('ctrl','h')</code> | App-specific meaning |
| 254 | Press Ctrl+N new document | PY | <code>pg.hotkey('ctrl','n')</code> |  |
| 255 | Press Ctrl+W close tab/document | PY | <code>pg.hotkey('ctrl','w')</code> |  |
| 256 | Press Alt+F4 close window | PY | <code>pg.hotkey('alt','f4')</code> | May discard unsaved changes |
| 257 | Switch application | PY | <code>pg.hotkey('alt','tab')</code> |  |
| 258 | Task View | PY | <code>pg.hotkey('win','tab')</code> |  |
| 259 | Show desktop | PY | <code>pg.hotkey('win','d')</code> |  |
| 260 | Show Windows search | PY | <code>pg.hotkey('win','s')</code> |  |
| 261 | Open Run dialog | PY | <code>pg.hotkey('win','r')</code> |  |
| 262 | Open Windows Settings | PY | <code>pg.hotkey('win','i')</code> |  |
| 263 | Open File Explorer | PY | <code>pg.hotkey('win','e')</code> |  |
| 264 | Quick Link menu | PY | <code>pg.hotkey('win','x')</code> |  |
| 265 | Open clipboard history | PY | <code>pg.hotkey('win','v')</code> | May need enabled in Settings |
| 266 | Open emoji picker | PY | <code>pg.hotkey('win','.')</code> |  |
| 267 | Take snip overlay | PY | <code>pg.hotkey('win','shift','s')</code> |  |
| 268 | Lock workstation | PY | <code>pg.hotkey('win','l')</code> |  |
| 269 | Snap window left | PY | <code>pg.hotkey('win','left')</code> |  |
| 270 | Snap window right | PY | <code>pg.hotkey('win','right')</code> |  |
| 271 | Maximize current window | PY | <code>pg.hotkey('win','up')</code> |  |
| 272 | Minimize/restore window | PY | <code>pg.hotkey('win','down')</code> |  |
| 273 | Minimize all windows | PY | <code>pg.hotkey('win','m')</code> |  |
| 274 | New virtual desktop | PY | <code>pg.hotkey('win','ctrl','d')</code> |  |
| 275 | Close virtual desktop | PY | <code>pg.hotkey('win','ctrl','f4')</code> |  |
| 276 | Virtual desktop right | PY | <code>pg.hotkey('win','ctrl','right')</code> |  |
| 277 | Virtual desktop left | PY | <code>pg.hotkey('win','ctrl','left')</code> |  |
| 278 | System context menu | PY | <code>pg.hotkey('shift','f10')</code> |  |
| 279 | Select previous word | PY | <code>pg.hotkey('ctrl','shift','left')</code> | In text field |
| 280 | Select next word | PY | <code>pg.hotkey('ctrl','shift','right')</code> | In text field |
| 281 | Jump previous word | PY | <code>pg.hotkey('ctrl','left')</code> | In text field |
| 282 | Jump next word | PY | <code>pg.hotkey('ctrl','right')</code> | In text field |
| 283 | Select until line end | PY | <code>pg.hotkey('shift','end')</code> | In text field |
| 284 | Select until line start | PY | <code>pg.hotkey('shift','home')</code> | In text field |
| 285 | Select all until document end | PY | <code>pg.hotkey('ctrl','shift','end')</code> | In text field |

## 09 Mouse, touch-like and visual control (28 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 286 | Click coordinates | PY | <code>pg.click(500,300)</code> | Coordinate must correspond to intended target |
| 287 | Right-click coordinates | PY | <code>pg.rightClick(500,300)</code> |  |
| 288 | Double-click coordinates | PY | <code>pg.doubleClick(500,300)</code> |  |
| 289 | Middle-click coordinates | PY | <code>pg.middleClick(500,300)</code> |  |
| 290 | Triple-click coordinates | PY | <code>pg.tripleClick(500,300)</code> |  |
| 291 | Move pointer | PY | <code>pg.moveTo(500,300,duration=0.3)</code> |  |
| 292 | Move relatively | PY | <code>pg.moveRel(100,0,duration=0.3)</code> |  |
| 293 | Click at pointer | PY | <code>pg.click()</code> |  |
| 294 | Press left mouse button | PY | <code>pg.mouseDown(button='left')</code> | Remember to release |
| 295 | Release left mouse button | PY | <code>pg.mouseUp(button='left')</code> |  |
| 296 | Drag by offset | PY | <code>pg.dragRel(100,50,duration=0.5)</code> |  |
| 297 | Drag to target | PY | <code>pg.moveTo(300,300); pg.dragTo(700,450,duration=0.8)</code> |  |
| 298 | Scroll down | PY | <code>pg.scroll(-5)</code> |  |
| 299 | Scroll up | PY | <code>pg.scroll(5)</code> |  |
| 300 | Read mouse coordinates | PY | <code>pg.position()</code> |  |
| 301 | Read screen dimensions | PY | <code>pg.size()</code> |  |
| 302 | Screenshot entire display | PY | <code>pg.screenshot().save('screen.png')</code> |  |
| 303 | Screenshot region | PY | <code>pg.screenshot(region=(100,100,600,400)).save('region.png')</code> |  |
| 304 | Read pixel color | PY | <code>pg.pixel(100,100)</code> |  |
| 305 | Compare pixel color | PY | <code>pg.pixelMatchesColor(100,100,(255,255,255))</code> |  |
| 306 | Locate button by screenshot | PY | <code>pg.locateOnScreen('button.png')</code> | Requires reference image on disk; may raise if not found |
| 307 | Click image match | PY | <code>pg.click(pg.center(pg.locateOnScreen('button.png')))</code> | Only when a unique match exists; otherwise can raise |
| 308 | Locate screen image confidence | PY | <code>pg.locateOnScreen('button.png',confidence=0.9)</code> | Install opencv-python; confidence requires OpenCV |
| 309 | Type simple text | PY | <code>pg.write('Hello world',interval=0.03)</code> | ASCII-style keyboard typing |
| 310 | Press key repeatedly | PY | <code>pg.press('down', presses=5, interval=0.1)</code> |  |
| 311 | Hold Shift while clicking | PY | <code>pg.keyDown('shift'); pg.click(500,400); pg.keyUp('shift')</code> | Ensure key release if errors |
| 312 | Ctrl-click to toggle selection | PY | <code>pg.keyDown('ctrl'); pg.click(500,400); pg.keyUp('ctrl')</code> | Ensure key release if errors |
| 313 | Select screen rectangle | PY | <code>pg.moveTo(200,200); pg.dragTo(700,500,duration=0.6)</code> | Only in apps supporting drag selection |

## 10 File Explorer shortcuts (focus Explorer) (12 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 314 | New folder | PY | <code>pg.hotkey('ctrl','shift','n')</code> |  |
| 315 | Rename selected file | PY | <code>pg.press('f2')</code> |  |
| 316 | Properties of selection | PY | <code>pg.hotkey('alt','enter')</code> |  |
| 317 | Open selected file | PY | <code>pg.press('enter')</code> |  |
| 318 | Up one directory | PY | <code>pg.hotkey('alt','up')</code> |  |
| 319 | Navigate back | PY | <code>pg.hotkey('alt','left')</code> |  |
| 320 | Navigate forward | PY | <code>pg.hotkey('alt','right')</code> |  |
| 321 | Focus address bar | PY | <code>pg.hotkey('alt','d')</code> |  |
| 322 | New Explorer window | PY | <code>pg.hotkey('ctrl','n')</code> |  |
| 323 | Focus Explorer search | PY | <code>pg.hotkey('ctrl','f')</code> |  |
| 324 | Refresh file list | PY | <code>pg.press('f5')</code> |  |
| 325 | Select file range | PY | <code>pg.keyDown('shift'); pg.click(500,400); pg.keyUp('shift')</code> | Click endpoint after selecting a start item |

## 11 Browser / Chrome / Edge shortcuts (focus browser) (26 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 326 | New tab | PY | <code>pg.hotkey('ctrl','t')</code> |  |
| 327 | New window | PY | <code>pg.hotkey('ctrl','n')</code> |  |
| 328 | Incognito/InPrivate window | PY | <code>pg.hotkey('ctrl','shift','n')</code> |  |
| 329 | Close tab | PY | <code>pg.hotkey('ctrl','w')</code> |  |
| 330 | Reopen tab | PY | <code>pg.hotkey('ctrl','shift','t')</code> |  |
| 331 | Next tab | PY | <code>pg.hotkey('ctrl','tab')</code> |  |
| 332 | Previous tab | PY | <code>pg.hotkey('ctrl','shift','tab')</code> |  |
| 333 | First tab | PY | <code>pg.hotkey('ctrl','1')</code> |  |
| 334 | Last tab | PY | <code>pg.hotkey('ctrl','9')</code> |  |
| 335 | Address bar | PY | <code>pg.hotkey('ctrl','l')</code> |  |
| 336 | Navigate to URL | PY | <code>pg.hotkey('ctrl','l'); pg.write('https://example.com'); pg.press('enter')</code> |  |
| 337 | Refresh page | PY | <code>pg.hotkey('ctrl','r')</code> |  |
| 338 | Hard refresh | PY | <code>pg.hotkey('ctrl','shift','r')</code> | Browser-dependent cache behavior |
| 339 | Page back | PY | <code>pg.hotkey('alt','left')</code> |  |
| 340 | Page forward | PY | <code>pg.hotkey('alt','right')</code> |  |
| 341 | Find in page | PY | <code>pg.hotkey('ctrl','f')</code> |  |
| 342 | Open downloads | PY | <code>pg.hotkey('ctrl','j')</code> |  |
| 343 | Open history | PY | <code>pg.hotkey('ctrl','h')</code> |  |
| 344 | Bookmark current page | PY | <code>pg.hotkey('ctrl','d')</code> |  |
| 345 | Show bookmark manager | PY | <code>pg.hotkey('ctrl','shift','o')</code> |  |
| 346 | Developer tools | PY | <code>pg.hotkey('ctrl','shift','i')</code> |  |
| 347 | Developer console | PY | <code>pg.hotkey('ctrl','shift','j')</code> | Chrome/Edge |
| 348 | Zoom in | PY | <code>pg.hotkey('ctrl','+')</code> | Layout-specific; Ctrl+equals is another choice |
| 349 | Zoom out | PY | <code>pg.hotkey('ctrl','-')</code> |  |
| 350 | Reset zoom | PY | <code>pg.hotkey('ctrl','0')</code> |  |
| 351 | Scroll to page bottom | PY | <code>pg.hotkey('ctrl','end')</code> |  |

## 12 Media controls and YouTube (26 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 352 | Global media play/pause | PY | <code>pg.press('playpause')</code> | Targets active media session, if supported |
| 353 | Global next track | PY | <code>pg.press('nexttrack')</code> | Requires supported media session |
| 354 | Global previous track | PY | <code>pg.press('prevtrack')</code> | Requires supported media session |
| 355 | Global stop media | PY | <code>pg.press('stop')</code> | Media key; app may ignore |
| 356 | Increase volume | PY | <code>pg.press('volumeup')</code> | Global media volume key |
| 357 | Decrease volume | PY | <code>pg.press('volumedown')</code> | Global media volume key |
| 358 | Mute/unmute | PY | <code>pg.press('volumemute')</code> | Global media mute key |
| 359 | YouTube play/pause | PY | <code>pg.press('k')</code> | Focus YouTube player |
| 360 | YouTube rewind 10 sec | PY | <code>pg.press('j')</code> | Focus YouTube player |
| 361 | YouTube forward 10 sec | PY | <code>pg.press('l')</code> | Focus YouTube player |
| 362 | YouTube mute | PY | <code>pg.press('m')</code> | Focus YouTube player |
| 363 | YouTube fullscreen | PY | <code>pg.press('f')</code> | Focus YouTube player |
| 364 | YouTube captions | PY | <code>pg.press('c')</code> | Focus YouTube player |
| 365 | YouTube theater mode | PY | <code>pg.press('t')</code> | Focus YouTube player |
| 366 | YouTube mini player | PY | <code>pg.press('i')</code> | Focus YouTube player |
| 367 | YouTube seek 50 percent | PY | <code>pg.press('5')</code> | Focus YouTube player |
| 368 | YouTube seek beginning | PY | <code>pg.press('0')</code> | Focus YouTube player |
| 369 | YouTube next video | PY | <code>pg.hotkey('shift','n')</code> | Focus YouTube player |
| 370 | YouTube faster speed | PY | <code>pg.hotkey('shift','.')</code> | US keyboard layout; focus player |
| 371 | YouTube slower speed | PY | <code>pg.hotkey('shift',',')</code> | US keyboard layout; focus player |
| 372 | YouTube next frame | PY | <code>pg.press('.')</code> | Paused video |
| 373 | YouTube previous frame | PY | <code>pg.press(',')</code> | Paused video |
| 374 | VLC play/pause | PY | <code>pg.press('space')</code> | Focus VLC; default hotkeys |
| 375 | VLC fullscreen | PY | <code>pg.press('f')</code> | Focus VLC; default hotkeys |
| 376 | VLC mute | PY | <code>pg.press('m')</code> | Focus VLC; default hotkeys |
| 377 | VLC stop | PY | <code>pg.press('s')</code> | Focus VLC; default hotkeys |

## 13 VS Code default shortcuts (focus VS Code) (28 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 378 | Command Palette | PY | <code>pg.hotkey('ctrl','shift','p')</code> |  |
| 379 | Quick Open file | PY | <code>pg.hotkey('ctrl','p')</code> |  |
| 380 | Integrated terminal | PY | <code>pg.hotkey('ctrl','`')</code> |  |
| 381 | New terminal | PY | <code>pg.hotkey('ctrl','shift','`')</code> |  |
| 382 | Explorer panel | PY | <code>pg.hotkey('ctrl','shift','e')</code> |  |
| 383 | Search panel | PY | <code>pg.hotkey('ctrl','shift','f')</code> |  |
| 384 | Source Control panel | PY | <code>pg.hotkey('ctrl','shift','g')</code> |  |
| 385 | Run/Debug panel | PY | <code>pg.hotkey('ctrl','shift','d')</code> |  |
| 386 | Extensions panel | PY | <code>pg.hotkey('ctrl','shift','x')</code> |  |
| 387 | Problems panel | PY | <code>pg.hotkey('ctrl','shift','m')</code> |  |
| 388 | Toggle side bar | PY | <code>pg.hotkey('ctrl','b')</code> |  |
| 389 | Split editor | PY | <code>pg.hotkey('ctrl','\\')</code> | Backslash key; keyboard layout dependent |
| 390 | Format document | PY | <code>pg.hotkey('shift','alt','f')</code> | Formatter required |
| 391 | Go to definition | PY | <code>pg.press('f12')</code> |  |
| 392 | Peek definition | PY | <code>pg.hotkey('alt','f12')</code> |  |
| 393 | Rename symbol | PY | <code>pg.press('f2')</code> |  |
| 394 | Open suggestions | PY | <code>pg.hotkey('ctrl','space')</code> |  |
| 395 | Duplicate line down | PY | <code>pg.hotkey('shift','alt','down')</code> |  |
| 396 | Move line down | PY | <code>pg.hotkey('alt','down')</code> |  |
| 397 | Move line up | PY | <code>pg.hotkey('alt','up')</code> |  |
| 398 | Delete current line | PY | <code>pg.hotkey('ctrl','shift','k')</code> |  |
| 399 | Select next occurrence | PY | <code>pg.hotkey('ctrl','d')</code> |  |
| 400 | Select all occurrences | PY | <code>pg.hotkey('ctrl','f2')</code> |  |
| 401 | Add cursor below | PY | <code>pg.hotkey('ctrl','alt','down')</code> |  |
| 402 | Add cursor above | PY | <code>pg.hotkey('ctrl','alt','up')</code> |  |
| 403 | Go to line | PY | <code>pg.hotkey('ctrl','g')</code> |  |
| 404 | New line below | PY | <code>pg.hotkey('ctrl','enter')</code> |  |
| 405 | Open Settings | PY | <code>pg.hotkey('ctrl',',')</code> |  |

## 14 Microsoft Word shortcuts (focus Word) (10 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 406 | Bold selected text | PY | <code>pg.hotkey('ctrl','b')</code> |  |
| 407 | Italic selected text | PY | <code>pg.hotkey('ctrl','i')</code> |  |
| 408 | Underline selected text | PY | <code>pg.hotkey('ctrl','u')</code> |  |
| 409 | Insert hyperlink | PY | <code>pg.hotkey('ctrl','k')</code> |  |
| 410 | Align paragraph left | PY | <code>pg.hotkey('ctrl','l')</code> |  |
| 411 | Center paragraph | PY | <code>pg.hotkey('ctrl','e')</code> |  |
| 412 | Align paragraph right | PY | <code>pg.hotkey('ctrl','r')</code> |  |
| 413 | Justify paragraph | PY | <code>pg.hotkey('ctrl','j')</code> |  |
| 414 | Insert page break | PY | <code>pg.hotkey('ctrl','enter')</code> |  |
| 415 | Open Go To | PY | <code>pg.hotkey('ctrl','g')</code> |  |

## 15 Microsoft Excel shortcuts (focus Excel) (12 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 416 | Edit active cell | PY | <code>pg.press('f2')</code> |  |
| 417 | Format cells dialog | PY | <code>pg.hotkey('ctrl','1')</code> |  |
| 418 | Select current column | PY | <code>pg.hotkey('ctrl','space')</code> |  |
| 419 | Select current row | PY | <code>pg.hotkey('shift','space')</code> |  |
| 420 | Toggle filters | PY | <code>pg.hotkey('ctrl','shift','l')</code> |  |
| 421 | AutoSum | PY | <code>pg.hotkey('alt','=')</code> |  |
| 422 | Insert current date | PY | <code>pg.hotkey('ctrl',';')</code> |  |
| 423 | Fill cells downward | PY | <code>pg.hotkey('ctrl','d')</code> |  |
| 424 | Fill cells rightward | PY | <code>pg.hotkey('ctrl','r')</code> |  |
| 425 | Create table from selection | PY | <code>pg.hotkey('ctrl','t')</code> |  |
| 426 | Next sheet | PY | <code>pg.hotkey('ctrl','pagedown')</code> |  |
| 427 | Previous sheet | PY | <code>pg.hotkey('ctrl','pageup')</code> |  |

## 16 Microsoft PowerPoint (focus PowerPoint) (8 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 428 | New slide | PY | <code>pg.hotkey('ctrl','m')</code> |  |
| 429 | Duplicate selected slide/object | PY | <code>pg.hotkey('ctrl','d')</code> |  |
| 430 | Start slideshow | PY | <code>pg.press('f5')</code> |  |
| 431 | Start slideshow from current | PY | <code>pg.hotkey('shift','f5')</code> |  |
| 432 | Next slideshow slide | PY | <code>pg.press('right')</code> | While slideshow active |
| 433 | Previous slideshow slide | PY | <code>pg.press('left')</code> | While slideshow active |
| 434 | Black slideshow screen | PY | <code>pg.press('b')</code> | While slideshow active |
| 435 | Exit slideshow | PY | <code>pg.press('esc')</code> | While slideshow active |

## 17 Blender default keymap (focus viewport) (10 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 436 | Move/grab selection | PY | <code>pg.press('g')</code> | Blender default keymap |
| 437 | Rotate selection | PY | <code>pg.press('r')</code> | Blender default keymap |
| 438 | Scale selection | PY | <code>pg.press('s')</code> | Blender default keymap |
| 439 | Toggle Edit Mode | PY | <code>pg.press('tab')</code> | Blender default keymap |
| 440 | Add object menu | PY | <code>pg.hotkey('shift','a')</code> | Blender default keymap |
| 441 | Search operators | PY | <code>pg.press('f3')</code> | Blender default keymap |
| 442 | Toggle side panel | PY | <code>pg.press('n')</code> | Blender default keymap |
| 443 | Front view | PY | <code>pg.press('num1')</code> | Numpad required |
| 444 | Right view | PY | <code>pg.press('num3')</code> | Numpad required |
| 445 | Top view | PY | <code>pg.press('num7')</code> | Numpad required |

## 18 Unreal Engine 5 Editor (focus editor) (9 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 446 | Play in Editor | PY | <code>pg.hotkey('alt','p')</code> | Default shortcut |
| 447 | Simulate in Editor | PY | <code>pg.hotkey('alt','s')</code> | Default shortcut |
| 448 | Toggle game view | PY | <code>pg.press('g')</code> | Viewport focus required |
| 449 | Toggle immersive viewport | PY | <code>pg.press('f11')</code> | Viewport focus required |
| 450 | Move tool | PY | <code>pg.press('w')</code> | Viewport focus |
| 451 | Rotate tool | PY | <code>pg.press('e')</code> | Viewport focus |
| 452 | Scale tool | PY | <code>pg.press('r')</code> | Viewport focus |
| 453 | Focus selection | PY | <code>pg.press('f')</code> | Viewport focus |
| 454 | Open Content Drawer | PY | <code>pg.hotkey('ctrl','space')</code> | Default editor shortcut; may vary by settings |

## 19 Desktop UI Automation (pywinauto) (11 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 455 | List top-level windows | PY | <code>Desktop(backend='uia').windows()</code> |  |
| 456 | Find Notepad window | PY | <code>w = Desktop(backend='uia').window(title_re='.*Notepad.*')</code> | Initialize w for following examples; title depends on locale |
| 457 | Wait for selected window | PY | <code>w.wait('visible',timeout=10)</code> | Requires w initialization |
| 458 | Bring window to foreground | PY | <code>w.set_focus()</code> | Requires w initialization |
| 459 | Maximize selected window | PY | <code>w.maximize()</code> | Requires w initialization |
| 460 | Minimize selected window | PY | <code>w.minimize()</code> | Requires w initialization |
| 461 | Restore selected window | PY | <code>w.restore()</code> | Requires w initialization |
| 462 | Print controls in window | PY | <code>w.print_control_identifiers()</code> | Inspect actual available UI elements |
| 463 | Find button by visible label | PY | <code>w.child_window(title='Save',control_type='Button')</code> | Control may not exist |
| 464 | Click button by visible label | PY | <code>w.child_window(title='Save',control_type='Button').click_input()</code> | Control must be present and visible |
| 465 | Read edit box text | PY | <code>w.child_window(control_type='Edit').window_text()</code> | Choose correct edit control when multiple |

## 20 Web page DOM via Playwright (14 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 466 | Navigate to URL | WEB | <code>page.goto('https://example.org')</code> |  |
| 467 | Get page title | WEB | <code>page.title()</code> |  |
| 468 | Click button by name | WEB | <code>page.get_by_role('button',name='Submit').click()</code> | Target must exist |
| 469 | Click link by name | WEB | <code>page.get_by_role('link',name='More information').click()</code> | Target must exist |
| 470 | Fill labeled field | WEB | <code>page.get_by_label('Email').fill('test@example.org')</code> | Target must exist |
| 471 | Fill placeholder field | WEB | <code>page.get_by_placeholder('Search').fill('Jarvis')</code> | Target must exist |
| 472 | Fill CSS input | WEB | <code>page.locator('input[name="q"]').fill('Jarvis')</code> | Target must exist |
| 473 | Press Enter in input | WEB | <code>page.get_by_role('textbox').press('Enter')</code> | Choose unique textbox |
| 474 | Select dropdown item | WEB | <code>page.get_by_label('Country').select_option('IN')</code> | Select element with matching option |
| 475 | Check checkbox | WEB | <code>page.get_by_role('checkbox',name='Subscribe').check()</code> | Target must exist |
| 476 | Uncheck checkbox | WEB | <code>page.get_by_role('checkbox',name='Subscribe').uncheck()</code> | Target must exist |
| 477 | Click text | WEB | <code>page.get_by_text('Continue',exact=True).click()</code> | Target must exist |
| 478 | Save screenshot | WEB | <code>page.screenshot(path='page.png',full_page=True)</code> |  |
| 479 | Read text from element | WEB | <code>page.get_by_role('heading').first.inner_text()</code> | Target must exist |

## 21 Office app APIs (PowerShell COM) (14 commands)

| ID | Task | Language | Exact command | Notes |
|---:|---|---|---|---|
| 480 | Launch Excel via COM | PS | <code>$xl = New-Object -ComObject Excel.Application; $xl.Visible = $true</code> | Installed desktop Excel required |
| 481 | Create Excel workbook | PS | <code>$wb = $xl.Workbooks.Add()</code> | Run after Excel COM launch |
| 482 | Open Excel workbook | PS | <code>$wb = $xl.Workbooks.Open('C:\Work\Book.xlsx')</code> | Run after Excel COM launch; file exists |
| 483 | Get first Excel sheet | PS | <code>$sh = $wb.Worksheets.Item(1)</code> | Run after opening workbook |
| 484 | Write Excel cell | PS | <code>$sh.Range('A1').Value2 = 'Jarvis'</code> | Run after choosing worksheet |
| 485 | Read Excel cell | PS | <code>$sh.Range('A1').Text</code> | Run after choosing worksheet |
| 486 | Write Excel formula | PS | <code>$sh.Range('B1').Formula = '=SUM(C1:C10)'</code> | Run after choosing worksheet |
| 487 | Bold Excel cell | PS | <code>$sh.Range('A1').Font.Bold = $true</code> | Run after choosing worksheet |
| 488 | Save Excel as file | PS | <code>$wb.SaveAs('C:\Work\Output.xlsx')</code> | Run after opening workbook; may overwrite |
| 489 | Close Excel workbook | PS | <code>$wb.Close($false)</code> | Do this only after saving |
| 490 | Quit Excel | PS | <code>$xl.Quit()</code> | Run after closing workbook |
| 491 | Launch Word via COM | PS | <code>$word = New-Object -ComObject Word.Application; $word.Visible = $true; $doc = $word.Documents.Add()</code> | Desktop Word required |
| 492 | Add Word paragraph text | PS | <code>$doc.Content.InsertAfter('Hello from Jarvis')</code> | Run after creating doc |
| 493 | Export Word document to PDF | PS | <code>$doc.ExportAsFixedFormat('C:\Work\Report.pdf',17)</code> | Requires Word document open |


## Recommended implementation architecture

**Speech recognition → intent parser → allowlisted action registry → argument validation → user confirmation for risky changes → executor (native API / pywinauto / PowerShell / Playwright) → state verification → voice response.**

Do not assume a command completed solely because it returned successfully. Verify the expected window opened or the expected UI, file or system state changed. Avoid sending secrets to an external model, and consider dry-run previews for file mutations. The shortcuts in this document assume conventional app defaults; customizable shortcuts can differ.

## Reference material

- Microsoft PowerShell Start-Process: https://learn.microsoft.com/powershell/module/microsoft.powershell.management/start-process
- Microsoft Windows UI Automation: https://learn.microsoft.com/windows/win32/winauto/entry-uiauto-win32
- PyAutoGUI: https://pyautogui.readthedocs.io/
- Playwright locator API: https://playwright.dev/python/docs/locators
- VS Code default keys: https://code.visualstudio.com/docs/reference/default-keybindings
- Epic UE editor play/simulate: https://dev.epicgames.com/documentation/unreal-engine/playing-and-simulating-in-unreal-engine
- YouTube keyboard shortcuts: https://support.google.com/youtube/answer/7631406?hl=en
