"""Fortitudo AI local workflow app.

Run with ``python app.py`` and open http://127.0.0.1:8000.
Product-guide questions use Ollama. Client records stay on this machine.
"""
import argparse
import base64
import json
import os
import re
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import unquote, urlparse

import client_store
import expert_route
import rooms
import store
import versioning
import sort_engine
from ingest import extract_any
from retrieval import corpus_exclusions, search
from config import CHAT_MODEL, EMBED_MODEL, MAX_PAGE_CHARS, WEB_DIR, ROOT, DOCS_DIR
from llm import OllamaError, chat, has_model, health
import desk_extra
import ask as ask_mod

try:
    import pdfplumber  # noqa: F401
except ImportError:
    pdfplumber = None

HOST = "127.0.0.1"
PORT = 8000
MAX_BODY = 35 * 1024 * 1024

# The desk UI runs on :8080 and calls this server cross-origin. A wildcard
# would let any site the adviser has open read client files off the loopback
# backend, which has no login, so only the desk's own port is reflected back.
DESK_PORT = os.environ.get("FORTITUDO_DESK_PORT", "8080")
EXTRA_ORIGINS = {
    o.strip().rstrip("/")
    for o in os.environ.get("FORTITUDO_ALLOWED_ORIGINS", "").split(",")
    if o.strip()
}


def origin_allowed(origin: str) -> bool:
    """True for the desk UI on any host (LAN or Tailscale) plus explicit extras."""
    if not origin:
        return False
    origin = origin.rstrip("/")
    if origin in EXTRA_ORIGINS:
        return True
    parsed = urlparse(origin)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    return str(parsed.port or "") == DESK_PORT


def load_ui(filename: str) -> str:
    path = WEB_DIR / filename
    if not path.exists():
        return (
            "<!DOCTYPE html><html><body style='font-family:sans-serif;padding:2rem'>"
            f"<h1>Fortitudo AI</h1><p>UI file missing: <code>{path}</code></p>"
            "</body></html>"
        )
    return path.read_text(encoding="utf-8")


def projection(values):
    years = max(1, min(int(values.get("years", 5)), 60))
    lump = max(0.0, float(values.get("lump_sum", 0) or 0))
    monthly = max(0.0, float(values.get("monthly_contribution", 0) or 0))
    gross = float(values.get("gross_growth", 0) or 0) / 100
    fee = max(0.0, float(values.get("advice_fee", 0) or 0)) / 100
    gross_monthly = (1 + gross) ** (1 / 12) - 1
    net_monthly = ((1 + gross) / (1 + fee)) ** (1 / 12) - 1
    balance = lump
    gross_balance = lump
    rows = []
    total_contributions = lump
    total_fees = 0.0
    for month in range(1, years * 12 + 1):
        gross_balance = gross_balance * (1 + gross_monthly) + monthly
        before_fee = balance * (1 + gross_monthly) + monthly
        balance = balance * (1 + net_monthly) + monthly
        total_contributions += monthly
        total_fees += max(0.0, before_fee - balance)
        if month % 12 == 0:
            rows.append({
                "year": month // 12,
                "contributions": round(total_contributions, 2),
                "gross_value": round(gross_balance, 2),
                "net_value": round(balance, 2),
                "fees": round(total_fees, 2),
            })
    price = float(values.get("current_price", 0) or 0)
    units = float(values.get("units_held", 0) or 0)
    return {
        "inputs": {
            "years": years, "lump_sum": lump, "monthly_contribution": monthly,
            "gross_growth": gross * 100, "advice_fee": fee * 100,
            "fund_name": str(values.get("fund_name", "")).strip(),
            "current_price": price, "units_held": units,
        },
        "summary": {
            "total_contributions": round(total_contributions, 2),
            "projected_value": round(balance, 2),
            "gross_value": round(gross_balance, 2),
            "estimated_fees": round(total_fees, 2),
            "current_fund_value": round(price * units, 2),
        },
        "rows": rows,
    }


def client_source_text(client):
    pieces = []
    total = 0
    for doc in client["documents"]:
        if doc["doc_type"] == client_store.AI_DRAFT_TYPE:
            continue  # never let a draft become the source for the next one
        path = Path(doc["relative_path"])
        if not path.exists():
            continue
        try:
            for page_no, text in extract_any(path):
                if not text.strip():
                    continue
                if len(text) > MAX_PAGE_CHARS:
                    text = text[:MAX_PAGE_CHARS] + "... [TRUNCATED]"
                block = f"--- {doc['doc_type']} (Page {page_no}): {doc['filename']} ---\n{text.strip()}"
                pieces.append(block)
                total += len(block)
                if total >= 24000:
                    break
        except Exception as e:
            print(f"Error extracting {path}: {e}")
            continue
        if total >= 24000:
            break
    if not pieces:
        raise ValueError("No readable PDF, TXT or MD files are filed for this client.")
    return "\n\n".join(pieces)[:24000]


DRAFT_SYSTEM = """You prepare INTERNAL working drafts for a licensed South African financial adviser.
You are not the adviser and you do not provide advice to the end client.

Rules:
1. Use ONLY the supplied client document text. Never invent facts, figures, funds, dates, objectives, licence numbers or testimonials.
2. If information is missing, write [MISSING] in that section.
3. Professional, neutral language. South African English.
4. First line must be: INTERNAL DRAFT — ADVISER REVIEW REQUIRED.
5. Do not write as if advice has been approved or delivered.
6. Respect FAIS concepts without fabricating compliance content.
7. Where product mechanics are mentioned, leave [EVIDENCE: document, page]."""


def json_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    # A negative length would make rfile.read() block until the peer hangs up.
    if length < 0 or length > MAX_BODY:
        raise ValueError("Request is too large.")
    return json.loads(handler.rfile.read(length) or b"{}")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(fmt % args)

    def cors(self):
        origin = self.headers.get("Origin", "")
        self.send_header("Vary", "Origin")
        if origin_allowed(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Max-Age", "600")

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def send_json(self, payload, code=200):
        data = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.cors()
        self.end_headers()
        self.wfile.write(data)

    def send_html(self):
        data = load_ui("app.html").encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.cors()
        self.end_headers()
        self.wfile.write(data)

    def send_file(self, path: Path, content_type: str):
        if not path.exists() or not path.is_file():
            return self.send_json({"error": "Not found."}, 404)
        try:
            path.resolve().relative_to(ROOT.resolve())
        except ValueError:
            return self.send_json({"error": "Not found."}, 404)
        content = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.cors()
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        parts = [unquote(x) for x in urlparse(self.path).path.strip("/").split("/") if x]
        try:
            if desk_extra.handle_get(self, parts):
                return
            if not parts:
                return self.send_html()
            if parts[0] == "assets" and len(parts) == 2:
                name = parts[1]
                if name == "app.css":
                    return self.send_file(WEB_DIR / "app.css", "text/css; charset=utf-8")
                path = ROOT / "assets" / name
                ctype = "image/svg+xml" if name.endswith(".svg") else "application/octet-stream"
                return self.send_file(path, ctype)
            if parts == ["api", "status"]:
                conn = store.connect()
                try:
                    installed = health()
                    ok = has_model(installed, EMBED_MODEL) and has_model(installed, CHAT_MODEL)
                except OllamaError:
                    installed, ok = [], False
                return self.send_json({
                    "ok": ok,
                    "models": installed,
                    "chat_model": CHAT_MODEL,
                    "embed_model": EMBED_MODEL,
                    "sort_status": sort_engine.engine.last_status,
                    "drop_zone": str(sort_engine.DROP_ZONE),
                    "clients_indexed": sum(1 for n, c in store.sources(conn) if n.startswith("client:")),
                    "sources": [{"name": n, "pages": c} for n, c in store.sources(conn)],
                })
            if parts == ["api", "clients"]:
                return self.send_json(client_store.list_clients())
            if len(parts) == 3 and parts[:2] == ["api", "clients"]:
                client = client_store.get_client(parts[2])
                return self.send_json(client or {"error": "Client not found."}, 200 if client else 404)
            if len(parts) == 3 and parts[:2] == ["api", "documents"]:
                doc = client_store.get_document(parts[2])
                if not doc:
                    return self.send_json({"error": "Document not found."}, 404)
                path = Path(doc["relative_path"])
                # The stored path decides what gets read, so confirm it is still
                # inside the client vault before serving it.
                try:
                    path.resolve().relative_to(client_store.CLIENTS_DIR.resolve())
                except ValueError:
                    return self.send_json({"error": "Document not found."}, 404)
                if not path.exists():
                    return self.send_json({"error": "File missing on disk."}, 404)
                ctype = doc.get("content_type") or "application/octet-stream"
                if ctype == "application/octet-stream":
                    if str(path).lower().endswith(".pdf"):
                        ctype = "application/pdf"
                    elif str(path).lower().endswith(".txt"):
                        ctype = "text/plain"
                    elif str(path).lower().endswith(".md"):
                        ctype = "text/markdown"
                content = path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(content)))
                self.cors()
                self.end_headers()
                self.wfile.write(content)
                return
            return self.send_json({"error": "Not found."}, 404)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 500)

    def do_POST(self):
        parts = [unquote(x) for x in urlparse(self.path).path.strip("/").split("/") if x]
        try:
            body = json_body(self)
            if desk_extra.handle_post(self, parts, body):
                return
            if parts == ["api", "clients"]:
                cid = client_store.create_client(body.get("name", ""), body.get("email", ""), body.get("phone", ""))
                return self.send_json({"id": cid})
            if len(parts) == 4 and parts[:2] == ["api", "clients"]:
                cid, action = parts[2], parts[3]
                if action == "documents":
                    raw = base64.b64decode(body.get("content_base64", ""), validate=True)
                    if not raw or len(raw) > 25 * 1024 * 1024:
                        raise ValueError("Choose a document smaller than 25 MB.")
                    relative = client_store.add_document(
                        cid, body.get("filename"), raw,
                        body.get("doc_type", "Other"), body.get("content_type", ""),
                    )
                    return self.send_json({"path": relative})
                if action == "notes":
                    client_store.add_note(cid, body.get("note_type"), body.get("title", ""), body.get("content", ""))
                    return self.send_json({"ok": True})
                if action == "emails":
                    client_store.add_email(
                        cid, body.get("direction", "outgoing"), body.get("sender", ""),
                        body.get("recipient", ""), body.get("subject", ""), body.get("body", ""),
                        body.get("status", "Draft"),
                    )
                    return self.send_json({"ok": True})
                if action == "projections":
                    client_store.add_projection(
                        cid, body.get("name", "Projection scenario"),
                        body.get("inputs", {}), body.get("summary", {}),
                    )
                    return self.send_json({"ok": True})
                if action == "drafts":
                    client = client_store.get_client(cid)
                    if not client:
                        raise ValueError("Client not found.")
                    draft_type = str(body.get("draft_type", "Advice summary"))
                    if draft_type in ("Website mockup", "Client website mockup"):
                        brief = str(body.get("brief", "")).strip()
                        # Client side of the desk: practice storefront only.
                        # A trade shop is a Craft lead, not an advice client, and
                        # the filed documents are not consulted at all — the page
                        # is written from the brief.
                        import mockup_router

                        if not brief:
                            raise ValueError(
                                "Give a brief for the page (shop facts, or "
                                "'Fortitudo Wealth practice storefront'). "
                                "The page is never generated from the FNA."
                            )
                        html = mockup_router.generate_for_client(
                            client.get("name") or cid, "", extra_brief=brief,
                        )
                        filename = "website_mockup.html"
                        path = client_store.add_generated_file(cid, filename, html)
                        client_store.add_note(
                            cid, "AI draft", "Website mockup (internal)",
                            "Generated from the brief only. Open website_mockup.html in a browser.",
                        )
                        return self.send_json({
                            "draft": html,
                            "path": path,
                            "format": "html",
                            "message": "Mockup saved from the brief, not the FNA.",
                        })

                    source = client_source_text(client)
                    instructions = {
                        "Advice summary": "Create an internal summary of the client's circumstances, objectives, information gaps and issues requiring adviser confirmation.",
                        "ROA structure": "Create an INTERNAL Record of Advice working draft. Label top: INTERNAL DRAFT — ADVISER REVIEW REQUIRED. Never invent product figures. Use [MISSING] freely.",
                        "Follow-up": "Create a concise internal follow-up list. Do not invent dates.",
                        "Evidence Pack": "Generate a technical supplement that explains mechanics from the files only.",
                        "Technical Post": "Transform one technical finding into a draft post. No invented figures.",
                    }.get(draft_type, "Create an internal adviser working summary.")
                    prompt = f"Client documents:\n\n{source}\n\n---\nDraft type: {draft_type}\n{instructions}"
                    draft = chat(DRAFT_SYSTEM, prompt)
                    # Drafting is roa work and was the one generated output with
                    # no check on it: a figure the client file does not support
                    # went straight into a Record of Advice, and the banner was
                    # only ever an instruction in the prompt.
                    draft, _flagged = versioning.span_check(draft, source)
                    banner = rooms.get_room("roa").draft_banner
                    if banner and not draft.lstrip().startswith(banner.strip()):
                        draft = banner + draft
                    filename = f"{draft_type.lower().replace(' ', '_')}_draft.md"
                    path = client_store.add_generated_file(cid, filename, draft)
                    client_store.add_note(cid, "AI draft", f"{draft_type} (internal draft)", draft)
                    return self.send_json({"draft": draft, "path": path})
                if action == "meeting-prep":
                    return self.send_json(client_store.meeting_prep(cid))
            if parts == ["api", "route"]:
                route = expert_route.classify(
                    str(body.get("question", "")), hinted_room=str(body.get("room", "")),
                )
                return self.send_json({
                    "room": route.room, "why": route.why, "standard": route.standard,
                    "refuse": route.refuse, "tools": route.tools,
                })
            if parts == ["api", "ask"]:
                question = str(body.get("question", "")).strip()
                if not question or len(question) > 2000:
                    raise ValueError("Enter a question up to 2,000 characters.")
                hinted = str(body.get("room") or "")
                route = expert_route.classify(question, hinted_room=hinted)
                conn = store.connect()
                excerpt = ""
                client_id = str(body.get("client_id") or "").strip()
                if client_id:
                    client = client_store.get_client(client_id)
                    if not client:
                        raise ValueError("Client not found.")
                    try:
                        excerpt = client_source_text(client)
                    except ValueError:
                        excerpt = ""  # nothing readable filed yet — answer without it

                room, why = route.room, route.why
                # Selecting a client makes this a client-aware job, and fa is not
                # a client-aware room. Only promote when the desk did not choose.
                if excerpt and room == "fa" and not hinted:
                    room, why = "roa", why + "; client attached"
                spec = rooms.get_room(room)
                if not spec.include_clients:
                    excerpt = ""

                if body.get("show_only"):
                    results = search(conn, question, as_of=versioning.parse_as_of(question),
                                     exclude_prefixes=corpus_exclusions(room))
                    return self.send_json({"show_only": True, "room": room, "pages": [
                        {"source": r[0][1], "page": r[0][2], "score": round(r[1], 3),
                         "snippet": r[0][3][:1500]} for r in results
                    ], "sources": [
                        {"source": r[0][1], "page": r[0][2], "score": round(r[1], 3)} for r in results
                    ]})

                # Same path as the CLI: history rewriting, the room's own standard
                # and refusal, the client-file block, and the span check that
                # strips a figure the retrieved pages do not support.
                history = body.get("history") if isinstance(body.get("history"), list) else []
                text, results = ask_mod.answer(
                    conn, question, history=history, client_excerpt=excerpt, room=room,
                )
                return self.send_json({
                    "answer": text,
                    "room": room,
                    "why": why,
                    "standard": route.standard,
                    "refuse": route.refuse,
                    "used_client_files": bool(excerpt),
                    "sources": [
                        {"source": r[0][1], "page": r[0][2], "score": round(r[1], 3)}
                        for r in results
                    ],
                })
            return self.send_json({"error": "Not found."}, 404)
        except (ValueError, json.JSONDecodeError) as exc:
            return self.send_json({"error": str(exc)}, 400)
        except OllamaError as exc:
            return self.send_json({"error": str(exc)}, 503)
        except Exception as exc:
            return self.send_json({"error": str(exc)}, 503)


def main():
    global PORT
    ap = argparse.ArgumentParser(description="Fortitudo AI local workspace")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--host", default=HOST)
    args = ap.parse_args()
    PORT = args.port

    sort_engine.engine.start()
    server = ThreadingHTTPServer((args.host, PORT), Handler)
    print(f"Fortitudo AI running at http://{args.host}:{PORT}")
    print(f"Chat model: {CHAT_MODEL}  |  Embed: {EMBED_MODEL}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        sort_engine.engine.stop()
        server.server_close()


if __name__ == "__main__":
    main()
