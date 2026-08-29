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

## Vercel
UI only. Ask / ingest / vault still need the home PC with Ollama.

iPhone: Safari → Add to Home Screen.
