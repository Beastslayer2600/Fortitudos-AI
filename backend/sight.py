"""Read a screenshot the adviser drops into Chat or Learn."""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from config import DOCS_DIR, OLLAMA_HOST
SHOT_DIR = DOCS_DIR / "learn" / "shots"
VISION_MODELS = ("moondream", "llama3.2-vision", "llava", "minicpm-v", "qwen2.5vl")
INTENTS = {
    "learn": "Teach the desk this topic. Quote visible text only.",
    "client": "Client message. Extract ask, facts, tone. No invented product figures.",
    "idea": "Craft shop photo. Read the sign only: name, phone, hours, trades. Do not guess hours or reviews.",
    "craft": "Craft shop photo. Read the sign only: name, phone, hours, trades. Do not guess hours or reviews.",
    "chat": "Extra context. Quote what is visible. Say if unreadable.",
}

def _vision_model(host=""):
    try:
        import urllib.request
        req = urllib.request.Request(f"{host or OLLAMA_HOST}/api/tags", method="GET")
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
    # A shop-sign photo is Craft work and may go to the fast box. Every other
    # intent can be a client's screen, so it is routed as client data and
    # compute.resolve pins it to this machine.
    import compute
    plan = compute.resolve("craft" if intent in ("craft", "idea") else "sight", OLLAMA_HOST)
    model = _vision_model(plan.host)
    instruction = INTENTS.get(intent, INTENTS["chat"])
    prompt = f"{instruction}\n\nAdviser note: {caption or '(none)'}\n\nWHAT IS ON SCREEN / FACTS / GAPS. Never invent a phone number or opening hours."
    if not model:
        return f"(No vision model. Caption only.)\n{caption or 'Screenshot filed.'}\nRun: ollama pull moondream"
    import urllib.request
    body = json.dumps({"model": model, "prompt": prompt, "images": [image_b64], "stream": False, "options": {"temperature": 0.1, "num_predict": 400}}).encode()
    req = urllib.request.Request(f"{plan.host}/api/generate", data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=180) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    return (payload.get("response") or "").strip()

def ingest_sight(image_b64, filename, caption, intent="chat", client_id=""):
    """File a photo and the model's reading of it.

    A client photo belongs to that client, not to the shared shelf. It is filed
    in the client's AI-drafts folder: the extract is model-written, so it is
    kept alongside the client but never becomes citable evidence. The desk was
    already sending client_id; this is where it lands.
    """
    intent = intent if intent in INTENTS else "chat"
    raw = image_b64.split(",", 1)[1] if "," in image_b64[:80] else image_b64
    blob = __import__("base64").b64decode(raw)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe = "".join(ch if ch.isalnum() or ch in ".-_" else "-" for ch in (filename or "shot.png"))
    if not Path(safe).suffix:
        safe += ".png"
    name = f"{stamp}-{safe}"
    extract = describe_image(raw, caption, intent)
    applies = "Craft" if intent in ("idea", "craft") else ("Advisor" if intent == "client" else "Learn")
    body = (
        f"# Sight — {intent} — {caption or filename}\n\n"
        f"Applies to: {applies}\nImage: {name}\n\n"
        f"## Caption\n{caption}\n\n## Extract\n{extract}\n"
    )

    if intent == "client" and client_id:
        import client_store
        client_store.add_document(
            client_id, name, blob, client_store.AI_DRAFT_TYPE,
            "image/png", folder=client_store.AI_DRAFT_FOLDER,
        )
        note = client_store.add_generated_file(
            client_id, Path(name).with_suffix(".md").name, body,
        )
        return {"ok": True, "intent": intent, "extract": extract, "pages": 0,
                "vision": _vision_model() or "", "note": note}

    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    dest = SHOT_DIR / name
    dest.write_bytes(blob)
    md_path = DOCS_DIR / "learn" / "sight" / dest.with_suffix(".md").name
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(body, encoding="utf-8")
    pages = 0
    if intent not in ("idea", "craft"):
        try:
            import ingest, store
            pages = ingest.ingest_file(store.connect(), md_path, rebuild=False,
                                       source_name=f"learn:sight:{md_path.name}")
        except Exception:
            pages = 0
    return {"ok": True, "intent": intent, "extract": extract, "pages": pages,
            "vision": _vision_model() or "", "note": str(md_path)}
