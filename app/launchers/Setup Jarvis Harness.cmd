@echo off
cd /d "%~dp0.."
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m scripts.setup.setup_harness --enable
) else (
  python -m scripts.setup.setup_harness --enable
)
if errorlevel 1 pause
