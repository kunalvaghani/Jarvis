@echo off
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m scripts.setup.setup_gmail
pause
