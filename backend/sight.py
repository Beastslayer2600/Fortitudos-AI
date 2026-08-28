"""Read a screenshot the adviser drops into Chat or Learn."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from config import DATA_DIR, DOCS_DIR, OLLAMA_HOST
SHOT_DIR = DOCS_DIR / "learn" / "shots"
VISION_MODELS = ("llama3.2-vision", "llava", "llava:7b", "moondream", "minicpm-v", "qwen2.5vl")
INTENTS = {
    "learn": "Teach the desk this topic for Advisor, Studio and Craft.",
    "client": "Client message. Extract ask, facts, tone. No invented product figures.",
    "idea": "Web / Craft idea. First screen, one object, one action.",
    "chat": "Extra context. Quote what is visible. Say if unreadable.",
}
def _vision_model():
    try:
        import urllib.request
        req = urllib.request.Request(f"{OLLAMA_HOST}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=3) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        names = [m.get("name", "") for m in data.get("models", [])]
        for cand in VISION_MODELS:
            for n in names:
                if cand in n:
                    return n
    except Exception:
        return None
    return None
def describe_image(image_b64, caption, intent):
    model = _vision_model()
    job = INTENTS.get(intent, INTENTS["chat"])
    prompt = f"{job}\n\nAdviser note: {caption or '(none)'}\n\nWHAT IS ON SCREEN / FACTS / GAPS / HOW TO USE."
    if not model:
        return f"(No vision model. Caption only.)\n{caption or 'Screenshot filed.'}\nRun: ollama pull moondream"
    import urllib.request
    body = json.dumps({"model": model, "prompt": prompt, "images": [image_b64], "stream": False, "options": {"temperature": 0.1, "num_predict": 500}}).encode()
    req = urllib.request.Request(f"{OLLAMA_HOST}/api/generate", data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return (payload.get("response") or "").strip()
def ingest_sight(image_b64, filename, caption, intent="chat", client_id=""):
    intent = intent if intent in INTENTS else "chat"
    raw = image_b64.split(",", 1)[1] if "," in image_b64[:80] else image_b64
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in ".-_" else "-" for ch in (filename or "shot.png"))
    if not Path(safe).suffix:
        safe += ".png"
    dest = SHOT_DIR / f"{stamp}-{safe}"
    dest.write_bytes(__import__("base64").b64decode(raw))
    extract = describe_image(raw, caption, intent)
    md_path = DOCS_DIR / "learn" / "all" / dest.with_suffix(".md").name
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(f"# Sight — {intent} — {caption or filename}\n\nApplies to: Advisor · Studio · Craft\nImage: {dest.name}\n\n## Caption\n{caption}\n\n## Extract\n{extract}\n", encoding="utf-8")
    pages = 0
    try:
        import ingest, store
        pages = ingest.ingest_file(store.connect(), md_path, rebuild=True, source_name=f"learn:all:{md_path.name}")
    except Exception:
        pages = 0
    return {"ok": True, "intent": intent, "extract": extract, "pages": pages, "vision": _vision_model() or "", "note": str(md_path)}
