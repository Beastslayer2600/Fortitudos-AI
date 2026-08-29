"""Fortitudo AI local workflow app.

Run with ``python app.py`` and open http://127.0.0.1:8000.
Product-guide questions use Ollama. Client records, files and projections
remain on this machine and are kept separate from the product index.
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
import store
import sort_engine
from ingest import extract_any
from retrieval import build_context, search
from config import CHAT_MODEL, EMBED_MODEL, SYSTEM_PROMPT, MAX_PAGE_CHARS, WEB_DIR, ROOT, DOCS_DIR
from llm import OllamaError, chat, has_model, health
import website_mockup

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
            "<p>Create <code>web/app.html</code> or reinstall the workspace.</p></body></html>"
        )
    return path.read_text(encoding="utf-8")


def projection(values):
    """Project end-of-month contributions with an annual advisory fee."""
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
    """Extract a bounded amount of text from the client's filed documents."""
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
6. Respect FAIS concepts: FNA, Record of Advice elements, FICA/CDD, suitability and disclosure — without fabricating compliance content.
7. Where product mechanics are mentioned, leave [EVIDENCE: document, page] for the adviser to complete from technical guides."""


SHELF_SUFFIXES = {".pdf", ".md", ".txt"}

LEARN_HOW = [
    "Tell it a topic and paste the rules in your own words.",
    "Drop product PDFs on Files — they are indexed page by page.",
    "Client documents are filed on the client, never on this shelf.",
]

BRANCH_PURPOSE = {
    "craft": "Design and local-marketing lessons for the Craft desk.",
    "advisor": "Product and FAIS practice lessons behind Advisor answers.",
    "voice": "Tone and phrasing rules for drafted copy.",
    "drama": "Adjudication craft for the Studio desk.",
    "all": "Lessons every desk should see.",
}

# This desk answers from filed pages. Generating unsourced material into the
# index is the one thing FA_CHAT.md rules out, so self-teaching stays off and
# says so rather than quietly doing nothing.
SELF_LEARN_NOTE = (
    "Self-teaching is off. This desk answers from filed pages, so it will not "
    "write unsourced material into the index. File a lesson under Tell it, or "
    "drop a guide under Files."
)

RESEARCH_NOTE = (
    "Filed as you wrote it. Advisor does not research a lesson for itself — "
    "an answer it cited later would be its own words, not a filed page."
)

# Advisor answers under FAIS, so it retrieves only what a person filed. These
# prefixes are written by the model (Craft's design lessons, Sight's reading of
# a photo); they stay available to their own rooms and out of /api/ask.
MACHINE_WRITTEN_SOURCES = ("learn:craft:", "learn:sight:")


def shelf_files():
    """Everything on the product and lesson shelf, straight off disk."""
    files = []
    if DOCS_DIR.exists():
        for path in sorted(DOCS_DIR.rglob("*")):
            if path.is_file() and path.suffix.lower() in SHELF_SUFFIXES:
                rel = path.relative_to(DOCS_DIR).as_posix()
                files.append({
                    "name": rel,
                    "kind": "lesson" if rel.startswith("learn/") else "guide",
                    "bytes": path.stat().st_size,
                })
    return files


def branch_shelves():
    """Per-room lesson counts, used to show which shelves are still empty."""
    import learn_teach

    rows = []
    for branch, folder in learn_teach.BRANCH_DIR.items():
        count = len(list(folder.glob("*.md"))) if folder.exists() else 0
        rows.append({
            "id": f"learn-{branch}",
            "branch": branch,
            "title": f"{branch.title()} lessons",
            "why": BRANCH_PURPOSE.get(branch, ""),
            "count": count,
            "have": count > 0,
        })
    return rows


def json_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length > MAX_BODY:
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
        # Prevent path traversal: only serve from ROOT
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
            if parts == ["api", "learn"]:
                conn = store.connect()
                return self.send_json({
                    "docs": shelf_files(),
                    "sources": [{"name": n, "pages": c} for n, c in store.sources(conn)],
                    "how": LEARN_HOW,
                })
            if parts == ["api", "learn", "self"]:
                return self.send_json({
                    "enabled": False,
                    "interval_hours": 0,
                    "last": None,
                    "curriculum": [
                        {"id": row["id"], "title": row["title"], "why": row["why"]}
                        for row in branch_shelves() if not row["have"]
                    ],
                    "note": SELF_LEARN_NOTE,
                })
            if parts == ["api", "learn", "discover"]:
                shelves = branch_shelves()
                return self.send_json({
                    "catalog": [
                        {
                            "id": row["id"], "branch": row["branch"], "title": row["title"],
                            "why": row["why"], "url": "", "ask": f"Teach me {row['branch']}: ",
                        }
                        for row in shelves
                    ],
                    "gaps": [
                        {"id": row["id"], "title": row["title"], "branch": row["branch"], "have": row["have"]}
                        for row in shelves
                    ],
                    "rule": "Shelves are read off disk. Nothing here is researched for you.",
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
                    source = client_source_text(client)

                    # Website mockup: structured HTML via dedicated generator
                    if draft_type in ("Website mockup", "Client website mockup"):
                        brief = str(body.get("brief", "")).strip()
                        html = website_mockup.generate_from_client_documents(
                            client.get("name") or cid, source, extra_brief=brief,
                        )
                        filename = "website_mockup.html"
                        path = client_store.add_generated_file(cid, filename, html, "Other")
                        client_store.add_note(
                            cid, "AI draft", "Website mockup (internal)",
                            "Generated HTML mockup saved as website_mockup.html. Open the file in a browser for preview.",
                        )
                        return self.send_json({
                            "draft": html,
                            "path": path,
                            "format": "html",
                            "message": "Mockup HTML saved to the client folder. Open website_mockup.html in a browser.",
                        })

                    instructions = {
                        "Advice summary": "Create an internal summary of the client's circumstances, objectives, information gaps and issues requiring adviser confirmation. Focus on identifying missing context for advice.",
                        "ROA structure": "Create an INTERNAL Record of Advice working draft aligned to FAIS practice (not client-facing). Sections: (1) Summary of information on which advice is based — circumstances, needs, objectives from filed documents only; (2) Products / options considered; (3) Product(s) recommended and specific reasons linked to stated needs; (4) Material risks, limitations, waiting/survival periods and definitions with [EVIDENCE: document, page] placeholders; (5) Costs, fees and charges — [MISSING] if not in files; (6) Replacement comparison if a replacement is implied — else state N/A; (7) Outstanding FICA / documents / information still required; (8) Adviser confirmation checklist. Label top: INTERNAL DRAFT — ADVISER REVIEW REQUIRED. Never invent product figures. Use [MISSING] freely.",
                        "Follow-up": "Create a concise internal follow-up list for the adviser and client. List missing documents (FICA, RPQ, etc.), specific questions for the client, and proposed next actions. Do not invent dates.",
                        "Evidence Pack": "Generate a client-facing 'Evidence Pack' draft. This should not be a letter, but a technical supplement that explains the specific mechanics of the proposed benefits (e.g., survival periods, waiting periods, definition of severity). Use clear, professional language that builds trust through technical transparency.",
                        "Technical Post": "Transform a technical finding from the client documents into a draft LinkedIn or blog post. Focus on one specific technical nuance (e.g., waiting periods, exclusions, or specific benefit wording). Structure: 1. Hook (The problem), 2. The Nuance (The technical detail), 3. The Solution (Structure over emotion). Avoid generic advice; keep it technical and authoritative.",
                    }.get(draft_type, "Create an internal adviser working summary.")
                    prompt = f"Client documents:\n\n{source}\n\n---\nDraft type: {draft_type}\n{instructions}"
                    draft = chat(DRAFT_SYSTEM, prompt)
                    filename = f"{draft_type.lower().replace(' ', '_')}_draft.md"
                    path = client_store.add_generated_file(
                        cid, filename, draft,
                        "Advice Report" if draft_type == "ROA structure" else "Other",
                    )
                    client_store.add_note(cid, "AI draft", f"{draft_type} (internal draft)", draft)
                    return self.send_json({"draft": draft, "path": path})
                if action == "meeting-prep":
                    return self.send_json(client_store.meeting_prep(cid))
            if parts == ["api", "learn", "self"]:
                return self.send_json({"ok": False, "errors": [SELF_LEARN_NOTE]})
            if parts == ["api", "learn", "teach"]:
                import learn_teach
                title = str(body.get("title", "")).strip() or "Lesson"
                text = str(body.get("text", "")).strip()
                if not text:
                    raise ValueError("Paste what it should learn. This desk does not invent the lesson for you.")
                applies = str(body.get("applies", "") or "all")
                path = learn_teach.file_lesson(title, text, applies)
                conn = store.connect()
                pages = dict(store.sources(conn)).get(f"learn:{applies}:{path.name}", 0)
                return self.send_json({
                    "ok": True, "pages": pages, "source": path.name,
                    "researched": None, "note": RESEARCH_NOTE if body.get("research") else "",
                })
            if parts == ["api", "ingest", "paste"]:
                import learn_teach
                title = str(body.get("title", "")).strip() or "Note"
                text = str(body.get("text", "")).strip()
                if not text:
                    raise ValueError("Paste some text to file.")
                path = learn_teach.file_lesson(title, text, "all")
                conn = store.connect()
                pages = dict(store.sources(conn)).get(f"learn:all:{path.name}", 0)
                return self.send_json({
                    "ok": True, "pages": pages, "source": path.name,
                    "branches": ["advisor", "drama", "craft"],
                })
            if parts == ["api", "ingest", "guides"]:
                import ingest
                filename = str(body.get("filename", "")).strip()
                if not filename:
                    raise ValueError("Give the guide a filename.")
                suffix = Path(filename).suffix.lower()
                if suffix not in SHELF_SUFFIXES:
                    raise ValueError("Guides must be PDF, TXT or MD.")
                raw = base64.b64decode(body.get("content_base64", ""), validate=True)
                if not raw or len(raw) > 25 * 1024 * 1024:
                    raise ValueError("Choose a guide smaller than 25 MB.")
                topic = re.sub(r"[^a-z0-9]+", "-", str(body.get("topic", "misc")).lower()).strip("-") or "misc"
                safe = Path(filename).name
                dest = DOCS_DIR / "learn" / topic / safe
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(raw)
                source = f"learn:{topic}:{safe}"
                pages = ingest.ingest_file(store.connect(), dest, rebuild=False, source_name=source)
                return self.send_json({"ok": True, "pages": pages, "topic": topic, "source": source})
            if parts == ["api", "sight"]:
                import sight
                image = str(body.get("image_base64", ""))
                if not image:
                    raise ValueError("Attach an image.")
                return self.send_json(sight.ingest_sight(
                    image,
                    str(body.get("filename", "shot.png")),
                    str(body.get("caption", "")),
                    str(body.get("intent", "chat")),
                    str(body.get("client_id", "")),
                ))
            if parts == ["api", "ingest", "clients"]:
                import ingest
                client_store.sync_from_disk()
                conn = store.connect()
                count = ingest.ingest_clients(conn, rebuild=body.get("rebuild", False))
                return self.send_json({"ok": True, "pages": count})
            if parts == ["api", "projection"]:
                return self.send_json(projection(body))
            if parts == ["api", "ask"]:
                question = str(body.get("question", "")).strip()
                if not question or len(question) > 2000:
                    raise ValueError("Enter a question up to 2,000 characters.")
                conn = store.connect()
                results = search(conn, question, exclude_prefixes=MACHINE_WRITTEN_SOURCES)
                if not results:
                    return self.send_json({
                        "answer": "Nothing is indexed yet. Run `python ingest.py` first.",
                        "sources": [],
                    })
                if body.get("show_only"):
                    pages = []
                    for (rid, source, page, text, _emb), score in results:
                        pages.append({
                            "source": source,
                            "page": page,
                            "score": round(score, 3),
                            "snippet": text[:1500],
                        })
                    return self.send_json({"show_only": True, "pages": pages, "sources": [
                        {"source": r[0][1], "page": r[0][2], "score": round(r[1], 3)} for r in results
                    ]})
                context = build_context(results)
                prompt = (
                    f"Document extracts:\n\n{context}\n\n---\n\nAdviser's question: {question}\n\n"
                    "Answer from the extracts above, citing document and page for every figure. "
                    "If the answer is not in the extracts, say so."
                )
                answer = chat(SYSTEM_PROMPT, prompt)
                return self.send_json({
                    "answer": answer,
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
    ap.add_argument("--port", type=int, default=PORT, help="HTTP port (default 8000)")
    ap.add_argument("--host", default=HOST, help="Bind address (default 127.0.0.1)")
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
