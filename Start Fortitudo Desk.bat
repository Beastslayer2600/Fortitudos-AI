@echo off
REM Fortitudo Desk — ONE workspace: UI + local AI backend + Ollama
setlocal EnableExtensions
cd /d "%~dp0"

if not exist "package.json" (
  echo This file must live in the Fortitudos-AI folder.
  pause
  exit /b 1
)

where node >nul 2>&1
if errorlevel 1 (
  echo Node.js is not installed or not on PATH.
  echo Install from https://nodejs.org and try again.
  pause
  exit /b 1
)

where python >nul 2>&1
if errorlevel 1 (
  where py >nul 2>&1
  if errorlevel 1 (
    echo Python not found. Install Python 3 and add it to PATH.
    pause
    exit /b 1
  )
  set "PYTHON=py"
) else (
  set "PYTHON=python"
)

if not exist "node_modules\" (
  echo Installing Node dependencies first time...
  call npm install
  if errorlevel 1 (
    echo npm install failed.
    pause
    exit /b 1
  )
)

set "OLLAMA_HOST=http://127.0.0.1:11434"
if not defined OLLAMA_MODEL set OLLAMA_MODEL=llama3.2:3b
if not defined FORTITUDO_LLM set FORTITUDO_LLM=auto

REM --- Ollama (already running is fine) ---
where ollama >nul 2>&1
if not errorlevel 1 (
  curl -sf http://127.0.0.1:11434/api/tags >nul 2>&1
  if errorlevel 1 (
    echo Starting Ollama...
    start "" /min ollama serve
    timeout /t 2 /nobreak >nul
  )
)

REM --- Python FA backend (Ask / index / clients) on :8000 ---
if exist "backend\app.py" (
  echo Starting Fortitudo AI backend on http://127.0.0.1:8000 ...
  start "Fortitudo Backend" /min cmd /c "cd /d ""%~dp0backend"" && %PYTHON% app.py --host 127.0.0.1 --port 8000"
  timeout /t 1 /nobreak >nul
)

echo.
echo ============================================================
echo  Fortitudo Desk  —  single workspace
echo ============================================================
echo  UI (this app):     http://localhost:8080
echo  AI backend:        http://127.0.0.1:8000
echo  Ollama:            %OLLAMA_HOST%  model %OLLAMA_MODEL%
echo.
echo  Modules: Advisor Ask · Clients · Studio (Drama) · Craft
echo  Press Ctrl+C in this window to stop the UI.
echo  Backend runs in a separate minimized window.
echo ============================================================
echo.

start "" "http://localhost:8080"
call npm run dev
pause
