"""sqlite page index. As-of columns migrate in place."""
import os
import sqlite3
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from config import DB_PATH, DATA_DIR
from versioning import guess_meta_from_name, sha256_text

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    source    TEXT NOT NULL,
    page      INTEGER NOT NULL,
    text      TEXT NOT NULL,
    embedding BLOB NOT NULL,
    content_hash TEXT DEFAULT '',
    effective_from TEXT DEFAULT '',
    effective_to TEXT DEFAULT '',
    domain TEXT DEFAULT '',
    UNIQUE(source, page)
);
CREATE INDEX IF NOT EXISTS idx_source ON pages(source);

CREATE TABLE IF NOT EXISTS source_meta (
    source    TEXT PRIMARY KEY,
    mtime     REAL NOT NULL,
    size      INTEGER NOT NULL,
    page_count INTEGER NOT NULL,
    updated_at TEXT NOT NULL
);
"""

_CACHE: Optional[Tuple[List[Any], np.ndarray]] = None
_CACHE_MTIME: float = 0


def _migrate(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(pages)").fetchall()}
    for name, ddl in (
        ("content_hash", "TEXT DEFAULT ''"),
        ("effective_from", "TEXT DEFAULT ''"),
        ("effective_to", "TEXT DEFAULT ''"),
        ("domain", "TEXT DEFAULT ''"),
    ):
        if name not in cols:
            conn.execute(f"ALTER TABLE pages ADD COLUMN {name} {ddl}")
    conn.commit()


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    _migrate(conn)
    return conn


def clear_source(conn: sqlite3.Connection, source: str):
    conn.execute("DELETE FROM pages WHERE source = ?", (source,))
    conn.execute("DELETE FROM source_meta WHERE source = ?", (source,))
    conn.commit()
    global _CACHE
    _CACHE = None


def set_source_meta(conn: sqlite3.Connection, source: str, mtime: float, size: int, page_count: int):
    from datetime import datetime
    conn.execute(
        "INSERT OR REPLACE INTO source_meta (source, mtime, size, page_count, updated_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (source, mtime, size, page_count, datetime.now().isoformat(timespec="seconds")),
    )


def get_source_meta(conn: sqlite3.Connection, source: str) -> Optional[Tuple[float, int, int]]:
    row = conn.execute(
        "SELECT mtime, size, page_count FROM source_meta WHERE source = ?", (source,)
    ).fetchone()
    return (row[0], row[1], row[2]) if row else None


def _domain_of(source: str) -> str:
    s = source or ""
    if s.startswith(("learn:craft", "guide:craft")) or "/craft/" in s:
        return "craft"
    if s.startswith(("learn:voice",)):
        return "voice"
    if s.startswith(("learn:drama", "drama:")):
        return "drama"
    if s.startswith("client:"):
        return "client"
    if s.startswith("learn:"):
        return "learn"
    return "fa"


def add_page(
    conn: sqlite3.Connection,
    source: str,
    page: int,
    text: str,
    embedding: Any,
    effective_from: str = "",
    effective_to: str = "",
    domain: str = "",
):
    guessed = guess_meta_from_name(source)
    vec = np.asarray(embedding, dtype=np.float32)
    conn.execute(
        "INSERT OR REPLACE INTO pages "
        "(source, page, text, embedding, content_hash, effective_from, effective_to, domain) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            source,
            page,
            text,
            vec.tobytes(),
            sha256_text(text),
            effective_from or guessed.get("effective_from") or "",
            effective_to or guessed.get("effective_to") or "",
            domain or _domain_of(source),
        ),
    )


def page_meta(conn: sqlite3.Connection) -> Dict[int, Tuple[str, str, str]]:
    """id -> (effective_from, effective_to, domain)"""
    _migrate(conn)
    out = {}
    for row in conn.execute("SELECT id, effective_from, effective_to, domain FROM pages"):
        out[row[0]] = (row[1] or "", row[2] or "", row[3] or "")
    return out


def load_all(conn: sqlite3.Connection) -> Tuple[List[Any], np.ndarray]:
    global _CACHE, _CACHE_MTIME
    try:
        mtime = os.path.getmtime(DB_PATH)
    except OSError:
        mtime = 0
    if _CACHE is not None and mtime <= _CACHE_MTIME:
        return _CACHE
    rows = conn.execute("SELECT id, source, page, text, embedding FROM pages").fetchall()
    if not rows:
        _CACHE = ([], np.zeros((0, 0), dtype=np.float32))
        _CACHE_MTIME = mtime
        return _CACHE
    vecs = np.stack([np.frombuffer(r[4], dtype=np.float32) for r in rows])
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    _CACHE = (rows, vecs / norms)
    _CACHE_MTIME = mtime
    return _CACHE


def sources(conn: sqlite3.Connection) -> List[Tuple[str, int]]:
    return [
        (r[0], r[1])
        for r in conn.execute(
            "SELECT source, COUNT(*) FROM pages GROUP BY source ORDER BY source"
        ).fetchall()
    ]


def invalidate_cache():
    global _CACHE
    _CACHE = None
