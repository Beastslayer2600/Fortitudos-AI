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

## Scoring the desk

```bat
python eval_desk.py            :: offline suites, no Ollama needed
python eval_desk.py -v         :: show every case
python eval_desk.py --live     :: also ask the real model
python eval_desk.py --top-k 1  :: precision@1, the harder number
```

Seven suites: routing, retrieval, grounding, craft separation, the HTML gate,
version conflict, reasoning depth. Exit code is non-zero on any regression, and
it runs in CI on every commit.

The fixture corpus in `backend/eval/corpus` is deliberately adversarial — it
contains two versions of the same product guide whose figures differ. Without
rival versions the retrieval score sits at 100% and measures nothing.

Embeddings in the harness are a deterministic hash, not bge-m3, so the score
depends on the desk rather than on which models happen to be installed.

Add a case in `backend/eval/cases.py`. One line, and a regression names itself.

## PDF workbench

Open a filed client PDF from the client's Documents tab: the document on the
left, what may be done to it on the right.

```
GET  /api/pdf/<doc_id>            pages, text, form fields, what this file supports
POST /api/pdf/<doc_id>/fill       fill AcroForm fields
POST /api/pdf/<doc_id>/annotate   add comments
POST /api/pdf/<doc_id>/redact     genuinely remove text
POST /api/pdf/<doc_id>/assemble   select / rotate pages
POST /api/pdf/<doc_id>/stamp      overlay a banner or reference
POST /api/pdf/<doc_id>/extract    write an editable markdown draft
```

### The original is never edited

A filed client document is the signed record. Changing it in place is not
editing, it is altering evidence — and append-only versioning *is* the
compliance trail, not a restriction on it.

So every operation writes a **new** file into `99_AI_Drafts`, typed as an AI
draft, and the document it read stays byte-identical. This is structural, not a
setting: `pdf_tools` takes bytes and returns bytes and never touches the
filesystem, so there is no code path that can overwrite an original. Tests
assert both halves, and each was verified by deliberately breaking it.

### What is deliberately not offered

Rewriting body prose inside a PDF. PDF is a page-description format, not a
document with editable text, and a scan has no text at all. Anything claiming
to do it is reflowing a guess, which on a client file is silent corruption.
`extract` is the honest version: the text comes out into markdown you can edit,
the PDF stays the original, and both sit in the client folder.

### Redaction removes, it does not cover

A black rectangle drawn over an ID number leaves the number in the file and any
reader will copy it out. `redact` rewrites the content stream so the glyphs are
gone — the eval asserts the text is absent from the raw bytes, not just from
what extraction returns.

### Scans

A scan's content is pixels, so the two redactions are genuinely different jobs:

| | how |
|---|---|
| Text PDF | rewrite the content stream — `redact()` |
| Scan | blank the pixels, rebuild the page — `redact_regions()` |

The `redact` action picks the right one. This matters more than it looks: OCR a
scan, find the ID number, and run a text redaction on the literal, and it
removes nothing at all while reporting success — there is no such string in the
file. Worse, OCR misreading a single digit makes a literal-based redaction miss
silently.

**So OCR never decides what gets removed.** It reads the page and *suggests*
regions. The removal is pixel-level, which holds whether or not the OCR was
right, and the result is re-read afterwards to prove the text is gone — a
redaction that cannot be confirmed is refused rather than returned.

A suggestion is narrowed to the match rather than the whole OCR line. Blanking
the line would take the client's name out with the ID number. There is no
per-character geometry, so the span is estimated from character offsets and
padded wider than the error: clipping a digit is worse than eating a
neighbouring letter.

Pixel redaction refuses a page that still has real text, rather than quietly
flattening the text layer into an image.

OCR output is labelled as a guess everywhere it surfaces, and never becomes
citable evidence. A figure read by OCR was read from a picture of the document,
not from the document.

**Installing OCR** — deliberately not in `requirements.txt`, because it is a
large download and the desk works without it:

```bat
pip install rapidocr-onnxruntime
```

Without it, a scan can still be annotated, stamped and reordered; the workbench
says so and gives the install line rather than failing oddly.

### The viewer

The browser's own PDF renderer in an iframe, not pdf.js. pdf.js would give
per-page coordinates for highlighting, at the cost of a worker bundle and a
pinned version on a machine that already fights its Python wheels. The model
does not read pixels — it reads the per-page text the backend extracts. When
highlighting a span on the page becomes the thing you want, that is the moment
to take the dependency.

### Driving it from chat

With a client open, the desk agent can act on their filed PDFs directly:

> "Redact her ID number from the FICA copy"
> "Stamp the FNA as an internal draft"
> "Pull the advice report into an editable draft"

The open document's page text goes into the agent's context, so it can answer
questions about the document as well as act on it.

**A document id is not a licence.** The workbench only ever lists the open
client's documents, so scoping used to be implicit. The agent names a document
from a sentence, and a wrong or invented id would otherwise reach another
client's file — so every call from the chat carries the client, the backend
refuses a mismatch, and the agent is only shown the active client's documents
in the first place. Three layers, because the id now comes from a model.

The refusal is worded exactly like "not found": confirming that a document
exists but belongs to someone else is itself a leak.

An ambiguous filename is refused rather than guessed. Acting on the wrong
document of the right client is still the wrong document.

## One client's file never reaches another client's answer

Client documents are indexed beside the product guides as
`client:<cid>:<file>`. `retrieval.search(client_scope=...)` filters them
**before ranking**, alongside the as-of mask and the room exclusions:

- `client_scope=None` — no client page is retrievable at all
- `client_scope="botha"` — only `client:botha:` pages, plus the shared guides

The default is `None`, so a caller that forgets scoping leaks nothing rather
than everything.

This closes a real leak. The `roa` room previously fell through to "keep every
source", so drafting a Record of Advice for one client could retrieve and cite
a page out of another client's filed FNA — and `span_check` would pass it,
because the figure genuinely was in the retrieved context. It would have read
as a properly cited fact.

`/api/ask` and its `show_only` branch both pass the scope; `show_only` needs it
more, not less, since it returns raw page text straight to the adviser.

`ask._keep_source` is the second layer, and the eval tests the guard through
`search()` rather than the filter alone — a guard that exists but is not wired
in is exactly the failure this suite is for.

## Backing up the vault

The vault is one folder on one machine and FAIS wants records kept five years.
A dead laptop currently costs the practice everything.

```bat
"Backup Vault.bat" E:\FortitudoBackup
```

or directly:

```bat
python backend\vault_backup.py --to E:\FortitudoBackup
python backend\vault_backup.py --verify E:\FortitudoBackup
python backend\vault_backup.py --list E:\FortitudoBackup
python backend\vault_backup.py --restore E:\FortitudoBackup --into C:\vaultcheck
python backend\vault_backup.py --prune E:\FortitudoBackup --keep 12
```

A backup run verifies itself and exits non-zero if it does not check out, so a
scheduled task fails loudly rather than writing rubbish for months.

### Four decisions, each aimed at a way backups fail

**Snapshots, not a mirror.** A mirror propagates a deletion or a corruption —
delete a client file by accident and the next sync destroys the only other
copy. Snapshots are immutable, so an older one still has the file.

**Content-addressed.** Every unique file is stored once under the SHA-256 of
its own contents, so repeat runs copy only what changed, and because an
object's name IS its checksum, silent corruption is detectable.

**The database goes through SQLite, not off the disk.** Copying a live `.db`
mid-write gives a plausible file that will not open — months later, when it is
the only copy left. `-wal`, `-shm` and `-journal` files are skipped for the
same reason.

**Verify and restore are first-class.** `--verify` re-hashes every object any
snapshot references, not just the newest one — an object kept only by an older
snapshot is the copy of a file since deleted from the vault, which is exactly
what snapshots are for, and exactly what a newest-only check would let rot. `restore` refuses a non-empty directory, so a mistyped
command during an emergency cannot eat the vault it is recovering, and it
re-hashes as it writes rather than producing a subtly wrong vault.

### Not encrypted, deliberately

Key management done badly loses an archive more reliably than having no backup
at all. The correct answer is a destination the operating system already
encrypts — BitLocker, FileVault, LUKS. **The archive holds client data in the
clear: treat the destination exactly as you treat the vault.** The archive's own
README says so, for whoever finds the drive.
