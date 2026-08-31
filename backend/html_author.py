"""The model writes the HTML itself, and the page is gated before it ships.

design_reason has the model emit a spec and paints the page from a fixed
template. That guarantees honesty by construction but caps the design at one
layout. Here the model authors the whole document instead — and because it can
then write anything, nothing it produces is served until it passes `gate`.

The gate is the trade. It refuses a page that is truncated, that carries script
or a form, or that states a phone number, time, price or percentage the brief
did not contain. A shop owner is shown a page about their shop, not a plausible
page about a shop like theirs.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# A whole document, not a spec. The desk default would truncate this mid-tag.
HTML_NUM_PREDICT = int(os.environ.get("FORTITUDO_HTML_NUM_PREDICT", "3500"))
# Prompt and answer share the window. At the desk default of 3072 a 3500-token
# page pushes its own instructions out of context and comes back malformed.
HTML_NUM_CTX = int(os.environ.get("FORTITUDO_HTML_NUM_CTX", "8192"))
# Wall-clock, not compute. llama3.2:3b on this CPU writes 2-5 tokens/sec, so a
# page is 10-25 minutes. The desk's 300s default would abort every attempt.
HTML_TIMEOUT = int(os.environ.get("FORTITUDO_HTML_TIMEOUT", "1800"))
# Off by default is wrong for a feature you asked for, but a machine that
# cannot spare the RAM should be able to say so without editing code.
ENABLED = (os.environ.get("FORTITUDO_HTML_AUTHOR", "1").strip().lower()
           not in {"0", "false", "off", "no"})

SYSTEM = """You are Fortitudo Craft's web developer. You write ONE complete HTML document for a South African local shop.

Output ONLY the HTML. Start at <!DOCTYPE html> and end at </html>. No markdown fences, no commentary.

Build it like this:
- One file. All CSS inside a single <style> in the head. No external CSS, fonts, images or scripts.
- Mobile first. The shop's job and suburb, and a tap-to-call link, must be visible without scrolling.
- Sections: header with the trade and suburb, one headline, a call/WhatsApp row, what they do, contact details, footer.
- A sticky bottom bar with Call and WhatsApp on small screens.
- @media print rules that hide the sticky bar.

Facts are law:
- Use ONLY the facts given. Never write a phone number, an address, opening hours, a price, a percentage, a rating, a review or a year that is not in the FACTS block.
- If a fact is missing, write the placeholder given for it, e.g. [PHONE] or [HOURS]. Never guess.
- Never write "24/7", "always open", "award-winning", "best in", "#1", "guaranteed", "5-star" or any testimonial.
- No <script>, no <form>, no on-click handlers, no tracking, no external URLs except the WhatsApp and Maps links given.
"""

BANNED_CLAIM = re.compile(
    r"\b(best in (sa|south africa|gauteng)|#1|no\.\s?1|award[- ]winning|24/7|"
    r"always open|guaranteed|5[- ]star|testimonial)\b",
    re.I,
)
UNSAFE = [
    (re.compile(r"<script\b", re.I), "contains <script>"),
    (re.compile(r"<iframe\b", re.I), "contains <iframe>"),
    (re.compile(r"<form\b", re.I), "contains <form>"),
    (re.compile(r"\bon[a-z]+\s*=", re.I), "contains an inline event handler"),
    (re.compile(r"javascript:", re.I), "contains a javascript: URL"),
]
# Facts a page must not state unless the brief did.
PHONE = re.compile(r"(?:\+?27|0)\s?\d{2}[\s-]?\d{3}[\s-]?\d{4}")
TIME = re.compile(r"\b\d{1,2}\s?[:.]\s?\d{2}\b")
MONEY = re.compile(r"\bR\s?\d[\d\s,.]*")
PERCENT = re.compile(r"\b\d+(?:\.\d+)?\s?%")
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")

STRUCTURE = ["<!doctype html", "<html", "</html>", "<body", "</body>"]


@dataclass
class Verdict:
    ok: bool
    problems: List[str] = field(default_factory=list)


def _digits(text: str) -> set:
    return {re.sub(r"\D", "", m) for m in PHONE.findall(text)}


def visible_text(html: str) -> str:
    """The document minus style/head markup — what a reader actually sees."""
    body = re.sub(r"(?is)<(script|style|head)\b.*?</\1>", " ", html)
    return re.sub(r"<[^>]+>", " ", body)


def gate(html: str, allowed: str, *, live: bool = False) -> Verdict:
    """Is this page fit to show a shop owner?

    `allowed` is every fact the page is entitled to state — the brief plus the
    extracted facts. Anything numeric outside it is treated as invented.
    """
    problems: List[str] = []
    low = (html or "").lower()

    for token in STRUCTURE:
        if token not in low:
            problems.append(f"missing {token} — the document is truncated or malformed")
    for pattern, why in UNSAFE:
        if pattern.search(html or ""):
            problems.append(why)

    seen = visible_text(html or "")
    for claim in {m.group(0) for m in BANNED_CLAIM.finditer(seen)}:
        problems.append(f"unearned claim: {claim!r}")

    allowed_digits = _digits(allowed)
    for phone in {m for m in PHONE.findall(seen)}:
        if re.sub(r"\D", "", phone) not in allowed_digits:
            problems.append(f"phone not in the brief: {phone!r}")
    for pattern, label in ((TIME, "time"), (MONEY, "price"), (PERCENT, "percentage"), (YEAR, "year")):
        for hit in {m.group(0).strip() for m in pattern.finditer(seen)}:
            compact = re.sub(r"\s+", "", hit)
            if compact not in re.sub(r"\s+", "", allowed):
                problems.append(f"{label} not in the brief: {hit!r}")

    if not live and "internal mockup" not in low:
        problems.append("missing the INTERNAL MOCKUP marker")
    if not live and "noindex" not in low:
        problems.append("missing noindex")

    return Verdict(not problems, problems)


DOCTRINE_FILE = Path(__file__).resolve().parent / "docs" / "craft_html_doctrine.md"


def doctrine() -> str:
    """The Craft HTML doctrine, plus any lessons filed under Learn.

    The gate rejects; doctrine is how the model learns what it rejects *before*
    spending three thousand tokens finding out. Filed Craft lessons ride along
    so a rule taught once applies to every later page.
    """
    chunks = []
    try:
        if DOCTRINE_FILE.exists():
            chunks.append(DOCTRINE_FILE.read_text(encoding="utf-8")[:3000])
    except OSError:
        pass
    try:
        from learn_teach import craft_lessons_text
        extra = craft_lessons_text(1200)
        if extra:
            chunks.append("LESSONS FILED IN LEARN (Craft):\n" + extra)
    except Exception:
        pass
    return "\n\n".join(chunks)


def _facts_block(facts) -> str:
    rows = [
        f"Shop name: {facts.name}",
        f"Suburb/city: {facts.city}",
        f"Trade: {facts.trade or '(unknown — do not guess)'}",
        f"Phone: {facts.phone or '(missing — write [PHONE])'}",
        f"Hours: {facts.hours or '(missing — write [HOURS])'}",
        f"Address: {facts.address or '(missing — omit the address section)'}",
    ]
    if facts.services:
        rows.append("Services: " + ", ".join(facts.services[:6]))
    return "\n".join(rows)


def author(facts, spec=None, brief: str = "", *, live: bool = False,
           attempts: int = 2) -> tuple[Optional[str], List[str]]:
    """Ask the model for a whole page. Returns (html, notes).

    html is None when nothing survived the gate — the caller then falls back to
    the deterministic renderer, which cannot be wrong about a fact.
    """
    from llm import chat

    if not ENABLED:
        return None, ["html authoring is off (FORTITUDO_HTML_AUTHOR=0)"]
    allowed = "\n".join([_facts_block(facts), brief or "", getattr(facts, "note", "") or ""])
    notes: List[str] = []
    guidance = ""
    if spec is not None:
        guidance = (
            f"\nIntent: {spec.intent}\nHeadline to use: {spec.headline}\n"
            f"Lead line: {spec.lead}\nFirst screen: {spec.first_screen}\n"
        )
    marker = "" if live else (
        "\nThis is an internal mockup: put "
        "<!-- INTERNAL MOCKUP — adviser review required; not live. --> after the doctype, "
        "add <meta name=\"robots\" content=\"noindex,nofollow\">, and show a small banner "
        "reading 'Internal mockup · not live'.\n"
    )

    rules = doctrine()
    for attempt in range(1, attempts + 1):
        user = (
            (f"DOCTRINE (how this desk builds a shop page):\n{rules}\n\n" if rules else "")
            + f"FACTS (the only facts you may state):\n{allowed}\n{guidance}{marker}"
        )
        if notes:
            user += "\nYour previous attempt was rejected for:\n- " + "\n- ".join(notes[-6:])
        try:
            raw = chat(SYSTEM, user, temperature=0.2,
                       num_predict=HTML_NUM_PREDICT, num_ctx=HTML_NUM_CTX,
                       timeout=HTML_TIMEOUT, job="craft")
        except Exception as exc:
            return None, [f"model unavailable: {exc}"]
        html = _strip_fences(raw)
        verdict = gate(html, allowed, live=live)
        if verdict.ok:
            return html, [f"model wrote the page (attempt {attempt})"]
        notes = verdict.problems
    return None, notes


def _strip_fences(raw: str) -> str:
    text = (raw or "").strip()
    text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.lower().find("<!doctype")
    if start == -1:
        start = text.lower().find("<html")
    return text[start:].strip() if start > 0 else text
