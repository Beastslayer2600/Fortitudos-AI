"""When rooms may share a skill — and when they must not.

Craft may design the Fortitudo Wealth *marketing* site.
Craft may not open an FNA, RoA, or product waiting-period as page copy.
Advisor may not invent a plumber page.
"""
from __future__ import annotations

import re
from typing import Literal

Kind = Literal["trade", "practice", "unknown"]

PRACTICE = re.compile(
    r"\b(fortitudo wealth|financial advis|financial planner|fsp\b|fais\b|"
    r"record of advice site|practice storefront|retirement planning page|"
    r"wealth site|advisor website|adviser website)\b",
    re.I,
)
CLIENT_FILE = re.compile(
    r"\b(fna|record of advice|needs analysis|client file|policy number|"
    r"id number|said number)\b",
    re.I,
)


def kind_of(blob: str) -> Kind:
    text = blob or ""
    if CLIENT_FILE.search(text) and not PRACTICE.search(text):
        return "unknown"
    if PRACTICE.search(text):
        return "practice"
    from trade_page import is_trade_brief
    if is_trade_brief(text):
        return "trade"
    return "unknown"


def craft_may_edit_practice(blob: str) -> bool:
    """True only for the practice marketing site, not a client matter."""
    if CLIENT_FILE.search(blob or "") and not PRACTICE.search(blob or ""):
        return False
    return kind_of(blob) == "practice"


def refuse_reason(blob: str) -> str:
    if CLIENT_FILE.search(blob or "") and kind_of(blob) != "practice":
        return (
            "This is a client file. Craft does not turn an FNA or RoA into a website. "
            "Use Advisor / RoA. Craft only edits the public practice storefront."
        )
    return ""
