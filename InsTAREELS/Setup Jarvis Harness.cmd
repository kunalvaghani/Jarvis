@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" setup_harness.py --enable
) else (
  python setup_harness.py --enable
)
if errorlevel 1 pause
