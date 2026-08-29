"""
Fortitudo AI - configuration
Everything tunable lives here. Change values, re-run ingest.py if you touch
CHUNK settings or EMBED_MODEL.

Environment overrides (optional):
  FORTITUDO_CHAT_MODEL, FORTITUDO_EMBED_MODEL, FORTITUDO_OLLAMA_HOST
  FORTITUDO_CLIENT_DATA_DIR, FORTITUDO_DROP_ZONE, FORTITUDO_REVIEW_ZONE
"""
import os
from pathlib import Path

# ---------------------------------------------------------------- paths
ROOT = Path(__file__).parent
DOCS_DIR = ROOT / "docs"          # drop your PDFs here
DATA_DIR = ROOT / "data"          # sqlite index lives here
DB_PATH = DATA_DIR / "index.db"
WEB_DIR = ROOT / "web"

# Client vault, drop zone and drama records live outside the repo. The desk is
# a Windows product, but "C:\FortitudoData" is a relative name everywhere else,
# so running the backend on Linux or macOS would create that literal folder in
# the working directory. FORTITUDO_DATA_ROOT overrides both.
DATA_ROOT = Path(
    os.environ.get("FORTITUDO_DATA_ROOT")
    or (r"C:\FortitudoData" if os.name == "nt" else Path.home() / "FortitudoData")
)

# ---------------------------------------------------------------- ollama
OLLAMA_HOST = os.environ.get("FORTITUDO_OLLAMA_HOST") or os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")

# Embedding model. bge-m3 = 1024 dims, handles long passages well.
# Alternative: "nomic-embed-text" (768 dims, faster, slightly weaker).
EMBED_MODEL = os.environ.get("FORTITUDO_EMBED_MODEL", "bge-m3")

# Chat model.
#
# THIS MACHINE (measured 18 Aug 2026):
#   Intel Core i7-1355U, 10 cores / 12 threads, 1.7 GHz base
#   15.6 GB RAM  -  but only ~1 GB free under normal load
#   Intel UHD Graphics, 2 GB shared - no CUDA, Ollama runs on CPU
#
# Free RAM is the binding constraint, not total RAM. A model has to fit in
# memory that is actually free, or Windows pages it to disk and generation
# slows to a crawl. Close Chrome/Teams/Outlook before running the model.
#
#   Model          Approx RAM    Verdict on this machine
#   llama3.2:3b    ~2.5 GB       Usable. Default.
#   qwen3:4b       ~3.5 GB       Works if you free memory first.
#   qwen3:8b       ~6 GB         Too slow to be practical.
#   anything 14b+  8 GB+         Do not.
#
# Expect roughly 2-5 tokens/sec on CPU. A short answer takes 30-60 seconds.
# That is fine for desk work and too slow to use live in a client meeting -
# use `ask.py --show` for that, which needs no model at all.
CHAT_MODEL = os.environ.get("FORTITUDO_CHAT_MODEL", "llama3.2:3b")

# Generation knobs (CPU-friendly defaults)
CHAT_TEMPERATURE = float(os.environ.get("FORTITUDO_CHAT_TEMPERATURE", "0.1"))
CHAT_NUM_CTX = int(os.environ.get("FORTITUDO_CHAT_NUM_CTX", "3072"))
CHAT_NUM_PREDICT = int(os.environ.get("FORTITUDO_CHAT_NUM_PREDICT", "400"))

# ---------------------------------------------------------------- retrieval
# We index at PAGE level, not paragraph level. This is deliberate:
# benefit matrices in the Lifestyle Protector guide span a whole page and
# get destroyed by small chunks. A page keeps the table intact.
TOP_K = 4                 # pages fed to the model after hybrid fusion
# Candidate pool size is controlled in retrieval.py (CANDIDATE_POOL)
KEYWORD_BOOST = 0.15      # bonus applied when query terms appear literally
MIN_PAGE_CHARS = 60       # skip near-empty pages (covers, dividers)

# Long pages get truncated before going to the model. On CPU this is the
# single biggest lever on response time - every character costs.
MAX_PAGE_CHARS = 3500

# ---------------------------------------------------------------- prompting
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
