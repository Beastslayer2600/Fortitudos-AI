# GitHub is the source of the app

Repo: https://github.com/Beastslayer2600/Fortitudos-AI
Branch: `main`

The app lives here. Client PDFs and the local index stay on the home PC.

## Update every machine

1. Change lands on `main`.
2. GitHub Actions runs `.github/workflows/ci.yml`.
3. Vercel rebuilds the desk UI from `main`.
4. On the home PC: `Update Fortitudo Desk.bat` (git pull + start).

Phone opens the running desk (LAN / Tailscale) or the Vercel UI with Home backend pointed at the PC.

## Never commit
backend/data/, backend/docs/clients/, live identity shots, .env, keys.
