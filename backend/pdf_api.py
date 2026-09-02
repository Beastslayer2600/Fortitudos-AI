"""HTTP surface for the PDF workbench.

Every route here reads a filed client document and writes a NEW file. None of
them can modify the document they read: pdf_tools returns bytes and
client_store.add_generated_bytes only ever writes to 99_AI_Drafts. The
original is the signed record and stays that way.

Routes:
  GET  /api/pdf/<doc_id>            what the document is — pages, text, fields
  POST /api/pdf/<doc_id>/fill       fill AcroForm fields
  POST /api/pdf/<doc_id>/annotate   add comments
  POST /api/pdf/<doc_id>/redact     genuinely remove text
  POST /api/pdf/<doc_id>/assemble   select / rotate pages
  POST /api/pdf/<doc_id>/stamp      overlay a banner or reference
  POST /api/pdf/<doc_id>/extract    write an editable markdown draft
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import parse_qs, urlparse

import client_store
import pdf_tools


class DocError(ValueError):
    """A document that cannot be worked on, with a reason worth showing."""


class WrongClient(DocError):
    """The document belongs to someone else. Never a 'did you mean'."""


def load(doc_id: str, for_client: str = "") -> Tuple[dict, bytes]:
    """Fetch a filed document's bytes, refusing anything outside the vault.

    The stored path decides what gets read, so it is checked against the vault
    root before any read — a document row is not a licence to open a file.

    `for_client` is the caller saying which client it believes this is. A
    mismatch is refused. The workbench UI only ever lists the open client's
    documents, but the chat agent names a document by id from a sentence, and
    a wrong or invented id would otherwise reach into another client's file.
    Anything that can name an id must say whose it is.
    """
    doc = client_store.get_document(doc_id)
    if not doc:
        raise DocError("Document not found.")
    if for_client and str(doc.get("client_id") or "") != str(for_client):
        # Deliberately the same wording as "not found": confirming that a
        # document exists but belongs to someone else is itself a leak.
        raise WrongClient("Document not found.")
    path = Path(doc["relative_path"])
    try:
        path.resolve().relative_to(client_store.CLIENTS_DIR.resolve())
    except ValueError:
        raise DocError("Document not found.")
    if not path.exists():
        raise DocError("The file is missing on disk.")
    if path.suffix.lower() != ".pdf":
        raise DocError(f"{path.name} is not a PDF.")
    return doc, path.read_bytes()


def _stamped_name(original: str, suffix: str, ext: str = ".pdf") -> str:
    stem = Path(original or "document").stem
    when = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return f"{stem} ({suffix} {when}){ext}"


def _save(doc: dict, data: bytes, suffix: str, ctype="application/pdf") -> dict:
    ext = ".md" if ctype.startswith("text/") else ".pdf"
    name = _stamped_name(doc.get("filename", ""), suffix, ext)
    if ext == ".md":
        path = client_store.add_generated_file(doc["client_id"], name, data.decode("utf-8"))
    else:
        path = client_store.add_generated_bytes(doc["client_id"], name, data, ctype)
    return {
        "ok": True,
        "saved_as": name,
        "path": str(path),
        "folder": client_store.AI_DRAFT_FOLDER,
        "doc_type": client_store.AI_DRAFT_TYPE,
        "original_untouched": doc.get("filename", ""),
        "note": (
            "Saved as a new draft. The original is unchanged — a filed client "
            "document is the signed record and is never edited in place."
        ),
    }


def describe(doc_id: str, for_client: str = "") -> dict:
    """Everything the desk needs to show the document and reason about it."""
    doc, data = load(doc_id, for_client)
    pages = pdf_tools.read_pages(data)
    fields = pdf_tools.form_fields(data)
    scanned = all(p.blank for p in pages)
    ocr_ok, ocr_why = pdf_tools.ocr_available()
    return {
        "id": doc_id,
        "filename": doc.get("filename", ""),
        "client_id": doc.get("client_id", ""),
        "doc_type": doc.get("doc_type", ""),
        "page_count": len(pages),
        "scanned": scanned,
        "pages": [{"page": p.number, "text": p.text} for p in pages],
        "fields": [
            {"name": f.name, "kind": f.kind, "value": f.value,
             "options": f.options, "required": f.required}
            for f in fields
        ],
        "ocr": {"available": ocr_ok, "why": ocr_why},
        "can": {
            # Say up front what this particular document supports, rather than
            # offering an action that will fail on it. A scan can be read and
            # redacted too, but only once an OCR engine is installed.
            "fill": bool(fields),
            "redact": (not scanned) or ocr_ok,
            "annotate": True,
            "assemble": True,
            "stamp": True,
            "extract": (not scanned) or ocr_ok,
        },
        "why": (
            ("No text in this file — it is a scan. It will be read by OCR, "
             "which is a guess at a picture, so check every figure. Redaction "
             "blanks the pixels and rebuilds the page as an image."
             if ocr_ok else
             "No text in this file — it is a scan, and no OCR engine is "
             "installed, so it can only be annotated, stamped and reordered. "
             + ocr_why)
            if scanned else ""
        ),
    }


def _client_scope(handler) -> str:
    """?client_id=... from the request. The handler only splits the path, so
    the query has to be read here rather than assumed onto it."""
    try:
        query = parse_qs(urlparse(handler.path).query)
    except Exception:
        return ""
    values = query.get("client_id") or []
    return str(values[0]) if values else ""


def handle_get(handler, parts) -> bool:
    if len(parts) == 3 and parts[:2] == ["api", "pdf"]:
        try:
            handler.send_json(describe(parts[2], _client_scope(handler)))
        except DocError as exc:
            handler.send_json({"error": str(exc)}, 404)
        return True
    return False


def handle_post(handler, parts, body) -> bool:
    if len(parts) != 4 or parts[:2] != ["api", "pdf"]:
        return False
    doc_id, action = parts[2], parts[3]
    try:
        doc, data = load(doc_id, str(body.get("client_id") or ""))
    except DocError as exc:
        handler.send_json({"error": str(exc)}, 404)
        return True

    try:
        if action == "fill":
            out, missing = pdf_tools.fill_form(data, dict(body.get("values") or {}))
            result = _save(doc, out, "filled")
            result["unknown_fields"] = missing
            if missing:
                result["warning"] = (
                    "These field names are not in this form and were not "
                    "written: " + ", ".join(missing)
                )
            handler.send_json(result)
            return True

        if action == "annotate":
            notes = [
                pdf_tools.Note(
                    page=int(n.get("page") or 1),
                    text=str(n.get("text") or ""),
                    title=str(n.get("title") or "Fortitudo AI"),
                )
                for n in (body.get("notes") or [])
                if str(n.get("text") or "").strip()
            ]
            if not notes:
                handler.send_json({"error": "No note text given."}, 400)
                return True
            handler.send_json(_save(doc, pdf_tools.annotate(data, notes), "annotated"))
            return True

        if action == "redact":
            literals = [str(x) for x in (body.get("literals") or [])]
            patterns = [str(x) for x in (body.get("patterns") or [])]
            if pdf_tools.is_scanned(data):
                # A scan's content is pixels, so removing text from a content
                # stream would do nothing and report success. Blank the pixels
                # instead — and say so, because the result is a flattened image.
                ok, why = pdf_tools.ocr_available()
                if not ok:
                    handler.send_json({"error": (
                        "This is a scan, so redaction has to remove pixels, "
                        "which needs OCR to find them. " + why), "scanned": True}, 400)
                    return True
                regions = pdf_tools.suggest_redactions(
                    data, patterns=patterns, literals=literals)
                if not regions:
                    handler.send_json({
                        "ok": False, "removed": [], "scanned": True,
                        "error": "OCR found nothing matching on this scan. "
                                 "Check the exact text, or the scan may be too "
                                 "poor to read.",
                    }, 400)
                    return True
                out, notes = pdf_tools.redact_regions(data, regions)
                result = _save(doc, out, "redacted")
                result["removed"] = sorted({r.label for r in regions})
                result["scanned"] = True
                result["notes"] = notes
                result["note"] += (
                    " This was a scan, so the pixels were blanked and the page "
                    "rebuilt as an image. The removal was re-read to confirm it. "
                    "The ORIGINAL still contains everything."
                )
                handler.send_json(result)
                return True
            out, removed = pdf_tools.redact(
                data, literals=literals, patterns=patterns,
            )
            if not removed:
                handler.send_json({
                    "ok": False,
                    "removed": [],
                    "error": "Nothing matched, so no redacted copy was written. "
                             "Check the exact text, or pick a pattern.",
                }, 400)
                return True
            result = _save(doc, out, "redacted")
            result["removed"] = removed
            result["note"] += (
                " The removed text is gone from the new file's content, not "
                "covered over — but the ORIGINAL still contains it."
            )
            handler.send_json(result)
            return True

        if action == "assemble":
            out = data
            select = str(body.get("select") or "").strip()
            degrees = int(body.get("rotate") or 0)
            if select:
                out = pdf_tools.select_pages(out, select)
            if degrees:
                out = pdf_tools.rotate_pages(out, str(body.get("rotate_pages") or ""), degrees)
            if out is data:
                handler.send_json({"error": "Nothing to do — give select or rotate."}, 400)
                return True
            handler.send_json(_save(doc, out, "pages"))
            return True

        if action == "stamp":
            text = str(body.get("text") or "").strip()
            if not text:
                handler.send_json({"error": "No stamp text given."}, 400)
                return True
            out = pdf_tools.stamp(
                data, text,
                where=str(body.get("where") or "top"),
                pages=str(body.get("pages") or ""),
            )
            handler.send_json(_save(doc, out, "stamped"))
            return True

        if action == "extract":
            if pdf_tools.is_scanned(data):
                ok, why = pdf_tools.ocr_available()
                if not ok:
                    handler.send_json({"error": (
                        "This is a scan with no text to extract. " + why),
                        "scanned": True}, 400)
                    return True
                pages = pdf_tools.ocr_pages(data)
                md = pdf_tools.ocr_markdown(pages, doc.get("filename", ""))
                result = _save(doc, md.encode("utf-8"), "ocr draft", "text/markdown")
                result["scanned"] = True
                result["ocr"] = True
                result["lowest_confidence"] = round(
                    min((p.worst for p in pages if p.lines), default=0.0), 2)
                result["note"] += (
                    " Read by OCR from a picture of the page, not from the "
                    "document. Check every figure against the scan before using it."
                )
                handler.send_json(result)
                return True
            md = pdf_tools.to_markdown(data, doc.get("filename", ""))
            handler.send_json(_save(doc, md.encode("utf-8"), "draft", "text/markdown"))
            return True

    except pdf_tools.NotRedactable as exc:
        handler.send_json({"error": str(exc), "scanned": True}, 400)
        return True
    except ValueError as exc:
        handler.send_json({"error": str(exc)}, 400)
        return True

    handler.send_json({"error": f"Unknown PDF action {action!r}."}, 404)
    return True
