"""
Fortitudo AI - storage layer

Deliberately boring: sqlite + numpy. No vector database, no Docker, no
services to keep running. A few thousand pages brute-forces in milliseconds
and you can open the .db in any sqlite viewer to see exactly what is indexed.
"""
import os
import sqlite3
from typing import List, Tuple, Optional, Any

import numpy as np
from config import DB_PATH, DATA_DIR

SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    source    TEXT NOT NULL,
    page      INTEGER NOT NULL,
    text      TEXT NOT NULL,
    embedding BLOB NOT NULL,
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

# In-memory cache for the vector matrix to avoid redundant SQLite BLOB decoding
# and normalization on every search query.
_CACHE: Optional[Tuple[List[Any], np.ndarray]] = None
_CACHE_MTIME: float = 0


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(SCHEMA)
    return conn


def clear_source(conn: sqlite3.Connection, source: str):
    """Remove an existing document so it can be re-ingested cleanly."""
    conn.execute("DELETE FROM pages WHERE source = ?", (source,))
    conn.execute("DELETE FROM source_meta WHERE source = ?", (source,))
    conn.commit()
    # Invalidate cache
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


def add_page(conn: sqlite3.Connection, source: str, page: int, text: str, embedding: Any):
    vec = np.asarray(embedding, dtype=np.float32)
    conn.execute(
        "INSERT OR REPLACE INTO pages (source, page, text, embedding) "
        "VALUES (?, ?, ?, ?)",
        (source, page, text, vec.tobytes()),
    )
    # Cache will be refreshed on next load_all due to DB file mtime change


def load_all(conn: sqlite3.Connection) -> Tuple[List[Any], np.ndarray]:
    """Return (rows, matrix) where matrix is L2-normalised for cosine.
    Uses an in-memory cache that refreshes if the database file changes.
    """
    global _CACHE, _CACHE_MTIME

    try:
        mtime = os.path.getmtime(DB_PATH)
    except OSError:
        mtime = 0

    if _CACHE is not None and mtime <= _CACHE_MTIME:
        return _CACHE

    rows = conn.execute(
        "SELECT id, source, page, text, embedding FROM pages"
    ).fetchall()

    if not rows:
        _CACHE = ([], np.zeros((0, 0), dtype=np.float32))
        _CACHE_MTIME = mtime
        return _CACHE

    # Decode BLOBs and stack into a matrix
    vecs = np.stack([np.frombuffer(r[4], dtype=np.float32) for r in rows])

    # L2 normalize for cosine similarity via dot product
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
