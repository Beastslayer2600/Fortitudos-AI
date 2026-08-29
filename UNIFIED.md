# Fortitudo — one project (Fortitudos-AI)

Everything runs from this repository. One launcher. Three modules in one desk.

## Launch

```bat
Start Fortitudo Desk.bat
```

| Surface | URL | Role |
|---------|-----|------|
| **Desk UI** | http://localhost:8080 | React app (Ask, Clients, Studio, Craft) |
| **AI backend** | http://127.0.0.1:8000 | Python RAG: product guides, clients |
| **Ollama** | http://127.0.0.1:11434 | Local models |

## Modules

1. **Advisor** — product questions with page citations, client vault, ROA drafts
2. **Studio (Drama)** — adjudication companion
3. **Craft** — local shop book, mock page, walk-in pack (`/craft`)

Craft is in this repo: `src/craft/CraftApp.tsx` plus `src/lib/craft.ts`.

## Routing

`backend/expert_route.py` classifies the job, `backend/rooms.py` says what that
room may read, and `backend/crossover.py` refuses work that belongs elsewhere —
Craft may edit the practice storefront, never a client file. See `FA_CHAT.md`.
