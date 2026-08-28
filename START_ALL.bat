@echo off
setlocal EnableExtensions EnableDelayedExpansion
title Fortitudo — starting all services
cd /d "%~dp0"

echo.
echo  ============================================================
echo   FORTITUDO — one-click start
echo  ============================================================
echo.

REM ---------- Python ----------
set "PYTHON="
where python >nul 2>&1 && set "PYTHON=python"
if not defined PYTHON where py >nul 2>&1 && set "PYTHON=py"
if not defined PYTHON (
  echo  [ERROR] Python not found on PATH.
  echo  Install Python 3 and tick "Add to PATH", then try again.
  pause
  exit /b 1
)

REM ---------- Node ----------
where node >nul 2>&1
if errorlevel 1 (
  echo  [ERROR] Node.js not found on PATH.
  echo  Install from https://nodejs.org
  pause
  exit /b 1
)

if not exist "package.json" (
  echo  [ERROR] package.json missing. Run this from the Fortitudos-AI folder.
  pause
  exit /b 1
)

if not exist "node_modules\" (
  echo  Installing npm packages first time...
  call npm install
  if errorlevel 1 (
    echo  npm install failed.
    pause
    exit /b 1
  )
)

REM ---------- Free ports 8080 and 8000 (old instances) ----------
echo  Freeing ports 8080 and 8000 if busy...
for %%P in (8080 8000) do (
  for /f "tokens=5" %%A in ('netstat -ano ^| findstr ":%%P" ^| findstr "LISTENING"') do (
    echo  Stopping PID %%A on port %%P
    taskkill /F /PID %%A >nul 2>&1
  )
)
timeout /t 1 /nobreak >nul

REM ---------- Ollama ----------
set "OLLAMA_HOST=http://127.0.0.1:11434"
if not defined OLLAMA_MODEL set "OLLAMA_MODEL=llama3.2:3b"

where ollama >nul 2>&1
if not errorlevel 1 (
  curl -sf http://127.0.0.1:11434/api/tags >nul 2>&1
  if errorlevel 1 (
    echo  Starting Ollama...
    start "Ollama" /min cmd /c "ollama serve"
    timeout /t 3 /nobreak >nul
  ) else (
    echo  Ollama already running.
  )
) else (
  echo  [WARN] ollama not on PATH — install Ollama for local AI.
)

REM ---------- Backend ----------
if not exist "backend\app.py" (
  echo  [WARN] backend\app.py missing — UI will start without Python API.
  goto :ui
)

echo  Checking backend Python packages...
%PYTHON% -c "import pdfplumber,numpy,requests" >nul 2>&1
if errorlevel 1 (
  echo  Installing backend requirements...
  if exist "backend\requirements.txt" (
    %PYTHON% -m pip install -r backend\requirements.txt
  ) else (
    %PYTHON% -m pip install pdfplumber numpy requests PyYAML
  )
)

echo  Starting AI backend on http://127.0.0.1:8000 ...
start "Fortitudo Backend" cmd /c "cd /d ""%~dp0backend"" && %PYTHON% app.py --host 127.0.0.1 --port 8000 & echo. & echo Backend stopped. & pause"
timeout /t 2 /nobreak >nul

:ui
echo.
echo  ============================================================
echo   UI:       http://localhost:8080
echo   Backend:  http://127.0.0.1:8000
echo   Ollama:   %OLLAMA_HOST%  model %OLLAMA_MODEL%
echo  ============================================================
echo   Leave this window open. Ctrl+C stops the UI.
echo   Backend runs in the "Fortitudo Backend" window.
echo  ============================================================
echo.

start "" "http://localhost:8080"
call npm run dev
echo.
echo  UI stopped.
pause
