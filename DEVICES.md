# Phone, laptop, office PC — one desk

The app is one product. Client files stay on your machine. The UI can travel.

## Same Wi-Fi
Start Fortitudo Desk.bat on the PC (binds 0.0.0.0:8080).
Phone: http://<PC-LAN-IP>:8080
On Learn, set Home backend to http://<PC-LAN-IP>:8000

## Away from the office
Use Tailscale (or similar). Do not publish port 8000 on the public internet.
Phone opens http://<tailscale-name>:8080 and points Home backend at :8000 on that node.

## Vercel
UI only. Ask / ingest / vault still need the home PC with Ollama.

iPhone: Safari → Add to Home Screen.
