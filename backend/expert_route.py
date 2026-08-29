"""One gate for the whole desk.

Classify the job → pick the room → load that room's expert standard
→ refuse work that belongs elsewhere.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from reason import DOCTRINE

ROOM_HINTS = [
    ("roa", re.compile(r"\b(record of advice|roa draft|suitability draft)\b", re.I)),
    ("drama", re.compile(r"\b(eisteddfod|adjudicat|rubric|drama syllabus|monologue)\b", re.I)),
    ("craft", re.compile(r"\b(website|mockup|shop page|flyer|qr|storefront|plumber|salon|craft)\b", re.I)),
    ("voice", re.compile(r"\b(instagram|caption|carousel|voice note|shame|money psycholog)\b", re.I)),
    ("learn", re.compile(r"\b(teach the desk|file this rule|learn this|doctrine)\b", re.I)),
    ("fa", re.compile(r"\b(waiting period|survival|severity|exclusion|premium|lifestyle protector|liberty)\b", re.I)),
]


@dataclass(frozen=True)
class Route:
    room: str
    why: str
    refuse: str
    standard: str
    tools: List[str]


TOOLS = {
    "fa": ["retrieve product pages", "cite SOURCE PAGE", "span_check"],
    "roa": ["retrieve as_of", "list gaps", "draft banner"],
    "voice": ["draft caption", "claimGuard"],
    "craft": ["design_reason", "trade_page or wealth mockup", "flyer + QR"],
    "drama": ["rubric language", "human mark"],
    "learn": ["file_lesson"],
}

REFUSE = {
    "fa": "Do not draft an Instagram caption or a plumber page here.",
    "roa": "Do not sign this. Do not treat it as advice to the client.",
    "voice": "Do not quote a waiting period unless a filed guide is cited.",
    "craft": "Do not build a page from an FNA. Practice storefront only, or a shop.",
    "drama": "Do not award the mark.",
    "learn": "Do not perform the other rooms. File the rule.",
}

STANDARD = {
    "fa": "Expert = the cited page is right. If the table is thin, send the adviser to the PDF.",
    "roa": "Expert = every need on file is listed, every gap is named, the banner stays on.",
    "voice": "Expert = one true line about money fear. No product pitch unless asked.",
    "craft": "Expert = a phone can call in one tap. Headline is job + place. Nothing invented.",
    "drama": "Expert = comment language tied to a rubric line the human already saw.",
    "learn": "Expert = a rule other rooms can load tomorrow, tagged to one branch.",
}


def classify(text: str, hinted_room: str = "") -> Route:
    if hinted_room and hinted_room.lower() in STANDARD:
        room = hinted_room.lower()
        why = f"room set by the desk ({room})"
    else:
        room, why = "fa", "default Advisor — product wording"
        blob = text or ""
        for rid, pat in ROOM_HINTS:
            if pat.search(blob):
                room, why = rid, f"matched {rid} language"
                break
        if room == "craft":
            try:
                from crossover import refuse_reason
                extra = refuse_reason(blob)
                if extra:
                    return Route("fa", why, extra, STANDARD["fa"], TOOLS["fa"])
            except Exception:
                pass
    return Route(room, why, REFUSE[room], STANDARD[room], TOOLS[room])


def expert_system(room: str) -> str:
    room = room if room in DOCTRINE else "fa"
    return (
        f"You are Fortitudo AI in the {room} room.\n"
        f"{STANDARD[room]}\n{DOCTRINE[room]}\n{REFUSE[room]}\n"
        "You are an evidence engine for Gert Fourie (FSP 2409). "
        "You are not the FSP. You do not advise the end client.\n"
        "Shape: Take / Evidence / Gap / Next. Cite or omit. Never invent."
    )
