"""File a lesson so Learn can teach Craft (or Advisor) without mixing rooms."""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from config import DOCS_DIR

Applies = Literal["craft", "advisor", "voice", "drama", "all"]

BRANCH_DIR = {
    "craft": DOCS_DIR / "learn" / "craft",
    "advisor": DOCS_DIR / "learn" / "advisor",
    "voice": DOCS_DIR / "learn" / "voice",
    "drama": DOCS_DIR / "learn" / "drama",
    "all": DOCS_DIR / "learn" / "all",
}


def _slug(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return (s or "lesson")[:60]


def file_lesson(title: str, text: str, applies: Applies = "craft") -> Path:
    applies = applies if applies in BRANCH_DIR else "craft"
    folder = BRANCH_DIR[applies]
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    path = folder / f"{stamp}-{_slug(title)}.md"
    body = (
        f"# {title.strip() or 'Lesson'}\n\n"
        f"Applies to: {applies}\n"
        f"Filed: {stamp}\n\n"
        f"{text.strip()}\n"
    )
    path.write_text(body, encoding="utf-8")
    if applies != "advisor":
        try:
            import ingest, store
            ingest.ingest_file(
                store.connect(),
                path,
                rebuild=False,
                source_name=f"learn:{applies}:{path.name}",
            )
        except Exception:
            pass
    return path


def craft_lessons_text(limit_chars: int = 3500) -> str:
    folder = BRANCH_DIR["craft"]
    if not folder.exists():
        return ""
    parts = []
    for p in sorted(folder.glob("*.md"), reverse=True)[:12]:
        parts.append(p.read_text(encoding="utf-8")[:800])
    blob = "\n\n".join(parts)
    return blob[:limit_chars]
