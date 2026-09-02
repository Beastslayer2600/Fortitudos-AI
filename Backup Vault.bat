@echo off
REM Back up the Fortitudo client vault, then verify the backup.
REM
REM Pass the destination, or set FORTITUDO_BACKUP_DIR once:
REM     "Backup Vault.bat" E:\FortitudoBackup
REM
REM The destination holds client data in the clear. Keep it on an encrypted
REM drive (BitLocker), and never on the same disk as the vault.
setlocal EnableExtensions
cd /d "%~dp0"

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

set "DEST=%~1"
if "%DEST%"=="" set "DEST=%FORTITUDO_BACKUP_DIR%"
if "%DEST%"=="" (
  echo.
  echo Where should the backup go?
  echo   "Backup Vault.bat" E:\FortitudoBackup
  echo.
  echo Or set it once, then just double-click this file:
  echo   setx FORTITUDO_BACKUP_DIR "E:\FortitudoBackup"
  echo.
  pause
  exit /b 2
)

echo Backing up the client vault to %DEST% ...
%PYTHON% backend\vault_backup.py --to "%DEST%"
if errorlevel 1 (
  echo.
  echo THE BACKUP DID NOT VERIFY. Do not rely on it. Read the messages above.
  pause
  exit /b 1
)

echo.
echo Done, and verified.
echo Test a restore now and then - a backup nobody has restored is a guess:
echo   %PYTHON% backend\vault_backup.py --restore "%DEST%" --into "%TEMP%\vaultcheck"
pause
