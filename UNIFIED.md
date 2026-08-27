# Fortitudo — one project (Fortitudos-AI)

Everything runs from this repository. One launcher. Three modules in one desk.

## Launch

```bat
Start Fortitudo Desk.bat
```

| Surface | URL | Role |
|---------|-----|------|
| **Desk UI** | http://localhost:8080 | React app (Ask, Clients, Studio, Craft) |
| **AI backend** | http://127.0.0.1:8000 | Python RAG: product guides, clients, mockups |
| **Ollama** | http://127.0.0.1:11434 | Local models |

## Modules

1. **Advisor** — product questions with page citations, client vault, ROA drafts
2. **Studio (Drama)** — adjudication companion
3. **Craft** — local business craft / outreach

## Day-to-day index

```bat
cd backend
python ingest.py
```

Incremental only. Full rebuild: `python ingest.py --rebuild`

## Related private repos (merge sources)

- https://github.com/Beastslayer2600/lion-wolf-moss-shadow — desk UI
- https://github.com/Beastslayer2600/Fortitudocraftstudio — Craft module

Copy desk `src/` and Craft into this repo; see `MERGE_CRAFT.md` and `desk-patches/`.
