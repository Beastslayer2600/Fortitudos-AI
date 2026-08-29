"""POPIA s69 gate for electronic Craft / Voice approaches."""
from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from config import DATA_DIR

DB_PATH = Path(DATA_DIR) / "consent.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    identifier   TEXT PRIMARY KEY,
    state        TEXT NOT NULL,
    asked_at     TEXT,
    decided_at   TEXT,
    note         TEXT,
    updated_at   TEXT NOT NULL
);
"""

UNKNOWN, ASKED, CONSENTED, REFUSED, CUSTOMER = (
    "unknown", "asked", "consented", "refused", "customer",
)


@dataclass(frozen=True)
class Decision:
    allowed: bool
    kind: str
    reason: str


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def normalise(identifier: str) -> str:
    raw = (identifier or "").strip().lower()
    if not raw:
        raise ValueError("An identifier is required.")
    if "@" in raw:
        return raw
    digits = re.sub(r"\D", "", raw)
    if not digits:
        raise ValueError("An identifier is required.")
    if digits.startswith("27") and len(digits) == 11:
        digits = "0" + digits[2:]
    elif digits.startswith("0027"):
        digits = "0" + digits[4:]
    return digits


def connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def state_of(identifier: str, conn: Optional[sqlite3.Connection] = None) -> str:
    own = conn is None
    conn = conn or connect()
    try:
        row = conn.execute(
            "SELECT state FROM contacts WHERE identifier = ?",
            (normalise(identifier),),
        ).fetchone()
        return row["state"] if row else UNKNOWN
    finally:
        if own:
            conn.close()


def may_contact(identifier: str, conn: Optional[sqlite3.Connection] = None) -> Decision:
    own = conn is None
    conn = conn or connect()
    try:
        state = state_of(identifier, conn)
        if state == REFUSED:
            return Decision(False, "none", "Consent was refused. That is permanent.")
        if state == CONSENTED:
            return Decision(True, "marketing", "Consent on record.")
        if state == CUSTOMER:
            return Decision(
                True, "marketing",
                "Existing customer — s69(3). Similar services only, opt-out in every message.",
            )
        if state == ASKED:
            return Decision(
                False, "none",
                "Already approached once for consent. Silence is not consent.",
            )
        return Decision(
            True, "consent_request",
            "First electronic message must request consent, not pitch.",
        )
    finally:
        if own:
            conn.close()


def _set(identifier: str, state: str, note: str = "", stamp_asked: bool = False) -> str:
    key = normalise(identifier)
    conn = connect()
    try:
        row = conn.execute("SELECT * FROM contacts WHERE identifier = ?", (key,)).fetchone()
        asked = (_now() if stamp_asked else (row["asked_at"] if row else None))
        decided = _now() if state in (CONSENTED, REFUSED, CUSTOMER) else (row["decided_at"] if row else None)
        conn.execute(
            "INSERT OR REPLACE INTO contacts "
            "(identifier, state, asked_at, decided_at, note, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (key, state, asked, decided, note, _now()),
        )
        conn.commit()
        return state
    finally:
        conn.close()


def mark_asked(identifier: str, note: str = "") -> str:
    return _set(identifier, ASKED, note, stamp_asked=True)


def mark_consented(identifier: str, note: str = "") -> str:
    return _set(identifier, CONSENTED, note)


def mark_refused(identifier: str, note: str = "") -> str:
    return _set(identifier, REFUSED, note)


def mark_customer(identifier: str, note: str = "") -> str:
    return _set(identifier, CUSTOMER, note)
