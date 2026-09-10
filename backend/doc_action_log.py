"""What was done to a client's documents, and by whom.

The desk can fill, annotate, redact, reorder, stamp and extract a client's
filed documents. Every one of those writes a new file and leaves the original
alone, which is the right structure — but until now the only record that any
of it happened was a timestamp inside a generated filename.

"Who redacted this client's ID number, and when" is a question asked at a
compliance review. A filename is not an answer to it: filenames are renamed,
drafts are tidied away, and a folder listing does not say who was at the
keyboard.

This is the third log of its kind, deliberately shaped like the other two.
answer_log records what the desk was asked; doc_register records who approved
a product document; this records what was done to a client file. All three are
append-only, all three take the actor from the credential rather than from the
request, and all three swallow their own errors — a desk that will not save an
adviser's redaction because its logbook is full has its priorities backwards.

It holds no document content. The filename of a client document is frequently
the client's name, and that is already inside the vault this row points at, so
the row adds nothing new — but it also means retention.erase must clear these
rows, and it does.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from config import DATA_ROOT

ACTION_LOG = Path(os.environ.get("FORTITUDO_DOC_ACTION_LOG")
                  or (DATA_ROOT / "doc_actions.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS doc_actions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    at        TEXT NOT NULL,
    client_id TEXT NOT NULL DEFAULT '',
    action    TEXT NOT NULL DEFAULT '',
    source    TEXT NOT NULL DEFAULT '',
    saved_as  TEXT NOT NULL DEFAULT '',
    -- Empty when the request never proved who it was. Honestly blank beats a
    -- guess: a log that invents an actor is worse than one that admits it does
    -- not know.
    by        TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_doc_actions_client ON doc_actions(client_id);
"""


def connect() -> sqlite3.Connection:
    ACTION_LOG.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ACTION_LOG)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def record_action(*, client_id: str, action: str, source: str = "",
                  saved_as: str = "", by: str = "") -> int:
    """Note one action on one client document. Returns its id, or 0.

    Never raises into the write path: a draft that saved but was not logged is
    better than a draft the adviser has lost.
    """
    try:
        conn = connect()
        cur = conn.execute(
            "INSERT INTO doc_actions (at, client_id, action, source, saved_as, by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(timespec="seconds"),
             client_id or "", action or "", source or "", saved_as or "", by or ""),
        )
        conn.commit()
        row_id = int(cur.lastrowid)
        conn.close()
        return row_id
    except Exception:
        return 0


def for_client(client_id: str) -> List[dict]:
    conn = connect()
    try:
        rows = conn.execute(
            "SELECT * FROM doc_actions WHERE client_id = ? ORDER BY id",
            (client_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def count_for(client_id: str) -> int:
    conn = connect()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM doc_actions WHERE client_id = ?",
            (client_id,)).fetchone()[0]
    finally:
        conn.close()


def erase_client(client_id: str) -> int:
    """Remove one client's rows, for POPIA erasure.

    Deleted rather than redacted, unlike the answer log. These rows are not
    evidence of advice given — they record that a draft was produced — and what
    they hold (client id, document filenames) is entirely personal information
    with no audit value left once the documents themselves are gone.
    """
    if not client_id:
        return 0
    conn = connect()
    try:
        cur = conn.execute("DELETE FROM doc_actions WHERE client_id = ?",
                           (client_id,))
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def render(client_id: str) -> str:
    rows = for_client(client_id)
    if not rows:
        return f"Nothing has been done to {client_id}'s documents.\n"
    lines = [f"Document actions — {client_id}", "=" * 58]
    for r in rows:
        who = r["by"] or "(unattributed)"
        lines.append(f"  {r['at']}  {r['action']:<10} {who:<16} {r['source']}")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="What was done to a client's documents.")
    ap.add_argument("client_id")
    print(render(ap.parse_args().client_id))
