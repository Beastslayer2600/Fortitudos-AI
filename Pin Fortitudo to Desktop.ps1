$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$bat = Join-Path $here "Fortitudo Desk.bat"
$desktop = [Environment]::GetFolderPath("Desktop")
$lnkPath = Join-Path $desktop "Fortitudo Desk.lnk"
$w = New-Object -ComObject WScript.Shell
$lnk = $w.CreateShortcut($lnkPath)
$lnk.TargetPath = $bat
$lnk.WorkingDirectory = $here
$lnk.WindowStyle = 1
$lnk.Description = "Sync from GitHub, then open Fortitudo Desk"
$lnk.Save()
Write-Host "Shortcut: $lnkPath"
Write-Host "Target: $bat"
