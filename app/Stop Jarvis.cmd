@echo off
cd /d "%~dp0"
if exist "%~dp0.venv\Scripts\pythonw.exe" (
  start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0jarvis_bootstrap.py" --stop
) else (
  start "" pyw -3 "%~dp0jarvis_bootstrap.py" --stop
)
exit /b
