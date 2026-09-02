"""A desk that can be scored.

Every refinement to this AI — a bigger model, more doctrine, a rerank pass —
was until now unfalsifiable. Nothing said whether an answer got better, so
"better" meant "the last one I looked at seemed fine".

This builds a fixture corpus with known contents, then measures the parts of
the desk that are deterministic: which room a question lands in, whether the
right page is retrieved, whether an ungrounded figure survives, whether a
cross-room ask is refused, and whether the Craft gate holds. None of it needs
Ollama, so it runs in CI on every commit.

Answer quality itself needs the model and lives behind --live.
"""
from __future__ import annotations

import hashlib
import re
import sqlite3
from pathlib import Path
from typing import Dict, List

import numpy as np

CORPUS = Path(__file__).resolve().parent / "corpus"
EMBED_DIM = 256          # smaller than bge-m3; only has to be self-consistent

_TOKEN = re.compile(r"[a-z0-9]+")


def fake_embed(texts):
    """Deterministic lexical embedding — feature hashing, L2 normalised.

    A real evaluation would use the real embedder, but that needs Ollama and
    makes the score depend on a model that may not be installed. Hashing keeps
    dense retrieval genuinely similarity-preserving (shared words move vectors
    together) while staying reproducible on any machine, so a change in score
    means a change in the desk rather than a change in the weather.
    """
    if isinstance(texts, str):
        texts = [texts]
    out = []
    for text in texts:
        vec = np.zeros(EMBED_DIM, dtype=np.float32)
        for token in _TOKEN.findall((text or "").lower()):
            h = int(hashlib.blake2b(token.encode(), digest_size=8).hexdigest(), 16)
            vec[h % EMBED_DIM] += 1.0
            # A second slot per token so two texts sharing one word do not
            # collide into an identical direction.
            vec[(h >> 17) % EMBED_DIM] += 0.5
        norm = float(np.linalg.norm(vec)) or 1.0
        out.append((vec / norm).tolist())
    return out


def parse_pages(text: str) -> List[tuple]:
    """Split a fixture file on %%PAGE markers into (page_number, body)."""
    pages = []
    for chunk in re.split(r"^%%PAGE\s+(\d+)\s*$", text, flags=re.M)[1:]:
        if chunk.strip().isdigit():
            pages.append([int(chunk.strip()), ""])
        elif pages:
            pages[-1][1] = chunk.strip()
    return [(n, body) for n, body in pages if body]


def build_index() -> sqlite3.Connection:
    """An in-memory index over the fixture corpus, wired for offline search."""
    import store, retrieval

    store.invalidate_cache()
    conn = sqlite3.connect(":memory:")
    conn.executescript(store.SCHEMA if hasattr(store, "SCHEMA") else "")
    # store.connect() owns the schema; replay it here against memory.
    for stmt in _schema_statements():
        conn.executescript(stmt)

    for path in sorted(CORPUS.glob("*.txt")):
        # Client fixtures are indexed the way ingest names them, so scoping is
        # exercised against the real prefix rather than a stand-in.
        source = (f"client:{path.stem[len('client_'):]}:fna.pdf"
                  if path.stem.startswith("client_") else f"guide:{path.stem}")
        for page, body in parse_pages(path.read_text(encoding="utf-8")):
            store.add_page(conn, source, page, body, fake_embed(body)[0])
    conn.commit()
    store.invalidate_cache()
    retrieval.embed = fake_embed          # offline, deterministic
    return conn


def _schema_statements() -> List[str]:
    import store
    src = Path(store.__file__).read_text(encoding="utf-8")
    return re.findall(r'"""(CREATE TABLE.*?)"""', src, re.S) or [_FALLBACK_SCHEMA]


_FALLBACK_SCHEMA = """
CREATE TABLE IF NOT EXISTS pages (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    page INTEGER NOT NULL,
    text TEXT NOT NULL,
    embedding BLOB NOT NULL,
    content_hash TEXT,
    effective_from TEXT,
    effective_to TEXT,
    domain TEXT
);
CREATE TABLE IF NOT EXISTS source_meta (
    source TEXT PRIMARY KEY,
    mtime REAL,
    size INTEGER,
    page_count INTEGER
);
"""


class Score:
    """A tally that knows which cases failed, not just how many."""

    def __init__(self, name: str):
        self.name = name
        self.passed = 0
        self.failed: List[str] = []

    def check(self, ok: bool, label: str):
        if ok:
            self.passed += 1
        else:
            self.failed.append(label)

    @property
    def total(self) -> int:
        return self.passed + len(self.failed)

    @property
    def rate(self) -> float:
        return self.passed / self.total if self.total else 1.0

    def line(self) -> str:
        bar = f"{self.passed}/{self.total}"
        return f"  {self.name:24} {bar:>8}  {self.rate:6.1%}"


def report(scores: List[Score], threshold: float = 1.0) -> int:
    """Print a scorecard. Return a shell exit code."""
    print("\nDesk evaluation")
    print("=" * 52)
    for s in scores:
        print(s.line())
    overall_pass = sum(s.passed for s in scores)
    overall_total = sum(s.total for s in scores)
    rate = overall_pass / overall_total if overall_total else 1.0
    print("-" * 52)
    print(f"  {'OVERALL':24} {f'{overall_pass}/{overall_total}':>8}  {rate:6.1%}")

    bad = [s for s in scores if s.rate < threshold]
    if bad:
        print("\nFailures:")
        for s in bad:
            for label in s.failed:
                print(f"  [{s.name}] {label}")
        return 1
    return 0
