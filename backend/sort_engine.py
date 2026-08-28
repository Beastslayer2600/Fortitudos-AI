"""Drop-zone auto-filing for Fortitudo AI.

Drop or copy a file into the drop zone. The engine extracts its text, asks the
local model what it is and whose it is, and files it into the right client
folder using the same terminology as client_store.FOLDERS.

Design notes:
  - Document type labels come from client_store.FOLDERS directly, so the
    classifier can never invent a label the filer does not understand.
  - Files below the confidence threshold are parked for manual review rather
    than filed on a guess. Misfiling a client document is worse than asking.
  - The review area lives OUTSIDE the drop zone so parked files are not
    picked up and reprocessed on the next pass.
"""
import json
import logging
import os
import shutil
import threading
import time
from datetime import datetime
from pathlib import Path

import client_store
from ingest import extract_any
from llm import chat
from config import CHAT_MODEL

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("SortEngine")

DROP_ZONE = Path(os.environ.get("FORTITUDO_DROP_ZONE",
                                r"C:\FortitudoData\DropZone"))
# Deliberately a sibling of the drop zone, not a child of it.
REVIEW_ZONE = Path(os.environ.get("FORTITUDO_REVIEW_ZONE",
                                  str(DROP_ZONE.parent / "ManualReview")))

DROP_ZONE.mkdir(parents=True, exist_ok=True)
REVIEW_ZONE.mkdir(parents=True, exist_ok=True)

POLL_SECONDS = 5
MIN_CONFIDENCE = 0.65
MAX_CLASSIFY_CHARS = 2500

# Partial files produced by browsers, Office and copy operations.
IGNORE_SUFFIXES = {".crdownload", ".part", ".partial", ".tmp", ".download"}
IGNORE_PREFIXES = ("~$", ".~", "._")

SYSTEM = (
    "You are a filing assistant for a South African financial adviser. "
    "You classify documents precisely and you never guess. "
    "You reply with a single JSON object and nothing else."
)


def doc_type_labels():
    """The only labels the filer understands. Single source of truth."""
    return [k for k in client_store.FOLDERS.keys()]


class SortEngine:
    def __init__(self):
        self.running = False
        self._thread = None
        self.last_status = "Idle"
        self.recent = []              # newest-first log for the UI
        self._sizes = {}              # path -> (size, seen_at) for stability

    # ---------------------------------------------------------------- control

    def start(self):
        if not self.running:
            self.running = True
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            logger.info("SortEngine started, watching %s", DROP_ZONE)

    def stop(self):
        self.running = False
        self.last_status = "Stopped"

    def status(self):
        return {
            "running": self.running,
            "status": self.last_status,
            "drop_zone": str(DROP_ZONE),
            "review_zone": str(REVIEW_ZONE),
            "recent": self.recent[:25],
        }

    # ---------------------------------------------------------------- loop

    def _run(self):
        while self.running:
            try:
                pending = [p for p in DROP_ZONE.rglob("*")
                           if p.is_file() and self._is_candidate(p)]
                if pending:
                    ready = [p for p in pending if self._is_stable(p)]
                    if ready:
                        self.last_status = f"Processing {len(ready)} file(s)"
                        for p in ready:
                            self._process_file(p)
                    else:
                        self.last_status = "Waiting for copy to finish"
                    self._cleanup_empty_dirs()
                else:
                    self.last_status = "Idle"
                    self._sizes.clear()
            except Exception as e:
                logger.exception("SortEngine loop error")
                self.last_status = f"Error: {str(e)[:60]}"
            time.sleep(POLL_SECONDS)

    def _is_candidate(self, path):
        if path.suffix.lower() in IGNORE_SUFFIXES:
            return False
        if path.name.startswith(IGNORE_PREFIXES):
            return False
        if path.name.startswith("."):
            return False
        return True

    def _is_stable(self, path):
        """True once the file size has stopped changing between polls.

        Dragging a large PDF in can otherwise be read halfway through the
        copy, producing a truncated document and a confident wrong answer.
        """
        try:
            size = path.stat().st_size
        except OSError:
            return False
        if size == 0:
            return False

        prev = self._sizes.get(str(path))
        self._sizes[str(path)] = (size, time.time())
        return prev is not None and prev[0] == size

    def _cleanup_empty_dirs(self):
        for d in sorted((p for p in DROP_ZONE.rglob("*") if p.is_dir()),
                        key=lambda p: len(p.parts), reverse=True):
            try:
                if not any(d.iterdir()):
                    d.rmdir()
            except OSError:
                pass

    # ---------------------------------------------------------------- process

    def _process_file(self, path):
        logger.info("Processing %s", path.name)
        try:
            pages = list(extract_any(path))
        except Exception as e:
            logger.error("Extraction failed for %s: %s", path.name, e)
            return self._park(path, "unreadable",
                              f"Could not read this file type: {e}")

        text = "\n".join(p[1] for p in pages[:3]).strip()
        if not text:
            return self._park(
                path, "no_text",
                "No text found. If this is a scan or photo it needs OCR "
                "before it can be classified.")

        result = self._classify(text, path.name)
        if not result:
            return self._park(path, "classify_failed",
                              "The model did not return usable JSON.")

        cid = result.get("client_id")
        doc_type = result.get("doc_type") or "Other"
        confidence = float(result.get("confidence") or 0)
        reason = result.get("reason", "")

        if doc_type not in client_store.FOLDERS:
            logger.warning("Unknown doc_type %r, treating as Other", doc_type)
            doc_type = "Other"

        if not cid or str(cid).lower() in {"null", "none", ""}:
            return self._park(path, "unknown_client",
                              f"Could not match a client. {reason}",
                              extra={"doc_type": doc_type,
                                     "confidence": confidence})

        if confidence < MIN_CONFIDENCE:
            return self._park(path, "low_confidence",
                              f"Only {confidence:.0%} sure. {reason}",
                              extra={"client_id": cid, "doc_type": doc_type})

        self._file_it(path, cid, doc_type, confidence, reason)

    def _classify(self, text, filename):
        clients = client_store.list_clients()
        if not clients:
            return None
        client_list = "\n".join(
            f"- id: {c['id']}  |  name: {c['name']}" for c in clients)
        types = "\n".join(f'  - "{t}"' for t in doc_type_labels())

        user = f"""Known clients:
{client_list}

Allowed doc_type values, use one of these EXACTLY:
{types}

What each type means:
  "FICA / Identity"  - ID document, passport, proof of address, tax number
                       confirmation, bank confirmation letter
  "RPQ"              - risk profile questionnaire, risk tolerance assessment
  "Signed FNA"       - financial needs analysis, completed and signed
  "Advice Report"    - advice report or recommendation summary
  "Quote"            - product quotation or illustration from a provider
  "ROA"              - record of advice
  "Correspondence"   - emails, letters, general client communication
  "Other"            - anything that does not clearly fit above

Filename: {filename}
Document text (beginning):
---
{text[:MAX_CLASSIFY_CHARS]}
---

Match the client by the person's name in the document. If no known client
matches, set client_id to null - do not guess.
Set confidence honestly: 1.0 only when the name and type are both explicit.

Reply with exactly this JSON and nothing else:
{{"client_id": "<id or null>", "doc_type": "<one of the allowed values>",
 "confidence": <0.0-1.0>, "reason": "<one short sentence>"}}"""

        try:
            response = chat(SYSTEM, user)
        except Exception as e:
            logger.error("LLM classification error: %s", e)
            return None

        start, end = response.find("{"), response.rfind("}") + 1
        if start == -1 or end <= start:
            logger.error("No JSON in model response: %s", response[:200])
            return None
        try:
            return json.loads(response[start:end])
        except json.JSONDecodeError as e:
            logger.error("Bad JSON from model: %s", e)
            return None

    def _file_it(self, path, cid, doc_type, confidence, reason):
        try:
            content = path.read_bytes()
            client_store.add_document(cid=cid, filename=path.name,
                                      content=content, doc_type=doc_type)
        except Exception as e:
            logger.error("Filing failed for %s: %s", path.name, e)
            return self._park(path, "filing_failed", str(e))

        name = path.name
        try:
            path.unlink()
        except OSError as e:
            logger.warning("Filed but could not remove %s: %s", name, e)

        folder = client_store.FOLDERS.get(doc_type, "07_Other")
        logger.info("Filed %s -> %s / %s (%.0f%%)",
                    name, cid, folder, confidence * 100)
        self._log(name, "filed", client_id=cid, doc_type=doc_type,
                  folder=folder, confidence=confidence, reason=reason)

    # ---------------------------------------------------------------- review

    def _park(self, path, reason_code, message, extra=None):
        """Move a file to the review area with a note explaining why."""
        dest_dir = REVIEW_ZONE / reason_code
        dest_dir.mkdir(parents=True, exist_ok=True)

        dest = dest_dir / path.name
        if dest.exists():
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dest = dest_dir / f"{dest.stem}_{stamp}{dest.suffix}"

        name = path.name
        try:
            shutil.move(str(path), str(dest))
        except Exception as e:
            logger.error("Could not park %s: %s", name, e)
            return

        note = {"file": name, "reason_code": reason_code,
                "message": message, "at": datetime.now().isoformat(timespec="seconds")}
        if extra:
            note.update(extra)
        try:
            dest.with_suffix(dest.suffix + ".note.json").write_text(
                json.dumps(note, indent=2), encoding="utf-8")
        except OSError:
            pass

        logger.info("Parked %s for review: %s", name, reason_code)
        self._log(name, "review", reason=message, folder=reason_code)

    def _log(self, filename, outcome, **fields):
        entry = {"file": filename, "outcome": outcome,
                 "at": datetime.now().strftime("%H:%M:%S")}
        entry.update(fields)
        self.recent.insert(0, entry)
        del self.recent[50:]


engine = SortEngine()
