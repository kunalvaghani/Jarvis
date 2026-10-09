@echo off
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m scripts.setup.setup_hermes
) else (
  py -3 -m scripts.setup.setup_hermes
)
if errorlevel 1 pause
