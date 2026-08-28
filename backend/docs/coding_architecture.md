# Fortitudo AI — Expert Coding & Architecture Guide

## Design principles

1. **Local-only by default** — Ollama on localhost; client files under configurable `FORTITUDO_CLIENT_DATA_DIR` (not OneDrive).
2. **Auditable storage** — SQLite + numpy vectors; open `data/index.db` in any viewer.
3. **Page-level RAG** — stable citations; tables preserved as pipe-delimited text.
4. **Hybrid retrieval** — dense + BM25 + Reciprocal Rank Fusion (`retrieval.py`).
5. **Role boundary** — prompts state the system is an adviser tool, not the FSP.
6. **Deterministic shells for UX** — website mockups: model fills JSON; HTML/CSS is fixed quality.

## Module map

| Module | Responsibility |
|--------|----------------|
| `config.py` | Paths, models, prompts, env overrides |
| `llm.py` | Ollama HTTP client, embed/chat, think-off, cleanup |
| `store.py` | pages + source_meta, vector cache |
| `retrieval.py` | BM25 index, RRF fusion, synonym expand, context builder |
| `ingest.py` | PDF/text extract, context-enriched embeddings |
| `ask.py` | CLI Q&A |
| `app.py` | Local HTTP desk (clients, ask, drafts, projection) |
| `client_store.py` | Client vault metadata + files |
| `sort_engine.py` | Drop-zone classify/file |
| `website_mockup.py` | Research-backed one-pager generator |
| `drama_app.py` / `drama_store.py` | Stage-2 adjudication companion |

## Coding standards (this repo)

- No cloud APIs in the FA path.
- Prefer explicit errors (`OllamaError`) over silent failure.
- After changing `EMBED_MODEL` or embed input format → `python ingest.py --rebuild`.
- Keep dependencies minimal (`requirements.txt`: pdfplumber, numpy, requests, pyyaml).
- Windows launchers must start Ollama if needed and bind only to 127.0.0.1 for the app server.

## Adding a new knowledge domain (e.g. drama syllabi)

1. Drop PDFs into `docs/` **or** a dedicated folder with a source prefix in ingest.
2. Extend `SYNONYMS` in `retrieval.py` for domain tokens.
3. Optional: separate SQLite path later if index size or confidentiality requires split.
4. Do not mix drama learner PII into FA client vaults.

## Performance checklist (CPU laptop)

- Prefer `llama3.2:3b` or `qwen3:4b` when free RAM is tight.
- `num_ctx` 2048–3072; avoid huge defaults on Qwen3.
- `think: false` / `/no_think` for lookup tasks.
- Close browser/Teams before heavy generation.
- Use `--show` in meetings; generate full answers after.

## Security checklist

- App listens on 127.0.0.1 only.
- No email send in core app until firm-approved integration.
- Client data path outside consumer sync folders when policy requires.
- Treat AI drafts as internal until human review.

## Test discipline

```text
python eval_retrieval.py
python ask.py --show "hearing loss both ears 90 decibels"
python ask.py --sources
```

Golden answers must cite a real page in the indexed guide.
