# One app. One startup.

Double-click **`Start Fortitudo Desk.bat`**. That is the only launcher.

It starts:

| Process | Address | Role |
|---------|---------|------|
| Desk UI | http://localhost:8080 | Everything you click |
| FA backend | http://127.0.0.1:8000 | Index, clients, ingest, drafts |
| Ollama | http://127.0.0.1:11434 | Local model |

Do not open the old Python `app.html` in a second window. Use the desk.

## Do this inside the desk

- **Learn & ingest** (`/learn`) — drop product PDFs; re-index client files
- **Drop zone** — paste or drop a file, file it to a client
- **Clients** — vault, notes, drafts, meeting prep
- **Ask / Chat** — questions against the index + selected client files
- **Library** — read indexed pages
- **Craft** — shop job: Jobs → Audit → 3D → Page → Send
- **Social Studio** — posts
- **Adjudication** — studio marks

No separate Grok URL for the shop mock. No second bat file for day-to-day work.
