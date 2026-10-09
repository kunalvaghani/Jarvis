@echo off
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\setup\setup.ps1"
if errorlevel 1 (
  echo.
  echo Setup did not finish. When your connection is stable, run this file again.
) else (
  echo.
  echo Whisper GPU is ready. Open Start Jarvis.cmd.
)
pause
