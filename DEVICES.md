# Phone, laptop, office PC — one desk

The app is one product. Client files stay on your machine. The UI can travel.

## Same Wi-Fi
Start Fortitudo Desk.bat on the PC. The UI binds 0.0.0.0:8080, so the phone
reaches it at http://<PC-LAN-IP>:8080.

The backend binds 127.0.0.1:8000 — the launcher passes `--host 127.0.0.1` — so
the phone cannot reach it until you start it for the LAN:

```bat
cd backend
python app.py --host 0.0.0.0 --port 8000
```

Then on Learn, set Home backend to http://<PC-LAN-IP>:8000.

**:8000 has no login.** Anything that can reach it can read every client file.
Bind it to the LAN only on a network you trust, and stop it when you are done.

## Away from the office
Use Tailscale (or similar). Do not publish port 8000 on the public internet.
Phone opens http://<tailscale-name>:8080 and points Home backend at :8000 on
that node — again started with `--host 0.0.0.0` so the tunnel can reach it.

## Where things are saved

Nothing a client touches is written inside the repo.

| What | Where | Committed |
|---|---|---|
| Client vault, drop zone, drama records | `FORTITUDO_DATA_ROOT` (Windows: `C:\FortitudoData`) | never |
| Model-written drafts and client photos | that client's `99_AI_Drafts/` | never |
| Product guides and lessons | `backend/docs/` | lessons yes, PDFs no |
| Sight photos and their extracts | `backend/docs/learn/shots/`, `.../sight/` | never |
| Search and consent databases | `backend/data/` | never |

`99_AI_Drafts/` is the quarantine: `ingest_clients` skips it, so nothing the
model wrote can come back as evidence in an answer or a later draft.

## Vercel
UI only. Ask / ingest / vault still need the home PC with Ollama.

iPhone: Safari → Add to Home Screen.
