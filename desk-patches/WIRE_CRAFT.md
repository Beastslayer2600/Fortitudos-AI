# Wire /craft into the desk

1. tsconfig paths: `"@craft/*": ["./integrations/craft/src/*"]`
2. Vite alias: `@craft` -> `integrations/craft/src`
3. Copy `desk-patches/craft.tsx` to `src/routes/craft.tsx`
4. Copy `desk-patches/CraftApp.tsx` to `src/craft/CraftApp.tsx`
5. Add Craft link on home nav
6. Restart Start Fortitudo Desk.bat — open http://localhost:8080/craft
