"""Deterministic one-page for a trade shop. No wealth defaults. No invented hours."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

PRICE = 5500
DEPOSIT = 2750

TRADE_HINT = re.compile(
    r"\b(plumb|electr|geyser|builder|carpenter|welder|panel.?beat|mechanic|"
    r"auto|workshop|tiler|roofer|painter|locksmith|aircon|hvac|gardener|"
    r"landscap|bakery|butcher|salon|hair|cafe|gym)\b",
    re.I,
)


@dataclass
class TradeFacts:
    name: str
    city: str = "Kempton Park"
    trade: str = ""
    phone: str = ""
    hours: str = ""
    address: str = ""
    services: List[str] = field(default_factory=list)
    note: str = ""

    def missing(self) -> List[str]:
        gaps = []
        if not self.phone:
            gaps.append("PHONE")
        if not self.hours:
            gaps.append("HOURS")
        if not self.trade:
            gaps.append("TRADE")
        return gaps


def is_trade_brief(text: str) -> bool:
    return bool(TRADE_HINT.search(text or ""))


def facts_from_text(name: str, blob: str, city: str = "Kempton Park") -> TradeFacts:
    phone = ""
    m = re.search(r"(0\d{2}[\s-]?\d{3}[\s-]?\d{4}|\+27[\s-]?\d{2}[\s-]?\d{3}[\s-]?\d{4})", blob or "")
    if m:
        phone = re.sub(r"\s+", " ", m.group(1)).strip()
    hours = ""
    hm = re.search(r"\b(\d{1,2}[:.]\d{2}\s*[-to]+\s*\d{1,2}[:.]\d{2}|\bMon\b.+\bSat\b)", blob or "", re.I)
    if hm:
        hours = hm.group(0)
    trade = ""
    tm = TRADE_HINT.search(blob or "")
    if tm:
        trade = tm.group(1)
    return TradeFacts(name=name.strip() or "Shop", city=city, trade=trade, phone=phone, hours=hours, note=(blob or "")[:400])


def _esc(s: object) -> str:
    return str(s or "").replace("&", "&").replace("<", "<").replace(">", ">").replace('"', """)


def render_trade_html(facts: TradeFacts, *, include_sku: bool = False) -> str:
    phone = facts.phone or "[PHONE]"
    hours = facts.hours or "[HOURS]"
    trade = facts.trade or "local trade"
    tel = re.sub(r"\D", "", facts.phone)
    wa = f"27{tel[1:]}" if tel.startswith("0") and len(tel) == 10 else tel
    gaps = facts.missing()
    gap_banner = (
        f"Missing on the door: {', '.join(gaps)}. Do not invent them."
        if gaps else "Facts only — review before print."
    )
    sku = (
        f"<p class='sku'>A page like this from Fortitudo Studios: R{PRICE:,} once, R{DEPOSIT:,} to start.</p>"
        if include_sku else ""
    )
    services = "".join(f"<li>{_esc(s)}</li>" for s in (facts.services or [trade])[:6])
    addr = f"<li>Address: {_esc(facts.address)}</li>" if facts.address else ""
    return (
        "<!DOCTYPE html>\n"
        "<!-- INTERNAL MOCKUP — trade page — review before print. Not live. -->\n"
        "<html lang=\"en-ZA\"><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<meta name=\"robots\" content=\"noindex,nofollow\">"
        f"<title>{_esc(facts.name)} · {_esc(facts.city)}</title>"
        "<style>body{margin:0;font-family:system-ui,sans-serif;background:#121212;color:#ece8e0}"
        "a{color:inherit}.banner{background:#2a2418;color:#e8c48a;text-align:center;font-size:.78rem;padding:.5rem}"
        "header{padding:1.25rem}.city{letter-spacing:.18em;text-transform:uppercase;font-size:.7rem;opacity:.65}"
        "h1{margin:.35rem 0;font-size:2rem}.bar{display:flex;gap:.6rem;flex-wrap:wrap;padding:0 1.25rem 1.25rem}"
        ".btn{display:inline-block;padding:.7rem 1.1rem;border-radius:999px;background:#d0ccc4;color:#121212;font-weight:650;text-decoration:none}"
        ".btn.ghost{background:transparent;color:#ece8e0;border:1px solid #3a3a3a}section{padding:1rem 1.25rem}"
        "footer{padding:1.25rem;opacity:.7;font-size:.8rem;border-top:1px solid #2a2a2a}</style></head><body>"
        f"<div class=\"banner\">{_esc(gap_banner)}</div>"
        f"<header><p class=\"city\">{_esc(facts.city)}</p><h1>{_esc(facts.name)}</h1>"
        f"<p>{_esc(trade)} · Call or WhatsApp. Nothing invented.</p></header>"
        f"<div class=\"bar\"><a class=\"btn\" href=\"tel:{_esc(phone)}\">Call {_esc(phone)}</a>"
        f"<a class=\"btn ghost\" href=\"https://wa.me/{_esc(wa)}\">WhatsApp</a></div>"
        f"<section><h2>On the door</h2><ul><li>Hours: {_esc(hours)}</li><li>Phone: {_esc(phone)}</li>{addr}</ul>"
        f"<h2>Work</h2><ul>{services}</ul></section>"
        f"<footer><p>Internal mockup. Print and walk it to the door. Do not email this as a pitch unless consent is on file.</p>{sku}</footer>"
        "</body></html>"
    )


def generate_trade_page(name: str, source_text: str, city: str = "Kempton Park") -> str:
    return render_trade_html(facts_from_text(name, source_text, city=city), include_sku=False)
