@echo off
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" setup_hermes.py
) else (
  py -3 setup_hermes.py
)
if errorlevel 1 pause
