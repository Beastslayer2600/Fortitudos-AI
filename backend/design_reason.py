"""Design reasoning for Craft pages.

The model thinks like a local conversion designer.
It emits a spec. The renderer paints HTML. Nothing invented.
Lessons filed in Learn → Craft are prepended to the doctrine.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List

from trade_page import TradeFacts, _headline, facts_from_text, render_trade_html

DOCTRINE = Path(__file__).resolve().parent / "docs" / "craft_design_doctrine.md"

SYSTEM = """You are Fortitudo Craft's design and marketing lead for one-page local shop sites in Gauteng.
Output ONLY one JSON object. No markdown. No HTML. No hex codes. No fonts.

Use the DOCTRINE and any LESSONS FILED IN LEARN as law.
Think in this order, then fill the JSON:
1. Intent — emergency (call now) or appointment (hours + place).
2. Audience — one person, one suburb, one job.
3. First screen — suburb, job, Call.
4. Headline — job + suburb. Never a slogan.
5. Proof — only what the brief actually contains.
6. Omit — anything not supplied.
7. Flyer line — same job as the headline.

CTA: Call first, WhatsApp second.
Mood: industrial | warm | cool | lush.
South African English. Grade 6.
Never invent phone, hours, awards, 24/7, testimonials, or prices.
"""


@dataclass
class DesignSpec:
    headline: str
    lead: str
    audience: str
    job: str = ""
    intent: str = "emergency"
    first_screen: str = ""
    why: str = ""
    seo_title: str = ""
    cta_primary: str = "Call"
    mood: str = "industrial"
    omit: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    flyer_line: str = ""
    missing: List[str] = field(default_factory=list)
    raw: str = ""


def _doctrine() -> str:
    chunks = []
    if DOCTRINE.exists():
        chunks.append(DOCTRINE.read_text(encoding="utf-8")[:2200])
    try:
        from learn_teach import craft_lessons_text
        extra = craft_lessons_text(2000)
        if extra:
            chunks.append("LESSONS FILED IN LEARN (Craft):\n" + extra)
    except Exception:
        pass
    return "\n\n".join(chunks)


def _extract_json(text: str) -> dict:
    start, end = text.find("{"), text.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("no json")
    return json.loads(text[start:end])


def fallback_spec(facts: TradeFacts) -> DesignSpec:
    emergency = (facts.trade or "").lower() in {
        "plumb", "electr", "geyser", "mechanic", "workshop", "auto", "locksmith",
    }
    h = _headline(facts)
    return DesignSpec(
        headline=h,
        lead="Call or WhatsApp. The number is on this page.",
        audience=f"Someone in {facts.city} who needs a {facts.trade or 'local trade'} now",
        job=facts.trade or "local trade",
        intent="emergency" if emergency else "appointment",
        first_screen="Suburb + job + Call in the first thumb-scroll",
        why="Emergency trades sell the tap. Appointment trades sell place and hours.",
        seo_title=f"{facts.name} · {facts.trade or 'shop'} · {facts.city}",
        mood="industrial" if emergency else "warm",
        omit=facts.missing(),
        services=facts.services[:4] or ([facts.trade] if facts.trade else []),
        flyer_line=f"{h}. Scan to open the page.",
        missing=facts.missing(),
        raw="(fallback — model skipped)",
    )


def reason(facts: TradeFacts) -> DesignSpec:
    user = (
        _doctrine()
        + "\n\nFACTS (do not add to these):\n"
        + f"Shop: {facts.name}\nCity: {facts.city}\nTrade: {facts.trade or '(unknown)'}\n"
        + f"Phone: {facts.phone or '(none)'}\nHours: {facts.hours or '(none)'}\n"
        + f"Address: {facts.address or '(none)'}\nNote: {facts.note or '(none)'}\n"
        + "JSON keys: headline, lead, audience, job, intent, first_screen, why, seo_title, "
        + "cta_primary, mood, omit, services, flyer_line, missing"
    )
    try:
        from llm import chat
        raw = chat(SYSTEM, user, temperature=0.2)
        data = _extract_json(raw)
    except Exception:
        return fallback_spec(facts)
    spec = DesignSpec(
        headline=str(data.get("headline") or _headline(facts))[:120],
        lead=str(data.get("lead") or "Call or WhatsApp.")[:220],
        audience=str(data.get("audience") or "")[:160],
        job=str(data.get("job") or facts.trade or "")[:80],
        intent=str(data.get("intent") or "emergency").lower(),
        first_screen=str(data.get("first_screen") or "")[:180],
        why=str(data.get("why") or "")[:240],
        seo_title=str(data.get("seo_title") or f"{facts.name} · {facts.city}")[:70],
        cta_primary=str(data.get("cta_primary") or "Call")[:24],
        mood=str(data.get("mood") or "industrial").lower(),
        omit=[str(x) for x in (data.get("omit") or [])][:8],
        services=[str(x) for x in (data.get("services") or facts.services)][:4],
        flyer_line=str(data.get("flyer_line") or f"A page for {facts.name}.")[:140],
        missing=[str(x) for x in (data.get("missing") or facts.missing())][:8],
        raw=raw[:2500],
    )
    if spec.mood not in {"industrial", "warm", "cool", "lush"}:
        spec.mood = "industrial"
    if spec.intent not in {"emergency", "appointment"}:
        spec.intent = "emergency"
    if spec.cta_primary.lower() not in {"call", "whatsapp"}:
        spec.cta_primary = "Call"
    if not facts.hours:
        if "HOURS" not in spec.omit:
            spec.omit.append("HOURS")
        spec.missing = list(dict.fromkeys([*spec.missing, "HOURS"]))
    if not facts.phone:
        spec.missing = list(dict.fromkeys([*spec.missing, "PHONE"]))
    return spec


def apply_spec(facts: TradeFacts, spec: DesignSpec) -> TradeFacts:
    return TradeFacts(
        name=facts.name, city=facts.city, trade=facts.trade, phone=facts.phone,
        hours="" if "HOURS" in spec.omit else facts.hours, address=facts.address,
        services=spec.services or facts.services, note=facts.note, photos=facts.photos,
    )


def flyer_html(facts: TradeFacts, spec: DesignSpec, mock_url: str) -> str:
    from html import escape
    q = "https://api.qrserver.com/v1/create-qr-code/?size=240x240&data=" + __import__("urllib.parse").quote(mock_url, safe="")
    public = mock_url.startswith("http") and "127.0.0.1" not in mock_url and "localhost" not in mock_url
    warn = "" if public else "<p class='warn'>This QR is not public. Host the mock before you print.</p>"
    return f"""<!DOCTYPE html><html lang="en-ZA"><head><meta charset="utf-8"><title>Flyer — {escape(facts.name)}</title>
<style>@page{{size:A6;margin:10mm}}body{{font:14px/1.4 system-ui,sans-serif}}h1{{font-size:1.4rem}}.qr{{width:160px;height:160px}}.warn{{color:#8a1f1f}}</style></head>
<body><p style="letter-spacing:.14em;text-transform:uppercase;font-size:.7rem">{escape(facts.city)} · {escape(spec.intent)}</p>
<h1>{escape(facts.name)}</h1><p>{escape(spec.flyer_line)}</p>
<img class="qr" alt="QR" src="{escape(q)}">
<p>Scan for the page we drafted. Call Gert · Fortitudo Studios · +27 77 386 6299</p>{warn}</body></html>"""


def design_and_render(name: str, source_text: str, city: str = "Kempton Park", mock_url: str = "") -> dict:
    facts = facts_from_text(name, source_text, city=city)
    spec = reason(facts)
    painted = apply_spec(facts, spec)
    page = render_trade_html(painted, include_sku=False)
    page = page.replace(f"<h1>{_esc_safe(_headline(facts))}</h1>", f"<h1>{_esc_safe(spec.headline)}</h1>", 1)
    flyer = flyer_html(facts, spec, mock_url or "https://fortitudostudios.site/m/preview")
    return {"spec": asdict(spec), "page": page, "flyer": flyer, "missing": spec.missing}


def _esc_safe(s: str) -> str:
    return str(s or "").replace("&", "&").replace("<", "<").replace(">", ">").replace('"', """)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
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
