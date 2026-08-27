# SETUP.ps1 — Build Fortitudos-AI as the single repo from your existing clones
# Run once on the PC after cloning Fortitudos-AI.

$ErrorActionPreference = "Stop"
$Root = "C:\Users\gertj\Fortitudos-AI"
$Desk = "C:\Users\gertj\lion-wolf-moss-shadow"
$Craft = "C:\Users\gertj\Fortitudocraftstudio"

if (-not (Test-Path $Root)) {
  git clone https://github.com/Beastslayer2600/Fortitudos-AI.git $Root
}
Set-Location $Root
git pull origin main

# Bring full React desk from lion-wolf if present
if (Test-Path $Desk) {
  Write-Host "Merging desk UI from lion-wolf-moss-shadow..."
  foreach ($name in @("src","public","scripts","server","package.json","package-lock.json","vite.config.ts","tsconfig.json","eslint.config.mjs","startup.sh")) {
    $src = Join-Path $Desk $name
    if (Test-Path $src) {
      Copy-Item -Recurse -Force $src $Root
      Write-Host "  + $name"
    }
  }
} else {
  Write-Host "Desk clone not found at $Desk — clone lion-wolf-moss-shadow first for full UI."
}

# Craft
if (-not (Test-Path $Craft)) {
  git clone https://github.com/Beastslayer2600/Fortitudocraftstudio.git $Craft
}
New-Item -ItemType Directory -Force -Path (Join-Path $Root "integrations\craft") | Out-Null
Copy-Item -Recurse -Force (Join-Path $Craft "src") (Join-Path $Root "integrations\craft\src")
Write-Host "  + integrations/craft/src"

# Wire craft route if desk src exists
$routes = Join-Path $Root "src\routes"
if (Test-Path $routes) {
  Copy-Item -Force (Join-Path $Root "desk-patches\craft.tsx") (Join-Path $routes "craft.tsx") -ErrorAction SilentlyContinue
  New-Item -ItemType Directory -Force -Path (Join-Path $Root "src\craft") | Out-Null
  if (Test-Path (Join-Path $Root "desk-patches\CraftApp.tsx")) {
    Copy-Item -Force (Join-Path $Root "desk-patches\CraftApp.tsx") (Join-Path $Root "src\craft\CraftApp.tsx")
  }
}

# Backend deps
if (Test-Path (Join-Path $Root "backend\requirements.txt")) {
  pip install -r (Join-Path $Root "backend\requirements.txt")
}

Write-Host ""
Write-Host "Done. Launch:"
Write-Host "  cd $Root"
Write-Host "  .\Start Fortitudo Desk.bat"
Write-Host ""
Write-Host "Then open http://localhost:8080 and http://localhost:8080/craft"
