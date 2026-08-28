"""
Domain registry for Fortitudo AI.

Today: single product index under data/index.db.
Stage 2: drama syllabi can use a source prefix or separate DB without
rewriting callers — keep client FA data isolated from learner drama records.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict

from config import DATA_DIR, DOCS_DIR


@dataclass(frozen=True)
class Domain:
    id: str
    label: str
    docs_dir: Path
    db_path: Path
    source_prefix: str  # empty for FA product docs; "drama:" for stage 2


DOMAINS: Dict[str, Domain] = {
    "fa": Domain(
        id="fa",
        label="Financial advice — product technical",
        docs_dir=DOCS_DIR,
        db_path=DATA_DIR / "index.db",
        source_prefix="",
    ),
    "drama": Domain(
        id="drama",
        label="Drama & eisteddfod — syllabi and adjudication",
        docs_dir=DOCS_DIR,  # can later point at docs/drama/
        db_path=DATA_DIR / "drama_index.db",
        source_prefix="drama:",
    ),
}

DEFAULT_DOMAIN = "fa"


def get_domain(domain_id: str = DEFAULT_DOMAIN) -> Domain:
    return DOMAINS.get(domain_id, DOMAINS[DEFAULT_DOMAIN])
