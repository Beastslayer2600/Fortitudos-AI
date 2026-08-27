# Fortitudo

Local workspace for **South African financial advice**, **performance adjudication**, and **craft** tools.

**One launcher:** `Start Fortitudo Desk.bat`

- UI: http://localhost:8080  
- AI backend: http://127.0.0.1:8000  
- Ollama: local models only  

You remain responsible under FAIS for advice under your licence. The system is an evidence and drafting tool, not an FSP.

## Modules

| Module | What you use it for |
|--------|---------------------|
| **Advisor** | Product questions (cited pages), clients, notes, projections, ROA drafts |
| **Studio** | Speech & Drama / arts adjudication feedback |
| **Craft** | Local business craft workflows |

See `UNIFIED.md` for architecture. Merge desk UI from `lion-wolf-moss-shadow` and Craft from `Fortitudocraftstudio` into this repo as the single source of truth.

## First run

1. Install Node.js, Python 3, Ollama (`ollama pull llama3.2:3b` and `ollama pull bge-m3`)
2. Clone this repo
3. If you already have the full React desk elsewhere, copy its `src/`, `package.json`, and lockfile here (or pull from lion-wolf-moss-shadow)
4. `pip install -r backend/requirements.txt`
5. Double-click `Start Fortitudo Desk.bat`
6. Drop product PDFs into `backend/docs/` then `cd backend && python ingest.py`

## Sample product questions

- What percentage is paid for hearing loss in both ears of 90 decibels or more?
- Survival period on Living Lifestyle Protector?
- Waiting period options on Income Protector?

## Stack

React · TanStack · Tailwind · local Python RAG · Ollama  

**Fortitudo Studios** · fortitudostudios.site · WhatsApp +27 77 386 6299
