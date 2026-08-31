# CORS between the desk (:8080) and the backend (:8000)

`app.py` answers `OPTIONS` and sends `Access-Control-Allow-Origin`, so the desk
UI can call the backend cross-origin.

The header is **not** a wildcard. `:8000` has no login, so a wildcard would let
any site the adviser has open read client files off the loopback backend. The
origin is reflected only when it is the desk: any host, on port 8080.

- Other port on the same host → refused
- `https://anything-else.com` → refused
- Phone at `http://192.168.1.20:8080` → allowed

## Overrides

| Variable | Effect |
|---|---|
| `FORTITUDO_DESK_PORT` | Serve the desk on a port other than 8080 |
| `FORTITUDO_ALLOWED_ORIGINS` | Comma-separated extra origins, matched exactly |

## "Failed to fetch" on Learn

1. Use http://localhost:8080, not the Vercel URL.
2. Home backend = http://127.0.0.1:8000
3. Open http://127.0.0.1:8000/api/status in the same browser — you must see JSON.
4. Open http://127.0.0.1:8000/api/build. If that 404s, the "Fortitudo Backend"
   window is running code from before the Learn routes and this CORS handler
   existed. Close it and start it again from this folder — `START_ALL.bat` frees
   port 8000 first, so it does this for you.
5. If the desk is on a non-standard port, set `FORTITUDO_DESK_PORT` to match and
   restart `python app.py`.

A stale backend fails in two ways that look like a CORS bug but are not: the
preflight `OPTIONS` comes back **501** (no `do_OPTIONS` in that older build) and
`/api/learn` comes back **404**. Restarting fixes both.
