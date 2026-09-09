"""Which documents the desk is allowed to answer from, and who said so.

Right now the adviser controls what goes in: drop a PDF in docs/, run ingest,
and the desk will quote it. That is fine for one person's own guides. It is the
first thing an FSP's compliance function will refuse, because "the adviser
decided what the tool learned" is not a control — it is the absence of one.

What a control looks like:

**Approval is of a document, not of a filename.** Every ingest fingerprints the
bytes. Approval is recorded against that fingerprint. When the file changes, the
new fingerprint has no approval, so the document silently loses it — which is
the whole point. A register that keeps saying "approved" after the document was
swapped is worse than no register, because it certifies the wrong thing.

**Nothing is deleted.** approve, withdraw and supersede all append an event.
The register can therefore answer "was this approved on the day that advice was
given", which is the question actually asked at review, rather than only "is it
approved now".

**Two modes, one register.**

  open        (default) Everything indexes. Unapproved documents are recorded
              and answers that cite them say so. The adviser's day-to-day use
              builds the register without anyone maintaining it.

  controlled  Ingest refuses anything without a current approval. This is the
              mode an FSP runs: product documents arrive from a controlled
              source with an approval on them, or they do not arrive.

Switching between them is a setting, not a re-ingest, because the register is
kept the same way in both. A desk that had to be rebuilt to become governable
would never be made governable.

Client files and the adviser's own filed lessons are registered under their own
kind and are not subject to product approval — a client's own FNA is evidence
about that client, not a product document somebody has to sign off.
"""
from __future__ import annotations

import hashlib
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from config import DATA_ROOT

REGISTER_DB = Path(os.environ.get("FORTITUDO_DOC_REGISTER")
                   or (DATA_ROOT / "documents.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    source      TEXT PRIMARY KEY,
    kind        TEXT NOT NULL DEFAULT 'product',
    -- Fingerprint of the bytes actually indexed, not of whatever is on disk
    -- now. The index answers from what it read; the register describes that.
    sha256      TEXT NOT NULL DEFAULT '',
    pages       INTEGER DEFAULT 0,
    first_seen  TEXT NOT NULL DEFAULT '',
    last_seen   TEXT NOT NULL DEFAULT '',
    -- Where it came from, in the FSP's terms: a document library id, a URL, a
    -- person's name. Free text on purpose; every firm names this differently.
    origin      TEXT DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'unapproved',
    -- The approval, if any, and the fingerprint it was granted against.
    approved_by   TEXT DEFAULT '',
    approved_at   TEXT DEFAULT '',
    approved_sha  TEXT DEFAULT '',
    note          TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS document_events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    at      TEXT NOT NULL,
    source  TEXT NOT NULL,
    event   TEXT NOT NULL,
    sha256  TEXT DEFAULT '',
    actor   TEXT DEFAULT '',
    detail  TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_events_source ON document_events(source);
"""

# open: index everything, say when a cited document is unapproved.
# controlled: an unapproved document is not indexed at all.
MODES = ("open", "controlled")

PRODUCT = "product"
CLIENT = "client"
LEARN = "learn"

# Kinds that need a human to approve them before the desk quotes them as
# authority. A client's own filed documents and the adviser's own lessons are
# not product literature and nobody signs them off.
GOVERNED = (PRODUCT,)


def mode() -> str:
    m = (os.environ.get("FORTITUDO_INGEST_MODE") or "open").strip().lower()
    return m if m in MODES else "open"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    REGISTER_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(REGISTER_DB)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


def fingerprint(path: Path) -> str:
    """sha256 of the file as bytes.

    Not of the extracted text: two PDFs can extract to the same text and still
    be different documents, and the thing a compliance officer approved was a
    file they opened.
    """
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def kind_of(source: str) -> str:
    s = str(source or "")
    if s.startswith("client:"):
        return CLIENT
    if s.startswith(("learn:", "drama:")):
        return LEARN
    return PRODUCT


@dataclass
class Doc:
    source: str
    kind: str = PRODUCT
    sha256: str = ""
    pages: int = 0
    first_seen: str = ""
    last_seen: str = ""
    origin: str = ""
    status: str = "unapproved"
    approved_by: str = ""
    approved_at: str = ""
    approved_sha: str = ""
    note: str = ""

    @property
    def approved(self) -> bool:
        """Approved, and approved for *this* document.

        The fingerprint comparison is the control, and it is deliberately a
        derived fact rather than a stored status. A status has to be updated by
        whatever code notices the change; if any path forgets, the register
        keeps saying "approved" about a document nobody read. Comparing the two
        fingerprints cannot be forgotten, because nothing has to remember it.
        """
        return (
            self.status == "approved"
            and bool(self.approved_sha)
            and self.approved_sha == self.sha256
        )

    @property
    def lapsed(self) -> bool:
        """Was approved, and then the file underneath it changed.

        Different from never having been approved, and the only one of the two
        that means somebody should be told.
        """
        return (
            self.status == "approved"
            and bool(self.approved_sha)
            and self.approved_sha != self.sha256
        )

    @property
    def governed(self) -> bool:
        return self.kind in GOVERNED


def _row_to_doc(row: Sequence) -> Doc:
    return Doc(source=row[0], kind=row[1], sha256=row[2], pages=row[3] or 0,
               first_seen=row[4] or "", last_seen=row[5] or "", origin=row[6] or "",
               status=row[7] or "unapproved", approved_by=row[8] or "",
               approved_at=row[9] or "", approved_sha=row[10] or "", note=row[11] or "")


_COLS = ("source, kind, sha256, pages, first_seen, last_seen, origin, status, "
         "approved_by, approved_at, approved_sha, note")


def get(source: str, conn: Optional[sqlite3.Connection] = None) -> Optional[Doc]:
    own = conn is None
    conn = conn or connect()
    try:
        row = conn.execute(
            f"SELECT {_COLS} FROM documents WHERE source = ?", (source,)
        ).fetchone()
        return _row_to_doc(row) if row else None
    finally:
        if own:
            conn.close()


def _event(conn: sqlite3.Connection, source: str, event: str, sha: str = "",
           actor: str = "", detail: str = "") -> None:
    conn.execute(
        "INSERT INTO document_events (at, source, event, sha256, actor, detail) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (_now(), source, event, sha, actor, detail),
    )


def may_ingest(source: str, sha: str) -> tuple:
    """(allowed, reason). In controlled mode an unapproved document is refused.

    Called before the embedding work, so a refusal costs nothing and a
    controlled desk cannot be made to learn something by simply running ingest.
    """
    if mode() != "controlled" or kind_of(source) not in GOVERNED:
        return True, ""
    doc = get(source)
    if doc is None:
        return False, "not in the document register"
    if doc.status == "withdrawn":
        return False, f"withdrawn by {doc.approved_by or 'the register'}"
    if doc.status != "approved":
        return False, f"status is {doc.status!r}"
    if doc.approved_sha != sha:
        return False, ("approved fingerprint does not match this file — the "
                       "document changed since it was approved")
    return True, ""


def record_ingest(source: str, sha: str, pages: int, origin: str = "") -> Doc:
    """Note that this document, these bytes, went into the index.

    When the bytes differ from the ones an approval was granted against, the
    approval does not carry over. It is recorded as superseded rather than
    edited away, so the register can still say what was approved when.
    """
    conn = connect()
    try:
        prior = get(source, conn)
        now = _now()
        if prior is None:
            conn.execute(
                f"INSERT INTO documents ({_COLS}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (source, kind_of(source), sha, pages, now, now, origin,
                 "unapproved", "", "", "", ""),
            )
            _event(conn, source, "ingested", sha, detail=f"{pages} pages")
        else:
            if prior.sha256 != sha and prior.status == "approved":
                _event(conn, source, "superseded", sha, actor=prior.approved_by,
                       detail=f"was approved as {prior.sha256[:12]}")
            # status, approved_by and approved_sha are the human's decision and
            # are never rewritten here. Ingest reports what it read; whether
            # that is still the approved document falls out of the comparison.
            conn.execute(
                "UPDATE documents SET sha256 = ?, pages = ?, last_seen = ?, "
                "origin = COALESCE(NULLIF(?, ''), origin) WHERE source = ?",
                (sha, pages, now, origin, source),
            )
            _event(conn, source, "ingested", sha, detail=f"{pages} pages")
        conn.commit()
        return get(source, conn)
    finally:
        conn.close()


def approve(source: str, by: str, sha: str = "", origin: str = "",
            note: str = "") -> tuple:
    """(ok, message). Approval is granted against the indexed fingerprint.

    Passing an explicit `sha` is how a reviewer says which document they read;
    it is refused when it is not the one indexed, because approving a document
    the desk is not answering from approves nothing.
    """
    if not (by or "").strip():
        return False, "an approval needs a name against it"
    conn = connect()
    try:
        doc = get(source, conn)
        if doc is None:
            return False, f"{source} is not in the register — ingest it first"
        if sha and sha != doc.sha256:
            return False, ("that fingerprint is not the one indexed "
                           f"({doc.sha256[:12]}) — re-ingest before approving")
        now = _now()
        conn.execute(
            "UPDATE documents SET status = 'approved', approved_by = ?, "
            "approved_at = ?, approved_sha = ?, note = ?, "
            "origin = COALESCE(NULLIF(?, ''), origin) WHERE source = ?",
            (by, now, doc.sha256, note, origin, source),
        )
        _event(conn, source, "approved", doc.sha256, actor=by, detail=note)
        conn.commit()
        return True, f"{source} approved by {by}"
    finally:
        conn.close()


def withdraw(source: str, by: str, reason: str = "") -> tuple:
    conn = connect()
    try:
        doc = get(source, conn)
        if doc is None:
            return False, f"{source} is not in the register"
        # approved_by is left alone. Replacing the approver's name with the
        # withdrawer's would erase the fact the register exists to keep: that
        # somebody did approve this, and on what.
        conn.execute(
            "UPDATE documents SET status = 'withdrawn', note = ? WHERE source = ?",
            (reason, source),
        )
        _event(conn, source, "withdrawn", doc.sha256, actor=by, detail=reason)
        conn.commit()
        return True, f"{source} withdrawn by {by}"
    finally:
        conn.close()


def history(source: str) -> List[dict]:
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT at, event, sha256, actor, detail FROM document_events "
            "WHERE source = ? ORDER BY id",
            (source,),
        ).fetchall()
        return [{"at": r[0], "event": r[1], "sha256": r[2], "actor": r[3],
                 "detail": r[4]} for r in rows]
    finally:
        conn.close()


def register(kind: str = "") -> List[Doc]:
    conn = connect()
    try:
        if kind:
            rows = conn.execute(
                f"SELECT {_COLS} FROM documents WHERE kind = ? ORDER BY source",
                (kind,),
            ).fetchall()
        else:
            rows = conn.execute(
                f"SELECT {_COLS} FROM documents ORDER BY source"
            ).fetchall()
        return [_row_to_doc(r) for r in rows]
    finally:
        conn.close()


def unapproved_sources(sources: Iterable[str]) -> List[str]:
    """Of these cited sources, which carry no current approval.

    Only governed kinds are considered, and a source the register has never
    heard of counts as unapproved: silence is not an approval.
    """
    wanted = [s for s in dict.fromkeys(sources) if kind_of(s) in GOVERNED]
    if not wanted:
        return []
    conn = connect()
    try:
        marks = ",".join("?" * len(wanted))
        rows = conn.execute(
            f"SELECT {_COLS} FROM documents WHERE source IN ({marks})", wanted
        ).fetchall()
        known: Dict[str, Doc] = {r[0]: _row_to_doc(r) for r in rows}
    finally:
        conn.close()
    return [s for s in wanted if not (known.get(s) and known[s].approved)]


def provenance_note(results) -> str:
    """A line for the adviser when an answer leans on an unapproved document.

    Deliberately not a refusal in open mode. The adviser's own guides are
    useful before anyone signs them off; what is not acceptable is quoting them
    as though someone had.
    """
    sources = [row[1] for row, _score in (results or []) if len(row) > 1]
    missing = unapproved_sources(sources)
    if not missing:
        return ""
    return (
        "\n\n[UNAPPROVED] This answer cites documents with no current approval "
        "in the register: " + ", ".join(missing) + ". They may be superseded or "
        "may never have been checked. Confirm the version before you rely on a "
        "figure from them."
    )


def render(docs: Optional[Sequence[Doc]] = None) -> str:
    docs = register() if docs is None else docs
    if not docs:
        return "The document register is empty. Run ingest.\n"
    width = max(len(d.source) for d in docs)
    lines = [f"Document register  ({mode()} mode)", "=" * (width + 46)]
    for d in docs:
        if not d.governed:
            state = f"{d.kind} (not governed)"
        elif d.approved:
            state = f"approved by {d.approved_by} on {d.approved_at[:10]}"
        elif d.lapsed:
            state = f"APPROVAL LAPSED — the file changed since {d.approved_by}"
        else:
            state = d.status.upper()
        lines.append(f"  {d.source:<{width}}  {d.pages:>4}p  {state}")
    ungoverned = sum(1 for d in docs if d.governed and not d.approved)
    lines.append("-" * (width + 46))
    lines.append(f"  {len(docs)} documents, {ungoverned} product document(s) "
                 "without a current approval")
    return "\n".join(lines) + "\n"


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description="The desk's document register.")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("list")
    a = sub.add_parser("approve")
    a.add_argument("source")
    a.add_argument("--by", required=True)
    a.add_argument("--sha", default="")
    a.add_argument("--origin", default="")
    a.add_argument("--note", default="")
    w = sub.add_parser("withdraw")
    w.add_argument("source")
    w.add_argument("--by", required=True)
    w.add_argument("--reason", default="")
    h = sub.add_parser("history")
    h.add_argument("source")
    args = ap.parse_args()

    if args.cmd == "approve":
        ok, msg = approve(args.source, args.by, args.sha, args.origin, args.note)
        print(msg)
        raise SystemExit(0 if ok else 1)
    if args.cmd == "withdraw":
        ok, msg = withdraw(args.source, args.by, args.reason)
        print(msg)
        raise SystemExit(0 if ok else 1)
    if args.cmd == "history":
        for e in history(args.source):
            print(f"  {e['at']}  {e['event']:<11} {e['sha256'][:12]:<12} "
                  f"{e['actor']:<16} {e['detail']}")
        return
    print(render())


if __name__ == "__main__":
    main()
