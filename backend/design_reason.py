"""Design reasoning for Craft pages.

The model decides audience, headline job, mood, and what to omit.
It does not emit HTML or invent phone / hours / reviews.
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import List, Optional

from trade_page import TradeFacts, _headline, facts_from_text, generate_trade_page, render_trade_html

SYSTEM = """You are the design lead for Fortitudo Craft one-page local shop sites in Gauteng.
Output ONLY one JSON object. No markdown fences. No commentary.

Decide:
- who the first screen is for (one person, one urgent job)
- one headline that names the suburb and the job
- a one-line lead
- mood: industrial | warm | cool | lush
- which facts to OMIT because they were not supplied (hours, reviews, prices)
- up to 4 service lines from the brief only
- one flyer line for a printed pamphlet

Never invent a phone number, opening hours, awards, testimonials, or prices.
If hours are missing, omit them. If phone is missing, say so in missing.
South African English. Short sentences.
"""


@dataclass
class DesignSpec:
    headline: str
    lead: str
    audience: str
    mood: str = "industrial"
    omit: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    flyer_line: str = ""
    missing: List[str] = field(default_factory=list)
    raw: str = ""


def _extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("no json")
    return json.loads(text[start:end])


def fallback_spec(facts: TradeFacts) -> DesignSpec:
    return DesignSpec(
        headline=_headline(facts),
        lead="Call or WhatsApp. The number is on this page.",
        audience=f"Someone in {facts.city} who needs a {facts.trade or 'local trade'} now",
        mood="industrial" if (facts.trade or "").lower() in {"plumb", "electr", "mechanic", "workshop", "auto"} else "warm",
        omit=facts.missing(),
        services=facts.services[:4] or ([facts.trade] if facts.trade else []),
        flyer_line=f"A page for {facts.name}. Scan to open it.",
        missing=facts.missing(),
        raw="(fallback — model skipped)",
    )


def reason(facts: TradeFacts) -> DesignSpec:
    user = (
        f"Shop: {facts.name}\nCity: {facts.city}\nTrade: {facts.trade or '(unknown)'}\n"
        f"Phone: {facts.phone or '(none)'}\nHours: {facts.hours or '(none)'}\n"
        f"Address: {facts.address or '(none)'}\nNote: {facts.note or '(none)'}\n"
        "JSON keys: headline, lead, audience, mood, omit, services, flyer_line, missing"
    )
    try:
        from llm import chat
        raw = chat(SYSTEM, user, temperature=0.2)
        data = _extract_json(raw)
    except Exception:
        spec = fallback_spec(facts)
        return spec
    spec = DesignSpec(
        headline=str(data.get("headline") or _headline(facts))[:120],
        lead=str(data.get("lead") or "Call or WhatsApp.")[:220],
        audience=str(data.get("audience") or "")[:160],
        mood=str(data.get("mood") or "industrial").lower(),
        omit=[str(x) for x in (data.get("omit") or [])][:8],
        services=[str(x) for x in (data.get("services") or facts.services)][:4],
        flyer_line=str(data.get("flyer_line") or f"A page for {facts.name}.")[:140],
        missing=[str(x) for x in (data.get("missing") or facts.missing())][:8],
        raw=raw[:2000],
    )
    if spec.mood not in {"industrial", "warm", "cool", "lush"}:
        spec.mood = "industrial"
    # Never let the model smuggle hours that were not on the facts.
    if not facts.hours:
        if "HOURS" not in spec.omit:
            spec.omit.append("HOURS")
        spec.missing = list(dict.fromkeys([*spec.missing, "HOURS"]))
    if not facts.phone:
        spec.missing = list(dict.fromkeys([*spec.missing, "PHONE"]))
    return spec


def apply_spec(facts: TradeFacts, spec: DesignSpec) -> TradeFacts:
    services = spec.services or facts.services
    return TradeFacts(
        name=facts.name,
        city=facts.city,
        trade=facts.trade,
        phone=facts.phone,
        hours="" if "HOURS" in spec.omit else facts.hours,
        address=facts.address,
        services=services,
        note=facts.note,
        photos=facts.photos,
    )


def flyer_html(facts: TradeFacts, spec: DesignSpec, mock_url: str) -> str:
    """A6 pamphlet. QR points at the hosted mock — not localhost."""
    from html import escape
    q = (
        "https://api.qrserver.com/v1/create-qr-code/?size=240x240&data="
        + __import__("urllib.parse").quote(mock_url, safe="")
    )
    warn = "" if mock_url.startswith("http") and "127.0.0.1" not in mock_url and "localhost" not in mock_url else (
        "<p class='warn'>This QR is not public. Host the mock before you print.</p>"
    )
    return f"""<!DOCTYPE html>
<html lang="en-ZA"><head><meta charset="utf-8">
<title>Flyer — {escape(facts.name)}</title>
<style>
@page {{ size: A6; margin: 10mm; }}
body {{ font: 14px/1.4 system-ui,sans-serif; color:#111; }}
h1 {{ font-size: 1.4rem; margin: 0 0 .4rem; }}
.qr {{ width: 160px; height: 160px; }}
.warn {{ color:#8a1f1f; font-size:.85rem; }}
</style></head>
<body>
<p style="letter-spacing:.14em;text-transform:uppercase;font-size:.7rem">{escape(facts.city)}</p>
<h1>{escape(facts.name)}</h1>
<p>{escape(spec.flyer_line)}</p>
<img class="qr" alt="QR" src="{escape(q)}">
<p>Scan for the page we drafted. Call Gert · Fortitudo Studios · +27 77 386 6299</p>
{warn}
</body></html>
"""


def design_and_render(name: str, source_text: str, city: str = "Kempton Park", mock_url: str = "") -> dict:
    facts = facts_from_text(name, source_text, city=city)
    spec = reason(facts)
    painted = apply_spec(facts, spec)
    page = render_trade_html(painted, include_sku=False)
    # Overlay the reasoned headline by simple replace of the fallback H1 if present.
    page = page.replace(
        f"<h1>{_esc_safe(_headline(facts))}</h1>",
        f"<h1>{_esc_safe(spec.headline)}</h1>",
        1,
    )
    flyer = flyer_html(facts, spec, mock_url or "https://fortitudostudios.site/m/preview")
    return {"spec": asdict(spec), "page": page, "flyer": flyer, "missing": spec.missing}


def _esc_safe(s: str) -> str:
    return (
        str(s or "")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


if __name__ == "__main__":
    import argparse
    from pathlib import Path
    ap = argparse.ArgumentParser(description="Reason a Craft page + flyer")
    ap.add_argument("--name", required=True)
    ap.add_argument("--city", default="Kempton Park")
    ap.add_argument("--facts", default="")
    ap.add_argument("--url", default="")
    ap.add_argument("-o", default="craft_out")
    args = ap.parse_args()
    out = design_and_render(args.name, args.facts, args.city, args.url)
    root = Path(args.o)
    root.mkdir(parents=True, exist_ok=True)
    (root / "page.html").write_text(out["page"], encoding="utf-8")
    (root / "flyer.html").write_text(out["flyer"], encoding="utf-8")
    (root / "spec.json").write_text(json.dumps(out["spec"], indent=2), encoding="utf-8")
    print("wrote", root, "missing", out["missing"])
