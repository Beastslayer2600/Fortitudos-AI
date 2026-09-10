"""POPIA s14 retention, and erasing a client from every place they exist.

Two obligations that pull in opposite directions, which is why this is a
module and not a delete button.

**POPIA s14** says personal information must not be kept for longer than is
necessary — *except* where another law requires it. **The FAIS General Code**
requires advice records to be kept for five years after the advice or after
the product ends. So the desk's honest position is not "delete when asked". It
is: keep for the period the law requires, know when that period expires, and
be able to erase completely when it does.

The part worth building carefully is *completely*.

A client's personal information lives in five places, and they were built at
different times by different code:

  1. the vault files under clients/<id>/
  2. the client database — five tables, all keyed on client_id
  3. the page index, as `client:<id>:<filename>` rows carrying the extracted
     text of their documents
  4. the answer log, where an answer that quoted their file contains their
     information in its own text
  5. the document action log, which records what was done to their documents
     and by whom

An erasure that removes the folder and the database rows looks complete, is
reported as complete, and leaves the desk able to quote the client's income
and ID number out of the index for as long as the index survives. That is the
failure this module exists to prevent, and `survey()` is deliberately the
first thing it offers: you are shown all four counts before anything is
removed.

**Nothing here deletes on a timer.** Retention expiry is reported; a person
erases. A desk that quietly destroyed records a regulator may still call for
would be a worse failure than one that keeps them too long, and "the software
did it automatically" is not a defence anyone wants to offer.

**The answer log is redacted, not deleted.** Its rows are the audit trail of
advice that was given; removing them entirely would put a hole in the record
of what happened. The personal information in a row is the question, the
answer text and the client id, so those are blanked and the row keeps its
time, room, model, timing and retrieval snapshot. What was said is gone; that
something was said, and from which document versions, remains provable.

**The erasure receipt holds no personal information.** Only the client id,
counts, who did it and when — enough to prove the erasure happened without
recreating what it removed.
"""
from __future__ import annotations

import os
import shutil
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from config import DATA_ROOT

ERASURE_LOG = Path(os.environ.get("FORTITUDO_ERASURE_LOG")
                   or (DATA_ROOT / "erasures.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS erasures (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    at          TEXT NOT NULL,
    client_id   TEXT NOT NULL,
    by          TEXT NOT NULL DEFAULT '',
    reason      TEXT DEFAULT '',
    -- Counts only. A receipt that recorded what was erased would be a copy of
    -- the thing that was erased.
    files       INTEGER DEFAULT 0,
    db_rows     INTEGER DEFAULT 0,
    index_pages INTEGER DEFAULT 0,
    log_rows    INTEGER DEFAULT 0,
    complete    INTEGER DEFAULT 0,
    note        TEXT DEFAULT ''
);
"""

# The FAIS General Code of Conduct requires advice records to be kept for five
# years. This is the legal basis POPIA s14 defers to, so it is named here
# rather than left as a bare number somebody later "tidies up".
FAIS_RECORD_YEARS = int(os.environ.get("FORTITUDO_RETENTION_YEARS", "5"))
RETENTION_BASIS = (
    f"FAIS General Code of Conduct — advice records kept {FAIS_RECORD_YEARS} "
    "years after the advice or the end of the product. POPIA s14 permits "
    "retention where another law requires it."
)

# Client statuses that mean the relationship has ended and the clock has
# started. Anything else is an active client and is not up for erasure.
CLOSED_STATUSES = {"closed", "lapsed", "terminated", "cancelled", "declined"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect() -> sqlite3.Connection:
    ERASURE_LOG.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(ERASURE_LOG)
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


@dataclass
class Survey:
    """Everywhere one client's information currently is."""
    client_id: str
    exists: bool = False
    status: str = ""
    files: List[str] = field(default_factory=list)
    db_rows: Dict[str, int] = field(default_factory=dict)
    index_pages: int = 0
    log_rows: int = 0
    action_rows: int = 0
    last_activity: str = ""

    @property
    def total_db_rows(self) -> int:
        return sum(self.db_rows.values())

    @property
    def anything(self) -> bool:
        return bool(self.files or self.total_db_rows or self.index_pages
                    or self.log_rows or self.action_rows)


# The client-database tables holding personal information, in delete order:
# children before the row they reference.
CLIENT_TABLES = ("documents", "notes", "emails", "projections", "clients")


def survey(client_id: str) -> Survey:
    """Count this client's information in all four places, changing nothing.

    Offered before erase() rather than only inside it, because the number that
    matters is the one you did not expect — usually the index pages.
    """
    import client_store

    s = Survey(client_id=client_id)
    client = client_store.get_client(client_id)
    if client:
        s.exists = True
        s.status = str(client.get("status") or "")
        s.last_activity = str(client.get("updated_at") or "")

    root = client_store.CLIENTS_DIR / client_id
    if root.exists():
        s.files = sorted(str(p.relative_to(root)) for p in root.rglob("*")
                         if p.is_file())

    conn = client_store.connect()
    try:
        for table in CLIENT_TABLES:
            column = "id" if table == "clients" else "client_id"
            try:
                s.db_rows[table] = conn.execute(
                    f"SELECT COUNT(*) FROM {table} WHERE {column} = ?",
                    (client_id,)).fetchone()[0]
            except sqlite3.Error:
                s.db_rows[table] = 0
    finally:
        conn.close()

    # The one that gets missed. These rows hold the extracted text of the
    # client's own documents, so they are the client's information, not a
    # reference to it.
    try:
        import store
        idx = store.connect()
        try:
            s.index_pages = idx.execute(
                "SELECT COUNT(*) FROM pages WHERE source LIKE ?",
                (f"client:{client_id}:%",)).fetchone()[0]
        finally:
            idx.close()
    except Exception:
        s.index_pages = 0

    try:
        import answer_log
        conn = answer_log.connect()
        try:
            # client_id is cleared by redaction, so a redacted row no longer
            # matches and the count going to zero means the work was done —
            # not that the rows were deleted.
            s.log_rows = conn.execute(
                "SELECT COUNT(*) FROM answers WHERE client_id = ?",
                (client_id,)).fetchone()[0]
        finally:
            conn.close()
    except Exception:
        s.log_rows = 0

    # The fifth place, added after this module was written. Adding a store that
    # holds client data without teaching erase() about it is precisely the
    # failure this module exists to prevent, so it is surveyed here and cleared
    # below in the same change.
    try:
        import doc_action_log
        s.action_rows = doc_action_log.count_for(client_id)
    except Exception:
        s.action_rows = 0

    return s


@dataclass
class Due:
    client_id: str
    name_withheld: str = ""      # never the name; the id is the handle
    status: str = ""
    last_activity: str = ""
    expires_on: str = ""
    over_by_days: int = 0


def _parse_day(text: str) -> Optional[date]:
    raw = (text or "")[:10]
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


def due(as_of: Optional[date] = None) -> List[Due]:
    """Closed clients whose retention period has run out.

    Only closed ones. An active client's records are not up for erasure however
    old they are, and a list that mixed the two would train whoever reads it to
    skim.
    """
    import client_store

    today = as_of or date.today()
    out: List[Due] = []
    for client in client_store.list_clients():
        status = str(client.get("status") or "").strip().lower()
        if status not in CLOSED_STATUSES:
            continue
        started = _parse_day(str(client.get("updated_at") or ""))
        if started is None:
            continue
        expires = date(started.year + FAIS_RECORD_YEARS, started.month,
                       started.day) if _valid(started) else started + timedelta(
                           days=365 * FAIS_RECORD_YEARS)
        if expires <= today:
            out.append(Due(client_id=str(client.get("id") or ""),
                           status=status,
                           last_activity=str(client.get("updated_at") or "")[:10],
                           expires_on=expires.isoformat(),
                           over_by_days=(today - expires).days))
    return sorted(out, key=lambda d: -d.over_by_days)


def _valid(d: date) -> bool:
    """Whether adding whole years to this date lands on a real date.

    29 February does not exist in most years, and a retention date that threw
    on one client in four hundred would be found by that client.
    """
    try:
        date(d.year + FAIS_RECORD_YEARS, d.month, d.day)
        return True
    except ValueError:
        return False


@dataclass
class Receipt:
    client_id: str
    at: str = ""
    by: str = ""
    files: int = 0
    db_rows: int = 0
    index_pages: int = 0
    log_rows: int = 0
    action_rows: int = 0
    complete: bool = False
    dry_run: bool = True
    problems: List[str] = field(default_factory=list)


def erase(client_id: str, by: str, reason: str = "",
          dry_run: bool = True) -> Receipt:
    """Remove one client from all four places. Dry run by default.

    The default is a dry run on purpose: the destructive reading of a one-word
    command should be the one you have to ask for.

    `complete` is set only after re-surveying afterwards and finding nothing
    left. Reporting success from the fact that the delete statements ran is how
    an erasure comes to be certified while the index still holds the pages.
    """
    import client_store

    before = survey(client_id)
    r = Receipt(client_id=client_id, at=_now(), by=by or "",
                files=len(before.files), db_rows=before.total_db_rows,
                index_pages=before.index_pages, log_rows=before.log_rows,
                action_rows=before.action_rows, dry_run=dry_run)
    if not (by or "").strip():
        r.problems.append("an erasure needs a name against it")
        return r
    if not before.anything:
        r.complete = True
        return r
    if dry_run:
        return r

    root = client_store.CLIENTS_DIR / client_id
    if root.exists():
        try:
            shutil.rmtree(root)
        except OSError as exc:
            r.problems.append(f"files: {exc}")

    conn = client_store.connect()
    try:
        for table in CLIENT_TABLES:
            column = "id" if table == "clients" else "client_id"
            try:
                conn.execute(f"DELETE FROM {table} WHERE {column} = ?", (client_id,))
            except sqlite3.Error as exc:
                r.problems.append(f"{table}: {exc}")
        conn.commit()
    finally:
        conn.close()

    # store.clear_source drops the pages and the source fingerprint together,
    # so a later ingest cannot decide the document is "unchanged" and skip it.
    try:
        import store
        idx = store.connect()
        try:
            sources = [row[0] for row in idx.execute(
                "SELECT DISTINCT source FROM pages WHERE source LIKE ?",
                (f"client:{client_id}:%",)).fetchall()]
            for source in sources:
                store.clear_source(idx, source)
        finally:
            idx.close()
        store.invalidate_cache()
    except Exception as exc:
        r.problems.append(f"index: {exc}")

    try:
        import answer_log
        answer_log.redact_client(client_id)
    except Exception as exc:
        r.problems.append(f"answer log: {exc}")

    try:
        import doc_action_log
        doc_action_log.erase_client(client_id)
    except Exception as exc:
        r.problems.append(f"document action log: {exc}")

    after = survey(client_id)
    r.complete = not after.anything and not r.problems
    if after.anything:
        r.problems.append(
            f"still present: {len(after.files)} files, {after.total_db_rows} "
            f"database rows, {after.index_pages} index pages, "
            f"{after.log_rows} log rows, {after.action_rows} action rows")

    conn = connect()
    try:
        conn.execute(
            "INSERT INTO erasures (at, client_id, by, reason, files, db_rows, "
            "index_pages, log_rows, complete, note) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (r.at, client_id, r.by, reason, r.files, r.db_rows, r.index_pages,
             r.log_rows, 1 if r.complete else 0, "; ".join(r.problems)),
        )
        conn.commit()
    finally:
        conn.close()
    return r


def receipts(client_id: str = "") -> List[dict]:
    """Proof that an erasure happened. Holds no personal information."""
    conn = connect()
    try:
        if client_id:
            rows = conn.execute(
                "SELECT * FROM erasures WHERE client_id = ? ORDER BY id",
                (client_id,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM erasures ORDER BY id").fetchall()
        cols = [d[0] for d in conn.execute("SELECT * FROM erasures LIMIT 0").description]
    finally:
        conn.close()
    return [dict(zip(cols, r)) for r in rows]


def render_due(items: Optional[Sequence[Due]] = None) -> str:
    items = due() if items is None else items
    lines = [f"Retention — {RETENTION_BASIS}", "=" * 60]
    if not items:
        lines.append("  Nothing is past its retention period.")
        lines.append("  Only closed clients are counted; an active client's")
        lines.append("  records are not up for erasure however old they are.")
        return "\n".join(lines) + "\n"
    for d in items:
        lines.append(f"  {d.client_id:<20} {d.status:<12} expired "
                     f"{d.expires_on}  ({d.over_by_days} days ago)")
    lines.append("-" * 60)
    lines.append(f"  {len(items)} past retention. Nothing is erased on a timer —")
    lines.append("  review each one, then:  python retention.py erase <id> "
                 "--by \"<name>\" --confirm")
    return "\n".join(lines) + "\n"


def render_survey(s: Survey) -> str:
    lines = [f"Where {s.client_id} exists", "=" * 46]
    if not s.exists and not s.anything:
        return f"Nothing found for {s.client_id}.\n"
    lines.append(f"  {'vault files':22} {len(s.files):>5}")
    for table, n in s.db_rows.items():
        lines.append(f"  {('  ' + table):22} {n:>5}")
    lines.append(f"  {'database rows':22} {s.total_db_rows:>5}")
    lines.append(f"  {'index pages':22} {s.index_pages:>5}"
                 "   the extracted text of their documents")
    lines.append(f"  {'answer log rows':22} {s.log_rows:>5}"
                 "   redacted, not deleted")
    lines.append(f"  {'document actions':22} {s.action_rows:>5}"
                 "   who did what to their files")
    return "\n".join(lines) + "\n"


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(
        description="POPIA s14 retention and complete erasure.")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("due")
    w = sub.add_parser("where")
    w.add_argument("client_id")
    e = sub.add_parser("erase")
    e.add_argument("client_id")
    e.add_argument("--by", required=True)
    e.add_argument("--reason", default="")
    e.add_argument("--confirm", action="store_true",
                   help="actually erase; without it this is a dry run")
    r = sub.add_parser("receipts")
    r.add_argument("client_id", nargs="?", default="")
    args = ap.parse_args()

    if args.cmd == "where":
        print(render_survey(survey(args.client_id)))
        return
    if args.cmd == "erase":
        rec = erase(args.client_id, args.by, args.reason, dry_run=not args.confirm)
        head = "WOULD erase" if rec.dry_run else "Erased"
        print(f"\n  {head} {rec.client_id}: {rec.files} files, "
              f"{rec.db_rows} database rows, {rec.index_pages} index pages, "
              f"{rec.log_rows} answer-log rows redacted")
        for p in rec.problems:
            print(f"  PROBLEM: {p}")
        if rec.dry_run:
            print("\n  Nothing was removed. Add --confirm to erase.\n")
        else:
            print(f"\n  complete: {rec.complete}\n")
        raise SystemExit(0 if (rec.dry_run or rec.complete) else 1)
    if args.cmd == "receipts":
        for row in receipts(args.client_id):
            print(f"  {row['at']}  {row['client_id']:<16} by {row['by']:<16} "
                  f"files={row['files']} db={row['db_rows']} "
                  f"index={row['index_pages']} log={row['log_rows']} "
                  f"complete={bool(row['complete'])}")
        return
    print(render_due())


if __name__ == "__main__":
    main()
