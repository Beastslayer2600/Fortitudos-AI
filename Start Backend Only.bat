@echo off
cd /d "%~dp0backend"
where python >nul 2>&1 && set PYTHON=python || set PYTHON=py
echo Fortitudo AI backend — http://127.0.0.1:8000
%PYTHON% app.py --host 127.0.0.1 --port 8000
pause
