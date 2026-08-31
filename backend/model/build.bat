@echo off
REM Build the Fortitudo model into Ollama. Run from the repo root.
setlocal EnableExtensions
cd /d "%~dp0..\.."

where ollama >nul 2>&1
if errorlevel 1 (
  echo Ollama is not installed or not on PATH.
  pause
  exit /b 1
)

if "%FORTITUDO_BASE_MODEL%"=="" set FORTITUDO_BASE_MODEL=llama3.2:3b
echo Pulling base model %FORTITUDO_BASE_MODEL% ...
ollama pull %FORTITUDO_BASE_MODEL%
if errorlevel 1 (
  echo Could not pull %FORTITUDO_BASE_MODEL%.
  pause
  exit /b 1
)

echo Building fortitudo ...
ollama create fortitudo -f backend\model\Modelfile
if errorlevel 1 (
  echo Build failed.
  pause
  exit /b 1
)

echo.
echo Done. "fortitudo" is now an Ollama model:
ollama list | findstr /i fortitudo
echo.
echo Point the desk at it with:  set FORTITUDO_CHAT_MODEL=fortitudo
pause
