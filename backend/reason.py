from __future__ import annotations
import re
FIGURE_RE = re.compile(r"\b(waiting|survival|premium|percent|percentage|exclusion|benefit|severity|payout|deferment|term|sum assured|rate)\b|%", re.I)
PRACTICE_RE = re.compile(r"\b(how should|voice|letter|page|shop|craft|adjudicat|drama|anxiety|shame|avoid|review language|first screen|brand|fortitudo|screenshot|whatsapp|idea|design|psycholog)\b", re.I)
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
ANSWER_SHAPE = """Write in this shape (omit an empty heading):\n\nTake\n- one or two sentences.\n\nEvidence\n- each fact with SOURCE and PAGE, or file name, or SIGHT\n\nGap\n- what is not in the extracts\n\nNext\n- one action for the adviser, not advice to the end client\n"""
