# Live desk wiring

The browser talks to `python app.py`. That process now uses:

- `ask.answer` + room doctrine + span-check for `/api/ask`
- `mockup_router` for website drafts (brief only — not the FNA)
- `learn_teach.file_lesson` for `/api/learn/teach`
- `design_reason` for `/api/craft/page` then `/m/{slug}`
- `consent.may_contact` for `/api/consent`
- `sight.ingest_sight` for `/api/sight`

```bat
cd backend
python app.py --host 127.0.0.1 --port 8000
python -m unittest test_expert_route test_design_reason test_trade_page test_versioning
```

Craft page:

```
POST /api/craft/page  {"name":"Joe Plumbing","city":"Kempton Park","facts":"geyser 011 …"}
GET  /m/joe-plumbing
```

Print the flyer only when `/m/joe-plumbing` is on a public host, not localhost.
