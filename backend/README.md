# Fortitudo AI backend

Local RAG + client tools. Started by `Start Fortitudo Desk.bat`.

```bat
python ingest.py
python ask.py "question"
python app.py
```

Requires Ollama with embedding model `bge-m3` (or set FORTITUDO_EMBED_MODEL).

## Running the model on another machine

Ollama on a CPU laptop writes 2–5 tokens/sec. On a desktop with a CUDA card it
is an order of magnitude faster, which is the difference between a Craft page
taking twenty minutes and taking one. The desk can use that machine.

On the fast machine:

```bat
set OLLAMA_HOST=0.0.0.0:11434
ollama serve
ollama pull qwen2.5-coder:7b
```

Ollama listens on localhost only by default, so it needs both that variable and
a firewall rule allowing port 11434 on your local network.

On the desk machine:

```bat
set FORTITUDO_CRAFT_HOST=http://192.168.1.50:11434
set FORTITUDO_CRAFT_MODEL=qwen2.5-coder:7b
```

### What will not go to that machine

Craft only. A Craft brief is a shop owner's advert, and `mockup_router` refuses
one that reads like a client file.

Everything else is pinned to this machine, because the prompts contain client
data: the ROA draft path passes the client's documents verbatim, the filing
classifier passes the document it is filing, and an adviser's typed question
can name a client. Setting `FORTITUDO_OLLAMA_HOST` to the fast box does **not**
move those — `compute.py` routes them back to localhost and says so in
`/api/status`, where `pinned_local` shows which jobs were held back.

Nothing here is encrypted. Ollama over a LAN is plaintext HTTP with no auth, so
the pin keeps client data on the machine that already holds it. To override:

```bat
set FORTITUDO_ALLOW_REMOTE_CLIENT_DATA=1
```

Per job, `FORTITUDO_<JOB>_MODEL` and `FORTITUDO_<JOB>_HOST` set the model and
host. Jobs are the room ids (`fa`, `roa`, `voice`, `craft`, `drama`, `learn`)
plus `filing`, `sight` and `mockup`.

### Writing HTML with a local model

`html_author` asks the model for a whole page and refuses it if it invents a
phone number, price, time or year. On a 3B model expect refusals; the
deterministic template runs instead and `/api/craft/page` returns
`authored: false` with the reason. A coder model raises the pass rate more
than any prompt change. `FORTITUDO_HTML_AUTHOR=0` turns authoring off.

## The Fortitudo model

The desk's default chat model is `fortitudo` — not a stock Ollama model. It is
built from `backend/model/Modelfile`, which takes a base model and bakes in the
identity, the refusals, the answer shape and the desk's sampling settings.

```bat
backend\model\build.bat
```

or by hand:

```bat
ollama create fortitudo -f backend\model\Modelfile
ollama list
```

Set `FORTITUDO_BASE_MODEL` before building to change the base — use
`qwen2.5-coder:7b` on a machine with a GPU, `llama3.2:3b` when RAM is tight.

**If you have not built it**, nothing breaks: `llm.resolve_model()` checks once,
falls back to `FORTITUDO_BASE_MODEL` (default `llama3.2:3b`), and caches the
answer so it is one probe, not one per question.

The Modelfile is a *floor*, not a ceiling. The Python desk always sends a room
prompt (`expert_route.expert_system`) and that governs. The baked-in SYSTEM is
what a caller gets when it forgets to send one.

## Where the AI lives

Two paths reach a model, and both are now the same desk:

- **Python** — `backend/llm.py` → `expert_route.expert_system(room)`. Rooms,
  doctrine, retrieval, `span_check`.
- **Browser** — `src/lib/llm.ts` → `src/lib/fortitudo.ts`. Mirrors the Python
  identity, standards and refusals. `src/lib/fortitudo.test.ts` reads
  `expert_route.py` and fails if the two drift apart.

### The desk does not call the cloud

`src/lib/llm.ts` used to fall back to xAI whenever Ollama was down — silently,
on a path that handles client work. It no longer does. `auto` means this
machine; a dead Ollama is an error the caller handles offline. Reaching xAI now
requires `FORTITUDO_LLM=xai`, set deliberately. `XAI_API_KEY` alone does
nothing.
