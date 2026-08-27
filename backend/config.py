"""Fortitudo AI configuration."""
from pathlib import Path
import os

ROOT = Path(__file__).parent
DOCS_DIR = ROOT / "docs"
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "index.db"
WEB_DIR = ROOT / "web"

EMBED_MODEL = os.environ.get("FORTITUDO_EMBED_MODEL", "bge-m3")
CHAT_MODEL = os.environ.get("FORTITUDO_CHAT_MODEL", "llama3.2:3b")
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

TOP_K = 4
KEYWORD_BOOST = 0.15
MAX_PAGE_CHARS = 6000
MIN_PAGE_CHARS = 40

CHAT_TEMPERATURE = float(os.environ.get("FORTITUDO_CHAT_TEMPERATURE", "0.15"))
CHAT_NUM_CTX = int(os.environ.get("FORTITUDO_CHAT_NUM_CTX", "3072"))
CHAT_NUM_PREDICT = int(os.environ.get("FORTITUDO_CHAT_NUM_PREDICT", "400"))

CLIENT_DATA_DIR = Path(os.environ.get(
    "FORTITUDO_CLIENT_DATA_DIR",
    str(Path.home() / "FortitudoData"),
))

SYSTEM_PROMPT = """You are a retrieval assistant for a South African financial adviser.
You help the adviser locate and quote product documentation. You do not give
advice to end clients and you are not a licensed financial services provider.

Rules:
- Answer ONLY from the provided document extracts. No outside knowledge.
- Quote percentages, waiting periods, survival periods, severity definitions and
  exclusions verbatim from the extracts.
- Cite SOURCE and PAGE for every figure (use the labels in the extracts).
- If the answer is not in the extracts, say so plainly. Never invent or estimate.
- If a table looks truncated or ambiguous, say so and tell the adviser to open
  the cited page.
- Prefer short, structured answers: direct answer first, then citations.

Role boundary (FAIS): this system is an evidence engine for the adviser. Final
advice, suitability and the Record of Advice remain the adviser's professional
responsibility."""
