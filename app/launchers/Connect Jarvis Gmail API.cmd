@echo off
cd /d "%~dp0.."
".venv\Scripts\python.exe" -m pip install -r requirements/gmail.txt
if errorlevel 1 goto end
".venv\Scripts\python.exe" -m scripts.setup.connect_gmail_api %*
:end
pause
