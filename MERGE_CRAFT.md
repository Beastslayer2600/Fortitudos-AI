# Merge Craft into Fortitudos-AI

```powershell
cd C:\Users\gertj
git clone https://github.com/Beastslayer2600/Fortitudocraftstudio.git Fortitudocraftstudio
cd Fortitudos-AI   # or lion-wolf-moss-shadow until fully migrated
New-Item -ItemType Directory -Force -Path integrations\craft | Out-Null
Copy-Item -Recurse -Force ..\Fortitudocraftstudio\src integrations\craft\
```

Then follow `desk-patches/WIRE_CRAFT.md`.
