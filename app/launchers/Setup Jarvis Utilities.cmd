@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo Run Setup Jarvis first to create the main Python environment.
  exit /b 1
)
if not exist ".venv-skills\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m venv .venv-skills
  if errorlevel 1 exit /b 1
)
".venv-skills\Scripts\python.exe" -m pip --isolated install -r requirements/skills.txt
if errorlevel 1 exit /b 1
echo Utility Python dependencies installed. Docker and Tesseract are separate prerequisites.
echo Follow docs\utility-skills.md and revalidate before enabling any capability.
