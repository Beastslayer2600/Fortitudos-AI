"""
Fortitudo AI - Ollama client

Thin wrapper over the local Ollama HTTP API. No cloud calls anywhere in this
project: every request goes to localhost.
"""
import re
import requests
from typing import List, Union, Dict, Any, Optional, Iterator

from config import (
    OLLAMA_HOST, EMBED_MODEL, CHAT_MODEL,
    CHAT_TEMPERATURE, CHAT_NUM_CTX, CHAT_NUM_PREDICT,
)

TIMEOUT = 300


class OllamaError(RuntimeError):
    pass


def _post(path: str, payload: Dict[str, Any], timeout: int = TIMEOUT) -> Dict[str, Any]:
    url = f"{OLLAMA_HOST}{path}"
    try:
        r = requests.post(url, json=payload, timeout=timeout)
    except requests.exceptions.ConnectionError:
        raise OllamaError(
            f"Cannot reach Ollama at {OLLAMA_HOST}.\n"
            "Is it running? Open PowerShell and run:  ollama serve"
        )
    except requests.exceptions.Timeout:
        raise OllamaError(
            f"Ollama timed out after {timeout}s on {path}.\n"
            "The model may be too large for free RAM, or the machine is under load.\n"
            f"Try a smaller model (set FORTITUDO_CHAT_MODEL=llama3.2:3b) or close other apps."
        )
    if r.status_code == 404:
        raise OllamaError(
            f"Ollama returned 404 for {path}. The model may not be pulled.\n"
            f"Try:  ollama pull {payload.get('model', '<model>')}"
        )
    if r.status_code >= 400:
        detail = ""
        try:
            detail = r.json().get("error", r.text[:200])
        except Exception:
            detail = r.text[:200]
        raise OllamaError(f"Ollama error {r.status_code}: {detail}")
    r.raise_for_status()
    return r.json()


def health() -> List[str]:
    """Return list of installed model names, or raise with a clear message."""
    try:
        r = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise OllamaError(
            f"Cannot reach Ollama at {OLLAMA_HOST}.\n"
            "Start it with:  ollama serve"
        )
    return [m["name"] for m in r.json().get("models", [])]


def has_model(installed: List[str], needed: str) -> bool:
    """Return True when Ollama has the requested model or its :latest tag."""
    names = {m.lower() for m in installed}
    needed = needed.lower()
    if needed in names:
        return True
    if ":" not in needed and f"{needed}:latest" in names:
        return True
    # Also match base name against tagged variants (e.g. llama3.2:3b-instruct-q4_K_M)
    base = needed.split(":")[0]
    return any(n == needed or n.startswith(base + ":") for n in names)


def embed(texts: Union[str, List[str]]) -> List[List[float]]:
    """Embed a list of strings. Returns list of vectors."""
    if isinstance(texts, str):
        texts = [texts]

    # Newer Ollama exposes /api/embed with batch support.
    try:
        data = _post("/api/embed", {"model": EMBED_MODEL, "input": texts})
        if "embeddings" in data:
            return data["embeddings"]
    except OllamaError:
        raise
    except Exception:
        pass

    # Fallback for older builds: /api/embeddings, one at a time.
    out = []
    for t in texts:
        data = _post("/api/embeddings", {"model": EMBED_MODEL, "prompt": t})
        out.append(data["embedding"])
    return out


_THINK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)


def _clean_response(text: str) -> str:
    """Strip leaked chain-of-thought blocks some models still emit."""
    cleaned = _THINK_RE.sub("", text or "").strip()
    # Drop a leading /no_think echo if the model repeats the control token
    if cleaned.lower().startswith("/no_think"):
        cleaned = cleaned[9:].lstrip()
    return cleaned


def chat(system: str, user: str, temperature: Optional[float] = None) -> str:
    """Single-turn chat completion. Low temperature - we want it literal."""
    if temperature is None:
        temperature = CHAT_TEMPERATURE
    # think=False: Qwen3-class models otherwise burn tokens on hidden reasoning
    # on CPU (and can exhaust num_predict before the answer). /no_think is a
    # second belt for models that ignore the API flag.
    payload = {
        "model": CHAT_MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": "/no_think\n" + user},
        ],
        "stream": False,
        "think": False,
        "keep_alive": "30m",
        "options": {
            "temperature": temperature,
            "num_ctx": CHAT_NUM_CTX,
            "num_predict": CHAT_NUM_PREDICT,
        },
    }
    data = _post("/api/chat", payload)
    return _clean_response(data.get("message", {}).get("content", ""))
