"""HTTP extras: Learn, Sight, Craft pages, consent."""
from __future__ import annotations

import base64
import os
import re
from pathlib import Path

from config import DOCS_DIR, LOCAL_BASE, MOCKS_DIR, PUBLIC_BASE

MOCK_DIR = MOCKS_DIR
SHELF_SUFFIXES = {".pdf", ".md", ".txt"}
MAX_GUIDE_BYTES = 25 * 1024 * 1024
DESK_BUILD = "wire3-2026-08-29"


def _slug(name: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", (name or "page").lower()).strip("-")
    return (s or "page")[:60]


def public_base() -> str:
    return PUBLIC_BASE


def _is_public(url: str) -> bool:
    u = (url or "").lower()
    return u.startswith("http") and "127.0.0.1" not in u and "localhost" not in u


def list_learn_docs():
    files = []
    if DOCS_DIR.exists():
        for pth in sorted(DOCS_DIR.rglob("*")):
            if pth.is_file() and pth.suffix.lower() in {".pdf", ".md", ".txt"}:
                files.append({
                    "name": pth.relative_to(DOCS_DIR).as_posix(),
                    "kind": "guide",
                    "bytes": pth.stat().st_size,
                })
    return files


def handle_get(handler, parts) -> bool:
    if parts == ["api", "build"]:
        handler.send_json({"desk_build": DESK_BUILD, "public_base": public_base() or None})
        return True
    if parts[:2] == ["api", "learn"] and len(parts) == 2:
        import store
        conn = store.connect()
        handler.send_json({
            "docs": list_learn_docs(),
            "sources": [{"name": n, "pages": c} for n, c in store.sources(conn)],
            "desk_build": DESK_BUILD,
            "how": [
                "Teach a rule and tag the room: craft, advisor, voice, drama.",
                "Craft lessons feed the design reasoner.",
                "Advisor lessons must not invent figures.",
            ],
        })
        return True
    if parts == ["api", "learn", "self"]:
        handler.send_json({
            "enabled": False,
            "interval_hours": 0,
            "last": None,
            "curriculum": [],
            "note": "Self-learn is off. Use Teach and tag the room.",
        })
        return True
    if parts == ["api", "learn", "discover"]:
        docs = {d["name"] for d in list_learn_docs()}
        catalog = [
            {"id": "craft-doctrine", "branch": "craft", "title": "Craft design doctrine", "why": "First screen + Call", "url": "", "ask": ""},
            {"id": "storefront", "branch": "craft", "title": "Practice storefront", "why": "Wealth site is Craft + wealth renderer", "url": "", "ask": ""},
        ]
        gaps = [{
            "id": item["id"],
            "title": item["title"],
            "branch": item["branch"],
            "have": any(item["title"].split()[0].lower() in n.lower() for n in docs),
        } for item in catalog]
        handler.send_json({"catalog": catalog, "gaps": gaps, "rule": "File lessons per room."})
        return True
    if len(parts) == 2 and parts[0] == "m":
        raw = parts[1]
        flyer = raw.endswith("-flyer")
        slug = _slug(raw[:-6] if flyer else raw)
        path = MOCK_DIR / (f"{slug}-flyer.html" if flyer else f"{slug}.html")
        if not path.exists():
            handler.send_json({"error": "No mock for that slug. POST /api/craft/page first."}, 404)
            return True
        html = path.read_bytes()
        handler.send_response(200)
        handler.cors()
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(html)))
        handler.end_headers()
        handler.wfile.write(html)
        return True
    return False


def handle_post(handler, parts, body) -> bool:
    if parts == ["api", "learn", "teach"]:
        from learn_teach import file_lesson
        title = str(body.get("title") or "Lesson").strip()
        text = str(body.get("text") or "").strip()
        applies = str(body.get("applies") or "craft").strip().lower()
        if applies not in {"craft", "advisor", "voice", "drama", "all"}:
            applies = "craft"
        if not text and not body.get("research"):
            raise ValueError("Paste the rule to file.")
        path = file_lesson(title, text or title, applies)
        handler.send_json({"ok": True, "pages": 1, "source": str(path), "researched": None})
        return True
    if parts == ["api", "learn", "self"]:
        handler.send_json({"ok": False, "errors": ["Self-learn is off. Use Teach."]})
        return True
    if parts == ["api", "sight"]:
        import sight
        out = sight.ingest_sight(
            str(body.get("image_base64") or ""),
            str(body.get("filename") or "shot.png"),
            str(body.get("caption") or ""),
            str(body.get("intent") or "chat"),
            str(body.get("client_id") or ""),
        )
        handler.send_json(out)
        return True
    if parts == ["api", "ingest", "paste"]:
        from learn_teach import file_lesson
        path = file_lesson(str(body.get("title") or "Paste"), str(body.get("text") or ""), "all")
        handler.send_json({"ok": True, "pages": 1, "source": str(path), "branches": ["all"]})
        return True
    if parts == ["api", "ingest", "guides"]:
        import ingest, store
        name = str(body.get("filename") or "guide.md")
        # Only the shelf's own file kinds, and only under DOCS_DIR: an
        # unsanitised topic is a directory name, so "../.." would escape it.
        if Path(name).suffix.lower() not in SHELF_SUFFIXES:
            raise ValueError("Guides must be PDF, TXT or MD.")
        raw = base64.b64decode(body.get("content_base64") or b"", validate=False)
        if not raw or len(raw) > MAX_GUIDE_BYTES:
            raise ValueError("Choose a guide smaller than 25 MB.")
        topic = _slug(str(body.get("topic") or "misc"))
        dest = DOCS_DIR / topic
        dest.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(name).name)
        path = dest / safe
        path.write_bytes(raw)
        pages = ingest.ingest_file(store.connect(), path, rebuild=False, source_name=f"guide:{topic}:{safe}")
        handler.send_json({"ok": True, "pages": pages or 1, "topic": topic, "source": str(path)})
        return True
    if parts == ["api", "craft", "page"]:
        import mockup_router
        name = str(body.get("name") or "Shop").strip()
        facts = str(body.get("facts") or body.get("brief") or "").strip()
        city = str(body.get("city") or "Kempton Park").strip()
        public = str(body.get("url") or public_base()).strip()
        MOCK_DIR.mkdir(parents=True, exist_ok=True)
        slug = _slug(name)
        if _is_public(public):
            mock_url = public.rstrip("/")
            if not mock_url.endswith(slug):
                mock_url = mock_url + "/m/" + slug
        else:
            mock_url = f"{LOCAL_BASE}/m/{slug}"
        # Craft leads and advice clients never share a record; the router refuses
        # a brief carrying client-file language.
        out = mockup_router.generate_for_lead(name, facts, city=city, mock_url=mock_url)
        (MOCK_DIR / f"{slug}.html").write_text(out["page"], encoding="utf-8")
        (MOCK_DIR / f"{slug}-flyer.html").write_text(out["flyer"], encoding="utf-8")
        (MOCK_DIR / f"{slug}-spec.json").write_text(
            __import__("json").dumps(out["spec"], indent=2), encoding="utf-8"
        )
        printable = _is_public(mock_url)
        handler.send_json({
            "ok": True,
            "desk_build": DESK_BUILD,
            "slug": slug,
            "path": f"/m/{slug}",
            "flyer": f"/m/{slug}-flyer",
            "qr_url": mock_url,
            "qr_printable": printable,
            "spec": out["spec"],
            "missing": out["missing"],
            "note": (
                "QR is public — safe to print."
                if printable
                else "Do not print this QR. Set FORTITUDO_PUBLIC_BASE=https://your-host and pass url, then reprint."
            ),
        })
        return True
    if parts == ["api", "consent"]:
        import consent
        ident = str(body.get("identifier") or "").strip()
        action = str(body.get("action") or "check").strip()
        if action == "asked":
            consent.mark_asked(ident)
        elif action == "consented":
            consent.mark_consented(ident)
        elif action == "refused":
            consent.mark_refused(ident)
        elif action == "customer":
            consent.mark_customer(ident)
        decision = consent.may_contact(ident)
        handler.send_json({
            "identifier": consent.normalise(ident),
            "allowed": decision.allowed,
            "kind": decision.kind,
            "reason": decision.reason,
            "state": consent.state_of(ident),
        })
        return True
    return False
