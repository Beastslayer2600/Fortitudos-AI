# Live desk wiring

The browser talks to `python app.py`. That process now uses:

- `ask.answer` + room doctrine + span-check for `/api/ask`
- `mockup_router` for website drafts (brief only — not the FNA)
- `learn_teach.file_lesson` for `/api/learn/teach`
- `mockup_router.generate_for_lead` (which refuses a client-file brief)
  then `design_reason` for `/api/craft/page`, served at `/m/{slug}`
  and `/m/{slug}-flyer`
- `consent.may_contact` for `/api/consent`
- `sight.ingest_sight` for `/api/sight`

```bat
cd backend
python app.py --host 127.0.0.1 --port 8000
python -m pytest -q          # the whole backend suite
```

Craft page:

```
POST /api/craft/page  {"name":"Joe Plumbing","city":"Kempton Park","facts":"geyser 011 …"}
GET  /m/joe-plumbing
```

Set `FORTITUDO_PUBLIC_BASE` to a host a phone can reach. Until you do, the
flyer prints no QR at all and says so — a dead QR is worse than none.

Do not expose port 8000 to serve `/m/`: the whole API, client vault included,
has no login. Proxy only `/m/`, or copy the files out of `backend/data/mocks`.
