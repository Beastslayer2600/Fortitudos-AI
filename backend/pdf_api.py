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

import client_store
import pdf_tools


class DocError(ValueError):
    """A document that cannot be worked on, with a reason worth showing."""


def load(doc_id: str) -> Tuple[dict, bytes]:
    """Fetch a filed document's bytes, refusing anything outside the vault.

    The stored path decides what gets read, so it is checked against the vault
    root before any read — a document row is not a licence to open a file.
    """
    doc = client_store.get_document(doc_id)
    if not doc:
        raise DocError("Document not found.")
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


def describe(doc_id: str) -> dict:
    """Everything the desk needs to show the document and reason about it."""
    doc, data = load(doc_id)
    pages = pdf_tools.read_pages(data)
    fields = pdf_tools.form_fields(data)
    scanned = all(p.blank for p in pages)
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
        "can": {
            # Say up front what this particular document supports, rather than
            # offering an action that will fail on it.
            "fill": bool(fields),
            "redact": not scanned,
            "annotate": True,
            "assemble": True,
            "stamp": True,
            "extract": not scanned,
        },
        "why": (
            "No extractable text — this is a scan. It can be annotated, "
            "stamped and reordered, but not read or redacted until it is OCRed."
            if scanned else ""
        ),
    }


def handle_get(handler, parts) -> bool:
    if len(parts) == 3 and parts[:2] == ["api", "pdf"]:
        try:
            handler.send_json(describe(parts[2]))
        except DocError as exc:
            handler.send_json({"error": str(exc)}, 404)
        return True
    return False


def handle_post(handler, parts, body) -> bool:
    if len(parts) != 4 or parts[:2] != ["api", "pdf"]:
        return False
    doc_id, action = parts[2], parts[3]
    try:
        doc, data = load(doc_id)
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
            out, removed = pdf_tools.redact(
                data,
                literals=[str(x) for x in (body.get("literals") or [])],
                patterns=[str(x) for x in (body.get("patterns") or [])],
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
