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



def _who(handler, capability: str):
    """(user, why not) for this request. Identity comes from the credential.

    Kept here rather than on the handler so that a route added later has to go
    through the same two questions — who is this, and may they — instead of
    trusting whatever the body says about itself.
    """
    import desk_users
    peer = ""
    try:
        peer = str(handler.client_address[0])
    except Exception:
        peer = ""
    return desk_users.require(peer, handler.headers, capability)


def handle_get(handler, parts) -> bool:
    # The PDF workbench owns /api/pdf/*. It only ever reads a filed document
    # and writes a new draft; it cannot modify what it opens.
    import pdf_api
    if pdf_api.handle_get(handler, parts):
        return True
    if parts == ["api", "answers"]:
        import answer_log
        rep = answer_log.report(7)
        handler.send_json({
            "since": rep.since,
            "total": rep.total,
            "hours_saved": round(rep.hours_saved, 1),
            "by_room": rep.by_room,
            "verdicts": rep.verdicts,
            "unmarked": rep.unmarked,
            # None, not 0, when nothing has been judged. An unmeasured rate
            # is not a perfect one.
            "wrong_rate": rep.wrong_rate,
            "as_of_questions": rep.as_of_questions,
            "client_questions": rep.client_questions,
            "span_flagged": rep.span_flagged,
            "version_clash": rep.version_clash,
            "unapproved": rep.unapproved,
            "high_risk": rep.high_risk,
            "minutes_by_hand": answer_log.MINUTES_BY_HAND,
            "verdict_options": answer_log.VERDICTS,
            "recent": answer_log.recent(30),
        })
        return True

    if parts == ["api", "register"]:
        import doc_register
        docs = doc_register.register()
        handler.send_json({
            "mode": doc_register.mode(),
            "verdicts_note": ("In controlled mode an unapproved product "
                              "document is not indexed at all."),
            "documents": [{
                "source": d.source, "kind": d.kind, "pages": d.pages,
                "sha256": d.sha256, "origin": d.origin, "status": d.status,
                "approved": d.approved, "governed": d.governed,
                "approved_by": d.approved_by, "approved_at": d.approved_at,
                "note": d.note,
                # True only when an approval existed and the file then changed.
                # A document that was never approved is not the same problem.
                "lapsed": d.lapsed,
            } for d in docs],
            "awaiting_approval": [d.source for d in docs
                                  if d.governed and not d.approved],
        })
        return True

    if parts == ["api", "users"]:
        import desk_users
        # No tokens here, ever — only their hashes are stored, and a listing
        # that could hand them back would be worth stealing.
        handler.send_json({
            "directory": desk_users.any_users(),
            "roles": {r: sorted(c) for r, c in desk_users.CAPABILITIES.items()},
            "users": [{"id": u.id, "name": u.name, "role": u.role,
                       "active": u.active, "created_at": u.created_at,
                       "disabled_at": u.disabled_at, "note": u.note}
                      for u in desk_users.everyone()],
            "you": getattr(getattr(handler, "desk_user", None), "name", ""),
        })
        return True

    if len(parts) == 3 and parts[:2] == ["api", "answers"]:
        import answer_log
        try:
            row = answer_log.get(int(parts[2]))
        except ValueError:
            row = None
        handler.send_json(row or {"error": "No such answer."}, 200 if row else 404)
        return True

    if parts == ["api", "retention"]:
        import retention
        items = retention.due()
        handler.send_json({
            "basis": retention.RETENTION_BASIS,
            "years": retention.FAIS_RECORD_YEARS,
            # Ids only. A list of people due for erasure, holding their names,
            # would be its own POPIA problem.
            "due": [{"client_id": d.client_id, "status": d.status,
                     "expires_on": d.expires_on, "over_by_days": d.over_by_days}
                    for d in items],
            "nothing_is_automatic": True,
        })
        return True
    if len(parts) == 3 and parts[:2] == ["api", "retention"]:
        import retention
        s = retention.survey(parts[2])
        handler.send_json({
            "client_id": s.client_id, "exists": s.exists, "status": s.status,
            "files": len(s.files), "db_rows": s.db_rows,
            "total_db_rows": s.total_db_rows,
            "index_pages": s.index_pages, "log_rows": s.log_rows,
        })
        return True

    if parts == ["api", "identity"]:
        import identity as ident
        me = ident.load()
        # camelCase to match src/lib/identity.ts, which consumes this directly.
        handler.send_json({
            "adviserName": me.adviser_name, "fspName": me.fsp_name,
            "fspNumber": me.fsp_number, "practiceName": me.practice_name,
            "studioName": me.studio_name, "studioSite": me.studio_site,
            "studioEmail": me.studio_email, "contactPhone": me.contact_phone,
            "city": me.city, "sampleProduct": me.sample_product,
            "licenceLine": me.licence_line, "configured": me.configured,
            "missingForDocument": me.missing(),
        })
        return True

    if parts == ["api", "residency"]:
        import residency
        rep = residency.check()
        handler.send_json({
            "data_root": rep.data_root,
            "ok": rep.ok,
            "stores": [{"name": st.name, "kind": st.kind, "exists": st.exists,
                        "under_data_root": st.under_data_root,
                        "personal_data": st.holds_personal_data}
                       for st in rep.stores],
            # Paths are omitted deliberately: a directory listing of where the
            # client vault lives is not something to hand out over HTTP.
            "compute": [{"job": h.job, "local": h.local,
                         "carries_client_data": h.carries_client_data}
                        for h in rep.hops],
            "outbound": [{"host": e.host, "purpose": e.purpose,
                          "who_calls": e.who_calls} for e in rep.external],
            "findings": ([f"personal data outside the data root: {st.name}"
                          for st in rep.stray_stores]
                         + [f"work leaves this machine: {h.job}"
                            for h in rep.remote_hops]
                         + [f"unclassified external host: {e.host}"
                            for e in rep.unclassified]),
        })
        return True

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
    import pdf_api
    if pdf_api.handle_post(handler, parts, body):
        return True
    if parts == ["api", "answers", "mark"]:
        import answer_log
        try:
            ok = answer_log.mark(int(body.get("id") or 0),
                                 str(body.get("verdict") or ""),
                                 str(body.get("note") or ""))
        except ValueError as exc:
            handler.send_json({"error": str(exc),
                               "verdicts": answer_log.VERDICTS}, 400)
            return True
        handler.send_json({"ok": ok} if ok else {"error": "No such answer."},
                          200 if ok else 404)
        return True

    if parts == ["api", "register", "approve"]:
        import doc_register
        # The approver is taken from the credential, never from the body. A
        # name the caller supplies is a claim; the register's whole value is
        # that "who read this document" is a fact.
        user, why = _who(handler, "approve_documents")
        if user is None:
            handler.send_json({"error": why}, 403)
            return True
        ok, msg = doc_register.approve(
            str(body.get("source") or ""), user.name,
            str(body.get("sha256") or ""), str(body.get("origin") or ""),
            str(body.get("note") or ""))
        handler.send_json({"ok": ok, "message": msg}, 200 if ok else 400)
        return True
    if parts == ["api", "register", "withdraw"]:
        import doc_register
        user, why = _who(handler, "approve_documents")
        if user is None:
            handler.send_json({"error": why}, 403)
            return True
        ok, msg = doc_register.withdraw(
            str(body.get("source") or ""), user.name,
            str(body.get("reason") or ""))
        handler.send_json({"ok": ok, "message": msg}, 200 if ok else 400)
        return True

    if parts == ["api", "retention", "erase"]:
        import retention
        # Erasure is destructive and irreversible, so it takes the same
        # capability as approving a document and the same rule about names:
        # the eraser is whoever the credential says, not whoever the body says.
        user, why = _who(handler, "approve_documents")
        if user is None:
            handler.send_json({"error": why}, 403)
            return True
        # Over HTTP the dry run has to be asked out of, exactly as it does on
        # the command line. A missing field must not mean "destroy it".
        confirm = body.get("confirm") is True
        r = retention.erase(str(body.get("client_id") or ""), user.name,
                            str(body.get("reason") or ""), dry_run=not confirm)
        handler.send_json({
            "client_id": r.client_id, "dry_run": r.dry_run,
            "complete": r.complete, "files": r.files, "db_rows": r.db_rows,
            "index_pages": r.index_pages, "log_rows": r.log_rows,
            "problems": r.problems, "by": r.by,
        })
        return True

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
            "authored": out.get("authored", False),
            "author_notes": out.get("author_notes", []),
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
