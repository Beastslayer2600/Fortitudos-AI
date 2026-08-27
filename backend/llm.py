"""Ollama client for Fortitudo AI."""
from __future__ import annotations
import re
from typing import List, Optional
import requests
from config import CHAT_MODEL, EMBED_MODEL, OLLAMA_HOST, CHAT_TEMPERATURE, CHAT_NUM_CTX, CHAT_NUM_PREDICT

class OllamaError(Exception):
    pass

def _post(path: str, payload: dict, timeout: int = 300) -> dict:
    url = f"{OLLAMA_HOST.rstrip('/')}{path}"
    try:
        r = requests.post(url, json=payload, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError as e:
        raise OllamaError(
            f"Cannot reach Ollama at {OLLAMA_HOST}.\nIs it running? Run:  ollama serve"
        ) from e
    except requests.exceptions.HTTPError as e:
        raise OllamaError(f"Ollama HTTP error: {e}") from e

def health() -> List[str]:
    try:
        r = requests.get(f"{OLLAMA_HOST.rstrip('/')}/api/tags", timeout=10)
        r.raise_for_status()
        return [m.get("name", "") for m in r.json().get("models", [])]
    except Exception as e:
        raise OllamaError(f"Cannot reach Ollama: {e}") from e

def has_model(installed: List[str], name: str) -> bool:
    base = name.split(":")[0]
    return any(m == name or m.startswith(base + ":") or m == base for m in installed)

def _clean_response(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.I)
    text = re.sub(r"</?think>", "", text, flags=re.I)
    return text.strip()

def embed(texts: List[str]) -> List[List[float]]:
    data = _post("/api/embed", {"model": EMBED_MODEL, "input": texts})
    return data.get("embeddings") or []

def chat(system: str, user: str, temperature: Optional[float] = None) -> str:
    if temperature is None:
        temperature = CHAT_TEMPERATURE
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
