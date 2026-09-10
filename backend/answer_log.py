"""What the desk was asked, what it answered, and what it answered from.

Two jobs, one record.

**The evidence log.** The plan for taking this to Liberty rests on numbers:
how much time it saves, how often it is wrong, how often the as-of layer
answered something the normal systems could not. Kept by hand, that log does
not get kept. Kept automatically, it is six months of evidence by the time the
conversation happens.

**The audit trail.** The same record is what a compliance officer asks for:
who asked what, when, what came back, and *which version of which document* it
came from. versioning.snapshot_id() has always been able to fingerprint a
retrieval — it was simply never called, so the fingerprint was computed
nowhere and stored nowhere.

The distinction that makes this worth storing rather than deriving: the index
answers "what applied on 3 March" from how it stands **today**. Only a record
written at the time answers "what would this desk have told me on 3 March".
Once a guide is re-ingested or corrected, those are different answers, and the
second one is the one that matters at a compliance review.

Rows are append-only. An answer is a thing that happened; correcting the file
later does not un-happen it.
"""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from config import DATA_ROOT

LOG_DB = Path(os.environ.get("FORTITUDO_ANSWER_LOG")
              or (DATA_ROOT / "answers.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS answers (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    asked_at      TEXT NOT NULL,
    room          TEXT NOT NULL,
    question      TEXT NOT NULL,
    answer        TEXT NOT NULL,
    client_id     TEXT DEFAULT '',
    as_of         TEXT DEFAULT '',
    -- Fingerprint of exactly the pages this answer was built from.
    snapshot      TEXT DEFAULT '',
    -- The pages themselves, so the snapshot can be explained and not merely
    -- compared. A hash proves a match; it cannot show a reviewer the page.
    sources_json  TEXT DEFAULT '[]',
    model         TEXT DEFAULT '',
    seconds       REAL DEFAULT 0,
    used_client   INTEGER DEFAULT 0,
    -- Flags the desk raised on itself, so they are countable later.
    span_flagged  INTEGER DEFAULT 0,
    version_clash INTEGER DEFAULT 0,
    -- The answer leaned on a document nobody has approved.
    unapproved    INTEGER DEFAULT 0,
    -- Who asked. Empty on a single-adviser desk, where there is only one
    -- person and the question does not arise.
    asked_by      TEXT DEFAULT '',
    invent_risk   TEXT DEFAULT '',
    -- The adviser's verdict, added after the fact. NULL until marked.
    verdict       TEXT DEFAULT '',
    verdict_note  TEXT DEFAULT '',
    verdict_at    TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_answers_at ON answers(asked_at);
CREATE INDEX IF NOT EXISTS idx_answers_verdict ON answers(verdict);
"""

# What the adviser can say about an answer afterwards. Deliberately short —
# a long list does not get used, and these are the four that change a decision.
VERDICTS = {
    "good": "Right, and I used it.",
    "wrong": "Wrong — a figure or a fact was not right.",
    "thin": "Nothing useful. Missing citation or no answer.",
    "stale": "Answered from an out-of-date document.",
}


def connect() -> sqlite3.Connection:
    LOG_DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(LOG_DB)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns to a log that already has rows in it.

    The log is the evidence; dropping and recreating it to gain a column would
    throw away the thing being built.
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(answers)").fetchall()}
    for name, ddl in (("unapproved", "INTEGER DEFAULT 0"),
                      ("asked_by", "TEXT DEFAULT ''")):
        if name not in cols:
            conn.execute(f"ALTER TABLE answers ADD COLUMN {name} {ddl}")
    conn.commit()


def _sources(results: Sequence) -> List[Dict[str, Any]]:
    """Which page, from which document version, at what score."""
    out = []
    for row, score in results or []:
        try:
            out.append({
                "source": row[1],
                "page": row[2],
                "score": round(float(score), 4),
                # The page's own content hash: if the document is re-ingested
                # with different text, this no longer matches, which is how a
                # reviewer knows the answer predates the change.
                "hash": row[4] if len(row) > 4 and isinstance(row[4], str) else "",
            })
        except Exception:
            continue
    return out


def record(*, question: str, answer: str, room: str, results: Sequence,
           client_id: str = "", as_of: str = "", model: str = "",
           seconds: float = 0.0, used_client: bool = False,
           invent_risk: str = "", asked_by: str = "") -> int:
    """Write one answer to the log. Returns its id.

    Never raises into the answer path: a desk that cannot answer because its
    logbook is full is worse than a desk with a gap in the logbook.
    """
    try:
        from versioning import snapshot_id
        snapshot = snapshot_id(results)
    except Exception:
        snapshot = ""
    text = answer or ""
    try:
        conn = connect()
        cur = conn.execute(
            "INSERT INTO answers (asked_at, room, question, answer, client_id, "
            "as_of, snapshot, sources_json, model, seconds, used_client, "
            "span_flagged, version_clash, unapproved, invent_risk, asked_by) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                room or "",
                question or "",
                text,
                client_id or "",
                as_of or "",
                snapshot,
                json.dumps(_sources(results)),
                model or "",
                round(float(seconds or 0), 2),
                1 if used_client else 0,
                1 if "[SPAN-CHECK]" in text else 0,
                1 if "[VERSIONS]" in text else 0,
                1 if "[UNAPPROVED]" in text else 0,
                invent_risk or "",
                asked_by or "",
            ),
        )
        conn.commit()
        row_id = int(cur.lastrowid)
        conn.close()
        return row_id
    except Exception:
        return 0


def mark(answer_id: int, verdict: str, note: str = "") -> bool:
    """The adviser's verdict on an answer. This is the failure log.

    The row itself is never edited — only the verdict columns, which were
    empty. What the desk said stays exactly as it said it.
    """
    if verdict not in VERDICTS:
        raise ValueError(f"verdict must be one of {sorted(VERDICTS)}")
    conn = connect()
    try:
        cur = conn.execute(
            "UPDATE answers SET verdict = ?, verdict_note = ?, verdict_at = ? "
            "WHERE id = ?",
            (verdict, note or "",
             datetime.now(timezone.utc).isoformat(timespec="seconds"),
             int(answer_id)),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# What a redacted row says where the question and answer were. Distinct text,
# so a reviewer can tell an erased answer from an empty one.
REDACTED = "[ERASED — client record erased under POPIA s14]"


def redact_client(client_id: str) -> int:
    """Blank one client's information out of the log, keeping the rows.

    The rows are the audit trail of advice that was given; deleting them would
    put a hole in the record of what happened, which is the opposite of what a
    review needs. The personal information is the question, the answer text and
    the client id, so those go. Time, room, model, timing and the retrieval
    snapshot stay: what was said is gone, that something was said and from
    which document versions remains provable.

    sources_json is cleared too. It carries the filenames of the client's own
    documents, and a filename is frequently the client's name.
    """
    if not client_id:
        return 0
    conn = connect()
    try:
        cur = conn.execute(
            "UPDATE answers SET question = ?, answer = ?, client_id = '', "
            "sources_json = '[]', verdict_note = '' "
            "WHERE client_id = ? AND question != ?",
            (REDACTED, REDACTED, client_id, REDACTED),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get(answer_id: int) -> Optional[dict]:
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM answers WHERE id = ?", (int(answer_id),)).fetchone()
        if not row:
            return None
        out = dict(row)
        out["sources"] = json.loads(out.pop("sources_json") or "[]")
        return out
    finally:
        conn.close()


# Minutes a question would have taken by hand: open the guide, find the page,
# read the clause, check it is the current version. Deliberately conservative
# and stated as an assumption rather than buried, because the whole number
# rests on it and someone will ask.
MINUTES_BY_HAND = float(os.environ.get("FORTITUDO_MINUTES_BY_HAND", "6"))


@dataclass
class Report:
    since: str
    total: int = 0
    by_room: Dict[str, int] = field(default_factory=dict)
    verdicts: Dict[str, int] = field(default_factory=dict)
    unmarked: int = 0
    span_flagged: int = 0
    version_clash: int = 0
    unapproved: int = 0
    high_risk: int = 0
    as_of_questions: int = 0
    client_questions: int = 0
    seconds: float = 0.0

    @property
    def marked(self) -> int:
        return sum(self.verdicts.values())

    @property
    def wrong_rate(self) -> Optional[float]:
        """Of the answers you judged, how many were wrong or thin.

        None when nothing has been marked — an unmeasured rate is not zero,
        and reporting it as zero is how a tool looks perfect until it is used.
        """
        if not self.marked:
            return None
        bad = self.verdicts.get("wrong", 0) + self.verdicts.get("thin", 0)
        return bad / self.marked

    @property
    def hours_saved(self) -> float:
        """Questions answered, times minutes-by-hand, minus what it cost to ask."""
        return max(0.0, (self.total * MINUTES_BY_HAND * 60 - self.seconds) / 3600)


def report(days: int = 7) -> Report:
    """What the desk did over the last `days`. The A1 evidence, computed."""
    conn = connect()
    try:
        since = conn.execute(
            "SELECT datetime('now', ?)", (f"-{max(int(days), 1)} days",)
        ).fetchone()[0]
        rows = conn.execute(
            "SELECT * FROM answers WHERE asked_at >= ? ORDER BY asked_at", (since,)
        ).fetchall()
    finally:
        conn.close()

    rep = Report(since=since)
    for row in rows:
        rep.total += 1
        rep.by_room[row["room"]] = rep.by_room.get(row["room"], 0) + 1
        if row["verdict"]:
            rep.verdicts[row["verdict"]] = rep.verdicts.get(row["verdict"], 0) + 1
        else:
            rep.unmarked += 1
        rep.span_flagged += int(row["span_flagged"] or 0)
        rep.version_clash += int(row["version_clash"] or 0)
        rep.unapproved += int(row["unapproved"] or 0)
        rep.high_risk += 1 if (row["invent_risk"] or "") == "high" else 0
        rep.client_questions += int(row["used_client"] or 0)
        rep.seconds += float(row["seconds"] or 0)
        # An explicit as-of is the question the normal systems cannot answer.
        if (row["as_of"] or "") and (row["as_of"] or "")[:10] != str(row["asked_at"])[:10]:
            rep.as_of_questions += 1
    return rep


def render(rep: Report) -> str:
    lines = [
        "Fortitudo desk — answer log",
        "=" * 52,
        f"  since {rep.since}",
        "",
        f"  {'questions answered':28} {rep.total:>6}",
        f"  {'time saved (hours)':28} {rep.hours_saved:>6.1f}"
        f"   at {MINUTES_BY_HAND:.0f} min/question by hand",
    ]
    if rep.by_room:
        lines.append("")
        for room, n in sorted(rep.by_room.items(), key=lambda kv: -kv[1]):
            lines.append(f"  {('  ' + room):28} {n:>6}")

    lines += ["", "  Quality"]
    if rep.marked:
        rate = rep.wrong_rate or 0.0
        lines.append(f"  {'  judged wrong or thin':28} {rate:>5.0%}"
                     f"   ({rep.marked} of {rep.total} marked)")
    else:
        lines.append(f"  {'  judged':28} {'none':>6}"
                     "   mark a few with --mark; an unmeasured rate is not zero")
    for label, value in (("desk removed a figure", rep.span_flagged),
                         ("rival document versions", rep.version_clash),
                         ("unapproved document cited", rep.unapproved),
                         ("desk flagged high risk", rep.high_risk)):
        lines.append(f"  {('  ' + label):28} {value:>6}")

    lines += ["", "  Worth telling Liberty"]
    lines.append(f"  {'  as-of questions':28} {rep.as_of_questions:>6}"
                 "   answers the normal systems cannot give")
    lines.append(f"  {'  client-file questions':28} {rep.client_questions:>6}")
    if rep.unmarked:
        lines += ["", f"  {rep.unmarked} answers not yet judged. The wrong-answer rate is"
                      " the number that gets asked about — mark them as you go."]
    return "\n".join(lines)


# How much of an answer the list carries. Enough to recognise it and to judge
# an obvious miss; not so much that the list becomes the answer and nobody
# opens the row. A wrong figure is usually visible in the first few lines.
PREVIEW_CHARS = 400


def recent(limit: int = 20, only_unmarked: bool = False) -> List[dict]:
    """The most recent answers, with enough of each to judge it.

    The first version returned the question and the verdict but not the answer,
    which made the marking screen impossible to use honestly: nobody can say
    whether an answer was wrong while looking only at the question.
    """
    conn = connect()
    try:
        sql = ("SELECT id, asked_at, room, question, answer, verdict, "
               "verdict_note, client_id, as_of, seconds, span_flagged, "
               "version_clash, unapproved, invent_risk, asked_by FROM answers")
        if only_unmarked:
            sql += " WHERE verdict = ''"
        sql += " ORDER BY id DESC LIMIT ?"
        rows = conn.execute(sql, (max(int(limit), 1),)).fetchall()
    finally:
        conn.close()
    out = []
    for row in rows:
        item = dict(row)
        text = item.pop("answer") or ""
        item["preview"] = text[:PREVIEW_CHARS]
        item["truncated"] = len(text) > PREVIEW_CHARS
        # The flags the desk raised on itself, as one list the UI can render
        # without knowing what each column means.
        item["flags"] = [name for name, on in (
            ("span-check", item.pop("span_flagged")),
            ("versions", item.pop("version_clash")),
            ("unapproved", item.pop("unapproved")),
        ) if on]
        if (item.get("invent_risk") or "") == "high":
            item["flags"].append("high risk")
        out.append(item)
    return out


def main() -> int:
    import argparse
    ap = argparse.ArgumentParser(description="The desk's answer log.")
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--list", action="store_true", help="recent answers")
    ap.add_argument("--todo", action="store_true", help="answers not yet judged")
    ap.add_argument("--mark", metavar="ID", type=int, help="judge an answer")
    ap.add_argument("--verdict", choices=sorted(VERDICTS))
    ap.add_argument("--note", default="")
    ap.add_argument("--show", metavar="ID", type=int, help="one answer in full")
    args = ap.parse_args()

    if args.mark:
        if not args.verdict:
            print("--mark needs --verdict:")
            for key, meaning in VERDICTS.items():
                print(f"  {key:6} {meaning}")
            return 2
        ok = mark(args.mark, args.verdict, args.note)
        print(f"answer {args.mark} marked {args.verdict}" if ok
              else f"no answer {args.mark}")
        return 0 if ok else 1

    if args.show:
        row = get(args.show)
        if not row:
            print(f"no answer {args.show}")
            return 1
        print(f"[{row['id']}] {row['asked_at']}  room={row['room']}  "
              f"as_of={row['as_of']}  snapshot={row['snapshot']}")
        print(f"\nQ: {row['question']}\n\nA: {row['answer']}\n")
        print("Built from:")
        for src in row["sources"]:
            print(f"  {src['score']:.4f}  {src['source']}  p.{src['page']}")
        if row["verdict"]:
            print(f"\nJudged: {row['verdict']}  {row['verdict_note']}")
        return 0

    if args.list or args.todo:
        for row in recent(30, only_unmarked=args.todo):
            mark_str = row["verdict"] or "-"
            print(f"[{row['id']:5}] {row['asked_at'][:16]}  {row['room']:6} "
                  f"{mark_str:6} {row['question'][:60]}")
        return 0

    print(render(report(args.days)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
