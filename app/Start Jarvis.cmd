@echo off
cd /d "%~dp0"
rem Supervisor tracks the actual interpreter and rechecks interrupted goals after a crash.
if exist "%~dp0.venv\Scripts\pythonw.exe" (
  start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0jarvis_bootstrap.py"
) else (
  start "" pyw -3 "%~dp0jarvis_bootstrap.py"
)
exit /b
