@echo off
REM One shortcut: sync from GitHub, then start the desk on the LAN / Tailscale.
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "package.json" (
  echo Put this file in the Fortitudos-AI folder.
  pause
  exit /b 1
)

if exist ".git" (
  echo Syncing from GitHub...
  git pull origin main
  if errorlevel 1 (
    echo Pull failed. Starting the copy you already have.
  )
)

where node >nul 2>&1
if errorlevel 1 (
  echo Node.js is not on PATH. Install from https://nodejs.org
  pause
  exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 (
    echo Python 3 is not on PATH.
    pause
    exit /b 1
  )
  set "PYTHON=py"
) else (
  set "PYTHON=python"
)

if not exist "node_modules\" (
  echo First run: npm install...
  call npm install
  if errorlevel 1 (
    pause
    exit /b 1
  )
)

set "OLLAMA_HOST=http://127.0.0.1:11434"
if not defined OLLAMA_MODEL set OLLAMA_MODEL=llama3.2:3b

where ollama >nul 2>&1
if not errorlevel 1 (
  curl -sf http://127.0.0.1:11434/api/tags >nul 2>&1
  if errorlevel 1 (
    echo Starting Ollama...
    start "" /min ollama serve
    timeout /t 2 /nobreak >nul
  )
)

if exist "backend\app.py" (
  echo Backend on http://0.0.0.0:8000
  start "Fortitudo Backend" /min cmd /c "cd /d ""%~dp0backend"" && %PYTHON% app.py --host 0.0.0.0 --port 8000"
  timeout /t 1 /nobreak >nul
)

echo UI http://localhost:8080  Backend http://THIS-PC:8000
start "" "http://localhost:8080"
call npm run dev
pause
