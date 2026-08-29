"""One gate for the whole desk.

Classify the job → pick the room → load that room's expert standard
→ refuse work that belongs elsewhere.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List

from reason import DOCTRINE

# Two weights. INTENT is what the adviser is asking the desk to *do* — the
# reliable signal. TOPIC is vocabulary that often appears in a room's work but
# also turns up incidentally: a client can be a plumber, and a severity benefit
# can belong to a web designer. First-match-wins on a single ordered list sent
# both of those product questions to Craft.
INTENT = {
    "roa": [r"\b(roa draft|suitability draft|draft (a |the )?record of advice|draft an? roa)\b"],
    "drama": [r"\b(adjudicat\w*|mark this|show the rubric|draft a comment for)\b"],
    "craft": [
        r"\b(build|make|draft|design|mock up|mockup|print)\b[^.?!]{0,40}"
        r"\b(page|site|website|storefront|flyer|poster|letter|qr)\b",
        r"\b(shop page|trade page|door letter|walk-?in pack)\b",
    ],
    "voice": [r"\b(write|draft|post)\b[^.?!]{0,30}\b(caption|carousel|instagram|linkedin|status)\b"],
    "learn": [r"\b(teach the desk|file this rule|learn this|remember this rule)\b"],
    "fa": [r"\b(what|which|how|does|is|are)\b[^.?!]{0,60}\b(waiting period|survival|severity|exclusion|premium|benefit)\b"],
}

TOPIC = {
    "roa": [r"\brecord of advice\b", r"\bsuitability\b"],
    "drama": [r"\b(eisteddfod|rubric|drama syllabus|monologue)\b"],
    "craft": [r"\b(flyer|qr code|storefront|shop front|walk-?in)\b"],
    "voice": [r"\b(instagram|caption|carousel|money psycholog\w*|money shame)\b"],
    "learn": [r"\bdoctrine\b"],
    "fa": [
        r"\b(waiting period|survival period|severity|exclusion|premium|"
        r"lifestyle protector|liberty|policy wording|benefit)\b",
    ],
}

INTENT_WEIGHT = 3
TOPIC_WEIGHT = 1

# Ties go to the room that constrains the answer most. Craft is last: it is the
# only room with no citation duty, so it must be *won*, never fallen into.
PRECEDENCE = ["roa", "fa", "drama", "learn", "voice", "craft"]

_INTENT_RE = {r: [re.compile(p, re.I) for p in pats] for r, pats in INTENT.items()}
_TOPIC_RE = {r: [re.compile(p, re.I) for p in pats] for r, pats in TOPIC.items()}


def score_rooms(text: str):
    """Weighted score per room. Intent beats vocabulary."""
    blob = text or ""
    scores = {}
    for room in PRECEDENCE:
        hits = sum(INTENT_WEIGHT for p in _INTENT_RE.get(room, []) if p.search(blob))
        hits += sum(TOPIC_WEIGHT for p in _TOPIC_RE.get(room, []) if p.search(blob))
        scores[room] = hits
    return scores


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
        return Route(room, f"room set by the desk ({room})", REFUSE[room], STANDARD[room], TOOLS[room])

    blob = text or ""
    scores = score_rooms(blob)
    best = max(scores.values())
    if best == 0:
        room, why = "fa", "default Advisor — product wording"
    else:
        room = next(r for r in PRECEDENCE if scores[r] == best)
        tied = [r for r in PRECEDENCE if scores[r] == best]
        why = f"matched {room} language (score {best})"
        if len(tied) > 1:
            why += f"; tie with {', '.join(t for t in tied if t != room)} went to the stricter room"

    if room == "craft":
        # Craft may edit the practice storefront, never a client matter.
        try:
            from crossover import refuse_reason
            extra = refuse_reason(blob)
            if extra:
                return Route("fa", why + "; client file", extra, STANDARD["fa"], TOOLS["fa"])
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
