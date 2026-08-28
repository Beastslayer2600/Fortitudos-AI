@echo off
cd /d "%~dp0"
echo Pulling Fortitudos-AI from GitHub...
git pull origin main
if errorlevel 1 (
  echo Pull failed. Fix git, then run this again.
  pause
  exit /b 1
)
if exist "Start Fortitudo Desk.bat" (
  call "Start Fortitudo Desk.bat"
) else (
  echo Start Fortitudo Desk.bat missing after pull.
  pause
)
