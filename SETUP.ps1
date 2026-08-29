# SETUP.ps1 — first run on a new PC.
#
# Clones or updates the repo, then installs Node and Python dependencies.
# The desk, Craft and the backend all live in this repository now, so nothing
# is copied in from other clones.

$ErrorActionPreference = "Stop"
$Root = if ($env:FORTITUDO_ROOT) { $env:FORTITUDO_ROOT } else { "C:\Users\$env:USERNAME\Fortitudos-AI" }

if (-not (Test-Path $Root)) {
  git clone https://github.com/Beastslayer2600/Fortitudos-AI.git $Root
}
Set-Location $Root
git pull origin main

Write-Host "Installing Node dependencies..."
npm install

if (Test-Path (Join-Path $Root "backend\requirements.txt")) {
  Write-Host "Installing Python dependencies..."
  pip install -r (Join-Path $Root "backend\requirements.txt")
}

Write-Host ""
Write-Host "Models (once):"
Write-Host "  ollama pull llama3.2:3b"
Write-Host "  ollama pull bge-m3"
Write-Host ""
Write-Host "Done. Launch:"
Write-Host "  cd $Root"
Write-Host "  .\Start Fortitudo Desk.bat"
Write-Host ""
Write-Host "Then open http://localhost:8080 and http://localhost:8080/craft"
