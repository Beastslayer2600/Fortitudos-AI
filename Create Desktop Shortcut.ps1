# Creates Desktop "Fortitudo Desk" shortcut -> START_ALL.bat
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $root) { $root = "C:\Users\gertj\Fortitudos-AI" }

$bat = Join-Path $root "START_ALL.bat"
if (-not (Test-Path $bat)) {
  $bat = Join-Path $root "Start Fortitudo Desk.bat"
}
if (-not (Test-Path $bat)) {
  Write-Error "No START_ALL.bat or Start Fortitudo Desk.bat in $root"
}

$desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desktop "Fortitudo Desk.lnk"
$shell = New-Object -ComObject WScript.Shell
$lnk = $shell.CreateShortcut($lnkPath)
$lnk.TargetPath = $bat
$lnk.WorkingDirectory = $root
$lnk.WindowStyle = 1
$lnk.Description = "Start Fortitudo (UI + backend + Ollama)"
$lnk.Save()
Write-Host "Desktop shortcut created:"
Write-Host "  $lnkPath"
Write-Host "Target:"
Write-Host "  $bat"
