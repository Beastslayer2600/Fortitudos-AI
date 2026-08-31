"""Shared reasoning shape for every Fortitudo room.

Craft already has design_reason. Advisor, RoA, Voice, Drama, Learn
use the same order: doctrine + filed lessons + extracts → spec → prose.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import List

FIGURE_RE = re.compile(
    r"\b(waiting|survival|premium|percent|percentage|exclusion|benefit|severity|payout|deferment|term|sum assured|rate)\b|%",
    re.I,
)
PRACTICE_RE = re.compile(
    r"\b(how should|voice|letter|page|shop|craft|adjudicat|drama|anxiety|shame|avoid|review language|first screen|brand|fortitudo|screenshot|whatsapp|idea|design|psycholog)\b",
    re.I,
)
SOURCE_RE = re.compile(r"\b(?:SOURCE[:\s]+|learn:[^\s]+|[A-Za-z0-9._-]+\.pdf)\b")
NAME_RE = re.compile(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b")


def is_figure_question(text: str) -> bool:
    return bool(FIGURE_RE.search(text or ""))


def is_practice_question(text: str) -> bool:
    return bool(PRACTICE_RE.search(text or "")) and not is_figure_question(text)


def anchors_from_history(question: str, history=None) -> str:
    bits = [question.strip()]
    if history:
        for turn in history[-8:]:
            text = str(turn.get("content", ""))
            bits.extend(SOURCE_RE.findall(text)[:6])
            bits.extend(NAME_RE.findall(text)[:4])
    uniq, seen = [], set()
    for b in bits:
        key = b.lower().strip()
        if key and key not in seen:
            seen.add(key)
            uniq.append(b.strip())
    return " ".join(uniq)[:1600]


ANSWER_SHAPE = """Write in this shape (omit an empty heading):

Take
- one or two sentences.

Evidence
- each fact with SOURCE and PAGE, or file name, or SIGHT

Gap
- what is not in the extracts

Next
- one action for the adviser, not advice to the end client
"""

DOCTRINE = {
    "fa": (
        "Room: Advisor. You retrieve product wording.\n"
        "Order: what was asked → which pages apply → figures only if cited → gaps.\n"
        "Never invent a waiting period, %, definition, or FSP number.\n"
        "Next is something the adviser does (open the cited page), not advice to a client."
    ),
    "roa": (
        "Room: Record of Advice draft. Human signs. Banner stays on.\n"
        "Order: facts on file → needs stated → product pages in force as_of the RoA date → gaps.\n"
        "Do not recommend. List what the draft still lacks."
    ),
    "voice": (
        "Room: Voice / Studio. Money psychology content for Instagram.\n"
        "Order: feeling named → one true line → no product figures unless a filed guide is cited.\n"
        "No shame. No 'DM REVIEW' unless asked. South African English."
    ),
    "craft": (
        "Room: Craft. Local shop page.\n"
        "Order: intent → audience → first screen → headline job+suburb → omit missing hours/reviews.\n"
        "Call first. No invented 24/7.\n"
        "You may author the HTML and its CSS. Design freely; invent no fact."
    ),
    "drama": (
        "Room: Drama. Adjudication comments.\n"
        "Order: rubric criterion → what was seen → comment language → the mark stays human.\n"
        "Do not award a percentage. Do not invent syllabus rules."
    ),
    "learn": (
        "Room: Learn. File a rule, do not perform the other rooms.\n"
        "Order: what the lesson is → which room it applies to → one example → what it must never do."
    ),
}

SYSTEM = """You are Fortitudo's reasoning layer for one desk room.
Output ONLY one JSON object. No markdown.
Keys: take, evidence (list of short cited lines), gap, next, omit (list), invent_risk (low|med|high).
Use the room doctrine and any filed Learn lessons. If extracts are empty, say so in gap.
Never invent figures, hours, marks, or testimonials.
"""


@dataclass
class Thought:
    take: str
    evidence: List[str] = field(default_factory=list)
    gap: str = ""
    next: str = ""
    omit: List[str] = field(default_factory=list)
    invent_risk: str = "low"
    raw: str = ""


def _lessons(room: str) -> str:
    try:
        from learn_teach import BRANCH_DIR
        folder = BRANCH_DIR.get(room) or BRANCH_DIR.get("all")
        if not folder or not folder.exists():
            return ""
        parts = [p.read_text(encoding="utf-8")[:600] for p in sorted(folder.glob("*.md"), reverse=True)[:8]]
        return "\n\n".join(parts)[:2400]
    except Exception:
        return ""


def _extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("no json")
    return json.loads(text[start:end])


def fallback_thought(room: str, question: str) -> Thought:
    return Thought(
        take="Use the extracts. If a figure is missing, stop.",
        gap="Model did not return a spec — answer only from retrieved pages.",
        next="Open the cited page before you quote it.",
        invent_risk="med",
        raw="(fallback)",
    )


def think(room: str, question: str, extracts: str = "") -> Thought:
    room = (room or "fa").lower()
    if room not in DOCTRINE:
        room = "fa"
    user = (
        DOCTRINE[room]
        + "\n\nLESSONS:\n"
        + (_lessons(room) or "(none filed)")
        + "\n\nEXTRACTS:\n"
        + (extracts or "(none)")[:8000]
        + "\n\nQUESTION:\n"
        + question
    )
    try:
        from llm import chat
        raw = chat(SYSTEM, user, temperature=0.15, job=room)
        data = _extract_json(raw)
    except Exception:
        return fallback_thought(room, question)
    ev = data.get("evidence") or []
    if isinstance(ev, str):
        ev = [ev]
    omit = data.get("omit") or []
    if isinstance(omit, str):
        omit = [omit]
    risk = str(data.get("invent_risk") or "low").lower()
    if risk not in {"low", "med", "high"}:
        risk = "low"
    return Thought(
        take=str(data.get("take") or "")[:240],
        evidence=[str(x)[:200] for x in ev][:8],
        gap=str(data.get("gap") or "")[:240],
        next=str(data.get("next") or "")[:200],
        omit=[str(x)[:80] for x in omit][:8],
        invent_risk=risk,
        raw=raw[:2000],
    )


def as_prompt_block(thought: Thought) -> str:
    ev = "\n".join(f"- {e}" for e in thought.evidence) or "- (none)"
    omit = ", ".join(thought.omit) or "(none)"
    return (
        f"Reasoned spec (follow this; do not add omitted items):\n"
        f"Take: {thought.take}\nEvidence:\n{ev}\nGap: {thought.gap}\n"
        f"Next: {thought.next}\nOmit: {omit}\nInvent risk: {thought.invent_risk}\n"
    )
